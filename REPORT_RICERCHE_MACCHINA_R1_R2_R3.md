# Report ricerche macchina — R1 / R2 / R3

Analisi + ragionamento sui tre lavori in coda in [ROADMAP.md](ROADMAP.md) §
"Backlog ricerche funzionali future". **Fatto a macchina SPENTA** (il log su
`P:`/`Z:` è fermo dal 18/07): tutto ciò che richiede la macchina viva per essere
confermato è marcato **🟡 IPOTESI**; tutto ciò che è estratto dal codice è ✅.
Codici/path riportati fedeli, senza normalizzazione.

Data: 2026-07-19. Fonte: tre analisi parallele del repo + ricerca di dominio.

---

## Correzione a CLAUDE.md (emersa dall'analisi)

La tabella "Stack" dice: *«Bridge OPC UA: server C# esterno (`machine_server_csharp/`)
che legge il Sinumerik via OPC UA»*. **È inesatto e ha depistato finora.** In realtà:

- `machine_server_csharp/` (`SocketServer.cs`) è un **server TCP di trasferimento
  file NC sulla porta 9999** — NON tocca OPC UA (è materia di R1).
- Il vero attore OPC UA è **`opcUa_Server_xp.exe`** (alias "OpcUaLegacy", launcher
  `runopcua`) sul PCU 50, che scrive `OpcUaLegacy.log`.
