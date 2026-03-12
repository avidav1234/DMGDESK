// App.jsx — Root con React Router
import { BrowserRouter, Routes, Route, Navigate } from 'react-router-dom'
import Sidebar from './components/Sidebar'
import Macchina     from './pages/Macchina'
import Scaffale     from './pages/Scaffale'
import Smontati     from './pages/Smontati'
import HolderBussole from './pages/HolderBussole'
import Generatore   from './pages/Generatore'
import AnalisiNC    from './pages/AnalisiNC'

export default function App() {
  return (
    <BrowserRouter>
      <div style={{ display: 'flex', height: '100vh', overflow: 'hidden' }}>
        <Sidebar />
        <main style={{
          flex: 1,
          overflow: 'auto',
          padding: '24px 28px',
          background: 'var(--bg-base)',
        }}>
          <Routes>
            <Route path="/"               element={<Navigate to="/macchina" replace />} />
            <Route path="/macchina"       element={<Macchina />} />
            <Route path="/scaffale"       element={<Scaffale />} />
            <Route path="/smontati"       element={<Smontati />} />
            <Route path="/holder-bussole" element={<HolderBussole />} />
            <Route path="/generatore"     element={<Generatore />} />
            <Route path="/analisi-nc"     element={<AnalisiNC />} />
          </Routes>
        </main>
      </div>
    </BrowserRouter>
  )
}
