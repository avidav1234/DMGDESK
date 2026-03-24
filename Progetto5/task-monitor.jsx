import { useState, useRef, useEffect } from "react";

// ─── PERSISTENZA & BACKUP ─────────────────────────────────────────────────────
const STORAGE_TEMPLATES    = "worktrack_templates_v1";
const STORAGE_PROJECTS     = "worktrack_projects_v1";
const STORAGE_BACKUP_INDEX = "worktrack_backup_index_v1"; // lista metadati backup
const STORAGE_BACKUP_DATA  = "worktrack_backup_data_v1";  // mappa id→payload
const BACKUP_VERSION       = 2;
const MAX_AUTO_BACKUPS      = 30; // giorni massimi conservati

// ── helpers storage ──────────────────────────────────────────────────────────
function lsGet(key) { try { const r = localStorage.getItem(key); return r ? JSON.parse(r) : null; } catch { return null; } }
function lsSet(key, val) { try { localStorage.setItem(key, JSON.stringify(val)); return true; } catch { return false; } }

// ── progetti ─────────────────────────────────────────────────────────────────
function loadProjectsFromStorage() {
  const p = lsGet(STORAGE_PROJECTS);
  return Array.isArray(p) ? p : null;
}
function saveProjectsToStorage(p) { lsSet(STORAGE_PROJECTS, p); }

// ── template ──────────────────────────────────────────────────────────────────
function loadTemplatesFromStorage() {
  const t = lsGet(STORAGE_TEMPLATES);
  return Array.isArray(t) && t.length > 0 ? t : null;
}
function saveTemplatesToStorage(t) { lsSet(STORAGE_TEMPLATES, t); }

// ── backup index ──────────────────────────────────────────────────────────────
// index entry: { id, label, createdAt (ISO), type: "auto"|"manual", projectCount, templateCount }
function loadBackupIndex() { return lsGet(STORAGE_BACKUP_INDEX) || []; }
function loadBackupData()  { return lsGet(STORAGE_BACKUP_DATA)  || {}; }

function saveBackupToStorage(projects, templates, type = "auto", customLabel = null) {
  const index = loadBackupIndex();
  const data  = loadBackupData();
  const now   = new Date();
  const dateStr = now.toISOString().slice(0, 10);

  // Per i backup automatici: uno al giorno — se esiste già per oggi, aggiorna
  if (type === "auto") {
    const todayEntry = index.find(e => e.type === "auto" && e.createdAt.startsWith(dateStr));
    if (todayEntry) {
      data[todayEntry.id] = { projects, templates };
      lsSet(STORAGE_BACKUP_DATA, data);
      // aggiorna contatori
      todayEntry.projectCount  = projects.length;
      todayEntry.templateCount = templates.length;
      todayEntry.createdAt     = now.toISOString();
      lsSet(STORAGE_BACKUP_INDEX, index);
      return;
    }
  }

  const id = `bk_${Date.now()}`;
  const entry = {
    id,
    label: customLabel || (type === "auto"
      ? `Backup automatico ${dateStr}`
      : `Backup manuale ${now.toLocaleString("it-IT")}`),
    createdAt: now.toISOString(),
    type,
    projectCount:  projects.length,
    templateCount: templates.length,
  };

  data[id] = { projects, templates };
  index.unshift(entry); // più recente in testa

  // Pulizia: tieni solo MAX_AUTO_BACKUPS backup automatici
  const autoEntries = index.filter(e => e.type === "auto");
  if (autoEntries.length > MAX_AUTO_BACKUPS) {
    const toDelete = autoEntries.slice(MAX_AUTO_BACKUPS);
    toDelete.forEach(e => { delete data[e.id]; });
    const deleteIds = new Set(toDelete.map(e => e.id));
    lsSet(STORAGE_BACKUP_INDEX, index.filter(e => !deleteIds.has(e.id)));
  } else {
    lsSet(STORAGE_BACKUP_INDEX, index);
  }
  lsSet(STORAGE_BACKUP_DATA, data);
}

function deleteBackupFromStorage(id) {
  const index = loadBackupIndex().filter(e => e.id !== id);
  const data  = loadBackupData();
  delete data[id];
  lsSet(STORAGE_BACKUP_INDEX, index);
  lsSet(STORAGE_BACKUP_DATA, data);
}

function getBackupPayload(id) {
  const data = loadBackupData();
  return data[id] || null;
}

// ── export / import file ─────────────────────────────────────────────────────
function exportToFile(projects, templates, label = null) {
  const payload = {
    _worktrack: true,
    version: BACKUP_VERSION,
    exportedAt: new Date().toISOString(),
    label: label || `Backup ${new Date().toISOString().slice(0,10)}`,
    projects,
    templates,
  };
  const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `worktrack_backup_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function importFromFile(file, onSuccess, onError) {
  const reader = new FileReader();
  reader.onload = e => {
    try {
      const parsed = JSON.parse(e.target.result);
      if (parsed._worktrack || parsed._worktrack_backup) {
        if (!Array.isArray(parsed.projects) || !Array.isArray(parsed.templates))
          throw new Error("File backup danneggiato");
        onSuccess({ projects: parsed.projects, templates: parsed.templates, label: parsed.label });
      } else if (Array.isArray(parsed)) {
        // legacy: solo template
        parsed.forEach(t => { if (!t.id || !t.name) throw new Error("Template malformato"); });
        onSuccess({ projects: null, templates: parsed, label: null });
      } else {
        throw new Error("Formato non riconosciuto. Usa un file .json esportato da WorkTrack.");
      }
    } catch(err) { onError(err.message); }
  };
  reader.readAsText(file);
}

// Export solo template (compatibilità pagina template)
function exportTemplatesAsJSON(templates) {
  const blob = new Blob([JSON.stringify(templates, null, 2)], { type: "application/json" });
  const url  = URL.createObjectURL(blob);
  const a    = document.createElement("a");
  a.href     = url;
  a.download = `worktrack_templates_${new Date().toISOString().slice(0,10)}.json`;
  a.click();
  URL.revokeObjectURL(url);
}

function importTemplatesFromJSON(file, onSuccess, onError) {
  const reader = new FileReader();
  reader.onload = e => {
    try {
      const parsed = JSON.parse(e.target.result);
      if (!Array.isArray(parsed)) throw new Error("Formato non valido");
      parsed.forEach(t => { if (!t.id || !t.name || !Array.isArray(t.steps)) throw new Error("Template malformato"); });
      onSuccess(parsed);
    } catch(err) { onError(err.message); }
  };
  reader.readAsText(file);
}

// ─── THEME ────────────────────────────────────────────────────────────────────
const T = {
  bg:        "#F5F4F0",
  surface:   "#FFFFFF",
  surface2:  "#F0EEE8",
  border:    "#D8D5CC",
  borderStrong: "#B0ADA4",
  text:      "#1A1814",
  textSub:   "#5A5750",
  textMuted: "#9A978E",
  accent:    "#D4700A",
  accentBg:  "#FFF4E8",
  green:     "#1A7A4A",
  greenBg:   "#E8F5EE",
  red:       "#C0392B",
  redBg:     "#FDECEA",
  blue:      "#1D5FAD",
  blueBg:    "#EAF1FB",
};

// ─── DATI INIZIALI ────────────────────────────────────────────────────────────
const INITIAL_TEMPLATES = [
  {
    id:"tmpl1", name:"Progetto Web", description:"Siti web e e-commerce", icon:"🌐", color:"#1D5FAD",
    steps:[
      {id:"ts1",title:"Analisi",tasks:[{id:"tt1",text:"Brief con cliente"},{id:"tt2",text:"Analisi competitor"},{id:"tt3",text:"Definizione obiettivi"}]},
      {id:"ts2",title:"Design",tasks:[{id:"tt4",text:"Wireframe"},{id:"tt5",text:"Palette colori"},{id:"tt6",text:"Design UI"},{id:"tt7",text:"Approvazione cliente"}]},
      {id:"ts3",title:"Sviluppo",tasks:[{id:"tt8",text:"Setup ambiente"},{id:"tt9",text:"Frontend"},{id:"tt10",text:"Backend / CMS"},{id:"tt11",text:"Test cross-browser"}]},
      {id:"ts4",title:"Deploy",tasks:[{id:"tt12",text:"Configurazione server"},{id:"tt13",text:"Go live"},{id:"tt14",text:"Monitoraggio post-launch"}]},
    ]
  },
  {
    id:"tmpl2", name:"App Mobile", description:"App iOS e Android", icon:"📱", color:"#1A7A4A",
    steps:[
      {id:"ts5",title:"Discovery",tasks:[{id:"tt15",text:"Interviste stakeholder"},{id:"tt16",text:"Documento requisiti"},{id:"tt17",text:"User stories"}]},
      {id:"ts6",title:"Prototipo",tasks:[{id:"tt18",text:"Flussi utente"},{id:"tt19",text:"Prototipo interattivo"},{id:"tt20",text:"Test usabilità"}]},
      {id:"ts7",title:"Sviluppo MVP",tasks:[{id:"tt21",text:"Setup ambiente"},{id:"tt22",text:"Autenticazione"},{id:"tt23",text:"Schermata principale"},{id:"tt24",text:"API integration"}]},
      {id:"ts8",title:"Release",tasks:[{id:"tt25",text:"QA e bug fixing"},{id:"tt26",text:"App Store submission"},{id:"tt27",text:"Monitoring"}]},
    ]
  },
  {
    id:"tmpl3", name:"Campagna Marketing", description:"Campagne digital", icon:"📣", color:"#8B2FC9",
    steps:[
      {id:"ts9",title:"Strategia",tasks:[{id:"tt28",text:"Definizione target"},{id:"tt29",text:"Analisi canali"},{id:"tt30",text:"Budget e KPI"}]},
      {id:"ts10",title:"Contenuti",tasks:[{id:"tt31",text:"Copywriting"},{id:"tt32",text:"Visual e grafiche"},{id:"tt33",text:"Video / Reel"}]},
      {id:"ts11",title:"Lancio",tasks:[{id:"tt34",text:"Scheduling post"},{id:"tt35",text:"Setup ads"},{id:"tt36",text:"Email campaign"}]},
      {id:"ts12",title:"Analisi",tasks:[{id:"tt37",text:"Report risultati"},{id:"tt38",text:"Ottimizzazione"}]},
    ]
  }
];

const INITIAL_DATA = {
  projects:[
    {
      id:"p1", name:"Sito Web Cliente Rossi", color:"#D4700A",
      description:"Redesign completo sito e-commerce", createdAt:"2026-02-10", archived:false,
      steps:[
        {id:"s1",title:"Analisi e wireframe",tasks:[
          {id:"t1",text:"Brief con cliente",done:true,note:"",doneAt:"2026-02-11"},
          {id:"t2",text:"Analisi competitor",done:true,note:"",doneAt:"2026-02-12"},
          {id:"t3",text:"Wireframe homepage",done:true,note:"",doneAt:"2026-02-14"},
        ]},
        {id:"s2",title:"Design UI",tasks:[
          {id:"t4",text:"Palette colori e typography",done:true,note:"",doneAt:"2026-02-18"},
          {id:"t5",text:"Design homepage",done:false,note:"In attesa approvazione palette dal cliente",doneAt:null},
          {id:"t6",text:"Design pagine interne",done:false,note:"",doneAt:null},
        ]},
        {id:"s3",title:"Sviluppo",tasks:[
          {id:"t7",text:"Setup ambiente",done:false,note:"",doneAt:null},
          {id:"t8",text:"Frontend",done:false,note:"",doneAt:null},
        ]}
      ],
      log:[{id:"l1",user:"Tu",text:"Palette inviata, aspettiamo feedback",time:"2026-02-19 09:15"}]
    },
    {
      id:"p2", name:"Logo Brand Verdi", color:"#1A7A4A",
      description:"Identità visiva completa", createdAt:"2026-01-15", archived:false,
      steps:[
        {id:"s4",title:"Ricerca",tasks:[
          {id:"t9",text:"Moodboard",done:true,note:"",doneAt:"2026-01-16"},
          {id:"t10",text:"Analisi settore",done:true,note:"",doneAt:"2026-01-17"},
        ]},
        {id:"s5",title:"Concept",tasks:[
          {id:"t11",text:"Bozzetti a mano",done:true,note:"",doneAt:"2026-01-20"},
          {id:"t12",text:"3 proposte digitali",done:true,note:"",doneAt:"2026-01-25"},
          {id:"t13",text:"Presentazione cliente",done:true,note:"",doneAt:"2026-01-28"},
        ]},
        {id:"s6",title:"Finalizzazione",tasks:[
          {id:"t14",text:"Revisioni feedback",done:true,note:"",doneAt:"2026-02-02"},
          {id:"t15",text:"Brand guidelines",done:true,note:"",doneAt:"2026-02-05"},
          {id:"t16",text:"Export file finali",done:true,note:"",doneAt:"2026-02-06"},
        ]}
      ],
      log:[{id:"l2",user:"Tu",text:"Progetto consegnato e approvato!",time:"2026-02-06 17:00"}]
    }
  ],
  templates:INITIAL_TEMPLATES
};

// ─── UTILS ────────────────────────────────────────────────────────────────────
function uid() { return Math.random().toString(36).slice(2,9); }
function nowStr() { return new Date().toLocaleString("it-IT",{year:"numeric",month:"2-digit",day:"2-digit",hour:"2-digit",minute:"2-digit"}).replace(",",""); }
function getProgress(project) {
  const all=project.steps.flatMap(s=>s.tasks);
  if(!all.length)return 0;
  return Math.round((all.filter(t=>t.done).length/all.length)*100);
}
function getNextTask(project) {
  for(const step of project.steps){const next=step.tasks.find(t=>!t.done);if(next)return{step,task:next};}
  return null;
}
function cloneTemplateToSteps(tmpl) {
  return tmpl.steps.map(s=>({...s,id:uid(),tasks:s.tasks.map(t=>({...t,id:uid(),done:false,note:"",doneAt:null}))}));
}
function reorder(arr,from,to){const r=[...arr];const[item]=r.splice(from,1);r.splice(to,0,item);return r;}

const COLORS=["#D4700A","#1A7A4A","#1D5FAD","#C0392B","#8B2FC9","#C2185B","#0097A7","#E65100"];
const ICONS=["🌐","📱","📣","🏗️","📦","🎯","🔧","📊","✍️","🚀","💡","🎨"];

// ─── SHARED UI ────────────────────────────────────────────────────────────────
function ProgressBar({value,color}){
  return(
    <div style={{height:8,background:T.surface2,borderRadius:4,overflow:"hidden",border:`1px solid ${T.border}`}}>
      <div style={{height:"100%",width:`${value}%`,background:color,borderRadius:4,transition:"width 0.5s ease"}}/>
    </div>
  );
}

function StatusBadge({progress}){
  const s=progress===100?["COMPLETATO",T.green,T.greenBg]:
           progress===0?["NON INIZIATO",T.textMuted,T.surface2]:
           progress<50?["IN CORSO",T.accent,T.accentBg]:
           ["AVANZATO",T.blue,T.blueBg];
  return(
    <span style={{fontSize:11,fontWeight:700,letterSpacing:"0.08em",color:s[1],background:s[2],padding:"3px 10px",borderRadius:20,border:`1px solid ${s[1]}44`}}>
      {s[0]}
    </span>
  );
}

function ConfirmDialog({message,onConfirm,onCancel}){
  return(
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:200}} onClick={onCancel}>
      <div onClick={e=>e.stopPropagation()} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:12,padding:"28px 32px",maxWidth:380,width:"90vw",textAlign:"center",boxShadow:"0 8px 32px rgba(0,0,0,0.18)"}}>
        <div style={{fontSize:16,color:T.text,marginBottom:20,lineHeight:1.6}}>{message}</div>
        <div style={{display:"flex",gap:10,justifyContent:"center"}}>
          <button onClick={onCancel} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:"9px 22px",cursor:"pointer",fontWeight:600}}>Annulla</button>
          <button onClick={onConfirm} style={{background:T.red,border:"none",borderRadius:8,color:"#fff",fontWeight:700,fontSize:14,padding:"9px 22px",cursor:"pointer"}}>Conferma</button>
        </div>
      </div>
    </div>
  );
}

// ─── DRAG & DROP ──────────────────────────────────────────────────────────────
// Usiamo dataTransfer per codificare tipo + dati così step e task non si
// interferiscono anche quando i loro container sono annidati.
const DRAG_STEP = "application/x-wt-step";
const DRAG_TASK = "application/x-wt-task";

// ─── MPF PARSER ───────────────────────────────────────────────────────────────
function parseMpfFile(filename, content) {
  const lines = content.split(/\r?\n/);
  const get = (label) => { const l = lines.find(l => l.includes(label)); return l ? l.replace(/.*:\s*/, "").trim() : ""; };
  const opLine = lines.find(l => /N\d+;/.test(l) && !l.includes("DIAMETER") && !l.includes("TOOL COMMENT") && !l.includes("CIMATRON") && !l.includes("DOCUMENTO") && !l.includes("UTENTE") && !l.includes("POST") && !l.includes("REVISIONE") && !l.includes("DATA") && !l.includes("N.UT") && l.includes(";") && l.replace(/N\d+;\s*/,"").trim().length > 3);
  const tipoOp = opLine ? opLine.replace(/N\d+;\s*/,"").trim() : "";
  const toolLine = lines.find(l => l.includes("TOOL COMMENT:"));
  const utensile = toolLine ? toolLine.replace(/.*TOOL COMMENT:\s*/,"").trim() : "";
  const diaLine = lines.find(l => l.includes("DIAMETER:"));
  const diametro = diaLine ? diaLine.replace(/.*DIAMETER:\s*/,"").replace(/CORNER.*/,"").trim() : "";
  const dataPost = get("DATA ESECUZIONE POST");
  // Rileva IPM dal nome file o dall'utensile RENISHAW
  const isIPM = /[_\-]IPM[_\-]/i.test(filename) || utensile.toUpperCase().includes("RENISHAW");
  const tipoGruppo = isIPM ? "ipm" : "fresatura";
  // Numero programma: gestisce sia _IPM_01 che _01
  const baseName = filename.replace(/\.MPF$/i, "");
  const tokens = baseName.split("_");
  const ipmIdx = tokens.findIndex(t => t.toUpperCase() === "IPM");
  const numPgm = ipmIdx >= 0 && tokens[ipmIdx+1] ? tokens[ipmIdx+1] : tokens[tokens.length-1];
  const fase = tokens.length >= 3 ? tokens[tokens.length - (isIPM ? 3 : 2)] : "";
  return { numPgm, fase, tipoOp, utensile, diametro, dataPost, filename, tipoGruppo };
}

// ─── FRESATURA PANEL ──────────────────────────────────────────────────────────
const OPERATORI = ["I.Dodon","Operatore 2","Operatore 3"];

// Stato successivo in sequenza: click singolo avanza lo stato
const STATO_NEXT = { da_fare:"in_macchina", in_macchina:"completato", completato:"da_fare" };
const STATO_CFG = {
  da_fare:     { label:"Da fare",     short:"Da fare",    color:T.textMuted, bg:T.surface2,  border:T.border,    dot:"○" },
  in_macchina: { label:"In macchina", short:"In macchina",color:"#1D5FAD",   bg:"#dbeafe",   border:"#1D5FAD",   dot:"⚙" },
  completato:  { label:"Completato",  short:"Fatto",      color:"#166534",   bg:"#dcfce7",   border:"#166534",   dot:"✓" },
};

function ProgramRow({ pgm, gruppo, onStato, onOperatore, onTempo, onRemove }) {
  const [expanded,   setExpanded]   = useState(false);
  const [editTempo,  setEditTempo]  = useState(pgm.tempoStimato || "");
  const [editingT,   setEditingT]   = useState(false);
  const sc = STATO_CFG[pgm.stato] || STATO_CFG.da_fare;

  // Pulisce il tipoOp: rimuove " - NESSUN TESTO" e testo ridondante
  const opClean = pgm.tipoOp
    .replace(/[-–]\s*NESSUN TESTO\s*/gi, "")
    .replace(/MISURAZIONE NEL PROCESSO[-–]?/gi, "MISURA ")
    .trim();

  return (
    <div style={{
      borderBottom: `1px solid ${T.border}`,
      background: pgm.stato==="completato" ? "#f0fdf4" : pgm.stato==="in_macchina" ? "#eff6ff" : T.surface,
      opacity: pgm.stato==="completato" ? 0.72 : 1,
      transition: "background 0.15s",
    }}>
      {/* RIGA COMPATTA */}
      <div style={{display:"flex", alignItems:"center", gap:0, padding:"0", minHeight:38}}>

        {/* Badge stato — click avanza sequenza */}
        <div
          onClick={() => onStato(STATO_NEXT[pgm.stato])}
          title={`Click → ${STATO_CFG[STATO_NEXT[pgm.stato]].label}`}
          style={{
            flexShrink:0, width:110, display:"flex", alignItems:"center", justifyContent:"center",
            gap:5, padding:"0 10px", height:"100%", cursor:"pointer",
            borderRight:`1px solid ${T.border}`,
            background: sc.bg, color: sc.color,
            fontWeight:700, fontSize:12,
            userSelect:"none", transition:"all 0.12s",
            alignSelf:"stretch",
          }}
        >
          <span style={{fontSize:14}}>{sc.dot}</span>
          {sc.short}
        </div>

        {/* PGM numero */}
        <div style={{flexShrink:0, width:52, textAlign:"center", borderRight:`1px solid ${T.border}`, alignSelf:"stretch", display:"flex", alignItems:"center", justifyContent:"center"}}>
          <span style={{fontSize:13, fontWeight:800, color:gruppo.color, fontFamily:"monospace"}}>{pgm.numPgm}</span>
        </div>

        {/* Utensile */}
        <div style={{flexShrink:0, width:140, borderRight:`1px solid ${T.border}`, padding:"0 10px", alignSelf:"stretch", display:"flex", flexDirection:"column", justifyContent:"center"}}>
          <span style={{fontSize:12, fontWeight:700, color:T.text, fontFamily:"monospace", lineHeight:1.2}}>{pgm.utensile||"—"}</span>
          {pgm.diametro && <span style={{fontSize:10, color:T.textMuted}}>Ø {pgm.diametro}</span>}
        </div>

        {/* Tipo operazione */}
        <div style={{flex:1, padding:"0 10px", alignSelf:"stretch", display:"flex", alignItems:"center", overflow:"hidden"}}>
          <span style={{fontSize:12, color:T.textSub, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis"}}>{opClean||"—"}</span>
        </div>

        {/* Timestamp compatto se in macchina o completato */}
        {(pgm.tempoInizio || pgm.tempoFine) && (
          <div style={{flexShrink:0, padding:"0 8px", borderLeft:`1px solid ${T.border}`, alignSelf:"stretch", display:"flex", flexDirection:"column", justifyContent:"center"}}>
            {pgm.tempoInizio && <span style={{fontSize:10, color:"#1D5FAD", fontFamily:"monospace", whiteSpace:"nowrap"}}>▶ {pgm.tempoInizio}</span>}
            {pgm.tempoFine   && <span style={{fontSize:10, color:"#166534", fontFamily:"monospace", whiteSpace:"nowrap"}}>■ {pgm.tempoFine}</span>}
          </div>
        )}

        {/* Espandi */}
        <div
          onClick={() => setExpanded(v=>!v)}
          style={{flexShrink:0, width:32, borderLeft:`1px solid ${T.border}`, alignSelf:"stretch", display:"flex", alignItems:"center", justifyContent:"center", cursor:"pointer", color:T.textMuted, fontSize:11, userSelect:"none"}}
        >{expanded ? "▲" : "▼"}</div>
      </div>

      {/* DETTAGLI ESPANSI */}
      {expanded && (
        <div style={{padding:"12px 14px", background:T.surface2, borderTop:`1px solid ${T.border}`, display:"flex", flexWrap:"wrap", gap:16, alignItems:"flex-start"}}>
          {/* Operatore */}
          <div>
            <div style={{fontSize:10, color:T.textMuted, fontWeight:700, letterSpacing:"0.06em", marginBottom:4}}>OPERATORE</div>
            <select value={pgm.operatore||""} onChange={e=>onOperatore(e.target.value)}
              style={{background:T.surface, border:`1px solid ${T.border}`, borderRadius:6, color:pgm.operatore?T.text:T.textMuted, fontSize:12, padding:"4px 10px", outline:"none", cursor:"pointer"}}>
              <option value="">— Seleziona</option>
              {OPERATORI.map(o=><option key={o} value={o}>{o}</option>)}
            </select>
          </div>

          {/* Tempo stimato */}
          <div>
            <div style={{fontSize:10, color:T.textMuted, fontWeight:700, letterSpacing:"0.06em", marginBottom:4}}>TEMPO STIMATO</div>
            {editingT ? (
              <div style={{display:"flex", gap:5}}>
                <input value={editTempo} onChange={e=>setEditTempo(e.target.value)} placeholder="es. 2h30m" autoFocus
                  style={{width:90, background:T.surface, border:`1.5px solid #1D5FAD44`, borderRadius:6, padding:"4px 8px", color:T.text, fontSize:12, outline:"none"}}
                  onKeyDown={e=>{if(e.key==="Enter"){onTempo(editTempo);setEditingT(false);}if(e.key==="Escape")setEditingT(false);}}/>
                <button onClick={()=>{onTempo(editTempo);setEditingT(false);}} style={{background:"#1D5FAD",border:"none",borderRadius:5,color:"#fff",fontSize:11,fontWeight:700,padding:"4px 9px",cursor:"pointer"}}>OK</button>
              </div>
            ) : (
              <button onClick={()=>setEditingT(true)}
                style={{background:"none", border:`1px dashed ${T.border}`, borderRadius:6, color:pgm.tempoStimato?T.text:T.textMuted, fontSize:12, padding:"4px 10px", cursor:"pointer"}}>
                ⏱ {pgm.tempoStimato||"Aggiungi"}
              </button>
            )}
          </div>

          {/* Data post */}
          {pgm.dataPost && (
            <div>
              <div style={{fontSize:10, color:T.textMuted, fontWeight:700, letterSpacing:"0.06em", marginBottom:4}}>DATA POST</div>
              <div style={{fontSize:12, color:T.textSub, fontFamily:"monospace"}}>{pgm.dataPost}</div>
            </div>
          )}

          {/* File */}
          <div>
            <div style={{fontSize:10, color:T.textMuted, fontWeight:700, letterSpacing:"0.06em", marginBottom:4}}>FILE</div>
            <div style={{fontSize:11, color:T.textMuted, fontFamily:"monospace"}}>{pgm.filename}</div>
          </div>

          {/* Stato completo (per tornare indietro se serve) */}
          <div style={{marginLeft:"auto"}}>
            <div style={{fontSize:10, color:T.textMuted, fontWeight:700, letterSpacing:"0.06em", marginBottom:4}}>STATO</div>
            <div style={{display:"flex", gap:4}}>
              {Object.entries(STATO_CFG).map(([key,s])=>(
                <button key={key} onClick={()=>onStato(key)} style={{
                  background:pgm.stato===key?s.bg:"transparent",
                  border:`1.5px solid ${pgm.stato===key?s.border:T.border}`,
                  borderRadius:6, color:pgm.stato===key?s.color:T.textMuted,
                  fontSize:11, fontWeight:700, padding:"3px 10px", cursor:"pointer",
                }}>{s.dot} {s.label}</button>
              ))}
              <button onClick={onRemove} style={{marginLeft:8, background:"none", border:`1px solid ${T.red}44`, borderRadius:6, color:T.red, fontSize:11, padding:"3px 8px", cursor:"pointer"}}>🗑 Rimuovi</button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}

