// components/MLDataPopup.jsx
// Popup per raccolta dati classificazione — causa sostituzione utensile e causa fermo
import { useState, useEffect } from 'react'

// Cause per sostituzione fisica — utensile/inserti cambiati
const CAUSE_SOSTITUZIONE = [
  { id: 'usura_normale', label: 'Usura normale', desc: 'Degrado previsto, fine vita raggiunta',    color: '#d97706', bg: '#fffbeb', border: '#fcd34d' },
  { id: 'rottura',       label: 'Rottura',       desc: 'Fresa rovinata in modo non atteso',        color: '#dc2626', bg: '#fef2f2', border: '#fca5a5' },
]

// Cause per rimozione (utensile sparito dal TOA)
const CAUSE_RIMOZIONE = [
  { id: 'liberare_spazio',label: 'Libera spazio',    desc: 'Rimosso per holder o spazio magazzino', color: '#7c3aed', bg: '#f5f3ff', border: '#c4b5fd' },
  { id: 'rottura',        label: 'Rottura',          desc: 'Rotto e rimosso senza rimpiazzo',        color: '#dc2626', bg: '#fef2f2', border: '#fca5a5' },
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
      await fetch(`/api/tool-history/sostituzioni/${encodeURIComponent(sostituzione.ts)}/causa`, {
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
          <div style={{width:10,height:10,borderRadius:'50%',
            background:sostituzione.tipo==='rimosso'?'#7c3aed':'#d97706',flexShrink:0}}/>
          <div>
            <div style={{fontSize:14,fontWeight:800,color:'#0d2d5e'}}>
              {sostituzione.tipo === 'rimosso' ? 'Utensile rimosso' : 'Utensile sostituito'}
            </div>
            <div style={{fontSize:11,color:'#64748b',fontFamily:'monospace'}}>{sostituzione.alias}</div>
          </div>
          <div style={{marginLeft:'auto',fontSize:11,color:'#94a3b8',textAlign:'right'}}>
            <div style={{display:'flex',alignItems:'center',gap:4,justifyContent:'flex-end',flexWrap:'wrap'}}>
              <span>pos.{sostituzione.posizione||'—'}</span>
              {sostituzione.magazine&&(
                <span style={{background:'#f1f5f9',padding:'1px 5px',borderRadius:3,
                  fontSize:10,color:'#64748b'}}>
                  M{sostituzione.magazine}
                </span>
              )}
              {sostituzione.duplo>1&&(
                <span style={{background:'#fef9c3',padding:'1px 5px',borderRadius:3,
                  fontSize:10,color:'#854d0e',fontWeight:700,border:'1px solid #fcd34d'}}>
                  duplo #{sostituzione.duplo}
                </span>
              )}
            </div>
            <div>
              {sostituzione.vita_prima!=null?`${sostituzione.vita_prima}%`:'—'}
              {' → '}
              {sostituzione.vita_dopo!=null?`${sostituzione.vita_dopo}%`:'rimosso'}
            </div>
          </div>
        </div>

        <div style={{fontSize:12,fontWeight:700,color:'#64748b',marginBottom:10,
          textTransform:'uppercase',letterSpacing:'.07em'}}>
          {sostituzione.tipo === 'rimosso' ? 'Perché è stato rimosso?' : 'Perché è stato sostituito?'}
        </div>

        {/* Opzioni — dipendono dal tipo evento */}
        <div style={{display:'flex',flexDirection:'column',gap:7,marginBottom:16}}>
          {(sostituzione.tipo === 'rimosso' ? CAUSE_RIMOZIONE : CAUSE_SOSTITUZIONE).map(c => (
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
export function PopupFermo({ fermoSec, tsInizio, tsFine, onClassifica, onIgnora }) {
  const [selected, setSelected] = useState(null)
  const [loading, setLoading] = useState(false)

  const fmtDurata = (sec) => {
    const h = Math.floor(sec/3600), m = Math.floor((sec%3600)/60)
    return h > 0 ? `${h}h ${m}m` : `${m} min`
  }

  const fmtOra = (isoStr) => {
    if (!isoStr) return '—'
    const d = new Date(isoStr)
    return `${String(d.getHours()).padStart(2,'0')}:${String(d.getMinutes()).padStart(2,'0')}`
  }

  const oraInizio = fmtOra(tsInizio)
  const oraFine   = fmtOra(tsFine || new Date().toISOString())

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
            <div style={{fontSize:11,color:'#64748b'}}>
              {tsInizio ? (
                <>
                  {new Date(tsInizio).toLocaleDateString('it-IT',{day:'2-digit',month:'2-digit'})}
                  {' · '}
                  {oraInizio} → {oraFine}
                  {' · '}
                  <b>{fmtDurata(fermoSec)}</b>
                </>
              ) : fmtDurata(fermoSec)}
            </div>
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
