import { useState } from "react"
// UI.jsx — DMG Desk shared components

export function Loader() {
  return (
    <div style={{ display:'flex', alignItems:'center', justifyContent:'center', padding:40 }}>
      <div className="spinner" />
    </div>
  )
}

export function EmptyState({ icon='⬡', title='Nessun dato', subtitle='' }) {
  return (
    <div style={{ padding:40, textAlign:'center' }}>
      <div style={{ fontSize:28, marginBottom:10, opacity:.4 }}>{icon}</div>
      <div style={{ color:'var(--text-secondary)', fontSize:14, fontWeight:500 }}>{title}</div>
      {subtitle && <div style={{ color:'var(--text-dim)', fontSize:12, marginTop:6 }}>{subtitle}</div>}
    </div>
  )
}

export function ErrorBanner({ message, onClose }) {
  if (!message) return null
  return (
    <div style={{
      padding:'10px 14px', borderRadius:6,
      background:'#fef2f2', border:'1px solid #fca5a5',
      display:'flex', alignItems:'center', gap:10,
    }}>
      <span style={{ color:'var(--red)', fontSize:14 }}>✕</span>
      <span style={{ fontSize:13, color:'#991b1b', flex:1 }}>{message}</span>
      {onClose && <button onClick={onClose} style={{ background:'none', border:'none', cursor:'pointer', color:'#991b1b', fontSize:14 }}>×</button>}
    </div>
  )
}

export function SuccessBanner({ message, onClose }) {
  if (!message) return null
  return (
    <div style={{
      padding:'10px 14px', borderRadius:6,
      background:'#f0fdf4', border:'1px solid #86efac',
      display:'flex', alignItems:'center', gap:10,
    }}>
      <span style={{ color:'var(--green)', fontSize:14 }}>✓</span>
      <span style={{ fontSize:13, color:'#15803d', flex:1 }}>{message}</span>
      {onClose && <button onClick={onClose} style={{ background:'none', border:'none', cursor:'pointer', color:'#15803d', fontSize:14 }}>×</button>}
    </div>
  )
}

export function StatCard({ label, value, color, unit='' }) {
  return (
    <div style={{
      background:'var(--bg-panel)', border:'1px solid var(--border)',
      borderLeft:`3px solid ${color || 'var(--navy-700)'}`,
      borderRadius:'0 var(--radius-sm) var(--radius-sm) 0',
      padding:'10px 14px', minWidth:90,
    }}>
      <div style={{ fontSize:11, color:'var(--text-dim)', marginBottom:4 }}>{label}</div>
      <div style={{ fontSize:20, fontWeight:700, color: color || 'var(--text-primary)', lineHeight:1 }}>
        {value}<span style={{ fontSize:11, fontWeight:400, color:'var(--text-dim)', marginLeft:3 }}>{unit}</span>
      </div>
    </div>
  )
}

export function SectionHeader({ title, subtitle, action }) {
  return (
    <div style={{ display:'flex', alignItems:'flex-start', justifyContent:'space-between', marginBottom:4 }}>
      <div>
        <h1 style={{ fontSize:20, fontWeight:700, color:'var(--text-primary)', lineHeight:1.2 }}>{title}</h1>
        {subtitle && <p style={{ fontSize:12, color:'var(--text-dim)', marginTop:3 }}>{subtitle}</p>}
      </div>
      {action && <div>{action}</div>}
    </div>
  )
}

export function WearBar({ value }) {
  if (value == null) return <span style={{ color:'var(--text-dim)', fontSize:12 }}>—</span>
  const v = Math.round(value)
  const cls = v < 20 ? 'wear-crit' : v < 40 ? 'wear-warn' : 'wear-ok'
  const color = v < 20 ? 'var(--red)' : v < 40 ? 'var(--amber)' : 'var(--green)'
  return (
    <div style={{ display:'flex', alignItems:'center', gap:8 }}>
      <div className="wear-bar-wrap">
        <div className={`wear-bar ${cls}`} style={{ width:`${v}%` }} />
      </div>
      <span style={{ fontFamily:'var(--font-mono)', fontSize:11, color, minWidth:30 }}>{v}%</span>
    </div>
  )
}

export function PalletBadge({ numero, stato, programma, onClick, selected }) {
  const cfg = {
    in_lavorazione: { cls:'pallet-lav', label:'IN LAV.' },
    grezzo:         { cls:'pallet-gre', label:'GREZZO' },
    finito:         { cls:'pallet-fin', label:'FINITO' },
    vuoto:          { cls:'pallet-vuo', label:'VUOTO' },
    guasto:         { cls:'pallet-gua', label:'GUASTO' },
  }
  const { cls, label } = cfg[stato] || cfg.vuoto
  return (
    <div
      onClick={onClick}
      className={`pallet-badge ${cls}`}
      style={{
        cursor: onClick ? 'pointer' : 'default',
        width: '100%', minHeight:56, padding:'8px 4px',
        outline: selected ? '2px solid var(--navy-accent)' : 'none',
        outlineOffset: 2,
        transition: 'all var(--t-fast)',
      }}
    >
      <span style={{ fontSize:13, fontWeight:700 }}>P{numero}</span>
      <span style={{ fontSize:9, marginTop:2 }}>{label}</span>
      {programma && (
        <span style={{
          fontSize:8, marginTop:3, opacity:.75,
          maxWidth:70, overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap',
        }}>
          {programma.split('/').pop()?.replace('_MPF','') || ''}
        </span>
      )}
    </div>
  )
}

// ── Tooltip informativo ───────────────────────────────────────────────────────
export function InfoTooltip({ text, position = "top" }) {
  const [visible, setVisible] = useState(false)

  const posStyle = position === "top"
    ? { bottom: "calc(100% + 6px)", left: "50%", transform: "translateX(-50%)" }
    : position === "bottom"
    ? { top: "calc(100% + 6px)", left: "50%", transform: "translateX(-50%)" }
    : position === "right"
    ? { left: "calc(100% + 6px)", top: "50%", transform: "translateY(-50%)" }
    : { right: "calc(100% + 6px)", top: "50%", transform: "translateY(-50%)" }

  return (
    <span
      style={{ position: "relative", display: "inline-flex", alignItems: "center" }}
      onMouseEnter={() => setVisible(true)}
      onMouseLeave={() => setVisible(false)}
    >
      <span style={{
        display: "inline-flex", alignItems: "center", justifyContent: "center",
        width: 14, height: 14, borderRadius: "50%",
        background: "#e2e8f0", color: "#64748b",
        fontSize: 9, fontWeight: 800, cursor: "help",
        lineHeight: 1, userSelect: "none", flexShrink: 0,
      }}>?</span>
      {visible && (
        <span style={{
          position: "absolute",
          ...posStyle,
          background: "#1e293b",
          color: "#f1f5f9",
          fontSize: 11,
          lineHeight: 1.5,
          padding: "7px 10px",
          borderRadius: 6,
          whiteSpace: "pre-wrap",
          maxWidth: 260,
          zIndex: 9999,
          boxShadow: "0 4px 16px rgba(0,0,0,.25)",
          pointerEvents: "none",
        }}>
          {text}
        </span>
      )}
    </span>
  )
}
