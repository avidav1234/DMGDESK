"""
cam_tracker.py — Agente CAMTracker per CAM35
=============================================
Monitora Cimatron in esecuzione su CAM35, rileva il progetto attivo,
accumula le ore di lavorazione CAM e invia i dati a DMGDesk via HTTP.

Requisiti:
  pip install requests pythonnet

Modalità di aggancio:
  - PRIMARY:  Cimatron COM API via pythonnet (Interop.CimAppAPI)
  - FALLBACK: Lettura titolo finestra via win32gui (se COM non disponibile)

Avvio:
  python cam_tracker.py

Configurazione via cam_tracker_config.ini (creato automaticamente se assente).
"""

import sys
import os
import re
import time
import json
import configparser
import logging
import socket
import threading
from datetime import datetime, date
from pathlib import Path


# ── Bootstrap .env del progetto (2026-07-18) ────────────────────────────────────
# cam_tracker gira sulla stessa macchina del backend: carica il .env della root
# del progetto in ambiente PRIMA di leggere la config, così DMG_API_KEY (e affini)
# sono disponibili sia a questo agente (Uploader) sia al subprocess estrattore
# cimatron_extract (che eredita l'env del processo). No-op se il .env non c'è
# (deploy separato): in quel caso la chiave resta da env di sistema o dal config.
def _bootstrap_env_progetto():
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    try:
        for raw in env_file.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip().lstrip("﻿")            # tollera BOM sul primo campo
            v = v.strip().strip('"').strip("'")
            if k and k not in os.environ:             # priorità all'env esplicito
                os.environ[k] = v
    except Exception:
        pass  # non bloccare l'avvio se il .env è illeggibile


_bootstrap_env_progetto()

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent
# RotatingFileHandler: max 1MB per file, 5 backup → 6MB totali invece di
# crescita illimitata (era ~50KB/giorno → ~18MB/anno senza rotation).
from logging.handlers import RotatingFileHandler as _RotHandler
_log_handler = _RotHandler(
    LOG_DIR / "cam_tracker.log",
    maxBytes=1024 * 1024,   # 1 MB
    backupCount=5,
    encoding="utf-8",
)
_log_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
_stream_handler = logging.StreamHandler(sys.stdout)
_stream_handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(message)s"))
logging.basicConfig(
    level=logging.INFO,
    handlers=[_log_handler, _stream_handler],
)
log = logging.getLogger("cam_tracker")

# ── Config ─────────────────────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "cam_tracker_config.ini"
SESSIONS_FILE = Path(__file__).parent / "cam_sessions_pending.json"
STATE_FILE = Path(__file__).parent / "cam_tracker_state.json"

DEFAULT_CONFIG = {
    "dmgdesk": {
        "url": "http://localhost:8000",
        "flush_interval_sec": "300",
        "timeout_sec": "5",
        # API key del backend DMGDesk. Vuota = backend in soft mode (nessuna
        # autenticazione, come oggi). Se il backend attiva DMG_API_KEY, mettere
        # qui la stessa chiave (oppure esportarla come env DMG_API_KEY).
        "api_key": "",
    },
    "cimatron": {
        "program_dir": r"C:\Program Files\Cimatron\Cimatron\2025.0\Program",
        "query_exe": r"C:\Program Files\Cimatron\Cimatron\2025.0\Program\cimatron_query.exe",
        "poll_interval_sec": "10",
        # Quando true (default), all'avvio scansiona C:\Program Files\Cimatron\Cimatron\*
        # e sceglie la versione installata piu' recente. Se non trova nulla o e' false,
        # ricade sul program_dir configurato sopra.
        "auto_detect_version": "true",
    },
    "tracker": {
        "workstation": socket.gethostname(),
        "min_session_sec": "10",
        "idle_timeout_min": "5",
    },
    # Estrattore parametri NC via SDK (cimatron_extract.py) — Fase 1
    # iniziativa classificazione percorsi. Gira in SUBPROCESS isolato:
    # un hang/crash COM non tocca mai il tracker.
    "estrattore": {
        "enabled": "true",
        # attesa dopo il cambio documento prima di estrarre (il doc si "assesta")
        "settle_sec": "60",
        # ri-estrazione periodica mentre lo stesso doc resta attivo
        # (cattura l'evoluzione dei parametri durante la programmazione)
        "reextract_min": "30",
        # timeout duro del subprocess di estrazione
        # (v1.3: multi-documento + chiamate MW → più generoso)
        # (2026-07-17: l'offset MW si legge per-procedura via GetProcedureParameter
        #  a ~2s/chiamata → un documento con molte Multi Asse può richiedere >10 min)
        "timeout_sec": "1200",
    },
}


# Base di ricerca per auto-detect: configurabile via env CIMATRON_INSTALL_BASE
# (utile se l'installer Cimatron e' in un path non standard, es. drive D:).
CIMATRON_INSTALL_BASE = Path(
    os.environ.get("CIMATRON_INSTALL_BASE",
                   r"C:\Program Files\Cimatron\Cimatron")
)


def detect_cimatron_installations(base: Path = CIMATRON_INSTALL_BASE) -> list[Path]:
    """Scansiona la base e ritorna i path 'Program' delle installazioni Cimatron
    trovate, ordinati dalla versione piu' alta alla piu' bassa.

    Una installazione e' valida se:
      - <base>/<version>/Program/ esiste
      - contiene almeno CimAppAccess.dll (interfaccia COM principale)

    Versione: cartelle nel formato 'X.Y' (es. '2025.0', '2026.0'). L'ordinamento
    e' lessicografico sui due numeri convertiti in tuple (major, minor): cosi'
    '2026.0' > '2025.0' > '2024.0' senza ambiguita'.
    """
    import re as _re
    if not base.exists() or not base.is_dir():
        return []

    candidates: list[tuple[tuple[int, int], Path]] = []
    for entry in base.iterdir():
        if not entry.is_dir():
            continue
        m = _re.match(r"^(\d+)\.(\d+)$", entry.name)
        if not m:
            continue
        program = entry / "Program"
        if not program.is_dir():
            continue
        # Sanity: la DLL principale deve esserci
        if not (program / "CimAppAccess.dll").exists():
            continue
        try:
            ver = (int(m.group(1)), int(m.group(2)))
        except ValueError:
            continue
        candidates.append((ver, program))

    # Ordina decrescente: versione piu' alta prima
    candidates.sort(key=lambda x: x[0], reverse=True)
    return [p for _, p in candidates]


