# Analisi di sicurezza — DMG Desk / Tool Manager

**Data:** 2026-07-18 · **Perimetro:** backend FastAPI (`api/`), frontend React
(`frontend/`), relay VNC (`api/routers/schermo_live.py`), bridge Heidenhain
(`heidenhain/`), server C# DNC (`machine_server_csharp/`), bot Telegram.
**Standard di riferimento:** IEC 62443 (sicurezza sistemi di automazione
industriale — zone/condotti e requisiti fondamentali FR1–FR7), OWASP ASVS/Top 10,
principi difesa-in-profondità / minimo privilegio / deny-by-default.

> Contesto fisico: DD **comanda** la DMG DMC 160U (Sinumerik 840D PowerLine, PCU 50
> su Windows XP) e visualizza/controlla le TNC 640. Un difetto di sicurezza qui non
> è solo data-breach: è **rischio di sicurezza fisica** (avvii/movimenti macchina,
> collisioni, danni, fermo produzione).

---

## 0. Executive summary

Il codice contiene difese **ben progettate** (middleware unificato di sicurezza,
auth PIN con PBKDF2+lockout, rate-limit, security headers/CSP, CORS ristretto,
validazione input robusta su invio-NC e allegati, bridge Heidenhain
deny-by-default). **Il problema non è l'assenza di difese, ma che sono spente.**

Verificato dal vivo sul backend in produzione (2026-07-18):

- `GET /api/auth/status` → `{"auth_attiva": false}`
- `GET /api/progetti` → **HTTP 200 senza credenziali**
- `.env` reale: **non** contiene `DMG_API_KEY` né `DMG_AUTH_ENABLED`

**Oggi tutta la superficie `/api/*` è aperta sulla LAN aziendale, incluso il
controllo tastiera della CNC.** In più esistono **due canali di comando macchina
completamente non autenticati** (relay VNC in modalità dev + server C# su porta
9999). Questa è un'esposizione **attiva**, non un rischio teorico.

Priorità: prima **chiudere l'esposizione attiva** (Fase 0), poi TLS + autenticazione
dei canali di comando (Fase 1), poi segmentazione di rete e RBAC (Fase 2+).

---

## 1. Architettura e superficie di attacco

| Componente | Porta | Bind | Auth | Comanda la macchina? |
|---|---|---|---|---|
| Backend DD (FastAPI) | 8000 | `0.0.0.0` (tutta la LAN) | PIN/API-key **ma OFF** | Sì (invio NC, relay VNC) |
| Relay VNC (`/api/schermo/vnc`) | 8000 | idem | dev = **aperto** | **Sì (tastiera/mouse CNC)** |
| Server C# DNC | 9999 | TCP | **NESSUNA** | **Sì (inietta programmi NC → NCU)** |
| Bridge Heidenhain | 8010 | separato | `TNC_BRIDGE_KEY` **deny-by-default** ✓ | Sì (TNC 640) |
| STEP analyzer | 8002 | `127.0.0.1` (solo locale) ✓ | — | No |
| Bot Telegram | — | cloud | filtro `chat_id`, comandi read-only ✓ | No |

Reti: LAN aziendale `10.95.20.x` e rete di sistema `192.168.214.x`. Il PCU 50
(Windows XP, **non aggiornabile**) è raggiungibile a `10.95.20.29:5900` con la
**password VNC di fabbrica** Siemens. La NCU riceve programmi via il server C#/DNC.

---

## 2. Modello di minaccia

**Asset da proteggere:** (a) sicurezza fisica e integrità della macchina; (b)
continuità produttiva; (c) integrità dei dati (pallet, progetti, MAIN); (d)
proprietà intellettuale (programmi NC, know-how CAM).

**Attaccante ESTERNO alla rete di stabilimento** — realistico solo se esiste un
ponte verso l'esterno (VPN, Wi-Fi ospiti, dispositivo compromesso che porta dentro
un impianto). Il backend non è (per quanto verificato) esposto su Internet, ma è su
`0.0.0.0` senza TLS né auth: qualsiasi foothold sulla LAN = controllo totale.

