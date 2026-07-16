# Heidenhain TNC 640 — Visualizzazione e controllo remoto: report tecnico per soluzione DIY

> **Contesto**: nuovo progetto collegato a "yellow hub". Officina con DMG/Sinumerik
> già integrata via OPC UA in un backend FastAPI + frontend React. Obiettivo:
> replicare lo stesso approccio per una macchina con controllo **HEIDENHAIN TNC 640**
> — vedere lo schermo e (potenzialmente) comandare la macchina da remoto —
> costruendo in casa il visualizzatore/controller invece di comprare la soluzione
> commerciale.
>
> **Stato**: da tenere in un branch separato, integrazione successiva.
>
> **Nota sulla ricerca**: le fonti sono state raccolte da 18 sorgenti (in gran
> parte documentazione ufficiale HEIDENHAIN e repository open source). La fase
> automatica di cross-verifica a 3 voti è stata interrotta dal limite di sessione;
> per questo ogni affermazione qui sotto è ancorata a una **citazione diretta**
> della fonte primaria (vedi sezione Fonti). Tre affermazioni chiave hanno
> comunque superato la verifica a 3 voti (marcate ✓✓✓).

---

## 1. TL;DR — risposta secca

> ⚡ **AGGIORNAMENTO (2026-07-15) — la vera risposta al caso reale.** Evidenza dal
> committente: il software fornito a suo tempo dall'OEM mostrava lo schermo del
> controllo **fluidissimo, come un video**, e permetteva di **operare col mouse**
> (cambio modalità, apertura tabelle/viste). **Questo è VNC**, non uno screendump.
> Il TNC 640 gira su **HEROS (Linux)** che ha un **server VNC integrato** (manuale
> utente TNC 640, funzione *Settings → VNC*): un client VNC remoto vede e
> **comanda** il controllo con mouse/tastiera. Il software OEM era quasi
> certamente **solo un client VNC** (o il RemoteAccess/TeleService di HEIDENHAIN)
> collegato a quel server già presente sulla macchina. → **Tutto il necessario è
> già a bordo macchina; va solo abilitato/configurato.** Vedi §4.0.