def resolve_cimatron_program_dir(cfg: configparser.ConfigParser) -> str:
    """Sceglie il program_dir effettivo dal config:
      1. Se auto_detect_version=true → versione piu' recente installata
      2. Altrimenti, o se auto-detect non trova nulla → program_dir configurato

    Logga sempre la scelta finale per facilitare il debug.
    """
    auto = cfg.getboolean("cimatron", "auto_detect_version", fallback=True)
    configured = cfg.get("cimatron", "program_dir", fallback="").strip()

    if auto:
        found = detect_cimatron_installations()
        if found:
            chosen = str(found[0])
            others = [str(p) for p in found[1:]]
            if others:
                log.info(
                    f"[Cimatron] Auto-detect: scelta {chosen} "
                    f"(altre installate: {', '.join(others)})"
                )
            else:
                log.info(f"[Cimatron] Auto-detect: scelta {chosen} (unica installata)")
            return chosen
        log.warning(
            f"[Cimatron] Auto-detect attivo ma nessuna installazione trovata in "
            f"{CIMATRON_INSTALL_BASE} — fallback a program_dir configurato"
        )

    if configured:
        log.info(f"[Cimatron] Uso program_dir configurato: {configured}")
        return configured

    log.warning("[Cimatron] Nessun program_dir disponibile (ne' auto-detect ne' config)")
    return DEFAULT_CONFIG["cimatron"]["program_dir"]


def detect_runtime_cimatron_dir() -> Path | None:
    """Rileva quale installazione Cimatron e' ATTUALMENTE in esecuzione.

    Logica:
      1. Cerca processi 'CimatronE.exe' attivi (psutil)
      2. Estrai il path completo dell'eseguibile
      3. Se contiene '....\\Cimatron\\<X.Y>\\Program\\CimatronE.exe' ritorna quel Program dir
      4. Se nessun processo o errore -> None (caller usa default)

    Ritorna sempre il path 'Program' (mai 'CimatronE.exe' stesso).
    Se ci sono piu' istanze, prende la PRIMA (l'utente in genere usa una versione alla volta).
    """
    try:
        import psutil
    except ImportError:
        return None
    try:
        for proc in psutil.process_iter(["name", "exe"]):
            try:
                name = (proc.info.get("name") or "").lower()
                if name != "cimatrone.exe":
                    continue
                exe = proc.info.get("exe") or ""
                if not exe:
                    continue
                p = Path(exe).parent  # ...\Cimatron\X.Y\Program
                # Verifica che corrisponda al pattern atteso (sanity check)
                if p.name.lower() == "program" and (p / "CimAppAccess.dll").exists():
                    return p
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
    except Exception as e:
        log.debug(f"[Cimatron] detect_runtime_cimatron_dir error: {e}")
    return None


def load_config() -> configparser.ConfigParser:
    cfg = configparser.ConfigParser()
    cfg.read_dict(DEFAULT_CONFIG)
    if CONFIG_FILE.exists():
        cfg.read(CONFIG_FILE, encoding="utf-8")
    else:
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            cfg.write(f)
        log.info(f"Config creata: {CONFIG_FILE}")
    return cfg


# ── Backend connector ──────────────────────────────────────────────────────────
class DMGDeskClient:
    def __init__(self, base_url: str, timeout: int, api_key: str = ""):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.api_key = (api_key or "").strip()

    def _headers(self) -> dict:
        # Header X-API-Key solo se la chiave e' configurata: a vuoto la
        # richiesta e' identica a prima (backend in soft mode).
        return {"X-API-Key": self.api_key} if self.api_key else {}

    def ping(self) -> bool:
        try:
            import requests
            # /health e' pubblico, ma passiamo comunque l'header per coerenza.
            r = requests.get(f"{self.base_url}/health", timeout=self.timeout,
                             headers=self._headers())
            return r.status_code == 200
        except Exception:
            return False

    def send_sessions(self, payload: dict) -> bool:
        try:
            import requests
            r = requests.post(
                f"{self.base_url}/api/cam-tracker/sessions",
                json=payload,
                timeout=self.timeout,
                headers=self._headers(),
            )
            if r.status_code == 200:
                log.info(f"[DMGDesk] Inviati {len(payload['sessions'])} record — OK")
                return True
            else:
                log.warning(f"[DMGDesk] HTTP {r.status_code}: {r.text[:200]}")
                return False
        except Exception as e:
            log.warning(f"[DMGDesk] Connessione fallita: {e}")
            return False


