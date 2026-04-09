// Home.jsx — Cruscotto turno (redesign V2)
import { useState, useEffect, useRef } from 'react'
import React from 'react'
import { useNavigate } from 'react-router-dom'
import { PopupSostituzione, PopupFermo } from '../components/MLDataPopup'

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
  const [macchinaLive, setMacchinaLive] = useState(null)  // dati OPC UA diretti
  const [confrontoIeri, setConfrontoIeri] = useState(null)  // completati oggi vs ieri
  const [popupSost, setPopupSost]     = useState(null)   // sostituzione da classificare
  const [popupFermo, setPopupFermo]     = useState(null)   // fermo da classificare {inizio,fine,durata_sec}
  const [fermoInizio, setFermoInizio]   = useState(null)   // ts inizio fermo corrente (per contatore live)
  const [fermoFine, setFermoFine]       = useState(null)   // ts fine fermo
  const [fermoInizioSalvato, setFermoInizioSalvato] = useState(null)
  const [fermoSec, setFermoSec]         = useState(0)

  useEffect(()=>{
    const ac = new AbortController()
    const sig = ac.signal
    Promise.all([
      fetch('/api/progetti/', {signal:sig}).then(r=>r.ok?r.json():{projects:[]}),
      fetch('/api/progetti/deliveries', {signal:sig}).then(r=>r.ok?r.json():[]),
      fetch('/api/pallet/', {signal:sig}).then(r=>r.ok?r.json():{pallet:[]}),
    ]).then(([pd,del,pal])=>{
      if(sig.aborted) return
      setProjects((pd.projects||[]).filter(p=>!p.archived))
      setDeliveries(Array.isArray(del)?del:[])
      setPallet(pal.pallet||[])
      setLoading(false)
    }).catch(e=>{ if(e.name!=='AbortError') setLoading(false) })
    // analisi-setup in background — non blocca il render iniziale
    fetch('/api/progetti/analisi-setup/non-utilizzati', {signal:sig})
      .then(r=>r.ok?r.json():{}).then(s=>{ if(!sig.aborted) setSetup(s||{}) }).catch(()=>{})

    // Sessione live: fetch iniziale + polling 10s
    const fetchSessLive=()=>
      fetch('/api/report/sessione-live').then(r=>r.ok?r.json():null)
        .then(d=>{ if(!sig.aborted) setSessLive(d) }).catch(()=>{})
    fetchSessLive()
    const t2=setInterval(fetchSessLive,10000)

    // Stato macchina live OPC UA: fetch iniziale + polling 10s
    const fetchMacchinaLive=()=>
      fetch('/api/macchina-live/stato').then(r=>r.ok?r.json():null)
        .then(d=>{ if(!sig.aborted) setMacchinaLive(d) }).catch(()=>{})
    fetchMacchinaLive()
    const t6=setInterval(fetchMacchinaLive,10000)

    // Confronto ieri: fetch iniziale + refresh ogni 5 min
    const fetchConfrontoIeri=()=>
      fetch('/api/report/confronto-ieri').then(r=>r.ok?r.json():null)
        .then(d=>{ if(!sig.aborted) setConfrontoIeri(d) }).catch(()=>{})
    fetchConfrontoIeri()
    const t7=setInterval(fetchConfrontoIeri,300000)

    // Popup sostituzione: controlla ogni 5 min se ci sono sostituzioni non classificate
    const checkSostituzioni=()=>
      fetch('/api/tool-history/sostituzioni/non-classificate').then(r=>r.ok?r.json():null)
        .then(d=>{
          if(!sig.aborted&&d?.sostituzioni?.length>0) setPopupSost(d.sostituzioni[0])
        }).catch(()=>{})
    checkSostituzioni()
    const t8=setInterval(checkSostituzioni,300000)

    // Timer UI per countdown ETA
    const t3=setInterval(()=>setTickSec(s=>s+1),1000)

    // Tempi ciclo: carica una volta + refresh ogni 5min (dati lenti)
    const fetchTempiCiclo=()=>
      fetch('/api/report/tempi-ciclo').then(r=>r.ok?r.json():null)
        .then(d=>{ if(!sig.aborted && d?.cicli) setTempiCiclo(d.cicli) }).catch(()=>{})
    fetchTempiCiclo()
    const t4=setInterval(fetchTempiCiclo,300000)

    // Refresh ore progetto ogni 5min
    const t5=setInterval(()=>{ progettoCorrenteRef.current = null }, 300000)

    // Pallet: ascolta GlobalPoller invece di poll separato (era ogni 15s)
    // GlobalPoller già gira ogni 5s → nessuna richiesta aggiuntiva
    const onStati = () => {
      if(sig.aborted) return
      fetch('/api/pallet/').then(r=>r.ok?r.json():{pallet:[]})
        .then(d=>{ if(!sig.aborted) setPallet(d.pallet||[]) }).catch(()=>{})
    }
    window.addEventListener('dmgdesk:stati-aggiornati', onStati)

    return()=>{
      ac.abort()
      clearInterval(t2); clearInterval(t3); clearInterval(t4); clearInterval(t5); clearInterval(t6); clearInterval(t7); clearInterval(t8)
      window.removeEventListener('dmgdesk:stati-aggiornati', onStati)
    }
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

  // Auto-reset sessione orfana
  useEffect(()=>{
    if(!sessLive?.attiva) return
    const palletLavNum = pallet.find(p=>(p.stato||'').toLowerCase().replace('_',' ')==='in lavorazione')?.numero
    const isOrfana = sessLive.pallet !== palletLavNum
    if(!isOrfana) return
    // Sessione orfana — reset automatico dopo 10 secondi
    // (delay per evitare falsi positivi durante caricamento iniziale)
    const t = setTimeout(()=>{
      fetch('/api/report/reset-sessione',{method:'POST'})
        .then(()=>setTimeout(()=>window.location.reload(),1500))
    }, 10000)
    return ()=>clearTimeout(t)
  },[sessLive?.attiva, sessLive?.pallet, pallet])

  // Traccia inizio fermo live (per contatore UI)
  useEffect(()=>{
    const eraMacchinaFerma = !sessLive?.attiva || sessLive?.in_pausa
    if(eraMacchinaFerma){
      if(!fermoInizio) setFermoInizio(new Date().toISOString())
    } else {
      setFermoInizio(null)
    }
  },[sessLive?.attiva, sessLive?.in_pausa])

  // Polling backend — fermi non classificati (ogni 30s)
  useEffect(()=>{
    let cancelled = false
    const check = async () => {
      if(cancelled) return
      try {
        const r = await fetch('/api/report/fermi/non-classificati')
        if(!r.ok || cancelled) return
        const d = await r.json()
        const fermi = d.fermi || []
        if(fermi.length > 0 && !popupFermo){
          const f = fermi[0]
          setFermoSec(f.durata_sec || 0)
          setFermoInizioSalvato(f.inizio)
          setFermoFine(f.fine)
          setPopupFermo(f)  // salva l'intero record
        }
      } catch {}
    }
    check()
    const t = setInterval(check, 30000)
    return () => { cancelled = true; clearInterval(t) }
  }, [popupFermo])

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
      progettoId: proj.id,
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
    if(stato==='in lavorazione') return {bg:'#dbeafe',fg:'#0d2d5e',border:'#1D5FAD',label:'LIVE',accent:'#1D5FAD',scaduto:isScaduto}
    // FINITO: pct 100%, stato backend finito, OPPURE nessun programma in_main/in_macchina/in_lavorazione
    const hasPgmAttivi = info?.inMac > 0
    const isFinito = info?.pct>=100 || stato==='finito' || (info && !hasPgmAttivi && info.done > 0)
    if(isFinito) return {bg:'#dcfce7',fg:'#14532d',border:'#16a34a',label:'FINITO',accent:'#16a34a',scaduto:isScaduto}
    if(info) return {bg:'#fefce8',fg:'#854d0e',border:'#eab308',label:'GREZZO',accent:'#eab308',scaduto:isScaduto}
    return {bg:'#f8fafc',fg:'#94a3b8',border:'#e2e8f0',label:'VUOTO',accent:null,scaduto:isScaduto}
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

    // Fallback globale: media di TUTTI i cicli reali noti (non del programma corrente)
    // Evita che un programma pesante (es. 174 min) gonfi la stima di tutti i programmi senza tempoStimato
    const mediaGlobaleCicli = (() => {
      const tuttiCicli = Object.values(tempiCiclo).filter(c => c.n >= 2)
      if (!tuttiCicli.length) return null
      return Math.round(tuttiCicli.reduce((a, c) => a + c.media_sec, 0) / tuttiCicli.length)
    })()
    const fallback = mediaGlobaleCicli

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

    // Separa in_main (già caricati) da da_fare
    const pgmSuccInMain = pgmSuccessivi.filter(p =>
      ['in_main','in_macchina','in_lavorazione'].includes(p.stato))
    const pgmSuccDaFare = pgmSuccessivi.filter(p => p.stato === 'da_fare')

    // Somma ETA successivi in_main (priorità)
    const secSuccInMain = pgmSuccInMain.reduce((acc, p) =>
      acc + stimaPgm(p, fallback || tempoCorrente), 0)
    // Somma ETA tutti i successivi (in_main + da_fare)
    const secSuccessivi = pgmSuccessivi.reduce((acc, p) =>
      acc + stimaPgm(p, fallback || tempoCorrente), 0)

    // totSec primario = in_main only (corrente + successivi in_main)
    // totSecTutto = corrente + tutti i successivi
    const totSec = rimPgm + secSuccInMain   // in_main only
    const totSecTutto = rimPgm + secSuccessivi  // tutto

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
      totSecTutto,
      secTotalePallet,
      nTotali,
      nCompletati,
      nRimanenti,
      nInMain: pgmSuccInMain.length + 1,  // +1 per il corrente
      nDaFare: pgmSuccDaFare.length,
      etaFmtPgm:      fmtEta(rimPgm),
      etaFmtPallet:   fmtEta(totSec),        // in_main only
      etaFmtTutto:    fmtEta(totSecTutto),   // tutto incluso da_fare
      etaFmtTotale:   fmtEta(secTotalePallet),
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

  // ── ETA per pallet (ore rimanenti stimate) ───────────────────────────────
  function etaPallet(num){
    const info = palletInfo(num)
    if(!info) return null
    const pgms = (info.proj.steps||[]).flatMap(s=>(s.tasks||[])
      .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
      .flatMap(t=>(t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm')))

    // Separazione in_main vs totale
    const inMain  = pgms.filter(p=>['in_main','in_lavorazione','in_macchina'].includes(p.stato))
    const totali  = pgms.filter(p=>p.stato!=='completato')
    if(!totali.length) return null

    const mediaGlobale = (()=>{
      const tutti = Object.values(tempiCiclo).filter(c=>c.n>=2)
      return tutti.length ? Math.round(tutti.reduce((a,c)=>a+c.media_sec,0)/tutti.length) : null
    })()
    // Media locale della commessa — fallback più accurato della media globale
    const mediaLocale = (()=>{
      const stimati = pgms.filter(p=>p.tempoStimato && parseInt(p.tempoStimato)>0)
      if(!stimati.length) return null
      return Math.round(stimati.reduce((a,p)=>a+parseInt(p.tempoStimato)*60, 0) / stimati.length)
    })()
    const fmtEta=(sec)=>{
      if(sec<60) return '<1 min'
      if(sec<3600) return `~${Math.round(sec/60)} min`
      const h=Math.floor(sec/3600), m=Math.round((sec%3600)/60)
      return m>0?`~${h}h ${m}m`:`~${h}h`
    }
    const calcolaTempi=(lista)=>{
      let sec=0, haStima=false
      for(const p of lista){
        const fn=(p.filename||'').toUpperCase()
        const tc=tempiCiclo[fn]
        if(tc?.n>=2){ sec+=tc.media_sec; haStima=true }
        else if(p.tempoStimato){ sec+=parseInt(p.tempoStimato)*60; haStima=true }
        else if(mediaLocale){ sec+=mediaLocale; haStima=true }
        else if(mediaGlobale){ sec+=mediaGlobale }
      }
      return { sec, haStima }
    }

    const { sec: secMain, haStima: haStimMain } = calcolaTempi(inMain)
    const { sec: secTot,  haStima: haStimTot  } = calcolaTempi(totali)

    if(secTot<=0) return null
    return {
      sec:        secMain || secTot,   // usa in_main per ordinare; fallback su totale
      fmt:        fmtEta(secMain || secTot),
      fmtTot:     fmtEta(secTot),
      haStima:    haStimMain || haStimTot,
      nMain:      inMain.length,       // programmi in_main (pianificati)
      nTotali:    totali.length,       // tutti i non-completati
      haMain:     inMain.length > 0,
    }
  }

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
      map[u.alias]={alias:u.alias,tipo:'mancante',label:'MANCANTE',color:'#dc2626',bg:'#fef2f2',border:'#fca5a5',
        detail:(u.progetti||[]).map(r=>r.progetto).join(', '),
        progetti:u.progetti||[]}
    })
    ;(setup.da_montare||[]).forEach(u=>{
      if(!map[u.alias]) map[u.alias]={alias:u.alias,tipo:'da_montare',label:'DA MONTARE',color:'#d97706',bg:'#fffbeb',border:'#fcd34d',
        detail:(u.progetti||[]).length>0?(u.progetti||[]).map(r=>r.progetto).join(', '):`pos. ${u.posizione||'—'}`,
        posizione:u.posizione,progetti:u.progetti||[]}
    })
    ;(setup.fin_vita||[]).forEach(u=>{
      const pct=typeof u.life_percent==='number'?u.life_percent:null
      if(!map[u.alias]) map[u.alias]={alias:u.alias,tipo:'fin_vita',label:pct!==null?`${pct.toFixed(0)}%`:'FINE VITA',color:'#c2410c',bg:'#fff7ed',border:'#fdba74',
        detail:(u.progetti||[]).length>0?(u.progetti||[]).map(r=>r.progetto).join(', '):`pos. ${u.position||u.posizione||'—'}`,
        posizione:u.position||u.posizione,progetti:u.progetti||[]}
    })
    ;(setup.previsione_vita?.utensili_critici||[]).forEach(u=>{
      if(!map[u.alias]) map[u.alias]={alias:u.alias,tipo:'rischio',label:`pgm ${u.programma_critico||'?'}`,color:'#7c3aed',bg:'#f5f3ff',border:'#c4b5fd',
        detail:u.progetto||'',progetti:u.progetto?[{progetto:u.progetto,file:u.programma_critico}]:[]}
    })
    return Object.values(map).sort((a,b)=>({mancante:0,da_montare:1,fin_vita:2,rischio:3}[a.tipo]||9)-({mancante:0,da_montare:1,fin_vita:2,rischio:3}[b.tipo]||9))
  })()

  if(loading) return(
    <div style={{flex:1,display:'flex',alignItems:'center',justifyContent:'center',
      background:'#f0f4f8',fontSize:14,color:'#94a3b8'}}>Caricamento…</div>
  )

  return(
    <>
    {/* Popup classificazione sostituzione utensile */}
    {popupSost&&(
      <PopupSostituzione
        sostituzione={popupSost}
        onClassifica={(ts,causa)=>{
          setPopupSost(null)
          // Ricarica subito — potrebbe esserci un'altra sostituzione in coda
          setTimeout(()=>{
            fetch('/api/tool-history/sostituzioni/non-classificate').then(r=>r.ok?r.json():null)
              .then(d=>{ if(d?.sostituzioni?.length>0) setPopupSost(d.sostituzioni[0]) })
              .catch(()=>{})
          }, 500)
        }}
        onIgnora={()=>{
          setPopupSost(null)
          // Passa alla prossima sostituzione non classificata
          setTimeout(()=>{
            fetch('/api/tool-history/sostituzioni/non-classificate').then(r=>r.ok?r.json():null)
              .then(d=>{
                const prossima = d?.sostituzioni?.find(s=>s.ts !== popupSost?.ts)
                if(prossima) setPopupSost(prossima)
              }).catch(()=>{})
          }, 500)
        }}
      />
    )}
    {/* Popup classificazione fermo */}
    {popupFermo&&(
      <PopupFermo
        fermoSec={fermoSec}
        tsInizio={fermoInizioSalvato}
        tsFine={fermoFine}
        onClassifica={async (causa)=>{
          // Classifica sul backend
          await fetch('/api/report/fermi/classifica', {
            method:'POST', headers:{'Content-Type':'application/json'},
            body: JSON.stringify({ causa, ts_inizio: fermoInizioSalvato, durata_sec: fermoSec })
          })
          setPopupFermo(null)
        }}
        onIgnora={async ()=>{
          if(fermoInizioSalvato){
            await fetch('/api/report/fermi/ignora', {
              method:'POST', headers:{'Content-Type':'application/json'},
              body: JSON.stringify({ ts_inizio: fermoInizioSalvato })
            })
          }
          setPopupFermo(null)
        }}
      />
    )}
    <div style={{flex:1,overflow:'hidden',background:'#f0f4f8',fontFamily:'var(--font-display)',display:'flex',flexDirection:'column',height:'100%'}}>

      {/* ── TOPBAR ─────────────────────────────────────────────────────── */}
      <div style={{background:'#fff',borderBottom:'1px solid #e2e8f0',padding:'8px 20px',
        display:'flex',alignItems:'center',gap:16,flexShrink:0}}>
        <span style={{fontSize:15,fontWeight:800,color:'#0d2d5e'}}>Cruscotto turno</span>
        <span style={{fontSize:12,color:'#94a3b8'}}>{dayLabel}</span>
        {/* Banner stato macchina */}
        {sessLive?.attiva&&sessLive?.programma_corrente&&(
          <div style={{marginLeft:12,background:'#dbeafe',border:'1px solid #1D5FAD',
            borderRadius:8,padding:'5px 14px',display:'flex',alignItems:'center',gap:8}}>
            <span style={{width:8,height:8,borderRadius:'50%',background:'#1D5FAD',
              flexShrink:0,display:'inline-block',animation:'pulse-dot 1.5s ease-in-out infinite'}}/>
            <span style={{fontSize:11,fontWeight:800,color:'#0d2d5e',letterSpacing:'0.05em'}}>IN ESECUZIONE</span>
            <span style={{fontSize:12,fontWeight:700,color:'#1D5FAD',fontFamily:'monospace'}}>
              {sessLive.programma_corrente.replace('.MPF','').replace('.mpf','')}
            </span>
          </div>
        )}
        {/* Log age indicator — sempre a destra */}
        {macchinaLive?.connessa&&macchinaLive?.log_age_sec!=null&&(
          <div style={{marginLeft:'auto',display:'flex',alignItems:'center',gap:5,fontSize:11,color:'#64748b'}}>
            <span style={{width:6,height:6,borderRadius:'50%',
              background:macchinaLive.log_stale?'#f59e0b':'#16a34a',display:'inline-block'}}/>
            <span>log {macchinaLive.log_age_sec < 60
              ? `${macchinaLive.log_age_sec}s fa`
              : `${Math.floor(macchinaLive.log_age_sec/60)}m fa`}
            </span>
          </div>
        )}
        {!sessLive?.attiva&&(sessLive?.fermo_sec_giornaliero||0)>0&&(
          <div style={{marginLeft:12,background:'#fef2f2',border:'1px solid #fca5a5',
            borderRadius:8,padding:'5px 14px',display:'flex',alignItems:'center',gap:8}}>
            <span style={{width:8,height:8,borderRadius:'50%',background:'#ef4444',flexShrink:0,display:'inline-block'}}/>
            <span style={{fontSize:11,fontWeight:800,color:'#dc2626',letterSpacing:'0.05em'}}>MACCHINA FERMA</span>
            {macchinaLive?.allarme&&macchinaLive?.allarme_tipo==='allarme'&&(
              <span style={{fontSize:11,fontFamily:'monospace',color:'#991b1b',marginLeft:4,
                maxWidth:200,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                — {macchinaLive.allarme}
              </span>
            )}
          </div>
        )}
        {macchinaLive?.log_stale&&(macchinaLive?.log_age_sec||0)>120&&sessLive?.attiva&&(
          <div style={{marginLeft:'auto',background:'#fffbeb',border:'1px solid #fcd34d',
            borderRadius:8,padding:'5px 14px',display:'flex',alignItems:'center',gap:8}}>
            <span style={{fontSize:12}}>⚠️</span>
            <span style={{fontSize:11,fontWeight:700,color:'#92400e'}}>Log fermo da {Math.floor((macchinaLive.log_age_sec||0)/60)} min</span>
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
              <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:10}}>
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

              {/* Utensile prominente — T number e vita sempre visibile */}
              {(macchinaLive?.utensile_attivo||macchinaLive?.numero_utensile)&&(
                <div style={{background:'#eff6ff',border:'1px solid #bfdbfe',borderRadius:8,
                  padding:'7px 12px',display:'flex',alignItems:'center',gap:12,marginBottom:10}}>
                  <div style={{flex:1,minWidth:0}}>
                    <div style={{fontSize:13,fontWeight:800,color:'#0d2d5e',whiteSpace:'nowrap',
                      overflow:'hidden',textOverflow:'ellipsis'}}>
                      {macchinaLive.utensile_attivo||'—'}
                    </div>
                    <div style={{fontSize:11,color:'#1D5FAD'}}>
                      {macchinaLive.numero_utensile?`T${macchinaLive.numero_utensile} · `:''}utensile attivo
                    </div>
                  </div>
                  {(()=>{
                    // Cerca vita dell'utensile attivo nei dati setup
                    const alias = (macchinaLive.utensile_attivo||'').toUpperCase().trim()
                    const utSetup = (setup.fin_vita||[]).find(u=>(u.alias||'').toUpperCase()===alias)
                    if(!utSetup||utSetup.life_percent==null) return null
                    const pct = Math.round(utSetup.life_percent)
                    const col = pct < 20 ? '#dc2626' : pct < 40 ? '#d97706' : '#16a34a'
                    return (
                      <div style={{textAlign:'right',flexShrink:0}}>
                        <div style={{fontSize:16,fontWeight:800,color:col}}>{pct}%</div>
                        <div style={{height:4,width:54,background:'#bfdbfe',borderRadius:2,marginTop:3,overflow:'hidden'}}>
                          <div style={{height:'100%',width:`${pct}%`,background:col,borderRadius:2}}/>
                        </div>
                        <div style={{fontSize:9,color:'#64748b',marginTop:2}}>vita residua</div>
                      </div>
                    )
                  })()}
                </div>
              )}

              {/* Timer principale — PROGRAMMA CORRENTE, grande al centro */}
              <div style={{textAlign:'center',padding:'8px 0 10px',borderBottom:'1px solid #bfdbfe',marginBottom:10}}>
                <div style={{fontSize:10,fontWeight:700,color:
                  sessMatch&&sessLive?.anomalia_ciclo?'#dc2626':sessMatch&&sessLive?.in_pausa?'#92400e':'#1D5FAD',
                  letterSpacing:'0.07em',textTransform:'uppercase',marginBottom:4,
                  display:'flex',alignItems:'center',justifyContent:'center',gap:6}}>
                  {sessMatch&&sessLive?.anomalia_ciclo&&(
                    <span style={{fontSize:9,fontWeight:800,color:'#dc2626',background:'#fef2f2',
                      padding:'1px 6px',borderRadius:3,border:'1px solid #fca5a5'}}>CICLO LUNGO</span>
                  )}
                  {sessMatch&&sessLive?.in_pausa&&!sessLive?.anomalia_ciclo&&(
                    <span style={{fontSize:9,fontWeight:800,color:'#92400e',background:'#fef3c7',
                      padding:'1px 6px',borderRadius:3,border:'1px solid #fcd34d'}}>PAUSA</span>
                  )}
                  Programma corrente
                </div>
                <div style={{fontSize:38,fontWeight:900,fontFamily:'monospace',lineHeight:1,
                  color:sessMatch&&sessLive?.anomalia_ciclo?'#dc2626':sessMatch&&sessLive?.in_pausa?'#92400e':'#0d2d5e'}}>
                  {sessMatch&&durataProgrammaLive!=null?fmtTimer(durataProgrammaLive):'—:——:——'}
                </div>
                {sessMatch&&sessLive?.programma_corrente&&(
                  <div style={{fontSize:11,color:'#1D5FAD',marginTop:4,fontFamily:'monospace'}}>
                    {sessLive.programma_corrente.replace('.MPF','').replace('.mpf','')}
                    {sessMatch&&sessLive?.ciclo_stats&&(
                      <span style={{color:'#94a3b8',marginLeft:8}}>
                        media {fmtTimer(sessLive.ciclo_stats.media_sec)} ({sessLive.ciclo_stats.n} cicli)
                      </span>
                    )}
                  </div>
                )}
                {sessMatch&&sessLive?.utensile&&(
                  <div style={{marginTop:6,display:'inline-block',fontSize:11,fontWeight:700,color:'#0d2d5e',
                    background:'#eff6ff',padding:'3px 12px',borderRadius:6,fontFamily:'monospace'}}>
                    {sessLive.utensile}
                    {sessLive.t_number&&(
                      <span style={{color:'#1D5FAD',marginLeft:8}}>T{sessLive.t_number}</span>
                    )}
                  </div>
                )}
              </div>

              {/* ── INFO LIVE OPC UA: allarme, log stale, T number ── */}
              {macchinaLive?.connessa&&(()=>{
                const allarme    = macchinaLive.allarme
                const allarmeT   = macchinaLive.allarme_tipo
                const logStale   = macchinaLive.log_stale
                const logAge     = macchinaLive.log_age_sec
                const tNum       = macchinaLive.numero_utensile
                const showAlarm  = allarme && allarmeT === 'allarme'
                const showStale  = logStale && logAge > 120
                const showTNum   = tNum && tNum > 0
                if(!showAlarm && !showStale && !showTNum) return null
                return (
                  <div style={{display:'flex',flexDirection:'column',gap:5,marginBottom:10}}>
                    {/* Allarme critico */}
                    {showAlarm&&(
                      <div style={{background:'#fef2f2',border:'1px solid #fca5a5',borderRadius:7,
                        padding:'6px 10px',display:'flex',alignItems:'center',gap:8}}>
                        <span style={{fontSize:16}}>🚨</span>
                        <div style={{flex:1,minWidth:0}}>
                          <div style={{fontSize:9,fontWeight:800,color:'#dc2626',letterSpacing:'0.07em',textTransform:'uppercase'}}>Allarme attivo</div>
                          <div style={{fontSize:11,fontWeight:700,color:'#991b1b',fontFamily:'monospace',
                            overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{allarme}</div>
                        </div>
                      </div>
                    )}
                    {/* Log stale */}
                    {showStale&&(
                      <div style={{background:'#fffbeb',border:'1px solid #fcd34d',borderRadius:7,
                        padding:'6px 10px',display:'flex',alignItems:'center',gap:8}}>
                        <span style={{fontSize:14}}>⚠️</span>
                        <div>
                          <div style={{fontSize:9,fontWeight:800,color:'#92400e',letterSpacing:'0.07em',textTransform:'uppercase'}}>Log non aggiornato</div>
                          <div style={{fontSize:11,color:'#78350f'}}>Fermo da {Math.floor(logAge/60)} min — verifica MchnSrv</div>
                        </div>
                      </div>
                    )}
                    {/* T number utensile */}
                    {showTNum&&!showAlarm&&(
                      <div style={{background:'#f0fdf4',border:'1px solid #bbf7d0',borderRadius:7,
                        padding:'5px 10px',display:'flex',alignItems:'center',gap:8}}>
                        <span style={{fontSize:12}}>🔧</span>
                        <span style={{fontSize:11,color:'#15803d'}}>
                          Utensile attivo: <b style={{fontFamily:'monospace'}}>T{tNum}</b>
                          {macchinaLive.utensile_attivo&&(
                            <span style={{marginLeft:6,fontFamily:'monospace',color:'#166534'}}>{macchinaLive.utensile_attivo}</span>
                          )}
                        </span>
                      </div>
                    )}
                  </div>
                )
              })()}

              {/* ETA — prominente */}
              {etaCalc&&(
                <div style={{background: etaCalc.anomalia?'#fef2f2':'#dbeafe',
                  borderRadius:8,padding:'8px 12px',marginBottom:10,
                  display:'flex',alignItems:'center',justifyContent:'space-between',
                  border:`1px solid ${etaCalc.anomalia?'#fca5a5':'#93c5fd'}`}}>
                  <div>
                    <div style={{fontSize:10,color:etaCalc.anomalia?'#dc2626':'#1D5FAD',marginBottom:1}}>
                      fine pallet {etaCalc.nInMain>0?`· ${etaCalc.nInMain} in main`:''}
                    </div>
                    <div style={{fontSize:20,fontWeight:900,fontFamily:'monospace',
                      color:etaCalc.anomalia?'#dc2626':'#0d2d5e',lineHeight:1}}>
                      {etaCalc.etaFmtPallet}
                      {(()=>{
                        const oraFine = new Date(Date.now() + etaCalc.totSec*1000)
                        return (
                          <span style={{fontSize:13,fontWeight:700,color:etaCalc.anomalia?'#ef4444':'#1D5FAD',marginLeft:10}}>
                            → {String(oraFine.getHours()).padStart(2,'0')}:{String(oraFine.getMinutes()).padStart(2,'0')}
                          </span>
                        )
                      })()}
                    </div>
                    {etaCalc.nDaFare>0&&(
                      <div style={{fontSize:10,color:'#64748b',marginTop:3}}>
                        inclusi da fare: {etaCalc.etaFmtTutto}
                        <span style={{marginLeft:6,opacity:0.7}}>+{etaCalc.nDaFare} pgm da caricare</span>
                      </div>
                    )}
                  </div>
                  <div style={{textAlign:'right'}}>
                    <div style={{fontSize:10,color:'#64748b'}}>
                      {etaCalc.nCampioni>=2?`da ${etaCalc.nCampioni} cicli reali`:'da tempi CAM'}
                    </div>
                    <div style={{fontSize:10,color:'#64748b',marginTop:1}}>
                      {etaCalc.nInMain} pgm in main
                    </div>
                  </div>
                </div>
              )}

              {/* Timeline sessione oggi */}
              {sessLive?.attiva&&sessLive?.inizio_sessione&&(()=>{
                const inizioSess = new Date(sessLive.inizio_sessione)
                const ora = new Date()
                const mezzanotte = new Date(ora); mezzanotte.setHours(0,0,0,0)
                const totMin = (ora - mezzanotte) / 60000
                const inizioMin = (inizioSess - mezzanotte) / 60000
                const fermoSec = sessLive?.fermo_sec_giornaliero || 0
                const runMin = Math.max(0, (ora - inizioSess)/60000 - fermoSec/60)
                const fermoMin = fermoSec / 60
                const beforePct = Math.min(100, (inizioMin / totMin) * 100)
                const runPct = Math.min(100 - beforePct, (runMin / totMin) * 100)
                const fermoPct = Math.min(100 - beforePct - runPct, (fermoMin / totMin) * 100)
                const nowPct = Math.max(2, 100 - beforePct - runPct - fermoPct)
                const fmtT = (d) => `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
                return (
                  <div style={{marginBottom:10}}>
                    <div style={{fontSize:9,fontWeight:700,color:'#1D5FAD',letterSpacing:'.07em',
                      textTransform:'uppercase',marginBottom:5}}>Sessione oggi</div>
                    <div style={{height:10,background:'#e2e8f0',borderRadius:5,display:'flex',gap:1,overflow:'hidden'}}>
                      <div style={{width:`${beforePct}%`,background:'#e2e8f0'}}/>
                      <div style={{width:`${runPct}%`,background:'#1D5FAD',borderRadius:2}}/>
                      {fermoPct>1&&<div style={{width:`${fermoPct}%`,background:'#e2e8f0'}}/>}
                      <div style={{width:`${nowPct}%`,background:'#93c5fd',opacity:.8,borderRadius:2}}/>
                    </div>
                    <div style={{display:'flex',justifyContent:'space-between',marginTop:3}}>
                      <span style={{fontSize:9,color:'#94a3b8'}}>00:00</span>
                      <span style={{fontSize:9,color:'#1D5FAD'}}>{fmtT(inizioSess)}</span>
                      <span style={{fontSize:9,color:'#94a3b8'}}>{fmtT(ora)}</span>
                    </div>
                  </div>
                )
              })()}

              {/* Timer secondari — compatti in 2 colonne */}
              <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:8,marginBottom:10}}>
                <div style={{background:'#fff',borderRadius:8,padding:'6px 10px',border:'1px solid #bfdbfe'}}>
                  <div style={{fontSize:9,fontWeight:700,color:'#1D5FAD',letterSpacing:'0.07em',textTransform:'uppercase',marginBottom:3}}>
                    Sessione pallet
                  </div>
                  <div style={{fontSize:18,fontWeight:900,color:'#0d2d5e',fontFamily:'monospace',lineHeight:1}}>
                    {sessMatch?fmtTimer(durataSessioneLive):'—:——:——'}
                  </div>
                  {sessMatch&&sessLive?.inizio_sessione&&(
                    <div style={{fontSize:10,color:'#64748b',marginTop:2}}>
                      dal {sessLive.inizio_sessione.slice(11,16)}
                    </div>
                  )}
                  {!sessMatch&&sessLive?.attiva&&(
                    <div style={{marginTop:4}}>
                      <div style={{fontSize:10,color:'#dc2626',marginBottom:3}}>
                        orfana (P{sessLive.pallet}→P{palletLav?.numero})
                      </div>
                      <button onClick={()=>{
                        fetch('/api/report/reset-sessione',{method:'POST'})
                          .then(()=>setTimeout(()=>window.location.reload(),1500))
                      }} style={{fontSize:10,padding:'2px 8px',borderRadius:4,
                        background:'#dc2626',border:'none',color:'#fff',cursor:'pointer',fontWeight:600}}>
                        ↺ Ripristina
                      </button>
                    </div>
                  )}
                </div>
                {(()=>{
                  const secStorico = oreProgetto?.ore_sec || 0
                  const secSessioneBase = sessMatch?(sessLive?.durata_sec||0):0
                  const secSessioneAperta = secSessioneBase>0&&sessLive?.attiva&&!sessLive?.in_pausa
                    ? secSessioneBase+(tickSec%10) : secSessioneBase
                  const secTot = secStorico+secSessioneAperta
                  const nSessioni = oreProgetto?.n_sessioni||0
                  const primaData = oreProgetto?.prima_data
                  return(
                    <div style={{background:'#fff',borderRadius:8,padding:'6px 10px',border:'1px solid #bbf7d0'}}>
                      <div style={{fontSize:9,fontWeight:700,color:'#15803d',letterSpacing:'0.07em',textTransform:'uppercase',marginBottom:3}}>
                        Ore progetto
                      </div>
                      <div style={{fontSize:18,fontWeight:900,color:'#166534',fontFamily:'monospace',lineHeight:1}}>
                        {secTot>0?fmtTimer(secTot):'—:——:——'}
                      </div>
                      {secTot>0&&(
                        <div style={{fontSize:10,color:'#64748b',marginTop:2}}>
                          {nSessioni>0?`${nSessioni} sess.`:''}{primaData&&nSessioni>1?` · dal ${primaData}`:''}
                        </div>
                      )}
                    </div>
                  )
                })()}
              </div>

              {/* Barra + stats */}
              <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:6}}>
                <div style={{flex:1,height:6,background:'rgba(29,95,173,0.15)',borderRadius:3,overflow:'hidden'}}>
                  <div style={{height:'100%',width:`${lavInfo.pct}%`,
                    background:lavInfo.proj.color||'#1D5FAD',borderRadius:3,transition:'width 0.4s'}}/>
                </div>
                <span style={{fontSize:13,fontWeight:800,color:'#0d2d5e',minWidth:38,textAlign:'right'}}>
                  {lavInfo.pct}%
                </span>
              </div>
              <div style={{display:'flex',alignItems:'center',gap:8,flexWrap:'wrap'}}>
                <span style={{fontSize:12,color:'#64748b'}}>
                  <b style={{color:'#16a34a'}}>{lavInfo.done}</b> completati &nbsp;·&nbsp;
                  <b style={{color:'#1D5FAD'}}>{lavInfo.inMac}</b> in corso &nbsp;·&nbsp;
                  <b style={{color:'#94a3b8'}}>{lavInfo.daFare}</b> da fare
                </span>
              </div>
            </div>
          ):(
            <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,
              padding:'16px 20px',flexShrink:0}}>
              <div style={{display:'flex',alignItems:'center',gap:12}}>
                <div style={{width:10,height:10,borderRadius:'50%',background:'#ef4444',flexShrink:0}}/>
                <span style={{fontSize:14,fontWeight:800,color:'#64748b'}}>Macchina ferma</span>
                {sessLive?.fermo_sec_giornaliero>0&&(()=>{
                  const h=Math.floor(sessLive.fermo_sec_giornaliero/3600)
                  const m=Math.floor((sessLive.fermo_sec_giornaliero%3600)/60)
                  return <span style={{fontSize:12,color:'#94a3b8',marginLeft:8}}>
                    fermo da {h>0?`${h}h `:''}${m}m oggi
                  </span>
                })()}
                {macchinaLive?.allarme&&macchinaLive?.allarme_tipo==='allarme'&&(
                  <span style={{fontSize:11,fontFamily:'monospace',color:'#dc2626',
                    background:'#fef2f2',padding:'2px 8px',borderRadius:4,border:'1px solid #fca5a5'}}>
                    {macchinaLive.allarme}
                  </span>
                )}
              </div>
              <div style={{marginTop:10,fontSize:12,color:'#94a3b8'}}>
                Seleziona un pallet per avviare la lavorazione
              </div>
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
                      <div style={{display:'flex',flexDirection:'column',alignItems:'flex-end',gap:3}}>
                        {!isVuoto&&(
                          <span style={{fontSize:9,fontWeight:800,color:c.accent||c.fg,
                            background:'#fff',padding:'2px 6px',borderRadius:4,
                            border:`1px solid ${c.border}`,letterSpacing:'0.05em',lineHeight:1.4}}>
                            {c.label}
                          </span>
                        )}
                        {c.scaduto&&(
                          <span style={{fontSize:9,fontWeight:800,color:'#c2410c',
                            background:'#fff7ed',padding:'2px 6px',borderRadius:4,
                            border:'1px solid #c2410c',letterSpacing:'0.05em',lineHeight:1.4}}>
                            SCADUTO
                          </span>
                        )}
                      </div>
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
                        {(()=>{
                          const eta = etaPallet(n)
                          if(!eta) return null
                          const etaBg = isLav ? 'rgba(29,95,173,0.15)' : 'rgba(0,0,0,0.08)'
                          return(
                            <div style={{fontSize:11,fontWeight:700,color:c.fg,
                              background:etaBg,borderRadius:4,padding:'2px 5px',
                              textAlign:'center',marginTop:2}}>
                              {eta.fmt}
                            </div>
                          )
                        })()}
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

          </div>
        </div>{/* fine col-main */}

        {/* ══ COL SIDE ═══════════════════════════════════════════════ */}
        <div style={{display:'flex',flexDirection:'column',gap:8,overflowY:'auto',minHeight:0}}>
          <div style={{fontSize:10,fontWeight:800,letterSpacing:'0.1em',color:'#64748b',textTransform:'uppercase'}}>
            Metriche turno
          </div>

          {/* Card metriche — compatta, gerarchizzata */}
          {(()=>{
            const totale = allPgm.length
            const completatiTot = allPgm.filter(p=>p.stato==='completato').length
            const pctTot = totale ? Math.round(completatiTot/totale*100) : 0
            const ora = now.getHours()
            const oreTurno = Math.max(0.5, ora >= 6 ? ora - 6 : ora + 18)
            const ritmo = oreTurno > 0 ? (completatiOggi / oreTurno).toFixed(1) : null
            return(
              <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'12px 14px'}}>
                {/* Principale: completati oggi */}
                <div style={{background:'#eff6ff',borderRadius:8,padding:'10px 12px',marginBottom:8}}>
                  <div style={{display:'flex',justifyContent:'space-between',alignItems:'baseline'}}>
                    <div style={{fontSize:30,fontWeight:900,color:'#0d2d5e',lineHeight:1}}>{completatiOggi}</div>
                    {ritmo&&completatiOggi>0&&(
                      <div style={{fontSize:12,fontWeight:700,color:'#1D5FAD'}}>~{ritmo}/h</div>
                    )}
                  </div>
                  <div style={{fontSize:11,fontWeight:700,color:'#1D5FAD',marginTop:2,display:'flex',alignItems:'center',gap:4}}>completati oggi <InfoTooltip text="Programmi NC completati dall'inizio del turno corrente (ore 07:30).&#10;Conteggio basato sui cambi di stato registrati dal LOG macchina." /></div>
                </div>
                {/* Secondari: griglia 2x2 */}
                <div style={{display:'grid',gridTemplateColumns:'1fr 1fr',gap:6,marginBottom:8}}>
                  <div style={{background:'#f8fafc',borderRadius:7,padding:'8px 10px'}}>
                    <div style={{fontSize:22,fontWeight:900,color:'#1D5FAD',lineHeight:1}}>{inMacTot}</div>
                    <div style={{fontSize:10,color:'#64748b',marginTop:2,display:'flex',alignItems:'center',gap:3}}>in macchina <InfoTooltip text="Programmi con stato in_main o in_lavorazione.&#10;Sono i programmi caricati nel MAIN della macchina e pronti per essere eseguiti." /></div>
                  </div>
                  <div style={{background:'#f8fafc',borderRadius:7,padding:'8px 10px'}}>
                    <div style={{fontSize:22,fontWeight:900,color:'#0d2d5e',lineHeight:1}}>{daFareTot}</div>
                    <div style={{fontSize:10,color:'#64748b',marginTop:2,display:'flex',alignItems:'center',gap:3}}>da fare <InfoTooltip text="Programmi non ancora caricati nel MAIN della macchina.&#10;Richiedono un nuovo ciclo di generazione MAIN prima di poter essere eseguiti." /></div>
                  </div>
                  <div style={{background:critici>0?'#fef2f2':'#f8fafc',borderRadius:7,padding:'8px 10px'}}>
                    <div style={{fontSize:22,fontWeight:900,color:critici>0?'#dc2626':'#64748b',lineHeight:1}}>{critici}</div>
                    <div style={{fontSize:10,color:critici>0?'#dc2626':'#64748b',marginTop:2,display:'flex',alignItems:'center',gap:3}}>critici <InfoTooltip text="Commesse con data di consegna scaduta o imminente.&#10;Vengono evidenziate in rosso quando la data di consegna è già passata." /></div>
                  </div>
                  <div style={{background:'#f8fafc',borderRadius:7,padding:'8px 10px'}}>
                    <div style={{fontSize:13,fontWeight:800,color:'#0d2d5e',lineHeight:1}}>{pctTot}%</div>
                    <div style={{height:4,background:'#bfdbfe',borderRadius:2,overflow:'hidden',margin:'4px 0 2px'}}>
                      <div style={{height:'100%',width:`${pctTot}%`,background:'#1D5FAD',borderRadius:2}}/>
                    </div>
                    <div style={{fontSize:10,color:'#64748b'}}>{completatiTot}/{totale} pgm</div>
                  </div>
                </div>
                {/* Confronto ieri stessa ora + Fermo giornaliero */}
                {confrontoIeri&&(confrontoIeri.oggi>0||confrontoIeri.ieri>0)&&(
                  <div style={{display:'flex',justifyContent:'space-between',
                    fontSize:11,color:'#64748b',marginBottom:8}}>
                    <span style={{display:'flex',alignItems:'center',gap:3}}>ieri stessa ora: <b style={{color:'#0d2d5e'}}>{confrontoIeri.ieri}</b> <InfoTooltip text="Programmi completati ieri alla stessa ora del giorno.&#10;Permette di confrontare il ritmo produttivo con il giorno precedente." /></span>
                    <span>oggi: <b style={{
                      color: confrontoIeri.delta>0?'#16a34a':confrontoIeri.delta<0?'#dc2626':'#64748b'
                    }}>{confrontoIeri.oggi} {confrontoIeri.delta>0?'↑':confrontoIeri.delta<0?'↓':'='}</b></span>
                  </div>
                )}
                {sessLive&&(()=>{
                  const fermoSec = sessLive?.fermo_sec_giornaliero||0
                  if(fermoSec===0&&sessLive?.attiva&&!sessLive?.in_pausa) return null
                  const hh=Math.floor(fermoSec/3600), mm=Math.floor((fermoSec%3600)/60), ss=fermoSec%60
                  const fermoFmt=hh>0?`${hh}h ${String(mm).padStart(2,'0')}m`:mm>0?`${mm}m ${String(ss).padStart(2,'0')}s`:`${ss}s`
                  const isFermo=!sessLive?.attiva||sessLive?.in_pausa
                  const fermoColor=fermoSec>3600?'#dc2626':fermoSec>1800?'#d97706':'#64748b'
                  const fermoBg=fermoSec>3600?'#fef2f2':fermoSec>1800?'#fffbeb':'#f8fafc'
                  return(
                    <div style={{background:fermoBg,border:`1px solid ${fermoColor}33`,borderRadius:7,
                      padding:'8px 10px',display:'flex',justifyContent:'space-between',alignItems:'center'}}>
                      <div>
                        <div style={{fontSize:16,fontWeight:900,color:fermoColor,fontFamily:'monospace',lineHeight:1}}>{fermoFmt}</div>
                        <div style={{fontSize:10,color:fermoColor,marginTop:2,display:'flex',alignItems:'center',gap:3}}>
                          {isFermo?'macchina ferma':'fermo oggi'} <InfoTooltip text="Tempo totale di fermo della macchina nel turno corrente.&#10;Rosso > 1h · Arancio > 30min.&#10;Cliccabile per classificare la causa del fermo." position="left" />
                        </div>
                      </div>
                      {isFermo&&(
                        <span style={{fontSize:9,fontWeight:800,color:fermoColor,
                          background:`${fermoColor}18`,padding:'2px 6px',borderRadius:3,letterSpacing:'0.05em'}}>
                          FERMO
                        </span>
                      )}
                    </div>
                  )
                })()}
              </div>
            )
          })()}

          {/* ── ORE MACCHINA RIMANENTI — nuova card ─────────────────── */}
          {(()=>{
            const palletAttivi = [1,2,3,4,5,6]
              .map(n=>({ n, info: palletInfo(n), eta: etaPallet(n), colors: palletColors(n) }))
              .filter(x=>x.info&&x.eta)
              .sort((a,b)=>a.eta.sec-b.eta.sec)
            if(!palletAttivi.length) return null
            const totSec = palletAttivi.reduce((acc,x)=>acc+x.eta.sec,0)
            const fmtTot=(sec)=>{
              if(sec<3600) return `~${Math.round(sec/60)} min`
              const h=Math.floor(sec/3600), m=Math.round((sec%3600)/60)
              return m>0?`~${h}h ${m}m`:`~${h}h`
            }
            return(
              <div style={{background:'#faf5ff',border:'1.5px solid #a78bfa',borderRadius:12,padding:'12px 14px'}}>
                <div style={{fontSize:10,fontWeight:800,letterSpacing:'0.1em',color:'#6d28d9',
                  textTransform:'uppercase',marginBottom:8}}>ore macchina rimanenti</div>
                <div style={{display:'flex',flexDirection:'column',gap:0}}>
                  {palletAttivi.map(({n,info,eta,colors},i)=>{
                    const isLive=colors.label==='LIVE'
                    return(
                      <div key={n} onClick={()=>nav('/progetti',{state:{openId:info.proj.id}})}
                        style={{display:'flex',alignItems:'center',gap:8,
                          padding:'7px 0',cursor:'pointer',
                          borderTop:i>0?'1px solid #ede9fe':'none'}}>
                        <div style={{fontSize:11,fontWeight:800,color:isLive?'#4c1d95':'#6d28d9',
                          minWidth:22,background:isLive?'#ddd6fe':'#ede9fe',
                          borderRadius:4,padding:'1px 4px',textAlign:'center'}}>
                          P{n}
                        </div>
                        <div style={{flex:1,overflow:'hidden'}}>
                          <div style={{fontSize:11,fontWeight:700,color:'#3b0764',
                            overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                            {info.proj.name}
                          </div>
                          <div style={{display:'flex',alignItems:'baseline',gap:4}}>
                            <span style={{fontSize:9,fontWeight:700,color:isLive?'#4c1d95':'#7c3aed'}}>
                              {isLive?'IN ESECUZIONE':'in attesa'}
                            </span>
                            {/* in_main grande */}
                            {eta.haMain&&(
                              <span style={{fontSize:11,fontWeight:800,color:'#3b0764'}}>
                                {eta.nMain} pgm
                              </span>
                            )}
                            {/* totali piccoli */}
                            {eta.nTotali>eta.nMain&&(
                              <span style={{fontSize:9,color:'#a78bfa'}}>
                                / {eta.nTotali} tot
                              </span>
                            )}
                          </div>
                        </div>
                        <div style={{textAlign:'right',flexShrink:0}}>
                          {/* in_main grande */}
                          <div style={{fontSize:13,fontWeight:900,fontFamily:'monospace',
                            color:isLive?'#4c1d95':'#5b21b6'}}>
                            {eta.fmt}
                          </div>
                          {/* totale piccolo */}
                          {eta.nTotali>eta.nMain&&(
                            <div style={{fontSize:9,color:'#a78bfa',fontFamily:'monospace'}}>
                              {eta.fmtTot} tot
                            </div>
                          )}
                          {!eta.haStima&&(
                            <div style={{fontSize:9,color:'#a78bfa'}}>stima grezza</div>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
                <div style={{borderTop:'1px solid #c4b5fd',marginTop:6,paddingTop:6,
                  display:'flex',justifyContent:'space-between',alignItems:'baseline'}}>
                  <span style={{fontSize:10,color:'#6d28d9'}}>totale in macchina</span>
                  <div style={{textAlign:'right'}}>
                    <span style={{fontSize:14,fontWeight:900,fontFamily:'monospace',color:'#3b0764'}}>
                      {fmtTot(palletAttivi.reduce((acc,x)=>acc+x.eta.sec,0))}
                    </span>
                  </div>
                </div>
              </div>
            )
          })()}

          {/* Utensili problemi */}
          <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'10px 14px'}}>
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
                    style={{background:u.bg,border:`1px solid ${u.border}`,
                      borderRadius:8,padding:'6px 10px'}}>
                    {/* Riga principale */}
                    <div style={{display:'flex',alignItems:'center',gap:10}}>
                      <span style={{fontSize:10,fontWeight:800,color:u.color,
                        background:'#fff',padding:'2px 8px',borderRadius:4,
                        border:`1px solid ${u.border}`,flexShrink:0,
                        minWidth:68,textAlign:'center'}}>{u.label}</span>
                      <span style={{fontSize:12,fontWeight:700,color:'#1e293b',
                        fontFamily:'monospace',flex:1,
                        overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>{u.alias}</span>
                      {u.posizione&&<span style={{fontSize:10,color:u.color,opacity:0.7,flexShrink:0}}>
                        pos.{u.posizione}
                      </span>}
                    </div>
                    {/* Riga contesto: progetti + file */}
                    {u.progetti?.length>0&&(
                      <div style={{marginTop:4,paddingTop:4,borderTop:`1px solid ${u.border}`,
                        display:'flex',flexDirection:'column',gap:2}}>
                        {u.progetti.slice(0,3).map((r,i)=>(
                          <div key={i} style={{display:'flex',alignItems:'center',gap:6}}>
                            <div style={{width:4,height:4,borderRadius:'50%',
                              background:u.color,flexShrink:0,opacity:0.6}}/>
                            <span style={{fontSize:10,fontWeight:700,color:u.color,
                              opacity:0.9,flexShrink:0}}>{r.progetto}</span>
                            {r.file&&<span style={{fontSize:10,fontFamily:'monospace',
                              color:'#64748b',overflow:'hidden',textOverflow:'ellipsis',
                              whiteSpace:'nowrap'}}>{r.file.replace('.MPF','').replace('.mpf','')}</span>}
                          </div>
                        ))}
                        {u.progetti.length>3&&(
                          <span style={{fontSize:10,color:u.color,opacity:0.6}}>
                            +{u.progetti.length-3} altri programmi
                          </span>
                        )}
                      </div>
                    )}
                  </div>
                ))}
              </div>
            )}
          </div>

        </div>{/* fine col-side */}

      </div>
    </div>
  </>
  )
}