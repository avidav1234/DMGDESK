// pages/Macchina.jsx — V16: solo Sync TOA/TMA + Confronto MPF
import { useState, useEffect, useRef, useCallback } from 'react'
import { InfoTooltip } from '../components/UI'
import { api } from '../api/client'
import { Loader, SectionHeader } from '../components/UI'
import { PopupSostituzione } from '../components/MLDataPopup'

// ── Coda Esecuzione con drag&drop ────────────────────────────────────────────
function CodaEsecuzione({ setupData, onOrdineChanged }) {
  const [pallet, setPallet]     = useState([])
  const [ordine, setOrdine]     = useState([])   // [3,4,5] — numeri pallet in coda
  const [saving, setSaving]     = useState(false)
  const dragIdx = useRef(null)

  useEffect(() => {
    fetch('/api/pallet/ordine-esecuzione')
      .then(r => r.ok ? r.json() : null)
      .then(d => {
        if (!d) return
        setPallet(d.pallet || [])
        setOrdine(d.ordine || [])
      })
  }, [])

  // Pallet assegnati non ancora in ordine + in ordine
  const assegnati = pallet.filter(p => p.progetto_id)
  const inCoda    = ordine.map(n => assegnati.find(p => p.numero === n)).filter(Boolean)
  const fuoriCoda = assegnati.filter(p => !ordine.includes(p.numero))

  async function salvaOrdine(nuovoOrdine) {
    setOrdine(nuovoOrdine)
    setSaving(true)
    try {
      await fetch('/api/pallet/ordine-esecuzione', {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ ordine: nuovoOrdine })
      })
      // Ricalcola previsione vita con nuovo ordine
      if (onOrdineChanged) onOrdineChanged()
    } finally { setSaving(false) }
  }

  function aggiungiACoda(numPallet) {
    if (!ordine.includes(numPallet))
      salvaOrdine([...ordine, numPallet])
  }

  function rimuoviDaCoda(numPallet) {
    salvaOrdine(ordine.filter(n => n !== numPallet))
  }

  // Drag & drop
  function onDragStart(e, idx) {
    dragIdx.current = idx
    e.dataTransfer.effectAllowed = 'move'
  }
  function onDragOver(e, idx) {
    e.preventDefault()
    if (dragIdx.current === null || dragIdx.current === idx) return
    const newOrdine = [...inCoda]
    const [moved] = newOrdine.splice(dragIdx.current, 1)
    newOrdine.splice(idx, 0, moved)
    dragIdx.current = idx
    setOrdine(newOrdine.map(p => p.numero))
  }
  function onDrop() {
    salvaOrdine(ordine)
    dragIdx.current = null
  }

  const fmtTempo = (min) => {
    if (!min) return null
    const h = Math.floor(min / 60), m = min % 60
    return h > 0 ? `${h}h${m > 0 ? ` ${m}m` : ''}` : `${m}m`
  }

  const prev = setupData?.previsione_vita || []

  // Colori pallet
  const PAL_COLOR = ['#0d2d5e','#1D5FAD','#2563eb','#7c3aed','#0891b2','#059669']

  if (!assegnati.length) return null

  return (
    <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)', borderRadius: 10, padding: '14px 16px', marginBottom: 12 }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12 }}>
        <span style={{ fontSize: 14 }}>📋</span>
        <span style={{ fontSize: 13, fontWeight: 800, color: 'var(--text-primary)', letterSpacing: '0.04em' }}>CODA ESECUZIONE</span>
        {saving && <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>salvataggio…</span>}
        {prev.length > 0 && (
          <span style={{ marginLeft: 'auto', fontSize: 11, fontWeight: 700, color: '#e65100', background: '#fff3e0', padding: '2px 10px', borderRadius: 20, border: '1px solid #ffb74d' }}>
            🔮 {prev.length} utensil{prev.length === 1 ? 'e' : 'i'} a rischio
          </span>
        )}
      </div>

      {/* Zona coda ordinata */}
      <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', marginBottom: fuoriCoda.length ? 10 : 0 }}>
        {inCoda.map((p, idx) => {
          const col = PAL_COLOR[(p.numero - 1) % PAL_COLOR.length]
          const alert = prev.find(a => a.programma_critico?.progetto_id === p.progetto_id || a.programma_critico?.progetto === p.progetto_nome)
          return (
            <div key={p.numero}
              draggable
              onDragStart={e => onDragStart(e, idx)}
              onDragOver={e => onDragOver(e, idx)}
              onDrop={onDrop}
              style={{ background: 'var(--bg-card)', border: `2px solid ${col}`, borderRadius: 10,
                padding: '10px 14px', minWidth: 130, cursor: 'grab', position: 'relative',
                boxShadow: '0 2px 6px rgba(0,0,0,0.08)', userSelect: 'none' }}>
              {/* Numero ordine */}
              <div style={{ position: 'absolute', top: -10, left: 10, background: col, color: '#fff',
                fontSize: 10, fontWeight: 800, borderRadius: 10, padding: '1px 7px' }}>{idx + 1}°</div>
              {/* Rimuovi */}
              <button onClick={() => rimuoviDaCoda(p.numero)}
                style={{ position: 'absolute', top: 4, right: 6, background: 'none', border: 'none',
                  cursor: 'pointer', color: 'var(--text-dim)', fontSize: 13, lineHeight: 1 }}>✕</button>
              <div style={{ fontSize: 10, color: col, fontWeight: 700, marginBottom: 2 }}>P{p.numero}</div>
              <div style={{ fontSize: 12, fontWeight: 800, color: 'var(--text-primary)', fontFamily: 'var(--font-mono)' }}>
                {p.progetto_nome || '—'}
              </div>
              {alert && (
                <div style={{ fontSize: 10, color: '#e65100', fontWeight: 700, marginTop: 4 }}>
                  🔮 {alert.alias} a rischio
                </div>
              )}
            </div>
          )
        })}
        {inCoda.length === 0 && (
          <div style={{ fontSize: 12, color: 'var(--text-dim)', padding: '8px 12px' }}>
            Nessun progetto in coda — aggiungi i pallet assegnati ↓
          </div>
        )}
      </div>

      {/* Pallet assegnati ma fuori coda */}
      {fuoriCoda.length > 0 && (
        <div style={{ borderTop: '1px solid var(--border)', paddingTop: 8 }}>
          <div style={{ fontSize: 10, color: 'var(--text-dim)', fontWeight: 700, letterSpacing: '0.06em', marginBottom: 6 }}>
            NON IN CODA — clicca per aggiungere
          </div>
          <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
            {fuoriCoda.map(p => {
              const col = PAL_COLOR[(p.numero - 1) % PAL_COLOR.length]
              return (
                <button key={p.numero} onClick={() => aggiungiACoda(p.numero)}
                  style={{ background: 'var(--bg-hover)', border: `1.5px dashed ${col}44`,
                    borderRadius: 8, padding: '6px 12px', cursor: 'pointer', fontSize: 12,
                    color: 'var(--text-secondary)', fontWeight: 600 }}>
                  + P{p.numero} {p.progetto_nome}
                </button>
              )
            })}
          </div>
        </div>
      )}

      {/* Previsione vita cross-progetto */}
      {prev.length > 0 && (
        <div style={{ borderTop: '1px solid #ffb74d', marginTop: 12, paddingTop: 10 }}>
          <div style={{ fontSize: 11, fontWeight: 800, color: '#e65100', marginBottom: 8 }}>🔮 PREVISIONE FINE VITA — ordine coda attuale</div>
          {prev.map((a, i) => {
            const cr = a.programma_critico
            const pct = Math.round((a.vita_rimanente / a.consumo_totale) * 100)
            return (
              <div key={i} style={{ background: '#fff8f0', border: '1px solid #ffcc80', borderRadius: 8, padding: '8px 12px', marginBottom: 6 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 4 }}>
                  <span style={{ fontFamily: 'monospace', fontWeight: 800, color: '#bf360c', fontSize: 12 }}>{a.alias}</span>
                  <div style={{ flex: 1, height: 5, background: '#ffe0b2', borderRadius: 3, overflow: 'hidden' }}>
                    <div style={{ height: 5, width: `${Math.min(pct, 100)}%`, background: pct < 50 ? '#f44336' : '#ff9800', borderRadius: 3 }} />
                  </div>
                  <span style={{ fontSize: 11, color: '#e65100', fontWeight: 700, flexShrink: 0 }}>{a.vita_rimanente}min / {a.consumo_totale}min</span>
                </div>
                {cr && (
                  <div style={{ fontSize: 11, color: '#5d4037' }}>
                    <span style={{ fontWeight: 700, color: '#bf360c' }}>⚠ Finisce durante </span>
                    <span style={{ fontFamily: 'monospace', fontWeight: 700 }}>{cr.progetto}</span>
                    <span> pgm <span style={{ fontFamily: 'monospace' }}>{cr.numPgm}</span></span>
                    <span style={{ color: '#9a3412' }}> — {a.vita_rimanente}min disponibili / {a.consumo_totale}min richiesti</span>
                  </div>
                )}
              </div>
            )
          })}
        </div>
      )}
    </div>
  )
}

