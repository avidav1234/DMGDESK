import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect, useState, Component } from 'react'
import AuthGate      from './components/AuthGate'
import Sidebar       from './components/Sidebar'
import Home          from './pages/Home'
import CodaLavorazione from './pages/CodaLavorazione'
import Macchina      from './pages/Macchina'
import Scaffale      from './pages/Scaffale'
import Smontati      from './pages/Smontati'
import HolderBussole from './pages/HolderBussole'
import Generatore    from './pages/Generatore'
import AnalisiNC     from './pages/AnalisiNC'
import InvioMacchina from './pages/InvioMacchina'
import Progetti      from './pages/Progetti'
import Report        from './pages/Report'
import RendicontoProgetto from './pages/RendicontoProgetto'
import CamTracker    from './pages/CamTracker'
import AnalyticsCommesse from './pages/AnalyticsCommesse'
import AlertUtensili from './pages/AlertUtensili'
import RiepilogoTurno from './pages/RiepilogoTurno'
import StepAnalyzer  from './pages/StepAnalyzer'
import SchermoLive   from './pages/SchermoLive'
import GestioneOperatori from './pages/GestioneOperatori'

// â”€â”€ Error Boundary globale â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Previene schermo bianco su eccezioni non gestite nei componenti React.
// Mostra un messaggio di errore con pulsante per ricaricare la pagina.
class ErrorBoundary extends Component {
  constructor(props) {
    super(props)
    this.state = { hasError: false, error: null }
  }
  static getDerivedStateFromError(error) {
    return { hasError: true, error }
  }
  componentDidCatch(error, info) {
    console.error('[DMGDesk] Errore non gestito:', error, info.componentStack)
  }
  render() {
    if (!this.state.hasError) return this.props.children
    return (
      <div style={{
        display: 'flex', flexDirection: 'column', alignItems: 'center',
        justifyContent: 'center', height: '100vh', gap: 16,
        background: '#fef2f2', fontFamily: 'system-ui, sans-serif',
      }}>
        <div style={{ fontSize: 32 }}>âš </div>
        <div style={{ fontSize: 18, fontWeight: 700, color: '#dc2626' }}>
          Errore imprevisto
        </div>
        <div style={{
          fontSize: 12, fontFamily: 'monospace', color: '#7f1d1d',
          background: '#fee2e2', padding: '8px 16px', borderRadius: 6,
          maxWidth: 500, textAlign: 'center',
        }}>
          {this.state.error?.message || 'Errore sconosciuto'}
        </div>
        <button
          onClick={() => window.location.reload()}
          style={{
            background: '#dc2626', color: '#fff', border: 'none',
            borderRadius: 8, padding: '10px 24px', fontSize: 14,
            fontWeight: 700, cursor: 'pointer',
          }}
        >
          Ricarica pagina
        </button>
      </div>
    )
  }
}

// â”€â”€ Barra stato macchina globale â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€â”€
// Striscia di 4px in cima al contenuto principale, sempre visibile.
// Verde = in lavorazione Â· Giallo = JOG Â· Rosso pulse = FERMA/allarme Â· Grigio = sconosciuto
function GlobalStatusBar() {
  const [stato, setStato] = useState(null)

  useEffect(() => {
    const onUpdate = (e) => {
      const d = e.detail || {}
      if (d.backend_down) {
        setStato('backend_down')
      } else if (d.log_stale || d.stato_macchina === -1) {
        // -1 = tick saltato lato server (log macchina o share non leggibili)
        setStato('stale')
      } else if (d.stato_macchina !== undefined) {
        if ([1, 3].includes(d.stato_macchina)) setStato('attiva')
        else if (d.stato_macchina === 2)        setStato('jog')
        else                                    setStato('ferma')
      }
    }
    // Fetch iniziale
    fetch('/api/macchina-live/stato')
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d) return
        if (d.log_stale) setStato('stale')
        else if ([1, 3].includes(d.stato_programma)) setStato('attiva')
        else if (d.stato_programma === 2)             setStato('jog')
        else                                          setStato('ferma')
      }).catch(() => {})

    window.addEventListener('dmgdesk:stati-aggiornati', onUpdate)
    return () => window.removeEventListener('dmgdesk:stati-aggiornati', onUpdate)
  }, [])

  const cfg = {
    attiva: { color: '#22c55e', label: 'IN LAVORAZIONE', animate: false },
    jog:    { color: '#3b82f6', label: 'JOG',            animate: false },
    ferma:  { color: '#ef4444', label: 'FERMA',          animate: true  },
    stale:  { color: '#ef4444', label: 'CONNESSIONE PERSA', animate: true },
    backend_down: { color: '#7c3aed', label: 'BACKEND NON RAGGIUNGIBILE', animate: true },
  }[stato] || { color: '#475569', label: '', animate: false }

  // Stati critici: oltre alla striscia colorata serve un testo esplicito,
  // 4px di colore non bastano per un operatore a distanza braccio.
  const critico = stato === 'backend_down' || stato === 'stale'

  return (
    <div style={{ flexShrink: 0, position: 'relative', zIndex: 10 }}>
      <div style={{
        height: 4,
        background: cfg.color,
        transition: 'background 0.4s ease',
        animation: cfg.animate ? 'statusPulse 2s ease-in-out infinite' : 'none',
      }} />
      {critico && (
        <div style={{
          background: cfg.color, color: '#fff', textAlign: 'center',
          fontSize: 13, fontWeight: 800, letterSpacing: '0.08em',
          padding: '4px 0',
          animation: 'statusPulse 2s ease-in-out infinite',
        }}>
          ⚠ {cfg.label} — DATI NON AGGIORNATI
        </div>
      )}
      <style>{`
        @keyframes statusPulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.45; }
        }
      `}</style>
    </div>
  )
}

