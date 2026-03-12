// pages/AnalisiNC.jsx — Upload e analisi file NC
import { useState, useRef } from 'react'
import { api } from '../api/client'
import { Loader, ErrorBanner, SuccessBanner, StatCard, SectionHeader } from '../components/UI'

export default function AnalisiNC() {
  const [file, setFile]         = useState(null)
  const [result, setResult]     = useState(null)
  const [loading, setLoading]   = useState(false)
  const [error, setError]       = useState(null)
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()

  const handleFile = (f) => {
    if (!f) return
    const ext = f.name.split('.').pop().toLowerCase()
    if (!['mpf','nc','spf'].includes(ext)) {
      setError('Formato non supportato. Carica un file .MPF, .NC o .SPF')
      return
    }
    setFile(f); setResult(null); setError(null)
  }

  const analizza = async () => {
    if (!file) return
    try {
      setLoading(true); setError(null); setResult(null)
      const data = await api.analizzaNC(file)
      setResult(data)
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  const onDrop = (e) => {
    e.preventDefault(); setDragging(false)
    handleFile(e.dataTransfer.files[0])
  }

  return (
    <div className="fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader title="Analisi NC" subtitle="Confronta file programma CNC con il database macchina" />

      <ErrorBanner message={error} onClose={() => setError(null)} />

      {/* Drop zone */}
      <div
        onClick={() => inputRef.current.click()}
        onDragOver={e => { e.preventDefault(); setDragging(true) }}
        onDragLeave={() => setDragging(false)}
        onDrop={onDrop}
        style={{
          border: `2px dashed ${dragging ? 'var(--cyan)' : file ? 'var(--green)' : 'var(--border-bright)'}`,
          borderRadius: 'var(--radius)',
          padding: '32px 24px',
          textAlign: 'center',
          cursor: 'pointer',
          background: dragging ? 'var(--cyan-glow)' : file ? 'rgba(0,255,136,0.04)' : 'var(--bg-card)',
          transition: 'all var(--t-med)',
        }}
      >
        <input ref={inputRef} type="file" accept=".mpf,.nc,.spf" style={{ display: 'none' }} onChange={e => handleFile(e.target.files[0])} />
        <div style={{ fontSize: 32, marginBottom: 8 }}>{file ? '✅' : '📄'}</div>
        {file ? (
          <>
            <div style={{ fontFamily: 'var(--font-mono)', fontSize: 14, color: 'var(--green)', fontWeight: 700 }}>{file.name}</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>{(file.size / 1024).toFixed(1)} KB — clicca per cambiare file</div>
          </>
        ) : (
          <>
            <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>Trascina qui il file NC</div>
            <div style={{ fontSize: 12, color: 'var(--text-dim)', marginTop: 4 }}>oppure clicca per sfogliare — .MPF .NC .SPF</div>
          </>
        )}
      </div>

      <button className="btn btn-primary" onClick={analizza} disabled={!file || loading} style={{ alignSelf: 'flex-start', padding: '10px 24px' }}>
        {loading ? <><div className="spinner" style={{ width: 14, height: 14, borderWidth: 2 }} /> Analisi in corso...</> : '▶ Analizza File'}
      </button>

      {/* Risultati */}
      {result && (
        <div className="fade-in" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>

          {/* Stats */}
          <div style={{ display: 'flex', gap: 12 }}>
            <StatCard label="Utensili nel file" value={result.totale_file}      color="var(--cyan)" />
            <StatCard label="Presenti"          value={result.presenti_in_macchina.length} color="var(--green)" />
            <StatCard label="Mancanti"          value={result.totale_mancanti}  color={result.totale_mancanti > 0 ? 'var(--red)' : 'var(--text-secondary)'} />
          </div>

          {/* Banner mancanti */}
          {result.totale_mancanti > 0 && (
            <div style={{
              background: 'rgba(255,68,85,0.08)', border: '1px solid rgba(255,68,85,0.3)',
              borderRadius: 'var(--radius-sm)', padding: '12px 16px',
            }}>
              <div style={{ fontSize: 12, fontWeight: 700, color: 'var(--red)', fontFamily: 'var(--font-mono)', marginBottom: 8, letterSpacing: '0.05em' }}>
                ⚠ UTENSILI MANCANTI IN MACCHINA
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                {result.mancanti.map(a => (
                  <span key={a} className="mono" style={{ padding: '3px 10px', background: 'rgba(255,68,85,0.15)', borderRadius: 3, fontSize: 12, color: 'var(--red)' }}>{a}</span>
                ))}
              </div>
            </div>
          )}

          {/* Tabella completa */}
          <div className="card" style={{ flex: 1, overflow: 'auto' }}>
            <div style={{ padding: '12px 16px', borderBottom: '1px solid var(--border)', fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em', textTransform: 'uppercase' }}>
              Dettaglio Utensili — {file?.name}
            </div>
            <table className="table">
              <thead>
                <tr>
                  <th>Riga</th>
                  <th>Alias</th>
                  <th>Stato</th>
                  <th>Testo NC</th>
                </tr>
              </thead>
              <tbody>
                {result.utensili_nel_file.map((u, i) => {
                  const presente = result.presenti_in_macchina.includes(u.alias)
                  return (
                    <tr key={i}>
                      <td><span className="mono" style={{ color: 'var(--text-dim)', fontSize: 12 }}>{u.riga}</span></td>
                      <td><span className="mono" style={{ fontWeight: 600 }}>{u.alias}</span></td>
                      <td>
                        <span className={`badge ${presente ? 'badge-green' : 'badge-red'}`}>
                          {presente ? '✓ Presente' : '✗ Mancante'}
                        </span>
                      </td>
                      <td><span className="mono" style={{ fontSize: 11, color: 'var(--text-dim)' }}>{u.testo_riga}</span></td>
                    </tr>
                  )
                })}
              </tbody>
            </table>
          </div>
        </div>
      )}
    </div>
  )
}