- La **copia del log sulla share** la fa **`machine_server_c/server.c`** (in **C**,
  non C#), che è anche il server :9999 realmente deployato (vedi R1).

→ Correggere la voce in CLAUDE.md quando si tocca quell'area.

---

## Filo conduttore (leggere prima dei dettagli)

Tre scoperte cambiano l'inquadramento di tutto:

1. **Non si parte da zero: gran parte è già scritta.** R1 ha la catena DNC completa
   (client + 3 server + VBS + header NCK corretto); R2 ha i programmi NC che generano
   TOA/TMA (`nc_programs/`) **e** un thread C che li copia già sulla share; R3 ha
   client `asyncua` funzionanti + `client_cert.der`/`client_key.pem` già generati e la
   mappa dei nodi noti. Il collo di bottiglia è **verifica e cablaggio**, non creazione.

2. **R3 è la chiave di volta.** L'interrogazione OPC UA diretta abilita R2 in versione
   pulita (leggere i dati utensile live invece di far girare programmi NC) e alimenta il
   veto "allarme NCK" della regola d'oro pallet. Ed è **la più prototipabile offline**
   (gli script `asyncua` esistono, manca solo la macchina per puntarli).

3. **R1 ha un bug diagnosticabile e correggibile OGGI**: la risposta `stato:ok` è
   **scollegata dall'arrivo reale** nella NCU. Finché "OK" non significa "importato",
   nessuno potrà mai debuggare il canale sulla macchina. Questo si fixa offline.

**Sequenza consigliata**: R3 (prototipo offline + checklist macchina) → R1 (fix
"OK onesto" offline, poi test DNC a macchina accesa) → R2 (versione OPC UA una volta
che R3 conferma i nodi tool; fallback = i programmi NC già pronti).

---

# R1 — Invio file diretto PC → macchina (porta 9999)

## Meccanismo attuale (✅ dal codice)

Catena intesa:
```
InvioMacchina.jsx  →  POST /api/macchina-invio/{invia|invia-batch}  (backend :8000)
  →  MachineClient (machine_client.py)  →  TCP 10.95.20.29:9999
     →  server sul PCU 50  →  header NCK  %_N_<NOME>_MPF ;$PATH=/_N_WKS_DIR/_N_<PROG>_WPD
        →  scrive D:\tmp\autoimport\<NOME>.MPF  →  cscript transfer_dnc.vbs
           →  DncOCX.CopyDNC / TransferAutom  →  DncSrv (DNC Siemens)  →  NCU passive memory
```
File chiave: `frontend/src/pages/InvioMacchina.jsx`, `api/routers/macchina_invio.py`
(prefix `/api/macchina-invio`, default `10.95.20.29:9999`), `machine_client.py`
(header JSON `\n` + bytes), `transfer_dnc.vbs` (`DncOCX.CopyDNC`), config
`server_config.ini` (`port=9999, base_path=F:\dh\wks.dir, dnc_path=D:\tmp\autoimport,
vbs_path=F:\ADD_ON\DNC\transfer_dnc.vbs`).

## Trappola: TRE server, non uno

- **Python storico** (non nel repo, visibile solo in `machine_client_debug.log`):
  scriveva diretto in `F:\dh\wks.dir\<PROG>.WPD`, pretendeva la WPD già esistente
  (`Cartella WPD non esiste. Crearla dall HMI.`).
- **C `MchnSrv`** (`machine_server_c/server.c`): **quello deployato** (`Regie.ini`
  Startup24). Gestisce CHECK/INVIA/INVIA_BATCH, legge sia `cmd` che `comando`, chiama
  il VBS **passando il file**, monitora sparizione `.MPF` / comparsa `.ERR`.
- **C# `MachineServer`** (`machine_server_csharp/SocketServer.cs`): ramo più arretrato.
  Solo CHECK/INVIA (no batch), legge solo `comando`, chiama il VBS **senza file**,
  CHECK guarda `F:\dh\wks.dir\<progetto>` **senza `.WPD`**. Se è questo a girare, il
  pulsante Batch e la CHECK sono rotti.

Il git log mostra l'evoluzione recente tutta sul **C**; README + `bin\` puntano al C#.
**Quale gira davvero sul PCU va confermato 🟡** (Regie.ini dice C).

## Ipotesi di fallimento — RANKED

1. **H1 ⭐ "OK" disaccoppiato dall'arrivo reale (falso positivo sistemico).** Il C#
   risponde `ok` **sempre**, esito VBS solo loggato (`SocketServer.cs:222-230`); il C su
   timeout risponde `ok` come "in coda autoimport" (`server.c:370-373`). Gli `stato:ok`
   nel log provano solo che il file è stato **scritto/accodato**, non importato. È la
   spiegazione diretta di "dice OK ma in macchina non arriva niente". **Correggibile offline.**
2. **H2 ⭐ Dipendenza `DncOCX.CopyDNC` / DncSrv assente o non configurata 🟡.** Tutto
   poggia su `CreateObject("DncOCX.CopyDNC")`, l'ActiveX del pacchetto Siemens **MCIS/RCS
   DNC** (add-on licenziato, da installare+registrare sul PCU) + la cartella autoimport
   di DncSrv = `D:\tmp\autoimport`. Non verificabile a macchina spenta.
3. **H3 Ambiguità su quale server gira → protocollo incoerente col frontend** (batch,
   CopyDNC-del-file, path CHECK).
4. **H4 File scritti diretti nella `.WPD` non compaiono in HMI (indicizzazione dh).**
   HMI-Advanced tiene un indice (`_dhinf.000`): un file copiato "da fuori" esiste su disco
   ma è invisibile nel program manager finché non si rigenera l'indice / si esce-rientra.
   Prova nel repo: `machine_server_c/fix_dhinf.c` è nato apposta per questo.
5. **H5 La WPD di destinazione deve pre-esistere / path NCK errato** (nome ≤25 char,
   path ≤112). 6. **H6 Errori inghiottiti ovunque** (`On Error Resume Next` nel VBS; commit
   `7720efb` "rimuovi >NUL per vedere output VBS" = il canale d'errore era cieco).

## Dominio (con fonti)

Header "punch tape" NCK corretto nel codice: `%_N_<NOME>_MPF` + `;$PATH=/_N_WKS_DIR/
_N_<PROG>_WPD`, terminatore `%`, righe CR+LF. Vie reali per far entrare un programma in
una 840D PL / PCU 50 HMI-Advanced: **DNC via DncSrv+DncOCX** (la via scelta; richiede il
pacchetto OEM installato/registrato/configurato), **servizi Data-In/Out dell'HMI** (l'HMI
deve aggiornare l'indice dh), **EXTCALL da drive di rete** (piano B, Siemens lo sconsiglia,
path ≤112), **WinPCIN/V.24** (RS232 emulata). Fonti: shopfloormanager 840D PDF; Siemens
forum "File don't appear in DH folder"; manualslib 840D EXTCALL / Execute from network drive;
aggsoft Siemens 840D DNC.

**Conclusione**: il codice è concettualmente giusto, ma dipende da un componente OEM
Siemens (DncSrv/DncOCX) che deve essere installato/licenziato/registrato e con autoimport
configurato sul PCU — mai confermato.

## Cosa possiamo fare OFFLINE
- **Fix "OK onesto"**: far dipendere la risposta dall'esito reale (sparizione `.MPF` /
  assenza `.ERR` / exit VBS), non "accoda-e-dichiara-ok". Priorità sul C#.
