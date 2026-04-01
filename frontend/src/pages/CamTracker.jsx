// CamTracker.jsx — Monitoraggio Ore CAM per Progetto
// Modulo DMGDesk — dati da Cimatron via CAMTracker agent su CAM35

import { useState, useEffect, useCallback } from 'react'

const API = '/api/cam-tracker'

// ── Icone inline ────────────────────────────────────────────────────────────
const IcoTime = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <circle cx="12" cy="12" r="10"/><path d="M12 6v6l4 2"/>
  </svg>
)
const IcoCam = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="2" y="6" width="20" height="14" rx="2"/>
    <path d="M8 6V4h8v2"/><circle cx="12" cy="13" r="3"/>
  </svg>
)
const IcoFolder = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M22 19a2 2 0 01-2 2H4a2 2 0 01-2-2V5a2 2 0 012-2h5l2 3h9a2 2 0 012 2z"/>
  </svg>
)
const IcoTrend = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="23 6 13.5 15.5 8.5 10.5 1 18"/><polyline points="17 6 23 6 23 12"/>
  </svg>
)
const IcoRefresh = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <path d="M23 4v6h-6"/><path d="M20.49 15a9 9 0 11-2.12-9.36L23 10"/>
  </svg>
)
const IcoCalendar = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="4" width="18" height="18" rx="2"/><path d="M16 2v4M8 2v4M3 10h18"/>
  </svg>
)

// ── Helpers ──────────────────────────────────────────────────────────────────
function fmtHours(h) {
  const hh = Math.floor(h)
  const mm = Math.round((h - hh) * 60)
  if (hh === 0) return `${mm}m`
  if (mm === 0) return `${hh}h`
  return `${hh}h ${mm}m`
}

function fmtDate(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('-')
  return `${d}/${m}/${y}`
}

function todayISO() {
  return new Date().toISOString().slice(0, 10)
}

function nDaysAgoISO(n) {
  const d = new Date()
  d.setDate(d.getDate() - n)
  return d.toISOString().slice(0, 10)
}

// ── Barra ore ────────────────────────────────────────────────────────────────
function HoursBar({ hours, maxHours }) {
  const pct = maxHours > 0 ? Math.min(100, (hours / maxHours) * 100) : 0
  const color = pct > 75 ? '#16a34a' : pct > 40 ? '#0d2d5e' : '#94a3b8'
  return (
    <div style={{ flex: 1, height: 6, background: '#e2e8f0', borderRadius: 3, overflow: 'hidden' }}>
      <div style={{
        width: `${pct}%`, height: '100%',
        background: color, borderRadius: 3,
        transition: 'width 0.4s ease',
      }}/>
    </div>
  )
}

// ── Card sommario ────────────────────────────────────────────────────────────
function StatCard({ label, value, sub, accent }) {
  return (
    <div style={{
      background: '#fff', border: '1px solid #e2e8f0',
      borderRadius: 10, padding: '14px 18px', flex: 1, minWidth: 140,
    }}>
      <div style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'var(--font-mono)', textTransform: 'uppercase', letterSpacing: '0.06em', marginBottom: 6 }}>
        {label}
      </div>
      <div style={{ fontSize: 24, fontWeight: 700, color: accent || '#0d2d5e', fontFamily: 'var(--font-mono)' }}>
        {value}
      </div>
      {sub && <div style={{ fontSize: 11, color: '#94a3b8', marginTop: 4 }}>{sub}</div>}
    </div>
  )
}

