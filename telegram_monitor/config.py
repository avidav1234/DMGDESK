"""
telegram_monitor/config.py
Carica TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID da variabili d'ambiente
o dal file .env nella root del progetto.
"""

import os
from pathlib import Path


def _load_dotenv(env_path: Path):
    """Carica .env senza dipendenze esterne. Gestisce BOM UTF-8 (Windows PowerShell)."""
    if not env_path.exists():
        return
    with open(env_path, encoding="utf-8-sig") as f:  # utf-8-sig rimuove BOM automaticamente
        for line in f:
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, _, val = line.partition("=")
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def load_telegram_config() -> dict | None:
    """
    Ritorna {"token": ..., "chat_id": ..., "interval": ..., "stale_alert_sec": ...}
    oppure None se non configurato.
    """
    # Cerca .env in più posti — root progetto, CWD, cartella padre CWD
    candidates = [
        Path(__file__).parent.parent / ".env",   # root repo (nominale)
        Path.cwd() / ".env",                      # directory di avvio uvicorn
        Path.cwd().parent / ".env",
    ]
    for p in candidates:
        _load_dotenv(p)

    token   = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    chat_id = os.environ.get("TELEGRAM_CHAT_ID", "").strip()

    if not token or not chat_id:
        return None

    return {
        "token":           token,
        "chat_id":         chat_id,
        "interval_sec":    int(os.environ.get("TELEGRAM_INTERVAL_SEC", "30")),
        "stale_alert_sec": int(os.environ.get("TELEGRAM_STALE_ALERT_SEC", "300")),
    }
