// Home.jsx — Dashboard turno, layout B (no header, tutto in una schermata)
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const T = {
  bg:'#eef2f7', surface:'#ffffff', surface2:'#f8fafc',
  border:'#e2e8f0', text:'#0f172a', textSub:'#475569', textMuted:'#94a3b8',
  accent:'#0d2d5e', accentBg:'#e6f1fb',
  green:'#16a34a', greenBg:'#f0fdf4',
  red:'#dc2626', redBg:'#fef2f2',
  blue:'#0d2d5e', blueBg:'#e6f1fb',
}
function getProgress(project) {
  const all=(project.steps||[]).flatMap(s=>s.tasks||[])
  if(!all.length) return 0
  return Math.round(all.filter(t=>t.done).length/all.length*100)
}
function daysUntil(dateStr) {
  if(!dateStr) return null
  const today=new Date(); today.setHours(0,0,0,0)
  const target=new Date(dateStr); target.setHours(0,0,0,0)
  return Math.round((target-today)/86400000)
}

const STATO_COLOR={grezzo:'#b45309',finito:'#16a34a',guasto:'#dc2626',vuoto:'#94a3b8'}
const STATO_BG={grezzo:'#fef9c3',finito:'#f0fdf4',guasto:'#fef2f2',vuoto:'#f8fafc'}

