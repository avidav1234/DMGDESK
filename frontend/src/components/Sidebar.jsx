import { NavLink, useLocation } from 'react-router-dom'
import { useState } from 'react'

const NAV_PRIMARY = [
  { to: '/home',       icon: '🏠', label: 'Home',     title: 'Home — Dashboard turno' },
  { to: '/progetti',   icon: '📋', label: 'Lavori',   title: 'Lavori — Gestione commesse' },
  { to: '/coda',       icon: '○',  label: 'Macchina', title: 'Macchina — Stato pallet live' },
  { to: '/analisi-nc', icon: '📄', label: 'Analisi',  title: 'Analisi NC' },
  { to: '/macchina',   icon: '🔧', label: 'Utensili', title: 'Utensili in macchina' },
]

const NAV_UTILITA = [
  { to: '/scaffale',       icon: '📦', label: 'Scaffale', title: 'Scaffale' },
  { to: '/smontati',       icon: '🔩', label: 'Smontati', title: 'Smontati' },
  { to: '/holder-bussole', icon: '⚙',  label: 'Holder',   title: 'Holder & Bussole' },
  { to: '/generatore',     icon: '📝', label: 'Genera.',  title: 'Generatore codici' },
]

function NavItem({ to, icon, label, title, small }) {
  return (
    <NavLink to={to} title={title}
      style={({ isActive }) => ({
        width: small ? 52 : 58, height: small ? 40 : 52,
        borderRadius: 8, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 2,
        textDecoration: 'none', transition: 'all 0.15s',
        background: isActive ? 'rgba(255,255,255,0.18)' : 'transparent',
        borderLeft: isActive ? '3px solid var(--navy-accent)' : '3px solid transparent',
      })}>
      {({ isActive }) => (<>
        <span style={{ fontSize: small ? 16 : 22, opacity: isActive ? 1 : 0.5, lineHeight: 1 }}>{icon}</span>
        <span style={{ fontSize: small ? 7 : 9, fontFamily: 'var(--font-mono)', fontWeight: 600,
          color: isActive ? 'var(--navy-accent)' : 'rgba(255,255,255,0.45)', letterSpacing: '0.04em' }}>
          {label}
        </span>
      </>)}
    </NavLink>
  )
}

export default function Sidebar() {
  const loc = useLocation()
  const isUtilitaActive = NAV_UTILITA.some(n => loc.pathname.startsWith(n.to))
  const [open, setOpen] = useState(isUtilitaActive)

  return (
    <nav style={{ width: 72, flexShrink: 0, background: 'var(--navy-700)',
      display: 'flex', flexDirection: 'column', alignItems: 'center',
      paddingTop: 10, paddingBottom: 12, gap: 2, overflowY: 'auto' }}>

      {/* Logo */}
      <div style={{ marginBottom: 12, display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2 }}>
        <div style={{ width: 42, height: 42, background: 'rgba(255,255,255,0.15)', borderRadius: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 800, color: '#fff', letterSpacing: '-0.02em' }}>
          DMG
        </div>
        <div style={{ fontSize: 8, color: 'var(--navy-accent)', letterSpacing: '0.1em',
          fontFamily: 'var(--font-mono)', animation: 'pulse 2s ease infinite' }}>
          LIVE
        </div>
      </div>

      {/* Nav principali */}
      {NAV_PRIMARY.map(item => <NavItem key={item.to} {...item} />)}

      {/* Separatore */}
      <div style={{ width: 40, height: 1, background: 'rgba(255,255,255,0.1)', margin: '6px 0' }} />

      {/* Utilità — bottone toggle */}
      <div onClick={() => setOpen(v => !v)} title="Utilità"
        style={{ width: 58, height: 52, borderRadius: 8, display: 'flex', flexDirection: 'column',
          alignItems: 'center', justifyContent: 'center', gap: 2, cursor: 'pointer',
          background: isUtilitaActive ? 'rgba(255,255,255,0.18)' : open ? 'rgba(255,255,255,0.08)' : 'transparent',
          borderLeft: isUtilitaActive ? '3px solid var(--navy-accent)' : '3px solid transparent',
          transition: 'all 0.15s' }}>
        <span style={{ fontSize: 22, opacity: isUtilitaActive || open ? 1 : 0.5, lineHeight: 1 }}>⚙</span>
        <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', fontWeight: 600,
          color: isUtilitaActive ? 'var(--navy-accent)' : open ? 'rgba(255,255,255,0.7)' : 'rgba(255,255,255,0.45)',
          letterSpacing: '0.04em' }}>
          Utilità {open ? '▴' : '▾'}
        </span>
      </div>

      {/* Sotto-voci Utilità — espandibili */}
      {open && (
        <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'center',
          gap: 2, width: '100%', background: 'rgba(0,0,0,0.15)', paddingTop: 4, paddingBottom: 4 }}>
          {NAV_UTILITA.map(item => <NavItem key={item.to} {...item} small />)}
        </div>
      )}

      {/* Footer */}
      <div style={{ marginTop: 'auto' }}>
        <a href="/api/docs" target="_blank" rel="noreferrer" title="API Docs"
          style={{ width: 58, height: 36, display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, color: 'rgba(255,255,255,0.2)', textDecoration: 'none', borderRadius: 8, transition: 'color 0.15s' }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--navy-accent)'}
          onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.2)'}>
          ⬡
        </a>
      </div>

      <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}`}</style>
    </nav>
  )
}
