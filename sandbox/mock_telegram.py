"""
sandbox/mock_telegram.py
=========================
Sostituisce il notifier Telegram reale in modalità sandbox.
Tutti i messaggi vengono stampati in console con timestamp
invece di essere inviati via API Telegram.

Come funziona:
    In sandbox_env.py viene fatto il monkey-patch del modulo
    telegram_monitor.notifier con questo mock.
"""

from datetime import datetime

_log = []  # storico messaggi in memoria


def _print_msg(prefix: str, text: str):
    ts = datetime.now().strftime("%H:%M:%S")
    sep = "─" * 50
    print(f"\n{sep}")
    print(f"[SANDBOX TELEGRAM {prefix}] {ts}")
    print(text)
    print(sep)
    _log.append({"ts": ts, "tipo": prefix, "testo": text})


def send_message(text: str, **kwargs):
    _print_msg("📨 MSG", text)
    return True


def send_alert(text: str, **kwargs):
    _print_msg("🚨 ALERT", text)
    return True


def send_daily_summary(text: str, **kwargs):
    _print_msg("📊 SUMMARY", text)
    return True


def get_log():
    """Restituisce tutti i messaggi inviati in questa sessione."""
    return list(_log)


def clear_log():
    _log.clear()
