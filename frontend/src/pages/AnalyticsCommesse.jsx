// AnalyticsCommesse.jsx — OEE · Ratio CAM/Macchina · Stima fine lavori
import { useState, useEffect } from 'react'
import { useNavigate } from 'react-router-dom'

function fmtH(sec) {
  if (!sec) return '0h'
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}
function fmtDate(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}
function daysUntil(iso) {
  if (!iso) return null
  const today = new Date(); today.setHours(0,0,0,0)
  return Math.round((new Date(iso) - today) / 86400000)
}

// ── OEE Gauge ────────────────────────────────────────────────────────────────
function OeeGauge({ pct }) {
  const r = 42, cx = 56, cy = 56
  const circ = Math.PI * r
  const fill = (pct / 100) * circ
  const color = pct >= 75 ? '#16a34a' : pct >= 50 ? '#d97706' : '#dc2626'
  return (
    <svg width="112" height="80" viewBox="0 0 112 80">
      <path d={`M ${cx-r},${cy} A ${r},${r} 0 0,1 ${cx+r},${cy}`}
        fill="none" stroke="#e2e8f0" strokeWidth="10" strokeLinecap="round"/>
      <path d={`M ${cx-r},${cy} A ${r},${r} 0 0,1 ${cx+r},${cy}`}
        fill="none" stroke={color} strokeWidth="10" strokeLinecap="round"
        strokeDasharray={`${fill} ${circ}`}/>
      <text x={cx} y={cy-4} textAnchor="middle"
        style={{fontSize:18, fontWeight:700, fill:color, fontFamily:'var(--font-mono)'}}>
        {pct}%
      </text>
      <text x={cx} y={cy+14} textAnchor="middle"
        style={{fontSize:10, fill:'#94a3b8', fontFamily:'var(--font-mono)'}}>
        OEE
      </text>
    </svg>
  )
}

// ── OEE sparkline ─────────────────────────────────────────────────────────────
function OeeSparkline({ giorni }) {
  if (!giorni?.length) return null
  const w = 280, h = 48, pad = 4
  const max = Math.max(...giorni.map(g => g.oee_pct), 100)
  const pts = giorni.map((g, i) => {
    const x = pad + (i / Math.max(giorni.length - 1, 1)) * (w - pad*2)
    const y = h - pad - (g.oee_pct / max) * (h - pad*2)
    return `${x},${y}`
  }).join(' ')
  const last = giorni[giorni.length - 1]
  return (
    <div>
      <svg width={w} height={h} style={{display:'block'}}>
        <polyline points={pts} fill="none" stroke="#0d2d5e" strokeWidth="1.5"
          strokeLinejoin="round" strokeLinecap="round"/>
        {giorni.map((g, i) => {
          const x = pad + (i / Math.max(giorni.length - 1, 1)) * (w - pad*2)
          const y = h - pad - (g.oee_pct / max) * (h - pad*2)
          const c = g.oee_pct >= 75 ? '#16a34a' : g.oee_pct >= 50 ? '#d97706' : '#dc2626'
          return <circle key={i} cx={x} cy={y} r="3" fill={c}/>
        })}
      </svg>
      <div style={{display:'flex', justifyContent:'space-between', fontSize:10, color:'#94a3b8', marginTop:2}}>
        <span>{fmtDate(giorni[0]?.data)}</span>
        <span>{fmtDate(last?.data)}</span>
      </div>
    </div>
  )
}

// ── Ratio bar ────────────────────────────────────────────────────────────────
function RatioBar({ cam, mac }) {
  const tot = cam + mac
  if (!tot) return <div style={{fontSize:11,color:'#94a3b8'}}>nessun dato</div>
  const camPct = (cam / tot) * 100
  return (
    <div>
      <div style={{height:8, borderRadius:4, background:'#e2e8f0', overflow:'hidden', marginBottom:4}}>
        <div style={{height:'100%', width:`${camPct}%`, background:'#0f766e',
          borderRadius:4, transition:'width 0.4s'}}/>
      </div>
      <div style={{display:'flex', justifyContent:'space-between', fontSize:10, color:'#94a3b8'}}>
        <span>CAM {fmtH(cam)}</span>
        <span>Macchina {fmtH(mac)}</span>
      </div>
    </div>
  )
}

