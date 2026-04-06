// components/MLDataPopup.jsx
// Popup per raccolta dati classificazione — causa sostituzione utensile e causa fermo
import { useState, useEffect } from 'react'

const CAUSE_SOSTITUZIONE = [
  { id: 'usura',          label: 'Usura',           desc: 'Utensile consumato normalmente',       color: '#d97706', bg: '#fffbeb', border: '#fcd34d' },
  { id: 'rottura',        label: 'Rottura',          desc: 'Utensile rotto durante lavorazione',   color: '#dc2626', bg: '#fef2f2', border: '#fca5a5' },
  { id: 'liberare_spazio',label: 'Libera spazio',    desc: 'Rimosso per holder o spazio magazzino',color: '#7c3aed', bg: '#f5f3ff', border: '#c4b5fd' },
]

const CAUSE_FERMO = [
  { id: 'setup',           label: 'Setup',            desc: 'Preparazione / cambio pallet / utensile', color: '#1D5FAD', bg: '#eff6ff', border: '#bfdbfe' },
  { id: 'allarme',         label: 'Allarme',          desc: 'Fermo per allarme macchina',              color: '#dc2626', bg: '#fef2f2', border: '#fca5a5' },
  { id: 'pausa_operatore', label: 'Pausa operatore',  desc: 'Pausa / assenza operatore',               color: '#64748b', bg: '#f8fafc', border: '#e2e8f0' },
  { id: 'altro',           label: 'Altro',            desc: 'Altra causa',                             color: '#94a3b8', bg: '#f8fafc', border: '#e2e8f0' },
]

// ── Popup sostituzione utensile ─────────────────────────────────────────────
export function PopupSostituzione({ sostituzione, onClassifica, onIgnora }) {
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)

  const handleSalva = async () => {
    if (!selected) return
    setLoading(true)
    try {
      await fetch(`/api/tools/sostituzioni/${encodeURIComponent(sostituzione.ts)}/causa`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ causa: selected }),
      })
      onClassifica(sostituzione.ts, selected)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position:'fixed', inset:0, background:'rgba(0,0,0,0.4)',
      display:'flex', alignItems:'center', justifyContent:'center',
      zIndex:1000, padding:16
    }}>
      <div style={{
        background:'#fff', borderRadius:14, padding:'20px 22px',
        width:'100%', maxWidth:420, boxShadow:'0 8px 32px rgba(0,0,0,0.18)'
      }}>
        {/* Header */}
        <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:16}}>
          <div style={{width:10,height:10,borderRadius:'50%',background:'#d97706',flexShrink:0}}/>
          <div>
            <div style={{fontSize:14,fontWeight:800,color:'#0d2d5e'}}>Utensile sostituito</div>
            <div style={{fontSize:11,color:'#64748b',fontFamily:'monospace'}}>{sostituzione.alias}</div>
          </div>
          <div style={{marginLeft:'auto',fontSize:11,color:'#94a3b8',textAlign:'right'}}>
            <div>pos.{sostituzione.posizione||'—'}</div>
            <div>{sostituzione.vita_prima}% → {sostituzione.vita_dopo}%</div>
          </div>
        </div>

        <div style={{fontSize:12,fontWeight:700,color:'#64748b',marginBottom:10,
          textTransform:'uppercase',letterSpacing:'.07em'}}>
          Perché è stato sostituito?
        </div>

        {/* Opzioni */}
        <div style={{display:'flex',flexDirection:'column',gap:7,marginBottom:16}}>
          {CAUSE_SOSTITUZIONE.map(c => (
            <button key={c.id} onClick={()=>setSelected(c.id)} style={{
              background: selected===c.id ? c.bg : '#f8fafc',
              border: `1.5px solid ${selected===c.id ? c.border : '#e2e8f0'}`,
              borderRadius:8, padding:'9px 14px', cursor:'pointer',
              display:'flex', alignItems:'center', gap:10, textAlign:'left',
              transition:'all .12s'
            }}>
              <div style={{
                width:16, height:16, borderRadius:'50%', flexShrink:0,
                border: `2px solid ${selected===c.id ? c.color : '#cbd5e1'}`,
                background: selected===c.id ? c.color : 'transparent',
              }}/>
              <div>
                <div style={{fontSize:13,fontWeight:700,color:selected===c.id?c.color:'#0d2d5e'}}>{c.label}</div>
                <div style={{fontSize:11,color:'#94a3b8'}}>{c.desc}</div>
              </div>
            </button>
          ))}
        </div>

        {/* Azioni */}
        <div style={{display:'flex',gap:8}}>
          <button onClick={onIgnora} style={{
            flex:1, padding:'9px', borderRadius:8, border:'1px solid #e2e8f0',
            background:'#f8fafc', color:'#94a3b8', fontSize:12, cursor:'pointer'
          }}>
            Ignora
          </button>
          <button onClick={handleSalva} disabled={!selected||loading} style={{
            flex:2, padding:'9px', borderRadius:8, border:'none',
            background: selected ? '#0d2d5e' : '#e2e8f0',
            color: selected ? '#fff' : '#94a3b8',
            fontSize:13, fontWeight:700, cursor: selected?'pointer':'default',
            transition:'all .12s'
          }}>
            {loading ? 'Salvo...' : 'Salva'}
          </button>
        </div>

        <div style={{fontSize:10,color:'#94a3b8',textAlign:'center',marginTop:10}}>
          Questi dati migliorano le previsioni di vita utensile
        </div>
      </div>
    </div>
  )
}

