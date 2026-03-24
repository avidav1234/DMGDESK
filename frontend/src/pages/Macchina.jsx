// pages/Macchina.jsx — V16: solo Sync TOA/TMA + Confronto MPF
import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'
import { Loader, SectionHeader } from '../components/UI'

function LifeBar({ pct }) {
  if (pct === null || pct === undefined)
    return <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>—</span>
  const c = Math.min(100, Math.max(0, pct))
  const color = c < 10 ? 'var(--red)' : c < 30 ? 'var(--amber)' : 'var(--green)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 44, height: 4, background: 'var(--border)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${c}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color }}>{Math.round(c)}%</span>
    </div>
  )
}

const COL = {
  ok:       { bg: 'rgba(22,163,74,0.08)',  border: 'rgba(22,163,74,0.25)',  text: 'var(--green)'  },
  missing:  { bg: 'rgba(255,68,85,0.10)',  border: 'rgba(255,68,85,0.30)',  text: 'var(--red)'    },
  disabled: { bg: 'rgba(255,179,0,0.10)',  border: 'rgba(255,179,0,0.30)',  text: 'var(--amber)'  },
  worn:     { bg: 'rgba(109,40,217,0.10)', border: 'rgba(109,40,217,0.30)', text: '#6d28d9' },
}

export default function Macchina() {
  const [tools, setTools]             = useState([])
  const [syncStatus, setSyncStatus]   = useState(null)
  const [setupPopup, setSetupPopup]   = useState(false)
  const [setupData,  setSetupData]    = useState(null)
  const [setupLoading, setSetupLoading] = useState(false)

  // ── Popup Analisi Setup (componente interno) ──────────────────────────────
  const SetupPopup = () => {
    if (!setupPopup || !setupData) return null
    const {non_utilizzati, da_montare, fin_vita} = setupData

    const Section = ({title, items, color: c, bg, renderItem}) => (
      items.length > 0 ? (
        <div style={{marginBottom:16}}>
          <div style={{fontSize:12,fontWeight:700,color:c,letterSpacing:'0.06em',marginBottom:8}}>{title}</div>
          <div style={{border:'1px solid #D8D5CC',borderRadius:8,overflow:'hidden'}}>
            {items.map((item,i) => (
              <div key={item.alias} style={{display:'flex',alignItems:'center',gap:10,
                padding:'7px 12px',background:i%2===0?'#FFFFFF':bg,
                borderBottom:i<items.length-1?'1px solid #D8D5CC':'none'}}>
                {renderItem(item)}
              </div>
            ))}
          </div>
        </div>
      ) : null
    )

    return (
      <div style={{position:'fixed',inset:0,background:'rgba(0,0,0,0.5)',
        display:'flex',alignItems:'center',justifyContent:'center',zIndex:500}}>
        <div style={{background:'#FFFFFF',borderRadius:14,
          width:580,maxWidth:'92vw',maxHeight:'85vh',
          display:'flex',flexDirection:'column',
          border:'1px solid #D8D5CC',boxShadow:'0 12px 48px rgba(0,0,0,0.2)'}}>
          <div style={{padding:'18px 24px',borderBottom:'1px solid #D8D5CC',
            display:'flex',alignItems:'center',gap:10}}>
            <span style={{fontSize:20}}>🔧</span>
            <div style={{flex:1}}>
              <div style={{fontSize:17,fontWeight:800,color:'#1A1814'}}>Analisi Setup Macchina</div>
              {setupData.sync_time && (
                <div style={{fontSize:11,color:'#9A978E',marginTop:2}}>
                  Ultimo sync: {new Date(setupData.sync_time).toLocaleString('it-IT')}
                </div>
              )}
            </div>
            <button onClick={()=>setSetupPopup(false)}
              style={{background:'none',border:'1px solid #D8D5CC',borderRadius:8,
                color:'#5A5750',fontSize:13,padding:'5px 12px',cursor:'pointer',fontWeight:600}}>
              Chiudi
            </button>
          </div>
          <div style={{flex:1,overflowY:'auto',padding:'20px 24px'}}>
            <Section title={`✗ MANCANTI / DA MONTARE — ${da_montare.length}`}
              items={da_montare} c='#C0392B' bg='#FDECEA'
              renderItem={item=><>
                <span style={{flex:1,fontSize:13,fontFamily:'monospace',fontWeight:700,color:'#1A1814'}}>{item.alias}</span>
                <span style={{fontSize:11,fontWeight:700,padding:'2px 8px',borderRadius:12,
                  color:item.provenienza==='mancante'?'#C0392B':item.provenienza==='scaffale'?'#1D5FAD':'#C2720A',
                  background:item.provenienza==='mancante'?'#FDECEA':item.provenienza==='scaffale'?'#dbeafe':'#FFF0DC'}}>
                  {item.provenienza==='scaffale'?'🏠 A scaffale':item.provenienza==='smontato'?'📦 Smontato':'✗ Non trovato'}
                </span>
              </>}
            />
            <Section title={`⚠ FINE VITA (<15%) — ${fin_vita.length}`}
              items={fin_vita} c='#B45309' bg='#FEF3C7'
              renderItem={item=><>
                <span style={{flex:1,fontSize:13,fontFamily:'monospace',fontWeight:700,color:'#1A1814'}}>{item.alias}</span>
                {item.magazine!=null&&<span style={{fontSize:11,color:'#5A5750',fontFamily:'monospace'}}>M{item.magazine}{item.position!=null?` P${item.position}`:''}</span>}
                <span style={{fontSize:12,fontWeight:800,color:'#C0392B'}}>{item.life_percent}%</span>
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
          </div>
          <div style={{padding:'12px 24px',borderTop:'1px solid #D8D5CC',
            display:'flex',gap:10,justifyContent:'flex-end',
            background:'#F5F4F0',borderRadius:'0 0 14px 14px'}}>
            <button onClick={()=>setSetupPopup(false)}
              style={{background:'#D4700A',border:'none',borderRadius:8,
                color:'#fff',fontWeight:700,fontSize:13,padding:'8px 20px',cursor:'pointer'}}>
              OK, ho capito
            </button>
          </div>
        </div>
      </div>
    )
  }

  const [loading, setLoading]         = useState(false)
  const [syncing, setSyncing]         = useState(false)
  const [syncMsg, setSyncMsg]         = useState(null)
  const [errorSync, setErrorSync]     = useState(null)
  const [searchSync, setSearchSync]   = useState('')
  const [checkFiles, setCheckFiles]   = useState([])
  const [checking, setChecking]       = useState(false)
  const [checkResult, setCheckResult] = useState(null)
  const [checkError, setCheckError]   = useState(null)
  const fileInputRef = useRef()

  useEffect(() => { loadSync() }, [])

  async function loadSync() {
    setLoading(true)
    try {
      const [t, s] = await Promise.all([api.getTools(), api.getToolsSyncStatus()])
      setTools(t); setSyncStatus(s)
    } catch (e) { setErrorSync(e.message) }
    finally { setLoading(false) }
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

  async function loadSetupAnalisi() {
    setSetupLoading(true)
    try {
      const r = await fetch('/api/progetti/analisi-setup/non-utilizzati')
      if (r.ok) {
        const d = await r.json()
        setSetupData(d)
        // Mostra popup solo se ci sono situazioni da gestire
        if (d.non_utilizzati.length > 0 || d.da_montare.length > 0 || d.fin_vita.length > 0) {
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

  const btn_small = {
    padding: '6px 14px', borderRadius: 5, fontSize: 12, cursor: 'pointer',
    background: 'var(--bg-hover)', border: '1px solid var(--border)',
    color: 'var(--text-secondary)', fontWeight: 500,
  }

  return (
    <>
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 12 }}>
      <SectionHeader title="In Macchina — V16"
        subtitle="Sync TOA/TMA  •  Confronto MPF  •  Tabella utensili" />

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

      {/* Tabella utensili */}
      {loading ? <Loader /> : tools.length === 0 ? null : (
        <div style={{ flex: 1, overflow: 'auto', background: 'var(--bg-surface)',
          borderRadius: 10, border: '1px solid var(--border)' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Pos', 'Nome utensile', 'Duplo', 'L (mm)', 'R (mm)', 'Vita %', 'Stato'].map(h => (
                  <th key={h} style={{ padding: '9px 14px', textAlign: 'left', fontSize: 11,
                    fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
                    fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em',
                    position: 'sticky', top: 0, background: 'var(--bg-surface)' }}>{h}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {filtered.map(t => {
                const fuoriMag = t.magazine == null
                const isDis    = !t.is_enabled || t.is_worn
                const isWorn   = t.life_percent !== null && t.life_percent < 10
                const rowBg    = fuoriMag ? 'rgba(0,0,0,0.02)' : isDis ? 'rgba(255,68,85,0.04)' : isWorn ? 'rgba(109,40,217,0.04)' : 'transparent'
                const posFmt = t.magazine != null && t.position != null
                  ? `M${t.magazine}·${String(t.position).padStart(3,'0')}` : '—'
                return (
                  <tr key={t.tool_id}
                    style={{ borderBottom: '1px solid var(--border)', background: rowBg }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = rowBg}>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 11,
                      color: 'var(--navy-accent)', opacity: 0.8 }}>{posFmt}</td>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 13,
                      color: isDis ? 'var(--text-dim)' : 'var(--text-primary)', fontWeight: 600 }}>{t.name}</td>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                      color: 'var(--text-dim)' }}>#{t.duplo}</td>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                      color: 'var(--text-secondary)' }}>{t.length?.toFixed(3)}</td>
                    <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                      color: 'var(--text-secondary)' }}>{t.radius?.toFixed(3)}</td>
                    <td style={{ padding: '8px 14px' }}><LifeBar pct={t.life_percent} /></td>
                    <td style={{ padding: '8px 14px' }}>
                      {fuoriMag
                        ? <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
                            background: 'rgba(0,0,0,0.05)', padding: '2px 7px', borderRadius: 3 }}>FUORI MAG.</span>
                        : isDis
                        ? <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--red)',
                            background: 'rgba(255,68,85,0.1)', padding: '2px 7px', borderRadius: 3 }}>DISAB.</span>
                        : isWorn
                        ? <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: '#6d28d9',
                            background: 'rgba(109,40,217,0.1)', padding: '2px 7px', borderRadius: 3 }}>VITA BASSA</span>
                        : <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--green)',
                            background: 'rgba(22,163,74,0.08)', padding: '2px 7px', borderRadius: 3 }}>OK</span>}
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
    <SetupPopup />
    </>
  )
}
