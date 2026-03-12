// pages/AnalisiNC.jsx — Analisi multi-file NC (redesign)
import { useState, useRef, useCallback } from 'react'
import { api } from '../api/client'

function FileChip({ entry, onRemove }) {
  const { file, status, result, error } = entry
  const badge = () => {
    if (status === 'analyzing') return <Spinner />
    if (status === 'error')     return <Tag color="red">{error || 'Errore'}</Tag>
    if (status === 'done') {
      const n = result?.totale_mancanti ?? 0
      return n > 0 ? <Tag color="red">{n} mancant{n===1?'e':'i'}</Tag> : <Tag color="green">OK</Tag>
    }
    return <Tag color="gray">in coda</Tag>
  }
  const sub = () => {
    if (status === 'analyzing') return 'analisi in corso...'
    if (status === 'done')      return `${result?.totale_file ?? 0} utensili · analizzato`
    if (status === 'error')     return 'analisi fallita'
    return `${(file.size / 1024).toFixed(1)} KB`
  }
  const dotColor = status === 'done' && (result?.totale_mancanti ?? 0) === 0 ? 'green'
    : (status === 'done' || status === 'error') ? 'red' : 'dim'
  return (
    <div style={{ display:'flex', alignItems:'center', gap:10, padding:'10px 14px', background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:'var(--radius)' }}>
      <Dot color={dotColor} />
      <div style={{ flex:1, minWidth:0 }}>
        <div className="mono" style={{ fontSize:13, fontWeight:600, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{file.name}</div>
        <div style={{ fontSize:11, color:'var(--text-secondary)', marginTop:1 }}>{sub()}</div>
      </div>
      {badge()}
      {status !== 'analyzing' && (
        <button onClick={() => onRemove(entry.id)} style={{ background:'none', border:'none', cursor:'pointer', color:'var(--text-dim)', padding:'2px 4px', fontSize:18, lineHeight:1 }}>×</button>
      )}
    </div>
  )
}

function ResultDetail({ entry }) {
  const [open, setOpen] = useState(false)
  if (entry.status !== 'done' || !entry.result) return null
  const { result, file } = entry
  const mancanti = result.mancanti ?? []
  const presenti = result.presenti_in_macchina ?? []
  const tutti = result.utensili_nel_file ?? []
  return (
    <div style={{ borderBottom:'0.5px solid var(--border)' }}>
      <div onClick={() => setOpen(o => !o)} style={{ display:'flex', alignItems:'center', gap:10, padding:'11px 14px', cursor:'pointer', userSelect:'none' }}>
        <svg width="12" height="12" viewBox="0 0 12 12" fill="none" style={{ flexShrink:0, transition:'transform 150ms', transform: open ? 'rotate(90deg)' : 'rotate(0deg)' }}>
          <path d="M4 2l4 4-4 4" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round"/>
        </svg>
        <span className="mono" style={{ fontSize:13, fontWeight:600, flex:1, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{file.name}</span>
        {mancanti.length > 0
          ? <Tag color="red">{mancanti.length} mancant{mancanti.length===1?'e':'i'}</Tag>
          : <Tag color="green">tutti presenti</Tag>}
      </div>
      {open && (
        <div style={{ paddingLeft:22, paddingRight:14, paddingBottom:12 }}>
          {tutti.map((u, i) => {
            const ok = presenti.includes(u.alias)
            return (
              <div key={i} style={{ display:'flex', alignItems:'center', gap:10, padding:'8px 0', borderBottom: i < tutti.length-1 ? '0.5px solid var(--border)' : 'none' }}>
                <Dot color={ok ? 'green' : 'red'} />
                <span className="mono" style={{ fontSize:12, flex:1 }}>{u.alias}</span>
                <span style={{ fontSize:11, color:'var(--text-dim)' }}>riga {u.riga}</span>
                {ok ? <Tag color="green" small>presente</Tag> : <Tag color="red" small>mancante</Tag>}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

export default function AnalisiNC() {
  const [entries, setEntries] = useState([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()
  const idRef = useRef(0)

  const addFiles = useCallback((files) => {
    const valid = Array.from(files).filter(f => /\.(mpf|nc|spf)$/i.test(f.name))
    if (!valid.length) return
    setEntries(prev => [...prev, ...valid.map(f => ({ id: ++idRef.current, file: f, status: 'pending', result: null, error: null }))])
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

  const done       = entries.filter(e => e.status === 'done')
  const totFile    = done.length
  const totUten    = done.reduce((s, e) => s + (e.result?.totale_file ?? 0), 0)
  const allManc    = [...new Set(done.flatMap(e => e.result?.mancanti ?? []))]
  const hasPending = entries.some(e => e.status === 'pending' || e.status === 'error')
  const isRunning  = entries.some(e => e.status === 'analyzing')

  return (
    <div className="fade-in" style={{ height:'100%', display:'flex', flexDirection:'column', gap:0 }}>
      <div style={{ display:'grid', gridTemplateColumns:'minmax(0,1fr) minmax(0,1.5fr)', gap:24, flex:1, overflow:'hidden' }}>

        {/* ── Sinistra: upload ── */}
        <div style={{ display:'flex', flexDirection:'column', gap:12, overflow:'auto' }}>
          <div
            onClick={() => inputRef.current.click()}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
            style={{ border:`1px dashed ${dragging ? 'var(--cyan)' : 'var(--border-bright)'}`, borderRadius:'var(--radius)', padding:'28px 20px', textAlign:'center', cursor:'pointer', background: dragging ? 'var(--cyan-glow)' : 'var(--bg-card)', transition:'all var(--t-med)', flexShrink:0 }}
          >
            <input ref={inputRef} type="file" accept=".mpf,.nc,.spf" multiple style={{ display:'none' }} onChange={e => { addFiles(e.target.files); e.target.value='' }} />
            <div style={{ width:32, height:32, border:'1px solid var(--border-bright)', borderRadius:'var(--radius-sm)', display:'flex', alignItems:'center', justifyContent:'center', margin:'0 auto 12px', color:'var(--text-secondary)' }}>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path d="M8 2v8M5 5l3-3 3 3M2 12h12" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </div>
            <div style={{ fontSize:13, fontWeight:600, marginBottom:4 }}>Trascina i file NC qui</div>
            <div style={{ fontSize:12, color:'var(--text-secondary)', marginBottom:14 }}>.MPF · .NC · .SPF — più file contemporaneamente</div>
            <button className="btn btn-ghost" style={{ fontSize:12, padding:'5px 14px' }} onClick={e => e.stopPropagation()}>Sfoglia file</button>
          </div>

          {entries.length > 0 && (
            <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
              {entries.map(e => <FileChip key={e.id} entry={e} onRemove={removeEntry} />)}
            </div>
          )}

          {entries.length > 0 && (
            <div style={{ display:'flex', gap:8, flexShrink:0 }}>
              <button className="btn btn-primary" style={{ flex:1 }} onClick={analyzeAll} disabled={!hasPending || isRunning}>
                {isRunning ? <><Spinner small /> Analisi...</> : 'Analizza tutti'}
              </button>
              <button className="btn btn-ghost" onClick={clearAll} disabled={isRunning}>Pulisci</button>
            </div>
          )}
        </div>

        {/* ── Destra: risultati ── */}
        <div style={{ display:'flex', flexDirection:'column', gap:16, overflow:'auto' }}>
          {done.length > 0 ? (
            <>
              <div style={{ display:'flex', gap:10, flexShrink:0 }}>
                <StatCard label="File analizzati" value={totFile} />
                <StatCard label="Utensili totali" value={totUten} />
                <StatCard label="Mancanti" value={allManc.length} alert={allManc.length > 0} />
              </div>

              {allManc.length > 0 && (
                <div style={{ background:'rgba(255,68,85,0.07)', border:'1px solid rgba(255,68,85,0.2)', borderRadius:'var(--radius)', padding:'12px 14px', flexShrink:0 }}>
                  <div style={{ fontSize:11, fontFamily:'var(--font-mono)', color:'var(--red)', letterSpacing:'0.06em', textTransform:'uppercase', marginBottom:10 }}>Mancanti in macchina</div>
                  <div style={{ display:'flex', flexWrap:'wrap', gap:6 }}>
                    {allManc.map(a => (
                      <span key={a} className="mono" style={{ padding:'3px 10px', background:'rgba(255,68,85,0.12)', borderRadius:3, fontSize:12, color:'var(--red)' }}>{a}</span>
                    ))}
                  </div>
                </div>
              )}

              <div style={{ fontSize:11, color:'var(--text-dim)', fontFamily:'var(--font-mono)', letterSpacing:'0.08em', textTransform:'uppercase', flexShrink:0 }}>Dettaglio per file</div>
              <div className="card" style={{ flexShrink:0 }}>
                {done.map(e => <ResultDetail key={e.id} entry={e} />)}
              </div>
            </>
          ) : (
            <div style={{ flex:1, display:'flex', alignItems:'center', justifyContent:'center', flexDirection:'column', gap:10, color:'var(--text-dim)' }}>
              <svg width="40" height="40" viewBox="0 0 40 40" fill="none" opacity="0.3">
                <rect x="8" y="4" width="24" height="32" rx="3" stroke="currentColor" strokeWidth="1.5"/>
                <path d="M14 14h12M14 20h12M14 26h7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
              </svg>
              <div style={{ fontSize:14, fontWeight:600, color:'var(--text-secondary)' }}>Nessun file analizzato</div>
              <div style={{ fontSize:12 }}>Carica uno o più file NC per iniziare</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Dot({ color }) {
  const c = { green:'var(--green)', red:'var(--red)', dim:'var(--text-dim)' }
  return <div style={{ width:6, height:6, borderRadius:'50%', background:c[color]||c.dim, flexShrink:0 }} />
}
function Tag({ color, children, small }) {
  const s = { green:{ bg:'rgba(0,255,136,0.1)', text:'var(--green)' }, red:{ bg:'rgba(255,68,85,0.1)', text:'var(--red)' }, gray:{ bg:'var(--bg-hover)', text:'var(--text-dim)' } }[color] || {}
  return <span style={{ background:s.bg, color:s.text, fontSize:small?10:11, padding:small?'1px 6px':'2px 8px', borderRadius:3, fontFamily:'var(--font-mono)', fontWeight:700, flexShrink:0 }}>{children}</span>
}
function Spinner({ small }) {
  const sz = small ? 12 : 14
  return <div style={{ width:sz, height:sz, border:`${small?1.5:2}px solid var(--border)`, borderTopColor:'var(--cyan)', borderRadius:'50%', animation:'spin 0.7s linear infinite', flexShrink:0 }} />
}
function StatCard({ label, value, alert }) {
  return (
    <div className="card" style={{ flex:1, padding:'12px 14px' }}>
      <div style={{ fontSize:11, color:'var(--text-dim)', fontFamily:'var(--font-mono)', textTransform:'uppercase', letterSpacing:'0.07em', marginBottom:4 }}>{label}</div>
      <div style={{ fontSize:24, fontWeight:800, fontFamily:'var(--font-mono)', color: alert ? 'var(--red)' : 'var(--cyan)', lineHeight:1 }}>{value}</div>
    </div>
  )
}
