# Aggancio della pagina "Macchine TNC 640" al frontend yellow hub

La pagina React `frontend/src/pages/Macchine.jsx` è pronta ma **non ancora
agganciata** al router/nav, perché `App.jsx` e `Sidebar.jsx` sono in mezzo a
modifiche non committate (feature auth + altro). Applicare queste 2 modifiche
**quando il lavoro sul frontend è committato/stabile** (oppure chiedimi di farlo).

## 1. `frontend/src/App.jsx`

Import (accanto agli altri import di pagina):
```jsx
import Macchine from './pages/Macchine'
```

Rotta (dentro `<Routes>` in `MainContent`):
```jsx
<Route path="/macchine" element={<Wrap><Macchine /></Wrap>} />
```

Full-bleed (la pagina usa un iframe a tutta altezza) — aggiungere `/macchine`
alla lista `FULL_PAGES`:
```jsx
const FULL_PAGES = ['/home', '/coda', ..., '/macchine']
```

## 2. `frontend/src/components/Sidebar.jsx`

Voce di menu (in `NAV_UTILITA`, oppure `NAV_PRIMARY` se la si vuole in alto):
```jsx
{ to: '/macchine', icon: 'macchina', label: 'TNC 640' },
```

## 3. Gating admin

- **Per il momento** l'accesso è protetto dal **bridge** stesso: la pagina mostra
  il form di login del bridge (master key `DMG_API_KEY`) finché non si è admin.
  Quindi il contenuto è già "solo admin" anche senza gating nel frontend.
- Quando il frontend avrà un flag admin esplicito, si può nascondere anche la
  **voce di menu** ai non-admin (filtrando `NAV_*`).

## 4. Requisiti runtime

- Il **bridge** deve girare (default `http://<host>:8010`):
  ```sh
  # PowerShell:  $env:DMG_API_KEY = "..."   (o DMG_BRIDGE_KEY)
  py -m uvicorn heidenhain.bridge:app --host 0.0.0.0 --port 8010
  ```
- L'URL del bridge è configurabile nell'intestazione della pagina (persistito in
  `localStorage['tnc_bridge_base']`), utile se in produzione gira su altra
  porta/host.
- Client noVNC: `git clone --depth 1 https://github.com/novnc/noVNC heidenhain/vendor/noVNC`.

## Alternativa (futura): integrazione same-origin

Per evitare il servizio separato e il doppio login, si può **montare** il bridge
dentro l'app FastAPI principale (`api/main.py`) sotto `/heidenhain`, così eredita
l'auth del backend e la pagina può usare `src="/heidenhain/"` (stessa origine).
Richiede però una modifica a `api/main.py` (ora in volo).
