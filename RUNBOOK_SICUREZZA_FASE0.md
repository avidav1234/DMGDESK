# Runbook — Fase 0 sicurezza DMG Desk (chiusura esposizione attiva)

Chiude **V1** (auth off) e mitiga **V2/V3/V5** del [REPORT_SICUREZZA_DMG_DESK.md](REPORT_SICUREZZA_DMG_DESK.md).
Modifiche minime e **reversibili** (vedi Rollback in fondo).

> ⚠️ Eseguire in un momento a **bassa attività**: al termine gli operatori dovranno
> fare login col PIN. Serve accesso console al **server del backend** e alla
> **macchina del cam_tracker** (CAM35). Fare i passi **nell'ordine indicato**.

---

## Passo 1 — PIN operatori: auto-registrazione al primo accesso

Non serve pre-impostarli. Con l'auth attiva, la pagina di login mostra gli
operatori; ognuno, al **primo accesso**, sceglie il proprio PIN (che diventa il
suo). Nessuna azione admin.

Accorgimento: gli account nascono "vuoti" → vale *"il primo che accede rivendica
lo slot"*. Su LAN interna con operatori noti il rischio è piccolo se:
- si attiva **quando gli operatori sono presenti** (rivendicano subito il loro slot);
- si usano **nomi reali** (vedi pannello sotto), così è chiaro chi prende quale slot.

**Gestione operatori dalla UI** (nuova scheda **Utilità → Operatori**, dietro
master key): aggiungere/rinominare operatori, azzerare o impostare PIN, eliminare.
Riserva da console sempre disponibile: `py scripts/reset_pin.py --lista` /
`op1 --pin <cifre>` / `op1 --clear`.

> Nota: il pannello e l'auto-registrazione diventano operativi **dopo** il riavvio
> del backend (Passo 4) e con `DMG_API_KEY` configurata (le mutazioni admin la
> richiedono).

---

## Passo 2 — Configurare il `.env` del backend (NON riavviare ancora)

Nel `.env` locale del backend, aggiungere/verificare:

```ini
DMG_AUTH_ENABLED=1
DMG_API_KEY=<LA_TUA_CHIAVE>        # generata con: py -c "import secrets; print(secrets.token_urlsafe(32))"
DMG_AUTH_SESSION_ORE=12
# DMG_VNC_PASSWORD deve restare valorizzata (serve al relay per autenticarsi al PCU)
```

Non mettere `VITE_API_KEY` nel frontend: la master key non deve entrare nel bundle.
Gli umani entrano col PIN (Bearer token), la chiave serve solo ai servizi.

---

## Passo 3 — Propagare la chiave al cam_tracker — AUTOMATICO

Se il cam_tracker è sulla **stessa macchina** del backend (deploy attuale): niente
da fare. `cam_tracker.py` ora carica il `.env` del progetto all'avvio, quindi
`DMG_API_KEY` arriva sia all'agente sia al subprocess estrattore. Basta
**riavviare il cam_tracker** (Passo 4) perché prenda la chiave.

Deploy **separato** (cam_tracker su un'altra macchina, senza il `.env` accanto):
imposta `DMG_API_KEY=<LA_TUA_CHIAVE>` come variabile d'ambiente del processo, o
`[dmgdesk] api_key = <LA_TUA_CHIAVE>` in `cam_tracker_config.ini` (che però è
tracciato da git: non committarlo con il segreto dentro).

---

## Passo 4 — Riavvio coordinato + verifica

1. Riavviare il **backend** (uvicorn `api.main:app`, porta 8000).
2. Riavviare **cam_tracker / agente** estrattore.

Verifiche (attese tra parentesi):

```sh
curl -s http://localhost:8000/api/auth/status                          # ({"auth_attiva":true})
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/progetti          # (401)
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: <LA_TUA_CHIAVE>" http://localhost:8000/api/progetti   # (200)
```

- Browser → deve comparire la schermata di **login PIN**; l'operatore entra e usa DD.
- cam_tracker → al primo upload deve dare **200** (non 401): controlla i log dell'agente.

---

## Passo 5 — Firewall (mitiga V2 server C# 9999 e V3 relay/PCU 5900)

Sulla macchina che ospita il **server C#** (porta 9999) e sul percorso verso il
**PCU (5900)**, consentire solo l'IP del backend DD. Esempio Windows:

```powershell
# Blocca 9999 in ingresso, poi consenti solo l'IP del backend
netsh advfirewall firewall add rule name="DNC 9999 deny" dir=in action=block protocol=TCP localport=9999
netsh advfirewall firewall add rule name="DNC 9999 allow backend" dir=in action=allow protocol=TCP localport=9999 remoteip=<IP_BACKEND>
```

(Analogamente per il 5900 del PCU, se gestibile lato rete.) È una mitigazione
temporanea finché la Fase 1 non aggiunge autenticazione vera a quei canali.

---

## Passo 6 — Igiene segreti

- `.env.example` — **già bonificato** in questo commit (rimossa la password VNC di
  fabbrica, aggiunta la documentazione dell'auth PIN).
- **Ruotare il token Telegram**: su @BotFather `/revoke` → nuovo token → aggiorna
  `TELEGRAM_BOT_TOKEN` nel `.env`. Il vecchio è nella git history.
- **Cambiare la password VNC** sul PCU (con la config TCU) appena possibile →
  aggiornare `DMG_VNC_PASSWORD` nel `.env`.

---

## Verifica finale (checklist)

- [ ] `/api/auth/status` → `auth_attiva:true`
- [ ] `/api/progetti` senza credenziali → 401
- [ ] `/api/progetti` con `X-API-Key` → 200
- [ ] login PIN funziona nel browser per op1 e op2
- [ ] upload cam_tracker → 200
- [ ] porta 9999 non raggiungibile se non dal backend
- [ ] token Telegram ruotato
- [ ] `.env` non committato (`git status` non lo elenca)

---

## Rollback (se qualcosa si rompe)

Rimuovere `DMG_AUTH_ENABLED` e `DMG_API_KEY` dal `.env` del backend e riavviare:
si torna esattamente allo stato precedente (accesso libero). Rimuovere anche la
chiave dal cam_tracker. Le regole firewall si eliminano con
`netsh advfirewall firewall delete rule name="..."`.

## Cosa NON fare

- ❌ Non attivare **solo una** delle due (`DMG_API_KEY` senza `DMG_AUTH_ENABLED` rompe
  la UI browser; l'auth senza chiave rompe l'upload cam_tracker).
- ❌ Non mettere `VITE_API_KEY` nel bundle frontend.
- ❌ Non committare mai il `.env` (già escluso da `.gitignore`).
