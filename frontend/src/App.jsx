import { BrowserRouter, Routes, Route, Navigate, useLocation } from 'react-router-dom'
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

const FULL_PAGES = ['/home', '/coda', '/analisi-nc', '/macchina', '/progetti']

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
        <Route path="/magazzino"      element={<Smontati />} />
        <Route path="/progetti"       element={<Progetti />} />
      </Routes>
    </main>
  )
}

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display:'flex', height:'100vh', overflow:'hidden', background:'var(--bg-base)' }}>
        <Sidebar />
        <MainContent />
      </div>
    </BrowserRouter>
  )
}
