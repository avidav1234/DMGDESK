"""
Logger centralizzato — Tool Manager V14.0
==========================================
Logging su file con rotazione automatica.

Utilizzo:
    from utils.logger import get_logger
    log = get_logger(__name__)

    log.info("Utensile montato: FF12R2-F80H4 → pos 7")
    log.warning("Holder E3 quantità sotto soglia (1 rimasto)")
    log.error("Errore salvataggio database", exc_info=True)

File generati in: logs/
  - toolmanager.log          → log corrente (max 2 MB)
  - toolmanager.log.1        → backup 1
  - toolmanager.log.2        → backup 2  (poi ruota)
  - errors.log               → solo ERROR e CRITICAL (sempre)
"""

import logging
import logging.handlers
import os
import sys
from pathlib import Path


# ─── Configurazione ─────────────────────────────────────────
LOG_DIR = Path("logs")
LOG_FILE = LOG_DIR / "toolmanager.log"
ERROR_FILE = LOG_DIR / "errors.log"

MAX_BYTES = 2 * 1024 * 1024  # 2 MB per file
BACKUP_COUNT = 3               # 3 backup → max ~8 MB totali

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)-30s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# Level di default: INFO in produzione, DEBUG se variabile d'ambiente impostata
DEFAULT_LEVEL = logging.DEBUG if os.environ.get("TM_DEBUG") else logging.INFO


# ─── Setup (eseguito una sola volta) ───────────────────────
_initialized = False


def _setup_logging():
    """Configura il sistema di logging. Chiamata automaticamente al primo get_logger()."""
    global _initialized
    if _initialized:
        return
    _initialized = True

    # Crea cartella logs/ se non esiste
    LOG_DIR.mkdir(exist_ok=True)

    root_logger = logging.getLogger("toolmanager")
    root_logger.setLevel(logging.DEBUG)  # il root cattura tutto, i handler filtrano

    formatter = logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT)

    # ── Handler 1: Console (INFO+) ────────────────────────
    console = logging.StreamHandler(sys.stdout)
    console.setLevel(logging.INFO)
    console.setFormatter(formatter)
    root_logger.addHandler(console)

    # ── Handler 2: File rotante principale (DEBUG+) ───────
    file_handler = logging.handlers.RotatingFileHandler(
        LOG_FILE,
        maxBytes=MAX_BYTES,
        backupCount=BACKUP_COUNT,
        encoding="utf-8"
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(formatter)
    root_logger.addHandler(file_handler)

    # ── Handler 3: File errori (ERROR+, sempre separato) ──
    error_handler = logging.handlers.RotatingFileHandler(
        ERROR_FILE,
        maxBytes=MAX_BYTES,
        backupCount=2,
        encoding="utf-8"
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)
    root_logger.addHandler(error_handler)

    root_logger.info("=" * 60)
    root_logger.info("Tool Manager V14.0 — Logger inizializzato")
    root_logger.info(f"Log file: {LOG_FILE.resolve()}")
    root_logger.info(f"Error file: {ERROR_FILE.resolve()}")
    root_logger.info("=" * 60)


def get_logger(name: str) -> logging.Logger:
    """
    Restituisce un logger figlio del root 'toolmanager'.

    Args:
        name: tipicamente __name__ del modulo chiamante
              es. 'logic.nc_analyzer', 'ui.tab_macchina'

    Returns:
        logging.Logger configurato e pronto all'uso
    """
    _setup_logging()

    # Normalizza il nome: rimuove prefisso package se presente
    # es. "tool_manager.logic.nc_analyzer" → "toolmanager.logic.nc_analyzer"
    clean_name = name.replace("tool_manager.", "").replace(".", ".")

    return logging.getLogger(f"toolmanager.{clean_name}")


# ─── Helper per eventi di business ─────────────────────────
class ToolManagerLogger:
    """
    Logger con metodi semantici per gli eventi tipici dell'app.
    Opzionale — usalo quando vuoi log più strutturati.

    Esempio:
        from utils.logger import tool_log
        tool_log.utensile_montato("FF12R2-F80H4", posizione=7, holder="E3")
    """

    def __init__(self):
        self._log = get_logger("business")

    def utensile_montato(self, alias: str, posizione: int = None, holder: str = None):
        extra = f"pos={posizione}" if posizione else ""
        extra += f" holder={holder}" if holder else ""
        self._log.info(f"MOUNT   | {alias} {extra}".strip())

    def utensile_smontato(self, alias: str, da: str = "macchina"):
        self._log.info(f"UNMOUNT | {alias} da={da}")

    def database_caricato(self, path: str, righe: int):
        self._log.info(f"DB_LOAD | {path} ({righe} righe)")

    def database_salvato(self, path: str, righe: int):
        self._log.info(f"DB_SAVE | {path} ({righe} righe)")

    def nc_analizzato(self, file: str, utensili_trovati: int, mancanti: int):
        level = logging.WARNING if mancanti > 0 else logging.INFO
        self._log.log(level, f"NC_ANAL | {file} trovati={utensili_trovati} mancanti={mancanti}")

    def main_generato(self, path: str, utensili: int, calibra_count: int):
        self._log.info(f"MAIN_GEN| {path} utensili={utensili} calibra={calibra_count}")

    def holder_basso(self, alias: str, quantita: int):
        self._log.warning(f"LOW_HOLD| {alias} quantita={quantita} (sotto soglia)")

    def errore_critico(self, msg: str, exc: Exception = None):
        self._log.critical(f"CRITICAL| {msg}", exc_info=exc is not None)


# Istanza globale pronta all'uso
tool_log = ToolManagerLogger()