- **Consolidare su UN server** (raccomandato il **C**: ha batch + CopyDNC-del-file).
- **Rendere visibili gli errori VBS** all'operatore (già iniziato in `7720efb`).

## Checklist a macchina accesa 🟡
1. Quale exe gira: `MchnSrv.exe` (C) vs `MachineServer.exe` (C#). 2. `Test-NetConnection
10.95.20.29 -Port 9999`. 3. In un `.vbs` minimale `CreateObject("DncOCX.CopyDNC")` → non
deve dare errore (se errore = root cause). Verificare autoimport DncSrv = `D:\tmp\autoimport`.
4. `cscript //Nologo transfer_dnc.vbs "D:\tmp\autoimport\TEST.MPF"` → leggere
`transfer_dnc_log.txt`, verificare in NCU. 5. INVIA singolo su progetto `TEST` (WPD già
creata da HMI): osservare se il `.MPF` **sparisce** (importato) o compare `.ERR`. 6. Se
resta su disco e non compare in HMI: `FixDhinf.exe` + esci/rientra cartella.

## Sicurezza
:9999 accetta file NC su TCP **senza auth**, framing raw, li inietta nella NCU = vettore
comando macchina più diretto (vuln V2 del report sicurezza). Prima di renderlo operativo:
firewall che limiti 9999 al solo IP backend, poi chiave/HMAC sul socket o bind 127.0.0.1.

---

# R2 — Generazione autonoma TOA/TMA + copia su share

## Stato attuale (✅ dal codice)

Il backend **non parla mai con la macchina** per gli utensili: legge file dalla share.
- **Parser**: `api/toa_parser.py` → `sync_from_share()` auto-rileva il formato più recente
  e produce `MachineTool`/`MagazinePosition`. Due formati: **A** = `TOOL_SYNC.TOA` +
  `TOOL_SYNC.TMA` (output "HMI → Servizi → Salva Attrezzaggio"); **B** =
  `TOOL_SYN1/2/3_TOA.MPF` (output programma NC). Lettura **latin-1**. Variabili: `$TC_TP1`
  (duplo), `$TC_TP2` (nome), `$TC_DP3` (lung. Z), `$TC_DP6` (raggio), `$TC_MOP2` (vita
  residua), `$TC_MOP11` (vita totale), `$TC_TP8` (stato), `$TC_MPP6[mag,pos]` (T in posizione).
- **Writer** di `tools_machine.json`: `api/routers/tools.py` `_save_tools_db()`, chiamato
  **solo** da `POST /api/tools/sync` (e dal bottone desktop `ui/tab_macchina.py:597`).
  **Nessun loop automatico** → il refresh è **manuale**.
- **Consumatori** (sola lettura): allerta vita utensile nel poller, analisi setup, previsione
  fine vita, tool_history/vita_stimata, backup.

## Processo manuale odierno (ricostruito 🟡)
1. **Genera** i file sulla macchina: operatore da HMI → *Servizi → Salva Attrezzaggio*
   (→ `TOOL_SYNC.TOA` + `.TMA` in `F:\dh\wks.dir\_TOOLSYNC.WPD\`). 2. **Copia** sulla share
   (a mano). 3. **Importa** in DMG Desk: bottone "Sync Macchina" (`POST /api/tools/sync`).
   Tutti e tre i passi oggi manuali.

## Già pronto nel repo (spesso ignorato)
- **Programmi NC che generano TOA/TMA**: `nc_programs/TOOL_SYNC.MPF` chiama
  `SAVE_TOA_*.SPF` + `SAVE_TMA.SPF` (leggono le `$TC_*` live con `WRITE()`, poi `COPYFILE()`
  sulla share). Tre varianti per l'**allarme 17020** (indici array variabili su PowerLine):
  V2 con `T="nome" M6` (~60-90s, fa **cambi utensile reali**); **LOOP/V3** con `FOR` senza M6
  (~10-15s, **richiede** che `TEST_VAR_INDEX.MPF` passi senza 17020). Confermati in repo:
  `SAVE_TOA_LOOP.SPF`, `SAVE_TOA_V3.SPF`, `SAVE_TMA.SPF`, `TEST_VAR_INDEX.MPF`, `TOOL_SYNC.MPF`.
- **Copia su share GIÀ automatizzata**: `machine_server_c/server.c` `export_thread`
  (~riga 708-786) sorveglia `_TOOLSYNC.WPD\TOOL_SYNC.TOA`/`.TMA` e li copia sulla share su
  mtime-change. Quindi qualunque *generazione* che scriva nella WPD viene già propagata —
  **basta confermare che quel bridge giri**.

## Formato TOA/TMA (dominio + codice)
Archivi **INI di testo** con le system-variable area TO. TOA: header `METRIC`, blocchi
`$TC_TP*`/`$TC_DP*`/`$TC_MOP*` per T-number. TMA: `$TC_MAP1..10[mag]` (tipo/nome es.
`"Regal_120"`), `$TC_MPP6[mag,pos]=T-number`, buffer 9998, punto carico 9999. Fonti: Siemens
FBWsl Tool Management; 840D Description of Functions; Access MyMachine/OPC UA config manual;
Softing uaGate 840D; Data Backup HMI Advanced. **Nessun `.TOA`/`.TMA` campione nel repo**
(solo gli SPF che li generano) → formato inferito da SPF + doc.

## Vie di automazione
- **(a) Job schedulato sul PCU che pilota l'export HMI** — invasività **alta**, fragile
  (l'export HMI-Advanced non è pensato headless). Scartare.
- **(b) Programmi NC già pronti + COPYFILE** — invasività **media**. Con la variante **LOOP**
  (se `TEST_VAR_INDEX.MPF` passa) genera+copia in ~15-20s a fine pallet, senza cambi utensile
  e senza toccare il PCU. Fallback = V2 con M6. **Via più veloce da mettere in campo.**
- **(c) Leggere via OPC UA e scrivere noi i file (o direttamente `tools_machine.json`)** —
  invasività **bassa**, la più pulita, si lega a R3. Oggi 🔴 **non implementato** (né il C né
  il C# leggono nodi tool). Percorribile **solo dopo** che R3 conferma che `opcUa_Server_xp`
  espone l'area TO/magazzino sui NodeId. Dominio: fattibile su gateway/AMM, ma **incognita**
  su questo PowerLine legacy.

**Raccomandazione**: breve termine **(b) LOOP** (previo test 17020) + confermare l'export_thread
del bridge C. Medio termine **(c) OPC UA** dopo R3. Inoltre, indipendente dalla macchina:
aggiungere un **loop di auto-sync** che chiama `sync_from_share` su mtime-change del TOA (come
già si fa per `OpcUaLegacy.log`) → chiude l'anello lato backend. **Fattibile offline.**

## Checklist a macchina accesa 🟡
1. Confermare col reparto il processo manuale reale. 2. `TEST_VAR_INDEX.MPF` → fin dove arriva
senza 17020 (decide LOOP vs M6). 3. `MchnSrv` gira e l'export_thread copia già TOA/TMA?
(heartbeat `xp_heartbeat.txt`). 4. Path COPYFILE/share funzionante e WPD `_TOOLSYNC.WPD`
esistente (creata da HMI). 5. Per (c): con UaExpert verificare nodi area TO/magazzino.

---

# R3 — Interrogazione OPC UA diretta (query on-demand)

## Pipeline attuale (✅ dal codice)
1. **`opcUa_Server_xp.exe` / `runopcua`** sul PCU 50: server OPC UA su `opc.tcp://<PCU>:4840`,
   scrive `F:\oem\opcualegacy\OpcUaLegacy.log` (una riga per lettura: `ReadPlVar: VarName=…;
   read Value=…`). Avviato da `Regie.ini` Startup47. `MchnSrv` aspetta **120s** all'avvio per
   non disturbarlo → processo separato e "delicato".
2. **`machine_server_c/server.c` `export_thread`**: **copia** il log sulla share ogni **60s**
   (`DEFAULT_OPCUA_LOG F:\oem\opcualegacy\OpcUaLegacy.log` → `Z:\DMG_DMC_160U\`). Non
   interroga OPC UA. Latenza totale vista dal backend: ~4s (read interno) + fino a 60s (copia)
   = **fino a ~64s di ritardo** → argomento forte per il diretto.
3. **Backend `api/routers/macchina_live.py`**: legge il `.log` copiato e fa **parsing testuale**
   (`RE_LINE`, `VAR_MAP`), mai OPC UA.
4. **Client OPC UA già nel repo** (`lettura tab utensili/`): `test_opcua.py` (lib `opcua` sync,
   endpoint `192.168.214.241:4840`, user/pass `admin/admin123`, `NODES` da `NodeTreeConfig.ini`),
   `discover_opcua.py` (`asyncua`, `10.95.20.29:4840`, enumera endpoint/policy), `brute_opcua.py`
   (brute credenziali → **le reali non sono note**), `test_cert_opcua.py`, **`client_cert.der` +
   `client_key.pem` già presenti** (→ il server vuole probabilmente Sign/SignAndEncrypt).

## Nodi noti → aree OPC UA (✅ path dal codice, 🟡 NodeId completo da browsare)
| Campo backend | Path variabile (log) | Area |
|---|---|---|
| `stato_programma` | `/Channel/State/progStatus` | 0 reset·1/3 exec·2 search·5 stop |
| `programma_attivo` | `/Channel/ProgramInfo/workPandProgName[u1]` | path MPF attivo |
| `numero_utensile` | `/Channel/State/actTNumber` | T attivo |
| `utensile_attivo` | `/Channel/State/actToolIdent` | ident utensile |
| `allarme` | `/Hmi/OpcUaAlarm1` (+ `/Hmi/OpcUaAlarmNumbers`) | testo/nr allarmi |
| modo operativo | `/BAG/State/opmode` | AUTO/JOG/MDA (noto, non usato) |
| `pallet_attivo` | `/PLC/DB0.DBB67` | byte PLC pallet |
| feed/rpm/override | `actFeedRate`/`actSpindleSpeed`/`feedRateOvr`/`spindleOvr` | **oggi parsati e SCARTATI** |

I NodeId (ns + identifier) non sono nel codice: i test usano browse-by-path da `Objects` →
**vanno letti live**.

## Dominio (con fonti)
La 840D qui è **PowerLine, non SolutionLine** → l'opzione nativa Siemens "Access MyMachine /
OPC UA" (richiede SINUMERIK Operate) **non si applica**. Quindi `opcUa_Server_xp.exe` è un
**server OPC UA di terze parti/OEM** sul PCU 50 che fa da wrapper sul livello OPI/BTSS (le
stesse `ReadPlVar`), con mappa nodi in `NodeTreeConfig.ini`. Connessione tipo `asyncua`:
```python
from asyncua import Client
client = Client("opc.tcp://10.95.20.29:4840")
client.set_user("admin"); client.set_password("…")            # 🟡 credenziali
# await client.set_security_string("Basic256Sha256,SignAndEncrypt,client_cert.der,client_key.pem")
async with client:
    vals = await client.read_values([client.get_node(nid) for nid in nodeids])  # 1 round-trip
```
Porta 4840 confermata dal codice. `ns` e forma identifier da leggere live. Sicurezza/policy da
confermare con `discover_opcua.py`. Fonti: Siemens AMM/OPC UA config manual; forum Siemens
"840D powerline with OPC-UA" (215064) e "OPC UA server setup PCU50" (116791); Softing uaGate
840D; MachineMetrics 840D OPC UA.

## Architetture
- **(A) Client OPC UA dentro il server sul PCU (C/XP)** — un solo consumer, localhost, ma
  scrivere un client OPC UA in C su XP/.NET 2.0 è costoso e fragile. **Sconsigliata.**
- **(B) Client `asyncua` diretto dal backend** — già in repo, si integra con i poller asyncio,
  read in blocco/subscription, sblocca subito allarmi/TOA/feed/rpm/blocco. Apre una seconda
  sessione sul server OEM (da tenere singola) e va autenticata/rate-limited.
- **(C) IBRIDO — RACCOMANDATA** — mantieni il tail-log a 5s come baseline e **fallback**; aggiungi
  **un client `asyncua` unico e persistente** nel backend per (a) un "interroga adesso"
  on-demand e (b) polling mirato a bassa frequenza dei segnali che il log non dà freschi
  (allarmi, tool, feed/rpm, blocco). Guardie: **una sola sessione condivisa**, read in blocco,
  rate-limit+coalescing, timeout brevi, backoff che ricade sul log.

## Cosa si sblocca
- **Allarmi NCK live** → veto "allarme" della regola d'oro pallet (Fase 3 evidenze multiple),
  senza il ritardo ~64s. - **TOA/utensili live** → alimenta R2 e la previsione fine vita con
  dati reali. - **Feed/RPM/override reali** (oggi scartati) → rallentamenti, OEE, veto durata.
  - **Posizione/blocco corrente** → avanzamento ed ETA precisi. - **Modo operativo** → distingue
  fermo produttivo da setup/JOG. - **Subscription** (se supportate) → push, elimina la copia-log.

## Cosa possiamo fare OFFLINE
- **Modulo client `asyncua`** nel backend (sessione unica persistente, read in blocco, fallback
  al log) — scrivibile e testabile su mock; si attiva quando la macchina è accesa.
- **Rifinire `discover/browse`** in `lettura tab utensili/` pronti a girare al primo accesso
  per estrarre NodeId reali, policy, credenziali.

## Rischi + checklist a macchina accesa 🟡
Rischi: carico sul pipe OPI/BTSS (mono-coda, lento → può rallentare l'HMI dell'operatore);
limiti di sessione del server OEM (tenere 1 sola sessione); XP non patchabile + rete piatta
(nuovo canale :4840 va autenticato e dietro firewall); policy/certificato ignoti.
Checklist: 1. `discover_opcua.py` → EndpointUrl/SecurityPolicy/Mode/UserIdentityTokens.
2. Credenziali reali o Anonymous. 3. Browse da `Objects` → NodeId reali. 4. `NodeTreeConfig.ini`:
quali nodi esistono, aggiungere i mancanti (feed/rpm/override, nr blocco, tool life). 5. Quale IP
raggiungibile (`10.95.20.29` LAN vs `192.168.214.241` sistema) + firewall 4840. 6. In ciclo:
misurare latenza read e reattività HMI; provare subscription.

---

## Sintesi operativa (cosa fare, in ordine)

| # | Lavoro | Quando | Bloccato da |
|---|--------|--------|-------------|
| 1 | R3 — modulo client `asyncua` nel backend (sessione unica + fallback log) | **offline ora** | — |
| 2 | R3 — rifinire `discover/browse` pronti al primo accesso | **offline ora** | — |
| 3 | R1 — fix "OK onesto" + consolidare su un server + errori VBS visibili | **offline ora** | — |
| 4 | R2 — loop auto-sync `sync_from_share` su mtime TOA | **offline ora** | — |
| 5 | R3 — discover/browse reali → NodeId, policy, credenziali | macchina accesa 🟡 | macchina |
| 6 | R1 — test catena DNC (DncOCX, autoimport, INVIA) | macchina accesa 🟡 | macchina |
| 7 | R2 — `TEST_VAR_INDEX` → scelta LOOP/M6; conferma export_thread | macchina accesa 🟡 | macchina |
| 8 | R2 via OPC UA (lettura tool live) | dopo #5 | R3 |
