// RendicontoProgetto.jsx — Report rendiconto commessa
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

const NAVY   = '#0d2d5e'
const BLUE   = '#1D5FAD'
const GREEN  = '#15803d'
const AMBER  = '#b45309'
const RED    = '#dc2626'
const GRAY   = '#64748b'
const BORDER = '#e2e8f0'

function fmt(sec) {
  if (!sec) return '—'
  const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60)
  if (h === 0) return `${m}min`
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}
function fmtData(s) {
  if (!s) return '—'
  try {
    const d = new Date(s)
    return d.toLocaleDateString('it-IT', { day:'2-digit', month:'short', year:'numeric' })
  } catch { return s }
}
function pct(a, b) {
  if (!b) return 0
  return Math.min(100, Math.round(a / b * 100))
}

// ── Stampa / PDF ─────────────────────────────────────────────────────────────
function stampa() {
  window.print()
}

// ── KPI Card ─────────────────────────────────────────────────────────────────
function KpiCard({ label, value, sub, color = NAVY, icon }) {
  return (
    <div style={{ background:'#fff', border:`1px solid ${BORDER}`, borderRadius:12,
      padding:'16px 20px', display:'flex', flexDirection:'column', gap:4 }}>
      <div style={{ fontSize:11, fontWeight:700, color:GRAY, letterSpacing:'0.07em',
        textTransform:'uppercase' }}>{label}</div>
      <div style={{ fontSize:28, fontWeight:900, color, fontFamily:'monospace',
        lineHeight:1.1 }}>{value}</div>
      {sub && <div style={{ fontSize:11, color:GRAY }}>{sub}</div>}
    </div>
  )
}

// ── Timeline visiva ───────────────────────────────────────────────────────────
function Timeline({ tl, scadenza, colore }) {
  const steps = [
    { key:'apertura_progetto', label:'Apertura',   color:BLUE,  above:true  },
    { key:'inizio_macchina',   label:'Inizio mac.',color:GREEN, above:false },
    { key:'fine_macchina',     label:'Fine mac.',  color:GREEN, above:true  },
    { key:'consegna',          label:'Consegna',   color: tl.consegna ? GREEN : GRAY, above:false },
  ].filter(s => tl[s.key])

  if (steps.length < 2) return null

  const dates = steps.map(s => new Date(tl[s.key]).getTime())
  const tMin  = Math.min(...dates)
  const tMax  = Math.max(...dates, scadenza ? new Date(scadenza).getTime() : 0)
  const span  = tMax - tMin || 1

  const pos = (iso) => Math.max(0, Math.min(100, ((new Date(iso).getTime() - tMin) / span) * 100))

  // Scadenza — mancata?
  const scadenzaPos    = scadenza ? pos(scadenza) : null
  const consegnaTs     = tl.consegna ? new Date(tl.consegna).getTime() : null
  const scadenzaTs     = scadenza    ? new Date(scadenza).getTime()    : null
  const scadenzaMancata = consegnaTs && scadenzaTs && consegnaTs > scadenzaTs

  return (
    <div style={{ position:'relative', padding:'44px 0 44px', minHeight:130 }}>
      {/* Barra di sfondo */}
      <div style={{ position:'absolute', top:'50%', left:'4%', right:'4%', height:4, transform:'translateY(-50%)',
        background:BORDER, borderRadius:2 }}/>

      {/* Segmento lavorazione macchina */}
      {tl.inizio_macchina && tl.fine_macchina && (
        <div style={{ position:'absolute', top:'calc(50% - 4px)', height:8, borderRadius:4,
          background: colore || GREEN, opacity:0.3,
          left: `calc(4% + ${pos(tl.inizio_macchina) * 0.92}%)`,
          width: `${(pos(tl.fine_macchina) - pos(tl.inizio_macchina)) * 0.92}%`,
        }}/>
      )}

      {/* Punti + label */}
      {steps.map((s) => {
        const x = pos(tl[s.key])
        return (
          <div key={s.key} style={{ position:'absolute',
            left: `calc(4% + ${x * 0.92}%)`, transform:'translateX(-50%)',
            top:0, bottom:0, display:'flex', flexDirection:'column',
            alignItems:'center', justifyContent:'space-between', width:72 }}>
            <div style={{ textAlign:'center', visibility: s.above ? 'visible' : 'hidden',
              lineHeight:1.2 }}>
              <div style={{ fontSize:9, color:GRAY, fontWeight:600 }}>{s.label}</div>
              <div style={{ fontSize:9, color:NAVY, fontWeight:700 }}>{fmtData(tl[s.key])}</div>
            </div>
            <div style={{ width:13, height:13, borderRadius:'50%', flexShrink:0,
              background:s.color, border:'3px solid #fff',
              boxShadow:`0 0 0 2px ${s.color}` }}/>
            <div style={{ textAlign:'center', visibility: s.above ? 'hidden' : 'visible',
              lineHeight:1.2 }}>
              <div style={{ fontSize:9, color:GRAY, fontWeight:600 }}>{s.label}</div>
              <div style={{ fontSize:9, color:NAVY, fontWeight:700 }}>{fmtData(tl[s.key])}</div>
            </div>
          </div>
        )
      })}

      {/* Scadenza */}
      {scadenzaPos !== null && (
        <div style={{ position:'absolute', top:16,
          left: `calc(4% + ${scadenzaPos * 0.92}%)`,
          transform:'translateX(-50%)' }}>
          <div style={{ width:2, height:24, background: scadenzaMancata ? RED : AMBER,
            margin:'0 auto' }}/>
          <div style={{ fontSize:9, fontWeight:700,
            color: scadenzaMancata ? RED : AMBER,
            textAlign:'center', whiteSpace:'nowrap', marginTop:2 }}>
            ⚑ Scadenza
          </div>
          <div style={{ fontSize:9, color: scadenzaMancata ? RED : AMBER,
            textAlign:'center' }}>
            {fmtData(scadenza)}
          </div>
        </div>
      )}
    </div>
  )
}