# ── Cimatron daemon adapter ────────────────────────────────────────────────────
class CimatronCOMAdapter:
    """
    Interroga Cimatron tramite cimatron_daemon.exe — processo persistente.

    Il daemon viene avviato una volta sola, carica le DLL COM, e risponde
    alle query via stdin/stdout. Elimina il costo di avvio/chiusura ad ogni
    poll e i timeout durante i calcoli NC.

    Fallback: cimatron_query.exe (vecchio metodo, un processo per query).
    """

    def __init__(self, program_dir: str):
        self.program_dir = program_dir
        self._available  = False
        self._mode       = None        # "daemon" | "exe" | "com"
        self._last_timeout = False

        # Path exe
        self._daemon_exe = None
        self._query_exe  = Path(__file__).parent / "cimatron_query.exe"

        # Processo daemon
        self._proc   = None            # subprocess.Popen
        self._ready  = False           # daemon ha mandato READY
        self._errors = 0               # errori consecutivi

        # Runtime switch (auto-detect quale Cimatron e' aperto)
        # Check ogni RUNTIME_CHECK_INTERVAL secondi via detect_runtime_cimatron_dir().
        # Se versione runtime != versione daemon, kill+restart daemon con DLL corrette.
        self._last_runtime_check = 0.0
        self.RUNTIME_CHECK_INTERVAL = 30.0

    def try_connect(self) -> bool:
        """Trova il metodo di connessione migliore disponibile."""

        # ── Metodo 1: cimatron_daemon.exe (preferito) ──────────────────────
        cim_daemon = Path(self.program_dir) / "cimatron_daemon.exe"
        loc_daemon = Path(__file__).parent / "cimatron_daemon.exe"
        # Anche .py funziona se pythonnet è installato in Cimatron
        loc_daemon_py = Path(__file__).parent / "cimatron_daemon.py"

        for candidate in [cim_daemon, loc_daemon]:
            if candidate.exists():
                self._daemon_exe = candidate
                self._available  = True
                self._mode       = "daemon"
                log.info(f"[Cimatron] Daemon: {candidate}")
                self._start_daemon()
                return True

        # ── Metodo 2: cimatron_query.exe (fallback) ────────────────────────
        cim_exe   = Path(self.program_dir) / "cimatron_query.exe"
        local_exe = Path(__file__).parent / "cimatron_query.exe"

        for candidate in [cim_exe, local_exe]:
            if candidate.exists():
                self._query_exe  = candidate
                self._available  = True
                self._mode       = "exe"
                log.info(f"[Cimatron] EXE (legacy): {candidate}")
                return True

        # ── Metodo 3: pythonnet diretto ────────────────────────────────────
        try:
            sys.path.insert(0, self.program_dir)
            import clr
            clr.AddReference("interop.CimatronE")
            from interop.CimatronE import CimApplicationClass
            self.app = CimApplicationClass()
            _ = self.app.ActiveDocument
            self._available = True
            self._mode = "com"
            log.info("[Cimatron COM] Connesso via pythonnet")
            return True
        except Exception:
            pass

        log.warning("[Cimatron] Nessun metodo disponibile")
        return False

    # ── Daemon lifecycle ───────────────────────────────────────────────────

    def _start_daemon(self):
        """Avvia cimatron_daemon.exe come processo figlio persistente.

        Passa al daemon il program_dir scelto dal tracker (auto-detect 2026 → 2025)
        sia come argv[1] sia come env CIMATRON_PROGRAM_DIR. Il daemon .py
        aggiornato lo legge dalla precedenza argv > env > default hardcoded.
        L'EXE precompilato vecchio ignora gli argv e usa il proprio path interno —
        funziona ugualmente (retrocompat).
        """
        import subprocess
        import threading
        try:
            env = os.environ.copy()
            env["CIMATRON_PROGRAM_DIR"] = self.program_dir
            self._proc = subprocess.Popen(
                [str(self._daemon_exe), self.program_dir],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
                env=env,
            )
            # Aspetta READY su stdout con timeout di 20s
            # Leggi tutte le righe finché non troviamo READY o errore.
            # NOTA: rimossi 'import select' e 'import os' locali — erano inutili e
            # l'import 'os' locale creava UnboundLocalError sul .copy() qui sopra
            # (Python: import dentro funzione rende il nome LOCALE per tutto lo scope).
            import time
            deadline = time.time() + 20
            while time.time() < deadline:
                if self._proc.poll() is not None:
                    log.warning("[Cimatron Daemon] Processo terminato durante avvio")
                    self._proc = None
                    self._mode = "exe"
                    return
                line = self._proc.stdout.readline()
                if not line:
                    time.sleep(0.1)
                    continue
                line = line.strip()
                if line == "READY":
                    self._ready = True
                    log.info("[Cimatron Daemon] Avviato e pronto")
                    return
                elif line.startswith("ERROR"):
                    log.warning(f"[Cimatron Daemon] Errore avvio: {line}")
                    self._proc = None
                    self._mode = "exe"
                    return
                # Altre righe (log) — ignora e continua
            log.warning("[Cimatron Daemon] Timeout avvio — fallback exe")
            self._proc = None
            self._mode = "exe"
        except Exception as e:
            log.warning(f"[Cimatron Daemon] Impossibile avviare: {e}")
            self._proc = None
            self._mode = "exe"

    def _ensure_daemon(self):
        """Riavvia il daemon se è morto."""
        if self._proc and self._proc.poll() is None:
            return True  # ancora vivo
        log.info("[Cimatron Daemon] Riavvio daemon...")
        self._ready = False
        self._start_daemon()
        return self._ready

    def _query_daemon(self) -> dict | None:
        """Invia "?" al daemon e legge la risposta."""
        self._last_timeout = False
        if not self._ensure_daemon():
            return None
        try:
            self._proc.stdin.write("?\n")
            self._proc.stdin.flush()
            # Risposta immediata — nessun timeout perché già connesso
            line = self._proc.stdout.readline()
            if not line:
                # Daemon morto
                self._proc = None
                return None
            full_path = line.strip()
            if not full_path or full_path.startswith("ERROR"):
                self._errors += 1
                return None
            self._errors = 0
            proj = parse_project_from_path(full_path)
            return proj
        except Exception as e:
            log.debug(f"[Cimatron Daemon] Errore query: {e}")
            self._proc = None
            return None

    def shutdown(self):
        """Chiude il daemon alla fine del tracker."""
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.write("exit\n")
                self._proc.stdin.flush()
                self._proc.wait(timeout=3)
            except Exception:
                self._proc.kill()
            log.info("[Cimatron Daemon] Chiuso")

    # ── Interfaccia pubblica ───────────────────────────────────────────────

    def _check_runtime_switch(self):
        """Se Cimatron in esecuzione e' di una versione diversa da quella su cui e'
        connesso il daemon corrente, fa lo switch: kill daemon, riavvia con DLL
        della versione runtime.

        Cache: chiamato max ogni RUNTIME_CHECK_INTERVAL secondi (default 30s) per
        non sprecare CPU su process_iter.
        Costo: ~10-20ms quando esegue, 0 quando in cache.
        Sicurezza: se nessun Cimatron in esecuzione o psutil mancante, non fa nulla.
        """
        import time as _t
        now = _t.monotonic()
        if now - self._last_runtime_check < self.RUNTIME_CHECK_INTERVAL:
            return
        self._last_runtime_check = now

        runtime_dir = detect_runtime_cimatron_dir()
        if runtime_dir is None:
            return  # nessun Cimatron in esecuzione, o psutil mancante: niente da fare

        try:
            current = Path(self.program_dir).resolve()
            target  = runtime_dir.resolve()
        except Exception:
            return
        if current == target:
            return  # gia' allineati

        # Switch necessario
        log.info(
            f"[Cimatron] Switch daemon richiesto: {current.parent.name} → "
            f"{target.parent.name} (Cimatron in esecuzione: {target})"
        )

        # 1) Chiudi daemon corrente (graceful poi force)
        if self._proc and self._proc.poll() is None:
            try:
                self._proc.stdin.write("exit\n")
                self._proc.stdin.flush()
                self._proc.wait(timeout=2)
            except Exception:
                try: self._proc.kill()
                except Exception: pass
        self._proc = None
        self._ready = False

        # 2) Aggiorna paths
        self.program_dir = str(target)
        new_daemon = target / "cimatron_daemon.exe"
        if new_daemon.exists():
            self._daemon_exe = new_daemon
        else:
            # Daemon non presente nella nuova versione → fallback locale
            loc_daemon = Path(__file__).parent / "cimatron_daemon.exe"
            if loc_daemon.exists():
                self._daemon_exe = loc_daemon
                log.warning(
                    f"[Cimatron] Daemon non trovato in {target}, uso fallback locale {loc_daemon}"
                )
            else:
                log.warning(
                    f"[Cimatron] Daemon non disponibile per versione runtime {target}, "
                    f"tracker resta senza COM (title parsing only)"
                )
                self._available = False
                return

        # 3) Riavvia daemon con nuovo path (passato come argv[1])
        self._available = True
        self._mode = "daemon"
        self._start_daemon()

    def get_active_project(self) -> dict | None:
        if not self._available:
            return None
        if self._mode == "daemon":
            self._check_runtime_switch()  # adatta daemon alla versione Cimatron runtime
        if self._mode == "daemon":
            return self._query_daemon()
        elif self._mode == "exe":
            return self._query_via_exe()
        else:
            return self._query_via_com()

    def _query_via_exe(self) -> dict | None:
        """Fallback: lancia cimatron_query.exe per ogni query."""
        import subprocess
        self._last_timeout = False
        try:
            result = subprocess.run(
                [str(self._query_exe)],
                capture_output=True, text=True, timeout=8
            )
            full_path = result.stdout.strip()
            if not full_path or full_path.startswith("ERROR"):
                return None
            proj = parse_project_from_path(full_path)
            if proj:
                log.debug(f"[Cimatron EXE] path={full_path} → {proj['project_id']}")
            return proj
        except subprocess.TimeoutExpired:
            log.warning("[Cimatron EXE] timeout")
            self._last_timeout = True
            return None
        except Exception as e:
            log.debug(f"[Cimatron EXE] {e}")
            return None

    def _query_via_com(self) -> dict | None:
        """Fallback: pythonnet diretto."""
        try:
            doc = self.app.ActiveDocument
            if doc is None:
                return None
            full_path = str(doc.FullName)
            return parse_project_from_path(full_path)
        except Exception:
            return None


