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

# ── Logging ────────────────────────────────────────────────────────────────────
LOG_DIR = Path(__file__).parent
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.FileHandler(LOG_DIR / "cam_tracker.log", encoding="utf-8"),
        logging.StreamHandler(sys.stdout),
    ],
)
log = logging.getLogger("cam_tracker")

# ── Config ─────────────────────────────────────────────────────────────────────
CONFIG_FILE = Path(__file__).parent / "cam_tracker_config.ini"
SESSIONS_FILE = Path(__file__).parent / "cam_sessions_pending.json"

DEFAULT_CONFIG = {
    "dmgdesk": {
        "url": "http://localhost:8000",
        "flush_interval_sec": "300",
        "timeout_sec": "5",
    },
    "cimatron": {
        "program_dir": r"C:\Program Files\Cimatron\Cimatron\2025.0\Program",
        "query_exe": r"C:\Program Files\Cimatron\Cimatron\2025.0\Program\cimatron_query.exe",
        "poll_interval_sec": "10",
    },
    "tracker": {
        "workstation": socket.gethostname(),
        "min_session_sec": "10",
        "idle_timeout_min": "5",
    },
}


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
    def __init__(self, base_url: str, timeout: int):
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout

    def ping(self) -> bool:
        try:
            import requests
            r = requests.get(f"{self.base_url}/health", timeout=self.timeout)
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


