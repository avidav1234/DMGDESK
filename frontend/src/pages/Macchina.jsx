// pages/Macchina.jsx — Tab In Macchina (carosello CNC)
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Loader, EmptyState, ErrorBanner, SuccessBanner, StatCard, SectionHeader } from '../components/UI'

export default function Macchina() {
  const [utensili, setUtensili]     = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)
  const [success, setSuccess]       = useState(null)
  const [smontaPos, setSmontaPos]   = useState(null)
  const [noteSmonta, setNoteSmonta] = useState('')
  const [busy, setBusy]             = useState(false)
  const [search, setSearch]         = useState('')

  const load = async () => {
    try {
      setLoading(true); setError(null)
      const data = await api.getMacchina()
      setUtensili(data)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => { load() }, [])

  const handleSmonta = async () => {
    try {
      setBusy(true); setError(null)
      await api.smontaUtensile(smontaPos, noteSmonta)
      setSuccess(`Utensile smontato dalla posizione ${smontaPos}`)
      setSmontaPos(null); setNoteSmonta('')
      load()
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  const filtered = utensili.filter(u =>
    u.alias.toLowerCase().includes(search.toLowerCase()) ||
    String(u.posizione).includes(search)
  )

  return (
    <div className="fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader
        title="In Macchina"
        subtitle="Utensili nel carosello CNC — DMG 160U"
        action={
          <button className="btn btn-ghost" onClick={load} style={{ fontSize: 12 }}>
            ↻ Aggiorna
          </button>
        }
      />

      {/* Stats */}
      <div style={{ display: 'flex', gap: 12 }}>
        <StatCard label="In Carosello"   value={utensili.length}           color="var(--cyan)" />
        <StatCard label="Frese Finitura" value={utensili.filter(u => u.alias.startsWith('FF')).length} color="var(--green)" />
        <StatCard label="Posizioni Libere" value={120 - utensili.length}   color="var(--text-secondary)" unit="/ 120" />
      </div>

      <ErrorBanner   message={error}   onClose={() => setError(null)} />
      <SuccessBanner message={success} onClose={() => setSuccess(null)} />

      {/* Ricerca */}
      <input
        className="input"
        placeholder="Cerca per alias o posizione..."
        value={search}
        onChange={e => setSearch(e.target.value)}
        style={{ maxWidth: 320 }}
      />

      {/* Tabella */}
      <div className="card" style={{ flex: 1, overflow: 'auto' }}>
        {loading ? <Loader /> : filtered.length === 0 ? (
          <EmptyState icon="⚙" title="Nessun utensile trovato" subtitle="Il carosello è vuoto o la ricerca non ha risultati" />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>Pos.</th>
                <th>Alias Utensile</th>
                <th>Tipo</th>
                <th>Stato</th>
                <th style={{ textAlign: 'right' }}>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(u => (
                <tr key={u.posizione}>
                  <td>
                    <span className="mono" style={{ color: 'var(--cyan)', fontWeight: 700, fontSize: 14 }}>
                      {String(u.posizione).padStart(3, '0')}
                    </span>
                  </td>
                  <td>
                    <span className="mono" style={{ color: 'var(--text-primary)', fontSize: 13 }}>{u.alias}</span>
                  </td>
                  <td>
                    <span className={`badge ${
                      u.alias.startsWith('FF') ? 'badge-green' :
                      u.alias.startsWith('FS') ? 'badge-amber' :
                      u.alias.startsWith('PM') || u.alias.startsWith('P')  ? 'badge-cyan' :
                      'badge-cyan'
                    }`}>
                      {u.alias.startsWith('FF') ? 'Finitura' :
                       u.alias.startsWith('FS') ? 'Sgrossatura' :
                       u.alias.startsWith('PM') ? 'Pettine' :
                       u.alias.startsWith('P')  ? 'Punta' : '—'}
                    </span>
                  </td>
                  <td><span className="badge badge-green">IN MACCHINA</span></td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      className="btn btn-danger"
                      style={{ fontSize: 11, padding: '4px 10px' }}
                      onClick={() => setSmontaPos(u.posizione)}
                    >
                      Smonta
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal smonta */}
      {smontaPos && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <div className="card fade-in" style={{ padding: 24, width: 380, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>Smonta Utensile — Pos. {smontaPos}</h3>
            <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
              {utensili.find(u => u.posizione === smontaPos)?.alias}
            </p>
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 6 }}>NOTE (opzionale)</label>
              <input className="input" placeholder="es. usura, cambio programma..." value={noteSmonta} onChange={e => setNoteSmonta(e.target.value)} />
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => { setSmontaPos(null); setNoteSmonta('') }}>Annulla</button>
              <button className="btn btn-danger" onClick={handleSmonta} disabled={busy}>
                {busy ? 'Smontaggio...' : 'Conferma Smontaggio'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