// ── Popup classificazione fermo ─────────────────────────────────────────────
export function PopupFermo({ fermoSec, tsInizio, onClassifica, onIgnora }) {
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)

  const fmtDurata = (sec) => {
    const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60)
    return h > 0 ? `${h}h ${m}m` : `${m} min`
  }

  const handleSalva = async () => {
    if (!selected) return
    setLoading(true)
    try {
      await fetch('/api/report/fermi/classifica', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ causa: selected, ts_inizio: tsInizio, durata_sec: fermoSec }),
      })
      onClassifica(selected)
    } catch (e) {
      console.error(e)
    } finally {
      setLoading(false)
    }
  }

  return (
    <div style={{
      position:'fixed', inset:0, background:'rgba(0,0,0,0.4)',
      display:'flex', alignItems:'center', justifyContent:'center',
      zIndex:1000, padding:16
    }}>
      <div style={{
        background:'#fff', borderRadius:14, padding:'20px 22px',
        width:'100%', maxWidth:400, boxShadow:'0 8px 32px rgba(0,0,0,0.18)'
      }}>
        {/* Header */}
        <div style={{display:'flex',alignItems:'center',gap:10,marginBottom:16}}>
          <div style={{width:10,height:10,borderRadius:'50%',background:'#ef4444',flexShrink:0}}/>
          <div>
            <div style={{fontSize:14,fontWeight:800,color:'#0d2d5e'}}>Fermo registrato</div>
            <div style={{fontSize:11,color:'#64748b'}}>Durata: {fmtDurata(fermoSec)}</div>
          </div>
        </div>

        <div style={{fontSize:12,fontWeight:700,color:'#64748b',marginBottom:10,
          textTransform:'uppercase',letterSpacing:'.07em'}}>
          Causa del fermo?
        </div>

        <div style={{display:'flex',flexDirection:'column',gap:7,marginBottom:16}}>
          {CAUSE_FERMO.map(c => (
            <button key={c.id} onClick={()=>setSelected(c.id)} style={{
              background: selected===c.id ? c.bg : '#f8fafc',
              border: `1.5px solid ${selected===c.id ? c.border : '#e2e8f0'}`,
              borderRadius:8, padding:'9px 14px', cursor:'pointer',
              display:'flex', alignItems:'center', gap:10, textAlign:'left',
              transition:'all .12s'
            }}>
              <div style={{
                width:16, height:16, borderRadius:'50%', flexShrink:0,
                border: `2px solid ${selected===c.id ? c.color : '#cbd5e1'}`,
                background: selected===c.id ? c.color : 'transparent',
              }}/>
              <div>
                <div style={{fontSize:13,fontWeight:700,color:selected===c.id?c.color:'#0d2d5e'}}>{c.label}</div>
                <div style={{fontSize:11,color:'#94a3b8'}}>{c.desc}</div>
              </div>
            </button>
          ))}
        </div>

        <div style={{display:'flex',gap:8}}>
          <button onClick={onIgnora} style={{
            flex:1, padding:'9px', borderRadius:8, border:'1px solid #e2e8f0',
            background:'#f8fafc', color:'#94a3b8', fontSize:12, cursor:'pointer'
          }}>
            Ignora
          </button>
          <button onClick={handleSalva} disabled={!selected||loading} style={{
            flex:2, padding:'9px', borderRadius:8, border:'none',
            background: selected ? '#0d2d5e' : '#e2e8f0',
            color: selected ? '#fff' : '#94a3b8',
            fontSize:13, fontWeight:700, cursor: selected?'pointer':'default',
          }}>
            {loading ? 'Salvo...' : 'Salva'}
          </button>
        </div>

        <div style={{fontSize:10,color:'#94a3b8',textAlign:'center',marginTop:10}}>
          Opzionale — aiuta il sistema a imparare
        </div>
      </div>
    </div>
  )
}
