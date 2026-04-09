import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect, Component } from 'react'
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
import ChatAssistente from './components/ChatAssistente'

// ── Error Boundary globale ──────────────────────────────────────────────────
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
        <div style={{ fontSize: 32 }}>⚠</div>
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

// Polling globale — gira sempre, indipendentemente dalla pagina aperta
function GlobalPoller() {
  useEffect(() => {
    let isRunning = false
    const tick = async () => {
      if (isRunning) return
      isRunning = true
      try {
        // SOLO LETTURA — legge il risultato dell'ultimo ciclo del poller interno.
        // Nessuna scrittura dal frontend — elimina race condition con N client aperti.
        const r = await fetch('/api/macchina-live/tick')
        if (!r.ok) return
        const d = await r.json()
        window.dispatchEvent(new CustomEvent('dmgdesk:stati-aggiornati', { detail: d }))
      } catch {}
      finally { isRunning = false }
    }
    tick()
    const t = setInterval(tick, 5000)
    return () => clearInterval(t)
  }, [])
  return null
}

const FULL_PAGES = ['/home', '/coda', '/analisi-nc', '/macchina', '/progetti', '/report', '/cam-tracker', '/analytics', '/alert-utensili', '/turno']

function MainContent() {
  const loc = useLocation()
  const isFull = FULL_PAGES.some(p => loc.pathname.startsWith(p))
  const Wrap = ({ children }) => <ErrorBoundary>{children}</ErrorBoundary>
  return (
    <main style={{ flex:1, overflow:'auto', background:'var(--bg-base)',
      padding: isFull ? 0 : '20px 24px', display:'flex', flexDirection:'column' }}>
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
      </Routes>
    </main>
  )
}

export default function App() {
  return (
    <ErrorBoundary>
      <BrowserRouter>
        <GlobalPoller />
        <div style={{ display:'flex', height:'100vh', overflow:'hidden', background:'var(--bg-base)' }}>
          <Sidebar />
          <MainContent />
        </div>
        <ChatAssistente />
      </BrowserRouter>
    </ErrorBoundary>
  )
}