1. **Vedere E comandare lo schermo live è già possibile a costo zero via VNC**:
   HEROS espone un server VNC (porta standard 5900). Un qualsiasi VNC viewer, o
   `noVNC` embeddato nel frontend React, dà lo schermo fluido + controllo mouse
   — esattamente ciò che l'OEM faceva pagare. La funzione VNC **non risulta tra
   le opzioni SIK a pagamento** (a differenza del Remote Desktop Manager #133,
   che è tutt'altra cosa). Vedi §4.0.
2. **Il monitoraggio dello stato (assi, override, programma attivo, utensile,
   PLC) è fattibile in casa e gratis** con `pyLSV2` (Python puro, MIT, testato
   su TNC 640 reale). Complementare al VNC: VNC per vedere/comandare, pyLSV2 per
   estrarre dati strutturati da mettere nel yellow hub.
3. **Alternative ufficiali a pagamento** (utili solo come benchmark/prezzo di
   riferimento): `RemoteAccess` + *Secure Remote Access* (live + comando +
   cifratura Internet) e `TNCremoPlus` (*live screen*, solo visione). Fanno ciò
   che HEROS-VNC + noVNC fanno gratis in LAN.
4. **Pilotare la macchina da MES/automazione (start/stop programma, override
   programmatici, non via mouse)** è un discorso diverso: possibile solo tramite
   `OPC UA NC Server` (opzioni a pagamento 56–61) e **solo se il PLC del
   costruttore lo consente + l'utente ha il diritto `NC.RemoteProgramRun`**. Via
   LSV2/pyLSV2 il comando è **bloccato da un lockout** per sicurezza. Il comando
   "umano" via mouse invece passa dal VNC (punto 1).
5. **Attenzione safety/OEM**: dare il controllo mouse da remoto mentre un
   operatore è alla macchina richiede l'arbitraggio **VNC Focus** di HEROS; il
   costruttore può aver bloccato/vincolato l'accesso VNC esterno via PLC — è
   probabilmente l'unica cosa che l'OEM può davvero "far pagare" (una
   configurazione, non un hardware). Vedi §4.0 e §6.

---

## 2. Tabella comparativa delle vie di integrazione

| Via | Opzione sul controllo | A pagamento? | Legge stato | Trasferisce file | Vede lo schermo | Pilota (start/stop/override) | Stack adatto a yellow hub? |
|---|---|---|---|---|---|---|---|
| **VNC server HEROS** ⭐ | Ethernet (#16) — VNC in HEROS | **No** (non è opzione SIK) | — (schermo) | No | **Live + mouse/tastiera** ✅✅ | Via mouse (come l'operatore) | ✅✅ **noVNC in React** |
| **LSV2 / TNCremo** (gratis) | Ethernet (#16) | No (TNCremo gratis) | Sì (parziale senza opt.18) | Sì | Screenshot statico | No (remote control solo seriale) | ⚠️ via pyLSV2 |
| **pyLSV2** (open source) | Ethernet (#16) | No | Sì | Sì | Screendump periodico | **No — bloccato da lockout** | ✅ Python nativo |
| **TNCremoPlus** | Ethernet (#16) | Sì (ID 340447-xx) | Sì | Sì | **Live screen** ✅ | No | ❌ tool desktop chiuso |
| **RemoteAccess** | — (software PC HEIDENHAIN) | Sì (ID 1339577-01…) | Sì | — | **Live + tastiera** ✅ | **Sì (opera il controllo)** | ❌ prodotto chiuso |
| **HEIDENHAIN DNC** (RemoTools SDK) | **Opzione 18** (ID 526451-01) | Sì (opt.18 + SDK ID 340442-xx) | Sì (completo) | Sì | Screenshot | **Sì** (select/start/stop, override) | ❌ COM/Windows only |
| **OPC UA NC Server** | **Opzioni 56–61** (ID 1291434-01…-06) | Sì (1 opz. = 1 connessione) | Sì (read/write var.) | Sì (Part 20) | No | **Sì** (Start/Stop/Cancel + override, con vincoli) | ✅✅ **Python `asyncua`** |
| **StateMonitor** | Opzione 18 (o OPC UA) | Sì (licenze multiple) | Sì (sola lettura) | No | No | No | ❌ prodotto chiuso |
| **Remote Desktop Manager** | **Opzione 133** (ID 894423-01) | Sì | — | — | **Direzione opposta** (PC→TNC) | No | ❌ non pertinente |
| **ITC** (thin client HW) | — | Sì (hardware) | — | — | **Mirror HW 1:1** (locale, non IP) | No | ❌ postazione locale |
| **CNCnetPDM** (3° parte) | Ethernet (#16) | Sì (commerciale) | Sì (legge/scrive PLC) | — | No | Scrittura PLC limitata | ⚠️ chiuso |

> Legenda opzioni SIK del TNC 640: `#16` Ethernet · `#18` HEIDENHAIN DNC ·
> `#56–61` OPC UA NC Server 1–6 · `#133` Remote Desktop Manager · `#137` State
> Reporting.

---

## 3. Dettaglio delle interfacce ufficiali

### 3.1 LSV2 + TNCremo (la base gratuita)
- **TNCremo** è il pacchetto PC **gratuito** che usa il protocollo **LSV2** per
  parlare col TNC via Ethernet: trasferimento programmi/tabelle utensili/pallet,
  backup, creazione file di service, **screenshot statico** del controllo,
  lettura del log e campionamento dello stato macchina. ✓✓✓
- **Limite chiave**: il "remote control" completo di TNCremo è dichiarato
  disponibile **solo via seriale**, non su Ethernet. Il **live screen** non c'è:
  serve TNCremoPlus.
- LSV2 usa un **modello di login a livelli** (`INSPECT` < `DN` < `DNC`): alcune
  letture (es. posizioni assi X/Y/Z) funzionano già col login base `INSPECT`
  **senza opzione 18**; la lettura dello **stato programma** richiede il login
  `DNC`, che a sua volta **richiede l'opzione 18 attiva** sul controllo.
- **Discontinuazione**: su forum (marzo/giugno 2024, quindi affidabilità media)
  si riporta che HEIDENHAIN ha annunciato la fine di LSV2 sui *nuovi* CNC entro
  ~2-3 anni, con successore la connessione DNC/RemoTools. **Per il TNC 640 non è
  un problema pratico**: è una generazione con sviluppo ormai interrotto, LSV2
  resterà per tutta la vita della macchina (TNCremo e i tool OEM lo usano ancora).

### 3.2 HEIDENHAIN DNC — opzione 18 + RemoTools SDK
- **Opzione software n. 18** (ID `526451-01`), disponibile su TNC 640 dal NC SW
  `34059x-01`. Su controlli SIK2 (TNC7) l'opzione equivalente è `3-03-1`. ✓✓✓
- Abilita un'app Windows a **leggere e modificare** i dati del TNC. Funzioni
  documentate: selezionare/avviare il programma NC, interromperlo (subito o a un
  blocco), leggere/cambiare il modo operativo, leggere/**modificare gli override**,
  **screenshot** del controllo, **read/write della memoria PLC** (marker, counter,
  timer, byte, word, dword, string), trasferimento file. Include quindi **pieno
  pilotaggio**.
- **Si sviluppa con RemoTools SDK** (accessorio ID `340442-xx`, V3.1 = `340442-31`):
  è un **componente Microsoft (D)COM**, richiede **Windows 7/8/10** e linguaggi
  COM (C++, C#, VB.NET, scripting Windows). **Non è utilizzabile nativamente da
  uno stack Linux/Python** senza un ponte intermedio (es. un microservizio C#/.NET
  su Windows — analogo al tuo `machine_server_csharp` per il Sinumerik).
- **Avvertenza HEIDENHAIN**: la comunicazione DNC **non è hard real-time**; i
  tempi di reazione dipendono dal carico di rete. Rilevante per qualsiasi logica
  di controllo.
- L'installazione dell'opzione 18 è **a carico del costruttore della macchina** (OEM).

### 3.3 OPC UA NC Server — opzioni 56–61 (la via "gemella" del Sinumerik)
- **Sei opzioni SIK separate**, `#56`–`#61` (ID `1291434-01` … `-06`): **ogni
  opzione = una connessione OPC UA client concorrente**. Su TNC 640 richiede
  **NC SW `34059x-10` o successivo** e **adattamento OEM**. **Non** richiede
  RemoTools SDK.
- Interfaccia **standardizzata e platform-independent** (identica come filosofia
  all'OPC UA che già usi sul Sinumerik). Funzioni: lettura/scrittura variabili,
  subscription a cambi valore, esecuzione metodi, eventi, trasferimento file
  (OPC UA Part 20 — file system TNC e PLC).
- **Controllo esecuzione programma**: espone la state machine `NCProgramStateMachineType`
  con metodi `SelectProgram`, `Start`, `Stop`, `Cancel`, `SelectBlockNumber` e
  stati osservabili (`Idle`, `Running`, `Stopped`, `Interrupted`, `Error`, `Finished`).
- **Override** (`FeedOverride`, `RapidOverride`, `SpeedOverride`, 0–150%) sono
  **variabili scrivibili**.
- **Vincoli di sicurezza sul comando** (importantissimi): lo start remoto funziona
  **solo se** (1) il **PLC del costruttore** supporta lo start esterno
  (`ApiChn.NN_ChnNcStartExternRequest`) **e** (2) l'utente client ha il diritto
  **`NC.RemoteProgramRun`**; altrimenti la richiesta è respinta con
  `BadUserAccessDenied`.
- **Autenticazione**: certificati X.509 (default) o user/password; permessi via
  user administration del controllo; connection wizard per l'integrazione IT/OT.
- **Versioni firmware**: OPC UA compare sul TNC 640 dal NC SW `34059x-10`
  (Core Information Model 1.00). Il TNC 640 si ferma al modello **1.04** (da
  `34059x-18`); NC SW **19+** (modelli 1.05–1.07) esistono **solo per TNC7**.
  → **Sotto `34059x-10` l'OPC UA NC Server non esiste affatto**: la versione
  firmware installata in officina è la prima cosa da verificare.

### 3.4 RemoteAccess — l'esatto equivalente commerciale della tua idea
- Software ufficiale HEIDENHAIN che **replica l'interfaccia del controllo sul PC**
  e permette di **comandarlo da remoto** tramite live view + tastiera integrata.
  Licenza singola ID `1339577-01`, di rete `-02`/`-03`.
- **Secure Remote Access** (ID `1356741-01`) aggiunge la connessione **cifrata via
  Internet**.
- È letteralmente "il visualizzatore + controller da remoto" che vuoi costruire:
  utile come benchmark funzionale e come prezzo di riferimento contro cui valutare
  il DIY.

### 3.5 Remote Desktop Manager — opzione 133 (attenzione: direzione opposta!)
- **Opzione 133** (ID `894423-01`), TNC 640 dal NC SW `34059x-02`. ✓✓✓
- **NON serve a vedere lo schermo del TNC da un PC remoto.** Funziona
  all'**inverso**: mostra sullo **schermo del TNC** il desktop di **PC Windows
  esterni** (in rete o un IPC nell'armadio), per usare CAD/MES/ERP direttamente
  in macchina. Il TNC fa qui da **client VNC verso altri PC**.
- ⚠️ **Da non confondere** con il **server VNC di HEROS** (§4.0), che è la
  funzione opposta e gratuita: fa vedere/comandare lo schermo **del TNC** da un
  PC remoto. Sono due cose diverse — il Remote Desktop Manager (#133, a pagamento)
  **non** è ciò che serve al caso del committente.
- Connessioni supportate (come client): Windows Terminal Server (RemoteFX), VNC,
  SSH, XDMCP, ecc.
- **Garanzia HEIDENHAIN solo** per la combinazione **HEROS 5 + IPC 6641**; altre
  combinazioni sono senza garanzia.

### 3.6 StateMonitor — monitoraggio commerciale (sola lettura)
- Software su host **Windows**, cattura **in sola lettura**: modi operativi,
  override (mandrino/rapido/avanzamento), stato e nome programma, runtime,
  SIK/software, messaggi macchina. **Nessun** controllo, mirroring o pilotaggio.
- **Prerequisito**: opzione 18 (DNC) attiva sul controllo — **non inclusa** nel
  prodotto, va abilitata a parte. In alternativa collega via OPC UA/MTConnect/Modbus TCP.
- **TNC 640 supportato** (tutti gli NCK con opzione 18). Collegabili anche macchine
  vecchie (da iTNC 530 sw `340490-03`, 2006). Collegamento ~3 minuti.
- **Licenze**: base ID `1218930-xx`, +5 macchine `1220884-xx`, moduli OPC UA
  Interface `1268673-xx`, Modbus, MTConnect, JobTerminal. Disponibile anche a
  **noleggio** (min. 6 mesi, ID `1432346-MA`), **prezzo solo su richiesta**.
- Rilevante come confronto: fa **meno** di quello che vuoi (niente schermo/comando)
  e costa comunque licenze + opzione 18.

### 3.7 ITC — Industrial Thin Client (mirroring hardware, ma locale)
- ITC 755/750/860: dopo il boot **replicano 1:1 lo schermo del TNC** via Ethernet
  (porta X116, cavo fino a 100 m), plug-and-play. È mirroring **hardware** per una
  **postazione operatore locale**, non un flusso IP verso un PC remoto arbitrario.

---

## 4.0 ⭐ Server VNC di HEROS — la vera risposta (schermo live + comando mouse)

**Questa è la via che risolve il caso reale del committente** (schermo fluido come
video + mouse per cambiare modalità/aprire tabelle) — ed è **già presente sulla
macchina, senza opzioni a pagamento**.

> ✅ **VERIFICATO SUL CAMPO (2026-07-16)** — macchina **Mikron P800** (GF), TNC 640,
> IP `192.168.244.149`:
> - Porta **5900 aperta**, handshake **`RFB 003.008`**, desktop **`HEROS5:0` 1280×1024**.
> - Autenticazione offerta: **solo "None" → nessuna password**.
> - **Cattura di un fotogramma completo dello schermo riuscita** con un mini-client
>   RFB in Python (solo stdlib, encoding Raw) — schermo di controllo reale acquisito
>   perfettamente, **senza alcun software OEM**. Script: `scratchpad/vnc_grab.py`.
> - Porta **19000 (LSV2) aperta**. Firmware **`340590 08 SP7`** (NC SW `-08`).
> - **Opzione 18 (DNC) ATTIVA** (confermato: la usa anche il MES): via pyLSV2 si
>   leggono **dati strutturati live** — assi (X/Y/Z/A/C), override feed/rapid/spindle,
>   stato programma (`STARTED`/`AUTOMATIC`), programma+sottoprogramma+riga. Nota: in
>   `pyLSV2` con `safe_mode=True` il login DNC è escluso dai login noti → sembra
>   inattivo; va aggiunto esplicitamente (solo lettura). **OPC UA non serve** (e non
>   c'è: richiede NC SW ≥ `-10`).
> - ⚠️ **Security**: VNC senza password sulla LAN = chiunque in rete può vedere **e
>   comandare** la macchina. Valutare password VNC (Settings → VNC), segmentazione
>   rete, e gating del "prendi il controllo" a livello app.
>
> **Conclusione**: il dispositivo/licenza che l'OEM vuole rivendere per la sola
> visione/comando schermo **non è necessario**. Serve solo un client (noVNC nel
> yellow hub).

- Il TNC 640 gira su **HEROS**, un sistema **Linux** HEIDENHAIN, che include un
  **server VNC**. Nel manuale utente del TNC 640 la funzione è documentata come
  *Settings → VNC* (accessibile da: taskbar in basso → tasto verde HEIDENHAIN →
  menu JH → *Settings → VNC*).
- Citazione dal manuale: *"Use the VNC function to configure the behavior of the
  various VNC clients. This includes, for example, operation via soft keys, mouse
  and the ASCII keyboard."* → conferma che un client VNC remoto **opera** il
  controllo (non solo lo guarda).
- **Porta**: 5900 (standard VNC).
- **Nessuna opzione SIK a pagamento** risulta associata al server VNC: il manuale
  non lo elenca tra le opzioni (diversamente dal Remote Desktop Manager #133).
  È funzione di HEROS.
- **Client**: qualsiasi VNC viewer (RealVNC/TightVNC/UltraVNC) oppure **noVNC**
  (client VNC in browser via WebSocket) — quest'ultimo è la chiave per integrarlo
  **direttamente nel frontend React del yellow hub**, senza installare nulla sui
  PC degli utenti.

### Sicurezza e accesso concorrente — VNC Focus
- HEROS ha un **gestore del "focus" VNC**: quando più client (incluso l'operatore
  fisico alla macchina) potrebbero comandare, il sistema **arbitra chi ha il
  controllo** e, di default, **impedisce a due utenti di operare simultaneamente**.
- Impostazioni *VNC Focus*: client `Manual` (inserito a mano), `Denied` (non
  ammesso), `TeleService/IPC 61xx`, client DHCP. Si imposta anche una **password**
  per la connessione.
- ⚠️ **Punto OEM**: il costruttore della macchina può aver **vincolato via PLC**
  l'accesso VNC esterno o la concessione del focus (il manuale rimanda a
  *"Refer to your machine manual"* per l'assegnazione del focus). **È molto
  probabilmente questo — una configurazione, non un hardware — ciò che l'OEM
  vuole rivendere.** Da verificare a bordo macchina.

### Perché "ha smesso di funzionare"? Ipotesi da verificare
Dato che l'hardware/funzione è a bordo, la perdita di funzionalità dopo il
cambio proprietà/software dell'OEM è quasi certamente **configurazione, non
capacità mancante**. Cause tipiche:
1. Il **client software** dell'OEM (VNC viewer ribattezzato o TeleService/RemoteAccess)
   non è più licenziato/aggiornato → sostituibile con un VNC viewer/noVNC qualsiasi.
2. Un **aggiornamento HEROS** ha riattivato firewall / user administration →
   la porta 5900 va ri-permessa (HEROS *Settings → Firewall*) o serve un tunnel SSH.
3. La **password / lista client VNC** o l'assegnazione del **focus** è stata
   resettata.
4. Il "**dispositivo**" che vogliono sostituire era un **IPC** (PC industriale)
   che ospitava il loro client e la rotta di rete/VPN → la sua **funzione** si
   rifà con un PC/mini-PC qualsiasi che esegue il viewer o il server noVNC.

### Cosa verificare a bordo macchina (checklist operativa)
- [ ] Versione HEROS / NC SW (MOD → SIK): serve per capire firewall/user-admin.
- [ ] *Settings → VNC*: il servizio è attivo? Ci sono client permessi? Password?
- [ ] *Settings → Firewall*: la porta **5900** (VNC) è consentita? (o serve SSH)
- [ ] IP del controllo sulla rete officina e raggiungibilità (ping).
- [ ] Esiste un vincolo OEM/PLC sul focus VNC? (manuale macchina / costruttore)
- [ ] Prova: da un PC in rete, VNC viewer → `IP_controllo:5900` + password.

---

## 4. Come "vedere lo schermo": le strade a confronto

| Strada | Tipo | Costo | DIY? |
|---|---|---|---|
| **VNC server HEROS** ⭐ | **Live fluido + comando mouse/tastiera** | **Gratis** (già a bordo) | ✅✅ **Sì (noVNC in React)** |
| `pyLSV2` screendump | Immagini statiche periodiche (es. ogni 3–10 s) | Gratis | ✅ Sì (solo visione) |
| `TNCremoPlus` *live screen* | Streaming live schermo → PC (sola visione) | A pagamento (ID 340447-xx) | ❌ tool chiuso |
| `RemoteAccess` (+ Secure) | Live + comando + cifratura Internet | A pagamento | ❌ prodotto chiuso |

**La strada giusta per il caso del committente è la prima (VNC).** Lo screendump
pyLSV2 resta utile come *fallback* di sola visione o per catturare snapshot da
salvare/notificare; TNCremoPlus e RemoteAccess sono gli equivalenti commerciali a
pagamento (benchmark di prezzo).

**Realtà pratica**: già nel 2012 c'era chi catturava screenshot statici del TNC
ogni pochi minuti + SMS a fine/errore per telemonitorare lavorazioni non
presidiate — **lo stesso identico caso d'uso** (weekend/notte, "vedere lo schermo
da laptop/smartphone, notifica a fine job"). Il DIY via screendump periodico è
una strada battuta e sufficiente per il monitoraggio; il *live* video vero rimane
appannaggio dei prodotti a pagamento.

---

## 5. Open source e reverse engineering

### 5.1 pyLSV2 (`drunsinn/pyLSV2`) — **il pezzo centrale del DIY**
- Python 3 puro, licenza **MIT**, ultima release **v1.5 (2 apr 2025)**.
- **Testato su TNC 640 reale** con più versioni NC (`340594 01`, `340595 08 SP1`,
  `10 SP2`, `11 SP1`, `11 SP4`) — oltre a iTNC530, TNC320, TNC620, TNC7.
- **Cosa fa**: trasferimento file da/verso il controllo + raccolta dati — stato
  esecuzione programma, valori override, posizioni assi, **memoria PLC**
  (marker/input/output/counter/timer/byte/word/dword/string), **screenshot**,
  tabella utensili, parametri macchina.
- **Cosa NON fa (di proposito)**: "tutto ciò che va oltre la semplice manipolazione
  file è **bloccato da un lockout parameter**". Gli autori avvertono esplicitamente:
  *"could damage the control or cause injuries! Use at your own risk!"* → **niente
  start/stop/MDI remoto** per design.
- Supporta il **tunnel SSH** (via `sshtunnel`) per cifrare LSV2 sui controlli
  recenti.
- **Basato su reverse engineering** (nessuna doc ufficiale libera del protocollo):
  alcune parti "might therefore be not correct" — da testare sul campo.

### 5.2 Eclipse-Plugin-Heidenhain (`tfischer73`)
- Implementazione **Java** originale di LSV2 (`LSV_Client.java`) — è la **fonte
  storica** da cui pyLSV2 ha derivato la conoscenza del protocollo. v2.0.0 (30 ott
  2019). Scope: **trasferimento file** da IDE. Mostra i login-level LSV2
  (`PW_INSPECT`, `PW_DNC`, `PW_MONITOR`, …) e i telegrammi (login, read version,
  read params, file ops). Utile come riferimento di protocollo.

### 5.3 CNCnetPDM (inventcom) — aggira l'opzione 18
- Tool commerciale che **legge (e scrive) il PLC direttamente**. Afferma di
  raccogliere dati macchina (giri mandrino `SPINDLE[0].DG_RPM`, avanzamento
  programmato, numero utensile `NN_DG_TOOL_NUMBER`) **senza opzione 18**, leggendo
  il PLC. Dimostra che il **monitoraggio base è possibile anche senza la costosa
  opzione DNC** — la stessa tecnica è replicabile con pyLSV2 sui marker/word PLC.

### 5.4 ADONTEC SuperCom — libreria commerciale LSV2
- Supporta TNC 640, seriale o TCP/IP. Espone anche funzioni di comando
  (`HN_ActivateAndRun` = attiva+lancia programma, `HN_WriteMarkers`/`HN_WriteWords`
  = scrittura PLC, `HN_GetPgmStatus`, override, posizioni assi). Dimostra che
  **LSV2 tecnicamente può anche pilotare** — ma è codice chiuso a pagamento, e il
  fatto che l'open source (pyLSV2) blocchi queste funzioni è una scelta di safety,
  non un limite del protocollo.

---

## 6. Pilotare la macchina da remoto: cosa è possibile e cosa no

| Azione | LSV2 / pyLSV2 | HEIDENHAIN DNC (opt.18) | OPC UA NC Server (opt.56-61) |
|---|---|---|---|
| Leggere stato/assi/override | ✅ (stato pieno con opt.18) | ✅ | ✅ |
| Leggere/scrivere PLC | ✅ read; write **bloccato** in pyLSV2 | ✅ | ✅ (variabili) |
| Trasferire file NC | ✅ | ✅ | ✅ (Part 20) |
| Screenshot | ✅ (statico) | ✅ | ❌ |
| **Start/Stop programma** | **❌ lockout** | ✅ | ✅ (`Start`/`Stop`/`Cancel`) † |
| **Cambiare override** | ❌ (write bloccato) | ✅ | ✅ † |
| Cambiare modo operativo | ❌ | ✅ | (via metodi/variabili) |

† **Solo con** PLC OEM che supporta lo start esterno **e** utente con diritto
`NC.RemoteProgramRun`. Senza questi due requisiti la richiesta è **rifiutata**.

**Implicazioni di safety (da non sottovalutare)**:
- La comunicazione DNC/OPC UA su rete PC **non è hard real-time**.
- Uno start remoto su macchina non presidiata ha implicazioni di **sicurezza
  macchina e responsabilità** (Direttiva Macchine): serve valutazione del rischio,
  e non a caso HEIDENHAIN mette il comando dietro un permesso utente esplicito +
  supporto PLC del costruttore.
- **Raccomandazione netta**: il DIY dovrebbe **fermarsi al monitoraggio/visualizzazione**.
  Il pilotaggio (se davvero serve) va fatto **solo** via OPC UA NC Server ufficiale,
  con i diritti/PLC in regola, e mai reimplementando comandi via LSV2 grezzo.

---

## 7. Rete, hardware, firmware, porte

- **Interfaccia**: Ethernet standard (opzione `#16`). Il TNC 640 va raggiunto per
  IP/nome DHCP sulla rete dell'officina — identico requisito del Sinumerik.
- **Porte TCP**: **VNC = 5900** (server HEROS, per schermo+comando); **LSV2 = 19000**
  (e 19001, per file/stato via TNCremo/pyLSV2). La 5900 è lo standard VNC; la 19000
  è la porta nota LSV2 (indicata anche come "porta lato macchina da aprire dietro
  firewall"). ⚠️ Verificare comunque sul campo (scan/telnet) e nella config di rete
  del controllo. I controlli recenti hanno **firewall HEROS** e **user administration**
  attivi: la 5900/19000 potrebbero essere da abilitare, o richiedere **tunnel SSH**.
- **Firmware TNC 640** (versioni `34059x-NN`): soglie che contano →
  DNC dal `-01`, Remote Desktop Manager dal `-02`, **OPC UA NC Server dal `-10`**.
  Il TNC 640 arriva fino al modello OPC UA **1.04** (da `-18`); oltre è solo TNC7.
  → **Verifica la versione NC installata** (MOD → SIK) prima di scegliere la via.
- **Stato opzioni**: si controlla a bordo macchina (modo programmazione → tasto
  `MOD` → code-number `SIK` → voce "HEIDENHAIN DNC"/"OPC UA NC Server" spuntata o no).

---

## 8. Costi e licenze (indicativi)

- **pyLSV2 / Eclipse plugin**: gratis (open source). **Costo zero sul controllo**
  per il monitoraggio base (login INSPECT/PLC).
- **TNCremo**: gratis. **TNCremoPlus**: a pagamento, ID `340447-xx` (prezzo non
  pubblicato — richiesto sui forum, rimasto senza risposta ufficiale).
- **Opzione 18 (DNC)**: opzione SIK a pagamento sul controllo (ID `526451-01`),
  installata dall'OEM; **+ RemoTools SDK** a parte (ID `340442-xx`). Prezzi non
  pubblici.
- **OPC UA NC Server**: **6 opzioni SIK** (ID `1291434-01…-06`), una per
  connessione. Prezzi non pubblici.
- **StateMonitor**: licenze multiple (base `1218930-xx`, +5 macchine, moduli
  protocollo) o noleggio ≥6 mesi (`1432346-MA`); **prezzo su richiesta**. Richiede
  comunque opzione 18.
- **RemoteAccess / Secure Remote Access**: a pagamento (ID `1339577-01…`,
  `1356741-01`).

> Nessuna fonte pubblica riporta i prezzi esatti delle opzioni SIK: HEIDENHAIN
> quota tramite l'OEM/rivenditore. Per una stima reale serve una richiesta di
> offerta al costruttore della macchina indicando modello e versione NC.

---

## 9. Rischi legali, garanzia, sicurezza

- **Sblocco "grigio" delle opzioni SIK**: sui forum circolano offerte di sblocco
  non ufficiale via screenshot della schermata SIK. **Da evitare**: viola i termini
  di licenza, fa decadere garanzia/supporto ed è un rischio legale. Le opzioni
  vanno acquistate tramite l'OEM.
- **Garanzia connessioni**: HEIDENHAIN garantisce alcune combinazioni solo in
  configurazioni specifiche (es. Remote Desktop garantito solo HEROS 5 + IPC 6641).
- **Reverse engineering (pyLSV2)**: legalmente usabile (MIT), ma gli autori
  declinano ogni responsabilità e avvertono del rischio di **danno al controllo o
  infortuni** — motivo del lockout sulle funzioni di comando.
- **Sicurezza macchina**: qualsiasi funzione di scrittura (PLC, override, start)
  va trattata come intervento sulla sicurezza della macchina. Il monitoraggio in
  sola lettura non ha questi rischi.

---

## 10. Raccomandazione architetturale per il DIY

Data la coerenza con lo stack esistente (FastAPI + React + poller, già collaudato
sul Sinumerik via OPC UA), e alla luce dell'evidenza che **la funzione era VNC già
a bordo macchina**, la strada consigliata è **incrementale**, tutta in un **branch
separato** (`feature/heidenhain-tnc640`).

### Fase 0 — Verifica sul campo (mezza giornata, costo zero) ✅ **PARTIRE DA QUI**
Prima di scrivere codice, riportare in vita la funzione VNC che l'OEM faceva pagare:
1. A bordo macchina: *Settings → VNC* → verificare servizio attivo, client
   permessi, impostare/recuperare la **password**.
2. *Settings → Firewall* → consentire la porta **5900** (o predisporre SSH).
3. Da un PC in rete officina: **VNC viewer** → `IP_controllo:5900` + password.
   Se compare lo schermo fluido comandabile col mouse → **la funzione è ripristinata
   senza comprare nulla**.
4. Se non funziona, isolare la causa (firewall / password / focus / vincolo OEM-PLC)
   con la checklist di §4.0.

### Fase 1 — Schermo live nel yellow hub via noVNC ✅ il cuore del progetto
- **noVNC** (client VNC in browser, WebSocket) + **websockify** come proxy →
  lo schermo del TNC 640 vive **dentro il frontend React**, senza installare nulla
  sui PC degli utenti. È l'equivalente esatto (gratis, in casa) del RemoteAccess.
- Backend FastAPI: un endpoint/servizio che avvia websockify verso `IP:5900`;
  React monta il canvas noVNC. Gestione **read-only vs. take-control** a livello
  applicativo (bottone "prendi il controllo") per rispettare l'arbitraggio focus.
- **Costo controllo: zero** (VNC è funzione HEROS, non opzione SIK).

### Fase 2 — Monitoraggio dati strutturati (complementare, gratis)
- **pyLSV2** (Python, MIT) come secondo *collector*, gemello del poller Sinumerik:
  posizioni assi, override, programma attivo/stato, utensile, marker PLC →
  endpoint `/api/heidenhain/tick` (stesso pattern di `/api/macchina-live/tick`).
- Serve per KPI/notifiche/storicizzazione nel yellow hub (il VNC dà l'immagine, non
  il dato). Senza opzione 18 lo stato programma via login DNC non c'è: ripiega su
  login INSPECT (assi) + lettura PLC (come CNCnetPDM). `screendump` pyLSV2 utile
  per snapshot/notifiche a fine job.

### Fase 3 — Parità "pulita" + eventuale pilotaggio via OPC UA (opzionale, a pagamento)
- Se serve integrazione dati robusta come sul Sinumerik: **OPC UA NC Server**
  (opzioni 56–61, firmware ≥ `34059x-10`) via client **`asyncua`** Python —
  identico all'integrazione Sinumerik.
- Pilotaggio programmatico (`Start`/`Stop`/`Cancel`, override) **solo** qui e solo
  con: PLC OEM che supporta lo start esterno + utente con diritto `NC.RemoteProgramRun`.
  Valutazione del rischio macchina obbligatoria. **Non** reimplementare comandi via
  LSV2 grezzo (bloccato per safety).

### Cosa evitare
- La via **RemoTools SDK/COM** (opzione 18): **Windows/COM-only**, non si sposa con
  lo stack Python/Linux se non con un microservizio-ponte C# — complessità inutile
  rispetto a VNC + pyLSV2 (+ OPC UA).
- Ricomprare la soluzione OEM per la **sola visione/comando schermo**: è VNC, già
  presente. Pagare avrebbe senso solo per accesso **cifrato via Internet**
  (allora valutare *Secure Remote Access*) o per una vera integrazione dati OPC UA.

### Perché questo batte la proposta OEM
| | Proposta OEM (nuovo dispositivo a pagamento) | DIY consigliato |
|---|---|---|
| Schermo live + comando mouse | ✅ (ma a pagamento) | ✅ VNC HEROS (già a bordo, gratis) |
| Integrato nel yellow hub | ❌ tool separato | ✅ noVNC in React + dati pyLSV2 |
| Costo | Ricorrente/dispositivo | ~0 (LAN) + tempo sviluppo |
| Dipendenza dall'OEM | Alta | Nessuna |

---

## 11. Fonti

**Documentazione ufficiale HEIDENHAIN (primaria)**
1. Options and Accessories for TNC Controls — https://www.heidenhain.us/wp-content/uploads/827222-27_TNC_Optionen_Zubehoer_en.pdf
2. HEIDENHAIN DNC (prodotto) — https://www.heidenhain.com/products/software/heidenhain-dnc
3. RemoTools SDK / VirtualTNC — https://s3.amazonaws.com/www.motionusa.com/heidenhain/RemoTools_SDK_VirtualTNC.pdf
4. OPC UA NC Server (prodotto) — https://www.heidenhain.com/products/software/opc-ua-nc-server
5. Connected Machining (portafoglio) — https://www.heidenhain.com/products/digital-shop-floor/connected-machining
6. Options and Accessories PR (08/2024) — https://www.heidenhain.us/wp-content/uploads/2024/08/PR_Options_and_Accessories_for_TNC_ID827222_en.pdf
7. OPC UA NC Server — Information Model / Program execution — https://product.heidenhain.de/JPBC/image/FILEBASE_PUBLIC/1309365_08_B_01_1.pdf
8. TNC 640 User's Manual (Remote Desktop) — https://www.manualslib.com/manual/1372445/Heidenhain-Tnc-640.html?page=118
9. StateMonitor — prerequisiti — https://www.klartext-portal.com/software/machine-data-collection/prerequisites
10. StateMonitor rental (shop) — https://www.heidenhain.shop/en/statemonitor-rental.html

**Open source / reverse engineering (primaria)**
11. pyLSV2 (drunsinn) — https://github.com/drunsinn/pyLSV2
12. pyLSV2 protocol docs — https://pylsv2.readthedocs.io/en/master/protocol.html
13. pyLSV2 issue #60 — https://github.com/drunsinn/pyLSV2/issues/60
14. Eclipse-Plugin-Heidenhain (tfischer73) — https://github.com/tfischer73/Eclipse-Plugin-Heidenhain

**Integratori / terze parti (secondaria)**
15. DNC Option 18 — inventcom/CNCnetPDM — https://www.inventcom.net/support/heidenhain/dnc-option-18
16. ADONTEC — LSV2 functions (SuperCom) — https://www.adontec.com/heidenhain-lsv2-functions.htm

**VNC / HEROS (aggiunte 2026-07-15)**
17. Manuale TNC 640 — funzione VNC (Settings → VNC), operatività mouse/tastiera, VNC Focus — https://www.manualslib.com/manual/1359214/Heidenhain-Tnc-640.html?page=117
18. TNC 640 User's Manual — Setup, Testing and Running (sezione "Configuring the connection – VNC") — https://content.heidenhain.de/doku/tnc_guide/pdf_files/TNC640/34059x-11/einrichten/1261174-22.pdf
19. HEIDENHAIN RemoteAccess (ex TeleService) — controllo/monitoraggio remoto via Internet — https://www.heidenhain.com/products/software/remote-desktop-manager
20. MachineMetrics — connettere iTNC 530 / TNC 640 (rete, porte) — https://support.machinemetrics.com/hc/en-us/articles/26357942877971-How-to-Connect-Heidenhain-iTNC-530-and-640-Controls

**Forum (affidabilità media — usati solo per contesto)**
21. IndustryArena — costo TNCremoPlus — https://en.industryarena.com/forum/costs-tncremo-plus--229975.html
22. CNCarena — tabella opzioni TNC — https://en.cncarena.com/heidenhain/forum/thread/365707-heidenhain-tnc-option-function-table/
23. CNCarena — VNC Viewer su HEIDENHAIN — https://en.cncarena.com/heidenhain/forum/thread/91993-vnc-viewer/

---

*Report generato il 2026-07-15 da ricerca web multi-fonte. La cross-verifica
automatica a 3 voti è stata interrotta dal limite di sessione; le affermazioni
marcate ✓✓✓ hanno superato la verifica, le altre sono ancorate a citazioni dirette
delle fonti primarie sopra elencate. Verificare sul campo: versione NC firmware
installata, stato opzioni SIK (MOD→SIK), porte TCP effettive e requisito SSH.*
