// pages/CodaLavorazione.jsx — fix layout pallet
import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'
import { Loader, ErrorBanner } from '../components/UI'

const REFRESH_MS = 5000
const STATI = ['vuoto','grezzo','finito','guasto']
const STATI_LABEL = { vuoto:'Vuoto', grezzo:'Grezzo', in_lavorazione:'In lavorazione', finito:'Finito', guasto:'Guasto' }
const PROG_STATUS = { 0:'Fermo', 1:'Interrotto', 2:'In attesa', 3:'In esecuzione' }

const PALLET_CFG = {
  in_lavorazione: { bg:'#0d2d5e', fg:'#fff',     bd:'#0d2d5e', label:'IN LAV.' },
  grezzo:         { bg:'#fefce8', fg:'#854d0e',   bd:'#eab308', label:'GREZZO'  },
  finito:         { bg:'#dcfce7', fg:'#14532d',   bd:'#22c55e', label:'FINITO'  },
  vuoto:          { bg:'#f1f5f9', fg:'#94a3b8',   bd:'#e2e8f0', label:'VUOTO'   },
  guasto:         { bg:'#fef2f2', fg:'#991b1b',   bd:'#f87171', label:'GUASTO'  },
}

function PalCard({ p, selected, onClick }) {
  const cfg = PALLET_CFG[p.stato] || PALLET_CFG.vuoto
  return (
    <div
      onClick={onClick}
      style={{
        background: cfg.bg,
        border: `1.5px solid ${cfg.bd}`,
        borderRadius: 8,
        cursor: 'pointer',
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        justifyContent: 'center',
        gap: 6,
        padding: 12,
        minHeight: 90,
        outline: selected ? '2px solid #7eb8f5' : 'none',
        outlineOffset: 2,
        transition: 'all 120ms ease',
        userSelect: 'none',
      }}
    >
      <span style={{ fontSize:16, fontWeight:700, color:cfg.fg, fontFamily:'var(--font-mono)', lineHeight:1 }}>
        Pallet {p.numero}
      </span>
      <span style={{
        fontSize:10, fontWeight:600, color:cfg.fg, fontFamily:'var(--font-mono)',
        letterSpacing:'.06em', opacity: p.stato === 'vuoto' ? .7 : 1,
      }}>
        {cfg.label}
      </span>
      {p.programma && (
        <span style={{ fontSize:9, color:cfg.fg, opacity:.65, maxWidth:120, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap', textAlign:'center' }}>
          {p.programma.split('/').pop()?.replace('_MPF','') || ''}
        </span>
      )}
    </div>
  )
}

function StatoPicker({ palletNum, statoAttuale, onScegli, onClose }) {
  return (
    <div style={{
      position:'absolute', top:'100%', left:0, right:0, zIndex:50,
      background:'#fff', border:'1px solid #e2e8f0', borderRadius:8,
      boxShadow:'0 4px 16px rgba(0,0,0,.10)', padding:8, marginTop:4,
    }}>
      <div style={{ fontSize:9, color:'#94a3b8', fontFamily:'var(--font-mono)', padding:'2px 6px 6px', textTransform:'uppercase', letterSpacing:'.08em' }}>
        Cambia stato Pallet {palletNum}
      </div>
      {STATI.filter(s => s !== statoAttuale).map(s => {
        const c = PALLET_CFG[s]
        return (
          <button key={s} onClick={() => onScegli(s)} style={{
            display:'block', width:'100%', textAlign:'left',
            padding:'7px 10px', border:'none', borderRadius:5,
            cursor:'pointer', fontSize:12, fontWeight:500,
            background:c.bg, color:c.fg, marginBottom:3,
            fontFamily:'var(--font-display)',
          }}>
            {STATI_LABEL[s]}
          </button>
        )
      })}
      <button onClick={onClose} style={{
        display:'block', width:'100%', textAlign:'center',
        padding:'5px', border:'1px solid #e2e8f0', borderRadius:5,
        cursor:'pointer', fontSize:11, color:'#94a3b8', background:'none',
        marginTop:2,
      }}>
        Annulla
      </button>
    </div>
  )
}

export default function CodaLavorazione() {
  const [pallet, setPallet] = useState(
    Array.from({length:6}, (_,i) => ({ numero:i+1, stato:'vuoto', programma:null }))
  )
  const [stato, setStato]       = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [selected, setSelected] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const timer = useRef(null)

  const loadLive = async (silent=false) => {
    try {
      if (!silent) setLoading(true)
      setError(null)
      try {
        const s = await api.getStatoMacchina()
        setStato(s)
        if (s.connessa && s.pallet_attivo != null) {
          setPallet(prev => prev.map(p => ({
            ...p,
            stato: p.numero === s.pallet_attivo ? 'in_lavorazione'
              : p.stato === 'in_lavorazione' ? 'finito' : p.stato,
            programma: p.numero === s.pallet_attivo ? s.programma_attivo : p.programma,
          })))
        }
      } catch {}
      setLastUpdate(new Date().toLocaleTimeString('it-IT'))
    } catch(e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    loadLive()
    timer.current = setInterval(() => loadLive(true), REFRESH_MS)
    return () => clearInterval(timer.current)
  }, [])

  const handleStato = (num, nuovoStato) => {
    setPallet(prev => prev.map(p => p.numero === num ? {...p, stato:nuovoStato} : p))
    setSelected(null)
  }

  const palletAttivo   = pallet.find(p => p.stato === 'in_lavorazione')
  const nGrezzi        = pallet.filter(p => p.stato === 'grezzo').length
  const nFiniti        = pallet.filter(p => p.stato === 'finito').length
  const progColor      = stato?.stato_programma === 3 ? '#16a34a' : stato?.stato_programma === 0 ? '#94a3b8' : '#d97706'

  return (
    <div className="fade-in" style={{ height:'100%', display:'flex', flexDirection:'column', gap:14 }}>

      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <div>
          <h1 style={{ fontSize:20, fontWeight:700, color:'#0f172a' }}>Coda lavorazione</h1>
          <p style={{ fontSize:12, color:'#94a3b8', marginTop:2 }}>
            DMG DMC 160U — 6 pallet{lastUpdate && <span> — aggiornato {lastUpdate}</span>}
          </p>
        </div>
        <button className="btn btn-ghost" style={{ fontSize:12 }} onClick={() => loadLive()}>↻ Aggiorna</button>
      </div>

      <ErrorBanner message={error} onClose={() => setError(null)} />

      {/* Stats */}
      <div style={{ display:'grid', gridTemplateColumns:'repeat(4,1fr)', gap:10 }}>
        {[
          { label:'In lavorazione', val: palletAttivo ? `Pallet ${palletAttivo.numero}` : '—', color:'#0d2d5e' },
          { label:'In coda (grezzi)', val: nGrezzi, color:'#16a34a' },
          { label:'Finiti', val: nFiniti, color:'#d97706' },
          { label:'Programma attivo', val: stato?.programma_attivo?.split('/').pop()?.replace('_MPF','').slice(0,18) || '—', color:progColor },
        ].map((s,i) => (
          <div key={i} style={{
            background:'#fff', border:'1px solid #e2e8f0',
            borderLeft:`3px solid ${s.color}`,
            borderRadius:'0 6px 6px 0', padding:'8px 14px',
          }}>
            <div style={{ fontSize:10, color:'#94a3b8', marginBottom:3 }}>{s.label}</div>
            <div style={{ fontSize:16, fontWeight:700, color:s.color, fontFamily:'var(--font-mono)' }}>{s.val}</div>
          </div>
        ))}
      </div>

      {/* Corpo diviso */}
      <div style={{ flex:1, display:'grid', gridTemplateColumns:'1fr 260px', gap:12, minHeight:0 }}>

        {/* SX — pallet */}
        <div className="card" style={{ padding:16, display:'flex', flexDirection:'column', gap:10, overflow:'auto' }}>
          <div style={{ fontSize:10, fontWeight:600, color:'#94a3b8', textTransform:'uppercase', letterSpacing:'.08em' }}>
            Stato pallet
          </div>
          {loading ? <Loader /> : (
            <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:10 }}>
              {pallet.map(p => (
                <div key={p.numero} style={{ position:'relative' }}>
                  <PalCard
                    p={p}
                    selected={selected === p.numero}
                    onClick={() => setSelected(selected === p.numero ? null : p.numero)}
                  />
                  {selected === p.numero && (
                    <StatoPicker
                      palletNum={p.numero}
                      statoAttuale={p.stato}
                      onScegli={s => handleStato(p.numero, s)}
                      onClose={() => setSelected(null)}
                    />
                  )}
                </div>
              ))}
            </div>
          )}
          <div style={{ fontSize:10, color:'#94a3b8', borderTop:'1px solid #e2e8f0', paddingTop:8, marginTop:'auto' }}>
            Clicca su un pallet per cambiarne lo stato manualmente. IN LAVORAZIONE viene aggiornato automaticamente dalla macchina.
          </div>
        </div>

        {/* DX — utensile + programma + allarmi */}
        <div style={{ display:'flex', flexDirection:'column', gap:10, overflow:'auto' }}>

          {/* Utensile attivo */}
          <div className="card" style={{ padding:14, flex:1 }}>
            <div style={{ fontSize:10, fontWeight:600, color:'#94a3b8', textTransform:'uppercase', letterSpacing:'.08em', marginBottom:10 }}>
              Utensile attivo
            </div>
            {stato?.connessa ? (
              <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
                <div style={{ fontFamily:'var(--font-mono)', fontSize:20, fontWeight:700, color:'#0d2d5e', letterSpacing:'-.01em' }}>
                  {stato.utensile_attivo || '—'}
                </div>
                <div style={{ fontSize:12, color:'#475569' }}>T{stato.numero_utensile || '—'}</div>
                <div style={{ height:1, background:'#e2e8f0' }} />
                <div style={{ display:'flex', justifyContent:'space-between', fontSize:12 }}>
                  <span style={{ color:'#94a3b8' }}>Stato</span>
                  <span style={{ color:progColor, fontFamily:'var(--font-mono)', fontWeight:600 }}>
                    {PROG_STATUS[stato.stato_programma] || '—'}
                  </span>
                </div>
              </div>
            ) : (
              <div style={{ textAlign:'center', color:'#94a3b8', fontSize:12 }}>
                <div style={{ fontSize:28, marginBottom:8, opacity:.3 }}>⚡</div>
                File log non disponibile.
                <br/>Avvia lo script XP per dati live.
              </div>
            )}
          </div>

          {/* Programma */}
          <div className="card" style={{ padding:14 }}>
            <div style={{ fontSize:10, fontWeight:600, color:'#94a3b8', textTransform:'uppercase', letterSpacing:'.08em', marginBottom:8 }}>
              Programma NC
            </div>
            {stato?.programma_attivo ? (
              <div style={{ fontFamily:'var(--font-mono)', fontSize:11, fontWeight:600, color:'#0d2d5e', wordBreak:'break-all', lineHeight:1.5 }}>
                {stato.programma_attivo.split('/').pop()?.replace('_MPF','') || stato.programma_attivo}
              </div>
            ) : (
              <div style={{ color:'#94a3b8', fontSize:12 }}>Nessun programma attivo</div>
            )}
            {palletAttivo && (
              <div style={{
                marginTop:8, display:'inline-flex', alignItems:'center', gap:6,
                background:'#0d2d5e', color:'#fff', padding:'3px 8px', borderRadius:4,
                fontSize:10, fontFamily:'var(--font-mono)', fontWeight:600,
              }}>
                Pallet {palletAttivo.numero} — IN LAV.
              </div>
            )}
          </div>

          {/* Allarmi */}
          <div className="card" style={{ padding:14 }}>
            <div style={{ fontSize:10, fontWeight:600, color:'#94a3b8', textTransform:'uppercase', letterSpacing:'.08em', marginBottom:8 }}>
              Allarmi
            </div>
            {stato?.allarme ? (
              <div style={{ fontSize:11, color:'#dc2626', fontFamily:'var(--font-mono)', lineHeight:1.5 }}>{stato.allarme}</div>
            ) : (
              <div style={{ fontSize:12, color:'#16a34a', display:'flex', alignItems:'center', gap:6 }}>
                <span>✓</span> Nessun allarme attivo
              </div>
            )}
          </div>

        </div>
      </div>
    </div>
  )
}