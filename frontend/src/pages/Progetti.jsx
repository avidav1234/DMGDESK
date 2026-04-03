// Progetti.jsx — WorkTrack porting fedele COMPLETO per DMGDesk
// Persistenza su file via /api/progetti — identico all'app originale

import { useState, useEffect, useCallback, useRef, createContext, useContext } from 'react'
import { useNavigate, useLocation } from 'react-router-dom'
import TabDocumenti from './TabDocumenti'

const API = '/api/progetti'


// ── Context selezione programmi ─────────────────────────────────────────────
const PgmSelContext = createContext({ selectedIds: new Set(), setSelectedIds: ()=>{} })

// ── Tema allineato al sistema blu navy ────────────────────────────────────────
const T = {
  bg:'#eef2f7', surface:'#ffffff', surface2:'#f8fafc',
  border:'#e2e8f0', borderStrong:'#cbd5e1',
  text:'#0f172a', textSub:'#475569', textMuted:'#94a3b8',
  accent:'#0d2d5e', accentBg:'#e6f1fb',
  green:'#16a34a', greenBg:'#f0fdf4',
  red:'#dc2626', redBg:'#fef2f2',
  blue:'#0d2d5e', blueBg:'#e6f1fb',
}
const COLORS = ['#0d2d5e','#16a34a','#0d2d5e','#dc2626','#7c3aed','#be185d','#0891b2','#d97706']
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
  if(days===null) return {label:'Nessuna data',         color:T.textMuted, bg:T.surface2, dot:'⚪',rank:4}
  if(days<0)     return {label:`Scaduta ${Math.abs(days)}gg fa`, color:'#fff', bg:T.red, dot:'💀',rank:0}
  if(days===0)   return {label:'OGGI',                  color:'#fff',      bg:T.red,     dot:'🚨',rank:0}
  if(days===0)   return {label:'OGGI',          color:'#fff',    bg:T.red,     dot:'🚨',rank:0}
  if(days<=3)    return {label:`${days}gg`,     color:T.red,     bg:T.redBg,   dot:'🔴',rank:1}
  if(days<=7)    return {label:`${days}gg`,     color:'#1e40af', bg:'#FFF0DC', dot:'🟠',rank:2}
  if(days<=21)   return {label:`${days}gg`,     color:T.accent,  bg:T.accentBg,dot:'🟡',rank:3}
  return               {label:`${days}gg`,     color:T.green,   bg:T.greenBg, dot:'🟢',rank:4}
}

// ── MPF parser ─────────────────────────────────────────────────────────────────
function parseMpfFile(filename,content){
  const lines=content.split(/\r?\n/)
  // get() prende tutto dopo il primo ':' — NON greedy per non troncare timestamp HH:MM:SS
  const get=(label)=>{const l=lines.find(l=>l.includes(label));return l?(l.indexOf(':')>=0?l.slice(l.indexOf(':')+1).trim():''):''}
  const opLine=lines.find(l=>/N\d+;/.test(l)&&!l.includes('DIAMETER')&&!l.includes('TOOL COMMENT')&&!l.includes('CIMATRON')&&!l.includes('DOCUMENTO')&&!l.includes('UTENTE')&&!l.includes('POST')&&!l.includes('REVISIONE')&&!l.includes('DATA')&&!l.includes('N.UT')&&l.includes(';')&&l.replace(/N\d+;\s*/,'').trim().length>3)
  const tipoOp=opLine?opLine.replace(/N\d+;\s*/,'').trim():''
  // Utensile: legge T="alias" dalla riga immediatamente prima di M6
  // Più affidabile di TOOL COMMENT che è un commento Cimatron potenzialmente stale
  let utensile = ''
  const m6Idx = lines.findIndex(l => /\bM6\b/.test(l))
  if (m6Idx > 0) {
    // Risale fino a 5 righe prima di M6 cercando T = "..."
    for (let i = m6Idx - 1; i >= Math.max(0, m6Idx - 5); i--) {
      const m = lines[i].match(/T\s*=\s*"([^"]+)"/)
      if (m) { utensile = m[1].trim(); break }
    }
  }
  // Fallback a TOOL COMMENT se T= non trovato
  if (!utensile) {
    const toolLine = lines.find(l => l.includes('TOOL COMMENT:'))
    if (toolLine) utensile = toolLine.replace(/.*TOOL COMMENT:\s*/, '').trim()
  }
  const diaLine=lines.find(l=>l.includes('DIAMETER:'))
  const diametro=diaLine?diaLine.replace(/.*DIAMETER:\s*/,'').replace(/CORNER.*/,'').trim():''
  // DATA ESECUZIONE POST: "9/3/2026 - 13:16:35" → "09/03/2026 13:16"
  const dataPostRaw=get('DATA ESECUZIONE POST')
  const dataPost=(()=>{
    if(!dataPostRaw) return ''
    try{
      const m=dataPostRaw.match(/(\d{1,2})\/(\d{1,2})\/(\d{4}).*?(\d{1,2}):(\d{2})/)
      if(m){
        const [,d,mo,y,h,mi]=m
        return `${d.padStart(2,'0')}/${mo.padStart(2,'0')}/${y} ${h}:${mi}`
      }
    }catch{}
    return dataPostRaw
  })()
  const isIPM=/[_\-]IPM[_\-]/i.test(filename)||utensile.toUpperCase().includes('RENISHAW')
  const tipoGruppo=isIPM?'ipm':'fresatura'
  const baseName=filename.replace(/\.MPF$/i,'')
  const tokens=baseName.split('_')
  const ipmIdx=tokens.findIndex(t=>t.toUpperCase()==='IPM')
  const numPgm=ipmIdx>=0&&tokens[ipmIdx+1]?tokens[ipmIdx+1]:tokens[tokens.length-1]
  const fase=tokens.length>=3?tokens[tokens.length-(isIPM?3:2)]:''
  // Somma TUTTI i tempi M6 — ogni utensile ha il suo TEMPO
  // es: "M6 ; TEMPO: 00:01:29" → ogni riga M6 contribuisce al totale
  function parseTempo(raw){
    if(!raw) return null
    if(raw.includes(':')){
      const p=raw.split(':').map(Number)
      if(p.length===3) return p[0]*60+p[1]+Math.round(p[2]/60)
      if(p.length===2) return p[0]+Math.round(p[1]/60)
    }
    const n=parseInt(raw); return isNaN(n)?null:n
  }
  const m6Lines=lines.filter(l=>/\bM6\b/.test(l)&&/TEMPO\s*:/i.test(l))
  const tempoTotale=m6Lines.reduce((acc,l)=>{
    const raw=(l.match(/TEMPO\s*:\s*([\d:]+)/i)||[])[1]
    return acc+(parseTempo(raw)||0)
  },0)
  const tempoStimato=tempoTotale>0?tempoTotale:null
  return{numPgm,fase,tipoOp,utensile,diametro,dataPost,filename,tipoGruppo,tempoStimato}
}

