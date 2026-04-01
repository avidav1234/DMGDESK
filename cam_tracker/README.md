# CAMTracker — Modulo DMGDesk

Monitora **Cimatron** su CAM35, rileva il progetto attivo, accumula le ore CAM
e le invia a DMGDesk via REST API.

## Struttura del modulo

```
cam_tracker/
├── cam_tracker.py          # Agente Python — gira su CAM35
├── cam_tracker_config.ini  # Config (auto-generata al primo avvio)
├── cam_tracker.log         # Log operativo
├── cam_sessions_pending.json  # Payload in attesa se DMGDesk offline
└── README.md               # Questo file

api/routers/
└── cam_tracker_router.py   # Endpoint FastAPI (/api/cam-tracker/*)

frontend/src/pages/
└── CamTracker.jsx          # Pagina React (sidebar: Utilità → CAM)
```

## Setup su CAM35

### 1. Requisiti

```
pip install requests pythonnet pywin32
```

`pythonnet` serve per la COM API di Cimatron.
`pywin32` serve per il fallback via titolo finestra (win32gui).

### 2. Configurazione Cimatron (pythonnet manifest)

Per usare le Interop DLL di Cimatron con Python è richiesta
la registrazione del manifest. Seguire la guida ufficiale:
https://api.cimatron.com/assets/docs/introduction/standaloneapplication_python.htm

In breve:
1. Creare `python.manifest` nella cartella di CimatronE.exe
2. Associarlo a `python.exe` con `mt.exe`:
   ```
   mt.exe -manifest "python.manifest" -updateresource:"python.exe;#1"
   ```

### 3. Config

Al primo avvio viene creato `cam_tracker_config.ini`. Editare:

```ini
[dmgdesk]
url = http://IP_DMGDESK:8000        ; IP del server DMGDesk
flush_interval_sec = 300            ; ogni 5 minuti invia i dati

[cimatron]
program_dir = C:\Program Files\Cimatron\Cimatron\2024.0\Program
poll_interval_sec = 10              ; polling ogni 10 secondi

[tracker]
workstation = CAM35
min_session_sec = 30                ; sessioni < 30s vengono scartate
```

### 4. Avvio

```bash
python cam_tracker.py
```

Per avvio automatico con Windows: creare un task in Task Scheduler
con trigger "All'accesso" che esegue `python cam_tracker.py`.

## API endpoints

| Metodo | Path | Descrizione |
|--------|------|-------------|
| POST | `/api/cam-tracker/sessions` | Riceve sessioni da CAM35 |
| GET  | `/api/cam-tracker/sessions` | Lista sessioni (filtrabili) |
| GET  | `/api/cam-tracker/summary`  | Ore totali per progetto |
| GET  | `/api/cam-tracker/today`    | Solo oggi |
| DELETE | `/api/cam-tracker/sessions/{project}` | Reset progetto |

## Modalità di aggancio a Cimatron

1. **COM API** (primaria): si aggancia all'istanza Cimatron aperta via
   `CimAppAPI.CimApplication()` e legge `ActiveDocument.FullName`.
   Richiede pythonnet + manifest configurato.

2. **Window Title** (fallback): scansiona tutte le finestre aperte cercando
   "Cimatron" nel titolo ed estrae il nome file con regex.
   Funziona senza pythonnet ma meno precisa.

## Nome progetto

Il nome progetto estratto da Cimatron è il **nome del file senza estensione**
in maiuscolo. Esempio:
- File aperto: `C:\Progetti\FLANGIA_BASE\operazione_OP10.elt`
- Progetto rilevato: `OPERAZIONE_OP10`

Se la convenzione di naming Cimatron include il codice commessa nel nome file
(es. `DMG_FLANGIA_OP10.elt`) il codice viene estratto automaticamente.