// Polling globale — gira solo quando il tab è visibile.
// Su un client multi-tab (es. ufficio + officina), N tab nascosti continuavano
// a polleggiare ogni 5s aumentando il carico server senza valore aggiunto.
// Ora i tab in background sono silenziati; tornando in primo piano fanno una
// catch-up immediata.
function GlobalPoller() {
  useEffect(() => {
    let isRunning = false
    // Tick falliti consecutivi: dopo BACKEND_DOWN_SOGLIA (~15s) emette un
    // evento dedicato — senza, la UI resterebbe congelata sull'ultimo stato
    // buono mostrandolo come "live" a tempo indeterminato (audit 2026-07-02).
    let failCount = 0
    const BACKEND_DOWN_SOGLIA = 3
    const tick = async () => {
      if (document.hidden) return        // tab nascosto → skip
      if (isRunning) return
      isRunning = true
      try {
        const r = await fetch('/api/macchina-live/tick')
        if (!r.ok) throw new Error(`HTTP ${r.status}`)
        const d = await r.json()
        failCount = 0
        window.dispatchEvent(new CustomEvent('dmgdesk:stati-aggiornati', { detail: d }))
      } catch {
        failCount += 1
        if (failCount >= BACKEND_DOWN_SOGLIA) {
          window.dispatchEvent(new CustomEvent('dmgdesk:stati-aggiornati', {
            detail: { backend_down: true, stato_macchina: -1 },
          }))
        }
      }
      finally { isRunning = false }
    }
    tick()
    const t = setInterval(tick, 5000)
    // Catch-up immediato quando il tab torna visibile
    const onVis = () => { if (!document.hidden) tick() }
    document.addEventListener('visibilitychange', onVis)
    return () => {
      clearInterval(t)
      document.removeEventListener('visibilitychange', onVis)
    }
  }, [])
  return null
}

const FULL_PAGES = ['/home', '/coda', '/analisi-nc', '/macchina', '/progetti', '/report', '/cam-tracker', '/analytics', '/alert-utensili', '/turno', '/schermo']

// A livello modulo, NON dentro MainContent: ridefinito a ogni render creava
// una nuova identità di componente → React smontava e rimontava l'intera
// pagina a ogni navigazione (doppio load(), interval ricreati, flash UI).
const Wrap = ({ children }) => <ErrorBoundary>{children}</ErrorBoundary>

function MainContent() {
  const loc = useLocation()
  const isFull = FULL_PAGES.some(p => loc.pathname.startsWith(p))
  return (
    <main style={{ flex:1, overflow:'auto', background:'var(--bg-base)',
      padding: 0, display:'flex', flexDirection:'column' }}>
      <GlobalStatusBar />
      <div style={{ flex:1, overflow:'auto', padding: isFull ? 0 : '20px 24px' }}>
      <Routes>
        <Route path="/"               element={<Navigate to="/home" replace />} />
        <Route path="/home"           element={<Wrap><Home /></Wrap>} />
        <Route path="/coda"           element={<Wrap><CodaLavorazione /></Wrap>} />
        <Route path="/macchina"       element={<Wrap><Macchina /></Wrap>} />
        <Route path="/scaffale"       element={<Wrap><Scaffale /></Wrap>} />
        <Route path="/smontati"       element={<Wrap><Smontati /></Wrap>} />
        <Route path="/holder-bussole" element={<Wrap><HolderBussole /></Wrap>} />
        <Route path="/generatore"     element={<Wrap><Generatore /></Wrap>} />
        <Route path="/analisi-nc"     element={<Wrap><AnalisiNC /></Wrap>} />
        <Route path="/invia"          element={<Wrap><InvioMacchina /></Wrap>} />
        <Route path="/report"         element={<Wrap><Report /></Wrap>} />
        <Route path="/magazzino"      element={<Wrap><Smontati /></Wrap>} />
        <Route path="/progetti"       element={<Wrap><Progetti /></Wrap>} />
        <Route path="/rendiconto/:projectId" element={<Wrap><RendicontoProgetto /></Wrap>} />
        <Route path="/cam-tracker"  element={<Wrap><CamTracker /></Wrap>} />
        <Route path="/analytics"    element={<Wrap><AnalyticsCommesse /></Wrap>} />
        <Route path="/alert-utensili" element={<Wrap><AlertUtensili /></Wrap>} />
        <Route path="/turno"          element={<Wrap><RiepilogoTurno /></Wrap>} />
        <Route path="/step-analyzer"  element={<Wrap><StepAnalyzer /></Wrap>} />
        <Route path="/schermo"        element={<Wrap><SchermoLive /></Wrap>} />
        <Route path="/operatori"      element={<Wrap><GestioneOperatori /></Wrap>} />
      </Routes>
      </div>
    </main>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <AuthGate>
        <BrowserRouter>
          <GlobalPoller />
          <div style={{ display:'flex', height:'100vh', overflow:'hidden', background:'var(--bg-base)' }}>
            <Sidebar />
            <MainContent />
          </div>
        </BrowserRouter>
      </AuthGate>
    </ErrorBoundary>
  )
}

