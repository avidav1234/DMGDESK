# Runbook — Deploy sicurezza Fasi 1→3 (DMG Desk)

Checklist ordinata per portare in produzione l'hardening dopo la Fase 0.
Piano completo: [ROADMAP_SICUREZZA.md](ROADMAP_SICUREZZA.md).

> Eseguire in finestra a bassa attività. Ogni fase è **indipendente e reversibile**:
> puoi fermarti dopo ognuna. L'ordine consigliato massimizza il guadagno di sicurezza.

---

## Fase 1 — Attivare l'hardening applicativo (solo riavvio)

Il codice è già in repo e **testato** (36/36). Si attiva riavviando il backend.

1. Riavviare il backend (uvicorn `api.main:app`).
2. Verifiche:

```sh
curl -s http://localhost:8000/api/auth/status                                 # {"auth_attiva":true}
curl -s -o /dev/null -w "%{http_code}\n" http://localhost:8000/api/progetti     # 401
curl -s -o /dev/null -w "%{http_code}\n" -H "X-API-Key: <CHIAVE>" http://localhost:8000/api/progetti  # 200
```

3. Browser → login PIN come sempre. Nessun cambiamento per gli operatori.

**Opzionali (env, quando pronti — nessun deploy codice):**
- `DMG_PIN_MIN=6` nel `.env` → PIN nuovi ad almeno 6 cifre (gli esistenti continuano
  a funzionare). Avvisare gli operatori prima.
- `DMG_TRUST_PROXY=1` → **solo dopo** la Fase 2 (quando il backend è raggiungibile
  solo via proxy), altrimenti l'header IP è falsificabile.

Rollback: nulla da fare (il comportamento in prod è invariato). In emergenza estrema
resta `DMG_DISABLE_CUSTOM_MIDDLEWARE=1`.

---

## Fase 2 — TLS (cifra il traffico) — via consigliata: Caddy

Oggi PIN/token/master key viaggiano in chiaro. Con Caddy il traffico browser↔server
diventa HTTPS e il backend torna a bindare solo localhost.

1. **Generare il certificato** (sul server DMG Desk):

```sh
py scripts/genera_cert_tls.py --host <HOSTNAME> --ip <IP_SERVER>
# → certs/cert.pem, certs/key.pem  (oppure usa `tls internal` di Caddy, vedi Caddyfile)
```

2. **Backend solo su localhost** — cambiare l'avvio da `--host 0.0.0.0` a:

```sh
uvicorn api.main:app --host 127.0.0.1 --port 8000
```

3. **Configurare `deploy/Caddyfile`** — sostituire `dmgdesk.local` / `10.95.20.50`
   con hostname e IP reali del server.

4. **`.env`**: aggiungere `DMG_TRUST_PROXY=1` (ora il vero IP client arriva dal proxy).

5. **Avviare Caddy** (scaricato da caddyserver.com/download, singolo .exe):

```sh
caddy.exe run --config deploy/Caddyfile
```

6. **Client**: aprire `https://<hostname-o-IP>/` (non più `http://...:8000`).
   Con `tls internal` importare una volta il root CA di Caddy (`caddy trust`) per
   togliere l'avviso del browser.

7. **Verifica**:

```sh
curl -k -s -o /dev/null -w "%{http_code}\n" https://<HOST>/api/auth/status   # 200
curl -s -o /dev/null -w "%{http_code}\n" http://<HOST>/                        # 301 → https
```

8. Rimuovere i link `?token=` (non più necessari su TLS; evitano il token nei log).

Rollback: fermare Caddy, riportare uvicorn a `--host 0.0.0.0`, togliere `DMG_TRUST_PROXY`.

> Variante Docker/nginx: usare `deploy/nginx.tls.conf` al posto del Caddyfile.
> Variante senza proxy (uvicorn `--ssl-*`): sconsigliata — il cam_tracker dovrebbe
> fidarsi del cert self-signed.

---

## Fase 3 — Firewall OT (chiude i canali non autenticati)

Sulla macchina che ospita il **server DNC C# (:9999)** — come **amministratore**:

```powershell
# Blocca del tutto la 9999 (se il canale non è usato):
powershell -ExecutionPolicy Bypass -File scripts\firewall_ot.ps1

# Oppure: consenti la 9999 SOLO dal backend DD:
powershell -ExecutionPolicy Bypass -File scripts\firewall_ot.ps1 -Backend <IP_BACKEND>
```

Verifica da un altro PC della LAN: la porta 9999 non deve più rispondere.
Rollback: `powershell -File scripts\firewall_ot.ps1 -Rimuovi`.

> Il VNC del PCU (:5900) va chiuso **sul PCU o a livello di rete/switch**, non sul
> backend (che deve poterci uscire per il relay). Lo script accetta `-Porte 9999,5900`
> solo se questa macchina espone davvero il 5900.

---

## Fase 4 — Igiene segreti

1. **Revocare/ruotare il PAT GitHub** trapelato nel commit `3d740d9`
   (GitHub → Settings → Developer settings → Personal access tokens → Revoke).
2. Token Telegram: già ruotato. ✔
3. (Opzionale) Purge della history dei segreti con `git filter-repo`/BFG — in
   finestra dedicata, coordinando i cloni.
4. Rimuovere dalla guida `frontend/.env.example` l'invito a copiare la master key in
   `VITE_API_KEY` (footgun; oggi il bundle è pulito).

---

## Checklist finale

- [ ] Fase 1 attiva (backend riavviato, `/api/progetti` → 401 senza credenziali)
- [ ] TLS attivo (`https://` risponde, `http://` → 301, backend su 127.0.0.1)
- [ ] `DMG_TRUST_PROXY=1` impostato dopo il proxy
- [ ] Porta 9999 non raggiungibile dalla LAN (se non dal backend)
- [ ] PAT GitHub revocato
- [ ] (opz.) `DMG_PIN_MIN=6` con operatori avvisati
