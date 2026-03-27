// Home.jsx — Cruscotto turno
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

function daysUntil(dateStr){
  if(!dateStr) return null
  try{
    const p=dateStr.split(/[\/\-]/)
    const d=p[0].length===4?new Date(p[0],p[1]-1,p[2]):new Date(p[2],p[1]-1,p[0])
    const now=new Date(); now.setHours(0,0,0,0)
    return Math.ceil((d-now)/(1000*60*60*24))
  }catch{return null}
}

export default function Home(){
  const nav = useNavigate()
  const [projects,  setProjects]  = useState([])
  const [deliveries,setDeliveries]= useState([])
  const [pallet,    setPallet]    = useState([])
  const [setup,     setSetup]     = useState({})
  const [loading,   setLoading]   = useState(true)

  useEffect(()=>{
    Promise.all([
      fetch('/api/progetti/').then(r=>r.ok?r.json():{projects:[]}),
      fetch('/api/progetti/deliveries').then(r=>r.ok?r.json():[]),
      fetch('/api/pallet/').then(r=>r.ok?r.json():{pallet:[]}),
      fetch('/api/progetti/analisi-setup/non-utilizzati').then(r=>r.ok?r.json():{}).catch(()=>({})),
    ]).then(([pd,del,pal,s])=>{
      setProjects((pd.projects||[]).filter(p=>!p.archived))
      setDeliveries(Array.isArray(del)?del:[])
      setPallet(pal.pallet||[])
      setSetup(s||{})
      setLoading(false)
    }).catch(()=>setLoading(false))
    const t=setInterval(()=>
      fetch('/api/pallet/').then(r=>r.ok?r.json():{pallet:[]}).then(d=>setPallet(d.pallet||[]))
    ,15000)
    return()=>clearInterval(t)
  },[])

  const now   = new Date()
  const DAYS  = ['Domenica','Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']
  const MONTHS= ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno','Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']
  const dayLabel = `${DAYS[now.getDay()]} ${now.getDate()} ${MONTHS[now.getMonth()]} ${now.getFullYear()}`

  // ── Pallet helpers ──────────────────────────────────────────────────────
  function palletInfo(num){
    const pal = pallet.find(p=>p.numero===num)
    if(!pal?.progetto_id) return null
    const proj = projects.find(p=>p.id===pal.progetto_id)
    if(!proj) return null
    const pgms = (proj.steps||[]).flatMap(s=>(s.tasks||[])
      .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
      .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm')))
    const tot  = pgms.length
    const done = pgms.filter(p=>p.stato==='completato').length
    const pct  = tot?Math.round(done/tot*100):0
    return {proj, pal, pct, done, tot,
      daFare:  pgms.filter(p=>p.stato==='da_fare').length,
      inMac:   pgms.filter(p=>p.stato==='in_macchina').length}
  }

  function palletColors(num){
    const pal = pallet.find(p=>p.numero===num)
    const stato = (pal?.stato||'').toLowerCase().replace('_',' ')
    const info  = palletInfo(num)
    if(stato==='in lavorazione') return {bg:'#dbeafe',fg:'#0d2d5e',border:'#1D5FAD',label:'IN LAV.'}
    if(info?.pct>=100||stato==='finito') return {bg:'#dcfce7',fg:'#14532d',border:'#16a34a',label:'FINITO'}
    if(info) return {bg:'#fefce8',fg:'#854d0e',border:'#eab308',label:'GREZZO'}
    return {bg:'#f1f5f9',fg:'#94a3b8',border:'#e2e8f0',label:'VUOTO'}
  }

  // ── Progetto IN LAVORAZIONE ─────────────────────────────────────────────
  const palletLav    = pallet.find(p=>(p.stato||'').toLowerCase().replace('_',' ')==='in lavorazione')
  const progettoLav  = palletLav?projects.find(p=>p.id===palletLav.progetto_id):null
  const lavInfo      = progettoLav?palletInfo(palletLav.numero):null

  // ── Metriche turno ──────────────────────────────────────────────────────
  const allPgm   = projects.flatMap(p=>(p.steps||[]).flatMap(s=>(s.tasks||[])
    .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
    .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm'))))
  const daFare   = allPgm.filter(p=>p.stato==='da_fare').length
  const inMac    = allPgm.filter(p=>p.stato==='in_macchina').length
  const oggiStr  = now.toDateString()
  const completatiOggi = allPgm.filter(p=>{
    if(p.stato!=='completato'||!p.tempoFine) return false
    try{
      const raw=p.tempoFine; const parts=raw.split(' ')
      const dp=parts[0].split('/'); const d=new Date(dp[2],dp[1]-1,dp[0])
      return d.toDateString()===oggiStr
    }catch{return false}
  }).length

  // ── Scadenze ────────────────────────────────────────────────────────────
  const conScadenza = projects
    .map(p=>({p, d:deliveries.find(d=>d.projectId===p.id), pNum:pallet.find(x=>x.progetto_id===p.id)?.numero}))
    .filter(({d})=>d?.dueDate&&!d.delivered)
    .map(({p,d,pNum})=>({p, days:daysUntil(d.dueDate), pNum}))
    .sort((a,b)=>a.days-b.days)
  const critici = conScadenza.filter(x=>x.days!==null&&x.days<=0).length

  // ── Utensili con problemi ───────────────────────────────────────────────
  const utensiliProblema = (()=>{
    const map={}
    ;(setup.non_utilizzati||[]).filter(u=>u.provenienza==='richiesto_da_progetto').forEach(u=>{
      map[u.alias]={alias:u.alias,tipo:'mancante',label:'MANCANTE',color:'#dc2626',
        bg:'#fef2f2',border:'#fca5a5',detail:(u.progetti||[]).map(r=>r.progetto).join(', ')}
    })
    ;(setup.da_montare||[]).forEach(u=>{
      if(!map[u.alias]) map[u.alias]={alias:u.alias,tipo:'da_montare',label:'DA MONTARE',
        color:'#d97706',bg:'#fffbeb',border:'#fcd34d',detail:`pos. ${u.posizione||'—'}`}
    })
    ;(setup.fin_vita||[]).forEach(u=>{
      const pct=typeof u.life_percent==='number'?u.life_percent:null
      if(!map[u.alias]) map[u.alias]={alias:u.alias,tipo:'fin_vita',
        label:pct!==null?`${pct.toFixed(0)}%`:'FINE VITA',
        color:'#c2410c',bg:'#fff7ed',border:'#fdba74',detail:`pos. ${u.posizione||'—'}`}
    })
    ;(setup.previsione_vita?.utensili_critici||[]).forEach(u=>{
      if(!map[u.alias]) map[u.alias]={alias:u.alias,tipo:'rischio',
        label:`pgm ${u.programma_critico||'?'}`,
        color:'#7c3aed',bg:'#f5f3ff',border:'#c4b5fd',detail:u.progetto||''}
    })
    return Object.values(map).sort((a,b)=>({mancante:0,da_montare:1,fin_vita:2,rischio:3}[a.tipo]||9)-({mancante:0,da_montare:1,fin_vita:2,rischio:3}[b.tipo]||9))
  })()

  if(loading) return(
    <div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center',
      background:'#eef2f7',fontSize:14,color:'#94a3b8'}}>Caricamento…</div>
  )

  return(
    <div style={{flex:1,overflowY:'auto',background:'#eef2f7',fontFamily:'var(--font-display)'}}>
      {/* Header */}
      <div style={{background:'#fff',borderBottom:'1px solid #e2e8f0',padding:'12px 24px',
        display:'flex',alignItems:'baseline',gap:12}}>
        <span style={{fontSize:20,fontWeight:800,color:'#0d2d5e'}}>Cruscotto turno</span>
        <span style={{fontSize:13,color:'#94a3b8'}}>{dayLabel}</span>
      </div>

      {/* Body — 3 colonne */}
      <div style={{display:'grid',gridTemplateColumns:'300px 1fr 210px',gap:16,
        padding:'16px 20px',alignItems:'start'}}>

        {/* ── COL 1: PALLET ─────────────────────────────────────────── */}
        <div style={{display:'flex',flexDirection:'column',gap:10}}>
          <div style={{fontSize:11,fontWeight:800,letterSpacing:'0.08em',color:'#0d2d5e'}}>PALLET</div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
            {[1,2,3,4,5,6].map(n=>{
              const info = palletInfo(n)
              const c    = palletColors(n)
              const isLav= c.label==='IN LAV.'
              return(
                <div key={n}
                  onClick={info?()=>nav('/progetti',{state:{openId:info.proj.id}}):undefined}
                  style={{background:c.bg,border:`2px solid ${c.border}`,borderRadius:10,
                    padding:'10px 12px',cursor:info?'pointer':'default',
                    minHeight:115,display:'flex',flexDirection:'column',
                    justifyContent:'space-between',transition:'box-shadow 0.15s'}}
                  onMouseEnter={e=>{if(info)e.currentTarget.style.boxShadow='0 4px 12px rgba(0,0,0,0.1)'}}
                  onMouseLeave={e=>e.currentTarget.style.boxShadow='none'}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                    <span style={{fontSize:26,fontWeight:900,color:c.fg,lineHeight:1}}>P{n}</span>
                    {isLav&&<span style={{fontSize:8,fontWeight:800,color:'#1D5FAD',
                      background:'#eff6ff',padding:'2px 6px',borderRadius:4,letterSpacing:1}}>● LIVE</span>}
                  </div>
                  {info?(
                    <div>
                      <div style={{fontSize:11,fontWeight:800,color:c.fg,
                        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',marginBottom:4}}>
                        {info.proj.name}
                      </div>
                      <div style={{height:4,background:'rgba(0,0,0,0.1)',borderRadius:2,overflow:'hidden',marginBottom:3}}>
                        <div style={{height:'100%',width:`${info.pct}%`,
                          background:info.proj.color||'#1D5FAD',borderRadius:2}}/>
                      </div>
                      <div style={{display:'flex',justifyContent:'space-between'}}>
                        <span style={{fontSize:9,color:c.fg,opacity:0.7}}>{info.done}/{info.tot} pgm</span>
                        <span style={{fontSize:11,fontWeight:800,color:c.fg}}>{info.pct}%</span>
                      </div>
                      <div style={{fontSize:8,fontWeight:700,color:c.fg,letterSpacing:1,marginTop:2,opacity:0.8}}>
                        {c.label}
                      </div>
                    </div>
                  ):(
                    <div style={{fontSize:10,fontWeight:600,color:c.fg,letterSpacing:1}}>VUOTO</div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* ── COL 2: PROGETTO ATTIVO + SCADENZE + UTENSILI ────────────── */}
        <div style={{display:'flex',flexDirection:'column',gap:12}}>

          {/* Progetto in lavorazione */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'14px 18px'}}>
            <div style={{fontSize:11,fontWeight:800,letterSpacing:'0.08em',color:'#0d2d5e',marginBottom:10}}>
              PROGETTO IN LAVORAZIONE
            </div>
            {progettoLav&&lavInfo?(
              <div style={{cursor:'pointer'}} onClick={()=>nav('/progetti',{state:{openId:progettoLav.id}})}>
                <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
                  <div style={{width:10,height:10,borderRadius:'50%',
                    background:progettoLav.color||'#1D5FAD',flexShrink:0}}/>
                  <span style={{fontSize:16,fontWeight:800,color:'#0d2d5e',flex:1,
                    overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                    {progettoLav.name}
                  </span>
                  <span style={{fontSize:11,fontWeight:700,color:'#fff',background:'#1D5FAD',
                    padding:'2px 8px',borderRadius:6,flexShrink:0}}>P{palletLav.numero}</span>
                </div>
                <div style={{height:8,background:'#e2e8f0',borderRadius:4,overflow:'hidden',marginBottom:6}}>
                  <div style={{height:'100%',width:`${lavInfo.pct}%`,
                    background:progettoLav.color||'#1D5FAD',borderRadius:4,transition:'width 0.4s'}}/>
                </div>
                <div style={{display:'flex',gap:20}}>
                  <span style={{fontSize:12,color:'#475569'}}>
                    <b style={{color:'#0d2d5e'}}>{lavInfo.done}</b>/{lavInfo.tot} completati
                  </span>
                  <span style={{fontSize:12,color:'#475569'}}>
                    <b style={{color:'#1D5FAD'}}>{lavInfo.inMac}</b> in macchina
                  </span>
                  <span style={{fontSize:13,fontWeight:800,color:progettoLav.color||'#1D5FAD',marginLeft:'auto'}}>
                    {lavInfo.pct}%
                  </span>
                </div>
              </div>
            ):(
              <div style={{color:'#94a3b8',fontSize:13,fontStyle:'italic'}}>
                Nessun pallet in lavorazione — premi Avvia nella pagina Macchina
              </div>
            )}
          </div>

          {/* Scadenze */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'14px 18px'}}>
            <div style={{fontSize:11,fontWeight:800,letterSpacing:'0.08em',color:'#0d2d5e',marginBottom:10}}>
              SCADENZE PROGETTI
              {conScadenza.length>0&&<span style={{marginLeft:8,fontSize:11,
                color:'#94a3b8',fontWeight:500}}>{conScadenza.length} totali</span>}
            </div>
            {conScadenza.length===0?(
              <div style={{color:'#94a3b8',fontSize:13,fontStyle:'italic'}}>Nessun progetto con scadenza impostata</div>
            ):(
              <div style={{display:'flex',flexDirection:'column',gap:5}}>
                {conScadenza.map(({p,days,pNum})=>{
                  const over=days<0,today=days===0,soon=days>0&&days<=3
                  const color=over?'#dc2626':today?'#d97706':soon?'#c2410c':'#475569'
                  const bg=over?'#fef2f2':today?'#fffbeb':soon?'#fff7ed':'#f8fafc'
                  const badge=over?`${Math.abs(days)}gg fa`:today?'OGGI':`${days}gg`
                  return(
                    <div key={p.id} onClick={()=>nav('/progetti',{state:{openId:p.id}})}
                      style={{display:'flex',alignItems:'center',gap:10,background:bg,
                        borderRadius:8,padding:'7px 12px',cursor:'pointer',
                        border:`1px solid ${color}33`}}>
                      <div style={{width:7,height:7,borderRadius:'50%',background:color,flexShrink:0}}/>
                      <span style={{fontSize:12,fontWeight:700,color:'#1e293b',flex:1,
                        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{p.name}</span>
                      {pNum&&<span style={{fontSize:10,fontWeight:700,color:'#0d2d5e',
                        background:'#eff6ff',padding:'1px 6px',borderRadius:4,flexShrink:0}}>P{pNum}</span>}
                      <span style={{fontSize:11,fontWeight:800,color,flexShrink:0,
                        background:'#fff',padding:'1px 8px',borderRadius:10,
                        border:`1px solid ${color}44`}}>{badge}</span>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Utensili con problemi */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'14px 18px'}}>
            <div style={{fontSize:11,fontWeight:800,letterSpacing:'0.08em',color:'#0d2d5e',marginBottom:10}}>
              UTENSILI — ATTENZIONE
              {utensiliProblema.length>0?(
                <span style={{marginLeft:8,fontSize:11,fontWeight:800,color:'#dc2626',
                  background:'#fef2f2',padding:'1px 8px',borderRadius:10}}>
                  {utensiliProblema.length}
                </span>
              ):(
                <span style={{marginLeft:8,fontSize:11,color:'#94a3b8',fontWeight:400}}>
                  — in attesa dati
                </span>
              )}
            </div>
            {utensiliProblema.length===0?(
              <div style={{color:'#22c55e',fontSize:13,fontWeight:600}}>✓ Nessun problema rilevato</div>
            ):(
              <div style={{display:'flex',flexDirection:'column',gap:4}}>
                {utensiliProblema.map(u=>(
                  <div key={u.alias}
                    style={{display:'flex',alignItems:'center',gap:10,
                      background:u.bg,border:`1px solid ${u.border}`,
                      borderRadius:8,padding:'7px 12px'}}>
                    <span style={{fontSize:10,fontWeight:800,color:u.color,
                      background:'#fff',padding:'1px 7px',borderRadius:4,
                      border:`1px solid ${u.border}`,flexShrink:0,
                      minWidth:65,textAlign:'center'}}>{u.label}</span>
                    <span style={{fontSize:12,fontWeight:700,color:'#1e293b',
                      fontFamily:'monospace',flex:1,
                      overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{u.alias}</span>
                    {u.detail&&<span style={{fontSize:10,color:u.color,opacity:0.8,
                      flexShrink:0,maxWidth:150,overflow:'hidden',
                      textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{u.detail}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── COL 3: METRICHE ────────────────────────────────────────── */}
        <div style={{display:'flex',flexDirection:'column',gap:10}}>
          <div style={{fontSize:11,fontWeight:800,letterSpacing:'0.08em',color:'#0d2d5e'}}>METRICHE TURNO</div>
          {[
            {val:daFare,         label:'Da fare',         sub:`${projects.length} lavori attivi`, color:'#0d2d5e', bg:'#eff6ff'},
            {val:inMac,          label:'In macchina',     sub:'programmi attivi',                 color:'#1D5FAD', bg:'#dbeafe'},
            {val:completatiOggi, label:'Completati oggi', sub:'nel turno corrente',               color:'#166534', bg:'#dcfce7'},
            {val:critici,        label:'Critici',          sub:'scaduti o oggi',                  color:'#dc2626', bg:'#fef2f2'},
          ].map(({val,label,sub,color,bg})=>(
            <div key={label} style={{background:bg,borderRadius:10,padding:'14px 16px'}}>
              <div style={{fontSize:32,fontWeight:800,color,lineHeight:1,marginBottom:2}}>{val}</div>
              <div style={{fontSize:12,fontWeight:700,color,marginBottom:2}}>{label}</div>
              <div style={{fontSize:10,color,opacity:0.7}}>{sub}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}