// ── Barra orizzontale programmi ───────────────────────────────────────────────
function BarraProgramma({ nome, durata_sec, stima_sec, max_sec, colore }) {
  const pctReale = pct(durata_sec, max_sec)
  const pctStima = stima_sec ? pct(stima_sec, max_sec) : null
  const over     = stima_sec && durata_sec > stima_sec * 1.1
  const under    = stima_sec && durata_sec < stima_sec * 0.9

  return (
    <div style={{ display:'grid', gridTemplateColumns:'180px 1fr 80px',
      gap:8, alignItems:'center', marginBottom:4 }}>
      <div style={{ fontSize:10, fontFamily:'monospace', color:NAVY,
        overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}
        title={nome}>{nome}</div>
      <div style={{ position:'relative', height:18, background:'#f1f5f9',
        borderRadius:4, overflow:'hidden' }}>
        {/* Barra stima */}
        {pctStima && (
          <div style={{ position:'absolute', top:4, left:0,
            width:`${pctStima}%`, height:10,
            background:'#cbd5e1', borderRadius:2 }}/>
        )}
        {/* Barra reale */}
        <div style={{ position:'absolute', top:0, left:0, height:'100%',
          width:`${pctReale}%`,
          background: over ? RED : under ? GREEN : colore || BLUE,
          borderRadius:4, opacity:0.8 }}/>
      </div>
      <div style={{ fontSize:10, fontWeight:700,
        color: over ? RED : under ? GREEN : NAVY,
        textAlign:'right', fontFamily:'monospace' }}>
        {fmt(durata_sec)}
        {stima_sec ? (
          <span style={{ color:GRAY, fontWeight:400 }}>
            /{fmt(stima_sec)}
          </span>
        ) : null}
      </div>
    </div>
  )
}

// ── Componente principale ─────────────────────────────────────────────────────
export default function RendicontoProgetto() {
  const { projectId } = useParams()
  const navigate      = useNavigate()
  const [data, setData]     = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError]   = useState(null)
  const printRef = useRef()

  useEffect(() => {
    fetch(`/api/report/rendiconto-progetto?project_id=${projectId}`)
      .then(r => { if (!r.ok) throw new Error(r.status); return r.json() })
      .then(d => { setData(d); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [projectId])

  if (loading) return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center',
      height:'60vh', color:GRAY, fontSize:14 }}>
      Caricamento rendiconto…
    </div>
  )
  if (error) return (
    <div style={{ padding:32, color:RED }}>Errore: {error}</div>
  )
  if (!data) return null

  const { progetto, delivery, timeline, kpi, programmi, utensili, sessioni } = data
  const maxDur = programmi[0]?.durata_sec || 1
  const scadenzaMancata = delivery.scadenza && !delivery.consegnato &&
    new Date() > new Date(delivery.scadenza)

  return (
    <div ref={printRef} style={{ maxWidth:900, margin:'0 auto',
      padding:'24px 20px 60px', fontFamily:'system-ui, sans-serif' }}>

      {/* ── Intestazione ── */}
      <div style={{ display:'flex', alignItems:'flex-start',
        justifyContent:'space-between', marginBottom:24 }}>
        <div>
          <button onClick={() => navigate(-1)}
            style={{ background:'none', border:'none', color:BLUE,
              cursor:'pointer', fontSize:13, marginBottom:8, padding:0 }}>
            ← Torna ai progetti
          </button>
          <div style={{ display:'flex', alignItems:'center', gap:12 }}>
            <div style={{ width:14, height:36, borderRadius:4,
              background: progetto.colore || BLUE }}/>
            <div>
              <h1 style={{ margin:0, fontSize:26, fontWeight:900, color:NAVY,
                fontFamily:'monospace', letterSpacing:'-0.02em' }}>
                {progetto.nome}
              </h1>
              <div style={{ fontSize:12, color:GRAY, marginTop:2 }}>
                Rendiconto commessa · generato {new Date().toLocaleDateString('it-IT')}
              </div>
            </div>
          </div>
        </div>
        <div style={{ display:'flex', gap:8, alignItems:'center' }}>
          {scadenzaMancata && (
            <div style={{ background:'#fef2f2', border:'1px solid #fca5a5',
              color:RED, fontSize:11, fontWeight:700, padding:'6px 12px',
              borderRadius:6 }}>
              ⚠ SCADENZA MANCATA
            </div>
          )}
          {delivery.consegnato && (
            <div style={{ background:'#f0fdf4', border:'1px solid #86efac',
              color:GREEN, fontSize:11, fontWeight:700, padding:'6px 12px',
              borderRadius:6 }}>
              ✓ CONSEGNATO {fmtData(delivery.consegnato_at)}
            </div>
          )}
          <button onClick={stampa}
            style={{ background:NAVY, color:'#fff', border:'none',
              borderRadius:8, padding:'8px 16px', fontSize:12,
              fontWeight:700, cursor:'pointer' }}>
            ⎙ Stampa / PDF
          </button>
        </div>
      </div>

      {/* ── Timeline ── */}
      <div style={{ background:'#f8fafc', border:`1px solid ${BORDER}`,
        borderRadius:12, padding:'16px 24px', marginBottom:20 }}>
        <div style={{ fontSize:11, fontWeight:700, color:GRAY,
          letterSpacing:'0.07em', textTransform:'uppercase', marginBottom:4 }}>
          Timeline commessa
        </div>
        <Timeline tl={timeline} scadenza={delivery.scadenza} colore={progetto.colore}/>
        <div style={{ display:'flex', gap:24, fontSize:11, color:GRAY }}>
          {timeline.giorni_totali != null && (
            <span>📅 <b style={{color:NAVY}}>{timeline.giorni_totali}</b> giorni totali commessa</span>
          )}
          {timeline.giorni_macchina != null && (
            <span>⚙ <b style={{color:NAVY}}>{timeline.giorni_macchina}</b> giorni di lavorazione</span>
          )}
          {delivery.scadenza && (
            <span style={{color: scadenzaMancata ? RED : GRAY}}>
              ⚑ Scadenza: <b>{fmtData(delivery.scadenza)}</b>
            </span>
          )}
        </div>
      </div>

      {/* ── KPI ── */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)',
        gap:12, marginBottom:20 }}>
        <KpiCard label="Ore macchina" value={kpi.ore_macchina_str}
          sub={kpi.stima_tot_str ? `stima CAM: ${kpi.stima_tot_str}` : undefined}
          color={NAVY}/>
        <KpiCard label="Programmi eseguiti"
          value={`${kpi.n_programmi_completati}/${kpi.n_programmi_totali}`}
          sub={`${kpi.n_programmi_eseguiti} distinti`} color={BLUE}/>
        <KpiCard label="Utensili utilizzati"
          value={kpi.n_utensili} color={GREEN}/>
        <KpiCard label="Fasi lavorazione"
          value={kpi.n_fasi}
          sub={kpi.fasi?.join(' · ')} color={AMBER}/>
      </div>

      {/* ── Scostamento CAM ── */}
      {kpi.scostamento_pct != null && kpi.stima_tot_sec > 0 && (
        <div style={{ background: kpi.scostamento_pct > 10 ? '#fef2f2' : '#f0fdf4',
          border:`1px solid ${kpi.scostamento_pct > 10 ? '#fca5a5' : '#86efac'}`,
          borderRadius:10, padding:'10px 16px', marginBottom:20,
          display:'flex', alignItems:'center', gap:12 }}>
          <div style={{ fontSize:20, fontWeight:900, fontFamily:'monospace',
            color: kpi.scostamento_pct > 10 ? RED : GREEN }}>
            {kpi.scostamento_pct > 0 ? '+' : ''}{kpi.scostamento_pct}%
          </div>
          <div style={{ fontSize:12, color:NAVY }}>
            <b>Scostamento rispetto alla stima CAM</b><br/>
            <span style={{ color:GRAY }}>
              {kpi.ore_macchina_str} effettivi vs {kpi.stima_tot_str} stimati
            </span>
          </div>
        </div>
      )}

      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:16 }}>

        {/* ── Programmi ── */}
        <div style={{ background:'#fff', border:`1px solid ${BORDER}`,
          borderRadius:12, padding:'16px 20px' }}>
          <div style={{ fontSize:11, fontWeight:700, color:GRAY,
            letterSpacing:'0.07em', textTransform:'uppercase', marginBottom:12 }}>
            Programmi NC — tempo effettivo
          </div>
          <div style={{ fontSize:9, color:GRAY, marginBottom:8 }}>
            <span style={{ display:'inline-block', width:10, height:6,
              background:'#cbd5e1', borderRadius:1, marginRight:4 }}/>
            stima CAM &nbsp;&nbsp;
            <span style={{ display:'inline-block', width:10, height:6,
              background:BLUE, borderRadius:1, marginRight:4, opacity:0.8 }}/>
            reale
          </div>
          {programmi.slice(0, 15).map(p => (
            <BarraProgramma key={p.filename}
              nome={p.filename}
              durata_sec={p.durata_sec}
              stima_sec={p.stima_sec}
              max_sec={maxDur}
              colore={progetto.colore}/>
          ))}
          {programmi.length > 15 && (
            <div style={{ fontSize:10, color:GRAY, marginTop:6 }}>
              + {programmi.length - 15} altri programmi
            </div>
          )}
        </div>

        <div style={{ display:'flex', flexDirection:'column', gap:16 }}>

          {/* ── Utensili ── */}
          <div style={{ background:'#fff', border:`1px solid ${BORDER}`,
            borderRadius:12, padding:'16px 20px' }}>
            <div style={{ fontSize:11, fontWeight:700, color:GRAY,
              letterSpacing:'0.07em', textTransform:'uppercase', marginBottom:12 }}>
              Utensili utilizzati
            </div>
            {utensili.length === 0 ? (
              <div style={{ fontSize:11, color:GRAY }}>
                Nessun dato utensile registrato
              </div>
            ) : (
              <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11 }}>
                <thead>
                  <tr style={{ borderBottom:`1px solid ${BORDER}` }}>
                    <th style={{ textAlign:'left', color:GRAY, fontWeight:600,
                      padding:'0 0 6px' }}>Alias</th>
                    <th style={{ textAlign:'right', color:GRAY, fontWeight:600,
                      padding:'0 0 6px' }}>Ore macchina</th>
                  </tr>
                </thead>
                <tbody>
                  {utensili.map(u => (
                    <tr key={u.alias}
                      style={{ borderBottom:`1px solid #f1f5f9` }}>
                      <td style={{ padding:'5px 0', fontFamily:'monospace',
                        color:NAVY, fontSize:10 }}>{u.alias}</td>
                      <td style={{ textAlign:'right', fontWeight:700,
                        color:NAVY, fontFamily:'monospace' }}>
                        {u.ore_str || fmt(u.durata_sec)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* ── Sessioni ── */}
          <div style={{ background:'#fff', border:`1px solid ${BORDER}`,
            borderRadius:12, padding:'16px 20px' }}>
            <div style={{ fontSize:11, fontWeight:700, color:GRAY,
              letterSpacing:'0.07em', textTransform:'uppercase', marginBottom:12 }}>
              Sessioni di lavorazione
            </div>
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11 }}>
              <thead>
                <tr style={{ borderBottom:`1px solid ${BORDER}` }}>
                  <th style={{ textAlign:'left', color:GRAY, fontWeight:600,
                    padding:'0 0 6px' }}>Data</th>
                  <th style={{ textAlign:'left', color:GRAY, fontWeight:600,
                    padding:'0 0 6px' }}>Orario</th>
                  <th style={{ textAlign:'right', color:GRAY, fontWeight:600,
                    padding:'0 0 6px' }}>Durata</th>
                  <th style={{ textAlign:'right', color:GRAY, fontWeight:600,
                    padding:'0 0 6px' }}>Pgm</th>
                </tr>
              </thead>
              <tbody>
                {sessioni.map((s, i) => (
                  <tr key={i} style={{ borderBottom:`1px solid #f1f5f9` }}>
                    <td style={{ padding:'5px 0', color:NAVY, fontWeight:600 }}>
                      {fmtData(s.data)}
                    </td>
                    <td style={{ color:GRAY, fontFamily:'monospace', fontSize:10 }}>
                      {s.inizio?.slice(11,16)}
                      {s.fine ? `→${s.fine.slice(11,16)}` : '→…'}
                    </td>
                    <td style={{ textAlign:'right', fontWeight:700,
                      color:NAVY, fontFamily:'monospace' }}>
                      {s.durata_str}
                    </td>
                    <td style={{ textAlign:'right', color:GRAY }}>
                      {s.n_programmi}
                    </td>
                  </tr>
                ))}
              </tbody>
              <tfoot>
                <tr style={{ borderTop:`2px solid ${BORDER}` }}>
                  <td colSpan={2} style={{ padding:'6px 0', fontWeight:700,
                    color:NAVY }}>Totale</td>
                  <td style={{ textAlign:'right', fontWeight:900,
                    color:NAVY, fontFamily:'monospace' }}>
                    {kpi.ore_macchina_str}
                  </td>
                  <td/>
                </tr>
              </tfoot>
            </table>
          </div>

        </div>
      </div>

      {/* ── CSS stampa ── */}
      <style>{`
        @media print {
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          button { display: none !important; }
        }
      `}</style>
    </div>
  )
}