// ── Alert badge ───────────────────────────────────────────────────────────────
function AlertBadge({ alert }) {
  if (!alert) return null
  const isRitardo = alert.tipo === 'ritardo'
  return (
    <div style={{
      fontSize:10, fontWeight:700, padding:'3px 8px', borderRadius:4,
      background: isRitardo ? '#fef2f2' : '#fffbeb',
      color: isRitardo ? '#dc2626' : '#b45309',
      border: `1px solid ${isRitardo ? '#fca5a5' : '#fcd34d'}`,
      whiteSpace:'nowrap',
    }}>
      {isRitardo ? '⚠ ' : '⏰ '}{alert.msg}
    </div>
  )
}

// ── Riga progetto ─────────────────────────────────────────────────────────────
function RigaProgetto({ p, onClick }) {
  const days = daysUntil(p.scadenza)
  const scadColor = days === null ? '#94a3b8'
    : p.consegnato ? '#16a34a'
    : days < 0 ? '#dc2626'
    : days <= 3 ? '#dc2626'
    : days <= 7 ? '#d97706'
    : '#16a34a'

  return (
    <div onClick={onClick} style={{
      display:'grid', gridTemplateColumns:'180px 1fr 140px 100px 120px',
      gap:12, alignItems:'center',
      padding:'12px 16px',
      borderBottom:'1px solid #f1f5f9',
      cursor:'pointer',
      transition:'background 0.15s',
    }}
    onMouseEnter={e => e.currentTarget.style.background='#f8fafc'}
    onMouseLeave={e => e.currentTarget.style.background='transparent'}
    >
      {/* Nome progetto */}
      <div>
        <div style={{display:'flex', alignItems:'center', gap:6}}>
          <div style={{width:8, height:8, borderRadius:'50%', background:p.colore, flexShrink:0}}/>
          <span style={{fontSize:13, fontWeight:600, color:'#0f172a',
            fontFamily:'var(--font-mono)'}}>{p.nome}</span>
        </div>
        {p.alert && <div style={{marginTop:4}}><AlertBadge alert={p.alert}/></div>}
      </div>

      {/* Ratio CAM/Macchina */}
      <RatioBar cam={p.ore_cam_sec} mac={p.ore_macchina_sec}/>

      {/* Ratio numerico */}
      <div style={{textAlign:'center'}}>
        {p.ratio_cam_macchina ? (
          <div>
            <div style={{fontSize:15, fontWeight:700, color:'#0d2d5e',
              fontFamily:'var(--font-mono)'}}>
              1 : {p.ratio_cam_macchina.toFixed(1)}
            </div>
            <div style={{fontSize:10, color:'#94a3b8'}}>CAM : Macchina</div>
          </div>
        ) : (
          <span style={{fontSize:11, color:'#94a3b8'}}>—</span>
        )}
      </div>

      {/* Stima fine */}
      <div style={{textAlign:'center'}}>
        {p.data_fine_stimata ? (
          <div>
            <div style={{fontSize:12, fontWeight:600, color:'#475569'}}>
              {fmtDate(p.data_fine_stimata)}
            </div>
            <div style={{fontSize:10, color:'#94a3b8'}}>
              {p.giorni_rimanenti}gg rimanenti
            </div>
          </div>
        ) : (
          <span style={{fontSize:11, color:'#94a3b8'}}>—</span>
        )}
      </div>

      {/* Scadenza */}
      <div style={{textAlign:'center'}}>
        {p.consegnato ? (
          <span style={{fontSize:11, fontWeight:700, color:'#16a34a'}}>✓ Consegnato</span>
        ) : p.scadenza ? (
          <div>
            <div style={{fontSize:12, fontWeight:600, color:scadColor}}>
              {fmtDate(p.scadenza)}
            </div>
            <div style={{fontSize:10, color:scadColor}}>
              {days === null ? '' : days < 0 ? `${Math.abs(days)}gg scaduto` : `${days}gg`}
            </div>
          </div>
        ) : <span style={{fontSize:11, color:'#94a3b8'}}>—</span>}
      </div>
    </div>
  )
}