export default function Home() {
  const nav = useNavigate()
  const [projects,    setProjects]    = useState([])
  const [deliveries,  setDeliveries]  = useState([])
  const [palletState, setPalletState] = useState([])
  const [setupData,   setSetupData]   = useState({})
  const [loading,     setLoading]     = useState(true)

  useEffect(() => {
    Promise.all([
      fetch('/api/progetti/').then(r=>r.ok?r.json():{projects:[]}),
      fetch('/api/progetti/deliveries').then(r=>r.ok?r.json():[]),
      fetch('/api/pallet/').then(r=>r.ok?r.json():{pallet:[]}),
      fetch('/api/progetti/analisi-setup/non-utilizzati').then(r=>r.ok?r.json():{}).catch(()=>({})),
    ]).then(([pd,del,pal,setup]) => {
      setProjects((pd.projects||[]).map(p=>({pallet_assegnato:null,...p})))
      setDeliveries(Array.isArray(del)?del:[])
      setPalletState(pal.pallet||[])
      setSetupData(setup||{})
      setLoading(false)
    }).catch(()=>setLoading(false))
    const t=setInterval(()=>{
      fetch('/api/pallet/').then(r=>r.ok?r.json():{pallet:[]}).then(d=>setPalletState(d.pallet||[]))
    },15000)
    return ()=>clearInterval(t)
  },[])

  const todayStr=new Date().toISOString().slice(0,10)
  const inProgress=projects.filter(p=>!p.archived&&getProgress(p)<100)
  const allPgm=inProgress.flatMap(p=>(p.steps||[]).flatMap(s=>s.tasks||[])
    .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
    .flatMap(t=>(t.programs||[]).filter(pr=>pr.tipoGruppo!=='ipm')))

  const pgmDaFare    = allPgm.filter(p=>p.stato==='da_fare')
  const pgmInMac     = allPgm.filter(p=>p.stato==='in_macchina')
  const pgmCompletati= allPgm.filter(p=>p.stato==='completato')
  const pgmOggi      = allPgm.filter(p=>(p.tempoFine||'').startsWith(todayStr))
  const daMontare    = (setupData?.da_montare||[]).length
  const fineVita     = (setupData?.fin_vita||[]).length

  function getDelivery(pid){return deliveries.find(d=>d.projectId===pid)||null}

  const urgenti=inProgress.filter(p=>{
    const d=getDelivery(p.id); const days=d&&d.dueDate&&!d.delivered?daysUntil(d.dueDate):null
    return days!==null&&days<=7
  }).sort((a,b)=>{
    const da=getDelivery(a.id); const db=getDelivery(b.id)
    return (daysUntil(da?.dueDate)||99)-(daysUntil(db?.dueDate)||99)
  })

  function apri(pid){sessionStorage.setItem('dmgdesk_apri_progetto_id',pid);nav('/progetti')}

  if(loading) return(
    <div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center',
      background:T.bg,color:T.textMuted,fontSize:14}}>Caricamento...</div>
  )

  return(
    <div style={{flex:1,overflowY:'auto',background:T.bg,fontFamily:'var(--font-display)',height:'100%'}}>
      <div style={{padding:'20px 32px',display:'flex',flexDirection:'column',gap:12}}>

      {/* ── Alert strip compresso ── */}
      {(urgenti.length>0||daMontare>0||fineVita>0)&&(
        <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>
          {urgenti.map(p=>{
            const d=getDelivery(p.id); const days=daysUntil(d?.dueDate)
            const dayTxt=days===0?'oggi':days<0?`${Math.abs(days)}gg fa`:`tra ${days}gg`
            return(
              <div key={p.id} onClick={()=>apri(p.id)}
                style={{display:'flex',alignItems:'center',gap:10,background:'#fef2f2',
                  border:'1px solid #fca5a5',borderRadius:8,padding:'7px 14px',
                  cursor:'pointer',flex:1,minWidth:200}}>
                <div style={{width:7,height:7,borderRadius:'50%',background:'#dc2626',flexShrink:0}}/>
                <span style={{fontSize:12,fontWeight:700,color:'#7f1d1d',flex:1}}>
                  {p.name} <span style={{fontWeight:400,color:'#dc2626'}}>— scadenza {dayTxt}</span>
                </span>
                <span style={{fontSize:11,fontWeight:800,color:'#dc2626',background:'#fff',
                  padding:'1px 8px',borderRadius:12,border:'1px solid #fca5a5',flexShrink:0}}>
                  {days===0?'OGGI':days<0?`${Math.abs(days)}gg fa`:`${days}gg`}
                </span>
              </div>
            )
          })}
          {(daMontare>0||fineVita>0)&&(
            <div style={{display:'flex',alignItems:'center',gap:10,background:'#fef9c3',
              border:'1px solid #fcd34d',borderRadius:8,padding:'7px 14px',flexShrink:0}}>
              <span style={{fontSize:12,fontWeight:700,color:'#b45309'}}>🔧</span>
              {daMontare>0&&<span style={{fontSize:12,color:'#b45309'}}>{daMontare} da montare</span>}
              {fineVita>0&&<span style={{fontSize:12,color:'#b45309'}}>{fineVita} a fine vita</span>}
            </div>
          )}
        </div>
      )}

      {/* ── Pallet 3×2 compatti ── */}
      <div>
        <div style={{fontSize:10,fontWeight:700,letterSpacing:'0.08em',color:T.textMuted,marginBottom:8}}>PALLET MACCHINA</div>
        <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:8}}>
          {[1,2,3,4,5,6].map(n=>{
            const pd=palletState.find(x=>x.numero===n)||{}
            const stato=(pd.stato||'vuoto').toLowerCase()
            const nome=pd.progetto_nome||''
            const pid=pd.progetto_id
            const proj=pid?inProgress.find(x=>x.id===pid):null
            const pct=proj?getProgress(proj):null
            const d=proj?getDelivery(proj.id):null
            const days=d&&d.dueDate&&!d.delivered?daysUntil(d.dueDate):null
            const isUrgent=days!==null&&days<=3
            const color=STATO_COLOR[stato]||'#94a3b8'
            const bg=STATO_BG[stato]||'#f8fafc'
            const isEmpty=stato==='vuoto'&&!nome
            return(
              <div key={n} onClick={pid?()=>apri(pid):undefined}
                style={{background:bg,border:`1.5px solid ${isUrgent?'#dc2626':isEmpty?T.border:color+'66'}`,
                  borderRadius:10,padding:'10px 12px',cursor:pid?'pointer':'default',
                  minHeight:isEmpty?52:90,transition:'all 0.15s',opacity:isEmpty?0.6:1}}>
                <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:nome?5:0}}>
                  <span style={{fontSize:18,fontWeight:900,color:isEmpty?'#C8C5BE':color,lineHeight:1}}>P{n}</span>
                  <span style={{fontSize:9,fontWeight:700,color:isEmpty?'#C8C5BE':color,
                    padding:'1px 6px',borderRadius:8,border:`1px solid ${isEmpty?'transparent':color+'44'}`}}>
                    {stato}
                  </span>
                  {isUrgent&&<span style={{marginLeft:'auto',fontSize:9,fontWeight:800,color:'#dc2626',
                    background:'#fef2f2',padding:'1px 6px',borderRadius:8,flexShrink:0}}>
                    {days===0?'OGGI':`${days}gg`}
                  </span>}
                </div>
                {nome&&(
                  <>
                    <div style={{fontSize:12,fontWeight:800,color:T.text,marginBottom:4,
                      overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{nome}</div>
                    {pct!==null&&(
                      <div style={{display:'flex',alignItems:'center',gap:6}}>
                        <div style={{flex:1,height:4,background:'rgba(0,0,0,0.08)',borderRadius:2,overflow:'hidden'}}>
                          <div style={{height:4,width:`${pct}%`,background:color,borderRadius:2}}/>
                        </div>
                        <span style={{fontSize:11,fontWeight:800,color,flexShrink:0}}>{pct}%</span>
                      </div>
                    )}
                  </>
                )}
              </div>
            )
          })}
        </div>
      </div>

      {/* ── Metriche + Lavori affiancati ── */}
      <div style={{display:'grid',gridTemplateColumns:'auto 1fr',gap:16,alignItems:'start',flex:1,minHeight:0}}>

        {/* Metriche 2×2 */}
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,width:260}}>
          {[
            {val:pgmDaFare.length,    label:'Da fare',        sub:`${inProgress.length} lavori`, color:'#475569', bg:T.surface2},
            {val:pgmInMac.length,     label:'In macchina',    sub:'pgm attivi',    color:'#0d2d5e', bg:'#e6f1fb'},
            {val:pgmOggi.length,      label:'Completati oggi',sub:`${pgmCompletati.length} tot.`,color:'#16a34a', bg:'#f0fdf4'},
            {val:daMontare+fineVita,  label:'Utensili critici',sub:daMontare>0?`${daMontare} da montare`:'tutto ok',
             color:daMontare+fineVita>0?'#dc2626':'#16a34a',bg:daMontare+fineVita>0?'#fef0ee':'#f0fdf4'},
          ].map(({val,label,sub,color,bg})=>(
            <div key={label} style={{background:bg,borderRadius:8,padding:'10px 12px'}}>
              <div style={{fontSize:22,fontWeight:700,color,lineHeight:1,marginBottom:2}}>{val}</div>
              <div style={{fontSize:10,fontWeight:700,color,marginBottom:1}}>{label}</div>
              <div style={{fontSize:9,color:T.textMuted}}>{sub}</div>
            </div>
          ))}
        </div>

        {/* Lavori in corso */}
        <div style={{display:'flex',flexDirection:'column',gap:1}}>
          <div style={{fontSize:10,fontWeight:700,letterSpacing:'0.08em',color:T.textMuted,marginBottom:6}}>LAVORI IN CORSO</div>
          {inProgress.slice(0,8).map(p=>{
            const pct=getProgress(p)
            const d=getDelivery(p.id)
            const days=d&&d.dueDate&&!d.delivered?daysUntil(d.dueDate):null
            const pNum=palletState.find(x=>x.progetto_id===p.id)?.numero
            return(
              <div key={p.id} onClick={()=>apri(p.id)}
                style={{display:'flex',alignItems:'center',gap:10,background:T.surface,
                  border:`1px solid ${T.border}`,borderRadius:8,padding:'7px 12px',
                  cursor:'pointer',borderLeft:`3px solid ${p.color||T.accent}`,marginBottom:4}}>
                <div style={{flex:1,minWidth:0}}>
                  <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:3}}>
                    <span style={{fontSize:12,fontWeight:700,color:T.text,
                      overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{p.name}</span>
                    {pNum&&<span style={{fontSize:9,fontWeight:700,color:'#0d2d5e',
                      background:'#e6f1fb',padding:'1px 6px',borderRadius:6,flexShrink:0}}>P{pNum}</span>}
                  </div>
                  <div style={{height:3,background:T.surface2,borderRadius:2,overflow:'hidden'}}>
                    <div style={{height:3,width:`${pct}%`,background:p.color||T.accent,borderRadius:2}}/>
                  </div>
                </div>
                <div style={{textAlign:'right',flexShrink:0,minWidth:48}}>
                  <div style={{fontSize:12,fontWeight:800,color:pct===100?'#16a34a':p.color||T.accent}}>{pct}%</div>
                  {days!==null&&<div style={{fontSize:9,fontWeight:700,
                    color:days<=3?'#dc2626':days<=7?'#b45309':'#94a3b8'}}>
                    {days===0?'oggi':days<0?`${Math.abs(days)}gg fa`:`${days}gg`}
                  </div>}
                </div>
              </div>
            )
          })}
        </div>
      </div>

    </div>
    </div>
  )
}
