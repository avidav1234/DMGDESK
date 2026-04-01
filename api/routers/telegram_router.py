"""
api/routers/telegram_router.py
Endpoint per configurazione e test Telegram dal frontend.
"""

from fastapi import APIRouter
from pydantic import BaseModel
from telegram_monitor.config import load_telegram_config
from telegram_monitor.notifier import TelegramNotifier

router = APIRouter()


class TelegramTestRequest(BaseModel):
    message: str | None = None


@router.get("/status")
async def telegram_status():
    """Ritorna se Telegram è configurato."""
    cfg = load_telegram_config()
    if not cfg:
        # Debug: mostra dove ha cercato il .env
        from pathlib import Path as _P
        import os
        candidates = [
            _P(__file__).parent.parent.parent / ".env",
            _P.cwd() / ".env",
            _P.cwd().parent / ".env",
        ]
        return {
            "configurato": False,
            "motivo": "TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID mancanti nel .env",
            "env_cercato_in": [str(p) + (" ✓ esiste" if p.exists() else " ✗ non trovato") for p in candidates],
            "cwd": str(_P.cwd()),
        }
    return {
        "configurato":     True,
        "chat_id":         cfg["chat_id"],
        "interval_sec":    cfg["interval_sec"],
        "stale_alert_sec": cfg["stale_alert_sec"],
    }


@router.post("/test")
async def telegram_test(body: TelegramTestRequest = TelegramTestRequest()):
    """Invia messaggio di test al bot Telegram."""
    cfg = load_telegram_config()
    if not cfg:
        return {"ok": False, "errore": "Telegram non configurato — aggiungi .env"}

    notifier = TelegramNotifier(token=cfg["token"], chat_id=cfg["chat_id"])
    msg = body.message or "✅ <b>DMGDesk — Test notifica</b>\nConfigurazione Telegram attiva."
    ok = await notifier.send(msg)
    return {"ok": ok}