function FresaturaPanel({ task, onUpdateTask }) {
  const fileInputRef = useRef(null);
  const programs = Array.isArray(task.programs) ? task.programs : [];
  const [expanded,        setExpanded]        = useState(false);
  const [collapsedGroups, setCollapsedGroups] = useState({ipm:true, fresatura:true});

  const ipmPrograms  = programs.filter(p => p.tipoGruppo === "ipm");
  const fresPrograms = programs.filter(p => p.tipoGruppo !== "ipm");
  const doneTotal    = programs.filter(p => p.stato === "completato").length;
  const inMacchina   = programs.filter(p => p.stato === "in_macchina").length;
  const total        = programs.length;
  const allDone      = total > 0 && doneTotal === total;

  function updatePrograms(newPrograms) {
    const allComplete = newPrograms.length > 0 && newPrograms.every(p => p.stato === "completato");
    onUpdateTask({ ...task, programs: newPrograms, done: allComplete, doneAt: allComplete ? new Date().toISOString().slice(0,10) : task.doneAt });
  }

  async function handleFileUpload(e) {
    const files = Array.from(e.target.files);
    const parsed = [];
    for (const file of files) {
      const text = await file.text();
      const info = parseMpfFile(file.name, text);
      if (!programs.find(p => p.filename === info.filename)) {
        parsed.push({ id:uid(), ...info, stato:"da_fare", operatore:"", tempoStimato:"", tempoInizio:null, tempoFine:null });
      }
    }
    if (parsed.length > 0) {
      const all = [...programs, ...parsed];
      all.sort((a,b) => {
        if (a.tipoGruppo !== b.tipoGruppo) return a.tipoGruppo==="ipm" ? -1 : 1;
        return a.numPgm.localeCompare(b.numPgm, undefined, {numeric:true});
      });
      updatePrograms(all);
    }
    e.target.value = "";
  }

  function updatePgm(id, patch) {
    updatePrograms(programs.map(p => {
      if (p.id !== id) return p;
      const next = {...p, ...patch};
      // timestamp automatici
      if (patch.stato === "in_macchina" && !p.tempoInizio) next.tempoInizio = nowStr();
      if (patch.stato === "completato")  next.tempoFine = nowStr();
      return next;
    }));
  }

  function removeProgram(id) { updatePrograms(programs.filter(p => p.id!==id)); }
  function toggleGroup(key)  { setCollapsedGroups(g => ({...g,[key]:!g[key]})); }

  const gruppi = [
    { key:"ipm",      label:"Tastatura (IPM)", icon:"📏", color:"#8B2FC9", bgColor:"#F3E8FF", list:ipmPrograms },
    { key:"fresatura",label:"Fresatura",        icon:"⚙️", color:"#1D5FAD", bgColor:"#E8F0FA", list:fresPrograms },
  ].filter(g => g.list.length > 0);

  return (
    <div style={{marginTop:8, background:T.surface, border:"1.5px solid #1D5FAD33", borderRadius:10, overflow:"hidden"}}>

      {/* Header principale */}
      <div onClick={()=>setExpanded(v=>!v)} style={{display:"flex",alignItems:"center",gap:10,padding:"10px 14px",cursor:"pointer",background:"#E8F0FA",userSelect:"none"}}>
        <span style={{fontSize:15}}>⚙️</span>
        <span style={{fontSize:13,fontWeight:800,color:"#1D5FAD",flex:1}}>PROGRAMMI FRESATURA</span>
        {inMacchina > 0 && (
          <span style={{fontSize:11,fontWeight:700,color:"#1D5FAD",background:"#fff",padding:"2px 9px",borderRadius:20,border:"1px solid #1D5FAD44"}}>⚙ {inMacchina} in macchina</span>
        )}
        {total > 0 && (
          <span style={{fontSize:12,fontWeight:700,color:allDone?"#166534":"#1D5FAD",background:allDone?"#dcfce7":"#fff",padding:"2px 10px",borderRadius:20,border:`1px solid ${allDone?"#166534":"#1D5FAD"}44`}}>
            {doneTotal}/{total} {allDone?"✓":"completati"}
          </span>
        )}
        <span style={{fontSize:11,color:"#1D5FAD",fontWeight:700}}>{expanded?"▲":"▼"}</span>
      </div>

      {expanded && (
        <div>
          {/* Upload */}
          <div style={{display:"flex",gap:10,alignItems:"center",padding:"10px 14px",borderBottom:`1px solid ${T.border}`, background:T.surface}}>
            <input ref={fileInputRef} type="file" accept=".mpf,.MPF" multiple style={{display:"none"}} onChange={handleFileUpload}/>
            <button onClick={()=>fileInputRef.current.click()} style={{background:"#1D5FAD",border:"none",borderRadius:7,color:"#fff",fontWeight:700,fontSize:13,padding:"7px 14px",cursor:"pointer"}}>📂 Carica .mpf</button>
            {total > 0 && <span style={{fontSize:12,color:T.textMuted}}>
              {ipmPrograms.length>0 && `📏 ${ipmPrograms.length} IPM · `}⚙️ {fresPrograms.length} fresatura
            </span>}
          </div>

          {total === 0 && (
            <div style={{textAlign:"center",padding:"24px",color:T.textMuted,fontSize:13,border:`2px dashed ${T.border}`,borderRadius:8,margin:12}}>
              Nessun programma caricato · Clicca "Carica .mpf" per iniziare
            </div>
          )}

          {/* Colonne header — visibile solo se ci sono programmi */}
          {total > 0 && (
            <div style={{display:"flex",alignItems:"center",background:T.surface2,borderBottom:`1px solid ${T.border}`,fontSize:10,fontWeight:700,color:T.textMuted,letterSpacing:"0.07em"}}>
              <div style={{width:110,padding:"5px 10px",borderRight:`1px solid ${T.border}`}}>STATO</div>
              <div style={{width:52,textAlign:"center",padding:"5px 0",borderRight:`1px solid ${T.border}`}}>PGM</div>
              <div style={{width:140,padding:"5px 10px",borderRight:`1px solid ${T.border}`}}>UTENSILE</div>
              <div style={{flex:1,padding:"5px 10px"}}>OPERAZIONE</div>
            </div>
          )}

          {/* Gruppi */}
          {gruppi.map(gruppo => (
            <div key={gruppo.key}>
              {/* Header gruppo — solo se ci sono entrambi i gruppi */}
              {gruppi.length > 1 && (
                <div onClick={()=>toggleGroup(gruppo.key)} style={{display:"flex",alignItems:"center",gap:8,padding:"6px 14px",background:gruppo.bgColor,cursor:"pointer",userSelect:"none",borderBottom:`1px solid ${T.border}`}}>
                  <span style={{fontSize:12}}>{gruppo.icon}</span>
                  <span style={{fontSize:11,fontWeight:800,color:gruppo.color,flex:1,letterSpacing:"0.06em"}}>{gruppo.label.toUpperCase()}</span>
                  <span style={{fontSize:11,color:gruppo.color,fontWeight:700,background:"rgba(255,255,255,0.6)",padding:"1px 8px",borderRadius:10}}>
                    {gruppo.list.filter(p=>p.stato==="completato").length}/{gruppo.list.length}
                  </span>
                  <span style={{fontSize:10,color:gruppo.color}}>{collapsedGroups[gruppo.key]?"▼":"▲"}</span>
                </div>
              )}
              {(gruppi.length === 1 || !collapsedGroups[gruppo.key]) && gruppo.list.map(pgm => (
                <ProgramRow
                  key={pgm.id}
                  pgm={pgm}
                  gruppo={gruppo}
                  onStato={stato => updatePgm(pgm.id, {stato})}
                  onOperatore={operatore => updatePgm(pgm.id, {operatore})}
                  onTempo={tempoStimato => updatePgm(pgm.id, {tempoStimato})}
                  onRemove={() => removeProgram(pgm.id)}
                />
              ))}
            </div>
          ))}
        </div>
      )}
    </div>
  );
}

// ─── TASK ITEM ────────────────────────────────────────────────────────────────
function TaskItem({task, idx, stepId, onToggle, onUpdateTask, onDelete, isNext, onReorderTask}){
  const [hovered,    setHovered]    = useState(false);
  const [dragOver,   setDragOver]   = useState(false);
  const [addingNote, setAddingNote] = useState(false);
  const [newNote,    setNewNote]    = useState("");
  const [editingNote,setEditingNote]= useState(null);
  const [editVal,    setEditVal]    = useState("");
  const noteInputRef = useRef(null);

  // Normalizza una volta sola: se esiste task.notes usa quello,
  // altrimenti converte il vecchio task.note in array al primo salvataggio.
  // NON generiamo uid() qui dentro per evitare id diversi ad ogni render.
  const notes = Array.isArray(task.notes) ? task.notes : [];

  function saveNewNote() {
    if (!newNote.trim()) { setAddingNote(false); return; }
    // Se c'è ancora il vecchio campo note stringa, migralo insieme
    const legacy = (!Array.isArray(task.notes) && task.note)
      ? [{ id: `legacy_${task.id}`, text: task.note, createdAt: "" }]
      : [];
    const updated = { ...task, notes: [...legacy, ...notes, { id: uid(), text: newNote.trim(), createdAt: nowStr() }], note: "" };
    onUpdateTask(updated);
    setNewNote(""); setAddingNote(false);
  }
  function saveEditNote(noteId) {
    const updated = { ...task, notes: notes.map(n => n.id===noteId ? {...n, text: editVal} : n), note: "" };
    onUpdateTask(updated);
    setEditingNote(null);
  }
  function deleteNote(noteId) {
    const updated = { ...task, notes: notes.filter(n => n.id!==noteId), note: "" };
    onUpdateTask(updated);
  }

  // Note da mostrare: array notes + eventuale legacy note stringa non ancora migrata
  const displayNotes = notes.length > 0
    ? notes
    : (task.note ? [{ id: `legacy_${task.id}`, text: task.note, createdAt: "" }] : []);

  useEffect(() => { if (addingNote) noteInputRef.current?.focus(); }, [addingNote]);

  return (
    <div
      draggable
      onDragStart={e => {
        e.stopPropagation();
        e.dataTransfer.effectAllowed = "move";
        e.dataTransfer.setData(DRAG_TASK, JSON.stringify({ stepId, idx }));
        setTimeout(() => e.target.style.opacity = "0.4", 0);
      }}
      onDragEnd={e => { e.target.style.opacity = "1"; setDragOver(false); }}
      onDragOver={e => { if (e.dataTransfer.types.includes(DRAG_TASK)) { e.preventDefault(); e.stopPropagation(); setDragOver(true); } }}
      onDragLeave={() => setDragOver(false)}
      onDrop={e => {
        if (!e.dataTransfer.types.includes(DRAG_TASK)) return;
        e.preventDefault(); e.stopPropagation(); setDragOver(false);
        const { stepId: fromStep, idx: fromIdx } = JSON.parse(e.dataTransfer.getData(DRAG_TASK));
        if (fromStep === stepId && fromIdx !== idx) onReorderTask(stepId, fromIdx, idx);
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        display:"flex", flexDirection:"column",
        background: dragOver ? T.accentBg : isNext ? T.accentBg : hovered ? T.surface2 : "transparent",
        border: dragOver ? `2px solid ${T.accent}` : isNext ? `1.5px solid ${T.accent}44` : `1px solid ${hovered ? T.border : "transparent"}`,
        borderRadius:8, padding:"8px 10px", marginBottom:4, cursor:"grab", transition:"all 0.12s",
      }}
    >
      {/* Riga principale */}
      <div style={{display:"flex", alignItems:"center", gap:10}}>
        <span style={{color:T.borderStrong, fontSize:13, cursor:"grab", opacity:hovered?0.8:0.25, flexShrink:0, userSelect:"none"}}>⣿</span>
        {isNext && <span style={{fontSize:13}}>📍</span>}
        <div onClick={()=>onToggle(task.id)}
          style={{width:20,height:20,borderRadius:6,border:task.done?"none":`2px solid ${T.borderStrong}`,background:task.done?"#1A7A4A":"transparent",cursor:"pointer",flexShrink:0,display:"flex",alignItems:"center",justifyContent:"center",transition:"all 0.2s"}}>
          {task.done && <span style={{color:"#fff",fontSize:13,fontWeight:700}}>✓</span>}
        </div>
        <span style={{fontSize:15,color:task.done?T.textMuted:T.text,textDecoration:task.done?"line-through":"none",flex:1,fontWeight:task.done?400:500}}>
          {task.text}
        </span>
        {task.done && task.doneAt && <span style={{fontSize:12,color:T.textMuted,fontFamily:"monospace"}}>{task.doneAt}</span>}
        <div style={{display:"flex",gap:4,opacity:hovered?1:0,transition:"opacity 0.15s"}}>
          <button onClick={()=>setAddingNote(true)}
            style={{background:"none",border:`1px solid ${T.border}`,borderRadius:6,cursor:"pointer",color:displayNotes.length>0?T.accent:T.textMuted,fontSize:12,padding:"2px 7px"}}
            title={`${displayNotes.length} commento/i · aggiungi`}>
            💬{displayNotes.length > 0 ? ` ${displayNotes.length}` : ""}
          </button>
          <button onClick={()=>onDelete(task.id)}
            style={{background:"none",border:`1px solid ${T.border}`,borderRadius:6,cursor:"pointer",color:T.red,fontSize:12,padding:"2px 7px"}} title="Elimina task">🗑️</button>
        </div>
      </div>

      {/* Note esistenti */}
      {displayNotes.length > 0 && (
        <div style={{marginTop:6, marginLeft:44, display:"flex", flexDirection:"column", gap:4}}>
          {displayNotes.map(note => (
            <div key={note.id} style={{background:T.accentBg, borderRadius:6, borderLeft:`3px solid ${T.accent}`, padding:"5px 10px", display:"flex", alignItems:"flex-start", gap:8}}>
              {editingNote === note.id ? (
                <>
                  <input value={editVal} onChange={e=>setEditVal(e.target.value)} autoFocus
                    style={{flex:1,background:T.surface,border:`1.5px solid ${T.accent}`,borderRadius:6,padding:"4px 8px",color:T.text,fontSize:13,outline:"none"}}
                    onKeyDown={e=>{if(e.key==="Enter")saveEditNote(note.id);if(e.key==="Escape")setEditingNote(null);}}/>
                  <button onClick={()=>saveEditNote(note.id)} style={{background:T.accent,border:"none",borderRadius:5,color:"#fff",fontSize:12,fontWeight:700,padding:"4px 10px",cursor:"pointer",flexShrink:0}}>OK</button>
                  <button onClick={()=>setEditingNote(null)} style={{background:"none",border:`1px solid ${T.border}`,borderRadius:5,color:T.textSub,fontSize:12,padding:"4px 8px",cursor:"pointer",flexShrink:0}}>✕</button>
                </>
              ) : (
                <>
                  <div style={{flex:1}}>
                    <span style={{fontSize:13,color:T.accent,fontStyle:"italic"}}>"{note.text}"</span>
                    {note.createdAt && <span style={{fontSize:11,color:T.textMuted,marginLeft:8}}>{note.createdAt}</span>}
                  </div>
                  <button onClick={()=>{setEditingNote(note.id);setEditVal(note.text);}}
                    style={{background:"none",border:"none",cursor:"pointer",color:T.textMuted,fontSize:12,padding:"0 3px",opacity:0.7}} title="Modifica">✏️</button>
                  <button onClick={()=>deleteNote(note.id)}
                    style={{background:"none",border:"none",cursor:"pointer",color:T.red,fontSize:12,padding:"0 3px",opacity:0.7}} title="Elimina commento">×</button>
                </>
              )}
            </div>
          ))}
        </div>
      )}

      {/* Input nuovo commento */}
      {addingNote && (
        <div style={{marginTop:6, marginLeft:44, display:"flex", gap:8}}>
          <input ref={noteInputRef} value={newNote} onChange={e=>setNewNote(e.target.value)}
            placeholder="Aggiungi commento..."
            style={{flex:1,background:T.surface2,border:`1.5px solid ${T.accent}44`,borderRadius:8,padding:"7px 10px",color:T.text,fontSize:13,outline:"none"}}
            onKeyDown={e=>{if(e.key==="Enter")saveNewNote();if(e.key==="Escape"){setAddingNote(false);setNewNote("");}}}/>
          <button onClick={saveNewNote} style={{background:T.accent,border:"none",borderRadius:8,color:"#fff",fontSize:13,fontWeight:700,padding:"7px 14px",cursor:"pointer",flexShrink:0}}>+ Aggiungi</button>
          <button onClick={()=>{setAddingNote(false);setNewNote("");}} style={{background:"none",border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:13,padding:"7px 10px",cursor:"pointer"}}>✕</button>
        </div>
      )}

      {/* Pannello fresatura — attivo quando il task si chiama "Fresatura" */}
      {task.text.trim().toLowerCase()==="fresatura" && (
        <div style={{marginTop:8}}>
          <FresaturaPanel task={task} onUpdateTask={onUpdateTask}/>
        </div>
      )}
    </div>
  );
}

