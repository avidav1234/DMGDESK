// pages/Macchina.jsx — In Macchina unificato: DB manuale + Sync TOA/TMA + Verifica MPF
import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'
import { Loader, EmptyState, ErrorBanner, SuccessBanner, StatCard, SectionHeader } from '../components/UI'

// ── Componenti interni Sync ──────────────────────────────────────────────────

function LifeBar({ pct }) {
  if (pct === null || pct === undefined)
    return <span style={{ color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', fontSize: 11 }}>—</span>
  const c = Math.min(100, Math.max(0, pct))
  const color = c < 10 ? 'var(--red)' : c < 30 ? 'var(--amber)' : 'var(--green)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 44, height: 4, background: 'var(--bg-base)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${c}%`, height: '100%', background: color, borderRadius: 2 }} />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color }}>{Math.round(c)}%</span>
    </div>
  )
}

const COL = {
  ok:       { bg: 'rgba(0,255,136,0.08)',  border: 'rgba(0,255,136,0.25)',  text: 'var(--green)'  },
  missing:  { bg: 'rgba(255,68,85,0.10)',  border: 'rgba(255,68,85,0.30)',  text: 'var(--red)'    },
  disabled: { bg: 'rgba(255,179,0,0.10)',  border: 'rgba(255,179,0,0.30)',  text: 'var(--amber)'  },
  worn:     { bg: 'rgba(168,85,247,0.10)', border: 'rgba(168,85,247,0.30)', text: 'var(--purple)' },
}

function CheckBadge({ label, color, count }) {
  if (!count) return null
  return (
    <span style={{
      display: 'inline-flex', alignItems: 'center', gap: 5,
      padding: '3px 10px', borderRadius: 4,
      background: COL[color].bg, border: `1px solid ${COL[color].border}`,
      fontSize: 12, fontFamily: 'var(--font-mono)', color: COL[color].text,
    }}>
      <b>{count}</b> {label}
    </span>
  )
}

// ── Pagina principale ────────────────────────────────────────────────────────

export default function Macchina() {
  const [vista, setVista] = useState('db') // 'db' | 'sync'

  // ── stato DB manuale ──
  const [utensili, setUtensili]     = useState([])
  const [loadingDb, setLoadingDb]   = useState(true)
  const [errorDb, setErrorDb]       = useState(null)
  const [success, setSuccess]       = useState(null)
  const [smontaPos, setSmontaPos]   = useState(null)
  const [noteSmonta, setNoteSmonta] = useState('')
  const [busy, setBusy]             = useState(false)
  const [searchDb, setSearchDb]     = useState('')

  // ── stato sync ──
  const [tools, setTools]           = useState([])
  const [syncStatus, setSyncStatus] = useState(null)
  const [loadingSync, setLoadingSync] = useState(false)
  const [syncing, setSyncing]       = useState(false)
  const [errorSync, setErrorSync]   = useState(null)
  const [syncMsg, setSyncMsg]       = useState(null)
  const [searchSync, setSearchSync] = useState('')

  // ── stato check MPF ──
  const [checkResult, setCheckResult] = useState(null)
  const [checking, setChecking]       = useState(false)
  const [checkError, setCheckError]   = useState(null)
  const [checkFile, setCheckFile]     = useState(null)
  const fileInputRef = useRef()

  // ── caricamento iniziale ──
  useEffect(() => { loadDb() }, [])
  useEffect(() => { if (vista === 'sync') loadSync() }, [vista])

  async function loadDb() {
    try { setLoadingDb(true); setErrorDb(null); setUtensili(await api.getMacchina()) }
    catch (e) { setErrorDb(e.message) }
    finally { setLoadingDb(false) }
  }

  async function loadSync() {
    setLoadingSync(true)
    try {
      const [t, s] = await Promise.all([api.getTools(), api.getToolsSyncStatus()])
      setTools(t); setSyncStatus(s)
    } catch (e) { setErrorSync(e.message) }
    finally { setLoadingSync(false) }
  }

  // ── smonta DB ──
  async function handleSmonta() {
    try {
      setBusy(true); setErrorDb(null)
      await api.smontaUtensile(smontaPos, noteSmonta)
      setSuccess(`Utensile smontato dalla posizione ${smontaPos}`)
      setSmontaPos(null); setNoteSmonta(''); loadDb()
    } catch (e) { setErrorDb(e.message) }
    finally { setBusy(false) }
  }

  // ── sync TOA/TMA ──
  async function handleSync() {
    setSyncing(true); setSyncMsg(null); setErrorSync(null)
    try {
      const r = await api.syncTools()
      setSyncMsg(`Sync completato — ${r.tool_count} utensili, ${r.positions_mapped} posizioni`)
      await loadSync()
    } catch (e) { setErrorSync(e.message) }
    finally { setSyncing(false) }
  }

  // ── check MPF ──
  async function handleCheckFile(file) {
    if (!file) return
    setCheckFile(file); setChecking(true); setCheckResult(null); setCheckError(null)
    try { setCheckResult(await api.checkToolsMpf(file)) }
    catch (e) { setCheckError(e.message) }
    finally { setChecking(false) }
  }

  // ── filtri ──
  const filteredDb   = utensili.filter(u =>
    u.alias.toLowerCase().includes(searchDb.toLowerCase()) ||
    String(u.posizione).includes(searchDb))

  const filteredSync = tools.filter(t =>
    !searchSync || t.name.toLowerCase().includes(searchSync.toLowerCase()))

  // ── render ───────────────────────────────────────────────────────────────
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>

      {/* Header */}
      <SectionHeader
        title="In Macchina"
        subtitle="Carosello CNC — DB manuale  •  Sync TOA/TMA  •  Verifica MPF"
      />

      {/* Selettore vista */}
      <div style={{ display: 'flex', gap: 0, borderRadius: 6, overflow: 'hidden',
                    border: '1px solid var(--border)', alignSelf: 'flex-start' }}>
        {[['db', '⚙ DB Manuale'], ['sync', '🗂 Sync Macchina']].map(([key, label]) => (
          <button key={key} onClick={() => setVista(key)} style={{
            padding: '8px 20px', fontSize: 13, fontWeight: 600, cursor: 'pointer',
            border: 'none', borderRight: key === 'db' ? '1px solid var(--border)' : 'none',
            background: vista === key ? 'var(--cyan-glow)' : 'var(--bg-card)',
            color: vista === key ? 'var(--cyan)' : 'var(--text-secondary)',
            transition: 'all var(--t-fast)',
          }}>{label}</button>
        ))}
      </div>

      {/* ════════════════════════════════════════════════════
          VISTA DB MANUALE
      ════════════════════════════════════════════════════ */}
      {vista === 'db' && (
        <>
          {/* Stats */}
          <div style={{ display: 'flex', gap: 12 }}>
            <StatCard label="In Carosello"    value={utensili.length} color="var(--cyan)" />
            <StatCard label="Frese Finitura"  value={utensili.filter(u => u.alias.startsWith('FF')).length} color="var(--green)" />
            <StatCard label="Posizioni Libere" value={120 - utensili.length} color="var(--text-secondary)" unit="/ 120" />
          </div>

          <ErrorBanner   message={errorDb} onClose={() => setErrorDb(null)} />
          <SuccessBanner message={success}  onClose={() => setSuccess(null)} />

          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: 12 }}>
            <input className="input" placeholder="Cerca per alias o posizione..."
              value={searchDb} onChange={e => setSearchDb(e.target.value)}
              style={{ maxWidth: 320 }} />
            <button className="btn btn-ghost" onClick={loadDb} style={{ fontSize: 12 }}>↻ Aggiorna</button>
          </div>

          <div className="card" style={{ flex: 1, overflow: 'auto' }}>
            {loadingDb ? <Loader /> : filteredDb.length === 0 ? (
              <EmptyState icon="⚙" title="Nessun utensile trovato"
                subtitle="Il carosello è vuoto o la ricerca non ha risultati" />
            ) : (
              <table className="table">
                <thead>
                  <tr>
                    <th>Pos.</th><th>Alias Utensile</th><th>Tipo</th><th>Stato</th>
                    <th style={{ textAlign: 'right' }}>Azioni</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredDb.map(u => (
                    <tr key={u.posizione}>
                      <td>
                        <span className="mono" style={{ color: 'var(--cyan)', fontWeight: 700, fontSize: 14 }}>
                          {String(u.posizione).padStart(3, '0')}
                        </span>
                      </td>
                      <td><span className="mono" style={{ fontSize: 13 }}>{u.alias}</span></td>
                      <td>
                        <span className={`badge ${
                          u.alias.startsWith('FF') ? 'badge-green' :
                          u.alias.startsWith('FS') ? 'badge-amber' : 'badge-cyan'}`}>
                          {u.alias.startsWith('FF') ? 'Finitura' :
                           u.alias.startsWith('FS') ? 'Sgrossatura' :
                           u.alias.startsWith('P')  ? 'Punta' : '—'}
                        </span>
                      </td>
                      <td><span className="badge badge-green">IN MACCHINA</span></td>
                      <td style={{ textAlign: 'right' }}>
                        <button className="btn btn-danger"
                          style={{ fontSize: 11, padding: '4px 10px' }}
                          onClick={() => setSmontaPos(u.posizione)}>
                          Smonta
                        </button>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          {/* Modal smonta */}
          {smontaPos && (
            <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)',
                          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
              <div className="card fade-in" style={{ padding: 24, width: 380, display: 'flex', flexDirection: 'column', gap: 16 }}>
                <h3 style={{ fontSize: 16, fontWeight: 700 }}>Smonta Utensile — Pos. {smontaPos}</h3>
                <p style={{ color: 'var(--text-secondary)', fontSize: 13 }}>
                  {utensili.find(u => u.posizione === smontaPos)?.alias}
                </p>
                <div>
                  <label style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 6 }}>
                    NOTE (opzionale)
                  </label>
                  <input className="input" placeholder="es. usura, cambio programma..."
                    value={noteSmonta} onChange={e => setNoteSmonta(e.target.value)} />
                </div>
                <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
                  <button className="btn btn-ghost" onClick={() => { setSmontaPos(null); setNoteSmonta('') }}>Annulla</button>
                  <button className="btn btn-danger" onClick={handleSmonta} disabled={busy}>
                    {busy ? 'Smontaggio...' : 'Conferma Smontaggio'}
                  </button>
                </div>
              </div>
            </div>
          )}
        </>
      )}

      {/* ════════════════════════════════════════════════════
          VISTA SYNC MACCHINA
      ════════════════════════════════════════════════════ */}
      {vista === 'sync' && (
        <>
          {/* Header sync */}
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 16 }}>
            <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
              {syncStatus?.last_sync
                ? `Ultimo sync: ${new Date(syncStatus.last_sync).toLocaleString('it-IT')} — ${syncStatus.tool_count} utensili`
                : 'Nessun sync effettuato'}
            </div>
            <button onClick={handleSync} disabled={syncing} style={{
              display: 'flex', alignItems: 'center', gap: 8,
              padding: '9px 18px', borderRadius: 6, cursor: syncing ? 'not-allowed' : 'pointer',
              background: 'var(--cyan-glow)', border: '1px solid rgba(0,212,255,0.35)',
              color: syncing ? 'var(--text-dim)' : 'var(--cyan)',
              fontSize: 13, fontWeight: 600, transition: 'all var(--t-fast)',
            }}>
              <span style={{ animation: syncing ? 'spin 1s linear infinite' : 'none' }}>⟳</span>
              {syncing ? 'Sincronizzazione…' : 'Sync da Macchina'}
            </button>
          </div>

          {/* Messaggi */}
          {syncMsg && (
            <div style={{ padding: '10px 14px', borderRadius: 6, fontSize: 13,
                          background: 'rgba(0,255,136,0.07)', border: '1px solid rgba(0,255,136,0.2)',
                          color: 'var(--green)' }}>
              ✓ {syncMsg}
            </div>
          )}
          {errorSync && (
            <div style={{ padding: '10px 14px', borderRadius: 6, fontSize: 13,
                          background: 'rgba(255,68,85,0.08)', border: '1px solid rgba(255,68,85,0.25)',
                          color: 'var(--red)' }}>
              ✕ {errorSync}
            </div>
          )}

          {/* Istruzioni primo sync */}
          {!syncStatus?.last_sync && (
            <div style={{ padding: '14px 16px', borderRadius: 8, fontSize: 13,
                          background: 'var(--bg-card)', border: '1px solid var(--border)',
                          color: 'var(--text-secondary)', lineHeight: 1.7 }}>
              <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>Come sincronizzare</div>
              <ol style={{ paddingLeft: 20 }}>
                <li>Sulla macchina: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>HMI → Servizi → Salva Attrezzaggio</span></li>
                <li>Navigare in <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>Z:\DMG_DMC_160U\</span> e salvare con nome <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>TOOL_SYNC</span></li>
                <li>Premere <strong>Sync da Macchina</strong> qui sopra</li>
              </ol>
            </div>
          )}

          {/* Check MPF */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)',
                        borderRadius: 10, padding: '14px 16px' }}>
            <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 10 }}>
              🔍 Verifica Programma MPF
            </div>
            <div
              onClick={() => fileInputRef.current?.click()}
              onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--cyan)' }}
              onDragLeave={e => { e.currentTarget.style.borderColor = 'var(--border-bright)' }}
              onDrop={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--border-bright)'; handleCheckFile(e.dataTransfer.files[0]) }}
              style={{ border: '2px dashed var(--border-bright)', borderRadius: 8, padding: '16px',
                       textAlign: 'center', cursor: 'pointer', transition: 'border-color var(--t-fast)' }}>
              <input ref={fileInputRef} type="file" accept=".mpf,.nc,.spf"
                style={{ display: 'none' }}
                onChange={e => handleCheckFile(e.target.files[0])} />
              <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
                {checkFile
                  ? <><span style={{ color: 'var(--cyan)', fontFamily: 'var(--font-mono)' }}>{checkFile.name}</span> — clicca per cambiare</>
                  : <>Trascina un file MPF o <span style={{ color: 'var(--cyan)' }}>clicca per scegliere</span></>}
              </div>
            </div>

            {checking && <div style={{ marginTop: 10, fontSize: 13, color: 'var(--text-dim)' }}>Analisi in corso…</div>}
            {checkError && (
              <div style={{ marginTop: 10, padding: '8px 12px', borderRadius: 6, fontSize: 13,
                            background: 'rgba(255,68,85,0.08)', border: '1px solid rgba(255,68,85,0.2)',
                            color: 'var(--red)' }}>✕ {checkError}</div>
            )}
            {checkResult && (
              <div style={{ marginTop: 12 }}>
                {/* Banner */}
                <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 10,
                              padding: '10px 14px', borderRadius: 6,
                              background: checkResult.can_run ? 'rgba(0,255,136,0.07)' : 'rgba(255,68,85,0.08)',
                              border: `1px solid ${checkResult.can_run ? 'rgba(0,255,136,0.2)' : 'rgba(255,68,85,0.25)'}` }}>
                  <span style={{ fontSize: 18 }}>{checkResult.can_run ? '✅' : '❌'}</span>
                  <div>
                    <div style={{ fontWeight: 700, fontSize: 13,
                                  color: checkResult.can_run ? 'var(--green)' : 'var(--red)' }}>
                      {checkResult.can_run ? 'Programma eseguibile' : 'Utensili mancanti o non disponibili'}
                    </div>
                    <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginTop: 2 }}>
                      {checkResult.total_required} utensili richiesti
                    </div>
                  </div>
                </div>
                {/* Badge */}
                <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 12 }}>
                  <CheckBadge label="OK"          color="ok"       count={checkResult.ok.length} />
                  <CheckBadge label="Mancanti"    color="missing"  count={checkResult.missing.length} />
                  <CheckBadge label="Disabilitati" color="disabled" count={checkResult.disabled.length} />
                  <CheckBadge label="Vita bassa"  color="worn"     count={checkResult.worn.length} />
                </div>
                {/* Liste */}
                {[
                  { key: 'missing',  label: '❌ Mancanti in macchina',    color: 'missing'  },
                  { key: 'disabled', label: '⚠️ Disabilitati / Esauriti', color: 'disabled' },
                  { key: 'worn',     label: '🟣 Vita residua < 10%',       color: 'worn'     },
                  { key: 'ok',       label: '✅ Disponibili',              color: 'ok'       },
                ].map(({ key, label, color }) => {
                  const list = checkResult[key]
                  if (!list?.length) return null
                  return (
                    <div key={key} style={{ marginBottom: 8 }}>
                      <div style={{ fontSize: 11, fontWeight: 600, color: COL[color].text,
                                    fontFamily: 'var(--font-mono)', marginBottom: 4,
                                    textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                        {label}
                      </div>
                      <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
                        {list.map(name => (
                          <span key={name} style={{ padding: '3px 9px', borderRadius: 3, fontSize: 12,
                                                    fontFamily: 'var(--font-mono)',
                                                    background: COL[color].bg,
                                                    border: `1px solid ${COL[color].border}`,
                                                    color: COL[color].text }}>
                            {name}
                          </span>
                        ))}
                      </div>
                    </div>
                  )
                })}
              </div>
            )}
          </div>

          {/* Barra ricerca e contatore */}
          {tools.length > 0 && (
            <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
              <input value={searchSync} onChange={e => setSearchSync(e.target.value)}
                placeholder="Cerca utensile…"
                style={{ flex: 1, maxWidth: 280, padding: '8px 12px', borderRadius: 6,
                         background: 'var(--bg-card)', border: '1px solid var(--border)',
                         color: 'var(--text-primary)', fontSize: 13, outline: 'none',
                         fontFamily: 'var(--font-mono)' }} />
              <span style={{ fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                {filteredSync.length} / {tools.length}
              </span>
            </div>
          )}

          {/* Tabella sync */}
          {loadingSync ? <Loader /> : tools.length === 0 ? null : (
            <div style={{ flex: 1, overflow: 'auto', background: 'var(--bg-card)',
                          borderRadius: 10, border: '1px solid var(--border)' }}>
              <table style={{ width: '100%', borderCollapse: 'collapse' }}>
                <thead>
                  <tr style={{ borderBottom: '1px solid var(--border)' }}>
                    {['Pos', 'Nome utensile', 'Duplo', 'L (mm)', 'R (mm)', 'Vita %', 'Stato'].map(h => (
                      <th key={h} style={{ padding: '10px 14px', textAlign: 'left', fontSize: 11,
                                           fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
                                           fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em',
                                           position: 'sticky', top: 0, background: 'var(--bg-card)' }}>
                        {h}
                      </th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {filteredSync.map(t => {
                    const isDisabled = !t.is_enabled || t.is_worn
                    const isWorn     = t.life_percent !== null && t.life_percent < 10
                    const rowBg      = isDisabled ? 'rgba(255,68,85,0.04)' :
                                       isWorn     ? 'rgba(168,85,247,0.04)' : 'transparent'
                    const posFmt = t.magazine != null && t.position != null
                      ? `M${t.magazine}·${String(t.position).padStart(3, '0')}`
                      : '—'
                    return (
                      <tr key={t.tool_id}
                        style={{ borderBottom: '1px solid var(--border)', background: rowBg }}
                        onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                        onMouseLeave={e => e.currentTarget.style.background = rowBg}>
                        <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 11,
                                     color: 'var(--cyan)', opacity: 0.8, whiteSpace: 'nowrap' }}>
                          {posFmt}
                        </td>
                        <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 13,
                                     color: isDisabled ? 'var(--text-dim)' : 'var(--text-primary)', fontWeight: 600 }}>
                          {t.name}
                        </td>
                        <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                                     color: 'var(--text-dim)' }}>#{t.duplo}</td>
                        <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                                     color: 'var(--text-secondary)' }}>{t.length?.toFixed(3)}</td>
                        <td style={{ padding: '8px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                                     color: 'var(--text-secondary)' }}>{t.radius?.toFixed(3)}</td>
                        <td style={{ padding: '8px 14px' }}><LifeBar pct={t.life_percent} /></td>
                        <td style={{ padding: '8px 14px' }}>
                          {isDisabled
                            ? <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--red)',
                                             background: 'rgba(255,68,85,0.1)', padding: '2px 7px', borderRadius: 3 }}>DISAB.</span>
                            : isWorn
                            ? <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--purple)',
                                             background: 'rgba(168,85,247,0.1)', padding: '2px 7px', borderRadius: 3 }}>VITA BASSA</span>
                            : <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--green)',
                                             background: 'rgba(0,255,136,0.08)', padding: '2px 7px', borderRadius: 3 }}>OK</span>
                          }
                        </td>
                      </tr>
                    )
                  })}
                </tbody>
              </table>
            </div>
          )}
        </>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