function LifeBar({ pct, pctStimato, stimaAffidabile }) {
  if (pct === null || pct === undefined)
    return <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>—</span>
  const c = Math.min(100, Math.max(0, pct))
  const cs = pctStimato != null ? Math.min(100, Math.max(0, pctStimato)) : null
  const color = c < 10 ? 'var(--red)' : c < 30 ? 'var(--amber)' : 'var(--green)'
  const colorS = cs != null ? (cs < 10 ? 'var(--red)' : cs < 30 ? 'var(--amber)' : '#0369a1') : null
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 2 }}>
      {/* Valore TOA reale */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
        <div style={{ width: 44, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
          <div style={{ width: `${c}%`, height: '100%', background: color, borderRadius: 2 }} />
        </div>
        <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color }}>{Math.round(c)}%</span>
      </div>
      {/* Stima live — mostrata solo se disponibile */}
      {cs != null && (
        <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
          <div style={{ width: 44, height: 3, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
            <div style={{ width: `${cs}%`, height: '100%', background: colorS,
              borderRadius: 2, opacity: stimaAffidabile ? 1 : 0.5 }} />
          </div>
          <span style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: colorS,
            opacity: stimaAffidabile ? 1 : 0.7 }}>
            ~{Math.round(cs)}%
          </span>
        </div>
      )}
    </div>
  )
}

const COL = {
  ok:       { bg: 'rgba(22,163,74,0.08)',  border: 'rgba(22,163,74,0.25)',  text: 'var(--green)'  },
  missing:  { bg: 'rgba(255,68,85,0.10)',  border: 'rgba(255,68,85,0.30)',  text: 'var(--red)'    },
  disabled: { bg: 'rgba(255,179,0,0.10)',  border: 'rgba(255,179,0,0.30)',  text: 'var(--amber)'  },
  worn:     { bg: 'rgba(109,40,217,0.10)', border: 'rgba(109,40,217,0.30)', text: '#6d28d9' },
}

