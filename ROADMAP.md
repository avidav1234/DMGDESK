# ROADMAP — Tool Manager V14

Piano dei lavori in corso e backlog. Aggiornare quando si chiude o si apre un'iniziativa.
**Data ultimo aggiornamento**: 2026-07-10 — Nuova iniziativa "Classificazione
percorsi NC + MAIN builder": spike SDK Cimatron ✅ (accesso standalone alla
griglia parametri completa di tutte le procedure — offset/tolleranze/MW — via
`IPdm.GetModel → INcModel → GetProcessManagerAsXML2`, no add-in; +
`SavePicture2` anteprima pezzo). Aggiornamento precedente (2026-07-08) — Check critico Task 1-3
(dettagli e soluzioni proposte in [REPORT_CHECK_CRITICO_2026-07-08.md](REPORT_CHECK_CRITICO_2026-07-08.md)):
**root cause del bug #1 trovata e provata sui dati** (blocco "sessione
orfana" → Fase 0 predittore chiusa, Fase 1 pronta), nuovi item #9-#16 nel
backlog (ognuno con fix proposto), migliorie Task 2 e dati sottoutilizzati
Task 3 nella sezione idee, checkpoint vita-utensili "uscita dal proxy"
verificato e maturo. Aggiornamento precedente (2026-07-02): Hardening post-audit: Fasi 1, 3, 4, 5, 6, 7, 8 ✅. **Fase 2**: verificato che i 3 token esposti in history sono **tutti già morti** (401) e il token attivo non è mai stato committato → nessuna revoca urgente, resta solo lo scrub opzionale della history. Fase 8: item 2/3/4 fatti + verificati; API key (item 1) preparata su tutti i client ma **OFF** → attivazione on-demand in [scripts/ATTIVAZIONE_API_KEY.md](scripts/ATTIVAZIONE_API_KEY.md)

---

## 🚨 Iniziativa attiva: Hardening post-audit (PRIORITÀ MASSIMA)

**Motivazione**: audit critico completo dell'app (2026-07-02, quattro review
parallele su logica core, sicurezza API, frontend, dati/operatività — ~39k
righe coperte, finding critici verificati uno a uno sul codice) ha trovato
tre falle operative gravi, tutte confermate:

