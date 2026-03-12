// components/UI.jsx — Componenti riutilizzabili

export function Loader({ text = 'Caricamento...' }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '24px 0', color: 'var(--text-secondary)' }}>
      <div className="spinner" />
      <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13 }}>{text}</span>
    </div>
  )
}

export function EmptyState({ icon, title, subtitle }) {
  return (
    <div style={{ textAlign: 'center', padding: '48px 24px', color: 'var(--text-dim)' }}>
      <div style={{ fontSize: 40, marginBottom: 12 }}>{icon}</div>
      <div style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)', marginBottom: 4 }}>{title}</div>
      {subtitle && <div style={{ fontSize: 13 }}>{subtitle}</div>}
    </div>
  )
}

export function ErrorBanner({ message, onClose }) {
  if (!message) return null
  return (
    <div style={{
      background: 'rgba(255,68,85,0.1)', border: '1px solid rgba(255,68,85,0.3)',
      borderRadius: 'var(--radius-sm)', padding: '10px 14px', marginBottom: 16,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
      color: 'var(--red)', fontSize: 13, fontFamily: 'var(--font-mono)',
    }}>
      <span>⚠ {message}</span>
      {onClose && <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--red)', cursor: 'pointer', fontSize: 16 }}>✕</button>}
    </div>
  )
}

export function SuccessBanner({ message, onClose }) {
  if (!message) return null
  return (
    <div style={{
      background: 'rgba(0,255,136,0.08)', border: '1px solid rgba(0,255,136,0.25)',
      borderRadius: 'var(--radius-sm)', padding: '10px 14px', marginBottom: 16,
      display: 'flex', alignItems: 'center', justifyContent: 'space-between', gap: 12,
      color: 'var(--green)', fontSize: 13, fontFamily: 'var(--font-mono)',
    }}>
      <span>✓ {message}</span>
      {onClose && <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--green)', cursor: 'pointer', fontSize: 16 }}>✕</button>}
    </div>
  )
}

export function StatCard({ label, value, unit, color = 'var(--cyan)' }) {
  return (
    <div className="card" style={{ padding: '16px 20px', flex: 1 }}>
      <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6 }}>{label}</div>
      <div style={{ fontSize: 28, fontWeight: 800, color, fontFamily: 'var(--font-mono)', lineHeight: 1 }}>
        {value}
        {unit && <span style={{ fontSize: 14, fontWeight: 400, color: 'var(--text-secondary)', marginLeft: 4 }}>{unit}</span>}
      </div>
    </div>
  )
}

export function SectionHeader({ title, subtitle, action }) {
  return (
    <div style={{ display: 'flex', alignItems: 'flex-end', justifyContent: 'space-between', marginBottom: 16 }}>
      <div>
        <h2 style={{ fontSize: 18, fontWeight: 700, letterSpacing: '-0.02em' }}>{title}</h2>
        {subtitle && <p style={{ fontSize: 12, color: 'var(--text-secondary)', marginTop: 2 }}>{subtitle}</p>}
      </div>
      {action}
    </div>
  )
}
