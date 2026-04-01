// AlertUtensili.jsx — Monitoraggio predittivo utensili + Notifiche
import { useState, useEffect } from 'react'

function fmtSec(s) {
  if (!s) return '—'
  const m = Math.floor(s/60), sec = s%60
  return m > 0 ? `${m}m ${sec}s` : `${sec}s`
}

function SlopeBar({ slope, max=10 }) {
  const pct = Math.min(Math.abs(slope)/max*100, 100)
  const color = slope > 5 ? '#dc2626' : slope > 2 ? '#d97706' : '#16a34a'
  return (
    <div style={{display:'flex', alignItems:'center', gap:8}}>
      <div style={{width:80, height:6, background:'#e2e8f0', borderRadius:3, overflow:'hidden'}}>
        <div style={{width:`${pct}%`, height:'100%', background:color, borderRadius:3}}/>
      </div>
      <span style={{fontSize:11, fontFamily:'var(--font-mono)', color,
        fontWeight:600, minWidth:60}}>
        {slope > 0 ? '+' : ''}{slope.toFixed(1)}s/ciclo
      </span>
    </div>
  )
}

function AlertCard({ item, tipo }) {
  const isAlta = item.severita === 'alta'
  const bgColor = tipo === 'alert'
    ? (isAlta ? '#fef2f2' : '#fffbeb')
    : '#f8fafc'
  const bdColor = tipo === 'alert'
    ? (isAlta ? '#fca5a5' : '#fcd34d')
    : '#e2e8f0'
  const labelColor = tipo === 'alert'
    ? (isAlta ? '#dc2626' : '#b45309')
    : '#64748b'

  return (
    <div style={{
      background: bgColor, border: `1px solid ${bdColor}`,
      borderRadius:8, padding:'12px 16px', marginBottom:8,
    }}>
      <div style={{display:'flex', justifyContent:'space-between', alignItems:'flex-start', gap:12}}>
        <div style={{flex:1}}>
          <div style={{display:'flex', alignItems:'center', gap:8, marginBottom:4}}>
            <span style={{fontSize:12, fontWeight:700, color:labelColor,
              fontFamily:'var(--font-mono)'}}>
              {item.utensile}
            </span>
            <span style={{fontSize:10, color:'#94a3b8'}}>→</span>
            <span style={{fontSize:11, color:'#475569', fontFamily:'var(--font-mono)'}}>
              {item.programma}
            </span>
            <span style={{
              fontSize:9, fontWeight:700, padding:'2px 6px', borderRadius:3,
              background: isAlta ? '#fca5a5' : tipo==='alert' ? '#fcd34d' : '#e2e8f0',
              color: labelColor,
            }}>
              {item.tipo?.toUpperCase()}
            </span>
          </div>
          <div style={{fontSize:12, color:'#475569'}}>{item.msg}</div>
        </div>
        <div style={{textAlign:'right', flexShrink:0}}>
          <div style={{fontSize:10, color:'#94a3b8', marginBottom:4}}>
            {item.n_cicli} cicli · media {fmtSec(item.media_sec)}
          </div>
          {item.slope !== undefined && <SlopeBar slope={item.slope}/>}
        </div>
      </div>
      {item.tipo === 'picco' && (
        <div style={{marginTop:8, fontSize:11, color:'#64748b'}}>
          Ultimo: <strong>{fmtSec(item.ultimo_sec)}</strong> |
          Media: {fmtSec(item.media_sec)} |
          Soglia: {fmtSec(item.soglia_sec)}
        </div>
      )}
    </div>
  )
}

