# Roadmap Sicurezza — DMG Desk

Piano di hardening progressivo. Nasce dall'assessment del 2026-07-18 (vedi
[REPORT_SICUREZZA_DMG_DESK.md](REPORT_SICUREZZA_DMG_DESK.md)) misurato contro
**IEC 62443-3-3** (sistemi di controllo industriale), **OWASP Top 10 2021 / ASVS**
e **NIST CSF**.

Principio guida: **deny-by-default**. Assenza di configurazione ⇒ *chiuso*, mai aperto.

Legenda stato: ✅ fatto · 🟡 pronto, da lanciare da te (rete/host) · 🔜 pianificato.

---

## Quadro di partenza (verdetto assessment)

| Livello | Aderenza | Nota |
|---|---|---|
| Auth applicativa (PIN/sessioni/ruoli) | 🟢 buona (~ASVS L2) | PBKDF2 200k+salt, lockout, token opachi, CSP, rate-limit |
| Sistema / OT (IEC 62443) | 🔴 non conforme | no TLS, server CNC :9999 senza auth, segreti in history, default fail-open, rete piatta |

Il collo di bottiglia **non** è il login: è il **trasporto in chiaro** e la
**superficie di rete** attorno alla macchina.

---

## Fase 0 — Chiusura esposizione attiva ✅ (2026-07-16)

Auth operatori attivata in produzione. Dettaglio operativo in
[RUNBOOK_SICUREZZA_FASE0.md](RUNBOOK_SICUREZZA_FASE0.md).

- ✅ `DMG_AUTH_ENABLED=1` + `DMG_API_KEY` in `.env` (gitignored)
- ✅ Login PIN (PBKDF2-SHA256 200k + salt), lockout progressivo, sessioni a token
- ✅ Ruoli admin/operatore + bootstrap primo admin
- ✅ Relay VNC dietro auth (password del PCU terminata lato server)
- ✅ `.env` de-trackato, token Telegram ruotato

---

## Fase 1 — Hardening applicativo ✅ (2026-07-18)

Modifiche **solo codice**, sicure sul deployment in produzione (auth già attiva ⇒
il percorso in uso resta invariato). Nessun rischio di lock-out.

- ✅ **1a** — Master key: confronto a **tempo costante** e robusto ai non-ASCII
  (`_api_key_uguale`, UTF-8 bytes). Elimina il timing side-channel e la classe di
  500 da autofill del browser. `api/main.py`.
- ✅ **1b** — **Deny-by-default**: se non è configurata alcuna auth, le API `/api/`
  rispondono **503** invece di aprirsi. Escape hatch esplicito per lo sviluppo:
  `DMG_ALLOW_INSECURE=1`. `api/main.py`.
- ✅ **1c** — **Trust proxy** opt-in (`DMG_TRUST_PROXY=1`): dietro reverse proxy il
  rate-limit e i log usano il vero IP client da `X-Forwarded-For` (default OFF →
  nessun cambiamento se esposto diretto). `api/main.py`.
- ✅ **1d** — **Lunghezza PIN configurabile** (`DMG_PIN_MIN` / `DMG_PIN_MAX`, default
  4/10 invariati). Permette di alzare il minimo a 6 senza toccare il codice, quando
  gli operatori sono avvisati. `api/auth.py`.
- ✅ **1e** — **Relay VNC deny-by-default**: senza auth configurata il relay resta
  **chiuso** (prima era aperto). Pilota la HMI della macchina: non deve mai essere
  fail-open. Confronto API key anch'esso a tempo costante. `api/routers/schermo_live.py`.

> Attivazione: al **prossimo riavvio** del backend. Nessuna azione lato operatore.

