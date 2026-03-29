import { useState, useEffect, useCallback, useRef } from "react";
import { createPortal } from "react-dom";
import { useNavigate } from 'react-router-dom';

// ── Colori stati pallet ──────────────────────────────────────────
const STATI = {
  "IN LAVORAZIONE": { bg: "#0d2d5e", fg: "#fff",     border: "#1a4080" },
  "GREZZO":         { bg: "#fefce8", fg: "#854d0e",  border: "#eab308" },
  "FINITO":         { bg: "#dcfce7", fg: "#14532d",  border: "#22c55e" },
  "VUOTO":          { bg: "#f1f5f9", fg: "#94a3b8",  border: "#e2e8f0" },
  "GUASTO":         { bg: "#fef2f2", fg: "#991b1b",  border: "#f87171" },
};
const STATI_ORDER = ["VUOTO", "GREZZO", "FINITO", "GUASTO"];

// Estrae commessa/posizione/fase dal path NC
function parseProgram(path) {
  if (!path) return null;
  // Caso 1: path raw completo /_N_WKS_DIR/_N_4349_0221_WPD/_N_4349_0221_03_010_MPF
  const m = path.match(/_N_(\d+)_(\d+)_WPD\/_N_\d+_\d+_(.+?)_MPF/);
  if (m) return { commessa: m[1], posizione: m[2], fase: m[3], full: path };
  // Caso 2: nome file già estratto es. "4348_0301_02_24.MPF"
  const m2 = path.match(/^(\d+)_(\d+)_(.+?)\.MPF$/i);
  if (m2) return { commessa: m2[1], posizione: m2[2], fase: m2[3], full: path };
  // Caso 3: fallback generico — mostra tutto
  const nome = path.replace(/\/_N_/g, '').replace(/_MPF$/,'').replace(/_/g,' ');
  return { fase: nome, full: path };
}