// ── Pagina principale ─────────────────────────────────────────────────────────
export default function AnalyticsCommesse() {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const navigate = useNavigate()

  useEffect(() => {
    fetch('/api/report/analytics-commesse')
      .then(r => r.ok ? r.json() : null)
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  if (loading) return (
    <div style={{display:'flex', alignItems:'center', justifyContent:'center',
      height:'100%', color:'#94a3b8', fontSize:13}}>
      Caricamento analytics...
    </div>
  )

  if (!data) return (
    <div style={{padding:24, color:'#dc2626', fontSize:13}}>
      Errore caricamento dati
    </div>
  )

  const { oee, progetti, n_alert } = data

  return (
    <div style={{display:'flex', flexDirection:'column', height:'100%',
      background:'#eef2f7', overflow:'auto'}}>

      {/* Header */}
      <div style={{background:'#0d2d5e', color:'#fff', padding:'14px 24px',
        display:'flex', alignItems:'center', gap:12, flexShrink:0}}>
        <div style={{flex:1}}>
          <div style={{fontWeight:700, fontSize:15}}>Analytics Commesse</div>
          <div style={{fontSize:11, color:'rgba(255,255,255,0.55)',
            fontFamily:'var(--font-mono)'}}>
            OEE · Ratio CAM/Macchina · Stima fine lavori
          </div>
        </div>
        {n_alert > 0 && (
          <div style={{background:'#dc2626', color:'#fff', fontSize:11,
            fontWeight:700, padding:'4px 10px', borderRadius:6}}>
            {n_alert} alert scadenza
          </div>
        )}
      </div>

      <div style={{padding:'16px 24px', flex:1}}>

        {/* OEE Card */}
        <div style={{background:'#fff', border:'1px solid #e2e8f0',
          borderRadius:12, padding:'20px 24px', marginBottom:16,
          display:'flex', gap:32, alignItems:'center', flexWrap:'wrap'}}>

          {oee.medio_pct !== null ? (
            <>
              <OeeGauge pct={oee.medio_pct}/>
              <div style={{flex:1, minWidth:200}}>
                <div style={{fontSize:11, color:'#94a3b8', marginBottom:8,
                  textTransform:'uppercase', letterSpacing:'0.06em', fontWeight:700}}>
                  OEE medio — ultimi {oee.n_giorni} giorni con lavorazioni
                </div>
                <OeeSparkline giorni={oee.giorni}/>
              </div>
              <div style={{display:'flex', flexDirection:'column', gap:8}}>
                {[
                  {label:'≥ 75%', color:'#16a34a', desc:'World class'},
                  {label:'50–74%', color:'#d97706', desc:'In miglioramento'},
                  {label:'< 50%', color:'#dc2626', desc:'Da analizzare'},
                ].map(t => (
                  <div key={t.label} style={{display:'flex', alignItems:'center', gap:8}}>
                    <div style={{width:10, height:10, borderRadius:2,
                      background:t.color, flexShrink:0}}/>
                    <span style={{fontSize:11, color:'#475569'}}>
                      <strong>{t.label}</strong> — {t.desc}
                    </span>
                  </div>
                ))}
              </div>
            </>
          ) : (
            <div style={{color:'#94a3b8', fontSize:13}}>
              Nessun dato OEE disponibile — il log lavorazioni è vuoto.
            </div>
          )}
        </div>

        {/* Tabella progetti */}
        <div style={{background:'#fff', border:'1px solid #e2e8f0', borderRadius:12,
          overflow:'hidden'}}>

          {/* Intestazione tabella */}
          <div style={{
            display:'grid', gridTemplateColumns:'180px 1fr 140px 100px 120px',
            gap:12, padding:'10px 16px',
            background:'#f8fafc', borderBottom:'1px solid #e2e8f0',
          }}>
            {['Commessa', 'Ripartizione ore', 'Ratio CAM:Mac', 'Fine stimata', 'Scadenza'].map(h => (
              <div key={h} style={{fontSize:10, fontWeight:700, color:'#94a3b8',
                textTransform:'uppercase', letterSpacing:'0.06em'}}>{h}</div>
            ))}
          </div>

          {progetti.length === 0 ? (
            <div style={{padding:'40px 24px', textAlign:'center',
              color:'#94a3b8', fontSize:13}}>
              Nessuna commessa con dati disponibili.
            </div>
          ) : (
            progetti.map(p => (
              <RigaProgetto
                key={p.id}
                p={p}
                onClick={() => navigate(`/rendiconto/${p.id}`)}
              />
            ))
          )}
        </div>

        {/* Footer info */}
        <div style={{padding:'12px 4px', fontSize:11, color:'#94a3b8',
          fontFamily:'var(--font-mono)'}}>
          Ratio CAM:Macchina = ore programmazione Cimatron : ore lavorazione CNC ·
          Stima fine = ore rimanenti / velocità media ultimi 7gg
        </div>
      </div>
    </div>
  )
}
