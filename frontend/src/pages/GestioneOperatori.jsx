import { useEffect, useState, useCallback } from 'react'

// ── Pannello admin: gestione operatori ───────────────────────────────────────
// Elenco/aggiunta/rinomina/reset-PIN/eliminazione degli operatori.
// Le azioni sono protette dalla MASTER KEY (DMG_API_KEY): l'admin la inserisce
// qui (resta in sessionStorage per la sessione del tab) e viene inviata come
// header X-API-Key. Finché non c'è RBAC (Fase 2), "admin" = chi ha la master key.
//
// La sola LETTURA della lista (/api/auth/operatori) è pubblica; le mutazioni
// (/api/auth/admin/*) richiedono la master key e rispondono 503 se il backend
// non ha DMG_API_KEY configurata (cioè se la sicurezza non è ancora attiva).

const MK_STORE = 'dmgdesk_master_key'

const C = {
  bg: '#f1f5f9', card: '#ffffff', border: '#e2e8f0', text: '#0f172a',
  muted: '#64748b', accent: '#1D5FAD', ok: '#16a34a', warn: '#b45309',
  err: '#dc2626', danger: '#dc2626', chip: '#334155',
}

export default function GestioneOperatori() {
  const [operatori, setOperatori] = useState(null)   // null = loading
  const [masterKey, setMasterKey] = useState(() => {
    try { return sessionStorage.getItem(MK_STORE) || '' } catch { return '' }
  })
  const [mkInput, setMkInput]   = useState('')
  const [nuovoNome, setNuovoNome] = useState('')
  const [msg, setMsg]           = useState(null)      // { tipo:'ok'|'err', testo }
  const [busy, setBusy]         = useState(false)

  const carica = useCallback(async () => {
    try {
      const r = await fetch('/api/auth/operatori')
      if (!r.ok) throw new Error('HTTP ' + r.status)
      const d = await r.json()
      setOperatori(d.operatori || [])
    } catch {
      setOperatori([])
      setMsg({ tipo: 'err', testo: 'Backend non raggiungibile' })
    }
  }, [])

  useEffect(() => { carica() }, [carica])

  function salvaMasterKey() {
    const k = mkInput.trim()
    setMasterKey(k)
    try { k ? sessionStorage.setItem(MK_STORE, k) : sessionStorage.removeItem(MK_STORE) } catch { /* no-op */ }
    setMkInput('')
    setMsg(k ? { tipo: 'ok', testo: 'Master key impostata per questa sessione' } : null)
  }

  function dimenticaMasterKey() {
    setMasterKey('')
    try { sessionStorage.removeItem(MK_STORE) } catch { /* no-op */ }
    setMsg(null)
  }

  // Chiamata admin: header X-API-Key = master key. L'interceptor globale non
  // sovrascrive un X-API-Key già presente.
  const adminCall = useCallback(async (path, body) => {
    setBusy(true); setMsg(null)
    try {
      const r = await fetch(path, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-API-Key': masterKey },
        body: JSON.stringify(body),
      })
      const d = await r.json().catch(() => ({}))
      if (!r.ok) {
        const testo = typeof d.detail === 'string' ? d.detail : `Errore (HTTP ${r.status})`
        throw new Error(testo)
      }
      return d
    } finally {
      setBusy(false)
    }
  }, [masterKey])

  async function aggiungi() {
    const nome = nuovoNome.trim()
    if (!nome) return
    try {
      await adminCall('/api/auth/admin/operatori', { nome })
      setNuovoNome('')
      setMsg({ tipo: 'ok', testo: `Operatore "${nome}" creato` })
      carica()
    } catch (e) { setMsg({ tipo: 'err', testo: e.message }) }
  }

  async function rinomina(op) {
    const nuovo = window.prompt(`Nuovo nome per "${op.nome}":`, op.nome)
    if (nuovo == null || !nuovo.trim() || nuovo.trim() === op.nome) return
    try {
      await adminCall('/api/auth/admin/rinomina', { operatore_id: op.id, nuovo_nome: nuovo.trim() })
      setMsg({ tipo: 'ok', testo: 'Operatore rinominato' })
      carica()
    } catch (e) { setMsg({ tipo: 'err', testo: e.message }) }
  }

  async function azzeraPin(op) {
    if (!window.confirm(`Azzerare il PIN di "${op.nome}"?\nAl prossimo accesso lo re-imposterà.`)) return
    try {
      await adminCall('/api/auth/admin/reset-pin', { operatore_id: op.id })
      setMsg({ tipo: 'ok', testo: `PIN di "${op.nome}" azzerato` })
      carica()
    } catch (e) { setMsg({ tipo: 'err', testo: e.message }) }
  }

  async function impostaPin(op) {
    const pin = window.prompt(`Imposta un PIN per "${op.nome}" (4-10 cifre):`, '')
    if (pin == null || !pin.trim()) return
    try {
      await adminCall('/api/auth/admin/reset-pin', { operatore_id: op.id, nuovo_pin: pin.trim() })
      setMsg({ tipo: 'ok', testo: `PIN di "${op.nome}" impostato` })
      carica()
    } catch (e) { setMsg({ tipo: 'err', testo: e.message }) }
  }

  async function elimina(op) {
    if (!window.confirm(`Eliminare l'operatore "${op.nome}"?\nLe sue sessioni verranno chiuse.`)) return
    try {
      await adminCall('/api/auth/admin/elimina', { operatore_id: op.id })
      setMsg({ tipo: 'ok', testo: `Operatore "${op.nome}" eliminato` })
      carica()
    } catch (e) { setMsg({ tipo: 'err', testo: e.message }) }
  }

  const haChiave = !!masterKey

  return (
    <div style={{ padding: 24, background: C.bg, minHeight: '100%', color: C.text,
                  fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ maxWidth: 720, margin: '0 auto' }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, margin: '0 0 4px' }}>Gestione operatori</h1>
        <p style={{ color: C.muted, fontSize: 14, margin: '0 0 20px' }}>
          Crea, rinomina, resetta i PIN o elimina gli operatori. Ogni operatore
          imposta il proprio PIN al primo accesso. Le azioni richiedono la master key.
        </p>

        {/* Master key */}
        <div style={card}>
          {haChiave ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ color: C.ok, fontWeight: 700 }}>🔑 Master key attiva</span>
              <span style={{ color: C.muted, fontSize: 13 }}>(solo per questa sessione)</span>
              <span style={{ flex: 1 }} />
              <button style={btn(C.chip)} onClick={dimenticaMasterKey}>Dimentica</button>
            </div>
          ) : (
            <div>
              <div style={{ fontWeight: 700, marginBottom: 8 }}>Master key richiesta per le modifiche</div>
              <div style={{ display: 'flex', gap: 8 }}>
                <input
                  type="password" value={mkInput} placeholder="DMG_API_KEY"
                  onChange={e => setMkInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && salvaMasterKey()}
                  style={input} />
                <button style={btn(C.accent)} disabled={!mkInput.trim()} onClick={salvaMasterKey}>
                  Sblocca
                </button>
              </div>
              <div style={{ color: C.muted, fontSize: 12, marginTop: 8 }}>
                È la stessa chiave <code>DMG_API_KEY</code> del backend. Resta solo in questa
                scheda del browser, non viene salvata su disco.
              </div>
            </div>
          )}
        </div>

        {/* Messaggio */}
        {msg && (
          <div style={{ ...card, borderColor: msg.tipo === 'ok' ? C.ok : C.err,
                        color: msg.tipo === 'ok' ? C.ok : C.err, fontWeight: 600 }}>
            {msg.tipo === 'ok' ? '✓ ' : '⚠ '}{msg.testo}
          </div>
        )}

        {/* Lista operatori */}
        <div style={card}>
          <div style={{ fontWeight: 700, marginBottom: 12 }}>
            Operatori {operatori ? `(${operatori.length})` : ''}
          </div>
          {operatori === null ? (
            <div style={{ color: C.muted }}>Caricamento…</div>
          ) : operatori.length === 0 ? (
            <div style={{ color: C.muted }}>Nessun operatore.</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {operatori.map(op => (
                <div key={op.id} style={row}>
                  <div style={{ display: 'flex', flexDirection: 'column' }}>
                    <span style={{ fontWeight: 700 }}>{op.nome}</span>
                    <span style={{ fontSize: 12, color: op.pin_impostato ? C.muted : C.warn }}>
                      {op.id} · {op.pin_impostato ? 'PIN impostato' : 'PIN da impostare al primo accesso'}
                    </span>
                  </div>
                  <span style={{ flex: 1 }} />
                  {haChiave && (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap' }}>
                      <button style={btn(C.chip)}  disabled={busy} onClick={() => rinomina(op)}>Rinomina</button>
                      <button style={btn(C.chip)}  disabled={busy} onClick={() => impostaPin(op)}>Imposta PIN</button>
                      <button style={btn(C.warn)}  disabled={busy} onClick={() => azzeraPin(op)}>Azzera PIN</button>
                      <button style={btn(C.danger)} disabled={busy} onClick={() => elimina(op)}>Elimina</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Aggiungi operatore */}
        {haChiave && (
          <div style={card}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Aggiungi operatore</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input
                value={nuovoNome} placeholder="Nome operatore"
                onChange={e => setNuovoNome(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && aggiungi()}
                style={input} />
              <button style={btn(C.accent)} disabled={busy || !nuovoNome.trim()} onClick={aggiungi}>
                Aggiungi
              </button>
            </div>
            <div style={{ color: C.muted, fontSize: 12, marginTop: 8 }}>
              Il nuovo operatore comparirà nel login e imposterà il PIN al primo accesso.
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

// ── stili ─────────────────────────────────────────────────────────────────────
const card = {
  background: '#fff', border: `1px solid ${C.border}`, borderRadius: 12,
  padding: 16, marginBottom: 16,
}
const row = {
  display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px',
  background: '#f8fafc', border: `1px solid ${C.border}`, borderRadius: 10,
}
const input = {
  flex: 1, padding: '10px 12px', borderRadius: 8, border: `1px solid ${C.border}`,
  fontSize: 14, outline: 'none',
}
function btn(bg) {
  return {
    background: bg, color: '#fff', border: 'none', borderRadius: 8,
    padding: '8px 14px', fontSize: 13, fontWeight: 700, cursor: 'pointer',
  }
}