### Da alzare quando pronti (env, nessun deploy codice)
- `DMG_PIN_MIN=6` — dopo aver avvisato gli operatori (i PIN esistenti continuano a
  funzionare; il vincolo scatta solo all'impostazione di un PIN nuovo).
- `DMG_TRUST_PROXY=1` — **solo** quando il backend sarà raggiungibile *unicamente*
  tramite il reverse proxy (Fase 2), altrimenti l'header è falsificabile.

---

## Fase 2 — TLS (confidenzialità del trasporto) 🟡 pronta da lanciare

Oggi PIN, token e master key viaggiano **in chiaro** sulla LAN → viola IEC 62443
SR 4.1 e OWASP A02. Deliverable pronti in questo repo:

- 🟡 `scripts/genera_cert_tls.py` — genera un certificato self-signed (con SAN per
  hostname **e** IP del server) usando `cryptography` (già dipendenza). Nessun
  openssl richiesto.
- 🟡 `deploy/Caddyfile` — **via consigliata**: Caddy (singolo .exe) termina il TLS
  su `:443` e inoltra a `127.0.0.1:8000`. Il backend torna a bindare **solo
  localhost**, così sparisce anche l'esposizione su `0.0.0.0`; le chiamate interne
  (cam_tracker, self-call su `http://localhost:8000`) **non si rompono**.
- 🟡 `deploy/nginx.tls.conf` — variante equivalente per chi usa già nginx/Docker.

**Architettura target:** `browser ──HTTPS:443──▶ reverse proxy ──http──▶ 127.0.0.1:8000`.
Terminare il TLS al bordo evita di dover far fidare i servizi interni del cert
self-signed.

Passi (vedi header dei file): generare il cert → avviare il proxy → cambiare il
bind del backend a `127.0.0.1` → togliere i link `?token=` (non più necessari su
TLS, evitano il token nei log).

Alternativa (senza proxy): `uvicorn ... --ssl-keyfile key.pem --ssl-certfile cert.pem`
— **ma** il cam_tracker dovrà accettare il cert self-signed. Preferire il proxy.

---

## Fase 3 — Rete / OT (segmentazione + firewall) 🟡 / 🔜

- 🟡 **3a** — `scripts/firewall_ot.ps1`: blocca in ingresso `:9999` (server DNC C#)
  e `:5900` (VNC PCU) da tutta la LAN **tranne** l'IP del backend DD. Da eseguire
  come **admin** sulla macchina che ospita il server C#/percorso PCU. Mitiga il
  reperto più grave (comando CNC senza auth) senza toccare la macchina.
  > Nota: hai indicato che il canale :9999 "non ha mai funzionato" — questo script
  > lo **chiude comunque**, così non resta una porta in ascolto non presidiata.
- 🔜 **3b** — Verificare se i processi `machine_server_csharp` / `machine_server_c`
  sono davvero in ascolto; se non servono, **dismetterli**. Se servono, aggiungere
  autenticazione al protocollo (token condiviso) — non lasciarli aperti.
- 🔜 **3c** *(strutturale)* — Segmentazione **IT/OT**: VLAN o DMZ industriale tra
  rete uffici e cella macchina (PCU XP non aggiornabile, server :9999). È la voce
  che manca per poter dichiarare "conforme 62443 zone & conduits". Richiede l'IT
  di rete aziendale.
- ✅ **3d** *(2026-07-19)* — **Allowlist IP applicativa, gestita da UI** (restrizione
  del condotto lato app): con filtro attivo solo i PC in lista usano DMG Desk; gli
  altri vedono **solo la pagina di login**. Un login **admin** auto-ammette il suo
  IP (basta loggarsi da un PC per autorizzarlo); **registro dei tentativi bloccati**
  con "autorizza" al volo. Gestione in **Operatori → Accesso per IP**. Loopback
  sempre ammesso; riserva CLI `scripts/ip_allowlist.py` (`--disable` per sblocco).
  `api/ip_allowlist.py` + middleware + endpoint admin + UI. Default: disattivo.

---

## Fase 4 — Igiene segreti 🔜

- 🔜 **4a** — **PAT GitHub nel commit `3d740d9`** (`.env` storico) — **verificato
  presente**. Confermare che sia **revocato/ruotato** su GitHub (Settings → Developer
  settings → Personal access tokens). Un PAT trapelato = accesso ai repo.
- ✅ Token Telegram (commit `fd81971`) — già ruotato.
- 🔜 **4b** *(opzionale)* — Purge della history dei segreti (`git filter-repo` /
  BFG). Da fare in finestra dedicata perché riscrive la history; coordinare con
  eventuali cloni.
- ✅ **4c** *(2026-07-19)* — `frontend/.env.example` bonificato: invertita la guida —
  `VITE_API_KEY` va lasciata **vuota** (gli operatori usano il PIN → token runtime;
  la master key nel bundle sarebbe pubblica). Il bundle resta **pulito**, verificato.

---

## Note di verifica (assessment 2026-07-18)

- Bundle `frontend/dist`: **0** occorrenze della master key → non trapela nel client. ✅
- `frontend/.env`: **assente** → `VITE_API_KEY` non è bakeato. ✅
- `3d740d9:.env`: contiene **1** token `ghp_…` → da rotazione confermata. ⚠️
- Trasporto: `uvicorn --host 0.0.0.0` HTTP puro, `nginx.conf` solo `:80` → **no TLS**. ⚠️
