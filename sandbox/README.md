# DMGDesk V2 — Sandbox

Ambiente di sviluppo/test isolato che gira in **parallelo** alla V16 di produzione
senza toccare dati reali, macchina reale, o Telegram reale.

## Differenze sandbox vs produzione

| Aspetto | Produzione (V16) | Sandbox (V2-dev) |
|---|---|---|
| Porta backend | 8000 | 8010 |
| Porta STEP analyzer | 8002 | 8012 |
| Dati | `P:\DMG_DMC_160U` | `./sandbox/data/` |
| OpcUaLegacy.log | Macchina reale | Generato da mock_opcua_generator.py |
| Telegram | Messaggi reali | Stampati in console |
| Config | `config.json` | `sandbox/sandbox_config.json` |
| Branch Git | `main` | `v2-sandbox` |

## Avvio rapido

```batch
# 1. Prima volta — genera dati mock
python sandbox\genera_dati_mock.py

# 2. Avvia tutto con un doppio click
AVVIA_SANDBOX.bat
```

Apri http://localhost:8010 — la produzione continua su http://localhost:8000.

## Struttura sandbox

```
sandbox/
├── sandbox_config.json       ← config con tutti i path locali
├── sandbox_env.py            ← monkey-patch per modalità sandbox
├── genera_dati_mock.py       ← genera dati fittizi realistici
├── mock_opcua_generator.py   ← simula la macchina live (log ogni 10s)
├── mock_telegram.py          ← Telegram → console
└── data/                     ← tutti i dati mock (generati)
    ├── DMGDesk_principale.csv
    ├── DMGDesk_smontati.csv
    ├── DMGDesk_scaffale.csv
    ├── DMGDesk_holder.csv
    ├── OpcUaLegacy.log
    ├── lavorazioni_log.json
    ├── worktrack_projects.json
    ├── pallet_state.json
    ├── tool_replacements.json
    ├── step_features.json
    └── nc_programs/
        └── SANDBOX_4201_WPD/
```

## Rigenerare i dati mock

```batch
python sandbox\genera_dati_mock.py
```

Sovrascrive tutti i dati in `sandbox/data/` con dati fittizi freschi.

## Workflow sviluppo V2

```
git checkout v2-sandbox        # branch sandbox
# ... sviluppa feature ...
git commit -m "v2: nuova feature"
git push origin v2-sandbox     # push sandbox, main non tocco

# Quando feature è pronta:
git checkout main
git merge v2-sandbox --no-ff
git push origin main
```

## Variabili d'ambiente attive in sandbox

```
SANDBOX_MODE=1
DMGDESK_CONFIG=./sandbox/sandbox_config.json
TELEGRAM_BOT_TOKEN=SANDBOX_MOCK
TELEGRAM_CHAT_ID=0
```

## Aggiungere nuovi dati mock

Modifica `sandbox/genera_dati_mock.py` — aggiungi commesse, utensili,
sessioni extra e riesegui lo script.

## Note

- La sandbox **non scrive mai** su `P:\` o sulla macchina reale
- Il mock OpcUa simula cicli macchina realistici (lavora/ferma/reset)
- I messaggi Telegram appaiono nel terminale "MockOpcUa" con prefisso `[SANDBOX TELEGRAM]`
- `sandbox/data/` è in `.gitignore` — i dati mock non vengono committati