const REFRESH_MS = 5000;

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
  // ── Coda esecuzione ────────────────────────────────────────────
  const [codaOrdine, setCodaOrdine] = useState([]);   // [3,4,5]
  const [codaSaving, setCodaSaving] = useState(false);
  const dragCodaIdx = useRef(null);
  // Programmi in macchina per pallet
  const [pgmInMacchina, setPgmInMacchina] = useState({}); // {palletNum: {progetto, programmi}}
  const [pgmSelezionati, setPgmSelezionati] = useState({}); // {palletNum: Set(ids)}
  const [pgmSaving, setPgmSaving] = useState(false);

  const fetchLiveContext = async () => {
    try {
      const r = await fetch('/api/macchina-live/live-context')
      if (r.ok) setLiveCtx(await r.json())
    } catch {}
  }

  const navigate = typeof useNavigate === 'function' ? useNavigate() : null;

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
      alert(err.detail || 'Errore assegnazione pallet')
      fetchAll(); return
    }
    fetchAll()
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
          macchinaData?.stato_programma === 3
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

  // Polling aggiornamento automatico stati da log OpcUa (ogni 5s)
  useEffect(() => {
    const aggiornaStati = async () => {
      try {
        const r = await fetch('/api/macchina-live/aggiorna-stati-da-log', { method: 'POST' })
        if (!r.ok) return
        const d = await r.json()
        // Se ci sono stati aggiornamenti → ricarica tutto
        if (d.pallet > 0 || d.in_macchina > 0 || d.completato > 0) {
          await fetchAll()
          await caricaPgmInMacchina()
        }
      } catch {}
    }
    aggiornaStati()
    const t2 = setInterval(aggiornaStati, 5000)
    return () => clearInterval(t2)
  }, [fetchAll])

  useEffect(() => {
    fetchAll()
    fetch('/api/pallet/ordine-esecuzione')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setCodaOrdine(d.ordine || []) })
      .catch(() => {})
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

  const inLavorazione = macchina?.stato_programma === 3;
  const prog          = parseProgram(macchina?.programma_attivo);
  const utensile      = macchina?.utensile_attivo || null;
  const tNum          = macchina?.numero_utensile   || null;
  const alarm         = macchina?.allarme?.replace(/^\|[^|]*\|[^|]*\| ?/, "") || null;

  // Carica lista progetti per il modal
  const [listaProgetti, setListaProgetti] = useState([]);
  useEffect(()=>{
    fetch('/api/progetti/').then(r=>r.ok?r.json():[]).then(d=>{
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

  return (
    <div style={{
      display: "flex",
      gap: 20,
      padding: 20,
      height: "100%",
      boxSizing: "border-box",
      background: "var(--bg-base, #eef2f7)",
    }}>

      {/* ── Banner live context (programma in esecuzione) ───────── */}
      {liveCtx?.match && (
        <div style={{ marginBottom: 16, padding: '12px 16px', borderRadius: 10,
          background: liveCtx.match.allerta_utensile === 'fin_vita' ? '#FEF9C3'
            : liveCtx.match.allerta_utensile === 'disabilitato' ? '#FEE2E2'
            : '#EFF6FF',
          border: `1px solid ${liveCtx.match.allerta_utensile ? '#D97706' : '#1D5FAD'}44`,
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
                background: liveCtx.match.progetto_colore,
                transition: 'width 0.5s' }}/>
            </div>
            <span style={{ fontSize: 12, fontWeight: 700, color: '#5A5750', minWidth: 80 }}>
              {liveCtx.match.programmi_completati}/{liveCtx.match.programmi_totali} pgm · {liveCtx.match.pct_avanzamento}%
            </span>
            {liveCtx.match.prossimi_programmi?.length > 0 && (
              <span style={{ fontSize: 11, color: '#9A978E' }}>
                Prossimo: {liveCtx.match.prossimi_programmi[0].filename}
              </span>
            )}
          </div>
        </div>
      )}
      {liveCtx && !liveCtx.match && liveCtx.programma_attivo && (
        <div style={{ marginBottom: 12, padding: '8px 14px', borderRadius: 8,
          background: '#F5F4F0', border: '1px solid #D8D5CC',
          fontSize: 12, color: '#9A978E', display: 'flex', gap: 8 }}>
          <span>⚙</span>
          <span>In esecuzione: <code style={{ fontFamily: 'monospace' }}>{liveCtx.programma_attivo}</code> — nessun progetto associato</span>
        </div>
      )}

      <div style={{ flex: '0 0 calc(50% - 8px)', minWidth: 0, overflowY: 'auto', display: 'flex', flexDirection: 'column', gap: 12 }}>
      {/* ── Griglia 2×3 pallet ─────────────────────────────────── */}
      <div style={{ flexShrink: 0 }}>
        <div style={{
          display: "flex",
          justifyContent: "space-between",
          alignItems: "center",
          marginBottom: 10,
        }}>
          <span style={{ fontSize: 12, fontWeight: 700, color: "#0d2d5e", letterSpacing: 1 }}>
            PALLET
          </span>
          {lastUpdate && (
            <span style={{ fontSize: 10, color: "#94a3b8" }}>{lastUpdate}</span>
          )}
        </div>

        <div style={{
          display: "grid",
          gridTemplateColumns: "repeat(2, 1fr)",
          gridTemplateRows: "auto",
          gap: 10,
          alignItems: "start",
        }}>
          {pallets.map(p => {
            const s        = STATI[p.stato] || STATI["VUOTO"];
            const isActive = macchina?.pallet_attivo === p.id;
            const isLav    = p.stato === "IN LAVORAZIONE";
            const hasProj  = !!progettiPallet[p.id];
            const isEmpty  = !hasProj && p.stato === "VUOTO";
            const proj     = progettiPallet[p.id];
            const isAvviato  = p.stato === "IN LAVORAZIONE";
            const isCompleto = proj && proj.pct === 100;
            const cardBg     = isCompleto ? "#dcfce7" : isAvviato ? "#dbeafe" : isEmpty ? "#F8F7F5" : s.bg;
            const cardBorder = isCompleto ? "#16a34a" : isAvviato ? "#1D5FAD" : isActive ? "#f59e0b" : isEmpty ? "#E8E6E0" : s.border;
            const cardFg     = isCompleto ? "#14532d" : isAvviato ? "#0d2d5e" : isEmpty ? "#B0ADA4" : s.fg;

            return (
              <div
                key={p.id}
                title={isLav ? "Gestito automaticamente dalla macchina" : "Click per cambiare stato"}
                style={{
                  background:   cardBg,
                  border:       `2px solid ${cardBorder}`,
                  borderRadius: 10,
                  padding:      isEmpty ? "10px 14px" : "14px 16px",
                  cursor:       isLav ? "default" : "pointer",
                  position:     "relative",
                  height:       isEmpty ? 90 : 200,
                  boxShadow:    isActive
                    ? "0 0 0 3px rgba(245,158,11,0.25), 0 2px 6px rgba(0,0,0,0.12)"
                    : isEmpty ? "none" : "0 1px 3px rgba(0,0,0,0.07)",
                  display:        "flex",
                  flexDirection:  "column",
                  justifyContent: "space-between",
                  transition: "all 0.2s",
                  userSelect: "none",
                  opacity: isEmpty ? 0.6 : 1,
                }}
                onClick={(e) => {
                  if (isLav) return;
                  setPalletMenu({ id: p.id, x: e.clientX, y: e.clientY });
                }}
              >
                {/* Numero + stato */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <span style={{ fontSize: isEmpty ? 24 : 42, fontWeight: 900, color: cardFg, lineHeight: 1 }}>
                    P{p.id}
                  </span>
                  {isActive && (
                    <span style={{
                      width: 9, height: 9, borderRadius: "50%",
                      background: "#f59e0b", display: "inline-block",
                      animation: "blink 1.4s infinite",
                    }} />
                  )}
                </div>

                {/* Stato label */}
                {isEmpty ? (
                  <div style={{fontSize:11, color:'#B0ADA4', fontWeight:700, letterSpacing:1}}>VUOTO</div>
                ) : (
                  <div style={{flex:1,minHeight:0,display:'flex',flexDirection:'column',justifyContent:'flex-end',gap:2}}>
                    <div style={{fontSize:11,fontWeight:800,color:cardFg,letterSpacing:1,textTransform:'uppercase'}}>
                      {p.stato}
                    </div>
                    {progettiPallet[p.id] ? (
                      <div style={{marginTop:2}}>
                        <div style={{display:'flex',alignItems:'center',gap:4,marginBottom:3}}>
                          <div style={{width:7,height:7,borderRadius:'50%',background:progettiPallet[p.id].colore,flexShrink:0}}/>
                          <span style={{fontSize:13,fontWeight:800,color:cardFg,overflow:'hidden',textOverflow:'ellipsis',whiteSpace:'nowrap'}}>
                            {progettiPallet[p.id].nome}
                          </span>
                        </div>
                        <div style={{height:6,background:'rgba(0,0,0,0.12)',borderRadius:3,overflow:'hidden'}}>
                          <div style={{height:'100%',background:progettiPallet[p.id].colore,width:`${progettiPallet[p.id].pct}%`,borderRadius:2}}/>
                        </div>
                        <div style={{display:'flex',justifyContent:'space-between',marginTop:2}}>
                          <span style={{fontSize:10,color:cardFg,opacity:0.8}}>{progettiPallet[p.id].completati}/{progettiPallet[p.id].totale} pgm</span>
                          <span style={{fontSize:12,fontWeight:800,color:cardFg}}>{progettiPallet[p.id].pct}%</span>
                        </div>
                        {(progettiPallet[p.id].da_fare > 0 || progettiPallet[p.id].in_macchina > 0) && !isAvviato && (
                          <button onClick={e=>{e.stopPropagation();avviaProgetto(p.id)}}
                            style={{marginTop:4,width:'100%',background:'#1D5FAD',border:'none',borderRadius:4,
                              color:'#fff',fontWeight:700,fontSize:10,padding:'4px 0',cursor:'pointer'}}>
                            ▶ Avvia ({progettiPallet[p.id].da_fare + progettiPallet[p.id].in_macchina})
                          </button>
                        )}
                        {progettiPallet[p.id].pct===100 && p.stato!=='FINITO' && (
                          <button onClick={e=>{e.stopPropagation();setPalletStato(p.id,'FINITO')}}
                            style={{marginTop:3,width:'100%',background:'#166534',border:'none',borderRadius:4,
                              color:'#fff',fontWeight:700,fontSize:9,padding:'3px 0',cursor:'pointer'}}>
                            ✓ Segna Finito
                          </button>
                        )}
                      </div>
                    ) : (
                      <button onClick={e=>{e.stopPropagation();setModalAssegna({palletId:p.id})}}
                        style={{marginTop:4,width:'100%',background:'transparent',
                          border:'1px dashed rgba(0,0,0,0.2)',borderRadius:4,
                          color:s.fg,opacity:0.5,fontWeight:600,fontSize:8,padding:'3px 0',cursor:'pointer'}}>
                        + Assegna progetto
                      </button>
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>

        <ModalAssegna/>
      <style>{`
          @keyframes blink {
            0%, 100% { opacity: 1; }
            50%       { opacity: 0.3; }
          }
        `}</style>
      </div>

        {/* Stato macchina + programma + utensile — tutto in un blocco compatto */}
        <div style={{
          background:   inLavorazione ? "#0d2d5e" : "#ffffff",
          border:       `1px solid ${inLavorazione ? "#1a4080" : "#e2e8f0"}`,
          borderRadius: 12,
          padding:      "14px 18px",
          display:      "flex",
          flexDirection: "column",
          gap:          10,
        }}>
          {/* Riga stato */}
          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
            <div style={{
              width: 12, height: 12, borderRadius: "50%", flexShrink: 0,
              background:   inLavorazione ? "#22c55e" : "#94a3b8",
              boxShadow:    inLavorazione ? "0 0 8px #22c55e" : "none",
            }} />
            <span style={{ fontSize: 14, fontWeight: 800,
              color: inLavorazione ? "#ffffff" : "#374151" }}>
              {inLavorazione ? "IN LAVORAZIONE" : "FERMA"}
            </span>
            {macchina?.pallet_attivo > 0 && (
              <span style={{ fontSize: 11, color: inLavorazione ? "#93c5fd" : "#94a3b8" }}>
                · Pallet {macchina.pallet_attivo}
              </span>
            )}
          </div>

          {/* Programma + utensile sulla stessa riga */}
          <div style={{ display: "grid", gridTemplateColumns: "1fr 1fr", gap: 12 }}>
            <div>
              <div style={{ fontSize: 10, letterSpacing: 1, marginBottom: 4,
                color: inLavorazione ? "#93c5fd" : "#94a3b8" }}>PROGRAMMA</div>
              {prog ? (
                <div style={{ display: "flex", flexDirection: "column", gap: 2 }}>
                  {(prog.commessa || prog.posizione) && (
                    <div style={{ fontSize: 18, fontWeight: 800,
                      color: inLavorazione ? "#ffffff" : "#0d2d5e" }}>
                      {prog.commessa}{prog.posizione ? `_${prog.posizione}` : ""}
                    </div>
                  )}
                  {prog.fase && (
                    <div style={{ fontSize: 11, color: inLavorazione ? "#93c5fd" : "#64748b" }}>
                      {prog.fase}
                    </div>
                  )}
                </div>
              ) : (
                <span style={{ fontSize: 13, color: inLavorazione ? "#4e7aad" : "#94a3b8" }}>—</span>
              )}
            </div>
            <div>
              <div style={{ fontSize: 10, letterSpacing: 1, marginBottom: 4,
                color: inLavorazione ? "#93c5fd" : "#94a3b8" }}>UTENSILE ATTIVO</div>
              {utensile ? (
                <div>
                  <div style={{ fontSize: 16, fontWeight: 800,
                    color: inLavorazione ? "#fbbf24" : "#0d2d5e",
                    fontFamily: 'var(--font-mono)', letterSpacing: '-0.02em' }}>{utensile}</div>
                  {tNum > 0 && (
                    <div style={{ fontSize: 11, fontWeight: 600,
                      color: inLavorazione ? "#93c5fd" : "#64748b", marginTop: 2 }}>
                      Posizione T{tNum}
                    </div>
                  )}
                </div>
              ) : (
                <span style={{ fontSize: 13, color: inLavorazione ? "#4e7aad" : "#94a3b8" }}>—</span>
              )}
            </div>
          </div>
        </div>

        {/* Progetti attivi sui pallet — riepilogo */}
        {Object.keys(progettiPallet).length > 0 && (
          <div style={{ background: "#ffffff", border: "1px solid #e2e8f0",
            borderRadius: 12, padding: "14px 18px" }}>
            <div style={{ fontSize: 10, color: "#94a3b8", letterSpacing: 1, marginBottom: 10 }}>
              PROGETTI IN CORSO
            </div>
            <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
              {Object.entries(progettiPallet).map(([palletNum, proj]) => (
                <div key={palletNum} style={{ display: "flex", alignItems: "center", gap: 10 }}>
                  <span style={{ fontSize: 11, fontWeight: 700, color: "#64748b", minWidth: 24 }}>
                    P{palletNum}
                  </span>
                  <div style={{ width: 8, height: 8, borderRadius: "50%",
                    background: proj.colore, flexShrink: 0 }}/>
                  <span style={{ fontSize: 12, fontWeight: 700, color: "#0d2d5e", flex: 1,
                    overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap" }}>
                    {proj.nome}
                  </span>
                  <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                    <div style={{ width: 60, height: 5, background: "#e2e8f0",
                      borderRadius: 3, overflow: "hidden" }}>
                      <div style={{ height: "100%", background: proj.colore,
                        width: `${proj.pct}%`, borderRadius: 3 }}/>
                    </div>
                    <span style={{ fontSize: 11, fontWeight: 700, color: "#374151", minWidth: 32 }}>
                      {proj.pct}%
                    </span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        )}

        {/* Allarmi */}
        {alarm && (
          <div style={{
            background:   "#fef2f2",
            border:       "1px solid #fca5a5",
            borderRadius: 12,
            padding:      "12px 16px",
          }}>
            <div style={{ fontSize: 10, color: "#991b1b", letterSpacing: 1, marginBottom: 4, fontWeight: 700 }}>
              ⚠ ALLARME MACCHINA
            </div>
            <div style={{ fontSize: 12, color: "#991b1b", fontWeight: 500 }}>
              {alarm.startsWith('MESS.') || alarm.startsWith('MESS,')
                ? 'Macchina ferma — nessun programma in esecuzione'
                : alarm}
            </div>
          </div>
        )}

        {/* Errore connessione */}
        {error && (
          <div style={{
            background:   "#fef3c7",
            border:       "1px solid #fcd34d",
            borderRadius: 8,
            padding:      "8px 12px",
            fontSize:     11,
            color:        "#92400e",
          }}>
            ⚠️ {error}
          </div>
        )}

      {/* Menu selezione stato pallet manuale */}
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
                { s:'GREZZO',  dot:'#eab308', bg:'#fefce8', fg:'#854d0e' },
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
                        window.location.href='/progetti'
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

                {/* Voci stato */}
                {STATI_MENU.map(({s, dot, bg, fg}) => {
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
                      <span>{s}</span>
                      {sel && <span style={{marginLeft:'auto',fontSize:11,color:fg}}>✓</span>}
                    </div>
                  )
                })}
              </>)
            })()}
          </div>
        </div>
      , document.body)}
      </div>

      <div style={{ flex: '0 0 calc(50% - 8px)', display: 'flex', flexDirection: 'column', gap: 10, minWidth: 0, overflowY: 'auto' }}>


        {/* ── Coda Esecuzione ───────────────────────────────────── */}
        {assegnatiCoda.length > 0 && (
          <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '12px 16px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 10 }}>
              <span style={{ fontSize: 13, fontWeight: 800, color: '#0d2d5e' }}>📋 CODA ESECUZIONE</span>
              {codaSaving && <span style={{ fontSize: 11, color: '#94a3b8' }}>salvataggio…</span>}
              <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 'auto' }}>trascina per riordinare</span>
            </div>
            {/* Pallet in coda — drag&drop */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: fuoriCodaList.length ? 8 : 0 }}>
              {inCodaList.map((p, idx) => (
                <div key={p.numero}
                  draggable
                  onDragStart={e => codaDragStart(e, idx)}
                  onDragOver={e => codaDragOver(e, idx)}
                  onDrop={codaDrop}
                  style={{ background: '#eef4fb', border: '2px solid #1D5FAD', borderRadius: 10,
                    padding: '8px 12px', cursor: 'grab', position: 'relative', userSelect: 'none',
                    display: 'flex', alignItems: 'center', gap: 8 }}>
                  <span style={{ position: 'absolute', top: -8, left: 8, background: '#0d2d5e',
                    color: '#fff', fontSize: 9, fontWeight: 800, borderRadius: 8, padding: '1px 6px' }}>
                    {idx + 1}°
                  </span>
                  <span style={{ fontSize: 11, color: '#0d2d5e', fontWeight: 700 }}>P{p.numero}</span>
                  <span style={{ fontSize: 12, fontWeight: 800, color: '#0d2d5e', fontFamily: 'monospace' }}>
                    {p.progetto_nome}
                  </span>
                  <button onClick={() => salvaCoda(codaOrdine.filter(n => n !== p.numero))}
                    style={{ background: 'none', border: 'none', cursor: 'pointer',
                      color: '#94a3b8', fontSize: 13, lineHeight: 1, padding: '0 2px' }}>✕</button>
                </div>
              ))}
              {inCodaList.length === 0 && (
                <span style={{ fontSize: 12, color: '#94a3b8' }}>Nessun progetto in coda — aggiungi ↓</span>
              )}
            </div>
            {/* Pallet fuori coda */}
            {fuoriCodaList.length > 0 && (
              <div style={{ display: 'flex', gap: 6, alignItems: 'center', flexWrap: 'wrap' }}>
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

        {/* ── Programmi in macchina ─────────────────────────────── */}
        {(() => {
          // Pallet con almeno un programma in_macchina, nell'ordine della coda
          const ordineEffettivo = codaOrdine.length > 0
            ? codaOrdine
            : pallets.filter(p => progettiPallet[p.id]).map(p => p.id)
          const blocchi = ordineEffettivo
            .map(n => pgmInMacchina[n])
            .filter(d => d?.programmi?.length > 0)
          if (!blocchi.length) return null
          const totSel = Object.values(pgmSelezionati).reduce((acc, s) => acc + (s?.size || 0), 0)
          return (
            <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 12, padding: '12px 16px' }}>
              {/* Header */}
              <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
                <span style={{ fontSize: 13, fontWeight: 800, color: '#0d2d5e' }}>⚙ PROGRAMMI IN MACCHINA</span>
                <span style={{ fontSize: 11, color: '#94a3b8' }}>
                  {blocchi.reduce((a, b) => a + b.programmi.length, 0)} programmi attivi
                </span>
                {totSel > 0 && (
                  <button onClick={() => {
                    // Completa per tutti i pallet con selezioni
                    Object.entries(pgmSelezionati).forEach(([n, s]) => {
                      if (s?.size > 0) completaPgm(parseInt(n))
                    })
                  }}
                    disabled={pgmSaving}
                    style={{ marginLeft: 'auto', background: '#166534', border: 'none', borderRadius: 7,
                      color: '#fff', fontWeight: 700, fontSize: 12, padding: '5px 14px', cursor: 'pointer' }}>
                    ✓ Segna {totSel} completat{totSel === 1 ? 'o' : 'i'}
                  </button>
                )}
              </div>

              {/* Blocchi per progetto */}
              {blocchi.map((d, bi) => {
                const col = PAL_COLORS[(d.pallet - 1) % PAL_COLORS.length]
                const sel = pgmSelezionati[d.pallet] || new Set()
                const tuttiSel = d.programmi.every(p => sel.has(p.id))
                return (
                  <div key={d.pallet} style={{ marginBottom: bi < blocchi.length - 1 ? 10 : 0 }}>
                    {/* Header progetto */}
                    <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6,
                      padding: '4px 10px', background: col + '12', borderRadius: 7,
                      borderLeft: `3px solid ${col}` }}>
                      <input type='checkbox' checked={tuttiSel}
                        onChange={() => {
                          const newSel = tuttiSel ? new Set() : new Set(d.programmi.map(p => p.id))
                          setPgmSelezionati(prev => ({ ...prev, [d.pallet]: newSel }))
                        }}
                        style={{ accentColor: col, cursor: 'pointer', width: 14, height: 14 }} />
                      <span style={{ width: 8, height: 8, borderRadius: '50%', background: col, flexShrink: 0 }} />
                      <span style={{ fontSize: 12, fontWeight: 800, color: col }}>P{d.pallet} — {d.progetto.nome}</span>
                      <span style={{ fontSize: 11, color: '#94a3b8', marginLeft: 4 }}>
                        {d.programmi.length} in macchina
                      </span>
                    </div>

                    {/* Lista programmi */}
                    <div style={{ display: 'flex', flexDirection: 'column', gap: 2, paddingLeft: 8 }}>
                      {d.programmi.map(pgm => {
                        const checked = sel.has(pgm.id)
                        return (
                          <div key={pgm.id}
                            onClick={() => togglePgm(d.pallet, pgm.id)}
                            style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '5px 8px',
                              borderRadius: 7, cursor: 'pointer', userSelect: 'none',
                              background: checked ? '#dcfce7' : '#f8fafc',
                              border: `1px solid ${checked ? '#166534' : '#e2e8f0'}`,
                              transition: 'all 0.12s' }}>
                            <input type='checkbox' checked={checked} onChange={() => togglePgm(d.pallet, pgm.id)}
                              onClick={e => e.stopPropagation()}
                              style={{ accentColor: '#166534', cursor: 'pointer', width: 14, height: 14, flexShrink: 0 }} />
                            {/* Numero programma */}
                            <span style={{ fontSize: 12, fontWeight: 800, color: col,
                              fontFamily: 'monospace', minWidth: 32 }}>{pgm.numPgm}</span>
                            {/* Utensile */}
                            <span style={{ fontSize: 11, fontWeight: 600, color: '#1e293b',
                              fontFamily: 'monospace', flex: 1, overflow: 'hidden',
                              textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {pgm.utensile || '—'}
                            </span>
                            {/* Nome file */}
                            <span style={{ fontSize: 10, color: '#94a3b8', fontFamily: 'monospace',
                              flexShrink: 0, maxWidth: 160, overflow: 'hidden',
                              textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                              {pgm.filename}
                            </span>
                            {/* Tempo */}
                            {pgm.tempoStimato && (
                              <span style={{ fontSize: 10, fontWeight: 700, color: '#475569',
                                flexShrink: 0, whiteSpace: 'nowrap' }}>⏱ {pgm.tempoStimato}m</span>
                            )}
                            {/* Orario inizio */}
                            {pgm.tempoInizio && (
                              <span style={{ fontSize: 10, color: '#0d2d5e', fontFamily: 'monospace',
                                flexShrink: 0, whiteSpace: 'nowrap' }}>▶ {pgm.tempoInizio}</span>
                            )}
                          </div>
                        )
                      })}
                    </div>
                  </div>
                )
              })}
            </div>
          )
        })()}

      </div>
    </div>
  );
}