// ─── STEP SECTION ─────────────────────────────────────────────────────────────
function StepSection({step, stepIdx, nextTaskId, onToggle, onUpdateTask, onAddTask, onDeleteTask, onReorderTask, onReorderStep, onDeleteStep, projectColor}){
  const [collapsed, setCollapsed] = useState(false);
  const [adding, setAdding]       = useState(false);
  const [newTask, setNewTask]     = useState("");
  const [hovered, setHovered]     = useState(false);
  const [stepDragOver, setStepDragOver] = useState(false);
  const done = step.tasks.filter(t=>t.done).length;

  // Handle del grip della fase (solo da quella strip)
  const handleStepGripDragStart = e => {
    e.stopPropagation();
    e.dataTransfer.effectAllowed = "move";
    e.dataTransfer.setData(DRAG_STEP, String(stepIdx));
    setTimeout(() => {
      // trova il parent step div e abbassa opacità
      const el = e.target.closest("[data-stepcontainer]");
      if (el) el.style.opacity = "0.4";
    }, 0);
  };

  return (
    <div
      data-stepcontainer
      onDragOver={e => {
        // Accetta solo DRAG_STEP a questo livello
        if (e.dataTransfer.types.includes(DRAG_STEP)) {
          e.preventDefault();
          setStepDragOver(true);
        }
        // DRAG_TASK viene gestito dai TaskItem figli: non fare nulla qui
      }}
      onDragLeave={e => {
        // Ignora se il leave è verso un figlio
        if (e.currentTarget.contains(e.relatedTarget)) return;
        setStepDragOver(false);
      }}
      onDrop={e => {
        if (!e.dataTransfer.types.includes(DRAG_STEP)) return;
        e.preventDefault();
        setStepDragOver(false);
        const fromIdx = parseInt(e.dataTransfer.getData(DRAG_STEP));
        if (!isNaN(fromIdx) && fromIdx !== stepIdx) {
          onReorderStep(fromIdx, stepIdx);
        }
        // Ripristina opacità
        document.querySelectorAll("[data-stepcontainer]").forEach(el => el.style.opacity = "1");
      }}
      onDragEnd={() => {
        document.querySelectorAll("[data-stepcontainer]").forEach(el => el.style.opacity = "1");
        setStepDragOver(false);
      }}
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{
        marginBottom:12,
        background: T.surface,
        border: stepDragOver ? `2px solid ${projectColor}` : `1.5px solid ${T.border}`,
        borderLeft:`4px solid ${projectColor}`,
        borderRadius:10, padding:"12px 16px",
        transition:"box-shadow 0.15s, border 0.12s",
        boxShadow: hovered ? "0 2px 12px rgba(0,0,0,0.08)" : "none",
      }}
    >
      <div style={{display:"flex", alignItems:"center", gap:8, marginBottom: collapsed ? 0 : 10}}>
        {/* Grip solo per le fasi */}
        <span
          draggable
          onDragStart={handleStepGripDragStart}
          style={{color:T.borderStrong,fontSize:14,cursor:"grab",opacity:hovered?0.8:0.25,flexShrink:0,transition:"opacity 0.15s",userSelect:"none"}}
          title="Trascina per spostare la fase"
        >⣿</span>
        <span onClick={()=>setCollapsed(!collapsed)} style={{color:T.textMuted,fontSize:12,cursor:"pointer",userSelect:"none"}}>{collapsed?"▶":"▼"}</span>
        <span style={{fontSize:15,fontWeight:700,color:T.text,flex:1,cursor:"pointer"}} onClick={()=>setCollapsed(!collapsed)}>{step.title}</span>
        <span style={{fontSize:13,color:T.textMuted,fontWeight:500}}>{done}/{step.tasks.length} completati</span>
        <button onClick={()=>onDeleteStep(step.id)} style={{background:"none",border:`1px solid ${T.border}`,borderRadius:6,cursor:"pointer",color:T.red,fontSize:12,padding:"2px 8px",opacity:hovered?1:0,transition:"opacity 0.15s"}} title="Elimina fase">🗑️</button>
      </div>

      {!collapsed && (
        <>
          {step.tasks.map((task, tIdx) => (
            <TaskItem
              key={task.id} task={task} idx={tIdx} stepId={step.id}
              onToggle={onToggle}
              onUpdateTask={onUpdateTask}
              onDelete={tid => onDeleteTask(step.id, tid)}
              isNext={task.id === nextTaskId}
              onReorderTask={onReorderTask}
            />
          ))}
          {adding ? (
            <div style={{display:"flex",gap:8,marginTop:8,marginLeft:22}}>
              <input autoFocus value={newTask} onChange={e=>setNewTask(e.target.value)} placeholder="Descrivi il nuovo task..."
                style={{flex:1,background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:8,padding:"8px 12px",color:T.text,fontSize:14,outline:"none"}}
                onKeyDown={e=>{if(e.key==="Enter"&&newTask.trim()){onAddTask(step.id,newTask.trim());setNewTask("");setAdding(false);}if(e.key==="Escape"){setAdding(false);setNewTask("");}}}/>
              <button onClick={()=>{if(newTask.trim())onAddTask(step.id,newTask.trim());setAdding(false);setNewTask("");}}
                style={{background:projectColor,border:"none",borderRadius:8,color:"#fff",fontSize:14,fontWeight:700,padding:"8px 16px",cursor:"pointer"}}>Aggiungi</button>
            </div>
          ) : (
            <button onClick={()=>setAdding(true)} style={{background:"none",border:`1.5px dashed ${T.border}`,borderRadius:8,color:T.textMuted,fontSize:13,padding:"7px 16px",cursor:"pointer",width:"100%",marginTop:6,fontWeight:500}}>+ Aggiungi task</button>
          )}
        </>
      )}
    </div>
  );
}

// ─── SAVE AS TEMPLATE MODAL ───────────────────────────────────────────────────
function SaveAsTemplateModal({ project, templates, onSave, onClose }) {
  const [mode, setMode]         = useState("new");        // "new" | "replace"
  const [tmplName, setTmplName] = useState(project.name);
  const [tmplDesc, setTmplDesc] = useState(project.description || "");
  const [tmplIcon, setTmplIcon] = useState("🚀");
  const [tmplColor, setTmplColor] = useState(project.color);
  const [replaceId, setReplaceId] = useState(templates[0]?.id || null);
  const [showIconPicker, setShowIconPicker] = useState(false);
  const [saved, setSaved]       = useState(false);

  // Converte le fasi del progetto in struttura template (senza stato done/note)
  function buildSteps() {
    return project.steps.map(s => ({
      id: uid(),
      title: s.title,
      tasks: s.tasks.map(t => ({ id: uid(), text: t.text }))
    }));
  }

  function handleSave() {
    const steps = buildSteps();
    if (mode === "new") {
      onSave({
        id:   uid(),
        name: tmplName.trim() || project.name,
        description: tmplDesc.trim(),
        icon:  tmplIcon,
        color: tmplColor,
        steps,
      });
    } else {
      const existing = templates.find(t => t.id === replaceId);
      if (!existing) return;
      onSave({
        ...existing,
        name:  tmplName.trim() || existing.name,
        description: tmplDesc.trim(),
        icon:  tmplIcon,
        color: tmplColor,
        steps,
      });
    }
    setSaved(true);
    setTimeout(onClose, 1200);
  }

  const inputStyle = {
    width:"100%", background:T.surface2, border:`1.5px solid ${T.border}`,
    borderRadius:8, padding:"9px 12px", color:T.text, fontSize:14, outline:"none"
  };

  return (
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:150}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,padding:30,width:500,maxWidth:"92vw",maxHeight:"90vh",overflowY:"auto",boxShadow:"0 12px 48px rgba(0,0,0,0.18)"}}>

        {saved ? (
          <div style={{textAlign:"center",padding:"30px 0"}}>
            <div style={{fontSize:44,marginBottom:12}}>✅</div>
            <div style={{fontSize:18,fontWeight:800,color:T.green}}>Template salvato!</div>
          </div>
        ) : (
          <>
            <div style={{fontSize:18,fontWeight:800,color:T.text,marginBottom:6}}>💾 Salva come Template</div>
            <div style={{fontSize:13,color:T.textSub,marginBottom:22}}>
              Le fasi e i task vengono copiati nel template. I segni di spunta e le note vengono rimossi.
            </div>

            {/* Modalità */}
            <div style={{display:"flex",gap:8,marginBottom:22}}>
              <button
                onClick={()=>setMode("new")}
                style={{flex:1,padding:"10px",borderRadius:8,border:`2px solid ${mode==="new"?T.accent:T.border}`,background:mode==="new"?T.accentBg:T.surface2,color:mode==="new"?T.accent:T.textSub,fontWeight:700,fontSize:14,cursor:"pointer"}}
              >✦ Nuovo template</button>
              <button
                onClick={()=>setMode("replace")}
                disabled={templates.length===0}
                style={{flex:1,padding:"10px",borderRadius:8,border:`2px solid ${mode==="replace"?T.accent:T.border}`,background:mode==="replace"?T.accentBg:T.surface2,color:mode==="replace"?T.accent:templates.length===0?T.textMuted:T.textSub,fontWeight:700,fontSize:14,cursor:templates.length===0?"not-allowed":"pointer",opacity:templates.length===0?0.5:1}}
              >↺ Sostituisci esistente</button>
            </div>

            {/* Sostituisci: selezione template */}
            {mode==="replace" && templates.length>0 && (
              <div style={{marginBottom:18}}>
                <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:8}}>SCEGLI IL TEMPLATE DA SOSTITUIRE</label>
                <div style={{display:"flex",flexDirection:"column",gap:6}}>
                  {templates.map(t=>(
                    <div key={t.id} onClick={()=>setReplaceId(t.id)}
                      style={{display:"flex",alignItems:"center",gap:12,padding:"10px 14px",borderRadius:8,border:`2px solid ${replaceId===t.id?t.color:T.border}`,background:replaceId===t.id?t.color+"12":T.surface2,cursor:"pointer",transition:"all 0.15s"}}>
                      <span style={{fontSize:20}}>{t.icon}</span>
                      <div style={{flex:1}}>
                        <div style={{fontSize:14,fontWeight:700,color:T.text}}>{t.name}</div>
                        <div style={{fontSize:12,color:T.textMuted}}>{t.steps.length} fasi · {t.steps.reduce((a,s)=>a+s.tasks.length,0)} task</div>
                      </div>
                      {replaceId===t.id && <span style={{color:t.color,fontWeight:700,fontSize:18}}>✓</span>}
                    </div>
                  ))}
                </div>
              </div>
            )}

            {/* Nome e descrizione */}
            <div style={{marginBottom:14}}>
              <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:6}}>NOME TEMPLATE</label>
              <input value={tmplName} onChange={e=>setTmplName(e.target.value)} style={inputStyle}/>
            </div>
            <div style={{marginBottom:18}}>
              <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:6}}>DESCRIZIONE</label>
              <input value={tmplDesc} onChange={e=>setTmplDesc(e.target.value)} style={inputStyle} placeholder="Breve descrizione..."/>
            </div>

            {/* Icona + colore */}
            <div style={{display:"flex",gap:28,marginBottom:22,alignItems:"flex-start"}}>
              <div>
                <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:8}}>ICONA</label>
                <div style={{position:"relative"}}>
                  <button onClick={()=>setShowIconPicker(v=>!v)} style={{background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:10,padding:"8px 16px",cursor:"pointer",fontSize:22,lineHeight:1}}>{tmplIcon}</button>
                  {showIconPicker && (
                    <div style={{position:"absolute",top:"110%",left:0,background:T.surface,border:`1px solid ${T.border}`,borderRadius:10,padding:10,display:"flex",flexWrap:"wrap",gap:6,width:220,zIndex:30,boxShadow:"0 4px 20px rgba(0,0,0,0.12)"}}>
                      {ICONS.map(ic=><button key={ic} onClick={()=>{setTmplIcon(ic);setShowIconPicker(false);}} style={{background:ic===tmplIcon?T.surface2:"transparent",border:`1px solid ${ic===tmplIcon?T.border:"transparent"}`,borderRadius:6,padding:"5px 7px",cursor:"pointer",fontSize:20}}>{ic}</button>)}
                    </div>
                  )}
                </div>
              </div>
              <div>
                <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:8}}>COLORE</label>
                <div style={{display:"flex",gap:8,flexWrap:"wrap"}}>
                  {COLORS.map(c=><div key={c} onClick={()=>setTmplColor(c)} style={{width:26,height:26,borderRadius:"50%",background:c,cursor:"pointer",border:tmplColor===c?"3px solid #333":"3px solid transparent",transition:"transform 0.15s",transform:tmplColor===c?"scale(1.15)":"scale(1)"}}/>)}
                </div>
              </div>
            </div>

            {/* Anteprima fasi */}
            <div style={{background:T.surface2,borderRadius:8,padding:"12px 14px",marginBottom:22}}>
              <div style={{fontSize:12,color:T.textSub,fontWeight:700,marginBottom:8,letterSpacing:"0.06em"}}>ANTEPRIMA FASI</div>
              {project.steps.map((s,i)=>(
                <div key={s.id} style={{display:"flex",alignItems:"center",gap:8,marginBottom:5}}>
                  <span style={{fontSize:12,color:tmplColor,fontWeight:700,minWidth:18}}>{i+1}.</span>
                  <span style={{fontSize:14,color:T.text,fontWeight:500,flex:1}}>{s.title}</span>
                  <span style={{fontSize:12,color:T.textMuted}}>{s.tasks.length} task</span>
                </div>
              ))}
            </div>

            {/* Azioni */}
            <div style={{display:"flex",gap:10,justifyContent:"flex-end"}}>
              <button onClick={onClose} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:"9px 20px",cursor:"pointer",fontWeight:600}}>Annulla</button>
              <button onClick={handleSave} style={{background:T.accent,border:"none",borderRadius:8,color:"#fff",fontWeight:800,fontSize:14,padding:"9px 24px",cursor:"pointer"}}>
                {mode==="new" ? "💾 Salva come nuovo" : "↺ Sostituisci template"}
              </button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}

// ─── LOG ENTRY (editable) ─────────────────────────────────────────────────────
function LogEntry({ entry, projectColor, onUpdate, onDelete }) {
  const [hovered,  setHovered]  = useState(false);
  const [editing,  setEditing]  = useState(false);
  const [editVal,  setEditVal]  = useState(entry.text);
  const [confirm,  setConfirm]  = useState(false);

  function save() {
    if (editVal.trim()) onUpdate(editVal.trim());
    setEditing(false);
  }

  return (
    <div onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>{setHovered(false);setConfirm(false);}}
      style={{background:T.surface,border:`1px solid ${hovered?T.borderStrong:T.border}`,borderRadius:10,padding:"12px 16px",marginBottom:10,transition:"border 0.15s"}}>
      <div style={{display:"flex",gap:10,alignItems:"center",marginBottom:6}}>
        <span style={{fontSize:14,fontWeight:700,color:projectColor}}>{entry.user}</span>
        <span style={{fontSize:12,color:T.textMuted}}>{entry.time}</span>
        {entry.editedAt && <span style={{fontSize:11,color:T.textMuted,fontStyle:"italic"}}>· modificato {entry.editedAt}</span>}
        <div style={{marginLeft:"auto",display:"flex",gap:6,opacity:hovered?1:0,transition:"opacity 0.15s"}}>
          <button onClick={()=>{setEditing(true);setEditVal(entry.text);}}
            style={{background:"none",border:`1px solid ${T.border}`,borderRadius:6,color:T.textSub,fontSize:12,padding:"2px 8px",cursor:"pointer",fontWeight:600}}>✏️ Modifica</button>
          {confirm
            ? <>
                <button onClick={onDelete} style={{background:T.red,border:"none",borderRadius:6,color:"#fff",fontSize:12,padding:"2px 10px",cursor:"pointer",fontWeight:700}}>Conferma elimina</button>
                <button onClick={()=>setConfirm(false)} style={{background:"none",border:`1px solid ${T.border}`,borderRadius:6,color:T.textSub,fontSize:12,padding:"2px 8px",cursor:"pointer"}}>✕</button>
              </>
            : <button onClick={()=>setConfirm(true)} style={{background:"none",border:`1px solid ${T.red}44`,borderRadius:6,color:T.red,fontSize:12,padding:"2px 8px",cursor:"pointer"}}>🗑️</button>
          }
        </div>
      </div>
      {editing ? (
        <div style={{display:"flex",gap:8}}>
          <textarea value={editVal} onChange={e=>setEditVal(e.target.value)} autoFocus rows={2}
            style={{flex:1,background:T.surface2,border:`1.5px solid ${T.accent}44`,borderRadius:8,padding:"8px 12px",color:T.text,fontSize:15,outline:"none",resize:"vertical",fontFamily:"inherit"}}
            onKeyDown={e=>{if(e.key==="Enter"&&!e.shiftKey){e.preventDefault();save();}if(e.key==="Escape")setEditing(false);}}/>
          <div style={{display:"flex",flexDirection:"column",gap:6}}>
            <button onClick={save} style={{background:T.accent,border:"none",borderRadius:8,color:"#fff",fontSize:13,fontWeight:700,padding:"8px 14px",cursor:"pointer"}}>Salva</button>
            <button onClick={()=>setEditing(false)} style={{background:"none",border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:13,padding:"8px 10px",cursor:"pointer"}}>✕</button>
          </div>
        </div>
      ) : (
        <div style={{fontSize:15,color:T.text,whiteSpace:"pre-wrap"}}>{entry.text}</div>
      )}
    </div>
  );
}

