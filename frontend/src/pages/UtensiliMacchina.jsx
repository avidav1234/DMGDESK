// pages/UtensiliMacchina.jsx
// Tabella utensili macchina con sync da TOA/TMA e check programmi MPF
import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'

// ── Costanti UI ──────────────────────────────────────────────────────────────
const COL = {
  ok:       { bg: 'rgba(0,255,136,0.08)', border: 'rgba(0,255,136,0.25)', text: 'var(--green)' },
  missing:  { bg: 'rgba(255,68,85,0.10)', border: 'rgba(255,68,85,0.30)', text: 'var(--red)' },
  disabled: { bg: 'rgba(255,179,0,0.10)', border: 'rgba(255,179,0,0.30)', text: 'var(--amber)' },
  worn:     { bg: 'rgba(168,85,247,0.10)', border: 'rgba(168,85,247,0.30)', text: 'var(--purple)' },
}

function StatusBadge({ label, color, count }) {
  if (!count) return null
  return (
    <div style={{
      display: 'inline-flex', alignItems: 'center', gap: 6,
      padding: '3px 10px', borderRadius: 4,
      background: COL[color].bg, border: `1px solid ${COL[color].border}`,
      fontSize: 12, fontFamily: 'var(--font-mono)', color: COL[color].text,
    }}>
      <span style={{ fontWeight: 700 }}>{count}</span> {label}
    </div>
  )
}

function LifeBar({ pct }) {
  if (pct === null || pct === undefined) return <span style={{ color: 'var(--text-dim)', fontSize: 11 }}>—</span>
  const clamped = Math.min(100, Math.max(0, pct))
  const color = clamped < 10 ? 'var(--red)' : clamped < 30 ? 'var(--amber)' : 'var(--green)'
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 6 }}>
      <div style={{ width: 48, height: 4, background: 'var(--bg-base)', borderRadius: 2, overflow: 'hidden' }}>
        <div style={{ width: `${clamped}%`, height: '100%', background: color, borderRadius: 2, transition: 'width 0.3s' }} />
      </div>
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 11, color }}>{clamped.toFixed(0)}%</span>
    </div>
  )
}