# ── Parser path → commessa/operazione ─────────────────────────────────────────
def parse_project_from_path(full_path: str) -> dict | None:
    """
    Estrae commessa e operazione dal path del file CAM.

    Strutture supportate:
      C:\\Lavoro\\4348\\P0221\\file.elt   → commessa=4348, op=0221, id=4348_0221
      H:\\...\\4349\\0301\\file.elt       → commessa=4349, op=0301, id=4349_0301

    La P iniziale nelle cartelle operazione (P0221, P7221) viene rimossa
    per allinearsi ai nomi progetto in DMGDesk (es. 4348_0221).
    """
    p = Path(full_path)
    parts = p.parts

    if len(parts) < 4:
        return None

    operazione_raw = parts[-2]   # es. P0221
    commessa       = parts[-3]   # es. 4348

    # Esclude cartelle generiche troppo lunghe o con spazi
    if len(commessa) > 10 or ' ' in commessa:
        return None

    # Normalizza: P0221 → 0221, P7221 → 7221, 0301 → 0301
    op_norm = re.sub(r'^[Pp](\d)', r'\1', operazione_raw)

    project_id = f"{commessa}_{op_norm}".upper()

    return {
        "commessa":   commessa.upper(),
        "operazione": op_norm.upper(),
        "project_id": project_id,
        "full_path":  full_path,
    }


def parse_project_from_title(title_name: str) -> dict:
    """
    Fallback: dal nome nel titolo finestra (es. E541540221_0221_A#1_V3)
    tenta di estrarre commessa e operazione.

    Se il nome inizia con 4 cifre (commessa numerica tipo 4348),
    splitta su _ per ottenere commessa_operazione → allineato a DMGDesk.
    Altrimenti usa il nome intero.
    """
    # Caso: 4348_0221_xxx → commessa=4348, op=0221, id=4348_0221
    m = re.match(r'^(\d{4})_(\d{4})', title_name)
    if m:
        commessa   = m.group(1)
        operazione = m.group(2)
        return {
            "commessa":   commessa,
            "operazione": operazione,
            "project_id": f"{commessa}_{operazione}",
            "full_path":  None,
        }

    # Caso generico: XXXX_YYYY → split primo underscore
    parts = title_name.split("_", 1)
    if len(parts) == 2:
        return {
            "commessa":   parts[0],
            "operazione": parts[1],
            "project_id": title_name,
            "full_path":  None,
        }
    return {
        "commessa":   title_name,
        "operazione": "",
        "project_id": title_name,
        "full_path":  None,
    }




CIMATRON_PATTERNS = [
    # Prima cerca NC-Standard (file reali), esclude il simulatore
    # "Cimatron 2025.0 SP4P1 - [E541540221_0221_A#1_V3 : NC-Standard]"
    r"\[([^\]:]+?)\s*:\s*NC-Standard\s*\]",
    # Fallback: qualsiasi parentesi quadra tranne il simulatore
    r"\[(?!CimExtSimul)([^\]:]+?)\s*:\s*[^\]]+\]",
    # Formato vecchio "Cimatron 2024 — FLANGIA_BASE.elt"
    r"Cimatron\s+\S+\s*[-–—]\s*(.+?)(?:\.elt|\.icd)?$",
]


