// Home.jsx — Pallet in primo piano
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

const T = {
  bg:'#eef2f7', surface:'#ffffff', surface2:'#f8fafc',
  border:'#e2e8f0', text:'#0f172a', textSub:'#475569', textMuted:'#94a3b8',
  accent:'#0d2d5e', green:'#2d8a55', greenBg:'#f0f9f4',
  red:'#c0392b', redBg:'#fdf4f4', blue:'#0d2d5e', blueBg:'#eef4fb',
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
      <div style={{padding:'28px 40px 40px',display:'flex',flexDirection:'column',gap:28}}>

        {/* ══ 1° PIANO — PALLET (protagonista) ══ */}
        <div>
          <div style={{fontSize:11,fontWeight:700,letterSpacing:'0.1em',color:T.textMuted,marginBottom:16}}>PALLET MACCHINA</div>
          <div style={{display:'grid',gridTemplateColumns:'repeat(3,1fr)',gap:16}}>
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
                  style={{background:bg,
                    border:`2px solid ${isUrg?'#e87070':empty?T.border:color+'55'}`,
                    borderRadius:16,padding:'20px 22px',cursor:pid?'pointer':'default',
                    minHeight:empty?80:130,opacity:empty?0.5:1,
                    transition:'all 0.15s',
                    boxShadow:pid?'0 2px 8px rgba(0,0,0,0.07)':'none'}}
                  onMouseEnter={e=>{if(pid)e.currentTarget.style.boxShadow='0 4px 16px rgba(0,0,0,0.13)'}}
                  onMouseLeave={e=>{e.currentTarget.style.boxShadow=pid?'0 2px 8px rgba(0,0,0,0.07)':'none'}}>
                  <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:nome?12:0}}>
                    <span style={{fontSize:32,fontWeight:900,color:empty?'#C8C5BE':color,lineHeight:1}}>P{n}</span>
                    <span style={{fontSize:12,fontWeight:700,color:empty?'#C8C5BE':color,
                      padding:'3px 10px',borderRadius:20,border:`1px solid ${empty?'transparent':color+'44'}`}}>
                      {stato}
                    </span>
                    {isUrg&&<span style={{marginLeft:'auto',fontSize:11,fontWeight:800,color:'#c0392b',
                      background:'#fdf4f4',padding:'3px 10px',borderRadius:20,flexShrink:0}}>
                      {days===0?'OGGI':`${days}gg`}
                    </span>}
                  </div>
                  {nome&&(
                    <>
                      <div style={{fontSize:16,fontWeight:800,color:T.text,marginBottom:10,
                        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{nome}</div>
                      {pct!==null&&(
                        <div style={{display:'flex',alignItems:'center',gap:10}}>
                          <div style={{flex:1,height:7,background:'rgba(0,0,0,0.08)',borderRadius:4,overflow:'hidden'}}>
                            <div style={{height:7,width:`${pct}%`,background:color,borderRadius:4,transition:'width 0.3s'}}/>
                          </div>
                          <span style={{fontSize:14,fontWeight:800,color,flexShrink:0}}>{pct}%</span>
                        </div>
                      )}
                    </>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* ══ 2° PIANO — Alert + Metriche ══ */}
        <div style={{display:'grid',gridTemplateColumns:'auto 1fr',gap:20,alignItems:'start'}}>

          {/* Metriche 2×2 */}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10,width:280}}>
            {[
              {val:daFare.length,   label:'Da fare',        sub:`${ip.length} lavori`, color:'#475569', bg:T.surface2},
              {val:inMac.length,    label:'In macchina',    sub:'pgm attivi',           color:'#0d2d5e', bg:'#eef4fb'},
              {val:ogg.length,      label:'Completati oggi',sub:`${comp.length} tot.`,  color:'#2d8a55', bg:'#f0f9f4'},
              {val:daM+fV,          label:'Critici',        sub:daM>0?`${daM} da montare`:'tutto ok',
               color:(daM+fV)>0?'#c0392b':'#2d8a55', bg:(daM+fV)>0?'#fdf4f4':'#f0f9f4'},
            ].map(({val,label,sub,color,bg})=>(
              <div key={label} style={{background:bg,borderRadius:12,padding:'14px 16px'}}>
                <div style={{fontSize:28,fontWeight:700,color,lineHeight:1,marginBottom:4}}>{val}</div>
                <div style={{fontSize:11,fontWeight:700,color,marginBottom:2}}>{label}</div>
                <div style={{fontSize:10,color:T.textMuted}}>{sub}</div>
              </div>
            ))}
          </div>

          {/* Alert urgenti */}
          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            {urgenti.map(p=>{
              const d=getDel(p.id);const days=daysUntil(d?.dueDate)
              const txt=days===0?'oggi':days<0?`scaduta ${Math.abs(days)}gg fa`:`tra ${days}gg`
              return(
                <div key={p.id} onClick={()=>apri(p.id)}
                  style={{display:'flex',alignItems:'center',gap:12,background:'#fdf4f4',
                    border:'1px solid #e8b4b4',borderRadius:10,padding:'10px 16px',cursor:'pointer'}}>
                  <div style={{width:8,height:8,borderRadius:'50%',background:'#c0392b',flexShrink:0}}/>
                  <span style={{fontSize:13,fontWeight:700,color:'#6b2929',flex:1}}>
                    {p.name} <span style={{fontWeight:400,color:'#c0392b'}}>— {txt}</span>
                  </span>
                  <span style={{fontSize:11,fontWeight:800,color:'#c0392b',background:'#fff',
                    padding:'2px 10px',borderRadius:20,border:'1px solid #e8b4b4',flexShrink:0}}>
                    {days===0?'OGGI':days<0?`${Math.abs(days)}gg fa`:`${days}gg`}
                  </span>
                </div>
              )
            })}
            {(daM>0||fV>0)&&(
              <div style={{display:'flex',alignItems:'center',gap:10,background:'#fdf6e3',
                border:'1px solid #e8d090',borderRadius:10,padding:'10px 16px'}}>
                <span style={{fontSize:15}}>🔧</span>
                {daM>0&&<span style={{fontSize:13,fontWeight:600,color:'#9a6b2e'}}>{daM} da montare</span>}
                {fV>0&&<span style={{fontSize:13,fontWeight:600,color:'#9a6b2e'}}>{fV} a fine vita</span>}
              </div>
            )}
          </div>
        </div>

        {/* ══ 3° PIANO — Lavori in corso (contesto) ══ */}
        <div>
          <div style={{fontSize:11,fontWeight:700,letterSpacing:'0.1em',color:T.textMuted,marginBottom:14,
            paddingTop:20,borderTop:`1px solid ${T.border}`}}>LAVORI IN CORSO</div>
          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            {ip.slice(0,8).map(p=>{
              const pct=getProgress(p)
              const d=getDel(p.id)
              const days=d&&d.dueDate&&!d.delivered?daysUntil(d.dueDate):null
              const pNum=pallet.find(x=>x.progetto_id===p.id)?.numero
              return(
                <div key={p.id} onClick={()=>apri(p.id)}
                  style={{display:'flex',alignItems:'center',gap:14,background:T.surface,
                    border:`1px solid ${T.border}`,borderRadius:10,padding:'11px 16px',
                    cursor:'pointer',borderLeft:`4px solid ${p.color||T.accent}88`,
                    transition:'box-shadow 0.15s'}}
                  onMouseEnter={e=>e.currentTarget.style.boxShadow='0 2px 8px rgba(0,0,0,0.09)'}
                  onMouseLeave={e=>e.currentTarget.style.boxShadow='none'}>
                  <div style={{flex:1,minWidth:0}}>
                    <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:5}}>
                      <span style={{fontSize:13,fontWeight:700,color:T.text,
                        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{p.name}</span>
                      {pNum&&<span style={{fontSize:10,fontWeight:700,color:'#0d2d5e',
                        background:'#eef4fb',padding:'2px 8px',borderRadius:8,flexShrink:0}}>P{pNum}</span>}
                    </div>
                    <div style={{height:4,background:T.surface2,borderRadius:2,overflow:'hidden'}}>
                      <div style={{height:4,width:`${pct}%`,background:p.color||T.accent,borderRadius:2}}/>
                    </div>
                  </div>
                  <div style={{textAlign:'right',flexShrink:0,minWidth:52}}>
                    <div style={{fontSize:13,fontWeight:800,color:pct===100?'#2d8a55':p.color||T.accent}}>{pct}%</div>
                    {days!==null&&<div style={{fontSize:10,fontWeight:700,
                      color:days<=3?'#c0392b':days<=7?'#9a6b2e':'#94a3b8'}}>
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
