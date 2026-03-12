// pages/Scaffale.jsx
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Loader, EmptyState, ErrorBanner, SuccessBanner, StatCard, SectionHeader } from '../components/UI'

export default function Scaffale() {
  const [utensili, setUtensili] = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [success, setSuccess]   = useState(null)
  const [spostaItem, setSpostaItem] = useState(null)
  const [nuovaPos, setNuovaPos]     = useState('')
  const [busy, setBusy]             = useState(false)

  const load = async () => {
    try { setLoading(true); setError(null); setUtensili(await api.getScaffale()) }
    catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const handleSposta = async () => {
    try {
      setBusy(true)
      await api.spostaInMacchina({ posizione: spostaItem.posizione, nuova_posizione_macchina: parseInt(nuovaPos) })
      setSuccess(`${spostaItem.alias} spostato in macchina pos. ${nuovaPos}`)
      setSpostaItem(null); setNuovaPos(''); load()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  return (
    <div className="fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader title="Scaffale" subtitle="Utensili assemblati non in macchina"
        action={<button className="btn btn-ghost" onClick={load} style={{ fontSize: 12 }}>↻ Aggiorna</button>} />
      <div style={{ display: 'flex', gap: 12 }}>
        <StatCard label="A Scaffale" value={utensili.length} color="var(--amber)" />
        <StatCard label="Frese Fin." value={utensili.filter(u => u.alias.startsWith('FF')).length} color="var(--green)" />
      </div>
      <ErrorBanner message={error} onClose={() => setError(null)} />
      <SuccessBanner message={success} onClose={() => setSuccess(null)} />
      <div className="card" style={{ flex: 1, overflow: 'auto' }}>
        {loading ? <Loader /> : utensili.length === 0 ? (
          <EmptyState icon="📦" title="Scaffale vuoto" subtitle="Nessun utensile assemblato presente" />
        ) : (
          <table className="table">
            <thead><tr><th>Pos.</th><th>Alias</th><th>Stato</th><th style={{ textAlign: 'right' }}>Azioni</th></tr></thead>
            <tbody>
              {utensili.map(u => (
                <tr key={u.posizione}>
                  <td><span className="mono" style={{ color: 'var(--amber)' }}>{String(u.posizione).padStart(3,'0')}</span></td>
                  <td><span className="mono">{u.alias}</span></td>
                  <td><span className="badge badge-amber">SCAFFALE</span></td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn btn-primary" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => setSpostaItem(u)}>
                      → Macchina
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {spostaItem && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card fade-in" style={{ padding: 24, width: 360, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>Sposta in Macchina</h3>
            <p className="mono" style={{ color: 'var(--cyan)' }}>{spostaItem.alias}</p>
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 6 }}>POSIZIONE DESTINAZIONE (1-120)</label>
              <input className="input" type="number" min="1" max="120" placeholder="es. 45" value={nuovaPos} onChange={e => setNuovaPos(e.target.value)} />
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => { setSpostaItem(null); setNuovaPos('') }}>Annulla</button>
              <button className="btn btn-primary" onClick={handleSposta} disabled={busy || !nuovaPos}>{busy ? 'Spostando...' : 'Conferma'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