// ── Tabella sessioni giornaliere ──────────────────────────────────────────────
function SessioniTable({ sessions }) {
  if (!sessions.length) return (
    <div style={{ textAlign: 'center', padding: '40px 20px', color: '#94a3b8', fontSize: 13 }}>
      Nessuna sessione nel periodo selezionato
    </div>
  )

  const byDate = sessions.reduce((acc, s) => {
    if (!acc[s.date]) acc[s.date] = []
    acc[s.date].push(s)
    return acc
  }, {})

  const dates = Object.keys(byDate).sort((a, b) => b.localeCompare(a))

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 16 }}>
      {dates.map(d => {
        const rows = byDate[d].sort((a, b) => b.seconds - a.seconds)
        const totH = rows.reduce((s, r) => s + r.hours, 0)
        const isToday = d === todayISO()
        return (
          <div key={d} style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden' }}>
            {/* header data */}
            <div style={{
              display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '10px 16px',
              background: isToday ? '#e6f1fb' : '#f8fafc',
              borderBottom: '1px solid #e2e8f0',
            }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                <IcoCalendar />
                <span style={{ fontWeight: 600, fontSize: 13, color: '#0f172a' }}>
                  {fmtDate(d)}
                </span>
                {isToday && (
                  <span style={{
                    background: '#0d2d5e', color: '#fff',
                    fontSize: 9, fontWeight: 700, padding: '2px 6px',
                    borderRadius: 4, fontFamily: 'var(--font-mono)', letterSpacing: '0.06em',
                  }}>OGGI</span>
                )}
              </div>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, fontWeight: 600, color: '#0d2d5e' }}>
                {fmtHours(totH)} tot.
              </span>
            </div>
            {/* righe */}
            {rows.map((r, i) => (
              <div key={r.id || i} style={{
                display: 'flex', alignItems: 'center', gap: 12,
                padding: '8px 16px',
                borderBottom: i < rows.length - 1 ? '1px solid #f1f5f9' : 'none',
              }}>
                <IcoFolder />
                <span style={{ flex: 1, fontSize: 13, fontFamily: 'var(--font-mono)', color: '#0f172a', fontWeight: 500 }}>
                  {r.project}
                </span>
                <HoursBar hours={r.hours} maxHours={8} />
                <span style={{ fontSize: 13, fontFamily: 'var(--font-mono)', fontWeight: 600, color: '#0d2d5e', minWidth: 52, textAlign: 'right' }}>
                  {fmtHours(r.hours)}
                </span>
              </div>
            ))}
          </div>
        )
      })}
    </div>
  )
}

// ── Riepilogo per progetto ───────────────────────────────────────────────────
function SummaryTable({ summary }) {
  if (!summary.length) return (
    <div style={{ textAlign: 'center', padding: '40px 20px', color: '#94a3b8', fontSize: 13 }}>
      Nessun dato disponibile
    </div>
  )
  const maxH = summary[0]?.total_hours || 1

  return (
    <div style={{ background: '#fff', border: '1px solid #e2e8f0', borderRadius: 10, overflow: 'hidden' }}>
      <div style={{ padding: '10px 16px', background: '#f8fafc', borderBottom: '1px solid #e2e8f0' }}>
        <span style={{ fontSize: 12, fontWeight: 600, color: '#475569', textTransform: 'uppercase', letterSpacing: '0.05em' }}>
          Ore totali per progetto
        </span>
      </div>
      {summary.map((s, i) => (
        <div key={s.project} style={{
          display: 'flex', alignItems: 'center', gap: 12,
          padding: '10px 16px',
          borderBottom: i < summary.length - 1 ? '1px solid #f1f5f9' : 'none',
        }}>
          <span style={{
            fontSize: 11, fontFamily: 'var(--font-mono)', color: '#94a3b8',
            minWidth: 20, textAlign: 'right',
          }}>{i + 1}</span>
          <IcoFolder />
          <span style={{ flex: 1, fontSize: 13, fontFamily: 'var(--font-mono)', color: '#0f172a', fontWeight: 500 }}>
            {s.project}
          </span>
          <HoursBar hours={s.total_hours} maxHours={maxH} />
          <span style={{ fontSize: 14, fontFamily: 'var(--font-mono)', fontWeight: 700, color: '#0d2d5e', minWidth: 64, textAlign: 'right' }}>
            {fmtHours(s.total_hours)}
          </span>
        </div>
      ))}
    </div>
  )
}

