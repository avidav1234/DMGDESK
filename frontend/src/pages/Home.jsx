// Home.jsx — Dashboard turno, layout areoso
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const T = {
  bg:'#eef2f7', surface:'#ffffff', surface2:'#f8fafc',
  border:'#e2e8f0', text:'#0f172a', textSub:'#475569', textMuted:'#94a3b8',
  accent:'#0d2d5e', accentBg:'#eef4fb',
  green:'#16a34a', greenBg:'#eef8f2',
  red:'#dc2626', redBg:'#fdf4f4',
  blue:'#0d2d5e', blueBg:'#eef4fb',
}
function getProgress(p){const a=(p.steps||[]).flatMap(s=>s.tasks||[]);if(!a.length)return 0;return Math.round(a.filter(t=>t.done).length/a.length*100)}
function daysUntil(d){if(!d)return null;const t=new Date();t.setHours(0,0,0,0);const g=new Date(d);g.setHours(0,0,0,0);return Math.round((g-t)/86400000)}

const STATO_COLOR={grezzo:'#b07030',finito:'#2d8a55',guasto:'#c0392b',vuoto:'#94a3b8'}
const STATO_BG   ={grezzo:'#fdf8ee',finito:'#f0f9f4',guasto:'#fdf2f2',vuoto:'#f8fafc'}

