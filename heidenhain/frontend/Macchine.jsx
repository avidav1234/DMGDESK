import { useState } from 'react'

// Pagina "Macchine TNC 640" — schermo live (noVNC) + pannello dati.
//
// TEMPLATE per il frontend di **Yellow Hub** (le TNC 640 sono ambiente YH).
// NON e' una pagina di DMG desk: va copiata/adattata nel frontend di Yellow Hub.
//
// Incapsula il bridge FastAPI (heidenhain/bridge.py) via iframe: il bridge
// gestisce login, elenco macchine, schermo live e dati. Nessuna dipendenza
// aggiuntiva nel frontend (niente noVNC nel bundle). Il bridge gira come servizio
// separato (default porta 8010); l'URL e' configurabile e persistito in localStorage.

const DEFAULT_BRIDGE = `${window.location.protocol}//${window.location.hostname}:8010`

export default function Macchine() {
  const [base, setBase] = useState(() => localStorage.getItem('tnc_bridge_base') || DEFAULT_BRIDGE)
  const [draft, setDraft] = useState(base)

  const salvaBase = () => {
    const v = draft.trim().replace(/\/+$/, '')
    if (!v) return
    localStorage.setItem('tnc_bridge_base', v)
    setBase(v)
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <div style={{
        display: 'flex', gap: 8, alignItems: 'center',
        padding: '8px 12px', borderBottom: '1px solid rgba(128,128,128,0.25)',
      }}>
        <strong style={{ fontSize: 14 }}>Macchine TNC 640</strong>
        <span style={{ fontSize: 12, opacity: 0.6 }}>schermo live + dati</span>
        <span style={{ marginLeft: 'auto', fontSize: 12, opacity: 0.7 }}>bridge:</span>
        <input
          value={draft}
          onChange={e => setDraft(e.target.value)}
          onKeyDown={e => { if (e.key === 'Enter') salvaBase() }}
          style={{ width: 230, fontSize: 12, padding: '3px 6px' }}
        />
        <button onClick={salvaBase} style={{ fontSize: 12, padding: '3px 10px', cursor: 'pointer' }}>OK</button>
      </div>
      <iframe
        title="TNC 640 — live"
        src={base + '/'}
        style={{ flex: 1, width: '100%', border: 'none' }}
      />
    </div>
  )
}
