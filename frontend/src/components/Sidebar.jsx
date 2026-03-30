import { NavLink, useLocation } from 'react-router-dom'
import { useState, useEffect } from 'react'

const ICONS = {
  home: (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M3 9.5L12 3l9 6.5V20a1 1 0 01-1 1H4a1 1 0 01-1-1V9.5z"/><path d="M9 21V12h6v9"/></svg>),
  lavori: (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="5" y="2" width="14" height="20" rx="2"/><path d="M9 7h6M9 11h6M9 15h4"/><path d="M9 2v3h6V2"/></svg>),
  macchina: (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M12 1v3M12 20v3M4.22 4.22l2.12 2.12M17.66 17.66l2.12 2.12M1 12h3M20 12h3M4.22 19.78l2.12-2.12M17.66 6.34l2.12-2.12"/></svg>),
  analisi: (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8z"/><path d="M14 2v6h6"/><path d="M8 13h2.5M8 17h5M8 9h1"/><path d="M13 13l2 2 3-3"/></svg>),
  utensili: (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M14.7 6.3a1 1 0 000 1.4l1.6 1.6a1 1 0 001.4 0l3.77-3.77a6 6 0 01-7.94 7.94l-6.91 6.91a2.12 2.12 0 01-3-3l6.91-6.91a6 6 0 017.94-7.94l-3.76 3.76z"/></svg>),
  scaffale: (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="2" y="3" width="20" height="14" rx="2"/><path d="M8 21h8M12 17v4"/><path d="M2 10h20"/></svg>),
  smontati: (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="2"/><path d="M12 2v4M12 18v4M4.93 4.93l2.83 2.83M16.24 16.24l2.83 2.83M2 12h4M18 12h4M4.93 19.07l2.83-2.83M16.24 7.76l2.83-2.83"/></svg>),
  holder: (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 22V8M5 12H2a10 10 0 0020 0h-3"/><path d="M8 6l4-4 4 4"/></svg>),
  generatore: (<svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><path d="M12 20h9M16.5 3.5a2.121 2.121 0 013 3L7 19l-4 1 1-4L16.5 3.5z"/></svg>),
  utilita: (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="3"/><path d="M19.4 15a1.65 1.65 0 00.33 1.82l.06.06a2 2 0 010 2.83 2 2 0 01-2.83 0l-.06-.06a1.65 1.65 0 00-1.82-.33 1.65 1.65 0 00-1 1.51V21a2 2 0 01-4 0v-.09A1.65 1.65 0 009 19.4a1.65 1.65 0 00-1.82.33l-.06.06a2 2 0 01-2.83-2.83l.06-.06A1.65 1.65 0 004.68 15a1.65 1.65 0 00-1.51-1H3a2 2 0 010-4h.09A1.65 1.65 0 004.6 9a1.65 1.65 0 00-.33-1.82l-.06-.06a2 2 0 012.83-2.83l.06.06A1.65 1.65 0 009 4.68a1.65 1.65 0 001-1.51V3a2 2 0 014 0v.09a1.65 1.65 0 001 1.51 1.65 1.65 0 001.82-.33l.06-.06a2 2 0 012.83 2.83l-.06.06A1.65 1.65 0 0019.4 9a1.65 1.65 0 001.51 1H21a2 2 0 010 4h-.09a1.65 1.65 0 00-1.51 1z"/></svg>),
  report: (<svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="18" height="18" rx="2"/><path d="M7 16v-4M11 16V9M15 16v-6M19 16v-2" strokeWidth="2"/></svg>),
}

const NAV_PRIMARY = [
  { to: '/home',       icon: 'home',     label: 'Home',     title: 'Home' },
  { to: '/progetti',   icon: 'lavori',   label: 'Lavori',   title: 'Lavori' },
  { to: '/coda',       icon: 'macchina', label: 'Macchina', title: 'Macchina' },
  { to: '/analisi-nc', icon: 'analisi',  label: 'Analisi',  title: 'Analisi NC', alertKey: 'analisi' },
  { to: '/macchina',   icon: 'utensili', label: 'Utensili', title: 'Utensili',   alertKey: 'utensili' },
  { to: '/report',     icon: 'report',   label: 'Report',   title: 'Report Lavorazioni' },
]
const NAV_UTILITA = [
  { to: '/scaffale',       icon: 'scaffale',   label: 'Scaffale' },
  { to: '/smontati',       icon: 'smontati',   label: 'Smontati' },
  { to: '/holder-bussole', icon: 'holder',     label: 'Holder' },
  { to: '/generatore',     icon: 'generatore', label: 'Genera.' },
]

// ── Badge rosso numero ────────────────────────────────────────────────────
function AlertBadge({ count }) {
  if (!count) return null
  return (
    <div style={{
      position: 'absolute', top: 4, right: 4,
      background: '#ef4444', color: '#fff',
      fontSize: 9, fontWeight: 800, lineHeight: 1,
      minWidth: 16, height: 16, borderRadius: 8,
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      padding: '0 4px', border: '1.5px solid var(--navy-700)',
      fontFamily: 'var(--font-mono)',
    }}>
      {count > 9 ? '9+' : count}
    </div>
  )
}

function NavItem({ to, icon, label, title, small, alertCount }) {
  const sz = small ? 48 : 56
  return (
    <NavLink to={to} title={title}
      style={({ isActive }) => ({
        width: sz, height: sz, position: 'relative',
        borderRadius: 10, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 4,
        textDecoration: 'none', transition: 'all 0.15s',
        background: isActive ? 'rgba(126,184,245,0.18)' : 'transparent',
        borderLeft: isActive ? '3px solid #7eb8f5' : '3px solid transparent',
      })}>
      {({ isActive }) => (<>
        <span style={{ color: isActive ? '#ffffff' : '#c8dff4', opacity: isActive ? 1 : 0.75, display: 'flex', lineHeight: 1 }}>
          {ICONS[icon]}
        </span>
        <span style={{ fontSize: small ? 8 : 9, fontFamily: 'var(--font-mono)', fontWeight: 700, color: isActive ? '#7eb8f5' : 'rgba(200,223,244,0.6)', letterSpacing: '0.05em' }}>
          {label}
        </span>
        <AlertBadge count={alertCount} />
      </>)}
    </NavLink>
  )
}

export default function Sidebar() {
  const loc = useLocation()
  const isUtilitaActive = NAV_UTILITA.some(n => loc.pathname.startsWith(n.to))
  const [open, setOpen] = useState(isUtilitaActive)

  // ── Stato macchina live ───────────────────────────────────────────────
  const [statoMacchina, setStatoMacchina] = useState(null)
  // { attiva: bool, programma: str|null, utensile: str|null }

  // ── Alert contatori ───────────────────────────────────────────────────
  const [alerts, setAlerts] = useState({ analisi: 0, utensili: 0 })

  useEffect(() => {
    // Carica stato macchina iniziale
    const fetchStato = () =>
      fetch('/api/macchina-live/stato')
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (!d) return
          const attiva = [1, 3].includes(d.stato_programma)
          setStatoMacchina({
            attiva,
            programma:  d.programma_attivo,
            utensile:   d.utensile_attivo,
            pallet:     d.pallet_attivo  || null,
            progetto:   d.progetto_attivo || null,
          })
        }).catch(() => {})

    // Carica alert utensili iniziali
    const fetchAlerts = () =>
      fetch('/api/progetti/analisi-setup/non-utilizzati')
        .then(r => r.ok ? r.json() : null)
        .then(d => {
          if (!d) return
          const mancanti  = (d.non_utilizzati || []).filter(u => u.provenienza === 'richiesto_da_progetto').length
          const daMontar  = (d.da_montare   || []).length
          const finVita   = (d.fin_vita     || []).length
          const totAnalisi = mancanti + daMontar + finVita
          setAlerts({ analisi: totAnalisi, utensili: daMontar })
        }).catch(() => {})

    fetchStato()
    fetchAlerts()

    // Ascolta il GlobalPoller — aggiorna stato macchina ad ogni tick
    const onUpdate = (e) => {
      const d = e.detail || {}
      if (d.stato_macchina !== undefined) {
        const attiva = [1, 3].includes(d.stato_macchina)
        setStatoMacchina(prev => ({
          attiva,
          programma: d.programma_attivo  || prev?.programma  || null,
          utensile:  prev?.utensile || null,
          pallet:    d.pallet_rilevato   ?? prev?.pallet   ?? null,
          progetto:  d.progetto_rilevato || prev?.progetto || null,
        }))
      }
      // Ricarica alert se ci sono cambiamenti utensili
      if (d.in_macchina > 0 || d.completato > 0) {
        fetchAlerts()
      }
    }
    window.addEventListener('dmgdesk:stati-aggiornati', onUpdate)

    // Refresh alert ogni 30s (per utensili fin_vita non triggerati dal poller)
    const t = setInterval(fetchAlerts, 30000)

    return () => {
      window.removeEventListener('dmgdesk:stati-aggiornati', onUpdate)
      clearInterval(t)
    }
  }, [])

  return (
    <nav style={{ width: 72, flexShrink: 0, background: 'var(--navy-700)',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      paddingTop: 10, paddingBottom: 12, gap: 1, overflowY: 'auto' }}>

      {/* Logo */}
      <div style={{ marginBottom: 6, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
        <div style={{ width: 42, height: 42, background: 'rgba(255,255,255,0.13)', borderRadius: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
          DMG
        </div>
      </div>

      {/* ── Stato macchina ─────────────────────────────────────────── */}
      <NavLink to="/coda" style={{ textDecoration: 'none' }}>
        <div style={{
          width: 58, marginBottom: 6, borderRadius: 8, padding: '5px 6px',
          background: statoMacchina?.attiva ? 'rgba(34,197,94,0.15)' : 'rgba(255,255,255,0.05)',
          border: `1px solid ${statoMacchina?.attiva ? 'rgba(34,197,94,0.3)' : 'rgba(255,255,255,0.08)'}`,
          display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 3,
          transition: 'all 0.3s', cursor: 'pointer',
        }}>
          {/* Dot + LIVE/FERMO */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 4 }}>
            <div style={{
              width: 6, height: 6, borderRadius: '50%', flexShrink: 0,
              background: statoMacchina?.attiva ? '#22c55e' : '#64748b',
              animation: statoMacchina?.attiva ? 'pulse-green 2s ease-in-out infinite' : 'none',
            }}/>
            <span style={{
              fontSize: 8, fontWeight: 800, letterSpacing: '0.06em',
              fontFamily: 'var(--font-mono)',
              color: statoMacchina?.attiva ? '#86efac' : '#64748b',
            }}>
              {statoMacchina?.attiva ? 'LIVE' : 'FERMO'}
            </span>
          </div>
          {/* Pallet attivo */}
          {statoMacchina?.attiva && statoMacchina?.pallet && (
            <div style={{
              fontSize: 9, fontWeight: 800, fontFamily: 'var(--font-mono)',
              color: '#7eb8f5', letterSpacing: '0.04em',
            }}>
              P{statoMacchina.pallet}
            </div>
          )}
          {/* Programma corrente (troncato) */}
          {statoMacchina?.attiva && statoMacchina?.programma && (
            <div style={{
              fontSize: 7, fontFamily: 'var(--font-mono)', color: 'rgba(134,239,172,0.7)',
              textAlign: 'center', lineHeight: 1.3, wordBreak: 'break-all',
              maxHeight: 22, overflow: 'hidden',
            }}>
              {statoMacchina.programma.replace('.MPF','').replace('.mpf','').split('_').slice(-2).join('_')}
            </div>
          )}
          {!statoMacchina?.attiva && (
            <div style={{ fontSize: 7, color: 'rgba(100,116,139,0.6)', fontFamily: 'var(--font-mono)' }}>
              in attesa
            </div>
          )}
        </div>
      </NavLink>

      {/* Nav principale */}
      {NAV_PRIMARY.map(item => (
        <NavItem
          key={item.to}
          {...item}
          alertCount={item.alertKey ? alerts[item.alertKey] : 0}
        />
      ))}

      <div style={{ width: 40, height: 1, background: 'rgba(255,255,255,0.1)', margin: '6px 0' }} />

      {/* Utilità toggle */}
      <div onClick={() => setOpen(v => !v)} title="Utilità"
        style={{ width: 56, height: 56, borderRadius: 10, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 4, cursor: 'pointer',
          background: isUtilitaActive ? 'rgba(126,184,245,0.18)' : open ? 'rgba(255,255,255,0.06)' : 'transparent',
          borderLeft: isUtilitaActive ? '3px solid #7eb8f5' : '3px solid transparent',
          transition: 'all 0.15s' }}>
        <span style={{ color: isUtilitaActive ? '#fff' : '#c8dff4', opacity: isUtilitaActive || open ? 1 : 0.75, display: 'flex' }}>
          {ICONS.utilita}
        </span>
        <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 700,
          color: isUtilitaActive ? '#7eb8f5' : open ? 'rgba(200,223,244,0.7)' : 'rgba(200,223,244,0.5)',
          letterSpacing: '0.04em' }}>
          Utilità {open ? '▴' : '▾'}
        </span>
      </div>

      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
          gap: 1, width: '100%', background: 'rgba(0,0,0,0.15)', paddingTop: 4, paddingBottom: 4 }}>
          {NAV_UTILITA.map(item => <NavItem key={item.to} {...item} small />)}
        </div>
      )}

      <div style={{ marginTop: 'auto' }}>
        <a href="/api/docs" target="_blank" rel="noreferrer" title="API Docs"
          style={{ width: 56, height: 32, display: 'flex', alignItems: 'center', justifyContent: 'center',
            color: 'rgba(255,255,255,0.2)', textDecoration: 'none', borderRadius: 8, transition: 'color 0.15s', fontSize: 14 }}
          onMouseEnter={e => e.currentTarget.style.color = '#7eb8f5'}
          onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.2)'}>
          ⬡
        </a>
      </div>

      <style>{`
        @keyframes pulse-green {
          0%, 100% { opacity: 1; box-shadow: 0 0 0 0 rgba(34,197,94,0.4); }
          50%       { opacity: .7; box-shadow: 0 0 0 4px rgba(34,197,94,0); }
        }
      `}</style>
    </nav>
  )
}