// ── Componente principale ────────────────────────────────────────────────────
export default function UtensiliMacchina() {
  const [tools, setTools]             = useState([])
  const [syncStatus, setSyncStatus]   = useState(null)
  const [loading, setLoading]         = useState(false)
  const [syncing, setSyncing]         = useState(false)
  const [error, setError]             = useState(null)
  const [syncMsg, setSyncMsg]         = useState(null)

  // Filtro e ricerca
  const [search, setSearch]           = useState('')
  const [filterStatus, setFilterStatus] = useState('all') // all | ok | worn | disabled

  // Check MPF
  const [checkResult, setCheckResult] = useState(null)
  const [checking, setChecking]       = useState(false)
  const [checkError, setCheckError]   = useState(null)
  const [checkFile, setCheckFile]     = useState(null)
  const fileInputRef                  = useRef()

  // ── Caricamento iniziale ──────────────────────────────
  useEffect(() => {
    loadData()
  }, [])

  async function loadData() {
    setLoading(true)
    setError(null)
    try {
      const [toolsData, status] = await Promise.all([
        api.getTools(),
        api.getToolsSyncStatus(),
      ])
      setTools(toolsData)
      setSyncStatus(status)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }

  // ── Sync dalla share ──────────────────────────────────
  async function handleSync() {
    setSyncing(true)
    setSyncMsg(null)
    setError(null)
    try {
      const res = await api.syncTools()
      setSyncMsg(`Sync completato — ${res.tool_count} utensili, ${res.positions_mapped} posizioni`)
      await loadData()
    } catch (e) {
      setError(e.message)
    } finally {
      setSyncing(false)
    }
  }

  // ── Check MPF ─────────────────────────────────────────
  async function handleCheckFile(file) {
    if (!file) return
    setCheckFile(file)
    setChecking(true)
    setCheckResult(null)
    setCheckError(null)
    try {
      const res = await api.checkToolsMpf(file)
      setCheckResult(res)
    } catch (e) {
      setCheckError(e.message)
    } finally {
      setChecking(false)
    }
  }

  // ── Filtro tools ──────────────────────────────────────
  const filtered = tools.filter(t => {
    const matchSearch = !search || t.name.toLowerCase().includes(search.toLowerCase())
    const matchStatus =
      filterStatus === 'all'      ? true :
      filterStatus === 'ok'       ? (t.is_enabled && !t.is_worn) :
      filterStatus === 'worn'     ? (t.life_percent !== null && t.life_percent < 10) :
      filterStatus === 'disabled' ? (!t.is_enabled || t.is_worn) : true
    return matchSearch && matchStatus
  })

  // Raggruppa per nome (per mostrare dupli insieme)
  const grouped = filtered.reduce((acc, t) => {
    acc[t.name] = acc[t.name] || []
    acc[t.name].push(t)
    return acc
  }, {})

  // ── Render ────────────────────────────────────────────
  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20, height: '100%' }}>

      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', justifyContent: 'space-between', gap: 16 }}>
        <div>
          <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.03em', color: 'var(--text-primary)', marginBottom: 4 }}>
            Utensili Macchina
          </h1>
          <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
            {syncStatus?.last_sync
              ? `Ultimo sync: ${new Date(syncStatus.last_sync).toLocaleString('it-IT')} — ${syncStatus.tool_count} utensili`
              : 'Nessun sync effettuato'}
          </div>
        </div>

        {/* Bottone Sync */}
        <button
          onClick={handleSync}
          disabled={syncing}
          style={{
            display: 'flex', alignItems: 'center', gap: 8,
            padding: '9px 18px', borderRadius: 6, cursor: syncing ? 'not-allowed' : 'pointer',
            background: syncing ? 'var(--bg-hover)' : 'var(--cyan-glow)',
            border: `1px solid ${syncing ? 'var(--border)' : 'rgba(0,212,255,0.35)'}`,
            color: syncing ? 'var(--text-dim)' : 'var(--cyan)',
            fontSize: 13, fontWeight: 600, transition: 'all var(--t-fast)', flexShrink: 0,
          }}
        >
          <span style={{ fontSize: 15, animation: syncing ? 'spin 1s linear infinite' : 'none' }}>
            {syncing ? '↻' : '⟳'}
          </span>
          {syncing ? 'Sincronizzazione…' : 'Sync da Macchina'}
        </button>
      </div>

      {/* Messaggi */}
      {syncMsg && (
        <div style={{
          padding: '10px 14px', borderRadius: 6, fontSize: 13,
          background: 'rgba(0,255,136,0.07)', border: '1px solid rgba(0,255,136,0.2)', color: 'var(--green)',
        }}>
          ✓ {syncMsg}
        </div>
      )}
      {error && (
        <div style={{
          padding: '10px 14px', borderRadius: 6, fontSize: 13,
          background: 'rgba(255,68,85,0.08)', border: '1px solid rgba(255,68,85,0.25)', color: 'var(--red)',
        }}>
          ✕ {error}
        </div>
      )}

      {/* Istruzioni sync */}
      {(!syncStatus?.last_sync) && (
        <div style={{
          padding: '14px 16px', borderRadius: 8, fontSize: 13,
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          color: 'var(--text-secondary)', lineHeight: 1.7,
        }}>
          <div style={{ fontWeight: 700, color: 'var(--text-primary)', marginBottom: 6 }}>Come sincronizzare</div>
          <ol style={{ paddingLeft: 20 }}>
            <li>Sulla macchina: <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>HMI → Servizi → Salva Attrezzaggio</span></li>
            <li>Navigare in <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>Z:\DMG_DMC_160U\</span> e salvare con nome <span style={{ fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>TOOL_SYNC</span></li>
            <li>Premere il bottone <strong>Sync da Macchina</strong> qui sopra</li>
          </ol>
        </div>
      )}

      {/* Sezione Check MPF */}
      <div style={{
        background: 'var(--bg-card)', border: '1px solid var(--border)',
        borderRadius: 10, padding: '16px 18px',
      }}>
        <div style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)', marginBottom: 12 }}>
          🔍 Verifica Programma MPF
        </div>

        {/* Drop zone */}
        <div
          onClick={() => fileInputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--cyan)' }}
          onDragLeave={e => { e.currentTarget.style.borderColor = 'var(--border-bright)' }}
          onDrop={e => {
            e.preventDefault()
            e.currentTarget.style.borderColor = 'var(--border-bright)'
            const f = e.dataTransfer.files[0]
            if (f) handleCheckFile(f)
          }}
          style={{
            border: '2px dashed var(--border-bright)', borderRadius: 8,
            padding: '20px', textAlign: 'center', cursor: 'pointer',
            transition: 'border-color var(--t-fast)',
          }}
        >
          <input
            ref={fileInputRef} type="file" accept=".mpf,.nc,.spf"
            style={{ display: 'none' }}
            onChange={e => handleCheckFile(e.target.files[0])}
          />
          <div style={{ fontSize: 24, marginBottom: 6 }}>📄</div>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
            {checkFile
              ? <><span style={{ color: 'var(--cyan)', fontFamily: 'var(--font-mono)' }}>{checkFile.name}</span> — clicca per cambiare</>
              : <>Trascina un file MPF o <span style={{ color: 'var(--cyan)' }}>clicca per scegliere</span></>
            }
          </div>
        </div>

        {/* Risultato check */}
        {checking && (
          <div style={{ marginTop: 12, fontSize: 13, color: 'var(--text-dim)' }}>Analisi in corso…</div>
        )}
        {checkError && (
          <div style={{ marginTop: 12, padding: '8px 12px', borderRadius: 6, fontSize: 13,
            background: 'rgba(255,68,85,0.08)', border: '1px solid rgba(255,68,85,0.2)', color: 'var(--red)' }}>
            ✕ {checkError}
          </div>
        )}
        {checkResult && (
          <div style={{ marginTop: 14 }}>
            {/* Banner ok/ko */}
            <div style={{
              display: 'flex', alignItems: 'center', gap: 10, marginBottom: 12,
              padding: '10px 14px', borderRadius: 6,
              background: checkResult.can_run ? 'rgba(0,255,136,0.07)' : 'rgba(255,68,85,0.08)',
              border: `1px solid ${checkResult.can_run ? 'rgba(0,255,136,0.2)' : 'rgba(255,68,85,0.25)'}`,
            }}>
              <span style={{ fontSize: 18 }}>{checkResult.can_run ? '✅' : '❌'}</span>
              <div>
                <div style={{ fontWeight: 700, fontSize: 13,
                  color: checkResult.can_run ? 'var(--green)' : 'var(--red)' }}>
                  {checkResult.can_run ? 'Programma eseguibile' : 'Utensili mancanti o non disponibili'}
                </div>
                <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginTop: 2 }}>
                  {checkResult.total_required} utensili richiesti dal programma
                </div>
              </div>
            </div>

            {/* Badge riassunto */}
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8, marginBottom: 14 }}>
              <StatusBadge label="OK"        color="ok"       count={checkResult.ok.length} />
              <StatusBadge label="Mancanti"  color="missing"  count={checkResult.missing.length} />
              <StatusBadge label="Disabilitati" color="disabled" count={checkResult.disabled.length} />
              <StatusBadge label="Vita bassa" color="worn"    count={checkResult.worn.length} />
            </div>

            {/* Liste dettaglio */}
            {[
              { key: 'missing',  label: '❌ Mancanti in macchina', color: 'missing' },
              { key: 'disabled', label: '⚠️ Disabilitati / Esauriti', color: 'disabled' },
              { key: 'worn',     label: '🟣 Vita residua < 10%', color: 'worn' },
              { key: 'ok',       label: '✅ Disponibili', color: 'ok' },
            ].map(({ key, label, color }) => {
              const list = checkResult[key]
              if (!list?.length) return null
              return (
                <div key={key} style={{ marginBottom: 10 }}>
                  <div style={{ fontSize: 11, fontWeight: 600, color: COL[color].text,
                    fontFamily: 'var(--font-mono)', marginBottom: 5, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    {label}
                  </div>
                  <div style={{ display: 'flex', flexWrap: 'wrap', gap: 5 }}>
                    {list.map(name => (
                      <span key={name} style={{
                        padding: '3px 9px', borderRadius: 3, fontSize: 12,
                        fontFamily: 'var(--font-mono)',
                        background: COL[color].bg, border: `1px solid ${COL[color].border}`,
                        color: COL[color].text,
                      }}>
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

      {/* Barra ricerca e filtri */}
      {tools.length > 0 && (
        <div style={{ display: 'flex', gap: 10, alignItems: 'center' }}>
          <input
            value={search}
            onChange={e => setSearch(e.target.value)}
            placeholder="Cerca utensile…"
            style={{
              flex: 1, padding: '8px 12px', borderRadius: 6,
              background: 'var(--bg-card)', border: '1px solid var(--border)',
              color: 'var(--text-primary)', fontSize: 13, outline: 'none',
              fontFamily: 'var(--font-mono)',
            }}
          />
          {['all', 'ok', 'worn', 'disabled'].map(f => (
            <button key={f} onClick={() => setFilterStatus(f)} style={{
              padding: '7px 13px', borderRadius: 5, fontSize: 12, cursor: 'pointer',
              background: filterStatus === f ? 'var(--bg-active)' : 'var(--bg-card)',
              border: `1px solid ${filterStatus === f ? 'var(--border-bright)' : 'var(--border)'}`,
              color: filterStatus === f ? 'var(--text-primary)' : 'var(--text-dim)',
              fontWeight: filterStatus === f ? 600 : 400, transition: 'all var(--t-fast)',
            }}>
              {{ all: 'Tutti', ok: '✅ OK', worn: '🟣 Vita bassa', disabled: '⚠️ Disabilitati' }[f]}
            </button>
          ))}
          <span style={{ fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>
            {filtered.length} / {tools.length}
          </span>
        </div>
      )}

      {/* Tabella utensili */}
      {loading ? (
        <div style={{ textAlign: 'center', color: 'var(--text-dim)', padding: 40 }}>Caricamento…</div>
      ) : tools.length === 0 ? null : (
        <div style={{
          flex: 1, overflow: 'auto',
          background: 'var(--bg-card)', borderRadius: 10,
          border: '1px solid var(--border)',
        }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                {['Pos', 'Nome utensile', 'Duplo', 'L (mm)', 'R (mm)', 'Vita %', 'Stato'].map(h => (
                  <th key={h} style={{
                    padding: '10px 14px', textAlign: 'left', fontSize: 11,
                    fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
                    fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em',
                    position: 'sticky', top: 0, background: 'var(--bg-card)',
                  }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {Object.entries(grouped).map(([name, group]) =>
                group.map((t, i) => {
                  const isWorn     = t.life_percent !== null && t.life_percent < 10
                  const isDisabled = !t.is_enabled || t.is_worn
                  const rowColor   = isDisabled ? 'rgba(255,68,85,0.04)' :
                                     isWorn     ? 'rgba(168,85,247,0.04)' : 'transparent'
                  return (
                    <tr key={t.tool_id} style={{
                      borderBottom: '1px solid var(--border)',
                      background: rowColor,
                      transition: 'background var(--t-fast)',
                    }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = rowColor}
                    >
                      {/* Posizione magazzino */}
                      <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 11,
                        color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
                        {t.magazine != null && t.position != null
                          ? <span style={{ color: 'var(--cyan)', opacity: 0.8 }}>M{t.magazine}·{String(t.position).padStart(3,'0')}</span>
                          : '—'}
                      </td>
                      {/* Nome */}
                      <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 13,
                        color: isDisabled ? 'var(--text-dim)' : 'var(--text-primary)', fontWeight: 600 }}>
                        {name}
                        {group.length > 1 && <span style={{ fontSize: 10, color: 'var(--text-dim)', marginLeft: 6 }}>#{t.duplo}</span>}
                      </td>
                      {/* Duplo */}
                      <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                        color: 'var(--text-dim)' }}>
                        #{t.duplo}
                      </td>
                      {/* Lunghezza */}
                      <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                        color: 'var(--text-secondary)' }}>
                        {t.length?.toFixed(3)}
                      </td>
                      {/* Raggio */}
                      <td style={{ padding: '9px 14px', fontFamily: 'var(--font-mono)', fontSize: 12,
                        color: 'var(--text-secondary)' }}>
                        {t.radius?.toFixed(3)}
                      </td>
                      {/* Vita — MOP2/MOP11*100 */}
                      <td style={{ padding: '9px 14px' }}>
                        <LifeBar pct={t.life_percent} />
                      </td>
                      {/* Stato */}
                      <td style={{ padding: '9px 14px' }}>
                        {isDisabled
                          ? <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)',
                              color: 'var(--red)', background: 'rgba(255,68,85,0.1)',
                              padding: '2px 7px', borderRadius: 3 }}>DISAB.</span>
                          : isWorn
                          ? <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)',
                              color: 'var(--purple)', background: 'rgba(168,85,247,0.1)',
                              padding: '2px 7px', borderRadius: 3 }}>VITA BASSA</span>
                          : <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)',
                              color: 'var(--green)', background: 'rgba(0,255,136,0.08)',
                              padding: '2px 7px', borderRadius: 3 }}>OK</span>
                        }
                      </td>
                    </tr>
                  )
                })
              )}
            </tbody>
          </table>
        </div>
      )}

      <style>{`
        @keyframes spin { to { transform: rotate(360deg) } }
      `}</style>
    </div>
  )
}
