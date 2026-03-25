// Progetti.jsx — WorkTrack porting fedele COMPLETO per DMGDesk
// Persistenza su file via /api/progetti — identico all'app originale

import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

const API = '/api/progetti'

// ── Tema identico all'originale ────────────────────────────────────────────────
const T = {
  bg:'#F5F4F0', surface:'#FFFFFF', surface2:'#F0EEE8',
  border:'#D8D5CC', borderStrong:'#B0ADA4',
  text:'#1A1814', textSub:'#5A5750', textMuted:'#9A978E',
  accent:'#D4700A', accentBg:'#FFF4E8',
  green:'#1A7A4A', greenBg:'#E8F5EE',
  red:'#C0392B', redBg:'#FDECEA',
  blue:'#1D5FAD', blueBg:'#EAF1FB',
}
const COLORS = ['#D4700A','#1A7A4A','#1D5FAD','#C0392B','#8B2FC9','#C2185B','#0097A7','#E65100']
const ICONS  = ['🌐','📱','📣','🏗️','📦','🎯','🔧','📊','✍️','🚀','💡','🎨']
const DRAG_STEP = 'application/x-wt-step'
const DRAG_TASK = 'application/x-wt-task'

// ── Utils ──────────────────────────────────────────────────────────────────────
function uid() { return Math.random().toString(36).slice(2,9) }
function nowStr() { return new Date().toLocaleString('it-IT',{year:'numeric',month:'2-digit',day:'2-digit',hour:'2-digit',minute:'2-digit'}).replace(',','') }
function getProgress(project) {
  const all = (project.steps||[]).flatMap(s=>s.tasks||[])
  if(!all.length) return 0
  return Math.round(all.filter(t=>t.done).length/all.length*100)
}
function getNextTask(project) {
  for(const step of (project.steps||[])){
    const next=(step.tasks||[]).find(t=>!t.done)
    if(next) return {step,task:next}
  }
  return null
}
function reorder(arr,from,to){const r=[...arr];const[item]=r.splice(from,1);r.splice(to,0,item);return r}
function cloneTemplateToSteps(tmpl){
  return tmpl.steps.map(s=>({...s,id:uid(),tasks:s.tasks.map(t=>({...t,id:uid(),done:false,notes:[],note:'',doneAt:null}))}))
}
function daysUntil(dateStr){
  if(!dateStr) return null
  const today=new Date(); today.setHours(0,0,0,0)
  const target=new Date(dateStr); target.setHours(0,0,0,0)
  return Math.round((target-today)/86400000)
}
function deliveryUrgency(days){
  if(days===null) return {label:'Nessuna data',color:T.textMuted,bg:T.surface2,dot:'⚪',rank:4}
  if(days<0)     return {label:'SCADUTA',      color:'#fff',    bg:T.red,     dot:'💀',rank:0}
  if(days===0)   return {label:'OGGI',          color:'#fff',    bg:T.red,     dot:'🚨',rank:0}
  if(days<=3)    return {label:`${days}gg`,     color:T.red,     bg:T.redBg,   dot:'🔴',rank:1}
  if(days<=7)    return {label:`${days}gg`,     color:'#C2720A', bg:'#FFF0DC', dot:'🟠',rank:2}
  if(days<=21)   return {label:`${days}gg`,     color:T.accent,  bg:T.accentBg,dot:'🟡',rank:3}
  return               {label:`${days}gg`,     color:T.green,   bg:T.greenBg, dot:'🟢',rank:4}
}

// ── MPF parser ─────────────────────────────────────────────────────────────────
function parseMpfFile(filename,content){
  const lines=content.split(/\r?\n/)
  const get=(label)=>{const l=lines.find(l=>l.includes(label));return l?l.replace(/.*:\s*/,'').trim():''}
  const opLine=lines.find(l=>/N\d+;/.test(l)&&!l.includes('DIAMETER')&&!l.includes('TOOL COMMENT')&&!l.includes('CIMATRON')&&!l.includes('DOCUMENTO')&&!l.includes('UTENTE')&&!l.includes('POST')&&!l.includes('REVISIONE')&&!l.includes('DATA')&&!l.includes('N.UT')&&l.includes(';')&&l.replace(/N\d+;\s*/,'').trim().length>3)
  const tipoOp=opLine?opLine.replace(/N\d+;\s*/,'').trim():''
  const toolLine=lines.find(l=>l.includes('TOOL COMMENT:'))
  const utensile=toolLine?toolLine.replace(/.*TOOL COMMENT:\s*/,'').trim():''
  const diaLine=lines.find(l=>l.includes('DIAMETER:'))
  const diametro=diaLine?diaLine.replace(/.*DIAMETER:\s*/,'').replace(/CORNER.*/,'').trim():''
  const dataPost=get('DATA ESECUZIONE POST')
  const isIPM=/[_\-]IPM[_\-]/i.test(filename)||utensile.toUpperCase().includes('RENISHAW')
  const tipoGruppo=isIPM?'ipm':'fresatura'
  const baseName=filename.replace(/\.MPF$/i,'')
  const tokens=baseName.split('_')
  const ipmIdx=tokens.findIndex(t=>t.toUpperCase()==='IPM')
  const numPgm=ipmIdx>=0&&tokens[ipmIdx+1]?tokens[ipmIdx+1]:tokens[tokens.length-1]
  const fase=tokens.length>=3?tokens[tokens.length-(isIPM?3:2)]:''
  return{numPgm,fase,tipoOp,utensile,diametro,dataPost,filename,tipoGruppo}
}

const STATO_NEXT={da_fare:'in_macchina',in_macchina:'completato',completato:'da_fare'}
const STATO_CFG={
  da_fare:    {label:'Da fare',    short:'Da fare',    color:T.textMuted,bg:T.surface2,border:T.border,  dot:'○'},
  in_macchina:{label:'In macchina',short:'In macchina',color:'#1D5FAD',  bg:'#dbeafe', border:'#1D5FAD',dot:'⚙'},
  completato: {label:'Completato', short:'Fatto',      color:'#166534',  bg:'#dcfce7', border:'#166534',dot:'✓'},
}
const OPERATORI=['I.Dodon','Operatore 2','Operatore 3']
const PRIORITY={
  alta: {label:'Alta', color:'#C0392B',bg:'#FDECEA',dot:'🔴'},
  media:{label:'Media',color:'#D4700A',bg:'#FFF4E8',dot:'🟡'},
  bassa:{label:'Bassa',color:'#1A7A4A',bg:'#E8F5EE',dot:'🟢'},
}