# ── Cimatron COM adapter ───────────────────────────────────────────────────────
class CimatronCOMAdapter:
    """
    Legge il documento attivo in Cimatron tramite cimatron_query.exe
    (subprocess con manifest embedded) oppure via pythonnet diretto.
    """

    def __init__(self, program_dir: str):
        self.program_dir = program_dir
        self.app = None
        self._available = False
        # Path dell'exe query — stessa cartella di questo script
        self._query_exe = Path(__file__).parent / "cimatron_query.exe"

    def try_connect(self) -> bool:
        # Metodo 1: cimatron_query.exe nella cartella Cimatron (più affidabile)
        cim_exe = Path(self.program_dir) / "cimatron_query.exe"
        local_exe = Path(__file__).parent / "cimatron_query.exe"

        if cim_exe.exists():
            log.info(f"[Cimatron] Usando {cim_exe}")
            self._query_exe = cim_exe
            self._available = True
            self._mode = "exe"
            return True
        elif local_exe.exists():
            log.info(f"[Cimatron] Usando {local_exe} (locale — potrebbe dare errore SxS)")
            self._query_exe = local_exe
            self._available = True
            self._mode = "exe"
            return True

        # Metodo 2: pythonnet diretto (richiede manifest su python.exe)
        try:
            base = Path(self.program_dir).parent.parent
            candidates = [self.program_dir]
            if base.exists():
                versioni = sorted(
                    [str(d / "Program") for d in base.iterdir()
                     if d.is_dir() and (d / "Program").exists()],
                    reverse=True
                )
                candidates = versioni + candidates

            for path in candidates:
                if Path(path).exists():
                    sys.path.insert(0, path)
                    log.info(f"[Cimatron COM] Usando path: {path}")
                    break

            import clr
            clr.AddReference("interop.CimatronE")
            from interop.CimatronE import CimApplicationClass
            self.app = CimApplicationClass()
            _ = self.app.ActiveDocument
            self._available = True
            self._mode = "com"
            log.info("[Cimatron COM] Connesso via pythonnet")
            return True
        except ImportError:
            log.info("[Cimatron COM] pythonnet non disponibile")
            return False
        except Exception as e:
            log.debug(f"[Cimatron COM] {e}")
            return False

    def get_active_project(self) -> dict | None:
        if not self._available:
            return None

        if getattr(self, '_mode', None) == "exe":
            return self._query_via_exe()
        else:
            return self._query_via_com()

    def _query_via_exe(self) -> dict | None:
        """Lancia cimatron_query.exe e legge il path dal stdout."""
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
        """Legge path completo del documento attivo via COM."""
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

    def is_active(self) -> tuple[bool, str]:
        """
        Ritorna (conta_tempo, descrizione).
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

        # Backend
        self.client = DMGDeskClient(
            cfg["dmgdesk"]["url"],
            int(cfg["dmgdesk"]["timeout_sec"]),
        )

        # Adapter Cimatron (COM → window fallback)
        self.com = CimatronCOMAdapter(cfg["cimatron"]["program_dir"])
        self.window = WindowTitleAdapter()
        self.activity = ActivityMonitor(idle_timeout_sec=idle_timeout_min * 60)

        self._com_tried = False
        self._stop = threading.Event()

    def _get_project(self) -> dict | None:
        """
        Tenta EXE/COM prima (path completo → commessa affidabile).
        Fallback al titolo finestra SOLO se l'EXE non è disponibile,
        NON in caso di timeout (il timeout non deve causare cambio progetto).
        """
        if not self._com_tried:
            self.com.try_connect()
            self._com_tried = True

        p = self.com.get_active_project()
        if p:
            # Valida: accetta solo commesse numeriche (4 cifre) o formato NNNN_NNNN
            commessa = p.get("commessa", "")
            if commessa and re.match(r'^\d{4}', commessa):
                return p
            # Commessa non valida (es. E541540221) → ignora questo risultato
            # ma NON fare fallback al titolo — meglio tenere il progetto precedente
            return None

        # Fallback al titolo finestra solo se l'exe non ha dato timeout
        # (se ha dato timeout, self.com._last_timeout è True)
        if getattr(self.com, '_last_timeout', False):
            # Timeout EXE → mantieni progetto precedente, non cambiare
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
        if self.current_project and self.session_start:
            if not active and not self.is_paused:
                # Entra in pausa — congela il tempo accumulato fino ad ora
                elapsed = now - self.session_start
                pid = self._project_id(self.current_project)
                if elapsed >= self.min_session_sec:
                    self.accumulated[pid] = self.accumulated.get(pid, 0) + elapsed
                    self.project_meta[pid] = self.current_project
                self.session_start = None
                self.is_paused = True
                log.info(f"[Tracker] PAUSA — {reason}")

            elif active and self.is_paused:
                # Ripresa attività — riavvia il timer
                self.session_start = now
                self.is_paused = False
                log.info(f"[Tracker] RIPRESA — {reason}")

        # ── Cambio progetto ───────────────────────────────────────────────────
        if proj_id != self._project_id(self.current_project):
            # Chiudi sessione precedente se non in pausa
            if self.current_project and self.session_start and not self.is_paused:
                elapsed = now - self.session_start
                pid = self._project_id(self.current_project)
                if elapsed >= self.min_session_sec:
                    self.accumulated[pid] = self.accumulated.get(pid, 0) + elapsed
                    self.project_meta[pid] = self.current_project
                    log.info(
                        f"[Tracker] {pid}: "
                        f"+{elapsed/60:.1f} min "
                        f"(tot oggi: {self.accumulated[pid]/3600:.2f}h)"
                    )
                else:
                    log.debug(f"[Tracker] Sessione troppo breve: {pid} ({elapsed:.0f}s)")

            self.current_project = proj
            self.is_paused = not active
            self.session_start = now if (proj and active) else None

            if proj:
                log.info(
                    f"[Tracker] Progetto → commessa={proj['commessa']} op={proj['operazione']} "
                    f"| {reason}"
                )
            else:
                log.debug("[Tracker] Nessun progetto Cimatron")

    def flush(self):
        """Chiude la sessione corrente e invia a DMGDesk."""
        now = time.time()
        if self.current_project and self.session_start:
            elapsed = now - self.session_start
            pid = self._project_id(self.current_project)
            if elapsed >= self.min_session_sec:
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
        if ok:
            self.accumulated.clear()
        else:
            # Salva localmente per retry al prossimo flush
            self._save_pending(payload)
            log.warning("[Tracker] Payload salvato localmente — retry al prossimo flush")

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

        # Tenta connessione a DMGDesk
        if self.client.ping():
            log.info(f"[CAMTracker] DMGDesk raggiungibile: {self.cfg['dmgdesk']['url']}")
        else:
            log.warning(f"[CAMTracker] DMGDesk non raggiungibile — modalità offline")

        # Retry eventuali pending al boot
        self._retry_pending()

        while not self._stop.is_set():
            self.tick()

            if time.time() - last_flush >= self.flush_interval:
                self.flush()
                last_flush = time.time()

            self._stop.wait(self.poll_interval)

        # Flush finale all'uscita
        log.info("[CAMTracker] Stop ricevuto — flush finale...")
        self.flush()

    def stop(self):
        self._stop.set()


# ── Entry point ────────────────────────────────────────────────────────────────
if __name__ == "__main__":
    cfg = load_config()
    tracker = CAMTracker(cfg)

    try:
        tracker.run()
    except KeyboardInterrupt:
        log.info("[CAMTracker] Interruzione da tastiera")
        tracker.stop()