**Attaccante INTERNO** (il vettore che hai chiesto esplicitamente di coprire):
- Insider malevolo / dipendente in uscita: oggi può comandare la macchina, alterare
  pallet/progetti, cancellare dati, senza lasciare traccia attribuibile.
- Errore in buona fede: chiunque sulla LAN può "prendere il controllo" dello schermo
  o mandare comandi per sbaglio.
- Workstation compromessa (phishing/malware su un PC dell'ufficio): il malware trova
  una API aperta e due canali di comando macchina non autenticati.

**Capacità dell'attaccante OGGI, senza alcuna credenziale:**
1. Leggere/modificare tutti i dati (`/api/progetti`, `/api/pallet`, …).
2. Prendere il controllo tastiera della DMC 160U via relay VNC.
3. Iniettare programmi NC arbitrari nella NCU via server C# porta 9999.
4. Enumerare l'intera API via `/docs` + `/openapi.json`.
5. Inviare messaggi Telegram arbitrari via `/api/telegram/test`.

---

## 3. Vulnerabilità (per gravità)

Mapping IEC 62443: FR1 Autenticazione · FR2 Autorizzazione/uso · FR3 Integrità ·
FR4 Riservatezza · FR5 Flussi di dati ristretti (segmentazione) · FR6 Audit ·
FR7 Disponibilità.

### 🔴 CRITICA

**V1 — Autenticazione disattivata in produzione** · FR1/FR2
`.env` non contiene `DMG_API_KEY` né `DMG_AUTH_ENABLED`; il blocco auth del
middleware gira solo se una delle due è impostata ([api/main.py:243](api/main.py#L243)).
Tutta la `/api/*` è aperta sulla LAN. Confermato dal vivo (`auth_attiva:false`,
`/api/progetti`→200). *Le difese esistono ([api/auth.py](api/auth.py),
[api/main.py:193-338](api/main.py#L193)) ma sono a riposo.*

**V2 — Server C# DNC su porta 9999 senza autenticazione** · FR1/FR3
`machine_server_csharp/SocketServer.cs` accetta file su TCP 9999 senza alcun
controllo, li scrive in `D:\tmp\autoimport` e lancia `transfer_dnc.vbs` che
trasferisce il programma alla NCU via DncOCX. **Chiunque raggiunga la 9999 inietta
programmi NC arbitrari nel controllo.** Il canale di comando più diretto e meno
protetto.

**V3 — Relay VNC allow-by-default + "sola visione" solo cosmetica** · FR1/FR2
[schermo_live.py:247](api/routers/schermo_live.py#L247): `if not _API_KEY and not
auth_attiva(): return True` → senza credenziali configurate chiunque apre il
WebSocket verso il controllo. Inoltre il `viewOnly` è solo lato viewer JS: il relay
è un **pump RFB bidirezionale** ([schermo_live.py:207-226](api/routers/schermo_live.py#L207))
che non filtra nulla → un client WebSocket su misura invia comunque eventi
tastiera/mouse **ignorando la sola-visione** e comanda la macchina. La password VNC
è quella **di fabbrica**.

### 🟠 ALTA

**V4 — Nessun TLS: credenziali e traffico in chiaro** · FR4
Backend HTTP su `0.0.0.0:8000` (nessun `ssl-certfile`/`.pem` nel progetto). PIN di
login, token di sessione e stream VNC viaggiano **in chiaro** sulla LAN di
stabilimento → sniffabili (ARP spoofing, port mirroring). Il token passa anche in
query string (`?token=`), che finisce nei log e nella history del browser.

**V5 — Segreti esposti: password VNC in git, token su disco** · FR4
[.env.example:44](.env.example#L44) committato con `DMG_VNC_PASSWORD=password` →
chiunque legga il repo conosce la password del controllo. Il token bot Telegram è in
chiaro in `.env` e il file `.env` **è stato committato in passato** (git history,
commit `5f6dfc9` e precedenti) → segreti da **ruotare**.

**V6 — Nessun RBAC: autenticato = tutto** · FR2
Non esiste distinzione admin/operatore. Qualsiasi PIN valido (o l'API key) apre
l'intera app: controllo macchina, cancellazione dati, reset PIN. Gli operatori
`op1`/`op2` ([api/auth.py:49](api/auth.py#L49)) sono generici e intercambiabili.
L'API key è una **master key** condivisa col servizio `cam_tracker`: se leaka →
controllo completo.

**V7 — Rete piatta: PCU XP + NCU sulla LAN aziendale** · FR5
Il PCU 50 (Windows XP, non patchabile) con password VNC di fabbrica è direttamente
sulla `10.95.20.x`, insieme ai PC d'ufficio. Violazione del principio zone/condotti
IEC 62443: la cella macchina non è isolata. *(Voce infrastrutturale, non solo
applicativa.)*

### 🟡 MEDIA

**V8 — Kill switch unico spegne tutta la sicurezza** · FR3/FR7
`DMG_DISABLE_CUSTOM_MIDDLEWARE=1` ([api/main.py:99](api/main.py#L99)) disattiva in
un colpo security headers, rate-limit, body-size **e autenticazione**. Utile in
emergenza, ma è una leva unica di bypass totale (anche per un insider).

**V9 — `/api/telegram/test` non autenticato + info disclosure** · FR1
[telegram_router.py:45](api/routers/telegram_router.py#L45) invia messaggi Telegram
arbitrari senza auth (abuso/spam del canale). `/api/telegram/status` espone `chat_id`
e path del filesystem.

**V10 — `/docs`, `/openapi.json`, `/redoc` pubblici** · FR1 (difesa in profondità)
[api/main.py:161-165](api/main.py#L161): restano accessibili anche ad auth attiva →
l'intero schema API è enumerabile senza credenziali.

**V11 — Audit incompleto + AuthGate fail-open** · FR6
Audit presente ma per **IP** (nessuna identità operatore con auth OFF). Nessun audit
su chi apre la sessione VNC / "prende il controllo" ([schermo_live.py](api/routers/schermo_live.py)
logga solo errori) né sulle mutazioni pallet. `AuthGate.jsx` va in **fail-open**: se
`/api/auth/status` non risponde, l'app si apre lo stesso.

### 🔵 BASSA

**V12 — Timing e token in query** · FR1/FR4
API key confrontata con `==` ([api/main.py:262](api/main.py#L262)) invece di
`secrets.compare_digest` (timing side-channel, marginale su LAN). Token/`api_key`
accettati in query string (esposizione nei log).

---

## 4. Roadmap di remediation

### Fase 0 — Chiudere l'esposizione attiva (oggi, ~1–2 h, coordinata) — chiude V1, mitiga V2/V3/V5

1. **Attivare l'auth** impostando NEL `.env` del backend:
   `DMG_AUTH_ENABLED=1` **e** `DMG_API_KEY=<chiave forte, es. token_urlsafe(32)>`.
   *Entrambe insieme:* gli operatori usano il PIN (il browser manda il token di
   sessione), il servizio `cam_tracker` usa l'API key. Attivare solo `DMG_API_KEY`
   romperebbe la UI browser; attivare solo l'auth romperebbe l'upload cam_tracker.
2. **Pre-impostare i PIN** degli operatori via `scripts/reset_pin.py` **prima** di
   esporre il login (altrimenti "il primo che accede sceglie il PIN" — chiunque sulla
   LAN potrebbe rivendicare gli account op1/op2).
3. **Propagare l'API key al `cam_tracker`** (config/env dell'estrattore) e riavviare
   backend + estrattore. Verificare che l'upload CAM continui.
4. **Firewall di stabilimento**: bloccare la porta **9999** (server C#) e **5900**
   (VNC del PCU) a tutto tranne l'IP del backend DD. Mitigazione immediata di V2/V3
   finché non si aggiunge auth vera a quei canali.
5. **Igiene segreti**: sostituire il valore in `.env.example` con un placeholder,
   **ruotare** il token bot Telegram, e cambiare la password VNC sul PCU se il TCU lo
   consente.

### Fase 1 — Autenticare i canali di comando + cifrare (giorni) — chiude V2/V3/V4, mitiga V10

1. **TLS sul backend**: certificato interno (come già fatto sull'istanza CAM35 porta
   8800 con `cam35.pem`). PIN e VNC smettono di viaggiare in chiaro.
2. **Autenticare il server C#**: chiave condivisa/HMAC sul socket 9999, oppure
   restringerlo a `127.0.0.1` e farlo chiamare solo dal backend (che già valida i
   nomi file in [macchina_invio.py](api/routers/macchina_invio.py)).
3. **Relay VNC deny-by-default**: invertire [schermo_live.py:247](api/routers/schermo_live.py#L247)
   in "se non configurato → NEGA" (come fa il bridge Heidenhain, [bridge.py:67](heidenhain/bridge.py#L67)).
4. **Sola-visione lato server**: far filtrare al relay i messaggi RFB client→server
   (scartare `PointerEvent`/`KeyEvent`) quando la sessione è view-only, così il flag
   non è più aggirabile.
5. **`/docs` dietro auth** in produzione (o disattivarlo).

### Fase 2 — Autorizzazione e segmentazione (settimane) — chiude V6/V7, mitiga V8/V11

1. **RBAC**: ruoli `admin` / `operatore`; separare "comanda macchina" e "reset/admin"
   dalle operazioni di sola lettura. Attribuire ogni azione all'operatore loggato.
2. **Audit delle azioni sensibili**: chi prende il controllo VNC, chi invia NC, chi
   muta pallet — con identità operatore, non solo IP.
3. **Segmentazione di rete (IEC 62443 zone/condotti)**: isolare la cella macchina
   (PCU/NCU) dietro un condotto controllato; il PCU XP non deve essere raggiungibile
   dalla LAN uffici. Compensa l'impossibilità di patchare XP.
4. **Ridurre il kill switch**: renderlo granulare (non spegnere l'auth con un flag) o
   proteggerlo/loggarlo come evento di sicurezza.
5. **AuthGate fail-closed**: su errore di `/api/auth/status`, mostrare login, non aprire.

### Fase 3 — Robustezza e monitoraggio (strutturale)

Monitoraggio/alert su tentativi di accesso e comandi macchina anomali; gestione
segreti fuori dai file piatti; policy PIN (lunghezza minima > 4 dove possibile);
`compare_digest` sull'API key; token solo via header (non query); piano di risposta
incidenti; revisione periodica.

---

## 5. Da preservare (controlli già buoni)

- Middleware di sicurezza unificato pure-ASGI ([api/main.py:193](api/main.py#L193)):
  security headers, CSP `script-src 'self'`, rate-limit mutazioni, body-size.
- Auth PIN: PBKDF2-SHA256 200k iter + salt, lockout progressivo, confronto a tempo
  costante, token opachi in memoria ([api/auth.py](api/auth.py)).
- Validazione input robusta contro path traversal in
  [macchina_invio.py](api/routers/macchina_invio.py) e [allegati.py](api/routers/allegati.py).
- Bridge Heidenhain **deny-by-default** ([heidenhain/bridge.py:67](heidenhain/bridge.py#L67))
  — modello da replicare sul relay DMG.
- Nessun `subprocess`/`eval`/`shell=True` nel web layer; CORS senza wildcard;
  `/api/debug` già bonificato da data leak.
- Bot Telegram: comandi read-only + filtro `chat_id`.

---

## 6. Sequenza consigliata

Fase 0 subito (chiude l'esposizione critica con modifiche minime e reversibili),
poi Fase 1. Le fasi 0–1 vanno **coordinate** (tocca l'auth di produzione e il
servizio cam_tracker: fatte male possono bloccare gli operatori o rompere l'upload
CAM). Nessuna modifica va applicata alla produzione senza tua conferma esplicita.