// ── Shared UI ──────────────────────────────────────────────────────────────────
function ProgressBar({value,color}){
  return <div style={{height:6,background:T.surface2,borderRadius:3,overflow:'hidden'}}><div style={{height:'100%',width:`${value}%`,background:color||T.accent,borderRadius:3,transition:'width 0.3s'}}/></div>
}
function StatusBadge({progress}){
  const cfg=progress===100?{label:'✓ Completato',color:T.green,bg:T.greenBg}:progress>0?{label:`${progress}% — In corso`,color:T.accent,bg:T.accentBg}:{label:'Non iniziato',color:T.textMuted,bg:T.surface2}
  return <span style={{fontSize:12,fontWeight:700,color:cfg.color,background:cfg.bg,padding:'3px 10px',borderRadius:20,border:`1px solid ${cfg.color}33`}}>{cfg.label}</span>
}
function ConfirmDialog({message,onConfirm,onCancel}){
  return(
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.4)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:300}}>
      <div style={{background:T.surface,borderRadius:14,padding:28,maxWidth:420,border:`1px solid ${T.border}`,boxShadow:'0 8px 32px rgba(0,0,0,0.18)'}}>
        <p style={{fontSize:15,color:T.text,marginBottom:20}}>{message}</p>
        <div style={{display:'flex',gap:10,justifyContent:'flex-end'}}>
          <button onClick={onCancel} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:'8px 18px',cursor:'pointer',fontWeight:600}}>Annulla</button>
          <button onClick={onConfirm} style={{background:T.red,border:'none',borderRadius:8,color:'#fff',fontSize:14,padding:'8px 18px',cursor:'pointer',fontWeight:700}}>Conferma</button>
        </div>
      </div>
    </div>
  )
}
// ── ProgramRow ─────────────────────────────────────────────────────────────────
function ProgramRow({pgm,gruppo,onStato,onOperatore,onTempo,onRemove,toolStatus}){
  const[expanded,setExpanded]=useState(false)
  const[editTempo,setEditTempo]=useState(pgm.tempoStimato||'')
  const[editingT,setEditingT]=useState(false)
  const sc=STATO_CFG[pgm.stato]||STATO_CFG.da_fare
  const opClean=(pgm.tipoOp||'').replace(/[-–]\s*NESSUN TESTO\s*/gi,'').replace(/MISURAZIONE NEL PROCESSO[-–]?/gi,'MISURA ').trim()
  return(
    <div style={{borderBottom:`1px solid ${T.border}`,background:pgm.stato==='completato'?'#f0fdf4':pgm.stato==='in_macchina'?'#eff6ff':T.surface,opacity:pgm.stato==='completato'?0.75:1,transition:'background 0.15s'}}>
      <div style={{display:'flex',alignItems:'center',minHeight:38}}>
        <div onClick={()=>onStato(STATO_NEXT[pgm.stato])} title={`→ ${STATO_CFG[STATO_NEXT[pgm.stato]].label}`}
          style={{flexShrink:0,width:110,display:'flex',alignItems:'center',justifyContent:'center',gap:5,padding:'0 10px',cursor:'pointer',borderRight:`1px solid ${T.border}`,background:toolStatus==='mancante'?'#FEE2E2':toolStatus==='fin_vita'?'#FEF9C3':sc.bg,color:toolStatus==='mancante'?'#DC2626':toolStatus==='fin_vita'?'#D97706':sc.color,fontWeight:700,fontSize:12,userSelect:'none',alignSelf:'stretch',transition:'all 0.12s'}}>
          <span style={{fontSize:14}}>{sc.dot}</span>{sc.short}
        </div>
        <div style={{flexShrink:0,width:52,textAlign:'center',borderRight:`1px solid ${T.border}`,alignSelf:'stretch',display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',gap:2}}>
          <span style={{fontSize:13,fontWeight:800,color:gruppo.color,fontFamily:'monospace'}}>{pgm.numPgm}</span>
          {toolStatus&&toolStatus!=='ok'&&(()=>{
            const cfg={
              mancante: {dot:'✗',label:'MANCANTE',c:'#DC2626',bg:'#FEE2E2'},
              fin_vita: {dot:'⚠',label:'VITA BASSA',c:'#D97706',bg:'#FEF9C3'},
              disabilitato:{dot:'⊘',label:'DISAB.',c:'#7C3AED',bg:'#EDE9FE'}
            }
            const b=cfg[toolStatus]
            return b?<span style={{fontSize:9,fontWeight:800,color:b.c,background:b.bg,
              padding:'1px 4px',borderRadius:3,display:'block',lineHeight:1.3,
              whiteSpace:'nowrap'}}>{b.dot} {b.label}</span>:null
          })()}
        </div>
        <div style={{flexShrink:0,width:140,borderRight:`1px solid ${T.border}`,padding:'0 10px',alignSelf:'stretch',display:'flex',flexDirection:'column',justifyContent:'center'}}>
          <span style={{fontSize:12,fontWeight:700,color:T.text,fontFamily:'monospace',lineHeight:1.2}}>{pgm.utensile||'—'}</span>
          {pgm.diametro&&<span style={{fontSize:10,color:T.textMuted}}>Ø {pgm.diametro}</span>}
        </div>
        <div style={{flex:1,padding:'0 10px',alignSelf:'stretch',display:'flex',alignItems:'center',overflow:'hidden'}}>
          <span style={{fontSize:12,color:T.textSub,whiteSpace:'nowrap',overflow:'hidden',textOverflow:'ellipsis'}}>{opClean||'—'}</span>
        </div>
        {(pgm.tempoInizio||pgm.tempoFine)&&(
          <div style={{flexShrink:0,padding:'0 8px',borderLeft:`1px solid ${T.border}`,alignSelf:'stretch',display:'flex',flexDirection:'column',justifyContent:'center'}}>
            {pgm.tempoInizio&&<span style={{fontSize:10,color:'#1D5FAD',fontFamily:'monospace',whiteSpace:'nowrap'}}>▶ {pgm.tempoInizio}</span>}
            {pgm.tempoFine&&<span style={{fontSize:10,color:'#166534',fontFamily:'monospace',whiteSpace:'nowrap'}}>■ {pgm.tempoFine}</span>}
          </div>
        )}
        <div onClick={()=>setExpanded(v=>!v)} style={{flexShrink:0,width:32,borderLeft:`1px solid ${T.border}`,alignSelf:'stretch',display:'flex',alignItems:'center',justifyContent:'center',cursor:'pointer',color:T.textMuted,fontSize:11}}>{expanded?'▲':'▼'}</div>
      </div>
      {expanded&&(
        <div style={{padding:'12px 14px',background:T.surface2,borderTop:`1px solid ${T.border}`,display:'flex',flexWrap:'wrap',gap:16,alignItems:'flex-start'}}>
          <div>
            <div style={{fontSize:10,color:T.textMuted,fontWeight:700,letterSpacing:'0.06em',marginBottom:4}}>OPERATORE</div>
            <select value={pgm.operatore||''} onChange={e=>onOperatore(e.target.value)} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,color:pgm.operatore?T.text:T.textMuted,fontSize:12,padding:'4px 10px',outline:'none',cursor:'pointer'}}>
              <option value=''>— Seleziona</option>
              {OPERATORI.map(o=><option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          <div>
            <div style={{fontSize:10,color:T.textMuted,fontWeight:700,letterSpacing:'0.06em',marginBottom:4}}>TEMPO STIMATO</div>
            {editingT?(
              <div style={{display:'flex',gap:5}}>
                <input value={editTempo} onChange={e=>setEditTempo(e.target.value)} placeholder='es. 2h30m' autoFocus
                  style={{width:90,background:T.surface,border:'1.5px solid #1D5FAD44',borderRadius:6,padding:'4px 8px',color:T.text,fontSize:12,outline:'none'}}
                  onKeyDown={e=>{if(e.key==='Enter'){onTempo(editTempo);setEditingT(false)}if(e.key==='Escape')setEditingT(false)}}/>
                <button onClick={()=>{onTempo(editTempo);setEditingT(false)}} style={{background:'#1D5FAD',border:'none',borderRadius:5,color:'#fff',fontSize:11,fontWeight:700,padding:'4px 9px',cursor:'pointer'}}>OK</button>
              </div>
            ):(
              <button onClick={()=>setEditingT(true)} style={{background:'none',border:`1px dashed ${T.border}`,borderRadius:6,color:pgm.tempoStimato?T.text:T.textMuted,fontSize:12,padding:'4px 10px',cursor:'pointer'}}>⏱ {pgm.tempoStimato||'Aggiungi'}</button>
            )}
          </div>
          {pgm.dataPost&&<div><div style={{fontSize:10,color:T.textMuted,fontWeight:700,letterSpacing:'0.06em',marginBottom:4}}>DATA POST</div><div style={{fontSize:12,color:T.textSub,fontFamily:'monospace'}}>{pgm.dataPost}</div></div>}
          <div><div style={{fontSize:10,color:T.textMuted,fontWeight:700,letterSpacing:'0.06em',marginBottom:4}}>FILE</div><div style={{fontSize:11,color:T.textMuted,fontFamily:'monospace'}}>{pgm.filename}</div></div>
          <div style={{marginLeft:'auto'}}>
            <div style={{fontSize:10,color:T.textMuted,fontWeight:700,letterSpacing:'0.06em',marginBottom:4}}>STATO</div>
            <div style={{display:'flex',gap:4}}>
              {Object.entries(STATO_CFG).map(([key,s])=>(
                <button key={key} onClick={()=>onStato(key)} style={{background:pgm.stato===key?s.bg:'transparent',border:`1.5px solid ${pgm.stato===key?s.border:T.border}`,borderRadius:6,color:pgm.stato===key?s.color:T.textMuted,fontSize:11,fontWeight:700,padding:'3px 10px',cursor:'pointer'}}>{s.dot} {s.label}</button>
              ))}
              <button onClick={onRemove} style={{marginLeft:8,background:'none',border:`1px solid ${T.red}44`,borderRadius:6,color:T.red,fontSize:11,padding:'3px 8px',cursor:'pointer'}}>🗑 Rimuovi</button>
            </div>
          </div>
        </div>
      )}
    </div>
  )
}


// ── Classifica utensile rispetto a tools_machine ──────────────────────────────
// Ritorna: null (nessun alias/db), 'ok', 'fin_vita', 'disabilitato', 'mancante'
// Considera i gemelli (duplo): se il tool principale è disabilitato/worn
// ma esiste un gemello con stesso nome abilitato e vita ok → 'ok' o 'fin_vita'
function classifyTool(alias, toolsDB){
  if(!alias || !toolsDB) return null
  if(Object.keys(toolsDB).length === 0) return null  // db non ancora caricato
  const key = alias.toUpperCase().trim()

  // Raccoglie tutti i tool con questo alias (tool + gemelli)
  const tutti = Object.values(toolsDB).filter(t =>
    (t.name || '').toUpperCase().trim() === key
  )
  if(tutti.length === 0) return 'mancante'

  // Cerca il gemello migliore: abilitato, non worn, vita massima
  const abilitati = tutti.filter(t => t.is_enabled !== false && t.is_worn !== true)

  if(abilitati.length === 0) return 'disabilitato'  // tutti i gemelli sono KO

  // Tra gli abilitati, prendi quello con vita migliore
  const best = abilitati.reduce((a, b) => {
    const la = a.life_percent ?? 100
    const lb = b.life_percent ?? 100
    return la >= lb ? a : b
  })

  if(best.life_percent != null && best.life_percent < 15) return 'fin_vita'
  return 'ok'
}

// ── FresaturaPanel ─────────────────────────────────────────────────────────────
function FresaturaPanel({task,onUpdateTask,toolsDB,projectId}){
  const fileInputRef=useRef(null)
  const programs=Array.isArray(task.programs)?task.programs:[]
  const[expanded,setExpanded]=useState(false)
  const[collapsedGroups,setCollapsedGroups]=useState({ipm:true,fresatura:true})
  const TOOL_BADGE={
    ok:          {dot:'✓',color:'#166534',bg:'#dcfce7'},
    fin_vita:    {dot:'⚠',color:'#B45309',bg:'#FEF3C7'},
    disabilitato:{dot:'⊘',color:'#9333EA',bg:'#F3E8FF'},
    mancante:    {dot:'✗',color:'#C0392B',bg:'#FDECEA'},
  }
  const ipmPrograms=programs.filter(p=>p.tipoGruppo==='ipm')
  const fresPrograms=programs.filter(p=>p.tipoGruppo!=='ipm')
  const doneTotal=programs.filter(p=>p.stato==='completato').length
  const inMacchina=programs.filter(p=>p.stato==='in_macchina').length
  const total=programs.length
  const allDone=total>0&&doneTotal===total
  function updatePrograms(newPrograms){
    const allComplete=newPrograms.length>0&&newPrograms.every(p=>p.stato==='completato')
    onUpdateTask({...task,programs:newPrograms,done:allComplete,doneAt:allComplete?new Date().toISOString().slice(0,10):task.doneAt})
  }
  async function handleFileUpload(e){
    const files=Array.from(e.target.files)
    const parsed=[]
    for(const file of files){
      const text=await file.text()
      const info=parseMpfFile(file.name,text)
      if(!programs.find(p=>p.filename===info.filename))
        parsed.push({id:uid(),...info,stato:'da_fare',operatore:'',tempoStimato:'',tempoInizio:null,tempoFine:null})
    }
    if(parsed.length>0){
      const all=[...programs,...parsed].sort((a,b)=>{
        if(a.tipoGruppo!==b.tipoGruppo) return a.tipoGruppo==='ipm'?-1:1
        return a.numPgm.localeCompare(b.numPgm,undefined,{numeric:true})
      })
      updatePrograms(all)
    }
    e.target.value=''
  }
  function updatePgm(id,patch){
    updatePrograms(programs.map(p=>{
      if(p.id!==id) return p
      const next={...p,...patch}
      if(patch.stato==='in_macchina'&&!p.tempoInizio) next.tempoInizio=nowStr()
      if(patch.stato==='completato') next.tempoFine=nowStr()
      return next
    }))
  }
  const gruppi=[
    {key:'ipm',label:'Tastatura (IPM)',icon:'📏',color:'#8B2FC9',bgColor:'#F3E8FF',list:ipmPrograms},
    {key:'fresatura',label:'Fresatura',icon:'⚙️',color:'#1D5FAD',bgColor:'#E8F0FA',list:fresPrograms},
  ].filter(g=>g.list.length>0)
  return(
    <div style={{marginTop:8,background:T.surface,border:'1.5px solid #1D5FAD33',borderRadius:10,overflow:'hidden'}}>
      <div onClick={()=>setExpanded(v=>!v)} style={{display:'flex',alignItems:'center',gap:10,padding:'10px 14px',cursor:'pointer',background:'#E8F0FA',userSelect:'none'}}>
        <span style={{fontSize:15}}>⚙️</span>
        <span style={{fontSize:13,fontWeight:800,color:'#1D5FAD',flex:1}}>PROGRAMMI FRESATURA</span>
        {toolsDB&&(()=>{
          const issues=programs.filter(p=>p.stato==='in_macchina'&&p.utensile&&p.tipoGruppo!=='ipm'&&['mancante','fin_vita','disabilitato'].includes(classifyTool(p.utensile,toolsDB)))
          return issues.length>0?(
            <span style={{fontSize:11,fontWeight:700,color:'#C0392B',background:'#FDECEA',padding:'2px 8px',borderRadius:20,border:'1px solid #C0392B44'}}>
              ⚠ {issues.length} utensil{issues.length===1?'e':'i'} problematic{issues.length===1?'o':'i'}
            </span>
          ):null
        })()}
        {inMacchina>0&&<span style={{fontSize:11,fontWeight:700,color:'#1D5FAD',background:'#fff',padding:'2px 9px',borderRadius:20,border:'1px solid #1D5FAD44'}}>⚙ {inMacchina} in macchina</span>}
        {total>0&&<span style={{fontSize:12,fontWeight:700,color:allDone?'#166534':'#1D5FAD',background:allDone?'#dcfce7':'#fff',padding:'2px 10px',borderRadius:20,border:`1px solid ${allDone?'#166534':'#1D5FAD'}44`}}>{doneTotal}/{total} {allDone?'✓':'completati'}</span>}
        <span style={{fontSize:11,color:'#1D5FAD',fontWeight:700}}>{expanded?'▲':'▼'}</span>
      </div>
      {expanded&&(
        <div>
          <div style={{display:'flex',gap:10,alignItems:'center',padding:'10px 14px',borderBottom:`1px solid ${T.border}`}}>
            <input ref={fileInputRef} type='file' accept='.mpf,.MPF' multiple style={{display:'none'}} onChange={handleFileUpload}/>
            <button onClick={()=>fileInputRef.current.click()} style={{background:'#1D5FAD',border:'none',borderRadius:7,color:'#fff',fontWeight:700,fontSize:13,padding:'7px 14px',cursor:'pointer'}}>📂 Carica .mpf</button>
            {total>0&&<span style={{fontSize:12,color:T.textMuted}}>{ipmPrograms.length>0&&`📏 ${ipmPrograms.length} IPM · `}⚙️ {fresPrograms.length} fresatura</span>}
          </div>
          {total===0&&<div style={{textAlign:'center',padding:24,color:T.textMuted,fontSize:13}}>Nessun programma · clicca "Carica .mpf"</div>}
          {total>0&&(
            <div style={{display:'flex',background:T.surface2,borderBottom:`1px solid ${T.border}`,fontSize:10,fontWeight:700,color:T.textMuted,letterSpacing:'0.07em'}}>
              <div style={{width:110,padding:'5px 10px',borderRight:`1px solid ${T.border}`}}>STATO</div>
              <div style={{width:160,padding:'5px 10px',borderRight:`1px solid ${T.border}`}}>PROGRAMMA</div>
              <div style={{width:130,padding:'5px 10px',borderRight:`1px solid ${T.border}`}}>UTENSILE</div>
              <div style={{flex:1,padding:'5px 10px'}}>OPERAZIONE</div>
            </div>
          )}
          {gruppi.map(gruppo=>(
            <div key={gruppo.key}>
              {gruppi.length>1&&(
                <div onClick={()=>setCollapsedGroups(g=>({...g,[gruppo.key]:!g[gruppo.key]}))}
                  style={{display:'flex',alignItems:'center',gap:8,padding:'6px 14px',background:gruppo.bgColor,cursor:'pointer',userSelect:'none',borderBottom:`1px solid ${T.border}`}}>
                  <span style={{fontSize:12}}>{gruppo.icon}</span>
                  <span style={{fontSize:11,fontWeight:800,color:gruppo.color,flex:1,letterSpacing:'0.06em'}}>{gruppo.label.toUpperCase()}</span>
                  <span style={{fontSize:11,color:gruppo.color}}>{gruppo.list.filter(p=>p.stato==='completato').length}/{gruppo.list.length}</span>
                  <span style={{fontSize:10,color:gruppo.color}}>{collapsedGroups[gruppo.key]?'▼':'▲'}</span>
                </div>
              )}
              {(gruppi.length===1||!collapsedGroups[gruppo.key])&&gruppo.list.map(pgm=>(
                <ProgramRow key={pgm.id} pgm={pgm} gruppo={gruppo}
                  onStato={stato=>updatePgm(pgm.id,{stato})}
                  onOperatore={operatore=>updatePgm(pgm.id,{operatore})}
                  onTempo={tempoStimato=>updatePgm(pgm.id,{tempoStimato})}
                  onRemove={()=>updatePrograms(programs.filter(p=>p.id!==pgm.id))}
                  toolStatus={pgm.stato==='in_macchina'?classifyTool(pgm.utensile,toolsDB):null}/>
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

// ── UtensiliProgetto ───────────────────────────────────────────────────────────
function UtensiliProgetto({projectId}){
  const[data,setData]=useState(null)
  const[loading,setLoading]=useState(true)
  const[expanded,setExpanded]=useState(false)

  useEffect(()=>{
    if(!expanded)return
    setLoading(true)
    fetch(`/api/progetti/${projectId}/utensili-check`)
      .then(r=>r.ok?r.json():null)
      .then(d=>{setData(d);setLoading(false)})
      .catch(()=>setLoading(false))
  },[projectId,expanded])

  const CFG={
    ok:         {label:'In macchina',   color:'#166534',bg:'#dcfce7',dot:'✓'},
    fin_vita:   {label:'Fine vita <15%',color:'#B45309',bg:'#FEF3C7',dot:'⚠'},
    disabilitato:{label:'Disabilitato', color:'#9333EA',bg:'#F3E8FF',dot:'⊘'},
    scaffale:   {label:'A scaffale',    color:'#1D5FAD',bg:'#dbeafe',dot:'🏠'},
    smontato:   {label:'Smontato',      color:'#C2720A',bg:'#FFF0DC',dot:'📦'},
    mancante:   {label:'Non trovato',   color:'#C0392B',bg:'#FDECEA',dot:'✗'},
  }

  const hasIssues = data && (
    data.summary.mancante>0 || data.summary.fin_vita>0 ||
    data.summary.scaffale>0 || data.summary.smontato>0 || data.summary.disabilitato>0
  )

  return(
    <div style={{marginTop:12,border:`1.5px solid ${hasIssues&&expanded?'#C0392B33':'#D8D5CC'}`,borderRadius:10,overflow:'hidden'}}>
      <div onClick={()=>setExpanded(v=>!v)}
        style={{display:'flex',alignItems:'center',gap:10,padding:'10px 14px',cursor:'pointer',
          background:hasIssues?'#FFF4E8':'#F5F4F0',userSelect:'none'}}>
        <span style={{fontSize:14}}>🔧</span>
        <span style={{fontSize:13,fontWeight:800,color:'#1A1814',flex:1}}>UTENSILI RICHIESTI</span>
        {data&&<>
          <span style={{fontSize:11,fontWeight:700,color:'#166534',background:'#dcfce7',padding:'2px 8px',borderRadius:20}}>
            ✓ {data.summary.ok}
          </span>
          {data.summary.fin_vita>0&&<span style={{fontSize:11,fontWeight:700,color:'#B45309',background:'#FEF3C7',padding:'2px 8px',borderRadius:20}}>
            ⚠ {data.summary.fin_vita} vita bassa
          </span>}
          {(data.summary.scaffale+data.summary.smontato)>0&&<span style={{fontSize:11,fontWeight:700,color:'#1D5FAD',background:'#dbeafe',padding:'2px 8px',borderRadius:20}}>
            🏠 {data.summary.scaffale+data.summary.smontato} da montare
          </span>}
          {data.summary.mancante>0&&<span style={{fontSize:11,fontWeight:700,color:'#C0392B',background:'#FDECEA',padding:'2px 8px',borderRadius:20}}>
            ✗ {data.summary.mancante} mancanti
          </span>}
        </>}
        <span style={{fontSize:11,color:'#9A978E',fontWeight:700}}>{expanded?'▲':'▼'}</span>
      </div>

      {expanded&&(
        <div>
          {loading&&<div style={{padding:16,textAlign:'center',color:'#9A978E',fontSize:13}}>Caricamento...</div>}
          {!loading&&data&&data.utensili.length===0&&(
            <div style={{padding:16,textAlign:'center',color:'#9A978E',fontSize:13}}>
              Nessun utensile rilevato nei programmi MPF
            </div>
          )}
          {!loading&&data&&data.utensili.length>0&&(
            <>
              {/* Header colonne */}
              <div style={{display:'flex',background:'#F0EEE8',borderBottom:'1px solid #D8D5CC',
                fontSize:10,fontWeight:700,color:'#9A978E',letterSpacing:'0.07em'}}>
                <div style={{width:110,padding:'5px 10px',borderRight:'1px solid #D8D5CC'}}>STATO</div>
                <div style={{flex:1,padding:'5px 10px',borderRight:'1px solid #D8D5CC'}}>ALIAS</div>
                <div style={{width:80,padding:'5px 10px',borderRight:'1px solid #D8D5CC',textAlign:'center'}}>MAG/POS</div>
                <div style={{width:80,padding:'5px 10px',textAlign:'center'}}>VITA</div>
              </div>
              {data.utensili.map(u=>{
                const cfg=CFG[u.stato]||CFG.mancante
                return(
                  <div key={u.alias} style={{display:'flex',alignItems:'center',
                    borderBottom:'1px solid #D8D5CC',
                    background:u.stato==='mancante'?'#FFFAF9':u.stato==='ok'?'#FAFFFE':'#FFFFFF'}}>
                    <div style={{width:110,padding:'6px 10px',borderRight:'1px solid #D8D5CC',
                      display:'flex',alignItems:'center',gap:5,
                      background:cfg.bg,color:cfg.color,fontWeight:700,fontSize:12}}>
                      {cfg.dot} {cfg.label}
                    </div>
                    <div style={{flex:1,padding:'6px 10px',borderRight:'1px solid #D8D5CC',
                      fontSize:12,fontFamily:'monospace',fontWeight:700,color:'#1A1814'}}>
                      {u.alias}
                    </div>
                    <div style={{width:80,padding:'6px 10px',borderRight:'1px solid #D8D5CC',
                      textAlign:'center',fontSize:11,color:'#5A5750',fontFamily:'monospace'}}>
                      {u.magazine!=null?`M${u.magazine}`:''}{u.position!=null?` P${u.position}`:''}
                      {u.magazine==null&&u.position==null?'—':''}
                    </div>
                    <div style={{width:80,padding:'6px 10px',textAlign:'center',fontSize:11,
                      fontWeight:700,
                      color:u.life_percent!=null?(u.life_percent<15?'#C0392B':u.life_percent<30?'#D4700A':'#1A7A4A'):'#9A978E'}}>
                      {u.life_percent!=null?`${u.life_percent}%`:'—'}
                    </div>
                  </div>
                )
              })}
            </>
          )}
        </div>
      )}
    </div>
  )
}

// ── TaskItem ───────────────────────────────────────────────────────────────────
function TaskItem({task,idx,stepId,onToggle,onUpdateTask,onDelete,isNext,onReorderTask,toolsDB,projectId}){
  const[hovered,setHovered]=useState(false)
  const[dragOver,setDragOver]=useState(false)
  const[addingNote,setAddingNote]=useState(false)
  const[newNote,setNewNote]=useState('')
  const[editingNote,setEditingNote]=useState(null)
  const[editVal,setEditVal]=useState('')
  const noteInputRef=useRef(null)
  const notes=Array.isArray(task.notes)?task.notes:[]
  const displayNotes=notes.length>0?notes:(task.note?[{id:`legacy_${task.id}`,text:task.note,createdAt:''}]:[])
  function saveNewNote(){
    if(!newNote.trim()){setAddingNote(false);return}
    const legacy=(!Array.isArray(task.notes)&&task.note)?[{id:`legacy_${task.id}`,text:task.note,createdAt:''}]:[]
    onUpdateTask({...task,notes:[...legacy,...notes,{id:uid(),text:newNote.trim(),createdAt:nowStr()}],note:''})
    setNewNote('');setAddingNote(false)
  }
  useEffect(()=>{if(addingNote)noteInputRef.current?.focus()},[addingNote])
  return(
    <div
      draggable
      onDragStart={e=>{e.stopPropagation();e.dataTransfer.effectAllowed='move';e.dataTransfer.setData(DRAG_TASK,JSON.stringify({stepId,idx}));setTimeout(()=>e.target.style.opacity='0.4',0)}}
      onDragEnd={e=>{e.target.style.opacity='1';setDragOver(false)}}
      onDragOver={e=>{if(e.dataTransfer.types.includes(DRAG_TASK)){e.preventDefault();e.stopPropagation();setDragOver(true)}}}
      onDragLeave={()=>setDragOver(false)}
      onDrop={e=>{if(!e.dataTransfer.types.includes(DRAG_TASK))return;e.preventDefault();e.stopPropagation();setDragOver(false);const{stepId:fromStep,idx:fromIdx}=JSON.parse(e.dataTransfer.getData(DRAG_TASK));if(fromStep===stepId&&fromIdx!==idx)onReorderTask(stepId,fromIdx,idx)}}
      onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}
      style={{display:'flex',flexDirection:'column',background:dragOver?T.accentBg:isNext?T.accentBg:hovered?T.surface2:'transparent',border:dragOver?`2px solid ${T.accent}`:isNext?`1.5px solid ${T.accent}44`:`1px solid ${hovered?T.border:'transparent'}`,borderRadius:8,padding:'8px 10px',marginBottom:4,cursor:'grab',transition:'all 0.12s'}}>
      <div style={{display:'flex',alignItems:'center',gap:10}}>
        <span style={{color:T.borderStrong,fontSize:13,cursor:'grab',opacity:hovered?0.8:0.25,flexShrink:0,userSelect:'none'}}>⣿</span>
        {isNext&&<span style={{fontSize:13}}>📍</span>}
        <div onClick={()=>onToggle(task.id)} style={{width:20,height:20,borderRadius:6,border:task.done?'none':`2px solid ${T.borderStrong}`,background:task.done?'#1A7A4A':'transparent',cursor:'pointer',flexShrink:0,display:'flex',alignItems:'center',justifyContent:'center',transition:'all 0.2s'}}>
          {task.done&&<span style={{color:'#fff',fontSize:13,fontWeight:700}}>✓</span>}
        </div>
        <span style={{fontSize:15,color:task.done?T.textMuted:T.text,textDecoration:task.done?'line-through':'none',flex:1,fontWeight:task.done?400:500}}>{task.text}</span>
        {task.done&&task.doneAt&&<span style={{fontSize:12,color:T.textMuted,fontFamily:'monospace'}}>{task.doneAt}</span>}
        <div style={{display:'flex',gap:4,opacity:hovered?1:0,transition:'opacity 0.15s'}}>
          <button onClick={()=>setAddingNote(true)} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:6,cursor:'pointer',color:displayNotes.length>0?T.accent:T.textMuted,fontSize:12,padding:'2px 7px'}} title='Aggiungi commento'>💬{displayNotes.length>0?` ${displayNotes.length}`:''}</button>
          <button onClick={()=>onDelete(task.id)} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:6,cursor:'pointer',color:T.red,fontSize:12,padding:'2px 7px'}}>🗑️</button>
        </div>
      </div>
      {displayNotes.length>0&&(
        <div style={{marginTop:6,marginLeft:44,display:'flex',flexDirection:'column',gap:4}}>
          {displayNotes.map(note=>(
            <div key={note.id} style={{background:T.accentBg,borderRadius:6,borderLeft:`3px solid ${T.accent}`,padding:'5px 10px',display:'flex',alignItems:'flex-start',gap:8}}>
              {editingNote===note.id?(
                <>
                  <input value={editVal} onChange={e=>setEditVal(e.target.value)} autoFocus
                    style={{flex:1,background:T.surface,border:`1.5px solid ${T.accent}`,borderRadius:6,padding:'4px 8px',color:T.text,fontSize:13,outline:'none'}}
                    onKeyDown={e=>{if(e.key==='Enter'){onUpdateTask({...task,notes:notes.map(n=>n.id===note.id?{...n,text:editVal}:n),note:''});setEditingNote(null)}if(e.key==='Escape')setEditingNote(null)}}/>
                  <button onClick={()=>{onUpdateTask({...task,notes:notes.map(n=>n.id===note.id?{...n,text:editVal}:n),note:''});setEditingNote(null)}} style={{background:T.accent,border:'none',borderRadius:5,color:'#fff',fontSize:12,fontWeight:700,padding:'4px 10px',cursor:'pointer'}}>OK</button>
                </>
              ):(
                <>
                  <span style={{flex:1,fontSize:13,color:T.accent,fontStyle:'italic'}}>"{note.text}"</span>
                  {note.createdAt&&<span style={{fontSize:11,color:T.textMuted}}>{note.createdAt}</span>}
                  <button onClick={()=>{setEditingNote(note.id);setEditVal(note.text)}} style={{background:'none',border:'none',cursor:'pointer',color:T.textMuted,fontSize:12}}>✏️</button>
                  <button onClick={()=>onUpdateTask({...task,notes:notes.filter(n=>n.id!==note.id),note:''})} style={{background:'none',border:'none',cursor:'pointer',color:T.red,fontSize:12}}>×</button>
                </>
              )}
            </div>
          ))}
        </div>
      )}
      {addingNote&&(
        <div style={{marginTop:6,marginLeft:44,display:'flex',gap:8}}>
          <input ref={noteInputRef} value={newNote} onChange={e=>setNewNote(e.target.value)} placeholder='Aggiungi commento...'
            style={{flex:1,background:T.surface2,border:`1.5px solid ${T.accent}44`,borderRadius:8,padding:'7px 10px',color:T.text,fontSize:13,outline:'none'}}
            onKeyDown={e=>{if(e.key==='Enter')saveNewNote();if(e.key==='Escape'){setAddingNote(false);setNewNote('')}}}/>
          <button onClick={saveNewNote} style={{background:T.accent,border:'none',borderRadius:8,color:'#fff',fontSize:13,fontWeight:700,padding:'7px 14px',cursor:'pointer'}}>+ Aggiungi</button>
          <button onClick={()=>{setAddingNote(false);setNewNote('')}} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:13,padding:'7px 10px',cursor:'pointer'}}>✕</button>
        </div>
      )}
      {task.text?.trim().toLowerCase()==='fresatura'&&(
        <div style={{marginTop:8}}><FresaturaPanel task={task} onUpdateTask={onUpdateTask} toolsDB={toolsDB} projectId={projectId}/></div>
      )}
    </div>
  )
}

// ── StepSection ────────────────────────────────────────────────────────────────
function StepSection({step,stepIdx,nextTaskId,onToggle,onUpdateTask,onAddTask,onDeleteTask,onReorderTask,onReorderStep,onDeleteStep,projectColor,toolsDB,projectId}){
  const[collapsed,setCollapsed]=useState(false)
  const[adding,setAdding]=useState(false)
  const[newTask,setNewTask]=useState('')
  const[hovered,setHovered]=useState(false)
  const[stepDragOver,setStepDragOver]=useState(false)
  const done=(step.tasks||[]).filter(t=>t.done).length
  const handleStepGripDragStart=e=>{
    e.stopPropagation();e.dataTransfer.effectAllowed='move';e.dataTransfer.setData(DRAG_STEP,String(stepIdx))
    setTimeout(()=>{const el=e.target.closest('[data-stepcontainer]');if(el)el.style.opacity='0.4'},0)
  }
  return(
    <div data-stepcontainer
      onDragOver={e=>{if(e.dataTransfer.types.includes(DRAG_STEP)){e.preventDefault();setStepDragOver(true)}}}
      onDragLeave={e=>{if(e.currentTarget.contains(e.relatedTarget))return;setStepDragOver(false)}}
      onDrop={e=>{if(!e.dataTransfer.types.includes(DRAG_STEP))return;e.preventDefault();setStepDragOver(false);const fromIdx=parseInt(e.dataTransfer.getData(DRAG_STEP));if(!isNaN(fromIdx)&&fromIdx!==stepIdx)onReorderStep(fromIdx,stepIdx);document.querySelectorAll('[data-stepcontainer]').forEach(el=>el.style.opacity='1')}}
      onDragEnd={()=>{document.querySelectorAll('[data-stepcontainer]').forEach(el=>el.style.opacity='1');setStepDragOver(false)}}
      onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}
      style={{marginBottom:12,background:T.surface,border:stepDragOver?`2px solid ${projectColor}`:`1.5px solid ${T.border}`,borderLeft:`4px solid ${projectColor}`,borderRadius:10,padding:'12px 16px',transition:'box-shadow 0.15s, border 0.12s',boxShadow:hovered?'0 2px 12px rgba(0,0,0,0.08)':'none'}}>
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:collapsed?0:10}}>
        <span draggable onDragStart={handleStepGripDragStart} style={{color:T.borderStrong,fontSize:14,cursor:'grab',opacity:hovered?0.8:0.25,flexShrink:0,userSelect:'none'}} title='Trascina per spostare la fase'>⣿</span>
        <span onClick={()=>setCollapsed(!collapsed)} style={{color:T.textMuted,fontSize:12,cursor:'pointer',userSelect:'none'}}>{collapsed?'▶':'▼'}</span>
        <span style={{fontSize:15,fontWeight:700,color:T.text,flex:1,cursor:'pointer'}} onClick={()=>setCollapsed(!collapsed)}>{step.title}</span>
        <span style={{fontSize:13,color:T.textMuted,fontWeight:500}}>{done}/{(step.tasks||[]).length} completati</span>
        <button onClick={()=>onDeleteStep(step.id)} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:6,cursor:'pointer',color:T.red,fontSize:12,padding:'2px 8px',opacity:hovered?1:0,transition:'opacity 0.15s'}}>🗑️</button>
      </div>
      {!collapsed&&(
        <>
          {(step.tasks||[]).map((task,tIdx)=>(
            <TaskItem key={task.id} task={task} idx={tIdx} stepId={step.id}
              onToggle={onToggle} onUpdateTask={onUpdateTask}
              onDelete={tid=>onDeleteTask(step.id,tid)}
              isNext={task.id===nextTaskId} onReorderTask={onReorderTask}
              toolsDB={toolsDB} projectId={projectId}/>
          ))}
          {adding?(
            <div style={{display:'flex',gap:8,marginTop:8,marginLeft:22}}>
              <input autoFocus value={newTask} onChange={e=>setNewTask(e.target.value)} placeholder='Descrivi il nuovo task...'
                style={{flex:1,background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:8,padding:'8px 12px',color:T.text,fontSize:14,outline:'none'}}
                onKeyDown={e=>{if(e.key==='Enter'&&newTask.trim()){onAddTask(step.id,newTask.trim());setNewTask('');setAdding(false)}if(e.key==='Escape'){setAdding(false);setNewTask('')}}}/>
              <button onClick={()=>{if(newTask.trim())onAddTask(step.id,newTask.trim());setAdding(false);setNewTask('')}} style={{background:projectColor,border:'none',borderRadius:8,color:'#fff',fontSize:14,fontWeight:700,padding:'8px 16px',cursor:'pointer'}}>Aggiungi</button>
            </div>
          ):(
            <button onClick={()=>setAdding(true)} style={{background:'none',border:`1.5px dashed ${T.border}`,borderRadius:8,color:T.textMuted,fontSize:13,padding:'7px 16px',cursor:'pointer',width:'100%',marginTop:6,fontWeight:500}}>+ Aggiungi task</button>
          )}
        </>
      )}
    </div>
  )
}
// ── LogEntry (editabile) ───────────────────────────────────────────────────────
function LogEntry({entry,projectColor,onUpdate,onDelete}){
  const[hovered,setHovered]=useState(false)
  const[editing,setEditing]=useState(false)
  const[editVal,setEditVal]=useState(entry.text)
  const[confirm,setConfirm]=useState(false)
  function save(){if(editVal.trim())onUpdate(editVal.trim());setEditing(false)}
  return(
    <div onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>{setHovered(false);setConfirm(false)}}
      style={{background:T.surface,border:`1px solid ${hovered?T.borderStrong:T.border}`,borderRadius:10,padding:'12px 16px',marginBottom:10,transition:'border 0.15s'}}>
      <div style={{display:'flex',gap:10,alignItems:'center',marginBottom:6}}>
        <span style={{fontSize:14,fontWeight:700,color:projectColor}}>{entry.user}</span>
        <span style={{fontSize:12,color:T.textMuted}}>{entry.time}</span>
        {entry.editedAt&&<span style={{fontSize:11,color:T.textMuted,fontStyle:'italic'}}>· modificato {entry.editedAt}</span>}
        <div style={{marginLeft:'auto',display:'flex',gap:6,opacity:hovered?1:0,transition:'opacity 0.15s'}}>
          <button onClick={()=>{setEditing(true);setEditVal(entry.text)}} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:6,color:T.textSub,fontSize:12,padding:'2px 8px',cursor:'pointer',fontWeight:600}}>✏️ Modifica</button>
          {confirm
            ?<><button onClick={onDelete} style={{background:T.red,border:'none',borderRadius:6,color:'#fff',fontSize:12,padding:'2px 10px',cursor:'pointer',fontWeight:700}}>Conferma elimina</button><button onClick={()=>setConfirm(false)} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:6,color:T.textSub,fontSize:12,padding:'2px 8px',cursor:'pointer'}}>✕</button></>
            :<button onClick={()=>setConfirm(true)} style={{background:'none',border:`1px solid ${T.red}44`,borderRadius:6,color:T.red,fontSize:12,padding:'2px 8px',cursor:'pointer'}}>🗑️</button>
          }
        </div>
      </div>
      {editing?(
        <div style={{display:'flex',gap:8}}>
          <textarea value={editVal} onChange={e=>setEditVal(e.target.value)} autoFocus rows={2}
            style={{flex:1,background:T.surface2,border:`1.5px solid ${T.accent}44`,borderRadius:8,padding:'8px 12px',color:T.text,fontSize:15,outline:'none',resize:'vertical',fontFamily:'inherit'}}
            onKeyDown={e=>{if(e.key==='Enter'&&!e.shiftKey){e.preventDefault();save()}if(e.key==='Escape')setEditing(false)}}/>
          <div style={{display:'flex',flexDirection:'column',gap:6}}>
            <button onClick={save} style={{background:T.accent,border:'none',borderRadius:8,color:'#fff',fontSize:13,fontWeight:700,padding:'8px 14px',cursor:'pointer'}}>Salva</button>
            <button onClick={()=>setEditing(false)} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:13,padding:'8px 10px',cursor:'pointer'}}>✕</button>
          </div>
        </div>
      ):(
        <div style={{fontSize:15,color:T.text,whiteSpace:'pre-wrap'}}>{entry.text}</div>
      )}
    </div>
  )
}

