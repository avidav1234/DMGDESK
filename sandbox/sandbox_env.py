"""
sandbox/sandbox_env.py
=======================
Attiva la modalità sandbox per DMGDesk V2.

Importa questo modulo PRIMA di avviare il backend per:
  1. Caricare sandbox_config.json come config attiva
  2. Reindirizzare tutti i path verso sandbox/data/
  3. Mockare Telegram (messaggi → console)
  4. Impostare variabili d'ambiente SANDBOX_MODE=1

Uso (in AVVIA_SANDBOX.bat):
    set SANDBOX_MODE=1
    set DMGDESK_CONFIG=./sandbox/sandbox_config.json
    uvicorn api.main:app --port 8010 --reload
"""

import os
import sys
import json
from pathlib import Path

ROOT = Path(__file__).parent.parent
SANDBOX_DIR = ROOT / "sandbox"
DATA_DIR = SANDBOX_DIR / "data"

# ── 1. Variabili d'ambiente sandbox ──────────────────────────────────────────

os.environ["SANDBOX_MODE"] = "1"
os.environ["DMGDESK_CONFIG"] = str(SANDBOX_DIR / "sandbox_config.json")

# Telegram mock — token fittizi che non faranno mai chiamate reali
os.environ["TELEGRAM_BOT_TOKEN"] = "0000000000:SANDBOX_MOCK_TOKEN_NO_CALLS"
os.environ["TELEGRAM_CHAT_ID"] = "999999999"

print(f"\n{'='*55}")
print(f"  DMGDesk V2 — SANDBOX MODE ATTIVO")
print(f"  Data dir : {DATA_DIR}")
print(f"  Config   : {os.environ['DMGDESK_CONFIG']}")
print(f"  Telegram : MOCKATO (messaggi in console)")
print(f"{'='*55}\n")

# ── 2. Verifica dati mock esistano ────────────────────────────────────────────

if not (DATA_DIR / "DMGDesk_principale.csv").exists():
    print("⚠️  Dati mock non trovati. Esegui prima:")
    print("   python sandbox/genera_dati_mock.py\n")

# ── 3. Monkey-patch Telegram notifier ────────────────────────────────────────

try:
    # Importa il mock e sostituisce il modulo reale nel sys.modules
    sys.path.insert(0, str(SANDBOX_DIR))
    import mock_telegram as _mock_tg

    # Crea un modulo fittizio con le stesse interfacce del notifier reale
    import types
    fake_notifier = types.ModuleType("telegram_monitor.notifier")
    fake_notifier.send_message      = _mock_tg.send_message
    fake_notifier.send_alert        = _mock_tg.send_alert
    fake_notifier.send_daily_summary = _mock_tg.send_daily_summary
    sys.modules["telegram_monitor.notifier"] = fake_notifier

    print("✅ Telegram mockato — messaggi verranno stampati in console")
except Exception as e:
    print(f"⚠️  Mock Telegram non applicato: {e}")

# ── 4. Override path config ───────────────────────────────────────────────────

def get_sandbox_config() -> dict:
    """Ritorna la config sandbox completa."""
    cfg_path = SANDBOX_DIR / "sandbox_config.json"
    if cfg_path.exists():
        return json.loads(cfg_path.read_text(encoding="utf-8"))
    return {}


def patch_config_loader():
    """
    Fa il monkey-patch del config loader del backend
    per usare sandbox_config.json invece di config.json.
    """
    try:
        import database.db_handler as db
        _orig_load = db.load_config

        def _sandbox_load():
            cfg = _orig_load()
            sandbox_cfg = get_sandbox_config()
            # Override solo i path — mantieni il resto della config reale
            for key in ["percorso_nc_base", "radice", "tools_toa_folder",
                        "db_principale", "lavorazioni_log", "worktrack_projects",
                        "pallet_state", "opcua_log_path"]:
                if key in sandbox_cfg:
                    cfg[key] = sandbox_cfg[key]
            cfg["SANDBOX_MODE"] = True
            return cfg

        db.load_config = _sandbox_load
        print("✅ Config loader patchato per sandbox")
    except Exception as e:
        print(f"⚠️  Patch config loader non applicato: {e}")


patch_config_loader()
