import { useEffect, useState } from 'react'
import LoginPin from '../pages/LoginPin'
import { getSessionToken, clearSessionToken } from '../utils/apiAuth'

// ── Gate di autenticazione ───────────────────────────────────────────────────
// Avvolge tutta l'app.
//   1. /api/auth/status → auth attiva?  DISATTIVA → mostra i figli (come oggi).
//      ATTIVA → verifica il token (/api/auth/me). Valido → app; altrimenti login.
//   2. Auto-logout: alla scadenza della sessione (DMG_AUTH_SESSION_ORE, es. 8h)
//      un timer lato client fa logout automatico e riporta al login.
//   3. Allowlist IP: se /api/auth/me risponde 403, questo PC non è autorizzato →
//      schermata dedicata (la SPA e il login restano visibili da qualsiasi IP, ma
//      le API dati sono bloccate finché un admin non autorizza l'IP).
//
// Fail-safe: se /api/auth/status non risponde, NON blocca l'app dietro un login
// fantasma (mostra i figli). Evita che un glitch dello status renda l'app inusabile.

// Logout robusto e autonomo: invalida lato server (best-effort), pulisce il token
// e ricarica pulito → AuthGate rimonta, nessun token → login.
function faiLogout() {
  try { fetch('/api/auth/logout', { method: 'POST' }) } catch { /* best-effort */ }
  clearSessionToken()
  window.location.assign('/')
}

export default function AuthGate({ children }) {
  const [stato, setStato]     = useState('check')   // check | aperta | login | nonautorizzato
  const [nome, setNome]       = useState('')
  const [scadeMs, setScadeMs] = useState(null)       // timestamp scadenza sessione

  async function verifica() {
    let attiva = false
    try {
      const r = await fetch('/api/auth/status')
      if (r.ok) attiva = (await r.json()).auth_attiva === true
      else { setStato('aperta'); return }        // status non ok → non bloccare
    } catch {
      setStato('aperta'); return                 // backend giù → non bloccare
    }
    if (!attiva) { setStato('aperta'); return }

    if (!getSessionToken()) { setStato('login'); return }
    try {
      const r = await fetch('/api/auth/me')
      if (r.ok) {
        const d = await r.json()
        setNome(d?.operatore?.nome || '')
        if (d?.scade) setScadeMs(Date.parse(d.scade))
        setStato('aperta')
      } else if (r.status === 403) {
        // Token valido ma IP non autorizzato dall'allowlist.
        setStato('nonautorizzato')
      } else {
        clearSessionToken()
        setStato('login')
      }
    } catch {
      setStato('login')
    }
  }

  useEffect(() => { verifica() }, [])

  // Espone il logout globale (retro-compat + uso da altri componenti).
  useEffect(() => {
    window.dmgdeskLogout = faiLogout
    window.dmgdeskOperatore = () => nome
    return () => { delete window.dmgdeskLogout; delete window.dmgdeskOperatore }
  }, [nome])

  // Auto-logout alla scadenza della sessione (es. 8h).
  useEffect(() => {
    if (stato !== 'aperta' || !scadeMs) return
    const ms = scadeMs - Date.now()
    if (ms <= 0) { faiLogout(); return }
    const t = setTimeout(faiLogout, ms)
    return () => clearTimeout(t)
  }, [stato, scadeMs])

  if (stato === 'check') {
    return (
      <div style={{
        position: 'fixed', inset: 0, display: 'flex', alignItems: 'center',
        justifyContent: 'center', background: '#0f172a', color: '#94a3b8',
        fontFamily: 'system-ui, sans-serif',
      }}>Caricamento…</div>
    )
  }

  if (stato === 'nonautorizzato') {
    return (
      <div style={{
        position: 'fixed', inset: 0, display: 'flex', flexDirection: 'column',
        alignItems: 'center', justifyContent: 'center', gap: 14, padding: 24,
        background: '#0f172a', color: '#e2e8f0', textAlign: 'center',
        fontFamily: 'system-ui, sans-serif',
      }}>
        <div style={{ fontSize: 44 }}>🔒</div>
        <div style={{ fontSize: 20, fontWeight: 800 }}>Dispositivo non autorizzato</div>
        <div style={{ color: '#94a3b8', maxWidth: 460, lineHeight: 1.5 }}>
          Questo PC non è abilitato ad accedere a DMG Desk. Per autorizzarlo, un
          <b> amministratore</b> può semplicemente fare login da qui, oppure aggiungere
          l'IP di questo PC dal pannello <b>Operatori → Accesso per IP</b>.
        </div>
        <button onClick={faiLogout} style={{
          marginTop: 8, background: '#1D5FAD', color: '#fff', border: 'none',
          borderRadius: 10, padding: '10px 22px', fontSize: 14, fontWeight: 700, cursor: 'pointer',
        }}>Torna al login</button>
      </div>
    )
  }

  if (stato === 'login') {
    // Dopo il login ri-verifichiamo via /api/auth/me: un admin che si logga da un
    // PC non ancora ammesso viene auto-autorizzato (→ app); un operatore su PC
    // non autorizzato finisce sulla schermata dedicata.
    return <LoginPin onAuth={() => { setStato('check'); verifica() }} />
  }

  return children
}