// ── SaveAsTemplateModal ────────────────────────────────────────────────────────
function SaveAsTemplateModal({project,templates,onSave,onClose}){
  const[mode,setMode]=useState('new')
  const[tmplName,setTmplName]=useState(project.name)
  const[tmplDesc,setTmplDesc]=useState(project.description||'')
  const[tmplIcon,setTmplIcon]=useState('🚀')
  const[tmplColor,setTmplColor]=useState(project.color)
  const[replaceId,setReplaceId]=useState(templates[0]?.id||null)
  const[showIconPicker,setShowIconPicker]=useState(false)
  const[saved,setSaved]=useState(false)
  function buildSteps(){return project.steps.map(s=>({id:uid(),title:s.title,tasks:s.tasks.map(t=>({id:uid(),text:t.text}))}))}
  function handleSave(){
    const steps=buildSteps()
    if(mode==='new'){
      onSave({id:uid(),name:tmplName.trim()||project.name,description:tmplDesc.trim(),icon:tmplIcon,color:tmplColor,steps})
    }else{
      const existing=templates.find(t=>t.id===replaceId)
      if(!existing) return
      onSave({...existing,name:tmplName.trim()||existing.name,description:tmplDesc.trim(),icon:tmplIcon,color:tmplColor,steps})
    }
    setSaved(true);setTimeout(onClose,1200)
  }
  const inputStyle={width:'100%',background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:8,padding:'9px 12px',color:T.text,fontSize:14,outline:'none'}
  return(
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.45)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:150}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,padding:30,width:500,maxWidth:'92vw',maxHeight:'90vh',overflowY:'auto',boxShadow:'0 12px 48px rgba(0,0,0,0.18)'}}>
        {saved?(
          <div style={{textAlign:'center',padding:'30px 0'}}><div style={{fontSize:44,marginBottom:12}}>✅</div><div style={{fontSize:18,fontWeight:800,color:T.green}}>Template salvato!</div></div>
        ):(
          <>
            <div style={{fontSize:18,fontWeight:800,color:T.text,marginBottom:6}}>💾 Salva come Template</div>
            <div style={{fontSize:13,color:T.textSub,marginBottom:22}}>Le fasi e i task vengono copiati nel template. I segni di spunta e le note vengono rimossi.</div>
            <div style={{display:'flex',gap:8,marginBottom:22}}>
              <button onClick={()=>setMode('new')} style={{flex:1,padding:'10px',borderRadius:8,border:`2px solid ${mode==='new'?T.accent:T.border}`,background:mode==='new'?T.accentBg:T.surface2,color:mode==='new'?T.accent:T.textSub,fontWeight:700,fontSize:14,cursor:'pointer'}}>✦ Nuovo template</button>
              <button onClick={()=>setMode('replace')} disabled={templates.length===0} style={{flex:1,padding:'10px',borderRadius:8,border:`2px solid ${mode==='replace'?T.accent:T.border}`,background:mode==='replace'?T.accentBg:T.surface2,color:mode==='replace'?T.accent:templates.length===0?T.textMuted:T.textSub,fontWeight:700,fontSize:14,cursor:templates.length===0?'not-allowed':'pointer',opacity:templates.length===0?0.5:1}}>↺ Sostituisci esistente</button>
            </div>
            {mode==='replace'&&templates.length>0&&(
              <div style={{marginBottom:18}}>
                <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:8}}>SCEGLI IL TEMPLATE DA SOSTITUIRE</label>
                <div style={{display:'flex',flexDirection:'column',gap:6}}>
                  {templates.map(t=>(
                    <div key={t.id} onClick={()=>setReplaceId(t.id)} style={{display:'flex',alignItems:'center',gap:12,padding:'10px 14px',borderRadius:8,border:`2px solid ${replaceId===t.id?t.color:T.border}`,background:replaceId===t.id?t.color+'12':T.surface2,cursor:'pointer'}}>
                      <span style={{fontSize:20}}>{t.icon}</span>
                      <div style={{flex:1}}><div style={{fontSize:14,fontWeight:700,color:T.text}}>{t.name}</div><div style={{fontSize:12,color:T.textMuted}}>{t.steps?.length||0} fasi · {(t.steps||[]).reduce((a,s)=>a+(s.tasks||[]).length,0)} task</div></div>
                      {replaceId===t.id&&<span style={{color:t.color,fontWeight:700,fontSize:18}}>✓</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}
            <div style={{marginBottom:14}}><label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:6}}>NOME TEMPLATE</label><input value={tmplName} onChange={e=>setTmplName(e.target.value)} style={inputStyle}/></div>
            <div style={{marginBottom:18}}><label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:6}}>DESCRIZIONE</label><input value={tmplDesc} onChange={e=>setTmplDesc(e.target.value)} style={inputStyle} placeholder='Breve descrizione...'/></div>
            <div style={{display:'flex',gap:28,marginBottom:22,alignItems:'flex-start'}}>
              <div>
                <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:8}}>ICONA</label>
                <div style={{position:'relative'}}>
                  <button onClick={()=>setShowIconPicker(v=>!v)} style={{background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:10,padding:'8px 16px',cursor:'pointer',fontSize:22,lineHeight:1}}>{tmplIcon}</button>
                  {showIconPicker&&(<div style={{position:'absolute',top:'110%',left:0,background:T.surface,border:`1px solid ${T.border}`,borderRadius:10,padding:10,display:'flex',flexWrap:'wrap',gap:6,width:220,zIndex:30,boxShadow:'0 4px 20px rgba(0,0,0,0.12)'}}>
                    {ICONS.map(ic=><button key={ic} onClick={()=>{setTmplIcon(ic);setShowIconPicker(false)}} style={{background:ic===tmplIcon?T.surface2:'transparent',border:`1px solid ${ic===tmplIcon?T.border:'transparent'}`,borderRadius:6,padding:'5px 7px',cursor:'pointer',fontSize:20}}>{ic}</button>)}
                  </div>)}
                </div>
              </div>
              <div>
                <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:8}}>COLORE</label>
                <div style={{display:'flex',gap:8,flexWrap:'wrap'}}>{COLORS.map(c=><div key={c} onClick={()=>setTmplColor(c)} style={{width:26,height:26,borderRadius:'50%',background:c,cursor:'pointer',border:tmplColor===c?'3px solid #333':'3px solid transparent',transform:tmplColor===c?'scale(1.15)':'scale(1)'}}/>)}</div>
              </div>
            </div>
            <div style={{background:T.surface2,borderRadius:8,padding:'12px 14px',marginBottom:22}}>
              <div style={{fontSize:12,color:T.textSub,fontWeight:700,marginBottom:8,letterSpacing:'0.06em'}}>ANTEPRIMA FASI</div>
              {project.steps.map((s,i)=>(<div key={s.id} style={{display:'flex',alignItems:'center',gap:8,marginBottom:5}}><span style={{fontSize:12,color:tmplColor,fontWeight:700,minWidth:18}}>{i+1}.</span><span style={{fontSize:14,color:T.text,fontWeight:500,flex:1}}>{s.title}</span><span style={{fontSize:12,color:T.textMuted}}>{(s.tasks||[]).length} task</span></div>))}
            </div>
            <div style={{display:'flex',gap:10,justifyContent:'flex-end'}}>
              <button onClick={onClose} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:'9px 20px',cursor:'pointer',fontWeight:600}}>Annulla</button>
              <button onClick={handleSave} style={{background:T.accent,border:'none',borderRadius:8,color:'#fff',fontWeight:800,fontSize:14,padding:'9px 24px',cursor:'pointer'}}>{mode==='new'?'💾 Salva come nuovo':'↺ Sostituisci template'}</button>
            </div>
          </>
        )}
      </div>
    </div>
  )
}
// ── ProjectDetail ──────────────────────────────────────────────────────────────

