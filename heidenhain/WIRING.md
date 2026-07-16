# Integrazione della pagina "Macchine TNC 640" in **Yellow Hub**

> ⚠️ Le macchine TNC 640 (Mikron P800) sono ambiente **Yellow Hub**, NON DMG desk.
> Questo progetto è staged nella repo DMG desk solo su branch (`feature/heidenhain-tnc640`)
> in attesa di essere spostato/integrato in Yellow Hub. **Non agganciare a DMG desk.**

Il codice di Yellow Hub **non è in questa repo**, quindi l'aggancio va fatto là.
Qui trovi il **template** pronto e le indicazioni.

## Componenti pronti (in questa cartella)

- `bridge.py` + `tnc_client.py` + `config.py` + `live.html` + `vendor/noVNC` — il
  **bridge** (servizio FastAPI standalone) che fa schermo live + dati. Portabile.
- `frontend/Macchine.jsx` — **template React** della pagina (iframe al bridge).

## Passi per integrare in Yellow Hub

1. **Bridge**: far girare `heidenhain/bridge.py` come servizio (o montarlo nell'app
   di Yellow Hub) raggiungibile dal browser. Chiave propria:
   ```sh
   # PowerShell:  $env:TNC_BRIDGE_KEY = "una-chiave"
   py -m uvicorn heidenhain.bridge:app --host 0.0.0.0 --port 8010
   ```
   Client noVNC: `git clone --depth 1 https://github.com/novnc/noVNC heidenhain/vendor/noVNC`.

2. **Frontend Yellow Hub**: copiare `frontend/Macchine.jsx` nel frontend di YH e
   aggiungerla al router + menu di **Yellow Hub** (non di DMG desk). L'iframe punta
   al bridge (URL configurabile nell'header della pagina, persistito in
   `localStorage['tnc_bridge_base']`).

3. **Auth / admin**: gestione a carico di **Yellow Hub**. Due opzioni:
   - la pagina è visibile solo agli admin di YH (gating lato YH), e il bridge ha la
     sua `TNC_BRIDGE_KEY` come secondo livello;
   - oppure YH proxa il bridge dietro la propria auth.
   Il bridge di suo è **read-only** e default **sola visione** (comando esplicito).

## Integrazione same-origin (consigliata, quando si è dentro Yellow Hub)

Se YH ha una CSP stretta (`default-src 'self'`), un iframe cross-origin al bridge
(`:8010`) verrebbe bloccato. Per l'integrazione definitiva conviene **montare il
bridge dentro l'app di Yellow Hub** sotto un path (es. `/heidenhain`), servendolo
same-origin. In quel caso servono, sul bridge:
- CSP propria sulle pagine (per lo script inline del viewer + WebSocket same-origin);
- path **relativi** in `live.html` (per funzionare sotto il prefisso di mount);
- delega dell'auth a Yellow Hub (token di sessione di YH), NON a DMG desk.

Questi adattamenti sono rapidi ma dipendono dall'auth/CSP reali di Yellow Hub, che
non sono in questa repo — si fanno in fase di integrazione in YH.
