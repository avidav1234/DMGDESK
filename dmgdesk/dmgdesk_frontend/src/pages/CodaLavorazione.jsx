// pages/CodaLavorazione.jsx — DMG Desk home
// Vista divisa: pallet 2x3 sinistra | utensile attivo + programma destra
import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'
import { Loader, ErrorBanner, PalletBadge, WearBar } from '../components/UI'

const REFRESH_MS = 5000

const STATI = ['vuoto','grezzo','in_lavorazione','finito','guasto']
const STATI_LABEL = { vuoto:'Vuoto', grezzo:'Grezzo', in_lavorazione:'In lavorazione', finito:'Finito', guasto:'Guasto' }

const PROG_STATUS = { 0:'Fermo', 1:'Interrotto', 2:'In attesa', 3:'In esecuzione' }

function progStatusColor(s) {
  if (s === 3) return 'var(--green)'
  if (s === 0) return 'var(--text-dim)'
  return 'var(--amber)'
}

export default function CodaLavorazione() {
  const [pallet, setPallet]     = useState(
    Array.from({length:6}, (_,i) => ({ numero:i+1, stato:'vuoto', programma:null, main:null }))
  )
  const [stato, setStato]       = useState(null)
  const [loading, setLoading]   = useState(true)
  const [error, setError]       = useState(null)
  const [selected, setSelected] = useState(null)
  const [editStato, setEditStato] = useState(null)
  const [lastUpdate, setLastUpdate] = useState(null)
  const timer = useRef(null)

  const loadLive = async (silent=false) => {
    try {
      if (!silent) setLoading(true)
      setError(null)
      // Carica stato macchina live (se disponibile)
      try {
        const s = await api.getStatoMacchina()
        setStato(s)
        // Aggiorna pallet in lavorazione dal log
        if (s.connessa && s.pallet_attivo != null) {
          setPallet(prev => prev.map(p => ({
            ...p,
            stato: p.numero === s.pallet_attivo ? 'in_lavorazione'
              : p.stato === 'in_lavorazione' ? 'finito'
              : p.stato,
            programma: p.numero === s.pallet_attivo ? s.programma_attivo : p.programma,
          })))
        }
      } catch {}
      setLastUpdate(new Date().toLocaleTimeString('it-IT'))
    } catch (e) { setError(e.message) }
    finally { setLoading(false) }
  }

  useEffect(() => {
    loadLive()
    timer.current = setInterval(() => loadLive(true), REFRESH_MS)
    return () => clearInterval(timer.current)
  }, [])

  const handleSetStato = (palletNum, nuovoStato) => {
    setPallet(prev => prev.map(p =>
      p.numero === palletNum ? { ...p, stato: nuovoStato } : p
    ))
    setEditStato(null)
  }

  const palletAttivo = pallet.find(p => p.stato === 'in_lavorazione')
  const nInCoda = pallet.filter(p => p.stato === 'grezzo').length
  const nFiniti = pallet.filter(p => p.stato === 'finito').length

  return (
    <div className="fade-in" style={{ height:'100%', display:'flex', flexDirection:'column', gap:16 }}>

      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', justifyContent:'space-between' }}>
        <div>
          <h1 style={{ fontSize:20, fontWeight:700, color:'var(--text-primary)' }}>Coda lavorazione</h1>
          <p style={{ fontSize:12, color:'var(--text-dim)', marginTop:2 }}>
            DMG DMC 160U — 6 pallet
            {lastUpdate && <span> — aggiornato {lastUpdate}</span>}
          </p>
        </div>
        <button className="btn btn-ghost" style={{ fontSize:12 }} onClick={() => loadLive()}>
          ↻ Aggiorna
        </button>
      </div>

      <ErrorBanner message={error} onClose={() => setError(null)} />

      {/* Stats */}
      <div style={{ display:'flex', gap:10 }}>
        {[
          { label:'In lavorazione', value: palletAttivo ? `P${palletAttivo.numero}` : '—', color:'var(--navy-700)' },
          { label:'In coda (grezzi)', value: nInCoda, color:'var(--green)' },
          { label:'Finiti', value: nFiniti, color:'var(--amber)' },
          { label:'Programma attivo', value: stato?.programma_attivo
              ? stato.programma_attivo.split('/').pop()?.replace('_MPF','').slice(0,16)
              : '—',
            color: progStatusColor(stato?.stato_programma) },
        ].map((s,i) => (
          <div key={i} style={{
            background:'var(--bg-panel)', border:'1px solid var(--border)',
            borderLeft:`3px solid ${s.color}`,
            borderRadius:'0 var(--radius-sm) var(--radius-sm) 0',
            padding:'8px 14px', flex:1,
          }}>
            <div style={{ fontSize:10, color:'var(--text-dim)', marginBottom:3 }}>{s.label}</div>
            <div style={{ fontSize:16, fontWeight:700, color:s.color, fontFamily:'var(--font-mono)' }}>{s.value}</div>
          </div>
        ))}
      </div>

      {/* Vista divisa */}
      <div style={{ flex:1, display:'grid', gridTemplateColumns:'1fr 280px', gap:12, minHeight:0 }}>

        {/* SINISTRA — 6 pallet */}
        <div className="card" style={{ padding:16, display:'flex', flexDirection:'column', gap:12 }}>
          <div style={{ fontSize:11, fontWeight:600, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'.08em' }}>
            Stato pallet
          </div>
          {loading ? <Loader /> : (
            <div style={{ display:'grid', gridTemplateColumns:'repeat(2,1fr)', gap:10, flex:1 }}>
              {pallet.map(p => (
                <div key={p.numero} style={{ display:'flex', flexDirection:'column', gap:6 }}>
                  <PalletBadge
                    numero={p.numero}
                    stato={p.stato}
                    programma={p.programma}
                    selected={selected === p.numero}
                    onClick={() => setSelected(selected === p.numero ? null : p.numero)}
                  />
                  {/* Dropdown cambio stato */}
                  {selected === p.numero && (
                    <div style={{
                      background:'var(--bg-panel)', border:'1px solid var(--border)',
                      borderRadius:6, padding:6, display:'flex', flexDirection:'column', gap:2,
                    }}>
                      <div style={{ fontSize:9, color:'var(--text-dim)', fontFamily:'var(--font-mono)', marginBottom:2 }}>
                        CAMBIA STATO
                      </div>
                      {STATI.filter(s => s !== p.stato && s !== 'in_lavorazione').map(s => (
                        <button key={s}
                          onClick={() => handleSetStato(p.numero, s)}
                          style={{
                            background:'var(--bg-hover)', border:'1px solid var(--border)',
                            borderRadius:4, padding:'4px 8px', cursor:'pointer',
                            fontSize:11, color:'var(--text-primary)', textAlign:'left',
                            fontFamily:'var(--font-display)',
                          }}
                        >
                          {STATI_LABEL[s]}
                        </button>
                      ))}
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
          <div style={{ fontSize:10, color:'var(--text-dim)', borderTop:'1px solid var(--border)', paddingTop:8 }}>
            Clicca su un pallet per cambiarne lo stato manualmente.
            IN LAVORAZIONE viene aggiornato automaticamente dalla macchina.
          </div>
        </div>

        {/* DESTRA — utensile attivo + programma */}
        <div style={{ display:'flex', flexDirection:'column', gap:10 }}>

          {/* Utensile attivo */}
          <div className="card" style={{ padding:14, flex:1 }}>
            <div style={{ fontSize:11, fontWeight:600, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'.08em', marginBottom:10 }}>
              Utensile attivo
            </div>
            {stato?.connessa ? (
              <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
                <div style={{
                  fontFamily:'var(--font-mono)', fontSize:18, fontWeight:700,
                  color:'var(--navy-700)', letterSpacing:'-.01em',
                }}>
                  {stato.utensile_attivo || '—'}
                </div>
                <div style={{ fontSize:12, color:'var(--text-secondary)' }}>
                  T{stato.numero_utensile || '—'}
                </div>
                <div style={{ height:1, background:'var(--border)', margin:'4px 0' }} />
                <div style={{ display:'flex', justifyContent:'space-between', fontSize:12 }}>
                  <span style={{ color:'var(--text-dim)' }}>Stato programma</span>
                  <span style={{ color: progStatusColor(stato.stato_programma), fontFamily:'var(--font-mono)', fontWeight:600 }}>
                    {PROG_STATUS[stato.stato_programma] || '—'}
                  </span>
                </div>
                {stato.ultimo_aggiornamento && (
                  <div style={{ fontSize:10, color:'var(--text-dim)', fontFamily:'var(--font-mono)' }}>
                    {stato.ultimo_aggiornamento}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ color:'var(--text-dim)', fontSize:12 }}>
                <div style={{ fontSize:24, marginBottom:8, opacity:.3 }}>⚡</div>
                File log non disponibile.
                <br />Avvia lo script XP per dati live.
              </div>
            )}
          </div>

          {/* Programma attivo */}
          <div className="card" style={{ padding:14 }}>
            <div style={{ fontSize:11, fontWeight:600, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'.08em', marginBottom:10 }}>
              Programma NC
            </div>
            {stato?.programma_attivo ? (
              <div style={{ display:'flex', flexDirection:'column', gap:6 }}>
                <div style={{
                  fontFamily:'var(--font-mono)', fontSize:11, fontWeight:600,
                  color:'var(--navy-700)', wordBreak:'break-all', lineHeight:1.4,
                }}>
                  {stato.programma_attivo.split('/').pop()?.replace('_MPF','') || stato.programma_attivo}
                </div>
                {palletAttivo && (
                  <div className="pallet-badge pallet-lav" style={{ alignSelf:'flex-start', flexDirection:'row', gap:6 }}>
                    <span>P{palletAttivo.numero}</span>
                    <span style={{ opacity:.7 }}>IN LAVORAZIONE</span>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ color:'var(--text-dim)', fontSize:12 }}>Nessun programma attivo</div>
            )}
          </div>

          {/* Allarmi */}
          {stato?.connessa && (
            <div className="card" style={{ padding:14 }}>
              <div style={{ fontSize:11, fontWeight:600, color:'var(--text-dim)', textTransform:'uppercase', letterSpacing:'.08em', marginBottom:8 }}>
                Allarmi
              </div>
              {stato.allarme ? (
                <div style={{ fontSize:12, color:'var(--red)', fontFamily:'var(--font-mono)', lineHeight:1.5 }}>
                  {stato.allarme}
                </div>
              ) : (
                <div style={{ fontSize:12, color:'var(--green)', display:'flex', alignItems:'center', gap:6 }}>
                  <span>✓</span> Nessun allarme attivo
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}