// ── LancioNCModal ─────────────────────────────────────────────────────────────
function LancioNCModal({project, toolsDB, onLancia, onClose}){
  const allPgm = (project.steps||[])
    .flatMap(s=>s.tasks||[])
    .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
    .flatMap(t=>(t.programs||[]).filter(p=>p.tipoGruppo!=='ipm'))

  const da_fare    = allPgm.filter(p=>p.stato==='da_fare')
  const in_macchina= allPgm.filter(p=>p.stato==='in_macchina')
  const completati = allPgm.filter(p=>p.stato==='completato')

  const [selected, setSelected] = useState(new Set())
  const [showCompletati, setShowCompletati] = useState(false)

  function toggle(id){ setSelected(s=>{ const n=new Set(s); n.has(id)?n.delete(id):n.add(id); return n }) }
  function selezionaDaFare(){ setSelected(new Set(da_fare.map(p=>p.id))) }
  function selezionaTutti(){ setSelected(new Set([...da_fare,...in_macchina].map(p=>p.id))) }
  function deselezionaTutti(){ setSelected(new Set()) }

  const pgmSelezionati = allPgm.filter(p=>selected.has(p.id))
  const problemi = pgmSelezionati.filter(p=>{
    const s = classifyTool(p.utensile, toolsDB)
    return s==='mancante'||s==='fin_vita'||s==='disabilitato'
  })
  const mancanti = pgmSelezionati.filter(p=>classifyTool(p.utensile,toolsDB)==='mancante')

  function ToolBadge({alias}){
    if(!alias||!toolsDB) return null
    const s=classifyTool(alias,toolsDB)
    const cfg={
      ok:          {dot:'✓',color:'#166534',bg:'#dcfce7'},
      fin_vita:    {dot:'⚠',color:'#D97706',bg:'#FEF9C3'},
      disabilitato:{dot:'⊘',color:'#7C3AED',bg:'#EDE9FE'},
      mancante:    {dot:'✗',color:'#DC2626',bg:'#FEE2E2'},
    }[s]
    if(!cfg) return null
    return <span style={{fontSize:11,fontWeight:700,color:cfg.color,background:cfg.bg,
      padding:'1px 7px',borderRadius:20,flexShrink:0}}>{cfg.dot} {s==='ok'?'ok':s==='fin_vita'?'vita bassa':s==='disabilitato'?'disab.':'mancante'}</span>
  }

  function PgmRow({pgm, dimmed}){
    const sel = selected.has(pgm.id)
    const ts  = classifyTool(pgm.utensile, toolsDB)
    const rowBg = sel
      ? ts==='mancante'?'#FEE2E2':ts==='fin_vita'?'#FEF9C3':'#EFF6FF'
      : dimmed?'#FAFAFA':'#FFFFFF'
    return(
      <div onClick={()=>toggle(pgm.id)}
        style={{display:'flex',alignItems:'center',gap:10,padding:'8px 14px',
          cursor:'pointer',background:rowBg,
          borderLeft:sel?(ts==='mancante'?'3px solid #DC2626':ts==='fin_vita'?'3px solid #D97706':'3px solid #1D5FAD'):'3px solid transparent',
          borderBottom:'1px solid #F0EEE8',transition:'background 0.1s',
          opacity:dimmed?0.55:1}}>
        <div style={{width:18,height:18,borderRadius:5,flexShrink:0,
          border:sel?'none':'2px solid #B0ADA4',
          background:sel?'#1D5FAD':'transparent',
          display:'flex',alignItems:'center',justifyContent:'center'}}>
          {sel&&<span style={{color:'#fff',fontSize:12,fontWeight:800}}>✓</span>}
        </div>
        {/* Badge stato */}
        {(()=>{const s=pgm.stato||'da_fare';const cfg={
          da_fare:    {label:'Da fare',    color:'#9A978E',bg:'#F0EEE8'},
          in_macchina:{label:'In macchina',color:'#1D5FAD',bg:'#DBEAFE'},
          completato: {label:'Fatto',      color:'#166534',bg:'#DCFCE7'},
        }[s]||{label:s,color:'#9A978E',bg:'#F0EEE8'};return(
          <span style={{fontSize:10,fontWeight:700,color:cfg.color,background:cfg.bg,
            padding:'2px 7px',borderRadius:10,flexShrink:0,whiteSpace:'nowrap'}}>
            {cfg.label}
          </span>
        )})()}
        {/* Filename */}
        <span style={{fontSize:12,fontFamily:'monospace',fontWeight:700,
          color:'#1D5FAD',minWidth:145,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
          {pgm.filename?.replace(/\.MPF$/i,'')||`#${pgm.numPgm}`}
        </span>
        {/* Utensile */}
        <span style={{fontSize:11,fontFamily:'monospace',color:'#1A1814',
          minWidth:120,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
          {pgm.utensile||'—'}
        </span>
        {/* Operazione */}
        <span style={{fontSize:11,color:'#9A978E',flex:1,
          overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
          {(pgm.tipoOp||'').replace(/[-–]\s*NESSUN TESTO\s*/gi,'').trim()||''}
        </span>
        <ToolBadge alias={pgm.utensile}/>
      </div>
    )
  }

  return(
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.5)',
      display:'flex',alignItems:'center',justifyContent:'center',zIndex:400}}>
      <div style={{background:'#FFFFFF',borderRadius:16,width:660,maxWidth:'94vw',
        maxHeight:'88vh',display:'flex',flexDirection:'column',
        border:'1px solid #D8D5CC',boxShadow:'0 16px 56px rgba(0,0,0,0.22)'}}>

        {/* Header */}
        <div style={{padding:'18px 22px 14px',borderBottom:'1px solid #E8E6E0'}}>
          <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:4}}>
            <span style={{fontSize:18}}>📄</span>
            <div style={{flex:1}}>
              <div style={{fontSize:16,fontWeight:800,color:'#1A1814'}}>Lancia in Analisi NC</div>
              <div style={{fontSize:12,color:'#9A978E',marginTop:1}}>{project.name}</div>
            </div>
            <button onClick={onClose} style={{background:'none',border:'1px solid #D8D5CC',
              borderRadius:8,color:'#5A5750',fontSize:13,padding:'5px 12px',cursor:'pointer'}}>✕</button>
          </div>

          {/* Bottoni selezione rapida */}
          <div style={{display:'flex',gap:8,flexWrap:'wrap',marginTop:10}}>
            <button onClick={selezionaDaFare}
              style={{background:'#1D5FAD',border:'none',borderRadius:7,color:'#fff',
                fontSize:12,fontWeight:700,padding:'6px 14px',cursor:'pointer'}}>
              ☑ Seleziona da fare ({da_fare.length})
            </button>
            {in_macchina.length>0&&<button onClick={selezionaTutti}
              style={{background:'#F0EEE8',border:'1px solid #D8D5CC',borderRadius:7,
                color:'#5A5750',fontSize:12,fontWeight:600,padding:'6px 14px',cursor:'pointer'}}>
              Seleziona tutti ({da_fare.length+in_macchina.length})
            </button>}
            {selected.size>0&&<button onClick={deselezionaTutti}
              style={{background:'none',border:'1px solid #D8D5CC',borderRadius:7,
                color:'#9A978E',fontSize:12,padding:'6px 14px',cursor:'pointer'}}>
              Deseleziona tutto
            </button>}
          </div>
        </div>

        {/* Lista programmi */}
        <div style={{flex:1,overflowY:'auto'}}>
          {/* Da fare */}
          {da_fare.length>0&&(
            <div>
              <div style={{padding:'8px 14px 4px',fontSize:10,fontWeight:700,
                color:'#9A978E',letterSpacing:'0.07em',background:'#F5F4F0',
                borderBottom:'1px solid #E8E6E0'}}>
                DA FARE — {da_fare.length}
              </div>
              {da_fare.map(p=><PgmRow key={p.id} pgm={p}/>)}
            </div>
          )}

          {/* In macchina */}
          {in_macchina.length>0&&(
            <div>
              <div style={{padding:'8px 14px 4px',fontSize:10,fontWeight:700,
                color:'#1D5FAD',letterSpacing:'0.07em',background:'#F0F4FF',
                borderBottom:'1px solid #E8E6E0'}}>
                IN MACCHINA — {in_macchina.length}
              </div>
              {in_macchina.map(p=><PgmRow key={p.id} pgm={p} dimmed/>)}
            </div>
          )}

          {/* Completati (collassati) */}
          {completati.length>0&&(
            <div>
              <div onClick={()=>setShowCompletati(v=>!v)}
                style={{padding:'8px 14px',fontSize:10,fontWeight:700,
                  color:'#9A978E',letterSpacing:'0.07em',background:'#FAFAFA',
                  borderBottom:'1px solid #E8E6E0',cursor:'pointer',
                  display:'flex',alignItems:'center',gap:6}}>
                {showCompletati?'▼':'▶'} COMPLETATI — {completati.length}
              </div>
              {showCompletati&&completati.map(p=><PgmRow key={p.id} pgm={p} dimmed/>)}
            </div>
          )}

          {allPgm.length===0&&(
            <div style={{padding:40,textAlign:'center',color:'#9A978E',fontSize:14}}>
              Nessun programma MPF caricato
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{borderTop:'1px solid #E8E6E0',padding:'12px 22px',
          background:'#F5F4F0',borderRadius:'0 0 16px 16px'}}>

          {/* Avviso problemi */}
          {mancanti.length>0&&(
            <div style={{background:'#FEE2E2',border:'1px solid #DC262633',borderRadius:8,
              padding:'8px 12px',marginBottom:10,fontSize:12,color:'#DC2626',fontWeight:600}}>
              ⚠ {mancanti.length} programm{mancanti.length===1?'o':'i'} con utensile mancante —
              il MAIN verrà generato ma {mancanti.length===1?'quel programma potrebbe':'quei programmi potrebbero'} non essere eseguibil{mancanti.length===1?'e':'i'}.
            </div>
          )}
          {problemi.length>0&&mancanti.length===0&&(
            <div style={{background:'#FEF9C3',border:'1px solid #D9770633',borderRadius:8,
              padding:'8px 12px',marginBottom:10,fontSize:12,color:'#D97706',fontWeight:600}}>
              ⚠ {problemi.length} programm{problemi.length===1?'o':'i'} con utensile a fine vita — verificare prima di procedere.
            </div>
          )}

          <div style={{display:'flex',alignItems:'center',gap:12}}>
            {/* Counter */}
            <div style={{flex:1,fontSize:13,color:'#5A5750'}}>
              {selected.size===0
                ? <span style={{color:'#9A978E'}}>Nessun programma selezionato</span>
                : <><span style={{fontWeight:700,color:'#1A1814'}}>{selected.size} selezionat{selected.size===1?'o':'i'}</span>
                    {problemi.length===0&&<span style={{color:'#166534',marginLeft:6}}>· tutti ok ✓</span>}
                    {mancanti.length>0&&<span style={{color:'#DC2626',marginLeft:6}}>· {mancanti.length} mancant{mancanti.length===1?'e':'i'}</span>}
                  </>
              }
            </div>
            <button onClick={onClose}
              style={{background:'none',border:'1px solid #D8D5CC',borderRadius:8,
                color:'#5A5750',fontSize:13,padding:'9px 18px',cursor:'pointer',fontWeight:600}}>
              Annulla
            </button>
            <button
              disabled={selected.size===0}
              onClick={()=>onLancia(pgmSelezionati)}
              style={{background:selected.size===0?'#D8D5CC':'#1D5FAD',border:'none',
                borderRadius:8,color:'#fff',fontWeight:700,fontSize:14,
                padding:'9px 22px',cursor:selected.size===0?'default':'pointer',
                transition:'background 0.15s'}}>
              📄 Lancia {selected.size>0?selected.size:''} in NC →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function ProjectDetail({project,onBack,onUpdate,onDelete,onArchive,templates,onSaveAsTemplate,onLanciaNC,palletDisponibili=[]}){
  // Carica tools_machine una volta sola per questo progetto
  const [toolsDB, setToolsDB] = useState(null)
  const [showLancioModal, setShowLancioModal] = useState(()=>{
    // Apri automaticamente se arrivato dalla Coda con bottone Avvia
    const flag = sessionStorage.getItem('dmgdesk_apri_modal_lancio')
    if(flag){ sessionStorage.removeItem('dmgdesk_apri_modal_lancio'); return true }
    return false
  })
  useEffect(()=>{
    fetch('/api/tools/')
      .then(r=>r.ok?r.json():[])
      .then(arr=>{
        // Indicizia per tool_id (non per name) per conservare tutti i gemelli
        // classifyTool scansiona per name → trova tutti i gemelli con lo stesso alias
        const map={}
        arr.forEach(t=>{ if(t.name) map[String(t.tool_id)]=t })
        setToolsDB(map)
      }).catch(()=>setToolsDB({}))
  },[])  // solo al mount del ProjectDetail
  const[logText,setLogText]=useState('')
  const[logUser,setLogUser]=useState('Tu')
  const[editingName,setEditingName]=useState(false)
  const[editNameVal,setEditNameVal]=useState('')
  const[activeTab,setActiveTab]=useState('tasks')
  const[addingStep,setAddingStep]=useState(false)
  const[newStepName,setNewStepName]=useState('')
  const[confirm,setConfirm]=useState(null)
  const[showSaveTemplate,setShowSaveTemplate]=useState(false)
  const logRef=useRef(null)
  const next=getNextTask(project)
  const progress=getProgress(project)
  const mpfList=(project.steps||[]).flatMap(s=>s.tasks||[]).filter(t=>t.text?.trim().toLowerCase()==='fresatura').flatMap(t=>(t.programs||[]).filter(p=>p.tipoGruppo!=='ipm'))

  function toggleTask(taskId){onUpdate({...project,steps:project.steps.map(s=>({...s,tasks:s.tasks.map(t=>t.id===taskId?{...t,done:!t.done,doneAt:!t.done?new Date().toISOString().slice(0,10):null}:t)}))})}
  function updateTaskInProject(updatedTask){onUpdate({...project,steps:project.steps.map(s=>({...s,tasks:s.tasks.map(t=>t.id===updatedTask.id?updatedTask:t)}))})}
  function addTask(stepId,text){onUpdate({...project,steps:project.steps.map(s=>s.id===stepId?{...s,tasks:[...s.tasks,{id:uid(),text,done:false,notes:[],note:'',doneAt:null}]}:s)})}
  function deleteTask(stepId,taskId){onUpdate({...project,steps:project.steps.map(s=>s.id===stepId?{...s,tasks:s.tasks.filter(t=>t.id!==taskId)}:s)})}
  function deleteStep(stepId){onUpdate({...project,steps:project.steps.filter(s=>s.id!==stepId)})}
  function reorderTask(stepId,from,to){onUpdate({...project,steps:project.steps.map(s=>s.id===stepId?{...s,tasks:reorder(s.tasks,from,to)}:s)})}
  function reorderStep(from,to){onUpdate({...project,steps:reorder(project.steps,from,to)})}
  function addStep(){if(!newStepName.trim())return;onUpdate({...project,steps:[...project.steps,{id:uid(),title:newStepName.trim(),tasks:[]}]});setNewStepName('');setAddingStep(false)}
  function addLog(){if(!logText.trim())return;onUpdate({...project,log:[...(project.log||[]),{id:uid(),user:logUser,text:logText.trim(),time:nowStr()}]});setLogText('');setTimeout(()=>logRef.current?.scrollTo({top:9999,behavior:'smooth'}),50)}
  function updateLog(logId,newText){onUpdate({...project,log:(project.log||[]).map(e=>e.id===logId?{...e,text:newText,editedAt:nowStr()}:e)})}
  function deleteLog(logId){onUpdate({...project,log:(project.log||[]).filter(e=>e.id!==logId)})}

  const Tab=({id,label})=>(<button onClick={()=>setActiveTab(id)} style={{background:'none',border:'none',cursor:'pointer',color:activeTab===id?project.color:T.textSub,fontSize:15,fontWeight:700,padding:'10px 0',borderBottom:activeTab===id?`3px solid ${project.color}`:'3px solid transparent',marginRight:24,transition:'all 0.15s'}}>{label}</button>)

  return(
    <div style={{display:'flex',flexDirection:'column',height:'100%',background:T.bg,fontFamily:"'DM Sans', system-ui, sans-serif"}}>
      {/* Header */}
      <div style={{padding:'20px 28px 0',borderBottom:`1px solid ${T.border}`,flexShrink:0,background:T.surface}}>
        <div style={{display:'flex',alignItems:'center',gap:12,marginBottom:16,flexWrap:'wrap'}}>
          <button onClick={onBack} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:'7px 14px',cursor:'pointer',fontWeight:600}}>← Indietro</button>
          <div style={{width:14,height:14,borderRadius:'50%',background:project.color,flexShrink:0}}/>
          {editingName
            ? <div style={{display:'flex',gap:6,flex:1,alignItems:'center'}}>
                <input autoFocus value={editNameVal}
                  onChange={e=>setEditNameVal(e.target.value)}
                  onKeyDown={e=>{
                    if(e.key==='Enter'){onUpdate({...project,name:editNameVal.trim()||project.name});setEditingName(false)}
                    if(e.key==='Escape')setEditingName(false)
                  }}
                  style={{fontSize:18,fontWeight:800,color:T.text,background:T.surface2,
                    border:`2px solid ${project.color}`,borderRadius:8,padding:'4px 10px',
                    outline:'none',flex:1}}/>
                <button onClick={()=>{onUpdate({...project,name:editNameVal.trim()||project.name});setEditingName(false)}}
                  style={{background:project.color,border:'none',borderRadius:7,color:'#fff',
                    fontWeight:700,fontSize:13,padding:'5px 12px',cursor:'pointer'}}>✓</button>
                <button onClick={()=>setEditingName(false)}
                  style={{background:'none',border:`1px solid ${T.border}`,borderRadius:7,
                    color:T.textSub,fontSize:13,padding:'5px 10px',cursor:'pointer'}}>✕</button>
              </div>
            : <div style={{display:'flex',alignItems:'center',gap:6,flex:1}}>
                <div style={{fontSize:20,fontWeight:800,color:T.text}}>{project.name}</div>
                <button onClick={()=>{setEditNameVal(project.name);setEditingName(true)}}
                  title="Rinomina progetto"
                  style={{background:'none',border:'none',cursor:'pointer',
                    color:T.textMuted,fontSize:13,opacity:0.5,padding:'2px 4px',
                    lineHeight:1}}>✏️</button>
              </div>
          }
          <StatusBadge progress={progress}/>
          <button onClick={()=>setShowSaveTemplate(true)} style={{background:T.blueBg,border:`1px solid ${T.blue}44`,borderRadius:8,color:T.blue,fontSize:13,padding:'7px 14px',cursor:'pointer',fontWeight:600}}>💾 Salva come Template</button>
          {/* Pallet */}
          <div style={{display:'flex',alignItems:'center',gap:6}}>
            <span style={{fontSize:12,color:T.textMuted}}>Pallet:</span>
            <select
              value={project.pallet_assegnato||''}
              onChange={async e=>{
                const val = e.target.value ? parseInt(e.target.value) : null
                const old = project.pallet_assegnato
                // Rimuovi dal vecchio
                if(old && old!==val){
                  await fetch('/api/pallet/'+old+'/assegna-progetto',{
                    method:'PATCH',headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({progetto_id:null,progetto_nome:null,progetto_colore:null})
                  })
                }
                // Assegna al nuovo
                if(val){
                  const r = await fetch('/api/pallet/'+val+'/assegna-progetto',{
                    method:'PATCH',headers:{'Content-Type':'application/json'},
                    body:JSON.stringify({progetto_id:project.id,progetto_nome:project.name,progetto_colore:project.color||'#1D5FAD'})
                  })
                  if(!r.ok){
                    const err = await r.json().catch(()=>({}))
                    alert(err.detail||'Errore assegnazione pallet')
                    return
                  }
                }
                // Aggiorna lo state locale immediatamente
                onUpdate({...project, pallet_assegnato: val})

              }}
              style={{fontSize:12,fontWeight:700,background:'#F0F4FF',color:'#1D5FAD',
                border:'1px solid #BFDBFE',borderRadius:6,padding:'4px 8px',cursor:'pointer'}}>
              <option value=''>—</option>
              {[1,2,3,4,5,6].map(n=>{
                const disp = palletDisponibili.find(p=>p.numero===n)
                const isAssegnato = project.pallet_assegnato===n
                // Mostra: assegnato a questo progetto (sempre) o VUOTO libero
                if(!disp && !isAssegnato) return null
                return <option key={n} value={n}>P{n}{isAssegnato?' ✓':''}</option>
              })}
            </select>
            {project.pallet_assegnato&&(
              <span onClick={()=>window.location.href='/coda'}
                style={{fontSize:11,color:'#1D5FAD',cursor:'pointer',
                  textDecoration:'underline',textDecorationStyle:'dotted'}}>→ Coda</span>
            )}
          </div>
          {mpfList.length>0&&<button onClick={()=>setShowLancioModal(true)} style={{background:'#1D5FAD',border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:13,padding:'8px 16px',cursor:'pointer'}}>📄 Lancia in NC →</button>}
          <button onClick={()=>setConfirm('archive')} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:'7px 14px',cursor:'pointer',fontWeight:600}}>{project.archived?'📤 Riattiva':'📦 Archivia'}</button>
          <button onClick={()=>setConfirm('delete')} style={{background:T.redBg,border:`1px solid ${T.red}44`,borderRadius:8,color:T.red,fontSize:14,padding:'7px 14px',cursor:'pointer',fontWeight:600}}>🗑️ Elimina</button>
        </div>
        <div style={{marginBottom:14}}>
          <div style={{display:'flex',justifyContent:'space-between',marginBottom:6}}>
            <span style={{fontSize:13,color:T.textSub,fontWeight:600}}>Avanzamento</span>
            <span style={{fontSize:13,color:project.color,fontWeight:700}}>{progress}% — {project.steps.flatMap(s=>s.tasks||[]).filter(t=>t.done).length} di {project.steps.flatMap(s=>s.tasks||[]).length} task completati</span>
          </div>
          <ProgressBar value={progress} color={project.color}/>
        </div>
        {next&&(
          <div style={{background:T.accentBg,border:`1.5px solid ${T.accent}44`,borderRadius:10,padding:'12px 16px',marginBottom:14,display:'flex',alignItems:'flex-start',gap:10}}>
            <span style={{fontSize:20,flexShrink:0}}>📍</span>
            <div>
              <div style={{fontSize:12,color:T.accent,fontWeight:700,letterSpacing:'0.06em',marginBottom:3}}>RIPRENDI DA QUI</div>
              <div style={{fontSize:15,color:T.text,fontWeight:600}}><span style={{color:T.textSub,fontWeight:400}}>{next.step.title} › </span>{next.task.text}</div>
              {next.task.text?.trim().toLowerCase()==='fresatura'&&Array.isArray(next.task.programs)&&next.task.programs.length>0&&(
                <div style={{display:'flex',alignItems:'center',gap:8,marginTop:5}}>
                  <span style={{fontSize:13,color:'#1D5FAD',fontWeight:700}}>⚙️ {next.task.programs.filter(p=>p.stato==='completato').length}/{next.task.programs.length} programmi completati</span>
                  {next.task.programs.filter(p=>p.stato==='in_macchina').length>0&&<span style={{fontSize:12,color:'#1D5FAD',background:'#E8F0FA',padding:'2px 10px',borderRadius:10}}>{next.task.programs.filter(p=>p.stato==='in_macchina').length} in macchina</span>}
                </div>
              )}
            </div>
          </div>
        )}
        <div><Tab id='tasks' label='Task'/><Tab id='log' label={`Log aggiornamenti (${(project.log||[]).length})`}/></div>
      </div>
      {/* Body */}
      <div style={{flex:1,overflow:'auto',padding:'20px 28px'}}>
        {activeTab==='tasks'&&(
          <div>
            <div style={{fontSize:12,color:T.textMuted,marginBottom:12,display:'flex',alignItems:'center',gap:6}}><span>⣿</span> Trascina per riordinare fasi e task</div>

            {project.steps.map((step,sIdx)=>(
              <StepSection key={step.id} step={step} stepIdx={sIdx}
                nextTaskId={next?.step.id===step.id?next?.task.id:null}
                onToggle={toggleTask} onUpdateTask={updateTaskInProject} onAddTask={addTask}
                onDeleteTask={deleteTask} onReorderTask={reorderTask}
                onReorderStep={reorderStep} onDeleteStep={deleteStep}
                totalSteps={project.steps.length} projectColor={project.color}
                toolsDB={toolsDB} projectId={project.id}/>
            ))}
            {addingStep?(
              <div style={{display:'flex',gap:10,marginTop:10}}>
                <input autoFocus value={newStepName} onChange={e=>setNewStepName(e.target.value)} placeholder='Nome della nuova fase...'
                  style={{flex:1,background:T.surface,border:`1.5px solid ${T.border}`,borderRadius:10,padding:'10px 14px',color:T.text,fontSize:15,outline:'none'}}
                  onKeyDown={e=>{if(e.key==='Enter')addStep();if(e.key==='Escape'){setAddingStep(false);setNewStepName('')}}}/>
                <button onClick={addStep} style={{background:project.color,border:'none',borderRadius:10,color:'#fff',fontWeight:700,fontSize:15,padding:'10px 20px',cursor:'pointer'}}>Crea fase</button>
              </div>
            ):(
              <button onClick={()=>setAddingStep(true)} style={{background:'none',border:`2px dashed ${T.border}`,borderRadius:10,color:T.textMuted,fontSize:14,padding:'12px',cursor:'pointer',width:'100%',fontWeight:500,marginTop:4}}>+ Aggiungi fase</button>
            )}
          </div>
        )}
        {activeTab==='log'&&(
          <div style={{display:'flex',flexDirection:'column',height:'100%'}}>
            <div ref={logRef} style={{flex:1,overflowY:'auto',marginBottom:16}}>
              {!(project.log||[]).length&&<div style={{fontSize:15,color:T.textMuted,textAlign:'center',padding:'40px 0'}}>Nessun aggiornamento ancora. Aggiungine uno!</div>}
              {(project.log||[]).map(entry=>(<LogEntry key={entry.id} entry={entry} projectColor={project.color} onUpdate={newText=>updateLog(entry.id,newText)} onDelete={()=>deleteLog(entry.id)}/>))}
            </div>
            <div style={{display:'flex',gap:10,background:T.surface,padding:'14px',borderRadius:12,border:`1px solid ${T.border}`}}>
              <input value={logUser} onChange={e=>setLogUser(e.target.value)} style={{width:90,background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,padding:'9px 10px',color:project.color,fontSize:14,fontWeight:700,outline:'none'}}/>
              <input value={logText} onChange={e=>setLogText(e.target.value)} placeholder='Scrivi un aggiornamento...'
                style={{flex:1,background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,padding:'9px 12px',color:T.text,fontSize:15,outline:'none'}}
                onKeyDown={e=>{if(e.key==='Enter')addLog()}}/>
              <button onClick={addLog} style={{background:project.color,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:15,padding:'9px 18px',cursor:'pointer'}}>→</button>
            </div>
          </div>
        )}
      </div>
      {confirm==='delete'&&<ConfirmDialog message={`Eliminare il progetto "${project.name}"? L'operazione è irreversibile.`} onConfirm={()=>{onDelete(project.id);setConfirm(null)}} onCancel={()=>setConfirm(null)}/>}
      {confirm==='archive'&&<ConfirmDialog message={project.archived?`Riportare "${project.name}" tra i progetti attivi?`:`Archiviare "${project.name}"?`} onConfirm={()=>{onArchive(project.id);setConfirm(null)}} onCancel={()=>setConfirm(null)}/>}
      {showSaveTemplate&&<SaveAsTemplateModal project={project} templates={templates} onSave={tmpl=>{onSaveAsTemplate(tmpl);setShowSaveTemplate(false)}} onClose={()=>setShowSaveTemplate(false)}/>}
      {showLancioModal&&<LancioNCModal
        project={project}
        toolsDB={toolsDB}
        onClose={()=>setShowLancioModal(false)}
        onLancia={pgmSelezionati=>{
          setShowLancioModal(false)
          onLanciaNC(project, pgmSelezionati)
        }}
      />}
    </div>
  )
}
// ── ProjectCard ────────────────────────────────────────────────────────────────
function ProjectCard({project,onClick,onDelete,onArchive,delivery,onSetDelivery}){
  const progress=getProgress(project)
  const next=getNextTask(project)
  const[hovered,setHovered]=useState(false)
  const[confirm,setConfirm]=useState(null)
  const[editingDate,setEditingDate]=useState(false)
  const[dateVal,setDateVal]=useState(delivery?.dueDate||'')
  const mpfTot=(project.steps||[]).flatMap(s=>s.tasks||[]).filter(t=>t.text?.trim().toLowerCase()==='fresatura').flatMap(t=>(t.programs||[]).filter(p=>p.tipoGruppo!=='ipm'))
  const mpfDone=mpfTot.filter(p=>p.stato==='completato').length
  const days=delivery?daysUntil(delivery.dueDate):null
  const urgency=delivery?deliveryUrgency(days):null
  const leftBorder=urgency&&!delivery?.delivered?`4px solid ${urgency.color}`:`4px solid ${project.color}`
  function saveDate(e){e.stopPropagation();onSetDelivery(project.id,dateVal);setEditingDate(false)}
  return(
    <div onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}
      style={{background:T.surface,border:`1.5px solid ${hovered?(urgency&&!delivery?.delivered?urgency.color+'66':project.color+'88'):T.border}`,borderLeft:leftBorder,borderRadius:12,padding:'18px 20px',position:'relative',transition:'all 0.18s',boxShadow:hovered?'0 4px 20px rgba(0,0,0,0.1)':'0 1px 4px rgba(0,0,0,0.05)',cursor:'pointer'}}>
      {/* Azioni hover */}
      <div style={{position:'absolute',top:12,right:12,display:'flex',gap:6,opacity:hovered?1:0,transition:'opacity 0.15s'}}>
        <button onClick={e=>{e.stopPropagation();setConfirm('archive')}} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:6,color:T.textSub,fontSize:12,padding:'4px 9px',cursor:'pointer',fontWeight:600}}>{project.archived?'📤':'📦'}</button>
        <button onClick={e=>{e.stopPropagation();setConfirm('delete')}} style={{background:T.redBg,border:`1px solid ${T.red}44`,borderRadius:6,color:T.red,fontSize:12,padding:'4px 9px',cursor:'pointer',fontWeight:600}}>🗑️</button>
      </div>
      <div onClick={onClick}>
        <div style={{marginBottom:10,paddingRight:80,display:'flex',flexDirection:'column',gap:4}}>
          <div style={{display:'flex',alignItems:'center',gap:8}}>
            <div style={{width:10,height:10,borderRadius:'50%',background:project.color,flexShrink:0}}/>
            <div style={{fontSize:17,fontWeight:800,color:T.text}}>{project.name}</div>
            {project.pallet_assegnato&&(
              <span style={{fontSize:11,fontWeight:700,background:'#EFF6FF',color:'#1D5FAD',
                padding:'2px 8px',borderRadius:6,flexShrink:0}}>
                P{project.pallet_assegnato}
              </span>
            )}
          </div>
          {project.description&&<div style={{fontSize:13,color:T.textSub,marginLeft:18}}>{project.description}</div>}
        </div>
        {/* Scadenza */}
        <div onClick={e=>e.stopPropagation()} style={{marginBottom:10,marginLeft:18}}>
          {editingDate?(
            <div style={{display:'flex',gap:6,alignItems:'center'}}>
              <input type='date' value={dateVal} onChange={e=>setDateVal(e.target.value)} autoFocus style={{background:T.surface2,border:`1.5px solid ${T.accent}44`,borderRadius:6,padding:'4px 8px',color:T.text,fontSize:13,outline:'none'}}/>
              <button onClick={saveDate} style={{background:T.accent,border:'none',borderRadius:6,color:'#fff',fontSize:12,fontWeight:700,padding:'4px 10px',cursor:'pointer'}}>OK</button>
              <button onClick={e=>{e.stopPropagation();setEditingDate(false)}} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:6,color:T.textSub,fontSize:12,padding:'4px 8px',cursor:'pointer'}}>✕</button>
            </div>
          ):delivery?.dueDate?(
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              {delivery.delivered?(
                <span style={{fontSize:12,color:T.green,fontWeight:700,background:T.greenBg,padding:'2px 10px',borderRadius:20}}>✓ Consegnato {delivery.deliveredAt||''}</span>
              ):(
                <span style={{fontSize:12,fontWeight:800,color:urgency.color,background:urgency.bg,padding:'3px 12px',borderRadius:20,border:`1px solid ${urgency.color}33`}}>
                  {urgency.dot} {days===0?'OGGI':days<0?`Scaduto ${Math.abs(days)}gg fa`:`${days}gg alla consegna`}
                </span>
              )}
              <span style={{fontSize:12,color:T.textMuted}}>{new Date(delivery.dueDate).toLocaleDateString('it-IT',{day:'2-digit',month:'2-digit',year:'numeric'})}</span>
              <button onClick={e=>{e.stopPropagation();setDateVal(delivery.dueDate);setEditingDate(true)}} style={{background:'none',border:'none',color:T.textMuted,fontSize:11,cursor:'pointer',padding:'0 2px',opacity:hovered?0.7:0}}>✏️</button>
              <button onClick={e=>{e.stopPropagation();onSetDelivery(project.id,null,!delivery.delivered)}} title={delivery.delivered?'Segna come da consegnare':'Segna come consegnato'} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:6,color:delivery.delivered?T.textMuted:T.green,fontSize:11,cursor:'pointer',padding:'2px 7px',opacity:hovered?1:0}}>{delivery.delivered?'↩ Riapri':'✓ Consegnato'}</button>
            </div>
          ):(
            <button onClick={e=>{e.stopPropagation();setDateVal('');setEditingDate(true)}} style={{background:'none',border:`1px dashed ${T.border}`,borderRadius:6,color:T.textMuted,fontSize:12,padding:'3px 10px',cursor:'pointer',opacity:hovered?1:0.4}}>📅 Imposta scadenza</button>
          )}
        </div>
        <ProgressBar value={progress} color={project.color}/>
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginTop:8,marginBottom:next?12:0}}>
          <span style={{fontSize:13,color:T.textSub,fontWeight:500}}>{(project.steps||[]).flatMap(s=>s.tasks||[]).filter(t=>t.done).length} / {(project.steps||[]).flatMap(s=>s.tasks||[]).length} task</span>
          <div style={{display:'flex',gap:8,alignItems:'center'}}>
            {mpfTot.length>0&&<span style={{fontSize:11,color:'#1D5FAD',fontWeight:700,background:'#E8F0FA',padding:'2px 8px',borderRadius:10}}>⚙ {mpfDone}/{mpfTot.length} MPF</span>}
            <StatusBadge progress={progress}/>
          </div>
        </div>
        {next?(
          <div style={{background:T.accentBg,borderRadius:8,padding:'10px 12px',borderLeft:`3px solid ${T.accent}`}}>
            <div style={{fontSize:11,color:T.accent,fontWeight:700,letterSpacing:'0.06em',marginBottom:3}}>📍 PROSSIMO STEP</div>
            <div style={{fontSize:14,color:T.text,fontWeight:600}}><span style={{color:T.textSub,fontWeight:400}}>{next.step.title} › </span>{next.task.text}</div>
            {next.task.text?.trim().toLowerCase()==='fresatura'&&Array.isArray(next.task.programs)&&next.task.programs.length>0&&(
              <div style={{display:'flex',alignItems:'center',gap:8,marginTop:4}}>
                <span style={{fontSize:12,color:'#1D5FAD',fontWeight:700}}>⚙️ {next.task.programs.filter(p=>p.stato==='completato').length}/{next.task.programs.length} pgm</span>
                {next.task.programs.filter(p=>p.stato==='in_macchina').length>0&&<span style={{fontSize:11,color:'#1D5FAD',background:'#E8F0FA',padding:'1px 8px',borderRadius:10}}>{next.task.programs.filter(p=>p.stato==='in_macchina').length} in macchina</span>}
              </div>
            )}
          </div>
        ):(
          <div style={{fontSize:14,color:T.green,fontWeight:600,display:'flex',alignItems:'center',gap:6}}><span style={{background:T.greenBg,border:`1px solid ${T.green}44`,borderRadius:6,padding:'4px 10px'}}>✓ Progetto completato</span></div>
        )}
      </div>
      {confirm==='delete'&&<ConfirmDialog message={`Eliminare "${project.name}"?`} onConfirm={()=>{onDelete(project.id);setConfirm(null)}} onCancel={()=>setConfirm(null)}/>}
      {confirm==='archive'&&<ConfirmDialog message={project.archived?`Riportare "${project.name}" in Attivi?`:`Archiviare "${project.name}"?`} onConfirm={()=>{onArchive(project.id);setConfirm(null)}} onCancel={()=>setConfirm(null)}/>}
    </div>
  )
}
// ── TemplateEditor ─────────────────────────────────────────────────────────────
function TemplateEditor({template,onSave,onCancel}){
  const[name,setName]=useState(template.name)
  const[description,setDescription]=useState(template.description||'')
  const[icon,setIcon]=useState(template.icon||'🚀')
  const[color,setColor]=useState(template.color||T.accent)
  const[steps,setSteps]=useState(template.steps.map(s=>({...s,tasks:(s.tasks||[]).map(t=>({...t}))})))
  const[showIconPicker,setShowIconPicker]=useState(false)
  function addStep(){setSteps(p=>[...p,{id:uid(),title:'Nuova fase',tasks:[]}])}
  function updateStepTitle(id,title){setSteps(p=>p.map(s=>s.id===id?{...s,title}:s))}
  function removeStep(id){setSteps(p=>p.filter(s=>s.id!==id))}
  function addTask(stepId){setSteps(p=>p.map(s=>s.id===stepId?{...s,tasks:[...s.tasks,{id:uid(),text:'Nuovo task'}]}:s))}
  function updateTask(stepId,taskId,text){setSteps(p=>p.map(s=>s.id===stepId?{...s,tasks:s.tasks.map(t=>t.id===taskId?{...t,text}:t)}:s))}
  function removeTask(stepId,taskId){setSteps(p=>p.map(s=>s.id===stepId?{...s,tasks:s.tasks.filter(t=>t.id!==taskId)}:s))}
  function moveStep(idx,dir){const ns=[...steps],t=idx+dir;if(t<0||t>=ns.length)return;[ns[idx],ns[t]]=[ns[t],ns[idx]];setSteps(ns)}
  const inputStyle={background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:8,padding:'9px 12px',color:T.text,fontSize:14,outline:'none',width:'100%'}
  return(
    <div style={{display:'flex',flexDirection:'column',height:'100%',background:T.bg,fontFamily:"'DM Sans', system-ui"}}>
      <div style={{padding:'18px 28px',borderBottom:`1px solid ${T.border}`,flexShrink:0,background:T.surface,display:'flex',alignItems:'center',gap:12}}>
        <button onClick={onCancel} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:'8px 16px',cursor:'pointer',fontWeight:600}}>← Annulla</button>
        <div style={{fontSize:18,fontWeight:800,color:T.text,flex:1}}>{template.id.startsWith('new_')?'Nuovo Template':`Modifica: ${template.name}`}</div>
        <button onClick={()=>onSave({...template,name,description,icon,color,steps})} style={{background:color,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:15,padding:'9px 22px',cursor:'pointer'}}>💾 Salva Template</button>
      </div>
      <div style={{flex:1,overflowY:'auto',padding:'24px 28px'}}>
        <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:16,marginBottom:20}}>
          <div><label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:6}}>NOME TEMPLATE</label><input value={name} onChange={e=>setName(e.target.value)} style={inputStyle}/></div>
          <div><label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:6}}>DESCRIZIONE</label><input value={description} onChange={e=>setDescription(e.target.value)} style={inputStyle}/></div>
        </div>
        <div style={{display:'flex',gap:32,marginBottom:24,alignItems:'flex-start'}}>
          <div>
            <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:8}}>ICONA</label>
            <div style={{position:'relative'}}>
              <button onClick={()=>setShowIconPicker(v=>!v)} style={{background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:10,padding:'10px 18px',cursor:'pointer',fontSize:24,lineHeight:1}}>{icon}</button>
              {showIconPicker&&(<div style={{position:'absolute',top:'110%',left:0,background:T.surface,border:`1px solid ${T.border}`,borderRadius:10,padding:12,display:'flex',flexWrap:'wrap',gap:6,width:220,zIndex:20,boxShadow:'0 4px 20px rgba(0,0,0,0.12)'}}>
                {ICONS.map(ic=><button key={ic} onClick={()=>{setIcon(ic);setShowIconPicker(false)}} style={{background:ic===icon?T.surface2:'transparent',border:`1px solid ${ic===icon?T.border:'transparent'}`,borderRadius:6,padding:'5px 7px',cursor:'pointer',fontSize:20}}>{ic}</button>)}
              </div>)}
            </div>
          </div>
          <div>
            <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:8}}>COLORE</label>
            <div style={{display:'flex',gap:10,flexWrap:'wrap'}}>{COLORS.map(c=><div key={c} onClick={()=>setColor(c)} style={{width:28,height:28,borderRadius:'50%',background:c,cursor:'pointer',border:color===c?'3px solid #333':'3px solid transparent',transform:color===c?'scale(1.15)':'scale(1)'}}/>)}</div>
          </div>
        </div>
        <div style={{fontSize:13,color:T.textSub,fontWeight:600,letterSpacing:'0.06em',marginBottom:14}}>FASI E TASK</div>
        {steps.map((step,idx)=>(
          <div key={step.id} style={{background:T.surface,border:`1.5px solid ${T.border}`,borderLeft:`4px solid ${color}`,borderRadius:10,padding:'14px 16px',marginBottom:12}}>
            <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:12}}>
              <div style={{display:'flex',flexDirection:'column',gap:2}}>
                <button onClick={()=>moveStep(idx,-1)} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:4,cursor:'pointer',color:idx===0?T.textMuted:T.text,fontSize:10,padding:'2px 5px',lineHeight:1}}>▲</button>
                <button onClick={()=>moveStep(idx,1)} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:4,cursor:'pointer',color:idx===steps.length-1?T.textMuted:T.text,fontSize:10,padding:'2px 5px',lineHeight:1}}>▼</button>
              </div>
              <span style={{fontSize:12,color,fontWeight:700,minWidth:55}}>FASE {idx+1}</span>
              <input value={step.title} onChange={e=>updateStepTitle(step.id,e.target.value)} style={{...inputStyle,fontWeight:700,fontSize:15}}/>
              <button onClick={()=>removeStep(step.id)} style={{background:T.redBg,border:`1px solid ${T.red}44`,borderRadius:6,cursor:'pointer',color:T.red,fontSize:14,padding:'4px 8px',flexShrink:0}}>✕</button>
            </div>
            <div style={{marginLeft:32}}>
              {(step.tasks||[]).map(task=>(
                <div key={task.id} style={{display:'flex',alignItems:'center',gap:8,marginBottom:8}}>
                  <span style={{color,fontSize:12,opacity:0.6,flexShrink:0}}>◦</span>
                  <input value={task.text} onChange={e=>updateTask(step.id,task.id,e.target.value)} style={{...inputStyle,fontSize:14}}/>
                  <button onClick={()=>removeTask(step.id,task.id)} style={{background:T.redBg,border:`1px solid ${T.red}33`,borderRadius:6,cursor:'pointer',color:T.red,fontSize:13,padding:'4px 8px',flexShrink:0}}>✕</button>
                </div>
              ))}
              <button onClick={()=>addTask(step.id)} style={{background:'none',border:`1.5px dashed ${T.border}`,borderRadius:8,color:T.textMuted,fontSize:13,padding:'6px 14px',cursor:'pointer',fontWeight:500}}>+ Aggiungi task</button>
            </div>
          </div>
        ))}
        <button onClick={addStep} style={{background:'none',border:`2px dashed ${color}66`,borderRadius:10,color,fontSize:14,padding:'14px',cursor:'pointer',width:'100%',fontWeight:600}}>+ Aggiungi fase</button>
      </div>
    </div>
  )
}

