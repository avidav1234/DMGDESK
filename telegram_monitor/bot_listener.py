"""
telegram_monitor/bot_listener.py
Polling comandi in entrata dal bot Telegram.

Comandi supportati:
  /stato    — snapshot live macchina + progresso programma corrente
  /progetto — dettaglio commessa: avanzamento %, programmi completati/totali, prossimi
  /summary  — riepilogo ultime 24h
  /help     — lista comandi
"""

import asyncio
import logging
import httpx
from datetime import datetime, timedelta
from typing import Callable, Awaitable

log = logging.getLogger("telegram_monitor.bot_listener")


def _barra(pct: float, lunghezza: int = 10) -> str:
    """Barra di avanzamento testuale: ████░░░░░░ 42%"""
    piene = round(pct / 100 * lunghezza)
    return "█" * piene + "░" * (lunghezza - piene)


class BotListener:
    def __init__(
        self,
        token: str,
        chat_id: str,
        get_stato_fn:        Callable[[], Awaitable[dict]],
        get_live_context_fn: Callable[[], Awaitable[dict]] | None = None,
        get_report_fn:       Callable[[], Awaitable[dict]] | None = None,
        poll_interval: int = 5,
    ):
        self._token             = token
        self._chat_id           = str(chat_id)
        self._get_stato         = get_stato_fn
        self._get_live_context  = get_live_context_fn
        self._get_report        = get_report_fn
        self._poll              = poll_interval
        self._base              = f"https://api.telegram.org/bot{token}"
        self._offset: int       = 0

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
                return r.json().get("result", [])
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
        if not connessa:
            await self._send(
                f"🔴 <b>Macchina non raggiungibile</b>\n"
                f"🕐 {datetime.now().strftime('%d/%m/%Y %H:%M:%S')}"
            )
            return

        stato_prog = int(stato.get("stato_programma") or 0)
        programma  = stato.get("programma_attivo") or "—"
        utensile   = stato.get("utensile_attivo") or "—"
        t_num      = stato.get("numero_utensile") or "—"
        allarme    = stato.get("allarme") or None
        log_age    = stato.get("log_age_sec")
        aggiorn    = stato.get("ultimo_aggiornamento") or "—"
        ora        = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        stati_label = {
            0: "⬛ FERMO",
            1: "🟡 INTERROTTO",
            2: "🟢 IN ATTESA",
            3: "🟢 IN ESECUZIONE",
        }
        stato_str = stati_label.get(stato_prog, str(stato_prog))

        # Prova a recuperare il progresso dal live context
        progresso_str = ""
        if self._get_live_context:
            try:
                ctx = await self._get_live_context()
                match = ctx.get("match")
                if match:
                    nome            = match.get("progetto_nome", "")
                    batch_comp      = match.get("batch_completati", 0)
                    batch_tot       = match.get("batch_totale", 0)
                    batch_pct       = match.get("batch_pct", 0.0)
                    prog_comp       = match.get("programmi_completati", 0)
                    prog_tot        = match.get("programmi_totali", 0)
                    prog_pct        = match.get("pct_avanzamento", 0.0)
                    progresso_str = (
                        f"\n\n📁 Commessa: <b>{nome}</b>\n"
                        f"⚙️ Batch:    {_barra(batch_pct, 10)} {batch_pct}% ({batch_comp}/{batch_tot})\n"
                        f"📦 Progetto: {_barra(prog_pct, 10)} {prog_pct}% ({prog_comp}/{prog_tot})"
                    )
            except Exception:
                pass

        stale_warn = ""
        if log_age and log_age > 120:
            stale_warn = f"\n⚠️ Log fermo da {log_age // 60} min"

        allarme_str = f"\n🚨 Allarme: <code>{allarme}</code>" if allarme else ""

        await self._send(
            f"🏭 <b>DMG DMC 160U — Stato Live</b>\n"
            f"🕐 {ora}\n\n"
            f"📊 {stato_str}\n"
            f"📄 Programma: <code>{programma}</code>\n"
            f"🔧 Utensile: <code>{utensile}</code> (T{t_num})"
            f"{allarme_str}"
            f"{progresso_str}"
            f"{stale_warn}"
        )

    async def _cmd_progetto(self):
        if not self._get_live_context:
            await self._send("⚠️ Live context non disponibile")
            return
        try:
            ctx = await self._get_live_context()
        except Exception as e:
            await self._send(f"❌ Errore: {e}")
            return

        stato_prog = int(ctx.get("stato_programma") or 0)
        match = ctx.get("match")

        if not match:
            prog = ctx.get("programma_attivo") or "—"
            if stato_prog == 0:
                await self._send("⬛ <b>Macchina ferma</b> — nessun progetto in corso")
            else:
                await self._send(
                    f"⚠️ <b>Programma attivo non associato a nessuna commessa</b>\n"
                    f"📄 <code>{prog}</code>\n\n"
                    f"Verifica che il programma sia registrato in WorkTrack."
                )
            return

        nome       = match.get("progetto_nome", "—")
        completati = match.get("programmi_completati", 0)
        totali     = match.get("programmi_totali", 0)
        in_mac     = match.get("programmi_in_macchina", 0)
        pct        = match.get("pct_avanzamento", 0.0)
        utensile   = match.get("utensile_corrente") or "—"
        allerta    = match.get("allerta_utensile")
        prossimi   = match.get("prossimi_programmi") or []
        prog_cor   = match.get("programma_corrente") or "—"
        pallet     = match.get("pallet")
        ora        = datetime.now().strftime("%d/%m/%Y %H:%M:%S")

        batch_comp  = match.get("batch_completati", 0)
        batch_tot   = match.get("batch_totale", 0)
        batch_pct   = match.get("batch_pct", 0.0)

        # Allerta utensile
        allerta_str = ""
        if allerta == "fin_vita":
            allerta_str = "\n⚠️ <b>Utensile a fine vita!</b>"
        elif allerta == "disabilitato":
            allerta_str = "\n🚫 <b>Utensile disabilitato</b>"

        # Prossimi programmi
        if prossimi:
            prossimi_lines = "\n".join(
                f"  {i+1}. <code>{p.get('filename','?')}</code>"
                for i, p in enumerate(prossimi[:4])
            )
            prossimi_str = f"\n\n📋 <b>Prossimi programmi:</b>\n{prossimi_lines}"
        else:
            prossimi_str = "\n\n✅ Ultimo programma in esecuzione"

        pallet_str = f" · Pallet {pallet}" if pallet else ""

        await self._send(
            f"📁 <b>{nome}</b>{pallet_str}\n"
            f"🕐 {ora}\n\n"
            f"⚙️ Batch:    <b>{_barra(batch_pct)} {batch_pct}%</b> ({batch_comp}/{batch_tot})\n"
            f"📦 Progetto: <b>{_barra(pct)} {pct}%</b> ({completati}/{totali})\n\n"
            f"▶️ Corrente: <code>{prog_cor}</code>\n"
            f"🔧 Utensile: <code>{utensile}</code>"
            f"{allerta_str}"
            f"{prossimi_str}"
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

        oggi       = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
        ieri       = oggi - timedelta(days=1)
        label_ieri = ieri.strftime("%d/%m/%Y")

        sessioni_tutte = report.get("sessioni") or []
        sessioni = []
        for s in sessioni_tutte:
            try:
                inizio = datetime.fromisoformat(s["inizio"])
                if ieri <= inizio < oggi:
                    sessioni.append(s)
            except Exception:
                pass

        durata_tot  = sum(s.get("durata_sec", 0) for s in sessioni)
        n_programmi = sum(len(s.get("programmi", [])) for s in sessioni)
        ore  = durata_tot // 3600
        mins = (durata_tot % 3600) // 60

        if not sessioni:
            await self._send(
                f"📊 <b>Riepilogo {label_ieri}</b>\n\n"
                f"⏹ Nessuna lavorazione registrata"
            )
        else:
            await self._send(
                f"📊 <b>Riepilogo {label_ieri}</b>\n\n"
                f"⏱ Lavorazione totale: <b>{ore}h {mins}m</b>\n"
                f"🔄 Sessioni: {len(sessioni)}\n"
                f"📄 Programmi eseguiti: {n_programmi}"
            )

    async def _cmd_help(self):
        await self._send(
            "🤖 <b>DMGDesk Bot — Comandi disponibili</b>\n\n"
            "/stato — Stato live + progresso commessa\n"
            "/progetto — Dettaglio avanzamento commessa\n"
            "/summary — Riepilogo ultime 24h\n"
            "/help — Questo messaggio"
        )

    # ── dispatch ───────────────────────────────────────────────────────────

    async def _dispatch(self, update: dict):
        msg = update.get("message", {})
        chat_id = str(msg.get("chat", {}).get("id", ""))
        if chat_id != self._chat_id:
            log.warning(f"Messaggio da chat_id non autorizzato: {chat_id}")
            return

        text = (msg.get("text") or "").strip().lower().split("@")[0]

        if text == "/stato":
            await self._cmd_stato()
        elif text == "/progetto":
            await self._cmd_progetto()
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
