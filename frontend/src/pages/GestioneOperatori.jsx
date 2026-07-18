import { useEffect, useState, useCallback } from 'react'

// ── Pannello admin: gestione operatori ───────────────────────────────────────
// Elenco/aggiunta/rinomina/reset-PIN/ruolo/eliminazione degli operatori.
//
// Autorizzazione (Fase 1 — ruoli):
//   - se sei loggato con ruolo ADMIN, gestisci tutto col tuo PIN (il Bearer token
//     viene iniettato automaticamente dall'interceptor: niente master key);
//   - in alternativa, "break-glass": inserisci la master key (DMG_API_KEY), che
//     viene inviata come X-API-Key. Utile se nessun admin può loggarsi.
// La sola LETTURA della lista (/api/auth/operatori) è pubblica.

const MK_STORE = 'dmgdesk_master_key'

const C = {
  bg: '#f1f5f9', card: '#ffffff', border: '#e2e8f0', text: '#0f172a',
  muted: '#64748b', accent: '#1D5FAD', ok: '#16a34a', warn: '#b45309',
  err: '#dc2626', danger: '#dc2626', chip: '#334155', admin: '#7C3AED',
}

export default function GestioneOperatori() {
  const [operatori, setOperatori] = useState(null)   // null = loading
  const [sonoAdmin, setSonoAdmin] = useState(false)
  const [mioId, setMioId]         = useState(null)
  const [mioNome, setMioNome]     = useState('')
  const [masterKey, setMasterKey] = useState(() => {
    try {
      const s = sessionStorage.getItem(MK_STORE) || ''
      // Scarta valori palesemente non validi (autofill del browser): la master
      // key è una stringa ASCII stampabile senza spazi e corta.
      if (s && (!/^[\x21-\x7E]+$/.test(s) || s.length > 128)) { sessionStorage.removeItem(MK_STORE); return '' }
      return s
    } catch { return '' }
  })
  const [mkInput, setMkInput]     = useState('')
  const [nuovoNome, setNuovoNome] = useState('')
  const [msg, setMsg]             = useState(null)    // { tipo:'ok'|'err', testo }
  const [busy, setBusy]           = useState(false)
  const [ipStato, setIpStato]     = useState(null)    // { enabled, ips, tuo_ip, tentativi }
  const [nuovoIp, setNuovoIp]     = useState('')

  const carica = useCallback(async () => {
    try {
      const r = await fetch('/api/auth/operatori')
      const d = await r.json()
      setOperatori(d.operatori || [])
    } catch {
      setOperatori([])
      setMsg({ tipo: 'err', testo: 'Backend non raggiungibile' })
    }
  }, [])

  const chiMiSono = useCallback(async () => {
    try {
      const r = await fetch('/api/auth/me')
      if (!r.ok) { setSonoAdmin(false); return }
      const d = await r.json()
      const op = d?.operatore || {}
      setMioId(op.id || null)
      setMioNome(op.nome || '')
      setSonoAdmin(op.ruolo === 'admin')
    } catch { setSonoAdmin(false) }
  }, [])

  const caricaIp = useCallback(async () => {
    if (!sonoAdmin && !masterKey) { setIpStato(null); return }
    try {
      const headers = {}
      if (masterKey) headers['X-API-Key'] = masterKey
      const r = await fetch('/api/auth/admin/ip-allowlist', { headers })
      if (r.ok) setIpStato(await r.json())
    } catch { /* no-op */ }
  }, [sonoAdmin, masterKey])

  useEffect(() => { carica(); chiMiSono() }, [carica, chiMiSono])
  useEffect(() => { caricaIp() }, [caricaIp])

  function salvaMasterKey() {
    const k = mkInput.trim()
    if (k && (!/^[\x21-\x7E]+$/.test(k) || k.length > 128)) {
      setMsg({ tipo: 'err', testo: 'Valore non valido per la master key (attenzione all’autofill del browser)' })
      return
    }
    setMasterKey(k)
    try { k ? sessionStorage.setItem(MK_STORE, k) : sessionStorage.removeItem(MK_STORE) } catch { /* no-op */ }
    setMkInput('')
    setMsg(k ? { tipo: 'ok', testo: 'Master key impostata per questa sessione' } : null)
  }
  function dimenticaMasterKey() {
    setMasterKey('')
    try { sessionStorage.removeItem(MK_STORE) } catch { /* no-op */ }
  }

  // Header: Bearer token iniettato dall'interceptor; X-API-Key solo se break-glass.
  const adminCall = useCallback(async (path, body) => {
    setBusy(true); setMsg(null)
    try {
      const headers = { 'Content-Type': 'application/json' }
      if (masterKey) headers['X-API-Key'] = masterKey
      const r = await fetch(path, { method: 'POST', headers, body: JSON.stringify(body) })
      const d = await r.json().catch(() => ({}))
      if (!r.ok) throw new Error(typeof d.detail === 'string' ? d.detail : `Errore (HTTP ${r.status})`)
      return d
    } finally { setBusy(false) }
  }, [masterKey])

  const azione = (fn) => async (...a) => {
    try { await fn(...a); }
    catch (e) { setMsg({ tipo: 'err', testo: e.message }) }
  }

  const aggiungi = azione(async () => {
    const nome = nuovoNome.trim(); if (!nome) return
    await adminCall('/api/auth/admin/operatori', { nome })
    setNuovoNome(''); setMsg({ tipo: 'ok', testo: `Operatore "${nome}" creato` }); carica()
  })
  const rinomina = azione(async (op) => {
    const nuovo = window.prompt(`Nuovo nome per "${op.nome}":`, op.nome)
    if (nuovo == null || !nuovo.trim() || nuovo.trim() === op.nome) return
    await adminCall('/api/auth/admin/rinomina', { operatore_id: op.id, nuovo_nome: nuovo.trim() })
    setMsg({ tipo: 'ok', testo: 'Operatore rinominato' }); carica()
  })
  const azzeraPin = azione(async (op) => {
    if (!window.confirm(`Azzerare il PIN di "${op.nome}"?\nLo re-imposterà al prossimo accesso.`)) return
    await adminCall('/api/auth/admin/reset-pin', { operatore_id: op.id })
    setMsg({ tipo: 'ok', testo: `PIN di "${op.nome}" azzerato` }); carica()
  })
  const impostaPin = azione(async (op) => {
    const pin = window.prompt(`Imposta un PIN per "${op.nome}" (4-10 cifre):`, '')
    if (pin == null || !pin.trim()) return
    await adminCall('/api/auth/admin/reset-pin', { operatore_id: op.id, nuovo_pin: pin.trim() })
    setMsg({ tipo: 'ok', testo: `PIN di "${op.nome}" impostato` }); carica()
  })
  const cambiaRuolo = azione(async (op, ruolo) => {
    await adminCall('/api/auth/admin/ruolo', { operatore_id: op.id, ruolo })
    setMsg({ tipo: 'ok', testo: `"${op.nome}" ora è ${ruolo}` }); carica(); chiMiSono()
  })
  const elimina = azione(async (op) => {
    if (!window.confirm(`Eliminare l'operatore "${op.nome}"?\nLe sue sessioni verranno chiuse.`)) return
    await adminCall('/api/auth/admin/elimina', { operatore_id: op.id })
    setMsg({ tipo: 'ok', testo: `Operatore "${op.nome}" eliminato` }); carica()
  })

  // ── Allowlist IP ──
  const aggiungiIp = azione(async (ip) => {
    const v = (ip || '').trim(); if (!v) return
    await adminCall('/api/auth/admin/ip-allowlist/aggiungi', { ip: v })
    setNuovoIp(''); setMsg({ tipo: 'ok', testo: `IP ${v} aggiunto` }); caricaIp()
  })
  const rimuoviIp = azione(async (ip) => {
    await adminCall('/api/auth/admin/ip-allowlist/rimuovi', { ip })
    setMsg({ tipo: 'ok', testo: `IP ${ip} rimosso` }); caricaIp()
  })
  const abilitaIp = azione(async (flag) => {
    await adminCall('/api/auth/admin/ip-allowlist/abilita', { enabled: flag })
    setMsg({ tipo: 'ok', testo: flag ? 'Filtro IP attivato' : 'Filtro IP disattivato' }); caricaIp()
  })
  const pulisciTentativi = azione(async () => {
    await adminCall('/api/auth/admin/ip-allowlist/tentativi/pulisci', {})
    caricaIp()
  })
  // Attiva/disattiva con salvaguardia: prima di attivare, se il tuo IP non è in
  // lista, offri di aggiungerlo (per non perdere l'accesso da questo PC).
  const cambiaFiltro = async () => {
    const on = !ipStato?.enabled
    if (on && ipStato && !(ipStato.ips || []).includes(ipStato.tuo_ip)) {
      const add = window.confirm(
        `Il tuo IP ${ipStato.tuo_ip} non è nella lista.\n` +
        `Lo aggiungo prima di attivare il filtro? (consigliato: eviti di perdere l'accesso da questo PC)`)
      if (add) {
        try { await adminCall('/api/auth/admin/ip-allowlist/aggiungi', { ip: ipStato.tuo_ip }) }
        catch (e) { setMsg({ tipo: 'err', testo: e.message }); return }
      }
    }
    abilitaIp(on)
  }

  const haAccesso = sonoAdmin || !!masterKey

  return (
    <div style={{ padding: 24, background: C.bg, minHeight: '100%', color: C.text,
                  fontFamily: 'system-ui, sans-serif' }}>
      <div style={{ maxWidth: 760, margin: '0 auto' }}>
        <h1 style={{ fontSize: 22, fontWeight: 800, margin: '0 0 4px' }}>Gestione operatori</h1>
        <p style={{ color: C.muted, fontSize: 14, margin: '0 0 20px' }}>
          Ogni operatore imposta il proprio PIN al primo accesso. Gli <b>admin</b>
          gestiscono gli operatori e i ruoli.
        </p>

        {/* Accesso */}
        <div style={card}>
          {sonoAdmin ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
              <span style={{ color: C.admin, fontWeight: 800 }}>👤 {mioNome || 'admin'}</span>
              <span style={rBadge('admin')}>admin</span>
              <span style={{ color: C.muted, fontSize: 13 }}>— gestisci col tuo login</span>
            </div>
          ) : masterKey ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ color: C.ok, fontWeight: 700 }}>🔑 Master key attiva (break-glass)</span>
              <span style={{ flex: 1 }} />
              <button style={btn(C.chip)} onClick={dimenticaMasterKey}>Dimentica</button>
            </div>
          ) : (
            <div>
              <div style={{ fontWeight: 700, marginBottom: 6 }}>Serve un admin (o la master key)</div>
              <div style={{ color: C.muted, fontSize: 13, marginBottom: 10 }}>
                Se sei admin, gestisci direttamente col tuo login. Altrimenti, break-glass con la master key <code>DMG_API_KEY</code>.
              </div>
              <div style={{ display: 'flex', gap: 8 }}>
                <input type="password" value={mkInput} placeholder="Master key (DMG_API_KEY)"
                  name="dmg-master-key" autoComplete="new-password" spellCheck={false}
                  autoCorrect="off" autoCapitalize="off"
                  onChange={e => setMkInput(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && salvaMasterKey()} style={input} />
                <button style={btn(C.accent)} disabled={!mkInput.trim()} onClick={salvaMasterKey}>Sblocca</button>
              </div>
            </div>
          )}
        </div>

        {msg && (
          <div style={{ ...card, borderColor: msg.tipo === 'ok' ? C.ok : C.err,
                        color: msg.tipo === 'ok' ? C.ok : C.err, fontWeight: 600 }}>
            {msg.tipo === 'ok' ? '✓ ' : '⚠ '}{msg.testo}
          </div>
        )}

        {/* Lista */}
        <div style={card}>
          <div style={{ fontWeight: 700, marginBottom: 12 }}>
            Operatori {operatori ? `(${operatori.length})` : ''}
          </div>
          {operatori === null ? (
            <div style={{ color: C.muted }}>Caricamento…</div>
          ) : (
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              {operatori.map(op => (
                <div key={op.id} style={row}>
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 3 }}>
                    <span style={{ fontWeight: 700, display: 'flex', alignItems: 'center', gap: 8 }}>
                      {op.nome}
                      <span style={rBadge(op.ruolo)}>{op.ruolo || 'operatore'}</span>
                      {op.id === mioId && <span style={{ fontSize: 11, color: C.muted }}>(tu)</span>}
                    </span>
                    <span style={{ fontSize: 12, color: op.pin_impostato ? C.muted : C.warn }}>
                      {op.id} · {op.pin_impostato ? 'PIN impostato' : 'PIN da impostare al primo accesso'}
                    </span>
                  </div>
                  <span style={{ flex: 1 }} />
                  {haAccesso && (
                    <div style={{ display: 'flex', gap: 6, flexWrap: 'wrap', justifyContent: 'flex-end' }}>
                      {op.ruolo === 'admin'
                        ? <button style={btn(C.chip)} disabled={busy} onClick={() => cambiaRuolo(op, 'operatore')}>Rendi operatore</button>
                        : <button style={btn(C.admin)} disabled={busy} onClick={() => cambiaRuolo(op, 'admin')}>Rendi admin</button>}
                      <button style={btn(C.chip)}   disabled={busy} onClick={() => rinomina(op)}>Rinomina</button>
                      <button style={btn(C.chip)}   disabled={busy} onClick={() => impostaPin(op)}>Imposta PIN</button>
                      <button style={btn(C.warn)}   disabled={busy} onClick={() => azzeraPin(op)}>Azzera PIN</button>
                      <button style={btn(C.danger)} disabled={busy} onClick={() => elimina(op)}>Elimina</button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Aggiungi */}
        {haAccesso && (
          <div style={card}>
            <div style={{ fontWeight: 700, marginBottom: 8 }}>Aggiungi operatore</div>
            <div style={{ display: 'flex', gap: 8 }}>
              <input value={nuovoNome} placeholder="Nome operatore"
                onChange={e => setNuovoNome(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && aggiungi()} style={input} />
              <button style={btn(C.accent)} disabled={busy || !nuovoNome.trim()} onClick={aggiungi}>Aggiungi</button>
            </div>
            <div style={{ color: C.muted, fontSize: 12, marginTop: 8 }}>
              Nasce come <b>operatore</b>; comparirà nel login e imposterà il PIN al primo accesso.
            </div>
          </div>
        )}

        {/* Accesso per IP */}
        {haAccesso && (
          <div style={card}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, marginBottom: 8 }}>
              <div style={{ fontWeight: 700 }}>Accesso per IP</div>
              <span style={{ flex: 1 }} />
              <span style={{ fontSize: 12, fontWeight: 700, color: ipStato?.enabled ? C.ok : C.muted }}>
                {ipStato?.enabled ? '● ATTIVO' : '○ disattivo'}
              </span>
              <button style={btn(ipStato?.enabled ? C.warn : C.accent)} disabled={busy || !ipStato}
                onClick={cambiaFiltro}>
                {ipStato?.enabled ? 'Disattiva filtro' : 'Attiva filtro'}
              </button>
            </div>
            <div style={{ color: C.muted, fontSize: 12, marginBottom: 12 }}>
              Con il filtro attivo, solo i PC in lista usano DMG Desk; gli altri vedono
              solo la pagina di login. Un <b>admin</b> che fa login da un PC lo autorizza
              automaticamente. Localhost è sempre ammesso.
              {ipStato?.tuo_ip && <> Il tuo IP: <b style={{ fontFamily: 'monospace' }}>{ipStato.tuo_ip}</b>.</>}
            </div>

            {/* lista IP ammessi */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 6, marginBottom: 10 }}>
              {(ipStato?.ips || []).map(ip => (
                <div key={ip} style={row}>
                  <span style={{ fontWeight: 700, fontFamily: 'monospace' }}>{ip}</span>
                  {ip === ipStato?.tuo_ip && <span style={{ fontSize: 11, color: C.muted }}>(tu)</span>}
                  <span style={{ flex: 1 }} />
                  <button style={btn(C.danger)} disabled={busy} onClick={() => rimuoviIp(ip)}>Rimuovi</button>
                </div>
              ))}
              {(!ipStato?.ips || ipStato.ips.length === 0) && (
                <div style={{ color: C.muted, fontSize: 13 }}>Nessun IP in lista (con filtro attivo passerebbero tutti — safety).</div>
              )}
            </div>

            {/* aggiungi IP */}
            <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap' }}>
              <input value={nuovoIp} placeholder="IP o rete CIDR (es. 192.168.244.140 o 192.168.244.0/24)"
                onChange={e => setNuovoIp(e.target.value)}
                onKeyDown={e => e.key === 'Enter' && aggiungiIp(nuovoIp)} style={input} />
              <button style={btn(C.accent)} disabled={busy || !nuovoIp.trim()} onClick={() => aggiungiIp(nuovoIp)}>Aggiungi</button>
              {ipStato?.tuo_ip && !(ipStato.ips || []).includes(ipStato.tuo_ip) && (
                <button style={btn(C.chip)} disabled={busy} onClick={() => aggiungiIp(ipStato.tuo_ip)}>Aggiungi il mio IP</button>
              )}
            </div>

            {/* tentativi bloccati */}
            {ipStato?.tentativi?.length > 0 && (
              <div style={{ marginTop: 14 }}>
                <div style={{ display: 'flex', alignItems: 'center', gap: 8, marginBottom: 6 }}>
                  <div style={{ fontWeight: 700, fontSize: 13 }}>Tentativi bloccati ({ipStato.tentativi.length})</div>
                  <span style={{ flex: 1 }} />
                  <button style={btn(C.chip)} disabled={busy} onClick={pulisciTentativi}>Pulisci</button>
                </div>
                <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                  {ipStato.tentativi.map(t => (
                    <div key={t.ip} style={row}>
                      <span style={{ fontWeight: 700, fontFamily: 'monospace' }}>{t.ip}</span>
                      <span style={{ fontSize: 12, color: C.muted }}>
                        {t.count}× · ultimo {String(t.ultimo || '').replace('T', ' ')} · {t.path}
                      </span>
                      <span style={{ flex: 1 }} />
                      <button style={btn(C.accent)} disabled={busy} onClick={() => aggiungiIp(t.ip)}>Autorizza</button>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  )
}

// ── stili ─────────────────────────────────────────────────────────────────────
const card = { background: '#fff', border: `1px solid ${C.border}`, borderRadius: 12, padding: 16, marginBottom: 16 }
const row = { display: 'flex', alignItems: 'center', gap: 12, padding: '10px 12px', background: '#f8fafc', border: `1px solid ${C.border}`, borderRadius: 10 }
const input = { flex: 1, padding: '10px 12px', borderRadius: 8, border: `1px solid ${C.border}`, fontSize: 14, outline: 'none' }
function btn(bg) { return { background: bg, color: '#fff', border: 'none', borderRadius: 8, padding: '8px 14px', fontSize: 13, fontWeight: 700, cursor: 'pointer' } }
function rBadge(ruolo) {
  const admin = ruolo === 'admin'
  return { fontSize: 11, fontWeight: 800, letterSpacing: '0.03em', padding: '2px 8px', borderRadius: 999,
           color: admin ? '#fff' : C.muted, background: admin ? C.admin : '#e2e8f0' }
}
