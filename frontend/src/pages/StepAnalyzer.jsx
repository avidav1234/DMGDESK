import { useState, useEffect } from 'react'

const API = (path) => fetch(`/api/step${path}`)
const T = { surface: 'var(--bg-surface)', border: 'var(--border)', text: 'var(--text-primary)', dim: 'var(--text-secondary)' }

function Badge({ pct }) {
  const color = pct >= 90 ? '#16a34a' : pct >= 75 ? '#d97706' : pct >= 60 ? '#ea580c' : '#94a3b8'
  const bg    = pct >= 90 ? '#dcfce7' : pct >= 75 ? '#fef3c7' : pct >= 60 ? '#ffedd5' : '#f1f5f9'
  return (
    <span style={{fontSize:11,fontWeight:800,color,background:bg,
      padding:'2px 8px',borderRadius:6,flexShrink:0}}>
      {pct}%
    </span>
  )
}

export default function StepAnalyzer() {
  const [stato, setStato]       = useState(null)
  const [storico, setStorico]   = useState([])
  const [simili, setSimili]     = useState(null)
  const [loading, setLoading]   = useState(false)
  const [analyzing, setAnalyzing] = useState(false)
  const [error, setError]       = useState(null)
  const [success, setSuccess]   = useState(null)

  // Form analisi
  const [commessa, setCommessa] = useState('')
  const [fileStep, setFileStep] = useState(null)
  const [oreMacchina, setOreMacchina] = useState('')
  const [leadTime, setLeadTime] = useState('')
  const [note, setNote]         = useState('')

  // Simili
  const [commessaSim, setCommessaSim] = useState('')

  const loadAll = async () => {
    setLoading(true)
    try {
      const [st, stor] = await Promise.all([
        API('/stato').then(r => r.ok ? r.json() : null),
        API('/storico').then(r => r.ok ? r.json() : null),
      ])
      setStato(st)
      setStorico(stor?.commesse || [])
    } catch {}
    setLoading(false)
  }

  useEffect(() => { loadAll() }, [])

  const handleAnalizza = async () => {
    if (!commessa.trim() || !fileStep) {
      setError('Inserisci commessa e seleziona il file STEP')
      return
    }
    setAnalyzing(true); setError(null); setSuccess(null)
    try {
      const fd = new FormData()
      fd.append('file', fileStep)
      fd.append('commessa', commessa.trim())
      if (oreMacchina) fd.append('ore_macchina', oreMacchina)
      if (leadTime)    fd.append('lead_time_giorni', leadTime)
      if (note)        fd.append('note', note)

      const r = await fetch('/api/step/analizza-upload', { method: 'POST', body: fd })
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'Errore analisi')
      setSuccess(`✓ ${commessa} analizzato — ${d.features?.n_facce} facce, ${d.features?.n_cilindri} cilindri (${d.features?._elapsed_sec}s)`)
      setCommessa(''); setFileStep(null); setOreMacchina(''); setLeadTime(''); setNote('')
      loadAll()
    } catch (e) { setError(e.message) }
    setAnalyzing(false)
  }

  const handleSimili = async (nome) => {
    setCommessaSim(nome); setSimili(null); setError(null)
    try {
      const r = await API(`/simili/${encodeURIComponent(nome)}?top=5&soglia=50`)
      const d = await r.json()
      if (!r.ok) throw new Error(d.detail || 'Errore')
      setSimili(d)
    } catch (e) { setError(e.message) }
  }

  const fmtOre = h => h ? `${Math.floor(h)}h ${Math.round((h%1)*60)}m` : '—'

  return (
    <div style={{height:'100%',overflowY:'auto',background:'#f0f4f8',
      fontFamily:'var(--font-display)',padding:'16px 20px'}}>

      {/* Header */}
      <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:16}}>
        <div>
          <div style={{fontSize:16,fontWeight:800,color:'#0d2d5e'}}>STEP Analyzer</div>
          <div style={{fontSize:11,color:'#94a3b8'}}>
            Similarità geometrica tra commesse · microservizio porta 8002
          </div>
        </div>
        {stato && (
          <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:8}}>
            <div style={{width:8,height:8,borderRadius:'50%',background:'#16a34a'}}/>
            <span style={{fontSize:11,color:'#16a34a',fontWeight:700}}>Online</span>
            <span style={{fontSize:11,color:'#94a3b8'}}>{stato.n_commesse} commesse</span>
          </div>
        )}
      </div>

      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:14}}>

        {/* ── Aggiungi commessa ─────────────────────────────────────── */}
        <div style={{background:'#fff',borderRadius:12,padding:'16px',
          border:'1px solid #e2e8f0',gridColumn:'1'}}>
          <div style={{fontSize:11,fontWeight:700,letterSpacing:'0.08em',
            color:'#64748b',textTransform:'uppercase',marginBottom:12}}>
            Analizza file STEP
          </div>

          {error && (
            <div style={{background:'#fef2f2',border:'1px solid #fca5a5',borderRadius:8,
              padding:'8px 12px',fontSize:12,color:'#dc2626',marginBottom:10}}>
              {error}
            </div>
          )}
          {success && (
            <div style={{background:'#f0fdf4',border:'1px solid #86efac',borderRadius:8,
              padding:'8px 12px',fontSize:12,color:'#16a34a',marginBottom:10}}>
              {success}
            </div>
          )}

          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            <div>
              <label style={{fontSize:11,color:'#64748b',fontWeight:600}}>
                Commessa *
              </label>
              <input value={commessa} onChange={e=>setCommessa(e.target.value)}
                placeholder="es. 4298_0005"
                style={{width:'100%',marginTop:3,padding:'7px 10px',borderRadius:6,
                  border:'1px solid #e2e8f0',fontSize:12,fontFamily:'monospace',
                  boxSizing:'border-box'}}/>
            </div>
            <div>
              <label style={{fontSize:11,color:'#64748b',fontWeight:600}}>
                File STEP *
              </label>
              <input type="file" accept=".stp,.step,.STP,.STEP"
                onChange={e=>setFileStep(e.target.files[0]||null)}
                style={{width:'100%',marginTop:3,padding:'6px 10px',borderRadius:6,
                  border:'1px solid #e2e8f0',fontSize:12,boxSizing:'border-box',
                  cursor:'pointer'}}/>
              {fileStep && (
                <div style={{fontSize:10,color:'#16a34a',marginTop:3}}>
                  ✓ {fileStep.name} ({(fileStep.size/1024/1024).toFixed(1)} MB)
                </div>
              )}
            </div>
            <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
              <div>
                <label style={{fontSize:11,color:'#64748b',fontWeight:600}}>
                  Ore macchina reali
                </label>
                <input value={oreMacchina} onChange={e=>setOreMacchina(e.target.value)}
                  placeholder="es. 58.5" type="number" step="0.1"
                  style={{width:'100%',marginTop:3,padding:'7px 10px',borderRadius:6,
                    border:'1px solid #e2e8f0',fontSize:12,boxSizing:'border-box'}}/>
              </div>
              <div>
                <label style={{fontSize:11,color:'#64748b',fontWeight:600}}>
                  Lead time (giorni)
                </label>
                <input value={leadTime} onChange={e=>setLeadTime(e.target.value)}
                  placeholder="es. 14" type="number"
                  style={{width:'100%',marginTop:3,padding:'7px 10px',borderRadius:6,
                    border:'1px solid #e2e8f0',fontSize:12,boxSizing:'border-box'}}/>
              </div>
            </div>
            <div>
              <label style={{fontSize:11,color:'#64748b',fontWeight:600}}>Note</label>
              <input value={note} onChange={e=>setNote(e.target.value)}
                placeholder="es. stampaggio, acciaio 42CrMo4"
                style={{width:'100%',marginTop:3,padding:'7px 10px',borderRadius:6,
                  border:'1px solid #e2e8f0',fontSize:12,boxSizing:'border-box'}}/>
            </div>
            <button onClick={handleAnalizza} disabled={analyzing}
              style={{padding:'9px 0',borderRadius:8,border:'none',cursor:'pointer',
                background: analyzing ? '#94a3b8' : '#0d2d5e',
                color:'#fff',fontSize:13,fontWeight:700,marginTop:4}}>
              {analyzing ? '⏳ Analisi in corso (~5s)...' : '🔍 Analizza STEP'}
            </button>
          </div>
        </div>

        {/* ── Trova simili ──────────────────────────────────────────── */}
        <div style={{background:'#fff',borderRadius:12,padding:'16px',
          border:'1px solid #e2e8f0',gridColumn:'2'}}>
          <div style={{fontSize:11,fontWeight:700,letterSpacing:'0.08em',
            color:'#64748b',textTransform:'uppercase',marginBottom:12}}>
            Trova commesse simili
          </div>

          {simili ? (
            <div>
              <div style={{fontSize:12,color:'#64748b',marginBottom:10}}>
                Simili a <span style={{fontWeight:700,fontFamily:'monospace',
                  color:'#0d2d5e'}}>{simili.commessa_ref}</span>
                {' '}— {simili.n_totale} trovate
              </div>
              {simili.simili.length === 0 ? (
                <div style={{color:'#94a3b8',fontSize:12,padding:'20px 0',textAlign:'center'}}>
                  Nessuna commessa simile trovata (soglia 50%)
                </div>
              ) : (
                <div style={{display:'flex',flexDirection:'column',gap:8}}>
                  {simili.simili.map((s,i) => (
                    <div key={i} style={{border:'1px solid #e2e8f0',borderRadius:8,
                      padding:'10px 12px'}}>
                      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:6}}>
                        <Badge pct={s.similarita_pct}/>
                        <span style={{fontSize:13,fontWeight:700,fontFamily:'monospace',
                          color:'#0d2d5e'}}>{s.commessa}</span>
                      </div>
                      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',
                        gap:6,fontSize:11}}>
                        <div>
                          <div style={{color:'#94a3b8'}}>Ore macchina</div>
                          <div style={{fontWeight:700,fontFamily:'monospace',
                            color:'#0d2d5e'}}>{fmtOre(s.ore_macchina)}</div>
                        </div>
                        <div>
                          <div style={{color:'#94a3b8'}}>Lead time</div>
                          <div style={{fontWeight:700,color:'#0d2d5e'}}>
                            {s.lead_time_giorni ? `${s.lead_time_giorni}gg` : '—'}
                          </div>
                        </div>
                        <div>
                          <div style={{color:'#94a3b8'}}>Geometria</div>
                          <div style={{color:'#64748b'}}>
                            {s.n_facce}F / {s.n_cilindri}C
                          </div>
                        </div>
                      </div>
                      {s.note && (
                        <div style={{marginTop:4,fontSize:10,color:'#94a3b8',
                          fontStyle:'italic'}}>{s.note}</div>
                      )}
                    </div>
                  ))}
                </div>
              )}
              <button onClick={()=>setSimili(null)}
                style={{marginTop:10,padding:'6px 0',width:'100%',borderRadius:6,
                  border:'1px solid #e2e8f0',background:'#f8fafc',
                  fontSize:12,cursor:'pointer',color:'#64748b'}}>
                ← Torna allo storico
              </button>
            </div>
          ) : (
            <div>
              <div style={{fontSize:12,color:'#64748b',marginBottom:10}}>
                Clicca su una commessa nello storico per trovare le simili.
              </div>
              {storico.length === 0 ? (
                <div style={{color:'#94a3b8',fontSize:12,padding:'20px 0',textAlign:'center'}}>
                  Nessuna commessa analizzata ancora
                </div>
              ) : (
                <div style={{display:'flex',flexDirection:'column',gap:6,maxHeight:320,overflowY:'auto'}}>
                  {storico.map((s,i) => (
                    <div key={i} onClick={()=>handleSimili(s.commessa)}
                      style={{display:'flex',alignItems:'center',gap:10,
                        padding:'8px 10px',borderRadius:8,cursor:'pointer',
                        border:'1px solid #e2e8f0',
                        background: commessaSim===s.commessa ? '#eff6ff' : '#f8fafc'}}
                      onMouseEnter={e=>e.currentTarget.style.background='#eff6ff'}
                      onMouseLeave={e=>e.currentTarget.style.background=commessaSim===s.commessa?'#eff6ff':'#f8fafc'}>
                      <span style={{fontSize:12,fontWeight:700,fontFamily:'monospace',
                        color:'#0d2d5e',flex:1}}>{s.commessa}</span>
                      <span style={{fontSize:10,color:'#94a3b8'}}>
                        {s.n_facce}F · {s.n_cilindri}C
                      </span>
                      {s.ore_macchina && (
                        <span style={{fontSize:10,fontWeight:700,color:'#6d28d9',
                          background:'#f5f3ff',padding:'1px 6px',borderRadius:4}}>
                          {fmtOre(s.ore_macchina)}
                        </span>
                      )}
                      <span style={{fontSize:10,color:'#94a3b8'}}>→</span>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}
        </div>

      </div>

      {/* ── Storico completo ────────────────────────────────────────── */}
      {storico.length > 0 && (
        <div style={{background:'#fff',borderRadius:12,padding:'16px',
          border:'1px solid #e2e8f0',marginTop:14}}>
          <div style={{fontSize:11,fontWeight:700,letterSpacing:'0.08em',
            color:'#64748b',textTransform:'uppercase',marginBottom:10}}>
            Storico analisi ({storico.length})
          </div>
          <table style={{width:'100%',borderCollapse:'collapse',fontSize:12}}>
            <thead>
              <tr style={{borderBottom:'2px solid #e2e8f0'}}>
                {['Commessa','Facce','Cilindri','Compattezza','Ore macchina','Lead time','Analizzato'].map(h=>(
                  <th key={h} style={{padding:'6px 10px',textAlign:'left',fontSize:10,
                    color:'#94a3b8',fontWeight:700,textTransform:'uppercase',
                    letterSpacing:'0.06em'}}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {storico.map((s,i)=>(
                <tr key={i} onClick={()=>handleSimili(s.commessa)}
                  style={{borderBottom:'1px solid #f1f5f9',cursor:'pointer'}}
                  onMouseEnter={e=>e.currentTarget.style.background='#f8fafc'}
                  onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                  <td style={{padding:'7px 10px',fontWeight:700,fontFamily:'monospace',
                    color:'#0d2d5e'}}>{s.commessa}</td>
                  <td style={{padding:'7px 10px',color:'#475569'}}>{s.n_facce}</td>
                  <td style={{padding:'7px 10px',color:'#475569'}}>{s.n_cilindri}</td>
                  <td style={{padding:'7px 10px',color:'#475569'}}>
                    {s.compattezza?.toFixed(3)}
                  </td>
                  <td style={{padding:'7px 10px',fontFamily:'monospace',color:'#6d28d9',
                    fontWeight:600}}>{fmtOre(s.ore_macchina)}</td>
                  <td style={{padding:'7px 10px',color:'#475569'}}>
                    {s.lead_time_giorni ? `${s.lead_time_giorni}gg` : '—'}
                  </td>
                  <td style={{padding:'7px 10px',color:'#94a3b8',fontSize:11}}>
                    {s.analizzato?.slice(0,10)}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

    </div>
  )
}