// ─── PROJECT DETAIL ───────────────────────────────────────────────────────────
function ProjectDetail({project,onBack,onUpdate,onDelete,onArchive,templates,onSaveAsTemplate}){
  const[logText,setLogText]=useState("");
  const[logUser,setLogUser]=useState("Tu");
  const[activeTab,setActiveTab]=useState("tasks");
  const[addingStep,setAddingStep]=useState(false);
  const[newStepName,setNewStepName]=useState("");
  const[confirm,setConfirm]=useState(null);
  const[showSaveTemplate,setShowSaveTemplate]=useState(false);
  const logRef=useRef(null);
  const next=getNextTask(project);
  const progress=getProgress(project);

  function toggleTask(taskId){onUpdate({...project,steps:project.steps.map(s=>({...s,tasks:s.tasks.map(t=>t.id===taskId?{...t,done:!t.done,doneAt:!t.done?new Date().toISOString().slice(0,10):null}:t)}))});}
  function updateTaskInProject(updatedTask){onUpdate({...project,steps:project.steps.map(s=>({...s,tasks:s.tasks.map(t=>t.id===updatedTask.id?updatedTask:t)}))});}
  function addTask(stepId,text){onUpdate({...project,steps:project.steps.map(s=>s.id===stepId?{...s,tasks:[...s.tasks,{id:uid(),text,done:false,notes:[],note:"",doneAt:null}]}:s)});}
  function deleteTask(stepId,taskId){onUpdate({...project,steps:project.steps.map(s=>s.id===stepId?{...s,tasks:s.tasks.filter(t=>t.id!==taskId)}:s)});}
  function deleteStep(stepId){onUpdate({...project,steps:project.steps.filter(s=>s.id!==stepId)});}
  function reorderTask(stepId,from,to){onUpdate({...project,steps:project.steps.map(s=>s.id===stepId?{...s,tasks:reorder(s.tasks,from,to)}:s)});}
  function reorderStep(from,to){onUpdate({...project,steps:reorder(project.steps,from,to)});}
  function addStep(){if(!newStepName.trim())return;onUpdate({...project,steps:[...project.steps,{id:uid(),title:newStepName.trim(),tasks:[]}]});setNewStepName("");setAddingStep(false);}
  function addLog(){if(!logText.trim())return;onUpdate({...project,log:[...project.log,{id:uid(),user:logUser,text:logText.trim(),time:nowStr()}]});setLogText("");setTimeout(()=>logRef.current?.scrollTo({top:9999,behavior:"smooth"}),50);}
  function updateLog(logId,newText){onUpdate({...project,log:project.log.map(e=>e.id===logId?{...e,text:newText,editedAt:nowStr()}:e)});}
  function deleteLog(logId){onUpdate({...project,log:project.log.filter(e=>e.id!==logId)});}

  const Tab=({id,label})=>(
    <button onClick={()=>setActiveTab(id)} style={{background:"none",border:"none",cursor:"pointer",color:activeTab===id?project.color:T.textSub,fontSize:15,fontWeight:700,padding:"10px 0",borderBottom:activeTab===id?`3px solid ${project.color}`:"3px solid transparent",marginRight:24,transition:"all 0.15s"}}>{label}</button>
  );

  return(
    <div style={{display:"flex",flexDirection:"column",height:"100%",background:T.bg}}>
      {/* Header */}
      <div style={{padding:"20px 28px 0",borderBottom:`1px solid ${T.border}`,flexShrink:0,background:T.surface}}>
        <div style={{display:"flex",alignItems:"center",gap:12,marginBottom:16}}>
          <button onClick={onBack} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:"7px 14px",cursor:"pointer",fontWeight:600}}>← Indietro</button>
          <div style={{width:14,height:14,borderRadius:"50%",background:project.color,flexShrink:0}}/>
          <div style={{fontSize:20,fontWeight:800,color:T.text,flex:1}}>{project.name}</div>
          <StatusBadge progress={progress}/>
          <button onClick={()=>setShowSaveTemplate(true)} style={{background:T.blueBg,border:`1px solid ${T.blue}44`,borderRadius:8,color:T.blue,fontSize:14,padding:"7px 14px",cursor:"pointer",fontWeight:600}} title="Salva struttura come template">
            💾 Salva come Template
          </button>
          <button onClick={()=>setConfirm("archive")} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:"7px 14px",cursor:"pointer",fontWeight:600}}>
            {project.archived?"📤 Riattiva":"📦 Archivia"}
          </button>
          <button onClick={()=>setConfirm("delete")} style={{background:T.redBg,border:`1px solid ${T.red}44`,borderRadius:8,color:T.red,fontSize:14,padding:"7px 14px",cursor:"pointer",fontWeight:600}}>🗑️ Elimina</button>
        </div>
        <div style={{marginBottom:14}}>
          <div style={{display:"flex",justifyContent:"space-between",marginBottom:6}}>
            <span style={{fontSize:13,color:T.textSub,fontWeight:600}}>Avanzamento</span>
            <span style={{fontSize:13,color:project.color,fontWeight:700}}>{progress}% — {project.steps.flatMap(s=>s.tasks).filter(t=>t.done).length} di {project.steps.flatMap(s=>s.tasks).length} task completati</span>
          </div>
          <ProgressBar value={progress} color={project.color}/>
        </div>
        {next&&(
          <div style={{background:T.accentBg,border:`1.5px solid ${T.accent}44`,borderRadius:10,padding:"12px 16px",marginBottom:14,display:"flex",alignItems:"flex-start",gap:10}}>
            <span style={{fontSize:20,flexShrink:0}}>📍</span>
            <div>
              <div style={{fontSize:12,color:T.accent,fontWeight:700,letterSpacing:"0.06em",marginBottom:3}}>RIPRENDI DA QUI</div>
              <div style={{fontSize:15,color:T.text,fontWeight:600}}><span style={{color:T.textSub,fontWeight:400}}>{next.step.title} › </span>{next.task.text}</div>
              {(()=>{
                const t = next.task;
                if(t.text.trim().toLowerCase()==="fresatura" && Array.isArray(t.programs) && t.programs.length>0){
                  const done=t.programs.filter(p=>p.stato==="completato").length;
                  const inMacchina=t.programs.filter(p=>p.stato==="in_macchina").length;
                  return(
                    <div style={{display:"flex",alignItems:"center",gap:8,marginTop:5}}>
                      <span style={{fontSize:13,color:"#1D5FAD",fontWeight:700}}>⚙️ {done}/{t.programs.length} programmi completati</span>
                      {inMacchina>0&&<span style={{fontSize:12,color:"#1D5FAD",background:"#E8F0FA",padding:"2px 10px",borderRadius:10,border:"1px solid #1D5FAD44"}}>{inMacchina} in macchina ora</span>}
                    </div>
                  );
                }
                const firstNote = Array.isArray(t.notes) && t.notes.length > 0
                  ? t.notes[0].text
                  : t.note || null;
                const count = Array.isArray(t.notes) ? t.notes.length : (t.note ? 1 : 0);
                return firstNote ? (
                  <div style={{fontSize:13,color:T.accent,fontStyle:"italic",marginTop:4}}>
                    "{firstNote}"{count > 1 ? <span style={{fontSize:12,fontStyle:"normal",color:T.textMuted}}> +{count-1} altri commenti</span> : ""}
                  </div>
                ) : null;
              })()}
            </div>
          </div>
        )}
        <div><Tab id="tasks" label="Task"/><Tab id="log" label={`Log aggiornamenti (${project.log.length})`}/></div>
      </div>

      {/* Body */}
      <div style={{flex:1,overflow:"auto",padding:"20px 28px"}}>
        {activeTab==="tasks"&&(
          <div>
            <div style={{fontSize:12,color:T.textMuted,marginBottom:12,display:"flex",alignItems:"center",gap:6}}>
              <span>⣿</span> Trascina per riordinare fasi e task
            </div>
            {project.steps.map((step,sIdx)=>(
              <StepSection key={step.id} step={step} stepIdx={sIdx}
                nextTaskId={next?.step.id===step.id?next?.task.id:null}
                onToggle={toggleTask} onUpdateTask={updateTaskInProject} onAddTask={addTask}
                onDeleteTask={deleteTask} onReorderTask={reorderTask}
                onReorderStep={reorderStep} onDeleteStep={deleteStep}
                totalSteps={project.steps.length} projectColor={project.color}/>
            ))}
            {addingStep?(
              <div style={{display:"flex",gap:10,marginTop:10}}>
                <input autoFocus value={newStepName} onChange={e=>setNewStepName(e.target.value)} placeholder="Nome della nuova fase..."
                  style={{flex:1,background:T.surface,border:`1.5px solid ${T.border}`,borderRadius:10,padding:"10px 14px",color:T.text,fontSize:15,outline:"none"}}
                  onKeyDown={e=>{if(e.key==="Enter")addStep();if(e.key==="Escape"){setAddingStep(false);setNewStepName("");}}}/>
                <button onClick={addStep} style={{background:project.color,border:"none",borderRadius:10,color:"#fff",fontWeight:700,fontSize:15,padding:"10px 20px",cursor:"pointer"}}>Crea fase</button>
              </div>
            ):(
              <button onClick={()=>setAddingStep(true)} style={{background:"none",border:`2px dashed ${T.border}`,borderRadius:10,color:T.textMuted,fontSize:14,padding:"12px",cursor:"pointer",width:"100%",fontWeight:500,marginTop:4}}>+ Aggiungi fase</button>
            )}
          </div>
        )}
        {activeTab==="log"&&(
          <div style={{display:"flex",flexDirection:"column",height:"100%"}}>
            <div ref={logRef} style={{flex:1,overflowY:"auto",marginBottom:16}}>
              {project.log.length===0&&<div style={{fontSize:15,color:T.textMuted,textAlign:"center",padding:"40px 0"}}>Nessun aggiornamento ancora. Aggiungine uno!</div>}
              {project.log.map(entry=>(
                <LogEntry key={entry.id} entry={entry} projectColor={project.color}
                  onUpdate={newText=>updateLog(entry.id,newText)}
                  onDelete={()=>deleteLog(entry.id)}/>
              ))}
            </div>
            <div style={{display:"flex",gap:10,background:T.surface,padding:"14px",borderRadius:12,border:`1px solid ${T.border}`}}>
              <input value={logUser} onChange={e=>setLogUser(e.target.value)} style={{width:90,background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,padding:"9px 10px",color:project.color,fontSize:14,fontWeight:700,outline:"none"}}/>
              <input value={logText} onChange={e=>setLogText(e.target.value)} placeholder="Scrivi un aggiornamento..." style={{flex:1,background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,padding:"9px 12px",color:T.text,fontSize:15,outline:"none"}} onKeyDown={e=>{if(e.key==="Enter")addLog();}}/>
              <button onClick={addLog} style={{background:project.color,border:"none",borderRadius:8,color:"#fff",fontWeight:700,fontSize:15,padding:"9px 18px",cursor:"pointer"}}>→</button>
            </div>
          </div>
        )}
      </div>

      {confirm==="delete"&&<ConfirmDialog message={`Eliminare il progetto "${project.name}"? L'operazione è irreversibile.`} onConfirm={()=>{onDelete(project.id);setConfirm(null);}} onCancel={()=>setConfirm(null)}/>}
      {confirm==="archive"&&<ConfirmDialog message={project.archived?`Riportare "${project.name}" tra i progetti attivi?`:`Archiviare "${project.name}"?`} onConfirm={()=>{onArchive(project.id);setConfirm(null);}} onCancel={()=>setConfirm(null)}/>}
      {showSaveTemplate&&(
        <SaveAsTemplateModal
          project={project}
          templates={templates}
          onSave={tmpl=>{onSaveAsTemplate(tmpl);}}
          onClose={()=>setShowSaveTemplate(false)}
        />
      )}
    </div>
  );
}

// ─── PROJECT CARD ─────────────────────────────────────────────────────────────
function ProjectCard({project, onClick, onDelete, onArchive, delivery, onSetDelivery}){
  const progress  = getProgress(project);
  const next      = getNextTask(project);
  const [confirm,       setConfirm]       = useState(null);
  const [hovered,       setHovered]       = useState(false);
  const [editingDate,   setEditingDate]   = useState(false);
  const [dateVal,       setDateVal]       = useState(delivery?.dueDate||"");

  const days    = delivery ? daysUntil(delivery.dueDate) : null;
  const urgency = delivery ? deliveryUrgency(days) : null;

  // Bordo sinistro urgenza, bordo top colore progetto
  const leftBorder = urgency && !delivery?.delivered
    ? `4px solid ${urgency.color}`
    : `4px solid ${project.color}`;

  function saveDate(e){
    e.stopPropagation();
    onSetDelivery(project.id, dateVal);
    setEditingDate(false);
  }

  return(
    <div
      onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>{setHovered(false);}}
      style={{
        background:T.surface,
        border:`1.5px solid ${hovered?(urgency&&!delivery?.delivered?urgency.color+"66":project.color+"88"):T.border}`,
        borderLeft: leftBorder,
        borderRadius:12, padding:"18px 20px", position:"relative",
        transition:"all 0.18s",
        boxShadow: hovered?"0 4px 20px rgba(0,0,0,0.1)":"0 1px 4px rgba(0,0,0,0.05)",
        cursor:"pointer",
      }}
    >
      {/* Azioni hover */}
      <div style={{position:"absolute",top:12,right:12,display:"flex",gap:6,opacity:hovered?1:0,transition:"opacity 0.15s"}}>
        <button onClick={e=>{e.stopPropagation();setConfirm("archive");}} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:6,color:T.textSub,fontSize:12,padding:"4px 9px",cursor:"pointer",fontWeight:600}} title={project.archived?"Riattiva":"Archivia"}>{project.archived?"📤":"📦"}</button>
        <button onClick={e=>{e.stopPropagation();setConfirm("delete");}} style={{background:T.redBg,border:`1px solid ${T.red}44`,borderRadius:6,color:T.red,fontSize:12,padding:"4px 9px",cursor:"pointer",fontWeight:600}} title="Elimina">🗑️</button>
      </div>

      <div onClick={onClick}>
        {/* Header: nome + badge urgenza */}
        <div style={{marginBottom:10,paddingRight:80,display:"flex",flexDirection:"column",gap:4}}>
          <div style={{display:"flex",alignItems:"center",gap:8}}>
            <div style={{width:10,height:10,borderRadius:"50%",background:project.color,flexShrink:0}}/>
            <div style={{fontSize:17,fontWeight:800,color:T.text}}>{project.name}</div>
          </div>
          {project.description&&<div style={{fontSize:13,color:T.textSub,marginLeft:18}}>{project.description}</div>}
        </div>

        {/* Scadenza */}
        <div onClick={e=>e.stopPropagation()} style={{marginBottom:10,marginLeft:18}}>
          {editingDate ? (
            <div style={{display:"flex",gap:6,alignItems:"center"}}>
              <input type="date" value={dateVal} onChange={e=>setDateVal(e.target.value)} autoFocus
                style={{background:T.surface2,border:`1.5px solid ${T.accent}44`,borderRadius:6,padding:"4px 8px",color:T.text,fontSize:13,outline:"none"}}/>
              <button onClick={saveDate} style={{background:T.accent,border:"none",borderRadius:6,color:"#fff",fontSize:12,fontWeight:700,padding:"4px 10px",cursor:"pointer"}}>OK</button>
              <button onClick={e=>{e.stopPropagation();setEditingDate(false);}} style={{background:"none",border:`1px solid ${T.border}`,borderRadius:6,color:T.textSub,fontSize:12,padding:"4px 8px",cursor:"pointer"}}>✕</button>
            </div>
          ) : delivery?.dueDate ? (
            <div style={{display:"flex",alignItems:"center",gap:8}}>
              {delivery.delivered ? (
                <span style={{fontSize:12,color:T.green,fontWeight:700,background:T.greenBg,padding:"2px 10px",borderRadius:20}}>✓ Consegnato {delivery.deliveredAt||""}</span>
              ) : (
                <span style={{fontSize:12,fontWeight:800,color:urgency.color,background:urgency.bg,padding:"3px 12px",borderRadius:20,border:`1px solid ${urgency.color}33`}}>
                  {urgency.dot} {days===0?"OGGI":days<0?`Scaduto ${Math.abs(days)}gg fa`:`${days}gg alla consegna`}
                </span>
              )}
              <span style={{fontSize:12,color:T.textMuted}}>{new Date(delivery.dueDate).toLocaleDateString("it-IT",{day:"2-digit",month:"2-digit",year:"numeric"})}</span>
              <button onClick={e=>{e.stopPropagation();setDateVal(delivery.dueDate);setEditingDate(true);}}
                style={{background:"none",border:"none",color:T.textMuted,fontSize:11,cursor:"pointer",padding:"0 2px",opacity:hovered?0.7:0,transition:"opacity 0.15s"}}>✏️</button>
              <button onClick={e=>{e.stopPropagation();onSetDelivery(project.id,null,!delivery.delivered);}}
                title={delivery.delivered?"Segna come da consegnare":"Segna come consegnato"}
                style={{background:"none",border:`1px solid ${T.border}`,borderRadius:6,color:delivery.delivered?T.textMuted:T.green,fontSize:11,cursor:"pointer",padding:"2px 7px",opacity:hovered?1:0,transition:"opacity 0.15s"}}>
                {delivery.delivered?"↩ Riapri":"✓ Consegnato"}
              </button>
            </div>
          ) : (
            <button onClick={e=>{e.stopPropagation();setDateVal("");setEditingDate(true);}}
              style={{background:"none",border:`1px dashed ${T.border}`,borderRadius:6,color:T.textMuted,fontSize:12,padding:"3px 10px",cursor:"pointer",opacity:hovered?1:0.4,transition:"opacity 0.15s"}}>
              📅 Imposta scadenza
            </button>
          )}
        </div>

        <ProgressBar value={progress} color={project.color}/>
        <div style={{display:"flex",alignItems:"center",justifyContent:"space-between",marginTop:8,marginBottom:next?12:0}}>
          <span style={{fontSize:13,color:T.textSub,fontWeight:500}}>{project.steps.flatMap(s=>s.tasks).filter(t=>t.done).length} / {project.steps.flatMap(s=>s.tasks).length} task</span>
          <StatusBadge progress={progress}/>
        </div>
        {next?(
          <div style={{background:T.accentBg,borderRadius:8,padding:"10px 12px",borderLeft:`3px solid ${T.accent}`}}>
            <div style={{fontSize:11,color:T.accent,fontWeight:700,letterSpacing:"0.06em",marginBottom:3}}>📍 PROSSIMO STEP</div>
            <div style={{fontSize:14,color:T.text,fontWeight:600}}><span style={{color:T.textSub,fontWeight:400}}>{next.step.title} › </span>{next.task.text}</div>
            {(()=>{
              const t=next.task;
              // Se è una fresatura con programmi, mostra avanzamento programmi
              if(t.text.trim().toLowerCase()==="fresatura" && Array.isArray(t.programs) && t.programs.length>0){
                const done=t.programs.filter(p=>p.stato==="completato").length;
                const inMacchina=t.programs.filter(p=>p.stato==="in_macchina").length;
                return(
                  <div style={{display:"flex",alignItems:"center",gap:8,marginTop:4}}>
                    <span style={{fontSize:12,color:"#1D5FAD",fontWeight:700}}>⚙️ {done}/{t.programs.length} pgm</span>
                    {inMacchina>0&&<span style={{fontSize:11,color:"#1D5FAD",background:"#E8F0FA",padding:"1px 8px",borderRadius:10}}>{inMacchina} in macchina</span>}
                  </div>
                );
              }
              const firstNote=Array.isArray(t.notes)&&t.notes.length>0?t.notes[0].text:t.note||null;
              return firstNote?<div style={{fontSize:12,color:T.accent,marginTop:3,fontStyle:"italic"}}>"{firstNote}"</div>:null;
            })()}
          </div>
        ):(
          <div style={{fontSize:14,color:T.green,fontWeight:600,display:"flex",alignItems:"center",gap:6}}>
            <span style={{background:T.greenBg,border:`1px solid ${T.green}44`,borderRadius:6,padding:"4px 10px"}}>✓ Progetto completato</span>
          </div>
        )}
      </div>

      {confirm==="delete"&&<ConfirmDialog message={`Eliminare "${project.name}"?`} onConfirm={()=>{onDelete(project.id);setConfirm(null);}} onCancel={()=>setConfirm(null)}/>}
      {confirm==="archive"&&<ConfirmDialog message={project.archived?`Riportare "${project.name}" in Attivi?`:`Archiviare "${project.name}"?`} onConfirm={()=>{onArchive(project.id);setConfirm(null);}} onCancel={()=>setConfirm(null)}/>}
    </div>
  );
}

