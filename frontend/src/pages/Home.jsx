// Home.jsx — Cruscotto turno (redesign V2)
import { useState, useEffect, useRef } from 'react'
import React from 'react'
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

function fmtTimer(sec){
  if(sec==null||sec<0) return '—:——:——'
  const h=Math.floor(sec/3600), m=Math.floor((sec%3600)/60), s=sec%60
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
}

export default function Home(){
  const nav = useNavigate()
  const [projects,   setProjects]   = useState([])
  const [deliveries, setDeliveries] = useState([])
  const [pallet,     setPallet]     = useState([])
  const [setup,      setSetup]      = useState({})
  const [sessLive,   setSessLive]   = useState(null)
  const [tempiCiclo, setTempiCiclo] = useState({})
  const [tickSec,    setTickSec]    = useState(0)
  const [loading,    setLoading]    = useState(true)
  const [oreProgetto, setOreProgetto] = useState(null)  // ore storiche progetto corrente

  useEffect(()=>{
    const ac = new AbortController()
    const sig = ac.signal
    Promise.all([
      fetch('/api/progetti/', {signal:sig}).then(r=>r.ok?r.json():{projects:[]}),
      fetch('/api/progetti/deliveries', {signal:sig}).then(r=>r.ok?r.json():[]),
      fetch('/api/pallet/', {signal:sig}).then(r=>r.ok?r.json():{pallet:[]}),
      fetch('/api/progetti/analisi-setup/non-utilizzati', {signal:sig}).then(r=>r.ok?r.json():{}).catch(()=>({})),
    ]).then(([pd,del,pal,s])=>{
      if(sig.aborted) return
      setProjects((pd.projects||[]).filter(p=>!p.archived))
      setDeliveries(Array.isArray(del)?del:[])
      setPallet(pal.pallet||[])
      setSetup(s||{})
      setLoading(false)
    }).catch(e=>{ if(e.name!=='AbortError') setLoading(false) })
    const t=setInterval(()=>
      fetch('/api/pallet/').then(r=>r.ok?r.json():{pallet:[]}).then(d=>{ if(!sig.aborted) setPallet(d.pallet||[]) })
    ,15000)
    const fetchSessLive=()=>
      fetch('/api/report/sessione-live').then(r=>r.ok?r.json():null)
        .then(d=>{ if(!sig.aborted) setSessLive(d) }).catch(()=>{})
    fetchSessLive()
    const t2=setInterval(fetchSessLive,10000)
    const t3=setInterval(()=>setTickSec(s=>s+1),1000)
    const fetchTempiCiclo=()=>
      fetch('/api/report/tempi-ciclo').then(r=>r.ok?r.json():null)
        .then(d=>{ if(!sig.aborted && d?.cicli) setTempiCiclo(d.cicli) }).catch(()=>{})
    fetchTempiCiclo()
    const t4=setInterval(fetchTempiCiclo,300000)
    // Refresh ore progetto ogni 5min (per aggiornarsi quando sessioni si chiudono)
    const refreshOreProgetto = () => { progettoCorrenteRef.current = null }
    const t5=setInterval(refreshOreProgetto, 300000)
    return()=>{ ac.abort(); clearInterval(t);clearInterval(t2);clearInterval(t3);clearInterval(t4);clearInterval(t5) }
  },[])

  // Fetch ore storiche progetto ogni volta che cambia il progetto in lavorazione
  const progettoCorrenteRef = useRef(null)
  useEffect(()=>{
    const palletLavNow = pallet.find(p=>(p.stato||'').toLowerCase().replace('_',' ')==='in lavorazione')
    const progNow = palletLavNow ? projects.find(p=>p.id===palletLavNow.progetto_id) : null
    if(!progNow) { setOreProgetto(null); progettoCorrenteRef.current = null; return }
    const chiave = progNow.id
    if(chiave === progettoCorrenteRef.current) return  // stesso progetto, già caricato
    // Progetto cambiato — reset e fetch
    progettoCorrenteRef.current = chiave
    setOreProgetto(null)  // reset mentre carica
    const params = new URLSearchParams({
      progetto: progNow.name,
      project_id: progNow.id,
    })
    fetch(`/api/report/ore-progetto?${params}`)
      .then(r=>r.ok?r.json():null)
      .then(d=>{ if(d) setOreProgetto(d) })
      .catch(()=>{})
  },[pallet, projects])

  const now    = new Date()
  const DAYS   = ['Domenica','Lunedì','Martedì','Mercoledì','Giovedì','Venerdì','Sabato']
  const MONTHS = ['Gennaio','Febbraio','Marzo','Aprile','Maggio','Giugno','Luglio','Agosto','Settembre','Ottobre','Novembre','Dicembre']
  const dayLabel = `${DAYS[now.getDay()]} ${now.getDate()} ${MONTHS[now.getMonth()]} ${now.getFullYear()}`

  // ── Helpers ──────────────────────────────────────────────────────────────
  function palletInfo(num){
    const pal=pallet.find(p=>p.numero===num)
    if(!pal?.progetto_id) return null
    const proj=projects.find(p=>p.id===pal.progetto_id)
    if(!proj) return null
    const pgms=(proj.steps||[]).flatMap(s=>(s.tasks||[])
      .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
      .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm')))
    const tot=pgms.length
    const done=pgms.filter(p=>p.stato==='completato').length
    const pct=tot?Math.round(done/tot*100):0
    return {proj,pal,pct,done,tot,
      daFare:pgms.filter(p=>p.stato==='da_fare').length,
      inMac:pgms.filter(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato)).length}
  }

  function palletColors(num){
    const pal=pallet.find(p=>p.numero===num)
    const stato=(pal?.stato||'').toLowerCase().replace('_',' ')
    const info=palletInfo(num)
    // Controlla se ha scadenza critica
    const proj=info?.proj
    const del=proj?deliveries.find(d=>d.projectId===proj.id):null
    const days=del?.dueDate&&!del.delivered?daysUntil(del.dueDate):null
    const isScaduto=days!==null&&days<=0
    if(stato==='in lavorazione') return {bg:'#dbeafe',fg:'#0d2d5e',border:'#1D5FAD',label:'LIVE',accent:'#1D5FAD'}
    if(info?.pct>=100||stato==='finito') return {bg:'#dcfce7',fg:'#14532d',border:'#16a34a',label:'FINITO',accent:'#16a34a'}
    if(isScaduto) return {bg:'#fef2f2',fg:'#991b1b',border:'#ef4444',label:'SCADUTO',accent:'#ef4444'}
    if(info) return {bg:'#fefce8',fg:'#854d0e',border:'#eab308',label:'GREZZO',accent:'#eab308'}
    return {bg:'#f8fafc',fg:'#94a3b8',border:'#e2e8f0',label:'VUOTO',accent:null}
  }

  // ── Timer live ───────────────────────────────────────────────────────────
  void tickSec
  const durataSessioneLive=(()=>{
    if(!sessLive?.attiva||!sessLive?.inizio_sessione) return null
    try{ const d=Math.floor((Date.now()-new Date(sessLive.inizio_sessione).getTime())/1000); return d>=0?d:null }catch{return null}
  })()
  const durataProgrammaLive=(()=>{
    if(!sessLive?.attiva||!sessLive?.inizio_programma) return null
    try{ const d=Math.floor((Date.now()-new Date(sessLive.inizio_programma).getTime())/1000); return d>=0?d:null }catch{return null}
  })()

  // ── Pallet attivo ────────────────────────────────────────────────────────
  const palletLav   = pallet.find(p=>(p.stato||'').toLowerCase().replace('_',' ')==='in lavorazione')
  const progettoLav = palletLav?projects.find(p=>p.id===palletLav.progetto_id):null
  const lavInfo     = progettoLav?palletInfo(palletLav.numero):null
  const sessMatch   = sessLive?.attiva&&sessLive?.pallet===palletLav?.numero

  // ── ETA programma corrente + fine pallet ─────────────────────────────────
  // Gerarchia per ogni programma:
  //   1. Ciclo reale storico (tempiCiclo, ≥2 campioni) — più accurato
  //   2. tempoStimato CAM (minuti, già nel progetto)   — preciso a priori
  //   3. Media del programma corrente                  — fallback grezzo
  const etaCalc = (()=>{
    if(!sessMatch||!sessLive?.programma_corrente||!lavInfo) return null
    const fname = sessLive.programma_corrente.toUpperCase()
    const ciclo = tempiCiclo[fname]

    // Stima durata per un programma: ciclo reale > tempoStimato > fallback
    const stimaPgm = (pgm, fallbackSec) => {
      const fn = (pgm.filename||'').toUpperCase()
      const tc = tempiCiclo[fn]
      if (tc?.n >= 2) return tc.media_sec                       // 1. reale
      if (pgm.tempoStimato) return parseInt(pgm.tempoStimato)*60 // 2. CAM (minuti)
      return fallbackSec || 0                                    // 3. fallback
    }

    // Fallback globale: media del programma corrente (se disponibile)
    const fallback = ciclo?.n >= 2 ? ciclo.media_sec : null

    // Tempo del programma corrente: ciclo reale > tempoStimato CAM > media globale cicli
    const tempoCorrente = ciclo?.n >= 2
      ? ciclo.media_sec
      : (() => {
          // Cerca tempoStimato del programma corrente nel progetto
          const pgmCorrente = progettoLav
            ? (progettoLav.steps||[]).flatMap(s=>(s.tasks||[])
                .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
                .flatMap(t=>(t.programs||[])))
              .find(p=>(p.filename||'').toUpperCase()===fname)
            : null
          if (pgmCorrente?.tempoStimato) return parseInt(pgmCorrente.tempoStimato)*60
          // Fallback: media di tutti i cicli noti (almeno mostra qualcosa)
          const tuttiCicli = Object.values(tempiCiclo).filter(c=>c.n>=2)
          if (tuttiCicli.length > 0) {
            const mediaGlobale = Math.round(
              tuttiCicli.reduce((a,c)=>a+c.media_sec,0) / tuttiCicli.length
            )
            return mediaGlobale
          }
          return null
        })()
    if (!tempoCorrente) return null

    // Tempo rimanente nel programma corrente
    const elapsed = durataProgrammaLive || 0
    const rimPgm  = Math.max(0, tempoCorrente - elapsed)

    // Tutti i programmi del pallet (solo fresatura, esclusi IPM)
    const allPgmLav = progettoLav
      ? (progettoLav.steps||[]).flatMap(s=>(s.tasks||[])
          .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
          .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm')))
      : []

    // Programmi successivi a quello corrente non ancora completati
    const idxCorrente = allPgmLav.findIndex(p=>
      (p.filename||'').toUpperCase() === fname)
    const pgmSuccessivi = (idxCorrente >= 0
      ? allPgmLav.slice(idxCorrente+1)
      : allPgmLav
    ).filter(p => p.stato !== 'completato')

    // Somma ETA successivi con gerarchia
    const secSuccessivi = pgmSuccessivi.reduce((acc, p) =>
      acc + stimaPgm(p, fallback || tempoCorrente), 0)

    const totSec = rimPgm + secSuccessivi

    // Totale progetto/pallet — tutti i programmi (completati + in corso + da fare)
    // Serve per mostrare "X/Y" e la durata totale del pallet
    const secTotalePallet = allPgmLav.reduce((acc, p) => {
      // Per i completati usa la durata reale se disponibile
      if (p.stato === 'completato') {
        const fn = (p.filename||'').toUpperCase()
        const tc = tempiCiclo[fn]
        return acc + (tc?.n >= 2 ? tc.media_sec : stimaPgm(p, fallback || tempoCorrente))
      }
      return acc + stimaPgm(p, fallback || tempoCorrente)
    }, 0)

    const nTotali     = allPgmLav.length
    const nCompletati = allPgmLav.filter(p=>p.stato==='completato').length
    const nRimanenti  = pgmSuccessivi.length + 1  // +1 per il corrente

    // Fonte usata (per label informativa)
    const fontePgm = ciclo?.n >= 2 ? `${ciclo.n} cicli reali`
                   : progettoLav ? 'stima CAM'
                   : 'media globale'

    const fmtEta = (sec) => {
      if (sec < 60)   return `<1 min`
      if (sec < 3600) return `~${Math.round(sec/60)} min`
      const h = Math.floor(sec/3600), m = Math.round((sec%3600)/60)
      return m > 0 ? `~${h}h ${m}m` : `~${h}h`
    }

    return {
      rimPgm,
      totSec,
      secTotalePallet,
      nTotali,
      nCompletati,
      nRimanenti,
      etaFmtPgm:    fmtEta(rimPgm),
      etaFmtPallet: fmtEta(totSec),
      etaFmtTotale: fmtEta(secTotalePallet),
      nCampioni:    ciclo?.n || 0,
      fontePgm,
      deviazione:   ciclo?.std_sec || 0,
      anomalia:     durataProgrammaLive != null && (ciclo?.std_sec||0) > 0
                    && durataProgrammaLive > (tempoCorrente + 2*(ciclo?.std_sec||0)),
    }
  })()

  // ── Metriche ─────────────────────────────────────────────────────────────
  const allPgm=projects.flatMap(p=>(p.steps||[]).flatMap(s=>(s.tasks||[])
    .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
    .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm'))))
  const daFareTot=allPgm.filter(p=>p.stato==='da_fare').length
  const inMacTot =allPgm.filter(p=>['in_macchina','in_main','in_lavorazione'].includes(p.stato)).length
  const oggiStr  =now.toDateString()
  const completatiOggi=allPgm.filter(p=>{
    if(p.stato!=='completato'||!p.tempoFine) return false
    try{ const parts=p.tempoFine.split(' '); const dp=parts[0].split('/'); return new Date(dp[2],dp[1]-1,dp[0]).toDateString()===oggiStr }catch{return false}
  }).length

  // ── Scadenze ─────────────────────────────────────────────────────────────
  const conScadenza=projects
    .map(p=>({p,d:deliveries.find(d=>d.projectId===p.id),pNum:pallet.find(x=>x.progetto_id===p.id)?.numero}))
    .filter(({d})=>d?.dueDate&&!d.delivered)
    .map(({p,d,pNum})=>({p,days:daysUntil(d.dueDate),pNum}))
    .sort((a,b)=>a.days-b.days)
  const critici=conScadenza.filter(x=>x.days!==null&&x.days<=0).length
  const scadutiCount=conScadenza.filter(x=>x.days!==null&&x.days<0).length

  // ── Utensili problemi ────────────────────────────────────────────────────
  const utensiliProblema=(()=>{
    const map={}
    ;(setup.non_utilizzati||[]).filter(u=>u.provenienza==='richiesto_da_progetto').forEach(u=>{
      map[u.alias]={alias:u.alias,tipo:'mancante',label:'MANCANTE',color:'#dc2626',bg:'#fef2f2',border:'#fca5a5',detail:(u.progetti||[]).map(r=>r.progetto).join(', ')}
    })
    ;(setup.da_montare||[]).forEach(u=>{
      if(!map[u.alias]) map[u.alias]={alias:u.alias,tipo:'da_montare',label:'DA MONTARE',color:'#d97706',bg:'#fffbeb',border:'#fcd34d',detail:`pos. ${u.posizione||'—'}`}
    })
    ;(setup.fin_vita||[]).forEach(u=>{
      const pct=typeof u.life_percent==='number'?u.life_percent:null
      if(!map[u.alias]) map[u.alias]={alias:u.alias,tipo:'fin_vita',label:pct!==null?`${pct.toFixed(0)}%`:'FINE VITA',color:'#c2410c',bg:'#fff7ed',border:'#fdba74',detail:`pos. ${u.posizione||'—'}`}
    })
    ;(setup.previsione_vita?.utensili_critici||[]).forEach(u=>{
      if(!map[u.alias]) map[u.alias]={alias:u.alias,tipo:'rischio',label:`pgm ${u.programma_critico||'?'}`,color:'#7c3aed',bg:'#f5f3ff',border:'#c4b5fd',detail:u.progetto||''}
    })
    return Object.values(map).sort((a,b)=>({mancante:0,da_montare:1,fin_vita:2,rischio:3}[a.tipo]||9)-({mancante:0,da_montare:1,fin_vita:2,rischio:3}[b.tipo]||9))
  })()

  if(loading) return(
    <div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center',
      background:'#f0f4f8',fontSize:14,color:'#94a3b8'}}>Caricamento…</div>
  )

  return(
    <div style={{flex:1,overflow:'hidden',background:'#f0f4f8',fontFamily:'var(--font-display)',display:'flex',flexDirection:'column',height:'100%'}}>

      {/* ── TOPBAR ─────────────────────────────────────────────────────── */}
      <div style={{background:'#fff',borderBottom:'1px solid #e2e8f0',padding:'8px 20px',
        display:'flex',alignItems:'center',gap:16,flexShrink:0}}>
        <span style={{fontSize:15,fontWeight:800,color:'#0d2d5e'}}>Cruscotto turno</span>
        <span style={{fontSize:12,color:'#94a3b8'}}>{dayLabel}</span>
        {/* Banner stato macchina */}
        {sessLive?.attiva&&sessLive?.programma_corrente&&(
          <div style={{marginLeft:'auto',background:'#dbeafe',border:'1px solid #1D5FAD',
            borderRadius:8,padding:'5px 14px',display:'flex',alignItems:'center',gap:8}}>
            <span style={{width:8,height:8,borderRadius:'50%',background:'#1D5FAD',
              flexShrink:0,display:'inline-block',animation:'pulse-dot 1.5s ease-in-out infinite'}}/>
            <span style={{fontSize:11,fontWeight:800,color:'#0d2d5e',letterSpacing:'0.05em'}}>IN ESECUZIONE</span>
            <span style={{fontSize:12,fontWeight:700,color:'#1D5FAD',fontFamily:'monospace'}}>
              {sessLive.programma_corrente.replace('.MPF','').replace('.mpf','')}
            </span>
          </div>
        )}
        {!sessLive?.attiva&&(sessLive?.fermo_sec_giornaliero||0)>0&&(
          <div style={{marginLeft:'auto',background:'#fef2f2',border:'1px solid #fca5a5',
            borderRadius:8,padding:'5px 14px',display:'flex',alignItems:'center',gap:8}}>
            <span style={{width:8,height:8,borderRadius:'50%',background:'#ef4444',flexShrink:0,display:'inline-block'}}/>
            <span style={{fontSize:11,fontWeight:800,color:'#dc2626',letterSpacing:'0.05em'}}>MACCHINA FERMA</span>
          </div>
        )}
      </div>
      <style>{`@keyframes pulse-dot{0%,100%{opacity:1;transform:scale(1)}50%{opacity:.5;transform:scale(.85)}}`}</style>

      {/* ── BODY: col-main | col-side ──────────────────────────────────── */}
      <div style={{flex:1,display:'grid',gridTemplateColumns:'1fr 280px',gap:12,
        padding:'12px 18px',alignItems:'stretch',overflow:'hidden',minHeight:0}}>

        {/* ══ COL MAIN ══════════════════════════════════════════════════ */}
        <div style={{display:'flex',flexDirection:'column',gap:10,overflowY:'auto',minHeight:0}}>

          {/* ── CARD PROGETTO ATTIVO ────────────────────────────────── */}
          {lavInfo?(
            <div style={{background:'#f0f7ff',border:'1.5px solid #1D5FAD',borderRadius:12,padding:'12px 16px',flexShrink:0}}>
              {/* Header */}
              <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
                <div style={{width:11,height:11,borderRadius:2,
                  background:lavInfo.proj.color||'#1D5FAD',flexShrink:0}}/>
                <span style={{fontSize:16,fontWeight:800,color:'#0d2d5e',flex:1,
                  overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                  {lavInfo.proj.name}
                </span>
                <span style={{fontSize:11,fontWeight:700,color:'#1D5FAD',
                  background:'#dbeafe',padding:'3px 10px',borderRadius:6}}>
                  Pallet {palletLav.numero}
                </span>
              </div>

              {/* Timers — 3 colonne: sessione | programma | ore pallet */}
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr 1fr',gap:8,marginBottom:10}}>

                {/* Timer 1: Sessione pallet (da quando è partito oggi) */}
                <div style={{background:'#fff',borderRadius:9,padding:'6px 10px',
                  border:'1px solid #bfdbfe',textAlign:'center'}}>
                  <div style={{fontSize:10,fontWeight:700,color:'#1D5FAD',letterSpacing:'0.07em',
                    textTransform:'uppercase',marginBottom:5}}>Sessione pallet</div>
                  <div style={{fontSize:26,fontWeight:900,color:'#0d2d5e',fontFamily:'monospace',lineHeight:1}}>
                    {sessMatch?fmtTimer(durataSessioneLive):'—:——:——'}
                  </div>
                  {sessMatch&&sessLive?.inizio_sessione&&(
                    <div style={{fontSize:10,color:'#64748b',marginTop:4}}>
                      dal {sessLive.inizio_sessione.slice(11,16)}
                    </div>
                  )}
                </div>

                {/* Timer 2: Programma corrente */}
                <div style={{background:'#fff',borderRadius:9,padding:'8px 10px',
                  border: sessMatch&&sessLive?.anomalia_ciclo ? '1.5px solid #ef4444' : sessMatch&&sessLive?.in_pausa ? '1.5px solid #f59e0b' : '1px solid #e2e8f0',
                  textAlign:'center',
                  background: sessMatch&&sessLive?.anomalia_ciclo ? '#fef2f2' : sessMatch&&sessLive?.in_pausa ? '#fffbeb' : '#fff' }}>
                  <div style={{fontSize:10,fontWeight:700,
                    color: sessMatch&&sessLive?.anomalia_ciclo ? '#dc2626' : sessMatch&&sessLive?.in_pausa ? '#92400e' : '#64748b',
                    letterSpacing:'0.07em',textTransform:'uppercase',marginBottom:5,
                    display:'flex',alignItems:'center',justifyContent:'center',gap:5}}>
                    {sessMatch&&sessLive?.anomalia_ciclo&&(
                      <span style={{fontSize:9,fontWeight:800,color:'#dc2626',
                        background:'#fef2f2',padding:'1px 5px',borderRadius:3,
                        border:'1px solid #fca5a5'}}>LUNGO</span>
                    )}
                    {sessMatch&&sessLive?.in_pausa&&!sessLive?.anomalia_ciclo&&(
                      <span style={{fontSize:9,fontWeight:800,color:'#92400e',
                        background:'#fef3c7',padding:'1px 5px',borderRadius:3,
                        border:'1px solid #fcd34d'}}>PAUSA</span>
                    )}
                    Programma corrente
                  </div>
                  <div style={{fontSize:26,fontWeight:900,fontFamily:'monospace',lineHeight:1,
                    color: sessMatch&&sessLive?.anomalia_ciclo ? '#dc2626' : sessMatch&&sessLive?.in_pausa ? '#92400e' : '#475569'}}>
                    {sessMatch&&durataProgrammaLive!=null?fmtTimer(durataProgrammaLive):'—:——:——'}
                  </div>
                  {sessMatch&&sessLive?.programma_corrente&&(
                    <div style={{fontSize:10,color:'#64748b',marginTop:4,fontFamily:'monospace',
                      overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                      {sessLive.programma_corrente.replace('.MPF','').replace('.mpf','')}
                    </div>
                  )}
                  {sessMatch&&sessLive?.ciclo_stats&&(
                    <div style={{fontSize:9,color:'#94a3b8',marginTop:3}}>
                      media: {fmtTimer(sessLive.ciclo_stats.media_sec)} ({sessLive.ciclo_stats.n} cicli)
                    </div>
                  )}
                </div>

                {/* Timer 3: Ore totali progetto (storico chiuso + sessione live) */}
                {(()=>{
                  // Ore storiche: solo sessioni CHIUSE (fine != null) e non-zero
                  // Il backend esclude sessioni aperte e durata=0 per evitare doppio conteggio
                  const secStorico = oreProgetto?.ore_sec || 0
                  // Sessione corrente APERTA: usa sessLive.durata_sec calcolato dal backend
                  // come somma dei programmi eseguiti in questa sessione.
                  // NON usare durataSessioneLive (= now - inizio_sessione) che gonfia il valore
                  // se la sessione è rimasta aperta nel log mentre la macchina era ferma.
                  // Aggiunge tickSec secondi dall'ultimo refresh per far scorrere live.
                  const secSessioneBase = sessMatch ? (sessLive?.durata_sec || 0) : 0
                  // tickSec si azzera ad ogni fetch sessione-live (ogni 10s) — no drift
                  const secSessioneAperta = secSessioneBase > 0 && sessLive?.attiva && !sessLive?.in_pausa
                    ? secSessioneBase + (tickSec % 10)
                    : secSessioneBase
                  const secTot = secStorico + secSessioneAperta
                  const hh = Math.floor(secTot/3600)
                  const mm = Math.floor((secTot%3600)/60)
                  const ss = secTot % 60
                  const timerStr = `${String(hh).padStart(2,'0')}:${String(mm).padStart(2,'0')}:${String(ss).padStart(2,'0')}`
                  const nSessioni = oreProgetto?.n_sessioni || 0
                  const primaData = oreProgetto?.prima_data
                  return (
                    <div style={{background:'#fff',borderRadius:9,padding:'6px 10px',
                      border:'1px solid #bbf7d0',textAlign:'center'}}>
                      <div style={{fontSize:10,fontWeight:700,color:'#15803d',letterSpacing:'0.07em',
                        textTransform:'uppercase',marginBottom:4}}>Ore progetto</div>
                      <div style={{fontSize:26,fontWeight:900,color:'#166534',fontFamily:'monospace',lineHeight:1}}>
                        {secTot > 0 ? timerStr : '—:——:——'}
                      </div>
                      {secTot > 0 && (
                        <div style={{fontSize:9,color:'#64748b',marginTop:3}}>
                          {nSessioni > 0 ? `${nSessioni} sess.` : ''}
                          {primaData && nSessioni > 1 ? ` · dal ${primaData}` : ''}
                        </div>
                      )}
                    </div>
                  )
                })()}
              </div>

              {/* Barra */}
              <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:10}}>
                <div style={{flex:1,height:8,background:'rgba(29,95,173,0.15)',borderRadius:4,overflow:'hidden'}}>
                  <div style={{height:'100%',width:`${lavInfo.pct}%`,
                    background:lavInfo.proj.color||'#1D5FAD',borderRadius:4,transition:'width 0.4s'}}/>
                </div>
                <span style={{fontSize:14,fontWeight:800,color:'#0d2d5e',minWidth:38,textAlign:'right'}}>
                  {lavInfo.pct}%
                </span>
              </div>

              {/* Stats + utensile */}
              <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
                <span style={{fontSize:12,color:'#64748b'}}>
                  <b style={{color:'#16a34a'}}>{lavInfo.done}</b> completati &nbsp;·&nbsp;
                  <b style={{color:'#1D5FAD'}}>{lavInfo.inMac}</b> in corso &nbsp;·&nbsp;
                  <b style={{color:'#94a3b8'}}>{lavInfo.daFare}</b> da fare
                </span>
                {sessMatch&&sessLive?.utensile&&(
                  <span style={{marginLeft:'auto',fontSize:11,fontWeight:700,color:'#0d2d5e',
                    background:'#eff6ff',padding:'3px 10px',borderRadius:6,fontFamily:'monospace',flexShrink:0}}>
                    {sessLive.utensile}
                    {sessLive.t_number&&(
                      <span style={{color:'#1D5FAD',marginLeft:8}}>T{sessLive.t_number}</span>
                    )}
                  </span>
                )}
              </div>

              {/* ETA — riga semplice */}
              {etaCalc&&(
                <div style={{display:'flex',alignItems:'center',gap:8,
                  marginTop:6,padding:'7px 10px',borderRadius:8,flexWrap:'wrap',
                  background: etaCalc.anomalia ? '#fef2f2' : '#f0f7ff',
                  border: `1px solid ${etaCalc.anomalia ? '#fca5a5' : '#bfdbfe'}`}}>
                  {etaCalc.anomalia&&(
                    <span style={{fontSize:10,fontWeight:800,color:'#dc2626',
                      background:'#fff',padding:'2px 7px',borderRadius:4,
                      border:'1px solid #fca5a5',flexShrink:0}}>CICLO LUNGO</span>
                  )}
                  <span style={{fontSize:11,color: etaCalc.anomalia?'#dc2626':'#1D5FAD'}}>
                    pgm corrente: <b>{etaCalc.etaFmtPgm}</b>
                  </span>
                  <span style={{fontSize:11,color:'#64748b'}}>·</span>
                  <span style={{fontSize:11,color:'#0d2d5e'}}>
                    fine pallet: <b>{etaCalc.etaFmtPallet}</b>
                  </span>
                  <span style={{marginLeft:'auto',fontSize:10,color:'#94a3b8',fontStyle:'italic',flexShrink:0}}>
                    {etaCalc.nCampioni >= 2 ? `da ${etaCalc.nCampioni} cicli reali`
                     : etaCalc.fontePgm === 'media globale' ? 'media globale'
                     : 'da tempi CAM'}
                  </span>
                </div>
              )}
            </div>
          ):(
            <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,
              padding:'24px',textAlign:'center',color:'#94a3b8',fontSize:13}}>
              Nessun pallet in lavorazione
            </div>
          )}

          {/* ── PALLET GRID ─────────────────────────────────────────── */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'12px 16px',flexShrink:0}}>
            <div style={{fontSize:10,fontWeight:800,letterSpacing:'0.1em',color:'#64748b',
              textTransform:'uppercase',marginBottom:8}}>Pallet macchina</div>
            <div style={{display:'grid',gridTemplateColumns:'repeat(6,1fr)',gap:8}}>
              {[1,2,3,4,5,6].map(n=>{
                const info=palletInfo(n)
                const c=palletColors(n)
                const isLav=c.label==='LIVE'
                const isVuoto=c.label==='VUOTO'
                return(
                  <div key={n}
                    onClick={info?()=>nav('/progetti',{state:{openId:info.proj.id}}):undefined}
                    style={{background:c.bg,border:`1.5px solid ${c.border}`,borderRadius:10,
                      padding:'14px 14px',cursor:info?'pointer':'default',
                      minHeight:130,display:'flex',flexDirection:'column',gap:6,
                      transition:'transform 0.12s, box-shadow 0.12s',position:'relative'}}
                    onMouseEnter={e=>{if(info){e.currentTarget.style.transform='translateY(-2px)';e.currentTarget.style.boxShadow='0 4px 14px rgba(0,0,0,.08)'}}}
                    onMouseLeave={e=>{e.currentTarget.style.transform='none';e.currentTarget.style.boxShadow='none'}}>

                    {/* Numero + badge stato */}
                    <div style={{display:'flex',justifyContent:'space-between',alignItems:'flex-start'}}>
                      <span style={{fontSize:30,fontWeight:900,color:c.fg,lineHeight:1}}>P{n}</span>
                      {!isVuoto&&(
                        <span style={{fontSize:9,fontWeight:800,color:c.accent||c.fg,
                          background:'#fff',padding:'2px 6px',borderRadius:4,
                          border:`1px solid ${c.border}`,letterSpacing:'0.05em',lineHeight:1.4}}>
                          {c.label}
                        </span>
                      )}
                    </div>

                    {info?(
                      <>
                        <div style={{fontSize:12,fontWeight:800,color:c.fg,
                          overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                          {info.proj.name}
                        </div>
                        <div style={{height:4,background:'rgba(0,0,0,0.1)',borderRadius:2,overflow:'hidden'}}>
                          <div style={{height:'100%',width:`${info.pct}%`,
                            background:c.accent||info.proj.color||'#1D5FAD',borderRadius:2}}/>
                        </div>
                        <div style={{display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                          <span style={{fontSize:11,color:c.fg,opacity:0.7}}>{info.done}/{info.tot} pgm</span>
                          <span style={{fontSize:13,fontWeight:800,color:c.fg}}>{info.pct}%</span>
                        </div>
                      </>
                    ):(
                      <div style={{fontSize:11,fontWeight:600,color:'#cbd5e1',marginTop:'auto'}}>Vuoto</div>
                    )}
                  </div>
                )
              })}
            </div>
          </div>

          {/* ── PROGRAMMI + UTENSILI affiancati ───────────────── */}
          <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:10}}>
          {/* ── PROGRAMMI ATTIVI DEL PROGETTO IN LAVORAZIONE ─────────── */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'10px 16px'}}>
            <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:8}}>
              <span style={{fontSize:10,fontWeight:800,letterSpacing:'0.1em',color:'#64748b',textTransform:'uppercase'}}>
                Programmi attivi
              </span>
              {progettoLav&&(
                <span style={{fontSize:11,color:'#1D5FAD',fontWeight:700,
                  fontFamily:'monospace'}}>{progettoLav.name}</span>
              )}
            </div>
            {!progettoLav ? (
              <div style={{color:'#94a3b8',fontSize:13,fontStyle:'italic'}}>Nessun progetto in lavorazione</div>
            ) : (()=>{
              // Tutti i programmi fresatura del progetto (esclusi IPM)
              const pgmFresatura = (progettoLav.steps||[]).flatMap(s=>
                (s.tasks||[]).filter(t=>t.text?.trim().toLowerCase()==='fresatura')
                  .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm'))
              )
              const attivi = pgmFresatura.filter(p=>
                ['in_lavorazione','in_main','in_macchina'].includes(p.stato)
              )
              const corrente = sessLive?.programma_corrente?.toUpperCase().replace('.MPF','')

              if(attivi.length===0) return (
                <div style={{color:'#94a3b8',fontSize:13,fontStyle:'italic'}}>
                  Nessun programma in_main o in_lavorazione
                </div>
              )

              return (
                <div style={{display:'flex',flexDirection:'column',gap:3}}>
                  {attivi.map((pg,i)=>{
                    const fn = (pg.filename||'').toUpperCase().replace('.MPF','')
                    const isCorr  = corrente && fn === corrente.replace('.MPF','')
                    const isInLav = pg.stato==='in_lavorazione'
                    // Estrai numero programma dal filename (es. 4297_005_01_53 → 53)
                    const numMatch = (pg.filename||'').match(/[_-](\d+)\.MPF$/i)
                    const numPgm = numMatch ? numMatch[1] : ''
                    return (
                      <div key={pg.filename||i} style={{
                        display:'flex',alignItems:'center',gap:8,
                        padding:'4px 8px',borderRadius:6,userSelect:'none',
                        background: isCorr ? '#eff6ff' : isInLav ? '#f0fdf4' : 'transparent',
                        border: `1px solid ${isCorr ? '#1D5FAD' : isInLav ? '#bbf7d0' : '#e2e8f0'}`,
                      }}>
                        {/* Badge ⚙/📋 come nella Coda */}
                        <span style={{
                          fontSize:9,fontWeight:800,padding:'1px 4px',borderRadius:3,flexShrink:0,
                          background: isCorr ? '#1D5FAD' : isInLav ? '#1D5FAD' : '#fef3c7',
                          color: isCorr||isInLav ? '#fff' : '#92400e'
                        }}>{isCorr||isInLav ? '⚙' : '📋'}</span>
                        {/* Numero programma */}
                        {numPgm&&(
                          <span style={{fontSize:11,fontWeight:700,color:'#0d2d5e',
                            fontFamily:'monospace',minWidth:24,flexShrink:0}}>{numPgm}</span>
                        )}
                        {/* Utensile */}
                        <span style={{fontSize:11,fontFamily:'monospace',color:'#1e293b',
                          flex:1,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                          {pg.utensile||pg.firstTool||'—'}
                        </span>
                        {/* Filename */}
                        <span style={{fontSize:10,color:'#94a3b8',fontFamily:'monospace',
                          flexShrink:0,maxWidth:120,overflow:'hidden',
                          textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                          {(pg.filename||'').replace('.MPF','').replace('.mpf','')}
                        </span>
                        {/* Tempo stimato */}
                        {pg.tempoStimato&&(
                          <span style={{fontSize:10,color:'#475569',flexShrink:0}}>
                            ⏱{pg.tempoStimato}m
                          </span>
                        )}
                      </div>
                    )
                  })}
                </div>
              )
            })()}
          </div>

          {/* ── UTENSILI ────────────────────────────────────────────── */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'10px 16px'}}>
            <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:8}}>
              <span style={{fontSize:10,fontWeight:800,letterSpacing:'0.1em',color:'#64748b',textTransform:'uppercase'}}>
                Utensili — attenzione
              </span>
              {utensiliProblema.length>0?(
                <span style={{fontSize:10,fontWeight:800,color:'#dc2626',
                  background:'#fef2f2',padding:'2px 8px',borderRadius:8}}>
                  {utensiliProblema.length}
                </span>
              ):(
                <span style={{fontSize:11,color:'#94a3b8'}}>— in attesa dati</span>
              )}
            </div>
            {utensiliProblema.length===0?(
              <div style={{color:'#22c55e',fontSize:13,fontWeight:600}}>✓ Nessun problema rilevato</div>
            ):(
              <div style={{display:'flex',flexDirection:'column',gap:5}}>
                {utensiliProblema.map(u=>(
                  <div key={u.alias}
                    style={{display:'flex',alignItems:'center',gap:10,
                      background:u.bg,border:`1px solid ${u.border}`,
                      borderRadius:8,padding:'6px 10px'}}>
                    <span style={{fontSize:10,fontWeight:800,color:u.color,
                      background:'#fff',padding:'2px 8px',borderRadius:4,
                      border:`1px solid ${u.border}`,flexShrink:0,
                      minWidth:68,textAlign:'center'}}>{u.label}</span>
                    <span style={{fontSize:12,fontWeight:700,color:'#1e293b',
                      fontFamily:'monospace',flex:1,
                      overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{u.alias}</span>
                    {u.detail&&<span style={{fontSize:11,color:u.color,opacity:0.8,
                      flexShrink:0,maxWidth:160,overflow:'hidden',
                      textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{u.detail}</span>}
                  </div>
                ))}
              </div>
            )}
          </div>

          </div>
        </div>{/* fine col-main */}

        {/* ══ COL SIDE ═══════════════════════════════════════════════ */}
        <div style={{display:'flex',flexDirection:'column',gap:8,overflowY:'auto',minHeight:0}}>
          <div style={{fontSize:10,fontWeight:800,letterSpacing:'0.1em',color:'#64748b',textTransform:'uppercase'}}>
            Metriche turno
          </div>

          {/* Da fare con % completamento */}
          {(()=>{
            const totale = allPgm.length
            const completatiTot = allPgm.filter(p=>p.stato==='completato').length
            const pctTot = totale ? Math.round(completatiTot/totale*100) : 0
            return (
              <div style={{background:'#eff6ff',borderRadius:10,padding:'12px 16px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:2}}>
                  <div style={{fontSize:32,fontWeight:900,color:'#0d2d5e',lineHeight:1}}>{daFareTot}</div>
                  <div style={{fontSize:13,fontWeight:700,color:'#1D5FAD'}}>{pctTot}%</div>
                </div>
                <div style={{fontSize:12,fontWeight:700,color:'#0d2d5e',marginBottom:4}}>Da fare</div>
                <div style={{height:4,background:'#bfdbfe',borderRadius:2,overflow:'hidden',marginBottom:4}}>
                  <div style={{height:'100%',width:`${pctTot}%`,background:'#1D5FAD',borderRadius:2,transition:'width 0.4s'}}/>
                </div>
                <div style={{fontSize:10,color:'#1D5FAD',opacity:0.8}}>
                  {completatiTot}/{totale} pgm · {projects.length} lavori
                </div>
              </div>
            )
          })()}

          {/* In macchina con ritmo */}
          {(()=>{
            // Ritmo: completatiOggi / ore turno trascorse (stimiamo 8h turno dalle 06:00)
            const ora = now.getHours()
            const oreTurno = Math.max(0.5, ora >= 6 ? ora - 6 : ora + 18) // ore dall'inizio turno
            const ritmo = oreTurno > 0 ? (completatiOggi / oreTurno).toFixed(1) : '—'
            return (
              <div style={{background:'#dbeafe',borderRadius:10,padding:'12px 16px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:2}}>
                  <div style={{fontSize:32,fontWeight:900,color:'#1D5FAD',lineHeight:1}}>{inMacTot}</div>
                  {completatiOggi > 0 && <div style={{fontSize:12,fontWeight:700,color:'#1e40af'}}>~{ritmo}/h</div>}
                </div>
                <div style={{fontSize:12,fontWeight:700,color:'#1D5FAD',marginBottom:2}}>In macchina</div>
                <div style={{fontSize:10,color:'#1D5FAD',opacity:0.8}}>
                  {completatiOggi} completati oggi
                </div>
              </div>
            )
          })()}

          {/* Completati oggi con stima fine */}
          {(()=>{
            const ora = now.getHours()
            const oreTurno = Math.max(0.5, ora >= 6 ? ora - 6 : ora + 18)
            const ritmo = completatiOggi > 0 ? completatiOggi / oreTurno : null
            let stimaLabel = null
            if (ritmo && daFareTot > 0) {
              const oreRim = daFareTot / ritmo
              if (oreRim < 1) stimaLabel = `~${Math.round(oreRim*60)}min`
              else if (oreRim < 24) stimaLabel = `~${oreRim.toFixed(1)}h`
              else stimaLabel = `~${Math.round(oreRim/24)}gg`
            }
            return (
              <div style={{background:'#dcfce7',borderRadius:10,padding:'12px 16px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:2}}>
                  <div style={{fontSize:32,fontWeight:900,color:'#166534',lineHeight:1}}>{completatiOggi}</div>
                  {stimaLabel && <div style={{fontSize:11,fontWeight:700,color:'#15803d',textAlign:'right',lineHeight:1.3}}>
                    fine<br/>{stimaLabel}
                  </div>}
                </div>
                <div style={{fontSize:12,fontWeight:700,color:'#166534',marginBottom:2}}>Completati oggi</div>
                <div style={{fontSize:10,color:'#166534',opacity:0.8}}>
                  {stimaLabel ? `stima al ritmo attuale` : 'nel turno corrente'}
                </div>
              </div>
            )
          })()}

          {/* Tempo fermo giornaliero — sempre visibile, anche a macchina ferma */}
          {(()=>{
            const fermoSec = sessLive?.fermo_sec_giornaliero || 0
            if (fermoSec === 0 && sessLive?.attiva) return null  // in esecuzione, nessun fermo ancora
            const hh = Math.floor(fermoSec / 3600)
            const mm = Math.floor((fermoSec % 3600) / 60)
            const ss = fermoSec % 60
            const fermoFmt = hh > 0
              ? `${hh}h ${String(mm).padStart(2,'0')}m`
              : mm > 0
                ? `${mm}m ${String(ss).padStart(2,'0')}s`
                : `${ss}s`
            const isFermo = !sessLive?.attiva || sessLive?.in_pausa
            const fermoColor   = fermoSec > 3600 ? '#dc2626' : fermoSec > 1800 ? '#d97706' : '#64748b'
            const fermoBg      = fermoSec > 3600 ? '#fef2f2' : fermoSec > 1800 ? '#fffbeb' : '#f8fafc'
            return (
              <div style={{background:fermoBg,border:`1px solid ${fermoColor}33`,
                borderRadius:10,padding:'12px 16px'}}>
                <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline',marginBottom:2}}>
                  <div style={{fontSize:28,fontWeight:900,color:fermoColor,lineHeight:1,
                    fontFamily:'monospace'}}>{fermoFmt}</div>
                  {isFermo&&(
                    <span style={{fontSize:10,fontWeight:800,color:fermoColor,
                      background:`${fermoColor}18`,padding:'2px 7px',borderRadius:4,
                      letterSpacing:'0.05em'}}>
                      FERMO
                    </span>
                  )}
                </div>
                <div style={{fontSize:12,fontWeight:700,color:fermoColor,marginBottom:1}}>
                  Tempo fermo oggi
                </div>
                <div style={{fontSize:10,color:fermoColor,opacity:0.7}}>
                  {isFermo ? 'macchina ferma adesso' : 'accumulato nel turno'}
                </div>
              </div>
            )
          })()}

          {/* Critici */}
          <div style={{background:'#fef2f2',borderRadius:10,padding:'12px 16px'}}>
            <div style={{fontSize:32,fontWeight:900,color:'#dc2626',lineHeight:1,marginBottom:2}}>{critici}</div>
            <div style={{fontSize:12,fontWeight:700,color:'#dc2626',marginBottom:1}}>Critici</div>
            <div style={{fontSize:10,color:'#dc2626',opacity:0.7}}>scaduti o in scadenza oggi</div>
          </div>

        </div>

      </div>
    </div>
  )
}
