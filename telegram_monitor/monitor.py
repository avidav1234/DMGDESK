"""
telegram_monitor/monitor.py
Loop di monitoraggio stato macchina — invia notifiche Telegram
su cambio stato e allarmi critici.

Stato monitorato (da get_stato_macchina):
  stato_programma : 0=fermo, 1=interrotto, 2=attesa, 3=in esecuzione
  allarme         : stringa allarme attivo, None se nessuno
  log_stale       : True se il log non si aggiorna da > WATCHDOG_SOGLIA_SEC
  connessa        : False se il log non è raggiungibile
"""

import asyncio
import logging
from datetime import datetime
from typing import Callable, Awaitable

from .notifier import TelegramNotifier

log = logging.getLogger("telegram_monitor.monitor")

# Etichette leggibili per stato_programma
_STATO_LABEL = {
    0: "FERMO",
    1: "INTERROTTO",
    2: "IN ATTESA",
    3: "IN ESECUZIONE",
}

# stato_programma considerati "in lavorazione"
_IN_LAVORO = {2, 3}


class MachineMonitor:
    """
    Monitoraggio asincrono dello stato macchina con notifiche Telegram.

    Args:
        notifier:       TelegramNotifier configurato
        get_stato_fn:   funzione async() -> dict (da macchina_live.get_stato_macchina)
        interval_sec:   secondi tra un check e l'altro (default 30)
        stale_alert_sec: secondi stale log prima di notifica (default 300 = 5 min)
    """

    def __init__(
        self,
        notifier: TelegramNotifier,
        get_stato_fn: Callable[[], Awaitable[dict]],
        interval_sec:   int = 30,
        stale_alert_sec: int = 300,
    ):
        self._notifier        = notifier
        self._get_stato       = get_stato_fn
        self._interval        = interval_sec
        self._stale_alert_sec = stale_alert_sec

        # Stato precedente
        self._prev_stato_prog: int | None   = None
        self._prev_allarme:    str | None   = None
        self._prev_connessa:   bool | None  = None
        self._stale_notified:  bool         = False
        self._in_lavoro:       bool         = False

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    @staticmethod
    def _prog_str(stato: dict) -> str:
        prog = stato.get("programma_attivo") or "—"
        return f"<code>{prog}</code>"

    # ── check principale ───────────────────────────────────────────────────

    async def _check(self):
        try:
            stato = await self._get_stato()
        except Exception as e:
            log.error(f"Errore lettura stato macchina: {e}")
            return

        connessa    = stato.get("connessa", False)
        stato_prog  = int(stato.get("stato_programma") or 0)
        allarme     = stato.get("allarme") or None
        log_stale   = stato.get("log_stale", False)
        log_age     = stato.get("log_age_sec")
        programma   = self._prog_str(stato)
        now         = self._now()

        # ── 1. Perdita connessione log ─────────────────────────────────────
        if self._prev_connessa is True and not connessa:
            await self._notifier.send(
                f"🔴 <b>DMG DMC 160U — LOG NON RAGGIUNGIBILE</b>\n"
                f"🕐 {now}\n"
                f"⚠️ Verifica share di rete / MchnSrv"
            )
        elif self._prev_connessa is False and connessa:
            await self._notifier.send(
                f"🟢 <b>DMG DMC 160U — Connessione log ripristinata</b>\n"
                f"🕐 {now}"
            )
        self._prev_connessa = connessa

        if not connessa:
            return

        # ── 2. Log stale (MchnSrv / runopcua fermo) ───────────────────────
        if log_stale and log_age and log_age >= self._stale_alert_sec:
            if not self._stale_notified:
                await self._notifier.send(
                    f"⚠️ <b>DMG DMC 160U — LOG NON AGGIORNATO</b>\n"
                    f"🕐 {now}\n"
                    f"⏱ Ultimo aggiornamento: {log_age // 60} min fa\n"
                    f"Possibile crash runopcua o MchnSrv"
                )
                self._stale_notified = True
        else:
            self._stale_notified = False

        # ── 3. Allarme critico ────────────────────────────────────────────
        if allarme and allarme != self._prev_allarme:
            await self._notifier.send(
                f"🚨 <b>DMG DMC 160U — ALLARME</b>\n"
                f"🕐 {now}\n"
                f"⛔ <code>{allarme}</code>\n"
                f"📄 Programma: {programma}"
            )
            log.info(f"Notifica allarme: {allarme}")

        if self._prev_allarme and not allarme:
            await self._notifier.send(
                f"✅ <b>DMG DMC 160U — Allarme rientrato</b>\n"
                f"🕐 {now}"
            )
            log.info("Notifica allarme rientrato")

        self._prev_allarme = allarme

        # ── 4. Cambio stato lavorazione ───────────────────────────────────
        era_in_lavoro  = self._in_lavoro
        ora_in_lavoro  = stato_prog in _IN_LAVORO
        self._in_lavoro = ora_in_lavoro

        if self._prev_stato_prog is not None and stato_prog != self._prev_stato_prog:

            # Macchina si è fermata (da in-lavoro a fermo/interrotto)
            if era_in_lavoro and not ora_in_lavoro:
                label = _STATO_LABEL.get(stato_prog, str(stato_prog))
                await self._notifier.send(
                    f"⏹ <b>DMG DMC 160U — MACCHINA FERMA</b>\n"
                    f"🕐 {now}\n"
                    f"📊 Stato: {label}\n"
                    f"📄 Ultimo programma: {programma}"
                )
                log.info(f"Notifica: macchina ferma (stato {stato_prog})")

            # Macchina ripresa
            elif not era_in_lavoro and ora_in_lavoro:
                label = _STATO_LABEL.get(stato_prog, str(stato_prog))
                await self._notifier.send(
                    f"▶️ <b>DMG DMC 160U — LAVORAZIONE AVVIATA</b>\n"
                    f"🕐 {now}\n"
                    f"📊 Stato: {label}\n"
                    f"📄 Programma: {programma}"
                )
                log.info(f"Notifica: lavorazione avviata (stato {stato_prog})")

        self._prev_stato_prog = stato_prog

    # ── run loop ───────────────────────────────────────────────────────────

    async def run(self):
        log.info(f"MachineMonitor avviato — check ogni {self._interval}s")
        while True:
            await self._check()
            await asyncio.sleep(self._interval)
