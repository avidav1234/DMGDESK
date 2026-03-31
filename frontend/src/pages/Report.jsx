// pages/Report.jsx — Analytics lavorazioni CNC
import { useState, useEffect, useCallback, useRef, Fragment } from 'react'

const API = (path) => `/api/report${path}`

const fmt = (sec) => {
  if (!sec && sec !== 0) return '—'
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60), s = sec % 60
  return `${String(h).padStart(2,'0')}:${String(m).padStart(2,'0')}:${String(s).padStart(2,'0')}`
}
const fmtH = (sec) => {
  if (!sec) return '0h'
  return `${(sec / 3600).toFixed(1)}h`
}
const fmtDate = (iso) => iso ? iso.replace('T',' ').slice(0,16) : '—'
const fmtDay  = (iso) => {
  if (!iso) return ''
  const d = new Date(iso+'T00:00')
  return d.toLocaleDateString('it-IT',{weekday:'short',day:'numeric',month:'short'})
}

const PALETTE = ['#1D5FAD','#D97706','#7C3AED','#059669','#DC2626','#0891B2','#9333EA','#B45309','#065F46','#991B1B']
const _colorMap = {}
let _colorIdx = 0
const colorForProject = (name) => {
  if (!name) return '#888'
  if (!_colorMap[name]) _colorMap[name] = PALETTE[_colorIdx++ % PALETTE.length]
  return _colorMap[name]
}

const Card = ({ children, style = {} }) => (
  <div style={{ background:'var(--bg-card)', border:'1px solid var(--border)', borderRadius:10, ...style }}>
    {children}
  </div>
)
const SectionTitle = ({ children }) => (
  <div style={{ fontSize:11, fontWeight:700, letterSpacing:'0.08em', color:'var(--text-dim)',
                textTransform:'uppercase', marginBottom:14 }}>{children}</div>
)
const KpiCard = ({ label, value, sub, color = 'var(--text-primary)', trend }) => (
  <Card style={{ padding:'18px 20px', textAlign:'center' }}>
    <div style={{ fontSize:11, fontWeight:700, letterSpacing:'0.07em', color:'var(--text-dim)',
                  marginBottom:8, textTransform:'uppercase' }}>{label}</div>
    <div style={{ fontSize:28, fontWeight:800, color, fontVariantNumeric:'tabular-nums', lineHeight:1 }}>{value}</div>
    {sub && <div style={{ fontSize:12, color:'var(--text-dim)', marginTop:6 }}>{sub}</div>}
    {trend !== undefined && (
      <div style={{ fontSize:12, marginTop:5, color: trend >= 0 ? '#22c55e' : '#ef4444', fontWeight:600 }}>
        {trend >= 0 ? '▲' : '▼'} {Math.abs(trend).toFixed(1)}%
      </div>
    )}
  </Card>
)

function StoricoBars({ storico, selectedData, onSelect }) {
  if (!storico.length) return null
  const maxSec = Math.max(...storico.map(g => g.ore_lavorate_sec || 0), 1)
  return (
    <div>
      <div style={{ display:'flex', alignItems:'flex-end', gap:3, height:100 }}>
        {storico.map((g) => {
          const hPct = Math.max(5, (g.ore_lavorate_sec / maxSec) * 90)
          const isSelected = g.data === selectedData
          const effColor = g.efficienza_pct > 70 ? '#22c55e' : g.efficienza_pct > 40 ? '#f59e0b' : '#ef4444'
          return (
            <div key={g.data} style={{ flex:1, display:'flex', flexDirection:'column',
                                       alignItems:'center', cursor:'pointer', gap:2 }}
                 onClick={() => onSelect(g.data)}
                 title={`${fmtDay(g.data)}: ${fmtH(g.ore_lavorate_sec)}, ${g.efficienza_pct}% eff.`}>
              <div style={{ width:'60%', height:4, borderRadius:2,
                            background: isSelected ? effColor : effColor+'88' }} />
              <div style={{ width:'100%', height:hPct, borderRadius:'4px 4px 0 0',
                            background: isSelected ? '#3b82f6' : (g.ore_lavorate_sec > 0 ? '#1D5FAD88' : 'var(--border)'),
                            border: isSelected ? '1px solid #60a5fa' : 'none', transition:'all 0.15s' }} />
              <div style={{ fontSize:9, color: isSelected ? '#3b82f6' : 'var(--text-dim)',
                            fontWeight: isSelected ? 700 : 400 }}>
                {g.data.slice(8)}
              </div>
            </div>
          )
        })}
      </div>
      <div style={{ display:'flex', gap:16, marginTop:10, fontSize:11, color:'var(--text-dim)' }}>
        <span style={{ display:'flex', alignItems:'center', gap:4 }}>
          <span style={{ display:'inline-block', width:12, height:12, borderRadius:2, background:'#1D5FAD' }}/>
          Ore lavorate
        </span>
        <span style={{ display:'flex', alignItems:'center', gap:4 }}>
          <span style={{ display:'inline-block', width:28, height:4, borderRadius:2, background:'#22c55e' }}/>
          Efficienza
        </span>
      </div>
    </div>
  )
}

function TimelineGiornaliera({ sessioni }) {
  if (!sessioni?.length) return (
    <div style={{ color:'var(--text-dim)', fontSize:12, textAlign:'center', padding:20 }}>Nessuna sessione</div>
  )
  const ore = Array.from({length:24}, (_,h) => ({ h, lav:0, fermo:0 }))
  for (const s of sessioni) {
    for (const pgm of (s.programmi || [])) {
      if (!pgm.inizio || !pgm.fine) continue
      const dur = Math.max(0, (new Date(pgm.fine) - new Date(pgm.inizio)) / 1000)
      const h = new Date(pgm.inizio).getHours()
      if (ore[h]) ore[h].lav += dur
    }
    for (let i = 1; i < (s.programmi||[]).length; i++) {
      const prev = s.programmi[i-1], curr = s.programmi[i]
      if (!prev.fine || !curr.inizio) continue
      const gap = Math.max(0, (new Date(curr.inizio) - new Date(prev.fine)) / 1000)
      if (gap > 10) {
        const h = new Date(prev.fine).getHours()
        if (ore[h]) ore[h].fermo += gap
      }
    }
  }
  const maxSec = Math.max(...ore.map(o => o.lav + o.fermo), 1)
  return (
    <div>
      <div style={{ display:'flex', gap:1, alignItems:'flex-end', height:80 }}>
        {ore.map(o => {
          const lavH = Math.max(0, Math.round((o.lav / maxSec) * 72))
          const fermoH = Math.max(0, Math.round((o.fermo / maxSec) * 72))
          return (
            <div key={o.h} style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center' }}
                 title={`${String(o.h).padStart(2,'0')}:00 — Lav: ${fmt(o.lav)}, Fermo: ${fmt(o.fermo)}`}>
              <div style={{ width:'90%', display:'flex', flexDirection:'column', justifyContent:'flex-end', height:72 }}>
                {fermoH > 0 && <div style={{ background:'#f59e0b44', height:fermoH, borderRadius:'2px 2px 0 0' }}/>}
                {lavH > 0 && <div style={{ background:'#1D5FAD', height:lavH, borderRadius: fermoH>0?0:'2px 2px 0 0' }}/>}
              </div>
              <div style={{ fontSize:8, color:'var(--text-dim)', marginTop:2 }}>
                {o.h % 4 === 0 ? String(o.h).padStart(2,'0') : ''}
              </div>
            </div>
          )
        })}
      </div>
      <div style={{ display:'flex', gap:16, marginTop:10, fontSize:11, color:'var(--text-dim)' }}>
        <span style={{ display:'flex', alignItems:'center', gap:4 }}>
          <span style={{ display:'inline-block', width:12, height:12, borderRadius:2, background:'#1D5FAD' }}/> Lavorazione
        </span>
        <span style={{ display:'flex', alignItems:'center', gap:4 }}>
          <span style={{ display:'inline-block', width:10, height:10, borderRadius:2, background:'#f59e0b44', border:'1px solid #f59e0b88' }}/> Fermo
        </span>
      </div>
    </div>
  )
}