function SetupPannel({ setupData, setupPopup, setSetupPopup, onChiudi }) {
  const chiudi = onChiudi || (()=>setSetupPopup&&setSetupPopup(false))
  if (!setupPopup || !setupData) return null
  const {non_utilizzati, da_montare, fin_vita, previsione_vita=[], stime_live={}} = setupData
  const [q, setQ] = useState('')
  const filter = items => q.trim()
    ? items.filter(i => i.alias?.toLowerCase().includes(q.toLowerCase()))
    : items

  const Section = ({title, items, color: c, bg, renderItem}) => {
    const filtered = filter(items)
    return filtered.length > 0 ? (
      <div style={{marginBottom:16}}>
        <div style={{fontSize:12,fontWeight:700,color:c,letterSpacing:'0.06em',marginBottom:8}}>
          {title}{q.trim() && filtered.length !== items.length ? ` (${filtered.length} di ${items.length})` : ''}
        </div>
        <div style={{border:'1px solid #D8D5CC',borderRadius:8,overflow:'hidden'}}>
          {filtered.map((item,i) => (
            <div key={item.alias} style={{display:'flex',alignItems:'center',gap:10,
              padding:'7px 12px',background:i%2===0?'#FFFFFF':bg,
              borderBottom:i<filtered.length-1?'1px solid #D8D5CC':'none'}}>
              {renderItem(item)}
            </div>
          ))}
        </div>
      </div>
    ) : null
  }

  return (
    <div style={{marginTop:12,border:'1px solid #D8D5CC',borderRadius:12,
      overflow:'hidden',background:'#FFFFFF',
      maxHeight:'70vh',display:'flex',flexDirection:'column'}}>
      <div style={{display:'flex',flexDirection:'column',height:'100%',overflow:'hidden'}}>
        <div style={{padding:'18px 24px',borderBottom:'1px solid #D8D5CC',
          display:'flex',alignItems:'center',gap:10,flexShrink:0}}>
          <span style={{fontSize:20}}>🔧</span>
          <div style={{flex:1}}>
            <div style={{fontSize:17,fontWeight:800,color:'#1A1814'}}>Analisi Setup Macchina</div>
            {setupData.sync_time && (
              <div style={{fontSize:11,color:'#9A978E',marginTop:2}}>
                Ultimo sync: {new Date(setupData.sync_time).toLocaleString('it-IT')}
              </div>
            )}
          </div>
          <input
            value={q} onChange={e=>setQ(e.target.value)}
            placeholder="Cerca alias…"
            style={{flex:1, maxWidth:280, padding:'7px 12px', borderRadius:6,
              background:'var(--bg-surface)', border:'1px solid var(--border)',
              color:'var(--text-primary)', fontSize:13, outline:'none',
              fontFamily:'var(--font-mono)'}}
          />
          <button onClick={chiudi}
            style={{background:'none',border:'1px solid #D8D5CC',borderRadius:8,
              color:'#5A5750',fontSize:13,padding:'5px 12px',cursor:'pointer',fontWeight:600}}>
            Chiudi
          </button>
        </div>
        <div style={{flex:1,overflowY:'auto',padding:'20px 24px',minHeight:0}}>
          <Section title={`✗ MANCANTI / DA MONTARE — ${da_montare.length}`}
            items={da_montare} c='#C0392B' bg='#FDECEA'
            renderItem={item=><>
              <div style={{flex:1}}>
                <span style={{fontSize:13,fontFamily:'monospace',fontWeight:700,color:'#1A1814'}}>{item.alias}</span>
                {(item.progetti||[]).slice(0,3).map((r,i)=>(
                  <div key={i} style={{fontSize:10,color:'#5A5750',marginTop:1}}>
                    <span style={{fontWeight:700,color:'#1D5FAD'}}>{r.progetto}</span>
                    <span style={{color:'#9A978E',fontFamily:'monospace'}}> · {r.file?.replace(/\.MPF$/i,'')}</span>
                  </div>
                ))}
              </div>
              <span style={{fontSize:11,fontWeight:700,padding:'2px 8px',borderRadius:12,flexShrink:0,
                color:item.provenienza==='mancante'?'#C0392B':item.provenienza==='scaffale'?'#1D5FAD':'#C2720A',
                background:item.provenienza==='mancante'?'#FDECEA':item.provenienza==='scaffale'?'#dbeafe':'#FFF0DC'}}>
                {item.provenienza==='scaffale'?'🏠 A scaffale':item.provenienza==='smontato'?'📦 Smontato':'✗ Non trovato'}
              </span>
            </>}
          />
          <Section title={`⚠ FINE VITA (<15%) — ${fin_vita.length}`}
            tooltip="Utensili con vita residua sotto il 15% nel TOA Sinumerik. Sostituire prima della prossima lavorazione per evitare interruzioni."
            items={fin_vita} c='#B45309' bg='#FEF3C7'
            renderItem={item=><>
              <div style={{flex:1}}>
                <span style={{fontSize:13,fontFamily:'monospace',fontWeight:700,color:'#1A1814'}}>{item.alias}</span>
                {(item.progetti||[]).slice(0,2).map((r,i)=>(
                  <div key={i} style={{fontSize:10,color:'#5A5750',marginTop:1}}>
                    <span style={{fontWeight:700,color:item.disabilitato?'#7C3AED':'#B45309'}}>{r.progetto}</span>
                    <span style={{color:'#9A978E',fontFamily:'monospace'}}> · {r.file?.replace(/\.MPF$/i,'')}</span>
                  </div>
                ))}
              </div>
              {item.position!=null&&<span style={{fontSize:11,color:'#5A5750',fontFamily:'monospace',flexShrink:0}}>P{item.position}</span>}
              {item.disabilitato
                ? <span style={{fontSize:11,fontWeight:800,color:'#7C3AED',background:'#EDE9FE',padding:'1px 8px',borderRadius:10,flexShrink:0}}>⊘ Disab.</span>
                : <span style={{fontSize:12,fontWeight:800,color:'#C0392B',flexShrink:0}}>{item.life_percent}%</span>}
            </>}
          />
          <Section title={`📦 NON UTILIZZATI — ${non_utilizzati.length}`}
            items={non_utilizzati} c='#5A5750' bg='#F0EEE8'
            renderItem={item=><>
              <span style={{flex:1,fontSize:13,fontFamily:'monospace',color:'#5A5750'}}>{item.alias}</span>
              {item.magazine!=null&&<span style={{fontSize:11,color:'#9A978E',fontFamily:'monospace'}}>M{item.magazine}{item.position!=null?` P${item.position}`:''}</span>}
              {item.life_percent!=null&&<span style={{fontSize:11,color:'#9A978E'}}>{item.life_percent}%</span>}
            </>}
          />
          {/* ── PREVISIONE FINE VITA ── */}
          {previsione_vita.length>0&&(
            <div style={{marginBottom:20}}>
              <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:10,padding:'8px 12px',
                background:'#fff3e0',border:'1px solid #ff9800',borderRadius:8}}>
                <span style={{fontSize:16}}>🔮</span>
                <span style={{fontSize:13,fontWeight:800,color:'#e65100',display:'flex',alignItems:'center',gap:4}}>
                  PREVISIONE FINE VITA — {previsione_vita.length} utensil{previsione_vita.length===1?'e':'i'} a rischio
                  <InfoTooltip text={"Utensili che potrebbero esaurire la vita durante i programmi pianificati nel MAIN.\n\nCalcolato confrontando:\n• Vita rimanente (minuti dal TOA Sinumerik)\n• Consumo totale stimato (somma tempoStimato dei programmi che usano questo utensile)\n\nSe vita_rimanente < consumo_totale → l'utensile non basterà a completare il pallet.\nSostituire prima di avviare o impostare un duplo."} position='bottom' />
                </span>
                <span style={{fontSize:11,color:'#bf360c',marginLeft:'auto'}}>
                  basato sui tempi stimati nei file MPF
                </span>
              </div>
              {previsione_vita.map((alert,i)=>{
                const cr = alert.programma_critico
                const pct = Math.round((alert.vita_rimanente / alert.consumo_totale)*100)
                return(
                  <div key={i} style={{background:'#fff8f0',border:'1.5px solid #ffb74d',
                    borderRadius:10,padding:'12px 16px',marginBottom:8}}>
                    <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:8}}>
                      <span style={{fontSize:13,fontFamily:'monospace',fontWeight:800,color:'#bf360c'}}>
                        {alert.alias}
                      </span>
                      <div style={{flex:1,height:6,background:'#ffe0b2',borderRadius:3,overflow:'hidden'}}>
                        <div style={{height:6,width:`${Math.min(pct,100)}%`,
                          background:pct<50?'#f44336':'#ff9800',borderRadius:3}}/>
                      </div>
                      <span style={{fontSize:12,fontWeight:700,color:'#e65100',flexShrink:0,display:'flex',alignItems:'center',gap:3}}>
                        {alert.vita_rimanente}min rim. / {alert.consumo_totale}min req.
                        <InfoTooltip text={"Vita rimanente: minuti residui letti dal TOA Sinumerik (life_remaining del parametro utensile).\nConsumo totale: somma dei tempoStimato di tutti i programmi nel MAIN che usano questo utensile."} position='left' />
                      </span>
                    </div>
                    {cr&&<div style={{background:'#ffecb3',border:'1px solid #ffc107',
                      borderRadius:7,padding:'8px 12px',fontSize:12}}>
                      <div style={{fontWeight:800,color:'#e65100',marginBottom:3}}>
                        ⚠ Finisce durante: <span style={{fontFamily:'monospace'}}>{cr.filename?.replace(/\.MPF$/i,'')}</span>
                        <span style={{color:'#9a6b2e',marginLeft:6,fontWeight:600}}>pgm {cr.numPgm}</span>
                      </div>
                      <div style={{color:'#5d4037'}}>
                        {alert.vita_rimanente}min disponibili / {alert.consumo_totale}min richiesti
                      </div>
                    </div>}
                  </div>
                )
              })}
            </div>
          )}
        </div>
        <div style={{padding:'12px 24px',borderTop:'1px solid #D8D5CC',
          display:'flex',gap:10,justifyContent:'flex-end',
          background:'#F5F4F0',borderRadius:'0 0 14px 14px'}}>
          <button onClick={chiudi}
            style={{background:'#D4700A',border:'none',borderRadius:8,
              color:'#fff',fontWeight:700,fontSize:13,padding:'8px 20px',cursor:'pointer'}}>
            OK, ho capito
          </button>
        </div>
      </div>
    </div>
  )
}