// ─── TEMPLATE EDITOR ──────────────────────────────────────────────────────────
function TemplateEditor({template,onSave,onCancel}){
  const[name,setName]=useState(template.name);
  const[description,setDescription]=useState(template.description);
  const[icon,setIcon]=useState(template.icon);
  const[color,setColor]=useState(template.color);
  const[steps,setSteps]=useState(template.steps.map(s=>({...s,tasks:s.tasks.map(t=>({...t}))})));
  const[showIconPicker,setShowIconPicker]=useState(false);

  function addStep(){setSteps(p=>[...p,{id:uid(),title:"Nuova fase",tasks:[]}]);}
  function updateStepTitle(id,title){setSteps(p=>p.map(s=>s.id===id?{...s,title}:s));}
  function removeStep(id){setSteps(p=>p.filter(s=>s.id!==id));}
  function addTask(stepId){setSteps(p=>p.map(s=>s.id===stepId?{...s,tasks:[...s.tasks,{id:uid(),text:"Nuovo task"}]}:s));}
  function updateTask(stepId,taskId,text){setSteps(p=>p.map(s=>s.id===stepId?{...s,tasks:s.tasks.map(t=>t.id===taskId?{...t,text}:t)}:s));}
  function removeTask(stepId,taskId){setSteps(p=>p.map(s=>s.id===stepId?{...s,tasks:s.tasks.filter(t=>t.id!==taskId)}:s));}
  function moveStep(idx,dir){const ns=[...steps],t=idx+dir;if(t<0||t>=ns.length)return;[ns[idx],ns[t]]=[ns[t],ns[idx]];setSteps(ns);}

  const inputStyle={background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:8,padding:"9px 12px",color:T.text,fontSize:14,outline:"none",width:"100%"};

  return(
    <div style={{display:"flex",flexDirection:"column",height:"100%",background:T.bg}}>
      <div style={{padding:"18px 28px",borderBottom:`1px solid ${T.border}`,flexShrink:0,background:T.surface,display:"flex",alignItems:"center",gap:12}}>
        <button onClick={onCancel} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:"8px 16px",cursor:"pointer",fontWeight:600}}>← Annulla</button>
        <div style={{fontSize:18,fontWeight:800,color:T.text,flex:1}}>{template.id.startsWith("new_")?"Nuovo Template":`Modifica: ${template.name}`}</div>
        <button onClick={()=>onSave({...template,name,description,icon,color,steps})} style={{background:color,border:"none",borderRadius:8,color:"#fff",fontWeight:700,fontSize:15,padding:"9px 22px",cursor:"pointer"}}>💾 Salva Template</button>
      </div>
      <div style={{flex:1,overflowY:"auto",padding:"24px 28px"}}>
        <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:16,marginBottom:20}}>
          <div><label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:6}}>NOME TEMPLATE</label><input value={name} onChange={e=>setName(e.target.value)} style={inputStyle}/></div>
          <div><label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:6}}>DESCRIZIONE</label><input value={description} onChange={e=>setDescription(e.target.value)} style={inputStyle}/></div>
        </div>
        <div style={{display:"flex",gap:32,marginBottom:24,alignItems:"flex-start"}}>
          <div>
            <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:8}}>ICONA</label>
            <div style={{position:"relative"}}>
              <button onClick={()=>setShowIconPicker(v=>!v)} style={{background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:10,padding:"10px 18px",cursor:"pointer",fontSize:24,lineHeight:1}}>{icon}</button>
              {showIconPicker&&(
                <div style={{position:"absolute",top:"110%",left:0,background:T.surface,border:`1px solid ${T.border}`,borderRadius:10,padding:12,display:"flex",flexWrap:"wrap",gap:6,width:220,zIndex:20,boxShadow:"0 4px 20px rgba(0,0,0,0.12)"}}>
                  {ICONS.map(ic=><button key={ic} onClick={()=>{setIcon(ic);setShowIconPicker(false);}} style={{background:ic===icon?T.surface2:"transparent",border:`1px solid ${ic===icon?T.border:"transparent"}`,borderRadius:6,padding:"5px 7px",cursor:"pointer",fontSize:20}}>{ic}</button>)}
                </div>
              )}
            </div>
          </div>
          <div>
            <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:8}}>COLORE</label>
            <div style={{display:"flex",gap:10,flexWrap:"wrap"}}>
              {COLORS.map(c=><div key={c} onClick={()=>setColor(c)} style={{width:28,height:28,borderRadius:"50%",background:c,cursor:"pointer",border:color===c?"3px solid #333":"3px solid transparent",transition:"transform 0.15s",transform:color===c?"scale(1.15)":"scale(1)"}}/>)}
            </div>
          </div>
        </div>
        <div style={{fontSize:13,color:T.textSub,fontWeight:600,letterSpacing:"0.06em",marginBottom:14}}>FASI E TASK</div>
        {steps.map((step,idx)=>(
          <div key={step.id} style={{background:T.surface,border:`1.5px solid ${T.border}`,borderLeft:`4px solid ${color}`,borderRadius:10,padding:"14px 16px",marginBottom:12}}>
            <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:12}}>
              <div style={{display:"flex",flexDirection:"column",gap:2}}>
                <button onClick={()=>moveStep(idx,-1)} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:4,cursor:"pointer",color:idx===0?T.textMuted:T.text,fontSize:10,padding:"2px 5px",lineHeight:1}}>▲</button>
                <button onClick={()=>moveStep(idx,1)} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:4,cursor:"pointer",color:idx===steps.length-1?T.textMuted:T.text,fontSize:10,padding:"2px 5px",lineHeight:1}}>▼</button>
              </div>
              <span style={{fontSize:12,color:color,fontWeight:700,minWidth:55}}>FASE {idx+1}</span>
              <input value={step.title} onChange={e=>updateStepTitle(step.id,e.target.value)} style={{...inputStyle,fontWeight:700,fontSize:15}}/>
              <button onClick={()=>removeStep(step.id)} style={{background:T.redBg,border:`1px solid ${T.red}44`,borderRadius:6,cursor:"pointer",color:T.red,fontSize:14,padding:"4px 8px",flexShrink:0}}>✕</button>
            </div>
            <div style={{marginLeft:32}}>
              {step.tasks.map(task=>(
                <div key={task.id} style={{display:"flex",alignItems:"center",gap:8,marginBottom:8}}>
                  <span style={{color:color,fontSize:12,opacity:0.6,flexShrink:0}}>◦</span>
                  <input value={task.text} onChange={e=>updateTask(step.id,task.id,e.target.value)} style={{...inputStyle,fontSize:14}}/>
                  <button onClick={()=>removeTask(step.id,task.id)} style={{background:T.redBg,border:`1px solid ${T.red}33`,borderRadius:6,cursor:"pointer",color:T.red,fontSize:13,padding:"4px 8px",flexShrink:0}}>✕</button>
                </div>
              ))}
              <button onClick={()=>addTask(step.id)} style={{background:"none",border:`1.5px dashed ${T.border}`,borderRadius:8,color:T.textMuted,fontSize:13,padding:"6px 14px",cursor:"pointer",fontWeight:500}}>+ Aggiungi task</button>
            </div>
          </div>
        ))}
        <button onClick={addStep} style={{background:"none",border:`2px dashed ${color}66`,borderRadius:10,color:color,fontSize:14,padding:"14px",cursor:"pointer",width:"100%",fontWeight:600}}>+ Aggiungi fase</button>
      </div>
    </div>
  );
}

// ─── BACKUP PAGE ──────────────────────────────────────────────────────────────
function BackupPage({ projects, templates, onImport, lastSavedProjects, lastSavedTemplates }) {
  const [importState,   setImportState]   = useState(null);
  const [importPreview, setImportPreview] = useState(null);
  const [backupIndex,   setBackupIndex]   = useState(() => loadBackupIndex());
  const [manualLabel,   setManualLabel]   = useState("");
  const [confirmDelete, setConfirmDelete] = useState(null);
  const [confirmRestore, setConfirmRestore] = useState(null);
  const [toast, setToast] = useState(null);
  const fileInputRef = useRef(null);

  function showToast(msg, type = "ok") {
    setToast({ msg, type });
    setTimeout(() => setToast(null), 3000);
  }

  function refreshIndex() { setBackupIndex(loadBackupIndex()); }

  // Backup manuale
  function doManualBackup() {
    saveBackupToStorage(projects, templates, "manual", manualLabel.trim() || null);
    refreshIndex();
    setManualLabel("");
    showToast("Backup manuale salvato nel browser ✓");
  }

  // Export file
  function doExportFile() {
    exportToFile(projects, templates);
    showToast("File esportato ✓");
  }

  // Export singolo backup storico come file
  function doExportBackup(entry) {
    const payload = getBackupPayload(entry.id);
    if (!payload) return;
    exportToFile(payload.projects, payload.templates, entry.label);
  }

  // Elimina backup dallo storico
  function doDeleteBackup(id) {
    deleteBackupFromStorage(id);
    refreshIndex();
    setConfirmDelete(null);
    showToast("Backup eliminato");
  }

  // Ripristina da storico
  function doRestoreFromHistory(entry, mode) {
    const payload = getBackupPayload(entry.id);
    if (!payload) return;
    onImport(payload, mode);
    setConfirmRestore(null);
    showToast(`Ripristino completato da "${entry.label}" ✓`);
  }

  // Import da file
  function handleFileChange(e) {
    const file = e.target.files[0];
    if (!file) return;
    importFromFile(
      file,
      (data) => setImportPreview(data),
      (err)  => { setImportState({ error: err }); setTimeout(() => setImportState(null), 4000); }
    );
    e.target.value = "";
  }

  function confirmImport(mode) {
    onImport(importPreview, mode);
    setImportPreview(null);
    showToast("Importazione completata ✓");
  }

  const activeCount   = projects.filter(p => !p.archived).length;
  const archivedCount = projects.filter(p =>  p.archived).length;
  const totalTasks    = projects.flatMap(p => p.steps.flatMap(s => s.tasks)).length;
  const doneTasks     = projects.flatMap(p => p.steps.flatMap(s => s.tasks)).filter(t => t.done).length;

  const autoBackups   = backupIndex.filter(e => e.type === "auto");
  const manualBackups = backupIndex.filter(e => e.type === "manual");

  return (
    <div style={{ flex:1, overflowY:"auto", padding:"28px", background:T.bg }}>
      <div style={{ maxWidth:740, margin:"0 auto" }}>

        {/* Toast */}
        {toast && (
          <div style={{ position:"fixed", top:20, right:24, background: toast.type==="ok" ? T.green : T.red, color:"#fff", borderRadius:10, padding:"12px 20px", fontSize:14, fontWeight:700, zIndex:300, boxShadow:"0 4px 20px rgba(0,0,0,0.2)", display:"flex", alignItems:"center", gap:8 }}>
            {toast.type==="ok" ? "✓" : "✕"} {toast.msg}
          </div>
        )}

        {/* Titolo */}
        <div style={{ marginBottom:24 }}>
          <div style={{ fontSize:22, fontWeight:800, color:T.text, marginBottom:4 }}>🗄️ Backup & Ripristino</div>
          <div style={{ fontSize:14, color:T.textSub, lineHeight:1.6 }}>
            I dati vengono salvati automaticamente nel browser. Usa i backup per trasferire i dati tra PC o aggiornamenti software.
          </div>
        </div>

        {/* Stato attuale */}
        <div style={{ background:T.surface, border:`1.5px solid ${T.border}`, borderRadius:12, padding:"20px 24px", marginBottom:20 }}>
          <div style={{ fontSize:13, color:T.textSub, fontWeight:700, letterSpacing:"0.06em", marginBottom:14 }}>DATI ATTUALI NEL BROWSER</div>
          <div style={{ display:"grid", gridTemplateColumns:"repeat(4,1fr)", gap:10, marginBottom:14 }}>
            {[
              ["📁", activeCount,         "Progetti attivi"],
              ["📦", archivedCount,       "Archiviati"],
              ["🎯", templates.length,    "Template"],
              ["✓",  `${doneTasks}/${totalTasks}`, "Task completati"],
            ].map(([icon,val,label]) => (
              <div key={label} style={{ background:T.surface2, borderRadius:10, padding:"12px 14px", textAlign:"center" }}>
                <div style={{ fontSize:20, marginBottom:4 }}>{icon}</div>
                <div style={{ fontSize:20, fontWeight:800, color:T.text }}>{val}</div>
                <div style={{ fontSize:11, color:T.textMuted, marginTop:2 }}>{label}</div>
              </div>
            ))}
          </div>
          <div style={{ display:"flex", gap:8, flexWrap:"wrap" }}>
            {lastSavedProjects  && <span style={{ background:T.greenBg, border:`1px solid ${T.green}33`, borderRadius:20, padding:"2px 10px", color:T.green, fontSize:12, fontWeight:600 }}>💾 Progetti · {lastSavedProjects}</span>}
            {lastSavedTemplates && <span style={{ background:T.greenBg, border:`1px solid ${T.green}33`, borderRadius:20, padding:"2px 10px", color:T.green, fontSize:12, fontWeight:600 }}>💾 Template · {lastSavedTemplates}</span>}
          </div>
        </div>

        {/* Export file */}
        <div style={{ background:T.surface, border:`1.5px solid ${T.border}`, borderRadius:12, padding:"20px 24px", marginBottom:20 }}>
          <div style={{ fontSize:13, color:T.textSub, fontWeight:700, letterSpacing:"0.06em", marginBottom:6 }}>📤 ESPORTA FILE DI BACKUP</div>
          <div style={{ fontSize:14, color:T.textSub, marginBottom:14, lineHeight:1.6 }}>
            Scarica un file <code style={{ background:T.surface2, padding:"1px 6px", borderRadius:4 }}>.json</code> con <strong>tutti i progetti e template</strong>. Usalo per trasferire su un altro PC o come backup sicuro su disco prima di aggiornare il software.
          </div>
          <button onClick={doExportFile}
            style={{ background:T.accent, border:"none", borderRadius:10, color:"#fff", fontWeight:700, fontSize:15, padding:"11px 26px", cursor:"pointer", display:"flex", alignItems:"center", gap:8 }}>
            📤 Scarica backup completo ({projects.length} progetti · {templates.length} template)
          </button>
          <div style={{ marginTop:12, background:T.surface2, border:`1px solid ${T.border}`, borderRadius:8, padding:"10px 14px", display:"flex", alignItems:"flex-start", gap:8 }}>
            <span style={{ fontSize:16, flexShrink:0 }}>📁</span>
            <div style={{ fontSize:12, color:T.textSub, lineHeight:1.6 }}>
              Salva il file scaricato in: <br/>
              <code style={{ fontSize:12, color:T.text, background:T.surface, padding:"2px 8px", borderRadius:4, display:"inline-block", marginTop:3 }}>
                C:\Users\i.dodon\Documents\Progetto 5\backup
              </code>
            </div>
          </div>
        </div>

        {/* Backup manuale nel browser */}
        <div style={{ background:T.surface, border:`1.5px solid ${T.border}`, borderRadius:12, padding:"20px 24px", marginBottom:20 }}>
          <div style={{ fontSize:13, color:T.textSub, fontWeight:700, letterSpacing:"0.06em", marginBottom:6 }}>💾 SALVA BACKUP NEL BROWSER</div>
          <div style={{ fontSize:14, color:T.textSub, marginBottom:14, lineHeight:1.6 }}>
            Salva uno snapshot dei dati attuali nello storico del browser. Puoi dargli un nome e ripristinarlo in qualsiasi momento.<br/>
            I backup <strong>automatici</strong> vengono creati ogni giorno (max {MAX_AUTO_BACKUPS} giorni conservati, i più vecchi vengono eliminati automaticamente).
          </div>
          <div style={{ display:"flex", gap:10 }}>
            <input
              value={manualLabel}
              onChange={e => setManualLabel(e.target.value)}
              placeholder={`Backup manuale ${new Date().toLocaleDateString("it-IT")}...`}
              style={{ flex:1, background:T.surface2, border:`1.5px solid ${T.border}`, borderRadius:8, padding:"9px 14px", color:T.text, fontSize:14, outline:"none" }}
              onKeyDown={e => { if (e.key==="Enter") doManualBackup(); }}
            />
            <button onClick={doManualBackup}
              style={{ background:T.blue, border:"none", borderRadius:8, color:"#fff", fontWeight:700, fontSize:14, padding:"9px 20px", cursor:"pointer", flexShrink:0 }}>
              💾 Salva ora
            </button>
          </div>
        </div>

        {/* Import da file */}
        <div style={{ background:T.surface, border:`1.5px solid ${T.border}`, borderRadius:12, padding:"20px 24px", marginBottom:20 }}>
          <div style={{ fontSize:13, color:T.textSub, fontWeight:700, letterSpacing:"0.06em", marginBottom:6 }}>📥 IMPORTA DA FILE</div>
          <div style={{ fontSize:14, color:T.textSub, marginBottom:14, lineHeight:1.6 }}>
            Carica un file <code style={{ background:T.surface2, padding:"1px 6px", borderRadius:4 }}>.json</code> esportato da WorkTrack. Puoi scegliere se unire i dati o sostituire tutto.
          </div>
          <input ref={fileInputRef} type="file" accept=".json" style={{ display:"none" }} onChange={handleFileChange} />
          <button onClick={() => fileInputRef.current.click()}
            style={{ background:T.surface2, border:`1.5px solid ${T.border}`, borderRadius:8, color:T.text, fontWeight:700, fontSize:14, padding:"10px 22px", cursor:"pointer", display:"flex", alignItems:"center", gap:8 }}>
            📂 Seleziona file backup...
          </button>
          {importState?.error && (
            <div style={{ marginTop:12, background:T.redBg, border:`1px solid ${T.red}44`, borderRadius:8, padding:"10px 14px", fontSize:14, color:T.red, fontWeight:600 }}>
              ✕ {importState.error}
            </div>
          )}
        </div>

        {/* Storico backup manuali */}
        {manualBackups.length > 0 && (
          <div style={{ background:T.surface, border:`1.5px solid ${T.border}`, borderRadius:12, padding:"20px 24px", marginBottom:20 }}>
            <div style={{ fontSize:13, color:T.textSub, fontWeight:700, letterSpacing:"0.06em", marginBottom:14 }}>
              📋 BACKUP MANUALI — {manualBackups.length}
            </div>
            {manualBackups.map(entry => (
              <BackupEntry key={entry.id} entry={entry}
                onExport={() => doExportBackup(entry)}
                onRestore={() => setConfirmRestore(entry)}
                onDelete={() => setConfirmDelete(entry.id)}
              />
            ))}
          </div>
        )}

        {/* Storico backup automatici */}
        <div style={{ background:T.surface, border:`1.5px solid ${T.border}`, borderRadius:12, padding:"20px 24px", marginBottom:20 }}>
          <div style={{ display:"flex", justifyContent:"space-between", alignItems:"center", marginBottom:14 }}>
            <div>
              <div style={{ fontSize:13, color:T.textSub, fontWeight:700, letterSpacing:"0.06em" }}>
                ⏱ BACKUP AUTOMATICI — {autoBackups.length} / {MAX_AUTO_BACKUPS} giorni
              </div>
              <div style={{ fontSize:12, color:T.textMuted, marginTop:2 }}>
                Uno al giorno, automatico. I più vecchi vengono eliminati quando si supera il limite di {MAX_AUTO_BACKUPS} giorni.
              </div>
            </div>
          </div>

          {autoBackups.length === 0 ? (
            <div style={{ fontSize:14, color:T.textMuted, padding:"20px 0", textAlign:"center" }}>
              Nessun backup automatico ancora — verrà creato al prossimo salvataggio dati.
            </div>
          ) : (
            <div style={{ maxHeight:340, overflowY:"auto" }}>
              {autoBackups.map(entry => (
                <BackupEntry key={entry.id} entry={entry}
                  onExport={() => doExportBackup(entry)}
                  onRestore={() => setConfirmRestore(entry)}
                  onDelete={() => setConfirmDelete(entry.id)}
                />
              ))}
            </div>
          )}
        </div>

        {/* Info */}
        <div style={{ background:T.blueBg, border:`1px solid ${T.blue}33`, borderRadius:10, padding:"14px 18px", display:"flex", gap:12, alignItems:"flex-start" }}>
          <span style={{ fontSize:20, flexShrink:0 }}>💡</span>
          <div style={{ fontSize:13, color:T.blue, lineHeight:1.7 }}>
            <strong>Prima di aggiornare il software:</strong> esporta sempre un file backup completo con il pulsante arancione qui sopra. Il localStorage del browser può essere pulito durante aggiornamenti del codice o cambio di browser.
          </div>
        </div>
      </div>

      {/* Modal conferma import da file */}
      {importPreview && (
        <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.45)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:200 }} onClick={() => setImportPreview(null)}>
          <div onClick={e=>e.stopPropagation()} style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:14, padding:"28px 32px", width:460, maxWidth:"92vw", boxShadow:"0 12px 48px rgba(0,0,0,0.2)" }}>
            <div style={{ fontSize:18, fontWeight:800, color:T.text, marginBottom:4 }}>📥 Conferma importazione</div>
            {importPreview.label && <div style={{ fontSize:13, color:T.textMuted, marginBottom:16 }}>"{importPreview.label}"</div>}
            <div style={{ display:"grid", gridTemplateColumns:"1fr 1fr", gap:10, marginBottom:22 }}>
              {importPreview.projects && (
                <div style={{ background:T.surface2, borderRadius:8, padding:"12px 16px" }}>
                  <div style={{ fontSize:22, fontWeight:800, color:T.text }}>{importPreview.projects.length}</div>
                  <div style={{ fontSize:13, color:T.textSub }}>Progetti</div>
                  <div style={{ fontSize:12, color:T.textMuted, marginTop:2 }}>
                    {importPreview.projects.filter(p=>!p.archived).length} attivi · {importPreview.projects.filter(p=>p.archived).length} archiviati
                  </div>
                </div>
              )}
              <div style={{ background:T.surface2, borderRadius:8, padding:"12px 16px" }}>
                <div style={{ fontSize:22, fontWeight:800, color:T.text }}>{importPreview.templates.length}</div>
                <div style={{ fontSize:13, color:T.textSub }}>Template</div>
              </div>
            </div>
            <div style={{ fontSize:13, color:T.textSub, fontWeight:700, marginBottom:10 }}>COME VUOI PROCEDERE?</div>
            <div style={{ display:"flex", flexDirection:"column", gap:8, marginBottom:16 }}>
              <button onClick={() => confirmImport("merge")} style={{ background:T.surface2, border:`1.5px solid ${T.border}`, borderRadius:8, padding:"12px 16px", cursor:"pointer", textAlign:"left" }}>
                <div style={{ fontSize:14, fontWeight:700, color:T.text }}>🔀 Unisci ai dati esistenti</div>
                <div style={{ fontSize:12, color:T.textMuted, marginTop:2 }}>Aggiunge nuovi elementi, aggiorna quelli con ID già esistente</div>
              </button>
              <button onClick={() => confirmImport("replace")} style={{ background:T.redBg, border:`1.5px solid ${T.red}44`, borderRadius:8, padding:"12px 16px", cursor:"pointer", textAlign:"left" }}>
                <div style={{ fontSize:14, fontWeight:700, color:T.red }}>⚠️ Sostituisci tutto</div>
                <div style={{ fontSize:12, color:T.red+"99", marginTop:2 }}>I dati attuali vengono rimpiazzati completamente</div>
              </button>
            </div>
            <button onClick={() => setImportPreview(null)} style={{ background:"none", border:`1px solid ${T.border}`, borderRadius:8, color:T.textSub, fontSize:14, padding:"9px 20px", cursor:"pointer", fontWeight:600, width:"100%" }}>Annulla</button>
          </div>
        </div>
      )}

      {/* Modal conferma ripristino da storico */}
      {confirmRestore && (
        <div style={{ position:"fixed", inset:0, background:"rgba(0,0,0,0.45)", display:"flex", alignItems:"center", justifyContent:"center", zIndex:200 }} onClick={() => setConfirmRestore(null)}>
          <div onClick={e=>e.stopPropagation()} style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:14, padding:"28px 32px", width:420, maxWidth:"92vw", boxShadow:"0 12px 48px rgba(0,0,0,0.2)" }}>
            <div style={{ fontSize:18, fontWeight:800, color:T.text, marginBottom:6 }}>↩️ Ripristina backup</div>
            <div style={{ fontSize:14, color:T.textSub, marginBottom:20, lineHeight:1.6 }}>
              Vuoi ripristinare: <strong>"{confirmRestore.label}"</strong>?<br/>
              <span style={{ fontSize:12, color:T.textMuted }}>{new Date(confirmRestore.createdAt).toLocaleString("it-IT")} · {confirmRestore.projectCount} progetti · {confirmRestore.templateCount} template</span>
            </div>
            <div style={{ display:"flex", flexDirection:"column", gap:8, marginBottom:16 }}>
              <button onClick={() => doRestoreFromHistory(confirmRestore, "merge")} style={{ background:T.surface2, border:`1.5px solid ${T.border}`, borderRadius:8, padding:"11px 16px", cursor:"pointer", textAlign:"left" }}>
                <div style={{ fontSize:14, fontWeight:700, color:T.text }}>🔀 Unisci ai dati esistenti</div>
              </button>
              <button onClick={() => doRestoreFromHistory(confirmRestore, "replace")} style={{ background:T.redBg, border:`1.5px solid ${T.red}44`, borderRadius:8, padding:"11px 16px", cursor:"pointer", textAlign:"left" }}>
                <div style={{ fontSize:14, fontWeight:700, color:T.red }}>⚠️ Sostituisci tutto</div>
              </button>
            </div>
            <button onClick={() => setConfirmRestore(null)} style={{ background:"none", border:`1px solid ${T.border}`, borderRadius:8, color:T.textSub, fontSize:14, padding:"9px 20px", cursor:"pointer", fontWeight:600, width:"100%" }}>Annulla</button>
          </div>
        </div>
      )}

      {/* Modal conferma eliminazione */}
      {confirmDelete && (
        <ConfirmDialog
          message="Eliminare questo backup dallo storico? L'operazione è irreversibile."
          onConfirm={() => doDeleteBackup(confirmDelete)}
          onCancel={() => setConfirmDelete(null)}
        />
      )}
    </div>
  );
}