# ── Activity monitor ───────────────────────────────────────────────────────────
class ActivityMonitor:
    """
    Determina se il tempo va contato combinando 3 segnali:
      1. Mouse/tastiera attivi negli ultimi idle_timeout_sec secondi
      2. Cimatron è la finestra in foreground
      3. (implicito) Cimatron ha un documento aperto — gestito dal tracker

    Usa GetLastInputInfo (win32, zero dipendenze extra).
    """

    def __init__(self, idle_timeout_sec: int = 300):
        self.idle_timeout_sec = idle_timeout_sec
        self._ctypes_ok = False
        try:
            import ctypes
            self._ctypes = ctypes
            self._ctypes_ok = True
        except ImportError:
            log.warning("[Activity] ctypes non disponibile — idle detection disabilitata")

    def seconds_since_last_input(self) -> float:
        """Secondi dall'ultimo evento mouse/tastiera."""
        if not self._ctypes_ok:
            return 0.0
        try:
            ctypes = self._ctypes

            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", ctypes.c_uint), ("dwTime", ctypes.c_uint)]

            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(LASTINPUTINFO)
            ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii))
            tick_now = ctypes.windll.kernel32.GetTickCount()
            idle_ms = (tick_now - lii.dwTime) & 0xFFFFFFFF  # gestisce wraparound
            return max(0.0, idle_ms / 1000.0)
        except Exception as e:
            log.debug(f"[Activity] GetLastInputInfo: {e}")
            return 0.0

    def is_cimatron_foreground(self) -> bool:
        """True se Cimatron ha il focus."""
        try:
            import win32gui
            import win32process
            import psutil
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return False
            _, pid = win32process.GetWindowThreadProcessId(hwnd)
            name = psutil.Process(pid).name().lower()
            return "cimatron" in name
        except Exception:
            try:
                import win32gui
                title = win32gui.GetWindowText(win32gui.GetForegroundWindow())
                return "Cimatron" in title
            except Exception:
                return True  # fallback permissivo se win32 non disponibile

    def is_cimatron_foreground(self) -> bool:
        """True se una finestra Cimatron ha il focus."""
        try:
            import win32gui
            hwnd = win32gui.GetForegroundWindow()
            if not hwnd:
                return False
            title = win32gui.GetWindowText(hwnd)
            result = "cimatron" in title.lower()
            if not result:
                log.debug(f"[Activity] Foreground: '{title}' — non è Cimatron")
            return result
        except Exception:
            return True  # fallback permissivo se win32 non disponibile

    def is_active(self) -> tuple[bool, str]:
        """
        Ritorna (conta_tempo, descrizione).
        Conta il tempo solo se Cimatron è in foreground E c'è stato input recente.
        """
        idle_sec = self.seconds_since_last_input()

        if idle_sec > self.idle_timeout_sec:
            mins = idle_sec / 60
            return False, f"idle {mins:.1f}min (soglia={self.idle_timeout_sec//60}min)"

        if not self.is_cimatron_foreground():
            return False, f"Cimatron non in foreground (idle={idle_sec:.0f}s)"

        return True, f"attivo (idle={idle_sec:.0f}s)"


class WindowTitleAdapter:
    """Fallback: legge il titolo della finestra attiva di Windows."""

    def __init__(self):
        self._win32_ok = False
        try:
            import win32gui  # pywin32
            self._win32_ok = True
            log.info("[WindowTitle] Adapter win32gui pronto")
        except ImportError:
            log.warning("[WindowTitle] pywin32 non installato — rilevamento limitato")

    def get_active_project(self) -> dict | None:
        if not self._win32_ok:
            return None
        try:
            import win32gui

            fg_hwnd = win32gui.GetForegroundWindow()
            nc_windows = []

            def enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if "Cimatron" in t and "NC-Standard" in t and "CimExtSimul" not in t:
                        nc_windows.append((hwnd, t))

            win32gui.EnumWindows(enum_cb, None)
            nc_windows.sort(key=lambda x: 0 if x[0] == fg_hwnd else 1)

            for _, title in nc_windows:
                for pat in CIMATRON_PATTERNS:
                    m = re.search(pat, title, re.IGNORECASE)
                    if m:
                        name = m.group(1).strip()
                        name = re.sub(r'\s+', '_', name).upper()
                        return parse_project_from_title(name)
        except Exception as e:
            log.debug(f"[WindowTitle] {e}")
        return None