// ── TemplatesPage ──────────────────────────────────────────────────────────────
function TemplatesPage({templates,onEdit,onCreate,onDelete,onDuplicate,onUseTemplate,lastSaved}){
  return(
    <div style={{flex:1,overflowY:'auto',padding:'24px 28px',background:T.bg,fontFamily:"'DM Sans', system-ui"}}>
      <div style={{display:'flex',justifyContent:'space-between',alignItems:'center',marginBottom:20}}>
        <div>
          <div style={{fontSize:13,color:T.textSub,fontWeight:600,letterSpacing:'0.06em',marginBottom:4}}>TEMPLATE SALVATI — {templates.length}</div>
          {lastSaved&&<span style={{background:T.greenBg,border:`1px solid ${T.green}44`,borderRadius:20,padding:'2px 10px',fontSize:12,color:T.green,fontWeight:600}}>💾 Salvati automaticamente · {lastSaved}</span>}
        </div>
        <button onClick={onCreate} style={{background:T.accent,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:14,padding:'9px 20px',cursor:'pointer'}}>+ Nuovo Template</button>
      </div>
      {templates.length===0&&<div style={{textAlign:'center',padding:'60px 0',color:T.textMuted,fontSize:16}}>Nessun template. Creane uno!</div>}
      <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill, minmax(320px, 1fr))',gap:16}}>
        {templates.map(tmpl=>(
          <div key={tmpl.id} style={{background:T.surface,border:`1.5px solid ${T.border}`,borderTop:`4px solid ${tmpl.color}`,borderRadius:12,padding:'18px 20px',boxShadow:'0 1px 4px rgba(0,0,0,0.05)'}}>
            <div style={{display:'flex',alignItems:'flex-start',gap:14,marginBottom:14}}>
              <span style={{fontSize:28,lineHeight:1}}>{tmpl.icon}</span>
              <div style={{flex:1}}><div style={{fontSize:16,fontWeight:800,color:T.text,marginBottom:3}}>{tmpl.name}</div><div style={{fontSize:13,color:T.textSub}}>{tmpl.description}</div></div>
            </div>
            <div style={{background:T.surface2,borderRadius:8,padding:'10px 12px',marginBottom:10}}>
              {(tmpl.steps||[]).map((step,i)=>(
                <div key={step.id} style={{display:'flex',alignItems:'center',gap:8,marginBottom:i<tmpl.steps.length-1?5:0}}>
                  <span style={{fontSize:12,color:tmpl.color,fontWeight:700,minWidth:18}}>{i+1}.</span>
                  <span style={{fontSize:14,color:T.text,fontWeight:500,flex:1}}>{step.title}</span>
                  <span style={{fontSize:12,color:T.textMuted}}>{(step.tasks||[]).length} task</span>
                </div>
              ))}
            </div>
            <div style={{fontSize:12,color:T.textMuted,marginBottom:14}}>{(tmpl.steps||[]).reduce((a,s)=>a+(s.tasks||[]).length,0)} task totali · {(tmpl.steps||[]).length} fasi</div>
            <div style={{display:'flex',gap:6}}>
              <button onClick={()=>onUseTemplate(tmpl)} style={{flex:1,background:tmpl.color,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:14,padding:'9px',cursor:'pointer'}}>▶ Usa</button>
              <button onClick={()=>onDuplicate(tmpl)} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:'9px 12px',cursor:'pointer',fontWeight:600}} title='Duplica'>⧉</button>
              <button onClick={()=>onEdit(tmpl)} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:'9px 12px',cursor:'pointer',fontWeight:600}} title='Modifica'>✏️</button>
              <button onClick={()=>onDelete(tmpl.id)} style={{background:T.redBg,border:`1px solid ${T.red}44`,borderRadius:8,color:T.red,fontSize:14,padding:'9px 12px',cursor:'pointer'}} title='Elimina'>🗑️</button>
            </div>
          </div>
        ))}
      </div>
    </div>
  )
}
// ── QuickTaskRow ───────────────────────────────────────────────────────────────
function QuickTaskRow({task,onToggle,onDelete,onPriority,onEditText}){
  const[hovered,setHovered]=useState(false)
  const[showPrioPick,setShowPrioPick]=useState(false)
  const[editing,setEditing]=useState(false)
  const[editVal,setEditVal]=useState(task.text)
  const p=PRIORITY[task.priority]||PRIORITY.media
  function saveEdit(){if(editVal.trim())onEditText(editVal.trim());setEditing(false)}
  return(
    <div onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>{setHovered(false);setShowPrioPick(false)}}
      style={{display:'flex',alignItems:'flex-start',gap:8,padding:'8px 8px',borderRadius:8,marginBottom:3,background:hovered?T.surface2:'transparent',borderLeft:`3px solid ${task.done?T.border:p.color}`,transition:'background 0.12s',opacity:task.done?0.6:1}}>
      <div onClick={onToggle} style={{width:18,height:18,borderRadius:5,flexShrink:0,marginTop:editing?8:1,border:task.done?'none':`2px solid ${p.color}`,background:task.done?p.color:'transparent',cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center'}}>
        {task.done&&<span style={{color:'#fff',fontSize:11,fontWeight:800}}>✓</span>}
      </div>
      {editing?(
        <div style={{flex:1,display:'flex',gap:5}}>
          <input value={editVal} onChange={e=>setEditVal(e.target.value)} autoFocus
            style={{flex:1,background:T.surface,border:`1.5px solid ${T.accent}44`,borderRadius:6,padding:'4px 8px',color:T.text,fontSize:13,outline:'none'}}
            onKeyDown={e=>{if(e.key==='Enter')saveEdit();if(e.key==='Escape')setEditing(false)}}/>
          <button onClick={saveEdit} style={{background:T.accent,border:'none',borderRadius:5,color:'#fff',fontSize:12,fontWeight:700,padding:'4px 9px',cursor:'pointer',flexShrink:0}}>OK</button>
          <button onClick={()=>setEditing(false)} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:5,color:T.textSub,fontSize:12,padding:'4px 6px',cursor:'pointer',flexShrink:0}}>✕</button>
        </div>
      ):(
        <span onDoubleClick={()=>{setEditVal(task.text);setEditing(true)}} style={{flex:1,fontSize:13,color:T.text,lineHeight:1.5,textDecoration:task.done?'line-through':'none',wordBreak:'break-word',cursor:'text'}} title='Doppio click per modificare'>{task.text}</span>
      )}
      {hovered&&!editing&&(
        <div style={{display:'flex',flexDirection:'column',gap:3,flexShrink:0,position:'relative'}}>
          <button onClick={()=>{setEditVal(task.text);setEditing(true)}} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:5,fontSize:11,padding:'2px 5px',cursor:'pointer',color:T.textSub}}>✏️</button>
          <button onClick={()=>setShowPrioPick(v=>!v)} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:5,fontSize:12,padding:'2px 5px',cursor:'pointer',color:p.color,fontWeight:700}}>{p.dot}</button>
          <button onClick={onDelete} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:5,fontSize:11,padding:'2px 5px',cursor:'pointer',color:T.red}}>🗑️</button>
          {showPrioPick&&(
            <div style={{position:'absolute',right:'110%',top:0,background:T.surface,border:`1px solid ${T.border}`,borderRadius:8,padding:6,display:'flex',flexDirection:'column',gap:4,boxShadow:'0 4px 16px rgba(0,0,0,0.12)',zIndex:50,width:90}}>
              {Object.entries(PRIORITY).map(([key,pr])=>(
                <button key={key} onClick={()=>{onPriority(key);setShowPrioPick(false)}} style={{background:task.priority===key?pr.bg:'transparent',border:`1px solid ${task.priority===key?pr.color:'transparent'}`,borderRadius:5,color:pr.color,fontSize:12,fontWeight:700,padding:'4px 8px',cursor:'pointer',textAlign:'left'}}>{pr.dot} {pr.label}</button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── QuickTasksSidebar ──────────────────────────────────────────────────────────
function QuickTasksSidebar({collapsed,onToggleCollapse}){
  const[tasks,setTasks]=useState([])
  const[newText,setNewText]=useState('')
  const[newPrio,setNewPrio]=useState('media')
  const[filter,setFilter]=useState('tutti')
  const inputRef=useRef(null)
  const pendingCount=tasks.filter(t=>!t.done).length
  const filtered=tasks.filter(t=>{
    if(filter==='da_fare') return !t.done
    if(filter==='fatti')   return t.done
    if(filter==='alta')    return t.priority==='alta'
    if(filter==='media')   return t.priority==='media'
    if(filter==='bassa')   return t.priority==='bassa'
    return true
  })
  function addTask(){
    if(!newText.trim()) return
    setTasks(ts=>[{id:uid(),text:newText.trim(),priority:newPrio,done:false,createdAt:new Date().toISOString()},...ts])
    setNewText('');inputRef.current?.focus()
  }
  if(collapsed){
    return(
      <div onClick={onToggleCollapse} title='Apri task rapidi'
        style={{width:32,flexShrink:0,background:T.surface,borderLeft:`1px solid ${T.border}`,display:'flex',flexDirection:'column',alignItems:'center',justifyContent:'center',cursor:'pointer',userSelect:'none'}}>
        <div style={{writingMode:'vertical-rl',transform:'rotate(180deg)',fontSize:12,fontWeight:700,color:T.textSub,letterSpacing:'0.1em',display:'flex',alignItems:'center',gap:6}}>
          ⚡ TASK RAPIDI
          {pendingCount>0&&<span style={{background:T.accent,color:'#fff',borderRadius:10,fontSize:10,fontWeight:800,padding:'2px 5px',writingMode:'horizontal-tb'}}>{pendingCount}</span>}
        </div>
      </div>
    )
  }
  return(
    <div style={{width:280,flexShrink:0,background:T.surface,borderLeft:`1px solid ${T.border}`,display:'flex',flexDirection:'column',overflow:'hidden'}}>
      <div style={{padding:'14px 14px 10px',borderBottom:`1px solid ${T.border}`,flexShrink:0}}>
        <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:10}}>
          <span style={{fontSize:16}}>⚡</span>
          <span style={{fontSize:14,fontWeight:800,color:T.text,flex:1}}>Task Rapidi</span>
          {pendingCount>0&&<span style={{background:T.accent,color:'#fff',borderRadius:20,fontSize:11,fontWeight:800,padding:'2px 8px'}}>{pendingCount}</span>}
          <button onClick={onToggleCollapse} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:6,color:T.textMuted,fontSize:12,padding:'2px 7px',cursor:'pointer'}}>✕</button>
        </div>
        <div style={{display:'flex',flexDirection:'column',gap:6}}>
          <input ref={inputRef} value={newText} onChange={e=>setNewText(e.target.value)} onKeyDown={e=>{if(e.key==='Enter')addTask()}} placeholder='Nuovo task...'
            style={{background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:8,padding:'8px 10px',color:T.text,fontSize:13,outline:'none',width:'100%'}}/>
          <div style={{display:'flex',gap:5}}>
            {Object.entries(PRIORITY).map(([key,p])=>(
              <button key={key} onClick={()=>setNewPrio(key)} style={{flex:1,background:newPrio===key?p.bg:'transparent',border:`1.5px solid ${newPrio===key?p.color:T.border}`,borderRadius:6,color:newPrio===key?p.color:T.textMuted,fontSize:11,fontWeight:700,padding:'5px 0',cursor:'pointer'}}>{p.dot} {p.label}</button>
            ))}
          </div>
          <button onClick={addTask} style={{background:T.accent,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:13,padding:'8px',cursor:'pointer',width:'100%'}}>+ Aggiungi</button>
        </div>
      </div>
      <div style={{padding:'8px 10px',borderBottom:`1px solid ${T.border}`,display:'flex',flexWrap:'wrap',gap:4,flexShrink:0}}>
        {[['tutti',`Tutti (${tasks.length})`],['da_fare',`Da fare (${tasks.filter(t=>!t.done).length})`],['fatti',`Fatti (${tasks.filter(t=>t.done).length})`],['alta','🔴'],['media','🟡'],['bassa','🟢']].map(([key,label])=>(
          <button key={key} onClick={()=>setFilter(key)} style={{background:filter===key?T.surface2:'transparent',border:`1px solid ${filter===key?T.borderStrong:'transparent'}`,borderRadius:6,color:filter===key?T.text:T.textMuted,fontSize:11,fontWeight:600,padding:'3px 8px',cursor:'pointer'}}>{label}</button>
        ))}
      </div>
      <div style={{flex:1,overflowY:'auto',padding:'8px'}}>
        {filtered.length===0&&<div style={{textAlign:'center',padding:'30px 10px',color:T.textMuted,fontSize:13}}>{filter==='tutti'?'Nessun task ancora.\nAggiungine uno!':'Nessun task in questa categoria.'}</div>}
        {filtered.map(task=>(
          <QuickTaskRow key={task.id} task={task}
            onToggle={()=>setTasks(ts=>ts.map(t=>t.id===task.id?{...t,done:!t.done}:t))}
            onDelete={()=>setTasks(ts=>ts.filter(t=>t.id!==task.id))}
            onPriority={p=>setTasks(ts=>ts.map(t=>t.id===task.id?{...t,priority:p}:t))}
            onEditText={text=>setTasks(ts=>ts.map(t=>t.id===task.id?{...t,text}:t))}/>
        ))}
      </div>
    </div>
  )
}
// ── DeliveryRow ────────────────────────────────────────────────────────────────
function DeliveryRow({d,onToggle,onEdit,onDelete,onOpen}){
  const[hovered,setHovered]=useState(false)
  const u=d.urgency
  return(
    <div onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}
      style={{background:T.surface,border:`1.5px solid ${d.delivered?T.border:u.color+'44'}`,borderLeft:`4px solid ${d.delivered?T.border:u.color}`,borderRadius:12,padding:'14px 18px',display:'flex',alignItems:'center',gap:14,opacity:d.delivered?0.65:1,transition:'all 0.15s',boxShadow:hovered&&!d.delivered?'0 2px 12px rgba(0,0,0,0.07)':'none'}}>
      <div onClick={onToggle} title={d.delivered?'Segna come da consegnare':'Segna come consegnato'}
        style={{width:24,height:24,borderRadius:8,flexShrink:0,cursor:'pointer',display:'flex',alignItems:'center',justifyContent:'center',border:d.delivered?'none':`2px solid ${u.color}`,background:d.delivered?T.green:'transparent',transition:'all 0.2s'}}>
        {d.delivered&&<span style={{color:'#fff',fontSize:14,fontWeight:800}}>✓</span>}
      </div>
      <div style={{flex:1,minWidth:0}}>
        <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:3}}>
          {d.proj&&<div style={{width:10,height:10,borderRadius:'50%',background:d.proj.color,flexShrink:0}}/>}
          <span style={{fontSize:15,fontWeight:700,color:T.text,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{d.proj?.name||<span style={{color:T.red,fontStyle:'italic'}}>Progetto eliminato</span>}</span>
        </div>
        <div style={{display:'flex',alignItems:'center',gap:12,flexWrap:'wrap'}}>
          {d.note&&<span style={{fontSize:13,color:T.textSub}}>{d.note}</span>}
          {d.delivered&&d.deliveredAt&&<span style={{fontSize:12,color:T.textMuted,fontStyle:'italic'}}>Consegnato {d.deliveredAt}</span>}
        </div>
      </div>
      {d.proj&&!d.delivered&&(
        <div style={{width:80,flexShrink:0}}>
          <div style={{fontSize:11,color:T.textMuted,marginBottom:3,textAlign:'right'}}>{d.progress}%</div>
          <div style={{height:5,background:T.surface2,borderRadius:3,overflow:'hidden'}}><div style={{height:'100%',width:`${d.progress}%`,background:d.proj.color,borderRadius:3}}/></div>
        </div>
      )}
      {!d.delivered&&(
        <div style={{background:u.bg,color:u.color,border:`1.5px solid ${u.color}44`,borderRadius:20,padding:'4px 14px',fontSize:13,fontWeight:800,flexShrink:0,minWidth:70,textAlign:'center'}}>
          {u.dot} {d.days===null?'—':d.days===0?'OGGI':d.days<0?`${Math.abs(d.days)}gg fa`:`${d.days}gg`}
        </div>
      )}
      <div style={{fontSize:13,color:T.textMuted,flexShrink:0,minWidth:80,textAlign:'right'}}>
        {d.dueDate?new Date(d.dueDate).toLocaleDateString('it-IT',{day:'2-digit',month:'2-digit',year:'numeric'}):'—'}
      </div>
      <div style={{display:'flex',gap:6,opacity:hovered?1:0,transition:'opacity 0.15s',flexShrink:0}}>
        {d.proj&&<button onClick={onOpen} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:7,color:T.textSub,fontSize:12,padding:'4px 10px',cursor:'pointer',fontWeight:600}}>Apri →</button>}
        <button onClick={onEdit} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:7,color:T.textSub,fontSize:12,padding:'4px 8px',cursor:'pointer'}}>✏️</button>
        <button onClick={onDelete} style={{background:'none',border:`1px solid ${T.red}44`,borderRadius:7,color:T.red,fontSize:12,padding:'4px 8px',cursor:'pointer'}}>🗑️</button>
      </div>
    </div>
  )
}