// ── Pagina principale ────────────────────────────────────────────────────────
export default function CamTracker() {
  const [view, setView] = useState('today')  // 'today' | 'period' | 'summary'
  const [sessions, setSessions] = useState([])
  const [summary, setSummary] = useState([])
  const [todayData, setTodayData] = useState(null)
  const [loading, setLoading] = useState(false)
  const [lastUpdate, setLastUpdate] = useState(null)
  const [dateFrom, setDateFrom] = useState(nDaysAgoISO(7))
  const [dateTo, setDateTo] = useState(todayISO())
  const [filterProject, setFilterProject] = useState('')

  const fetchToday = useCallback(async () => {
    try {
      const r = await fetch(`${API}/today`)
      if (r.ok) setTodayData(await r.json())
    } catch {}
  }, [])

  const fetchSessions = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo })
      if (filterProject) params.set('project', filterProject)
      const r = await fetch(`${API}/sessions?${params}`)
      if (r.ok) setSessions(await r.json())
    } catch {}
    setLoading(false)
  }, [dateFrom, dateTo, filterProject])

  const fetchSummary = useCallback(async () => {
    setLoading(true)
    try {
      const params = new URLSearchParams({ date_from: dateFrom, date_to: dateTo })
      const r = await fetch(`${API}/summary?${params}`)
      if (r.ok) setSummary(await r.json())
    } catch {}
    setLoading(false)
  }, [dateFrom, dateTo])

  const refresh = useCallback(() => {
    fetchToday()
    if (view === 'today') {
      // already handled
    } else if (view === 'period') {
      fetchSessions()
    } else if (view === 'summary') {
      fetchSummary()
    }
    setLastUpdate(new Date().toLocaleTimeString('it-IT'))
  }, [view, fetchToday, fetchSessions, fetchSummary])

  // Fetch iniziale + ogni cambio view
  useEffect(() => {
    fetchToday()
  }, [fetchToday])

  useEffect(() => {
    if (view === 'period') fetchSessions()
    if (view === 'summary') fetchSummary()
  }, [view, fetchSessions, fetchSummary])

  // Auto-refresh ogni 60s
  useEffect(() => {
    const t = setInterval(refresh, 60000)
    return () => clearInterval(t)
  }, [refresh])

  // Stat cards valori
  const todayH = todayData?.total_hours || 0
  const todayProjects = todayData?.sessions?.length || 0
  const summaryTotH = summary.reduce((s, r) => s + r.total_hours, 0)
  const summaryProjects = summary.length

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%', background: '#eef2f7' }}>

      {/* ── Header ─────────────────────────────────────────────────────── */}
      <div style={{
        background: '#0d2d5e', color: '#fff',
        padding: '14px 24px',
        display: 'flex', alignItems: 'center', gap: 12,
        flexShrink: 0,
      }}>
        <IcoCam />
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 15, letterSpacing: '0.01em' }}>CAM Tracker</div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)', fontFamily: 'var(--font-mono)' }}>
            Ore Cimatron per progetto — CAM35
          </div>
        </div>
        {lastUpdate && (
          <div style={{ fontSize: 10, color: 'rgba(255,255,255,0.4)', fontFamily: 'var(--font-mono)' }}>
            aggiornato {lastUpdate}
          </div>
        )}
        <button
          onClick={refresh}
          style={{
            background: 'rgba(255,255,255,0.1)', border: '1px solid rgba(255,255,255,0.15)',
            color: '#fff', borderRadius: 6, padding: '6px 12px',
            cursor: 'pointer', display: 'flex', alignItems: 'center', gap: 6, fontSize: 12,
          }}
        >
          <IcoRefresh /> Aggiorna
        </button>
      </div>

      {/* ── Stat cards ─────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 12, padding: '16px 24px 0', flexShrink: 0 }}>
        <StatCard
          label="Ore oggi"
          value={fmtHours(todayH)}
          sub={`${todayProjects} progetti`}
          accent="#0d2d5e"
        />
        <StatCard
          label="Progetti periodo"
          value={summaryProjects || todayProjects}
          sub={dateFrom === dateTo ? 'solo oggi' : `${fmtDate(dateFrom)} → ${fmtDate(dateTo)}`}
          accent="#16a34a"
        />
        <StatCard
          label="Ore totali periodo"
          value={fmtHours(summaryTotH || todayH)}
          sub="Cimatron CAM35"
        />
      </div>

      {/* ── Tab bar ────────────────────────────────────────────────────── */}
      <div style={{ display: 'flex', gap: 4, padding: '16px 24px 0', flexShrink: 0 }}>
        {[
          { id: 'today', label: 'Oggi' },
          { id: 'period', label: 'Periodo' },
          { id: 'summary', label: 'Per Progetto' },
        ].map(tab => (
          <button
            key={tab.id}
            onClick={() => setView(tab.id)}
            style={{
              padding: '7px 18px', borderRadius: '8px 8px 0 0',
              border: '1px solid',
              borderColor: view === tab.id ? '#e2e8f0' : 'transparent',
              borderBottom: view === tab.id ? '1px solid #eef2f7' : '1px solid transparent',
              background: view === tab.id ? '#eef2f7' : 'transparent',
              color: view === tab.id ? '#0d2d5e' : '#94a3b8',
              fontWeight: view === tab.id ? 600 : 400,
              fontSize: 13, cursor: 'pointer',
              transition: 'all 0.15s',
            }}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* ── Corpo ──────────────────────────────────────────────────────── */}
      <div style={{
        flex: 1, overflow: 'auto',
        background: '#eef2f7',
        border: '1px solid #e2e8f0',
        margin: '0 24px',
        borderRadius: '0 8px 8px 8px',
        padding: 20,
      }}>

        {/* Filtri per Periodo / Summary */}
        {(view === 'period' || view === 'summary') && (
          <div style={{ display: 'flex', gap: 12, marginBottom: 16, flexWrap: 'wrap', alignItems: 'flex-end' }}>
            <div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>Da</div>
              <input
                type="date"
                value={dateFrom}
                onChange={e => setDateFrom(e.target.value)}
                style={{ padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13, background: '#fff', color: '#0f172a' }}
              />
            </div>
            <div>
              <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>A</div>
              <input
                type="date"
                value={dateTo}
                onChange={e => setDateTo(e.target.value)}
                style={{ padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13, background: '#fff', color: '#0f172a' }}
              />
            </div>
            {view === 'period' && (
              <div>
                <div style={{ fontSize: 11, color: '#94a3b8', marginBottom: 4 }}>Progetto</div>
                <input
                  type="text"
                  value={filterProject}
                  onChange={e => setFilterProject(e.target.value)}
                  placeholder="Filtra progetto..."
                  style={{ padding: '6px 10px', border: '1px solid #e2e8f0', borderRadius: 6, fontSize: 13, background: '#fff', color: '#0f172a', width: 180 }}
                />
              </div>
            )}
            <button
              onClick={() => { if (view === 'period') fetchSessions(); else fetchSummary() }}
              className="btn btn-primary"
            >
              Cerca
            </button>
            <div style={{ display: 'flex', gap: 6, marginLeft: 'auto' }}>
              {[7, 30, 90].map(n => (
                <button
                  key={n}
                  onClick={() => { setDateFrom(nDaysAgoISO(n)); setDateTo(todayISO()) }}
                  style={{
                    padding: '6px 12px', borderRadius: 6, fontSize: 12,
                    border: '1px solid #e2e8f0', background: '#fff', color: '#475569',
                    cursor: 'pointer',
                  }}
                >
                  {n}gg
                </button>
              ))}
            </div>
          </div>
        )}

        {/* Contenuto tab */}
        {loading && (
          <div style={{ textAlign: 'center', padding: 40, color: '#94a3b8', fontSize: 13 }}>
            Caricamento...
          </div>
        )}

        {!loading && view === 'today' && (
          <SessioniTable sessions={todayData?.sessions || []} />
        )}

        {!loading && view === 'period' && (
          <SessioniTable sessions={sessions} />
        )}

        {!loading && view === 'summary' && (
          <SummaryTable summary={summary} />
        )}
      </div>

      {/* ── Footer ─────────────────────────────────────────────────────── */}
      <div style={{ padding: '10px 24px', flexShrink: 0 }}>
        <div style={{ fontSize: 11, color: '#94a3b8', fontFamily: 'var(--font-mono)' }}>
          Agent attivo su CAM35 — polling Cimatron ogni 10s — flush ogni 5min
        </div>
      </div>
    </div>
  )
}
