"""
telegram_monitor/notifier.py
Invia messaggi a Telegram tramite Bot API.
"""

import httpx
import logging

log = logging.getLogger("telegram_monitor.notifier")


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str):
        self.token   = token
        self.chat_id = chat_id
        self._base   = f"https://api.telegram.org/bot{token}"

    async def send(self, message: str) -> bool:
        """Invia messaggio HTML. Ritorna True se ok."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                r = await client.post(
                    f"{self._base}/sendMessage",
                    json={
                        "chat_id":    self.chat_id,
                        "text":       message,
                        "parse_mode": "HTML",
                    },
                )
                if r.status_code != 200:
                    log.error(f"Telegram HTTP {r.status_code}: {r.text[:200]}")
                    return False
                return True
        except httpx.TimeoutException:
            log.warning("Telegram: timeout")
            return False
        except Exception as e:
            log.error(f"Telegram send error: {e}")
            return False

    async def test(self) -> bool:
        """Invia un messaggio di test per verificare configurazione."""
        return await self.send(
            "✅ <b>DMGDesk — Telegram configurato correttamente</b>\n"
            "Le notifiche macchina sono attive."
        )