export default function Home(){
  const nav=useNavigate()
  const [projects,setProjects]=useState([])
  const [deliveries,setDeliveries]=useState([])
  const [pallet,setPallet]=useState([])
  const [setup,setSetup]=useState({})
  const [loading,setLoading]=useState(true)

  useEffect(()=>{
    Promise.all([
      fetch('/api/progetti/').then(r=>r.ok?r.json():{projects:[]}),
      fetch('/api/progetti/deliveries').then(r=>r.ok?r.json():[]),
      fetch('/api/pallet/').then(r=>r.ok?r.json():{pallet:[]}),
      fetch('/api/progetti/analisi-setup/non-utilizzati').then(r=>r.ok?r.json():{}).catch(()=>({})),
    ]).then(([pd,del,pal,s])=>{
      setProjects((pd.projects||[]).map(p=>({pallet_assegnato:null,...p})))
      setDeliveries(Array.isArray(del)?del:[])
      setPallet(pal.pallet||[])
      setSetup(s||{})
      setLoading(false)
    }).catch(()=>setLoading(false))
    const t=setInterval(()=>fetch('/api/pallet/').then(r=>r.ok?r.json():{pallet:[]}).then(d=>setPallet(d.pallet||[])),15000)
    return()=>clearInterval(t)
  },[])

  const today=new Date().toISOString().slice(0,10)
  const ip=projects.filter(p=>!p.archived&&getProgress(p)<100)
  const pgm=ip.flatMap(p=>(p.steps||[]).flatMap(s=>s.tasks||[]).filter(t=>t.text?.trim().toLowerCase()==='fresatura').flatMap(t=>(t.programs||[]).filter(x=>x.tipoGruppo!=='ipm')))
  const daFare=pgm.filter(x=>x.stato==='da_fare')
  const inMac =pgm.filter(x=>x.stato==='in_macchina')
  const comp  =pgm.filter(x=>x.stato==='completato')
  const ogg   =pgm.filter(x=>(x.tempoFine||'').startsWith(today))
  const daM   =(setup?.da_montare||[]).length
  const fV    =(setup?.fin_vita||[]).length

  function getDel(pid){return deliveries.find(d=>d.projectId===pid)||null}
  const urgenti=ip.filter(p=>{const d=getDel(p.id);const dy=d&&d.dueDate&&!d.delivered?daysUntil(d.dueDate):null;return dy!==null&&dy<=7}).sort((a,b)=>(daysUntil(getDel(a.id)?.dueDate)||99)-(daysUntil(getDel(b.id)?.dueDate)||99))

  function apri(pid){sessionStorage.setItem('dmgdesk_apri_progetto_id',pid);nav('/progetti')}

  if(loading)return<div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center',background:T.bg,color:T.textMuted,fontSize:15}}>Caricamento...</div>

  return(
    <div style={{flex:1,overflowY:'auto',background:T.bg,fontFamily:'var(--font-display)',height:'100%'}}>
      <div style={{padding:'28px 40px 40px',display:'flex',flexDirection:'column',gap:24}}>

        {/* ── Alert strip ── */}
        {(urgenti.length>0||daM>0||fV>0)&&(
          <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>
            {urgenti.map(p=>{
              const d=getDel(p.id);const days=daysUntil(d?.dueDate)
              const txt=days===0?'oggi':days<0?`scaduta ${Math.abs(days)}gg fa`:`tra ${days}gg`
              return(
                <div key={p.id} onClick={()=>apri(p.id)}
                  style={{display:'flex',alignItems:'center',gap:12,background:'#fdf4f4',
                    border:'1px solid #fca5a5',borderRadius:10,padding:'10px 18px',
                    cursor:'pointer',flex:1,minWidth:220}}>
                  <div style={{width:9,height:9,borderRadius:'50%',background:'#dc2626',flexShrink:0}}/>
                  <span style={{fontSize:13,fontWeight:700,color:'#6b2929',flex:1}}>
                    {p.name} <span style={{fontWeight:400,color:'#dc2626'}}>— scadenza {txt}</span>
                  </span>
                  <span style={{fontSize:12,fontWeight:800,color:'#dc2626',background:'#fff',
                    padding:'3px 12px',borderRadius:20,border:'1px solid #fca5a5',flexShrink:0}}>
                    {days===0?'OGGI':days<0?`scaduta ${Math.abs(days)}gg fa`:`${days}gg`}
                  </span>
                </div>
              )
            })}
            {(daM>0||fV>0)&&(
              <div style={{display:'flex',alignItems:'center',gap:10,background:'#fdf6e3',
                border:'1px solid #fcd34d',borderRadius:10,padding:'10px 18px',flexShrink:0}}>
                <span style={{fontSize:16}}>🔧</span>
                {daM>0&&<span style={{fontSize:13,fontWeight:600,color:'#9a6b2e'}}>{daM} da montare</span>}
                {fV>0&&<span style={{fontSize:13,fontWeight:600,color:'#9a6b2e'}}>{fV} a fine vita</span>}
              </div>
            )}
          </div>
        )}

        {/* ── Pallet 3×2 ── */}
        <div>
          <div style={{fontSize:11,fontWeight:700,letterSpacing:'0.1em',color:T.textMuted,marginBottom:14}}>PALLET MACCHINA</div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:14}}>
            {[1,2,3,4,5,6].map(n=>{
              const pd=pallet.find(x=>x.numero===n)||{}
              const stato=(pd.stato||'vuoto').toLowerCase()
              const nome=pd.progetto_nome||''
              const pid=pd.progetto_id
              const proj=pid?ip.find(x=>x.id===pid):null
              const pct=proj?getProgress(proj):null
              const d=proj?getDel(proj.id):null
              const days=d&&d.dueDate&&!d.delivered?daysUntil(d.dueDate):null
              const isUrg=days!==null&&days<=3
              const color=STATO_COLOR[stato]||'#94a3b8'
              const bg=STATO_BG[stato]||'#f8fafc'
              const empty=stato==='vuoto'&&!nome
              return(
                <div key={n} onClick={pid?()=>apri(pid):undefined}
                  style={{background:bg,border:`1.5px solid ${isUrg?'#e87070':empty?T.border:color+'44'}`,
                    borderRadius:14,padding:'16px 18px',cursor:pid?'pointer':'default',
                    minHeight:empty?70:120,opacity:empty?0.55:1,
                    transition:'all 0.15s',boxShadow:pid?'0 1px 4px rgba(0,0,0,0.06)':'none'}}>
                  <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:nome?10:0}}>
                    <span style={{fontSize:26,fontWeight:900,color:empty?'#C8C5BE':color,lineHeight:1}}>P{n}</span>
                    <span style={{fontSize:11,fontWeight:700,color:empty?'#C8C5BE':color,
                      padding:'2px 9px',borderRadius:20,border:`1px solid ${empty?'transparent':color+'44'}`}}>
                      {stato}
                    </span>
                    {isUrg&&<span style={{marginLeft:'auto',fontSize:11,fontWeight:800,color:'#dc2626',
                      background:'#fdf4f4',padding:'2px 10px',borderRadius:20,flexShrink:0}}>
                      {days===0?'OGGI':`${days}gg`}
                    </span>}
                  </div>
                  {nome&&(
                    <>
                      <div style={{fontSize:15,fontWeight:800,color:T.text,marginBottom:8,
                        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{nome}</div>
                      {pct!==null&&(
                        <div style={{display:'flex',alignItems:'center',gap:8}}>
                          <div style={{flex:1,height:6,background:'rgba(0,0,0,0.08)',borderRadius:3,overflow:'hidden'}}>
                            <div style={{height:6,width:`${pct}%`,background:color,borderRadius:3,transition:'width 0.3s'}}/>
                          </div>
                          <span style={{fontSize:13,fontWeight:800,color,flexShrink:0}}>{pct}%</span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* ── Metriche + Lavori ── */}
        <div style={{display:'grid',gridTemplateColumns:'auto 1fr',gap:24,alignItems:'start'}}>

          {/* Metriche 2×2 */}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,width:300}}>
            {[
              {val:daFare.length,   label:'Da fare',        sub:`${ip.length} lavori attivi`,   color:'#475569', bg:T.surface2},
              {val:inMac.length,    label:'In macchina',    sub:'programmi attivi',              color:'#0d2d5e', bg:'#eef4fb'},
              {val:ogg.length,      label:'Completati oggi',sub:`${comp.length} totali`,         color:'#16a34a', bg:'#eef8f2'},
              {val:daM+fV,          label:'Utensili critici',sub:daM>0?`${daM} da montare`:'tutto ok',
               color:(daM+fV)>0?'#dc2626':'#16a34a', bg:(daM+fV)>0?'#fdf4f3':'#eef8f2'},
            ].map(({val,label,sub,color,bg})=>(
              <div key={label} style={{background:bg,borderRadius:12,padding:'16px 18px'}}>
                <div style={{fontSize:32,fontWeight:700,color,lineHeight:1,marginBottom:4}}>{val}</div>
                <div style={{fontSize:12,fontWeight:700,color,marginBottom:3}}>{label}</div>
                <div style={{fontSize:11,color:T.textMuted}}>{sub}</div>
              </div>
            ))}
          </div>

          {/* Lavori in corso */}
          <div>
            <div style={{fontSize:11,fontWeight:700,letterSpacing:'0.1em',color:T.textMuted,marginBottom:14}}>LAVORI IN CORSO</div>
            <div style={{display:'flex',flexDirection:'column',gap:8}}>
              {ip.slice(0,8).map(p=>{
                const pct=getProgress(p)
                const d=getDel(p.id)
                const days=d&&d.dueDate&&!d.delivered?daysUntil(d.dueDate):null
                const pNum=pallet.find(x=>x.progetto_id===p.id)?.numero
                return(
                  <div key={p.id} onClick={()=>apri(p.id)}
                    style={{display:'flex',alignItems:'center',gap:14,background:T.surface,
                      border:`1px solid ${T.border}`,borderRadius:10,padding:'12px 16px',
                      cursor:'pointer',borderLeft:`3px solid ${p.color||T.accent}88`,
                      boxShadow:'0 1px 3px rgba(0,0,0,0.05)',transition:'box-shadow 0.15s'}}
                    onMouseEnter={e=>e.currentTarget.style.boxShadow='0 3px 10px rgba(0,0,0,0.1)'}
                    onMouseLeave={e=>e.currentTarget.style.boxShadow='0 1px 3px rgba(0,0,0,0.05)'}>
                    <div style={{flex:1,minWidth:0}}>
                      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:5}}>
                        <span style={{fontSize:14,fontWeight:700,color:T.text,
                          overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{p.name}</span>
                        {pNum&&<span style={{fontSize:10,fontWeight:700,color:'#0d2d5e',
                          background:'#eef4fb',padding:'2px 8px',borderRadius:8,flexShrink:0}}>P{pNum}</span>}
                      </div>
                      <div style={{height:5,background:T.surface2,borderRadius:3,overflow:'hidden'}}>
                        <div style={{height:5,width:`${pct}%`,background:p.color||T.accent,borderRadius:3}}/>
                      </div>
                    </div>
                    <div style={{textAlign:'right',flexShrink:0,minWidth:56}}>
                      <div style={{fontSize:14,fontWeight:800,color:pct===100?'#16a34a':p.color||T.accent}}>{pct}%</div>
                      {days!==null&&<div style={{fontSize:11,fontWeight:700,
                        color:days<=3?'#dc2626':days<=7?'#9a6b2e':'#94a3b8'}}>
                        {days===0?'oggi':days<0?`scaduta ${Math.abs(days)}gg fa`:`${days}gg`}
                      </div>}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>

      </div>
    </div>
  )
}
