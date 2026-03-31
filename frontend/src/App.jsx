import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
import { useEffect } from 'react'
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

// Polling globale — gira sempre, indipendentemente dalla pagina aperta
function GlobalPoller() {
  useEffect(() => {
    let isRunning = false  // protezione: evita tick sovrapposti se backend lento
    const tick = async () => {
      if (isRunning) return  // tick precedente ancora in corso — salta
      isRunning = true
      try {
        const r = await fetch('/api/macchina-live/aggiorna-stati-da-log', { method: 'POST' })
        if (!r.ok) return
        const d = await r.json()
        // Notifica le pagine interessate
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

const FULL_PAGES = ['/home', '/coda', '/analisi-nc', '/macchina', '/progetti', '/report']

function MainContent() {
  const loc = useLocation()
  const isFull = FULL_PAGES.some(p => loc.pathname.startsWith(p))
  return (
    <main style={{ flex:1, overflow:'auto', background:'var(--bg-base)',
      padding: isFull ? 0 : '20px 24px', display:'flex', flexDirection:'column' }}>
      <Routes>
        <Route path="/"               element={<Navigate to="/home" replace />} />
        <Route path="/home"           element={<Home />} />
        <Route path="/coda"           element={<CodaLavorazione />} />
        <Route path="/macchina"       element={<Macchina />} />
        <Route path="/scaffale"       element={<Scaffale />} />
        <Route path="/smontati"       element={<Smontati />} />
        <Route path="/holder-bussole" element={<HolderBussole />} />
        <Route path="/generatore"     element={<Generatore />} />
        <Route path="/analisi-nc"     element={<AnalisiNC />} />
        <Route path="/invia"          element={<InvioMacchina />} />
        <Route path="/report"         element={<Report />} />
        <Route path="/magazzino"      element={<Smontati />} />
        <Route path="/progetti"       element={<Progetti />} />
      </Routes>
    </main>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <GlobalPoller />
      <div style={{ display:'flex', height:'100vh', overflow:'hidden', background:'var(--bg-base)' }}>
        <Sidebar />
        <MainContent />
      </div>
    </BrowserRouter>
  )
}