1. **Backup fantasma**: `_collect_files` in [backup.py:67-93](api/routers/backup.py#L67-L93)
   legge chiavi config che in `config.json` **non esistono** (`projects_path`,
   `log_path`, `cam_tracker_data_path`, `turno_snapshot_path`) → il backup
   giornaliero salva SOLO `config.json` (175 byte). Verificato sui MANIFEST
   del 2026-07-01 e 2026-04-22: da mesi non esiste alcuna copia di
   worktrack_projects / pallet_state / lavorazioni_log / tools_machine.
   Con retention 30 gg le copie buone precedenti sono già state cancellate.
   Nessuna funzione di restore esiste. `/api/backup/stato` riporta "OK".
2. **Segreti nella history git** (repo remoto GitHub): token bot Telegram
   committato in `.env` (commit `3d740d9`, toccato ancora in `fd81971`) e
   token GitHub `ghp_...` (commit `3d740d9`) — entrambi recuperabili con
   `git show`. La cancellazione del file NON basta: vanno ruotati.
3. **Glitch I/O = perdita stato persistita**: `_load` pallet/progetti su
   errore I/O (non parsing) cade in `except Exception: pass` e ritorna la
   struttura di default ([pallet.py:111-113](api/routers/pallet.py#L111-L113),
   [progetti.py:80-82](api/routers/progetti.py#L80-L82)); se nel medesimo
   tick qualcosa marca dirty, il default (6 pallet vuoti / zero progetti)
   viene **salvato sopra i dati reali**. Combinato con (1): irrecuperabile.

### Fasi e stato

| Fase | Stato | Inizio | Fine | Lavoro | Note |
|---|---|---|---|---|---|
| 1 — Backup reale | ✅ Done | 2026-07-02 | 2026-07-02 | 0.5 gg | Fix `_collect_files` (helper canonici dei moduli proprietari), archivi `lavorazioni_YYYY.json`, allarme log ERROR + Telegram su set incompleto, 14 file salvati (era 1), `scripts/restore_backup.py` testato. Vedi "Lavori completati" |
| 2 — Rotazione segreti | 🟢 Risolta di fatto (scrub opzionale) | 2026-07-02 | 2026-07-02 | 0.5 gg | **VERIFICATO 2026-07-02 (check validità API ufficiali)**: i 3 token esposti nella history sono **tutti già MORTI** (HTTP 401 da Telegram getMe e GitHub /user): Telegram@`fd81971`, GitHub@`3d740d9`, GitHub@`SETUP_GIT_GITHUB.md`. Il token Telegram **attivo** è un altro, presente **solo nel `.env` su disco, mai committato** (hash diverso da quello in history). Quindi **niente segreto vivo è esposto** → nessuna revoca urgente. Parte codice ✅ (sanificazione `SETUP_GIT_GITHUB.md`, httpx silenziato). **Resta solo, opzionale**: commit sanificazioni + scrub history (igiene, non sicurezza). Procedura in [scripts/ROTAZIONE_SEGRETI.md](scripts/ROTAZIONE_SEGRETI.md) |
| 3 — Poller fail-safe su I/O | ✅ Done | 2026-07-02 | 2026-07-02 | 1 gg | Loader fail-safe (`ShareNonRaggiungibileError` + quarantena corrotti), guardie anti-wipe sui save, tick early-return su log/stato illeggibili. 26/26 check simulazione + 128/128 regressione. Vedi "Lavori completati" |
| 4 — Fix rapidi verificati | ✅ Done | 2026-07-02 | 2026-07-02 | 0.5 gg | Tutti e 5 i fix applicati e verificati (import json, catena .then coda, stato backend-giù in UI, Wrap a modulo, log poller WARNING) + bonus: tick saltati riflessi in `GET /tick`. Vedi "Lavori completati" |
| 5 — CI onesta + igiene repo | ✅ Done | 2026-07-02 | 2026-07-02 | 1 gg | CI onesta (aggregato pytest reale + gate standalone + build frontend + coverage api/), release zip corretta, de-track 7407→220 file tracciati. Vedi "Lavori completati". **Restano azioni utente**: commit del de-track + valutare de-track dei 4 .exe/.spec |
| 6 — Lock read-modify-write | ✅ Done | 2026-07-02 | 2026-07-02 | 1 gg | Poller + 3 funzioni main_sync: load+modifica+save dentro UN lock. Test concorrenza prova no-lost-update (ordine eventi) + no-deadlock. Vedi "Lavori completati" |
| 7 — Autostart / supervisione | ✅ Done | 2026-07-02 | 2026-07-02 | 0.5 gg | `scripts/run_service.py` (launcher) + `scripts/installa_autostart.py` + `cam_tracker/installa_avvio_automatico.py` (3 task: backend, step, cam). **Watchdog `TimeTrigger` 1 min + IgnoreNew** (non `RestartOnFailure`, inaffidabile su kill esterni). Installer eseguiti da admin; **restart-on-kill provato sul campo: backend ucciso → ripartito da solo in ~15 s, HTTP 200**. Vedi "Lavori completati" |
| 8 — Hardening sicurezza | ✅ Done | 2026-07-02 | 2026-07-02 | 1 gg | **Item 2** (path traversal): `_nome_file_sicuro` su `/invia` E `/invia-batch` (era in entrambi) — basename + whitelist `{.mpf,.nc,.spf}` + audit IP, 19/19 test. **Item 3** validazione IP/host+porta (rifiuta typo-IPv4), 22/22. **Item 4** self-call `export_rendiconto` autenticata (backlog #7). **Item 1** API key: middleware già presente, tutti i client cablati (frontend interceptor già esistente + cam_tracker + self-call) ma **chiave OFF** per scelta utente (opzione "prepara, OFF") → zero rotture ora, attivazione = 1 var documentata in [ATTIVAZIONE_API_KEY.md](scripts/ATTIVAZIONE_API_KEY.md). Matrice 401/200 verificata 11/11. Vedi "Lavori completati" |

### Exit criteria

- **Fase 1**: il MANIFEST giornaliero contiene tutti i file di stato attesi;
  un restore di prova su cartella temporanea produce JSON validi e completi;
  allarme Telegram se il set è incompleto.
- **Fase 2**: ✅ vecchi token verificati NON più funzionanti (401 su API
  ufficiali, 2026-07-02); bot operativo col token nuovo (non esposto in git).
  Resta opzionale: history riscritta e force-push concordato (solo igiene).
- **Fase 3**: test simulato "share irraggiungibile 2h durante lavorazione" →
  zero modifiche persistite su pallet/progetti, zero falsi `guasto`,
  zero fermi fittizi nel report.
- **Fase 4**: allerta utensili live funzionante; coda risincronizzata al
  completamento; staccando il backend la barra stato lo dice entro 15 s.
- **Fase 5**: rompendo volutamente un assert in locale la CI diventa rossa;
  `git pull` di produzione pulito senza conflitti su file di stato.
- **Fase 6**: nessun programma "sparito" da worktrack_projects per ≥2
  settimane di produzione.
- **Fase 7**: riavvio del PC officina → backend + step_analyzer attivi entro
  2 min senza intervento umano.
- **Fase 8**: richiesta senza API key → 401; upload con filename `..\..\x`
  rifiutato; file non-MPF rifiutato.

### Fuori scope (rimandato a dopo l'hardening)

- Refactor `Progetti.jsx` (4451 righe, 115 useState, 29 componenti nello
  stesso file) + layer dati condiviso frontend (oggi ~12 richieste/10s con
  Home aperta, utility duplicate 4×) → iniziativa separata quando le fasi
  1-8 sono chiuse.
- Separazione `lavorazioni_log.json` hot/storico: oggi `_save_log` riscrive
  5.2 MB su SMB ogni ~5s (≈90 GB/giorno) con I/O sincrono nell'event loop.
- Versioning lato server per `PUT /progetti/batch/save` (oggi last-write-wins
  fra postazioni: ufficio e officina possono sovrascriversi a vicenda).

---

## 🧭 Iniziativa attiva: Classificazione percorsi NC + MAIN builder

**Motivazione** (2026-07-10): scarto strutturale fra sequenza ideale CAM e
sequenza reale d'officina. Dolore principale (dichiarato dall'utente): a ogni
generazione MAIN l'operatore riprocessa mentalmente cosa fa ogni programma.
Modello concettuale concordato: ogni programma ha **macro-operazione**
(SGR/PREF/FIN/RIP/FORATURA/MISURA), **zona** (piani, figura, colate, battute,
chiusure...), **classe di precisione** (CONTROLLATA ⇄ LIBERA — determinata da
tolleranze/offset veri) e **presidiabilità** (può girare non presidiata vs
richiede presenza). Precedenze: SGR→PREF→FIN *dentro* la stessa zona; fra zone
libertà guidata dalla realtà (continuità macchina, disponibilità operatore).

**Fonti dati** — decisione chiave post-spike: i report Excel Setup NON bastano
(appiattiscono offset raggio/piano, perdono offset su curve e tolleranze
ModuleWorks — obiezioni utente verificate sul campo). La fonte parametrica di
verità è l'**SDK Cimatron via COM standalone**, spike completato 2026-07-10 su
CAM35: `IPdm.GetModel(path) → QI INcModel → GetProcessManagerAsXML2` = griglia
completa dei parametri di tutte le procedure (offset ID 55, tolleranza ID 57,
offset contorno ID 20, tolleranze MW ID 57/218/20620, utensile completo,
strategia+commento puliti, ID procedura univoci). In più
`ICimDocument.SavePicture2` = PNG del pezzo aperto (anteprima per DMG Desk).
Ricetta tecnica completa nella memoria di progetto (cimatron-sdk-ncmodel).
Tempi NON presenti nei dump (restano da MPF `TEMPO:` + report Excel).

### Fasi e stato

| Fase | Stato | Inizio | Fine | Lavoro | Note |
|---|---|---|---|---|---|
| 0 — Spike SDK Cimatron | ✅ Done | 2026-07-10 | 2026-07-10 | 1 gg | Via standalone verificata live su documento reale (105 procedure, no add-in). Le 3 obiezioni utente (offset split, offset curve, tolleranze MW) tutte coperte dall'XML2 |
| 1 — Estrattore production-ready su CAM35 (v1.3) | ✅ Done | 2026-07-10 | 2026-07-13 | 1.5 gg | **IN PRODUZIONE** (branch `feature/estrattore-cam`, non committato): `cimatron_extract.py` (parser puro testabile offline + COM + invio con coda recupero `.sent`), router additivo `cam_params.py` (upload/storico/letture/anteprima, 7/7 test incl. fix retry-fuori-ordine trovato in e2e), trigger nel cam_tracker (cambio doc + ri-estrazione 30min, subprocess isolato). Catena e2e verificata in produzione: kill tracker → watchdog → estrazione 42 proc in 14,7s → upload → servito da :8000. Regressione pallet 128/128. **v1.3 (2026-07-13)**: estrae TUTTI i doc NC aperti della stessa istanza (GetOpenDocuments→path, throttle 20min sui non-attivi); lettura parametri ModuleWorks difensiva (GetModuleworksParameters, auto-validante al primo doc MW aperto — l'offset MW NON sta nell'XML2); gestione broker orfano (istanza attiva chiusa → None finché l'operatore non clicca in una finestra Cimatron); timeout tracker 360s. Limite documentato: istanze SEPARATE irraggiungibili — tenere i pezzi come schede della stessa istanza |
| 2 — Matching procedure ↔ programmi MPF | 🟡 Codice done, resta validazione manuale | 2026-07-11 | — | 1 gg | [logic/cam_matching.py](logic/cam_matching.py) (pura, 11 test) + endpoint `GET /api/cam-params/{c}/{p}/matching` LIVE. Chiave primaria (strategia, numero) dal commento M6 + verifica alias; **passata di recupero** per il bug numeri-commento-errati di Cimatron (diagnosticato: il post scrive numeri stantii, strategia+alias restano giusti; disambiguazione per ordine). **4388_0024: 98,8%** (79/80, 3 recuperi, 0 conflitti, mai inventa). 4388_0015: 43,7% per **drift versione doc** (87 MPF accumulati vs doc V3 con 42 procedure — non è errore del matching; futuro: match contro la versione storica giusta via `dataPost`). Exit: verifica manuale utente ≥95% su progetti freschi |
| 3 — Classificatore + badge UI | 🟡 98% — resta validazione + UI | 2026-07-11 | — | 2 gg | Motore IBRIDO (tabella famiglia+offset decide; conferme pesate = confidenza; discordanza → ⚠, mai scelte silenziose) + regole dichiarative [config/regole_classificazione.json](config/regole_classificazione.json) v3 (15 test). **Due sessioni di labeling live con l'esperto su firme reali** (25+11 situazioni): dry-run **42% → 72% → 98%** su 248 lavorazioni di 4 progetti, 0 conflitti — [REPORT_DRYRUN_CLASSIFICAZIONE.md](REPORT_DRYRUN_CLASSIFICAZIONE.md). Meta-regole dettate: offset>PU; toll alta=precisione bassa; Angolo Limite→superfici; fz dipende dal Ø; zona CULO=non critica. 4 ❓ residui bloccati su **estrattore v1.3** (offset MW via `GetModuleworksParameters` — non sta nell'XML2). **Resta**: validazione finale report + badge classe in UI |
| 4 — MAIN builder (selezione per classi) | ✅ v1 CONSEGNATA | 2026-07-13 | 2026-07-13 | 0.5 gg | **L'obiettivo finale dichiarato è operativo**: barra "SELEZIONA: [stati] · CLASSE: SGROSSATURE / PREFINITURE / FINITURE / FIN.TOLLERANZA / NON CRITICHE / FORATURE / MISURE" con conteggi, combinabile (X o Y), escluse riprese → checkbox pre-spuntate → Lancia in NC → LancioNCModal → genera MAIN. Flusso salva-main/snapshot INTATTO. **Estensioni future**: warning eleggibilità SGR→PREF→FIN, somme tempi per classe selezionata, filtro "solo non-presidiato" (presidio già nei dati) |
| 5 — Mappa parametri (impara + verifica) | 💤 Dopo Fase 3 | — | — | 2-3 gg | Accumulo JSON parametrici per (famiglia utensile × strategia × materiale) → range normali appresi → verifica pre-lancio "parametro insolito" (es. offset 0.5 su una FF). Evoluzione data-driven della tabella decisionale (idea utente 2026-07-10) |
| 6 — Rotture in contesto ("lampadina") | 💤 Specifica dettata 2026-07-11 | — | — | 4 gg | Vedi sottosezione "Scheda rottura" qui sotto — catena dettata dall'esperto: rottura → ultimo programma che ha chiamato l'utensile (log OPC UA) → tipo lavorazione + parametri + tempi → storico contestualizzato + contesto esteso (sequenza reale precedente, offset procedure precedenti, zona) |

**Nota Fase 3 (anticipo)**: ✅ **CONSEGNATO 2026-07-11** — badge parametri CAM
nella lista Fresatura di Progetti ([Progetti.jsx](frontend/src/pages/Progetti.jsx):
`CamBadge` + fetch matching in `FresaturaPanel`, additivo e best-effort: senza
estrazione la pagina è identica a prima). Mostra: sigla operazione colorata
(SGR/FIN/RIP/FOR/5X/MISURA/PROF) + offset parete/fondo/contorno + fz +
designazioni fori, tooltip con procedura/PU/commento/Vc/toll/SR, ⚠ sui match
recuperati dal bug numeri. Endpoint matching arricchito con `parametri`
compatti per procedura. Build deployata, verificata live su 4388_0024.

### Fase 6 — "Scheda rottura" (specifica dettata dall'esperto, 2026-07-11)

**Il problema**: oggi le rotture si raccolgono ma "nel vuoto" — manca il
match programma ↔ rottura.

**Cosa abbiamo già**: utensili chiamati dal log OPC UA (`_utensili_visti`,
sessioni/programmi in lavorazioni_log con timestamp), lista programmi con
utensile dichiarato (MPF), eventi rottura con causa (tool_history), e ora
parametri per procedura (estrattore SDK) + matching procedura↔MPF +
classificatore.

**La catena dettata**:
1. Rottura rilevata → **ultimo programma che ha chiamato quell'utensile**
   (dal log reale, non dalla lista) → è lì che è avvenuta la rottura.
2. Da quel programma, via matching+estrattore: **tipo di lavorazione,
   parametri utilizzati** (offset/fz/Vc/ap/ae/tolleranze), **tempo di
   impiego, tempo iniziale e finale** (~).
3. **Storico arricchito**: non solo l'evento, ma l'evento + tutto il contesto.
4. **Contesto esteso**: le procedure PRIMA della rottura — sequenza REALE
   eseguita (dal log, non dall'ordine teorico), utensili veri visti, offset
   delle procedure precedenti; in prospettiva le procedure fatte **nella
   stessa zona** in cui lavorava l'utensile rotto.

**Sotto-fasi**:
| | Cosa | Fonte dati |
|---|---|---|
| 6a | Aggancio rottura→programma: finestra temporale fra i due sync TOA, programmi eseguiti nella finestra che hanno chiamato l'utensile | tool_history (ts evento) × lavorazioni_log (sessioni/programmi) × _utensili_visti |
| 6b | Arricchimento: programma → procedura (matching) → parametri (estrattore, versione storica dell'epoca via `dataPost`) + durata impiego + inizio/fine | cam_matching + parametri_cam (storico versioni) |
| 6c | Contesto esteso: sequenza reale precedente (N programmi prima), utensili dal log, offset/parametri delle procedure precedenti | lavorazioni_log + estrattore |
| 6d | Zona di lavoro: proxy iniziale = SR/orientamento + P.U. + commento; zona geometrica vera (LocationData fori, riferimenti geometria) = evoluzione | estrattore (SR, PU, geometria) |
| 6e | "Scheda rottura" consultabile + retro-contestualizzazione delle rotture storiche via timestamp; poi il warning proattivo (pezzo simile da step_analyzer + sequenza simile → lampadina) | tutto quanto sopra |

⚠ **Limite noto da progettare onestamente**: la rottura viene RILEVATA al
sync TOA, non nell'istante in cui avviene — il contesto è una **finestra**
di programmi candidati fra due sync, non sempre un programma unico. La
scheda deve mostrare la finestra, non fingere certezza.

### Exit criteria

- **Fase 1**: JSON parametrico completo su share per un progetto reale entro
  60s dall'apertura del doc in Cimatron; nessun impatto percepibile sull'uso
  di Cimatron (chiamate read-only, throttle).
- **Fase 2**: matching corretto ≥95% su 3 progetti recenti (verifica manuale).
- **Fase 3**: l'operatore riconosce ogni programma dalla lista senza aprire
  il CAM (feedback sul campo ≥1 settimana).
- **Fase 4**: generazione MAIN senza "riprocessamento mentale"; zero MAIN con
  violazioni SGR→FIN sulla stessa zona.

---

## 🥇 Iniziativa attiva: Regola d'oro a evidenze multiple

**Motivazione**: pallet che finiscono in `guasto` anche quando *tutti* i
programmi del MAIN sono in stato `completato` nella UI. Causa diagnosticata:
la regola d'oro [`_applica_regola_oro` in macchina_live.py:659-715](api/routers/macchina_live.py#L659-L715)
fa un **doppio check** (`stato == completato` E `attesi ⊂ _utensili_visti`),
ma lo stato `completato` non garantisce per costruzione che
`_utensili_visti` sia pieno: ci sono quattro vie con cui un programma può
diventare `completato` senza popolare l'array (conferma manuale UI,
`_propaga_stato_a_project`, sync MAIN↔LOG, retro-marcatura con visti già
popolati dal poller solo parzialmente per M6 ravvicinati).

**Conflitto strutturale**: oggi la promozione di un programma a `completato`
richiede *due* condizioni (programma successivo visto + tutti gli utensili
visti). Le ragioni storiche del check utensili sono valide — proteggere
da programmi multi-utensile interrotti a metà, e dare un'evidenza extra
all'ultimo programma del MAIN che non ha un successore — ma il check
duplicato a livello pallet genera falsi `guasto` quando il programma è
stato segnato `completato` per una via che non ha aggiornato `_utensili_visti`.

**Approccio**: sostituire il check binario "attesi ⊂ visti" con un sistema a
**evidenze multiple** che usa più segnali per stabilire la "credibilità"
del completamento, e tracciare la *via* da cui un programma è diventato
completato (`_completato_da: poller_utensili | sequenza | manuale | sync | stop_macchina`).

### Evidenze e veti (definizione operativa)

Un programma è "completato credibilmente" se almeno UNA evidenza è positiva:

| Evidenza | Dato | Forza |
|----------|------|-------|
| **E1 — Utensili visti completi** | `attesi ⊂ _utensili_visti` | Forte |
| **E2 — Durata reale congruente** | `durata_reale ≥ max(60s, tempoStimato × 0.5)` | Forte |
| **E3 — Successore partito** | `_completato_per_sequenza == True` (già esiste a [linea 1336](api/routers/macchina_live.py#L1336)) | Forte |
| **E4 — Conferma operatore** | `_completato_manualmente == True` (nuovo flag) | Media |
| **E5 — Programma senza utensili** | `pg["utensili"]` vuoto (IPM senza M6/T) | Debole — vale solo da solo |

E non ci sono veti negativi attivi:

| Veto | Dato |
|------|------|
| **V1 — Allarme NCK durante l'esecuzione** | Allarme con codice < 700000 fra `tempoInizio` e `tempoFine` |
| **V2 — Durata anomala bassa** | `durata_reale < min(30s, tempoStimato × 0.1)` con `attesi` non vuoto |

### Fasi e stato

| Fase | Stato | Inizio | Fine | Lavoro | Note |
|---|---|---|---|---|---|
| 1 — Semplificare regola d'oro a `stato == completato` + flag `_completato_da` | 🟡 In corso | 2026-05-20 | — | 0.5 gg | Elimina falsi guasto immediatamente. Aggiunge metadati informativi. |
| 2 — Veto V2 (durata anomala) | ⏳ Pending | — | — | 0.5 gg | Cattura programmi promossi `completato` ma fermati subito da M0 |
| 3 — Veto V1 (allarme NCK) | ⏳ Pending | — | — | 0.5 gg | Richiede correlazione `allarmi_log` ↔ finestra `[tempoInizio, tempoFine]` |
| 4 — Evidenza E2 esplicita + confidenza pallet | ⏳ Pending | — | — | 1 gg | Salvataggio `_evidenza_completamento` + livello confidenza per audit |
| 5 — UI "finito con riserva" | 💤 Eventuale | — | — | 0.5 gg | Solo se Fase 4 mostra che la confidenza media è ≥ 0.8 |

### Exit criteria di ogni fase

- **Fase 1** → Fase 2: nessun pallet va più in `guasto` quando tutti i
  programmi sono `completato`. Verifica sul campo per ≥ 7 giorni post-deploy.
- **Fase 2** → Fase 3: zero pallet "finito" su programmi con durata reale
  < 30 s (auto-controllo sul log delle decisioni).
- **Fase 3** → Fase 4: zero pallet "finito" su programmi con allarme NCK
  attivo nella finestra di esecuzione. Verificare sui falsi positivi storici.
- **Fase 4** → Fase 5: la confidenza media giornaliera dei pallet finito è
  ≥ 0.8 (cioè ≥ 80% dei programmi del MAIN ha almeno 2 evidenze positive).

### Casi noti (matrice atteso vs nuovo comportamento)

| Caso | Oggi | Dopo Fase 1 | Dopo Fase 2-3 |
|------|------|-------------|---------------|
| Multi-utensile completato regolarmente | finito | finito | finito |
| Multi-utensile interrotto a metà (stato torna a `in_main`) | guasto | guasto | guasto |
| Ultimo programma del MAIN, M6 persi dal poller | guasto ❌ | **finito** ✅ | **finito** ✅ |
| Conferma manuale operatore | guasto ❌ | **finito** ✅ | **finito** ✅ |
| Sync MAIN↔LOG marca completato | guasto ❌ | **finito** ✅ | **finito** ✅ |
| Programma fermato dopo 5s da M0 | finito ❌ | finito (transitorio) | **guasto** ✅ (veto V2) |
| Allarme NCK nel mezzo, programma comunque "completato" | finito se utensili ok ❌ | finito (transitorio) | **guasto** ✅ (veto V1) |

---

## 🛡 Iniziativa attiva: Safety pallet-MAIN sync ack

**Motivazione**: il 2026-05-15 incidente sfiorato — assegnato un progetto nuovo
a un pallet, generati percorsi+MAIN nuovi, ma il programma pallet sulla
macchina (PALLET_N.MPF) era rimasto con `EXTCALL` al vecchio MAIN. La macchina
ha lanciato percorsi obsoleti su geometria nuova → rischio collisione. Il
backend non può leggere la macchina, quindi la verifica resta umana: serve
un protocollo che renda l'errore vistoso e idempotente.

**Vincolo dichiarato**: non bloccante (operatore deve poter procedere), ma
persistente (non si chiude da solo) e con barriera anti click-meccanico
(typed-confirmation del nome MAIN).

### Fasi e stato

| Fase | Stato | Inizio | Fine | Lavoro | Note |
|---|---|---|---|---|---|
| 1 — Backend ack + endpoint | 🟡 In corso | 2026-05-15 | — | 0.5 gg | Campi `main_sync_ack` + `progetto_id_notificato`, endpoint sync-warnings / sync-ack |
| 2 — Banner Home + modal | 🟡 In corso | 2026-05-15 | — | 0.5 gg | Persistente, typed-confirmation MAIN |
| 3 — Telegram promemoria assegnazione | 🟡 In corso | 2026-05-15 | — | 0.3 gg | Idempotente per (pallet, progetto), fire-and-forget |
| 4 — Badge ⚠ CodaLavorazione + Macchina | ⏳ Pending | — | — | 0.3 gg | Stesso modal, accesso da pagine secondarie |
| 5 — Allarme Telegram CYCLE START senza ack | ⏳ Pending | — | — | 0.3 gg | Seconda barriera al passaggio `grezzo → in_lavorazione` |

### Trigger logico

- `pal.progetto_id` impostato + `progetto.main_snapshot` presente + (`main_sync_ack.progetto_id != pal.progetto_id` OR `main_sync_ack.nome_main != basename(main_path)`).
- Notifica Telegram (Fase 3) idempotente sul campo `progetto_id_notificato`.
- Cambio fase su stesso progetto: **non** scatta (nome lancio invariato).
  Rischio gemello "MAIN obsoleto post-cambio-fase" → iniziativa separata.

### Iniziativa gemella in backlog

**MAIN obsoleto dopo cambio fase**: lo stesso progetto cambia fase ma il MAIN
non viene rigenerato. Soluzione: confronto `main_snapshot.main_programmi`
vs lista programmi `in_main` correnti del progetto. Se diverso → warning
"MAIN obsoleto — rigenera". Non urgente quanto questa, ma utile.

---

## 🎯 Iniziativa attiva: Predittore adattivo durata programmi

**Motivazione**: oggi `tempoStimato` (post-processore CAM) è sistematicamente
sbagliato sui programmi lunghi (rapporto reale/CAM mediano = 0.19 sui programmi
30-120 min, che pesano 1410 min sul totale). I dati storici esistono ma sono
corrotti dal bug di chiusura prematura sessioni in `report.py`. Obiettivo:
fixare il bug, raccogliere dati puliti, costruire un predittore che si adatta
da solo e mostrarlo solo quando affidabile.

**Vincolo dichiarato**: niente sklearn / ML libraries finché il volume dati
non lo giustifica. Statistica robusta + update online sono sufficienti.

### Fasi e stato

| Fase | Stato | Inizio | Fine | Lavoro | Note |
|---|---|---|---|---|---|
| 0 — Diagnostica logging | ✅ Done | 2026-05-07 | 2026-07-08 | 0.5 gg | **673 chiusure raccolte**: dominante `sessione_orfana_no_pgm_attivo` (606, 90%), NON `prog_diverso_dopo_pausa` (23, 3.4%). Root cause: blocco [report.py:248-264](api/routers/report.py#L248-L264) chiude al primo tick 0/5 senza check `in_esecuzione`/`in_pausa` → grace period mai raggiunto. 455/606 riprese entro 15 min, 199 con lo stesso programma (gap 17-483 s). Vedi [REPORT_CHECK_CRITICO_2026-07-08.md](REPORT_CHECK_CRITICO_2026-07-08.md) finding 1 |
| 1 — Fix `report.py` | ✅ Done | 2026-07-08 | 2026-07-08 | 0.5 gg | **Implementato e testato** (vedi Lavori completati 2026-07-08): blocco orfano condizionato a `not in_pausa` + gap tick > `SESSIONE_ORFANA_STALE_SEC` (120 s, riavvio backend); filtro `PALLET\d` (backlog #9); pause sottratte dalla durata programmi (`pausa_sec_programma`); endpoint bonifica `POST /api/report/bonifica-cicli-sistema`; 17 test nuovi su sequenze di tick (106 pytest + 128/128 standalone verdi). **Azioni post-deploy: riavvio backend + chiamare una volta la bonifica** |
| 2 — Osservazione dati puliti | 🟡 In corso | 2026-07-08 | — | 0 gg (3-4 settimane di calendario) | Exit criterion: gap brevi <15 min con stesso programma da ~5/giorno a ~0 entro il 2026-07-15 |
| 3 — Predittore statistico | ⏳ Pending | — | — | 2-3 gg | Modulo `durata_predittore.py` con EMA + filtro MAD |
| 4 — Integrazione UI | ⏳ Pending | — | — | 1 gg | Mostra previsione solo se `confidence ≥ 0.7` |
| 5 — Cross-program (opzionale) | 💤 Eventuale | — | — | — | Solo se Fase 3-4 mostrano i propri limiti |

### Exit criteria di ogni fase

- **Fase 0** → Fase 1: ≥50 chiamate a `_chiudi_sessione` loggate, distribuzione fra path chiara, ipotesi causa formulata.
- **Fase 1** → Fase 2: dopo 1 settimana post-fix, gap brevi (<15 min) con stesso programma in chiusura/apertura sessione passano da ~5/giorno a ~0.
- **Fase 2** → Fase 3: ≥50% dei programmi ha `n ≥ 5 campioni nelle ultime 4 settimane E CV < 50%`. Oggi è 18%.
  Se non si raggiunge: c'è un'altra fonte di rumore (override feed, condizioni grezzo, ecc.) — indagare prima di costruire il predittore.
- **Fase 3** → Fase 4: simulazione su dati storici post-fix mostra MAE < 20% sui programmi con `confidence ≥ 0.7`.
- **Fase 4** → produzione: 30%+ dei programmi raggiunge confidence ≥ 0.7 entro 4-8 settimane di osservazione.

### Calendario stimato

```
2026-05-07  →  Fase 0 (logging) deployato
2026-05-09  →  Check diagnostica, scrivere fix Fase 1
2026-05-10  →  Fase 1 deployata
2026-05-17  →  Validazione fix (gap brevi azzerati?)
2026-05-17  →  Inizio Fase 2 (osservazione)
2026-06-07  →  Fine Fase 2 — valutazione qualità dati
2026-06-08  →  Inizio Fase 3 se exit criterion soddisfatto
2026-06-15  →  Predittore in produzione (silente)
2026-07-15  →  Eventuale attivazione UI (Fase 4)
```

### Checkpoint temporali (verifica manuale all'apertura sessione)

Quando rientro in Claude Code, controllare se siamo arrivati a uno di questi
checkpoint e procedere alla fase successiva.

- ✅ **2026-07-08**: ≥50 log raccolti (673) e causa dominante individuata
  (blocco sessione orfana, 90%) → Fase 1 eseguita lo stesso giorno.
- 🔸 **dal 2026-07-15** (1 settimana post-fix): gap brevi <15 min con stesso
  programma scesi a ~0/giorno? Query: sessioni con `_closed_by ==
  "sessione_orfana_no_pgm_attivo"` e ripresa entro 15 min → devono sparire.
  → exit Fase 1 confermata, prosegue Fase 2 (osservazione qualità dati).
- 🔸 **dal 2026-05-17** (1 settimana post-fix): gap brevi <15 min con stesso
  programma scesi a ~0/giorno?
  → exit Fase 1, inizio Fase 2 (osservazione).
- 🔸 **dal 2026-06-07** (4 settimane post-fix): % programmi con n≥5 e CV<50%
  ha raggiunto 50%?
  → exit Fase 2, inizio Fase 3 (predittore).

---

## 🐛 Backlog bug noti

In ordine di priorità (alto → basso):

1. ~~**Sessioni chiuse prematuramente in `report.py`**~~ — ✅ **RISOLTO
   (2026-07-08, Fase 1 predittore)**. Root cause: il blocco "sessione orfana"
   chiudeva al primo tick 0/5 (606/673 chiusure, 199 riprese stesso programma;
   introdotto 2026-03-30 in `464c57b`). Fix: chiusura orfana solo con
   `not in_pausa` + gap tick > `SESSIONE_ORFANA_STALE_SEC`; pause sottratte
   dalle durate; 17 test. Vedi Lavori completati 2026-07-08 e
   [REPORT_CHECK_CRITICO_2026-07-08.md](REPORT_CHECK_CRITICO_2026-07-08.md)
   finding 1. **In osservazione fino al 2026-07-15** (exit criterion Fase 1).
2. **Timeout pallet 1h "lento"** — durante stop intermittenti con micro-tick
   attivi `stop_iniziato_ts` viene azzerato e il pallet può restare
   `in_lavorazione` per molte ore. Soluzioni candidate: abbassare `TIMEOUT_STOP`
   o azzerare il timer solo dopo >30s continui di esecuzione.
3. **Cache `_analisi_setup_cache` TTL 5 min** — dopo modifiche manuali alla
   coda, l'aggiornamento dell'alert utensili può tardare. Già invalidata su
   `avvia_pallet` e altre operazioni; verificare se ci sono altri trigger
   mancanti.
4. **`sync_lavorazione` viola la regola d'oro** (audit 2026-07-02) —
   [pallet.py:564-585](api/routers/pallet.py#L564-L585) mette il pallet
   precedente a `finito` incondizionatamente, senza `_applica_regola_oro`.
   Stesso bug già corretto in `avvia_pallet`, sopravvissuto qui.
   **Nota 2026-07-08**: il binding frontend `syncLavorazione`
   ([client.js:101](frontend/src/api/client.js#L101)) non è chiamato da
   nessun componente → endpoint + binding **eliminabili del tutto** invece
   che da correggere.
5. **`_sanity_unico_in_lavorazione` doppiamente rotta** (audit 2026-07-02) —
   [pallet.py:263-283](api/routers/pallet.py#L263-L283): (a) resetta i pallet
   "in eccesso" direttamente a `grezzo` (transizione vietata); (b) sceglie il
   più recente ordinando `aggiornato` lessicograficamente, ma il campo è
   scritto in formato italiano dal poller e ISO dagli endpoint → il confronto
   è privo di senso (ISO inizia per "2", italiano per "0-3"). Stesso
   anti-pattern del timer stop rotto. Unificare il formato di `aggiornato`.
6. **Chiusura immediata programmi al primo tick di stop** (audit 2026-07-02) —
   un M0 di 10 secondi chiude i programmi `in_lavorazione`: mono-utensile →
   `completato` prematuro (utensile già "visto" all'avvio); il grace di 15 min
   esiste solo per le sessioni, non per gli stati programma
   ([macchina_live.py:1423-1440](api/routers/macchina_live.py#L1423-L1440)).
   È il buco che la Fase 2 di "evidenze multiple" (veto durata) deve chiudere —
   considerare di anticiparla.
7. ~~**`export_rendiconto` self-call HTTP**~~ — ✅ **RISOLTO (2026-07-02, Fase 8
   item 4)**: la self-call ora aggiunge `X-API-Key` se `DMG_API_KEY` è settata
   (header condizionale, no-op a chiave vuota). Resta il *smell* architetturale
   (chiama se stesso via HTTP invece della funzione diretta) — refactor
   rimandato, non urgente.
8. **Matching progetto per substring bidirezionale** —
   [macchina_live.py:1006](api/routers/macchina_live.py#L1006):
   "4297_0008" matcha anche "4297_0008_BIS" → possibile attribuzione di
   programmi al progetto sbagliato con nomi affini.
9. ~~**Filtro `_FILTRI_SISTEMA` con `PALLET5` letterale**~~ — ✅ **RISOLTO
   (2026-07-08, insieme al #1)**: match esplicito `PALLET\d+(\.MPF)?` al posto
   del letterale; endpoint idempotente `POST /api/report/bonifica-cicli-sistema`
   per rimuovere le chiavi spurie storiche da `cicli_utensile` (**da chiamare
   una volta dopo il deploy**). Test parametrico su PALLET1-6 + guardia sui
   programmi utente normali.
10. ~~**Endpoint pallet senza lock — residuo Fase 6**~~ — ✅ **RISOLTO
    (2026-07-08)**: `async with _proj_write_lock` (lo stesso del poller) attorno
    a load→modifica→save di `set_stato_pallet`, `avvia_pallet`,
    `ricalcola_stati_pallet`, `sincronizza_coda`, `assegna_progetto`,
    `invia_programma`, `post_sync_ack`, `set_ordine_esecuzione`,
    `sync_pallet_progetti`, `sync_lavorazione`. La chiamata annidata
    `assegna_progetto → sincronizza_coda` (stesso lock non rientrante) spostata
    FUORI dal lock. Le due `_atomic_write` dirette su worktrack_projects.json
    sostituite con `_save_progetti` (guardia anti-wipe). Test
    [tests/test_pallet_lock.py](tests/test_pallet_lock.py): no-deadlock +
    no-lost-update (3/3). Vedi Lavori completati 2026-07-08.
11. ~~**Scan selettivo cieco su cartelle posizione `P*`**~~ — ✅ **RISOLTO
    (2026-07-08)**: nuovo helper `_risolvi_cartelle_progetti_attivi` enumera
    `base/<commessa>/` e confronta il nome-progetto normalizzato
    (`_nome_progetto`) — match esatto, gestisce `P0005`/`p609`/`0221` senza
    casi speciali. Verificato sulla share reale: **0 regressioni** (stesse 10
    cartelle risolte) + mapping `P*` corretto. 8 test in
    [tests/test_nc_scan_selettivo.py](tests/test_nc_scan_selettivo.py).
    Aggiunta diagnostica `stats["progetti_senza_cartella"]`.
12. **Salvataggio parziale del tick su timeout** (finding 5) — `await`
    Telegram fra `_save_progetti` e `_save_pallet` dentro il lock del poller
    ([macchina_live.py:1583](api/routers/macchina_live.py#L1583)); il
    `wait_for(timeout=10)` di main.py può cancellare lì → progetti salvati,
    pallet no. Fix: notifica dopo i save, o `asyncio.shield`.
13. **`_build_log_index` lavoro morto + priorità invertita** (finding 6) —
    [main_sync.py:82-136](api/routers/main_sync.py#L82-L136): calcolato ogni
    5 min ma non più usato (LEGGE 6); docstring di `reset_guasto` promette
    un ricalcolo che non avviene.
14. **`_load_log` ritorna la cache senza deepcopy** (finding 7) —
    [report.py:94](api/routers/report.py#L94), contro la convenzione
    CLAUDE.md. Regge solo finché nessun caller fa `await` fra load e save:
    documentare il vincolo nel modulo o fare deepcopy.
15. ~~**OEE "Performance" sempre 100% (finta)**~~ — ✅ **RISOLTO (2026-07-08)**:
    scelta utente = **consistenza vs media storica** (il tempo CAM è escluso,
    inaffidabile ~5×). Performance = Σ media_storica / Σ durata_reale (cappata
    a 1.0), solo per programmi con media affidabile (n≥`CICLI_MIN_ANOMALIA`).
    Helper condiviso `_performance_consistenza` usato da `/giornaliero` e
    `/storico` (che aveva `1.0` hardcoded). Flag `performance_da_storico` /
    `performance_n_pgm` per trasparenza. Verificato su dati reali: valori
    variati (59-100%, cattura i giorni lenti) invece del 100% fisso; 10 test
    in [tests/test_oee_performance.py](tests/test_oee_performance.py).
    **Nota**: ~100% in media per costruzione (proprietà della scelta
    consistenza) — segnala gli outlier, non è la performance OEE classica.
16. ~~**`pallet_history` non ha mai registrato un ciclo**~~ — ✅ **RISOLTO
    (2026-07-08)**: nuovo osservatore centrale `aggiorna_pallet_history` nel
    poller — rileva le transizioni dallo stato pallet PERSISTITO (aperti +
    ultimo_stato su disco → sopravvive ai riavvii), immune a chi ha cambiato
    lo stato. Rimossi `on_pallet_stato_changed` + `_cicli_aperti` (in memoria)
    e l'hook manuale in `set_stato_pallet`. Verificato sui dati reali (apre i
    4 cicli attivi, idempotente); 12 test in
    [tests/test_pallet_history.py](tests/test_pallet_history.py). **Backfill
    retroattivo dalle sessioni**: non incluso (i primi cicli dei pallet già
    attivi partono da "ora"; i successivi sono accurati) — eventuale follow-up.
17. **`/api/tools/check` di fatto inerte — regex rotta** (audit 2026-07-10) —
    [tools.py](api/routers/tools.py) `_estrai_utensili_da_testo`: backslash
    raddoppiati dentro raw string (`r'T\\s*=...'`) → la regex non matcha mai
    un MPF reale → il check disponibilità utensili risponde sempre
    `can_run=True` con liste vuote. La versione corretta esiste in
    `progetti_utensili.py:parse_mpf_testo` — unificare.
18. **Parse utensili vuoto = programmi promossi senza verifica** (audit
    2026-07-10) — se `_parse_mpf_metadati` torna `utensili=[]` (file in lock
    CAM: nc_analyzer riapre con `open()` normale senza share-mode e inghiotte
    l'errore), `_verifica_utensili_pgm` vede attesi=∅ e promuove il programma
    a `completato` SENZA verifica → possibile falso `finito` del pallet.
    Fix candidato: share-mode anche in nc_analyzer + trattare attesi vuoti
    come "verifica non possibile" (non come "verificato").
19. **Tre parser MPF paralleli divergenti** (audit 2026-07-10) — la stessa
    logica di parsing vive in `nc_scanner.py` (2 regex M6 DIVERSE al suo
    interno: substring `'M6'` in nc_analyzer vs `\bM6\b` interno, virgolette
    opzionali vs obbligatorie → `utensili[]` e `utensili_lista` possono avere
    lunghezze diverse), `Progetti.jsx:parseMpfFile` e `ui/tab_progetti.py`;
    `is_ripresa` è triplicata (nc_scanner, analisi_nc, ripresa.js). Unificare
    o almeno aggiungere test di parità.
20. **Incoerenza unità vita utensili in `analisi_fine_vita`** (audit
    2026-07-10) — [tools.py](api/routers/tools.py): `life_total` diviso per
    60 ma `life_remaining` usato direttamente come minuti nello stesso
    endpoint. Verificare le unità reali del TOA e uniformare.
21. **Analisi STEP all'avvio del cam_tracker mai funzionata** (visto nel log
    2026-07-11) — [cam_tracker.py](cam_tracker/cam_tracker.py) nel blocco di
    avvio di `run()`: `self.cimatron.get_active_project()` ma l'attributo si
    chiama `self.com` (e il metodo è un altro) → `AttributeError` inghiottito
    dal try/except: l'analisi STEP del progetto già aperto all'avvio non è
    mai partita (quella su cambio progetto funziona). Pre-esistente, non
    legato all'estrattore.

---

## 🔐 Backlog sicurezza (check critico 2026-07-08, Task 4)

Dettagli e raccomandazioni in [REPORT_CHECK_CRITICO_2026-07-08.md](REPORT_CHECK_CRITICO_2026-07-08.md)
sezione "Task 4". L'hardening 2026-07-02 (Fasi 1-8) ha coperto molto; questi
sono i residui. Contesto: backend su `--host 0.0.0.0` = esposto a tutta la LAN.

| # | Sev | Item | Fix proposto |
|---|-----|------|--------------|
| S1 | 🟡 In corso | API key OFF + host 0.0.0.0 → chiunque sulla LAN invia file NC alla CNC, cambia IP macchina/percorso NC, resetta stato — **senza credenziali** | **✅ Login operatori con PIN IMPLEMENTATO (2026-07-08)** — vedi Lavori completati e [ATTIVAZIONE_AUTH.md](scripts/ATTIVAZIONE_AUTH.md). Multi-PC preservato (no bind localhost), PIN non nel bundle, sessioni + lockout, reset 3 vie. **OFF di default**: attivazione = `DMG_AUTH_ENABLED=1` + `reset_pin.py --init`. **Resta consigliato (non ancora fatto)**: (b) firewall Windows allow-list IP sulla porta 8000; (d) reverse proxy HTTPS se serve cifratura del traffico LAN |
| S2 | 🟠 | CORS `allow_credentials=True` + `allow_methods=["*"]` + origins estendibili via env | Rifiutare `*`+credentials; nota difensiva nel codice |
| S3 | 🟠 | Canale TCP verso MachineServer C#: IP modificabile senza auth, no cifratura/auth, contenuto NC non validato | Auth sempre on + allow-list IP client sugli endpoint macchina; audit IP (già logga) |
| S4 | 🟠 | `TELEGRAM_BOT_TOKEN` in chiaro in `.env`/`os.environ` = controllo remoto macchina se rubato | Vincolo: mai dumpare env/config in un endpoint; ACL su `.env`; bot già filtra `chat_id` (ok) |
| S5 | 🟡 | `GET /api/scripts/*.reg` scaricabile senza auth (vettore modifica registro) | Auth + checksum noto |
| S6 | 🟡 | `salva_configurazione` (percorso-nc, machine-config) senza lock né validazione dominio (percorso `C:\` → scan intero disco) | Lock + scrittura atomica + validazione path |
| S7 | 🟡 | `/docs` e `/openapi.json` pubblici → mappa completa endpoint per reconnaissance | `docs_url=None` o dietro auth in produzione |

**Nota**: S1 resta la leva, ma il bind su localhost è **escluso per vincolo
operativo** (accesso da più PC). L'equivalente multi-PC è la coppia
**API key attiva + firewall allow-list IP**: la prima ferma gli accessi
accidentali/script da qualunque origine, la seconda restringe la superficie
ai soli PC autorizzati (e copre anche S3, S5, S7 verso il resto della LAN).
La chiave dedicata sugli endpoint macchina (c) protegge la CNC anche
dall'estrazione della chiave globale dal bundle.

**Valutazione "account operatore con PIN" (richiesta utente, 2026-07-08)**:
✅ **sì, risolve S1 meglio della sola API key** e mantiene il multi-PC —
il segreto non viaggia più nel bundle JS (login → token di sessione emesso
dal server) e in più dà identità per-operatore (audit: chi ha inviato alla
CNC, chi ha resettato). **Condizioni vincolanti** perché sia efficace:
1. validazione **server-side** con token di sessione a scadenza (mai
   PIN/logica nel bundle);
2. anti-brute-force sul login: PIN ≥ 5-6 cifre + lockout/backoff dopo N
   tentativi (un PIN a 4 cifre senza lockout si forza in <2 h da LAN);
3. i client non interattivi (cam_tracker, self-call rendiconto) restano su
   `DMG_API_KEY` da env — già predisposti, la chiave NON entra nel bundle;
4. token in header via interceptor (`apiAuth.js` già esistente, si estende)
   e in sessionStorage — niente cookie → CSRF neutralizzato (assorbe S2);
5. il firewall allow-list (b) resta consigliato: senza TLS il PIN/token
   viaggia in chiaro sulla LAN (sniffing) — la (d) proxy HTTPS lo chiude.
Non risolve (nessuna misura app-level lo fa): PC autorizzato compromesso.
Sforzo stimato: 1-2 gg (backend: login + store PIN hashati + sessioni nel
middleware esistente; frontend: pagina PIN + estensione interceptor; test).

---

## 🔬 Backlog ricerche funzionali future (da avviare)

Tre lavori messi in coda dall'utente il **2026-07-19** — richiedono **ricerca +
ragionamento**, non ancora avviati. Nessuno dei tre è iniziato: sono qui per
essere ripresi con contesto, non da improvvisare.

### R1 — Invio file diretto PC → macchina (porta 9999) «non ha mai funzionato»

**Obiettivo**: mandare i file NC direttamente dal PC alla macchina (DMG DMC 160U
/ Sinumerik 840D) via il canale sulla **porta 9999**. Dichiarazione utente: la
funzione **non ha mai funzionato davvero** → serve capire *perché* e *come*
farla funzionare, non solo "chiuderla".

**Cosa sappiamo già** (da audit sicurezza): il canale è il server C#
`machine_server_csharp` in ascolto su **:9999**, pensato per iniettare programmi
NC nella NCU via **DNC / `transfer_dnc.vbs`**. Oggi il flusso reale è invece
manuale (vedi [[project_flusso_main_reale]]): selezione in DD → genera MAIN →
**copia manuale** del MAIN sulla share/macchina.

**Da investigare (ricerca)**:
- Il listener :9999 è davvero attivo? Con quale protocollo si aspetta i dati
  (raw socket? framing custom? handshake DNC)?
- Come avviene fisicamente il transfer verso una 840D PowerLine con PCU 50: DNC
  gateway dell'HMI-Advanced, WinPCIN/RS232 emulata, accesso a drive di rete
  della NCU, o `transfer_dnc.vbs` che pilota l'HMI? Perché fallisce (percorso NC
  sbagliato, HMI non in stato ricevente, permessi share, encoding file)?
- Confronto col pattern che **funziona** altrove (bridge Heidenhain deny-by-default).
- ⚠ **Vincolo sicurezza**: se resa funzionale, il canale **deve** nascere con
  auth (oggi è senza) — intreccio con backlog sicurezza **S3** e con la Fase 3a
  del piano sicurezza (che invece lo *chiuderebbe*): decidere prima se serve
  vivo+autenticato o va dismesso.

### R2 — Generazione autonoma file TOA/TMA dalla macchina + copia su share

**Obiettivo**: far sì che la macchina **generi da sola** i file **TOA/TMA**
(dati utensili / correttori + magazzino della 840D) e li **copi sulla share**,
come oggi avviene **a mano**. Serve replicare in automatico i passi manuali odierni.

**Cosa sappiamo già**: `server_config.ini` ha `tools_toa_folder`; il backend
legge `tools_machine.json` (utensili caricati in macchina) dalla share. Esiste
già un canale **OPC UA** verso la macchina (`opcUa_Server_xp.exe` sul PCU 50) e
il server C# che lo legge.

**Da investigare (ricerca)**:
- Quali sono esattamente i passi manuali oggi (chi esporta il TOA/TMA dall'HMI-
  Advanced, con quale funzione — series start-up / data backup / upload — e dove
  li mette).
- Vie per automatizzarlo: (a) job schedulato sul **PCU 50** che invoca l'export
  HMI e copia sulla share; (b) azione **NC/PLC** che scatena il backup; (c)
  **leggere i dati utensile via OPC UA** (già disponibile) e **scrivere noi** i
  file TOA/TMA nel formato atteso, senza toccare l'HMI (piano meno invasivo,
  coerente con [[project_dmg_desk_schermo_live]] "non toccare il PCU").
- Formato/encoding preciso dei file TOA/TMA della 840D e cadenza necessaria
  (a ogni cambio utensile? a turno?).

### R3 — Collegamento diretto (live) ai dati macchina via OPC UA (query on-demand)

**Obiettivo**: oggi leggiamo `OpcUaLegacy.log` (funziona), ma è un canale **a
senso unico, ritardato (~4s) e a campi fissi**. Poter **interrogare la macchina
direttamente** e chiederle l'informazione che serve, quando serve, sarebbe
**molto di più**. Dichiarazione utente: «riprovare a collegarsi direttamente ai
dati forniti dalla macchina».

**Cosa sappiamo già**: il server C# `machine_server_csharp` legge la Sinumerik
via **OPC UA** (`opcUa_Server_xp.exe` sul **PCU 50 / Windows XP**) e ne scrive
un dump su `OpcUaLegacy.log` ogni ~4s sulla share; il backend lo legge
read-only. Quindi un **endpoint OPC UA sulla macchina esiste già** ed è
raggiungibile — oggi però lo consuma solo il C#.

**Da investigare (ricerca)**:
- Endpoint/porta e **security policy** dell'`opcUa_Server_xp` sul PCU 50; quali
  **NodeId** espongono ciò che ci serve (progStatus, nome programma/blocco,
  utensile attivo + dati TOA, posizioni, **allarmi NCK**, feed/rpm reali).
- Client OPC UA (es. `asyncua` in Python) **direttamente dal backend**, *oppure*
  estendere il C# esistente con un'**API query on-demand** — preferibile **un
  solo client** che tocca la macchina, per non avere due consumer OPC UA in
  concorrenza sul PCU datato.
- ⚠ **Impatto/rischio sul PCU 50 XP**: interrogare live mentre gira HMI-Advanced
  non deve destabilizzare la produzione (stesso principio di non-invasività di
  [[project_dmg_desk_schermo_live]]). Valutare throttle e read-only.
- **Cosa si sblocca**: allarmi in tempo reale (→ veto V1 "allarme NCK" della
  regola d'oro a evidenze multiple), TOA live (→ si lega a **R2**), feed/rpm
  reali (oggi *parsati e scartati*, vedi Idee/Task 3), posizione/blocco corrente.
- Dipendenza nota: il dato live esiste solo con **macchina + PCU accesi** (come
  il log, oggi fermo dal 18/07 perché la macchina è spenta).

---

## 💡 Idee / miglioramenti UX

Non urgenti. Tirar fuori quando c'è uno slot.

- **Check critico 2026-07-08 — Task 2 (migliorie tecniche)**: elenco completo
  con priorità in [REPORT_CHECK_CRITICO_2026-07-08.md](REPORT_CHECK_CRITICO_2026-07-08.md)
  sezione "Task 2". Highlights: separare `stato_corrente` dal log sessioni
  (−99% scritture SMB, oggi ~90 GB/giorno), tail-read di OpcUaLegacy.log con
  parse condiviso, I/O del tick in executor (rende reali i timeout), heartbeat
  applicativo per hang event-loop, timestamp ISO ovunque, test macchina a
  stati sessioni, rimozione codice morto (endpoint `/debug-ore-progetto`
  duplicato, `sync_lavorazione`, migrazioni one-shot in startup), costanti
  inline → constants.py, backup a orario fisso.

- **Layout PROGRAMMI ATTIVI**: aggiungere collapse dei gruppi al click,
  ricerca rapida per numero pgm, sticky header del gruppo durante scroll.
- **Notifiche Telegram**: aggiungere comando `/eta` per richiedere a chat
  l'ETA totale + programma corrente.
- **Frontend Macchina.jsx — previsione fine vita**: mostrare "tempo medio
  reale (ultimi 10 cicli)" accanto al tempo stimato per gli utensili con
  dati affidabili (legato all'iniziativa predittore).
- **Vita media — uscita dal proxy**: oggi tutti i record storici sono
  marcati `proxy=true` perché `life_total` non era salvato prima del
  2026-05-15. Da ora viene salvato (T1). Verificare dopo 4-8 settimane
  che gli alias attivi abbiano almeno qualche ciclo `proxy=false` →
  ridurre il peso del proxy nel calcolo o ignorarlo del tutto quando
  ci sono ≥5 cicli puri per alias.
  **✅ Checkpoint verificato 2026-07-08**: 99 cicli puri raccolti —
  `FS25R2L85`=21, `FFPI42R0.8L114`=6, `FS16R2L80F85E6`=6 → per questi
  3 alias la soglia ≥5 è superata: si può procedere alla riduzione del
  peso proxy.
- **Check critico 2026-07-08 — Task 3 (dati sottoutilizzati)**: elenco
  completo D1-D9 in [REPORT_CHECK_CRITICO_2026-07-08.md](REPORT_CHECK_CRITICO_2026-07-08.md)
  sezione "Task 3". Oltre a backlog #15/#16: `contesto_avvio` raccolto a
  ogni sessione ma mai letto (usa-o-elimina), classificazioni fermi
  dell'operatore mai lette (Pareto cause + TPM con durate reali invece
  della stima 300 s/fermo), anomalia ciclo che ignora l'override dello
  stesso tick, `allarmi_log` pronto per veto V1 + top-allarmi,
  `dataPost` vs `generato_il` per warning "MPF ri-postato dopo il MAIN",
  `feed_attuale`/`rpm_attuale` parsati ma scartati.

---

## ✅ Lavori completati (storico)

In ordine cronologico inverso. Solo i fix significativi, no commit minori.

### 2026-07-08
- **Storico cicli pallet — osservatore centrale (backlog #16 / D2)** —
  [pallet_history.py](api/routers/pallet_history.py) +
  [macchina_live.py](api/routers/macchina_live.py). `pallet_history.json` non
  veniva MAI scritto: l'hook `on_pallet_stato_changed` era chiamato solo dal
  PATCH manuale (mai da regola d'oro/avvia_pallet/main_sync) e teneva i cicli
  aperti in `_cicli_aperti` in memoria → persi a ogni riavvio. Sostituito con
  `aggiorna_pallet_history(pallets, projects, config)`: osservatore chiamato
  dal poller a ogni tick che rileva le transizioni confrontando lo stato
  attuale con l'ultimo osservato — `aperti` e `ultimo_stato` **persistiti su
  disco** (scrittura atomica) → sopravvivono ai riavvii; immune a quale punto
  del codice ha cambiato lo stato. Apre ciclo su grezzo/in_lavorazione con
  progetto, chiude su finito(completato)/guasto(guasto)/vuoto(interruzione)
  con durata e n_pgm. Rimossi hook manuale + `_cicli_aperti`; `/statistiche`
  legge gli aperti persistiti. Chiamato fuori dal lock progetti (file
  separato, scrive solo su transizione), non fa mai crashare il tick.
  **Verificato**: 12 test [tests/test_pallet_history.py](tests/test_pallet_history.py)
  (apri/chiudi, esiti, no-riapertura grezzo→in_lavorazione, idempotenza,
  multifase, sopravvivenza riavvio, durata, multi-pallet); dry-run sui dati
  reali apre i 4 cicli attivi con n_pgm corretto ed è idempotente; suite 164
  pytest + 128/128 gate. **Nota**: i primi cicli dei pallet già attivi al
  deploy partono da "ora" (ts_inizio approssimato); i successivi sono precisi.
- **OEE Performance reale — consistenza vs media storica (backlog #15 / D1)** —
  [report.py](api/routers/report.py). Il calcolo era finto: `sec_teorici =
  durata_sec_teorica or durata_sec` e `durata_sec_teorica` non è scritto da
  nessuno → `sec_teorici == sec_reali` → performance sempre 100%; in `/storico`
  era proprio `* 1.0` hardcoded. Il tempo CAM (`tempoStimato`) è escluso perché
  inaffidabile (~5×, motivo dell'iniziativa predittore). **Scelta utente**:
  performance = **consistenza vs media storica** = Σ media_storica(`cicli_utensile`)
  / Σ durata_reale, cappata a 1.0, solo per programmi con media affidabile
  (n≥`CICLI_MIN_ANOMALIA`); esclusi programma live e durate nulle. Helper puro
  `_performance_consistenza` condiviso fra `/giornaliero` e `/storico`. Aggiunti
  `oee.performance_da_storico` (bool) e `oee.performance_n_pgm` per trasparenza
  (fallback su disponibilità se nessuna media affidabile). **Verificato**: 10
  test [tests/test_oee_performance.py](tests/test_oee_performance.py) (lento→<100%,
  veloce→cap 100%, media non affidabile esclusa, live escluso, aggregazione
  pesata sul tempo, case-insensitive); su dati reali produce 59-100% variati
  (cattura i giorni lenti) invece del 100% fisso; frontend `oee.performance`
  invariato come contratto (numero) → nessuna rottura, build ok; suite 152
  pytest + 128/128 gate. **Limite dichiarato**: ~100% in media per costruzione
  (il ciclo è confrontato con la media che lo include) — utile per gli outlier,
  non è la performance OEE classica speed-loss.
- **Scan selettivo: risoluzione cartelle `P*` (backlog #11)** —
  [nc_scanner.py](api/routers/nc_scanner.py). La costruzione di
  `proj_attivi_dirs` ricostruiva `base/<cms>/<pos>` dal nome normalizzato →
  falliva su cartelle `P0005`/`p609` (escluse da scan selettivo E
  riconciliazione fino al full scan, 6 h). Nuovo helper
  `_risolvi_cartelle_progetti_attivi` enumera `base/<commessa>/` e confronta
  con `_nome_progetto(cms, sottocartella)` — stessa funzione dello scan file,
  match esatto e non euristico. Rimosso `proj_attivi_names_upper` (mai letto);
  aggiunta diagnostica `stats["progetti_senza_cartella"]`. **Verificato sulla
  share reale**: 0 regressioni (stesse 10 cartelle dei progetti attivi
  correnti), mapping P* corretto (P0005→4295_0005, p609→4231_0609); 8 test in
  [tests/test_nc_scan_selettivo.py](tests/test_nc_scan_selettivo.py); suite
  142 pytest + 128/128 gate pallet. Beneficio latente oggi (nessun progetto
  P* attivo) ma il branch `feature/scan-selettivo` è ora sicuro per il merge.
- **Lock read-modify-write sugli endpoint pallet (backlog #10)** —
  [pallet.py](api/routers/pallet.py). Completa la Fase 6: il poller salva
  l'intero `pallet_state.json` a fine tick, ma 10 endpoint facevano
  load→save fuori dal lock → lost-update (finestra 5 s). Ora tutti dentro
  `async with _proj_write_lock` (lo stesso lock che il poller e nc_scanner
  usano). Punti delicati gestiti: (a) `assegna_progetto → sincronizza_coda`
  usano lo stesso lock non rientrante → la chiamata a sincronizza_coda è
  spostata fuori dall'`async with` (due sezioni critiche sequenziali;
  sincronizza_coda è idempotente); (b) le due scritture dirette
  `_atomic_write` su worktrack_projects.json (`_sincronizza_pallet_progetto`,
  `sync_pallet_progetti`) sostituite con `_save_progetti` (guardia anti-wipe).
  `check_pallet_completati` (startup, sincrona, non-await) non necessita lock:
  non può interlacciarsi col poller. **Verificato**:
  [tests/test_pallet_lock.py](tests/test_pallet_lock.py) prova no-deadlock
  (assegna_progetto completa entro timeout) e no-lost-update (endpoint attende
  il poller e non sovrascrive la sua modifica); suite 134 pytest +
  128/128 gate pallet + compile ok.
- **Autenticazione operatori con PIN (backlog sicurezza S1)** — nuovo
  [api/auth.py](api/auth.py) + [api/routers/auth_router.py](api/routers/auth_router.py) +
  integrazione middleware in [api/main.py](api/main.py). Multi-PC preservato
  (bind localhost scartato per vincolo utente):
  - **Modello**: login con PIN (4-10 cifre) → token di sessione temporaneo.
    Il PIN NON viaggia nel bundle (a differenza della sola API key). Account e
    hash PIN (PBKDF2-SHA256+salt) su file **locale** `auth_accounts.json`,
    fuori dalla share. Sessioni in memoria (TTL `DMG_AUTH_SESSION_ORE`, 12h).
    Lockout progressivo dopo 5 PIN errati (60s→…→1h).
  - **Servizi non-umani** (cam_tracker, self-call): restano su `DMG_API_KEY`
    da env — il middleware accetta token di sessione OPPURE API key.
  - **Reset PIN, 3 vie** (come richiesto): (1) `scripts/reset_pin.py` da
    console — riserva sempre disponibile; (2) `POST /api/auth/admin/reset-pin`
    da browser con master key; (3) primo accesso imposta il PIN.
  - **Frontend**: `AuthGate` (chiede `/api/auth/status`; auth OFF → app
    diretta, zero cambi) + `LoginPin` (tastierino, selezione operatore,
    primo-accesso) + interceptor `apiAuth.js` esteso (inietta Bearer token) +
    logout in Sidebar.
  - **OFF di default**: `DMG_AUTH_ENABLED=1` per attivare; procedura in
    [scripts/ATTIVAZIONE_AUTH.md](scripts/ATTIVAZIONE_AUTH.md).
  - **Verificato**: `tests/test_auth.py` 25 test (primo accesso, login,
    lockout, sessioni/scadenza, cambio PIN, reset, validazione, hash mai in
    chiaro); middleware end-to-end 9/9 (401 senza cred, 200 con token/key,
    401 con cred errate, pubblici/OPTIONS/query-token passano); retro-compat
    auth OFF (nessuna auth richiesta come oggi); `npm run build` ok; suite
    131 pytest + 128/128 gate pallet; CLI reset provato end-to-end.
  - **Resta da fare (consigliato, non bloccante)**: firewall allow-list IP
    (S1-b), reverse proxy HTTPS (S1-d).
- **Fix chiusure premature sessioni + filtro PALLET (Fase 1 predittore,
  backlog #1 + #9)** — [report.py](api/routers/report.py) +
  [constants.py](api/constants.py):
  - **Blocco "sessione orfana"**: scatta solo se `not in_pausa` E gap fra
    `now` e `ultimo_tick` > `SESSIONE_ORFANA_STALE_SEC` (120 s = riavvio
    backend certo, il poller gira ogni 5 s). Con tick freschi la gestione
    torna al grace period 15 min, che prima era codice morto per gli stop
    0/5. Il caso riavvio resta gestito con `fine = ultimo_tick` (stima
    onesta, durate non gonfiate dal downtime); `_close_ctx` ora include
    `gap_tick_sec`.
  - **Filtro `PALLET\d`**: i file pallet Siemens PALLET1-6 sono filtrati
    con match esplicito (prima solo il letterale "PALLET5"). Nuovo endpoint
    idempotente `POST /api/report/bonifica-cicli-sistema` per pulire le
    chiavi spurie storiche in `cicli_utensile`.
  - **Pause sottratte dalle durate**: nuovo contatore
    `sc["pausa_sec_programma"]` accumulato alla ripresa entro grace;
    `_chiudi_programma` lo sottrae → i campioni `cicli_utensile` riflettono
    il tempo macchina, non il wall-clock con le pause M0.
  - **Endpoint live coerenti con la pausa**: `/giornaliero`, `/storico` e
    `/sessione-live` fermano il conteggio a `pausa_inizio` per la sessione
    corrente in pausa e sottraggono le pause del programma (prima del fix
    le sessioni si chiudevano subito e il caso non esisteva).
  - **Test**: nuovo [tests/test_report_sessioni.py](tests/test_report_sessioni.py)
    — 17 test sincroni sulle sequenze di tick (stop breve, continuazione,
    durata depurata, grace scaduto, programma diverso, riavvio/orfana,
    pausa lunga ≠ orfana, PALLET1-6, giornaliero in pausa, bonifica).
    **Verificato**: 106 pytest verdi (89 pre-esistenti + 17 nuovi),
    gate standalone 128/128, compile ok. NB: in locale lanciare pytest con
    `-p no:asyncio` (pytest-asyncio 0.23.3 rompe la collection del package;
    la CI non lo installa e non è affetta).
  - **Azioni post-deploy**: riavviare il backend; chiamare una volta
    `POST /api/report/bonifica-cicli-sistema`; verificare al 2026-07-15
    che i gap brevi con stesso programma siano ~0/giorno.
- **Check critico Task 1-4 (analisi, nessun fix applicato)** — revisione
  integrale dei file core + verifica su dati/config di produzione (sola
  lettura). Prodotto:
  [REPORT_CHECK_CRITICO_2026-07-08.md](REPORT_CHECK_CRITICO_2026-07-08.md).
  - **Task 1** (lacune logica): 7 finding, chiusura Fase 0 predittore
    (root cause bug #1: blocco "sessione orfana" report.py:248, provata su
    673 chiusure), backlog #9-#16.
  - **Task 2** (migliorie): I/O share (−99% scritture separando
    stato_corrente), tail-read log, executor, heartbeat, timestamp ISO,
    test sessioni, codice morto.
  - **Task 3** (dati sottoutilizzati): D1 OEE performance finta,
    D2 pallet_history mai scritto, D4 classificazioni fermi mai lette,
    D5 vita-utensili proxy maturo (99 cicli puri), D6-D9.
  - **Task 4** (sicurezza): backlog S1-S7 (sezione dedicata sopra);
    S1 = API key OFF + host 0.0.0.0 è la leva principale.

### 2026-07-02
- **Hardening Fase 8 — Sicurezza endpoint**:
  - **Item 2 — path traversal upload NC**: `_nome_file_sicuro` in
    [macchina_invio.py](api/routers/macchina_invio.py) applicata a `/invia`
    **e** `/invia-batch` (il `os.path.join(tmp, upload.filename)` grezzo era
    in **entrambi**, l'audit ne segnalava uno solo). Riduce al basename
    (neutralizza `..\`, `../`, `C:\`, `sub/dir/`), rifiuta nomi degeneri, ADS
    (`:`), wildcard; whitelist estensioni `{.mpf,.nc,.spf}` **allineata al
    filtro del frontend** (`InvioMacchina.jsx`) — NON solo `.MPF` come diceva
    l'audit: avrebbe rotto l'invio dei sottoprogrammi `.SPF`. Validazione
    fail-fast (un nome illecito → 400 su tutta la richiesta) + riga di audit
    con IP sorgente. **19/19** test avversariali.
  - **Item 3 — validazione config macchina**: `PUT /macchina-invio/config`
    ora valida IP/host (`_valida_ip_o_host`) e porta (`_valida_porta`).
    Accetta IPv4/IPv6 e hostname RFC 1123; **rifiuta i typo-IPv4** (es.
    `10.95.20.999`, `10.95.20`) che una regex hostname lascerebbe passare
    come "host" salvandoli silenziosamente. **22/22** test.
  - **Item 4 — self-call rendiconto** (ex backlog #7): la GET interna di
    `export_rendiconto` aggiunge `X-API-Key` se `DMG_API_KEY` è settata
    (no-op a chiave vuota) → non va più in 401 con la chiave attiva.
  - **Item 1 — API key preparata, OFF (scelta utente: "prepara, OFF")**:
    il middleware `DMGSecurityMiddleware` in [api/main.py](api/main.py) esisteva
    già (dormiente senza `DMG_API_KEY`). Scoperto che il **frontend era già
    cablato**: [apiAuth.js](frontend/src/utils/apiAuth.js) monkey-patcha
    `window.fetch` iniettando `X-API-Key` su ogni `/api/*` (copre i ~100 fetch
    sparsi), no-op a chiave vuota; `apiUrl()` firma i link diretti `<img>/<a>`
    (usato in TabDocumenti/Report/Progetti). Cablati i due client Python
    mancanti: **cam_tracker** (`DMGDeskClient` legge la chiave da env
    `DMG_API_KEY` o `[dmgdesk] api_key`) e la **self-call rendiconto**.
    Telegram in-process non chiama il backend (verificato). UI desktop legacy
    non più in uso (confermato dall'utente) → non cablata. Chiave lasciata
    **OFF**: zero cambiamenti in produzione ora; attivazione = 1 variabile,
    procedura completa in [ATTIVAZIONE_API_KEY.md](scripts/ATTIVAZIONE_API_KEY.md).
  - **Verificato**: 3 file compilano; sanitizzatore 19/19; validazione IP
    22/22; matrice auth middleware **11/11** in isolamento (chiave attiva:
    `/api` senza header→401, header/query giusti→200, chiave errata→401,
    pubblici/OPTIONS/assets→200; soft mode: tutto→200 come oggi) senza avviare
    i poller contro la share; regressione pallet **128/128**.
- **Hardening Fase 7 — Autostart / supervisione**:
  - Nuovo [scripts/run_service.py](scripts/run_service.py): launcher robusto
    per backend/step — libera la porta da processi orfani, (backend) verifica
    `frontend/dist`, esegue uvicorn in foreground loggando in
    `logs/uvicorn_<servizio>.log`. Foreground = il task resta "running"
    finché uvicorn vive → RestartOnFailure lo rilancia se esce.
  - Nuovo [scripts/installa_autostart.py](scripts/installa_autostart.py):
    registra i task `DMGDesk_Backend` e `DMGDesk_StepAnalyzer`, sul modello
    provato di `cam_tracker/installa_avvio_automatico.py`. Invocazione python
    DIRETTA (niente wrapper cmd.exe → nessun quoting fragile). Sotto-comandi
    `--stato`, `--rimuovi`, `--dry-run`.
  - **Watchdog corretto (fix chiave)**: la prima versione affidava il riavvio
    a `RestartOnFailure`, che **non riparte** i processi killati dall'esterno
    (Task Scheduler li registra come "completato", non "fallito") — verificato
    sul campo: backend chiuso → NON ripartiva. La ripetizione agganciata al
    `LogonTrigger` non basta: non si attiva nella sessione già loggata (query
    task → "Prossima esecuzione: N/D"). Soluzione: **`TimeTrigger` con
    `StartBoundary` nel passato + ripetizione 1 min + `MultipleInstancesPolicy=IgnoreNew`**.
    Servizio vivo → tick ignorato; morto → riavviato entro ~1 min. Applicato a
    tutti e tre i task (backend, step, **cam_tracker**).
  - [scripts/README_AUTOSTART.md](scripts/README_AUTOSTART.md): istruzioni +
    caveat (LogonTrigger richiede login/auto-login per i drive di rete; non
    usare i task insieme ad AVVIA_DMGDESK.bat; il watchdog copre crash e kill
    esterni ma NON gli hang dell'event-loop → watchdog applicativo futuro).
  - **Verificato sul campo**: installer eseguiti da admin (3 task installati);
    "Prossima esecuzione" valorizzata ~1 min nel futuro per tutti e tre (non
    più `N/D`) = watchdog armato nella sessione corrente; **prova reale kill →
    restart**: backend PID 42856 ucciso alle 18:14:52 → ripartito da solo PID
    34320 alle 18:15:07 (~15 s) → HTTP 200 con dati reali. STEP :8002 e
    CAMTracker confermati UP; il CAMTracker (era "Pronta") avviato dal primo
    tick del watchdog.
  - **Resta azione utente**: rimuovere `AVVIA_DMGDESK.bat` da `shell:startup`
    (evita doppio avvio) e configurare l'auto-login Windows per il ripristino
    completo dopo un riavvio senza operatore.
- **Hardening Fase 6 — Lock read-modify-write** (chiuso i lost-update
  poller ↔ nc_scanner ↔ UI):
  - **Poller** (`aggiorna_stati_da_log`): il lock copriva solo il save
    progetti; il load era fuori e `_save_pallet` **senza alcun lock**.
    Ora `async with _proj_lock` avvolge load+mutazione+save di progetti E
    pallet in un'unica sezione critica; rimosso il lock annidato interno
    (era `async with` solo attorno al save → race col load a monte).
    `aggiorna_da_log` (file separato) resta fuori per non allungare l'hold.
  - **main_sync**: stessa correzione su `job_sync_main_log`,
    `salva_main_snapshot` (proj caricato fuori dal lock, pallet dentro) e
    `reset_guasto` (load fuori, save pallet senza lock). Tutte e tre ora
    load+modifica+save dentro `_write_lock`.
  - **Perché era un bug reale**: nc_scanner tiene `_write_lock` attraverso
    `run_in_executor` (scansione share, secondi). Con il load fuori dal
    lock, il poller caricava proj_data, si sospendeva sull'acquisizione del
    lock al save, nc_scanner nel frattempo salvava i nuovi MPF, il poller
    poi salvava la propria copia stale → programmi appena scansionati
    spariti. Probabile causa di parte delle "sparizioni" attribuite allo
    scanner.
  - **Verificato**: test di concorrenza dedicato — writer che modifica i
    progetti mentre il poller lavora: ordine eventi
    `writer_acquire → tick_start → writer_save → tick_done`, progetto del
    writer **preservato** (no lost-update), lock rilasciato, nessun deadlock
    su ri-acquisizione (9/9). Verificato che main_sync si blocca se il lock
    è tenuto esternamente (acquisisce davvero). Regressione 128/128, pytest
    89, re-indent applicato via script con backup e compile-check.
- **Hardening Fase 5 — CI onesta + igiene repo**:
  - **La CI non era falsamente verde, era peggio: dipendeva dall'ambiente.**
    Verificato empiricamente: `check()` in `test_pallet_logic_v2.py` non fa
    `assert` → in CI (senza pytest-asyncio) i 52 `test_*` venivano raccolti
    e **passavano sempre**; in locale (con pytest-asyncio 0.23.3) pytest
    **crasha** con INTERNALERROR al collect del Package. In nessuno dei due
    casi la logica pallet era davvero un gate.
  - Fix onestà: [tests/conftest.py](tests/conftest.py) esclude il file
    standalone dalla raccolta diretta; nuovo [tests/test_pallet_logic_suite.py](tests/test_pallet_logic_suite.py)
    esegue la suite in-process e **asserisce l'aggregato** (`falliti == 0`,
    `totale >= 100`). Provato: rompendo un check l'aggregato diventa ROSSO
    (128/128 falliti → AssertionError).
  - [ci.yml](.github/workflows/ci.yml): (a) step gate standalone
    `python tests/test_pallet_logic_v2.py` (exit code = verdetto,
    deterministico); (b) pytest con coverage estesa ad **api/** (prima
    esclusa: 20k righe non misurate); (c) `PYTHONIOENCODING=utf-8` a livello
    job (il runner stampa ✅/❌, crashava su cp1252); (d) nuovo job **Frontend
    Build** (`npm ci && npm run build`) — prima un frontend rotto passava la
    CI; (e) release zip corretta: includeva la vecchia app desktop ed
    **escludeva api/ e frontend/**; ora include `api/`, `frontend/dist`
    (buildato nel job), `telegram_monitor/`, esclude `node_modules`.
    Verificato: YAML valido, zip di prova 74 file con api/main.py +
    frontend/dist, senza node_modules.
  - **Igiene repo**: de-track da **7407 → 220 file tracciati** (−7189).
    Rimossi dall'index (disk-safe, file intatti su disco): `frontend/node_modules`
    (4925), `Progetto5/` (2174, vecchio progetto React autonomo, nessun
    riferimento dal codice attivo — verificato), `archive/` (36), `backup/`
    (20), `dmgdesk_complete/` (13), `dmgdesk_update/` (5), file di stato
    runtime (`cam_tracker_data.json`, `turni_snapshot.json`,
    `cartelle_recenti.json`, `step_features.json`, `cam_tracker.pid`), dead
    file (`ui/*.old`, `*.pyold3`, vari `.zip`). `.gitignore` esteso di
    conseguenza. **Esclusi di proposito** 4 file: `machine_server_c/*.exe`
    (binari del server macchina, potenziale artefatto di deploy) e 2 `.spec`
    PyInstaller — lasciati tracciati, de-track a discrezione utente.
  - ⚠ **Nota transizione**: il de-track è staged, non committato. Su questa
    macchina i file restano su disco (untracked+ignored). Su ALTRI cloni il
    primo `git pull` dopo il commit rimuoverà la copia tracciata dei file di
    stato runtime — accettabile perché l'app li rigenera, ma da sapere.
    Annulla tutto con `git reset` se serve.
  - **Verificato dopo il de-track**: gate standalone 128/128, suite pytest
    89 passed (con aggregato onesto), nessun sorgente attivo de-trackato.
- **Hardening Fase 4 — Fix rapidi verificati**:
  - `import json` aggiunto a macchina_live.py: l'allerta utensili
    fine-vita/disabilitato di `get_live_context` non aveva **mai**
    funzionato (NameError inghiottito da `except: pass`). Verificato
    funzionante contro la share reale.
  - [CodaLavorazione.jsx](frontend/src/pages/CodaLavorazione.jsx): la
    catena `.then` di risincronizzazione coda era agganciata a `fetchLog()`
    (che non ritorna una Response) invece che alla POST `sincronizza-coda`
    → la coda non si è mai risincronizzata sui completamenti.
  - **Stato "backend giù" visibile** ([App.jsx](frontend/src/App.jsx)):
    GlobalPoller conta i tick falliti e dopo 3 (~15 s) emette
    `backend_down` sull'evento globale; GlobalStatusBar mostra banner
    testuale pulsante "⚠ BACKEND NON RAGGIUNGIBILE — DATI NON AGGIORNATI"
    (4px di colore non bastano a distanza braccio); Sidebar tratta
    backend-giù/`stato_macchina -1` come connessione persa. Prima:
    `catch {}` = dashboard congelata mostrata come live a tempo
    indeterminato — il failure mode peggiore per l'officina.
  - **Tick saltati riflessi in `GET /tick`** (`_segna_tick_errore` +
    pulizia flag episodici al primo tick buono): prima i rami log-stale
    e (da Fase 3) share-giù ritornavano senza aggiornare `_last_tick`,
    quindi il frontend continuava a ricevere l'ultimo stato buono come
    fresco. Risolve anche il bug "chiavi episodiche accumulate per sempre".
  - `Wrap` spostato fuori da `MainContent` ([App.jsx](frontend/src/App.jsx)):
    ridefinito a ogni render creava una nuova identità componente → React
    smontava/rimontava l'intera pagina a ogni navigazione (doppio load,
    interval ricreati). Rimosso anche `MARKER_TEST_123456` residuo.
  - Errori del machine poller da DEBUG a WARNING con traceback
    ([main.py](api/main.py)): un tick che moriva sistematicamente non
    lasciava traccia in produzione.
  - **Verificato**: compilazione, `get_live_context` funzionante su share
    reale, test dedicato `_last_tick` (tick saltato riflesso + pulizia al
    recovery), `npm run build` ok, regressione 128/128.
- **Hardening Fase 3 — Poller fail-safe su I/O** (chiuso "glitch share =
  perdita stato"):
  - Nuovo [utils/fs_guard.py](utils/fs_guard.py): `ShareNonRaggiungibileError`
    + `quarantena_file()` (rinomina `<nome>.corrotto.<timestamp>`).
  - I tre loader di stato (`_load_progetti`, `pallet._load`, `_load_log`)
    ora distinguono TRE casi: (a) file assente + cartella presente = prima
    esecuzione → default; (b) errore I/O o share giù (manca anche la
    cartella padre) → **eccezione, mai default** — prima un `except: pass`
    ritornava la struttura vuota che il tick poteva persistere sopra i dati
    reali; (c) JSON corrotto → quarantena con evidenza preservata + default.
  - Guardie anti-wipe: `_save_progetti` e `_save_log` **rifiutano** di
    scrivere 0 record sopra un file esistente > 100 KB (firma di un load
    fallito a monte, non di una cancellazione legittima).
  - Tick `aggiorna_stati_da_log`: early-return con WARNING se il log
    macchina è illeggibile (`errore_parse` prima ignorato → share giù
    diventava "stato 0 = FERMA" → falsi fermi + pallet `guasto` dopo 1h)
    o se progetti/pallet non sono leggibili. Ritorna `stato_macchina: -1`
    come il ramo log-stale.
  - Endpoint read-only (`/stato`, `/live-context`) non toccati: lì i dati
    parziali non scrivono nulla. Su share giù gli endpoint di scrittura
    ora rispondono 500 esplicito invece di operare su stato vuoto.
  - **Verificato**: suite di simulazione dedicata 26/26 (share giù, file
    = directory, corrotti con quarantena, guardie anti-wipe, tick saltati)
    + regressione 128/128.
- **Hardening Fase 2 — Rotazione segreti (parte codice)**:
  - Scansione mirata della history (`git log -S`, senza mai stampare i
    valori): trovati **3 segreti distinti**, non 2 come stimato dall'audit —
    token Telegram (`.env` @ `3d740d9`/`fd81971`), token GitHub #2 da 43
    char (`.env` @ `3d740d9`), e un token GitHub #1 da 36 char **ancora nel
    tree pubblicato** dentro `SETUP_GIT_GITHUB.md` riga 104, mascherato da
    "esempio" (entropia massima: 32 caratteri distinti su 32 — verificato).
  - `SETUP_GIT_GITHUB.md` sanificato con placeholder; verificato zero
    token ad alta entropia nel working tree. `push_dmgdesk.bat` era già
    pulito (legge `GITHUB_TOKEN` da `.env`; i suoi `ghp_` sono placeholder).
  - `utils/logger.py`: logger `httpx`/`httpcore` forzati a WARNING —
    httpx logga a INFO l'URL completo delle richieste e per Telegram l'URL
    contiene il bot token. Verificato: log di produzione già puliti
    (0 occorrenze storiche), INFO soppresso anche con root logger a INFO.
  - Procedura operativa completa in [scripts/ROTAZIONE_SEGRETI.md](scripts/ROTAZIONE_SEGRETI.md):
    revoca (BotFather + GitHub), commit sanificazioni, scrub history con
    git-filter-repo (comandi che estraggono i segreti dalla history senza
    digitarli), force-push, verifiche finali.
  - Regressione: 128/128 assertion.
- **Hardening Fase 1 — Backup reale** (chiuso il "backup fantasma"):
  - `_collect_files` riscritta: usa gli **helper canonici** dei moduli
    proprietari (`_progetti_path`, `_pallet_path`, `_log_path`,
    `_get_tools_db_path`, `_history_path`, ...) invece di chiavi config
    inesistenti. Ora ritorna `(files, critici_mancanti, avvisi)`.
  - Definito `FILE_CRITICI` (worktrack_projects, pallet_state,
    lavorazioni_log, tools_machine, config): assenza ⇒ log ERROR +
    **allarme Telegram** "BACKUP INCOMPLETO" via nuovo helper
    `_notifica_telegram` (TelegramNotifier reale).
  - Archivi annuali inclusi col nome vero `lavorazioni_YYYY.json`
    (il vecchio codice cercava `lavorazioni_log_archivio.json`, mai esistito).
  - MANIFEST arricchito: `completo`, `critici_mancanti`, hash MD5 calcolato
    **sulla copia** (riferimento di integrità per il restore; l'originale
    cambia ogni 5s). `GET /api/backup/stato` espone i nuovi campi.
  - Nuovo `scripts/restore_backup.py`: `--lista`, dry-run di default,
    `--esegui` con conferma typed, `--dest-override` per test; verifica
    hash + validità JSON prima di scrivere, scrittura atomica.
  - **Fix collaterale in `main.py`**: la notifica Telegram del backup
    notturno archivi importava `invia_messaggio_telegram`, funzione **mai
    esistita** — ImportError inghiottito da `except: pass`, notifica mai
    partita. Ora usa `_notifica_telegram`.
  - **Verificato sul campo**: backup reale 14 file (4.3MB progetti + 5.2MB
    log inclusi) su entrambe le destinazioni (C: + H:); restore di prova
    14/14 su cartella temporanea con hash e JSON validati; allarme testato
    con share fittizia vuota → MANIFEST `completo=false` + messaggio
    Telegram ricevuto (HTTP 200); regressione 128/128 assertion.
  - ⚠ Nota per Fase 2: `httpx` logga a INFO l'URL Telegram **col token
    dentro** — silenziare il logger `httpx` quando si ruota il token.

### 2026-05-15
- **Vita media utensili — feature completa** (T1→T5):
  - T1: arricchiti i record di `tool_replacements.json` con `life_total`
    (e `life_total_old` per sostituito/allungamento_vita) — modifiche a
    `tool_history.py` linee 245/277/343-344. I record pre-2026-05-15
    restano senza il campo (proxy).
  - T2: nuovo modulo `ml/vita_media.py` — funzioni `vita_media_alias`,
    `consumo_totale_per_alias`, `riepilogo_vita_media`. Aggrega per
    alias (i gemelli sono intercambiabili) ma pesa ogni ciclo con il
    `life_total` del **suo** tool_id (no media sporca quando i duplo
    hanno vite teoriche diverse). Include `rimosso+rottura` nei cicli
    di fine vita oltre a `sostituito`.
  - T3: tre endpoint REST in `tool_history.py`: `/vita-media`,
    `/vita-media/{alias}`, `/consumi?da=&a=`. Fix bug bordo data nel
    filtro (`YYYY-MM-DD` come `a` normalizzato a `T23:59:59`).
  - T4: widget "⏱ Vita media" in `Macchina.jsx` con tabella, filtro
    "Solo in macchina/Tutti", badge confidenza/proxy/warning.
  - T5: bottone "📥 CSV" + endpoint `?formato=csv` (separatore `;`,
    BOM UTF-8, default min_cicli=1 per CSV vs 3 per JSON).
  - **Stato dati al 2026-05-15**: 102 record storici, 20 alias toccati,
    4 alias con ≥3 cicli (FS25R2L85 primo a confidenza "alta" con 11
    cicli). Tutti `proxy=true`.
- **Vita media — fix allungamenti** (stesso giorno, follow-up T2):
  La prima versione di `vita_media_alias` IGNORAVA i record
  `allungamento_vita`, segnalandoli solo come `warning_allungamenti`.
  Errore semantico: se l'operatore allunga manualmente la vita di un
  duplo, l'utensile è realmente durato di più. Fix: nuova funzione
  `_estrai_cicli_da_timeline` in [ml/vita_media.py](ml/vita_media.py)
  che ricostruisce per ogni `tool_id` la sequenza temporale degli
  eventi e somma i delta degli allungamenti al ciclo in cui cadono:
  ```
  vita_consumata% = (start_pct − vita_prima_chiusura) + Σ Δ_allungamenti
  ```
  Per record vecchi senza `tool_id` la stessa logica si applica al
  bucket orfano, accettando l'approssimazione di mescolare duplo.
  Output: nuovo campo `min_medio_da_allungamenti` (informativo);
  rimosso `warning_allungamenti` (non più sottostima);
  badge frontend cambiato da warning `↑` a info `+N↑`.
  **Impatto numerico**: FS25R2L85 sale da 70 → 86 min reali (+22%),
  FS25R2L125F128 da 63 → 79 (+25%). Allungamenti in cicli ancora
  aperti (es. T3529 mai sostituito) NON sono contati — entreranno
  alla prossima sostituzione di quel duplo.

### 2026-05-07
- Fix sort lista programmi attivi (Home.jsx) per `numPgm` zfill 6.
- Redesign layout PROGRAMMI ATTIVI: dashboard + cambi utensile + progress bar
  programma corrente + marker ⚠ sui pgm > 30 min.
- Fix bug visivo segmenti schiacciati (`flexShrink: 0`).
- Setup ROADMAP.md, CLAUDE.md.

### 2026-05-06
- Fix Telegram notifiche: mappa stati Sinumerik 840D corretta in
  `monitor.py`, branch errore con codice ALARM, `_IN_LAVORO = {1,2,3}`.
- Fix `ricalcola_stati_pallet` riportava `guasto` → `grezzo`: aggiunto skip
  iniziale per stato `guasto`.
- Fix `estrai_alias_da_progetti` non filtrava progetti orfani: ora filtra
  per progetti effettivamente in coda su un pallet.

### 2026-05-05
- Fix timer `stop_iniziato_ts` rotto: `now_iso` separato + helper
  `_parse_stop_ts` tollerante a entrambi i formati. Tre call site corretti.
- Fix `avvia_pallet` violava regola d'oro: ora chiama `_applica_regola_oro`.
- Fix previsione vita utensili multi-utensile: distribuisce `tempoMin`
  per-M6 invece di attribuire tutto al primo utensile.

---

## Convenzioni di questo file

- **Stato fasi**: 🟡 in corso, ⏳ pending, ✅ done, ❌ abbandonato, 💤 eventuale.
- **Date**: ISO 8601 sempre (`YYYY-MM-DD`).
- Quando si chiude una fase: spostare riga in "Lavori completati" con data.
- Quando si apre una nuova iniziativa: copiare la struttura di "Iniziativa attiva".
- Aggiornare `Data ultimo aggiornamento` in cima ad ogni modifica significativa.
