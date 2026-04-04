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
        """Avvia cimatron_daemon.exe come processo figlio persistente."""
        import subprocess
        import threading
        try:
            self._proc = subprocess.Popen(
                [str(self._daemon_exe)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1,
            )
            # Aspetta READY su stdout con timeout di 20s
            # Leggi tutte le righe finché non troviamo READY o errore
            import time
            deadline = time.time() + 20
            while time.time() < deadline:
                if self._proc.poll() is not None:
                    log.warning("[Cimatron Daemon] Processo terminato durante avvio")
                    self._proc = None
                    self._mode = "exe"
                    return
                # Leggi con timeout non bloccante
                import select
                import os
                # Su Windows non c'è select su pipe — usiamo thread
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

    def get_active_project(self) -> dict | None:
        if not self._available:
            return None
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

        # GUI opzionale
        self.gui = None
        self._gui_thread = None
        self._init_gui()

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
                # Entra in pausa
                elapsed = now - self.session_start
                pid = self._project_id(self.current_project)
                if elapsed >= self.min_session_sec:
                    self.accumulated[pid] = self.accumulated.get(pid, 0) + elapsed
                    self.project_meta[pid] = self.current_project
                self.session_start = None
                self.is_paused = True
                log.info(f"[Tracker] PAUSA — {reason}")
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
            else:
                log.debug("[Tracker] Nessun progetto Cimatron")
                self._gui("set_progetto", "—", False)

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
            with open(stp, "rb") as f:
                resp = _req.post(url, files={"file": (stp.name, f, "application/octet-stream")},
                                 data={"commessa": project_id}, timeout=180)
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
            ts = datetime.now().strftime("%H:%M:%S")
            n  = len(payload["sessions"])
            self._gui("set_ultimo_invio", ts, n)
            self._gui("add_log", f"Inviati {n} record a DMGDesk", "ok")
            self._gui("set_ore", {})
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
