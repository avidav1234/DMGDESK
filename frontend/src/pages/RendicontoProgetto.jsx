// RendicontoProgetto.jsx — Rendiconto commessa (v2)
import { useState, useEffect, useRef } from 'react'
import { useParams, useNavigate } from 'react-router-dom'

function fmtOre(sec) {
  if (!sec) return '0h'
  const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}
function fmtData(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleDateString('it-IT',{day:'2-digit',month:'short',year:'numeric'}) }
  catch { return iso }
}
function fmtDataBreve(iso) {
  if (!iso) return '—'
  try { return new Date(iso).toLocaleDateString('it-IT',{day:'2-digit',month:'short'}) }
  catch { return iso }
}
function diffGiorni(a,b) {
  if(!a||!b) return null
  try { return Math.round((new Date(b)-new Date(a))/86400000) }
  catch { return null }
}

function TimelineCommessa({ tl, scadenza, colore }) {
  const FASI_DEF = [
    { key:'apertura_progetto', label:'Apertura',    col:'#1D5FAD', above:true  },
    { key:'inizio_macchina',   label:'Inizio mac.', col:colore||'#1D5FAD', above:false },
    { key:'fine_macchina',     label:'Fine mac.',   col:colore||'#1D5FAD', above:true  },
    { key:'consegna',          label:'Consegna',    col:'#15803d', above:false },
  ]
  const fasi = FASI_DEF.filter(f => tl[f.key])
  if (fasi.length < 2) return null

  const tsAll = fasi.map(f => new Date(tl[f.key]).getTime())
  if (scadenza) tsAll.push(new Date(scadenza).getTime())
  const tMin = Math.min(...tsAll), tMax = Math.max(...tsAll)
  const span = tMax - tMin || 1
  // Aggiunge 10% di padding a sinistra e destra per evitare label ai bordi
  const pos = iso => Math.max(5, Math.min(95, (new Date(iso)-tMin)/span*90+5))
  // Se inizio e fine macchina sono troppo vicini, forziamo separazione minima
  const posInizio = tl.inizio_macchina ? pos(tl.inizio_macchina) : null
  const posFine   = tl.fine_macchina   ? pos(tl.fine_macchina)   : null
  const troppoVicini = posInizio && posFine && Math.abs(posFine - posInizio) < 8

  const scadenzaMancata = tl.consegna
    ? new Date(tl.consegna) > new Date(scadenza)
    : new Date() > new Date(scadenza)

  return (
    <div>
      {/* Label SOPRA (fasi pari: 0, 2) */}
      <div style={{position:'relative',height:28,marginBottom:0}}>
        {fasi.map((f,i) => f.above ? (
          <div key={f.key} style={{position:'absolute',left:`${pos(tl[f.key])}%`,
            transform:'translateX(-50%)',textAlign:'center',minWidth:60}}>
            <div style={{fontSize:9,fontWeight:700,color:'#64748b',whiteSpace:'nowrap'}}>{f.label}</div>
            <div style={{fontSize:10,fontWeight:800,color:'#0d2d5e'}}>{fmtDataBreve(tl[f.key])}</div>
          </div>
        ) : null)}
      </div>
      {/* Retta con dot */}
      <div style={{position:'relative',height:20,margin:'0 0 0 0'}}>
        <div style={{position:'absolute',top:'50%',left:0,right:0,height:3,
          background:'#e2e8f0',borderRadius:2,transform:'translateY(-50%)'}}/>
        {tl.inizio_macchina && tl.fine_macchina && (
          <div style={{position:'absolute',top:'calc(50% - 4px)',height:8,borderRadius:4,
            background:colore||'#1D5FAD',opacity:0.25,
            left:`${pos(tl.inizio_macchina)}%`,
            width:`${Math.max(pos(tl.fine_macchina)-pos(tl.inizio_macchina),1)}%`}}/>
        )}
        {fasi.map((f,i) => (
          <div key={f.key} style={{position:'absolute',
            left:`${pos(tl[f.key])}%`,top:'50%',
            transform:'translate(-50%,-50%)',
            width:13,height:13,borderRadius:'50%',
            background:f.col,border:'3px solid #fff',
            boxShadow:`0 0 0 2px ${f.col}`,zIndex:2}}/>
        ))}
        {scadenza && (
          <div style={{position:'absolute',left:`${pos(scadenza)}%`,top:0,bottom:0,
            transform:'translateX(-50%)',
            display:'flex',flexDirection:'column',alignItems:'center',zIndex:3}}>
            <div style={{flex:1,width:2,background:scadenzaMancata?'#dc2626':'#b45309'}}/>
          </div>
        )}
      </div>
      {/* Label SOTTO (fasi dispari: 1, 3) + scadenza */}
      <div style={{position:'relative',height:28,marginTop:0}}>
        {fasi.map((f,i) => !f.above ? (
          <div key={f.key} style={{position:'absolute',left:`${pos(tl[f.key])}%`,
            transform:'translateX(-50%)',textAlign:'center',minWidth:60}}>
            <div style={{fontSize:9,fontWeight:700,color:'#64748b',whiteSpace:'nowrap'}}>{f.label}</div>
            <div style={{fontSize:10,fontWeight:800,color:'#0d2d5e'}}>{fmtDataBreve(tl[f.key])}</div>
          </div>
        ) : null)}
        {scadenza && (
          <div style={{position:'absolute',left:`${pos(scadenza)}%`,
            transform:'translateX(-50%)',textAlign:'center'}}>
            <div style={{fontSize:8,fontWeight:800,whiteSpace:'nowrap',
              color:scadenzaMancata?'#dc2626':'#b45309'}}>⚑ {fmtDataBreve(scadenza)}</div>
          </div>
        )}
      </div>
      {/* Legenda giorni */}
      <div style={{display:'flex',gap:20,flexWrap:'wrap',marginTop:14,paddingLeft:4}}>
        {fasi.map((f,i) => {
          if(i===0) return null
          const gg = diffGiorni(tl[fasi[i-1].key], tl[f.key])
          if(gg===null) return null
          return (
            <span key={f.key} style={{fontSize:11,color:'#64748b',
              display:'flex',alignItems:'center',gap:5}}>
              <span style={{display:'inline-block',width:16,height:2,
                background:i===1?'#94a3b8':(colore||'#1D5FAD'),borderRadius:1}}/>
              <b style={{color:'#0d2d5e'}}>{gg}</b> gg — {fasi[i-1].label} → {f.label}
            </span>
          )
        })}
        {scadenza && (
          <span style={{fontSize:11,fontWeight:700,
            color:scadenzaMancata?'#dc2626':'#b45309',
            background:scadenzaMancata?'#fef2f2':'#fffbeb',
            padding:'2px 10px',borderRadius:4}}>
            {scadenzaMancata
              ? `⚠ Scadenza mancata${tl.consegna&&diffGiorni(scadenza,tl.consegna)!==null?` (+${diffGiorni(scadenza,tl.consegna)} gg)`:''}`
              : `⚑ Scadenza: ${fmtData(scadenza)}`}
          </span>
        )}
      </div>
    </div>
  )
}

