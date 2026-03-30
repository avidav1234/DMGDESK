// pages/Report.jsx — Report lavorazioni giornaliero
import { useState, useEffect, useCallback } from 'react'

const API = (path) => `/api/report${path}`
const fmt = (sec) => {
  if (!sec) return '—'
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
}
const fmtDate = (iso) => iso ? iso.replace('T',' ').slice(0,16) : '—'

export default function Report() {
  const today = new Date().toISOString().slice(0,10)
  const [data,    setData]    = useState(today)
  const [rpt,     setRpt]     = useState(null)
  const [storico, setStorico] = useState([])
  const [loading, setLoading] = useState(false)
  const [tab,     setTab]     = useState('riepilogo') // riepilogo | programmi | fermi | utensili

  const carica = useCallback(async () => {
    setLoading(true)
    try {
      const [r1, r2] = await Promise.all([
        fetch(API(`/giornaliero?data=${data}`)).then(r => r.json()),
        fetch(API(`/storico?giorni=14`)).then(r => r.json()),
      ])
      setRpt(r1)
      setStorico(r2)
    } catch(e) { console.error(e) }
    finally { setLoading(false) }
  }, [data])

  useEffect(() => { carica() }, [carica])

  const scaricaExcel = () => {
    window.open(API(`/export-excel-download?data=${data}`), '_blank')
  }

  if (loading) return (
    <div style={{ padding: 32, color: 'var(--text-dim)' }}>Caricamento report...</div>
  )

  return (
    <div style={{ padding: '16px 24px', maxWidth: 1200, margin: '0 auto' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 16, marginBottom: 20, flexWrap: 'wrap' }}>
        <div style={{ fontSize: 20, fontWeight: 800, color: 'var(--text-primary)' }}>
          📊 Report Lavorazioni
        </div>
        <input type="date" value={data} onChange={e => setData(e.target.value)}
          style={{ padding: '6px 12px', borderRadius: 6, border: '1px solid var(--border)',
                   background: 'var(--bg-card)', color: 'var(--text-primary)', fontSize: 13 }} />
        <button onClick={carica}
          style={{ padding: '6px 14px', borderRadius: 6, fontSize: 13, fontWeight: 600,
                   background: 'var(--bg-hover)', border: '1px solid var(--border)',
                   color: 'var(--text-secondary)', cursor: 'pointer' }}>
          🔄 Aggiorna
        </button>
        <button onClick={scaricaExcel}
          style={{ padding: '6px 14px', borderRadius: 6, fontSize: 13, fontWeight: 700,
                   background: 'rgba(34,197,94,0.12)', border: '1px solid rgba(34,197,94,0.3)',
                   color: '#22c55e', cursor: 'pointer', marginLeft: 'auto' }}>
          📥 Scarica Excel
        </button>
      </div>

      {/* Grafico storico 14 giorni */}
      {storico.length > 0 && (
        <div style={{ background: 'var(--bg-card)', borderRadius: 10, padding: '14px 18px',
                      border: '1px solid var(--border)', marginBottom: 20 }}>
          <div style={{ fontSize: 11, fontWeight: 700, letterSpacing: 1,
                        color: 'var(--text-dim)', marginBottom: 10 }}>ORE LAVORATE — ULTIMI 14 GIORNI</div>
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 60 }}>
            {storico.map(g => {
              const maxSec = Math.max(...storico.map(x => x.ore_lavorate_sec || 0)) || 1
              const h = Math.max(4, Math.round((g.ore_lavorate_sec / maxSec) * 56))
              const isToday = g.data === data
              return (
                <div key={g.data} style={{ flex: 1, display: 'flex', flexDirection: 'column',
                                           alignItems: 'center', cursor: 'pointer' }}
                     onClick={() => setData(g.data)} title={`${g.data}: ${g.ore_lavorate}`}>
                  <div style={{ width: '100%', height: h, borderRadius: '3px 3px 0 0',
                                background: isToday ? '#3b82f6' : 'var(--navy-500)',
                                opacity: g.ore_lavorate_sec > 0 ? 1 : 0.2 }} />
                  <div style={{ fontSize: 8, color: isToday ? '#3b82f6' : 'var(--text-dim)',
                                marginTop: 2, fontWeight: isToday ? 700 : 400 }}>
                    {g.data.slice(5)}
                  </div>
                </div>
              )
            })}
          </div>
        </div>
      )}

      {!rpt && <div style={{ color: 'var(--text-dim)' }}>Nessun dato per questa data.</div>}
      {rpt && (<>

        {/* KPI Cards */}
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(5, 1fr)', gap: 10, marginBottom: 20 }}>
          {[
            { label: 'Ore lavorate',   val: rpt.ore_lavorate,         color: '#22c55e' },
            { label: 'Tempo fermo',    val: rpt.tempo_fermo,          color: '#f59e0b' },
            { label: 'Efficienza',     val: `${rpt.efficienza_pct}%`, color: rpt.efficienza_pct > 70 ? '#22c55e' : '#ef4444' },
            { label: 'Programmi',      val: rpt.n_programmi,          color: '#3b82f6' },
            { label: 'Sessioni',       val: rpt.n_sessioni,           color: '#8b5cf6' },
          ].map(k => (
            <div key={k.label} style={{ background: 'var(--bg-card)', borderRadius: 8,
                                        padding: '12px 14px', border: '1px solid var(--border)',
                                        textAlign: 'center' }}>
              <div style={{ fontSize: 10, letterSpacing: 1, color: 'var(--text-dim)',
                            marginBottom: 4 }}>{k.label.toUpperCase()}</div>
              <div style={{ fontSize: 20, fontWeight: 800, color: k.color, fontVariantNumeric: 'tabular-nums' }}>
                {k.val}
              </div>
            </div>
          ))}
        </div>

        {/* Tab selector */}
        <div style={{ display: 'flex', gap: 2, marginBottom: 16,
                      borderBottom: '1px solid var(--border)' }}>
          {[
            ['riepilogo',  '📋 Riepilogo'],
            ['programmi',  '⚙️ Programmi'],
            ['fermi',      '⏸ Fermi'],
            ['utensili',   '🔧 Utensili'],
          ].map(([id, label]) => (
            <button key={id} onClick={() => setTab(id)}
              style={{ padding: '8px 16px', fontSize: 13, fontWeight: 600,
                       border: 'none', cursor: 'pointer',
                       borderBottom: tab === id ? '2px solid #3b82f6' : '2px solid transparent',
                       background: 'transparent',
                       color: tab === id ? '#3b82f6' : 'var(--text-dim)' }}>
              {label}
            </button>
          ))}
        </div>

        {/* Tab Riepilogo */}
        {tab === 'riepilogo' && (
          <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: 16 }}>
            {/* Progetti */}
            <div style={{ background: 'var(--bg-card)', borderRadius: 8,
                          border: '1px solid var(--border)', overflow: 'hidden' }}>
              <div style={{ padding: '10px 16px', background: '#1D5FAD',
                            fontSize: 11, fontWeight: 700, letterSpacing: 1, color: 'white' }}>
                PROGETTI LAVORATI
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: 'var(--bg-hover)' }}>
                    {['Progetto','Pallet','Ore','Pgm'].map(h => (
                      <th key={h} style={{ padding: '7px 12px', textAlign: 'left',
                                           fontSize: 11, color: 'var(--text-dim)',
                                           fontWeight: 600, letterSpacing: 0.5 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(rpt.progetti).map(([prog, info], i) => (
                    <tr key={prog} style={{ borderTop: '1px solid var(--border)',
                                            background: i % 2 === 0 ? 'transparent' : 'var(--bg-hover)' }}>
                      <td style={{ padding: '8px 12px', fontWeight: 700,
                                   color: 'var(--text-primary)', fontFamily: 'monospace' }}>{prog}</td>
                      <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>
                        {info.pallet ? `P${info.pallet}` : '—'}
                      </td>
                      <td style={{ padding: '8px 12px', fontFamily: 'monospace',
                                   color: '#22c55e', fontWeight: 600 }}>
                        {fmt(info.durata_sec)}
                      </td>
                      <td style={{ padding: '8px 12px', color: 'var(--text-secondary)' }}>
                        {info.n_programmi}
                      </td>
                    </tr>
                  ))}
                  {Object.keys(rpt.progetti).length === 0 && (
                    <tr><td colSpan={4} style={{ padding: 16, color: 'var(--text-dim)',
                                                  textAlign: 'center' }}>Nessun progetto</td></tr>
                  )}
                </tbody>
              </table>
            </div>

            {/* Utensili top */}
            <div style={{ background: 'var(--bg-card)', borderRadius: 8,
                          border: '1px solid var(--border)', overflow: 'hidden' }}>
              <div style={{ padding: '10px 16px', background: '#1D5FAD',
                            fontSize: 11, fontWeight: 700, letterSpacing: 1, color: 'white' }}>
                TOP UTENSILI (ore utilizzo)
              </div>
              <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
                <thead>
                  <tr style={{ background: 'var(--bg-hover)' }}>
                    {['Alias','Ore','%'].map(h => (
                      <th key={h} style={{ padding: '7px 12px', textAlign: 'left',
                                           fontSize: 11, color: 'var(--text-dim)', fontWeight: 600 }}>{h}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(rpt.utensili).slice(0,10).map(([alias, info], i) => {
                    const totSec = Object.values(rpt.utensili).reduce((a,v) => a + v.sec, 0) || 1
                    const pct = Math.round(info.sec / totSec * 100)
                    return (
                      <tr key={alias} style={{ borderTop: '1px solid var(--border)',
                                               background: i%2===0?'transparent':'var(--bg-hover)' }}>
                        <td style={{ padding: '8px 12px', fontWeight: 600, fontFamily: 'monospace',
                                     color: 'var(--text-primary)', fontSize: 12 }}>{alias}</td>
                        <td style={{ padding: '8px 12px', fontFamily: 'monospace',
                                     color: '#f59e0b', fontWeight: 600 }}>{info.ore}</td>
                        <td style={{ padding: '8px 12px' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
                            <div style={{ flex: 1, height: 6, background: 'var(--border)',
                                          borderRadius: 3, overflow: 'hidden' }}>
                              <div style={{ width: `${pct}%`, height: '100%',
                                            background: '#3b82f6', borderRadius: 3 }} />
                            </div>
                            <span style={{ fontSize: 11, color: 'var(--text-dim)', minWidth: 30 }}>{pct}%</span>
                          </div>
                        </td>
                      </tr>
                    )
                  })}
                  {Object.keys(rpt.utensili).length === 0 && (
                    <tr><td colSpan={3} style={{ padding: 16, color: 'var(--text-dim)',
                                                  textAlign: 'center' }}>Nessun utensile tracciato</td></tr>
                  )}
                </tbody>
              </table>
            </div>
          </div>
        )}

        {/* Tab Programmi */}
        {tab === 'programmi' && (
          <div style={{ background: 'var(--bg-card)', borderRadius: 8,
                        border: '1px solid var(--border)', overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: '#1D5FAD' }}>
                  {['Progetto','Comm.','Pos.','Fase','N°','Inizio','Fine','Durata','Utensile'].map(h => (
                    <th key={h} style={{ padding: '8px 10px', textAlign: 'left',
                                         color: 'white', fontWeight: 700, fontSize: 11,
                                         whiteSpace: 'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rpt.sessioni.flatMap(s =>
                  s.programmi.map((pgm, i) => (
                    <tr key={pgm.filename+i} style={{ borderTop: '1px solid var(--border)',
                                                       background: i%2===0?'transparent':'var(--bg-hover)' }}>
                      <td style={{ padding: '7px 10px', fontWeight: 600,
                                   fontFamily: 'monospace', fontSize: 11 }}>{s.progetto}</td>
                      <td style={{ padding: '7px 10px', fontFamily: 'monospace' }}>{pgm.commessa}</td>
                      <td style={{ padding: '7px 10px', fontFamily: 'monospace' }}>{pgm.posizione}</td>
                      <td style={{ padding: '7px 10px', fontFamily: 'monospace' }}>{pgm.fase}</td>
                      <td style={{ padding: '7px 10px', fontFamily: 'monospace' }}>{pgm.seq}</td>
                      <td style={{ padding: '7px 10px', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                        {fmtDate(pgm.inizio)}
                      </td>
                      <td style={{ padding: '7px 10px', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                        {fmtDate(pgm.fine)}
                      </td>
                      <td style={{ padding: '7px 10px', fontFamily: 'monospace',
                                   color: '#22c55e', fontWeight: 700 }}>
                        {fmt(pgm.durata_sec)}
                      </td>
                      <td style={{ padding: '7px 10px', fontFamily: 'monospace',
                                   fontSize: 11, color: '#f59e0b' }}>
                        {pgm.utensile || '—'}
                      </td>
                    </tr>
                  ))
                )}
                {rpt.sessioni.flatMap(s => s.programmi).length === 0 && (
                  <tr><td colSpan={9} style={{ padding: 20, textAlign: 'center',
                                               color: 'var(--text-dim)' }}>
                    Nessun programma registrato per questa data
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab Fermi */}
        {tab === 'fermi' && (
          <div style={{ background: 'var(--bg-card)', borderRadius: 8,
                        border: '1px solid var(--border)', overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
              <thead>
                <tr style={{ background: '#92400E' }}>
                  {['Progetto','Programma precedente','Programma successivo','Inizio fermo','Durata fermo'].map(h => (
                    <th key={h} style={{ padding: '8px 12px', textAlign: 'left',
                                         color: 'white', fontWeight: 700, fontSize: 11 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {rpt.sessioni.flatMap(s => {
                  const gaps = []
                  for (let i = 1; i < s.programmi.length; i++) {
                    const prev = s.programmi[i-1], curr = s.programmi[i]
                    if (!prev.fine || !curr.inizio) continue
                    const gap = Math.round(
                      (new Date(curr.inizio) - new Date(prev.fine)) / 1000)
                    if (gap < 10) continue
                    gaps.push({ prog: s.progetto, prev, curr, gap })
                  }
                  return gaps
                }).map((g, i) => (
                  <tr key={i} style={{ borderTop: '1px solid var(--border)',
                                       background: i%2===0?'#FEF9C3':'#FFFBEB' }}>
                    <td style={{ padding: '8px 12px', fontWeight: 600,
                                 fontFamily: 'monospace', fontSize: 11 }}>{g.prog}</td>
                    <td style={{ padding: '8px 12px', fontFamily: 'monospace',
                                 color: '#92400E', fontSize: 11 }}>{g.prev.filename}</td>
                    <td style={{ padding: '8px 12px', fontFamily: 'monospace',
                                 fontSize: 11 }}>{g.curr.filename}</td>
                    <td style={{ padding: '8px 12px', color: '#78350F',
                                 whiteSpace: 'nowrap' }}>{fmtDate(g.prev.fine)}</td>
                    <td style={{ padding: '8px 12px', fontFamily: 'monospace',
                                 fontWeight: 700, color: '#D97706' }}>{fmt(g.gap)}</td>
                  </tr>
                ))}
                {rpt.sessioni.flatMap(s => s.programmi).length < 2 && (
                  <tr><td colSpan={5} style={{ padding: 20, textAlign: 'center',
                                               color: 'var(--text-dim)' }}>
                    Nessun fermo rilevato
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

        {/* Tab Utensili */}
        {tab === 'utensili' && (
          <div style={{ background: 'var(--bg-card)', borderRadius: 8,
                        border: '1px solid var(--border)', overflow: 'auto' }}>
            <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 13 }}>
              <thead>
                <tr style={{ background: '#1D5FAD' }}>
                  {['#','Alias utensile','Ore di utilizzo','Secondi','% sul totale'].map(h => (
                    <th key={h} style={{ padding: '9px 14px', textAlign: 'left',
                                         color: 'white', fontWeight: 700, fontSize: 11 }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {Object.entries(rpt.utensili).map(([alias, info], i) => {
                  const totSec = Object.values(rpt.utensili).reduce((a,v) => a+v.sec, 0) || 1
                  const pct = (info.sec / totSec * 100).toFixed(1)
                  return (
                    <tr key={alias} style={{ borderTop: '1px solid var(--border)',
                                             background: i%2===0?'transparent':'var(--bg-hover)' }}>
                      <td style={{ padding: '9px 14px', color: 'var(--text-dim)',
                                   fontSize: 12 }}>{i+1}</td>
                      <td style={{ padding: '9px 14px', fontWeight: 700,
                                   fontFamily: 'monospace', color: 'var(--text-primary)' }}>{alias}</td>
                      <td style={{ padding: '9px 14px', fontFamily: 'monospace',
                                   color: '#f59e0b', fontWeight: 700, fontSize: 15 }}>{info.ore}</td>
                      <td style={{ padding: '9px 14px', color: 'var(--text-dim)',
                                   fontFamily: 'monospace' }}>{info.sec}s</td>
                      <td style={{ padding: '9px 14px' }}>
                        <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                          <div style={{ width: 140, height: 8, background: 'var(--border)',
                                        borderRadius: 4, overflow: 'hidden' }}>
                            <div style={{ width: `${pct}%`, height: '100%',
                                          background: '#3b82f6', borderRadius: 4 }} />
                          </div>
                          <span style={{ fontWeight: 700, color: '#3b82f6' }}>{pct}%</span>
                        </div>
                      </td>
                    </tr>
                  )
                })}
                {Object.keys(rpt.utensili).length === 0 && (
                  <tr><td colSpan={5} style={{ padding: 20, textAlign: 'center',
                                               color: 'var(--text-dim)' }}>
                    Nessun utensile tracciato oggi
                  </td></tr>
                )}
              </tbody>
            </table>
          </div>
        )}

      </>)}
    </div>
  )
}
