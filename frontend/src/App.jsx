// App.jsx — DMG Desk
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar           from './components/Sidebar'
import CodaLavorazione   from './pages/CodaLavorazione'
import Macchina          from './pages/Macchina'
import Scaffale          from './pages/Scaffale'
import Smontati          from './pages/Smontati'
import HolderBussole     from './pages/HolderBussole'
import Generatore        from './pages/Generatore'
import AnalisiNC         from './pages/AnalisiNC'
import InvioMacchina     from './pages/InvioMacchina'

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display:'flex', height:'100vh', overflow:'hidden', background:'var(--bg-base)' }}>
        <Sidebar />
        <main style={{
          flex: 1,
          overflow: 'auto',
          padding: '20px 24px',
          background: 'var(--bg-base)',
        }}>
          <Routes>
            <Route path="/"              element={<Navigate to="/coda" replace />} />
            <Route path="/coda"          element={<CodaLavorazione />} />
            <Route path="/macchina"      element={<Macchina />} />
            <Route path="/scaffale"      element={<Scaffale />} />
            <Route path="/smontati"      element={<Smontati />} />
            <Route path="/holder-bussole" element={<HolderBussole />} />
            <Route path="/generatore"    element={<Generatore />} />
            <Route path="/analisi-nc"    element={<AnalisiNC />} />
            <Route path="/invia"          element={<InvioMacchina />} />
            <Route path="/magazzino"     element={<Smontati />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
