// Sidebar.jsx — DMG Desk, layout 2 (icone grandi)
import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/coda',        icon: '⬡',  label: 'Coda',    title: 'Coda lavorazione' },
  { to: '/stato',       icon: '⚡',  label: 'Stato',   title: 'Stato macchina' },
  { to: '/analisi-nc',  icon: '📄',  label: 'NC',      title: 'Analisi NC' },
  { to: '/macchina',    icon: '⚙',   label: 'Tool',    title: 'Utensili in macchina' },
  { to: '/magazzino',   icon: '🗄',  label: 'Mag.',    title: 'Magazzino' },
  { to: '/scaffale',    icon: '📦',  label: 'Scaff.',  title: 'Scaffale' },
  { to: '/smontati',    icon: '🔧',  label: 'Smont.',  title: 'Smontati' },
  { to: '/holder-bussole', icon: '🔩', label: 'Holder', title: 'Holder & Bussole' },
]

export default function Sidebar() {
  return (
    <nav style={{
      width: 64,
      flexShrink: 0,
      background: 'var(--navy-700)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      paddingTop: 12,
      paddingBottom: 12,
      gap: 2,
      overflowY: 'auto',
    }}>
      {/* Logo */}
      <div style={{
        marginBottom: 10,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
      }}>
        <div style={{
          width: 36, height: 36,
          background: 'rgba(255,255,255,0.15)',
          borderRadius: 8,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 11, fontWeight: 700, color: '#fff',
          letterSpacing: '-0.02em',
        }}>
          DMG
        </div>
        <div style={{
          fontSize: 7, color: 'var(--navy-accent)',
          letterSpacing: '0.08em', fontFamily: 'var(--font-mono)',
          animation: 'pulse 2s ease infinite',
        }}>
          LIVE
        </div>
      </div>

      {/* Nav items */}
      {NAV.map(({ to, icon, label, title }) => (
        <NavLink
          key={to}
          to={to}
          title={title}
          style={({ isActive }) => ({
            width: 48,
            height: 44,
            borderRadius: 8,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 2,
            textDecoration: 'none',
            transition: 'all var(--t-fast)',
            background: isActive ? 'rgba(255,255,255,0.18)' : 'transparent',
            borderLeft: isActive ? '2px solid var(--navy-accent)' : '2px solid transparent',
            cursor: 'pointer',
          })}
        >
          {({ isActive }) => (
            <>
              <span style={{ fontSize: 18, opacity: isActive ? 1 : 0.45 }}>{icon}</span>
              <span style={{
                fontSize: 8,
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                color: isActive ? 'var(--navy-accent)' : 'rgba(255,255,255,0.4)',
                letterSpacing: '0.04em',
              }}>
                {label}
              </span>
            </>
          )}
        </NavLink>
      ))}

      {/* Footer API docs */}
      <div style={{ marginTop: 'auto' }}>
        <a
          href="/api/docs"
          target="_blank"
          rel="noreferrer"
          title="API Docs"
          style={{
            width: 48, height: 32,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 14, color: 'rgba(255,255,255,0.25)',
            textDecoration: 'none', borderRadius: 6,
            transition: 'color var(--t-fast)',
          }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--navy-accent)'}
          onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.25)'}
        >
          ⬡
        </a>
      </div>

      <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}`}</style>
    </nav>
  )
}
