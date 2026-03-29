// pages/InvioMacchina.jsx — Invia programmi NC alla macchina CNC
import { useState, useEffect, useRef } from 'react'
import { api } from '../api/client'

export default function InvioMacchina() {
  const [ip,       setIp]       = useState('10.95.20.29')
  const [port,     setPort]     = useState(9999)
  const [progetto, setProgetto] = useState('')
  const [files,    setFiles]    = useState([])   // File objects
  const [check,    setCheck]    = useState(null)  // CheckResponse
  const [results,  setResults]  = useState([])   // InvioResult[]
  const [status,   setStatus]   = useState(null)  // {type, msg}
  const [checking, setChecking] = useState(false)
  const [sending,  setSending]  = useState(false)
  const [editingCfg, setEditingCfg] = useState(false)
  const fileRef = useRef()

  // Carica config al mount
  useEffect(() => {
    api.getMachineConfig()
      .then(r => { setIp(r.ip); setPort(r.port) })
      .catch(() => {})
  }, [])

  const saveCfg = async () => {
    try {
      await api.setMachineConfig({ ip, port: Number(port) })
      setEditingCfg(false)
      setStatus({ type: 'ok', msg: `Configurazione salvata: ${ip}:${port}` })
    } catch (e) {
      setStatus({ type: 'err', msg: e.message })
    }
  }

  const addFiles = (newFiles) => {
    const valid = Array.from(newFiles).filter(f => /\.(mpf|nc|spf)$/i.test(f.name))
    if (!valid.length) return
    setFiles(prev => {
      const names = new Set(prev.map(f => f.name))
      return [...prev, ...valid.filter(f => !names.has(f.name))]
    })
    setCheck(null); setResults([])
  }

  const removeFile = (name) => {
    setFiles(prev => prev.filter(f => f.name !== name))
    setCheck(null); setResults([])
  }

  const doCheck = async () => {
    if (!progetto.trim()) { setStatus({ type: 'warn', msg: 'Inserisci il nome cartella' }); return }
    if (!files.length)    { setStatus({ type: 'warn', msg: 'Aggiungi almeno un file' }); return }
    setChecking(true); setCheck(null); setResults([]); setStatus(null)
    try {
      const r = await api.checkMacchina(progetto.trim(), files.map(f => f.name))
      setCheck(r)
      if (!r.reachable) setStatus({ type: 'err', msg: `Server non raggiungibile: ${r.error}` })
      else setStatus({ type: 'ok', msg: `Connesso — ${r.esistenti.length} file già presenti` })
    } catch (e) {
      setStatus({ type: 'err', msg: e.message })
    } finally { setChecking(false) }
  }

  const doSend = async () => {
    if (!check?.reachable) return
    setSending(true); setResults([]); setStatus(null)
    try {
      const r = await api.inviaMacchina(progetto.trim(), files)
      setResults(r.risultati)
      if (r.n_err === 0)
        setStatus({ type: 'ok', msg: `✓ ${r.n_ok} file inviati con successo` })
      else
        setStatus({ type: 'warn', msg: `${r.n_ok} inviati, ${r.n_err} errori` })
    } catch (e) {
      setStatus({ type: 'err', msg: e.message })
    } finally { setSending(false) }
  }

  const doSendBatch = async () => {
    if (!check?.reachable) return
    setSending(true); setResults([]); setStatus(null)
    try {
      const r = await api.inviaBatch(progetto.trim(), files)
      setResults(r.risultati)
      if (r.n_err === 0)
        setStatus({ type: 'ok', msg: `⚡ ${r.n_ok} file inviati in batch (TransferAutom avviato)` })
      else
        setStatus({ type: 'warn', msg: `${r.n_ok} inviati, ${r.n_err} errori` })
    } catch (e) {
      setStatus({ type: 'err', msg: e.message })
    } finally { setSending(false) }
  }

  const fileState = (filename) => {
    if (results.length) {
      const r = results.find(r => r.filename === filename)
      if (r) return r.ok ? 'inviato' : 'errore'
    }
    if (check?.esistenti?.includes(filename)) return 'esistente'
    if (check?.reachable) return 'nuovo'
    return 'pending'
  }

  const stateColor = { nuovo: 'var(--green)', esistente: 'var(--amber)', inviato: 'var(--cyan)', errore: 'var(--red)', pending: 'var(--text-dim)' }
  const stateLabel = { nuovo: '🟢 Nuovo', esistente: '🟡 Da sovrascrivere', inviato: '✅ Inviato', errore: '❌ Errore', pending: '—' }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* Header */}
      <div>
        <h1 style={{ fontSize: 22, fontWeight: 800, letterSpacing: '-0.03em', marginBottom: 4 }}>
          Invia alla Macchina
        </h1>
        <div style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
          Trasferisce i programmi NC al MachineServer → DNCMachine → NCU Siemens
        </div>
      </div>

      {/* Config IP */}
      <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '14px 16px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: 12, flexWrap: 'wrap' }}>
          <span style={{ fontSize: 12, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>SERVER</span>

          {editingCfg ? (
            <>
              <input value={ip} onChange={e => setIp(e.target.value)}
                placeholder="IP macchina"
                style={{ padding: '6px 10px', borderRadius: 5, background: 'var(--bg-base)',
                         border: '1px solid var(--border)', color: 'var(--text-primary)',
                         fontSize: 13, fontFamily: 'var(--font-mono)', width: 140 }} />
              <input value={port} onChange={e => setPort(e.target.value)}
                placeholder="Porta"
                style={{ padding: '6px 10px', borderRadius: 5, background: 'var(--bg-base)',
                         border: '1px solid var(--border)', color: 'var(--text-primary)',
                         fontSize: 13, fontFamily: 'var(--font-mono)', width: 70 }} />
              <button onClick={saveCfg} style={{ padding: '6px 14px', borderRadius: 5, cursor: 'pointer',
                background: 'var(--cyan-glow)', border: '1px solid rgba(0,212,255,0.3)',
                color: 'var(--cyan)', fontSize: 12, fontWeight: 600 }}>
                Salva
              </button>
              <button onClick={() => setEditingCfg(false)} style={{ padding: '6px 12px', borderRadius: 5, cursor: 'pointer',
                background: 'var(--bg-hover)', border: '1px solid var(--border)',
                color: 'var(--text-secondary)', fontSize: 12 }}>
                Annulla
              </button>
            </>
          ) : (
            <>
              <span style={{ fontFamily: 'var(--font-mono)', fontSize: 13, color: 'var(--cyan)' }}>
                {ip}:{port}
              </span>
              <button onClick={() => setEditingCfg(true)} style={{ padding: '4px 10px', borderRadius: 4, cursor: 'pointer',
                background: 'transparent', border: '1px solid var(--border)',
                color: 'var(--text-dim)', fontSize: 11 }}>
                ✎ Modifica
              </button>
            </>
          )}
        </div>
      </div>

      {/* Cartella destinazione */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
        <span style={{ fontSize: 13, color: 'var(--text-secondary)', whiteSpace: 'nowrap' }}>
          Cartella NC:
        </span>
        <input value={progetto} onChange={e => setProgetto(e.target.value)}
          placeholder="es. 4349_0221  (diventa sottocartella nella macchina)"
          style={{ flex: 1, padding: '8px 12px', borderRadius: 6, background: 'var(--bg-card)',
                   border: '1px solid var(--border)', color: 'var(--text-primary)',
                   fontSize: 13, fontFamily: 'var(--font-mono)', outline: 'none' }} />
        {check?.dest_dir && (
          <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', whiteSpace: 'nowrap' }}>
            → {check.dest_dir}
          </span>
        )}
      </div>

      {/* Drop zone */}
      <div
        onClick={() => fileRef.current?.click()}
        onDragOver={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--cyan)' }}
        onDragLeave={e => { e.currentTarget.style.borderColor = 'var(--border-bright)' }}
        onDrop={e => { e.preventDefault(); e.currentTarget.style.borderColor = 'var(--border-bright)'; addFiles(e.dataTransfer.files) }}
        style={{ border: '2px dashed var(--border-bright)', borderRadius: 8, padding: '20px',
                 textAlign: 'center', cursor: 'pointer', transition: 'border-color var(--t-fast)' }}>
        <input ref={fileRef} type="file" accept=".mpf,.nc,.spf" multiple
          style={{ display: 'none' }} onChange={e => addFiles(e.target.files)} />
        <div style={{ fontSize: 22, marginBottom: 6 }}>📁</div>
        <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
          Trascina file MPF/NC/SPF o <span style={{ color: 'var(--cyan)' }}>clicca per scegliere</span>
        </div>
      </div>

      {/* Tabella file */}
      {files.length > 0 && (
        <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 10, overflow: 'hidden' }}>
          <table style={{ width: '100%', borderCollapse: 'collapse' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)', background: 'var(--bg-panel)' }}>
                {['File', 'Dimensione', 'Stato', ''].map(h => (
                  <th key={h} style={{ padding: '8px 14px', textAlign: 'left', fontSize: 11,
                                       fontFamily: 'var(--font-mono)', color: 'var(--text-dim)',
                                       fontWeight: 600, textTransform: 'uppercase', letterSpacing: '0.08em' }}>
                    {h}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {files.map(f => {
                const state = fileState(f.name)
                const isMain = f.name.toUpperCase().includes('MAIN') || f.name.startsWith('0_')
                return (
                  <tr key={f.name} style={{ borderBottom: '1px solid var(--border)' }}
                    onMouseEnter={e => e.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={e => e.currentTarget.style.background = 'transparent'}>
                    <td style={{ padding: '9px 14px', fontSize: 13, fontFamily: 'var(--font-mono)',
                                 color: isMain ? 'var(--cyan)' : 'var(--text-primary)' }}>
                      {isMain ? '⭐ ' : '📄 '}{f.name}
                    </td>
                    <td style={{ padding: '9px 14px', fontSize: 12, fontFamily: 'var(--font-mono)',
                                 color: 'var(--text-dim)' }}>
                      {(f.size / 1024).toFixed(1)} KB
                    </td>
                    <td style={{ padding: '9px 14px', fontSize: 12, color: stateColor[state] }}>
                      {stateLabel[state]}
                      {state === 'errore' && results.find(r => r.filename === f.name)?.msg && (
                        <span style={{ fontSize: 10, color: 'var(--red)', marginLeft: 8 }}>
                          {results.find(r => r.filename === f.name)?.msg}
                        </span>
                      )}
                    </td>
                    <td style={{ padding: '9px 14px', textAlign: 'right' }}>
                      <button onClick={() => removeFile(f.name)}
                        style={{ background: 'transparent', border: 'none', cursor: 'pointer',
                                 color: 'var(--text-dim)', fontSize: 14, padding: '2px 6px' }}>
                        ✕
                      </button>
                    </td>
                  </tr>
                )
              })}
            </tbody>
          </table>
        </div>
      )}

      {/* Status message */}
      {status && (
        <div style={{
          padding: '10px 14px', borderRadius: 6, fontSize: 13,
          background: status.type === 'ok' ? 'rgba(0,255,136,0.07)' :
                      status.type === 'err' ? 'rgba(255,68,85,0.08)' : 'rgba(255,179,0,0.08)',
          border: `1px solid ${status.type === 'ok' ? 'rgba(0,255,136,0.2)' :
                               status.type === 'err' ? 'rgba(255,68,85,0.25)' : 'rgba(255,179,0,0.25)'}`,
          color: status.type === 'ok' ? 'var(--green)' :
                 status.type === 'err' ? 'var(--red)' : 'var(--amber)',
        }}>
          {status.msg}
        </div>
      )}

      {/* Azioni */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'center' }}>
        <button onClick={doCheck} disabled={checking || sending}
          style={{ padding: '10px 20px', borderRadius: 6, cursor: checking ? 'not-allowed' : 'pointer',
                   background: 'var(--bg-card)', border: '1px solid var(--border-bright)',
                   color: 'var(--text-secondary)', fontSize: 13, fontWeight: 600 }}>
          {checking ? '⏳ Verifica...' : '🔍 Verifica connessione'}
        </button>

        <button onClick={doSend}
          disabled={!check?.reachable || sending || !files.length || !progetto.trim()}
          style={{
            padding: '10px 24px', borderRadius: 6, fontSize: 13, fontWeight: 700,
            cursor: (!check?.reachable || sending) ? 'not-allowed' : 'pointer',
            background: check?.reachable && !sending ? 'rgba(0,255,136,0.12)' : 'var(--bg-hover)',
            border: `1px solid ${check?.reachable && !sending ? 'rgba(0,255,136,0.3)' : 'var(--border)'}`,
            color: check?.reachable && !sending ? 'var(--green)' : 'var(--text-dim)',
            transition: 'all var(--t-fast)',
          }}>
          {sending ? '⏳ Invio in corso...' : `📤 Invia ${files.length ? files.length + ' file' : ''}`}
        </button>

        <button onClick={doSendBatch}
          disabled={!check?.reachable || sending || !files.length || !progetto.trim()}
          title="Invia tutti i file in una sola connessione — molto più veloce per batch grandi"
          style={{
            padding: '10px 24px', borderRadius: 6, fontSize: 13, fontWeight: 700,
            cursor: (!check?.reachable || sending) ? 'not-allowed' : 'pointer',
            background: check?.reachable && !sending ? 'rgba(0,180,255,0.12)' : 'var(--bg-hover)',
            border: `1px solid ${check?.reachable && !sending ? 'rgba(0,180,255,0.4)' : 'var(--border)'}`,
            color: check?.reachable && !sending ? '#38bdf8' : 'var(--text-dim)',
            transition: 'all var(--t-fast)',
          }}>
          {sending ? '⏳ Invio in corso...' : `⚡ Batch ${files.length ? '(' + files.length + ')' : ''}`}
        </button>

        {files.length > 0 && (
          <button onClick={() => { setFiles([]); setCheck(null); setResults([]); setStatus(null) }}
            style={{ padding: '10px 16px', borderRadius: 6, cursor: 'pointer',
                     background: 'transparent', border: '1px solid var(--border)',
                     color: 'var(--text-dim)', fontSize: 12 }}>
            Reset
          </button>
        )}

        <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginLeft: 'auto' }}>
          {files.length} file selezionati
        </span>
      </div>

      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