// ── DeliveryPage ───────────────────────────────────────────────────────────────
function DeliveryPage({projects,deliveries,onSetDelivery,onNavigateToProject}){
  const[showForm,setShowForm]=useState(false)
  const[editId,setEditId]=useState(null)
  const[form,setForm]=useState({projectId:'',note:'',dueDate:'',delivered:false})
  const[confirm,setConfirm]=useState(null)
  const activeProjects=projects.filter(p=>!p.archived)
  const enriched=deliveries.map(d=>{
    const proj=projects.find(p=>p.id===d.projectId)
    const days=daysUntil(d.dueDate)
    const urgency=deliveryUrgency(days)
    const progress=proj?getProgress(proj):0
    return{...d,proj,days,urgency,progress}
  }).sort((a,b)=>{
    if(a.delivered!==b.delivered) return a.delivered?1:-1
    if(a.days===null) return 1;if(b.days===null) return -1
    return a.days-b.days
  })
  const pending=enriched.filter(d=>!d.delivered)
  const delivered=enriched.filter(d=>d.delivered)
  const urgent=pending.filter(d=>d.days!==null&&d.days<=7)
  function openNew(){setForm({projectId:activeProjects[0]?.id||'',note:'',dueDate:'',delivered:false});setEditId(null);setShowForm(true)}
  function openEdit(d){setForm({projectId:d.projectId,note:d.note||'',dueDate:d.dueDate||'',delivered:d.delivered});setEditId(d.id);setShowForm(true)}
  function save(){
    if(!form.projectId||!form.dueDate) return
    if(editId){
      onSetDelivery(editId,form,true)
    }else{
      onSetDelivery(uid(),form,false)
    }
    setShowForm(false)
  }
  const inputSt={background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:8,padding:'9px 12px',color:T.text,fontSize:14,outline:'none',width:'100%'}
  return(
    <div style={{flex:1,overflowY:'auto',padding:'24px 28px',background:T.bg,fontFamily:"'DM Sans', system-ui"}}>
      {urgent.length>0&&(
        <div style={{background:T.redBg,border:`2px solid ${T.red}44`,borderRadius:14,padding:'16px 20px',marginBottom:24}}>
          <div style={{fontSize:13,fontWeight:800,color:T.red,letterSpacing:'0.08em',marginBottom:10}}>🎯 FOCUS DEL GIORNO — {urgent.length} CONSEGN{urgent.length===1?'A':'E'} URGENTI</div>
          <div style={{display:'flex',flexDirection:'column',gap:8}}>
            {urgent.map(d=>(
              <div key={d.id} style={{display:'flex',alignItems:'center',gap:12,background:'rgba(255,255,255,0.6)',borderRadius:10,padding:'10px 14px'}}>
                <span style={{fontSize:20}}>{d.urgency.dot}</span>
                <div style={{flex:1}}><span style={{fontWeight:700,color:T.text,fontSize:15}}>{d.proj?.name||'—'}</span>{d.note&&<span style={{fontSize:13,color:T.textSub,marginLeft:8}}>{d.note}</span>}</div>
                <span style={{fontSize:13,fontWeight:800,color:d.urgency.color,background:d.urgency.bg,padding:'3px 12px',borderRadius:20,border:`1px solid ${d.urgency.color}44`}}>{d.days===0?'OGGI':d.days<0?`${Math.abs(d.days)}gg fa`:`${d.days}gg`}</span>
                <span style={{fontSize:13,color:T.textSub}}>{d.progress}%</span>
                {d.proj&&<button onClick={()=>onNavigateToProject(d.proj.id)} style={{background:T.red,border:'none',borderRadius:7,color:'#fff',fontSize:12,fontWeight:700,padding:'5px 12px',cursor:'pointer'}}>Apri →</button>}
              </div>
            ))}
          </div>
        </div>
      )}
      <div style={{display:'flex',alignItems:'center',marginBottom:20}}>
        <div style={{fontSize:13,color:T.textSub,fontWeight:700,letterSpacing:'0.06em'}}>CONSEGNE — {pending.length} IN ATTESA</div>
        <button onClick={openNew} style={{marginLeft:'auto',background:T.accent,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:14,padding:'9px 20px',cursor:'pointer'}}>+ Nuova consegna</button>
      </div>
      {showForm&&(
        <div style={{background:T.surface,border:`1.5px solid ${T.accent}44`,borderRadius:14,padding:'20px',marginBottom:20}}>
          <div style={{fontSize:14,fontWeight:700,color:T.text,marginBottom:14}}>{editId?'✏️ Modifica consegna':'+ Nuova consegna'}</div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:12,marginBottom:12}}>
            <div><label style={{fontSize:12,color:T.textSub,fontWeight:700,display:'block',marginBottom:5}}>PROGETTO *</label>
              <select value={form.projectId} onChange={e=>setForm(f=>({...f,projectId:e.target.value}))} style={{...inputSt,appearance:'none'}}>
                <option value=''>— Seleziona —</option>
                {activeProjects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div><label style={{fontSize:12,color:T.textSub,fontWeight:700,display:'block',marginBottom:5}}>DATA DI CONSEGNA *</label><input type='date' value={form.dueDate} onChange={e=>setForm(f=>({...f,dueDate:e.target.value}))} style={inputSt}/></div>
          </div>
          <div style={{marginBottom:14}}><label style={{fontSize:12,color:T.textSub,fontWeight:700,display:'block',marginBottom:5}}>NOTE (opzionale)</label><input value={form.note} onChange={e=>setForm(f=>({...f,note:e.target.value}))} placeholder='Es. consegna parziale, cliente X...' style={inputSt}/></div>
          <div style={{display:'flex',gap:10,justifyContent:'flex-end'}}>
            <button onClick={()=>setShowForm(false)} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:'8px 18px',cursor:'pointer'}}>Annulla</button>
            <button onClick={save} disabled={!form.projectId||!form.dueDate} style={{background:form.projectId&&form.dueDate?T.accent:'#ccc',border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:14,padding:'8px 22px',cursor:form.projectId&&form.dueDate?'pointer':'default'}}>{editId?'Salva modifiche':'Aggiungi'}</button>
          </div>
        </div>
      )}
      {pending.length===0&&!showForm&&(
        <div style={{textAlign:'center',padding:'60px 0'}}>
          <div style={{fontSize:48,marginBottom:16}}>📅</div>
          <div style={{fontSize:18,fontWeight:700,color:T.text,marginBottom:8}}>Nessuna consegna programmata</div>
          <div style={{fontSize:15,color:T.textSub,marginBottom:20}}>Aggiungi le date di consegna dei tuoi progetti</div>
          <button onClick={openNew} style={{background:T.accent,border:'none',borderRadius:10,color:'#fff',fontWeight:700,fontSize:15,padding:'11px 26px',cursor:'pointer'}}>+ Prima consegna</button>
        </div>
      )}
      {pending.length>0&&<div style={{display:'flex',flexDirection:'column',gap:10,marginBottom:32}}>{pending.map(d=><DeliveryRow key={d.id} d={d} onToggle={()=>onSetDelivery(d.id,{delivered:!d.delivered,deliveredAt:!d.delivered?nowStr():null},true)} onEdit={()=>openEdit(d)} onDelete={()=>setConfirm(d.id)} onOpen={()=>d.proj&&onNavigateToProject(d.proj.id)}/>)}</div>}
      {delivered.length>0&&(
        <details style={{marginTop:8}}>
          <summary style={{fontSize:13,color:T.textSub,fontWeight:700,letterSpacing:'0.06em',cursor:'pointer',marginBottom:10}}>✅ CONSEGNATE — {delivered.length}</summary>
          <div style={{display:'flex',flexDirection:'column',gap:8,marginTop:10}}>{delivered.map(d=><DeliveryRow key={d.id} d={d} onToggle={()=>onSetDelivery(d.id,{delivered:!d.delivered,deliveredAt:!d.delivered?nowStr():null},true)} onEdit={()=>openEdit(d)} onDelete={()=>setConfirm(d.id)} onOpen={()=>d.proj&&onNavigateToProject(d.proj.id)}/>)}</div>
        </details>
      )}
      {confirm&&<ConfirmDialog message='Eliminare questa consegna?' onConfirm={()=>{onSetDelivery(confirm,null,null,true);setConfirm(null)}} onCancel={()=>setConfirm(null)}/>}
    </div>
  )
}