// ─── BACKUP ENTRY ROW ─────────────────────────────────────────────────────────
function BackupEntry({ entry, onExport, onRestore, onDelete }) {
  const [hovered, setHovered] = useState(false);
  const date = new Date(entry.createdAt);
  const dateStr = date.toLocaleDateString("it-IT", { day:"2-digit", month:"short", year:"numeric" });
  const timeStr = date.toLocaleTimeString("it-IT", { hour:"2-digit", minute:"2-digit" });

  return (
    <div
      onMouseEnter={() => setHovered(true)}
      onMouseLeave={() => setHovered(false)}
      style={{ display:"flex", alignItems:"center", gap:12, padding:"10px 12px", borderRadius:8, background: hovered ? T.surface2 : "transparent", transition:"background 0.15s", marginBottom:4 }}
    >
      <div style={{ fontSize:18, flexShrink:0 }}>{entry.type === "auto" ? "⏱" : "💾"}</div>
      <div style={{ flex:1, minWidth:0 }}>
        <div style={{ fontSize:14, fontWeight:600, color:T.text, whiteSpace:"nowrap", overflow:"hidden", textOverflow:"ellipsis" }}>{entry.label}</div>
        <div style={{ fontSize:12, color:T.textMuted, marginTop:1 }}>{dateStr} · {timeStr} · {entry.projectCount} progetti · {entry.templateCount} template</div>
      </div>
      <div style={{ display:"flex", gap:6, opacity: hovered ? 1 : 0, transition:"opacity 0.15s", flexShrink:0 }}>
        <button onClick={onExport}  style={{ background:T.surface, border:`1px solid ${T.border}`, borderRadius:6, color:T.textSub, fontSize:12, padding:"4px 10px", cursor:"pointer", fontWeight:600 }} title="Esporta come file">📤</button>
        <button onClick={onRestore} style={{ background:T.blueBg, border:`1px solid ${T.blue}44`, borderRadius:6, color:T.blue, fontSize:12, padding:"4px 10px", cursor:"pointer", fontWeight:600 }} title="Ripristina">↩️ Ripristina</button>
        <button onClick={onDelete}  style={{ background:T.redBg, border:`1px solid ${T.red}44`, borderRadius:6, color:T.red, fontSize:12, padding:"4px 10px", cursor:"pointer", fontWeight:600 }} title="Elimina">🗑️</button>
      </div>
    </div>
  );
}

// ─── TEMPLATES PAGE ───────────────────────────────────────────────────────────
function TemplatesPage({templates, onEdit, onCreate, onDelete, onDuplicate, onUseTemplate, lastSaved}){
  return(
    <div style={{flex:1,overflowY:"auto",padding:"24px 28px",background:T.bg}}>
      {/* Header */}
      <div style={{display:"flex",justifyContent:"space-between",alignItems:"center",marginBottom:20}}>
        <div>
          <div style={{fontSize:13,color:T.textSub,fontWeight:600,letterSpacing:"0.06em",marginBottom:4}}>
            TEMPLATE SALVATI — {templates.length}
          </div>
          {lastSaved && (
            <span style={{background:T.greenBg,border:`1px solid ${T.green}44`,borderRadius:20,padding:"2px 10px",fontSize:12,color:T.green,fontWeight:600}}>
              💾 Salvati automaticamente · {lastSaved}
            </span>
          )}
        </div>
        <button onClick={onCreate}
          style={{background:T.accent,border:"none",borderRadius:8,color:"#fff",fontWeight:700,fontSize:14,padding:"9px 20px",cursor:"pointer"}}>
          + Nuovo Template
        </button>
      </div>

      {templates.length===0 && (
        <div style={{textAlign:"center",padding:"60px 0",color:T.textMuted,fontSize:16}}>
          Nessun template. Creane uno!
        </div>
      )}

      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill, minmax(320px, 1fr))",gap:16}}>
        {templates.map(tmpl=>(
          <div key={tmpl.id} style={{background:T.surface,border:`1.5px solid ${T.border}`,borderTop:`4px solid ${tmpl.color}`,borderRadius:12,padding:"18px 20px",boxShadow:"0 1px 4px rgba(0,0,0,0.05)"}}>
            {/* Card header */}
            <div style={{display:"flex",alignItems:"flex-start",gap:14,marginBottom:14}}>
              <span style={{fontSize:28,lineHeight:1}}>{tmpl.icon}</span>
              <div style={{flex:1}}>
                <div style={{fontSize:16,fontWeight:800,color:T.text,marginBottom:3}}>{tmpl.name}</div>
                <div style={{fontSize:13,color:T.textSub}}>{tmpl.description}</div>
              </div>
            </div>
            {/* Fasi preview */}
            <div style={{background:T.surface2,borderRadius:8,padding:"10px 12px",marginBottom:10}}>
              {tmpl.steps.map((step,i)=>(
                <div key={step.id} style={{display:"flex",alignItems:"center",gap:8,marginBottom:i<tmpl.steps.length-1?5:0}}>
                  <span style={{fontSize:12,color:tmpl.color,fontWeight:700,minWidth:18}}>{i+1}.</span>
                  <span style={{fontSize:14,color:T.text,fontWeight:500,flex:1}}>{step.title}</span>
                  <span style={{fontSize:12,color:T.textMuted}}>{step.tasks.length} task</span>
                </div>
              ))}
            </div>
            <div style={{fontSize:12,color:T.textMuted,marginBottom:14}}>
              {tmpl.steps.reduce((a,s)=>a+s.tasks.length,0)} task totali · {tmpl.steps.length} fasi
            </div>
            {/* Azioni */}
            <div style={{display:"flex",gap:6}}>
              <button onClick={()=>onUseTemplate(tmpl)}
                style={{flex:1,background:tmpl.color,border:"none",borderRadius:8,color:"#fff",fontWeight:700,fontSize:14,padding:"9px",cursor:"pointer"}}>
                ▶ Usa
              </button>
              <button onClick={()=>onDuplicate(tmpl)}
                style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:"9px 12px",cursor:"pointer",fontWeight:600}}
                title="Duplica template">
                ⧉
              </button>
              <button onClick={()=>onEdit(tmpl)}
                style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:"9px 12px",cursor:"pointer",fontWeight:600}}
                title="Modifica template">
                ✏️
              </button>
              <button onClick={()=>onDelete(tmpl.id)}
                style={{background:T.redBg,border:`1px solid ${T.red}44`,borderRadius:8,color:T.red,fontSize:14,padding:"9px 12px",cursor:"pointer"}}
                title="Elimina template">
                🗑️
              </button>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

// ─── QUICK TASKS SIDEBAR ──────────────────────────────────────────────────────
const STORAGE_QUICKTASKS = "worktrack_quicktasks_v1";
function loadQuickTasks() { try { const r = localStorage.getItem(STORAGE_QUICKTASKS); return r ? JSON.parse(r) : []; } catch { return []; } }
function saveQuickTasks(t) { try { localStorage.setItem(STORAGE_QUICKTASKS, JSON.stringify(t)); } catch {} }

const PRIORITY = {
  alta:  { label:"Alta",  color:"#C0392B", bg:"#FDECEA", dot:"🔴" },
  media: { label:"Media", color:"#D4700A", bg:"#FFF4E8", dot:"🟡" },
  bassa: { label:"Bassa", color:"#1A7A4A", bg:"#E8F5EE", dot:"🟢" },
};

function QuickTasksSidebar({ collapsed, onToggleCollapse }) {
  const [tasks,   setTasks]   = useState(() => loadQuickTasks());
  const [newText, setNewText] = useState("");
  const [newPrio, setNewPrio] = useState("media");
  const [filter,  setFilter]  = useState("tutti");
  const inputRef = useRef(null);

  useEffect(() => { saveQuickTasks(tasks); }, [tasks]);

  function addTask() {
    if (!newText.trim()) return;
    setTasks(ts => [{ id:uid(), text:newText.trim(), priority:newPrio, done:false, createdAt:new Date().toISOString() }, ...ts]);
    setNewText("");
    inputRef.current?.focus();
  }
  function toggleDone(id)     { setTasks(ts => ts.map(t => t.id===id ? {...t, done:!t.done} : t)); }
  function deleteTask(id)     { setTasks(ts => ts.filter(t => t.id!==id)); }
  function setPriority(id, p) { setTasks(ts => ts.map(t => t.id===id ? {...t, priority:p} : t)); }
  function editText(id, text) { setTasks(ts => ts.map(t => t.id===id ? {...t, text} : t)); }

  const filtered = tasks.filter(t => {
    if (filter==="da_fare") return !t.done;
    if (filter==="fatti")   return t.done;
    if (filter==="alta")    return t.priority==="alta";
    if (filter==="media")   return t.priority==="media";
    if (filter==="bassa")   return t.priority==="bassa";
    return true;
  });
  const pendingCount = tasks.filter(t => !t.done).length;

  if (collapsed) {
    return (
      <div onClick={onToggleCollapse} title="Apri task rapidi"
        style={{ width:32, flexShrink:0, background:T.surface, borderLeft:`1px solid ${T.border}`, display:"flex", flexDirection:"column", alignItems:"center", justifyContent:"center", cursor:"pointer", userSelect:"none" }}>
        <div style={{ writingMode:"vertical-rl", transform:"rotate(180deg)", fontSize:12, fontWeight:700, color:T.textSub, letterSpacing:"0.1em", display:"flex", alignItems:"center", gap:6 }}>
          ⚡ TASK RAPIDI
          {pendingCount > 0 && <span style={{ background:T.accent, color:"#fff", borderRadius:10, fontSize:10, fontWeight:800, padding:"2px 5px", writingMode:"horizontal-tb" }}>{pendingCount}</span>}
        </div>
      </div>
    );
  }

  return (
    <div style={{ width:280, flexShrink:0, background:T.surface, borderLeft:`1px solid ${T.border}`, display:"flex", flexDirection:"column", overflow:"hidden" }}>
      {/* Header + input */}
      <div style={{ padding:"14px 14px 10px", borderBottom:`1px solid ${T.border}`, flexShrink:0 }}>
        <div style={{ display:"flex", alignItems:"center", gap:8, marginBottom:10 }}>
          <span style={{ fontSize:16 }}>⚡</span>
          <span style={{ fontSize:14, fontWeight:800, color:T.text, flex:1 }}>Task Rapidi</span>
          {pendingCount > 0 && <span style={{ background:T.accent, color:"#fff", borderRadius:20, fontSize:11, fontWeight:800, padding:"2px 8px" }}>{pendingCount}</span>}
          <button onClick={onToggleCollapse} title="Comprimi" style={{ background:"none", border:`1px solid ${T.border}`, borderRadius:6, color:T.textMuted, fontSize:12, padding:"2px 7px", cursor:"pointer" }}>✕</button>
        </div>
        <div style={{ display:"flex", flexDirection:"column", gap:6 }}>
          <input ref={inputRef} value={newText} onChange={e=>setNewText(e.target.value)}
            onKeyDown={e=>{if(e.key==="Enter")addTask();}}
            placeholder="Nuovo task..."
            style={{ background:T.surface2, border:`1.5px solid ${T.border}`, borderRadius:8, padding:"8px 10px", color:T.text, fontSize:13, outline:"none", width:"100%" }}/>
          <div style={{ display:"flex", gap:5 }}>
            {Object.entries(PRIORITY).map(([key, p]) => (
              <button key={key} onClick={()=>setNewPrio(key)} style={{
                flex:1, background:newPrio===key?p.bg:"transparent",
                border:`1.5px solid ${newPrio===key?p.color:T.border}`,
                borderRadius:6, color:newPrio===key?p.color:T.textMuted,
                fontSize:11, fontWeight:700, padding:"5px 0", cursor:"pointer", transition:"all 0.12s",
              }}>{p.dot} {p.label}</button>
            ))}
          </div>
          <button onClick={addTask} style={{ background:T.accent, border:"none", borderRadius:8, color:"#fff", fontWeight:700, fontSize:13, padding:"8px", cursor:"pointer", width:"100%" }}>+ Aggiungi</button>
        </div>
      </div>
      {/* Filtri */}
      <div style={{ padding:"8px 10px", borderBottom:`1px solid ${T.border}`, display:"flex", flexWrap:"wrap", gap:4, flexShrink:0 }}>
        {[["tutti",`Tutti (${tasks.length})`],["da_fare",`Da fare (${tasks.filter(t=>!t.done).length})`],["fatti",`Fatti (${tasks.filter(t=>t.done).length})`],["alta","🔴"],["media","🟡"],["bassa","🟢"]].map(([key,label])=>(
          <button key={key} onClick={()=>setFilter(key)} style={{
            background:filter===key?T.surface2:"transparent", border:`1px solid ${filter===key?T.borderStrong:"transparent"}`,
            borderRadius:6, color:filter===key?T.text:T.textMuted, fontSize:11, fontWeight:600, padding:"3px 8px", cursor:"pointer",
          }}>{label}</button>
        ))}
      </div>
      {/* Lista */}
      <div style={{ flex:1, overflowY:"auto", padding:"8px" }}>
        {filtered.length===0 && (
          <div style={{ textAlign:"center", padding:"30px 10px", color:T.textMuted, fontSize:13 }}>
            {filter==="tutti"?"Nessun task ancora.\nAggiungine uno!":"Nessun task in questa categoria."}
          </div>
        )}
        {filtered.map(task=>(
          <QuickTaskRow key={task.id} task={task}
            onToggle={()=>toggleDone(task.id)}
            onDelete={()=>deleteTask(task.id)}
            onPriority={p=>setPriority(task.id,p)}
            onEditText={text=>editText(task.id,text)}/>
        ))}
      </div>
    </div>
  );
}