export default function Macchina() {
  const [tools, setTools]             = useState([])
  const [syncStatus, setSyncStatus]   = useState(null)
  const [setupPopup, setSetupPopup]   = useState(false)
  const [setupData,  setSetupData]    = useState(null)
  const [setupChiusoTs, setSetupChiusoTs] = useState(null)  // ts ultimo sync quando popup è stato chiuso
  const [setupLoading, setSetupLoading] = useState(false)
  const [storico, setStotico]         = useState([])
  const [popupSost, setPopupSost]     = useState(null)
  const [vitaOtt, setVitaOtt]         = useState([])  // suggerimenti vita ottimale ML
  const [utilizzoMag, setUtilizzoMag] = useState(null) // analisi utilizzo magazine
  const [utilizzoLoading, setUtilizzoLoading] = useState(false)
  const [utilizzoGiorni, setUtilizzoGiorni]   = useState(90)
  const [utilizzoFiltro, setUtilizzoFiltro]   = useState('tutti')
  const [showUtilizzo, setShowUtilizzo]         = useState(false)

  useEffect(() => {
    fetch('/api/tool-history/sostituzioni?limit=50')
      .then(r=>r.json()).then(d=>setStotico(d.sostituzioni||[])).catch(()=>{})
    // Controlla sostituzioni non classificate
    fetch('/api/tool-history/sostituzioni/non-classificate')
      .then(r=>r.ok?r.json():null)
      .then(d=>{ if(d?.sostituzioni?.length>0) setPopupSost(d.sostituzioni[0]) })
      .catch(()=>{})
    // Suggerimenti vita ottimale ML
    fetch('/api/tool-history/vita-ottimale')
      .then(r=>r.ok?r.json():null)
      .then(d=>{ if(d?.suggerimenti) setVitaOtt(d.suggerimenti) })
      .catch(()=>{})
  }, [])

  const fetchUtilizzo = (giorni=90) => {
    setUtilizzoLoading(true)
    fetch(`/api/tool-history/utilizzo-magazine?giorni=${giorni}`)
      .then(r=>r.json())
      .then(d=>{ setUtilizzoMag(d) })
      .catch(err=>{ setUtilizzoMag({ok:false, error: String(err)}) })
      .finally(()=>setUtilizzoLoading(false))
  }

  // ── Popup Analisi Setup (componente interno) ──────────────────────────────

  const [loading, setLoading]         = useState(false)
  const [syncing, setSyncing]         = useState(false)
  const [syncMsg, setSyncMsg]         = useState(null)
  const [errorSync, setErrorSync]     = useState(null)
  const [searchSync, setSearchSync]   = useState('')
  const [checkFiles, setCheckFiles]   = useState([])
  const [checking, setChecking]       = useState(false)
  const [checkResult, setCheckResult] = useState(null)
  const [checkError, setCheckError]   = useState(null)
  const [cicliUtensile, setCicliUtensile] = useState({})  // { "ALIAS": {n_cicli, programmi:[]} }
  const fileInputRef = useRef()

  const mountedRef = useRef(true)
  useEffect(() => { mountedRef.current = true; return () => { mountedRef.current = false } }, [])
  useEffect(() => { loadSync() }, [])

  async function loadSync() {
    setLoading(true)
    try {
      const [t, s] = await Promise.all([api.getTools(), api.getToolsSyncStatus()])
      if (!mountedRef.current) return
      setTools(t); setSyncStatus(s)
    } catch (e) { if (mountedRef.current) setErrorSync(e.message) }
    finally { if (mountedRef.current) setLoading(false) }
    // Carica cicli utensile in background (dati storici)
    fetch('/api/report/cicli-utensile')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (mountedRef.current && d?.per_utensile) setCicliUtensile(d.per_utensile) })
      .catch(() => {})
  }

  async function handleSync() {
    setSyncing(true); setSyncMsg(null); setErrorSync(null)
    try {
      const r = await api.syncTools()
      const fmtLabel = r.format_used ? ` · ${r.format_used.toUpperCase()}` : ''
      setSyncMsg(`${r.tool_count} utensili, ${r.positions_mapped} posizioni${fmtLabel}`)
      await loadSync()
      // Dopo sync, carica analisi setup automaticamente
      loadSetupAnalisi()
    } catch (e) { setErrorSync(e.message) }
    finally { setSyncing(false) }
  }

  // Carica analisi setup all'apertura del tab
  useEffect(() => { loadSetupAnalisi() }, []) // eslint-disable-line

  async function loadSetupAnalisi(forceOpen = false) {
    setSetupLoading(true)
    try {
      const r = await fetch('/api/progetti/analisi-setup/non-utilizzati')
      if (r.ok) {
        const d = await r.json()
        setSetupData(d)
        const haProblemi = d.da_montare.length > 0 || d.fin_vita.length > 0 || d.previsione_vita?.length > 0
        if (forceOpen) {
          setSetupPopup(true)
        }
      }
    } catch {}
    finally { setSetupLoading(false) }
  }

  async function handleCheckFiles(newFiles) {
    if (!newFiles.length) return
    const all = [...checkFiles, ...Array.from(newFiles).filter(f => !checkFiles.find(x => x.name === f.name))]
    setCheckFiles(all)
    setChecking(true); setCheckResult(null); setCheckError(null)
    try {
      // Controlla il primo file (API supporta uno alla volta — aggrega lato client)
      const results = await Promise.all(all.map(f => api.checkToolsMpf(f)))
      // Aggrega risultati
      const agg = { ok: [], missing: [], disabled: [], worn: [], can_run: true, total_required: 0 }
      results.forEach(r => {
        r.missing.forEach(n => { if (!agg.missing.includes(n)) agg.missing.push(n) })
        r.disabled.forEach(n => { if (!agg.disabled.includes(n)) agg.disabled.push(n) })
        r.worn.forEach(n => { if (!agg.worn.includes(n)) agg.worn.push(n) })
        r.ok.forEach(n => { if (!agg.ok.includes(n)) agg.ok.push(n) })
        agg.total_required += r.total_required
        if (!r.can_run) agg.can_run = false
      })
      setCheckResult(agg)
    } catch (e) { setCheckError(e.message) }
    finally { setChecking(false) }
  }

  function resetFiles() {
    setCheckFiles([]); setCheckResult(null); setCheckError(null)
  }

  const filtered = tools.filter(t => !searchSync || t.name.toLowerCase().includes(searchSync.toLowerCase()))
  const stime_live = setupData?.stime_live || {}

  const btn_small = {
    padding: '6px 14px', borderRadius: 5, fontSize: 12, cursor: 'pointer',
    background: 'var(--bg-hover)', border: '1px solid var(--border)',
    color: 'var(--text-secondary)', fontWeight: 500,
  }

  return (
    <>
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12, padding: '12px 20px 0', overflowY: 'auto' }}>
      <SectionHeader title="Utensili in macchina" subtitle="" />

      {/* Coda Esecuzione */}
      <CodaEsecuzione setupData={setupData} onOrdineChanged={loadSetupAnalisi} />

      {/* Toolbar: MPF a sinistra (grande), sync a destra (piccolo) */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
        {/* PRIMARI */}
        <button onClick={() => fileInputRef.current?.click()} style={{
          padding: '10px 22px', borderRadius: 7, cursor: 'pointer',
          background: 'var(--navy-700)', border: 'none',
          color: 'white', fontSize: 14, fontWeight: 700,
        }}>+ Aggiungi MPF</button>
        <input ref={fileInputRef} type="file" accept=".mpf,.nc,.spf" multiple
          style={{ display: 'none' }}
          onChange={e => handleCheckFiles(e.target.files)} />
        <button onClick={resetFiles} style={btn_small}>Reset</button>
        <button onClick={()=>{ setShowUtilizzo(v=>!v); if(!utilizzoMag) fetchUtilizzo(utilizzoGiorni) }}
          style={{...btn_small,
            background: showUtilizzo ? '#0d2d5e' : 'var(--bg-hover)',
            color:      showUtilizzo ? '#fff'    : 'var(--text-secondary)',
            border:     showUtilizzo ? '1px solid #0d2d5e' : '1px solid var(--border)'}}>
          📊 Utilizzo
        </button>

        {checkFiles.length > 0 && (
          <span style={{ fontSize: 12, color: 'var(--navy-accent)', fontFamily: 'var(--font-mono)' }}>
            {checkFiles.length} file caricati
          </span>
        )}

        {/* SECONDARI a destra */}
        <div style={{ marginLeft: 'auto', display: 'flex', alignItems: 'center', gap: 8 }}>
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
            {syncStatus?.last_sync
              ? `Sync: ${new Date(syncStatus.last_sync).toLocaleString('it-IT')} — ${syncStatus.tool_count} ut.${syncStatus.format_used ? ' · ' + syncStatus.format_used.toUpperCase() : ''}`
              : 'Nessun sync'}
          </span>
          <button
            onClick={()=>{ loadSetupAnalisi(true) }}
            style={{
              padding:'9px 18px', borderRadius:8, fontSize:13, cursor:'pointer',
              background: setupPopup
                ? '#B45309'
                : setupData && ((setupData.da_montare||[]).length + (setupData.fin_vita||[]).length + (setupData.previsione_vita||[]).length) > 0
                  ? '#D97706'
                  : '#1D5FAD',
              color: 'white',
              border: 'none',
              fontWeight: 700,
              boxShadow: setupData && ((setupData.da_montare||[]).length + (setupData.fin_vita||[]).length) > 0
                ? '0 0 0 3px rgba(217,119,6,0.3)' : 'none',
              transition: 'all 0.15s',
            }}>
            {setupLoading
              ? '⏳ Analisi...'
              : setupData
                ? `🔧 Setup (${(setupData.da_montare||[]).length + (setupData.fin_vita||[]).length + (setupData.previsione_vita||[]).length})`
                : '🔧 Analisi Setup'}
          </button>
          <button onClick={handleSync} disabled={syncing} style={{
            ...btn_small,
            animation: syncing ? 'spin 1s linear infinite' : 'none',
          }}>
            {syncing ? '↻ Sync...' : '↻ Sync macchina'}
          </button>
        </div>
      </div>

      {/* Messaggi */}
      {syncMsg && <div style={{ padding: '8px 12px', borderRadius: 6, fontSize: 12,
        background: 'rgba(22,163,74,0.07)', border: '1px solid rgba(22,163,74,0.2)',
        color: 'var(--green)' }}>✓ Sync: {syncMsg}</div>}
      {errorSync && <div style={{ padding: '8px 12px', borderRadius: 6, fontSize: 12,
        background: 'rgba(255,68,85,0.08)', border: '1px solid rgba(255,68,85,0.25)',
        color: 'var(--red)' }}>✕ {errorSync}</div>}

      {/* Istruzioni primo sync */}
      {!syncStatus?.last_sync && (
        <div style={{ padding: '10px 14px', borderRadius: 8, fontSize: 12,
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          color: 'var(--text-secondary)' }}>
          Prima sync: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--navy-accent)' }}>
          HMI → Servizi → Salva Attrezzaggio → Z:\DMG_DMC_160U\TOOL_SYNC</span>, poi ↻ Sync macchina
        </div>
      )}

      {/* ── Pannello Utilizzo Magazine (toggle) ──────────────────────── */}
      {showUtilizzo&&(
        <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,padding:'14px 18px'}}>
          <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:10,flexWrap:'wrap'}}>
            <span style={{fontSize:11,fontWeight:800,letterSpacing:'.08em',color:'#64748b',textTransform:'uppercase'}}>
              📊 Utilizzo utensili — magazine
            </span>
            {utilizzoMag&&(
              <div style={{display:'flex',gap:5,flexWrap:'wrap'}}>
                {[
                  {id:'tutti',        label:'Tutti',          n:utilizzoMag.riepilogo.totale_in_macchina, col:'#64748b'},
                  {id:'inutilizzato', label:'🔴 Inutilizzati', n:utilizzoMag.riepilogo.inutilizzati,      col:'#dc2626'},
                  {id:'dormiente',    label:'🟡 Dormienti',    n:utilizzoMag.riepilogo.dormienti,          col:'#d97706'},
                  {id:'attivo',       label:'🟢 Attivi',       n:utilizzoMag.riepilogo.attivi,             col:'#16a34a'},
                  {id:'nuovo',        label:'⚪ Nuovi',        n:utilizzoMag.riepilogo.nuovi,              col:'#94a3b8'},
                ].map(f=>(
                  <button key={f.id} onClick={()=>setUtilizzoFiltro(f.id)}
                    style={{fontSize:10,fontWeight:utilizzoFiltro===f.id?800:500,
                      padding:'2px 8px',borderRadius:8,border:'none',cursor:'pointer',
                      background:utilizzoFiltro===f.id?f.col:'#f1f5f9',
                      color:utilizzoFiltro===f.id?'#fff':'#64748b'}}>
                    {f.label}{f.n!=null?` (${f.n})`:''}
                  </button>
                ))}
              </div>
            )}
            <div style={{marginLeft:'auto',display:'flex',gap:5,alignItems:'center'}}>
              <select value={utilizzoGiorni}
                onChange={e=>{setUtilizzoGiorni(Number(e.target.value));fetchUtilizzo(Number(e.target.value))}}
                style={{fontSize:11,border:'1px solid #e2e8f0',borderRadius:6,padding:'3px 6px',background:'#f8fafc'}}>
                <option value={30}>30 giorni</option>
                <option value={90}>90 giorni</option>
                <option value={180}>180 giorni</option>
                <option value={365}>365 giorni</option>
              </select>
              <button onClick={()=>fetchUtilizzo(utilizzoGiorni)}
                style={{fontSize:11,padding:'3px 10px',borderRadius:6,border:'1px solid #e2e8f0',
                  background:'#f8fafc',cursor:'pointer',color:'#475569'}}>
                {utilizzoLoading?'…':'↻'}
              </button>
              <button onClick={()=>setShowUtilizzo(false)}
                style={{fontSize:11,padding:'3px 8px',borderRadius:6,border:'1px solid #fca5a5',
                  background:'#fef2f2',cursor:'pointer',color:'#dc2626'}}>✕</button>
            </div>
          </div>
          {utilizzoLoading&&(
            <div style={{textAlign:'center',padding:'16px 0',color:'#94a3b8',fontSize:12}}>Analisi in corso…</div>
          )}
          {utilizzoMag&&!utilizzoMag.ok&&(
            <div style={{padding:'10px',background:'#fef2f2',borderRadius:8,fontSize:11,color:'#dc2626',fontFamily:'monospace'}}>
              ⚠ Errore: {utilizzoMag.error}<br/>{utilizzoMag.detail}
            </div>
          )}
          {utilizzoMag?.ok&&!utilizzoLoading&&(()=>{
            const lista=utilizzoMag.utensili.filter(u=>utilizzoFiltro==='tutti'||u.categoria===utilizzoFiltro)
            const CAT={
              attivo:       {dot:'🟢',col:'#16a34a',bg:'#f0fdf4',label:'Attivo'},
              dormiente:    {dot:'🟡',col:'#d97706',bg:'#fffbeb',label:'Dormiente'},
              inutilizzato: {dot:'🔴',col:'#dc2626',bg:'#fef2f2',label:'Inutilizzato'},
              nuovo:        {dot:'⚪',col:'#94a3b8',bg:'#f8fafc',label:'Nuovo'},
            }
            return(
              <div>
                <div style={{fontSize:10,color:'#94a3b8',marginBottom:8}}>
                  Analisi su {utilizzoMag.giorni_analisi} giorni · {utilizzoMag.data_analisi}
                  {utilizzoMag.riepilogo.inutilizzati>0&&(
                    <span style={{marginLeft:8,fontWeight:700,color:'#dc2626'}}>
                      ⚠ {utilizzoMag.riepilogo.inutilizzati} utensili mai chiamati
                    </span>
                  )}
                </div>
                <div style={{display:'grid',gridTemplateColumns:'repeat(auto-fill,minmax(250px,1fr))',gap:6}}>
                  {lista.map(u=>{
                    const c=CAT[u.categoria]||CAT.nuovo
                    return(
                      <div key={u.alias} style={{background:c.bg,border:`1px solid ${c.col}33`,
                        borderLeft:`3px solid ${c.col}`,borderRadius:8,padding:'8px 10px'}}>
                        <div style={{display:'flex',alignItems:'center',gap:6,marginBottom:3}}>
                          <span style={{fontSize:13}}>{c.dot}</span>
                          <span style={{fontSize:11,fontWeight:700,fontFamily:'monospace',
                            color:'#0f172a',flex:1,overflow:'hidden',textOverflow:'ellipsis',
                            whiteSpace:'nowrap'}}>{u.alias}</span>
                          <span style={{fontSize:10,fontWeight:700,color:c.col,
                            padding:'1px 5px',borderRadius:5,background:'#fff',
                            border:`1px solid ${c.col}44`,flexShrink:0}}>{c.label}</span>
                        </div>
                        <div style={{display:'flex',gap:8,fontSize:10,color:'#64748b',flexWrap:'wrap'}}>
                          {u.magazine!=null&&<span style={{fontFamily:'monospace'}}>M{u.magazine}{u.posizione!=null?` P${u.posizione}`:''}</span>}
                          {u.ultima_chiamata
                            ?<span>Ultima: <b style={{color:'#334155'}}>{u.ultima_chiamata}</b></span>
                            :<span style={{color:'#dc2626',fontWeight:700}}>Mai chiamato</span>}
                          {u.n_chiamate>0&&<span>{u.n_chiamate}×</span>}
                          {u.giorni_silenzio!=null&&(
                            <span style={{color:u.giorni_silenzio>90?'#dc2626':u.giorni_silenzio>30?'#d97706':'#94a3b8'}}>
                              {u.giorni_silenzio}gg fa
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  })}
                </div>
              </div>
            )
          })()}
        </div>
      )}

      {/* Lista file caricati */}
      {checkFiles.length > 0 && (
        <div style={{ padding: '8px 12px', borderRadius: 6,
          background: 'var(--bg-surface)', border: '1px solid var(--border)',
          fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>
          {checkFiles.map((f, i) => <span key={f.name} style={{ marginRight: 16 }}>{i+1}. {f.name}</span>)}
        </div>
      )}

      {/* Risultati confronto */}
      {checking && <div style={{ fontSize: 13, color: 'var(--text-dim)' }}>Analisi in corso…</div>}
      {checkError && <div style={{ padding: '8px 12px', borderRadius: 6, fontSize: 12,
        background: 'rgba(255,68,85,0.08)', color: 'var(--red)' }}>✕ {checkError}</div>}
      {checkResult && (
        <div style={{ background: 'var(--bg-surface)', border: '1px solid var(--border)',
                      borderRadius: 10, padding: '12px 14px' }}>
          {/* Banner */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10,
            padding: '8px 12px', borderRadius: 6,
            background: checkResult.can_run ? 'rgba(22,163,74,0.07)' : 'rgba(255,68,85,0.08)',
            border: `1px solid ${checkResult.can_run ? 'rgba(22,163,74,0.2)' : 'rgba(255,68,85,0.25)'}` }}>
            <span style={{ fontSize: 16 }}>{checkResult.can_run ? '✅' : '❌'}</span>
            <span style={{ fontWeight: 700, fontSize: 13,
              color: checkResult.can_run ? 'var(--green)' : 'var(--red)' }}>
              {checkResult.can_run ? 'Tutti gli utensili disponibili' : 'Utensili mancanti o non disponibili'}
            </span>
            <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginLeft: 8 }}>
              {checkResult.total_required} utensili richiesti
            </span>
          </div>
          {[
            { key: 'missing',  label: '❌ Mancanti',        color: 'missing'  },
            { key: 'disabled', label: '⚠️ Disabilitati',    color: 'disabled' },
            { key: 'worn',     label: '🟣 Vita < 10%',      color: 'worn'     },
            { key: 'ok',       label: '✅ Disponibili',     color: 'ok'       },
          ].map(({ key, label, color }) => {
            const list = checkResult[key]
            if (!list?.length) return null
            return (
              <div key={key} style={{ marginBottom: 8 }}>
                <div style={{ fontSize: 11, fontWeight: 600, color: COL[color].text,
                  fontFamily: 'var(--font-mono)', marginBottom: 4,
                  textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</div>
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                  {list.map(name => (
                    <span key={name} style={{ padding: '2px 8px', borderRadius: 3, fontSize: 12,
                      fontFamily: 'var(--font-mono)',
                      background: COL[color].bg, border: `1px solid ${COL[color].border}`,
                      color: COL[color].text }}>{name}</span>
                  ))}
                </div>
              </div>
            )
          })}
        </div>
      )}

      {/* Ricerca + contatore */}
      {!setupPopup && (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <input value={searchSync} onChange={e => setSearchSync(e.target.value)}
            placeholder="Cerca utensile…"
            style={{ flex: 1, maxWidth: 280, padding: '7px 12px', borderRadius: 6,
              background: 'var(--bg-surface)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', fontSize: 13, outline: 'none',
              fontFamily: 'var(--font-mono)' }} />
          <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
            {filtered.length} / {tools.length}
          </span>
        </div>
      )}

      {setupPopup && (
        <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.45)',
          zIndex:1000,display:'flex',alignItems:'flex-start',justifyContent:'center',
          padding:'40px 16px',overflowY:'auto'}}>
          <div style={{width:'100%',maxWidth:860,maxHeight:'85vh',overflowY:'auto'}}>
            <SetupPannel setupData={setupData} setupPopup={setupPopup}
              onChiudi={()=>{ setSetupPopup(false); setSetupChiusoTs(setupData?.sync_time||null) }} />
          </div>
        </div>
      )}

      {/* Tabella utensili */}
      {loading ? <Loader /> : tools.length === 0 ? null : (
        <div style={{ overflow: 'visible', background: 'var(--bg-surface)',
          borderRadius: 10, border: '1px solid var(--border)', marginBottom: 12 }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '2px solid var(--border)', background: '#f8fafc' }}>
                {[
                  { h:'Pos', t:'Posizione nel magazine Sinumerik.\nM = numero magazine · P = posizione slot.\nGli utensili fuori magazine (M—) non sono montati ma presenti in archivio TOA.' },
                  { h:'Nome utensile', t:'Alias utensile come registrato nel TOA (Tool Offset Archive) Sinumerik.\nUsato come chiave per associare i cicli di lavorazione registrati dal LOG macchina.' },
                  { h:'Duplo', t:'Numero fratello gemello (duplo) nel sistema Sinumerik.\nUtensili con lo stesso alias e duplo diverso sono gemelli intercambiabili — la macchina li alterna automaticamente quando uno si consuma.' },
                  { h:'L (mm)', t:'Lunghezza utensile in mm, letta dal TOA Sinumerik.\nValore di compensazione geometrica usato dal CNC per il calcolo delle traiettorie.' },
                  { h:'R (mm)', t:'Raggio utensile in mm, letto dal TOA Sinumerik.\nUsato per la compensazione del raggio nelle operazioni di fresatura.' },
                  { h:'Vita %', t:"Percentuale di vita utensile residua letta dal TOA Sinumerik.\n100% = utensile nuovo · 0% = vita esaurita (il CNC bloccherà l'uso).\nLa barra viola indica il livello residuo — rosso sotto il 10%." },
                  { h:'Cicli', t:'Numero di cicli NC eseguiti con questo utensile, rilevati dal LOG macchina.\nMostra anche la durata media per ciclo — utile per confrontare con il valore atteso dal CAM.' },
                  { h:'Stato', t:"Stato operativo dell'utensile:\n• Attivo — disponibile e nella norma\n• Worn — vita quasi esaurita (<10%)\n• Disabled — disabilitato nel Sinumerik\n• Fuori mag. — non montato nel magazine" },
                ].map(({h, t}) => (
                  <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 10,
                    fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
                    fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.1em',
                    position: 'sticky', top: 0, background: '#f8fafc', zIndex: 1 }}>
                    <span style={{display:'inline-flex',alignItems:'center',gap:3}}>
                      {h}<InfoTooltip text={t} position='bottom' />
                    </span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(t => {
                const fuoriMag = t.magazine == null
                const isDis    = !t.is_enabled || t.is_worn
                const isWorn   = t.life_percent !== null && t.life_percent < 10
                const rowBg    = fuoriMag ? 'rgba(0,0,0,0.02)' : isDis ? 'rgba(255,68,85,0.04)' : isWorn ? 'rgba(109,40,217,0.04)' : 'transparent'
                const mag  = t.magazine != null ? `M${t.magazine}` : null
                const pos  = t.position != null ? String(t.position).padStart(3,'0') : null
                return (
                  <tr key={t.tool_id}
                    style={{ borderBottom: '1px solid var(--border)', background: rowBg }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = rowBg}>
                    {/* POS — prominente */}
                    <td style={{ padding: '9px 14px', whiteSpace: 'nowrap' }}>
                      {mag
                        ? <span style={{ display:'inline-flex', alignItems:'center', gap:2 }}>
                            <span style={{ fontSize:12, fontFamily:'var(--font-mono)', fontWeight:800,
                              color:'#0d2d5e', background:'#eef4fb', padding:'3px 7px',
                              borderRadius:5, letterSpacing:'0.03em' }}>{mag}</span>
                            <span style={{ fontSize:13, fontFamily:'var(--font-mono)', fontWeight:700,
                              color:'#0f172a' }}>·{pos}</span>
                          </span>
                        : <span style={{ fontSize:12, color:'var(--text-dim)' }}>—</span>}
                    </td>
                    {/* Nome */}
                    <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 13,
                      color: isDis ? 'var(--text-dim)' : 'var(--text-primary)', fontWeight: 700 }}>{t.name}</td>
                    {/* Duplo */}
                    <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                      fontWeight: 700, color: '#475569' }}>#{t.duplo}</td>
                    {/* L mm */}
                    <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                      color: 'var(--text-secondary)' }}>{t.length?.toFixed(3)}</td>
                    {/* R mm */}
                    <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                      color: 'var(--text-secondary)' }}>{t.radius?.toFixed(3)}</td>
                    {/* Vita */}
                    <td style={{ padding: '9px 14px' }}>{(()=>{
                      const alias = (t.name||'').toUpperCase().trim()
                      const stima = stime_live?.[alias]
                      return <LifeBar
                        pct={t.life_percent}
                        pctStimato={stima?.life_percent_stimato}
                        stimaAffidabile={stima?.stima_affidabile}
                      />
                    })()}</td>
                    {/* Cicli — dati storici da lavorazioni_log */}
                    {(()=>{
                      const alias = (t.name||'').toUpperCase().trim()
                      const info  = cicliUtensile[alias]
                      if (!info || info.n_cicli < 1) return (
                        <td style={{ padding: '9px 14px' }}>
                          <span style={{ fontSize:11, color:'var(--text-dim)' }}>—</span>
                        </td>
                      )
                      // Calcola media ponderata del ciclo tra tutti i programmi
                      const pgms = info.programmi || []
                      const mediaMs = pgms.length > 0
                        ? pgms.reduce((a,p)=>a+p.media_sec*p.n,0) / pgms.reduce((a,p)=>a+p.n,0)
                        : null
                      const fmtSec = s => s<60?`${s}s`:s<3600?`${Math.round(s/60)}m`:`${(s/3600).toFixed(1)}h`
                      const hasAnomalia = pgms.some(p=>p.std_sec>0 && p.std_sec/p.media_sec > 0.3)
                      return (
                        <td style={{ padding: '9px 14px' }}
                          title={pgms.slice(0,5).map(p=>`${p.filename.replace('.MPF','')}: ${fmtSec(p.media_sec)} ±${fmtSec(p.std_sec)} (${p.n})`).join('\n')}>
                          <div style={{ display:'flex', alignItems:'center', gap:5 }}>
                            <span style={{ fontSize:12, fontFamily:'var(--font-mono)',
                              fontWeight:700, color: hasAnomalia?'#d97706':'#0d2d5e' }}>
                              {info.n_cicli}
                            </span>
                            {mediaMs && (
                              <span style={{ fontSize:10, color:'var(--text-dim)' }}>
                                ~{fmtSec(Math.round(mediaMs))}
                              </span>
                            )}
                            {hasAnomalia && (
                              <span style={{ fontSize:9, fontWeight:800, color:'#d97706',
                                background:'#fef3c7', padding:'1px 4px', borderRadius:3 }}>σ</span>
                            )}
                          </div>
                          <div style={{ fontSize:9, color:'var(--text-dim)', marginTop:1 }}>
                            {pgms.length} pgm tracciati
                          </div>
                        </td>
                      )
                    })()}
                    {/* Stato */}
                    <td style={{ padding: '9px 14px' }}>
                      {fuoriMag
                        ? <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
                            background: 'rgba(0,0,0,0.05)', padding: '2px 8px', borderRadius: 4 }}>FUORI MAG.</span>
                        : isDis
                        ? <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--red)',
                            background: 'rgba(255,68,85,0.1)', padding: '2px 8px', borderRadius: 4, fontWeight:700 }}>DISAB.</span>
                        : isWorn
                        ? <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#6d28d9',
                            background: 'rgba(109,40,217,0.1)', padding: '2px 8px', borderRadius: 4, fontWeight:700 }}>VITA BASSA</span>
                        : <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--green)',
                            background: 'rgba(22,163,74,0.08)', padding: '2px 8px', borderRadius: 4 }}>OK</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* ── Storico sostituzioni ─────────────────────────────────────── */}
      <div style={{background:'var(--bg-surface)',border:'1px solid var(--border)',
        borderRadius:10,overflow:'hidden',marginBottom:12}}>
        <div style={{padding:'10px 14px',borderBottom:'1px solid var(--border)',
          display:'flex',alignItems:'center',gap:8}}>
          <span style={{fontSize:10,fontWeight:700,letterSpacing:'0.1em',
            color:'var(--text-dim)',textTransform:'uppercase'}}>Storico sostituzioni</span>
          {storico.length>0&&<span style={{fontSize:10,fontWeight:700,color:'#6d28d9',
            background:'#f5f3ff',padding:'2px 8px',borderRadius:8}}>{storico.length}</span>}
        </div>
        {storico.length===0?(
          <div style={{padding:'16px',fontSize:12,color:'var(--text-dim)',textAlign:'center'}}>
            Nessuna sostituzione registrata — si aggiorna automaticamente ad ogni sync TOA
          </div>
        ):(
          <table style={{width:'100%',borderCollapse:'collapse'}}>
            <thead>
              <tr style={{background:'#f8fafc'}}>
                {['Data','Alias','Pos','Vita prima','Vita dopo','Tipo','Causa'].map(h=>(
                  <th key={h} style={{padding:'8px 12px',textAlign:'left',fontSize:10,
                    fontFamily:'var(--font-mono)',color:'var(--text-dim)',fontWeight:700,
                    textTransform:'uppercase',letterSpacing:'0.08em',
                    borderBottom:'1px solid var(--border)'}}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {storico.slice(0,20).map((r,i)=>{
                const isNew = r.tipo==='sostituito'
                return(
                  <tr key={i} style={{borderBottom:'1px solid var(--border)',
                    background:i%2===0?'transparent':'rgba(0,0,0,0.01)'}}>
                    <td style={{padding:'7px 12px',fontSize:11,fontFamily:'var(--font-mono)',
                      color:'var(--text-dim)'}}>{r.ts?.slice(0,16).replace('T',' ')}</td>
                    <td style={{padding:'7px 12px',fontSize:12,fontWeight:700,
                      fontFamily:'var(--font-mono)',color:'var(--text-primary)'}}>{r.alias}</td>
                    <td style={{padding:'7px 12px',fontSize:11,color:'var(--text-dim)'}}>{r.posizione||'—'}</td>
                    <td style={{padding:'7px 12px',fontSize:11,color:'#dc2626'}}>{r.vita_prima}%</td>
                    <td style={{padding:'7px 12px',fontSize:11,color:'#16a34a'}}>{r.vita_dopo}%</td>
                    <td style={{padding:'7px 12px'}}>
                      <span style={{fontSize:10,fontWeight:700,
                        color: isNew?'#6d28d9':'#0369a1',
                        background: isNew?'#f5f3ff':'#e0f2fe',
                        padding:'2px 8px',borderRadius:4}}>
                        {r.tipo}
                      </span>
                    </td>
                    <td style={{padding:'7px 12px'}}>
                      {r.causa?(
                        <span style={{fontSize:10,fontWeight:700,color:'#16a34a',
                          background:'#dcfce7',padding:'2px 8px',borderRadius:4}}>
                          {r.causa.replace('_',' ')}
                        </span>
                      ):(
                        <button onClick={()=>setPopupSost(r)} style={{
                          fontSize:10,color:'#d97706',background:'#fffbeb',
                          border:'1px solid #fcd34d',borderRadius:4,padding:'2px 8px',cursor:'pointer'
                        }}>classifica</button>
                      )}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        )}
      </div>


      {/* ── Suggerimenti Vita Ottimale ML — visibile solo con dati reali (min 10 sostituzioni classificate) */}
      {vitaOtt.length>0&&(
        <div style={{background:'#fff',border:'1px solid #e2e8f0',borderRadius:12,
          padding:'14px 18px',marginTop:10}}>
          <div style={{display:'flex',alignItems:'center',gap:8,marginBottom:12}}>
            <span style={{fontSize:10,fontWeight:800,letterSpacing:'.1em',color:'#64748b',
              textTransform:'uppercase',display:'flex',alignItems:'center',gap:4}}>
              Vita ottimale — suggerimenti ML
              <InfoTooltip text={"Suggerimenti calcolati dall'algoritmo ML basati sullo storico reale delle sostituzioni utensile.\n\nVita ottimale: percentile 80 delle vite registrate — il punto in cui l\'utensile era tipicamente consumato senza rotture.\n\nRange sicuro: ±1 deviazione standard attorno alla vita ottimale.\n\nConfidenza:\n• Alta: ≥5 campioni, bassa variabilità\n• Bassa: 2-4 campioni o alta variabilità\n\nSuggerisce il valore di vita da impostare nel Sinumerik per ottimizzare i cambi utensile."} />
            </span>
            <span style={{fontSize:10,fontWeight:700,color:'#0891b2',background:'#e0f2fe',
              padding:'2px 8px',borderRadius:8}}>{vitaOtt.length} utensili</span>
          </div>
          <div style={{display:'flex',flexDirection:'column',gap:6}}>
            {vitaOtt.map((s,i)=>{
              const confCol = s.confidenza==='alta' ? '#16a34a' : '#d97706'
              const confBg  = s.confidenza==='alta' ? '#dcfce7' : '#fffbeb'
              const confBdr = s.confidenza==='alta' ? '#86efac' : '#fcd34d'
              return(
                <div key={i} style={{background:'#f8fafc',border:'1px solid #e2e8f0',
                  borderRadius:8,padding:'10px 14px'}}>
                  <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:6}}>
                    <span style={{fontSize:12,fontWeight:800,color:'#0d2d5e',
                      fontFamily:'monospace',flex:1}}>{s.alias}</span>
                    <span style={{fontSize:10,fontWeight:700,color:confCol,
                      background:confBg,border:`1px solid ${confBdr}`,
                      padding:'2px 8px',borderRadius:4}}>
                      {s.confidenza === 'alta' ? '✓ Alta' : '~ Bassa'}
                    </span>
                    <span style={{fontSize:10,color:'#94a3b8',display:'flex',alignItems:'center',gap:3}}>{s.n_campioni} campioni <InfoTooltip text={"Numero di sostituzioni registrate usate per calcolare la vita ottimale.\nOgni sostituzione classificata come usura normale contribuisce al calcolo."} /></span>
                  </div>
                  {/* Barra vita ottimale */}
                  <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:6}}>
                    <span style={{fontSize:11,color:'#64748b',minWidth:90,display:'flex',alignItems:'center',gap:3}}>Vita ottimale <InfoTooltip text={"Percentuale di vita suggerita da impostare nel Sinumerik.\nCalcolata come percentile 80 delle vite registrate all'atto della sostituzione normale (esclude rotture)."} /></span>
                    <div style={{flex:1,height:6,background:'#e2e8f0',borderRadius:3,overflow:'hidden'}}>
                      <div style={{height:'100%',width:`${s.vita_ottimale}%`,
                        background: s.vita_ottimale < 50 ? '#dc2626' : s.vita_ottimale < 75 ? '#d97706' : '#16a34a',
                        borderRadius:3}}/>
                    </div>
                    <span style={{fontSize:14,fontWeight:800,color:'#0d2d5e',
                      minWidth:42,textAlign:'right'}}>{s.vita_ottimale}%</span>
                  </div>
                  {/* Range */}
                  <div style={{fontSize:10,color:'#94a3b8',marginBottom:4}}>
                    Range sicuro: {s.range_min}% — {s.range_max}%
                    {s.n_rotture>0&&(
                      <span style={{color:'#dc2626',marginLeft:8}}>
                        · {s.pct_rotture}% rotture ({s.n_rotture})
                      </span>
                    )}
                  </div>
                  {/* Messaggio */}
                  <div style={{fontSize:11,color:'#475569',fontStyle:'italic',
                    borderTop:'1px solid #e2e8f0',paddingTop:6,marginTop:4}}>
                    {s.messaggio}
                  </div>
                </div>
              )
            })}
          </div>
          <div style={{fontSize:10,color:'#94a3b8',marginTop:10,textAlign:'center'}}>
            Basato su storico sostituzioni classificate · si aggiorna ad ogni sync TOA
          </div>
        </div>
      )}

      {popupSost&&(
        <PopupSostituzione
          sostituzione={popupSost}
          onClassifica={(ts,causa)=>{
            setStotico(prev=>prev.map(r=>r.ts===ts?{...r,causa}:r))
            setPopupSost(null)
          }}
          onIgnora={()=>setPopupSost(null)}
        />
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
    </>
  )
}