function ProgrammiChart({ sessioni }) {
  // Aggrega per filename: somma durata_sec di tutte le esecuzioni dello stesso programma
  // (un programma può apparire in più sessioni o essere stato stoppato e riavviato)
  const aggMap = {}
  for (const s of (sessioni || [])) {
    for (const p of (s.programmi || [])) {
      if (!p.filename || !(p.durata_sec > 0)) continue
      const key = (p.filename || '').toUpperCase()
      if (!aggMap[key]) {
        aggMap[key] = { filename: p.filename, durata_sec: 0, n_esecuzioni: 0, progetto: s.progetto }
      }
      aggMap[key].durata_sec   += p.durata_sec
      aggMap[key].n_esecuzioni += 1
    }
  }
  const allPgm = Object.values(aggMap)
    .sort((a, b) => b.durata_sec - a.durata_sec)
    .slice(0, 20)

  if (!allPgm.length) return (
    <div style={{ color:'var(--text-dim)', fontSize:12, textAlign:'center', padding:20 }}>Nessun programma</div>
  )
  const maxSec = allPgm[0].durata_sec
  return (
    <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
      {allPgm.map((p, i) => {
        const pct = (p.durata_sec / maxSec * 100).toFixed(1)
        const color = colorForProject(p.progetto)
        return (
          <div key={p.filename+i} style={{ display:'flex', alignItems:'center', gap:10 }}>
            <div style={{ width:160, fontSize:11, fontFamily:'monospace', color:'var(--text-secondary)',
                          textAlign:'right', flexShrink:0, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}
                 title={p.filename + (p.n_esecuzioni > 1 ? ` (${p.n_esecuzioni} esecuzioni aggregate)` : '')}>
              {(p.filename || '').replace('.MPF','').replace('.mpf','')}
            </div>
            <div style={{ flex:1, height:20, background:'var(--bg-hover)', borderRadius:4, overflow:'hidden' }}>
              <div style={{ width:`${pct}%`, height:'100%', background:color, borderRadius:4, transition:'width 0.4s ease' }} />
            </div>
            <div style={{ width:64, fontSize:12, fontFamily:'monospace', color, fontWeight:700, flexShrink:0, textAlign:'right' }}>
              {fmt(p.durata_sec)}
            </div>
            {p.n_esecuzioni > 1 && (
              <div style={{ fontSize:10, color:'var(--text-dim)', flexShrink:0, width:24, textAlign:'left' }}
                   title={`${p.n_esecuzioni} esecuzioni aggregate`}>
                ×{p.n_esecuzioni}
              </div>
            )}
          </div>
        )
      })}
    </div>
  )
}

function UtensiliDonut({ utensili }) {
  const entries = Object.entries(utensili || {}).slice(0, 8)
  if (!entries.length) return (
    <div style={{ color:'var(--text-dim)', fontSize:12, textAlign:'center', padding:20 }}>Nessun utensile</div>
  )
  const totSec = entries.reduce((a, [, v]) => a + v.sec, 0) || 1
  const colors = ['#1D5FAD','#D97706','#7C3AED','#059669','#DC2626','#0891B2','#9333EA','#B45309']
  const R = 52, CX = 64, CY = 64
  let cumPct = 0
  const slices = entries.map(([alias, info], i) => {
    const pct = info.sec / totSec
    const startAngle = cumPct * 2 * Math.PI - Math.PI / 2
    cumPct += pct
    const endAngle = cumPct * 2 * Math.PI - Math.PI / 2
    const x1 = CX + R * Math.cos(startAngle), y1 = CY + R * Math.sin(startAngle)
    const x2 = CX + R * Math.cos(endAngle),   y2 = CY + R * Math.sin(endAngle)
    const large = pct > 0.5 ? 1 : 0
    const path = pct > 0.999
      ? `M ${CX} ${CY - R} A ${R} ${R} 0 1 1 ${CX - 0.01} ${CY - R} Z`
      : `M ${x1} ${y1} A ${R} ${R} 0 ${large} 1 ${x2} ${y2}`
    return { alias, sec: info.sec, ore: info.ore, pct, path, color: colors[i % colors.length] }
  })
  return (
    <div style={{ display:'flex', gap:20, alignItems:'center' }}>
      <svg width={128} height={128} viewBox="0 0 128 128" style={{ flexShrink:0 }}>
        {slices.map((s, i) => (
          <path key={i} d={s.path} fill="none" stroke={s.color} strokeWidth={28} strokeLinecap="butt" opacity={0.9}>
            <title>{s.alias}: {s.ore} ({(s.pct*100).toFixed(1)}%)</title>
          </path>
        ))}
        <text x={CX} y={CY-5} textAnchor="middle" fontSize={11} fill="var(--text-dim)" fontWeight={600}>TOT</text>
        <text x={CX} y={CY+10} textAnchor="middle" fontSize={13} fill="var(--text-primary)" fontWeight={700}>{fmtH(totSec)}</text>
      </svg>
      <div style={{ flex:1, display:'flex', flexDirection:'column', gap:6 }}>
        {slices.map((s, i) => (
          <div key={i} style={{ display:'flex', alignItems:'center', gap:6 }}>
            <div style={{ width:8, height:8, borderRadius:2, background:s.color, flexShrink:0 }}/>
            <div style={{ flex:1, fontSize:12, fontFamily:'monospace', color:'var(--text-secondary)',
                          overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>{s.alias}</div>
            <div style={{ fontSize:12, fontFamily:'monospace', color:s.color, fontWeight:700, flexShrink:0 }}>{s.ore}</div>
          </div>
        ))}
      </div>
    </div>
  )
}

function HeatmapFermi({ sessioni }) {
  const GIORNI = ['Lun','Mar','Mer','Gio','Ven','Sab','Dom']
  const ORE = [6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22]
  const matrix = {}
  GIORNI.forEach(g => { matrix[g] = {}; ORE.forEach(h => { matrix[g][h] = 0 }) })
  for (const sess of (sessioni || [])) {
    if (!sess.data) continue
    const dow = new Date(sess.data+'T00:00').getDay()
    const label = GIORNI[dow === 0 ? 6 : dow - 1]
    for (let i = 1; i < (sess.programmi||[]).length; i++) {
      const prev = sess.programmi[i-1], curr = sess.programmi[i]
      if (!prev.fine || !curr.inizio) continue
      const gap = Math.max(0, (new Date(curr.inizio) - new Date(prev.fine)) / 1000)
      if (gap < 30) continue
      const h = new Date(prev.fine).getHours()
      if (matrix[label] && matrix[label][h] !== undefined) matrix[label][h] += gap
    }
  }
  const maxVal = Math.max(...GIORNI.flatMap(g => ORE.map(h => matrix[g][h])), 1)
  return (
    <div style={{ overflowX:'auto' }}>
      <div style={{ display:'grid', gridTemplateColumns:`52px repeat(${ORE.length}, 1fr)`, gap:2, minWidth:480 }}>
        <div/>
        {ORE.map(h => (
          <div key={h} style={{ fontSize:10, color:'var(--text-dim)', textAlign:'center', fontWeight:600 }}>
            {String(h).padStart(2,'0')}
          </div>
        ))}
        {GIORNI.map(g => (
          <Fragment key={g}>
            <div style={{ fontSize:11, color:'var(--text-dim)', fontWeight:600, display:'flex', alignItems:'center' }}>{g}</div>
            {ORE.map(h => {
              const val = matrix[g][h]
              const alpha = val > 0 ? Math.max(0.1, val / maxVal) : 0
              return (
                <div key={h} style={{ height:26, borderRadius:3,
                                      background: val > 0 ? `rgba(239,68,68,${alpha})` : 'var(--border)',
                                      border:'1px solid var(--border)', opacity: val > 0 ? 1 : 0.3 }}
                     title={val > 0 ? `${g} ${h}:00 — ${fmt(val)}` : `${g} ${h}:00`}/>
              )
            })}
          </Fragment>
        ))}
      </div>
      <div style={{ display:'flex', alignItems:'center', gap:8, marginTop:10, fontSize:11, color:'var(--text-dim)' }}>
        <span>Nessun fermo</span>
        {[0.1,0.3,0.5,0.7,0.9].map(a => (
          <div key={a} style={{ width:16, height:16, borderRadius:2, background:`rgba(239,68,68,${a})` }}/>
        ))}
        <span>Fermo lungo</span>
      </div>
    </div>
  )
}

function TabellaFermi({ sessioni }) {
  const fermi = (sessioni || []).flatMap(s => {
    const gaps = []
    for (let i = 1; i < (s.programmi||[]).length; i++) {
      const prev = s.programmi[i-1], curr = s.programmi[i]
      if (!prev.fine || !curr.inizio) continue
      const gap = Math.round((new Date(curr.inizio) - new Date(prev.fine)) / 1000)
      if (gap < 10) continue
      gaps.push({ prog: s.progetto, da: prev.filename, a: curr.filename, inizio: prev.fine, gap })
    }
    return gaps
  }).sort((a,b) => b.gap - a.gap)
  if (!fermi.length) return (
    <div style={{ color:'var(--text-dim)', fontSize:12, textAlign:'center', padding:20 }}>Nessun fermo rilevato</div>
  )
  return (
    <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
      <thead>
        <tr style={{ background:'var(--bg-hover)' }}>
          {['Durata','Ora','Commessa','Da','A'].map(h => (
            <th key={h} style={{ padding:'9px 12px', textAlign:'left', fontSize:11, color:'var(--text-dim)',
                                 fontWeight:700, letterSpacing:'0.04em', borderBottom:'1px solid var(--border)' }}>{h}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {fermi.map((f, i) => (
          <tr key={i} style={{ borderBottom:'1px solid var(--border)' }}>
            <td style={{ padding:'9px 12px', fontFamily:'monospace', fontWeight:700,
                         color: f.gap > 1800 ? '#ef4444' : f.gap > 600 ? '#f59e0b' : 'var(--text-secondary)' }}>
              {fmt(f.gap)}
            </td>
            <td style={{ padding:'9px 12px', color:'var(--text-dim)', whiteSpace:'nowrap', fontSize:12 }}>{fmtDate(f.inizio)}</td>
            <td style={{ padding:'9px 12px', fontFamily:'monospace', fontWeight:600, color:colorForProject(f.prog), fontSize:12 }}>{f.prog}</td>
            <td style={{ padding:'9px 12px', fontFamily:'monospace', fontSize:11, color:'var(--text-dim)' }}>{(f.da||'').replace('.MPF','')}</td>
            <td style={{ padding:'9px 12px', fontFamily:'monospace', fontSize:11, color:'var(--text-secondary)' }}>{(f.a||'').replace('.MPF','')}</td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function ConfrontoSettimane({ storico }) {
  if (!storico || storico.length < 14) return null
  const curr = storico.slice(-7)
  const prev = storico.slice(-14, -7)
  const totCurr = curr.reduce((a,g) => a + (g.ore_lavorate_sec||0), 0)
  const totPrev = prev.reduce((a,g) => a + (g.ore_lavorate_sec||0), 0)
  const effCurr = curr.reduce((a,g) => a + (g.efficienza_pct||0), 0) / 7
  const effPrev = prev.reduce((a,g) => a + (g.efficienza_pct||0), 0) / 7
  const pgmCurr = curr.reduce((a,g) => a + (g.n_programmi||0), 0)
  const pgmPrev = prev.reduce((a,g) => a + (g.n_programmi||0), 0)
  // OEE medio — solo giorni con dati
  const oeeCurrGiorni = curr.filter(g => g.oee?.valore)
  const oeePrevGiorni = prev.filter(g => g.oee?.valore)
  const oeeCurr = oeeCurrGiorni.length ? oeeCurrGiorni.reduce((a,g)=>a+(g.oee.valore||0),0)/oeeCurrGiorni.length : null
  const oeePrev = oeePrevGiorni.length ? oeePrevGiorni.reduce((a,g)=>a+(g.oee.valore||0),0)/oeePrevGiorni.length : null
  const delta = (a, b) => b === 0 ? 0 : ((a - b) / b * 100)
  return (
    <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr 1fr', gap:14 }}>
      <KpiCard label="Ore questa settimana" value={fmtH(totCurr)} sub={`Sett. prec.: ${fmtH(totPrev)}`}
               color="#3b82f6" trend={delta(totCurr, totPrev)} />
      <KpiCard label="Efficienza media" value={`${effCurr.toFixed(1)}%`} sub={`Sett. prec.: ${effPrev.toFixed(1)}%`}
               color={effCurr > 70 ? '#22c55e' : '#f59e0b'} trend={delta(effCurr, effPrev)} />
      <KpiCard label="Programmi eseguiti" value={pgmCurr} sub={`Sett. prec.: ${pgmPrev}`}
               color="#8b5cf6" trend={delta(pgmCurr, pgmPrev)} />
      {oeeCurr != null
        ? <KpiCard label="OEE medio" value={`${oeeCurr.toFixed(1)}%`}
            sub={oeePrev != null ? `Sett. prec.: ${oeePrev.toFixed(1)}%` : 'Prima settimana'}
            color={oeeCurr >= 75 ? '#22c55e' : oeeCurr >= 50 ? '#f59e0b' : '#ef4444'}
            trend={oeePrev != null ? delta(oeeCurr, oeePrev) : null} />
        : <KpiCard label="OEE" value="—" sub="Dati insufficienti" color="#94a3b8" />
      }
    </div>
  )
}

// ── Tab Utensili Potenziata ──────────────────────────────────────────────────
function TabUtensiliPro({ utensili }) {
  const [cicliUt,  setCicliUt]  = useState(null)
  const [sel,      setSel]      = useState(null)

  useEffect(() => {
    fetch('/api/report/cicli-utensile')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d) setCicliUt(d) })
      .catch(() => {})
  }, [])

  const totSec  = Object.values(utensili || {}).reduce((a,v) => a + v.sec, 0) || 1
  const entries = Object.entries(utensili || {}).sort((a,b) => b[1].sec - a[1].sec)

  const siFor = (alias) => cicliUt?.per_utensile?.[alias.toUpperCase()] || null

  const slopeColor = (s) => s==null?'#94a3b8':Math.abs(s)<1?'#22c55e':s>0?'#ef4444':'#059669'
  const slopeLabel = (s) => s==null?'—':Math.abs(s)<1?'→ stabile':s>0?`↗ +${Math.abs(s).toFixed(1)}s/ciclo`:`↘ ${Math.abs(s).toFixed(1)}s/ciclo`

  const selData = sel ? siFor(sel) : null

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:18 }}>
      <div style={{ display:'grid', gridTemplateColumns:'260px 1fr', gap:18 }}>
        <Card style={{ padding:'20px 24px' }}>
          <SectionTitle>Distribuzione ore</SectionTitle>
          <UtensiliDonut utensili={utensili} />
        </Card>

        <Card style={{ overflow:'auto' }}>
          <div style={{ padding:'12px 16px', borderBottom:'1px solid var(--border)',
            display:'flex', alignItems:'center', gap:10 }}>
            <div style={{ fontSize:11, fontWeight:700, letterSpacing:'0.08em', color:'var(--text-dim)',
              textTransform:'uppercase' }}>Ore · cicli · degradazione</div>
            {cicliUt && <span style={{ fontSize:11, color:'var(--text-dim)', marginLeft:'auto' }}>
              {cicliUt.n_utensili} utensili tracciati</span>}
          </div>
          <table style={{ width:'100%', borderCollapse:'collapse' }}>
            <thead>
              <tr style={{ background:'var(--bg-hover)' }}>
                {['#','Alias','Ore','%','Cicli','Slope degradaz.','Allarme'].map(h => (
                  <th key={h} style={{ padding:'8px 12px', textAlign:'left', fontSize:11,
                    fontWeight:700, color:'var(--text-dim)', letterSpacing:'0.04em',
                    borderBottom:'1px solid var(--border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {entries.map(([alias, info], i) => {
                const pct   = (info.sec / totSec * 100).toFixed(1)
                const si    = siFor(alias)
                const slope = si?.slope_medio ?? null
                const alarm = si?.degrado || false
                return (
                  <tr key={alias} onClick={() => setSel(sel===alias?null:alias)}
                    style={{ borderBottom:'1px solid var(--border)', cursor:'pointer',
                      background: sel===alias?'rgba(59,130,246,0.06)':alarm?'rgba(239,68,68,0.03)':'transparent',
                      transition:'background 0.15s' }}>
                    <td style={{ padding:'9px 12px', color:'var(--text-dim)', fontSize:12 }}>{i+1}</td>
                    <td style={{ padding:'9px 12px', fontFamily:'monospace', fontSize:12, fontWeight:700,
                      color:alarm?'#ef4444':'var(--text-primary)' }}>{alias}</td>
                    <td style={{ padding:'9px 12px', fontFamily:'monospace', fontSize:12,
                      color:'#f59e0b', fontWeight:700 }}>{info.ore}</td>
                    <td style={{ padding:'9px 12px' }}>
                      <div style={{ display:'flex', alignItems:'center', gap:5 }}>
                        <div style={{ width:60, height:5, background:'var(--border)', borderRadius:3, overflow:'hidden' }}>
                          <div style={{ width:`${pct}%`, height:'100%', background:'#3b82f6', borderRadius:3 }}/>
                        </div>
                        <span style={{ fontSize:11, color:'#3b82f6', fontWeight:700 }}>{pct}%</span>
                      </div>
                    </td>
                    <td style={{ padding:'9px 12px', fontSize:12, color:'var(--text-dim)', fontFamily:'monospace' }}>
                      {si?.n_cicli || '—'}
                    </td>
                    <td style={{ padding:'9px 12px' }}>
                      <span style={{ fontSize:12, fontWeight:700, color:slopeColor(slope) }}>
                        {slopeLabel(slope)}
                      </span>
                    </td>
                    <td style={{ padding:'9px 12px' }}>
                      {alarm ? (
                        <span style={{ fontSize:11, fontWeight:800, color:'#dc2626',
                          background:'rgba(239,68,68,0.1)', padding:'2px 8px', borderRadius:4 }}>⚠ DEGRADO</span>
                      ) : slope!==null ? (
                        <span style={{ fontSize:11, color:'#22c55e' }}>✓ ok</span>
                      ) : null}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>
      </div>

      {/* Dettaglio utensile selezionato */}
      {sel && selData && (
        <Card style={{ padding:'20px 24px' }}>
          <SectionTitle>{sel} — rendimento per programma</SectionTitle>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(3,1fr)', gap:10, marginBottom:16 }}>
            {[
              { label:'Cicli tracciati', value:selData.n_cicli, color:'#1D5FAD' },
              { label:'Programmi', value:selData.n_programmi, color:'#7C3AED' },
              { label:'Trend complessivo', value:slopeLabel(selData.slope_medio),
                color:slopeColor(selData.slope_medio) },
            ].map((k,i) => (
              <div key={i} style={{ padding:'10px 14px', background:'var(--bg-hover)',
                borderRadius:8, borderLeft:`3px solid ${k.color}` }}>
                <div style={{ fontSize:10, color:'var(--text-dim)', fontWeight:700,
                  textTransform:'uppercase', letterSpacing:'0.07em', marginBottom:3 }}>{k.label}</div>
                <div style={{ fontSize:20, fontWeight:800, color:k.color }}>{k.value}</div>
              </div>
            ))}
          </div>
          <table style={{ width:'100%', borderCollapse:'collapse', fontSize:12 }}>
            <thead>
              <tr style={{ background:'var(--bg-hover)' }}>
                {['Programma','Media ciclo','± Dev.std','N','Slope','Stato'].map(h => (
                  <th key={h} style={{ padding:'8px 12px', textAlign:'left', fontSize:11,
                    fontWeight:700, color:'var(--text-dim)', borderBottom:'1px solid var(--border)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {(selData.programmi||[]).sort((a,b)=>(b.slope||0)-(a.slope||0)).map(pgm => {
                const cv = pgm.media_sec>0 ? Math.round(pgm.std_sec/pgm.media_sec*100) : 0
                const sc = slopeColor(pgm.slope)
                return (
                  <tr key={pgm.filename}
                    style={{ borderBottom:'1px solid var(--border)',
                      background:pgm.slope>2?'rgba(239,68,68,0.03)':'transparent' }}>
                    <td style={{ padding:'8px 12px', fontFamily:'monospace', fontSize:12, fontWeight:600 }}>
                      {pgm.filename.replace('.MPF','')}
                    </td>
                    <td style={{ padding:'8px 12px', fontFamily:'monospace', fontSize:12, color:'#1D5FAD', fontWeight:700 }}>
                      {fmt(pgm.media_sec)}
                    </td>
                    <td style={{ padding:'8px 12px', fontSize:12, color:'var(--text-dim)', fontFamily:'monospace' }}>
                      ±{fmt(pgm.std_sec)}
                      {cv>0&&<span style={{ marginLeft:6, fontSize:10, fontWeight:700,
                        color:cv<10?'#22c55e':cv<20?'#f59e0b':'#ef4444' }}>CV{cv}%</span>}
                    </td>
                    <td style={{ padding:'8px 12px', fontSize:12, color:'var(--text-dim)', fontFamily:'monospace' }}>{pgm.n}</td>
                    <td style={{ padding:'8px 12px', fontSize:12, fontWeight:700, color:sc }}>
                      {slopeLabel(pgm.slope)}
                    </td>
                    <td style={{ padding:'8px 12px' }}>
                      {pgm.slope>2
                        ? <span style={{ fontSize:11, fontWeight:700, color:'#dc2626' }}>⚠ monitorare</span>
                        : pgm.n>=3
                          ? <span style={{ fontSize:11, color:'#22c55e' }}>✓</span>
                          : <span style={{ fontSize:11, color:'var(--text-dim)' }}>n insuff.</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </Card>
      )}
      {sel && !selData && (
        <Card style={{ padding:20 }}>
          <div style={{ fontSize:12, color:'var(--text-dim)' }}>
            Nessun dato ciclo per <b>{sel}</b> — servono ≥3 esecuzioni tracciate.
          </div>
        </Card>
      )}
    </div>
  )
}

// ── Tab Perdite TPM ──────────────────────────────────────────────────────────
function TabPerdite({ rpt }) {
  const p = rpt?.perdite_tpm
  const oee = rpt?.oee
  if (!p) return <div style={{ color:'var(--text-dim)', fontSize:12, textAlign:'center', padding:40 }}>Dati non disponibili</div>

  const turno = oee?.ore_turno_sec || 28800
  const colori = {
    produzione_netta: '#22c55e',
    velocita_ridotta: '#f59e0b',
    microfermi:       '#ef4444',
    setup:            '#8b5cf6',
    guasti:           '#dc2626',
    libero:           '#94a3b8',
  }
  const voci = [
    { k: 'produzione_netta', label: 'Produzione netta', sec: p.produzione_netta_sec },
    { k: 'velocita_ridotta', label: 'Velocità ridotta (override <90%)', sec: p.velocita_ridotta_sec },
    { k: 'microfermi',       label: 'Microfermi inter-programma', sec: p.microfermi_sec },
    { k: 'setup',            label: 'Setup / cambio pallet', sec: p.setup_sec },
    { k: 'guasti',           label: 'Fermi anomali (reset)', sec: p.guasti_sec },
    { k: 'libero',           label: 'Tempo non programmato', sec: p.libero_sec },
  ].filter(v => v.sec > 0)
  const totale = voci.reduce((a, v) => a + v.sec, 0) || 1

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:18 }}>

      {/* Waterfall OEE */}
      <Card style={{ padding:'20px 24px' }}>
        <SectionTitle>Waterfall OEE — decomposizione perdite</SectionTitle>
        <div style={{ display:'flex', alignItems:'flex-end', gap:8, height:140, marginBottom:12 }}>
          {[
            { label:'Turno',       val:100,                         col:'#1D5FAD' },
            { label:'Disponib.',   val:oee?.disponibilita||0,       col:'#0891B2' },
            { label:'Performance', val:oee?.performance||0,         col:'#7C3AED' },
            { label:'Qualità',     val:oee?.qualita||0,             col:'#059669' },
            { label:'OEE',         val:oee?.valore||0,              col: (oee?.valore||0)>=75?'#22c55e':(oee?.valore||0)>=50?'#f59e0b':'#ef4444', bold:true },
          ].map((b, i) => (
            <div key={i} style={{ flex:1, display:'flex', flexDirection:'column', alignItems:'center', gap:4 }}>
              <div style={{ fontSize:13, fontWeight:700, color: b.col, fontVariantNumeric:'tabular-nums' }}>
                {b.val.toFixed(1)}%
              </div>
              <div style={{ width:'100%', borderRadius:'4px 4px 0 0',
                height: Math.max(8, b.val * 1.2),
                background: b.col, opacity: b.bold ? 1 : 0.8,
                border: b.bold ? `2px solid ${b.col}` : 'none',
                transition: 'height 0.4s' }}/>
              <div style={{ fontSize:10, color:'var(--text-dim)', textAlign:'center', lineHeight:1.2 }}>{b.label}</div>
            </div>
          ))}
        </div>
        {/* Frecce perdita */}
        <div style={{ display:'flex', gap:8, flexWrap:'wrap', marginTop:8 }}>
          {[
            { label:`Indisponibilità`, val: 100 - (oee?.disponibilita||0), col:'#ef4444' },
            { label:`Perdita velocità`, val: (oee?.disponibilita||0) - (oee?.performance||oee?.disponibilita||0), col:'#f59e0b' },
            { label:`Difettosità`, val: 2, col:'#94a3b8' },
          ].filter(f => f.val > 0.1).map((f, i) => (
            <div key={i} style={{ display:'flex', alignItems:'center', gap:5,
              padding:'4px 10px', background:'var(--bg-hover)', borderRadius:6, fontSize:11 }}>
              <div style={{ width:8, height:8, borderRadius:2, background:f.col }}/>
              <span style={{ color:'var(--text-secondary)' }}>{f.label}:</span>
              <span style={{ fontWeight:700, color:f.col }}>{f.val.toFixed(1)}%</span>
            </div>
          ))}
        </div>
      </Card>

      {/* Torta perdite + KPI */}
      <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr', gap:18 }}>
        <Card style={{ padding:'20px 24px' }}>
          <SectionTitle>Distribuzione tempo turno</SectionTitle>
          <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
            {voci.map(v => {
              const pct = (v.sec / turno * 100).toFixed(1)
              return (
                <div key={v.k} style={{ display:'flex', alignItems:'center', gap:10 }}>
                  <div style={{ width:10, height:10, borderRadius:2, background:colori[v.k], flexShrink:0 }}/>
                  <div style={{ flex:1, fontSize:12, color:'var(--text-secondary)' }}>{v.label}</div>
                  <div style={{ width:60, height:6, background:'var(--border)', borderRadius:3, overflow:'hidden', flexShrink:0 }}>
                    <div style={{ width:`${Math.min(100,pct)}%`, height:'100%', background:colori[v.k], borderRadius:3 }}/>
                  </div>
                  <div style={{ width:44, fontSize:12, fontFamily:'monospace', fontWeight:700,
                    color:colori[v.k], textAlign:'right', flexShrink:0 }}>{pct}%</div>
                  <div style={{ width:52, fontSize:11, fontFamily:'monospace', color:'var(--text-dim)',
                    textAlign:'right', flexShrink:0 }}>{fmt(v.sec)}</div>
                </div>
              )
            })}
          </div>
        </Card>

        <Card style={{ padding:'20px 24px' }}>
          <SectionTitle>KPI processo</SectionTitle>
          <div style={{ display:'flex', flexDirection:'column', gap:12 }}>
            {[
              { label:'OEE', value:`${oee?.valore||'—'}%`,
                color:(oee?.valore||0)>=75?'#22c55e':(oee?.valore||0)>=50?'#f59e0b':'#ef4444',
                sub:`Target industriale stampi: 65-75%` },
              { label:'Setup medio / cambio pallet', value: p.n_setup > 0 ? fmt(p.media_setup_sec) : '—',
                color:'#8b5cf6', sub:`${p.n_setup} cambi rilevati oggi` },
              { label:'Fermi anomali', value: p.n_guasti,
                color: p.n_guasti > 2 ? '#ef4444' : p.n_guasti > 0 ? '#f59e0b' : '#22c55e',
                sub: p.n_guasti === 0 ? 'Nessun reset anomalo ✓' : 'Reset/spegnimenti imprevisti' },
              { label:'Tempo con override ridotto', value: p.velocita_ridotta_sec > 0 ? fmt(p.velocita_ridotta_sec) : '—',
                color: p.velocita_ridotta_sec > 1800 ? '#f59e0b' : '#22c55e',
                sub: p.velocita_ridotta_sec > 0
                  ? `${rpt.override_ridotto?.pct_tempo||0}% del tempo di taglio`
                  : 'Feed/mandrino sempre al 100%' },
            ].map((kpi, i) => (
              <div key={i} style={{ padding:'10px 14px', background:'var(--bg-hover)',
                borderRadius:8, borderLeft:`3px solid ${kpi.color}` }}>
                <div style={{ fontSize:10, fontWeight:700, color:'var(--text-dim)',
                  letterSpacing:'0.07em', textTransform:'uppercase', marginBottom:3 }}>{kpi.label}</div>
                <div style={{ fontSize:22, fontWeight:800, color:kpi.color, lineHeight:1 }}>{kpi.value}</div>
                <div style={{ fontSize:11, color:'var(--text-dim)', marginTop:3 }}>{kpi.sub}</div>
              </div>
            ))}
          </div>
        </Card>
      </div>
    </div>
  )
}

// ── Tab Cicli SPC ────────────────────────────────────────────────────────────
function TabCicli() {
  const [lista, setLista]       = useState([])
  const [sel,   setSel]         = useState(null)
  const [det,   setDet]         = useState(null)
  const [loading, setLoading]   = useState(false)

  useEffect(() => {
    fetch('/api/report/cicli-dettaglio')
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.programmi) setLista(d.programmi) })
      .catch(() => {})
  }, [])

  useEffect(() => {
    if (!sel) return
    setLoading(true)
    fetch(`/api/report/cicli-dettaglio?filename=${encodeURIComponent(sel)}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { setDet(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [sel])

  if (!lista.length) return (
    <div style={{ color:'var(--text-dim)', fontSize:12, textAlign:'center', padding:40 }}>
      Dati insufficienti — servono ≥5 esecuzioni per programma per l'analisi SPC
    </div>
  )

  const cvColor = (cv) => cv < 10 ? '#22c55e' : cv < 20 ? '#f59e0b' : '#ef4444'
  const slopeLabel = (s) => Math.abs(s) < 1 ? '→ stabile' : s > 0 ? '↗ degrado' : '↘ migliora'
  const slopeColor = (s) => Math.abs(s) < 1 ? '#94a3b8' : s > 0 ? '#ef4444' : '#22c55e'

  return (
    <div style={{ display:'grid', gridTemplateColumns:'340px 1fr', gap:18, height:'100%' }}>

      {/* Lista programmi */}
      <Card style={{ overflow:'auto', maxHeight:600 }}>
        <div style={{ padding:'14px 16px', borderBottom:'1px solid var(--border)' }}>
          <SectionTitle>Programmi analizzabili ({lista.length})</SectionTitle>
          <div style={{ fontSize:11, color:'var(--text-dim)' }}>
            Ordinati per instabilità (CV% decrescente)
          </div>
        </div>
        <div style={{ display:'flex', flexDirection:'column' }}>
          {lista.map((p, i) => (
            <div key={p.filename} onClick={() => setSel(p.filename)}
              style={{ padding:'10px 16px', cursor:'pointer', borderBottom:'1px solid var(--border)',
                background: sel === p.filename ? 'rgba(59,130,246,0.08)' : 'transparent',
                borderLeft: sel === p.filename ? '3px solid #3b82f6' : '3px solid transparent',
                transition:'all 0.15s' }}>
              <div style={{ fontSize:12, fontFamily:'monospace', fontWeight:700,
                color: sel===p.filename?'#3b82f6':'var(--text-primary)', marginBottom:4 }}>
                {p.filename.replace('.MPF','')}
              </div>
              <div style={{ display:'flex', alignItems:'center', gap:8 }}>
                <span style={{ fontSize:11, color:cvColor(p.cv_pct), fontWeight:700 }}>
                  CV {p.cv_pct}%
                </span>
                <span style={{ fontSize:11, color:'var(--text-dim)' }}>·</span>
                <span style={{ fontSize:11, color:'var(--text-dim)' }}>
                  media {fmt(p.media_sec)}
                </span>
                <span style={{ fontSize:11, color:'var(--text-dim)' }}>·</span>
                <span style={{ fontSize:11, color:slopeColor(p.slope) }}>
                  {slopeLabel(p.slope)}
                </span>
                <span style={{ marginLeft:'auto', fontSize:10, color:'var(--text-dim)' }}>
                  n={p.n}
                </span>
              </div>
            </div>
          ))}
        </div>
      </Card>

      {/* Dettaglio programma selezionato */}
      <div style={{ display:'flex', flexDirection:'column', gap:14 }}>
        {!sel && (
          <Card style={{ padding:30, display:'flex', alignItems:'center', justifyContent:'center' }}>
            <div style={{ fontSize:13, color:'var(--text-dim)' }}>← Seleziona un programma per vedere l'analisi</div>
          </Card>
        )}
        {sel && loading && (
          <Card style={{ padding:30, display:'flex', alignItems:'center', justifyContent:'center' }}>
            <div style={{ fontSize:13, color:'var(--text-dim)' }}>Caricamento...</div>
          </Card>
        )}
        {sel && det && !loading && (() => {
          const s = det.stats
          const campioni = det.run_chart || []
          const maxC = Math.max(...campioni, 1)
          const minC = Math.min(...campioni.filter(x=>x>0))
          const media = s.media || 0
          const std2  = s.std * 2

          return (<>
            {/* KPI statistici */}
            <Card style={{ padding:'16px 20px' }}>
              <SectionTitle>{det.filename?.replace('.MPF','')} — indici statistici</SectionTitle>
              <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:10 }}>
                {[
                  { label:'Media', value:fmt(s.media), color:'#1D5FAD' },
                  { label:'Dev. std (σ)', value:fmt(s.std), color:'#7C3AED' },
                  { label:'CV%', value:`${s.cv_pct}%`,
                    color:cvColor(s.cv_pct),
                    sub: s.cv_pct<10?'Stabile ✓':s.cv_pct<20?'Attenzione':'Instabile ⚠' },
                  { label:'P95 (worst case)', value:fmt(s.p95), color:'#f59e0b' },
                  { label:'Trend', value:slopeLabel(s.slope),
                    color:slopeColor(s.slope),
                    sub:`${Math.abs(s.slope).toFixed(1)}s/ciclo` },
                ].map((k,i) => (
                  <div key={i} style={{ padding:'10px 12px', background:'var(--bg-hover)',
                    borderRadius:8, textAlign:'center' }}>
                    <div style={{ fontSize:10, fontWeight:700, color:'var(--text-dim)',
                      textTransform:'uppercase', letterSpacing:'0.07em', marginBottom:4 }}>{k.label}</div>
                    <div style={{ fontSize:18, fontWeight:800, color:k.color, lineHeight:1 }}>{k.value}</div>
                    {k.sub && <div style={{ fontSize:10, color:k.color, marginTop:3 }}>{k.sub}</div>}
                  </div>
                ))}
              </div>
            </Card>

            {/* Run chart */}
            <Card style={{ padding:'16px 20px' }}>
              <SectionTitle>Run chart — ultimi {campioni.length} cicli</SectionTitle>
              <div style={{ position:'relative', height:120, marginTop:8 }}>
                {/* Bande ±2σ */}
                {std2 > 0 && (() => {
                  const range = maxC - minC || 1
                  const topBand  = Math.max(0, 100 - (media + std2 - minC) / range * 100)
                  const botBand  = Math.min(100, 100 - (media - std2 - minC) / range * 100)
                  const midLine  = 100 - (media - minC) / range * 100
                  return (<>
                    <div style={{ position:'absolute', left:0, right:0,
                      top:`${topBand}%`, height:`${botBand-topBand}%`,
                      background:'rgba(59,130,246,0.07)', borderTop:'1px dashed rgba(59,130,246,0.3)',
                      borderBottom:'1px dashed rgba(59,130,246,0.3)' }}/>
                    <div style={{ position:'absolute', left:0, right:0, top:`${midLine}%`,
                      borderTop:'1px solid rgba(59,130,246,0.5)' }}/>
                  </>)
                })()}
                {/* Punti */}
                <svg width="100%" height="100%" viewBox={`0 0 ${Math.max(campioni.length*1,1)} 100`}
                  preserveAspectRatio="none" style={{ position:'absolute', top:0, left:0 }}>
                  {campioni.length > 1 && (
                    <polyline
                      points={campioni.map((v,i)=>`${i*(100/(campioni.length-1))},${100-(v-minC)/(maxC-minC||1)*90}`).join(' ')}
                      fill="none" stroke="#1D5FAD" strokeWidth="2" vectorEffect="non-scaling-stroke"/>
                  )}
                  {campioni.map((v, i) => {
                    const isOut = std2 > 0 && Math.abs(v - media) > std2
                    const cx = campioni.length > 1 ? i * (100/(campioni.length-1)) : 50
                    const cy = 100 - (v - minC) / (maxC - minC || 1) * 90
                    return (
                      <circle key={i} cx={cx} cy={cy} r="2.5"
                        fill={isOut ? '#ef4444' : '#1D5FAD'}
                        vectorEffect="non-scaling-stroke">
                        <title>{fmt(v)}{isOut ? ' ⚠ fuori ±2σ' : ''}</title>
                      </circle>
                    )
                  })}
                </svg>
                {/* Etichette asse Y */}
                <div style={{ position:'absolute', right:-2, top:2, fontSize:9, color:'var(--text-dim)',
                  fontFamily:'monospace' }}>{fmt(maxC)}</div>
                <div style={{ position:'absolute', right:-2, bottom:2, fontSize:9, color:'var(--text-dim)',
                  fontFamily:'monospace' }}>{fmt(minC)}</div>
              </div>
              <div style={{ fontSize:10, color:'var(--text-dim)', marginTop:8, display:'flex', gap:16 }}>
                <span style={{ display:'flex', alignItems:'center', gap:4 }}>
                  <span style={{ display:'inline-block', width:20, height:2, background:'rgba(59,130,246,0.5)' }}/>
                  Media
                </span>
                <span style={{ display:'flex', alignItems:'center', gap:4 }}>
                  <span style={{ display:'inline-block', width:20, height:8,
                    background:'rgba(59,130,246,0.07)', border:'1px dashed rgba(59,130,246,0.3)' }}/>
                  ±2σ
                </span>
                <span style={{ display:'flex', alignItems:'center', gap:4 }}>
                  <span style={{ display:'inline-block', width:8, height:8, borderRadius:'50%', background:'#ef4444' }}/>
                  Outlier (&gt;±2σ)
                </span>
              </div>
            </Card>
          </>)
        })()}
      </div>
    </div>
  )
}

// ── Tab Takt (Teorico vs Reale) ──────────────────────────────────────────────
function TabTakt({ sessioni }) {
  const [cicliDb,  setCicliDb]  = useState({})
  const [progetti, setProgetti] = useState([])

  useEffect(() => {
    Promise.all([
      fetch('/api/report/tempi-ciclo').then(r=>r.ok?r.json():null),
      fetch('/api/progetti/').then(r=>r.ok?r.json():null),
    ]).then(([tc, pd]) => {
      if (tc?.cicli) setCicliDb(tc.cicli)
      if (pd?.projects) setProgetti(pd.projects.filter(p=>!p.archived))
    }).catch(() => {})
  }, [])

  // Costruisce tabella: per ogni programma eseguito oggi, incrocia con tempoStimato CAM
  const righe = (() => {
    const rows = []
    for (const s of (sessioni || [])) {
      for (const pgm of (s.programmi || [])) {
        if (!pgm.filename || !pgm.durata_sec) continue
        const fname = pgm.filename.toUpperCase()
        const ciclo = cicliDb[fname]
        if (!ciclo || ciclo.n < 2) continue

        // Cerca tempoStimato CAM nel progetto corrispondente
        let teorico = null
        for (const proj of progetti) {
          for (const step of (proj.steps || [])) {
            for (const task of (step.tasks || [])) {
              if (task.text?.toLowerCase() !== 'fresatura') continue
              for (const p of (task.programs || [])) {
                if ((p.filename||'').toUpperCase() === fname && p.tempoStimato) {
                  teorico = parseInt(p.tempoStimato) * 60  // tempoStimato è in minuti
                }
              }
            }
          }
        }

        const reale  = ciclo.media_sec
        const delta  = teorico ? Math.round((reale - teorico) / teorico * 100) : null
        rows.push({ filename: pgm.filename, teorico, reale, delta, n: ciclo.n,
                    cv: ciclo.std_sec ? Math.round(ciclo.std_sec / reale * 100) : 0,
                    progetto: s.progetto })
      }
    }
    // De-duplica per filename, mantieni il delta peggiore
    const map = {}
    for (const r of rows) {
      const k = r.filename.toUpperCase()
      if (!map[k] || (r.delta !== null && (map[k].delta === null || r.delta > map[k].delta)))
        map[k] = r
    }
    return Object.values(map).sort((a,b) => (b.delta||0) - (a.delta||0))
  })()

  if (!righe.length) return (
    <div style={{ color:'var(--text-dim)', fontSize:12, textAlign:'center', padding:40 }}>
      Nessun dato disponibile — servono sia dati di ciclo reale che tempi CAM nei progetti
    </div>
  )

  const hasTeorico = righe.some(r => r.teorico)

  return (
    <Card style={{ overflow:'auto' }}>
      <div style={{ padding:'16px 20px', borderBottom:'1px solid var(--border)' }}>
        <SectionTitle>Takt time — teorico CAM vs reale macchina</SectionTitle>
        {!hasTeorico && (
          <div style={{ fontSize:11, color:'#f59e0b', marginTop:4 }}>
            ⚠ Nessun tempoStimato trovato nei progetti — inserire i tempi CAM per il confronto completo
          </div>
        )}
      </div>
      <table style={{ width:'100%', borderCollapse:'collapse' }}>
        <thead>
          <tr style={{ background:'var(--bg-hover)' }}>
            {['Programma','Commessa','Teorico (CAM)','Reale (media)','Delta %','CV%','Stabilità'].map(h => (
              <th key={h} style={{ padding:'9px 14px', textAlign:'left', fontSize:11,
                fontWeight:700, color:'var(--text-dim)', letterSpacing:'0.05em',
                borderBottom:'1px solid var(--border)' }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {righe.map((r, i) => {
            const deltaColor = r.delta === null ? 'var(--text-dim)'
              : r.delta > 20 ? '#ef4444' : r.delta > 5 ? '#f59e0b' : '#22c55e'
            const cvColor2 = r.cv < 10 ? '#22c55e' : r.cv < 20 ? '#f59e0b' : '#ef4444'
            return (
              <tr key={r.filename} style={{ borderBottom:'1px solid var(--border)',
                background: i%2===0 ? 'transparent' : 'var(--bg-hover)',
                ...(r.delta > 20 ? { background:'rgba(239,68,68,0.04)' } : {}) }}>
                <td style={{ padding:'9px 14px', fontFamily:'monospace', fontSize:12, fontWeight:700 }}>
                  {r.filename.replace('.MPF','')}
                </td>
                <td style={{ padding:'9px 14px', fontSize:11, color:'var(--text-dim)' }}>
                  {r.progetto || '—'}
                </td>
                <td style={{ padding:'9px 14px', fontFamily:'monospace', fontSize:12,
                  color: r.teorico ? 'var(--text-secondary)' : 'var(--text-dim)' }}>
                  {r.teorico ? fmt(r.teorico) : '—'}
                </td>
                <td style={{ padding:'9px 14px', fontFamily:'monospace', fontSize:12,
                  fontWeight:700, color:'#1D5FAD' }}>
                  {fmt(r.reale)}
                  <span style={{ fontSize:10, color:'var(--text-dim)', fontWeight:400,
                    marginLeft:5 }}>n={r.n}</span>
                </td>
                <td style={{ padding:'9px 14px' }}>
                  {r.delta !== null ? (
                    <span style={{ fontSize:13, fontWeight:800, color:deltaColor }}>
                      {r.delta > 0 ? '+' : ''}{r.delta}%
                    </span>
                  ) : <span style={{ color:'var(--text-dim)', fontSize:12 }}>—</span>}
                </td>
                <td style={{ padding:'9px 14px' }}>
                  <span style={{ fontSize:12, fontWeight:700, color:cvColor2 }}>{r.cv}%</span>
                </td>
                <td style={{ padding:'9px 14px', fontSize:12, color: r.cv<10?'#22c55e':r.cv<20?'#f59e0b':'#ef4444' }}>
                  {r.cv < 10 ? '● Stabile' : r.cv < 20 ? '◐ Variabile' : '○ Instabile'}
                </td>
              </tr>
            )
          })}
        </tbody>
      </table>
    </Card>
  )
}



export default function Report() {
  const today = new Date().toISOString().slice(0,10)
  const [data,    setData]    = useState(today)
  const [rpt,     setRpt]     = useState(null)
  const [storico, setStorico] = useState([])
  const [loading, setLoading] = useState(false)
  const [tab,     setTab]     = useState('overview')

  const abortRef = useRef(null)

  const carica = useCallback(async () => {
    // Cancella fetch precedente se ancora in volo
    if (abortRef.current) abortRef.current.abort()
    abortRef.current = new AbortController()
    const sig = abortRef.current.signal
    setLoading(true)
    try {
      const [r1, r2] = await Promise.all([
        fetch(API(`/giornaliero?data=${data}`), {signal:sig}).then(r => r.json()),
        fetch(API(`/storico?giorni=14`), {signal:sig}).then(r => r.json()),
      ])
      if (sig.aborted) return
      setRpt(r1)
      setStorico(r2)
    } catch(e) {
      if (e.name !== 'AbortError') console.warn('[Report] carica error:', e.message)
    }
    finally { if (!sig.aborted) setLoading(false) }
  }, [data])

  useEffect(() => { carica() }, [carica])
  useEffect(() => {
    // Ricarica solo se ci sono completamenti — non ad ogni tick del poller
    const onUpdate = (e) => {
      const d = e.detail || {}
      if (d.completato > 0 || d.pallet > 0) carica()
    }
    window.addEventListener('dmgdesk:stati-aggiornati', onUpdate)
    return () => window.removeEventListener('dmgdesk:stati-aggiornati', onUpdate)
  }, [carica])

  const scaricaExcel = () => window.open(API(`/export-excel-download?data=${data}`), '_blank')

  const TABS = [
    { id:'overview',  label:'📊 Overview' },
    { id:'perdite',   label:'🎯 Perdite TPM' },
    { id:'cicli',     label:'📉 Cicli SPC' },
    { id:'takt',      label:'⏱ Takt' },
    { id:'programmi', label:'⚙ Programmi' },
    { id:'fermi',     label:'⏸ Fermi' },
    { id:'utensili',  label:'🔧 Utensili' },
    { id:'confronto', label:'📈 Settimana' },
  ]

  return (
    <div style={{ padding:'20px 28px', height:'100%', overflowY:'auto', boxSizing:'border-box' }}>

      {/* Header */}
      <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:20, flexWrap:'wrap' }}>
        <div style={{ fontSize:22, fontWeight:800, color:'var(--text-primary)' }}>Analisi Lavorazioni</div>
        <input type="date" value={data} onChange={e => setData(e.target.value)}
          style={{ padding:'6px 12px', borderRadius:6, border:'1px solid var(--border)',
                   background:'var(--bg-card)', color:'var(--text-primary)', fontSize:13 }} />
        <button onClick={carica}
          style={{ padding:'6px 14px', borderRadius:6, fontSize:13, fontWeight:600,
                   background:'var(--bg-hover)', border:'1px solid var(--border)',
                   color:'var(--text-secondary)', cursor:'pointer' }}>↺ Aggiorna</button>
        {loading && <span style={{ fontSize:12, color:'var(--text-dim)' }}>Caricamento...</span>}
        <button onClick={scaricaExcel}
          style={{ padding:'6px 14px', borderRadius:6, fontSize:13, fontWeight:700,
                   background:'rgba(34,197,94,0.12)', border:'1px solid rgba(34,197,94,0.3)',
                   color:'#22c55e', cursor:'pointer', marginLeft:'auto' }}>↓ Excel</button>
      </div>

      {/* Storico 14gg */}
      <Card style={{ padding:'18px 22px', marginBottom:18 }}>
        <SectionTitle>Ultimi 14 giorni — clicca per cambiare data</SectionTitle>
        <StoricoBars storico={storico} selectedData={data} onSelect={setData} />
      </Card>

      {/* KPI giornalieri */}
      {rpt && (
        <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)', gap:14, marginBottom:18 }}>
          <KpiCard label="Ore lavorate"  value={rpt.ore_lavorate}  color="#22c55e" />
          <KpiCard label="Tempo fermo"   value={rpt.tempo_fermo}   color="#f59e0b" />
          <KpiCard label="Efficienza"    value={`${rpt.efficienza_pct}%`}
                   color={rpt.efficienza_pct > 70 ? '#22c55e' : rpt.efficienza_pct > 40 ? '#f59e0b' : '#ef4444'} />
          <KpiCard label="Programmi"     value={rpt.n_programmi}   color="#3b82f6" />
          {/* OEE — se disponibile, sostituisce Sessioni */}
          {rpt.oee
            ? <KpiCard label="OEE"
                value={`${rpt.oee.valore}%`}
                color={rpt.oee.valore >= 75 ? '#22c55e' : rpt.oee.valore >= 50 ? '#f59e0b' : '#ef4444'}
                sub={`D:${rpt.oee.disponibilita}% P:${rpt.oee.performance}%`} />
            : <KpiCard label="Sessioni" value={rpt.n_sessioni} color="#8b5cf6" />
          }
        </div>
      )}

      {/* Banner override ridotto se presente */}
      {rpt?.override_ridotto?.sec_totale > 0 && (
        <div style={{ display:'flex', alignItems:'center', gap:12, marginBottom:14,
          padding:'9px 16px', borderRadius:8, background:'#fffbeb', border:'1px solid #f59e0b' }}>
          <span style={{ fontSize:11, fontWeight:800, color:'#92400e',
            background:'#fef3c7', padding:'2px 8px', borderRadius:5 }}>OVERRIDE RIDOTTO</span>
          <span style={{ fontSize:13, color:'#92400e' }}>
            <b>{rpt.override_ridotto.durata}</b> con feed/mandrino &lt; 90%
            {rpt.override_ridotto.min_valore != null &&
              ` · minimo rilevato: ${rpt.override_ridotto.min_valore}%`}
          </span>
          <span style={{ fontSize:11, color:'#a16207', marginLeft:'auto' }}>
            {rpt.override_ridotto.pct_tempo}% del tempo di lavorazione
          </span>
        </div>
      )}

      {!rpt && !loading && (
        <div style={{ color:'var(--text-dim)', textAlign:'center', padding:'40px 0' }}>
          Nessun dato per {data}
        </div>
      )}

      {rpt && (<>
        {/* Tab bar */}
        <div style={{ display:'flex', gap:4, marginBottom:18, borderBottom:'1px solid var(--border)' }}>
          {TABS.map(t => (
            <button key={t.id} onClick={() => setTab(t.id)}
              style={{ padding:'10px 18px', fontSize:13, fontWeight:600, border:'none', cursor:'pointer',
                       borderBottom: tab===t.id ? '2px solid #3b82f6' : '2px solid transparent',
                       background:'transparent', color: tab===t.id ? '#3b82f6' : 'var(--text-dim)' }}>
              {t.label}
            </button>
          ))}
        </div>

        {/* OVERVIEW */}
        {tab === 'overview' && (
          <div style={{ display:'grid', gridTemplateColumns:'1fr 1fr 1fr', gap:18 }}>
            <Card style={{ padding:'20px 24px' }}>
              <SectionTitle>Timeline giornaliera (per ora)</SectionTitle>
              <TimelineGiornaliera sessioni={rpt.sessioni} />
            </Card>
            <Card style={{ padding:'20px 24px' }}>
              <SectionTitle>Commesse lavorate</SectionTitle>
              {Object.entries(rpt.progetti).length === 0
                ? <div style={{ color:'var(--text-dim)', fontSize:12 }}>Nessun progetto</div>
                : (
                <div style={{ display:'flex', flexDirection:'column', gap:8 }}>
                  {Object.entries(rpt.progetti).map(([nome, info]) => {
                    const tot = Object.values(rpt.progetti).reduce((a,v)=>a+(v.durata_sec||0),0) || 1
                    const pct = (info.durata_sec / tot * 100).toFixed(0)
                    const color = colorForProject(nome)
                    return (
                      <div key={nome}>
                        <div style={{ display:'flex', justifyContent:'space-between', alignItems:'baseline', marginBottom:3 }}>
                          <span style={{ fontSize:14, fontWeight:700, fontFamily:'monospace', color }}>{nome}</span>
                          <span style={{ fontSize:12, color:'var(--text-dim)' }}>{fmt(info.durata_sec)} · {info.n_programmi} pgm</span>
                        </div>
                        <div style={{ height:8, background:'var(--bg-hover)', borderRadius:4, overflow:'hidden' }}>
                          <div style={{ width:`${pct}%`, height:'100%', background:color, borderRadius:4, transition:'width 0.4s' }} />
                        </div>
                      </div>
                    )
                  })}
                </div>
              )}
            </Card>
            <Card style={{ padding:'20px 24px' }}>
              <SectionTitle>Utilizzo utensili</SectionTitle>
              <UtensiliDonut utensili={rpt.utensili} />
            </Card>
            <Card style={{ padding:'20px 24px', gridColumn:'1 / -1' }}>
              <SectionTitle>Principali fermi macchina</SectionTitle>
              {(() => {
                const fermi = (rpt.sessioni || []).flatMap(s => {
                  const gaps = []
                  for (let i = 1; i < (s.programmi||[]).length; i++) {
                    const prev = s.programmi[i-1], curr = s.programmi[i]
                    if (!prev.fine || !curr.inizio) continue
                    const gap = Math.round((new Date(curr.inizio) - new Date(prev.fine)) / 1000)
                    if (gap < 30) continue
                    gaps.push({ prog: s.progetto, inizio: prev.fine, gap })
                  }
                  return gaps
                }).sort((a,b) => b.gap - a.gap).slice(0,8)
                if (!fermi.length) return <div style={{ color:'var(--text-dim)', fontSize:13 }}>Nessun fermo rilevato oggi</div>
                const maxGap = fermi[0].gap
                return (
                  <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill,minmax(300px,1fr))', gap:10 }}>
                    {fermi.map((f, i) => (
                      <div key={i} style={{ display:'flex', alignItems:'center', gap:10 }}>
                        <div style={{ width:64, fontSize:13, fontFamily:'monospace', fontWeight:700,
                                      color: f.gap > 1800 ? '#ef4444' : '#f59e0b', flexShrink:0 }}>{fmt(f.gap)}</div>
                        <div style={{ flex:1, height:14, background:'var(--bg-hover)', borderRadius:3 }}>
                          <div style={{ width:`${(f.gap/maxGap*100).toFixed(0)}%`, height:'100%',
                                        background: f.gap > 1800 ? '#ef444488' : '#f59e0b88', borderRadius:3 }} />
                        </div>
                        <div style={{ fontSize:12, color:'var(--text-dim)', width:48, textAlign:'right', flexShrink:0 }}>
                          {fmtDate(f.inizio).slice(11)}
                        </div>
                      </div>
                    ))}
                  </div>
                )
              })()}
            </Card>
          </div>
        )}

        {/* PERDITE TPM */}
        {tab === 'perdite' && <TabPerdite rpt={rpt} />}

        {/* CICLI SPC */}
        {tab === 'cicli' && <TabCicli />}

        {/* TAKT */}
        {tab === 'takt' && <TabTakt sessioni={rpt?.sessioni} />}

        {/* PROGRAMMI */}
        {tab === 'programmi' && (
          <Card style={{ padding:'20px 24px' }}>
            <SectionTitle>Durata programmi — top 20</SectionTitle>
            <ProgrammiChart sessioni={rpt.sessioni} />
          </Card>
        )}

        {/* FERMI */}
        {tab === 'fermi' && (
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            <Card style={{ padding:'20px 24px' }}>
              <SectionTitle>Pattern fermi per ora del giorno</SectionTitle>
              <HeatmapFermi sessioni={rpt.sessioni} />
            </Card>
            <Card style={{ padding:'20px 24px', overflow:'auto' }}>
              <SectionTitle>Dettaglio fermi — {data}</SectionTitle>
              <TabellaFermi sessioni={rpt.sessioni} />
            </Card>
          </div>
        )}

        {/* UTENSILI */}
        {tab === 'utensili' && (
          <TabUtensiliPro utensili={rpt.utensili} />
        )}

        {/* CONFRONTO SETTIMANE */}
        {tab === 'confronto' && (
          <div style={{ display:'flex', flexDirection:'column', gap:16 }}>
            <ConfrontoSettimane storico={storico} />
            <Card style={{ padding:'20px 24px' }}>
              <SectionTitle>Efficienza e ore — ultimi 14 giorni</SectionTitle>
              <div style={{ display:'flex', flexDirection:'column', gap:4, marginTop:4 }}>
                {storico.map(g => {
                  const eff = g.efficienza_pct || 0
                  const effColor = eff > 70 ? '#22c55e' : eff > 40 ? '#f59e0b' : eff > 0 ? '#ef4444' : 'var(--border)'
                  return (
                    <div key={g.data} style={{ display:'flex', alignItems:'center', gap:10, cursor:'pointer', padding:'2px 0' }}
                         onClick={() => setData(g.data)}>
                      <div style={{ width:90, fontSize:12, flexShrink:0,
                                    color: g.data===data ? '#3b82f6' : 'var(--text-dim)',
                                    fontWeight: g.data===data ? 700 : 400 }}>
                        {fmtDay(g.data)}
                      </div>
                      <div style={{ flex:1, height:18, background:'var(--bg-hover)', borderRadius:4, overflow:'hidden' }}>
                        {eff > 0 && (
                          <div style={{ width:`${eff}%`, height:'100%', background:effColor, borderRadius:4,
                                        display:'flex', alignItems:'center', paddingLeft:6, transition:'width 0.3s' }}>
                            {eff > 15 && <span style={{ fontSize:10, fontWeight:700, color:'#fff' }}>{eff.toFixed(0)}%</span>}
                          </div>
                        )}
                      </div>
                      <div style={{ width:52, fontSize:12, fontFamily:'monospace', color:'var(--text-dim)',
                                    textAlign:'right', flexShrink:0 }}>
                        {fmtH(g.ore_lavorate_sec)}
                      </div>
                    </div>
                  )
                })}
              </div>
            </Card>
          </div>
        )}

      </>)}
    </div>
  )
}