// ── NewProjectModal ────────────────────────────────────────────────────────────
function NewProjectModal({onClose,onCreate,templates,preselectedTemplate}){
  const[name,setName]=useState('')
  const[desc,setDesc]=useState('')
  const[color,setColor]=useState(preselectedTemplate?.color||'#D4700A')
  const[selectedTmpl,setSelectedTmpl]=useState(preselectedTemplate||null)
  const[stepsRaw,setStepsRaw]=useState('')
  function selectTmpl(t){setSelectedTmpl(t);if(t)setColor(t.color)}
  function create(){
    if(!name.trim()) return
    const steps=selectedTmpl?cloneTemplateToSteps(selectedTmpl):stepsRaw.split('\n').filter(l=>l.trim()).map(line=>({id:uid(),title:line.trim(),tasks:[]}))
    onCreate({id:uid(),name:name.trim(),description:desc.trim(),color,createdAt:new Date().toISOString().slice(0,10),archived:false,steps:steps.length?steps:[{id:uid(),title:'Step 1',tasks:[]}],log:[],pallet_assegnato:null})
    onClose()
  }
  const inputStyle={width:'100%',background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:10,padding:'10px 14px',color:T.text,fontSize:15,outline:'none'}
  return(
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.45)',display:'flex',alignItems:'center',justifyContent:'center',zIndex:100}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,padding:32,width:540,maxWidth:'92vw',maxHeight:'88vh',overflowY:'auto',boxShadow:'0 12px 48px rgba(0,0,0,0.2)'}}>
        <div style={{fontSize:20,fontWeight:800,color:T.text,marginBottom:22}}>Nuovo Progetto</div>
        <div style={{marginBottom:16}}><label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:6}}>NOME PROGETTO *</label><input autoFocus value={name} onChange={e=>setName(e.target.value)} style={inputStyle} placeholder='Es. 4349_0221'/></div>
        <div style={{marginBottom:22}}><label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:6}}>DESCRIZIONE</label><input value={desc} onChange={e=>setDesc(e.target.value)} style={inputStyle} placeholder='Breve descrizione'/></div>
        <div style={{marginBottom:22}}>
          <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:10}}>PARTI DA UN TEMPLATE</label>
          <div style={{display:'flex',flexWrap:'wrap',gap:8,marginBottom:12}}>
            <button onClick={()=>selectTmpl(null)} style={{background:!selectedTmpl?T.surface2:'transparent',border:`1.5px solid ${!selectedTmpl?T.borderStrong:T.border}`,borderRadius:8,color:!selectedTmpl?T.text:T.textSub,fontSize:13,padding:'7px 14px',cursor:'pointer',fontWeight:600}}>Nessuno</button>
            {templates.map(t=><button key={t.id} onClick={()=>selectTmpl(t)} style={{background:selectedTmpl?.id===t.id?t.color+'18':'transparent',border:`1.5px solid ${selectedTmpl?.id===t.id?t.color:T.border}`,borderRadius:8,color:selectedTmpl?.id===t.id?t.color:T.textSub,fontSize:13,padding:'7px 14px',cursor:'pointer',fontWeight:600}}>{t.icon} {t.name}</button>)}
          </div>
          {selectedTmpl?(
            <div style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:10,padding:'12px 16px'}}>
              <div style={{fontSize:12,color:T.textSub,fontWeight:700,marginBottom:8}}>FASI INCLUSE</div>
              {selectedTmpl.steps.map(s=><div key={s.id} style={{fontSize:14,color:T.text,marginBottom:4,display:'flex',gap:8}}><span style={{color:selectedTmpl.color,fontWeight:700}}>•</span>{s.title} <span style={{color:T.textMuted}}>({(s.tasks||[]).length} task)</span></div>)}
            </div>
          ):(
            <div><label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:6}}>OPPURE INSERISCI FASI (una per riga)</label><textarea value={stepsRaw} onChange={e=>setStepsRaw(e.target.value)} rows={4} placeholder={'Preparazione\nFase 1\nFase 2'} style={{...inputStyle,resize:'vertical'}}/></div>
          )}
        </div>
        <div style={{marginBottom:24}}>
          <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:'block',marginBottom:10}}>COLORE PROGETTO</label>
          <div style={{display:'flex',gap:10}}>{COLORS.map(c=><div key={c} onClick={()=>setColor(c)} style={{width:30,height:30,borderRadius:'50%',background:c,cursor:'pointer',border:color===c?'3px solid #333':'3px solid transparent',transform:color===c?'scale(1.15)':'scale(1)'}}/>)}</div>
        </div>
        <div style={{display:'flex',gap:10,justifyContent:'flex-end'}}>
          <button onClick={onClose} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:10,color:T.textSub,fontSize:15,padding:'10px 22px',cursor:'pointer',fontWeight:600}}>Annulla</button>
          <button onClick={create} style={{background:color,border:'none',borderRadius:10,color:'#fff',fontWeight:800,fontSize:15,padding:'10px 26px',cursor:'pointer'}}>Crea Progetto</button>
        </div>
      </div>
    </div>
  )
}
// ── App principale ─────────────────────────────────────────────────────────────
export default function Progetti(){
  const navigate=useNavigate()
  const[projects,setProjects]=useState([])
  const[templates,setTemplates]=useState([])
  const[palletDisponibili,setPalletDisponibili]=useState([])
  const[deliveries,setDeliveries]=useState([])
  const[loading,setLoading]=useState(true)
  const[error,setError]=useState(null)
  const[page,setPage]=useState('projects')      // projects|archived|templates|templateEditor|backup|consegne
  const[selectedId,setSelectedId]=useState(null)
  const[editingTemplate,setEditingTemplate]=useState(null)
  const[showNewProject,setShowNewProject]=useState(false)
  const[preselectedTemplate,setPreselectedTemplate]=useState(null)
  const[search,setSearch]=useState('')
  const[sidebarCollapsed,setSidebarCollapsed]=useState(false)
  const[lastSavedProj,setLastSavedProj]=useState(null)
  const[lastSavedTmpl,setLastSavedTmpl]=useState(null)
  const[importMsg,setImportMsg]=useState(null)
  const importRef=useRef(null)
  const saveTimer=useRef(null)
  const autoBackupTimer=useRef(null)

  // ── Carica ──────────────────────────────────────────────────────────────────
  const load=useCallback(async()=>{
    try{
      const [r, rd] = await Promise.all([
        fetch(API+'/'),
        fetch(API+'/deliveries')
      ])
      if(!r.ok) throw new Error(`Server error ${r.status}`)
      const d=await r.json()
      const projs = (d.projects||[]).map(p=>({pallet_assegnato:null,...p}))
      setProjects(projs)
      setTemplates(d.templates||[])
      if(rd.ok){ const ds=await rd.json(); setDeliveries(Array.isArray(ds)?ds:[]) }
      setError(null)
    }catch(e){setError(e.message)}
    finally{setLoading(false)}
  },[])
  useEffect(()=>{
    load()
    function caricaPalletDisp(){
      fetch('/api/pallet/disponibili').then(r=>r.ok?r.json():{pallet:[]})
        .then(d=>setPalletDisponibili(d.pallet||[])).catch(()=>{})
    }
    caricaPalletDisp()
    const t=setInterval(caricaPalletDisp,10000)
    return()=>clearInterval(t)
  },[load])

  // Apre il progetto giusto dopo il caricamento (da sessionStorage)
  useEffect(()=>{
    if(!projects.length) return
    // Apertura diretta per ID (da Coda → "Apri progetto")
    const pid = sessionStorage.getItem('dmgdesk_apri_progetto_id')
    if(pid){
      sessionStorage.removeItem('dmgdesk_apri_progetto_id')
      if(projects.find(p=>p.id===pid)) { setSelectedId(pid); return }
    }
    // Apertura per numero pallet (da Coda → "Avvia")
    const pn = sessionStorage.getItem('dmgdesk_apri_per_pallet')
    if(pn){
      sessionStorage.removeItem('dmgdesk_apri_per_pallet')
      const proj = projects.find(p=>p.pallet_assegnato===parseInt(pn))
      if(proj){
        setSelectedId(proj.id)
        sessionStorage.setItem('dmgdesk_apri_modal_lancio','1')
      }
    }
  },[projects])

  // ── Salva progetti (debounced) ───────────────────────────────────────────────
  const persistProjects=useCallback((projs)=>{
    clearTimeout(saveTimer.current)
    saveTimer.current=setTimeout(async()=>{
      try{
        // Salva tutti i progetti modificati in batch
        for(const p of projs){
          await fetch(`${API}/${p.id}`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({data:p})})
        }
        setLastSavedProj(nowStr())
      }catch{}
    },800)
  },[])

  const persistTemplates=useCallback(async(tmpls)=>{
    try{
      await fetch(`${API}/templates/save`,{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({templates:tmpls})})
      setLastSavedTmpl(nowStr())
    }catch{}
  },[])

  // ── CRUD progetti ────────────────────────────────────────────────────────────
  function updateProject(updated){
    setProjects(ps=>{const next=ps.map(p=>p.id===updated.id?updated:p);persistProjects(next);return next})
  }
  function addProject(project){
    setProjects(ps=>{const next=[...ps,project];persistProjects(next);return next})
    setLastSavedProj(nowStr())
  }
  async function deleteProject(id){
    setProjects(ps=>ps.filter(p=>p.id!==id))
    setSelectedId(null)
    try{await fetch(`${API}/${id}`,{method:'DELETE'})}catch{}
  }
  function archiveProject(id){
    setProjects(ps=>{const next=ps.map(p=>p.id===id?{...p,archived:!p.archived}:p);persistProjects(next);return next})
    setSelectedId(null)
  }

  // ── CRUD template ────────────────────────────────────────────────────────────
  function saveTemplate(tmpl){
    setTemplates(ts=>{const next=ts.some(t=>t.id===tmpl.id)?ts.map(t=>t.id===tmpl.id?tmpl:t):[...ts,tmpl];persistTemplates(next);return next})
    setPage('templates');setEditingTemplate(null)
  }
  function deleteTemplate(id){setTemplates(ts=>{const next=ts.filter(t=>t.id!==id);persistTemplates(next);return next})}
  function duplicateTemplate(tmpl){
    const copy={...tmpl,id:uid(),name:`${tmpl.name} (copia)`,steps:tmpl.steps.map(s=>({...s,id:uid(),tasks:(s.tasks||[]).map(t=>({...t,id:uid()}))}))}
    setTemplates(ts=>{const idx=ts.findIndex(t=>t.id===tmpl.id);const next=[...ts];next.splice(idx+1,0,copy);persistTemplates(next);return next})
  }
  function useTemplate(tmpl){setPreselectedTemplate(tmpl);setShowNewProject(true);setPage('projects')}

  // ── Consegne ─────────────────────────────────────────────────────────────────
  function setDelivery(id,patch,isUpdate,isDelete){
    setDeliveries(ds=>{
      let next
      if(isDelete) next=ds.filter(d=>d.id!==id)
      else if(isUpdate) next=ds.map(d=>d.id===id?{...d,...patch}:d)
      else next=[...ds,{id,createdAt:nowStr(),...patch}]
      // Persiste subito su disco — usa setTimeout per uscire dal batch React
      const toSave=next
      setTimeout(()=>{
        fetch(API+'/deliveries',{method:'PUT',headers:{'Content-Type':'application/json'},
          body:JSON.stringify(toSave)}).catch(()=>{})
      },0)
      return next
    })
  }
  function getDelivery(projectId){return deliveries.find(d=>d.projectId===projectId)||null}

  // ── Import/Export backup ─────────────────────────────────────────────────────
  async function handleImport(e,mode='merge'){
    const file=e.target.files?.[0];if(!file) return
    try{
      const text=await file.text()
      const parsed=JSON.parse(text)
      if(!parsed._worktrack&&!parsed._worktrack_backup) throw new Error('File non riconosciuto')
      if(!Array.isArray(parsed.projects)||!Array.isArray(parsed.templates)) throw new Error('Struttura backup non valida')
      const r=await fetch(`${API}/import`,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({projects:parsed.projects,templates:parsed.templates,mode})})
      if(!r.ok) throw new Error(`Errore server ${r.status}`)
      const res=await r.json()
      setImportMsg(`✓ ${res.progetti} progetti e ${res.templates} template importati (${mode})`)
      await load()
    }catch(err){setImportMsg(`⚠ ${err.message}`)}
    e.target.value=''
  }
  function handleExport(){window.open(`${API}/export`,'_blank')}

  // ── Lancia NC ───────────────────────────────────────────────────────────────
  function lanciaNC(project, pgmSelezionati){
    // pgmSelezionati = array di programmi scelti nel modal
    // Se non passati (chiamata diretta), usa tutti i da_fare
    const mpf = pgmSelezionati || (project.steps||[])
      .flatMap(s=>s.tasks||[])
      .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
      .flatMap(t=>(t.programs||[]).filter(p=>p.tipoGruppo!=='ipm'&&p.stato==='da_fare'))
    if(!mpf.length) return
    // nomeCartella: usa nome progetto come fonte primaria
    // Fallback su pattern file MPF solo se nome progetto è troppo generico
    const nomeFromProject = project.name.replace(/\s+/g,'_').replace(/[^a-zA-Z0-9_]/g,'').toUpperCase()
    const firstFile = mpf[0]?.filename || ''
    const baseTokens = firstFile.replace(/\.MPF$/i,'').split('_')
    const nomeFromFile = /^\d+$/.test(baseTokens[0]) && baseTokens.length >= 2
      ? `${baseTokens[0]}_${baseTokens[1]}`
      : null
    const nomeCartella = nomeFromProject || nomeFromFile || ''

    sessionStorage.setItem('dmgdesk_lancio_nc', JSON.stringify({
      projectId:   project.id,
      projectName: project.name,
      nomeCartella,
      mpfFiles:    mpf.map(p=>p.filename)
    }))
    navigate('/analisi-nc')
  }

  // ── Dati derivati ────────────────────────────────────────────────────────────
  const selectedProject=projects.find(p=>p.id===selectedId)
  const isOnEditor=page==='templateEditor'&&editingTemplate
  const isOnProject=!!selectedProject
  const activeProjects=projects.filter(p=>!p.archived&&(search===''||p.name.toLowerCase().includes(search.toLowerCase())||(p.description||'').toLowerCase().includes(search.toLowerCase())))
  const archivedProjects=projects.filter(p=>p.archived)
  const inProgress=activeProjects.filter(p=>getProgress(p)<100).sort((a,b)=>{
    const da=getDelivery(a.id);const db=getDelivery(b.id)
    const daysA=da&&da.dueDate&&!da.delivered?daysUntil(da.dueDate):9999
    const daysB=db&&db.dueDate&&!db.delivered?daysUntil(db.dueDate):9999
    if(daysA!==daysB) return daysA-daysB
    return getProgress(a)-getProgress(b)
  })
  const completed=activeProjects.filter(p=>getProgress(p)===100)
  const urgentProjects=inProgress.filter(p=>{const d=getDelivery(p.id);const days=d&&d.dueDate&&!d.delivered?daysUntil(d.dueDate):null;return days!==null&&days<=7})

  const NavBtn=({id,label,badge})=>(
    <button onClick={()=>{setPage(id);setSelectedId(null);setEditingTemplate(null)}}
      style={{background:'none',border:'none',cursor:'pointer',color:page===id&&!isOnProject&&!isOnEditor?T.accent:T.textSub,fontSize:15,fontWeight:700,padding:'16px 0',borderBottom:page===id&&!isOnProject&&!isOnEditor?`3px solid ${T.accent}`:'3px solid transparent',marginRight:24,transition:'all 0.15s',display:'flex',alignItems:'center',gap:7}}>
      {label}
      {badge>0&&<span style={{background:T.surface2,border:`1px solid ${T.border}`,color:T.textSub,borderRadius:20,fontSize:12,padding:'1px 8px',fontWeight:700}}>{badge}</span>}
    </button>
  )

  if(loading) return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:T.textMuted,background:T.bg,fontFamily:"'DM Sans', system-ui"}}>Caricamento...</div>

  return(
    <div style={{height:'100%',display:'flex',flexDirection:'column',background:T.bg,fontFamily:"'DM Sans', system-ui, sans-serif",color:T.text}}>
      <style>{`@import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');*{box-sizing:border-box}input,textarea,select{font-family:inherit}`}</style>

      {/* TOP BAR */}
      {!isOnProject&&!isOnEditor&&(
        <div style={{borderBottom:`1px solid ${T.border}`,padding:'0 28px',display:'flex',alignItems:'center',gap:0,flexShrink:0,background:T.surface,boxShadow:'0 1px 0 rgba(0,0,0,0.06)'}}>
          <div style={{fontSize:20,fontWeight:800,color:T.text,letterSpacing:'-0.02em',padding:'16px 16px 16px 0',marginRight:4,borderRight:`1px solid ${T.border}`}}><span style={{color:T.accent}}>◈</span> WorkTrack</div>
          <NavBtn id='projects' label='Progetti'/>
          <NavBtn id='archived' label='Archivio' badge={archivedProjects.length}/>
          <NavBtn id='templates' label={`Template (${templates.length})`}/>
          <NavBtn id='consegne' label='Consegne' badge={deliveries.filter(d=>!d.delivered&&daysUntil(d.dueDate)!==null&&daysUntil(d.dueDate)<=7).length}/>
          <NavBtn id='backup' label='Backup'/>
          {page==='projects'&&!isOnProject&&(
            <div style={{marginLeft:'auto',display:'flex',gap:12,alignItems:'center'}}>
              <input value={search} onChange={e=>setSearch(e.target.value)} placeholder='Cerca progetto...'
                style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,padding:'8px 14px',color:T.text,fontSize:14,outline:'none',width:200}}/>
              <span style={{fontSize:14,color:T.textSub,fontWeight:600}}>{inProgress.length} attivi</span>
              <button onClick={()=>{setPreselectedTemplate(null);setShowNewProject(true)}} style={{background:T.accent,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:14,padding:'9px 20px',cursor:'pointer'}}>+ Nuovo Progetto</button>
            </div>
          )}
        </div>
      )}

      {/* CONTENT + SIDEBAR */}
      <div style={{flex:1,overflow:'hidden',display:'flex',flexDirection:'row'}}>
        <div style={{flex:1,overflow:'hidden',display:'flex',flexDirection:'column'}}>
          {isOnEditor?(
            <TemplateEditor template={editingTemplate} onSave={saveTemplate} onCancel={()=>{setPage('templates');setEditingTemplate(null)}}/>
          ):isOnProject?(
            <ProjectDetail project={selectedProject} onBack={()=>setSelectedId(null)} onUpdate={updateProject} onDelete={deleteProject} onArchive={archiveProject} templates={templates} onSaveAsTemplate={tmpl=>{setTemplates(ts=>{const next=ts.some(t=>t.id===tmpl.id)?ts.map(t=>t.id===tmpl.id?tmpl:t):[...ts,tmpl];persistTemplates(next);return next})}} onLanciaNC={lanciaNC} palletDisponibili={palletDisponibili}/>
          ):page==='templates'?(
            <TemplatesPage templates={templates} onEdit={tmpl=>{setEditingTemplate(tmpl);setPage('templateEditor')}} onCreate={()=>{setEditingTemplate({id:`new_${uid()}`,name:'Nuovo Template',description:'',icon:'🚀',color:'#D4700A',steps:[]});setPage('templateEditor')}} onDelete={deleteTemplate} onDuplicate={duplicateTemplate} onUseTemplate={useTemplate} lastSaved={lastSavedTmpl}/>
          ):page==='consegne'?(
            <DeliveryPage projects={projects} deliveries={deliveries} onSetDelivery={setDelivery} onNavigateToProject={id=>{setSelectedId(id);setPage('projects')}}/>
          ):page==='backup'?(
            <div style={{flex:1,overflowY:'auto',padding:'28px',background:T.bg}}>
              <div style={{maxWidth:560}}>
                <div style={{fontSize:20,fontWeight:800,color:T.text,marginBottom:4}}>💾 Backup & Importazione</div>
                <div style={{fontSize:13,color:T.textMuted,marginBottom:24}}>Importa un backup da WorkTrack standalone o esporta i dati correnti.</div>
                {importMsg&&<div style={{padding:'10px 14px',borderRadius:8,background:importMsg.startsWith('⚠')?T.redBg:T.greenBg,border:`1px solid ${importMsg.startsWith('⚠')?T.red:T.green}44`,color:importMsg.startsWith('⚠')?T.red:T.green,fontSize:13,marginBottom:16}}>{importMsg}</div>}
                <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:20,marginBottom:16}}>
                  <div style={{fontSize:15,fontWeight:700,color:T.text,marginBottom:6}}>📥 Importa backup</div>
                  <div style={{fontSize:13,color:T.textMuted,marginBottom:16}}>Carica un file <code>.json</code> esportato da WorkTrack o da DMGDesk.</div>
                  <div style={{display:'flex',gap:10}}>
                    <input ref={importRef} type='file' accept='.json' style={{display:'none'}} onChange={e=>handleImport(e,'merge')}/>
                    <button onClick={()=>importRef.current?.click()} style={{background:T.accent,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:13,padding:'9px 18px',cursor:'pointer'}}>+ Importa (merge)</button>
                    <input type='file' accept='.json' style={{display:'none'}} onChange={e=>handleImport(e,'replace')} id='import-replace'/>
                    <button onClick={()=>document.getElementById('import-replace')?.click()} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontWeight:600,fontSize:13,padding:'9px 18px',cursor:'pointer'}}>Sostituisci tutto</button>
                  </div>
                  <div style={{fontSize:11,color:T.textMuted,marginTop:10}}><b>Merge</b>: aggiunge senza cancellare (consigliato) · <b>Sostituisci</b>: cancella tutto e importa</div>
                </div>
                <div style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:20,marginBottom:16}}>
                  <div style={{fontSize:15,fontWeight:700,color:T.text,marginBottom:6}}>📤 Esporta backup</div>
                  <div style={{fontSize:13,color:T.textMuted,marginBottom:16}}>Scarica tutti i progetti e template come file JSON compatibile con WorkTrack.</div>
                  <button onClick={handleExport} style={{background:T.blue,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:13,padding:'9px 18px',cursor:'pointer'}}>💾 Scarica backup completo</button>
                </div>
                <div style={{background:T.blueBg,border:`1px solid ${T.blue}33`,borderRadius:10,padding:'14px 18px',display:'flex',gap:12,alignItems:'flex-start'}}>
                  <span style={{fontSize:20,flexShrink:0}}>💡</span>
                  <div style={{fontSize:13,color:T.blue,lineHeight:1.7}}>I dati vengono salvati in tempo reale su <code>P:\DMG_DMC_160U\worktrack_projects.json</code> condiviso tra web e desktop.</div>
                </div>
              </div>
            </div>
          ):page==='archived'?(
            <div style={{flex:1,overflowY:'auto',padding:'24px 28px',background:T.bg}}>
              <div style={{fontSize:13,color:T.textSub,fontWeight:600,letterSpacing:'0.06em',marginBottom:18}}>ARCHIVIO — {archivedProjects.length} PROGETTI</div>
              {archivedProjects.length===0&&(
                <div style={{textAlign:'center',padding:'60px 0'}}>
                  <div style={{fontSize:48,marginBottom:16}}>📦</div>
                  <div style={{fontSize:18,fontWeight:700,color:T.text,marginBottom:8}}>Archivio vuoto</div>
                  <div style={{fontSize:15,color:T.textSub}}>Usa il pulsante 📦 su un progetto per archiviarlo.</div>
                </div>
              )}
              <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill, minmax(300px, 1fr))',gap:14}}>
                {archivedProjects.map(p=><ProjectCard key={p.id} project={p} onClick={()=>setSelectedId(p.id)} onDelete={deleteProject} onArchive={archiveProject} delivery={getDelivery(p.id)} onSetDelivery={(pid,date,toggle)=>{const d=getDelivery(pid);if(toggle!==undefined&&d)setDelivery(d.id,{delivered:toggle,deliveredAt:toggle?nowStr():null},true);else if(date!==null)d?setDelivery(d.id,{dueDate:date},true):setDelivery(uid(),{projectId:pid,dueDate:date,delivered:false},false);else if(d)setDelivery(d.id,{dueDate:''},true)}}/>)}
              </div>
            </div>
          ):(
            <div style={{flex:1,overflowY:'auto',padding:'24px 28px',background:T.bg}}>
              {inProgress.length===0&&completed.length===0&&(
                <div style={{textAlign:'center',padding:'80px 0'}}>
                  <div style={{fontSize:48,marginBottom:16}}>🚀</div>
                  <div style={{fontSize:20,fontWeight:700,color:T.text,marginBottom:8}}>Nessun progetto ancora</div>
                  <div style={{fontSize:15,color:T.textSub,marginBottom:24}}>Crea il tuo primo progetto per iniziare</div>
                  <button onClick={()=>setShowNewProject(true)} style={{background:T.accent,border:'none',borderRadius:10,color:'#fff',fontWeight:700,fontSize:16,padding:'12px 28px',cursor:'pointer'}}>+ Crea il primo progetto</button>
                </div>
              )}
              {urgentProjects.length>0&&(
                <div style={{background:T.redBg,border:`1.5px solid ${T.red}33`,borderRadius:14,padding:'14px 18px',marginBottom:22,display:'flex',alignItems:'center',gap:10}}>
                  <span style={{fontSize:22}}>🎯</span>
                  <div>
                    <div style={{fontSize:13,fontWeight:800,color:T.red,letterSpacing:'0.07em'}}>FOCUS — {urgentProjects.length} CONSEGN{urgentProjects.length===1?'A':'E'} ENTRO 7 GIORNI</div>
                    <div style={{fontSize:13,color:T.textSub,marginTop:2}}>{urgentProjects.map(p=>p.name).join(' · ')}</div>
                  </div>
                </div>
              )}
              {inProgress.length>0&&(
                <>
                  <div style={{fontSize:13,color:T.textSub,fontWeight:700,letterSpacing:'0.06em',marginBottom:14}}>IN CORSO — {inProgress.length} · ordinati per priorità</div>
                  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill, minmax(320px, 1fr))',gap:14,marginBottom:32}}>
                    {inProgress.map(p=>{
                      const d=getDelivery(p.id)
                      return <ProjectCard key={p.id} project={p} onClick={()=>setSelectedId(p.id)} onDelete={deleteProject} onArchive={archiveProject} delivery={d}
                        onSetDelivery={(pid,date,toggle)=>{if(toggle!==undefined&&d)setDelivery(d.id,{delivered:toggle,deliveredAt:toggle?nowStr():null},true);else if(date!==null)d?setDelivery(d.id,{dueDate:date},true):setDelivery(uid(),{projectId:pid,dueDate:date,delivered:false},false);else if(d)setDelivery(d.id,{dueDate:''},true)}}/>
                    })}
                  </div>
                </>
              )}
              {completed.length>0&&(
                <>
                  <div style={{fontSize:13,color:T.textSub,fontWeight:700,letterSpacing:'0.06em',marginBottom:14}}>COMPLETATI — {completed.length}</div>
                  <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill, minmax(320px, 1fr))',gap:14}}>
                    {completed.map(p=>{
                      const d=getDelivery(p.id)
                      return <ProjectCard key={p.id} project={p} onClick={()=>setSelectedId(p.id)} onDelete={deleteProject} onArchive={archiveProject} delivery={d}
                        onSetDelivery={(pid,date,toggle)=>{if(toggle!==undefined&&d)setDelivery(d.id,{delivered:toggle,deliveredAt:toggle?nowStr():null},true);else if(date!==null)d?setDelivery(d.id,{dueDate:date},true):setDelivery(uid(),{projectId:pid,dueDate:date,delivered:false},false);else if(d)setDelivery(d.id,{dueDate:''},true)}}/>
                    })}
                  </div>
                </>
              )}
            </div>
          )}
        </div>
        <QuickTasksSidebar collapsed={sidebarCollapsed} onToggleCollapse={()=>setSidebarCollapsed(v=>!v)}/>
      </div>

      {showNewProject&&(
        <NewProjectModal onClose={()=>{setShowNewProject(false);setPreselectedTemplate(null)}} onCreate={p=>{addProject(p);setShowNewProject(false);setPreselectedTemplate(null)}} templates={templates} preselectedTemplate={preselectedTemplate}/>
      )}
    </div>
  )
}
