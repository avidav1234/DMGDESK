// components/Sidebar.jsx
import { NavLink } from 'react-router-dom'

const NAV = [
  { to: '/macchina',        icon: '⚙',  label: 'In Macchina',     sub: 'Carosello CNC' },
  { to: '/scaffale',        icon: '📦', label: 'Scaffale',         sub: 'Assemblati' },
  { to: '/smontati',        icon: '🔧', label: 'Smontati',         sub: 'Archivio' },
  { to: '/holder-bussole',  icon: '🔩', label: 'Holder & Bussole', sub: 'Inventario' },
  { to: '/generatore',      icon: '⌨',  label: 'Generatore',       sub: 'Codici CNC' },
  { to: '/analisi-nc',      icon: '📄', label: 'Analisi NC',        sub: 'File MPF' },
]

export default function Sidebar() {
  return (
    <nav style={{
      width: 220,
      flexShrink: 0,
      background: 'var(--bg-panel)',
      borderRight: '1px solid var(--border)',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'hidden',
    }}>
      {/* Logo */}
      <div style={{
        padding: '20px 20px 16px',
        borderBottom: '1px solid var(--border)',
      }}>
        <div style={{ fontFamily: 'var(--font-mono)', fontSize: 10, color: 'var(--text-dim)', letterSpacing: '0.15em', textTransform: 'uppercase', marginBottom: 4 }}>
          DMG 160U
        </div>
        <div style={{ fontSize: 17, fontWeight: 800, letterSpacing: '-0.03em', color: 'var(--text-primary)' }}>
          Tool Manager
        </div>
        <div style={{
          marginTop: 8,
          display: 'inline-flex',
          alignItems: 'center',
          gap: 5,
          padding: '2px 8px',
          background: 'var(--cyan-glow)',
          border: '1px solid rgba(0,212,255,0.2)',
          borderRadius: 3,
          fontFamily: 'var(--font-mono)',
          fontSize: 10,
          color: 'var(--cyan)',
          letterSpacing: '0.05em',
        }}>
          <span style={{ width: 5, height: 5, borderRadius: '50%', background: 'var(--cyan)', display: 'inline-block', animation: 'pulse 2s ease infinite' }} />
          v14.0 LIVE
        </div>
      </div>

      {/* Nav items */}
      <div style={{ flex: 1, overflowY: 'auto', padding: '12px 0' }}>
        {NAV.map(({ to, icon, label, sub }) => (
          <NavLink
            key={to}
            to={to}
            style={({ isActive }) => ({
              display: 'flex',
              alignItems: 'center',
              gap: 12,
              padding: '10px 16px',
              textDecoration: 'none',
              transition: 'all var(--t-fast)',
              borderLeft: `2px solid ${isActive ? 'var(--cyan)' : 'transparent'}`,
              background: isActive ? 'var(--cyan-glow)' : 'transparent',
            })}
          >
            {({ isActive }) => (
              <>
                <span style={{ fontSize: 18, flexShrink: 0, opacity: isActive ? 1 : 0.7 }}>{icon}</span>
                <div>
                  <div style={{
                    fontSize: 13,
                    fontWeight: 600,
                    color: isActive ? 'var(--cyan)' : 'var(--text-secondary)',
                    transition: 'color var(--t-fast)',
                    lineHeight: 1.2,
                  }}>
                    {label}
                  </div>
                  <div style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                    {sub}
                  </div>
                </div>
              </>
            )}
          </NavLink>
        ))}
      </div>

      {/* Footer */}
      <div style={{ padding: '12px 16px', borderTop: '1px solid var(--border)' }}>
        <a href="/api/docs" target="_blank" rel="noreferrer" style={{
          display: 'flex', alignItems: 'center', gap: 8,
          fontSize: 11, color: 'var(--text-dim)', textDecoration: 'none',
          fontFamily: 'var(--font-mono)', transition: 'color var(--t-fast)',
        }}
        onMouseEnter={e => e.currentTarget.style.color = 'var(--cyan)'}
        onMouseLeave={e => e.currentTarget.style.color = 'var(--text-dim)'}
        >
          <span>⬡</span> API Docs →
        </a>
      </div>

      <style>{`
        @keyframes pulse {
          0%, 100% { opacity: 1; }
          50%       { opacity: 0.3; }
        }
      `}</style>
    </nav>
  )
}
