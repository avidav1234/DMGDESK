// pages/AnalisiNC.jsx — Analisi multi-file NC con aggiungi-a-scaffale e generazione MAIN
import { useState, useRef, useCallback, useEffect } from 'react'
import { api } from '../api/client'

export default function AnalisiNC() {
  const [entries, setEntries] = useState([])
  const [dragging, setDragging] = useState(false)
  const inputRef = useRef()
  const idRef = useRef(0)

  // ── Stato modal "aggiungi a scaffale" ──────────────────
  const [modal, setModal] = useState(null)        // { alias } oppure null
  const [holderInfo, setHolderInfo] = useState(null)
  const [loadingInfo, setLoadingInfo] = useState(false)
  const [selectedHolder, setSelectedHolder] = useState('')
  const [addBusy, setAddBusy] = useState(false)
  const [addError, setAddError] = useState(null)
  const [globalSuccess, setGlobalSuccess] = useState(null)

  // ── Stato generazione MAIN ─────────────────────────────
  const [nomeCartella, setNomeCartella] = useState('')
  const [selectedIds, setSelectedIds] = useState(new Set())
  const [mainPreview, setMainPreview] = useState(null)
  const [mainBusy, setMainBusy] = useState(false)
  const [mainError, setMainError] = useState(null)
  const [showPreview, setShowPreview] = useState(false)
  const [cartelleRecenti, setCartelleRecenti] = useState([])

  // Percorso composto da 3 parti:
  // - radiceNc: parte fissa da config (es. "P:\DMG_DMC_160U") — salvata sul server
  // - commessa: inserita dall'operatore (es. "4348")
  // - posizione: inserita dall'operatore (es. "0221")
  // Risultato: radiceNc\commessa\posizione  →  P:\DMG_DMC_160U\4348\0221
  const [radiceNc, setRadiceNc] = useState(null)          // dal server, null = non configurato
  const [radiceNcInput, setRadiceNcInput] = useState('')
  const [radiceNcBusy, setRadiceNcBusy] = useState(false)
  const [commessa, setCommessa] = useState('')
  const [posizione, setPosizione] = useState('')
  const [fase, setFase] = useState('')

  // Percorso di salvataggio = radice + commessa + posizione [+ fase opzionale]
  const percorsoSalvataggio = radiceNcInput.trim() && commessa.trim() && posizione.trim()
    ? [radiceNcInput.trim().replace(/[\\/]+$/, ''), commessa.trim(), posizione.trim(), ...(fase.trim() ? [fase.trim()] : [])].join('\\')
    : ''

  // Al mount: carica radice NC dal server + cartelle recenti
  useEffect(() => {
    api.getPercorsoNc()
      .then(r => {
        if (r.percorso_nc_base) {
          setRadiceNc(r.percorso_nc_base)
          setRadiceNcInput(r.percorso_nc_base)
        }
      })
      .catch(() => {})
    api.cartelleRecenti()
      .then(r => setCartelleRecenti(r.cartelle || []))
      .catch(() => {})
  }, [])

  // Salva radice NC sul server (una volta sola)
  const handleSalvaRadiceNc = async () => {
    const val = radiceNcInput.trim().replace(/[\\/]+$/, '')
    if (!val) return
    setRadiceNcBusy(true)
    try {
      const r = await api.setPercorsoNc(val)
      setRadiceNc(r.percorso_nc_base)
    } catch (e) {
      setMainError(`Errore salvataggio: ${e.message}`)
    } finally {
      setRadiceNcBusy(false)
    }
  }
  const addFiles = useCallback((files) => {
    const valid = Array.from(files).filter(f => /\.(mpf|nc|spf)$/i.test(f.name))
    if (!valid.length) return
    setEntries(prev => [...prev, ...valid.map(f => ({
      id: ++idRef.current, file: f, status: 'pending', result: null, error: null
    }))])
  }, [])

  const removeEntry = (id) => setEntries(prev => prev.filter(e => e.id !== id))
  const clearAll = () => setEntries([])

  const analyzeAll = async () => {
    const pending = entries.filter(e => e.status === 'pending' || e.status === 'error')
    for (const entry of pending) {
      setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: 'analyzing' } : e))
      try {
        const result = await api.analizzaNC(entry.file)
        setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: 'done', result } : e))
      } catch (err) {
        setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: 'error', error: err.message } : e))
      }
    }
  }

  // ── Apertura modal per utensile mancante ──────────────
  const openModal = async (alias) => {
    setModal({ alias })
    setHolderInfo(null)
    setLoadingInfo(true)
    setAddError(null)
    setSelectedHolder('')
    try {
      const info = await api.infoAlias(alias)
      setHolderInfo(info)
      // Pre-seleziona il holder se l'alias ne ha già uno integrato
      if (!info.ha_holder && info.holders_disponibili.length > 0) {
        setSelectedHolder(info.holders_disponibili[0].alias_holder)
      }
    } catch (e) {
      setAddError(`Impossibile caricare info alias: ${e.message}`)
    } finally {
      setLoadingInfo(false)
    }
  }

  const closeModal = () => {
    setModal(null)
    setHolderInfo(null)
    setAddError(null)
    setSelectedHolder('')
  }

  // ── Conferma aggiunta a scaffale ──────────────────────
  const handleAggiungi = async () => {
    if (!modal) return
    setAddBusy(true)
    setAddError(null)
    try {
      const body = {
        alias: modal.alias,
        holder_override: holderInfo?.ha_holder ? null : (selectedHolder || null),
      }
      const result = await api.aggiungiAScaffale(body)

      // Rimuove l'alias dalla lista mancanti in tutti i file
      const aliasRimosso = modal.alias
      setEntries(prev => prev.map(e => {
        if (!e.result) return e
        const nuoviMancanti = (e.result.mancanti ?? []).filter(a => a !== aliasRimosso)
        return {
          ...e,
          result: {
            ...e.result,
            mancanti: nuoviMancanti,
            totale_mancanti: nuoviMancanti.length,
          },
        }
      }))

      setGlobalSuccess(`${result.alias_finale} aggiunto a scaffale`)
      closeModal()
    } catch (e) {
      setAddError(e.message)
    } finally {
      setAddBusy(false)
    }
  }

  // ── Derivati ──────────────────────────────────────────
  const done        = entries.filter(e => e.status === 'done')
  const conMancanti = done.filter(e => (e.result?.totale_mancanti ?? 0) > 0)
  const allMancanti = [...new Set(done.flatMap(e => e.result?.mancanti ?? []))]
  const hasPending  = entries.some(e => e.status === 'pending' || e.status === 'error')
  const isRunning   = entries.some(e => e.status === 'analyzing')

  // ── Helpers Genera MAIN ───────────────────────────────
  const toggleSelectEntry = (id) => {
    setSelectedIds(prev => {
      const s = new Set(prev)
      s.has(id) ? s.delete(id) : s.add(id)
      return s
    })
    setMainPreview(null)
    setMainError(null)
  }

  const buildProgrammi = () =>
    done
      .filter(e => selectedIds.has(e.id))
      .map(e => ({
        nome_file: e.file.name,
        utensile_principale: e.result?.utensili_nel_file?.[0]?.alias ?? '—',
        num_cambi: e.result?.totale_file ?? 1,
      }))

  const handleAnteprimaMain = async () => {
    if (!nomeCartella.trim()) { setMainError('Inserisci il nome della cartella in macchina'); return }
    const programmi = buildProgrammi()
    if (!programmi.length) { setMainError('Seleziona almeno un programma'); return }
    setMainBusy(true); setMainError(null)
    try {
      const res = await api.anteprimaMain({ nome_cartella: nomeCartella, programmi })
      setMainPreview(res)
      setShowPreview(true)
    } catch (e) {
      setMainError(e.message)
    } finally {
      setMainBusy(false)
    }
  }



  const handleGeneraMain = async () => {
    if (!nomeCartella.trim()) { setMainError('Inserisci il nome della cartella (es. Fase-2)'); return }
    if (!percorsoSalvataggio.trim()) { setMainError('Inserisci il percorso base'); return }
    const programmi = buildProgrammi()
    if (!programmi.length) { setMainError('Seleziona almeno un programma'); return }
    setMainBusy(true); setMainError(null)
    try {
      const res = await api.salvaMain({
        nome_cartella: nomeCartella,
        percorso_cartella: percorsoSalvataggio,
        programmi,
      })
      setGlobalSuccess(`✓ ${res.nome_file} salvato in ${res.percorso_file}`)
      setShowPreview(false)
      api.cartelleRecenti().then(r => setCartelleRecenti(r.cartelle || [])).catch(() => {})
    } catch (e) {
      setMainError(e.message)
    } finally {
      setMainBusy(false)
    }
  }

  return (
    <div className="fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 20 }}>

      {/* ── Banner successo globale ── */}
      {globalSuccess && (
        <div style={{
          background: 'rgba(0,255,136,0.08)', border: '1px solid rgba(0,255,136,0.25)',
          borderRadius: 'var(--radius-sm)', padding: '10px 16px',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center',
          color: 'var(--green)', fontSize: 13, fontFamily: 'var(--font-mono)',
        }}>
          <span>✓ {globalSuccess}</span>
          <button onClick={() => setGlobalSuccess(null)} style={{ background: 'none', border: 'none', color: 'var(--green)', cursor: 'pointer', fontSize: 16 }}>✕</button>
        </div>
      )}

      {/* ── Dropzone + bottoni ── */}
      <div style={{ display: 'flex', gap: 12, alignItems: 'flex-start' }}>
        <div
          onClick={() => inputRef.current.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
          style={{
            flex: 1, border: `1px dashed ${dragging ? 'var(--cyan)' : 'var(--border-bright)'}`,
            borderRadius: 'var(--radius)', padding: '16px 20px',
            display: 'flex', alignItems: 'center', gap: 14,
            cursor: 'pointer',
            background: dragging ? 'var(--cyan-glow)' : 'var(--bg-card)',
            transition: 'all var(--t-med)',
          }}
        >
          <input ref={inputRef} type="file" accept=".mpf,.nc,.spf" multiple style={{ display: 'none' }}
            onChange={e => { addFiles(e.target.files); e.target.value = '' }} />
          <svg width="20" height="20" viewBox="0 0 20 20" fill="none" style={{ flexShrink: 0, color: 'var(--text-secondary)' }}>
            <path d="M10 3v10M7 6l3-3 3 3M3 15h14" stroke="currentColor" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round" />
          </svg>
          <div>
            <div style={{ fontSize: 13, fontWeight: 600 }}>Trascina i file NC</div>
            <div style={{ fontSize: 11, color: 'var(--text-secondary)', marginTop: 1 }}>.MPF · .NC · .SPF — più file insieme</div>
          </div>
        </div>
        {entries.length > 0 && (
          <>
            <button className="btn btn-primary" onClick={analyzeAll} disabled={!hasPending || isRunning} style={{ flexShrink: 0 }}>
              {isRunning ? <><Spinner small /> Analisi...</> : `Analizza (${entries.filter(e => e.status === 'pending' || e.status === 'error').length})`}
            </button>
            <button className="btn btn-ghost" onClick={clearAll} disabled={isRunning} style={{ flexShrink: 0 }}>Pulisci</button>
          </>
        )}
      </div>

      {/* ── Lista file con stato ── */}
      {entries.length > 0 && (
        <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
          {entries.map(e => {
            const n = e.result?.totale_mancanti ?? 0
            const color = e.status === 'analyzing' ? 'var(--text-dim)'
              : e.status === 'error' ? 'var(--red)'
              : e.status === 'done' && n > 0 ? 'var(--red)'
              : e.status === 'done' ? 'var(--green)'
              : 'var(--text-dim)'
            return (
              <div key={e.id} style={{
                display: 'flex', alignItems: 'center', gap: 7,
                padding: '5px 10px', background: 'var(--bg-card)',
                border: `1px solid ${e.status === 'done' && n > 0 ? 'rgba(255,68,85,0.3)' : 'var(--border)'}`,
                borderRadius: 'var(--radius-sm)', fontSize: 12,
              }}>
                {e.status === 'analyzing' ? <Spinner small />
                  : <div style={{ width: 6, height: 6, borderRadius: '50%', background: color, flexShrink: 0 }} />}
                <span className="mono" style={{ color: 'var(--text-primary)' }}>{e.file.name}</span>
                {e.status === 'done' && n > 0 && <span style={{ color: 'var(--red)', fontWeight: 700 }}>{n}×</span>}
                <button onClick={() => removeEntry(e.id)} disabled={e.status === 'analyzing'}
                  style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', padding: '0 2px', fontSize: 14, lineHeight: 1, marginLeft: 2 }}>×</button>
              </div>
            )
          })}
        </div>
      )}

      {/* ── Risultati ── */}
      {done.length > 0 && (
        <div className="fade-in" style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 16, overflow: 'auto' }}>

          {/* Sommario */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 16, padding: '12px 16px', background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 'var(--radius)' }}>
            <span style={{ fontSize: 13, color: 'var(--text-secondary)' }}>
              <span className="mono" style={{ color: 'var(--cyan)', fontWeight: 700 }}>{done.length}</span> file ·{' '}
              <span className="mono" style={{ color: 'var(--text-primary)', fontWeight: 700 }}>{done.reduce((s, e) => s + (e.result?.totale_file ?? 0), 0)}</span> utensili ·{' '}
            </span>
            {allMancanti.length === 0
              ? <span style={{ color: 'var(--green)', fontWeight: 700, fontSize: 13 }}>✓ Tutti presenti in macchina</span>
              : <span style={{ color: 'var(--red)', fontWeight: 700, fontSize: 13 }}>⚠ {allMancanti.length} mancant{allMancanti.length === 1 ? 'e' : 'i'}</span>
            }
          </div>

          {/* Mancanti cliccabili */}
          {allMancanti.length > 0 && (
            <div style={{ background: 'rgba(255,68,85,0.06)', border: '1px solid rgba(255,68,85,0.2)', borderRadius: 'var(--radius)', padding: '14px 16px' }}>
              <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--red)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 6 }}>
                Utensili mancanti — clicca per aggiungere a scaffale
              </div>
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 6 }}>
                {allMancanti.map(a => (
                  <button
                    key={a}
                    onClick={() => openModal(a)}
                    title="Clicca per aggiungere a scaffale"
                    style={{
                      padding: '5px 14px',
                      background: 'rgba(255,68,85,0.10)',
                      border: '1px solid rgba(255,68,85,0.25)',
                      borderRadius: 'var(--radius-sm)',
                      fontSize: 13, fontFamily: 'var(--font-mono)',
                      color: 'var(--red)', fontWeight: 600,
                      cursor: 'pointer',
                      transition: 'all 0.15s',
                    }}
                    onMouseEnter={e => {
                      e.currentTarget.style.background = 'rgba(255,68,85,0.20)'
                      e.currentTarget.style.borderColor = 'rgba(255,68,85,0.5)'
                    }}
                    onMouseLeave={e => {
                      e.currentTarget.style.background = 'rgba(255,68,85,0.10)'
                      e.currentTarget.style.borderColor = 'rgba(255,68,85,0.25)'
                    }}
                  >
                    {a}
                    <span style={{ marginLeft: 6, fontSize: 10, opacity: 0.7 }}>+ scaffale</span>
                  </button>
                ))}
              </div>

              {/* Dettaglio per file */}
              <div style={{ marginTop: 12, display: 'flex', flexDirection: 'column', gap: 4 }}>
                {conMancanti.map(e => (
                  <div key={e.id} style={{ fontSize: 12, color: 'var(--text-secondary)' }}>
                    <span className="mono" style={{ color: 'var(--text-primary)' }}>{e.file.name}</span>
                    {' → '}
                    {(e.result?.mancanti ?? []).map(a => (
                      <span key={a} className="mono" style={{ color: 'var(--red)', marginRight: 6 }}>{a}</span>
                    ))}
                  </div>
                ))}
              </div>
            </div>
          )}

          {/* File OK */}
          {allMancanti.length > 0 && done.filter(e => (e.result?.totale_mancanti ?? 0) === 0).length > 0 && (
            <div style={{ fontSize: 12, color: 'var(--text-dim)' }}>
              <span style={{ color: 'var(--green)' }}>✓</span>{' '}
              {done.filter(e => (e.result?.totale_mancanti ?? 0) === 0).map(e => e.file.name).join(' · ')}
            </div>
          )}
        </div>
      )}

      {/* Stato vuoto */}
      {entries.length === 0 && (
        <div style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 10, color: 'var(--text-dim)' }}>
          <svg width="40" height="40" viewBox="0 0 40 40" fill="none" opacity="0.25">
            <rect x="8" y="4" width="24" height="32" rx="3" stroke="currentColor" strokeWidth="1.5" />
            <path d="M14 14h12M14 20h12M14 26h7" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" />
          </svg>
          <div style={{ fontSize: 13, color: 'var(--text-secondary)' }}>Trascina i file NC per iniziare</div>
        </div>
      )}

      {/* ── Sezione Genera MAIN ── */}
      {done.length > 0 && (
        <div className="fade-in" style={{
          background: 'var(--bg-card)', border: '1px solid var(--border)',
          borderRadius: 'var(--radius)', padding: '18px 20px',
          display: 'flex', flexDirection: 'column', gap: 14,
        }}>
          {/* Titolo sezione */}
          <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" style={{ color: 'var(--cyan)', flexShrink: 0 }}>
              <path d="M2 13V3l5 2.5L12 3v10l-5-2.5L2 13Z" stroke="currentColor" strokeWidth="1.3" strokeLinejoin="round" />
            </svg>
            <span style={{ fontSize: 13, fontWeight: 700, color: 'var(--text-primary)' }}>Genera File MAIN</span>
          </div>

          {/* Percorso + campi operatore */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: 10 }}>

            {/* Radice NC — sempre visibile, editabile inline */}
            <div style={{ display: 'flex', gap: 8, alignItems: 'center' }}>
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', width: 90, flexShrink: 0 }}>RADICE</span>
              <input type="text" value={radiceNcInput}
                onChange={e => setRadiceNcInput(e.target.value)}
                onBlur={handleSalvaRadiceNc}
                onKeyDown={e => e.key === 'Enter' && handleSalvaRadiceNc()}
                placeholder="P:\DMG_DMC_160U"
                style={{
                  background: 'transparent', border: 'none', borderBottom: '1px solid var(--border)',
                  padding: '2px 4px', color: 'var(--text-dim)', fontFamily: 'var(--font-mono)',
                  fontSize: 11, width: 260, outline: 'none',
                }}
                onFocus={e => e.target.style.borderBottomColor = 'var(--cyan)'}
              />
              {radiceNcBusy && <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>...</span>}
            </div>

            {/* Campi operatore: commessa + posizione */}
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', width: 90, flexShrink: 0 }}>COMMESSA</span>
                <input type="text" value={commessa}
                  onChange={e => { setCommessa(e.target.value.replace(/[^a-zA-Z0-9_\-]/g, '')); setMainError(null) }}
                  placeholder="4348"
                  style={{
                    background: 'var(--bg-base)', border: '1px solid var(--border-bright)',
                    borderRadius: 'var(--radius-sm)', padding: '6px 10px',
                    color: 'var(--text-primary)', fontFamily: 'var(--font-mono)',
                    fontSize: 13, fontWeight: 700, width: 100, outline: 'none',
                  }}
                  onFocus={e => e.target.style.borderColor = 'var(--cyan)'}
                  onBlur={e => e.target.style.borderColor = 'var(--border-bright)'}
                />
                <span style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>╲</span>
                <input type="text" value={posizione}
                  onChange={e => { setPosizione(e.target.value.replace(/[^a-zA-Z0-9_\-]/g, '')); setMainError(null) }}
                  placeholder="0221"
                  style={{
                    background: 'var(--bg-base)', border: '1px solid var(--border-bright)',
                    borderRadius: 'var(--radius-sm)', padding: '6px 10px',
                    color: 'var(--text-primary)', fontFamily: 'var(--font-mono)',
                    fontSize: 13, fontWeight: 700, width: 100, outline: 'none',
                  }}
                  onFocus={e => e.target.style.borderColor = 'var(--cyan)'}
                  onBlur={e => e.target.style.borderColor = 'var(--border-bright)'}
                />
                <span style={{ fontSize: 13, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>╲</span>
                <input type="text" value={fase}
                  onChange={e => { setFase(e.target.value.replace(/[^a-zA-Z0-9_\-]/g, '')); setMainError(null) }}
                  placeholder="Fase-2 (opz.)"
                  style={{
                    background: 'var(--bg-base)', border: '1px solid var(--border)',
                    borderRadius: 'var(--radius-sm)', padding: '6px 10px',
                    color: fase ? 'var(--text-primary)' : 'var(--text-dim)',
                    fontFamily: 'var(--font-mono)',
                    fontSize: 13, fontWeight: fase ? 700 : 400, width: 130, outline: 'none',
                  }}
                  onFocus={e => e.target.style.borderColor = 'var(--cyan)'}
                  onBlur={e => e.target.style.borderColor = 'var(--border)'}
                />
                {/* Cartelle recenti */}
                {cartelleRecenti.length > 0 && cartelleRecenti.slice(0, 5).map(c => {
                  const parts = c.replace(/\\/g, '/').split('/')
                  const pos = parts.at(-1) || ''
                  const com = parts.at(-2) || ''
                  return (
                    <button key={c} onClick={() => { setCommessa(com); setPosizione(pos); setMainError(null) }}
                      style={{
                        background: commessa === com && posizione === pos ? 'rgba(0,225,255,0.12)' : 'var(--bg-base)',
                        border: `1px solid ${commessa === com && posizione === pos ? 'var(--cyan)' : 'var(--border)'}`,
                        borderRadius: 'var(--radius-sm)', padding: '3px 10px',
                        fontSize: 11, fontFamily: 'var(--font-mono)',
                        color: commessa === com && posizione === pos ? 'var(--cyan)' : 'var(--text-secondary)',
                        cursor: 'pointer',
                      }}>
                      {com}\{pos}
                    </button>
                  )
                })}
              </div>

            {/* CARTELLA MACCHINA — nome WPD per gli EXTCALL */}
            <div style={{ display: 'flex', gap: 10, alignItems: 'center', flexWrap: 'wrap' }}>
              <label style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', flexShrink: 0, width: 90 }}>
                CARTELLA CNC
              </label>
              <input type="text" value={nomeCartella}
                onChange={e => { setNomeCartella(e.target.value); setMainPreview(null); setMainError(null) }}
                placeholder="es. Fase-3"
                style={{
                  background: 'var(--bg-base)', border: '1px solid var(--border-bright)',
                  borderRadius: 'var(--radius-sm)', padding: '6px 10px',
                  color: 'var(--text-primary)', fontFamily: 'var(--font-mono)',
                  fontSize: 13, fontWeight: 700, width: 160, outline: 'none',
                }}
                onFocus={e => e.target.style.borderColor = 'var(--cyan)'}
                onBlur={e => e.target.style.borderColor = 'var(--border-bright)'}
              />
              <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>
                nome WPD nella macchina (EXTCALL)
              </span>
            </div>

            {/* Preview percorso finale */}
            {percorsoSalvataggio && nomeCartella.trim() && (
              <div style={{ paddingLeft: 100, display: 'flex', gap: 8, alignItems: 'center', flexWrap: 'wrap' }}>
                <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)' }}>SALVERÀ →</span>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--green)' }}>
                  {percorsoSalvataggio}\0_MAIN_{nomeCartella.trim().toUpperCase()}.MPF
                </span>
              </div>
            )}

          </div>



          {/* Selezione programmi */}
          <div>
            <div style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.08em', marginBottom: 8 }}>
              SELEZIONA PROGRAMMI DA INCLUDERE
            </div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 5 }}>
              {done.map(e => {
                const n = e.result?.totale_mancanti ?? 0
                const sel = selectedIds.has(e.id)
                return (
                  <label key={e.id} style={{
                    display: 'flex', alignItems: 'center', gap: 10,
                    padding: '7px 12px',
                    background: sel ? 'rgba(0,225,255,0.06)' : 'var(--bg-base)',
                    border: `1px solid ${sel ? 'var(--cyan)' : 'var(--border)'}`,
                    borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                    transition: 'all 0.15s',
                  }}>
                    <input
                      type="checkbox"
                      checked={sel}
                      onChange={() => toggleSelectEntry(e.id)}
                      style={{ accentColor: 'var(--cyan)', width: 13, height: 13, flexShrink: 0 }}
                    />
                    <span className="mono" style={{ fontSize: 13, fontWeight: 600, flex: 1 }}>{e.file.name}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                      {e.result?.totale_file ?? 0} utensili
                    </span>
                    {n > 0 && <span style={{ fontSize: 11, color: 'var(--red)', fontWeight: 700 }}>⚠ {n} mancanti</span>}
                    {n === 0 && <span style={{ fontSize: 11, color: 'var(--green)' }}>✓ ok</span>}
                  </label>
                )
              })}
            </div>
          </div>

          {/* Errore generazione */}
          {mainError && (
            <div style={{ background: 'rgba(255,68,85,0.09)', border: '1px solid rgba(255,68,85,0.3)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>
              ⚠ {mainError}
            </div>
          )}

          {/* Bottoni azioni */}
          <div style={{ display: 'flex', gap: 8, flexWrap: 'wrap', alignItems: 'center' }}>
            <button
              className="btn btn-ghost"
              onClick={handleAnteprimaMain}
              disabled={mainBusy || selectedIds.size === 0 || !nomeCartella.trim()}
              style={{ fontSize: 12 }}
            >
              {mainBusy && !showPreview ? <><Spinner small /> Caricamento...</> : '👁 Anteprima'}
            </button>
            <button
              className="btn btn-primary"
              onClick={handleGeneraMain}
              disabled={mainBusy || selectedIds.size === 0 || !nomeCartella.trim() || !percorsoSalvataggio}
              style={{ fontSize: 12 }}
            >
              {mainBusy ? <><Spinner small /> Salvataggio...</> : `💾 Salva MAIN (${selectedIds.size} pgm)`}
            </button>
          </div>

          {/* Anteprima testo */}
          {showPreview && mainPreview && (
            <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--cyan)', letterSpacing: '0.08em' }}>
                  ANTEPRIMA: {mainPreview.nome_file}
                </span>
                <button onClick={() => setShowPreview(false)} style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: 14 }}>✕</button>
              </div>
              <pre style={{
                background: 'var(--bg-base)', border: '1px solid var(--border)',
                borderRadius: 'var(--radius-sm)', padding: '12px 14px',
                fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                lineHeight: 1.65, overflowX: 'auto', maxHeight: 300, overflowY: 'auto',
                margin: 0,
              }}>
                {mainPreview.contenuto}
              </pre>
              <button
                className="btn btn-primary"
                onClick={handleGeneraMain}
                disabled={mainBusy || !percorsoSalvataggio}
                style={{ alignSelf: 'flex-end', fontSize: 12 }}
              >
                {mainBusy ? <><Spinner small /> Salvataggio...</> : '💾 Salva MAIN'}
              </button>
            </div>
          )}
        </div>
      )}

      {/* ── Modal aggiungi a scaffale ── */}
      {modal && (
        <ModalAggiungiScaffale
          alias={modal.alias}
          holderInfo={holderInfo}
          loadingInfo={loadingInfo}
          selectedHolder={selectedHolder}
          onSelectHolder={setSelectedHolder}
          addError={addError}
          addBusy={addBusy}
          onConferma={handleAggiungi}
          onClose={closeModal}
        />
      )}
    </div>
  )
}

