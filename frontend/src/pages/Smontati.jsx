// pages/Smontati.jsx
import { useState, useEffect } from 'react'
import { api } from '../api/client'
import { Loader, EmptyState, ErrorBanner, SuccessBanner, StatCard, SectionHeader } from '../components/UI'

export default function Smontati() {
  const [lista, setLista]       = useState([])
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [success, setSuccess]   = useState(null)
  const [showAdd, setShowAdd]   = useState(false)
  const [form, setForm]         = useState({ alias_utensile: '', provenienza: 'Manuale', note: '' })
  const [busy, setBusy]         = useState(false)
  const [search, setSearch]     = useState('')

  const load = async () => {
    try { setLoading(true); setLista(await api.getSmontati()) }
    catch (e) { setError(e.message) } finally { setLoading(false) }
  }
  useEffect(() => { load() }, [])

  const handleAggiungi = async () => {
    if (!form.alias_utensile.trim()) return
    try {
      setBusy(true)
      await api.aggiungiSmontato(form)
      setSuccess(`Aggiunto: ${form.alias_utensile}`)
      setShowAdd(false); setForm({ alias_utensile: '', provenienza: 'Manuale', note: '' }); load()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const handleElimina = async (id, alias) => {
    if (!confirm(`Eliminare "${alias}"?`)) return
    try {
      await api.eliminaSmontato(id)
      setSuccess(`Eliminato: ${alias}`); load()
    } catch (e) { setError(e.message) }
  }

  const filtered = lista.filter(u =>
    u.alias_utensile.toLowerCase().includes(search.toLowerCase()) ||
    u.provenienza?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader title="Smontati" subtitle="Archivio utensili smontati dal carosello"
        action={<button className="btn btn-primary" onClick={() => setShowAdd(true)} style={{ fontSize: 12 }}>+ Aggiungi</button>} />
      <div style={{ display: 'flex', gap: 12 }}>
        <StatCard label="Totale Smontati" value={lista.length} color="var(--purple)" />
        <StatCard label="Da Macchina" value={lista.filter(u => u.provenienza?.includes('Posizione') || u.provenienza === 'Macchina').length} color="var(--text-secondary)" />
      </div>
      <ErrorBanner message={error} onClose={() => setError(null)} />
      <SuccessBanner message={success} onClose={() => setSuccess(null)} />
      <input className="input" placeholder="Cerca per alias o provenienza..." value={search} onChange={e => setSearch(e.target.value)} style={{ maxWidth: 320 }} />
      <div className="card" style={{ flex: 1, overflow: 'auto' }}>
        {loading ? <Loader /> : filtered.length === 0 ? (
          <EmptyState icon="🔧" title="Archivio vuoto" subtitle="Nessun utensile smontato registrato" />
        ) : (
          <table className="table">
            <thead><tr><th>ID</th><th>Alias</th><th>Data Smontaggio</th><th>Provenienza</th><th>Note</th><th style={{ textAlign: 'right' }}>Azioni</th></tr></thead>
            <tbody>
              {filtered.map(u => (
                <tr key={u.id}>
                  <td><span className="mono" style={{ color: 'var(--text-dim)', fontSize: 11 }}>{u.id.slice(0,8)}</span></td>
                  <td><span className="mono" style={{ fontWeight: 600 }}>{u.alias_utensile}</span></td>
                  <td><span className="mono" style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{u.data_smontaggio?.slice(0,10)}</span></td>
                  <td><span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{u.provenienza}</span></td>
                  <td><span style={{ fontSize: 12, color: 'var(--text-dim)' }}>{u.note || '—'}</span></td>
                  <td style={{ textAlign: 'right' }}>
                    <button className="btn btn-danger" style={{ fontSize: 11, padding: '4px 10px' }} onClick={() => handleElimina(u.id, u.alias_utensile)}>Elimina</button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
      {showAdd && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card fade-in" style={{ padding: 24, width: 400, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>Aggiungi Utensile Smontato</h3>
            {['alias_utensile', 'provenienza', 'note'].map(field => (
              <div key={field}>
                <label style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 4, textTransform: 'uppercase' }}>{field.replace('_', ' ')}</label>
                <input className="input" value={form[field]} onChange={e => setForm(f => ({ ...f, [field]: e.target.value }))} placeholder={field === 'alias_utensile' ? 'es. FF12R2-F80H4' : field === 'provenienza' ? 'es. Macchina, Manuale...' : 'Opzionale'} />
              </div>
            ))}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
              <button className="btn btn-ghost" onClick={() => setShowAdd(false)}>Annulla</button>
              <button className="btn btn-primary" onClick={handleAggiungi} disabled={busy || !form.alias_utensile.trim()}>{busy ? 'Salvataggio...' : 'Aggiungi'}</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}