# ── Core tracker ───────────────────────────────────────────────────────────────
class CAMTracker:
    def __init__(self, cfg: configparser.ConfigParser):
        self.cfg = cfg
        self.workstation = cfg["tracker"]["workstation"]
        self.min_session_sec = int(cfg["tracker"]["min_session_sec"])
        self.flush_interval = int(cfg["dmgdesk"]["flush_interval_sec"])
        self.poll_interval = int(cfg["cimatron"]["poll_interval_sec"])
        idle_timeout_min = int(cfg["tracker"].get("idle_timeout_min", "5"))

        # Stato corrente
        self.current_project: dict | None = None
        self.session_start: float | None = None
        self.is_paused: bool = False  # True quando idle/non in foreground

        # Accumulatore: {project_id: secondi_totali_oggi}
        self.accumulated: dict[str, float] = {}
        self.project_meta: dict[str, dict] = {}
        # STEP già analizzati in questa sessione (evita invii doppi)
        self._step_analizzati: set = set()

        # Backend — API key da env DMG_API_KEY (precedenza) o dal config.
        api_key = os.environ.get("DMG_API_KEY") or cfg["dmgdesk"].get("api_key", "")
        self.client = DMGDeskClient(
            cfg["dmgdesk"]["url"],
            int(cfg["dmgdesk"]["timeout_sec"]),
            api_key=api_key,
        )

        # Estrattore parametri NC (subprocess isolato, vedi cimatron_extract.py)
        self.estrattore_enabled = cfg["estrattore"].get("enabled", "true").lower() == "true"
        self.estrattore_settle = int(cfg["estrattore"].get("settle_sec", "60"))
        self.estrattore_reextract = int(cfg["estrattore"].get("reextract_min", "30")) * 60
        self.estrattore_timeout = int(cfg["estrattore"].get("timeout_sec", "1200"))
        self._estrazioni: dict[str, float] = {}   # doc/proj_id -> ts ultima estrazione
        self._estrazione_lock = threading.Lock()  # una sola estrazione alla volta
        self._estrazione_in_corso = False

        # Adapter Cimatron (COM → window fallback)
        self.com = CimatronCOMAdapter(resolve_cimatron_program_dir(cfg))
        self.window = WindowTitleAdapter()
        self.activity = ActivityMonitor(idle_timeout_sec=idle_timeout_min * 60)

        self._com_tried = False
        self._stop = threading.Event()

        # GUI opzionale
        self.gui = None
        self._gui_thread = None
        self._init_gui()

        # Recovery da crash/shutdown precedente
        self._load_state()

    def _init_gui(self):
        """Avvia la finestra di stato in un thread separato (solo se tkinter disponibile)."""
        try:
            from cam_tracker_gui import TrackerGUI
            def _run():
                self.gui = TrackerGUI()
                self.gui.run()
            self._gui_thread = threading.Thread(target=_run, daemon=True)
            self._gui_thread.start()
            # Aspetta che la GUI sia pronta
            import time as _t
            for _ in range(20):
                if self.gui is not None:
                    break
                _t.sleep(0.1)
        except Exception as e:
            log.debug(f"[GUI] Non disponibile: {e}")

    def _gui(self, method: str, *args):
        """Chiama un metodo della GUI in modo sicuro (ignora se GUI non disponibile)."""
        try:
            if self.gui:
                getattr(self.gui, method)(*args)
        except Exception:
            pass

    def _get_project(self) -> dict | None:
        """
        Tenta daemon/EXE/COM prima (path completo → commessa affidabile).
        Fallback al titolo finestra SOLO se nessun metodo COM è disponibile.
        """
        if not self._com_tried:
            self.com.try_connect()
            self._com_tried = True

        p = self.com.get_active_project()
        if p:
            # Valida: accetta solo commesse numeriche (4 cifre iniziali)
            commessa = p.get("commessa", "")
            if commessa and re.match(r'^\d{4}', commessa):
                return p
            # Commessa non valida (es. E541540221, 1D24103D...) — Cimatron aperto
            # ma senza un progetto valido (finestra vuota o documento non strutturato)
            # Ritorna None — non fare fallback al titolo (darebbe stesso risultato)
            return None

        # EXE/COM non disponibile o timeout → fallback al titolo
        # Ma non se il daemon è attivo (in quel caso ha già risposto sopra)
        if self.com._mode == "daemon":
            # Daemon attivo ma nessun documento valido → nessun progetto
            if getattr(self.com, '_last_timeout', False):
                return self.current_project
            return None

        # Solo per modalità exe/com legacy
        if getattr(self.com, '_last_timeout', False):
            return self.current_project

        return self.window.get_active_project()

    def _project_id(self, proj: dict | None) -> str | None:
        return proj["project_id"] if proj else None

    def tick(self):
        proj = self._get_project()
        proj_id = self._project_id(proj)
        now = time.time()

        # ── Controllo attività ────────────────────────────────────────────────
        # Il tempo conta SOLO se: progetto rilevato + operatore attivo al PC
        if proj:
            active, reason = self.activity.is_active()
        else:
            active, reason = False, "nessun progetto"

        # Gestione pausa/ripresa
        if self.current_project:
            if self.session_start and not active and not self.is_paused:
                # Entra in pausa — accumula sempre, anche micro-burst.
                # I cicli foreground/background da pochi secondi sono lavoro
                # reale: scartarli sotto soglia produce perdita aggregata.
                elapsed = now - self.session_start
                pid = self._project_id(self.current_project)
                if elapsed > 0:
                    self.accumulated[pid] = self.accumulated.get(pid, 0) + elapsed
                    self.project_meta[pid] = self.current_project
                    self._persist_state()
                self.session_start = None
                self.is_paused = True
                log.info(f"[Tracker] PAUSA — {reason} (+{elapsed:.1f}s)")
                self._gui("set_progetto", pid, False)
                self._gui("add_log", f"Pausa — {pid}", "info")

            elif active and self.is_paused:
                # Ripresa — funziona anche se session_start era None
                self.session_start = now
                self.is_paused = False
                pid = self._project_id(self.current_project)
                log.info(f"[Tracker] RIPRESA — {reason}")
                self._gui("set_progetto", pid, True)
                self._gui("add_log", f"Ripresa — {pid}", "ok")

        # ── Cambio progetto ───────────────────────────────────────────────────
        if proj_id != self._project_id(self.current_project):
            if self.current_project and self.session_start and not self.is_paused:
                elapsed = now - self.session_start
                pid = self._project_id(self.current_project)
                if elapsed > 0:
                    self.accumulated[pid] = self.accumulated.get(pid, 0) + elapsed
                    self.project_meta[pid] = self.current_project
                    self._persist_state()
                    log.info(
                        f"[Tracker] {pid}: "
                        f"+{elapsed/60:.1f} min "
                        f"(tot oggi: {self.accumulated[pid]/3600:.2f}h)"
                    )

            self.current_project = proj
            self.is_paused = not active
            self.session_start = now if (proj and active) else None

            if proj:
                log.info(
                    f"[Tracker] Progetto → commessa={proj['commessa']} op={proj['operazione']} "
                    f"| {reason}"
                )
                self._gui("set_progetto", proj_id, active)
                self._gui("add_log",
                          f"{proj['commessa']}_{proj['operazione']} — {'attivo' if active else 'in foreground'}",
                          "ok" if active else "info")

                # ── Auto-analisi STEP in background ───────────────────────────
                full_path = proj.get("full_path")
                if full_path and proj_id not in self._step_analizzati:
                    threading.Thread(
                        target=self._analizza_step_background,
                        args=(proj_id, full_path),
                        daemon=True
                    ).start()

                # ── Estrazione parametri NC al cambio documento ───────────────
                self._pianifica_estrazione(proj_id, attesa=self.estrattore_settle)
            else:
                log.debug("[Tracker] Nessun progetto Cimatron")
                self._gui("set_progetto", "—", False)

        # ── Ri-estrazione periodica mentre lo stesso doc resta attivo ─────────
        # (cattura l'evoluzione dei parametri; l'ultima versione prima della
        # chiusura è quella che conta per il classificatore)
        if (self.current_project and proj_id
                and now - self._estrazioni.get(proj_id, 0) >= self.estrattore_reextract):
            self._pianifica_estrazione(proj_id, attesa=0)

        # ── Tick incrementale: consolida la sessione attiva ad ogni poll ──────
        # Senza questo, i secondi della sessione in corso (tra una pausa e
        # l'altra, o tra due flush) vivrebbero solo in `session_start` e
        # andrebbero persi su crash. Spostando il delta in `accumulated` ad
        # ogni tick e ri-azzerando `session_start`, lo state persistito su
        # disco rimane sempre allineato al secondo.
        if self.current_project and self.session_start and not self.is_paused:
            elapsed = now - self.session_start
            if elapsed > 0:
                pid = self._project_id(self.current_project)
                self.accumulated[pid] = self.accumulated.get(pid, 0) + elapsed
                self.project_meta[pid] = self.current_project
                self.session_start = now
                self._persist_state()

    def _analizza_step_background(self, project_id: str, full_path: str):
        """
        Cerca un file .stp/.step nella cartella del progetto Cimatron
        e lo manda allo STEP Analyzer in background.
        Chiamato in un thread separato — non blocca il tracker.
        """
        try:
            import requests as _req
            cartella = Path(full_path).parent
            stp = None
            for ext in ("*.stp", "*.STP", "*.step", "*.STEP"):
                trovati = list(cartella.glob(ext))
                if trovati:
                    stp = trovati[0]
                    break
            if not stp:
                log.warning(f"[STEP] Nessun file .stp in {cartella}")
                return

            log.info(f"[STEP] Trovato {stp.name} per {project_id} — invio a STEP Analyzer")
            url = f"{self.cfg['dmgdesk']['url'].rstrip('/')}/api/step/analizza-upload"
            # Header X-API-Key: come gli altri upload, serve quando l'auth è attiva.
            _key = os.environ.get("DMG_API_KEY", "").strip()
            _hdr = {"X-API-Key": _key} if _key else {}
            with open(stp, "rb") as f:
                resp = _req.post(url, files={"file": (stp.name, f, "application/octet-stream")},
                                 data={"commessa": project_id}, headers=_hdr, timeout=180)
            if resp.ok:
                d = resp.json()
                log.info(f"[STEP] {project_id} analizzato — "
                         f"{d.get('features',{}).get('n_facce')} facce, "
                         f"{d.get('features',{}).get('n_cilindri')} cilindri "
                         f"({'cache' if d.get('cached') else 'nuovo'})")
                # Segna come analizzato per non riprovare
                self._step_analizzati.add(project_id)
            else:
                log.warning(f"[STEP] Errore analisi {project_id}: {resp.status_code} — {resp.text[:200]}")
        except Exception as e:
            log.warning(f"[STEP] Analisi background fallita per {project_id}: {e}")
        except Exception as e:
            log.warning(f"[STEP] Analisi background fallita per {project_id}: {e}")

    # ── Estrazione parametri NC (Fase 1 classificazione percorsi) ─────────────

    def _pianifica_estrazione(self, proj_id: str, attesa: int = 0):
        """
        Pianifica un'estrazione parametri per il documento attivo, in thread +
        SUBPROCESS isolato (cimatron_extract.py): un hang/crash COM non tocca
        il tracker. Il timestamp è segnato SUBITO per non ri-pianificare ad
        ogni tick durante l'attesa di assestamento.
        """
        if not self.estrattore_enabled or not proj_id:
            return
        with self._estrazione_lock:
            if self._estrazione_in_corso:
                return
            self._estrazione_in_corso = True
            self._estrazioni[proj_id] = time.time()
        threading.Thread(
            target=self._estrai_parametri_background,
            args=(proj_id, attesa),
            daemon=True,
        ).start()

    def _estrai_parametri_background(self, proj_id: str, attesa: int):
        import subprocess as _sp
        try:
            if attesa > 0:
                # attesa di assestamento; se nel frattempo il tracker si ferma, esci
                if self._stop.wait(attesa):
                    return
            script = Path(__file__).parent / "cimatron_extract.py"
            out_dir = Path(__file__).parent / "parametri_cam"
            cmd = [sys.executable, str(script),
                   "--out", str(out_dir),
                   "--invia", self.cfg["dmgdesk"]["url"]]
            log.info(f"[Estrattore] avvio estrazione per {proj_id}")
            r = _sp.run(cmd, capture_output=True, text=True,
                        timeout=self.estrattore_timeout,
                        creationflags=0x08000000)  # CREATE_NO_WINDOW
            esito = (r.stdout or "").strip().splitlines()
            riga = esito[0] if esito else f"exit {r.returncode}"
            if r.returncode == 0:
                log.info(f"[Estrattore] {riga}")
                self._gui("add_log", f"Parametri estratti — {proj_id}", "ok")
            else:
                # SKIP legittimi (doc non NC, Cimatron chiuso) o errori veri:
                # loggati ma senza allarmare, l'estrazione ritenta al prossimo giro
                log.warning(f"[Estrattore] {riga}")
        except _sp.TimeoutExpired:
            log.warning(f"[Estrattore] timeout ({self.estrattore_timeout}s) per {proj_id} "
                        "— Cimatron occupato? ritenterà al prossimo ciclo")
        except Exception as e:
            log.warning(f"[Estrattore] fallita per {proj_id}: {e}")
        finally:
            with self._estrazione_lock:
                self._estrazione_in_corso = False

    def flush(self):
        """Chiude la sessione corrente e invia a DMGDesk."""
        now = time.time()
        if self.current_project and self.session_start:
            elapsed = now - self.session_start
            pid = self._project_id(self.current_project)
            if elapsed > 0:
                self.accumulated[pid] = self.accumulated.get(pid, 0) + elapsed
                self.project_meta[pid] = self.current_project
            self.session_start = now

        if not self.accumulated:
            return

        payload = {
            "source": "cimatron",
            "workstation": self.workstation,
            "date": date.today().isoformat(),
            "flushed_at": datetime.now().isoformat(),
            "sessions": [
                {
                    "project":    pid,
                    "commessa":   self.project_meta.get(pid, {}).get("commessa", pid),
                    "operazione": self.project_meta.get(pid, {}).get("operazione", ""),
                    "full_path":  self.project_meta.get(pid, {}).get("full_path"),
                    "seconds":    int(secs),
                    "hours":      round(secs / 3600, 3),
                }
                for pid, secs in self.accumulated.items()
            ],
        }

        ok = self.client.send_sessions(payload)
        if not ok:
            # Salva localmente per retry — _retry_pending() lo manderà più tardi
            self._save_pending(payload)
            log.warning("[Tracker] Payload salvato localmente — retry al prossimo flush")

        # In ogni caso (ok o pending), i secondi sono ora "consolidati" nel payload.
        # Pulire accumulated evita il doppio conteggio quando il pending viene
        # rinviato e nel frattempo nuovi secondi sono stati cumulati e flushati.
        self.accumulated.clear()
        self._persist_state()

        if ok:
            ts = datetime.now().strftime("%H:%M:%S")
            n  = len(payload["sessions"])
            self._gui("set_ultimo_invio", ts, n)
            self._gui("add_log", f"Inviati {n} record a DMGDesk", "ok")
            self._gui("set_ore", {})

    def _save_pending(self, payload: dict):
        existing = []
        if SESSIONS_FILE.exists():
            try:
                with open(SESSIONS_FILE, encoding="utf-8") as f:
                    existing = json.load(f)
            except Exception:
                pass
        existing.append(payload)
        with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
            json.dump(existing, f, indent=2, ensure_ascii=False)

    def _persist_state(self):
        """
        Salva accumulated su disco — recovery dopo crash/shutdown forzato.
        Senza questo, fino a flush_interval secondi (e tutti i progetti in
        accumulated) verrebbero persi su taskkill, BSOD, riavvio Windows.
        """
        try:
            state = {
                "date": date.today().isoformat(),
                "accumulated": dict(self.accumulated),
                "project_meta": {k: dict(v) if v else {} for k, v in self.project_meta.items()},
            }
            tmp = STATE_FILE.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2, ensure_ascii=False)
            tmp.replace(STATE_FILE)
        except Exception as e:
            log.debug(f"[Tracker] persist_state fallito: {e}")

    def _load_state(self):
        """
        Recupera accumulated all'avvio. Se il salvataggio è di un giorno
        precedente, il payload viene messo in pending (per essere inviato
        col date corretto), altrimenti ricaricato in memoria.
        """
        if not STATE_FILE.exists():
            return
        try:
            with open(STATE_FILE, encoding="utf-8") as f:
                state = json.load(f)
        except Exception as e:
            log.warning(f"[Tracker] state file corrotto, ignoro: {e}")
            try: STATE_FILE.unlink(missing_ok=True)
            except Exception: pass
            return

        saved_date = state.get("date", "")
        accumulated = state.get("accumulated", {}) or {}
        project_meta = state.get("project_meta", {}) or {}

        if not accumulated:
            try: STATE_FILE.unlink(missing_ok=True)
            except Exception: pass
            return

        today = date.today().isoformat()
        if saved_date == today:
            # Stesso giorno — recovery diretto in memoria
            self.accumulated = {k: float(v) for k, v in accumulated.items()}
            self.project_meta = project_meta
            tot_min = sum(self.accumulated.values()) / 60
            log.info(f"[Tracker] Recovery state — {len(self.accumulated)} progetti, {tot_min:.1f} min recuperati")
        else:
            # Giorno precedente — costruisce payload pending con la data corretta
            payload = {
                "source": "cimatron",
                "workstation": self.workstation,
                "date": saved_date,
                "flushed_at": datetime.now().isoformat(),
                "sessions": [
                    {
                        "project":    pid,
                        "commessa":   project_meta.get(pid, {}).get("commessa", pid),
                        "operazione": project_meta.get(pid, {}).get("operazione", ""),
                        "full_path":  project_meta.get(pid, {}).get("full_path"),
                        "seconds":    int(secs),
                        "hours":      round(secs / 3600, 3),
                    }
                    for pid, secs in accumulated.items()
                ],
            }
            self._save_pending(payload)
            log.info(
                f"[Tracker] Recovery cross-day — {len(accumulated)} progetti di {saved_date} "
                f"salvati come pending (saranno inviati al primo flush)"
            )

        try: STATE_FILE.unlink(missing_ok=True)
        except Exception: pass

    def _retry_pending(self):
        if not SESSIONS_FILE.exists():
            return
        try:
            with open(SESSIONS_FILE, encoding="utf-8") as f:
                pending = json.load(f)
        except Exception:
            return

        failed = []
        for payload in pending:
            if not self.client.send_sessions(payload):
                failed.append(payload)

        if failed:
            with open(SESSIONS_FILE, "w", encoding="utf-8") as f:
                json.dump(failed, f, indent=2, ensure_ascii=False)
        else:
            SESSIONS_FILE.unlink(missing_ok=True)
            log.info(f"[Tracker] {len(pending)} payload pending inviati con successo")

    def run(self):
        log.info(
            f"[CAMTracker] Avviato — workstation={self.workstation} "
            f"poll={self.poll_interval}s flush={self.flush_interval}s"
        )
        last_flush = time.time()
        last_reconnect = 0
        RECONNECT_INTERVAL = 60
        dmgdesk_online = False

        # Tenta connessione a DMGDesk
        if self.client.ping():
            dmgdesk_online = True
            log.info(f"[CAMTracker] DMGDesk raggiungibile: {self.cfg['dmgdesk']['url']}")
            self._gui("set_dmgdesk", True)
            self._gui("add_log", f"DMGDesk raggiungibile", "ok")
            self._retry_pending()

            # Analizza STEP del progetto già aperto in Cimatron all'avvio
            try:
                proj = self.cimatron.get_active_project()
                if proj and proj.get("full_path"):
                    pid = proj.get("project_id", "")
                    log.info(f"[STEP] Analisi all'avvio per progetto già aperto: {pid}")
                    threading.Thread(
                        target=self._analizza_step_background,
                        args=(pid, proj["full_path"]),
                        daemon=True
                    ).start()
            except Exception as e:
                log.warning(f"[STEP] Analisi avvio fallita: {e}")
        else:
            log.warning(f"[CAMTracker] DMGDesk non raggiungibile — modalità offline, retry ogni {RECONNECT_INTERVAL}s")
            self._gui("set_dmgdesk", False)
            self._gui("add_log", "DMGDesk non raggiungibile — modalità offline", "warn")

        while not self._stop.is_set():
            self.tick()

            now = time.time()

            # Aggiorna ore GUI
            self._gui("set_ore", self.accumulated)

            # Riconnessione attiva se offline
            if now - last_reconnect >= RECONNECT_INTERVAL:
                last_reconnect = now
                online = self.client.ping()
                if online != dmgdesk_online:
                    dmgdesk_online = online
                    self._gui("set_dmgdesk", online)
                    if online:
                        self._gui("add_log", "DMGDesk tornato online", "ok")
                        self._retry_pending()
                    else:
                        self._gui("add_log", "DMGDesk offline", "warn")

            if now - last_flush >= self.flush_interval:
                self.flush()
                last_flush = time.time()

            self._stop.wait(self.poll_interval)

        # Flush finale all'uscita
        log.info("[CAMTracker] Stop ricevuto — flush finale...")
        self.flush()

    def stop(self):
        self._stop.set()


