"""
telegram_monitor/bot_listener.py
Polling comandi in entrata dal bot Telegram.

Comandi supportati:
  /stato   — snapshot live macchina
  /summary — riepilogo giornaliero immediato
  /help    — lista comandi
"""

import asyncio
import logging
import httpx
from datetime import datetime
from typing import Callable, Awaitable

log = logging.getLogger("telegram_monitor.bot_listener")


class BotListener:
    def __init__(
        self,
        token: str,
        chat_id: str,
        get_stato_fn:  Callable[[], Awaitable[dict]],
        get_report_fn: Callable[[], Awaitable[dict]] | None = None,
        poll_interval: int = 5,
    ):
        self._token        = token
        self._chat_id      = str(chat_id)
        self._get_stato    = get_stato_fn
        self._get_report   = get_report_fn
        self._poll         = poll_interval
        self._base         = f"https://api.telegram.org/bot{token}"
        self._offset: int  = 0

    # ── Telegram API helpers ───────────────────────────────────────────────

    async def _get_updates(self) -> list:
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(
                    f"{self._base}/getUpdates",
                    params={"offset": self._offset, "timeout": 10, "allowed_updates": ["message"]},
                )
                if r.status_code != 200:
                    return []
                data = r.json()
                return data.get("result", [])
        except Exception as e:
            log.warning(f"getUpdates error: {e}")
            return []

    async def _send(self, text: str):
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                await client.post(
                    f"{self._base}/sendMessage",
                    json={"chat_id": self._chat_id, "text": text, "parse_mode": "HTML"},
                )
        except Exception as e:
            log.warning(f"send error: {e}")

    # ── handlers comandi ───────────────────────────────────────────────────

    async def _cmd_stato(self):
        try:
            stato = await self._get_stato()
        except Exception as e:
            await self._send(f"❌ Errore lettura stato: {e}")
            return

        connessa   = stato.get("connessa", False)
        stato_prog = int(stato.get("stato_programma") or 0)
        programma  = stato.get("programma_attivo") or "—"
        utensile   = stato.get("utensile_attivo") or "—"
        t_num      = stato.get("numero_utensile") or "—"
        allarme    = stato.get("allarme") or "Nessuno"
        log_age    = stato.get("log_age_sec")
        aggiorn    = stato.get("ultimo_aggiornamento") or "—"
        ora        = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        stati_label = {0: "⬛ FERMO", 1: "🟡 INTERROTTO", 2: "🟢 IN ATTESA", 3: "🟢 IN ESECUZIONE"}
        stato_str = stati_label.get(stato_prog, str(stato_prog))

        stale_warn = ""
        if log_age and log_age > 120:
            stale_warn = f"\n⚠️ Log fermo da {log_age // 60} min"

        if not connessa:
            await self._send(f"🔴 <b>Macchina non raggiungibile</b>\n🕐 {ora}")
            return

        await self._send(
            f"🏭 <b>DMG DMC 160U — Stato Live</b>\n"
            f"🕐 {ora}\n\n"
            f"📊 Stato: {stato_str}\n"
            f"📄 Programma: <code>{programma}</code>\n"
            f"🔧 Utensile: <code>{utensile}</code> (T{t_num})\n"
            f"🚨 Allarme: {allarme}\n"
            f"🕓 Log: {aggiorn}{stale_warn}"
        )

    async def _cmd_summary(self):
        if not self._get_report:
            await self._send("⚠️ Report non disponibile")
            return
        try:
            report = await self._get_report()
        except Exception as e:
            await self._send(f"❌ Errore lettura report: {e}")
            return

        sessioni    = report.get("sessioni_ieri") or report.get("sessioni") or []
        durata_tot  = sum(s.get("durata_sec", 0) for s in sessioni)
        n_programmi = sum(len(s.get("programmi", [])) for s in sessioni)
        allarmi     = report.get("allarmi_ieri", 0)
        ore  = durata_tot // 3600
        mins = (durata_tot % 3600) // 60
        now  = datetime.now().strftime("%d/%m/%Y %H:%M")

        await self._send(
            f"📊 <b>Riepilogo — {now}</b>\n\n"
            f"⏱ Lavorazione totale: <b>{ore}h {mins}m</b>\n"
            f"🔄 Sessioni: {len(sessioni)}\n"
            f"📄 Programmi eseguiti: {n_programmi}\n"
            f"🚨 Allarmi: {allarmi or 0}"
        )

    async def _cmd_help(self):
        await self._send(
            "🤖 <b>DMGDesk Bot — Comandi disponibili</b>\n\n"
            "/stato — Snapshot live macchina\n"
            "/summary — Riepilogo lavorazione\n"
            "/help — Questo messaggio"
        )

    # ── dispatch ───────────────────────────────────────────────────────────

    async def _dispatch(self, update: dict):
        msg = update.get("message", {})
        # Accetta solo messaggi dal chat_id autorizzato
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if chat_id != self._chat_id:
            log.warning(f"Messaggio da chat_id non autorizzato: {chat_id}")
            return

        text = (msg.get("text") or "").strip().lower().split("@")[0]

        if text == "/stato":
            await self._cmd_stato()
        elif text == "/summary":
            await self._cmd_summary()
        elif text in ("/help", "/start"):
            await self._cmd_help()
        else:
            await self._send("❓ Comando non riconosciuto. Usa /help per la lista comandi.")

    # ── run loop ───────────────────────────────────────────────────────────

    async def run(self):
        log.info("BotListener avviato — polling comandi Telegram")
        while True:
            updates = await self._get_updates()
            for upd in updates:
                self._offset = upd["update_id"] + 1
                try:
                    await self._dispatch(upd)
                except Exception as e:
                    log.error(f"Dispatch error: {e}")
            await asyncio.sleep(self._poll)
