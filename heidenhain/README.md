# Heidenhain TNC 640 — bridge di visualizzazione/monitoraggio (ambiente Yellow Hub)

Bridge per vedere e monitorare da remoto le macchine con controllo **HEIDENHAIN
TNC 640** (HEROS) — le **Mikron P800**, che sono ambiente **Yellow Hub**.
Vedi il report completo: [`../REPORT_HEIDENHAIN_TNC640_REMOTE.md`](../REPORT_HEIDENHAIN_TNC640_REMOTE.md).

> ⚠️ **Yellow Hub ≠ DMG desk.** Queste macchine (TNC 640) sono di **Yellow Hub**,
> NON di DMG desk (l'app di questa repo, per la DMG DMC 160U con Sinumerik). Il
> bridge è **standalone e senza alcun aggancio a DMG desk**: è staged qui solo sul
> branch `feature/heidenhain-tnc640` in attesa di essere integrato in Yellow Hub
> (vedi [WIRING.md](WIRING.md)).

## Verifica sul campo (2026-07-16) — 2 × Mikron P800

Due macchine, **configurazione identica** (in `config.py`):

| id | nome | IP | esito |
|---|---|---|---|
| `p800-1` | Mikron P800 #1 | `192.168.244.149` | ✅ VNC + LSV2/DNC ok |
| `p800-2` | Mikron P800 #2 | `192.168.244.150` | ✅ VNC + LSV2/DNC ok |

Entrambe: TNC 640, **NC SW 340590-08 SP7**, VNC aperto senza password, opzione 18
(DNC) attiva, dati strutturati live. Dettaglio sotto (rilevato su `p800-1`):

| Canale | Porta | Esito | Note |
|---|---|---|---|
| **VNC (schermo)** | 5900 | ✅ **funziona** | Handshake `RFB 003.008`, desktop `HEROS5:0` 1280×1024, **auth None (nessuna password)**. Screenshot completo catturato con client RFB stdlib. |
| **LSV2 (dati/file)** | 19000 | ✅ **funziona** | `versions`, lista/trasferimento file, `grab_screen_dump` OK. |
| **Dati strutturati LSV2 (DNC)** | 19000 | ✅ **disponibili** | **Opzione 18 (DNC) ATTIVA** (la usa anche il MES). Assi, override feed/rapid/spindle, stato programma/esecuzione, programma+sottoprogramma+riga. Serve `safe_mode=False` **oppure** aggiungere il login DNC ai login noti (vedi sotto). |
| OPC UA NC Server | — | ❌ non disponibile | Richiede NC SW ≥ `-10`; qui `-08`. Ma non serve: LSV2+DNC basta. |

**Conseguenza pratica**: su questa macchina **lo schermo (VNC)** e i **dati
strutturati (LSV2+DNC)** funzionano entrambi, gratis con codice nostro — copre sia
il "vedere/comandare lo schermo" sia il monitoraggio numerico (come il Sinumerik).

### ⚠️ Nota importante sul login DNC (pyLSV2 safe_mode)
Con `pyLSV2.LSV2(..., safe_mode=True)` la libreria **esclude DNC** dai login noti
(whitelist: INSPECT/FILETRANSFER/MONITOR) e i dati di stato tornano vuoti → si
poteva credere erroneamente che l'opzione 18 non fosse attiva. In realtà lo è.
Il collector mantiene `safe_mode=True` (comandi di scrittura bloccati) e aggiunge
**solo** il login DNC per la lettura:
```python
con = pyLSV2.LSV2(ip, port=19000, safe_mode=True); con.connect()
con._known_logins = tuple(set(con._known_logins) | {pyLSV2.Login.DNC})  # solo lettura
```

## Cosa c'è in questo scaffold (tutto testato, salvo 🟡)

| File | Contenuto | Stato |
|---|---|---|
| `tnc_client.py` | Client SOLA LETTURA: cattura schermo VNC/RFB (stdlib) + info LSV2 (pyLSV2) | ✅ testato su macchina |
| `bridge.py` | App FastAPI standalone: viewer + `/screenshot.png` + `/api/info` | ✅ testato (TestClient) |
| `viewer.html` | Visualizzatore live via auto-refresh dello screenshot | ✅ funziona |
| `requirements.txt` | Dipendenze | — |
| `tools/Test-TncVnc.ps1` | Diagnosi porte + handshake RFB da PowerShell | ✅ testato |
| `tools/Test-TncVncAuth.ps1` | Rileva se il VNC richiede password | ✅ testato |

## Setup (una volta) — client noVNC

Il client noVNC (per lo schermo live) NON è versionato (come i node_modules). Clonalo:
```sh
git clone --depth 1 https://github.com/novnc/noVNC heidenhain/vendor/noVNC
```

## Accesso admin (richiesto)

Tutte le pagine/endpoint macchina sono protetti dalla **chiave propria del bridge
`TNC_BRIDGE_KEY`** (nessun aggancio a DMG desk). Se non è configurata, il bridge è
**chiuso**.
```sh
# PowerShell:  $env:TNC_BRIDGE_KEY = "la-chiave-del-bridge"
```
Vie d'accesso: aprendo una pagina qualsiasi senza cookie compare un **form di
login** (digiti la chiave → cookie impostato → torni alla pagina richiesta).
In alternativa: header `X-API-Key: LA_CHIAVE` o query `?api_key=LA_CHIAVE`.
`GET /healthz` resta aperto. In fase di integrazione, l'auth vera sarà quella di
**Yellow Hub** (vedi [WIRING.md](WIRING.md)).

**Integrazione nel frontend Yellow Hub**: template React pronto in
`heidenhain/frontend/Macchine.jsx` (iframe al bridge) — istruzioni in
[WIRING.md](WIRING.md). Il codice di YH non è in questa repo.

## Avvio

```sh
# dalla root del repo (macchine in config.py; override via env TNC_MACHINES)
py -m uvicorn heidenhain.bridge:app --host 0.0.0.0 --port 8010
```

1. Apri `http://localhost:8010/login?api_key=LA_CHIAVE` → imposta il cookie admin.
2. Vai su `http://localhost:8010/` → elenco macchine.
3. Clic su una macchina → **schermo live fluido (noVNC) + pannello dati**.

Endpoint (multi-macchina, `{mid}` = `p800-1` | `p800-2`; tutti admin salvo dove indicato):
- `GET /` — elenco macchine
- `GET /m/{mid}` — **viewer LIVE fluido** (noVNC) + pannello dati — default *sola visione*
- `WS  /m/{mid}/vnc` — relay WebSocket ↔ VNC 5900
- `GET /api/machines` — lista macchine
- `GET /api/m/{mid}/info` — stato live (versione, assi, programma+riga, override)
- `GET /api/m/{mid}/connettivita` — check porte 5900/19000
- `GET /login?api_key=...` — imposta cookie admin (aperto)
- `GET /healthz` — stato bridge (aperto)

> Lo screenshot statico è stato rimosso: si usa solo la vista live. La funzione di
> cattura resta come utility in `tnc_client.screenshot_png` (usata per diagnostica).

Diagnosi rapida da PowerShell (senza avviare il bridge):
```powershell
.\heidenhain\tools\Test-TncVnc.ps1 -Ip 192.168.244.149   # oppure .150
```

## Limiti attuali (onestà)

- Il viewer è a **auto-refresh di screenshot** (alcuni fps), non streaming fluido.
  Il **live vero** (fluido + comando mouse) è il prossimo passo con noVNC (sotto).
- Quando il monitor del controllo va in **standby**, lo screenshot è **nero**: è il
  comportamento reale del framebuffer. Risvegliarlo richiederebbe un input (che
  qui NON inviamo, per sicurezza).
- `spindle_tool_status` (numero utensile) torna `None` su questo controllo: il
  numero utensile va letto altrimenti (es. PLC diretto) — da fare.
- `get_error_messages` logga un warning "does not work for all control types" ma
  non blocca (torna lista vuota).

## 🟡 Prossimo passo — schermo live fluido con noVNC

L'obiettivo finale (uguale al software OEM) è lo streaming fluido + comando mouse,
integrato nel frontend React. Ricetta:

1. Backend: `pip install websockify`, poi proxy WebSocket → VNC del controllo:
   ```sh
   websockify --heartbeat 30 6080 192.168.244.149:5900
   ```
   (in produzione: avviarlo come processo gestito dal backend, uno per macchina.)
2. Frontend React: dipendenza `@novnc/novnc`, componente che monta `RFB`
   puntando a `ws://<host>:6080/`:
   ```js
   import RFB from '@novnc/novnc/core/rfb';
   const rfb = new RFB(containerEl, 'ws://HOST:6080/', { /* credentials se password */ });
   rfb.viewOnly = true;              // default SOLA VISIONE
   // "prendi il controllo" => rfb.viewOnly = false (azione esplicita, vedi sicurezza)
   ```
3. Endpoint `/api/heidenhain/tick` per i dati (quando opzione 18 disponibile) →
   gemello di `/api/macchina-live/tick` del Sinumerik.

## ⚠️ Sicurezza (importante)

- Sulla macchina di test il **VNC è aperto senza password**: chiunque in rete può
  **vedere e comandare** il controllo. Prima di andare in produzione:
  - impostare una **password VNC** a bordo (*Settings → VNC*) e gestirla nel bridge;
  - **segmentare la rete** / limitare l'accesso alla porta 5900;
  - nel frontend, tenere il default **sola visione** e rendere il "prendi il
    controllo" un'azione esplicita e tracciata (rispetto dell'arbitraggio **VNC
    Focus** quando c'è un operatore alla macchina).
- Questo scaffold **non invia alcun comando** alla macchina: solo lettura di
  schermo, file e info. `safe_mode=True` su pyLSV2.
