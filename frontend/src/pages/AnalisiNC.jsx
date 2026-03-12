// pages/AnalisiNC.jsx — Analisi multi-file NC
import { useState, useRef, useCallback } from 'react'
import { api } from '../api/client'

export default function AnalisiNC() {
  const [entries, setEntries] = useState([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()
  const idRef = useRef(0)

  const addFiles = useCallback((files) => {
    const valid = Array.from(files).filter(f => /\.(mpf|nc|spf)$/i.test(f.name))
    if (!valid.length) return
    setEntries(prev => [...prev, ...valid.map(f => ({
      id: ++idRef.current, file: f, status: 'pending', result: null, error: null
    }))])
  }, [])

  const removeEntry = (id) => setEntries(prev => prev.filter(e => e.id !== id))
  const clearAll = () => setEntries([])

  const analyzeAll = async () => {
    const pending = entries.filter(e => e.status === 'pending' || e.status === 'error')
    for (const entry of pending) {
      setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: 'analyzing' } : e))
      try {
        const result = await api.analizzaNC(entry.file)
        setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: 'done', result } : e))
      } catch (err) {
        setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: 'error', error: err.message } : e))
      }
    }
  }

  const done        = entries.filter(e => e.status === 'done')
  const conMancanti = done.filter(e => (e.result?.totale_mancanti ?? 0) > 0)
  const allMancanti = [...new Set(done.flatMap(e => e.result?.mancanti ?? []))]
  const hasPending  = entries.some(e => e.status === 'pending' || e.status === 'error')
  const isRunning   = entries.some(e => e.status === 'analyzing')
  const totFile     = done.length

  return (
    <div className="fade-in" style={{ height:'100%', display:'flex', flexDirection:'column', gap:20 }}>

      {/* ── Riga superiore: dropzone + bottoni ── */}
      <div style={{ display:'flex', gap:12, alignItems:'flex-start' }}>
        {/* Dropzone compatta */}
        <div
          onClick={() => inputRef.current.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
          style={{
            flex: 1,
            border: `1px dashed ${dragging ? 'var(--cyan)' : 'var(--border-bright)'}`,
            borderRadius: 'var(--radius)',
            padding: '16px 20px',
            display: 'flex', alignItems: 'center', gap: 14,
            cursor: 'pointer',
            background: dragging ? 'var(--cyan-glow)' : 'var(--bg-card)',
            transition: 'all var(--t-med)',
          }}
        >
          <input ref={inputRef} type="file" accept=".mpf,.nc,.spf" multiple style={{ display:'none' }}
            onChange={e => { addFiles(e.target.files); e.target.value='' }} />
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{ flexShrink:0, color:'var(--text-secondary)' }}>
            <path d="M10 3v10M7 6l3-3 3 3M3 15h14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
          </svg>
          <div>
            <div style={{ fontSize:13, fontWeight:600 }}>Trascina i file NC</div>
            <div style={{ fontSize:11, color:'var(--text-secondary)', marginTop:1 }}>.MPF · .NC · .SPF — più file insieme</div>
          </div>
        </div>

        {entries.length > 0 && (
          <>
            <button className="btn btn-primary" onClick={analyzeAll} disabled={!hasPending || isRunning} style={{ flexShrink:0 }}>
              {isRunning ? <><Spinner small /> Analisi...</> : `Analizza (${entries.filter(e=>e.status==='pending'||e.status==='error').length})`}
            </button>
            <button className="btn btn-ghost" onClick={clearAll} disabled={isRunning} style={{ flexShrink:0 }}>Pulisci</button>
          </>
        )}
      </div>

      {/* ── Lista file: solo nome + stato sintetico ── */}
      {entries.length > 0 && (
        <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
          {entries.map(e => {
            const n = e.result?.totale_mancanti ?? 0
            const color = e.status === 'analyzing' ? 'var(--text-dim)'
              : e.status === 'error' ? 'var(--red)'
              : e.status === 'done' && n > 0 ? 'var(--red)'
              : e.status === 'done' ? 'var(--green)'
              : 'var(--text-dim)'
            return (
              <div key={e.id} style={{
                display:'flex', alignItems:'center', gap:7,
                padding:'5px 10px',
                background:'var(--bg-card)',
                border:`1px solid ${e.status==='done' && n>0 ? 'rgba(255,68,85,0.3)' : 'var(--border)'}`,
                borderRadius:'var(--radius-sm)',
                fontSize:12,
              }}>
                {e.status === 'analyzing'
                  ? <Spinner small />
                  : <div style={{ width:6, height:6, borderRadius:'50%', background:color, flexShrink:0 }} />
                }
                <span className="mono" style={{ color:'var(--text-primary)' }}>{e.file.name}</span>
                {e.status === 'done' && n > 0 && <span style={{ color:'var(--red)', fontWeight:700 }}>{n}×</span>}
                <button onClick={() => removeEntry(e.id)} disabled={e.status==='analyzing'}
                  style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-dim)', padding:'0 2px', fontSize:14, lineHeight:1, marginLeft:2 }}>×</button>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Risultati: solo quello che serve ── */}
      {done.length > 0 && (
        <div className="fade-in" style={{ flex:1, display:'flex', flexDirection:'column', gap:16, overflow:'auto' }}>

          {/* Sommario in una riga */}
          <div style={{ display:'flex', alignItems:'center', gap:16, padding:'12px 16px', background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:'var(--radius)' }}>
            <span style={{ fontSize:13, color:'var(--text-secondary)' }}>
              <span className="mono" style={{ color:'var(--cyan)', fontWeight:700 }}>{totFile}</span> file analizzati ·&nbsp;
              <span className="mono" style={{ color:'var(--text-primary)', fontWeight:700 }}>{done.reduce((s,e)=>s+(e.result?.totale_file??0),0)}</span> utensili ·&nbsp;
            </span>
            {allMancanti.length === 0
              ? <span style={{ color:'var(--green)', fontWeight:700, fontSize:13 }}>✓ Tutti presenti</span>
              : <span style={{ color:'var(--red)', fontWeight:700, fontSize:13 }}>⚠ {allMancanti.length} mancant{allMancanti.length===1?'e':'i'}</span>
            }
          </div>

          {/* Mancanti aggregati — solo se esistono */}
          {allMancanti.length > 0 && (
            <div style={{ background:'rgba(255,68,85,0.06)', border:'1px solid rgba(255,68,85,0.2)', borderRadius:'var(--radius)', padding:'14px 16px' }}>
              <div style={{ fontSize:10, fontFamily:'var(--font-mono)', color:'var(--red)', letterSpacing:'0.1em', textTransform:'uppercase', marginBottom:10 }}>
                Utensili mancanti in macchina
              </div>
              <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                {allMancanti.map(a => (
                  <span key={a} className="mono" style={{ padding:'4px 12px', background:'rgba(255,68,85,0.1)', border:'1px solid rgba(255,68,85,0.2)', borderRadius:'var(--radius-sm)', fontSize:13, color:'var(--red)', fontWeight:600 }}>{a}</span>
                ))}
              </div>
              {/* Da quali file */}
              <div style={{ marginTop:12, display:'flex', flexDirection:'column', gap:4 }}>
                {conMancanti.map(e => (
                  <div key={e.id} style={{ fontSize:12, color:'var(--text-secondary)' }}>
                    <span className="mono" style={{ color:'var(--text-primary)' }}>{e.file.name}</span>
                    {' → '}
                    {(e.result?.mancanti??[]).map(a => (
                      <span key={a} className="mono" style={{ color:'var(--red)', marginRight:6 }}>{a}</span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* File senza problemi: solo se ci sono mancanti (altrimenti il banner verde basta) */}
          {allMancanti.length > 0 && done.filter(e=>(e.result?.totale_mancanti??0)===0).length > 0 && (
            <div style={{ fontSize:12, color:'var(--text-dim)' }}>
              <span style={{ color:'var(--green)' }}>✓</span>{' '}
              {done.filter(e=>(e.result?.totale_mancanti??0)===0).map(e=>e.file.name).join(' · ')}
            </div>
          )}
        </div>
      )}

      {/* Stato vuoto */}
      {entries.length === 0 && (
        <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', flexDirection:'column', gap:10, color:'var(--text-dim)' }}>
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none" opacity="0.25">
            <rect x="8" y="4" width="24" height="32" rx="3" stroke="currentColor" strokeWidth="1.5"/>
            <path d="M14 14h12M14 20h12M14 26h7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
          </svg>
          <div style={{ fontSize:13, color:'var(--text-secondary)' }}>Trascina i file NC per iniziare</div>
        </div>
      )}
    </div>
  )
}

function Spinner({ small }) {
  const sz = small ? 10 : 14
  return <div style={{ width:sz, height:sz, border:`${small?1.5:2}px solid var(--border)`, borderTopColor:'var(--cyan)', borderRadius:'50%', animation:'spin 0.7s linear infinite', flexShrink:0 }} />
}
