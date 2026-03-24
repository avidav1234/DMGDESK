import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/coda',           icon: '⬡',  label: 'Coda',    title: 'Coda lavorazione' },
  { to: '/progetti',       icon: '📋', label: 'Progetti',title: 'Gestione Progetti' },
  { to: '/analisi-nc',     icon: '📄', label: 'NC',       title: 'Analisi NC' },
  { to: '/macchina',       icon: '⚙',  label: 'Tool',     title: 'Utensili in macchina' },
  { to: '/magazzino',      icon: '🗄', label: 'Mag.',     title: 'Magazzino' },
  { to: '/scaffale',       icon: '📦', label: 'Scaff.',   title: 'Scaffale' },
  { to: '/smontati',       icon: '🔧', label: 'Smont.',   title: 'Smontati' },
  { to: '/holder-bussole', icon: '🔩', label: 'Holder',   title: 'Holder & Bussole' },
]

export default function Sidebar() {
  return (
    <nav style={{
      width: 72,
      flexShrink: 0,
      background: 'var(--navy-700)',
      display: 'flex',
      flexDirection: 'column',
      alignItems: 'center',
      paddingTop: 10,
      paddingBottom: 12,
      gap: 2,
      overflowY: 'auto',
    }}>
      {/* Logo */}
      <div style={{
        marginBottom: 12,
        display: 'flex',
        flexDirection: 'column',
        alignItems: 'center',
        gap: 2,
      }}>
        <div style={{
          width: 42, height: 42,
          background: 'rgba(255,255,255,0.15)',
          borderRadius: 10,
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          fontSize: 12, fontWeight: 800, color: '#fff',
          letterSpacing: '-0.02em',
        }}>
          DMG
        </div>
        <div style={{
          fontSize: 8, color: 'var(--navy-accent)',
          letterSpacing: '0.1em', fontFamily: 'var(--font-mono)',
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
            width: 58,
            height: 52,
            borderRadius: 10,
            display: 'flex',
            flexDirection: 'column',
            alignItems: 'center',
            justifyContent: 'center',
            gap: 3,
            textDecoration: 'none',
            transition: 'all 0.15s',
            background: isActive ? 'rgba(255,255,255,0.18)' : 'transparent',
            borderLeft: isActive ? '3px solid var(--navy-accent)' : '3px solid transparent',
            cursor: 'pointer',
          })}
        >
          {({ isActive }) => (
            <>
              <span style={{ fontSize: 22, opacity: isActive ? 1 : 0.5, lineHeight: 1 }}>{icon}</span>
              <span style={{
                fontSize: 9,
                fontFamily: 'var(--font-mono)',
                fontWeight: 600,
                color: isActive ? 'var(--navy-accent)' : 'rgba(255,255,255,0.45)',
                letterSpacing: '0.04em',
              }}>
                {label}
              </span>
            </>
          )}
        </NavLink>
      ))}

      {/* Footer */}
      <div style={{ marginTop: 'auto' }}>
        <a
          href="/api/docs"
          target="_blank"
          rel="noreferrer"
          title="API Docs"
          style={{
            width: 58, height: 36,
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 16, color: 'rgba(255,255,255,0.2)',
            textDecoration: 'none', borderRadius: 8,
            transition: 'color 0.15s',
          }}
          onMouseEnter={e => e.currentTarget.style.color = 'var(--navy-accent)'}
          onMouseLeave={e => e.currentTarget.style.color = 'rgba(255,255,255,0.2)'}
        >
          ⬡
        </a>
      </div>

      <style>{`@keyframes pulse{0%,100%{opacity:1}50%{opacity:.4}}`}</style>
    </nav>
  )
}
