// pages/HolderBussole.jsx
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Loader, EmptyState, ErrorBanner, SuccessBanner, StatCard, SectionHeader } from '../components/UI'

export default function HolderBussole() {
  const [tab, setTab]           = useState('holder')
  const [holder, setHolder]     = useState([])
  const [bussole, setBussole]   = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [success, setSuccess]   = useState(null)

  const load = async () => {
    try {
      setLoading(true)
      const [h, b] = await Promise.all([api.getHolder(), api.getBussole()])
      setHolder(h); setBussole(b)
    } catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const handleEliminaHolder = async (alias) => {
    if (!confirm(`Eliminare holder "${alias}"?`)) return
    try { await api.eliminaHolder(alias); setSuccess(`Holder eliminato: ${alias}`); load() }
    catch (e) { setError(e.message) }
  }

  const handleEliminaBussola = async (codice) => {
    if (!confirm(`Eliminare bussola "${codice}"?`)) return
    try { await api.eliminaBussola(codice); setSuccess(`Bussola eliminata: ${codice}`); load() }
    catch (e) { setError(e.message) }
  }

  return (
    <div className="fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader title="Holder & Bussole" subtitle="Inventario porta-utensili e bussole idraulico"
        action={<button className="btn btn-ghost" onClick={load} style={{ fontSize: 12 }}>↻ Aggiorna</button>} />

      <div style={{ display: 'flex', gap: 12 }}>
        <StatCard label="Holder Smontati" value={holder.length} color="var(--navy-accent)" />
        <StatCard label="Tipi Bussole" value={bussole.length} color="var(--amber)" />
        <StatCard label="Tot. Bussole" value={bussole.reduce((s, b) => s + b.quantita, 0)} color="var(--green)" />
      </div>

      <ErrorBanner message={error} onClose={() => setError(null)} />
      <SuccessBanner message={success} onClose={() => setSuccess(null)} />

      {/* Tab switch */}
      <div style={{ display: 'flex', gap: 0, borderBottom: '1px solid var(--border)' }}>
        {['holder', 'bussole'].map(t => (
          <button key={t} onClick={() => setTab(t)} style={{
            padding: '8px 20px', border: 'none', background: 'none', cursor: 'pointer',
            fontFamily: 'var(--font-display)', fontSize: 13, fontWeight: 600,
            color: tab === t ? 'var(--navy-700)' : 'var(--text-secondary)',
            borderBottom: `2px solid ${tab === t ? 'var(--navy-700)' : 'transparent'}`,
            transition: 'all var(--t-fast)', textTransform: 'capitalize',
          }}>
            {t === 'holder' ? `Holder (${holder.length})` : `Bussole (${bussole.length})`}
          </button>
        ))}
      </div>

      <div className="card" style={{ flex: 1, overflow: 'auto' }}>
        {loading ? <Loader /> : tab === 'holder' ? (
          holder.length === 0 ? <EmptyState icon="🔩" title="Nessun holder" subtitle="Archivio holder smontati vuoto" /> : (
            <table className="table">
              <thead><tr><th>Alias Holder</th><th>Quantità</th><th>Data Smontaggio</th><th>Note</th><th style={{ textAlign: 'right' }}>Azioni</th></tr></thead>
              <tbody>
                {holder.map(h => (
                  <tr key={h.alias_holder}>
                    <td><span className="mono" style={{ fontWeight: 600 }}>{h.alias_holder}</span></td>
                    <td>
                      <span className={`badge ${h.quantita > 2 ? 'badge-green' : h.quantita > 0 ? 'badge-amber' : 'badge-red'}`}>
                        ×{h.quantita}
                      </span>
                    </td>
                    <td><span className="mono" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{h.data_smontaggio?.slice(0,10)}</span></td>
                    <td><span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{h.note || '—'}</span></td>
                    <td style={{ textAlign: 'right' }}>
                      <button className="btn btn-danger" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => handleEliminaHolder(h.alias_holder)}>Elimina</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        ) : (
          bussole.length === 0 ? <EmptyState icon="⭕" title="Nessuna bussola" subtitle="Inventario bussole idraulico vuoto" /> : (
            <table className="table">
              <thead><tr><th>Codice</th><th>Diametro</th><th>Quantità</th><th>Data Acquisizione</th><th>Note</th><th style={{ textAlign: 'right' }}>Azioni</th></tr></thead>
              <tbody>
                {bussole.map(b => (
                  <tr key={b.codice_bussola}>
                    <td><span className="mono" style={{ fontWeight: 600, color: 'var(--amber)' }}>{b.codice_bussola}</span></td>
                    <td><span className="mono">{b.diametro}</span></td>
                    <td>
                      <span className={`badge ${b.quantita > 2 ? 'badge-green' : b.quantita > 0 ? 'badge-amber' : 'badge-red'}`}>
                        ×{b.quantita}
                      </span>
                    </td>
                    <td><span className="mono" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{b.data_acquisizione?.slice(0,10) || '—'}</span></td>
                    <td><span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{b.note || '—'}</span></td>
                    <td style={{ textAlign: 'right' }}>
                      <button className="btn btn-danger" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => handleEliminaBussola(b.codice_bussola)}>Elimina</button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          )
        )}
      </div>
    </div>
  )
}