function KpiCard({ label, value, sub, accent='#0d2d5e', icon }) {
  return (
    <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:14,
      padding:'20px 22px',display:'flex',flexDirection:'column',gap:6,
      borderTop:`3px solid ${accent}`}}>
      <div style={{fontSize:10,fontWeight:800,color:'#94a3b8',
        letterSpacing:'0.1em',textTransform:'uppercase'}}>
        {icon&&<span style={{marginRight:5}}>{icon}</span>}{label}
      </div>
      <div style={{fontSize:32,fontWeight:900,color:accent,
        fontFamily:'monospace',lineHeight:1}}>{value}</div>
      {sub&&<div style={{fontSize:11,color:'#64748b'}}>{sub}</div>}
    </div>
  )
}

function BarraPgm({ nome, reale, stima, maxSec, colore }) {
  const wR = Math.round(reale/maxSec*100)
  const wS = stima ? Math.round(stima/maxSec*100) : null
  const sc = stima ? Math.round((reale-stima)/stima*100) : null
  const over = sc!==null && sc>15
  const under = sc!==null && sc<-10
  return (
    <div style={{display:'grid',gridTemplateColumns:'170px 1fr 88px',
      gap:8,alignItems:'center',marginBottom:5}}>
      <div style={{fontSize:10,fontFamily:'monospace',color:'#334155',
        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}
        title={nome}>{nome}</div>
      <div style={{position:'relative',height:16,background:'#f1f5f9',borderRadius:4}}>
        {wS&&<div style={{position:'absolute',top:3,left:0,height:10,
          width:`${wS}%`,background:'#cbd5e1',borderRadius:3}}/>}
        <div style={{position:'absolute',top:0,left:0,height:'100%',
          width:`${wR}%`,borderRadius:4,opacity:0.75,
          background:over?'#ef4444':under?'#16a34a':(colore||'#1D5FAD')}}/>
      </div>
      <div style={{display:'flex',justifyContent:'flex-end',alignItems:'center',gap:5}}>
        <span style={{fontSize:10,fontWeight:700,color:'#0d2d5e',fontFamily:'monospace'}}>
          {fmtOre(reale)}
        </span>
        {sc!==null&&(
          <span style={{fontSize:9,fontWeight:700,padding:'1px 5px',borderRadius:4,
            background:over?'#fef2f2':under?'#f0fdf4':'#f8fafc',
            color:over?'#dc2626':under?'#15803d':'#64748b'}}>
            {sc>0?'+':''}{sc}%
          </span>
        )}
      </div>
    </div>
  )
}

export default function RendicontoProgetto() {
  const { projectId } = useParams()
  const navigate = useNavigate()
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [error, setError] = useState(null)
  const [note, setNote] = useState('')
  const [editNote, setEditNote] = useState(false)
  const noteRef = useRef()

  useEffect(() => {
    fetch(`/api/report/rendiconto-progetto?project_id=${projectId}`)
      .then(r => { if(!r.ok) throw new Error(r.status); return r.json() })
      .then(d => { setData(d); setNote(d.progetto.note||''); setLoading(false) })
      .catch(e => { setError(e.message); setLoading(false) })
  }, [projectId])

  if(loading) return (
    <div style={{display:'flex',height:'60vh',alignItems:'center',
      justifyContent:'center',color:'#64748b',fontSize:14}}>
      Generazione rendiconto…
    </div>
  )
  if(error) return <div style={{padding:32,color:'#dc2626'}}>Errore: {error}</div>
  if(!data) return null

  const { progetto, delivery, timeline, kpi, programmi, utensili, sessioni } = data
  const colore = progetto.colore || '#1D5FAD'
  const maxDur = programmi[0]?.durata_sec || 1

  const consegnaTs = delivery.consegnato_at
    ? new Date(delivery.consegnato_at.includes('/')
        ? delivery.consegnato_at.replace(/(\d{2})\/(\d{2})\/(\d{4})/,'$3-$2-$1')
        : delivery.consegnato_at)
    : null
  const scadenzaTs = delivery.scadenza ? new Date(delivery.scadenza) : null
  const scadenzaMancata = scadenzaTs && (consegnaTs
    ? consegnaTs > scadenzaTs
    : new Date() > scadenzaTs)

  return (
    <div style={{maxWidth:960,margin:'0 auto',padding:'28px 24px 80px',
      fontFamily:'system-ui,-apple-system,sans-serif',color:'#0d2d5e'}}>

      {/* HEADER */}
      <div style={{display:'flex',justifyContent:'space-between',
        alignItems:'flex-start',marginBottom:32,gap:16}}>
        <div>
          <button onClick={()=>navigate(-1)} style={{background:'none',border:'none',
            color:'#64748b',cursor:'pointer',fontSize:12,padding:0,marginBottom:12}}>
            ← Torna ai progetti
          </button>
          <div style={{display:'flex',alignItems:'center',gap:14}}>
            <div style={{width:6,height:50,borderRadius:3,background:colore,flexShrink:0}}/>
            <div>
              <h1 style={{margin:0,fontSize:30,fontWeight:900,letterSpacing:'-0.03em',
                fontFamily:'monospace',color:'#0d2d5e'}}>{progetto.nome}</h1>
              {progetto.descrizione&&(
                <div style={{fontSize:15,fontWeight:600,color:'#334155',marginTop:2}}>
                  {progetto.descrizione}
                </div>
              )}
              <div style={{fontSize:12,color:'#94a3b8',marginTop:progetto.descrizione?2:3}}>
                Rendiconto commessa &nbsp;·&nbsp; generato il {new Date().toLocaleDateString('it-IT',{day:'2-digit',month:'long',year:'numeric'})}
              </div>
            </div>
          </div>
        </div>
        <div style={{display:'flex',flexDirection:'column',alignItems:'flex-end',gap:8}}>
          {delivery.consegnato ? (
            <div style={{background:'#f0fdf4',border:'1px solid #86efac',color:'#15803d',
              fontSize:11,fontWeight:800,padding:'6px 14px',borderRadius:8,letterSpacing:'0.04em'}}>
              ✓ CONSEGNATO {fmtData(delivery.consegnato_at?.replace(/(\d{2})\/(\d{2})\/(\d{4}).*/,'$3-$2-$1'))}
            </div>
          ) : scadenzaMancata ? (
            <div style={{background:'#fef2f2',border:'1px solid #fca5a5',color:'#dc2626',
              fontSize:11,fontWeight:800,padding:'6px 14px',borderRadius:8,letterSpacing:'0.04em'}}>
              ⚠ SCADENZA MANCATA
            </div>
          ) : (
            <div style={{background:'#fffbeb',border:'1px solid #fcd34d',color:'#92400e',
              fontSize:11,fontWeight:800,padding:'6px 14px',borderRadius:8}}>IN CORSO</div>
          )}
          <button onClick={()=>window.print()} style={{background:'#0d2d5e',color:'#fff',
            border:'none',borderRadius:8,padding:'9px 18px',fontSize:12,
            fontWeight:700,cursor:'pointer'}}>⎙ Stampa / PDF</button>
        </div>
      </div>

      {/* 1. TIMELINE */}
      <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:16,
        padding:'24px 28px',marginBottom:20}}>
        <div style={{fontSize:10,fontWeight:800,color:'#94a3b8',letterSpacing:'0.1em',
          textTransform:'uppercase',marginBottom:20}}>Percorrenza commessa</div>
        <TimelineCommessa tl={timeline} scadenza={delivery.scadenza} colore={colore}/>
      </div>

      {/* 2. KPI */}
      <div className="kpi-grid" style={{display:'grid',gridTemplateColumns:'repeat(4,1fr)',gap:12,marginBottom:20}}>
        <KpiCard label="Ore macchina" value={kpi.ore_macchina_str}
          sub={`${kpi.n_sessioni} sessioni`} accent={colore} icon="⚙"/>
        <KpiCard label="Programmi NC" value={`${kpi.n_programmi_completati??0}/${kpi.n_programmi_totali??0}`}
          sub={`${kpi.n_programmi_eseguiti} distinti eseguiti`} accent="#1D5FAD" icon="📋"/>
        <KpiCard label="Utensili usati" value={kpi.n_utensili}
          sub={`${kpi.n_fasi} fas${kpi.n_fasi===1?'e':'i'} di lavorazione`} accent="#0f766e" icon="🔧"/>
        <KpiCard label="Giorni commessa" value={timeline.giorni_totali??'—'}
          sub={`${timeline.giorni_macchina??'—'} giorni in macchina`} accent="#7c3aed" icon="📅"/>
      </div>

      {/* 3. DETTAGLIO */}
      <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:16,marginBottom:20}}>

        {/* Programmi */}
        <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:16,padding:'22px 24px'}}>
          <div style={{fontSize:10,fontWeight:800,color:'#94a3b8',letterSpacing:'0.1em',
            textTransform:'uppercase',marginBottom:14}}>Programmi NC — tempo effettivo</div>
          <div style={{display:'flex',gap:16,marginBottom:12}}>
            {[['#cbd5e1','stima CAM'],[colore,'reale'],['#ef4444','oltre stima']].map(([c,l])=>(
              <div key={l} style={{display:'flex',alignItems:'center',gap:5,fontSize:9,color:'#64748b'}}>
                <div style={{width:14,height:6,background:c,opacity:0.75,borderRadius:2}}/>{l}
              </div>
            ))}
          </div>
          {programmi.slice(0,20).map(p=>(
            <BarraPgm key={p.filename} nome={p.filename}
              reale={p.durata_sec} stima={p.stima_sec}
              maxSec={maxDur} colore={colore}/>
          ))}
          {programmi.length>20&&(
            <div style={{fontSize:10,color:'#94a3b8',marginTop:8,textAlign:'center'}}>
              + {programmi.length-20} altri programmi
            </div>
          )}
        </div>

        <div style={{display:'flex',flexDirection:'column',gap:16}}>

          {/* Utensili */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:16,
            padding:'22px 24px',flex:1}}>
            <div style={{fontSize:10,fontWeight:800,color:'#94a3b8',letterSpacing:'0.1em',
              textTransform:'uppercase',marginBottom:14}}>Utensili utilizzati</div>
            {utensili.length===0 ? (
              <div style={{fontSize:12,color:'#94a3b8',textAlign:'center',padding:'16px 0'}}>
                Nessun dato utensile
              </div>
            ) : (
              <table style={{width:'100%',borderCollapse:'collapse',fontSize:11}}>
                <thead>
                  <tr style={{borderBottom:'1px solid #f1f5f9'}}>
                    <th style={{textAlign:'left',color:'#94a3b8',fontWeight:700,fontSize:10,
                      padding:'0 0 8px',textTransform:'uppercase',letterSpacing:'0.05em'}}>Utensile</th>
                    <th style={{textAlign:'right',color:'#94a3b8',fontWeight:700,fontSize:10,
                      padding:'0 0 8px',textTransform:'uppercase',letterSpacing:'0.05em'}}>Ore uso</th>
                  </tr>
                </thead>
                <tbody>
                  {utensili.map(u=>(
                    <tr key={u.alias} style={{borderBottom:'1px solid #f8fafc'}}>
                      <td style={{padding:'6px 0',fontFamily:'monospace',fontSize:10,color:'#334155'}}>
                        {u.alias}
                      </td>
                      <td style={{textAlign:'right',fontWeight:700,color:'#0d2d5e',
                        fontFamily:'monospace',fontSize:11}}>
                        {u.ore_str||fmtOre(u.durata_sec)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Sessioni — aggregate per giorno */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:16,padding:'22px 24px'}}>
            <div style={{fontSize:10,fontWeight:800,color:'#94a3b8',letterSpacing:'0.1em',
              textTransform:'uppercase',marginBottom:14}}>Ore per giornata</div>
            {(()=>{
              const perGiorno = {}
              sessioni.forEach(s => {
                const d = s.data
                if(!perGiorno[d]) perGiorno[d] = {data:d,durata_sec:0,n_programmi:0}
                perGiorno[d].durata_sec  += s.durata_sec || 0
                perGiorno[d].n_programmi += s.n_programmi || 0
              })
              const giorni = Object.values(perGiorno).sort((a,b)=>a.data.localeCompare(b.data))
              const fmtH = sec => {
                const h=Math.floor(sec/3600),m=Math.floor((sec%3600)/60)
                return `${String(h).padStart(2,'0')}h ${String(m).padStart(2,'0')}m`
              }
              return (
                <table style={{width:'100%',borderCollapse:'collapse',fontSize:12}}>
                  <thead>
                    <tr style={{borderBottom:'2px solid #e2e8f0'}}>
                      <th style={{textAlign:'left',color:'#94a3b8',fontWeight:700,
                        fontSize:10,padding:'0 0 8px',textTransform:'uppercase',
                        letterSpacing:'0.05em'}}>Giorno</th>
                      <th style={{textAlign:'right',color:'#94a3b8',fontWeight:700,
                        fontSize:10,padding:'0 0 8px',textTransform:'uppercase',
                        letterSpacing:'0.05em'}}>Ore lavorate</th>
                      <th style={{textAlign:'right',color:'#94a3b8',fontWeight:700,
                        fontSize:10,padding:'0 0 8px',textTransform:'uppercase',
                        letterSpacing:'0.05em'}}>Pgm</th>
                    </tr>
                  </thead>
                  <tbody>
                    {giorni.map(g=>(
                      <tr key={g.data} style={{borderBottom:'1px solid #f1f5f9'}}>
                        <td style={{padding:'8px 0',fontWeight:700,color:'#0d2d5e',fontSize:13}}>
                          {new Date(g.data).toLocaleDateString('it-IT',
                            {weekday:'long',day:'2-digit',month:'long',year:'numeric'})}
                        </td>
                        <td style={{textAlign:'right',fontWeight:900,color:'#0d2d5e',
                          fontFamily:'monospace',fontSize:16}}>{fmtH(g.durata_sec)}</td>
                        <td style={{textAlign:'right',color:'#64748b',fontSize:12,
                          paddingLeft:8}}>{g.n_programmi}</td>
                      </tr>
                    ))}
                  </tbody>
                  <tfoot>
                    <tr style={{borderTop:'2px solid #0d2d5e'}}>
                      <td style={{padding:'10px 0',fontWeight:800,fontSize:13,color:'#0d2d5e'}}>
                        Totale
                      </td>
                      <td style={{textAlign:'right',fontWeight:900,color:'#0d2d5e',
                        fontFamily:'monospace',fontSize:18}}>{kpi.ore_macchina_str}</td>
                      <td/>
                    </tr>
                  </tfoot>
                </table>
              )
            })()}
          </div>
        </div>
      </div>

      {/* 4. NOTE OPERATIVE */}
      <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:16,padding:'22px 24px'}}>
        <div style={{display:'flex',justifyContent:'space-between',
          alignItems:'center',marginBottom:14}}>
          <div style={{fontSize:10,fontWeight:800,color:'#94a3b8',
            letterSpacing:'0.1em',textTransform:'uppercase'}}>Note operative</div>
          {!editNote ? (
            <button onClick={()=>{setEditNote(true);setTimeout(()=>noteRef.current?.focus(),50)}}
              style={{background:'none',border:'1px solid #e2e8f0',borderRadius:6,
                color:'#64748b',fontSize:11,padding:'4px 12px',cursor:'pointer',fontWeight:600}}>
              ✎ Modifica
            </button>
          ) : (
            <div style={{display:'flex',gap:8}}>
              <button onClick={()=>setEditNote(false)}
                style={{background:'#0d2d5e',border:'none',borderRadius:6,color:'#fff',
                  fontSize:11,padding:'4px 14px',cursor:'pointer',fontWeight:700}}>
                ✓ Salva
              </button>
              <button onClick={()=>{setNote(data.progetto.note||'');setEditNote(false)}}
                style={{background:'none',border:'1px solid #e2e8f0',borderRadius:6,
                  color:'#64748b',fontSize:11,padding:'4px 12px',cursor:'pointer'}}>
                Annulla
              </button>
            </div>
          )}
        </div>
        {editNote ? (
          <textarea ref={noteRef} value={note} onChange={e=>setNote(e.target.value)}
            placeholder="Inserisci note operative, osservazioni, criticità riscontrate durante la lavorazione…"
            style={{width:'100%',minHeight:100,border:'1px solid #e2e8f0',borderRadius:8,
              padding:'10px 14px',fontSize:12,color:'#334155',fontFamily:'inherit',
              resize:'vertical',outline:'none',boxSizing:'border-box',lineHeight:1.6}}/>
        ) : (
          <div style={{fontSize:12,color:note?'#334155':'#cbd5e1',lineHeight:1.7,
            minHeight:48,fontStyle:note?'normal':'italic'}}>
            <span className={note ? undefined : "note-placeholder"}>{note||'Nessuna nota inserita. Clicca "Modifica" per aggiungere osservazioni prima di stampare.'}</span>
          </div>
        )}
      </div>

      <style>{`
        @media print {
          body { -webkit-print-color-adjust: exact; print-color-adjust: exact; }
          button, nav, aside, [class*="sidebar"], [class*="Sidebar"],
          [class*="nav"], [class*="Nav"] { display: none !important; }
          main, #root > div, body > div { padding-left: 0 !important; margin-left: 0 !important; }
          .kpi-grid { grid-template-columns: repeat(2,1fr) !important; }
          .note-placeholder { display: none !important; }
          .detail-grid { grid-template-columns: 1fr 1fr !important; }
          @page { margin: 15mm; size: A4; }
          * { overflow: visible !important; }
        }
      `}</style>
    </div>
  )
}
