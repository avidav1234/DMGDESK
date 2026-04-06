"""
telegram_monitor/monitor.py
Loop di monitoraggio stato macchina — notifiche Telegram.

Feature:
  1. Fine programma pulita (progStatus 3→0 senza allarme)
  2. Macchina ferma / lavorazione avviata
  3. Allarme critico / rientrato
  4. Log stale (runopcua/MchnSrv fermo)
  5. Perdita connessione share
  6. Notifica invio batch (chiamata esterna)
  7. Daily summary alle 06:00
"""

import asyncio
import logging
from datetime import datetime, date
from typing import Callable, Awaitable

from .notifier import TelegramNotifier

log = logging.getLogger("telegram_monitor.monitor")

_STATO_LABEL = {
    0: "FERMO",
    1: "INTERROTTO",
    2: "IN ATTESA",
    3: "IN ESECUZIONE",
}

_IN_LAVORO = {2, 3}
_SUMMARY_HOUR = 6


class MachineMonitor:
    def __init__(
        self,
        notifier: TelegramNotifier,
        get_stato_fn:    Callable[[], Awaitable[dict]],
        get_report_fn:   Callable[[], Awaitable[dict]] | None = None,
        interval_sec:    int = 30,
        stale_alert_sec: int = 300,
    ):
        self._notifier        = notifier
        self._get_stato       = get_stato_fn
        self._get_report      = get_report_fn
        self._interval        = interval_sec
        self._stale_alert_sec = stale_alert_sec

        self._prev_stato_prog:  int | None  = None
        self._prev_allarme:     str | None  = None
        self._prev_programma:   str | None  = None
        self._prev_connessa:    bool | None = None
        self._stale_notified:   bool        = False
        self._in_lavoro:        bool        = False
        self._last_summary_day: date | None = None
        self._heartbeat_tick:   int         = 0

    # ── helpers ────────────────────────────────────────────────────────────

    @staticmethod
    def _now() -> str:
        return datetime.now().strftime("%d/%m/%Y %H:%M:%S")

    # ── notifica batch (chiamata dall'esterno da macchina_invio router) ────

    async def notify_batch(self, success: bool, programmi: list, errori: list | None = None):
        now = self._now()
        if success:
            lista = "\n".join(f"  \u2022 <code>{p}</code>" for p in programmi) or "  \u2014"
            await self._notifier.send(
                f"\U0001f4e4 <b>DMG DMC 160U \u2014 BATCH INVIATO</b>\n"
                f"\U0001f550 {now}\n"
                f"\U0001f4c4 Programmi ({len(programmi)}):\n{lista}"
            )
        else:
            err_txt = "\n".join(f"  \u26d4 <code>{e}</code>" for e in (errori or [])) or "  \u2014"
            await self._notifier.send(
                f"\u274c <b>DMG DMC 160U \u2014 ERRORE INVIO BATCH</b>\n"
                f"\U0001f550 {now}\n"
                f"{err_txt}"
            )

    # ── daily summary ──────────────────────────────────────────────────────

    async def _daily_summary(self):
        if not self._get_report:
            return
        try:
            report = await self._get_report()
        except Exception as e:
            log.error(f"Daily summary: errore lettura report: {e}")
            return

        # Filtra sessioni delle 24h precedenti: da mezzanotte ieri a mezzanotte oggi
        from datetime import timedelta
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
            await self._notifier.send(
                f"\U0001f4ca <b>DMG DMC 160U \u2014 RIEPILOGO {label_ieri}</b>\n\n"
                f"\u23f9 Nessuna lavorazione registrata"
            )
        else:
            await self._notifier.send(
                f"\U0001f4ca <b>DMG DMC 160U \u2014 RIEPILOGO {label_ieri}</b>\n\n"
                f"\u23f1 Lavorazione totale: <b>{ore}h {mins}m</b>\n"
                f"\U0001f504 Sessioni: {len(sessioni)}\n"
                f"\U0001f4c4 Programmi eseguiti: {n_programmi}"
            )
        log.info(f"Daily summary inviato — {len(sessioni)} sessioni, {ore}h {mins}m")

    async def _check_daily_summary(self):
        now = datetime.now()
        today = now.date()
        if (now.hour == _SUMMARY_HOUR
                and now.minute < 2
                and self._last_summary_day != today):
            self._last_summary_day = today
            await self._daily_summary()

    # ── check principale ───────────────────────────────────────────────────

    async def _check(self):
        try:
            stato = await self._get_stato()
        except Exception as e:
            log.error(f"Errore lettura stato macchina: {e}")
            return

        connessa    = stato.get("connessa", False)
        stato_prog  = int(stato.get("stato_programma") or 0)
        # Filtra: notifica solo allarmi veri (tipo="allarme"), ignora messaggi informativi
        # (700000-719999 = PLC messaggi/avvertenze che non fermano la macchina, es. 701515)
        allarme_raw  = stato.get("allarme") or None
        allarme_tipo = stato.get("allarme_tipo") or "allarme"
        allarme      = allarme_raw if allarme_tipo == "allarme" else None
        log_stale   = stato.get("log_stale", False)
        log_age    = stato.get("log_age_sec")
        programma  = stato.get("programma_attivo") or "\u2014"
        prog_str   = f"<code>{programma}</code>"
        now        = self._now()

        # ── Connessione ────────────────────────────────────────────────────
        if self._prev_connessa is True and not connessa:
            await self._notifier.send(
                f"\U0001f534 <b>DMG DMC 160U \u2014 LOG NON RAGGIUNGIBILE</b>\n"
                f"\U0001f550 {now}\n"
                f"\u26a0\ufe0f Verifica share di rete / MchnSrv"
            )
        elif self._prev_connessa is False and connessa:
            await self._notifier.send(
                f"\U0001f7e2 <b>DMG DMC 160U \u2014 Connessione ripristinata</b>\n"
                f"\U0001f550 {now}"
            )
        self._prev_connessa = connessa

        if not connessa:
            return

        # ── Log stale ──────────────────────────────────────────────────────
        if log_stale and log_age and log_age >= self._stale_alert_sec:
            if not self._stale_notified:
                await self._notifier.send(
                    f"\u26a0\ufe0f <b>DMG DMC 160U \u2014 LOG NON AGGIORNATO</b>\n"
                    f"\U0001f550 {now}\n"
                    f"\u23f1 Fermo da: {log_age // 60} min\n"
                    f"Possibile crash runopcua o MchnSrv"
                )
                self._stale_notified = True
        else:
            self._stale_notified = False

        # ── Allarme ────────────────────────────────────────────────────────
        if allarme and allarme != self._prev_allarme:
            await self._notifier.send(
                f"\U0001f6a8 <b>DMG DMC 160U \u2014 ALLARME</b>\n"
                f"\U0001f550 {now}\n"
                f"\u26d4 <code>{allarme}</code>\n"
                f"\U0001f4c4 Programma: {prog_str}"
            )
            log.info(f"Notifica allarme: {allarme}")

        if self._prev_allarme and not allarme:
            await self._notifier.send(
                f"\u2705 <b>DMG DMC 160U \u2014 Allarme rientrato</b>\n"
                f"\U0001f550 {now}"
            )

        self._prev_allarme = allarme

        # ── Cambio stato ───────────────────────────────────────────────────
        era_in_lavoro = self._in_lavoro
        ora_in_lavoro = stato_prog in _IN_LAVORO
        self._in_lavoro = ora_in_lavoro

        if self._prev_stato_prog is not None and stato_prog != self._prev_stato_prog:

            # Fine programma pulita 3→0 senza allarme
            if era_in_lavoro and stato_prog == 0 and not allarme:
                await self._notifier.send(
                    f"\u2705 <b>DMG DMC 160U \u2014 PROGRAMMA COMPLETATO</b>\n"
                    f"\U0001f550 {now}\n"
                    f"\U0001f4c4 {prog_str}"
                )
                log.info("Notifica: programma completato")

            # Fermo con interruzione o allarme
            elif era_in_lavoro and not ora_in_lavoro and (allarme or stato_prog == 1):
                label = _STATO_LABEL.get(stato_prog, str(stato_prog))
                await self._notifier.send(
                    f"\u23f9 <b>DMG DMC 160U \u2014 MACCHINA FERMA</b>\n"
                    f"\U0001f550 {now}\n"
                    f"\U0001f4ca Stato: {label}\n"
                    f"\U0001f4c4 Ultimo programma: {prog_str}"
                )
                log.info(f"Notifica: macchina ferma (stato {stato_prog})")

            # Lavorazione avviata
            elif not era_in_lavoro and ora_in_lavoro:
                label = _STATO_LABEL.get(stato_prog, str(stato_prog))
                await self._notifier.send(
                    f"\u25b6\ufe0f <b>DMG DMC 160U \u2014 LAVORAZIONE AVVIATA</b>\n"
                    f"\U0001f550 {now}\n"
                    f"\U0001f4ca Stato: {label}\n"
                    f"\U0001f4c4 Programma: {prog_str}"
                )
                log.info("Notifica: lavorazione avviata")

        self._prev_stato_prog = stato_prog
        self._prev_programma  = programma

    # ── run loop ───────────────────────────────────────────────────────────

    async def run(self):
        log.info(f"MachineMonitor avviato — check ogni {self._interval}s")
        while True:
            self._heartbeat_tick += 1
            await self._check()
            await self._check_daily_summary()
            await asyncio.sleep(self._interval)

# Istanza globale — impostata da api/main.py al startup
_instance: 'MachineMonitor | None' = None