function QuickTaskRow({ task, onToggle, onDelete, onPriority, onEditText }) {
  const [hovered,      setHovered]      = useState(false);
  const [showPrioPick, setShowPrioPick] = useState(false);
  const [editing,      setEditing]      = useState(false);
  const [editVal,      setEditVal]      = useState(task.text);
  const p = PRIORITY[task.priority] || PRIORITY.media;

  function saveEdit() {
    if (editVal.trim()) onEditText(editVal.trim());
    setEditing(false);
  }

  return (
    <div onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>{setHovered(false);setShowPrioPick(false);}}
      style={{ display:"flex", alignItems:"flex-start", gap:8, padding:"8px 8px", borderRadius:8, marginBottom:3, background:hovered?T.surface2:"transparent", borderLeft:`3px solid ${task.done?T.border:p.color}`, transition:"background 0.12s", opacity:task.done?0.6:1 }}>
      {/* Checkbox */}
      <div onClick={onToggle} style={{ width:18, height:18, borderRadius:5, flexShrink:0, marginTop:editing?8:1, border:task.done?"none":`2px solid ${p.color}`, background:task.done?p.color:"transparent", cursor:"pointer", display:"flex", alignItems:"center", justifyContent:"center" }}>
        {task.done && <span style={{color:"#fff",fontSize:11,fontWeight:800}}>✓</span>}
      </div>
      {/* Testo / edit */}
      {editing ? (
        <div style={{flex:1,display:"flex",gap:5}}>
          <input value={editVal} onChange={e=>setEditVal(e.target.value)} autoFocus
            style={{flex:1,background:T.surface,border:`1.5px solid ${T.accent}44`,borderRadius:6,padding:"4px 8px",color:T.text,fontSize:13,outline:"none"}}
            onKeyDown={e=>{if(e.key==="Enter")saveEdit();if(e.key==="Escape")setEditing(false);}}/>
          <button onClick={saveEdit} style={{background:T.accent,border:"none",borderRadius:5,color:"#fff",fontSize:12,fontWeight:700,padding:"4px 9px",cursor:"pointer",flexShrink:0}}>OK</button>
          <button onClick={()=>setEditing(false)} style={{background:"none",border:`1px solid ${T.border}`,borderRadius:5,color:T.textSub,fontSize:12,padding:"4px 6px",cursor:"pointer",flexShrink:0}}>✕</button>
        </div>
      ) : (
        <span onDoubleClick={()=>{setEditVal(task.text);setEditing(true);}}
          style={{ flex:1, fontSize:13, color:T.text, lineHeight:1.5, textDecoration:task.done?"line-through":"none", wordBreak:"break-word", cursor:"text" }}
          title="Doppio click per modificare">
          {task.text}
        </span>
      )}
      {/* Azioni hover */}
      {hovered && !editing && (
        <div style={{ display:"flex", flexDirection:"column", gap:3, flexShrink:0, position:"relative" }}>
          <button onClick={()=>{setEditVal(task.text);setEditing(true);}} title="Modifica"
            style={{ background:"none", border:`1px solid ${T.border}`, borderRadius:5, fontSize:11, padding:"2px 5px", cursor:"pointer", color:T.textSub }}>✏️</button>
          <button onClick={()=>setShowPrioPick(v=>!v)} title="Cambia priorità"
            style={{ background:"none", border:`1px solid ${T.border}`, borderRadius:5, fontSize:12, padding:"2px 5px", cursor:"pointer", color:p.color, fontWeight:700 }}>{p.dot}</button>
          <button onClick={onDelete} title="Elimina"
            style={{ background:"none", border:`1px solid ${T.border}`, borderRadius:5, fontSize:11, padding:"2px 5px", cursor:"pointer", color:T.red }}>🗑️</button>
          {showPrioPick && (
            <div style={{ position:"absolute", right:"110%", top:0, background:T.surface, border:`1px solid ${T.border}`, borderRadius:8, padding:6, display:"flex", flexDirection:"column", gap:4, boxShadow:"0 4px 16px rgba(0,0,0,0.12)", zIndex:50, width:90 }}>
              {Object.entries(PRIORITY).map(([key,pr])=>(
                <button key={key} onClick={()=>{onPriority(key);setShowPrioPick(false);}} style={{ background:task.priority===key?pr.bg:"transparent", border:`1px solid ${task.priority===key?pr.color:"transparent"}`, borderRadius:5, color:pr.color, fontSize:12, fontWeight:700, padding:"4px 8px", cursor:"pointer", textAlign:"left" }}>{pr.dot} {pr.label}</button>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

// ─── CONSEGNE ─────────────────────────────────────────────────────────────────
const STORAGE_DELIVERIES = "worktrack_deliveries_v1";
function loadDeliveries() { try { const r = localStorage.getItem(STORAGE_DELIVERIES); return r ? JSON.parse(r) : []; } catch { return []; } }
function saveDeliveries(d) { try { localStorage.setItem(STORAGE_DELIVERIES, JSON.stringify(d)); } catch {} }

function daysUntil(dateStr) {
  if (!dateStr) return null;
  const today = new Date(); today.setHours(0,0,0,0);
  const target = new Date(dateStr); target.setHours(0,0,0,0);
  return Math.round((target - today) / 86400000);
}

function deliveryUrgency(days) {
  if (days === null) return { label:"Nessuna data", color:T.textMuted, bg:T.surface2, dot:"⚪", rank:4 };
  if (days < 0)   return { label:"SCADUTA",        color:"#fff",    bg:T.red,      dot:"💀", rank:0 };
  if (days === 0) return { label:"OGGI",            color:"#fff",    bg:T.red,      dot:"🚨", rank:0 };
  if (days <= 3)  return { label:`${days}gg`,       color:T.red,     bg:T.redBg,    dot:"🔴", rank:1 };
  if (days <= 7)  return { label:`${days}gg`,       color:"#C2720A", bg:"#FFF0DC",  dot:"🟠", rank:2 };
  if (days <= 21) return { label:`${days}gg`,       color:T.accent,  bg:T.accentBg, dot:"🟡", rank:3 };
  return           { label:`${days}gg`,             color:T.green,   bg:T.greenBg,  dot:"🟢", rank:4 };
}

function DeliveryPage({ projects, onNavigateToProject }) {
  const [deliveries, setDeliveries] = useState(() => loadDeliveries());
  const [showForm,   setShowForm]   = useState(false);
  const [editId,     setEditId]     = useState(null);
  const [form,       setForm]       = useState({ projectId:"", note:"", dueDate:"", delivered:false });
  const [confirm,    setConfirm]    = useState(null);

  useEffect(() => { saveDeliveries(deliveries); }, [deliveries]);

  const activeProjects = projects.filter(p => !p.archived);

  // Arricchisce ogni delivery con i dati del progetto e l'urgenza
  const enriched = deliveries.map(d => {
    const proj = projects.find(p => p.id === d.projectId);
    const days = daysUntil(d.dueDate);
    const urgency = deliveryUrgency(days);
    const progress = proj ? getProgress(proj) : 0;
    return { ...d, proj, days, urgency, progress };
  }).sort((a,b) => {
    if (a.delivered !== b.delivered) return a.delivered ? 1 : -1;
    if (a.days === null) return 1;
    if (b.days === null) return -1;
    return a.days - b.days;
  });

  const pending   = enriched.filter(d => !d.delivered);
  const delivered = enriched.filter(d => d.delivered);
  const urgent    = pending.filter(d => d.days !== null && d.days <= 7);

  function openNew() {
    setForm({ projectId: activeProjects[0]?.id || "", note:"", dueDate:"", delivered:false });
    setEditId(null); setShowForm(true);
  }
  function openEdit(d) {
    setForm({ projectId:d.projectId, note:d.note||"", dueDate:d.dueDate||"", delivered:d.delivered });
    setEditId(d.id); setShowForm(true);
  }
  function save() {
    if (!form.projectId || !form.dueDate) return;
    if (editId) {
      setDeliveries(ds => ds.map(d => d.id===editId ? {...d,...form} : d));
    } else {
      setDeliveries(ds => [...ds, { id:uid(), ...form, createdAt:nowStr() }]);
    }
    setShowForm(false);
  }
  function toggleDelivered(id) { setDeliveries(ds => ds.map(d => d.id===id ? {...d,delivered:!d.delivered,deliveredAt:!d.delivered?nowStr():null} : d)); }
  function remove(id) { setDeliveries(ds => ds.filter(d => d.id!==id)); setConfirm(null); }

  const inputSt = { background:T.surface2, border:`1.5px solid ${T.border}`, borderRadius:8, padding:"9px 12px", color:T.text, fontSize:14, outline:"none", width:"100%" };

  return (
    <div style={{flex:1,overflowY:"auto",padding:"24px 28px",background:T.bg}}>

      {/* Focus del giorno */}
      {urgent.length > 0 && (
        <div style={{background:T.redBg,border:`2px solid ${T.red}44`,borderRadius:14,padding:"16px 20px",marginBottom:24}}>
          <div style={{fontSize:13,fontWeight:800,color:T.red,letterSpacing:"0.08em",marginBottom:10}}>🎯 FOCUS DEL GIORNO — {urgent.length} CONSEGN{urgent.length===1?"A":"E"} URGENTI</div>
          <div style={{display:"flex",flexDirection:"column",gap:8}}>
            {urgent.map(d=>(
              <div key={d.id} style={{display:"flex",alignItems:"center",gap:12,background:"rgba(255,255,255,0.6)",borderRadius:10,padding:"10px 14px"}}>
                <span style={{fontSize:20}}>{d.urgency.dot}</span>
                <div style={{flex:1}}>
                  <span style={{fontWeight:700,color:T.text,fontSize:15}}>{d.proj?.name||"—"}</span>
                  {d.note&&<span style={{fontSize:13,color:T.textSub,marginLeft:8}}>{d.note}</span>}
                </div>
                <span style={{fontSize:13,fontWeight:800,color:d.urgency.color,background:d.urgency.bg,padding:"3px 12px",borderRadius:20,border:`1px solid ${d.urgency.color}44`}}>
                  {d.days===0?"OGGI":d.days<0?`${Math.abs(d.days)}gg fa`:`${d.days}gg`}
                </span>
                <span style={{fontSize:13,color:T.textSub}}>{d.progress}%</span>
                {d.proj&&<button onClick={()=>onNavigateToProject(d.proj.id)} style={{background:T.red,border:"none",borderRadius:7,color:"#fff",fontSize:12,fontWeight:700,padding:"5px 12px",cursor:"pointer"}}>Apri →</button>}
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Header */}
      <div style={{display:"flex",alignItems:"center",marginBottom:20}}>
        <div>
          <div style={{fontSize:13,color:T.textSub,fontWeight:700,letterSpacing:"0.06em"}}>CONSEGNE — {pending.length} IN ATTESA</div>
        </div>
        <button onClick={openNew} style={{marginLeft:"auto",background:T.accent,border:"none",borderRadius:8,color:"#fff",fontWeight:700,fontSize:14,padding:"9px 20px",cursor:"pointer"}}>+ Nuova consegna</button>
      </div>

      {/* Form aggiunta/modifica */}
      {showForm && (
        <div style={{background:T.surface,border:`1.5px solid ${T.accent}44`,borderRadius:14,padding:"20px",marginBottom:20}}>
          <div style={{fontSize:14,fontWeight:700,color:T.text,marginBottom:14}}>{editId?"✏️ Modifica consegna":"+ Nuova consegna"}</div>
          <div style={{display:"grid",gridTemplateColumns:"1fr 1fr",gap:12,marginBottom:12}}>
            <div>
              <label style={{fontSize:12,color:T.textSub,fontWeight:700,display:"block",marginBottom:5}}>PROGETTO *</label>
              <select value={form.projectId} onChange={e=>setForm(f=>({...f,projectId:e.target.value}))} style={{...inputSt,appearance:"none"}}>
                <option value="">— Seleziona —</option>
                {activeProjects.map(p=><option key={p.id} value={p.id}>{p.name}</option>)}
              </select>
            </div>
            <div>
              <label style={{fontSize:12,color:T.textSub,fontWeight:700,display:"block",marginBottom:5}}>DATA DI CONSEGNA *</label>
              <input type="date" value={form.dueDate} onChange={e=>setForm(f=>({...f,dueDate:e.target.value}))} style={inputSt}/>
            </div>
          </div>
          <div style={{marginBottom:14}}>
            <label style={{fontSize:12,color:T.textSub,fontWeight:700,display:"block",marginBottom:5}}>NOTE (opzionale)</label>
            <input value={form.note} onChange={e=>setForm(f=>({...f,note:e.target.value}))} placeholder="Es. consegna parziale, cliente X..." style={inputSt}/>
          </div>
          <div style={{display:"flex",gap:10,justifyContent:"flex-end"}}>
            <button onClick={()=>setShowForm(false)} style={{background:"none",border:`1px solid ${T.border}`,borderRadius:8,color:T.textSub,fontSize:14,padding:"8px 18px",cursor:"pointer"}}>Annulla</button>
            <button onClick={save} disabled={!form.projectId||!form.dueDate}
              style={{background:form.projectId&&form.dueDate?T.accent:"#ccc",border:"none",borderRadius:8,color:"#fff",fontWeight:700,fontSize:14,padding:"8px 22px",cursor:form.projectId&&form.dueDate?"pointer":"default"}}>
              {editId?"Salva modifiche":"Aggiungi"}
            </button>
          </div>
        </div>
      )}

      {/* Lista consegne pendenti */}
      {pending.length === 0 && !showForm && (
        <div style={{textAlign:"center",padding:"60px 0"}}>
          <div style={{fontSize:48,marginBottom:16}}>📅</div>
          <div style={{fontSize:18,fontWeight:700,color:T.text,marginBottom:8}}>Nessuna consegna programmata</div>
          <div style={{fontSize:15,color:T.textSub,marginBottom:20}}>Aggiungi le date di consegna dei tuoi progetti</div>
          <button onClick={openNew} style={{background:T.accent,border:"none",borderRadius:10,color:"#fff",fontWeight:700,fontSize:15,padding:"11px 26px",cursor:"pointer"}}>+ Prima consegna</button>
        </div>
      )}

      {pending.length > 0 && (
        <div style={{display:"flex",flexDirection:"column",gap:10,marginBottom:32}}>
          {pending.map(d=>(
            <DeliveryRow key={d.id} d={d}
              onToggle={()=>toggleDelivered(d.id)}
              onEdit={()=>openEdit(d)}
              onDelete={()=>setConfirm(d.id)}
              onOpen={()=>d.proj&&onNavigateToProject(d.proj.id)}/>
          ))}
        </div>
      )}

      {/* Consegnate */}
      {delivered.length > 0 && (
        <details style={{marginTop:8}}>
          <summary style={{fontSize:13,color:T.textSub,fontWeight:700,letterSpacing:"0.06em",cursor:"pointer",marginBottom:10}}>
            ✅ CONSEGNATE — {delivered.length}
          </summary>
          <div style={{display:"flex",flexDirection:"column",gap:8,marginTop:10}}>
            {delivered.map(d=>(
              <DeliveryRow key={d.id} d={d}
                onToggle={()=>toggleDelivered(d.id)}
                onEdit={()=>openEdit(d)}
                onDelete={()=>setConfirm(d.id)}
                onOpen={()=>d.proj&&onNavigateToProject(d.proj.id)}/>
            ))}
          </div>
        </details>
      )}

      {confirm&&<ConfirmDialog message="Eliminare questa consegna?" onConfirm={()=>remove(confirm)} onCancel={()=>setConfirm(null)}/>}
    </div>
  );
}

function DeliveryRow({ d, onToggle, onEdit, onDelete, onOpen }) {
  const [hovered, setHovered] = useState(false);
  const u = d.urgency;

  return (
    <div onMouseEnter={()=>setHovered(true)} onMouseLeave={()=>setHovered(false)}
      style={{
        background:T.surface, border:`1.5px solid ${d.delivered?T.border:u.color+"44"}`,
        borderLeft:`4px solid ${d.delivered?T.border:u.color}`,
        borderRadius:12, padding:"14px 18px", display:"flex", alignItems:"center", gap:14,
        opacity:d.delivered?0.65:1, transition:"all 0.15s",
        boxShadow:hovered&&!d.delivered?"0 2px 12px rgba(0,0,0,0.07)":"none",
      }}>
      {/* Checkbox consegnato */}
      <div onClick={onToggle} title={d.delivered?"Segna come da consegnare":"Segna come consegnato"}
        style={{width:24,height:24,borderRadius:8,flexShrink:0,cursor:"pointer",display:"flex",alignItems:"center",justifyContent:"center",
          border:d.delivered?"none":`2px solid ${u.color}`, background:d.delivered?T.green:"transparent",transition:"all 0.2s"}}>
        {d.delivered&&<span style={{color:"#fff",fontSize:14,fontWeight:800}}>✓</span>}
      </div>

      {/* Info progetto */}
      <div style={{flex:1,minWidth:0}}>
        <div style={{display:"flex",alignItems:"center",gap:8,marginBottom:3}}>
          {d.proj&&<div style={{width:10,height:10,borderRadius:"50%",background:d.proj.color,flexShrink:0}}/>}
          <span style={{fontSize:15,fontWeight:700,color:T.text,overflow:"hidden",textOverflow:"ellipsis",whiteSpace:"nowrap"}}>
            {d.proj?.name||<span style={{color:T.red,fontStyle:"italic"}}>Progetto eliminato</span>}
          </span>
        </div>
        <div style={{display:"flex",alignItems:"center",gap:12,flexWrap:"wrap"}}>
          {d.note&&<span style={{fontSize:13,color:T.textSub}}>{d.note}</span>}
          {d.delivered&&d.deliveredAt&&<span style={{fontSize:12,color:T.textMuted,fontStyle:"italic"}}>Consegnato {d.deliveredAt}</span>}
        </div>
      </div>

      {/* Progress bar progetto */}
      {d.proj&&!d.delivered&&(
        <div style={{width:80,flexShrink:0}}>
          <div style={{fontSize:11,color:T.textMuted,marginBottom:3,textAlign:"right"}}>{d.progress}%</div>
          <div style={{height:5,background:T.surface2,borderRadius:3,overflow:"hidden"}}>
            <div style={{height:"100%",width:`${d.progress}%`,background:d.proj.color,borderRadius:3}}/>
          </div>
        </div>
      )}

      {/* Badge scadenza */}
      {!d.delivered&&(
        <div style={{background:u.bg,color:u.color,border:`1.5px solid ${u.color}44`,borderRadius:20,padding:"4px 14px",fontSize:13,fontWeight:800,flexShrink:0,minWidth:70,textAlign:"center"}}>
          {u.dot} {d.days===null?"—":d.days===0?"OGGI":d.days<0?`${Math.abs(d.days)}gg fa`:`${d.days}gg`}
        </div>
      )}

      {/* Data */}
      <div style={{fontSize:13,color:T.textMuted,flexShrink:0,minWidth:80,textAlign:"right"}}>
        {d.dueDate?new Date(d.dueDate).toLocaleDateString("it-IT",{day:"2-digit",month:"2-digit",year:"numeric"}):"—"}
      </div>

      {/* Azioni hover */}
      <div style={{display:"flex",gap:6,opacity:hovered?1:0,transition:"opacity 0.15s",flexShrink:0}}>
        {d.proj&&<button onClick={onOpen} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:7,color:T.textSub,fontSize:12,padding:"4px 10px",cursor:"pointer",fontWeight:600}}>Apri →</button>}
        <button onClick={onEdit} style={{background:"none",border:`1px solid ${T.border}`,borderRadius:7,color:T.textSub,fontSize:12,padding:"4px 8px",cursor:"pointer"}}>✏️</button>
        <button onClick={onDelete} style={{background:"none",border:`1px solid ${T.red}44`,borderRadius:7,color:T.red,fontSize:12,padding:"4px 8px",cursor:"pointer"}}>🗑️</button>
      </div>
    </div>
  );
}

// ─── NEW PROJECT MODAL ────────────────────────────────────────────────────────
function NewProjectModal({onClose,onCreate,templates,preselectedTemplate}){
  const[name,setName]=useState("");
  const[desc,setDesc]=useState("");
  const[color,setColor]=useState(preselectedTemplate?.color||"#D4700A");
  const[selectedTmpl,setSelectedTmpl]=useState(preselectedTemplate||null);
  const[stepsRaw,setStepsRaw]=useState("");

  function selectTmpl(t){setSelectedTmpl(t);if(t)setColor(t.color);}
  function create(){
    if(!name.trim())return;
    const steps=selectedTmpl?cloneTemplateToSteps(selectedTmpl):stepsRaw.split("\n").filter(l=>l.trim()).map(line=>({id:uid(),title:line.trim(),tasks:[]}));
    onCreate({id:uid(),name:name.trim(),description:desc.trim(),color,createdAt:new Date().toISOString().slice(0,10),archived:false,steps:steps.length?steps:[{id:uid(),title:"Step 1",tasks:[]}],log:[]});
    onClose();
  }

  const inputStyle={width:"100%",background:T.surface2,border:`1.5px solid ${T.border}`,borderRadius:10,padding:"10px 14px",color:T.text,fontSize:15,outline:"none"};

  return(
    <div style={{position:"fixed",inset:0,background:"rgba(0,0,0,0.45)",display:"flex",alignItems:"center",justifyContent:"center",zIndex:100}} onClick={onClose}>
      <div onClick={e=>e.stopPropagation()} style={{background:T.surface,border:`1px solid ${T.border}`,borderRadius:14,padding:32,width:540,maxWidth:"92vw",maxHeight:"88vh",overflowY:"auto",boxShadow:"0 12px 48px rgba(0,0,0,0.2)"}}>
        <div style={{fontSize:20,fontWeight:800,color:T.text,marginBottom:22}}>Nuovo Progetto</div>
        <div style={{marginBottom:16}}>
          <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:6}}>NOME PROGETTO *</label>
          <input autoFocus value={name} onChange={e=>setName(e.target.value)} style={inputStyle} placeholder="Es. Sito Web Cliente Bianchi"/>
        </div>
        <div style={{marginBottom:22}}>
          <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:6}}>DESCRIZIONE</label>
          <input value={desc} onChange={e=>setDesc(e.target.value)} style={inputStyle} placeholder="Breve descrizione del progetto"/>
        </div>
        <div style={{marginBottom:22}}>
          <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:10}}>PARTI DA UN TEMPLATE</label>
          <div style={{display:"flex",flexWrap:"wrap",gap:8,marginBottom:12}}>
            <button onClick={()=>selectTmpl(null)} style={{background:!selectedTmpl?T.surface2:"transparent",border:`1.5px solid ${!selectedTmpl?T.borderStrong:T.border}`,borderRadius:8,color:!selectedTmpl?T.text:T.textSub,fontSize:13,padding:"7px 14px",cursor:"pointer",fontWeight:600}}>Nessuno</button>
            {templates.map(t=>(
              <button key={t.id} onClick={()=>selectTmpl(t)} style={{background:selectedTmpl?.id===t.id?t.color+"18":"transparent",border:`1.5px solid ${selectedTmpl?.id===t.id?t.color:T.border}`,borderRadius:8,color:selectedTmpl?.id===t.id?t.color:T.textSub,fontSize:13,padding:"7px 14px",cursor:"pointer",fontWeight:600}}>{t.icon} {t.name}</button>
            ))}
          </div>
          {selectedTmpl?(
            <div style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:10,padding:"12px 16px"}}>
              <div style={{fontSize:12,color:T.textSub,fontWeight:700,marginBottom:8}}>FASI INCLUSE</div>
              {selectedTmpl.steps.map(s=><div key={s.id} style={{fontSize:14,color:T.text,marginBottom:4,display:"flex",gap:8}}>
                <span style={{color:selectedTmpl.color,fontWeight:700}}>•</span>{s.title} <span style={{color:T.textMuted}}>({s.tasks.length} task)</span>
              </div>)}
            </div>
          ):(
            <div>
              <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:6}}>OPPURE INSERISCI FASI (una per riga)</label>
              <textarea value={stepsRaw} onChange={e=>setStepsRaw(e.target.value)} rows={4} placeholder={"Analisi\nDesign\nSviluppo\nDeploy"} style={{...inputStyle,resize:"vertical"}}/>
            </div>
          )}
        </div>
        <div style={{marginBottom:24}}>
          <label style={{fontSize:13,color:T.textSub,fontWeight:600,display:"block",marginBottom:10}}>COLORE PROGETTO</label>
          <div style={{display:"flex",gap:10}}>
            {COLORS.map(c=><div key={c} onClick={()=>setColor(c)} style={{width:30,height:30,borderRadius:"50%",background:c,cursor:"pointer",border:color===c?"3px solid #333":"3px solid transparent",transition:"transform 0.15s",transform:color===c?"scale(1.15)":"scale(1)"}}/>)}
          </div>
        </div>
        <div style={{display:"flex",gap:10,justifyContent:"flex-end"}}>
          <button onClick={onClose} style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:10,color:T.textSub,fontSize:15,padding:"10px 22px",cursor:"pointer",fontWeight:600}}>Annulla</button>
          <button onClick={create} style={{background:color,border:"none",borderRadius:10,color:"#fff",fontWeight:800,fontSize:15,padding:"10px 26px",cursor:"pointer"}}>Crea Progetto</button>
        </div>
      </div>
    </div>
  );
}