# ── Entry point ────────────────────────────────────────────────────────────────
def _acquire_lock() -> bool:
    """Crea un file .pid per impedire istanze multiple. Solo stdlib, no psutil."""
    import os
    lock_path = Path(__file__).parent / "cam_tracker.pid"

    if lock_path.exists():
        try:
            old_pid = int(lock_path.read_text().strip())
            # Verifica se il processo è ancora vivo (funziona su Windows e Linux)
            # os.kill(pid, 0) non invia segnali — controlla solo se il processo esiste
            try:
                os.kill(old_pid, 0)
                # Processo vivo — controlla che sia davvero cam_tracker
                # Su Windows os.kill(pid,0) funziona per qualsiasi processo vivo
                log.error(f"[CAMTracker] Già in esecuzione (PID {old_pid}) — uscita")
                return False
            except (OSError, ProcessLookupError):
                # PID non esiste più — lock stale, sovrascriviamo
                pass
        except Exception:
            pass

    lock_path.write_text(str(os.getpid()))
    return True

def _release_lock():
    lock_path = Path(__file__).parent / "cam_tracker.pid"
    try: lock_path.unlink(missing_ok=True)
    except Exception: pass

if __name__ == "__main__":
    if not _acquire_lock():
        import sys; sys.exit(1)

    cfg = load_config()
    tracker = CAMTracker(cfg)

    try:
        tracker.run()
    except KeyboardInterrupt:
        log.info("[CAMTracker] Interruzione da tastiera")
        tracker.stop()
    finally:
        # Chiudi il daemon se attivo
        if hasattr(tracker, 'com'):
            tracker.com.shutdown()
        _release_lock()