// ── Pannello config notifiche ─────────────────────────────────────────────────
function PanelloNotifiche() {
  const [cfg, setCfg] = useState(null)
  const [saving, setSaving] = useState(false)
  const [testResult, setTestResult] = useState(null)

  useEffect(() => {
    fetch('/api/report/notifiche/config')
      .then(r => r.ok ? r.json() : null)
      .then(setCfg)
  }, [])

  const save = async () => {
    setSaving(true)
    await fetch('/api/report/notifiche/config', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify(cfg),
    })
    setSaving(false)
  }

  const test = async (tipo) => {
    setTestResult(null)
    const r = await fetch('/api/report/notifiche/test', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({tipo}),
    })
    const d = await r.json()
    setTestResult({tipo, ...d})
  }

  if (!cfg) return <div style={{color:'#94a3b8',fontSize:12}}>Caricamento...</div>

  const set = (sezione, campo, val) =>
    setCfg(prev => ({...prev, [sezione]: {...prev[sezione], [campo]: val}}))

  return (
    <div style={{display:'flex', flexDirection:'column', gap:16}}>

      {/* Webhook */}
      <div style={{background:'#fff', border:'1px solid #e2e8f0', borderRadius:10,
        padding:'16px 20px'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14}}>
          <label style={{display:'flex', alignItems:'center', gap:8, cursor:'pointer'}}>
            <input type="checkbox" checked={cfg.webhook?.attivo || false}
              onChange={e => set('webhook','attivo',e.target.checked)}/>
            <span style={{fontSize:13, fontWeight:600}}>Webhook</span>
          </label>
          <span style={{fontSize:11, color:'#94a3b8'}}>
            POST JSON a URL esterno (Teams, Slack, n8n, ecc.)
          </span>
        </div>
        <input
          placeholder="https://hooks.slack.com/..."
          value={cfg.webhook?.url || ''}
          onChange={e => set('webhook','url',e.target.value)}
          style={{width:'100%', padding:'8px 12px', border:'1px solid #e2e8f0',
            borderRadius:6, fontSize:12, fontFamily:'var(--font-mono)',
            boxSizing:'border-box', marginBottom:8}}
        />
        <button onClick={() => test('webhook')}
          style={{fontSize:11, padding:'5px 12px', borderRadius:5, cursor:'pointer',
            background:'#f1f5f9', border:'1px solid #e2e8f0', color:'#475569'}}>
          Test webhook
        </button>
      </div>

      {/* Email */}
      <div style={{background:'#fff', border:'1px solid #e2e8f0', borderRadius:10,
        padding:'16px 20px'}}>
        <div style={{display:'flex', alignItems:'center', gap:10, marginBottom:14}}>
          <label style={{display:'flex', alignItems:'center', gap:8, cursor:'pointer'}}>
            <input type="checkbox" checked={cfg.email?.attivo || false}
              onChange={e => set('email','attivo',e.target.checked)}/>
            <span style={{fontSize:13, fontWeight:600}}>Email SMTP</span>
          </label>
        </div>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:8, marginBottom:8}}>
          {[
            ['smtp_host','Server SMTP','smtp.gmail.com'],
            ['smtp_port','Porta','587'],
            ['mittente','Mittente','dmgdesk@vetimec.it'],
            ['password','Password','••••••••'],
          ].map(([k,l,ph]) => (
            <div key={k}>
              <div style={{fontSize:10, color:'#94a3b8', marginBottom:3}}>{l}</div>
              <input
                type={k==='password' ? 'password' : 'text'}
                placeholder={ph}
                value={cfg.email?.[k] || ''}
                onChange={e => set('email',k,e.target.value)}
                style={{width:'100%', padding:'6px 10px', border:'1px solid #e2e8f0',
                  borderRadius:5, fontSize:12, boxSizing:'border-box'}}
              />
            </div>
          ))}
        </div>
        <div style={{marginBottom:8}}>
          <div style={{fontSize:10, color:'#94a3b8', marginBottom:3}}>
            Destinatari (separati da virgola)
          </div>
          <input
            placeholder="mario@vetimec.it, luigi@vetimec.it"
            value={(cfg.email?.destinatari || []).join(', ')}
            onChange={e => set('email','destinatari',
              e.target.value.split(',').map(s=>s.trim()).filter(Boolean))}
            style={{width:'100%', padding:'6px 10px', border:'1px solid #e2e8f0',
              borderRadius:5, fontSize:12, boxSizing:'border-box'}}
          />
        </div>
        <button onClick={() => test('email')}
          style={{fontSize:11, padding:'5px 12px', borderRadius:5, cursor:'pointer',
            background:'#f1f5f9', border:'1px solid #e2e8f0', color:'#475569'}}>
          Test email
        </button>
      </div>

      {/* Soglie */}
      <div style={{background:'#fff', border:'1px solid #e2e8f0', borderRadius:10,
        padding:'16px 20px'}}>
        <div style={{fontSize:12, fontWeight:600, marginBottom:12}}>Soglie alert</div>
        <div style={{display:'grid', gridTemplateColumns:'1fr 1fr', gap:12}}>
          {[
            ['slope_alert','Slope degrado (sec/ciclo)','2.0'],
            ['cv_warning','CV% instabilità','20'],
            ['giorni_scadenza_warning','Giorni margine scadenza','3'],
          ].map(([k,l,ph]) => (
            <div key={k}>
              <div style={{fontSize:10, color:'#94a3b8', marginBottom:3}}>{l}</div>
              <input type="number" placeholder={ph}
                value={cfg.soglie?.[k] || ''}
                onChange={e => set('soglie',k,parseFloat(e.target.value)||0)}
                style={{width:'100%', padding:'6px 10px', border:'1px solid #e2e8f0',
                  borderRadius:5, fontSize:12, boxSizing:'border-box'}}
              />
            </div>
          ))}
        </div>
      </div>

      {/* Test result */}
      {testResult && (
        <div style={{
          padding:'10px 14px', borderRadius:6, fontSize:12,
          background: testResult.ok ? '#f0fdf4' : '#fef2f2',
          border: `1px solid ${testResult.ok ? '#86efac' : '#fca5a5'}`,
          color: testResult.ok ? '#15803d' : '#dc2626',
        }}>
          {testResult.ok
            ? `✓ Test ${testResult.tipo} inviato con successo`
            : `✗ Errore: ${testResult.errore}`}
        </div>
      )}

      <button onClick={save} disabled={saving}
        style={{padding:'10px 20px', borderRadius:6, fontSize:13, fontWeight:600,
          background:'#0d2d5e', color:'#fff', border:'none', cursor:'pointer',
          opacity: saving ? 0.6 : 1}}>
        {saving ? 'Salvataggio...' : 'Salva configurazione'}
      </button>
    </div>
  )
}

