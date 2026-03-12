// pages/Scaffale.jsx — Utensili assemblati a scaffale
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Loader, EmptyState, ErrorBanner, SuccessBanner, StatCard, SectionHeader } from '../components/UI'

export default function Scaffale() {
  const [utensili, setUtensili]       = useState([])
  const [loading, setLoading]         = useState(true)
  const [error, setError]             = useState(null)
  const [success, setSuccess]         = useState(null)
  const [spostaItem, setSpostaItem]   = useState(null)   // { alias, posizione }
  const [nuovaPos, setNuovaPos]       = useState('')
  const [busy, setBusy]               = useState(false)
  const [search, setSearch]           = useState('')

  const load = async () => {
    try {
      setLoading(true); setError(null)
      setUtensili(await api.getScaffale())
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const handleSposta = async () => {
    if (!spostaItem || !nuovaPos) return
    try {
      setBusy(true); setError(null)
      // lookup per alias (nuovo API: body.alias, non body.posizione)
      await api.spostaInMacchina({
        alias: spostaItem.alias,
        nuova_posizione_macchina: parseInt(nuovaPos),
      })
      setSuccess(`${spostaItem.alias} spostato in macchina pos. ${nuovaPos}`)
      setSpostaItem(null); setNuovaPos(''); load()
    } catch (e) { setError(e.message) }
    finally { setBusy(false) }
  }

  const filtered = utensili.filter(u =>
    u.alias.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader
        title="Scaffale"
        subtitle="Utensili assemblati (con holder) non ancora in macchina"
        action={<button className="btn btn-ghost" onClick={load} style={{ fontSize: 12 }}>↻ Aggiorna</button>}
      />

      {/* Stats */}
      <div style={{ display: 'flex', gap: 12 }}>
        <StatCard label="A Scaffale"   value={utensili.length}  color="var(--amber)" />
        <StatCard label="Frese Fin."   value={utensili.filter(u => u.alias.startsWith('FF')).length} color="var(--green)" />
        <StatCard label="Frese Sgr."   value={utensili.filter(u => u.alias.startsWith('FS')).length} color="var(--cyan)" />
      </div>

      <ErrorBanner   message={error}   onClose={() => setError(null)} />
      <SuccessBanner message={success} onClose={() => setSuccess(null)} />

      {/* Ricerca */}
      <input
        className="input"
        placeholder="Cerca per alias..."
        value={search}
        onChange={e => setSearch(e.target.value)}
        style={{ maxWidth: 340 }}
      />

      {/* Tabella */}
      <div className="card" style={{ flex: 1, overflow: 'auto' }}>
        {loading ? <Loader /> : filtered.length === 0 ? (
          <EmptyState icon="📦" title="Scaffale vuoto" subtitle="Nessun utensile assemblato presente" />
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
                <tr key={u.alias}>
                  <td>
                    <span className="mono" style={{ color: 'var(--amber)', fontWeight: 700, fontSize: 13 }}>
                      {u.posizione != null ? String(u.posizione).padStart(3, '0') : '—'}
                    </span>
                  </td>
                  <td>
                    <span className="mono" style={{ fontSize: 13 }}>{u.alias}</span>
                  </td>
                  <td>
                    <span className={`badge ${
                      u.alias.startsWith('FF') ? 'badge-green' :
                      u.alias.startsWith('FS') ? 'badge-amber' :
                      'badge-cyan'
                    }`}>
                      {u.alias.startsWith('FF') ? 'Finitura' :
                       u.alias.startsWith('FS') ? 'Sgrossatura' :
                       u.alias.startsWith('FP') ? 'Prefinitura' :
                       u.alias.startsWith('FR') ? 'Riprese' : '—'}
                    </span>
                  </td>
                  <td><span className="badge badge-amber">SCAFFALE</span></td>
                  <td style={{ textAlign: 'right' }}>
                    <button
                      className="btn btn-primary"
                      style={{ fontSize: 11, padding: '4px 10px' }}
                      onClick={() => { setSpostaItem(u); setNuovaPos('') }}
                    >
                      → Macchina
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* Modal sposta in macchina */}
      {spostaItem && (
        <div style={{
          position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100,
        }}>
          <div className="card fade-in" style={{ padding: 24, width: 380, display: 'flex', flexDirection: 'column', gap: 16 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>Sposta in Macchina</h3>
            <p className="mono" style={{ color: 'var(--cyan)', fontSize: 13 }}>{spostaItem.alias}</p>
            <div>
              <label style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 6 }}>
                POSIZIONE DESTINAZIONE (1-120)
              </label>
              <input
                className="input"
                type="number" min="1" max="120"
                placeholder="es. 45"
                value={nuovaPos}
                onChange={e => setNuovaPos(e.target.value)}
              />
            </div>
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button className="btn btn-ghost" onClick={() => { setSpostaItem(null); setNuovaPos('') }}>
                Annulla
              </button>
              <button className="btn btn-primary" onClick={handleSposta} disabled={busy || !nuovaPos}>
                {busy ? 'Spostando...' : 'Conferma'}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