// ── Componente Modal ───────────────────────────────────────

function ModalAggiungiScaffale({
  alias, holderInfo, loadingInfo,
  selectedHolder, onSelectHolder,
  addError, addBusy,
  onConferma, onClose,
}) {
  const holderIntegrato = holderInfo?.ha_holder
  const holderCod = holderInfo?.holder_cod
  const bussolaCod = holderInfo?.bussola_cod
  const utensileBase = holderInfo?.utensile_base

  // Holder selezionato disponibile in inventario?
  const holderTarget = holderIntegrato ? holderCod : selectedHolder
  const infoHolderTarget = holderInfo?.holders_disponibili?.find(h => h.alias_holder === holderTarget)
  const holderDisponibile = !!infoHolderTarget
  const qtaHolder = infoHolderTarget?.quantita ?? 0

  // Bussola disponibile (se presente)
  const infoBussola = bussolaCod ? holderInfo?.bussole_disponibili?.find(b => b.codice_bussola === bussolaCod) : null
  const bussolaDisponibile = infoBussola ? infoBussola.quantita > 0 : true  // se no bussola, non è un problema

  const canConfirm = !loadingInfo && !addBusy && (
    holderIntegrato
      ? true                      // ha già holder, basta confermare
      : selectedHolder.length > 0 // deve scegliere un holder
  )

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.75)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200,
    }}>
      <div className="card fade-in" style={{ padding: 28, width: 460, display: 'flex', flexDirection: 'column', gap: 20 }}>

        {/* Header */}
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
          <div>
            <h3 style={{ fontSize: 15, fontWeight: 700, marginBottom: 4 }}>Aggiungi a Scaffale</h3>
            <p style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
              Utensile mancante rilevato dall'analisi NC
            </p>
          </div>
          <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: 20, lineHeight: 1, padding: 4 }}>✕</button>
        </div>

        {/* Alias completo */}
        <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '10px 14px' }}>
          <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.08em', marginBottom: 4 }}>ALIAS CNC</div>
          <span className="mono" style={{ fontSize: 14, fontWeight: 700, color: 'var(--cyan)' }}>{alias}</span>
        </div>

        {loadingInfo ? (
          <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', fontSize: 13 }}>
            <Spinner /> Analisi alias in corso...
          </div>
        ) : holderInfo && (
          <>
            {/* Breakdown utensile */}
            <div style={{ display: 'flex', flexDirection: 'column', gap: 8 }}>
              <BreakdownRow label="Utensile base" value={utensileBase} color="var(--text-primary)" />
              {holderCod && (
                <BreakdownRow
                  label="Holder"
                  value={holderCod}
                  color={holderDisponibile ? 'var(--green)' : 'var(--amber)'}
                  suffix={holderIntegrato
                    ? (holderDisponibile ? `✓ disponibile (×${qtaHolder})` : `⚠ non in inventario`)
                    : null}
                  subtext={infoHolderTarget?.tipo_desc}
                />
              )}
              {bussolaCod && (
                <BreakdownRow
                  label="Bussola idraulico"
                  value={bussolaCod}
                  color={bussolaDisponibile ? 'var(--green)' : 'var(--amber)'}
                  suffix={infoBussola
                    ? (bussolaDisponibile ? `✓ disponibile (×${infoBussola.quantita})` : '⚠ non in inventario')
                    : '⚠ non in inventario'}
                  subtext={infoBussola?.diametro}
                />
              )}
            </div>

            {/* Selezione holder se non integrato */}
            {!holderIntegrato && (
              <div>
                <label style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.08em', display: 'block', marginBottom: 8 }}>
                  SELEZIONA HOLDER DA INVENTARIO *
                </label>
                {holderInfo.holders_disponibili.length === 0 ? (
                  <div style={{ fontSize: 12, color: 'var(--amber)', fontFamily: 'var(--font-mono)', padding: '8px 0' }}>
                    ⚠ Nessun holder disponibile in inventario
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6 }}>
                    {holderInfo.holders_disponibili.map(h => (
                      <label key={h.alias_holder} style={{
                        display: 'flex', alignItems: 'center', gap: 10,
                        padding: '8px 12px',
                        background: selectedHolder === h.alias_holder ? 'rgba(0,225,255,0.08)' : 'var(--bg-base)',
                        border: `1px solid ${selectedHolder === h.alias_holder ? 'var(--cyan)' : 'var(--border)'}`,
                        borderRadius: 'var(--radius-sm)',
                        cursor: 'pointer',
                        transition: 'all 0.15s',
                      }}>
                        <input
                          type="radio"
                          name="holder"
                          value={h.alias_holder}
                          checked={selectedHolder === h.alias_holder}
                          onChange={() => onSelectHolder(h.alias_holder)}
                          style={{ accentColor: 'var(--cyan)' }}
                        />
                        <span className="mono" style={{ fontWeight: 700, fontSize: 13, color: 'var(--cyan)' }}>{h.alias_holder}</span>
                        <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1 }}>{h.tipo_desc}</span>
                        <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>×{h.quantita}</span>
                      </label>
                    ))}
                  </div>
                )}
              </div>
            )}

            {/* Anteprima alias finale (quando holder non integrato) */}
            {!holderIntegrato && selectedHolder && (
              <div style={{ background: 'rgba(0,225,255,0.06)', border: '1px solid rgba(0,225,255,0.2)', borderRadius: 'var(--radius-sm)', padding: '10px 14px' }}>
                <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginBottom: 4 }}>ALIAS FINALE</div>
                <span className="mono" style={{ fontSize: 14, fontWeight: 700, color: 'var(--cyan)' }}>
                  {alias}{selectedHolder}
                </span>
              </div>
            )}
          </>
        )}

        {/* Errore */}
        {addError && (
          <div style={{ background: 'rgba(255,68,85,0.1)', border: '1px solid rgba(255,68,85,0.3)', borderRadius: 'var(--radius-sm)', padding: '8px 12px', fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>
            ⚠ {addError}
          </div>
        )}

        {/* Azioni */}
        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button className="btn btn-ghost" onClick={onClose} disabled={addBusy}>
            Annulla
          </button>
          <button
            className="btn btn-primary"
            onClick={onConferma}
            disabled={!canConfirm}
            style={{ minWidth: 160 }}
          >
            {addBusy ? <><Spinner small /> Aggiunta...</> : '+ Aggiungi a Scaffale'}
          </button>
        </div>
      </div>
    </div>
  )
}

function BreakdownRow({ label, value, color, suffix, subtext }) {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
      <span style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.06em', width: 110, flexShrink: 0 }}>
        {label.toUpperCase()}
      </span>
      <span className="mono" style={{ fontSize: 13, fontWeight: 700, color }}>{value}</span>
      {subtext && <span style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{subtext}</span>}
      {suffix && <span style={{ fontSize: 11, color: 'var(--text-dim)', marginLeft: 'auto' }}>{suffix}</span>}
    </div>
  )
}

function Spinner({ small }) {
  const sz = small ? 10 : 14
  return (
    <div style={{
      width: sz, height: sz,
      border: `${small ? 1.5 : 2}px solid var(--border)`,
      borderTopColor: 'var(--cyan)',
      borderRadius: '50%',
      animation: 'spin 0.7s linear infinite',
      flexShrink: 0,
      display: 'inline-block',
    }} />
  )
}