// ── Pagina principale ─────────────────────────────────────────────────────────
export default function AlertUtensili() {
  const [alerts, setAlerts] = useState(null)
  const [tab, setTab] = useState('alert')
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    fetch('/api/report/alert-utensili')
      .then(r => r.ok ? r.json() : null)
      .then(d => { setAlerts(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  return (
    <div style={{display:'flex', flexDirection:'column', height:'100%',
      background:'#eef2f7', overflow:'auto'}}>

      {/* Header */}
      <div style={{background:'#0d2d5e', color:'#fff', padding:'14px 24px',
        display:'flex', alignItems:'center', gap:12, flexShrink:0}}>
        <div style={{flex:1}}>
          <div style={{fontWeight:700, fontSize:15}}>Monitoraggio Utensili</div>
          <div style={{fontSize:11, color:'rgba(255,255,255,0.55)',
            fontFamily:'var(--font-mono)'}}>
            Degrado predittivo · Notifiche automatiche
          </div>
        </div>
        {alerts && (alerts.n_alert > 0) && (
          <div style={{background:'#dc2626', color:'#fff', fontSize:11,
            fontWeight:700, padding:'4px 10px', borderRadius:6}}>
            {alerts.n_alert} alert attivi
          </div>
        )}
      </div>

      {/* Tabs */}
      <div style={{display:'flex', gap:4, padding:'12px 24px 0', flexShrink:0}}>
        {[
          {id:'alert', label:`Alert (${alerts?.n_alert||0})`},
          {id:'warning', label:`Warning (${alerts?.n_warning||0})`},
          {id:'notifiche', label:'Notifiche'},
        ].map(t => (
          <button key={t.id} onClick={() => setTab(t.id)} style={{
            padding:'7px 16px', borderRadius:'8px 8px 0 0',
            border:'1px solid', borderColor: tab===t.id ? '#e2e8f0' : 'transparent',
            borderBottom: tab===t.id ? '1px solid #eef2f7' : '1px solid transparent',
            background: tab===t.id ? '#eef2f7' : 'transparent',
            color: tab===t.id ? '#0d2d5e' : '#94a3b8',
            fontWeight: tab===t.id ? 600 : 400,
            fontSize:13, cursor:'pointer',
          }}>{t.label}</button>
        ))}
      </div>

      {/* Corpo */}
      <div style={{flex:1, padding:'0 24px 20px',
        background:'#eef2f7', border:'1px solid #e2e8f0',
        margin:'0 24px', borderRadius:'0 8px 8px 8px',
        overflow:'auto'}}>

        {loading && (
          <div style={{padding:40, textAlign:'center', color:'#94a3b8', fontSize:13}}>
            Analisi utensili in corso...
          </div>
        )}

        {!loading && tab === 'alert' && (
          <div style={{paddingTop:16}}>
            {!alerts?.alert?.length ? (
              <div style={{padding:'40px 0', textAlign:'center'}}>
                <div style={{fontSize:24, marginBottom:8}}>✓</div>
                <div style={{fontSize:13, color:'#16a34a', fontWeight:600}}>
                  Nessun alert — tutti gli utensili nel range normale
                </div>
                <div style={{fontSize:11, color:'#94a3b8', marginTop:4}}>
                  {alerts?.totale_utensili_monitorati || 0} utensili monitorati
                </div>
              </div>
            ) : (
              alerts.alert.map((a, i) => (
                <AlertCard key={i} item={a} tipo="alert"/>
              ))
            )}
          </div>
        )}

        {!loading && tab === 'warning' && (
          <div style={{paddingTop:16}}>
            {!alerts?.warning?.length ? (
              <div style={{padding:'40px 0', textAlign:'center', color:'#94a3b8', fontSize:13}}>
                Nessun warning attivo
              </div>
            ) : (
              alerts.warning.map((a, i) => (
                <AlertCard key={i} item={a} tipo="warning"/>
              ))
            )}
          </div>
        )}

        {tab === 'notifiche' && (
          <div style={{paddingTop:16}}>
            <PanelloNotifiche/>
          </div>
        )}
      </div>
    </div>
  )
}
