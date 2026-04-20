import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from 'react-router-dom';
import { InfoTooltip } from '../components/UI.jsx';

// ── Colori stati pallet ──────────────────────────────────────────
const STATI = {
  "IN LAVORAZIONE": { bg: "#0d2d5e", fg: "#fff",     border: "#1a4080" },
  "GREZZO":         { bg: "#fefce8", fg: "#854d0e",  border: "#eab308", label: "IN CODA" },
  "FINITO":         { bg: "#dcfce7", fg: "#14532d",  border: "#22c55e" },
  "VUOTO":          { bg: "#f1f5f9", fg: "#94a3b8",  border: "#e2e8f0" },
  "GUASTO":         { bg: "#fef2f2", fg: "#991b1b",  border: "#f87171" },
};
const STATI_ORDER = ["VUOTO", "GREZZO", "FINITO", "GUASTO"];

// Estrae commessa/posizione/fase/sequenza dal nome programma NC
// Formato: 4297_0008_01_026.MPF
//   4297 = commessa
//   0008 = posizione
//   01   = fase
//   026  = numero programma in sequenza
function parseProgram(path) {
  if (!path) return null
  // Rimuovi estensione e path
  const nome = path.replace(/.*\//, '').replace(/\.MPF$/i, '').replace(/_MPF$/i, '')
  // Formato standard: COMMESSA_POSIZIONE_FASE_SEQ (4 parti)
  const p = nome.split('_')
  if (p.length >= 4) {
    return { commessa: p[0], posizione: p[1], fase: p[2], seq: p[3], full: nome }
  }
  if (p.length === 3) {
    return { commessa: p[0], posizione: p[1], fase: p[2], seq: null, full: nome }
  }
  if (p.length === 2) {
    return { commessa: p[0], posizione: p[1], fase: null, seq: null, full: nome }
  }
  return { commessa: nome, posizione: null, fase: null, seq: null, full: nome }
}

const REFRESH_MS = 15000; // GlobalPoller gestisce aggiornamenti veloci ogni 5s via evento

export default function CodaLavorazione() {
  const [pallets, setPallets] = useState(
    Array.from({ length: 6 }, (_, i) => ({ id: i + 1, stato: "VUOTO", programma: null }))
  );
  const [macchina, setMacchina]     = useState(null);
  const [lastUpdate, setLastUpdate] = useState(null);
  const [error, setError]           = useState(null);
  const [palletMenu, setPalletMenu]  = useState(null);
  const [liveCtx, setLiveCtx]        = useState(null);
  const [progettiPallet, setProgettiPallet] = useState({});
  const [modalAssegna, setModalAssegna]     = useState(null);
  // Override feed/mandrino — aggiornato dal GlobalPoller
  const [overrideStato, setOverrideStato] = useState(null);
  // Guard: evita setState su componente smontato
  const mountedRef = useRef(true);
  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false } }, []);
  // { feed: 85, mandrino: 100, ridotto: true, feed_stato: 'ridotto' }
  // ── Coda esecuzione ────────────────────────────────────────────
  const [codaOrdine, setCodaOrdine] = useState([]);   // [3,4,5]
  const [codaSaving, setCodaSaving] = useState(false);
  const dragCodaIdx = useRef(null);
  // Programmi in macchina per pallet
  const [pgmInMacchina, setPgmInMacchina] = useState({}); // {palletNum: {progetto, programmi}}
  const [pgmSelezionati, setPgmSelezionati] = useState({}); // {palletNum: Set(ids)}
  const [pgmSaving, setPgmSaving] = useState(false);
  // Pallet espansi nella coda unificata
  const [palletEspansi, setPalletEspansi] = useState(new Set());
  const [logEventi, setLogEventi]     = useState([])
  const [logLoading, setLogLoading]   = useState(false)
  const [logFiltro, setLogFiltro]     = useState('tutti')

  const fetchLiveContext = async () => {
    try {
      const r = await fetch('/api/macchina-live/live-context')
      if (r.ok) setLiveCtx(await r.json())
    } catch {}
  }

  const navigate = useNavigate();

  async function assegnaProgetto(palletNum, progettoId, progettoNome, progettoColore) {
    // Rimuovi dal pallet precedente se ce n'era uno diverso
    const palletPrecedente = Object.entries(progettiPallet)
      .find(([pn, pr]) => pr.id === progettoId && parseInt(pn) !== palletNum)
    if(palletPrecedente) {
      await fetch(`/api/pallet/${palletPrecedente[0]}/assegna-progetto`, {
        method: 'PATCH', headers: {'Content-Type':'application/json'},
        body: JSON.stringify({progetto_id:null, progetto_nome:null, progetto_colore:null})
      })
    }
    // Scrivi sul nuovo pallet (include cambio stato automatico nel backend)
    const res = await fetch(`/api/pallet/${palletNum}/assegna-progetto`, {
      method: 'PATCH', headers: {'Content-Type':'application/json'},
      body: JSON.stringify({progetto_id: progettoId, progetto_nome: progettoNome, progetto_colore: progettoColore})
    })
    if(!res.ok) {
      const err = await res.json().catch(()=>({}))
      setError(err.detail || 'Errore assegnazione pallet')
      setTimeout(() => setError(null), 4000)
      fetchAll(); return
    }
    // Il backend ha già chiamato sincronizza-coda — carica ordine aggiornato
    const coda = await fetch('/api/pallet/ordine-esecuzione').then(r=>r.ok?r.json():null).catch(()=>null)
    if (coda) setCodaOrdine(coda.ordine || [])
    fetchAll()
    caricaPgmInMacchina()
  }

  async function avviaProgetto(palletNum) {
    const proj = progettiPallet[palletNum]
    if (!proj?.id) return

    // Usa endpoint atomico: IN LAVORAZIONE + da_fare→in_macchina + gestisce pallet precedente
    await fetch(`/api/pallet/${palletNum}/avvia`, { method: 'POST' }).catch(() => {})

    // Metti in cima alla coda
    const nuovoOrdine = [palletNum, ...codaOrdine.filter(n => n !== palletNum)]
    await fetch('/api/pallet/ordine-esecuzione', {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ ordine: nuovoOrdine })
    }).catch(() => {})
    setCodaOrdine(nuovoOrdine)

    // Ricarica tutto
    await fetchAll()
    await caricaPgmInMacchina()
  }

  const fetchAll = useCallback(async () => {
    try {
      const [rPallets, rMacchina] = await Promise.all([
        fetch("/api/pallet/"),
        fetch("/api/macchina-live/stato"),
      ]);

      const palletData  = rPallets.ok  ? await rPallets.json()  : null;
      const macchinaData = rMacchina.ok ? await rMacchina.json() : null;

      if (!mountedRef.current) return;  // componente smontato — ignora

      setMacchina(macchinaData);

      // Backend ritorna { pallet: [{numero:1, stato:"grezzo"}, ...] }
      const palletArr = palletData?.pallet || [];
      setPallets(prev => prev.map(p => {
        const saved = palletArr.find(s => s.numero === p.id) || {};
        // Backend usa minuscolo, UI usa maiuscolo
        let stato = (saved.stato || "vuoto").toUpperCase().replace("_", " ");

        // Sovrascrive con IN LAVORAZIONE se macchina lo conferma live
        if (
          macchinaData?.pallet_attivo === p.id &&
          [1,3].includes(macchinaData?.stato_programma)
        ) {
          stato = "IN LAVORAZIONE";
        }

        return { ...p, stato, programma: saved.programma || null };
      }));

      setLastUpdate(new Date().toLocaleTimeString("it-IT"));
      setError(null);

      // Costruisci progettiPallet direttamente dai dati già in mano
      // I pallet ritornano già con progetto_id/nome/colore dal GET /api/pallet/
      const pInfo = {};
      for (const pal of palletArr) {
        if (pal.progetto_id) {
          pInfo[pal.numero] = {
            id:     pal.progetto_id,
            nome:   pal.progetto_nome   || '',
            colore: pal.progetto_colore || '#1D5FAD',
            pct:    0, completati: 0, totale: 0, da_fare: 0, in_macchina: 0,
          };
          // Carica avanzamento in background (non blocca il render)
          fetch(`/api/pallet/${pal.numero}/progetto-info`)
            .then(r => r.ok ? r.json() : null)
            .then(d => {
              if (d?.progetto) {
                setProgettiPallet(prev => ({...prev, [pal.numero]: d.progetto}));
              }
            }).catch(() => {});
        }
      }
      setProgettiPallet(pInfo);

    } catch {
      setError("Errore connessione");
    }
  }, []);

  // Ricarica quando il GlobalPoller segnala aggiornamenti
  useEffect(() => {
    const onUpdate = (e) => {
      const d = e.detail || {}
      // Aggiorna override a ogni tick (arriva sempre dal poller)
      if (d.override_feed !== undefined || d.override_mandrino !== undefined) {
        setOverrideStato({
          feed:         d.override_feed,
          mandrino:     d.override_mandrino,
          ridotto:      d.override_ridotto || false,
          feed_stato:   d.override_feed_stato,
          mandrino_stato: d.override_mandrino_stato,
        })
      }
      if (d.pallet > 0 || d.in_macchina > 0 || d.completato > 0) {
        fetchAll()
        caricaPgmInMacchina()
        // Risincronizza la coda: un completato potrebbe rimuovere un pallet
        fetch('/api/pallet/sincronizza-coda', { method: 'POST' })
        fetchLog()
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (d?.aggiornato) setCodaOrdine(d.ordine || []) })
          .catch(() => {})
      }
    }
    window.addEventListener('dmgdesk:stati-aggiornati', onUpdate)
    return () => window.removeEventListener('dmgdesk:stati-aggiornati', onUpdate)
  }, [fetchAll])

  useEffect(() => {
    fetchAll()
    // Sincronizza coda al mount — aggiunge automaticamente pallet con in_main
    fetch('/api/pallet/sincronizza-coda', { method: 'POST' })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setCodaOrdine(d.ordine || []) })
      .catch(() =>
        // Fallback: carica ordine esistente
        fetch('/api/pallet/ordine-esecuzione')
          .then(r => r.ok ? r.json() : null)
          .then(d => { if (d) setCodaOrdine(d.ordine || []) })
          .catch(() => {})
      )
    const t = setInterval(() => {
      fetchAll()
      caricaPgmInMacchina()
    }, REFRESH_MS);
    return () => clearInterval(t);
  }, [fetchAll]);

  // Carica programmi in macchina quando cambiano i pallet assegnati
  useEffect(() => {
    caricaPgmInMacchina()
  }, [JSON.stringify(Object.keys(progettiPallet))]);

  const setPalletStato = async (id, stato) => {
    if (stato === "IN LAVORAZIONE") return;
    // Se FINITO e c'è un progetto assegnato — avvisa che i programmi verranno completati
    if (stato === "FINITO") {
      const proj = progettiPallet[id];
      if (proj && proj.in_macchina > 0) {
        const ok = window.confirm(
          `Segnare Pallet ${id} come FINITO?\n\n` +
          `${proj.in_macchina} programma/i "in macchina" del progetto "${proj.nome}" ` +
          `verranno segnati come COMPLETATI automaticamente.`
        );
        if (!ok) return;
      }
    }
    // Se VUOTO e c'è un progetto — avvisa che il legame viene rimosso
    if (stato === "VUOTO") {
      const proj = progettiPallet[id];
      if (proj) {
        const ok = window.confirm(
          `Svuotare Pallet ${id}?\n\nIl progetto "${proj.nome}" verrà slegato dal pallet.`
        );
        if (!ok) return;
      }
    }
    // Aggiornamento ottimistico
    setPallets(prev => prev.map(p => p.id === id ? { ...p, stato } : p));
    try {
      let res;
      if (stato === "VUOTO") {
        // VUOTO = sgancia il progetto + imposta stato
        // Usa assegna-progetto(null) che fa entrambe le cose in un colpo
        res = await fetch(`/api/pallet/${id}/assegna-progetto`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({progetto_id: null, progetto_nome: null, progetto_colore: null}),
        });
      } else {
        // GREZZO / FINITO / GUASTO — solo cambio stato
        res = await fetch(`/api/pallet/${id}`, {
          method: "PATCH",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ stato: stato.toLowerCase() }),
        });
      }
      if (!res.ok) {
        const err = await res.json().catch(() => ({}));
        console.error('PATCH pallet error:', res.status, JSON.stringify(err));
        setError(`Errore: ${err.detail || res.status}`);
      }
      await fetchAll();
    } catch {
      setError("Errore aggiornamento");
      await fetchAll();
    }
  };

  const inLavorazione = [1,3].includes(macchina?.stato_programma);
  const prog          = parseProgram(macchina?.programma_attivo);
  const utensile      = macchina?.utensile_attivo || null;
  const tNum          = macchina?.numero_utensile   || null;
  const alarm         = macchina?.allarme || null;
  const alarmTipo     = macchina?.allarme_tipo || 'allarme'; // 'allarme' | 'messaggio'

  // Carica lista progetti per il modal
  const [listaProgetti, setListaProgetti] = useState([]);
  useEffect(()=>{
    fetch('/api/progetti').then(r=>r.ok?r.json():[]).then(d=>{
      // Mostra solo progetti non assegnati ad altri pallet (o già su questo pallet)
      const palletDiQuesto = modalAssegna ? progettiPallet[modalAssegna.palletId]?.id : null
      setListaProgetti((d.projects||d||[]).filter(p=>{
        if(p.archived) return false
        // Permesso se non assegnato a nessun pallet, o assegnato a questo stesso pallet
        return !p.pallet_assegnato || p.pallet_assegnato === (modalAssegna?.palletId)
      }))
    }).catch(()=>{})
  },[])

  const ModalAssegna = () => {
    if(!modalAssegna) return null;
    const pid = modalAssegna.palletId;
    return(
      <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.5)',
        display:'flex',alignItems:'center',justifyContent:'center',zIndex:500}}
        onClick={()=>setModalAssegna(null)}>
        <div style={{background:'#fff',borderRadius:14,width:480,maxWidth:'92vw',
          maxHeight:'80vh',display:'flex',flexDirection:'column',
          border:'1px solid #D8D5CC',boxShadow:'0 16px 48px rgba(0,0,0,0.2)'}}
          onClick={e=>e.stopPropagation()}>
          <div style={{padding:'16px 20px 12px',borderBottom:'1px solid #E8E6E0',
            display:'flex',alignItems:'center',gap:8}}>
            <span style={{fontSize:16,fontWeight:800,color:'#1A1814',flex:1}}>
              Assegna progetto — Pallet {pid}
            </span>
            <button onClick={()=>setModalAssegna(null)}
              style={{background:'none',border:'1px solid #D8D5CC',borderRadius:6,
                color:'#5A5750',fontSize:12,padding:'4px 10px',cursor:'pointer'}}>✕</button>
          </div>
          <div style={{flex:1,overflowY:'auto',padding:'8px 0'}}>
            {/* Opzione rimuovi */}
            {progettiPallet[pid] && (
              <div onClick={()=>{assegnaProgetto(pid,null,null,null);setModalAssegna(null)}}
                style={{padding:'10px 20px',cursor:'pointer',display:'flex',alignItems:'center',
                  gap:8,borderBottom:'1px solid #F0EEE8'}}>
                <span style={{fontSize:13,color:'#DC2626',fontWeight:600}}>✕ Rimuovi assegnazione</span>
              </div>
            )}
            {listaProgetti.map(p=>(
              <div key={p.id}
                onClick={()=>{assegnaProgetto(pid,p.id,p.name,p.color||'#1D5FAD');setModalAssegna(null)}}
                style={{padding:'10px 20px',cursor:'pointer',
                  background:progettiPallet[pid]?.id===p.id?'#EFF6FF':'transparent',
                  borderBottom:'1px solid #F5F4F0',
                  display:'flex',alignItems:'center',gap:10,
                  transition:'background 0.1s'}}>
                <div style={{width:10,height:10,borderRadius:'50%',
                  background:p.color||'#1D5FAD',flexShrink:0}}/>
                <div style={{flex:1}}>
                  <div style={{fontSize:13,fontWeight:700,color:'#1A1814'}}>{p.name}</div>
                  {(() => {
                    const pgms = (p.steps||[]).flatMap(s=>s.tasks||[])
                      .filter(t=>t.text?.trim().toLowerCase()==='fresatura')
                      .flatMap(t=>t.programs||[]).filter(pg=>pg.tipoGruppo!=='ipm');
                    const done = pgms.filter(pg=>pg.stato==='completato').length;
                    return pgms.length > 0 ? (
                      <div style={{fontSize:11,color:'#9A978E',marginTop:1}}>
                        {done}/{pgms.length} programmi completati
                      </div>
                    ) : null;
                  })()}
                </div>
                {progettiPallet[pid]?.id===p.id && (
                  <span style={{fontSize:11,color:'#1D5FAD',fontWeight:700}}>● assegnato</span>
                )}
              </div>
            ))}
            {listaProgetti.length===0 && (
              <div style={{padding:24,textAlign:'center',color:'#9A978E',fontSize:13}}>
                Nessun progetto attivo
              </div>
            )}
          </div>
        </div>
      </div>
    )
  }

  // ── Funzioni programmi in macchina ───────────────────────────
  async function caricaPgmInMacchina() {
    const nums = pallets.filter(p => progettiPallet[p.id]).map(p => p.id)
    if (!nums.length) return
    const results = {}
    await Promise.all(nums.map(async n => {
      try {
        const r = await fetch(`/api/pallet/${n}/programmi-in-macchina`)
        if (r.ok) results[n] = await r.json()
      } catch {}
    }))
    setPgmInMacchina(results)
  }

  async function completaPgm(palletNum) {
    const sel = pgmSelezionati[palletNum]
    if (!sel || sel.size === 0) return
    setPgmSaving(true)
    try {
      await fetch(`/api/pallet/${palletNum}/programmi-completa`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ids: [...sel] })
      })
      setPgmSelezionati(prev => ({ ...prev, [palletNum]: new Set() }))
      await caricaPgmInMacchina()
    } finally { setPgmSaving(false) }
  }

  function togglePgm(palletNum, id) {
    setPgmSelezionati(prev => {
      const cur = new Set(prev[palletNum] || [])
      cur.has(id) ? cur.delete(id) : cur.add(id)
      return { ...prev, [palletNum]: cur }
    })
  }

  // Colori fissi per progetto (basati sul numero pallet)
  const PAL_COLORS = ['#0d2d5e','#0891b2','#7c3aed','#059669','#d97706','#dc2626']

  // ── Funzioni coda esecuzione ──────────────────────────────────
  const assegnatiCoda = pallets
    .filter(p => progettiPallet[p.id])
    .map(p => ({ numero: p.id, progetto_nome: progettiPallet[p.id]?.nome, progetto_id: progettiPallet[p.id]?.id }))

  const inCodaList  = codaOrdine.map(n => assegnatiCoda.find(p => p.numero === n)).filter(Boolean)
  const fuoriCodaList = assegnatiCoda.filter(p => !codaOrdine.includes(p.numero))

  async function salvaCoda(nuovoOrdine) {
    setCodaOrdine(nuovoOrdine)
    setCodaSaving(true)
    try {
      await fetch('/api/pallet/ordine-esecuzione', {
        method: 'PUT', headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ordine: nuovoOrdine })
      })
    } finally { setCodaSaving(false) }
  }

  function codaDragStart(e, idx) { dragCodaIdx.current = idx; e.dataTransfer.effectAllowed = 'move' }
  function codaDragOver(e, idx) {
    e.preventDefault()
    if (dragCodaIdx.current === null || dragCodaIdx.current === idx) return
    const newList = [...inCodaList]
    const [moved] = newList.splice(dragCodaIdx.current, 1)
    newList.splice(idx, 0, moved)
    dragCodaIdx.current = idx
    setCodaOrdine(newList.map(p => p.numero))
  }
  function codaDrop() { salvaCoda(codaOrdine); dragCodaIdx.current = null }

  // ETA da programmi espansi (tempoStimato)
  function etaDaPgm(palletNum) {
    const pgmData = pgmInMacchina[palletNum]
    if (!pgmData?.programmi?.length) return null
    let tot = 0
    for (const p of pgmData.programmi) {
      if (p.stato === 'completato') continue
      if (p.tempoStimato) tot += parseInt(p.tempoStimato) * 60
    }
    if (!tot) return null
    const h = Math.floor(tot / 3600), m = Math.round((tot % 3600) / 60)
    return h > 0 ? (m > 0 ? `~${h}h ${m}m` : `~${h}h`) : `~${m} min`
  }

  // ── Fetch log eventi ──────────────────────────────────────────────
  const fetchLog = async () => {
    setLogLoading(true)
    try {
      const today = new Date().toISOString().slice(0, 10)
      const [rpt, macchina] = await Promise.all([
        fetch(`/api/report/giornaliero?data=${today}`).then(r => r.ok ? r.json() : null),
        fetch('/api/macchina-live/stato').then(r => r.ok ? r.json() : null),
      ])
      const eventi = []

      // Programmi dalle sessioni
      if (rpt?.sessioni) {
        for (const sess of rpt.sessioni) {
          for (const pgm of (sess.programmi || [])) {
            if (!pgm.inizio) continue
            eventi.push({
              tipo: 'programma',
              ts: pgm.inizio,
              ts_fine: pgm.fine,
              durata_sec: pgm.durata_sec,
              testo: pgm.filename?.replace('.MPF','') || pgm.filename,
              sub: pgm.utensile ? `${pgm.utensile}${pgm.t_number ? ' T'+pgm.t_number : ''}` : null,
              extra: `P${sess.pallet || '?'} · ${sess.progetto || '?'}`,
              colore: '#1D5FAD',
            })
          }
          // Cambio utensile: quando cambia utensile tra programmi consecutivi
          const pgms = (sess.programmi || []).filter(p => p.utensile)
          for (let i = 1; i < pgms.length; i++) {
            if (pgms[i].utensile !== pgms[i-1].utensile && pgms[i].inizio) {
              eventi.push({
                tipo: 'utensile',
                ts: pgms[i].inizio,
                testo: `${pgms[i-1].utensile} → ${pgms[i].utensile}`,
                sub: pgms[i].t_number ? `T${pgms[i].t_number}` : null,
                extra: `P${sess.pallet || '?'}`,
                colore: '#d97706',
              })
            }
          }
        }
      }

      // Fermi
      if (rpt?.fermi_globali) {
        for (const f of rpt.fermi_globali) {
          if (!f.inizio) continue
          eventi.push({
            tipo: 'fermo',
            ts: f.inizio,
            ts_fine: f.fine,
            durata_sec: f.durata_sec,
            testo: f.causa || 'Fermo macchina',
            sub: f.causa ? null : 'Non classificato',
            colore: f.ignorato ? '#94a3b8' : '#f59e0b',
            ignorato: f.ignorato,
          })
        }
      }

      // Cambi pallet dai dati pallet
      try {
        const palRes = await fetch('/api/pallet/').then(r => r.ok ? r.json() : null)
        if (palRes?.pallet) {
          const today2 = new Date().toISOString().slice(0, 10)
          for (const pal of palRes.pallet) {
            if (!pal.aggiornato || pal.stato === 'vuoto') continue
            try {
              // Supporta sia ISO (2026-04-17T14:21:00) che DD/MM/YYYY HH:MM
              let aggTs = pal.aggiornato
              if (!aggTs.includes('T')) {
                // formato DD/MM/YYYY HH:MM:SS o DD/MM/YYYY HH:MM
                const m = aggTs.match(/(\d{2})\/(\d{2})\/(\d{4})\s+(\d{2}:\d{2}(?::\d{2})?)/)
                if (m) aggTs = `${m[3]}-${m[2]}-${m[1]}T${m[4]}`
              }
              const d = new Date(aggTs)
              if (isNaN(d) || d.toISOString().slice(0,10) !== today2) continue
              const statoLabel = { grezzo:'IN CODA', in_lavorazione:'IN LAVORAZIONE', finito:'FINITO', guasto:'GUASTO' }
              eventi.push({
                tipo: 'pallet',
                ts: aggTs,
                testo: `P${pal.numero} → ${statoLabel[pal.stato] || pal.stato.toUpperCase()}`,
                sub: pal.progetto_nome || null,
                colore: '#7c3aed',
              })
            } catch {}
          }
        }
      } catch {}

      // Allarmi: fermi classificati come 'allarme' nel report giornaliero
      if (rpt?.fermi_globali) {
        for (const f of rpt.fermi_globali) {
          if (!f.inizio || f.causa !== 'allarme') continue
          eventi.push({
            tipo: 'allarme',
            ts: f.inizio,
            ts_fine: f.fine,
            durata_sec: f.durata_sec,
            testo: f.allarme_testo || 'Fermo per allarme',
            sub: f.durata_sec ? null : 'In corso',
            colore: '#dc2626',
          })
        }
      }
      // Allarme attivo in questo momento
      if (macchina?.allarme) {
        eventi.push({
          tipo: 'allarme',
          ts: new Date().toISOString(),
          testo: macchina.allarme,
          sub: 'ATTIVO ORA',
          colore: '#dc2626',
        })
      }

      // Ordina per timestamp decrescente
      eventi.sort((a, b) => new Date(b.ts) - new Date(a.ts))
      setLogEventi(eventi)
    } catch(e) {
      console.warn('fetchLog error:', e)
    } finally {
      setLogLoading(false)
    }
  }

  // Carica log quando si apre il tab
  // Carica log all'avvio
  useEffect(() => { fetchLog() }, [])

  return (
    <div style={{
      display: "flex",
      flexDirection: "column",
      gap: 10,
      padding: 16,
      height: "100%",
      boxSizing: "border-box",
      background: "var(--bg-base, #eef2f7)",
      overflow: "hidden",
    }}>

      {/* ── Banner override ridotto — in cima ───────────────────────── */}
      {overrideStato?.ridotto && (
        <div style={{ flexShrink: 0, padding: '10px 16px', borderRadius: 10,
          background: '#fffbeb', border: '1.5px solid #f59e0b',
          display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, fontWeight: 800, color: '#92400e',
            background: '#fef3c7', padding: '3px 10px', borderRadius: 6, flexShrink: 0 }}>
            OVERRIDE RIDOTTO
          </span>
          {overrideStato.feed != null && overrideStato.feed < 90 && (
            <span style={{ fontSize: 13, fontFamily: 'monospace', color: '#92400e' }}>
              Feed: <b>{overrideStato.feed}%</b>
            </span>
          )}
          {overrideStato.mandrino != null && overrideStato.mandrino < 90 && (
            <span style={{ fontSize: 13, fontFamily: 'monospace', color: '#92400e' }}>
              Mandrino: <b>{overrideStato.mandrino}%</b>
            </span>
          )}
          <span style={{ fontSize: 11, color: '#a16207', marginLeft: 'auto', fontStyle: 'italic' }}>
            {overrideStato.feed_stato === 'basso' || overrideStato.mandrino_stato === 'basso'
              ? 'Override molto basso — controllare setup o utensile'
              : 'Operatore ha rallentato la macchina'}
          </span>
        </div>
      )}

      {/* ── Programma senza progetto ─────────────────────────────────── */}
      {liveCtx && !liveCtx.match && liveCtx.programma_attivo && (
        <div style={{ flexShrink: 0, padding: '8px 14px', borderRadius: 8,
          background: '#F5F4F0', border: '1px solid #D8D5CC',
          fontSize: 12, color: '#9A978E', display: 'flex', gap: 8 }}>
          <span>⚙</span>
          <span>In esecuzione: <code style={{ fontFamily: 'monospace' }}>{liveCtx.programma_attivo}</code> — nessun progetto associato</span>
        </div>
      )}

      {/* ── Due colonne ──────────────────────────────────────────────── */}
      <div style={{ flex: 1, minHeight: 0, display: 'flex', gap: 14, overflow: 'hidden' }}>

      {/* COL SINISTRA */}
      <div style={{ flex: '0 0 calc(50% - 7px)', minWidth: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 10 }}>

      {/* ── Banner live context (programma in esecuzione) ───────── */}
      {liveCtx?.match && (
        <div style={{ flexShrink: 0, padding: '12px 16px', borderRadius: 10,
          background: liveCtx.match.allerta_utensile ? '#FEF9C3' : '#EFF6FF',
          border: '1px solid ' + (liveCtx.match.allerta_utensile ? '#D97706' : '#1D5FAD') + '44',
          display: 'flex', flexDirection: 'column', gap: 8 }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <div style={{ width: 10, height: 10, borderRadius: '50%',
              background: liveCtx.match.progetto_colore, flexShrink: 0 }}/>
            <span style={{ fontSize: 14, fontWeight: 800, color: '#1A1814' }}>
              {liveCtx.match.progetto_nome}
            </span>
            {liveCtx.match.pallet && (
              <span style={{ fontSize: 12, color: '#5A5750' }}>· Pallet {liveCtx.match.pallet}</span>
            )}
            <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#1D5FAD',
              background: '#DBEAFE', padding: '1px 8px', borderRadius: 6, marginLeft: 4 }}>
              {liveCtx.match.programma_corrente}
            </span>
            {liveCtx.match.allerta_utensile && (
              <span style={{ fontSize: 11, fontWeight: 700,
                color: liveCtx.match.allerta_utensile === 'fin_vita' ? '#D97706' : '#DC2626',
                background: liveCtx.match.allerta_utensile === 'fin_vita' ? '#FEF9C3' : '#FEE2E2',
                padding: '2px 8px', borderRadius: 20 }}>
                {liveCtx.match.allerta_utensile === 'fin_vita' ? '⚠ Utensile a fine vita' : '✗ Utensile disabilitato'}
              </span>
            )}
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
            <div style={{ flex: 1, height: 5, background: '#E2E8F0', borderRadius: 3, overflow: 'hidden' }}>
              <div style={{ height: '100%', borderRadius: 3,
                width: `${liveCtx.match.pct_avanzamento}%`,
                background: liveCtx.match.progetto_colore, transition: 'width 0.5s' }}/>
            </div>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#5A5750', minWidth: 80 }}>
              <span style={{display:'flex',alignItems:'center',gap:3}}>
                {liveCtx.match.programmi_completati}/{liveCtx.match.programmi_totali} pgm · {liveCtx.match.pct_avanzamento}%
                <InfoTooltip text={"Avanzamento della commessa corrente.\nProgrammi completati / totali nel MAIN × 100.\nSolo programmi con stato completato vengono conteggiati come eseguiti."} />
              </span>
            </span>
            {liveCtx.match.prossimi_programmi?.length > 0 && (
              <span style={{ fontSize: 11, color: '#9A978E' }}>
                Prossimo: {liveCtx.match.prossimi_programmi[0].filename}
              </span>
            )}
          </div>
        </div>
      )}
      {/* ── Griglia pallet ─────────────────────────────────── */}
      <div style={{ flexShrink: 0 }}>
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: 8 }}>
          <span style={{ fontSize: 11, fontWeight: 700, color: '#0d2d5e', letterSpacing: 1, textTransform: 'uppercase', display:'flex', alignItems:'center', gap:4 }}>
            Pallet
            <InfoTooltip text={"Stati pallet:\n\n• IN LAVORAZIONE — pallet in macchina, programmi in esecuzione\n• IN CODA (GREZZO) — MAIN generato, programmi pronti, in coda per la macchina\n• FINITO — lavorazione completata, pezzo da scaricare\n• GUASTO — lavorazione interrotta anomalmente (rottura utensile, allarme)\n• VUOTO — pallet libero, nessuna commessa assegnata\n\nClick su un pallet per cambiare stato manualmente."} position='right' />
          </span>
          {lastUpdate && <span style={{ fontSize: 10, color: '#94a3b8' }}>{lastUpdate}</span>}
        </div>

        {/* Pallet LIVE — a tutta larghezza, con stato macchina integrato */}
        {pallets.filter(p => p.stato === 'IN LAVORAZIONE').map(p => {
          const proj = progettiPallet[p.id]
          return (
            <div key={p.id} style={{
              background: '#dbeafe', border: '2px solid #1D5FAD',
              borderRadius: 12, padding: '12px 16px', marginBottom: 8
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
                <span style={{ fontSize: 28, fontWeight: 900, color: '#0d2d5e', lineHeight: 1 }}>P{p.id}</span>
                <div style={{ width: 8, height: 8, borderRadius: '50%', background: '#22c55e',
                  boxShadow: '0 0 6px #22c55e', flexShrink: 0 }}/>
                <span style={{ fontSize: 12, fontWeight: 800, color: '#1D5FAD', letterSpacing: '0.06em' }}>IN LAVORAZIONE</span>
                {/* Programma corrente integrato */}
                {prog && (
                  <span style={{ fontSize: 12, fontFamily: 'monospace', color: '#1D5FAD',
                    background: '#fff', padding: '2px 8px', borderRadius: 5, marginLeft: 4 }}>
                    {prog.full}
                  </span>
                )}
                {/* Utensile */}
                {utensile && (
                  <span style={{ fontSize: 12, fontFamily: 'monospace', fontWeight: 700,
                    color: '#92400e', background: '#fef3c7', padding: '2px 8px', borderRadius: 5 }}>
                    {utensile}{tNum > 0 ? ` T${tNum}` : ''}
                  </span>
                )}
                {/* Allarme */}
                {alarm && alarmTipo === 'allarme' && (
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#991b1b',
                    background: '#fef2f2', padding: '2px 8px', borderRadius: 5, marginLeft: 'auto' }}>
                    🔴 {alarm}
                  </span>
                )}
                {alarm && alarmTipo === 'messaggio' && (
                  <span style={{ fontSize: 11, fontWeight: 700, color: '#92400e',
                    background: '#fffbeb', padding: '2px 8px', borderRadius: 5, marginLeft: 'auto' }}>
                    🟡 {alarm}
                  </span>
                )}
              </div>
              {proj && (
                <>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 5 }}>
                    <div style={{ width: 7, height: 7, borderRadius: '50%', background: proj.colore, flexShrink: 0 }}/>
                    <span style={{ fontSize: 13, fontWeight: 700, color: '#0d2d5e' }}>{proj.nome}</span>
                    <span style={{ fontSize: 11, color: '#1D5FAD', marginLeft: 'auto' }}>
                      {proj.completati}/{proj.totale} pgm · {proj.pct}%
                    </span>
                  </div>
                  <div style={{ height: 5, background: 'rgba(29,95,173,0.15)', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${proj.pct}%`, background: proj.colore, borderRadius: 3 }}/>
                  </div>
                </>
              )}
              {!proj && (
                <div style={{ fontSize: 12, color: '#64748b', fontStyle: 'italic' }}>Nessun progetto assegnato</div>
              )}
            </div>
          )
        })}

        {/* Pallet con progetto non in lavorazione — card normale */}
        <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 8, marginBottom: 8 }}>
          {pallets.filter(p => p.stato !== 'IN LAVORAZIONE' && progettiPallet[p.id]).map(p => {
            const s        = STATI[p.stato] || STATI['VUOTO']
            const isActive = macchina?.pallet_attivo === p.id
            const proj     = progettiPallet[p.id]
            const isCompleto = proj && proj.pct === 100
            const cardBg   = isCompleto ? '#dcfce7' : s.bg
            const cardBorder = isCompleto ? '#16a34a' : isActive ? '#f59e0b' : s.border
            const cardFg   = isCompleto ? '#14532d' : s.fg
            return (
              <div key={p.id}
                title="Click per cambiare stato"
                style={{ background: cardBg, border: `2px solid ${cardBorder}`, borderRadius: 10,
                  padding: '12px 14px', cursor: 'pointer', position: 'relative',
                  boxShadow: isActive ? '0 0 0 3px rgba(245,158,11,0.25)' : 'none',
                  transition: 'all 0.2s', userSelect: 'none' }}
                onClick={e => setPalletMenu({ id: p.id, x: e.clientX, y: e.clientY })}>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: 4 }}>
                  <span style={{ fontSize: 28, fontWeight: 900, color: cardFg, lineHeight: 1 }}>P{p.id}</span>
                  <span style={{ fontSize: 9, fontWeight: 800, color: cardFg, letterSpacing: 1,
                    background: cardBorder + '22', padding: '2px 6px', borderRadius: 4 }}>
                    {STATI[p.stato]?.label || p.stato}
                  </span>
                </div>
                <div style={{ display: 'flex', alignItems: 'center', gap: 4, marginBottom: 4 }}>
                  <div style={{ width: 6, height: 6, borderRadius: '50%', background: proj.colore, flexShrink: 0 }}/>
                  <span style={{ fontSize: 12, fontWeight: 700, color: cardFg,
                    overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{proj.nome}</span>
                </div>
                <div style={{ height: 4, background: 'rgba(0,0,0,0.1)', borderRadius: 2, overflow: 'hidden', marginBottom: 3 }}>
                  <div style={{ height: '100%', background: proj.colore, width: `${proj.pct}%`, borderRadius: 2 }}/>
                </div>
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <span style={{ fontSize: 10, color: cardFg, opacity: 0.8, display:'flex', alignItems:'center', gap:3 }}>
                    {proj.completati}/{proj.totale} pgm
                    <InfoTooltip text={"Programmi NC completati rispetto al totale pianificato nel MAIN.\nLa barra colorata mostra la percentuale di avanzamento." } position='top' />
                  </span>
                  <span style={{ fontSize: 12, fontWeight: 800, color: cardFg }}>{proj.pct}%</span>
                </div>
                {isCompleto && p.stato !== 'FINITO' && (
                  <button onClick={e => { e.stopPropagation(); setPalletStato(p.id, 'FINITO') }}
                    style={{ marginTop: 5, width: '100%', background: '#166534', border: 'none', borderRadius: 4,
                      color: '#fff', fontWeight: 700, fontSize: 9, padding: '3px 0', cursor: 'pointer' }}>
                    ✓ Segna Finito
                  </button>
                )}
              </div>
            )
          })}
        </div>

        {/* Pallet VUOTO — riga compatta */}
        {pallets.filter(p => p.stato !== 'IN LAVORAZIONE' && !progettiPallet[p.id]).length > 0 && (
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {pallets.filter(p => p.stato !== 'IN LAVORAZIONE' && !progettiPallet[p.id]).map(p => (
              <div key={p.id}
                onClick={e => { if (p.stato !== 'IN LAVORAZIONE') setPalletMenu({ id: p.id, x: e.clientX, y: e.clientY }) }}
                style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '5px 10px',
                  background: '#f1f5f9', border: '1px dashed #cbd5e1', borderRadius: 8,
                  cursor: 'pointer', opacity: 0.6, userSelect: 'none' }}>
                <span style={{ fontSize: 13, fontWeight: 700, color: '#94a3b8' }}>P{p.id}</span>
                <span style={{ fontSize: 9, fontWeight: 700, color: '#94a3b8', letterSpacing: '0.05em' }}>VUOTO</span>
                <span style={{ fontSize: 10, color: '#94a3b8' }}>+</span>
              </div>
            ))}
          </div>
        )}

        <ModalAssegna/>
        <style>{`@keyframes blink{0%,100%{opacity:1}50%{opacity:0.3}}`}</style>
      </div>

        {/* ── Card stato macchina compatta ─────────────────────────── */}
        <div style={{
          background: inLavorazione ? '#0d2d5e' : '#ffffff',
          border: '1px solid ' + (inLavorazione ? '#1a4080' : '#e2e8f0'),
          borderRadius: 12, padding: '12px 16px', flexShrink: 0
        }}>
          {/* Riga principale: stato + programma + utensile */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 12, marginBottom: prog || utensile ? 10 : 0 }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <div style={{
                width: 10, height: 10, borderRadius: '50%', flexShrink: 0,
                background: inLavorazione ? '#22c55e' : '#94a3b8',
                boxShadow: inLavorazione ? '0 0 6px #22c55e' : 'none'
              }}/>
              <span style={{ fontSize: 13, fontWeight: 800,
                color: inLavorazione ? '#fff' : '#374151' }}>
                {inLavorazione ? 'IN ESECUZIONE' : 'FERMA'}
              </span>
            </div>
            {macchina?.pallet_attivo > 0 && (
              <span style={{ fontSize: 11, color: inLavorazione ? '#93c5fd' : '#94a3b8' }}>
                Pallet {macchina.pallet_attivo}
              </span>
            )}
            {overrideStato?.ridotto && (
              <span style={{ fontSize: 11, fontWeight: 700, color: '#92400e',
                background: '#fef3c7', padding: '2px 8px', borderRadius: 5, marginLeft: 'auto' }}>
                Feed {overrideStato.feed}% · Man {overrideStato.mandrino}%
              </span>
            )}
          </div>

          {/* Programma + utensile */}
          {(prog || utensile) && (
            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 12 }}>
              <div>
                <div style={{ fontSize: 9, letterSpacing: 1, marginBottom: 4,
                  color: inLavorazione ? '#93c5fd' : '#94a3b8', textTransform: 'uppercase' }}>Programma</div>
                {prog ? (
                  <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'baseline' }}>
                    {[
                      { label: 'COMM.', val: prog.commessa },
                      { label: 'POS.', val: prog.posizione },
                      { label: 'FASE', val: prog.fase },
                      { label: 'N°', val: prog.seq },
                    ].filter(x => x.val).map(x => (
                      <div key={x.label} style={{ display: 'flex', flexDirection: 'column', alignItems: 'center' }}>
                        <span style={{ fontSize: 9, color: inLavorazione ? '#93c5fd' : '#94a3b8',
                          letterSpacing: 1, marginBottom: 1 }}>{x.label}</span>
                        <span style={{ fontSize: 15, fontWeight: 700, fontFamily: 'monospace',
                          color: inLavorazione ? '#fff' : '#0d2d5e', lineHeight: 1 }}>{x.val}</span>
                      </div>
                    ))}
                  </div>
                ) : (
                  <span style={{ fontSize: 13, color: inLavorazione ? '#4e7aad' : '#94a3b8' }}>—</span>
                )}
              </div>
              <div>
                <div style={{ fontSize: 9, letterSpacing: 1, marginBottom: 4,
                  color: inLavorazione ? '#93c5fd' : '#94a3b8', textTransform: 'uppercase' }}>Utensile</div>
                {utensile ? (
                  <div>
                    <div style={{ fontSize: 15, fontWeight: 800, fontFamily: 'monospace',
                      color: inLavorazione ? '#fbbf24' : '#0d2d5e', letterSpacing: '-0.02em' }}>{utensile}</div>
                    {tNum > 0 && (
                      <div style={{ fontSize: 11, color: inLavorazione ? '#93c5fd' : '#64748b', marginTop: 2 }}>
                        T{tNum}
                      </div>
                    )}
                  </div>
                ) : (
                  <span style={{ fontSize: 13, color: inLavorazione ? '#4e7aad' : '#94a3b8' }}>—</span>
                )}
              </div>
            </div>
          )}
        </div>

        {/* Allarmi standalone se non IN LAVORAZIONE */}
        {(!inLavorazione) && alarm && alarmTipo === 'allarme' && (
          <div style={{ background: '#fef2f2', border: '1px solid #fca5a5',
            borderRadius: 12, padding: '12px 16px', flexShrink: 0 }}>
            <div style={{ fontSize: 10, color: '#991b1b', letterSpacing: 1, marginBottom: 4, fontWeight: 700 }}>
              🔴 ALLARME MACCHINA
            </div>
            <div style={{ fontSize: 12, color: '#991b1b', fontWeight: 500 }}>{alarm}</div>
          </div>
        )}
        {(!inLavorazione) && alarm && alarmTipo === 'messaggio' && (
          <div style={{ background: '#fffbeb', border: '1px solid #fcd34d',
            borderRadius: 12, padding: '12px 16px', flexShrink: 0 }}>
            <div style={{ fontSize: 10, color: '#92400e', letterSpacing: 1, marginBottom: 4, fontWeight: 700 }}>
              🟡 MESSAGGIO MACCHINA
            </div>
            <div style={{ fontSize: 12, color: '#92400e', fontWeight: 500 }}>{alarm}</div>
          </div>
        )}

        {error && (
          <div style={{ background: '#fef3c7', border: '1px solid #fcd34d',
            borderRadius: 8, padding: '8px 12px', fontSize: 11, color: '#92400e', flexShrink: 0 }}>
            ⚠️ {error}
          </div>
        )}

      </div>
      {palletMenu && createPortal(
        <div style={{ position: 'fixed', inset: 0, zIndex: 9998 }}
          onClick={() => setPalletMenu(null)}>
          <div style={{
            position: 'fixed', left: palletMenu.x, top: palletMenu.y,
            background: '#ffffff',
            border: '1px solid #D8D5CC',
            borderRadius: 10,
            boxShadow: '0 8px 32px rgba(0,0,0,0.25), 0 2px 8px rgba(0,0,0,0.15)',
            zIndex: 9999, minWidth: 200, overflow: 'hidden',
          }} onClick={e => e.stopPropagation()}>
            {/* Header menu */}
            {(()=>{
              const pal = pallets.find(p => p.id === palletMenu.id)
              const proj = progettiPallet[palletMenu.id]
              // Colori identici alle card pallet
              const STATI_MENU = [
                { s:'GREZZO',  dot:'#eab308', bg:'#fefce8', fg:'#854d0e', label:'IN CODA' },
                { s:'FINITO',  dot:'#22c55e', bg:'#dcfce7', fg:'#14532d' },
                { s:'GUASTO',  dot:'#f87171', bg:'#fef2f2', fg:'#991b1b' },
                { s:'VUOTO',   dot:'#cbd5e1', bg:'#f1f5f9', fg:'#94a3b8' },
              ]
              return(<>
                <div style={{ padding:'10px 14px 8px', fontSize:11, fontWeight:700,
                  color:'#0d2d5e', borderBottom:'1px solid #E8E6E0',
                  background:'#F8F7F4',
                  letterSpacing:'0.06em', display:'flex', alignItems:'center', gap:6 }}>
                  <span style={{fontWeight:900}}>P{palletMenu.id}</span>
                  {proj && <span style={{fontWeight:400,color:'#64748b',overflow:'hidden',
                    textOverflow:'ellipsis',whiteSpace:'nowrap',maxWidth:100}}>· {proj.nome}</span>}
                </div>

                {/* Link al progetto */}
                {proj && (
                  <>
                    <div onClick={()=>{
                        sessionStorage.setItem('dmgdesk_apri_progetto_id', progettiPallet[palletMenu.id]?.id||'')
                        setPalletMenu(null)
                        navigate('/progetti')
                      }}
                      style={{padding:'9px 14px',cursor:'pointer',fontSize:12,fontWeight:700,
                        color:'#1D5FAD',display:'flex',alignItems:'center',gap:8,
                        background:'#EFF6FF',borderBottom:'1px solid #E8E6E0'}}
                      onMouseEnter={e=>e.currentTarget.style.background='#EFF6FF'}
                      onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                      <span>📋</span>
                      <span>Apri progetto</span>
                      <span style={{marginLeft:'auto',fontSize:10,color:'#9A978E'}}>→</span>
                    </div>
                    <div onClick={()=>{ setModalAssegna({palletId:palletMenu.id}); setPalletMenu(null) }}
                      style={{padding:'9px 14px',cursor:'pointer',fontSize:12,
                        color:'#5A5750',display:'flex',alignItems:'center',gap:8,
                        borderBottom:'1px solid #F0EEE8'}}
                      onMouseEnter={e=>e.currentTarget.style.background='#F5F4F0'}
                      onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                      <span>🔄</span>
                      <span>Cambia progetto</span>
                    </div>
                  </>
                )}
                {!proj && (
                  <div onClick={()=>{ setModalAssegna({palletId:palletMenu.id}); setPalletMenu(null) }}
                    style={{padding:'9px 14px',cursor:'pointer',fontSize:12,fontWeight:600,
                      color:'#1D5FAD',display:'flex',alignItems:'center',gap:8,
                      borderBottom:'1px solid #F0EEE8'}}
                    onMouseEnter={e=>e.currentTarget.style.background='#EFF6FF'}
                    onMouseLeave={e=>e.currentTarget.style.background='transparent'}>
                    <span>📋</span>
                    <span>Assegna progetto</span>
                  </div>
                )}

                {/* Separatore stati */}
                <div style={{padding:'6px 14px 3px',fontSize:9,fontWeight:700,
                  color:'#9A978E',letterSpacing:'0.08em',background:'#F8F7F4',
                  borderTop:'1px solid #E8E6E0'}}>STATO</div>

                {/* Reset GUASTO — visibile solo se pallet è in GUASTO */}
                {pal?.stato?.toUpperCase() === 'GUASTO' && proj && (
                  <div onClick={async () => {
                    setPalletMenu(null)
                    try {
                      const r = await fetch(`/api/main-sync/reset-guasto/${proj.id}`, { method: 'POST' })
                      const d = await r.json()
                      if (d.ok) await fetchAll()
                    } catch {}
                  }}
                    style={{padding:'9px 14px',cursor:'pointer',fontSize:12,fontWeight:700,
                      color:'#166534',background:'#dcfce7',
                      display:'flex',alignItems:'center',gap:8,
                      borderBottom:'1px solid #E8E6E0'}}
                    onMouseEnter={e=>e.currentTarget.style.background='#bbf7d0'}
                    onMouseLeave={e=>e.currentTarget.style.background='#dcfce7'}>
                    <span>🔄</span>
                    <span>Reset GUASTO — riallinea da MAIN</span>
                  </div>
                )}

                {/* Voci stato */}
                {STATI_MENU.map(({s, dot, bg, fg, label}) => {
                  const sel = pal?.stato === s
                  return (
                    <div key={s}
                      onClick={() => { setPalletStato(palletMenu.id, s); setPalletMenu(null) }}
                      style={{ padding:'9px 14px', cursor:'pointer', fontSize:13,
                        fontWeight: sel ? 700 : 400,
                        color: sel ? fg : '#374151',
                        background: sel ? bg : 'transparent',
                        display:'flex', alignItems:'center', gap:10,
                        borderLeft: sel ? `3px solid ${dot}` : '3px solid transparent' }}
                      onMouseEnter={e => { if(!sel) e.currentTarget.style.background='#f1f5f9' }}
                      onMouseLeave={e => { e.currentTarget.style.background = sel ? bg : 'transparent' }}>
                      <div style={{width:10,height:10,borderRadius:'50%',
                        background:dot,flexShrink:0}}/>
                      <span>{label || s}</span>
                      {sel && <span style={{marginLeft:'auto',fontSize:11,color:fg}}>✓</span>}
                    </div>
                  )
                })}
              </>)
            })()}
          </div>
        </div>
      , document.body)}

      {/* COL DESTRA — Coda sopra + Log sotto */}
      <div style={{ flex: '0 0 calc(50% - 7px)', display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0, overflow: 'hidden' }}>

        {/* ── CODA ESECUZIONE (altezza fissa, max 40% dello spazio) ── */}
        <div style={{ flexShrink: 0 }}>
          {assegnatiCoda.length > 0 && (
<div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '12px 16px', flex: 1, overflowY: 'auto' }}>
            {/* Header */}
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 12 }}>
              <span style={{ fontSize: 13, fontWeight: 800, color: '#0d2d5e' }}>📋 Coda esecuzione</span>
              {codaSaving && <span style={{ fontSize: 11, color: '#94a3b8' }}>salvataggio…</span>}
              {(() => {
                const totSel = Object.values(pgmSelezionati).reduce((acc, s) => acc + (s?.size || 0), 0)
                return totSel > 0 ? (
                  <button onClick={() => Object.entries(pgmSelezionati).forEach(([n, s]) => { if (s?.size > 0) completaPgm(parseInt(n)) })}
                    disabled={pgmSaving}
                    style={{ marginLeft: 'auto', background: '#166534', border: 'none', borderRadius: 7,
                      color: '#fff', fontWeight: 700, fontSize: 12, padding: '5px 14px', cursor: 'pointer' }}>
                    ✓ Segna {totSel} completat{totSel === 1 ? 'o' : 'i'}
                  </button>
                ) : (
                  <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 'auto' }}>trascina per riordinare</span>
                )
              })()}
            </div>

            {/* Pallet in coda */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
              {inCodaList.map((p, idx) => {
                const pgmData = pgmInMacchina[p.numero]
                const hasPgm  = pgmData?.programmi?.length > 0
                const espanso = palletEspansi.has(p.numero)
                const col     = PAL_COLORS[(p.numero - 1) % PAL_COLORS.length]
                const pal     = pallets.find(pl => pl.id === p.numero)
                const isLav   = (pal?.stato || '').toUpperCase() === 'IN LAVORAZIONE'
                const nInLav  = pgmData?.programmi?.filter(pg => pg.stato === 'in_lavorazione').length || 0
                const nInMain = pgmData?.programmi?.filter(pg => pg.stato === 'in_main').length || 0
                const sel     = pgmSelezionati[p.numero] || new Set()
                const eta     = etaDaPgm(p.numero)

                return (
                  <div key={p.numero}
                    draggable={!espanso}
                    onDragStart={e => codaDragStart(e, idx)}
                    onDragOver={e => codaDragOver(e, idx)}
                    onDrop={codaDrop}
                    style={{ border: `1.5px solid ${isLav ? '#1D5FAD' : '#e2e8f0'}`,
                      borderLeft: `4px solid ${col}`,
                      borderRadius: 10, overflow: 'hidden',
                      background: isLav ? '#f0f7ff' : '#f8fafc',
                      transition: 'all 0.15s' }}>
                    {/* Riga pallet */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 12px',
                      cursor: hasPgm ? 'pointer' : 'grab', userSelect: 'none' }}
                      onClick={() => hasPgm && setPalletEspansi(prev => {
                        const n = new Set(prev)
                        n.has(p.numero) ? n.delete(p.numero) : n.add(p.numero)
                        return n
                      })}>
                      <span style={{ fontSize: 9, fontWeight: 800, color: col,
                        background: col + '18', padding: '2px 6px', borderRadius: 8, flexShrink: 0 }}>
                        {idx + 1}°
                      </span>
                      <span style={{ fontSize: 13, fontWeight: 900, color: col, minWidth: 24 }}>P{p.numero}</span>
                      <span style={{ fontSize: 12, fontWeight: 700, color: '#0d2d5e',
                        fontFamily: 'monospace', flex: 1,
                        overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>{p.progetto_nome}</span>
                      {isLav && <span style={{ fontSize: 10, fontWeight: 700, color: '#1D5FAD',
                        background: '#dbeafe', padding: '1px 6px', borderRadius: 5, flexShrink: 0 }}>LIVE</span>}
                      {nInLav > 0 && !isLav && <span style={{ fontSize: 10, color: '#1D5FAD',
                        background: '#eff6ff', padding: '1px 6px', borderRadius: 5, flexShrink: 0 }}>
                        {nInLav} lav.</span>}
                      {nInMain > 0 && <span style={{ fontSize: 10, color: '#92400e',
                        background: '#fef3c7', padding: '1px 6px', borderRadius: 5, flexShrink: 0 }}>
                        {nInMain} coda</span>}
                      {/* ETA — nuova */}
                      {eta && (
                        <span style={{ fontSize: 11, fontWeight: 700, fontFamily: 'monospace',
                          color: isLav ? '#1D5FAD' : '#475569', flexShrink: 0 }}>{eta}</span>
                      )}
                      {hasPgm && <span style={{ fontSize: 11, color: '#94a3b8', flexShrink: 0 }}>
                        {espanso ? '▴' : '▾'}
                      </span>}
                      <button onClick={e => { e.stopPropagation(); salvaCoda(codaOrdine.filter(n => n !== p.numero)) }}
                        style={{ background: 'none', border: 'none', cursor: 'pointer',
                          color: '#94a3b8', fontSize: 14, lineHeight: 1, padding: '0 2px', flexShrink: 0 }}>✕</button>
                    </div>

                    {/* Programmi espansi inline */}
                    {espanso && hasPgm && (
                      <div style={{ borderTop: '1px solid ' + col + '22', background: '#fff',
                        padding: '6px 10px', display: 'flex', flexDirection: 'column', gap: 2 }}>
                        {pgmData.programmi.map(pgm => {
                          const checked = sel.has(pgm.id)
                          const isInLav = pgm.stato === 'in_lavorazione'
                          return (
                            <div key={pgm.id}
                              onClick={() => togglePgm(p.numero, pgm.id)}
                              style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '4px 8px',
                                borderRadius: 6, cursor: 'pointer', userSelect: 'none',
                                background: checked ? '#dcfce7' : isInLav ? '#eff6ff' : 'transparent',
                                border: `1px solid ${checked ? '#166534' : isInLav ? '#1D5FAD' : '#e2e8f0'}`,
                                transition: 'all 0.1s' }}>
                              <input type='checkbox' checked={checked}
                                onChange={() => togglePgm(p.numero, pgm.id)}
                                onClick={e => e.stopPropagation()}
                                style={{ accentColor: '#166534', cursor: 'pointer', width: 13, height: 13, flexShrink: 0 }} />
                              <span style={{ fontSize: 9, fontWeight: 800, padding: '1px 4px', borderRadius: 3,
                                flexShrink: 0,
                                background: isInLav ? '#1D5FAD' : '#fef3c7',
                                color: isInLav ? '#fff' : '#92400e' }}>
                                {isInLav ? '⚙' : '📋'}
                              </span>
                              <span style={{ fontSize: 11, fontWeight: 700, color: col,
                                fontFamily: 'monospace', minWidth: 28 }}>{pgm.numPgm}</span>
                              <span style={{ fontSize: 11, fontFamily: 'monospace', color: '#1e293b',
                                flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {pgm.utensile || '—'}
                              </span>
                              <span style={{ fontSize: 10, color: '#94a3b8', fontFamily: 'monospace',
                                flexShrink: 0, maxWidth: 120, overflow: 'hidden',
                                textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                                {(pgm.filename || '').replace('.MPF', '')}
                              </span>
                              {pgm.tempoStimato && (
                                <span style={{ fontSize: 10, color: '#475569', flexShrink: 0 }}>⏱{pgm.tempoStimato}m</span>
                              )}
                            </div>
                          )
                        })}
                      </div>
                    )}
                  </div>
                )
              })}
            </div>

            {/* Pallet fuori coda */}
            {fuoriCodaList.length > 0 && (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap', marginTop: 10,
                paddingTop: 10, borderTop: '1px solid #e2e8f0' }}>
                <span style={{ fontSize: 10, color: '#94a3b8', fontWeight: 700, letterSpacing: '0.06em' }}>+ AGGIUNGI:</span>
                {fuoriCodaList.map(p => (
                  <button key={p.numero}
                    onClick={() => salvaCoda([...codaOrdine, p.numero])}
                    style={{ background: '#f1f5f9', border: '1.5px dashed #94a3b8', borderRadius: 8,
                      padding: '4px 10px', cursor: 'pointer', fontSize: 11, color: '#475569', fontWeight: 600 }}>
                    P{p.numero} {p.progetto_nome}
                  </button>
                ))}
              </div>
            )}
          </div>

          )}
          {assegnatiCoda.length === 0 && (
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12,
              padding: '16px 20px', textAlign: 'center', color: '#94a3b8', fontSize: 13 }}>
              Nessun progetto in coda — assegna un progetto a un pallet e genera il MAIN
            </div>
          )}
        </div>

        {/* ── LOG TURNO (spazio rimanente, scrollabile) ────────────── */}
        <div style={{ flex: 1, minHeight: 0, background: '#fff', border: '1px solid #e2e8f0',
          borderRadius: 12, padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6, overflow: 'hidden' }}>

          {/* Header + refresh */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexShrink: 0 }}>
            <span style={{ fontSize: 14, fontWeight: 800, color: '#0d2d5e' }}>📜 Log turno</span>
            <span style={{ fontSize: 11, color: '#94a3b8' }}>
              {logEventi.length > 0 ? `${logEventi.length} eventi` : ''}
            </span>
            <button onClick={fetchLog}
              style={{ marginLeft: 'auto', background: 'none', border: '1px solid #e2e8f0',
                borderRadius: 6, padding: '4px 12px', cursor: 'pointer', fontSize: 13, color: '#64748b' }}>
              ↻
            </button>
          </div>

          {/* Filtri */}
          <div style={{ display: 'flex', gap: 5, flexWrap: 'wrap', flexShrink: 0 }}>
            {[
              { id: 'tutti',     label: 'Tutti',      col: '#64748b' },
              { id: 'programma', label: '⚙ Pgm',      col: '#1D5FAD' },
              { id: 'utensile',  label: '🔧 Utens.',   col: '#d97706' },
              { id: 'fermo',     label: '⏸ Fermi',    col: '#f59e0b' },
              { id: 'allarme',   label: '🚨 Allarmi',  col: '#dc2626' },
              { id: 'pallet',    label: '📦 Pallet',   col: '#7c3aed' },
            ].map(f => (
              <button key={f.id} onClick={() => setLogFiltro(f.id)}
                style={{ padding: '4px 11px', borderRadius: 6, border: 'none', cursor: 'pointer',
                  fontSize: 12, fontWeight: logFiltro === f.id ? 700 : 500,
                  background: logFiltro === f.id ? f.col : '#f1f5f9',
                  color: logFiltro === f.id ? '#fff' : '#64748b' }}>
                {f.label}
              </button>
            ))}
          </div>

          {/* Lista eventi scrollabile */}
          <div style={{ flex: 1, overflowY: 'auto', minHeight: 0 }}>
            {logLoading ? (
              <div style={{ textAlign: 'center', padding: 20, color: '#94a3b8', fontSize: 13 }}>Caricamento…</div>
            ) : logEventi.filter(e => logFiltro === 'tutti' || e.tipo === logFiltro).length === 0 ? (
              <div style={{ textAlign: 'center', padding: 20, color: '#94a3b8', fontSize: 13 }}>
                {logEventi.length === 0 ? 'Nessun evento oggi — clicca ↻ per caricare' : 'Nessun evento di questo tipo'}
              </div>
            ) : (
              <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                {logEventi
                  .filter(e => logFiltro === 'tutti' || e.tipo === logFiltro)
                  .map((e, i) => {
                    const ora = new Date(e.ts).toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
                    const fmtDur = (sec) => {
                      if (!sec) return null
                      const h = Math.floor(sec / 3600)
                      const m = Math.floor((sec % 3600) / 60)
                      const s = sec % 60
                      return h > 0 ? `${h}h ${m}m` : m > 0 ? `${m}m` : `${s}s`
                    }
                    const ICONE = { programma: '⚙', utensile: '🔧', fermo: '⏸', pallet: '📦', allarme: '🚨' }
                    const COLORI = { programma: '#1D5FAD', utensile: '#d97706', fermo: '#f59e0b', pallet: '#7c3aed', allarme: '#dc2626' }
                    const col = COLORI[e.tipo] || '#94a3b8'
                    return (
                      <div key={i} style={{
                        display: 'flex', alignItems: 'flex-start', gap: 10, padding: '8px 10px',
                        borderRadius: 7, borderLeft: `3px solid ${col}`,
                        background: i % 2 === 0 ? '#f8fafc' : '#fff',
                        opacity: e.ignorato ? 0.45 : 1,
                      }}>
                        <span style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'monospace',
                          flexShrink: 0, minWidth: 38, marginTop: 1 }}>{ora}</span>
                        <span style={{ fontSize: 18, flexShrink: 0, lineHeight: 1.2 }}>{ICONE[e.tipo] || '•'}</span>
                        <div style={{ flex: 1, minWidth: 0 }}>
                          <div style={{ fontSize: 13, fontWeight: 700, color: '#1e293b',
                            fontFamily: ['programma','utensile'].includes(e.tipo) ? 'monospace' : 'inherit',
                            overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                            {e.testo}
                          </div>
                          {e.sub && <div style={{ fontSize: 11, color: col, marginTop: 2 }}>{e.sub}</div>}
                          {e.extra && <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 1 }}>{e.extra}</div>}
                        </div>
                        {e.durata_sec > 0 && (
                          <div style={{ fontSize: 12, color: '#64748b', fontFamily: 'monospace',
                            flexShrink: 0, alignSelf: 'center' }}>{fmtDur(e.durata_sec)}</div>
                        )}
                      </div>
                    )
                  })}
              </div>
            )}
          </div>
        </div>

      </div>
      </div>
    </div>
  );
}