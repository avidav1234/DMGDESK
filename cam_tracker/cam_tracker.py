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
        "program_dir": r"C:\Program Files\Cimatron\Cimatron\2024.0\Program",
        "poll_interval_sec": "10",
    },
    "tracker": {
        "workstation": socket.gethostname(),
        "min_session_sec": "30",   # sessioni < 30s vengono scartate
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
    Si aggancia a Cimatron in esecuzione via COM Interop (pythonnet).
    Legge il documento attivo per estrarre nome file e path progetto.
    """

    def __init__(self, program_dir: str):
        self.program_dir = program_dir
        self.app = None
        self._available = False

    def try_connect(self) -> bool:
        try:
            sys.path.insert(0, self.program_dir)
            import clr  # pythonnet
            clr.AddReference("Interop.CimAppAPI")
            import CimAppAPI

            # GetRunningApplication si aggancia all'istanza già aperta
            self.app = CimAppAPI.CimApplication()
            # Test: se non ci sono eccezioni, la connessione è valida
            _ = self.app.ActiveDocument
            self._available = True
            log.info("[Cimatron COM] Connesso via API nativa")
            return True
        except ImportError:
            log.info("[Cimatron COM] pythonnet non disponibile — userò fallback finestra")
            return False
        except Exception as e:
            log.debug(f"[Cimatron COM] {e}")
            return False

    def get_active_project(self) -> str | None:
        if not self._available or self.app is None:
            return None
        try:
            doc = self.app.ActiveDocument
            if doc is None:
                return None
            full_path = str(doc.FullName)
            p = Path(full_path)
            # Usa il nome del file senza estensione come ID progetto
            # Cimatron tipicamente: C:\Progetti\CODICE_COMMESSA\operazione.elt
            # → "operazione" oppure, se vuoi la cartella padre: p.parent.name
            return p.stem.upper()
        except Exception:
            return None


# ── Win32 window title fallback ────────────────────────────────────────────────
import re

CIMATRON_PATTERNS = [
    # "Cimatron 2024 — FLANGIA_BASE.elt"
    r"Cimatron\s+\S+\s*[-–—]\s*(.+?)(?:\.elt|\.icd)?$",
    # Titoli generici con percorso file
    r"[-–—]\s*.*[/\\](.+?)(?:\.elt|\.icd)?$",
]


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

    def get_active_project(self) -> str | None:
        if not self._win32_ok:
            return None
        try:
            import win32gui
            # Cerca la finestra Cimatron, non solo quella in primo piano
            results = []

            def enum_cb(hwnd, _):
                if win32gui.IsWindowVisible(hwnd):
                    t = win32gui.GetWindowText(hwnd)
                    if "Cimatron" in t or "cimatron" in t.lower():
                        results.append(t)

            win32gui.EnumWindows(enum_cb, None)
            for title in results:
                for pat in CIMATRON_PATTERNS:
                    m = re.search(pat, title, re.IGNORECASE)
                    if m:
                        return m.group(1).strip().upper()
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

        # Stato corrente
        self.current_project: str | None = None
        self.session_start: float | None = None

        # Accumulatore: {progetto: secondi_totali_oggi}
        self.accumulated: dict[str, float] = {}

        # Backend
        self.client = DMGDeskClient(
            cfg["dmgdesk"]["url"],
            int(cfg["dmgdesk"]["timeout_sec"]),
        )

        # Adapter Cimatron (COM → window fallback)
        self.com = CimatronCOMAdapter(cfg["cimatron"]["program_dir"])
        self.window = WindowTitleAdapter()

        self._com_tried = False
        self._stop = threading.Event()

    def _get_project(self) -> str | None:
        """Tenta COM prima, poi window title."""
        if not self._com_tried:
            self.com.try_connect()
            self._com_tried = True

        p = self.com.get_active_project()
        if p:
            return p
        return self.window.get_active_project()

    def tick(self):
        project = self._get_project()
        now = time.time()

        if project != self.current_project:
            # Chiudi sessione precedente
            if self.current_project and self.session_start:
                elapsed = now - self.session_start
                if elapsed >= self.min_session_sec:
                    self.accumulated[self.current_project] = (
                        self.accumulated.get(self.current_project, 0) + elapsed
                    )
                    log.info(
                        f"[Tracker] {self.current_project}: "
                        f"+{elapsed/60:.1f} min "
                        f"(tot oggi: {self.accumulated[self.current_project]/3600:.2f}h)"
                    )
                else:
                    log.debug(f"[Tracker] Sessione troppo breve scartata: {self.current_project} ({elapsed:.0f}s)")

            self.current_project = project
            self.session_start = now if project else None

            if project:
                log.info(f"[Tracker] Progetto attivo → {project}")
            else:
                log.debug("[Tracker] Nessun progetto Cimatron rilevato")

    def flush(self):
        """Chiude la sessione corrente e invia a DMGDesk."""
        now = time.time()
        # Chiudi sessione in corso prima del flush
        if self.current_project and self.session_start:
            elapsed = now - self.session_start
            if elapsed >= self.min_session_sec:
                self.accumulated[self.current_project] = (
                    self.accumulated.get(self.current_project, 0) + elapsed
                )
            self.session_start = now  # resetta il timer (sessione continua)

        if not self.accumulated:
            return

        payload = {
            "source": "cimatron",
            "workstation": self.workstation,
            "date": date.today().isoformat(),
            "flushed_at": datetime.now().isoformat(),
            "sessions": [
                {
                    "project": proj,
                    "seconds": int(secs),
                    "hours": round(secs / 3600, 3),
                }
                for proj, secs in self.accumulated.items()
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