// ─── MAIN APP ─────────────────────────────────────────────────────────────────
export default function App(){
  // ── Templates: persistenti in localStorage ──
  const [templates, setTemplates] = useState(() => loadTemplatesFromStorage() ?? INITIAL_TEMPLATES);
  const [lastSavedTmpl, setLastSavedTmpl] = useState(() => loadTemplatesFromStorage() ? nowStr() : null);
  useEffect(() => { saveTemplatesToStorage(templates); setLastSavedTmpl(nowStr()); }, [templates]);

  // ── Projects: persistenti in localStorage ──
  const [projects, setProjects] = useState(() => loadProjectsFromStorage() ?? INITIAL_DATA.projects);
  const [lastSavedProj, setLastSavedProj] = useState(() => loadProjectsFromStorage() ? nowStr() : null);
  useEffect(() => { saveProjectsToStorage(projects); setLastSavedProj(nowStr()); }, [projects]);

  // ── Auto-backup giornaliero: si aggiorna ogni volta che cambiano projects o templates ──
  // useRef per avere sempre i valori aggiornati senza creare loop
  const projectsRef  = useRef(projects);
  const templatesRef = useRef(templates);
  useEffect(() => { projectsRef.current  = projects;  }, [projects]);
  useEffect(() => { templatesRef.current = templates; }, [templates]);

  useEffect(() => {
    // Subito al mount: crea/aggiorna il backup automatico di oggi
    saveBackupToStorage(projectsRef.current, templatesRef.current, "auto");
  }, []); // eslint-disable-line

  // Backup automatico ritardato: evita di scrivere ad ogni singolo carattere
  const autoBackupTimer = useRef(null);
  useEffect(() => {
    clearTimeout(autoBackupTimer.current);
    autoBackupTimer.current = setTimeout(() => {
      saveBackupToStorage(projectsRef.current, templatesRef.current, "auto");
    }, 5000); // 5 secondi di debounce dopo l'ultima modifica
    return () => clearTimeout(autoBackupTimer.current);
  }, [projects, templates]);

  const[page,setPage]=useState("projects");
  const[selectedProjectId,setSelectedProjectId]=useState(null);
  const[editingTemplate,setEditingTemplate]=useState(null);
  const[showNewProject,setShowNewProject]=useState(false);
  const[preselectedTemplate,setPreselectedTemplate]=useState(null);
  const[search,setSearch]=useState("");
  const[sidebarCollapsed,setSidebarCollapsed]=useState(false);
  const[deliveries,setDeliveries]=useState(()=>loadDeliveries());

  useEffect(()=>{ saveDeliveries(deliveries); },[deliveries]);

  function setDelivery(projectId, dueDate, toggleDelivered){
    setDeliveries(ds=>{
      const existing = ds.find(d=>d.projectId===projectId);
      if(toggleDelivered!==undefined && existing){
        return ds.map(d=>d.projectId===projectId?{...d,delivered:toggleDelivered,deliveredAt:toggleDelivered?nowStr():null}:d);
      }
      if(dueDate===null){
        // clear date only, keep record if delivered
        return ds.map(d=>d.projectId===projectId?{...d,dueDate:""}:d);
      }
      if(existing){
        return ds.map(d=>d.projectId===projectId?{...d,dueDate}:d);
      }
      return [...ds,{id:uid(),projectId,dueDate,delivered:false,createdAt:nowStr()}];
    });
  }

  function getDelivery(projectId){ return deliveries.find(d=>d.projectId===projectId)||null; }

  const activeProjects=projects.filter(p=>!p.archived&&(p.name.toLowerCase().includes(search.toLowerCase())||p.description.toLowerCase().includes(search.toLowerCase())));
  const archivedProjects=projects.filter(p=>p.archived);
  const inProgress=activeProjects.filter(p=>getProgress(p)<100);
  const completed=activeProjects.filter(p=>getProgress(p)===100);
  const selectedProject=projects.find(p=>p.id===selectedProjectId);

  function updateProject(updated){setProjects(ps=>ps.map(p=>p.id===updated.id?updated:p));}
  function addProject(project){setProjects(ps=>[...ps,project]);}
  function deleteProject(id){setProjects(ps=>ps.filter(p=>p.id!==id));setSelectedProjectId(null);}
  function archiveProject(id){setProjects(ps=>ps.map(p=>p.id===id?{...p,archived:!p.archived}:p));setSelectedProjectId(null);}

  function saveTemplate(tmpl){
    setTemplates(ts => ts.some(t=>t.id===tmpl.id) ? ts.map(t=>t.id===tmpl.id?tmpl:t) : [...ts,tmpl]);
    setPage("templates"); setEditingTemplate(null);
  }
  function deleteTemplate(id){ setTemplates(ts=>ts.filter(t=>t.id!==id)); }
  function duplicateTemplate(tmpl){
    const copy = {
      ...tmpl,
      id:   uid(),
      name: `${tmpl.name} (copia)`,
      steps: tmpl.steps.map(s=>({...s, id:uid(), tasks:s.tasks.map(t=>({...t, id:uid()}))})),
    };
    setTemplates(ts=>{
      const idx = ts.findIndex(t=>t.id===tmpl.id);
      const next = [...ts];
      next.splice(idx+1, 0, copy);
      return next;
    });
  }
  function useTemplate(tmpl){ setPreselectedTemplate(tmpl); setShowNewProject(true); setPage("projects"); }
  function importTemplates(imported){
    setTemplates(ts => {
      const ids = new Set(ts.map(t=>t.id));
      return [...ts.map(t=>{const u=imported.find(i=>i.id===t.id);return u||t;}), ...imported.filter(t=>!ids.has(t.id))];
    });
  }

  function handleBackupImport({ projects: impProj, templates: impTmpl }, mode) {
    if (mode === "replace") {
      if (impProj) setProjects(impProj);
      setTemplates(impTmpl);
    } else {
      if (impProj) {
        setProjects(cur => {
          const ids = new Set(cur.map(p=>p.id));
          return [...cur.map(p=>{const u=impProj.find(i=>i.id===p.id);return u||p;}), ...impProj.filter(p=>!ids.has(p.id))];
        });
      }
      setTemplates(cur => {
        const ids = new Set(cur.map(t=>t.id));
        return [...cur.map(t=>{const u=impTmpl.find(i=>i.id===t.id);return u||t;}), ...impTmpl.filter(t=>!ids.has(t.id))];
      });
    }
  }

  const isOnEditor=page==="templateEditor"&&editingTemplate;
  const isOnProject=!!selectedProject;

  const NavBtn=({id,label,badge})=>(
    <button onClick={()=>{setPage(id);setSelectedProjectId(null);setEditingTemplate(null);}}
      style={{background:"none",border:"none",cursor:"pointer",color:page===id&&!isOnProject&&!isOnEditor?T.accent:T.textSub,fontSize:15,fontWeight:700,padding:"16px 0",borderBottom:page===id&&!isOnProject&&!isOnEditor?`3px solid ${T.accent}`:"3px solid transparent",display:"flex",alignItems:"center",gap:7,transition:"all 0.15s"}}>
      {label}
      {badge>0&&<span style={{background:T.surface2,border:`1px solid ${T.border}`,color:T.textSub,borderRadius:20,fontSize:12,padding:"1px 8px",fontWeight:700}}>{badge}</span>}
    </button>
  );

  return(
    <div style={{fontFamily:"'DM Sans', system-ui, sans-serif",background:T.bg,minHeight:"100vh",color:T.text,display:"flex",flexDirection:"column"}}>
      <style>{`
        @import url('https://fonts.googleapis.com/css2?family=DM+Sans:wght@400;500;600;700;800&display=swap');
        * { box-sizing:border-box; }
        ::-webkit-scrollbar { width:6px; }
        ::-webkit-scrollbar-track { background:${T.surface2}; }
        ::-webkit-scrollbar-thumb { background:${T.borderStrong}; border-radius:3px; }
        input::placeholder,textarea::placeholder { color:${T.textMuted} !important; }
        button { outline:none; font-family:inherit; }
      `}</style>

      {/* TOP BAR */}
      <div style={{borderBottom:`1px solid ${T.border}`,padding:"0 28px",display:"flex",alignItems:"center",gap:24,flexShrink:0,background:T.surface,boxShadow:"0 1px 0 rgba(0,0,0,0.06)"}}>
        <div style={{fontSize:20,fontWeight:800,color:T.text,letterSpacing:"-0.02em",paddingRight:16,borderRight:`1px solid ${T.border}`,marginRight:4,padding:"16px 16px 16px 0"}}>
          <span style={{color:T.accent}}>◈</span> WorkTrack
        </div>
        {!isOnProject&&!isOnEditor&&(
          <>
            <NavBtn id="projects"  label="Progetti"/>
            <NavBtn id="archived"  label="Archivio" badge={archivedProjects.length}/>
            <NavBtn id="templates" label={`Template (${templates.length})`}/>
            <NavBtn id="backup"    label="Backup"/>
          </>
        )}
        {page==="projects"&&!isOnProject&&!isOnEditor&&(
          <div style={{marginLeft:"auto",display:"flex",gap:12,alignItems:"center"}}>
            <input value={search} onChange={e=>setSearch(e.target.value)} placeholder="Cerca progetto..." style={{background:T.surface2,border:`1px solid ${T.border}`,borderRadius:8,padding:"8px 14px",color:T.text,fontSize:14,outline:"none",width:200}}/>
            <span style={{fontSize:14,color:T.textSub,fontWeight:600}}>{inProgress.length} attivi</span>
            <button onClick={()=>{setPreselectedTemplate(null);setShowNewProject(true);}} style={{background:T.accent,border:"none",borderRadius:8,color:"#fff",fontWeight:700,fontSize:14,padding:"9px 20px",cursor:"pointer"}}>+ Nuovo Progetto</button>
          </div>
        )}
      </div>

      {/* CONTENT + SIDEBAR */}
      <div style={{flex:1,overflow:"hidden",display:"flex",flexDirection:"row"}}>
        <div style={{flex:1,overflow:"hidden",display:"flex",flexDirection:"column"}}>
        {isOnEditor?(
          <TemplateEditor template={editingTemplate} onSave={saveTemplate} onCancel={()=>{setPage("templates");setEditingTemplate(null);}}/>
        ):isOnProject?(
          <ProjectDetail
            project={selectedProject}
            onBack={()=>setSelectedProjectId(null)}
            onUpdate={updateProject}
            onDelete={deleteProject}
            onArchive={archiveProject}
            templates={templates}
            onSaveAsTemplate={tmpl=>{
              setTemplates(ts=>ts.some(t=>t.id===tmpl.id)?ts.map(t=>t.id===tmpl.id?tmpl:t):[...ts,tmpl]);
            }}
          />
        ):page==="templates"?(
          <TemplatesPage
            templates={templates}
            onEdit={tmpl=>{setEditingTemplate(tmpl);setPage("templateEditor");}}
            onCreate={()=>{setEditingTemplate({id:`new_${uid()}`,name:"Nuovo Template",description:"",icon:"🚀",color:"#D4700A",steps:[]});setPage("templateEditor");}}
            onDelete={deleteTemplate}
            onDuplicate={duplicateTemplate}
            onUseTemplate={useTemplate}
            lastSaved={lastSavedTmpl}
          />
        ):page==="backup"?(
          <BackupPage
            projects={projects}
            templates={templates}
            onImport={handleBackupImport}
            lastSavedProjects={lastSavedProj}
            lastSavedTemplates={lastSavedTmpl}
          />
        ):page==="archived"?(
          <div style={{flex:1,overflowY:"auto",padding:"24px 28px",background:T.bg}}>
            <div style={{fontSize:13,color:T.textSub,fontWeight:600,letterSpacing:"0.06em",marginBottom:18}}>ARCHIVIO — {archivedProjects.length} PROGETTI</div>
            {archivedProjects.length===0&&(
              <div style={{textAlign:"center",padding:"60px 0"}}>
                <div style={{fontSize:48,marginBottom:16}}>📦</div>
                <div style={{fontSize:18,fontWeight:700,color:T.text,marginBottom:8}}>Archivio vuoto</div>
                <div style={{fontSize:15,color:T.textSub}}>Usa il pulsante 📦 su un progetto per archiviarlo.</div>
              </div>
            )}
            <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill, minmax(300px, 1fr))",gap:14}}>
              {archivedProjects.map(p=><ProjectCard key={p.id} project={p} onClick={()=>setSelectedProjectId(p.id)} onDelete={deleteProject} onArchive={archiveProject} delivery={getDelivery(p.id)} onSetDelivery={setDelivery}/>)}
            </div>
          </div>
        ):(
          <div style={{flex:1,overflowY:"auto",padding:"24px 28px",background:T.bg}}>
            {inProgress.length===0&&completed.length===0&&(
              <div style={{textAlign:"center",padding:"80px 0"}}>
                <div style={{fontSize:48,marginBottom:16}}>🚀</div>
                <div style={{fontSize:20,fontWeight:700,color:T.text,marginBottom:8}}>Nessun progetto ancora</div>
                <div style={{fontSize:15,color:T.textSub,marginBottom:24}}>Crea il tuo primo progetto per iniziare</div>
                <button onClick={()=>setShowNewProject(true)} style={{background:T.accent,border:"none",borderRadius:10,color:"#fff",fontWeight:700,fontSize:16,padding:"12px 28px",cursor:"pointer"}}>+ Crea il primo progetto</button>
              </div>
            )}
            {(()=>{
              // Ordina: prima per urgenza scadenza, poi per % avanzamento (meno avanzati prima)
              const sorted = [...inProgress].sort((a,b)=>{
                const da = getDelivery(a.id); const db = getDelivery(b.id);
                const daysA = da&&da.dueDate&&!da.delivered ? daysUntil(da.dueDate) : 9999;
                const daysB = db&&db.dueDate&&!db.delivered ? daysUntil(db.dueDate) : 9999;
                if(daysA!==daysB) return daysA-daysB;
                return getProgress(a)-getProgress(b);
              });
              const urgent = sorted.filter(p=>{ const d=getDelivery(p.id); const days=d&&d.dueDate&&!d.delivered?daysUntil(d.dueDate):null; return days!==null&&days<=7; });
              return(
                <>
                  {urgent.length>0&&(
                    <div style={{background:T.redBg,border:`1.5px solid ${T.red}33`,borderRadius:14,padding:"14px 18px",marginBottom:22,display:"flex",alignItems:"center",gap:10}}>
                      <span style={{fontSize:22}}>🎯</span>
                      <div>
                        <div style={{fontSize:13,fontWeight:800,color:T.red,letterSpacing:"0.07em"}}>FOCUS — {urgent.length} CONSEGN{urgent.length===1?"A":"E"} ENTRO 7 GIORNI</div>
                        <div style={{fontSize:13,color:T.textSub,marginTop:2}}>{urgent.map(p=>p.name).join(" · ")}</div>
                      </div>
                    </div>
                  )}
                  {sorted.length>0&&(
                    <>
                      <div style={{fontSize:13,color:T.textSub,fontWeight:700,letterSpacing:"0.06em",marginBottom:14}}>IN CORSO — {sorted.length} · ordinati per priorità</div>
                      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill, minmax(320px, 1fr))",gap:14,marginBottom:32}}>
                        {sorted.map(p=>(
                          <ProjectCard key={p.id} project={p}
                            onClick={()=>setSelectedProjectId(p.id)}
                            onDelete={deleteProject} onArchive={archiveProject}
                            delivery={getDelivery(p.id)}
                            onSetDelivery={setDelivery}/>
                        ))}
                      </div>
                    </>
                  )}
                  {completed.length>0&&(
                    <>
                      <div style={{fontSize:13,color:T.textSub,fontWeight:700,letterSpacing:"0.06em",marginBottom:14}}>COMPLETATI — {completed.length}</div>
                      <div style={{display:"grid",gridTemplateColumns:"repeat(auto-fill, minmax(320px, 1fr))",gap:14}}>
                        {completed.map(p=>(
                          <ProjectCard key={p.id} project={p}
                            onClick={()=>setSelectedProjectId(p.id)}
                            onDelete={deleteProject} onArchive={archiveProject}
                            delivery={getDelivery(p.id)}
                            onSetDelivery={setDelivery}/>
                        ))}
                      </div>
                    </>
                  )}
                </>
              );
            })()}
          </div>
        )}
        </div>
        <QuickTasksSidebar collapsed={sidebarCollapsed} onToggleCollapse={()=>setSidebarCollapsed(v=>!v)}/>
      </div>

      {showNewProject&&(
        <NewProjectModal
          onClose={()=>{setShowNewProject(false);setPreselectedTemplate(null);}}
          onCreate={p=>{addProject(p);setShowNewProject(false);setPreselectedTemplate(null);}}
          templates={templates}
          preselectedTemplate={preselectedTemplate}/>
      )}
    </div>
  );
}