const STATO_NEXT={da_fare:'in_main',in_main:'in_lavorazione',in_lavorazione:'completato',completato:'da_fare'}
const STATO_CFG={
  da_fare:      {label:'Da fare',       short:'Da fare',   color:T.textMuted, bg:T.surface2,  border:T.border,   dot:'○'},
  in_main:      {label:'In Main',        short:'In Main',   color:'#92400e',  bg:'#fef3c7',  border:'#d97706',  dot:'📋'},
  in_lavorazione:{label:'In Lavorazione',short:'In Lav.',   color:'#1e40af',  bg:'#dbeafe',  border:'#3b82f6',  dot:'⚙'},
  in_macchina:  {label:'In Lavorazione', short:'In Lav.',   color:'#1e40af',  bg:'#dbeafe',  border:'#3b82f6',  dot:'⚙'},
  completato:   {label:'Completato',     short:'Fatto',     color:'#166534',  bg:'#dcfce7',  border:'#166534',  dot:'✓'},
}
const _sc = (stato) => STATO_CFG[stato] || STATO_CFG.da_fare
const _scNext = (stato) => STATO_CFG[STATO_NEXT[stato] || 'da_fare'] || STATO_CFG.da_fare
const OPERATORI=['I.Dodon','Operatore 2','Operatore 3']
const PRIORITY={
  alta: {label:'Alta', color:'#dc2626',bg:'#fef2f2',dot:'🔴'},
  media:{label:'Media',color:'#0d2d5e',bg:'#e6f1fb',dot:'🟡'},
  bassa:{label:'Bassa',color:'#16a34a',bg:'#f0fdf4',dot:'🟢'},
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
function ProgramRow({pgm,gruppo,onStato,onOperatore,onTempo,onRemove,toolStatus,selected,onSelect}){
  const[expanded,setExpanded]=useState(false)
  const[editTempo,setEditTempo]=useState(pgm.tempoStimato||'')
  const[editingT,setEditingT]=useState(false)
  const sc=_sc(pgm.stato)
  const opClean=(pgm.tipoOp||'').replace(/[-–]\s*NESSUN TESTO\s*/gi,'').replace(/MISURAZIONE NEL PROCESSO[-–]?/gi,'MISURA ').trim()
  return(
    <div style={{borderBottom:`1px solid ${T.border}`,background:selected?'#EFF6FF':pgm.stato==='completato'?'#f0fdf4':['in_main','in_lavorazione','in_macchina'].includes(pgm.stato)?'#eff6ff':T.surface,opacity:pgm.stato==='completato'&&!selected?0.75:1,transition:'background 0.15s'}}>
      <div style={{display:'flex',alignItems:'center',minHeight:38}}>
        {/* Checkbox */}
        <div onClick={e=>{e.stopPropagation();onSelect&&onSelect()}}
          style={{flexShrink:0,width:32,display:'flex',alignItems:'center',justifyContent:'center',alignSelf:'stretch',borderRight:`1px solid ${T.border}`,cursor:'pointer',background:selected?'#DBEAFE':'transparent'}}>
          <div style={{width:16,height:16,borderRadius:4,border:selected?'none':'2px solid #B0ADA4',background:selected?'#0d2d5e':'transparent',display:'flex',alignItems:'center',justifyContent:'center',flexShrink:0}}>
            {selected&&<span style={{color:'#fff',fontSize:11,fontWeight:800,lineHeight:1}}>✓</span>}
          </div>
        </div>
        <div onClick={()=>onStato(STATO_NEXT[pgm.stato])} title={`→ ${_scNext(pgm.stato).label}`}
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
            {pgm.tempoInizio&&<span style={{fontSize:10,color:'#0d2d5e',fontFamily:'monospace',whiteSpace:'nowrap'}}>▶ {pgm.tempoInizio}</span>}
            {pgm.tempoFine&&<span style={{fontSize:10,color:'#166534',fontFamily:'monospace',whiteSpace:'nowrap'}}>■ {pgm.tempoFine}</span>}
          </div>
        )}
        {/* Tempo stimato + data post — sempre visibili */}
        <div style={{flexShrink:0,padding:'0 8px',borderLeft:`1px solid ${T.border}`,alignSelf:'stretch',display:'flex',flexDirection:'column',justifyContent:'center',minWidth:60,alignItems:'flex-end'}}>
          {pgm.tempoStimato&&<span style={{fontSize:11,fontWeight:700,color:'#475569',whiteSpace:'nowrap'}}>⏱ {pgm.tempoStimato}m</span>}
          {pgm.dataPost&&<span style={{fontSize:9,color:T.textMuted,fontFamily:'monospace',whiteSpace:'nowrap'}}>📅 {pgm.dataPost}</span>}
        </div>
        <div onClick={()=>setExpanded(v=>!v)} style={{flexShrink:0,width:28,borderLeft:`1px solid ${T.border}`,alignSelf:'stretch',display:'flex',alignItems:'center',justifyContent:'center',cursor:'pointer',color:T.textMuted,fontSize:11}}>{expanded?'▲':'▼'}</div>
      </div>
      {expanded&&(
        <div style={{padding:'10px 14px',background:T.surface2,borderTop:`1px solid ${T.border}`,
          display:'grid',gridTemplateColumns:'160px 160px 1fr auto auto',gap:16,alignItems:'end'}}>
          {/* OPERATORE */}
          <div>
            <div style={{fontSize:10,color:T.textMuted,fontWeight:700,letterSpacing:'0.06em',marginBottom:4}}>OPERATORE</div>
            <select value={pgm.operatore||''} onChange={e=>onOperatore(e.target.value)}
              style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:6,
                color:pgm.operatore?T.text:T.textMuted,fontSize:12,padding:'4px 10px',outline:'none',cursor:'pointer',width:'100%'}}>
              <option value=''>— Seleziona</option>
              {OPERATORI.map(o=><option key={o} value={o}>{o}</option>)}
            </select>
          </div>
          {/* TEMPO STIMATO */}
          <div>
            <div style={{fontSize:10,color:T.textMuted,fontWeight:700,letterSpacing:'0.06em',marginBottom:4}}>TEMPO STIMATO</div>
            {editingT?(
              <div style={{display:'flex',gap:5}}>
                <input value={editTempo} onChange={e=>setEditTempo(e.target.value)} placeholder='es. 45 o 00:35:00' autoFocus
                  style={{flex:1,background:T.surface,border:'1.5px solid #1D5FAD44',borderRadius:6,padding:'4px 8px',color:T.text,fontSize:12,outline:'none'}}
                  onKeyDown={e=>{if(e.key==='Enter'){onTempo(editTempo);setEditingT(false)}if(e.key==='Escape')setEditingT(false)}}/>
                <button onClick={()=>{onTempo(editTempo);setEditingT(false)}}
                  style={{background:'#0d2d5e',border:'none',borderRadius:5,color:'#fff',fontSize:11,fontWeight:700,padding:'4px 9px',cursor:'pointer'}}>OK</button>
              </div>
            ):(
              <button onClick={()=>setEditingT(true)}
                style={{background:'none',border:`1px dashed ${T.border}`,borderRadius:6,
                  color:pgm.tempoStimato?T.text:T.textMuted,fontSize:12,padding:'4px 10px',cursor:'pointer'}}>
                ⏱ {pgm.tempoStimato||'Aggiungi'}
              </button>
            )}
          </div>
          {/* FILE + data post */}
          <div>
            <div style={{fontSize:10,color:T.textMuted,fontWeight:700,letterSpacing:'0.06em',marginBottom:4}}>FILE</div>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <span style={{fontSize:11,color:T.textMuted,fontFamily:'monospace'}}>{pgm.filename}</span>
              {pgm.dataPost&&<span style={{fontSize:10,color:T.textMuted,fontFamily:'monospace',flexShrink:0}}>📅 {pgm.dataPost}</span>}
            </div>
          </div>
          {/* STATO */}
          <div>
            <div style={{fontSize:10,color:T.textMuted,fontWeight:700,letterSpacing:'0.06em',marginBottom:4}}>STATO</div>
            <div style={{display:'flex',gap:4}}>
              {Object.entries(STATO_CFG).filter(([key])=>key!=='in_macchina').map(([key,s])=>(
                <button key={key} onClick={()=>onStato(key)}
                  style={{background:pgm.stato===key?s.bg:'transparent',
                    border:`1.5px solid ${pgm.stato===key?s.border:T.border}`,
                    borderRadius:6,color:pgm.stato===key?s.color:T.textMuted,
                    fontSize:11,fontWeight:700,padding:'3px 10px',cursor:'pointer'}}>
                  {s.dot} {s.label}
                </button>
              ))}
            </div>
          </div>
          {/* RIMUOVI */}
          <div>
            <div style={{fontSize:10,color:'transparent',marginBottom:4}}>_</div>
            <button onClick={onRemove}
              style={{background:'none',border:`1px solid ${T.red}44`,borderRadius:6,
                color:T.red,fontSize:11,padding:'3px 10px',cursor:'pointer'}}>
              🗑 Rimuovi
            </button>
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
  const[uploadMsg,setUploadMsg]=useState(null)
  const { selectedIds: selected, setSelectedIds: setSelected } = useContext(PgmSelContext)
  const TOOL_BADGE={
    ok:          {dot:'✓',color:'#166534',bg:'#dcfce7'},
    fin_vita:    {dot:'⚠',color:'#B45309',bg:'#FEF3C7'},
    disabilitato:{dot:'⊘',color:'#9333EA',bg:'#F3E8FF'},
    mancante:    {dot:'✗',color:'#dc2626',bg:'#fef2f2'},
  }
  const ipmPrograms=programs.filter(p=>p.tipoGruppo==='ipm')
  const fresPrograms=programs.filter(p=>p.tipoGruppo!=='ipm')
  const doneTotal=programs.filter(p=>p.stato==='completato').length
  const inMacchina=programs.filter(p=>['in_main','in_lavorazione','in_macchina'].includes(p.stato)).length
  const total=programs.length
  const allDone=total>0&&doneTotal===total
  function updatePrograms(newPrograms){
    const allComplete=newPrograms.length>0&&newPrograms.every(p=>p.stato==='completato')
    onUpdateTask({...task,programs:newPrograms,done:allComplete,doneAt:allComplete?new Date().toISOString().slice(0,10):task.doneAt})
  }
  async function handleFileUpload(e){
    const files=Array.from(e.target.files)
    let nuovi=0, aggiornati=0
    let updatedPrograms=[...programs]
    for(const file of files){
      const text=await file.text()
      const info=parseMpfFile(file.name,text)
      const existing=updatedPrograms.find(p=>p.filename===info.filename)
      if(existing){
        // Aggiorna metadati, mantieni stato/tempi/operatore
        updatedPrograms=updatedPrograms.map(p=>p.filename===info.filename?{
          ...p,
          utensile:   info.utensile   || p.utensile,
          diametro:   info.diametro   || p.diametro,
          tipoOp:     info.tipoOp     || p.tipoOp,
          tempoStimato: info.tempoStimato || p.tempoStimato,
          numPgm:     info.numPgm     || p.numPgm,
          // stato, operatore, tempoInizio, tempoFine → invariati
        }:p)
        aggiornati++
      } else {
        updatedPrograms.push({id:uid(),...info,stato:'da_fare',operatore:'',
          tempoStimato:info.tempoStimato||'',tempoInizio:null,tempoFine:null})
        nuovi++
      }
    }
    const sorted=updatedPrograms.sort((a,b)=>{
      if(a.tipoGruppo!==b.tipoGruppo) return a.tipoGruppo==='ipm'?-1:1
      return a.numPgm.localeCompare(b.numPgm,undefined,{numeric:true})
    })
    updatePrograms(sorted)
    e.target.value=''
    if(aggiornati>0||nuovi>0){
      const parts=[]
      if(nuovi) parts.push(`${nuovi} nuov${nuovi===1?'o':'i'}`)
      if(aggiornati) parts.push(`${aggiornati} aggiornat${aggiornati===1?'o':'i'} — stato mantenuto`)
      setUploadMsg(parts.join(' · '))
      setTimeout(()=>setUploadMsg(null), 4000)
    }
  }
  function updatePgm(id,patch){
    updatePrograms(programs.map(p=>{
      if(p.id!==id) return p
      const next={...p,...patch}
      if(['in_main','in_lavorazione','in_macchina'].includes(patch.stato)&&!p.tempoInizio) next.tempoInizio=nowStr()
      if(patch.stato==='completato') next.tempoFine=nowStr()
      return next
    }))
  }
  function toggleSelect(id){ setSelected(s=>{ const n=new Set(s); n.has(id)?n.delete(id):n.add(id); return n }) }
  function selTutti(lista){ setSelected(s=>{ const n=new Set(s); lista.forEach(p=>n.add(p.id)); return n }) }
  function deselTutti(){ setSelected(new Set()) }
  function massaStato(stato){
    updatePrograms(programs.map(p=>{
      if(!selected.has(p.id)) return p
      const next={...p,stato}
      if(['in_main','in_lavorazione','in_macchina'].includes(stato)&&!p.tempoInizio) next.tempoInizio=nowStr()
      if(stato==='completato') next.tempoFine=nowStr()
      return next
    }))
    setSelected(new Set())
  }
  function eliminaSelezionati(){
    if(!window.confirm(`Eliminare ${selected.size} programm${selected.size===1?'o':'i'}?`)) return
    updatePrograms(programs.filter(p=>!selected.has(p.id)))
    setSelected(new Set())
  }
  const gruppi=[
    {key:'ipm',label:'Tastatura (IPM)',icon:'📏',color:'#8B2FC9',bgColor:'#F3E8FF',list:ipmPrograms},
    {key:'fresatura',label:'Fresatura',icon:'⚙️',color:'#0d2d5e',bgColor:'#E8F0FA',list:fresPrograms},
  ].filter(g=>g.list.length>0)
  // Calcolo ETA
  const fmtTempo=(min)=>{if(!min) return null; const h=Math.floor(min/60); const m=min%60; return h>0?`${h}h ${m>0?m+'m':''}`:`${m}m`}
  const totaleStimato=fresPrograms.reduce((acc,p)=>acc+(parseInt(p.tempoStimato)||0),0)
  const rimanente=fresPrograms.filter(p=>p.stato!=='completato').reduce((acc,p)=>acc+(parseInt(p.tempoStimato)||0),0)
  const haTempi=fresPrograms.some(p=>p.tempoStimato)

  // Previsione fine vita — calcola per ogni utensile il punto di rottura
  const previsioneVita = (() => {
    if(!toolsDB||!haTempi) return []
    // Raggruppa programmi da fare per utensile in ordine
    const perUtensile = {}
    for(const p of fresPrograms){
      if(p.stato==='completato') continue
      const alias=(p.utensile||'').toUpperCase().trim()
      const tempo=parseInt(p.tempoStimato)||0
      if(!alias||!tempo) continue
      if(!perUtensile[alias]) perUtensile[alias]=[]
      perUtensile[alias].push(p)
    }
    const alerts=[]
    for(const [alias, pgms] of Object.entries(perUtensile)){
      // Trova vita rimanente (life_percent = minuti)
      const utensili=Object.values(toolsDB).filter(t=>
        (t.name||'').toUpperCase().trim()===alias && t.is_enabled && !t.is_worn)
      if(!utensili.length) continue
      // life_remaining e life_total sono già in minuti (Sinumerik 840D)
      const lifeRem=Math.max(...utensili.map(t=>t.life_remaining||0))
      const lifeTot=Math.max(...utensili.map(t=>t.life_total||0))
      const vitaRim=lifeRem>0
        ? Math.round(lifeRem)
        : Math.round((Math.max(...utensili.map(t=>t.life_percent||0))/100)*lifeTot)
      let consumo=0, critico=null
      for(const p of pgms){
        consumo+=parseInt(p.tempoStimato)||0
        if(consumo>vitaRim && !critico) critico={...p, minutiRottura: vitaRim-(consumo-(parseInt(p.tempoStimato)||0))}
      }
      if(critico) alerts.push({alias, vitaRim, consumoTot:consumo, critico, mancanti:consumo-vitaRim})
    }
    return alerts.sort((a,b)=>b.mancanti-a.mancanti)
  })()
  return(
    <div style={{marginTop:8,background:T.surface,border:'1.5px solid #1D5FAD33',borderRadius:10}}>
      <div onClick={()=>setExpanded(v=>!v)}
        style={{display:'flex',alignItems:'center',gap:8,padding:'9px 14px',
          cursor:'pointer',userSelect:'none',
          background: inMacchina>0?'#E8F0FA': allDone?'#f0fdf4':'#F8FAFC',
          borderRadius: expanded?'10px 10px 0 0':'10px'}}>

        {/* Barra progresso mini verticale sinistra */}
        <div style={{width:3,height:32,background:'#e2e8f0',borderRadius:2,flexShrink:0,overflow:'hidden'}}>
          <div style={{width:'100%',height:`${fresPrograms.length>0?Math.round(doneTotal/fresPrograms.length*100):0}%`,
            background: allDone?'#16a34a':'#1D5FAD',borderRadius:2,marginTop:'auto',
            position:'relative',top:`${100-Math.round(doneTotal/(fresPrograms.length||1)*100)}%`}}/>
        </div>

        <span style={{fontSize:12}}>⚙️</span>
        <span style={{fontSize:13,fontWeight:700,color:'#0d2d5e'}}>Fresatura</span>

        {/* Programma in macchina — il più importante */}
        {inMacchina>0&&(()=>{
          const pgmLive=fresPrograms.find(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato))
          return pgmLive?(
            <span style={{fontSize:11,fontWeight:700,color:'#fff',background:'#1D5FAD',
              padding:'2px 8px',borderRadius:4,fontFamily:'monospace',flexShrink:0,
              maxWidth:160,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
              ⚙ {(pgmLive.filename||'').replace(/\.MPF$/i,'')||`#${pgmLive.numPgm}`}
            </span>
          ):null
        })()}

        {/* Contatore programmi */}
        <span style={{fontSize:11,fontWeight:700,
          color:allDone?'#166534':'#475569',
          background:allDone?'#dcfce7':'#f1f5f9',
          padding:'2px 8px',borderRadius:4}}>
          {doneTotal}/{fresPrograms.length}{allDone?' ✓':''}
        </span>

        {/* ETA rimanente */}
        {haTempi&&rimanente>0&&(
          <span style={{fontSize:11,fontWeight:700,color:'#1D5FAD',
            fontFamily:'monospace',flexShrink:0}}>
            {fmtTempo(rimanente)} rim.
          </span>
        )}

        {/* Alert utensili — visibile senza espandere */}
        {toolsDB&&(()=>{
          const issues=fresPrograms.filter(p=>
            p.stato!=='completato'&&p.utensile&&
            ['mancante','fin_vita','disabilitato'].includes(classifyTool(p.utensile,toolsDB)))
          return issues.length>0?(
            <span style={{fontSize:11,fontWeight:700,color:'#dc2626',
              background:'#fef2f2',padding:'2px 7px',borderRadius:4,
              border:'1px solid #fca5a5',flexShrink:0}}>
              ⚠ {issues.length} utensil{issues.length===1?'e':'i'}
            </span>
          ):null
        })()}

        {/* Previsione vita */}
        {previsioneVita.length>0&&(
          <span style={{fontSize:11,fontWeight:700,color:'#e65100',
            background:'#fff3e0',padding:'2px 7px',borderRadius:4,
            border:'1px solid #ffb74d',flexShrink:0}}>
            🔮 {previsioneVita.length} a rischio
          </span>
        )}

        <span style={{marginLeft:'auto',fontSize:11,color:'#0d2d5e',fontWeight:700,flexShrink:0}}>
          {expanded?'▲':'▼'}
        </span>
      </div>
      {expanded&&(
        <div>
          <div style={{display:'flex',gap:10,alignItems:'center',padding:'10px 14px',borderBottom:`1px solid ${T.border}`}}>
            <input ref={fileInputRef} type='file' accept='.mpf,.MPF' multiple style={{display:'none'}} onChange={handleFileUpload}/>
            <button onClick={()=>fileInputRef.current.click()} style={{background:'#0d2d5e',border:'none',borderRadius:7,color:'#fff',fontWeight:700,fontSize:13,padding:'7px 14px',cursor:'pointer'}}>📂 Carica .mpf</button>
            {total>0&&<span style={{fontSize:12,color:T.textMuted}}>{ipmPrograms.length>0&&`📏 ${ipmPrograms.length} IPM · `}⚙️ {fresPrograms.length} fresatura</span>}
            {uploadMsg&&<span style={{fontSize:12,fontWeight:700,color:'#166534',background:'#dcfce7',padding:'3px 10px',borderRadius:6}}>✓ {uploadMsg}</span>}
          </div>

          {/* ── Previsione fine vita ── */}
          {previsioneVita.length>0&&(
            <div style={{background:'#fff8f0',borderBottom:`1px solid #ffb74d`,padding:'10px 14px'}}>
              <div style={{fontSize:11,fontWeight:800,color:'#e65100',marginBottom:8,display:'flex',alignItems:'center',gap:6}}>
                <span>🔮</span>
                <span>PREVISIONE FINE VITA — {previsioneVita.length} utensil{previsioneVita.length===1?'e':'i'} a rischio in questa fase</span>
              </div>
              {previsioneVita.map((a,i)=>(
                <div key={i} style={{background:'#fff',border:'1px solid #ffcc80',borderRadius:8,
                  padding:'8px 12px',marginBottom:6,fontSize:12}}>
                  <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:4}}>
                    <span style={{fontFamily:'monospace',fontWeight:800,color:'#bf360c'}}>{a.alias}</span>
                    <div style={{flex:1,height:5,background:'#ffe0b2',borderRadius:3,overflow:'hidden'}}>
                      <div style={{height:5,width:`${Math.min(Math.round(a.vitaRim/a.consumoTot*100),100)}%`,
                        background:'#ff9800',borderRadius:3}}/>
                    </div>
                    <span style={{fontSize:11,color:'#e65100',flexShrink:0,fontWeight:700}}>
                      {a.vitaRim}min / {a.consumoTot}min
                    </span>
                  </div>
                  <div style={{background:'#fff3e0',borderRadius:6,padding:'6px 10px',fontSize:11}}>
                    <span style={{fontWeight:700,color:'#bf360c'}}>⚠ Finisce durante: </span>
                    <span style={{fontFamily:'monospace',fontWeight:700}}>{a.critico.filename?.replace(/\.MPF$/i,'')}</span>
                    <span style={{color:'#9a3412'}}> — vita esaurita dopo {a.critico.minutiRottura}min, mancano ancora {a.mancanti}min</span>
                    <div style={{marginTop:3,fontWeight:700,color:'#e65100'}}>
                      💡 Sostituire prima del programma <span style={{fontFamily:'monospace'}}>{a.critico.numPgm}</span>
                    </div>
                  </div>
                </div>
              ))}
            </div>
          )}

          {/* Toolbar multi-select */}
          {selected.size>0&&(
            <div style={{display:'flex',alignItems:'center',gap:8,padding:'8px 14px',
              background:'#EFF6FF',borderBottom:`1px solid #0d2d5e33`,flexWrap:'wrap',
              position:'sticky',top:0,zIndex:10,
              boxShadow:'0 2px 8px rgba(13,45,94,0.12)'}}>
              <span style={{fontSize:12,fontWeight:700,color:'#0d2d5e',marginRight:4}}>{selected.size} selezionati</span>
              <span style={{fontSize:11,color:'#0d2d5e',marginRight:8}}>→ Segna come:</span>
              {[['da_fare','○ Da fare','#f8fafc','#475569'],['in_macchina','⚙ In macchina','#DBEAFE','#0d2d5e'],['completato','✓ Completato','#DCFCE7','#166534']].map(([stato,label,bg,color])=>(
                <button key={stato} onClick={()=>massaStato(stato)}
                  style={{background:bg,border:`1.5px solid ${color}44`,borderRadius:6,color,fontSize:11,fontWeight:700,padding:'4px 10px',cursor:'pointer'}}>
                  {label}
                </button>
              ))}
              <div style={{width:1,background:'#0d2d5e33',alignSelf:'stretch',margin:'0 4px'}}/>
              <button onClick={eliminaSelezionati}
                style={{background:'#fef2f2',border:'1.5px solid #fca5a5',borderRadius:6,
                  color:'#dc2626',fontSize:11,fontWeight:700,padding:'4px 10px',cursor:'pointer'}}>
                🗑 Elimina
              </button>
              <button onClick={deselTutti} style={{marginLeft:'auto',background:'none',border:`1px solid ${T.border}`,borderRadius:6,color:T.textMuted,fontSize:11,padding:'4px 8px',cursor:'pointer'}}>✕ Deseleziona</button>
            </div>
          )}

          {total===0&&<div style={{textAlign:'center',padding:24,color:T.textMuted,fontSize:13}}>Nessun programma · clicca "Carica .mpf"</div>}
          {total>0&&(
            <div style={{display:'flex',background:T.surface2,borderBottom:`1px solid ${T.border}`,fontSize:10,fontWeight:700,color:T.textMuted,letterSpacing:'0.07em'}}>
              <div style={{width:32,padding:'5px 8px',borderRight:`1px solid ${T.border}`,display:'flex',alignItems:'center',justifyContent:'center'}}>
                <input type='checkbox' checked={selected.size>0&&programs.every(p=>selected.has(p.id))}
                  ref={el=>{if(el) el.indeterminate=selected.size>0&&!programs.every(p=>selected.has(p.id))}}
                  onChange={e=>e.target.checked?selTutti(programs):deselTutti()}
                  onClick={e=>e.stopPropagation()} style={{cursor:'pointer',accentColor:'#0d2d5e'}}/>
              </div>
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
                  <button onClick={e=>{e.stopPropagation();selTutti(gruppo.list)}} style={{background:'none',border:`1px solid ${gruppo.color}44`,borderRadius:5,color:gruppo.color,fontSize:10,padding:'2px 7px',cursor:'pointer',fontWeight:600}}>Sel. tutti</button>
                  <span style={{fontSize:11,color:gruppo.color}}>{gruppo.list.filter(p=>p.stato==='completato').length}/{gruppo.list.length}</span>
                  <span style={{fontSize:10,color:gruppo.color}}>{collapsedGroups[gruppo.key]?'▼':'▲'}</span>
                </div>
              )}
              {(gruppi.length===1||!collapsedGroups[gruppo.key])&&gruppo.list.map(pgm=>(
                <ProgramRow key={pgm.id} pgm={pgm} gruppo={gruppo}
                  selected={selected.has(pgm.id)}
                  onSelect={()=>toggleSelect(pgm.id)}
                  onStato={stato=>updatePgm(pgm.id,{stato})}
                  onOperatore={operatore=>updatePgm(pgm.id,{operatore})}
                  onTempo={tempoStimato=>updatePgm(pgm.id,{tempoStimato})}
                  onRemove={()=>updatePrograms(programs.filter(p=>p.id!==pgm.id))}
                  toolStatus={['in_macchina','in_main','in_lavorazione'].includes(pgm.stato)?classifyTool(pgm.utensile,toolsDB):null}/>
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
    scaffale:   {label:'A scaffale',    color:'#0d2d5e',bg:'#e6f1fb',dot:'🏠'},
    smontato:   {label:'Smontato',      color:'#1e40af',bg:'#FFF0DC',dot:'📦'},
    mancante:   {label:'Non trovato',   color:'#dc2626',bg:'#fef2f2',dot:'✗'},
  }

  const hasIssues = data && (
    data.summary.mancante>0 || data.summary.fin_vita>0 ||
    data.summary.scaffale>0 || data.summary.smontato>0 || data.summary.disabilitato>0
  )

  return(
    <div style={{marginTop:12,border:`1.5px solid ${hasIssues&&expanded?'#C0392B33':'#e2e8f0'}`,borderRadius:10}}>
      <div onClick={()=>setExpanded(v=>!v)}
        style={{display:'flex',alignItems:'center',gap:10,padding:'10px 14px',cursor:'pointer',
          background:hasIssues?'#e6f1fb':'#eef2f7',userSelect:'none'}}>
        <span style={{fontSize:14}}>🔧</span>
        <span style={{fontSize:13,fontWeight:800,color:'#0f172a',flex:1}}>UTENSILI RICHIESTI</span>
        {data&&<>
          <span style={{fontSize:11,fontWeight:700,color:'#166534',background:'#dcfce7',padding:'2px 8px',borderRadius:20}}>
            ✓ {data.summary.ok}
          </span>
          {data.summary.fin_vita>0&&<span style={{fontSize:11,fontWeight:700,color:'#B45309',background:'#FEF3C7',padding:'2px 8px',borderRadius:20}}>
            ⚠ {data.summary.fin_vita} vita bassa
          </span>}
          {(data.summary.scaffale+data.summary.smontato)>0&&<span style={{fontSize:11,fontWeight:700,color:'#0d2d5e',background:'#e6f1fb',padding:'2px 8px',borderRadius:20}}>
            🏠 {data.summary.scaffale+data.summary.smontato} da montare
          </span>}
          {data.summary.mancante>0&&<span style={{fontSize:11,fontWeight:700,color:'#dc2626',background:'#fef2f2',padding:'2px 8px',borderRadius:20}}>
            ✗ {data.summary.mancante} mancanti
          </span>}
        </>}
        <span style={{fontSize:11,color:'#94a3b8',fontWeight:700}}>{expanded?'▲':'▼'}</span>
      </div>

      {expanded&&(
        <div>
          {loading&&<div style={{padding:16,textAlign:'center',color:'#94a3b8',fontSize:13}}>Caricamento...</div>}
          {!loading&&data&&data.utensili.length===0&&(
            <div style={{padding:16,textAlign:'center',color:'#94a3b8',fontSize:13}}>
              Nessun utensile rilevato nei programmi MPF
            </div>
          )}
          {!loading&&data&&data.utensili.length>0&&(
            <>
              {/* Header colonne */}
              <div style={{display:'flex',background:'#f8fafc',borderBottom:'1px solid #D8D5CC',
                fontSize:10,fontWeight:700,color:'#94a3b8',letterSpacing:'0.07em'}}>
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
                      fontSize:12,fontFamily:'monospace',fontWeight:700,color:'#0f172a'}}>
                      {u.alias}
                    </div>
                    <div style={{width:80,padding:'6px 10px',borderRight:'1px solid #D8D5CC',
                      textAlign:'center',fontSize:11,color:'#475569',fontFamily:'monospace'}}>
                      {u.magazine!=null?`M${u.magazine}`:''}{u.position!=null?` P${u.position}`:''}
                      {u.magazine==null&&u.position==null?'—':''}
                    </div>
                    <div style={{width:80,padding:'6px 10px',textAlign:'center',fontSize:11,
                      fontWeight:700,
                      color:u.life_percent!=null?(u.life_percent<15?'#dc2626':u.life_percent<30?'#0d2d5e':'#16a34a'):'#94a3b8'}}>
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
        <div onClick={()=>onToggle(task.id)} style={{width:20,height:20,borderRadius:6,border:task.done?'none':`2px solid ${T.borderStrong}`,background:task.done?'#16a34a':'transparent',cursor:'pointer',flexShrink:0,display:'flex',alignItems:'center',justifyContent:'center',transition:'all 0.2s'}}>
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
        <div style={{marginTop:8}}><FresaturaPanel task={task} onUpdateTask={onUpdateTask} toolsDB={toolsDB} projectId={projectId} /></div>
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
function LancioNCModal({project, toolsDB, initialSelectedIds, onLancia, onClose}){
  // Costruisce mappa fase → programmi, IPM INCLUSI (sezione separata)
  const fasi = (project.steps||[]).map(step=>{
    const fres = (step.tasks||[]).find(t=>t.text?.trim().toLowerCase()==='fresatura')
    const pgmsAll = fres ? (fres.programs||[]) : []
    const pgmsFres = pgmsAll.filter(p=>p.tipoGruppo!=='ipm')
    const pgmsIpm  = pgmsAll.filter(p=>p.tipoGruppo==='ipm')
    return { stepId: step.id, stepTitle: step.title, pgms: pgmsFres, pgmsIpm }
  }).filter(f=>f.pgms.length>0||f.pgmsIpm.length>0)

  // allPgm: solo fresatura per logica fasi/selezione default
  const allPgm = fasi.flatMap(f=>f.pgms.map(p=>({...p, _stepId:f.stepId, _stepTitle:f.stepTitle})))
  // allIpm: programmi tastatura di tutte le fasi
  const allIpm = fasi.flatMap(f=>f.pgmsIpm.map(p=>({...p, _stepId:f.stepId, _stepTitle:f.stepTitle})))

  const da_fare    = allPgm.filter(p=>p.stato==='da_fare')
  const in_macchina= allPgm.filter(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato))
  const completati = allPgm.filter(p=>p.stato==='completato')

  const [selected, setSelected] = useState(()=>{
    if(initialSelectedIds && initialSelectedIds.size > 0){
      const valid = new Set([...initialSelectedIds].filter(id=>allPgm.some(p=>p.id===id)))
      if(valid.size > 0) return valid
    }
    return new Set(da_fare.map(p=>p.id))
  })
  // Selezione IPM separata — di default tutti i da_fare
  const [selectedIpm, setSelectedIpm] = useState(()=>
    new Set(allIpm.filter(p=>p.stato==='da_fare').map(p=>p.id))
  )
  const [showCompletati, setShowCompletati] = useState(false)
  const [showIpm, setShowIpm] = useState(allIpm.length > 0)
  const [faseMistaConfirmata, setFaseMistaConfirmata] = useState(false)

  function toggle(id){ setSelected(s=>{ const n=new Set(s); n.has(id)?n.delete(id):n.add(id); return n }) }
  function toggleIpm(id){ setSelectedIpm(s=>{ const n=new Set(s); n.has(id)?n.delete(id):n.add(id); return n }) }
  function selezionaTutti(fase){ setSelected(s=>{ const n=new Set(s); fase.pgms.forEach(p=>n.add(p.id)); return n }) }
  function deselezionaFase(fase){ setSelected(s=>{ const n=new Set(s); fase.pgms.forEach(p=>n.delete(p.id)); return n }) }
  function deselezionaTutti(){ setSelected(new Set()) }

  // pgmSelezionati include sia fresatura che IPM selezionati
  const pgmSelezionati = [
    ...allPgm.filter(p=>selected.has(p.id)),
    ...allIpm.filter(p=>selectedIpm.has(p.id)),
  ]

  // Rilevamento fasi miste
  const fasiSelezionate = [...new Set(pgmSelezionati.map(p=>p._stepTitle))]
  const faseMista = fasiSelezionate.length > 1
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
          background:sel?'#0d2d5e':'transparent',
          display:'flex',alignItems:'center',justifyContent:'center'}}>
          {sel&&<span style={{color:'#fff',fontSize:12,fontWeight:800}}>✓</span>}
        </div>
        {/* Badge stato */}
        {(()=>{const s=pgm.stato||'da_fare';const cfg={
          da_fare:    {label:'Da fare',    color:'#94a3b8',bg:'#f8fafc'},
          in_macchina:{label:'In macchina',color:'#0d2d5e',bg:'#DBEAFE'},
          completato: {label:'Fatto',      color:'#166534',bg:'#DCFCE7'},
        }[s]||{label:s,color:'#94a3b8',bg:'#f8fafc'};return(
          <span style={{fontSize:10,fontWeight:700,color:cfg.color,background:cfg.bg,
            padding:'2px 7px',borderRadius:10,flexShrink:0,whiteSpace:'nowrap'}}>
            {cfg.label}
          </span>
        )})()}
        {/* Filename */}
        <span style={{fontSize:12,fontFamily:'monospace',fontWeight:700,
          color:'#0d2d5e',minWidth:145,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
          {pgm.filename?.replace(/\.MPF$/i,'')||`#${pgm.numPgm}`}
        </span>
        {/* Utensile */}
        <span style={{fontSize:11,fontFamily:'monospace',color:'#0f172a',
          minWidth:120,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
          {pgm.utensile||'—'}
        </span>
        {/* Operazione */}
        <span style={{fontSize:11,color:'#94a3b8',flex:1,
          overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
          {(pgm.tipoOp||'').replace(/[-–]\s*NESSUN TESTO\s*/gi,'').trim()||''}
        </span>
        <ToolBadge alias={pgm.utensile}/>
      </div>
    )
  }

  // Colori per fase (fino a 6 fasi)
  const FASE_COLORS = ['#0d2d5e','#166534','#7C3AED','#C2410C','#0369A1','#B45309']

  return(
    <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.55)',
      display:'flex',alignItems:'center',justifyContent:'center',zIndex:400}}>
      <div style={{background:'#FFFFFF',borderRadius:16,width:700,maxWidth:'96vw',
        maxHeight:'90vh',display:'flex',flexDirection:'column',
        border:'1px solid #D8D5CC',boxShadow:'0 20px 60px rgba(0,0,0,0.25)'}}>

        {/* Header */}
        <div style={{padding:'16px 22px 12px',borderBottom:'1px solid #E8E6E0'}}>
          <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
            <span style={{fontSize:18}}>📄</span>
            <div style={{flex:1}}>
              <div style={{fontSize:15,fontWeight:800,color:'#0f172a'}}>Lancia in Analisi NC</div>
              <div style={{fontSize:12,color:'#94a3b8'}}>{project.name} · {allPgm.length} programmi totali</div>
            </div>
            <button onClick={onClose} style={{background:'none',border:'1px solid #D8D5CC',
              borderRadius:8,color:'#475569',fontSize:13,padding:'5px 12px',cursor:'pointer'}}>✕</button>
          </div>
          <div style={{display:'flex',gap:8,alignItems:'center'}}>
            <button onClick={()=>setSelected(new Set(da_fare.map(p=>p.id)))}
              style={{background:'#f8fafc',border:'1px solid #e2e8f0',borderRadius:6,
                color:'#475569',fontSize:11,fontWeight:700,padding:'4px 10px',cursor:'pointer'}}>
              ○ Seleziona Da fare ({da_fare.length})
            </button>
            <button onClick={()=>setSelected(new Set(allPgm.map(p=>p.id)))}
              style={{background:'#f8fafc',border:'1px solid #e2e8f0',borderRadius:6,
                color:'#475569',fontSize:11,fontWeight:700,padding:'4px 10px',cursor:'pointer'}}>
              ☑ Tutti ({allPgm.length})
            </button>
            {selected.size>0&&<button onClick={deselezionaTutti}
              style={{background:'none',border:'1px solid #fca5a5',borderRadius:6,
                color:'#dc2626',fontSize:11,padding:'4px 10px',cursor:'pointer'}}>
              ✕ Deseleziona ({selected.size})
            </button>}
          </div>
        </div>

        {/* ⚠ AVVISO FASI MISTE */}
        {faseMista&&(
          <div style={{background:'#fff7ed',borderBottom:'2px solid #f97316',
            padding:'10px 18px',display:'flex',flexDirection:'column',gap:6}}>
            <div style={{display:'flex',alignItems:'center',gap:8}}>
              <span style={{fontSize:18}}>⚠️</span>
              <span style={{fontSize:13,fontWeight:800,color:'#c2410c'}}>
                Attenzione: hai selezionato programmi con setup differente
              </span>
            </div>
            <div style={{fontSize:12,color:'#9a3412'}}>
              Fasi selezionate: {fasiSelezionate.map((f,i)=>(
                <strong key={i} style={{color:FASE_COLORS[i%FASE_COLORS.length]}}>{f}{i<fasiSelezionate.length-1?' + ':''}</strong>
              ))} — ogni fase può avere utensili, zero-pezzo e staffaggi diversi.
            </div>
            <label style={{display:'flex',alignItems:'center',gap:8,cursor:'pointer',fontSize:12,color:'#9a3412',fontWeight:700}}>
              <input type="checkbox" checked={faseMistaConfirmata} onChange={e=>setFaseMistaConfirmata(e.target.checked)}/>
              Ho verificato e confermo che i setup sono compatibili
            </label>
          </div>
        )}

        {/* Lista programmi raggruppata per FASE */}
        <div style={{flex:1,overflowY:'auto'}}>
          {fasi.length===0?(
            <div style={{padding:40,textAlign:'center',color:'#94a3b8',fontSize:14}}>
              Nessun programma MPF caricato
            </div>
          ):fasi.map((fase,fi)=>{
            const faseColor = FASE_COLORS[fi%FASE_COLORS.length]
            const faseSelected = fase.pgms.filter(p=>selected.has(p.id))
            const tuttiSel = faseSelected.length===fase.pgms.length
            return(
              <div key={fase.stepId}>
                {/* Header fase */}
                <div style={{display:'flex',alignItems:'center',gap:10,
                  padding:'8px 14px',background:`${faseColor}11`,
                  borderBottom:`2px solid ${faseColor}44`,
                  borderTop:fi>0?'1px solid #e2e8f0':'none',position:'sticky',top:0,zIndex:2}}>
                  <div style={{width:10,height:10,borderRadius:'50%',background:faseColor,flexShrink:0}}/>
                  <span style={{fontSize:12,fontWeight:800,color:faseColor,flex:1}}>
                    {fase.stepTitle} — {fase.pgms.length} programmi
                  </span>
                  <span style={{fontSize:11,color:faseColor,opacity:0.7}}>
                    {faseSelected.length}/{fase.pgms.length} sel.
                  </span>
                  <button onClick={()=>tuttiSel?deselezionaFase(fase):selezionaTutti(fase)}
                    style={{background:'none',border:`1px solid ${faseColor}66`,borderRadius:5,
                      color:faseColor,fontSize:10,fontWeight:700,padding:'2px 8px',cursor:'pointer'}}>
                    {tuttiSel?'Desel. tutti':'Sel. tutti'}
                  </button>
                </div>
                {/* Righe programmi */}
                {fase.pgms.map(pgm=>{
                  const sel=selected.has(pgm.id)
                  const ts=classifyTool(pgm.utensile,toolsDB)
                  const rowBg=sel?(ts==='mancante'?'#FEE2E2':ts==='fin_vita'?'#FEF9C3':'#EFF6FF'):'#FFFFFF'
                  return(
                    <div key={pgm.id} onClick={()=>toggle(pgm.id)}
                      style={{display:'flex',alignItems:'center',gap:10,padding:'7px 14px',
                        cursor:'pointer',background:rowBg,
                        borderLeft:`3px solid ${sel?faseColor:'transparent'}`,
                        borderBottom:'1px solid #F0EEE8',transition:'background 0.1s'}}>
                      <div style={{width:16,height:16,borderRadius:4,flexShrink:0,
                        border:sel?'none':'2px solid #B0ADA4',
                        background:sel?faseColor:'transparent',
                        display:'flex',alignItems:'center',justifyContent:'center'}}>
                        {sel&&<span style={{color:'#fff',fontSize:11,fontWeight:800}}>✓</span>}
                      </div>
                      {/* Stato */}
                      {(()=>{const s=pgm.stato||'da_fare';const cfg={
                        da_fare:    {label:'Da fare',    color:'#94a3b8',bg:'#f8fafc'},
                        in_macchina:{label:'In macchina',color:'#0d2d5e',bg:'#DBEAFE'},
                        completato: {label:'Fatto',      color:'#166534',bg:'#DCFCE7'},
                      }[s]||{label:s,color:'#94a3b8',bg:'#f8fafc'};return(
                        <span style={{fontSize:10,fontWeight:700,color:cfg.color,background:cfg.bg,
                          padding:'2px 6px',borderRadius:10,flexShrink:0,whiteSpace:'nowrap'}}>
                          {cfg.label}
                        </span>
                      )})()}
                      <span style={{fontSize:12,fontFamily:'monospace',fontWeight:700,color:'#0d2d5e',
                        minWidth:140,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                        {pgm.filename?.replace(/\.MPF$/i,'')||`#${pgm.numPgm}`}
                      </span>
                      <span style={{fontSize:11,fontFamily:'monospace',color:'#0f172a',
                        minWidth:100,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                        {pgm.utensile||'—'}
                      </span>
                      <span style={{fontSize:11,color:'#94a3b8',flex:1,
                        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                        {(pgm.tipoOp||'').replace(/[-–]\s*NESSUN TESTO\s*/gi,'').trim()||''}
                      </span>
                      <ToolBadge alias={pgm.utensile}/>
                    </div>
                  )
                })}
              </div>
            )
          })}

          {/* Completati */}
          {completati.length>0&&(
            <div>
              <div onClick={()=>setShowCompletati(v=>!v)}
                style={{padding:'8px 14px',fontSize:10,fontWeight:700,color:'#94a3b8',
                  letterSpacing:'0.07em',background:'#FAFAFA',
                  borderBottom:'1px solid #E8E6E0',cursor:'pointer',
                  display:'flex',alignItems:'center',gap:6}}>
                {showCompletati?'▼':'▶'} COMPLETATI — {completati.length}
              </div>
              {showCompletati&&completati.map(pgm=>{
                const sel=selected.has(pgm.id)
                return(
                  <div key={pgm.id} onClick={()=>toggle(pgm.id)}
                    style={{display:'flex',alignItems:'center',gap:10,padding:'6px 14px',
                      cursor:'pointer',background:sel?'#EFF6FF':'#FAFAFA',
                      borderLeft:`3px solid ${sel?'#0d2d5e':'transparent'}`,
                      borderBottom:'1px solid #F0EEE8',opacity:sel?1:0.6}}>
                    <div style={{width:16,height:16,borderRadius:4,flexShrink:0,
                      border:sel?'none':'2px solid #B0ADA4',
                      background:sel?'#0d2d5e':'transparent',
                      display:'flex',alignItems:'center',justifyContent:'center'}}>
                      {sel&&<span style={{color:'#fff',fontSize:11,fontWeight:800}}>✓</span>}
                    </div>
                    <span style={{fontSize:10,fontWeight:700,color:'#166534',background:'#DCFCE7',
                      padding:'2px 6px',borderRadius:10,flexShrink:0}}>Fatto</span>
                    <span style={{fontSize:12,fontFamily:'monospace',fontWeight:700,color:'#475569',flex:1}}>
                      {pgm.filename?.replace(/\.MPF$/i,'')||`#${pgm.numPgm}`}
                    </span>
                  </div>
                )
              })}
            </div>
          )}

          {/* Sezione IPM / Tastatura — sempre visibile se presenti */}
          {allIpm.length>0&&(
            <div>
              <div onClick={()=>setShowIpm(v=>!v)}
                style={{padding:'8px 14px',fontSize:10,fontWeight:700,color:'#8B2FC9',
                  letterSpacing:'0.07em',background:'#F9F0FF',
                  borderBottom:'1px solid #DDD6FE',borderTop:'1px solid #DDD6FE',
                  cursor:'pointer',display:'flex',alignItems:'center',gap:6}}>
                📏 {showIpm?'▼':'▶'} TASTATURA (IPM) — {allIpm.length} programmi
                <span style={{marginLeft:'auto',fontSize:11,color:'#8B2FC9',fontWeight:400}}>
                  {selectedIpm.size} selezionati
                </span>
                <button onClick={e=>{e.stopPropagation();
                  setSelectedIpm(allIpm.length===selectedIpm.size
                    ? new Set()
                    : new Set(allIpm.map(p=>p.id)))}}
                  style={{background:'none',border:'1px solid #8B2FC944',borderRadius:5,
                    color:'#8B2FC9',fontSize:10,fontWeight:700,padding:'2px 7px',cursor:'pointer'}}>
                  {allIpm.length===selectedIpm.size?'Desel. tutti':'Sel. tutti'}
                </button>
              </div>
              {showIpm&&allIpm.map(pgm=>{
                const sel=selectedIpm.has(pgm.id)
                const cfg={da_fare:{label:'Da fare',color:'#94a3b8',bg:'#f8fafc'},
                  in_macchina:{label:'In macchina',color:'#0d2d5e',bg:'#DBEAFE'},
                  completato:{label:'Fatto',color:'#166534',bg:'#DCFCE7'}}[pgm.stato]||{label:pgm.stato,color:'#94a3b8',bg:'#f8fafc'}
                return(
                  <div key={pgm.id} onClick={()=>toggleIpm(pgm.id)}
                    style={{display:'flex',alignItems:'center',gap:10,padding:'7px 14px',
                      cursor:'pointer',background:sel?'#F3E8FF':'#FAFAFA',
                      borderLeft:`3px solid ${sel?'#8B2FC9':'transparent'}`,
                      borderBottom:'1px solid #F0EEE8',transition:'background 0.1s'}}>
                    <div style={{width:16,height:16,borderRadius:4,flexShrink:0,
                      border:sel?'none':'2px solid #B0ADA4',
                      background:sel?'#8B2FC9':'transparent',
                      display:'flex',alignItems:'center',justifyContent:'center'}}>
                      {sel&&<span style={{color:'#fff',fontSize:11,fontWeight:800}}>✓</span>}
                    </div>
                    <span style={{fontSize:10,fontWeight:700,color:cfg.color,background:cfg.bg,
                      padding:'2px 6px',borderRadius:10,flexShrink:0,whiteSpace:'nowrap'}}>
                      {cfg.label}
                    </span>
                    <span style={{fontSize:12,fontFamily:'monospace',fontWeight:700,color:'#8B2FC9',
                      minWidth:140,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                      {pgm.filename?.replace(/\.MPF$/i,'')||`#${pgm.numPgm}`}
                    </span>
                    <span style={{fontSize:11,fontFamily:'monospace',color:'#0f172a',
                      minWidth:100,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                      {pgm.utensile||'RENISHAW'}
                    </span>
                    <span style={{fontSize:11,color:'#94a3b8',flex:1,
                      overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                      {(pgm.tipoOp||'').replace(/[-–]\s*NESSUN TESTO\s*/gi,'').trim()||''}
                    </span>
                  </div>
                )
              })}
            </div>
          )}
        </div>

        {/* Footer */}
        <div style={{borderTop:'1px solid #E8E6E0',padding:'12px 22px',
          background:'#eef2f7',borderRadius:'0 0 16px 16px'}}>

          {mancanti.length>0&&(
            <div style={{background:'#FEE2E2',border:'1px solid #DC262633',borderRadius:8,
              padding:'7px 12px',marginBottom:8,fontSize:12,color:'#DC2626',fontWeight:600}}>
              ⚠ {mancanti.length} utensil{mancanti.length===1?'e':'i'} mancant{mancanti.length===1?'e':'i'} — verificare prima di procedere
            </div>
          )}
          {problemi.length>0&&mancanti.length===0&&(
            <div style={{background:'#FEF9C3',border:'1px solid #D9770633',borderRadius:8,
              padding:'7px 12px',marginBottom:8,fontSize:12,color:'#D97706',fontWeight:600}}>
              ⚠ {problemi.length} utensil{problemi.length===1?'e':'i'} a fine vita
            </div>
          )}

          <div style={{display:'flex',alignItems:'center',gap:12}}>
            <div style={{flex:1,fontSize:13,color:'#475569'}}>
              {selected.size===0&&selectedIpm.size===0
                ? <span style={{color:'#94a3b8'}}>Nessun programma selezionato</span>
                : <><span style={{fontWeight:700,color:'#0f172a'}}>
                    {selected.size+selectedIpm.size} selezionat{(selected.size+selectedIpm.size)===1?'o':'i'}
                  </span>
                  {selectedIpm.size>0&&<span style={{color:'#8B2FC9',marginLeft:6,fontSize:12}}>
                    · {selectedIpm.size} IPM
                  </span>}
                  {!faseMista&&problemi.length===0&&<span style={{color:'#166634',marginLeft:6}}>· ok ✓</span>}
                  {faseMista&&<span style={{color:'#c2410c',marginLeft:6}}>· {fasiSelezionate.length} fasi diverse</span>}
                  </>
              }
            </div>
            <button onClick={onClose}
              style={{background:'none',border:'1px solid #D8D5CC',borderRadius:8,
                color:'#475569',fontSize:13,padding:'8px 18px',cursor:'pointer',fontWeight:600}}>
              Annulla
            </button>
            <button
              disabled={(selected.size+selectedIpm.size)===0||(faseMista&&!faseMistaConfirmata)}
              onClick={()=>onLancia(pgmSelezionati)}
              style={{
                background: (selected.size+selectedIpm.size)===0?'#e2e8f0'
                  : faseMista&&!faseMistaConfirmata?'#fed7aa'
                  : faseMista?'#ea580c'
                  : '#0d2d5e',
                border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:14,
                padding:'9px 22px',cursor:(selected.size+selectedIpm.size)===0||(faseMista&&!faseMistaConfirmata)?'default':'pointer',
                transition:'all 0.15s',
                opacity:faseMista&&!faseMistaConfirmata?0.6:1
              }}>
              {faseMista?'⚠ ':'📄 '}Lancia {(selected.size+selectedIpm.size)>0?(selected.size+selectedIpm.size):''} in NC →
            </button>
          </div>
        </div>
      </div>
    </div>
  )
}

function ProjectDetail({project,onBack,onUpdate,onDelete,onArchive,templates,onSaveAsTemplate,onLanciaNC,palletDisponibili=[],palletStato=[]}){
  const navPD = useNavigate()
  // Carica tools_machine una volta sola per questo progetto
  const [toolsDB, setToolsDB] = useState(null)
  const [palletError, setPalletError] = useState(null)  // errore assegnazione pallet
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [showLancioModal, setShowLancioModal] = useState(()=>{
    // Apri automaticamente se arrivato dalla Coda con bottone Avvia
    const flag = sessionStorage.getItem('dmgdesk_apri_modal_lancio')
    if(flag){ sessionStorage.removeItem('dmgdesk_apri_modal_lancio'); return true }
    return false
  })
  useEffect(()=>{
    fetch('/api/tools')
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

  // ── Dati derivati per header ─────────────────────────────────────────────
  const mpfTotDetail = mpfList.length
  const mpfDoneDetail = mpfList.filter(p=>p.stato==='completato').length
  const mpfInMacDetail = mpfList.filter(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato)).length
  const ncPctDetail = mpfTotDetail>0 ? Math.round(mpfDoneDetail/mpfTotDetail*100) : 0
  const etaDetail = (()=>{
    const rimasti = mpfList.filter(p=>p.stato!=='completato')
    let tot=0
    for(const p of rimasti){ if(p.tempoStimato) tot+=parseInt(p.tempoStimato)*60 }
    if(!tot) return null
    const h=Math.floor(tot/3600), m=Math.round((tot%3600)/60)
    return h>0?(m>0?`~${h}h ${m}m`:`~${h}h`):`~${m} min`
  })()
  const [showMoreMenu, setShowMoreMenu] = React.useState(false)

  return(
    <PgmSelContext.Provider value={{selectedIds, setSelectedIds}}>
    <div style={{display:'flex',flexDirection:'column',height:'100%',background:T.bg,fontFamily:"var(--font-display)"}}>
      {/* Header */}
      <div style={{padding:'10px 20px 0',borderBottom:`1px solid ${T.border}`,flexShrink:0,background:T.surface}}>

        {/* RIGA 1: navigazione + nome + pallet + CTA */}
        <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:10}}>
          <button onClick={onBack} style={{background:'none',border:`1px solid ${T.border}`,borderRadius:7,color:T.textSub,fontSize:12,padding:'5px 10px',cursor:'pointer',fontWeight:600,flexShrink:0}}>← Indietro</button>
          <div style={{width:9,height:9,borderRadius:2,background:project.color,flexShrink:0}}/>

          {/* Nome editabile */}
          {editingName
            ? <div style={{display:'flex',gap:6,flex:1,alignItems:'center'}}>
                <input autoFocus value={editNameVal}
                  onChange={e=>setEditNameVal(e.target.value)}
                  onKeyDown={e=>{
                    if(e.key==='Enter'){onUpdate({...project,name:editNameVal.trim()||project.name});setEditingName(false)}
                    if(e.key==='Escape')setEditingName(false)
                  }}
                  style={{fontSize:15,fontWeight:800,color:T.text,background:T.surface2,
                    border:`2px solid ${project.color}`,borderRadius:8,padding:'4px 10px',outline:'none',flex:1}}/>
                <button onClick={()=>{onUpdate({...project,name:editNameVal.trim()||project.name});setEditingName(false)}}
                  style={{background:project.color,border:'none',borderRadius:7,color:'#fff',fontWeight:700,fontSize:12,padding:'4px 10px',cursor:'pointer'}}>✓</button>
                <button onClick={()=>setEditingName(false)}
                  style={{background:'none',border:`1px solid ${T.border}`,borderRadius:7,color:T.textSub,fontSize:12,padding:'4px 8px',cursor:'pointer'}}>✕</button>
              </div>
            : <div style={{display:'flex',alignItems:'center',gap:4,flex:1,minWidth:0}}>
                <div style={{fontSize:16,fontWeight:800,color:T.text,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{project.name}</div>
                <button onClick={()=>{setEditNameVal(project.name);setEditingName(true)}}
                  title="Rinomina" style={{background:'none',border:'none',cursor:'pointer',color:T.textMuted,fontSize:11,opacity:0.35,padding:'2px 3px',flexShrink:0}}>✏️</button>
              </div>
          }

          {/* Pallet — prominente */}
          {(()=>{
            const palInfo = palletStato.find(p=>p.numero===project.pallet_assegnato)
            const isLav = palInfo && (palInfo.stato||'').toLowerCase().replace('_',' ')==='in lavorazione'
            return (
              <div style={{display:'flex',alignItems:'center',gap:5,
                background: isLav?'#dbeafe':'#eef4fb',
                border:`1px solid ${isLav?'#1D5FAD':'#c5d9f0'}`,
                borderRadius:7,padding:'4px 10px',flexShrink:0}}>
                {isLav&&<span style={{width:6,height:6,borderRadius:'50%',background:'#1D5FAD',flexShrink:0,display:'inline-block',animation:'pulse-dot 1.5s ease-in-out infinite'}}/>}
                <span style={{fontSize:11,fontWeight:700,color:'#0d2d5e'}}>P:</span>
                <select value={project.pallet_assegnato||''}
                  onChange={async e=>{
                    const val=e.target.value?parseInt(e.target.value):null
                    const old=project.pallet_assegnato
                    if(old&&old!==val){await fetch('/api/pallet/'+old+'/assegna-progetto',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({progetto_id:null,progetto_nome:null,progetto_colore:null})})}
                    if(val){const r=await fetch('/api/pallet/'+val+'/assegna-progetto',{method:'PATCH',headers:{'Content-Type':'application/json'},body:JSON.stringify({progetto_id:project.id,progetto_nome:project.name,progetto_colore:project.color||'#0d2d5e'})});if(!r.ok){const err=await r.json().catch(()=>({}));setPalletError(err.detail||'Errore assegnazione pallet');setTimeout(()=>setPalletError(null),4000);return}}
                    onUpdate({...project,pallet_assegnato:val})
                  }}
                  style={{fontSize:12,fontWeight:700,background:'transparent',color:isLav?'#1D5FAD':'#0d2d5e',border:'none',padding:'0 2px',cursor:'pointer',outline:'none'}}>
                  <option value=''>—</option>
                  {[1,2,3,4,5,6].map(n=>{const disp=palletDisponibili.find(p=>p.numero===n);const isAss=project.pallet_assegnato===n;if(!disp&&!isAss)return null;return <option key={n} value={n}>P{n}{isAss?' ✓':''}</option>})}
                </select>
                {project.pallet_assegnato&&(
                  <span onClick={()=>navPD('/coda')} style={{fontSize:10,fontWeight:700,cursor:'pointer',color:isLav?'#1D5FAD':'#0d2d5e',opacity:isLav?1:0.6}}>
                    {isLav?'LIVE →':'→'}
                  </span>
                )}
              </div>
            )
          })()}

          {palletError&&(
            <span style={{fontSize:11,fontWeight:700,color:'#dc2626',background:'#fef2f2',border:'1px solid #fca5a5',borderRadius:6,padding:'4px 10px',flexShrink:0}}>
              ⚠ {palletError}
            </span>
          )}

          {/* CTA primaria */}
          {mpfList.length>0&&(
            <button onClick={()=>setShowLancioModal(true)}
              style={{background:'#0d2d5e',border:'none',borderRadius:8,color:'#fff',fontWeight:800,fontSize:13,padding:'7px 16px',cursor:'pointer',flexShrink:0}}>
              📄 Lancia in NC →
            </button>
          )}

          {/* Rendiconto — secondario visibile */}
          <button onClick={()=>navPD(`/rendiconto/${project.id}`)}
            style={{background:'none',border:`1px solid ${T.border}`,borderRadius:6,
              color:'#1D5FAD',fontSize:12,padding:'5px 10px',cursor:'pointer',fontWeight:600,flexShrink:0}}>
            📊
          </button>

          {/* Menu ⋯ — secondari nascosti */}
          <div style={{position:'relative',flexShrink:0}}>
            <button onClick={()=>setShowMoreMenu(v=>!v)}
              style={{background:'none',border:`1px solid ${T.border}`,borderRadius:6,
                color:T.textSub,fontSize:13,padding:'5px 10px',cursor:'pointer'}}>
              ⋯
            </button>
            {showMoreMenu&&(
              <div style={{position:'absolute',right:0,top:'calc(100% + 4px)',
                background:T.surface,border:`1px solid ${T.border}`,borderRadius:10,
                boxShadow:'0 4px 16px rgba(0,0,0,0.12)',zIndex:50,minWidth:160,overflow:'hidden'}}>
                {[
                  {label:'💾 Salva come template', action:()=>{setShowSaveTemplate(true);setShowMoreMenu(false)}},
                  {label:project.archived?'📤 Riattiva':'📦 Archivia', action:()=>{setConfirm('archive');setShowMoreMenu(false)}},
                  {label:'🗑️ Elimina', action:()=>{setConfirm('delete');setShowMoreMenu(false)}, danger:true},
                ].map((item,i)=>(
                  <button key={i} onClick={item.action}
                    style={{display:'block',width:'100%',textAlign:'left',
                      background:'none',border:'none',borderTop:i>0?`1px solid ${T.border}`:'none',
                      color:item.danger?T.red:T.text,fontSize:13,padding:'10px 16px',
                      cursor:'pointer',fontWeight:item.danger?600:400}}>
                    {item.label}
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* RIGA 2: doppie barre + ETA + scadenza */}
        {(()=>{
          const taskTot = project.steps.flatMap(s=>s.tasks||[]).length
          const taskDone = project.steps.flatMap(s=>s.tasks||[]).filter(t=>t.done).length
          const del = (palletDisponibili||[]).find ? null : null  // delivery passata dal parent
          // Scadenza — la leggiamo da palletStato per semplicità (non disponibile qui)
          // La mostriamo solo se mpfTot > 0
          return(
            <div style={{display:'grid',gridTemplateColumns:'1fr auto',gap:16,alignItems:'center',marginBottom:12}}>
              <div>
                {/* Barra preparazione */}
                <div style={{display:'flex',justifyContent:'space-between',fontSize:10,color:T.textMuted,marginBottom:3}}>
                  <span>Preparazione — {taskDone}/{taskTot} task · {progress}%</span>
                </div>
                <div style={{height:5,background:T.surface2,borderRadius:3,overflow:'hidden',marginBottom:4}}>
                  <div style={{height:'100%',width:`${progress}%`,background:project.color,borderRadius:3,transition:'width 0.3s'}}/>
                </div>
                {/* Barra NC */}
                {mpfTotDetail>0&&(
                  <>
                    <div style={{display:'flex',justifyContent:'space-between',fontSize:10,color:T.textMuted,marginBottom:3}}>
                      <span>NC — {mpfDoneDetail}/{mpfTotDetail} programmi{mpfInMacDetail>0?` · ${mpfInMacDetail} in macchina`:''}</span>
                      {etaDetail&&<span style={{color:'#1D5FAD',fontWeight:600}}>{etaDetail} rimanenti</span>}
                    </div>
                    <div style={{height:4,background:T.surface2,borderRadius:2,overflow:'hidden'}}>
                      <div style={{height:'100%',width:`${ncPctDetail}%`,background:'#16a34a',borderRadius:2,transition:'width 0.3s'}}/>
                    </div>
                  </>
                )}
              </div>
              {/* StatusBadge compatto a destra */}
              <StatusBadge progress={progress}/>
            </div>
          )
        })()}

        {/* Tab */}
        <div style={{display:'flex',gap:0}}>
          <Tab id='tasks' label='Task'/>
          <Tab id='documenti' label='Documenti'/>
          <Tab id='log' label={`Log (${(project.log||[]).length})`}/>
        </div>
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
        {activeTab==='documenti'&&(
          <TabDocumenti project={project}/>
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

        initialSelectedIds={selectedIds}
        onClose={()=>setShowLancioModal(false)}
        onLancia={pgmSelezionati=>{
          setShowLancioModal(false)
          onLanciaNC(project, pgmSelezionati)
        }}
      />}
    </div>
    </PgmSelContext.Provider>
  )
}
// ── ProgettiListaFiltrata ─────────────────────────────────────────────────────
function ProgettiListaFiltrata({inProgress,completed,urgentProjects,palletState,deliveries,getDelivery,setDelivery,deleteProject,archiveProject,setSelectedId,nowStr}){
  const[vista,setVista]=useState('lista')   // 'lista' | 'griglia'
  const[filtroStato,setFiltroStato]=useState('tutti')  // 'tutti'|'in_corso'|'completati'|'critici'|'con_pallet'
  const[filtroOrdine,setFiltroOrdine]=useState('scadenza') // 'scadenza'|'pallet'|'avanzamento'|'nome'

  // Calcola ETA per progetto — ore rimanenti stimate dai tempi CAM
  function etaProgetto(project){
    const pgms=(project.steps||[]).flatMap(s=>(s.tasks||[])
      .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
      .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm')))
    const rimasti=pgms.filter(p=>p.stato!=='completato')
    if(!rimasti.length) return null
    let tot=0, haStima=false
    for(const p of rimasti){
      if(p.tempoStimato){ tot+=parseInt(p.tempoStimato)*60; haStima=true }
    }
    if(!tot) return null
    const h=Math.floor(tot/3600), m=Math.round((tot%3600)/60)
    return { sec: tot, fmt: h>0?(m>0?`~${h}h ${m}m`:`~${h}h`):`~${m} min`, haStima }
  }

  // Arricchisci ogni progetto con pallet e urgenza
  const tutti=[...inProgress,...completed].map(p=>{
    const del=getDelivery(p.id)
    const days=del?.dueDate&&!del.delivered?daysUntil(del.dueDate):null
    const urg=deliveryUrgency(days)
    const pal=palletState?.find(x=>x.progetto_id===p.id)
    const palNum=pal?.numero||p.pallet_assegnato||null
    const palStato=(pal?.stato||'').toLowerCase().replace('_',' ')
    const isLive=palStato==='in lavorazione'
    const eta=etaProgetto(p)
    const progress=getProgress(p)
    const mpfTot=(p.steps||[]).flatMap(s=>s.tasks||[]).filter(t=>t.text?.trim().toLowerCase()==='fresatura').flatMap(t=>(t.programs||[]).filter(x=>x.tipoGruppo!=='ipm'))
    const mpfDone=mpfTot.filter(x=>x.stato==='completato').length
    return{...p,_del:del,_days:days,_urg:urg,_pal:palNum,_isLive:isLive,_eta:eta,_progress:progress,_mpfTot:mpfTot.length,_mpfDone:mpfDone}
  })

  // Filtro stato
  const filtrati=tutti.filter(p=>{
    if(filtroStato==='in_corso') return p._progress<100
    if(filtroStato==='completati') return p._progress===100
    if(filtroStato==='critici') return p._days!==null&&p._days<=7
    if(filtroStato==='con_pallet') return !!p._pal
    return true
  })

  // Ordine
  const ordinati=[...filtrati].sort((a,b)=>{
    if(filtroOrdine==='scadenza'){
      const da=a._days??9999, db=b._days??9999
      return da-db
    }
    if(filtroOrdine==='pallet'){
      if(a._pal&&!b._pal) return -1
      if(!a._pal&&b._pal) return 1
      return (a._pal||99)-(b._pal||99)
    }
    if(filtroOrdine==='avanzamento') return a._progress-b._progress
    if(filtroOrdine==='nome') return a.name.localeCompare(b.name)
    return 0
  })

  const criticiN=urgentProjects.length
  const conPalletN=tutti.filter(p=>p._pal).length

  return(
    <div>
      {/* Banner critici */}
      {criticiN>0&&(
        <div style={{background:T.redBg,border:`1.5px solid ${T.red}33`,borderRadius:12,padding:'12px 18px',marginBottom:14,display:'flex',alignItems:'center',gap:10}}>
          <span style={{fontSize:18}}>🎯</span>
          <div>
            <span style={{fontSize:13,fontWeight:800,color:T.red,letterSpacing:'0.07em'}}>FOCUS — {criticiN} CONSEGN{criticiN===1?'A':'E'} ENTRO 7 GIORNI · </span>
            <span style={{fontSize:13,color:T.textSub}}>{urgentProjects.map(p=>p.name).join(' · ')}</span>
          </div>
        </div>
      )}

      {/* Toolbar filtri + vista */}
      <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:14,flexWrap:'wrap'}}>
        {/* Filtri stato */}
        {[
          ['tutti',`Tutti (${tutti.length})`],
          ['in_corso',`In corso (${inProgress.length})`],
          ['completati',`Completati (${completed.length})`],
          ...(criticiN>0?[['critici',`⚠ Critici (${criticiN})`]]:[]),
          ...(conPalletN>0?[['con_pallet',`Con pallet (${conPalletN})`]]:[]),
        ].map(([key,label])=>(
          <button key={key} onClick={()=>setFiltroStato(key)}
            style={{background:filtroStato===key?T.accent:'transparent',
              border:`1px solid ${filtroStato===key?T.accent:T.border}`,
              borderRadius:20,color:filtroStato===key?'#fff':T.textSub,
              fontSize:12,fontWeight:600,padding:'4px 12px',cursor:'pointer'}}>
            {label}
          </button>
        ))}

        <div style={{marginLeft:'auto',display:'flex',gap:6,alignItems:'center'}}>
          {/* Ordine */}
          <select value={filtroOrdine} onChange={e=>setFiltroOrdine(e.target.value)}
            style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:6,
              color:T.textSub,fontSize:12,padding:'4px 8px',outline:'none',cursor:'pointer'}}>
            <option value='scadenza'>Per scadenza</option>
            <option value='pallet'>Per pallet</option>
            <option value='avanzamento'>Per avanzamento</option>
            <option value='nome'>Per nome</option>
          </select>

          {/* Toggle vista */}
          <div style={{display:'flex',border:`1px solid ${T.border}`,borderRadius:6,overflow:'hidden'}}>
            {[['lista','☰'],['griglia','⊞']].map(([v,icon])=>(
              <button key={v} onClick={()=>setVista(v)}
                style={{background:vista===v?T.surface2:'transparent',border:'none',
                  color:vista===v?T.accent:T.textMuted,fontSize:14,
                  padding:'4px 9px',cursor:'pointer'}}>
                {icon}
              </button>
            ))}
          </div>
        </div>
      </div>

      {ordinati.length===0&&(
        <div style={{textAlign:'center',padding:'40px 0',color:T.textMuted,fontSize:13}}>Nessun progetto in questa categoria.</div>
      )}

      {/* Vista lista compatta */}
      {vista==='lista'&&ordinati.length>0&&(
        <div style={{display:'flex',flexDirection:'column',gap:2}}>
          {/* Header colonne */}
          <div style={{display:'grid',
            gridTemplateColumns:'minmax(0,1fr) 52px 72px 220px 90px 14px',
            gap:16,padding:'0 16px 6px',alignItems:'center'}}>
            <span style={{fontSize:10,fontWeight:700,color:T.textMuted,letterSpacing:'0.07em',textTransform:'uppercase'}}>Progetto</span>
            <span style={{fontSize:10,fontWeight:700,color:T.textMuted,letterSpacing:'0.07em',textAlign:'center'}}>Pallet</span>
            <span style={{fontSize:10,fontWeight:700,color:T.textMuted,letterSpacing:'0.07em',textAlign:'center'}}>Scadenza</span>
            <span style={{fontSize:10,fontWeight:700,color:T.textMuted,letterSpacing:'0.07em'}}>Preparazione &amp; NC</span>
            <span style={{fontSize:10,fontWeight:700,color:T.textMuted,letterSpacing:'0.07em',textAlign:'right'}}>Ore rimanenti</span>
            <span/>
          </div>

          {ordinati.map(p=>{
            const d=p._del
            const ncPct=p._mpfTot>0?Math.round(p._mpfDone/p._mpfTot*100):0
            return(
              <div key={p.id} onClick={()=>setSelectedId(p.id)}
                style={{
                  background:p._isLive?'#f0f7ff':T.surface,
                  border:`1px solid ${p._isLive?'#93c5fd':T.border}`,
                  borderLeft:`4px solid ${p._isLive?'#1D5FAD':p._urg&&d&&!d.delivered&&p._days<=7?p._urg.color:p.color}`,
                  borderRadius:8,padding:'10px 16px',cursor:'pointer',
                  display:'grid',
                  gridTemplateColumns:'minmax(0,1fr) 52px 72px 220px 90px 14px',
                  alignItems:'center',gap:16,
                  transition:'background 0.1s'}}
                onMouseEnter={e=>e.currentTarget.style.background=p._isLive?'#e0efff':'#f8fafc'}
                onMouseLeave={e=>e.currentTarget.style.background=p._isLive?'#f0f7ff':T.surface}>

                {/* Colonna 1: Nome */}
                <div style={{display:'flex',alignItems:'center',gap:8,minWidth:0}}>
                  <div style={{width:8,height:8,borderRadius:2,background:p.color,flexShrink:0}}/>
                  <span style={{fontSize:14,fontWeight:700,color:T.text,
                    overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                    {p.name}
                  </span>
                  {p._isLive&&(
                    <span style={{fontSize:9,fontWeight:800,color:'#fff',background:'#1D5FAD',
                      padding:'1px 6px',borderRadius:3,flexShrink:0,letterSpacing:'0.06em'}}>LIVE</span>
                  )}
                </div>

                {/* Colonna 2: Pallet */}
                <div style={{textAlign:'center'}}>
                  {p._pal?(
                    <span style={{fontSize:12,fontWeight:700,
                      color:p._isLive?'#0d2d5e':'#854d0e',
                      background:p._isLive?'#dbeafe':'#fefce8',
                      padding:'3px 8px',borderRadius:5,display:'inline-block'}}>
                      P{p._pal}
                    </span>
                  ):(
                    <span style={{fontSize:12,color:T.textMuted}}>—</span>
                  )}
                </div>

                {/* Colonna 3: Scadenza */}
                <div style={{textAlign:'center'}}>
                  {d?.dueDate&&!d.delivered?(
                    <span style={{fontSize:12,fontWeight:700,color:p._urg.color,
                      background:p._urg.bg,padding:'3px 10px',borderRadius:5,
                      display:'inline-block',textAlign:'center'}}>
                      {p._days===0?'OGGI':p._days<0?`${Math.abs(p._days)}gg fa`:`${p._days}gg`}
                    </span>
                  ):(
                    <span style={{fontSize:12,color:T.textMuted}}>—</span>
                  )}
                </div>

                {/* Colonna 4: Doppia barra con etichette chiare */}
                <div style={{display:'flex',flexDirection:'column',gap:4}}>
                  {/* Preparazione */}
                  <div style={{display:'flex',alignItems:'center',gap:6}}>
                    <span style={{fontSize:10,fontWeight:600,color:T.textMuted,width:28,flexShrink:0,textAlign:'right'}}>prep</span>
                    <div style={{flex:1,height:5,background:T.surface2,borderRadius:3,overflow:'hidden'}}>
                      <div style={{height:'100%',width:`${p._progress}%`,
                        background:p.color,borderRadius:3,transition:'width 0.3s'}}/>
                    </div>
                    <span style={{fontSize:10,fontWeight:700,color:p.color,width:28,flexShrink:0}}>{p._progress}%</span>
                  </div>
                  {/* NC — solo se ci sono programmi */}
                  {p._mpfTot>0?(
                    <div style={{display:'flex',alignItems:'center',gap:6}}>
                      <span style={{fontSize:10,fontWeight:600,color:T.textMuted,width:28,flexShrink:0,textAlign:'right'}}>NC</span>
                      <div style={{flex:1,height:5,background:T.surface2,borderRadius:3,overflow:'hidden'}}>
                        <div style={{height:'100%',width:`${ncPct}%`,
                          background:'#16a34a',borderRadius:3,transition:'width 0.3s'}}/>
                      </div>
                      <span style={{fontSize:10,fontWeight:700,color:'#16a34a',width:28,flexShrink:0}}>{p._mpfDone}/{p._mpfTot}</span>
                    </div>
                  ):(
                    <div style={{display:'flex',alignItems:'center',gap:6}}>
                      <span style={{fontSize:10,color:T.textMuted,width:28,flexShrink:0,textAlign:'right'}}>NC</span>
                      <span style={{fontSize:10,color:T.textMuted}}>nessun programma</span>
                    </div>
                  )}
                </div>

                {/* Colonna 5: ETA */}
                <div style={{textAlign:'right'}}>
                  {p._eta?(
                    <>
                      <div style={{fontSize:13,fontWeight:700,fontFamily:'monospace',color:'#1D5FAD'}}>
                        {p._eta.fmt}
                      </div>
                      {!p._eta.haStima&&(
                        <div style={{fontSize:9,color:T.textMuted}}>stima grezza</div>
                      )}
                    </>
                  ):(
                    <span style={{fontSize:12,color:T.textMuted}}>—</span>
                  )}
                </div>

                {/* Freccia */}
                <span style={{fontSize:13,color:T.textMuted}}>›</span>
              </div>
            )
          })}
        </div>
      )}

      {/* Vista griglia */}
      {vista==='griglia'&&ordinati.length>0&&(()=>{
        const inProg=ordinati.filter(p=>p._progress<100)
        const done=ordinati.filter(p=>p._progress===100)
        return(
          <>
            {inProg.length>0&&(
              <>
                <div style={{fontSize:13,color:T.textSub,fontWeight:700,letterSpacing:'0.06em',marginBottom:14}}>IN CORSO — {inProg.length}</div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(2, 1fr)',gap:14,marginBottom:32}}>
                  {inProg.map((p,i)=>{
                    const d=getDelivery(p.id)
                    const isLast=i===inProg.length-1&&inProg.length%2!==0
                    return <div key={p.id} style={{gridColumn:isLast?'1 / -1':undefined,maxWidth:isLast?'calc(50% - 7px)':undefined}}>
                      <ProjectCard project={p} onClick={()=>setSelectedId(p.id)} onDelete={deleteProject} onArchive={archiveProject} delivery={d}
                        onSetDelivery={(pid,date,toggle)=>{if(toggle!==undefined&&d)setDelivery(d.id,{delivered:toggle,deliveredAt:toggle?nowStr():null},true);else if(date!==null)d?setDelivery(d.id,{dueDate:date},true):setDelivery(uid(),{projectId:pid,dueDate:date,delivered:false},false);else if(d)setDelivery(d.id,{dueDate:''},true)}}/>
                    </div>
                  })}
                </div>
              </>
            )}
            {done.length>0&&(
              <>
                <div style={{fontSize:13,color:T.textSub,fontWeight:700,letterSpacing:'0.06em',marginBottom:14}}>COMPLETATI — {done.length}</div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(2, 1fr)',gap:14}}>
                  {done.map((p,i)=>{
                    const d=getDelivery(p.id)
                    const isLast=i===done.length-1&&done.length%2!==0
                    return <div key={p.id} style={{gridColumn:isLast?'1 / -1':undefined,maxWidth:isLast?'calc(50% - 7px)':undefined}}>
                      <ProjectCard project={p} onClick={()=>setSelectedId(p.id)} onDelete={deleteProject} onArchive={archiveProject} delivery={d}
                        onSetDelivery={(pid,date,toggle)=>{if(toggle!==undefined&&d)setDelivery(d.id,{delivered:toggle,deliveredAt:toggle?nowStr():null},true);else if(date!==null)d?setDelivery(d.id,{dueDate:date},true):setDelivery(uid(),{projectId:pid,dueDate:date,delivered:false},false);else if(d)setDelivery(d.id,{dueDate:''},true)}}/>
                    </div>
                  })}
                </div>
              </>
            )}
          </>
        )
      })()}
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
              <span style={{fontSize:11,fontWeight:700,background:'#EFF6FF',color:'#0d2d5e',
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
        {/* Barra preparazione */}
        <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:4}}>
          <span style={{fontSize:9,fontWeight:700,color:T.textMuted,letterSpacing:'0.07em',width:76,flexShrink:0}}>PREPARAZIONE</span>
          <div style={{flex:1}}><ProgressBar value={progress} color={project.color}/></div>
          <span style={{fontSize:11,fontWeight:700,color:project.color,width:34,textAlign:'right'}}>{progress}%</span>
        </div>
        {/* Barra NC fresatura */}
        {mpfTot.length>0&&(
          <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:4}}>
            <span style={{fontSize:9,fontWeight:700,color:T.textMuted,letterSpacing:'0.07em',width:76,flexShrink:0}}>NC</span>
            <div style={{flex:1}}>
              <div style={{height:6,background:T.surface2,borderRadius:3,overflow:'hidden',position:'relative'}}>
                {/* completati */}
                <div style={{position:'absolute',left:0,top:0,height:'100%',width:`${Math.round(mpfDone/mpfTot.length*100)}%`,background:'#16a34a',borderRadius:3,transition:'width 0.3s'}}/>
                {/* in macchina */}
                <div style={{position:'absolute',left:`${Math.round(mpfDone/mpfTot.length*100)}%`,top:0,height:'100%',
                  width:`${Math.round(mpfTot.filter(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato)).length/mpfTot.length*100)}%`,
                  background:'#0d2d5e',borderRadius:3,transition:'width 0.3s'}}/>
              </div>
            </div>
            <span style={{fontSize:11,fontWeight:700,color:'#16a34a',width:34,textAlign:'right'}}>
              {mpfDone}/{mpfTot.length}
            </span>
          </div>
        )}
        <div style={{display:'flex',alignItems:'center',justifyContent:'space-between',marginTop:6,marginBottom:next?12:0}}>
          <span style={{fontSize:13,color:T.textSub,fontWeight:500}}>{(project.steps||[]).flatMap(s=>s.tasks||[]).filter(t=>t.done).length} / {(project.steps||[]).flatMap(s=>s.tasks||[]).length} task</span>
          <div style={{display:'flex',gap:8,alignItems:'center'}}>
            <StatusBadge progress={progress}/>
          </div>
        </div>
        {next?(
          <div style={{background:T.accentBg,borderRadius:8,padding:'10px 12px',borderLeft:`3px solid ${T.accent}`}}>
            <div style={{fontSize:11,color:T.accent,fontWeight:700,letterSpacing:'0.06em',marginBottom:3}}>📍 PROSSIMO STEP</div>
            <div style={{fontSize:14,color:T.text,fontWeight:600}}><span style={{color:T.textSub,fontWeight:400}}>{next.step.title} › </span>{next.task.text}</div>
            {next.task.text?.trim().toLowerCase()==='fresatura'&&Array.isArray(next.task.programs)&&next.task.programs.length>0&&(
              <div style={{display:'flex',alignItems:'center',gap:8,marginTop:4}}>
                <span style={{fontSize:12,color:'#0d2d5e',fontWeight:700}}>⚙️ {next.task.programs.filter(p=>p.stato==='completato').length}/{next.task.programs.length} pgm</span>
                {next.task.programs.filter(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato)).length>0&&<span style={{fontSize:11,color:'#0d2d5e',background:'#E8F0FA',padding:'1px 8px',borderRadius:10}}>{next.task.programs.filter(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato)).length} in macchina</span>}
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
// ── TemplatesPage — Lista template ─────────────────────────────────────────
function TemplatesPage({templates,onEdit,onCreate,onDelete,onDuplicate,onUseTemplate,lastSaved}){
  return(
    <div style={{display:'flex',flexDirection:'column',height:'100%',background:T.bg,fontFamily:"var(--font-display)"}}>
      {/* Header */}
      <div style={{padding:'18px 28px',borderBottom:`1px solid ${T.border}`,flexShrink:0,background:T.surface,display:'flex',alignItems:'center',gap:12}}>
        <div style={{fontSize:18,fontWeight:800,color:T.text,flex:1}}>📋 Template Progetto</div>
        {lastSaved&&<span style={{fontSize:11,color:T.textMuted}}>Salvato {lastSaved}</span>}
        <button onClick={onCreate} style={{background:T.accent,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:14,padding:'9px 20px',cursor:'pointer'}}>+ Nuovo Template</button>
      </div>
      {/* Lista */}
      <div style={{flex:1,overflowY:'auto',padding:'24px 28px'}}>
        {templates.length===0?(
          <div style={{textAlign:'center',padding:'60px 20px',color:T.textMuted}}>
            <div style={{fontSize:48,marginBottom:16}}>📋</div>
            <div style={{fontSize:16,fontWeight:600,marginBottom:8}}>Nessun template</div>
            <div style={{fontSize:13,marginBottom:24}}>Crea un template per velocizzare la creazione di nuovi progetti</div>
            <button onClick={onCreate} style={{background:T.accent,border:'none',borderRadius:10,color:'#fff',fontWeight:700,fontSize:14,padding:'10px 24px',cursor:'pointer'}}>+ Crea primo template</button>
          </div>
        ):(
          <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(320px,1fr))',gap:16}}>
            {templates.map(tmpl=>(
              <div key={tmpl.id} style={{background:T.surface,border:`1.5px solid ${T.border}`,borderLeft:`5px solid ${tmpl.color||T.accent}`,borderRadius:12,padding:'16px 18px',display:'flex',flexDirection:'column',gap:10}}>
                {/* Titolo */}
                <div style={{display:'flex',alignItems:'center',gap:10}}>
                  <span style={{fontSize:26}}>{tmpl.icon||'📋'}</span>
                  <div style={{flex:1}}>
                    <div style={{fontSize:15,fontWeight:800,color:T.text}}>{tmpl.name}</div>
                    {tmpl.description&&<div style={{fontSize:12,color:T.textMuted,marginTop:2}}>{tmpl.description}</div>}
                  </div>
                </div>
                {/* Fasi */}
                <div style={{display:'flex',flexWrap:'wrap',gap:6}}>
                  {(tmpl.steps||[]).map((s,i)=>(
                    <span key={s.id||i} style={{fontSize:11,background:T.surface2,border:`1px solid ${T.border}`,borderRadius:6,padding:'3px 8px',color:T.textSub,fontWeight:600}}>
                      {i+1}. {s.title}
                    </span>
                  ))}
                  {(tmpl.steps||[]).length===0&&<span style={{fontSize:12,color:T.textMuted}}>Nessuna fase</span>}
                </div>
                {/* Azioni */}
                <div style={{display:'flex',gap:8,marginTop:4}}>
                  <button onClick={()=>onUseTemplate(tmpl)} style={{flex:1,background:tmpl.color||T.accent,border:'none',borderRadius:8,color:'#fff',fontWeight:700,fontSize:13,padding:'8px',cursor:'pointer'}}>▶ Usa</button>
                  <button onClick={()=>onEdit(tmpl)} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontWeight:600,fontSize:13,padding:'8px 12px',cursor:'pointer'}}>✏</button>
                  <button onClick={()=>onDuplicate(tmpl)} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontWeight:600,fontSize:13,padding:'8px 12px',cursor:'pointer'}}>⧉</button>
                  <button onClick={()=>onDelete(tmpl.id)} style={{background:T.redBg,border:`1px solid ${T.red}44`,borderRadius:8,color:T.red,fontWeight:600,fontSize:13,padding:'8px 12px',cursor:'pointer'}}>✕</button>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  )
}

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
    <div style={{display:'flex',flexDirection:'column',height:'100%',background:T.bg,fontFamily:"var(--font-display)"}}>
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

// ── HomePage — Dashboard turno ──────────────────────────────────────────────
function HomePage({projects,deliveries,palletState,setupData,onNavigateProject,onNavigateCoda}){
  const T = useTheme()
  const now   = new Date()
  const days  = ['Domenica','Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']
  const months= ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno','Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']
  const dayLabel = `${days[now.getDay()]} ${now.getDate()} ${months[now.getMonth()]} ${now.getFullYear()}`

  const pallets    = palletState || []
  const inProgress = projects.filter(p => !p.archived)

  // ── Progetto IN LAVORAZIONE ──────────────────────────────────────────────
  const palletLav   = pallets.find(p => (p.stato||'').toLowerCase().replace('_',' ') === 'in lavorazione')
  const progettoLav = palletLav ? inProgress.find(p => p.id === palletLav.progetto_id) : null

  // ── Metriche turno ───────────────────────────────────────────────────────
  const allPgm = inProgress.flatMap(p =>
    (p.steps||[]).flatMap(s=>(s.tasks||[]).filter(t=>t.text?.trim().toLowerCase()==='fresatura')
    .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm'))))
  const pgmDaFare   = allPgm.filter(p=>p.stato==='da_fare').length
  const pgmInMac    = allPgm.filter(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato)).length
  const pgmOggi     = allPgm.filter(p=>{
    if(p.stato!=='completato'||!p.tempoFine) return false
    const d=new Date(p.tempoFine.split(' ').reverse().join('-').replace(/(\d+)\/(\d+)\/(\d+)/,'$3-$2-$1'))
    return d.toDateString()===now.toDateString()
  }).length

  // ── Scadenze ─────────────────────────────────────────────────────────────
  function daysUntil(dateStr){
    if(!dateStr) return null
    try{
      const parts=dateStr.split(/[\/\-]/)
      const d=parts[0].length===4?new Date(parts[0],parts[1]-1,parts[2]):new Date(parts[2],parts[1]-1,parts[0])
      return Math.ceil((d-new Date(now.getFullYear(),now.getMonth(),now.getDate()))/(1000*60*60*24))
    }catch{return null}
  }
  const conScadenza = inProgress
    .map(p=>({p, d:deliveries.find(d=>d.projectId===p.id), pNum:pallets.find(x=>x.progetto_id===p.id)?.numero}))
    .filter(({d})=>d?.dueDate && !d.delivered)
    .map(({p,d,pNum})=>({p, days:daysUntil(d.dueDate), pNum}))
    .sort((a,b)=>a.days-b.days)

  // ── Utensili con problemi ─────────────────────────────────────────────────
  const mancanti    = (setupData?.non_utilizzati||[]).filter(u=>u.provenienza==='richiesto_da_progetto')
  const finVita     = (setupData?.fin_vita||[])
  const daMontare   = (setupData?.da_montare||[])
  const aRischio    = (setupData?.previsione_vita?.utensili_critici||[])
  // Unifica evitando duplicati per alias
  const utensiliProblema = (() => {
    const map = {}
    mancanti.forEach(u=>{
      map[u.alias]={alias:u.alias, tipo:'mancante', label:'MANCANTE', color:'#dc2626',
        bg:'#fef2f2', border:'#fca5a5',
        detail:(u.progetti||[]).map(r=>r.progetto).join(', ')||''}
    })
    daMontare.forEach(u=>{
      if(!map[u.alias]) map[u.alias]={alias:u.alias, tipo:'da_montare', label:'DA MONTARE', color:'#d97706',
        bg:'#fffbeb', border:'#fcd34d', detail:`pos. ${u.posizione||'—'}`}
    })
    finVita.forEach(u=>{
      const pct = typeof u.life_percent==='number' ? u.life_percent : null
      if(!map[u.alias]) map[u.alias]={alias:u.alias, tipo:'fin_vita',
        label: pct!==null ? `${pct.toFixed(0)}%` : 'FINE VITA',
        color:'#c2410c', bg:'#fff7ed', border:'#fdba74',
        detail:`pos. ${u.posizione||'—'}`}
    })
    aRischio.forEach(u=>{
      if(!map[u.alias]) map[u.alias]={alias:u.alias, tipo:'rischio',
        label:`esaurito al pgm ${u.programma_critico||'?'}`,
        color:'#7c3aed', bg:'#f5f3ff', border:'#c4b5fd',
        detail:u.progetto||''}
    })
    return Object.values(map).sort((a,b)=>{
      const ord={mancante:0,da_montare:1,fin_vita:2,rischio:3}
      return (ord[a.tipo]||9)-(ord[b.tipo]||9)
    })
  })()

  // ── Colori pallet ─────────────────────────────────────────────────────────
  function palletColors(stato, hasProj, pct){
    const s = (stato||'').toLowerCase().replace('_',' ')
    if(s==='in lavorazione') return {bg:'#dbeafe',fg:'#0d2d5e',border:'#1D5FAD',label:'IN LAV.'}
    if(pct>=100||s==='finito') return {bg:'#dcfce7',fg:'#14532d',border:'#16a34a',label:'FINITO'}
    if(hasProj) return {bg:'#fefce8',fg:'#854d0e',border:'#eab308',label:'GREZZO'}
    return {bg:'#f1f5f9',fg:'#94a3b8',border:'#e2e8f0',label:'VUOTO'}
  }

  // avanzamento per pallet
  function palletInfo(pNum){
    const pal = pallets.find(p=>p.numero===pNum)
    if(!pal?.progetto_id) return null
    const proj = inProgress.find(p=>p.id===pal.progetto_id)
    if(!proj) return null
    const pgms = (proj.steps||[]).flatMap(s=>(s.tasks||[])
      .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
      .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm')))
    const tot  = pgms.length
    const done = pgms.filter(p=>p.stato==='completato').length
    const pct  = tot ? Math.round(done/tot*100) : 0
    const daFare = pgms.filter(p=>p.stato==='da_fare').length
    const inMac  = pgms.filter(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato)).length
    return {proj, pct, tot, done, daFare, inMac, colore:proj.color||'#1D5FAD'}
  }

  // Avanzamento progetto in lavorazione
  const lavInfo = progettoLav ? (() => {
    const pgms = (progettoLav.steps||[]).flatMap(s=>(s.tasks||[])
      .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
      .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm')))
    const tot  = pgms.length
    const done = pgms.filter(p=>p.stato==='completato').length
    const pct  = tot ? Math.round(done/tot*100) : 0
    return {pct, done, tot, inMac:pgms.filter(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato)).length}
  })() : null

  const critici = conScadenza.filter(x=>x.days!==null&&x.days<=0).length

  // ── RENDER ────────────────────────────────────────────────────────────────
  return (
    <div style={{flex:1,overflowY:'auto',background:'#eef2f7',fontFamily:'var(--font-display)'}}>
      {/* Header */}
      <div style={{background:'#fff',borderBottom:'1px solid #e2e8f0',padding:'12px 24px',
        display:'flex',alignItems:'baseline',gap:12}}>
        <span style={{fontSize:20,fontWeight:800,color:'#0d2d5e'}}>Cruscotto turno</span>
        <span style={{fontSize:13,color:'#94a3b8'}}>{dayLabel}</span>
      </div>

      {/* Body principale — 3 colonne */}
      <div style={{display:'grid',gridTemplateColumns:'320px 1fr 220px',gap:16,padding:'16px 20px',
        alignItems:'start'}}>

        {/* ── COL 1: PALLET ─────────────────────────────────────────────── */}
        <div style={{display:'flex',flexDirection:'column',gap:10}}>
          <div style={{fontSize:11,fontWeight:800,letterSpacing:'0.08em',color:'#0d2d5e'}}>PALLET</div>
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8}}>
            {[1,2,3,4,5,6].map(n=>{
              const info = palletInfo(n)
              const pal  = pallets.find(p=>p.numero===n)||{}
              const c    = palletColors(pal.stato, !!info, info?.pct)
              const isLav= c.label==='IN LAV.'
              return (
                <div key={n}
                  onClick={info?()=>onNavigateProject(info.proj.id):undefined}
                  style={{background:c.bg,border:`2px solid ${c.border}`,borderRadius:10,
                    padding:'10px 12px',cursor:info?'pointer':'default',
                    minHeight:120,display:'flex',flexDirection:'column',justifyContent:'space-between'}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                    <span style={{fontSize:28,fontWeight:900,color:c.fg,lineHeight:1}}>P{n}</span>
                    {isLav&&<span style={{fontSize:8,fontWeight:800,color:'#1D5FAD',
                      background:'#eff6ff',padding:'2px 6px',borderRadius:4,letterSpacing:1}}>● LIVE</span>}
                  </div>
                  {info ? (
                    <div>
                      <div style={{fontSize:11,fontWeight:800,color:c.fg,
                        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap',marginBottom:4}}>
                        {info.proj.name}
                      </div>
                      <div style={{height:4,background:'rgba(0,0,0,0.1)',borderRadius:2,overflow:'hidden',marginBottom:3}}>
                        <div style={{height:'100%',width:`${info.pct}%`,
                          background:info.colore,borderRadius:2,transition:'width 0.3s'}}/>
                      </div>
                      <div style={{display:'flex',justifyContent:'space-between'}}>
                        <span style={{fontSize:9,color:c.fg,opacity:0.7}}>{info.done}/{info.tot} pgm</span>
                        <span style={{fontSize:11,fontWeight:800,color:c.fg}}>{info.pct}%</span>
                      </div>
                      <div style={{fontSize:8,fontWeight:700,color:c.fg,
                        letterSpacing:1,marginTop:3,opacity:0.85}}>{c.label}</div>
                    </div>
                  ) : (
                    <div style={{fontSize:10,fontWeight:600,color:c.fg,letterSpacing:1}}>VUOTO</div>
                  )}
                </div>
              )
            })}
          </div>
        </div>

        {/* ── COL 2: PROGETTO ATTIVO + SCADENZE + UTENSILI ──────────────── */}
        <div style={{display:'flex',flexDirection:'column',gap:12}}>

          {/* Progetto in lavorazione */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'14px 18px'}}>
            <div style={{fontSize:11,fontWeight:800,letterSpacing:'0.08em',color:'#0d2d5e',marginBottom:10}}>
              PROGETTO IN LAVORAZIONE
            </div>
            {progettoLav && lavInfo ? (
              <div>
                <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
                  <div style={{width:10,height:10,borderRadius:'50%',
                    background:progettoLav.color||'#1D5FAD',flexShrink:0}}/>
                  <span style={{fontSize:16,fontWeight:800,color:'#0d2d5e',
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
            ) : (
              <div style={{color:'#94a3b8',fontSize:13,fontStyle:'italic'}}>
                Nessun pallet in lavorazione
              </div>
            )}
          </div>

          {/* Scadenze */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'14px 18px'}}>
            <div style={{fontSize:11,fontWeight:800,letterSpacing:'0.08em',color:'#0d2d5e',marginBottom:10}}>
              SCADENZE PROGETTI
            </div>
            {conScadenza.length===0 ? (
              <div style={{color:'#94a3b8',fontSize:13,fontStyle:'italic'}}>Nessun progetto con scadenza</div>
            ) : (
              <div style={{display:'flex',flexDirection:'column',gap:5}}>
                {conScadenza.map(({p,days,pNum})=>{
                  const overdue = days<0
                  const today   = days===0
                  const soon    = days>0&&days<=3
                  const color   = overdue?'#dc2626':today?'#d97706':soon?'#c2410c':'#475569'
                  const bg      = overdue?'#fef2f2':today?'#fffbeb':soon?'#fff7ed':'#f8fafc'
                  const badge   = overdue?`${Math.abs(days)}gg fa`:today?'OGGI':`${days}gg`
                  return (
                    <div key={p.id} onClick={()=>onNavigateProject(p.id)}
                      style={{display:'flex',alignItems:'center',gap:10,
                        background:bg,borderRadius:8,padding:'7px 12px',cursor:'pointer',
                        border:`1px solid ${color}22`}}>
                      <div style={{width:7,height:7,borderRadius:'50%',background:color,flexShrink:0}}/>
                      <span style={{fontSize:12,fontWeight:700,color:'#1e293b',flex:1,
                        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                        {p.name}
                      </span>
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
              {utensiliProblema.length>0&&
                <span style={{marginLeft:8,fontSize:11,fontWeight:800,color:'#dc2626',
                  background:'#fef2f2',padding:'1px 8px',borderRadius:10}}>
                  {utensiliProblema.length}
                </span>}
            </div>
            {utensiliProblema.length===0 ? (
              <div style={{color:'#22c55e',fontSize:13,fontWeight:600}}>✓ Nessun problema rilevato</div>
            ) : (
              <div style={{display:'flex',flexDirection:'column',gap:4}}>
                {utensiliProblema.map(u=>(
                  <div key={u.alias}
                    style={{display:'flex',alignItems:'center',gap:10,
                      background:u.bg,border:`1px solid ${u.border}`,
                      borderRadius:8,padding:'7px 12px'}}>
                    <span style={{fontSize:11,fontWeight:800,color:u.color,
                      background:'#fff',padding:'1px 7px',borderRadius:4,
                      border:`1px solid ${u.border}`,flexShrink:0,minWidth:70,textAlign:'center'}}>
                      {u.label}
                    </span>
                    <span style={{fontSize:12,fontWeight:700,color:'#1e293b',
                      fontFamily:'monospace',flex:1,
                      overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                      {u.alias}
                    </span>
                    {u.detail&&<span style={{fontSize:10,color:u.color,opacity:0.8,
                      flexShrink:0,maxWidth:160,overflow:'hidden',
                      textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                      {u.detail}
                    </span>}
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>

        {/* ── COL 3: METRICHE ───────────────────────────────────────────── */}
        <div style={{display:'flex',flexDirection:'column',gap:10}}>
          <div style={{fontSize:11,fontWeight:800,letterSpacing:'0.08em',color:'#0d2d5e'}}>METRICHE TURNO</div>
          {[
            {val:pgmDaFare,  label:'Da fare',       sub:`${inProgress.length} lavori attivi`, color:'#0d2d5e', bg:'#eff6ff'},
            {val:pgmInMac,   label:'In macchina',    sub:'programmi attivi',                  color:'#1D5FAD', bg:'#dbeafe'},
            {val:pgmOggi,    label:'Completati oggi',sub:'nel turno corrente',                color:'#166534', bg:'#dcfce7'},
            {val:critici,    label:'Critici',         sub:'scaduti o in ritardo',             color:'#dc2626', bg:'#fef2f2'},
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

function QuickTaskRow({task, onToggle, onDelete, onPriority, onEditText}) {
  const [editing, setEditing] = useState(false)
  const [val, setVal] = useState(task.text)
  const PRIO = {alta:{color:'#dc2626',dot:'🔴'},media:{color:'#d97706',dot:'🟡'},bassa:{color:'#16a34a',dot:'🟢'}}
  const p = PRIO[task.priority] || PRIO.media
  return (
    <div style={{display:'flex',alignItems:'center',gap:6,padding:'6px 4px',borderRadius:6,
      background:task.done?T.surface2:'transparent',marginBottom:2,opacity:task.done?0.6:1}}>
      <div onClick={onToggle} style={{width:18,height:18,borderRadius:5,flexShrink:0,cursor:'pointer',
        display:'flex',alignItems:'center',justifyContent:'center',
        border:task.done?'none':'1.5px solid #cbd5e1',
        background:task.done?T.green:'transparent'}}>
        {task.done&&<span style={{color:'#fff',fontSize:11,fontWeight:800}}>✓</span>}
      </div>
      {editing ? (
        <input autoFocus value={val}
          onChange={e=>setVal(e.target.value)}
          onBlur={()=>{onEditText(val);setEditing(false)}}
          onKeyDown={e=>{if(e.key==='Enter'){onEditText(val);setEditing(false)}if(e.key==='Escape')setEditing(false)}}
          style={{flex:1,fontSize:12,border:'1px solid #cbd5e1',borderRadius:4,padding:'2px 6px'}}/>
      ) : (
        <span onDoubleClick={()=>setEditing(true)} style={{flex:1,fontSize:12,
          color:task.done?T.textMuted:T.text,
          textDecoration:task.done?'line-through':'none',cursor:'text',
          userSelect:'none'}}>
          {task.text}
        </span>
      )}
      <span onClick={()=>onPriority(task.priority==='alta'?'media':task.priority==='media'?'bassa':'alta')}
        style={{cursor:'pointer',fontSize:12,flexShrink:0}} title="Cambia priorità">
        {p.dot}
      </span>
      <span onClick={onDelete} style={{cursor:'pointer',color:T.textMuted,fontSize:14,
        flexShrink:0,lineHeight:1}} title="Elimina">×</span>
    </div>
  )
}

function QuickTasksSidebar({collapsed,onToggleCollapse}){
  const[tasks,setTasks]=useState([])
  const[newText,setNewText]=useState('')
  const[newPrio,setNewPrio]=useState('media')
  const[filter,setFilter]=useState('tutti')
  const inputRef=useRef(null)
  const pendingCount=tasks.filter(t=>!t.done).length

  // Carica da API all'avvio e ogni 15s
  useEffect(()=>{
    const load=()=>fetch('/api/progetti/quick-tasks').then(r=>r.ok?r.json():{tasks:[]}).then(d=>setTasks(d.tasks||[])).catch(()=>{})
    load()
    const t=setInterval(load,15000)
    return()=>clearInterval(t)
  },[])

  // Salva su API ogni volta che tasks cambia
  const saveRef=useRef(null)
  useEffect(()=>{
    if(saveRef.current) clearTimeout(saveRef.current)
    saveRef.current=setTimeout(()=>{
      fetch('/api/progetti/quick-tasks',{method:'PUT',headers:{'Content-Type':'application/json'},body:JSON.stringify({tasks})}).catch(()=>{})
    },400)
  },[tasks])

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
    <div style={{flex:1,overflowY:'auto',padding:'24px 28px',background:T.bg,fontFamily:"var(--font-display)"}}>
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
  const[color,setColor]=useState(preselectedTemplate?.color||'#0d2d5e')
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
  const location=useLocation()
  const[projects,setProjects]=useState([])
  const[templates,setTemplates]=useState([])
  const[palletDisponibili,setPalletDisponibili]=useState([])
  const[palletState,setPalletState]=useState([])
  const[setupData,setSetupData]=useState(null)
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
  const[saveError,setSaveError]=useState(null)        // errore salvataggio batch
  const[importMsg,setImportMsg]=useState(null)
  const importRef=useRef(null)
  const saveTimer=useRef(null)
  const autoBackupTimer=useRef(null)
  const isSaving=useRef(false)          // lock: true durante debounce+save+grace period
  const writeLockTimer=useRef(null)     // timer per rilasciare il lock dopo il salvataggio

  // ── Carica ──────────────────────────────────────────────────────────────────
  const load=useCallback(async()=>{
    try{
      const [r, rd] = await Promise.all([
        fetch(API+'/'),
        fetch(API+'/deliveries')
      ])
      if(!r.ok) throw new Error(`Server error ${r.status}`)
      const d=await r.json()
      const projs = (d.projects||[]).map(p=>({pallet_assegnato:null,...p,
        // Pulizia dataPost corrotti (valori numerici puri come "35" dal vecchio parser)
        steps:(p.steps||[]).map(s=>({...s,tasks:(s.tasks||[]).map(t=>({...t,
          programs:(t.programs||[]).map(pgm=>{
            const dp=pgm.dataPost
            return dp&&/^\d+$/.test(dp.toString().trim())?{...pgm,dataPost:''}:pgm
          })
        }))}))}))
      setProjects(projs)
      setTemplates(d.templates||[])
      if(rd.ok){ const ds=await rd.json(); setDeliveries(Array.isArray(ds)?ds:[]) }
      setError(null)
    }catch(e){setError(e.message)}
    finally{setLoading(false)}
  },[])

  // Polling leggero: ricarica solo i progetti (non deliveries) ogni 8s per sync col desktop
  const silentRefresh=useCallback(async()=>{
    // Non sovrascrivere mentre l'utente sta modificando e salvando
    if(isSaving.current) return
    try{
      const r=await fetch(API)
      if(!r.ok) return
      // Ricontrolla dopo la fetch — potrebbe essere partita una modifica nel frattempo
      if(isSaving.current) return
      const d=await r.json()
      const projs=(d.projects||[]).map(p=>({pallet_assegnato:null,...p}))
      setProjects(curr=>{
        // Merge chirurgico: aggiorna solo i progetti che il server ha cambiato
        // e che NON sono selezionati (aperti in edit dall'utente)
        let changed=false
        const next=curr.map(cp=>{
          const sp=projs.find(p=>p.id===cp.id)
          if(!sp) return cp
          // Non toccare il progetto aperto (selectedId) — l'utente potrebbe star editando
          if(cp.id===selectedId) return cp
          // Aggiorna solo se il server ha una versione diversa
          if(JSON.stringify(cp.steps)!==JSON.stringify(sp.steps)){
            changed=true
            return sp
          }
          return cp
        })
        return changed ? next : curr
      })
    }catch{}
  // eslint-disable-next-line react-hooks/exhaustive-deps
  },[selectedId])
  useEffect(()=>{
    load()

    // Polling consolidato: pallet disponibili + stato ogni 15s
    // (era duplicato: 10s + 15s separati → ora un solo fetch ogni 15s)
    function caricaPallet(){
      fetch('/api/pallet/').then(r=>r.ok?r.json():{pallet:[]})
        .then(d=>{
          setPalletState(d.pallet||[])
          // disponibili = pallet non in_lavorazione
          setPalletDisponibili((d.pallet||[]).filter(p=>
            (p.stato||'').toLowerCase().replace(' ','_') !== 'in_lavorazione'
          ))
        }).catch(()=>{})
    }
    caricaPallet()
    const t=setInterval(caricaPallet, 15000)

    // Polling sync dal desktop ogni 8s — usa evento GlobalPoller se disponibile
    // per evitare doppio fetch quando GlobalPoller è già attivo
    const t3=setInterval(silentRefresh, 8000)

    // Reagisce all'evento del GlobalPoller (App.jsx) — aggiorna pallet senza polling separato
    const onUpdate = () => caricaPallet()
    window.addEventListener('dmgdesk:stati-aggiornati', onUpdate)

    // Carica setup data per utensili critici (una tantum)
    fetch('/api/progetti/analisi-setup/non-utilizzati').then(r=>r.ok?r.json():null)
      .then(d=>{ if(d) setSetupData(d) }).catch(()=>{})

    return()=>{
      clearInterval(t)
      clearInterval(t3)
      window.removeEventListener('dmgdesk:stati-aggiornati', onUpdate)
    }
  },[load,silentRefresh])

  // Apre il progetto giusto dopo il caricamento (da sessionStorage o navigation state)
  useEffect(()=>{
    if(!projects.length) return
    // Apertura da navigation state (da Home → click pallet/progetto)
    const openId = location.state?.openId
    if(openId){
      navigate(location.pathname,{replace:true,state:{}}) // pulisce lo state
      if(projects.find(p=>p.id===openId)){ setSelectedId(openId); setPage('projects'); return }
    }
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
  },[projects, location.state])

  // ── Salva progetti (debounced) ───────────────────────────────────────────────
  const persistProjects=useCallback((projs)=>{
    // Attiva il lock immediatamente al primo click — il refresh non sovrascriverà
    isSaving.current=true
    clearTimeout(writeLockTimer.current)
    clearTimeout(saveTimer.current)
    saveTimer.current=setTimeout(async()=>{
      try{
        // Salva tutti i progetti in una sola richiesta (batch endpoint)
        const r=await fetch(`${API}/batch/save`,{
          method:'PUT',
          headers:{'Content-Type':'application/json'},
          body:JSON.stringify({projects:projs})
        })
        if(!r.ok) throw new Error(`Server ${r.status}`)
        setLastSavedProj(nowStr())
        setSaveError(null)
      }catch(e){
        setSaveError('Salvataggio fallito — riprova')
        setTimeout(()=>setSaveError(null), 6000)
        console.warn('[Progetti] batch save error:', e.message)
      }finally{
        // Grace period: mantieni il lock 3s dopo il salvataggio per evitare
        // che il silentRefresh immediatamente successivo sovrascriva
        writeLockTimer.current=setTimeout(()=>{ isSaving.current=false },3000)
      }
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
          body:JSON.stringify(toSave)})
          .then(r=>{ if(!r.ok) console.warn('[Deliveries] PUT fallito:', r.status) })
          .catch(e=>console.warn('[Deliveries] PUT errore rete:', e.message))
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
    // pgmSelezionati può contenere sia fresatura che IPM (dalla modale)
    // Fallback senza selezione: solo fresatura da_fare (comportamento precedente)
    const mpf = pgmSelezionati || (project.steps||[])
      .flatMap(s=>s.tasks||[])
      .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
      .flatMap(t=>(t.programs||[]).filter(p=>p.tipoGruppo!=='ipm'&&p.stato==='da_fare'))
    if(!mpf.length) return

    // Aggiorna stato → in_macchina per TUTTI i selezionati (fresatura + IPM)
    const mpfIds = new Set(mpf.map(p=>p.id))
    const now = nowStr()
    const updatedProject = {
      ...project,
      steps: (project.steps||[]).map(s=>({
        ...s,
        tasks: (s.tasks||[]).map(t=>{
          if(t.text?.trim().toLowerCase()!=='fresatura') return t
          return {
            ...t,
            programs: (t.programs||[]).map(p=>{
              if(!mpfIds.has(p.id)) return p
              return {...p, stato:'in_macchina', tempoInizio: p.tempoInizio||now}
            })
          }
        })
      }))
    }
    updateProject(updatedProject)

    const nomeFromProject = project.name.replace(/\s+/g,'_').replace(/[^a-zA-Z0-9_]/g,'').toUpperCase()
    const firstFres = mpf.find(p=>p.tipoGruppo!=='ipm') || mpf[0]
    const firstFile = firstFres?.filename || ''
    const baseTokens = firstFile.replace(/\.MPF$/i,'').split('_')
    const nomeFromFile = /^\d+$/.test(baseTokens[0]) && baseTokens.length >= 2
      ? `${baseTokens[0]}_${baseTokens[1]}`
      : null
    const nomeCartella = nomeFromProject || nomeFromFile || ''

    sessionStorage.setItem('dmgdesk_lancio_nc', JSON.stringify({
      projectId:   project.id,
      projectName: project.name,
      nomeCartella,
      mpfFiles:    mpf.map(p=>p.filename)   // include sia fresatura che IPM
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

  if(loading) return <div style={{display:'flex',alignItems:'center',justifyContent:'center',height:'100%',color:T.textMuted,background:T.bg,fontFamily:"var(--font-display)"}}>Caricamento...</div>

  return(
    <div style={{height:'100%',display:'flex',flexDirection:'column',background:T.bg,fontFamily:"var(--font-display)",color:T.text}}>
      <style>{`*{box-sizing:border-box}input,textarea,select{font-family:inherit}@keyframes pulse-dot{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.85)}}`}</style>

      {/* TOP BAR */}
      {!isOnProject&&!isOnEditor&&(
        <div style={{borderBottom:`1px solid ${T.border}`,padding:'0 28px',display:'flex',alignItems:'center',gap:0,flexShrink:0,background:T.surface,boxShadow:'0 1px 0 rgba(0,0,0,0.06)'}}>
          <div style={{fontSize:20,fontWeight:800,color:T.text,letterSpacing:'-0.02em',padding:'16px 16px 16px 0',marginRight:4,borderRight:`1px solid ${T.border}`}}><span style={{color:T.accent}}>◈</span> DMGDesk</div>
          <NavBtn id='projects' label='Lavori'/>
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
      <div style={{flex:1,overflow:'hidden',display:'flex',flexDirection:'column'}}>
        {/* Banner errore salvataggio — visibile in tutte le pagine */}
        {saveError&&(
          <div style={{padding:'8px 20px',background:'#fef2f2',borderBottom:'1px solid #fca5a5',
            fontSize:12,fontWeight:700,color:'#dc2626',display:'flex',alignItems:'center',gap:8,flexShrink:0}}>
            <span>⚠</span>
            <span>{saveError}</span>
          </div>
        )}
      <div style={{flex:1,overflow:'hidden',display:'flex',flexDirection:'row'}}>
        <div style={{flex:1,overflow:'hidden',display:'flex',flexDirection:'column'}}>
          {isOnEditor?(
            <TemplateEditor template={editingTemplate} onSave={saveTemplate} onCancel={()=>{setPage('templates');setEditingTemplate(null)}}/>
          ):isOnProject?(
            <ProjectDetail project={selectedProject} onBack={()=>setSelectedId(null)} onUpdate={updateProject} onDelete={deleteProject} onArchive={archiveProject} templates={templates} onSaveAsTemplate={tmpl=>{setTemplates(ts=>{const next=ts.some(t=>t.id===tmpl.id)?ts.map(t=>t.id===tmpl.id?tmpl:t):[...ts,tmpl];persistTemplates(next);return next})}} onLanciaNC={lanciaNC} palletDisponibili={palletDisponibili} palletStato={palletState}/>
          ):page==='home'?(
            <HomePage projects={projects} deliveries={deliveries} palletState={palletState} setupData={setupData}
              onNavigateProject={id=>{setSelectedId(id);setPage('projects')}}
              onNavigateCoda={()=>{ navigate('/coda'); }}/>
          ):page==='templates'?(
            <TemplatesPage templates={templates} onEdit={tmpl=>{setEditingTemplate(tmpl);setPage('templateEditor')}} onCreate={()=>{setEditingTemplate({id:`new_${uid()}`,name:'Nuovo Template',description:'',icon:'🚀',color:'#0d2d5e',steps:[]});setPage('templateEditor')}} onDelete={deleteTemplate} onDuplicate={duplicateTemplate} onUseTemplate={useTemplate} lastSaved={lastSavedTmpl}/>
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
            <div style={{flex:1,overflowY:'auto',padding:'16px 28px',background:T.bg}}>
              {inProgress.length===0&&completed.length===0&&(
                <div style={{textAlign:'center',padding:'80px 0'}}>
                  <div style={{fontSize:48,marginBottom:16}}>🚀</div>
                  <div style={{fontSize:20,fontWeight:700,color:T.text,marginBottom:8}}>Nessun progetto ancora</div>
                  <div style={{fontSize:15,color:T.textSub,marginBottom:24}}>Crea il tuo primo progetto per iniziare</div>
                  <button onClick={()=>setShowNewProject(true)} style={{background:T.accent,border:'none',borderRadius:10,color:'#fff',fontWeight:700,fontSize:16,padding:'12px 28px',cursor:'pointer'}}>+ Crea il primo progetto</button>
                </div>
              )}

              {/* ── TOOLBAR FILTRI ────────────────────────────────────── */}
              {(inProgress.length>0||completed.length>0)&&(()=>{
                // Stato locale filtri — usiamo ref per non causare re-render del parent
                // (i filtri vivono nel render inline tramite IIFE con useState locale)
                return null
              })()}
              {(inProgress.length>0||completed.length>0)&&(
                <ProgettiListaFiltrata
                  inProgress={inProgress}
                  completed={completed}
                  urgentProjects={urgentProjects}
                  palletState={palletState}
                  deliveries={deliveries}
                  getDelivery={getDelivery}
                  setDelivery={setDelivery}
                  deleteProject={deleteProject}
                  archiveProject={archiveProject}
                  setSelectedId={setSelectedId}
                  nowStr={nowStr}
                />
              )}
            </div>
          )}
        </div>
        <QuickTasksSidebar collapsed={sidebarCollapsed} onToggleCollapse={()=>setSidebarCollapsed(v=>!v)}/>
      </div>
      </div>

      {showNewProject&&(
        <NewProjectModal onClose={()=>{setShowNewProject(false);setPreselectedTemplate(null)}} onCreate={p=>{addProject(p);setShowNewProject(false);setPreselectedTemplate(null)}} templates={templates} preselectedTemplate={preselectedTemplate}/>
      )}
    </div>
  )
}
