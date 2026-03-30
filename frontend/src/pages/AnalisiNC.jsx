// pages/AnalisiNC.jsx — Flow identico al desktop:
// 1. Aggiungi file → confronto automatico
// 2. Inserisci nome cartella → Genera MAIN
// 3. Invia tutto / Solo MAIN

import { useState, useRef, useCallback, useEffect } from 'react'
import { api } from '../api/client'
import { useNavigate } from 'react-router-dom'

// ── PercorsoPanel: collassabile, con proprio stato locale ──────────────────
function PercorsoPanel({ daProgetti, radiceNcInput, setRadiceNcInput, commessa, setCommessa,
  posizione, setPosizione, fase, setFase, cartelleRecenti, percorso, nomeCompleto,
  inputStyle, setMainError, onSaveRadice }) {
  const [aperto, setAperto] = useState(!daProgetti)
  const preview = percorso && nomeCompleto
  return (
    <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden' }}>
      {/* Header cliccabile */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '8px 14px',
        cursor: 'pointer', userSelect: 'none',
        background: preview ? 'rgba(21,128,61,0.06)' : 'transparent',
        borderBottom: aperto ? '1px solid var(--border)' : 'none' }}
        onClick={() => setAperto(v => !v)}>
        <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-dim)',
          fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', flex: 1 }}>
          PERCORSO SALVATAGGIO
        </span>
        {preview && !aperto && (
          <span style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: '#15803d',
            flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
            ✓ {commessa}\{posizione}
          </span>
        )}
        <span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{aperto ? '▴' : '▾'}</span>
      </div>
      {aperto && (
        <div style={{ padding: '10px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
          <input value={radiceNcInput}
            onChange={e => setRadiceNcInput(e.target.value)}
            onBlur={async () => { const v = radiceNcInput.trim().replace(/[\\/]+$/, ''); if (v) await onSaveRadice(v) }}
            placeholder="P:\DMG_DMC_160U"
            style={{ ...inputStyle, fontSize: 11, color: 'var(--text-dim)', width: '100%' }} />
          <div style={{ display: 'flex', gap: 6 }}>
            <input value={commessa}
              onChange={e => setCommessa(e.target.value.replace(/[^a-zA-Z0-9_-]/g,''))}
              placeholder="4348" style={{ ...inputStyle, width: '50%', fontWeight: 700 }} />
            <input value={posizione}
              onChange={e => setPosizione(e.target.value.replace(/[^a-zA-Z0-9_-]/g,''))}
              placeholder="0221" style={{ ...inputStyle, width: '50%', fontWeight: 700 }} />
          </div>
          <input value={fase}
            onChange={e => { setFase(e.target.value); setMainError(null) }}
            placeholder="Sottocartella (opz.)"
            style={{ ...inputStyle, width: '100%', fontSize: 10, color: 'var(--text-dim)' }}
            onFocus={e => e.target.style.borderColor = 'var(--cyan)'}
            onBlur={e => e.target.style.borderColor = 'var(--border)'} />
          {cartelleRecenti.length > 0 && (
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4 }}>
              {cartelleRecenti.slice(0,4).map(c => {
                const pts = c.replace(/\\/g,'/').split('/'); const pos=pts.at(-1)||''; const com=pts.at(-2)||''
                return (
                  <button key={c} onClick={() => { setCommessa(com); setPosizione(pos) }}
                    style={{ padding: '2px 8px', borderRadius: 4, fontSize: 10, fontFamily: 'var(--font-mono)', cursor: 'pointer',
                      background: commessa===com&&posizione===pos ? 'rgba(0,225,255,0.12)' : 'var(--bg-base)',
                      border: `1px solid ${commessa===com&&posizione===pos ? 'var(--cyan)' : 'var(--border)'}`,
                      color: commessa===com&&posizione===pos ? 'var(--cyan)' : 'var(--text-secondary)' }}>
                    {com}\{pos}
                  </button>
                )
              })}
            </div>
          )}
          {preview && (
            <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: '#15803d' }}>
              → {percorso}\0_MAIN_{nomeCompleto.toUpperCase()}.MPF
            </div>
          )}
        </div>
      )}
    </div>
  )
}

// ── Spinner ────────────────────────────────────────────────────────────────
function Spinner({ small }) {
  const sz = small ? 10 : 14
  return <div style={{ width: sz, height: sz, border: `${small?1.5:2}px solid var(--border)`, borderTopColor: 'var(--cyan)', borderRadius: '50%', animation: 'spin 0.7s linear infinite', flexShrink: 0, display: 'inline-block' }} />
}

// ── Badge stato utensile ───────────────────────────────────────────────────
function StatoBadge({ stato }) {
  const cfg = {
    ok:    { bg: 'rgba(22,163,74,0.10)',  color: '#15803d', label: '✓  OK'          },
    manca: { bg: 'rgba(220,38,38,0.10)',  color: '#dc2626', label: '✕  Mancante'    },
    disab: { bg: 'rgba(234,179,8,0.15)',  color: '#a16207', label: '⚠  Disabilitato' },
  }[stato] || { bg: 'transparent', color: 'var(--text-dim)', label: stato }
  return (
    <span style={{ padding: '2px 8px', borderRadius: 4, fontSize: 11,
      fontFamily: 'var(--font-mono)', fontWeight: 600,
      background: cfg.bg, color: cfg.color }}>{cfg.label}</span>
  )
}

export default function AnalisiNC() {
  // ── File e analisi ────────────────────────────────────────────────────────
  const [entries, setEntries]       = useState([])   // {id, file, status, result}
  const [dragging, setDragging]     = useState(false)
  const inputRef = useRef()
  const idRef    = useRef(0)

  // ── Stato confronto aggregato ─────────────────────────────────────────────
  const [fonteDb, setFonteDb]       = useState('')

  // ── Nome cartella (condiviso tra MAIN e invio) ───────────────────────────
  const [nomeCartella, setNomeCartella] = useState('')
  const [fase, setFase]                   = useState('')

  // ── Percorso salvataggio MAIN ─────────────────────────────────────────────
  const [radiceNcInput, setRadiceNcInput] = useState('')
  const [commessa, setCommessa]     = useState('')
  const [posizione, setPosizione]   = useState('')
  const [cartelleRecenti, setCartelleRecenti] = useState([])

  // nomeCompleto = solo nome cartella — la fase NON entra nel nome MAIN
  // né negli EXTCALL del NC. Serve solo per il percorso Windows.
  const nomeCompleto = nomeCartella.trim()

  // Percorso Windows: radice\commessa\posizione[\fase]
  const percorso = radiceNcInput.trim() && commessa.trim() && posizione.trim()
    ? [radiceNcInput.trim().replace(/[\\/]+$/, ''), commessa.trim(), posizione.trim(),
       ...(fase.trim() ? [fase.trim()] : [])].join('\\')
    : ''

  // ── MAIN ──────────────────────────────────────────────────────────────────
  const [mainBusy, setMainBusy]           = useState(false)
  const [mainError, setMainError]         = useState(null)
  const [mainGeneratoFile, setMainGeneratoFile] = useState(null)
  const [mainPreview, setMainPreview]     = useState(null)
  const [showPreview, setShowPreview]     = useState(false)

  // ── Invio ─────────────────────────────────────────────────────────────────
  const [machIp, setMachIp]           = useState('10.95.20.29')
  const [machPort, setMachPort]       = useState(9999)
  const [editingCfg, setEditingCfg]   = useState(false)
  const [checkResult, setCheckResult] = useState(null)
  const [invioResults, setInvioResults] = useState([])
  const [invioStatus, setInvioStatus] = useState(null)
  const [checking, setChecking]       = useState(false)
  const [sending, setSending]         = useState(false)

  // ── Modal scaffale ────────────────────────────────────────────────────────
  const [modal, setModal]                       = useState(null)
  const [holderInfo, setHolderInfo]             = useState(null)
  const [loadingInfo, setLoadingInfo]           = useState(false)
  const [selectedHolder, setSelectedHolder]     = useState('')
  const [addBusy, setAddBusy]                   = useState(false)
  const [addError, setAddError]                 = useState(null)
  const [globalSuccess, setGlobalSuccess]       = useState(null)

  // Stato per lancio da progetto
  const [lancioProgetto, setLancioProgetto] = useState(null)
  const [lancioLoading,  setLancioLoading]  = useState(false)
  const [lancioError,    setLancioError]    = useState(null)
  // CTA guidate — passo successivo
  const navigate = useNavigate()
  const [ctaStep, setCtaStep] = useState(null) // null | 'invia' | 'coda'

  useEffect(() => {
    api.getPercorsoNc().then(r => { if (r.percorso_nc_base) setRadiceNcInput(r.percorso_nc_base) }).catch(() => {})
    api.cartelleRecenti().then(r => setCartelleRecenti(r.cartelle || [])).catch(() => {})
    api.getMachineConfig().then(r => { setMachIp(r.ip); setMachPort(r.port) }).catch(() => {})

    // Leggi lancio da progetto (sessionStorage) e carica i file da disco
    const caricaDaDisco = async () => {
      try {
        const raw = sessionStorage.getItem('dmgdesk_lancio_nc')
        if (raw) {
          // NON rimuovere qui — serve a handleGeneraMain per aggiornare gli stati
          const lancio = JSON.parse(raw)
          setLancioProgetto(lancio)
          if (lancio.nomeCartella) {
            setNomeCartella(lancio.nomeCartella)
            // Auto-split: 4297_0005 → commessa=4297, posizione=0005
            const parts = lancio.nomeCartella.split('_')
            if (parts.length >= 2 && /^\d+$/.test(parts[0])) {
              setCommessa(parts[0])
              setPosizione(parts[1])
            }
          }

          // Carica e analizza i file dal disco tramite API
          if (lancio.mpfFiles?.length) {
            setLancioLoading(true)
            try {
              const res = await fetch('/api/analisi-nc/analizza-da-disco', {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ filenames: lancio.mpfFiles })
            })
            const data = await res.json()

            // Aggiungi ogni risultato come entry nella lista
            for (const r of data.risultati || []) {
              const id = ++idRef.current
              if (!r.trovato || !r.result) {
                setEntries(prev => [...prev, {
                  id, file: { name: r.filename },
                  status: 'error',
                  result: null,
                  error: r.errore || 'File non trovato sul disco'
                }])
              } else {
                setEntries(prev => [...prev, {
                  id, file: { name: r.filename },
                  status: 'done',
                  result: r.result,
                  error: null
                }])
                if (r.result.fonte_db) setFonteDb(r.result.fonte_db)
              }
            }
          } catch (e) {
            setLancioError(e.message)
          } finally {
            setLancioLoading(false)
          }
        }
      }
    } catch {}
    }
    caricaDaDisco()
  }, [])

  // ── File: aggiungi + analisi automatica ───────────────────────────────────
  const addFiles = useCallback(async (files) => {
    const valid = Array.from(files).filter(f => /\.(mpf|nc|spf)$/i.test(f.name))
    if (!valid.length) return
    const newEntries = valid.map(f => ({ id: ++idRef.current, file: f, status: 'analyzing', result: null, error: null }))
    setEntries(prev => {
      const names = new Set(prev.map(e => e.file.name))
      return [...prev, ...newEntries.filter(e => !names.has(e.file.name))]
    })
    setCheckResult(null); setInvioResults([])

    // Analisi automatica
    for (const entry of newEntries) {
      try {
        const result = await api.analizzaNC(entry.file)
        if (result.fonte_db) setFonteDb(result.fonte_db)
        setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: 'done', result } : e))
      } catch (err) {
        setEntries(prev => prev.map(e => e.id === entry.id ? { ...e, status: 'error', error: err.message } : e))
      }
    }
  }, [])

  const removeEntry = (id) => {
    setEntries(prev => prev.filter(e => e.id !== id))
    setCheckResult(null); setInvioResults([])
  }

  const clearAll = () => {
    setEntries([]); setCheckResult(null); setInvioResults([])
    setMainGeneratoFile(null); setMainPreview(null); setShowPreview(false)
    setFonteDb(''); setGlobalSuccess(null); setFase('')
  }

  // ── Dati aggregati ────────────────────────────────────────────────────────
  const done         = entries.filter(e => e.status === 'done')
  const analyzing    = entries.some(e => e.status === 'analyzing')
  const allMancanti  = [...new Set(done.flatMap(e => e.result?.mancanti ?? []))]
  const allDisab     = [...new Set(done.flatMap(e => e.result?.disabilitati ?? []))]
  const allPresenti  = [...new Set(done.flatMap(e => e.result?.presenti_in_macchina ?? []))]
  const totUtensili  = [...new Set([...allMancanti, ...allDisab, ...allPresenti])].length
  const tuttoOk      = done.length > 0 && allMancanti.length === 0 && allDisab.length === 0

  // File da inviare
  const progetto = commessa.trim() && posizione.trim() ? `${commessa.trim()}_${posizione.trim()}` : nomeCartella.trim()
  const fileDaInviare = [...done.map(e => e.file), ...(mainGeneratoFile ? [mainGeneratoFile] : [])]

  // ── Modal scaffale ────────────────────────────────────────────────────────
  const openModal = async (alias) => {
    setModal({ alias }); setHolderInfo(null); setLoadingInfo(true); setAddError(null); setSelectedHolder('')
    try {
      const info = await api.infoAlias(alias)
      setHolderInfo(info)
      if (!info.ha_holder && info.holders_disponibili.length > 0) setSelectedHolder(info.holders_disponibili[0].alias_holder)
    } catch (e) { setAddError(`${e.message}`) }
    finally { setLoadingInfo(false) }
  }
  const closeModal = () => { setModal(null); setHolderInfo(null); setAddError(null); setSelectedHolder('') }
  const handleAggiungi = async () => {
    if (!modal) return
    setAddBusy(true); setAddError(null)
    try {
      const result = await api.aggiungiAScaffale({ alias: modal.alias, holder_override: holderInfo?.ha_holder ? null : (selectedHolder || null) })
      const r = modal.alias
      setEntries(prev => prev.map(e => !e.result ? e : { ...e, result: { ...e.result, mancanti: (e.result.mancanti??[]).filter(a=>a!==r), totale_mancanti: ((e.result.mancanti??[]).filter(a=>a!==r)).length } }))
      setGlobalSuccess(`${result.alias_finale} aggiunto a scaffale`)
      closeModal()
    } catch (e) { setAddError(e.message) }
    finally { setAddBusy(false) }
  }

  // ── MAIN ──────────────────────────────────────────────────────────────────
  const handleGeneraMain = async () => {
    if (!nomeCartella.trim()) { setMainError('Inserisci il nome cartella'); return }
    if (!percorso) { setMainError('Inserisci radice, commessa e posizione'); return }
    if (!done.length) { setMainError('Carica almeno un file NC'); return }
    const programmi = done.map(e => ({
      nome_file: e.file.name,
      utensile_principale: e.result?.utensili_nel_file?.[0]?.alias ?? '—',
      num_cambi: e.result?.totale_file ?? 1,
    }))
    setMainBusy(true); setMainError(null)
    try {
      const res = await api.salvaMain({ nome_cartella: nomeCompleto, percorso_cartella: percorso, programmi })
      setGlobalSuccess(`✓ ${res.nome_file} salvato`)
      const blob = new Blob([''], { type: 'text/plain' })
      setMainGeneratoFile(new File([blob], res.nome_file, { type: 'text/plain' }))
      api.cartelleRecenti().then(r => setCartelleRecenti(r.cartelle || [])).catch(() => {})
      setCheckResult(null); setInvioResults([])
      setCtaStep('invia') // ← guida verso invio

      // Aggiorna stato programmi → in_macchina nel progetto di origine
      try {
        const lancio = sessionStorage.getItem('dmgdesk_lancio_nc')
        console.log('[MAIN] lancio sessionStorage:', lancio)
        if (lancio) {
          const { projectId, mpfFiles } = JSON.parse(lancio)
          console.log('[MAIN] projectId:', projectId, 'filenames:', done.map(e => e.file.name))
          if (projectId && mpfFiles?.length) {
            const r = await fetch(`/api/progetti/${projectId}/segna-in-macchina`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ filenames: done.map(e => e.file.name) })
            })
            const result = await r.json()
            console.log('[MAIN] segna-in-macchina result:', result)
            // Consuma il sessionStorage solo dopo successo
            sessionStorage.removeItem('dmgdesk_lancio_nc')
          }
        }
      } catch {}

    } catch (e) { setMainError(e.message) }
    finally { setMainBusy(false) }
  }

  // ── Invio ─────────────────────────────────────────────────────────────────
  const doCheck = async () => {
    if (!progetto) { setInvioStatus({ type: 'warn', msg: 'Inserisci nome cartella o commessa+posizione' }); return }
    setChecking(true); setCheckResult(null); setInvioResults([]); setInvioStatus(null)
    try {
      const r = await api.checkMacchina(progetto, fileDaInviare.map(f => f.name))
      setCheckResult(r)
      setInvioStatus(r.reachable
        ? { type: 'ok', msg: `Connesso · ${r.esistenti.length} file già presenti` }
        : { type: 'err', msg: `Non raggiungibile: ${r.error}` })
    } catch (e) { setInvioStatus({ type: 'err', msg: e.message }) }
    finally { setChecking(false) }
  }

  const doSend = async (soloMain = false) => {
    const files = soloMain ? [mainGeneratoFile] : fileDaInviare
    if (!files.length) return
    setSending(true); setInvioResults([]); setInvioStatus(null)
    try {
      const r = await api.inviaMacchina(progetto, files)
      setInvioResults(r.risultati)
      if (r.n_err === 0) {
        setInvioStatus({ type: 'ok', msg: `✓ ${r.n_ok} file inviati` })
        setCtaStep('coda')
      } else {
        setInvioStatus({ type: 'warn', msg: `${r.n_ok} OK · ${r.n_err} errori` })
      }
    } catch (e) { setInvioStatus({ type: 'err', msg: e.message }) }
    finally { setSending(false) }
  }

  const doSendBatch = async () => {
    if (!fileDaInviare.length) return
    setSending(true); setInvioResults([]); setInvioStatus(null)
    try {
      const r = await api.inviaBatch(progetto, fileDaInviare)
      setInvioResults(r.risultati || [])
      if (r.n_err === 0) {
        setInvioStatus({ type: 'ok', msg: `⚡ ${r.n_ok} file batch — monitoraggio completato` })
        setCtaStep('coda') // ← guida verso coda lavorazione
      } else {
        setInvioStatus({ type: 'warn', msg: `${r.n_ok} OK · ${r.n_err} errori` })
      }
    } catch (e) { setInvioStatus({ type: 'err', msg: e.message }) }
    finally { setSending(false) }
  }

  const saveMachCfg = async () => {
    try { await api.setMachineConfig({ ip: machIp, port: Number(machPort) }); setEditingCfg(false) }
    catch (e) { setInvioStatus({ type: 'err', msg: e.message }) }
  }

  // ── stili comuni ──────────────────────────────────────────────────────────
  const inputStyle = {
    padding: '6px 10px', borderRadius: 6, fontSize: 12,
    background: 'var(--bg-base)', border: '1px solid var(--border)',
    color: 'var(--text-primary)', fontFamily: 'var(--font-mono)', outline: 'none',
  }
  const btnPrimary = (disabled) => ({
    padding: '7px 16px', borderRadius: 6, fontSize: 12, fontWeight: 700,
    cursor: disabled ? 'not-allowed' : 'pointer',
    background: disabled ? 'var(--bg-hover)' : 'var(--navy-700)',
    border: 'none', color: disabled ? 'var(--text-dim)' : 'white',
    transition: 'all 0.15s',
  })
  const btnGhost = {
    padding: '7px 14px', borderRadius: 6, fontSize: 12,
    cursor: 'pointer', background: 'transparent',
    border: '1px solid var(--border)', color: 'var(--text-secondary)',
  }

  // ── Layout ────────────────────────────────────────────────────────────────
  return (
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 0, padding: '12px 20px 0' }}>

      {/* ── Top bar: fasi progressive ── */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 0 8px', flexShrink: 0 }}>

        {/* Fase 1 — Carica */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <div style={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
            background: done.length > 0 ? '#15803d' : '#1D5FAD',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, fontWeight: 800, color: '#fff' }}>
            {done.length > 0 ? '✓' : '1'}
          </div>
          <div onClick={() => inputRef.current?.click()}
            onDragOver={e => { e.preventDefault(); setDragging(true) }}
            onDragLeave={() => setDragging(false)}
            onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
            style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '6px 12px',
              border: `1.5px dashed ${dragging ? 'var(--cyan)' : done.length > 0 ? 'rgba(21,128,61,0.4)' : 'var(--border-bright)'}`,
              borderRadius: 7, cursor: 'pointer',
              background: dragging ? 'var(--cyan-glow)' : done.length > 0 ? 'rgba(21,128,61,0.08)' : 'var(--navy-700)',
              transition: 'all 0.15s' }}>
            <input ref={inputRef} type="file" accept=".mpf,.nc,.spf" multiple style={{ display: 'none' }}
              onChange={e => { addFiles(e.target.files); e.target.value = '' }} />
            <span style={{ fontSize: 12, fontWeight: 700,
              color: done.length > 0 ? '#15803d' : 'white' }}>
              {done.length > 0 ? `${done.length} file` : '+ File NC'}
            </span>
          </div>
        </div>

        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>›</span>

        {/* Fase 2 — Nome + MAIN */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <div style={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
            background: mainGeneratoFile ? '#15803d' : done.length > 0 ? '#1D5FAD' : '#475569',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, fontWeight: 800, color: '#fff' }}>
            {mainGeneratoFile ? '✓' : '2'}
          </div>
          <input value={nomeCartella} onChange={e => {
              const v = e.target.value; setNomeCartella(v); setMainError(null)
              const parts = v.trim().split('_')
              if (parts.length >= 2 && /^\d+$/.test(parts[0])) { setCommessa(parts[0]); setPosizione(parts[1]) }
            }}
            placeholder="Commessa (es. 4297_0005)"
            style={{ ...inputStyle, width: 130, fontWeight: 600, fontSize: 12,
              borderColor: mainGeneratoFile ? 'rgba(21,128,61,0.4)' : 'var(--border)' }}
            onFocus={e => e.target.style.borderColor = 'var(--cyan)'}
            onBlur={e => e.target.style.borderColor = mainGeneratoFile ? 'rgba(21,128,61,0.4)' : 'var(--border)'} />
          <button onClick={handleGeneraMain}
            disabled={mainBusy || !done.length || !nomeCartella.trim() || !percorso}
            style={{ padding: '6px 12px', borderRadius: 7, fontSize: 12, fontWeight: 700, flexShrink: 0,
              cursor: (mainBusy || !done.length || !nomeCartella.trim() || !percorso) ? 'not-allowed' : 'pointer',
              background: mainGeneratoFile ? 'rgba(21,128,61,0.15)' : (!done.length || !nomeCartella.trim() || !percorso) ? 'var(--bg-hover)' : '#D4700A',
              border: mainGeneratoFile ? '1px solid rgba(21,128,61,0.3)' : 'none',
              color: mainGeneratoFile ? '#15803d' : (!done.length || !nomeCartella.trim() || !percorso) ? 'var(--text-dim)' : 'white' }}>
            {mainBusy ? '⏳' : mainGeneratoFile ? `✓ ${mainGeneratoFile.name}` : '📄 Genera MAIN'}
          </button>
        </div>

        <span style={{ color: 'var(--text-dim)', fontSize: 12 }}>›</span>

        {/* Fase 3 — Invia */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 6, flexShrink: 0 }}>
          <div style={{ width: 18, height: 18, borderRadius: '50%', flexShrink: 0,
            background: invioStatus?.type === 'ok' ? '#15803d' : fileDaInviare.length > 0 ? '#1D5FAD' : '#475569',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            fontSize: 10, fontWeight: 800, color: '#fff' }}>
            {invioStatus?.type === 'ok' ? '✓' : '3'}
          </div>
          {/* Pulsante principale: Verifica+Invia in uno */}
          {!checkResult?.reachable ? (
            <button onClick={doCheck}
              disabled={checking || sending || !fileDaInviare.length || !progetto}
              style={{ padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 700,
                cursor: (checking || !fileDaInviare.length || !progetto) ? 'not-allowed' : 'pointer',
                background: fileDaInviare.length && progetto ? 'var(--navy-700)' : 'var(--bg-hover)',
                border: 'none', color: fileDaInviare.length && progetto ? 'white' : 'var(--text-dim)' }}>
              {checking ? '⏳ Verifica...' : '🔍 Verifica connessione'}
            </button>
          ) : (
            <button onClick={doSendBatch}
              disabled={sending || !fileDaInviare.length}
              style={{ padding: '6px 14px', borderRadius: 7, fontSize: 12, fontWeight: 700,
                cursor: sending ? 'not-allowed' : 'pointer',
                background: sending ? 'var(--bg-hover)' : '#0369a1',
                border: 'none', color: sending ? 'var(--text-dim)' : 'white' }}>
              {sending ? '⏳ Invio...' : `⚡ Invia alla macchina (${fileDaInviare.length} file)`}
            </button>
          )}
        </div>

        {/* Spinner analisi */}
        {analyzing && <span style={{ fontSize: 11, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}><Spinner small /> Analisi...</span>}

        {/* Reset */}
        {entries.length > 0 && (
          <button onClick={() => { clearAll(); setCtaStep(null) }} style={{ ...btnGhost, fontSize: 11, marginLeft: 4 }}>Reset</button>
        )}

        {/* Fonte DB */}
        {fonteDb && <span style={{ fontSize: 9, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginLeft: 4 }}>{fonteDb}</span>}
      </div>

      {/* Status invio */}
      {invioStatus && (
        <div style={{ padding: '6px 12px', borderRadius: 6, fontSize: 12, marginBottom: 6, flexShrink: 0,
          background: invioStatus.type==='ok' ? 'rgba(22,163,74,0.07)' : invioStatus.type==='err' ? 'rgba(220,38,38,0.07)' : 'rgba(234,179,8,0.07)',
          border: `1px solid ${invioStatus.type==='ok' ? 'rgba(22,163,74,0.2)' : invioStatus.type==='err' ? 'rgba(220,38,38,0.2)' : 'rgba(234,179,8,0.2)'}`,
          color: invioStatus.type==='ok' ? '#15803d' : invioStatus.type==='err' ? '#dc2626' : '#a16207' }}>
          {invioStatus.msg}
        </div>
      )}

      {/* Successo */}
      {globalSuccess && (
        <div style={{ padding: '6px 12px', borderRadius: 6, fontSize: 12, marginBottom: 6, flexShrink: 0,
          background: 'rgba(22,163,74,0.07)', border: '1px solid rgba(22,163,74,0.2)', color: '#15803d',
          display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <span>✓ {globalSuccess}</span>
          <button onClick={() => setGlobalSuccess(null)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#15803d', fontSize: 14 }}>✕</button>
        </div>
      )}

      {/* ── CTA Passo successivo ── */}
      {ctaStep === 'invia' && !invioStatus && (
        <div style={{ padding: '10px 14px', borderRadius: 8, marginBottom: 6, flexShrink: 0,
          background: 'rgba(29,95,173,0.08)', border: '1.5px solid rgba(29,95,173,0.25)',
          display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#0d2d5e', marginBottom: 2 }}>
              MAIN generato — passo successivo
            </div>
            <div style={{ fontSize: 11, color: '#1D5FAD' }}>
              Verifica la connessione e invia i file alla macchina
            </div>
          </div>
          <button onClick={doCheck}
            style={{ background: '#1D5FAD', border: 'none', borderRadius: 7,
              color: '#fff', fontWeight: 700, fontSize: 12, padding: '7px 16px',
              cursor: 'pointer', flexShrink: 0 }}>
            🔍 Verifica e invia →
          </button>
          <button onClick={() => setCtaStep(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: 14, padding: 0 }}>✕</button>
        </div>
      )}
      {ctaStep === 'coda' && (
        <div style={{ padding: '10px 14px', borderRadius: 8, marginBottom: 6, flexShrink: 0,
          background: 'rgba(22,163,74,0.08)', border: '1.5px solid rgba(22,163,74,0.25)',
          display: 'flex', alignItems: 'center', gap: 12 }}>
          <div style={{ flex: 1 }}>
            <div style={{ fontSize: 12, fontWeight: 700, color: '#166534', marginBottom: 2 }}>
              File inviati alla macchina
            </div>
            <div style={{ fontSize: 11, color: '#15803d' }}>
              I programmi sono in coda — monitora l'esecuzione
            </div>
          </div>
          <button onClick={() => navigate('/coda')}
            style={{ background: '#166534', border: 'none', borderRadius: 7,
              color: '#fff', fontWeight: 700, fontSize: 12, padding: '7px 16px',
              cursor: 'pointer', flexShrink: 0 }}>
            Vai a Coda lavorazione →
          </button>
          <button onClick={() => setCtaStep(null)}
            style={{ background: 'none', border: 'none', cursor: 'pointer', color: '#94a3b8', fontSize: 14, padding: 0 }}>✕</button>
        </div>
      )}

      {/* ── Corpo: due colonne ── */}
      <div style={{ flex: 1, display: 'flex', gap: 10, minHeight: 0 }}>

        {/* ── Colonna sinistra: file + risultati ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0, minHeight: 0 }}>

          {/* Lista file — max 50% dello spazio, scrollabile */}
          {entries.length > 0 && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', flexShrink: 1, flexBasis: 'auto', maxHeight: '50%', overflowY: 'auto' }}>
              {entries.map(e => {
                const n = e.result?.totale_mancanti ?? 0
                const color = e.status === 'analyzing' ? 'var(--text-dim)' : e.status === 'error' ? '#dc2626' : n > 0 ? '#dc2626' : '#15803d'
                return (
                  <div key={e.id} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
                    borderBottom: '1px solid var(--border)' }}
                    onMouseEnter={ev => ev.currentTarget.style.background = 'var(--bg-hover)'}
                    onMouseLeave={ev => ev.currentTarget.style.background = 'transparent'}>
                    {e.status === 'analyzing' ? <Spinner small /> : <div style={{ width: 7, height: 7, borderRadius: '50%', background: color, flexShrink: 0 }} />}
                    <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', flex: 1, color: 'var(--text-primary)' }}>{e.file.name}</span>
                    {e.status === 'done' && n > 0 && <span style={{ fontSize: 11, color: '#dc2626', fontWeight: 700 }}>{n} mancanti</span>}
                    {e.status === 'done' && n === 0 && <span style={{ fontSize: 11, color: '#15803d' }}>✓</span>}
                    {e.status === 'error' && <span style={{ fontSize: 11, color: '#dc2626' }}>errore</span>}
                    <button onClick={() => removeEntry(e.id)} style={{ background: 'none', border: 'none', cursor: 'pointer', color: 'var(--text-dim)', fontSize: 14, padding: '0 2px' }}>✕</button>
                  </div>
                )
              })}
            </div>
          )}

          {/* Risultati confronto — sempre visibile con minHeight */}
          <div style={{ flex: 1, minHeight: 160, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>

            {/* Header tabella */}
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between',
              padding: '6px 12px', background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
              <span style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-dim)',
                fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>UTENSILI</span>
              {done.length > 0 && !analyzing && (
                <span style={{ fontSize: 11, fontWeight: 700,
                  color: tuttoOk ? '#15803d' : '#dc2626' }}>
                  {tuttoOk
                    ? `✓ tutti OK (${totUtensili})`
                    : `${allMancanti.length > 0 ? `✕ ${allMancanti.length} mancanti` : ''}${allMancanti.length && allDisab.length ? '  ' : ''}${allDisab.length > 0 ? `⚠ ${allDisab.length} disab.` : ''}`
                  }
                </span>
              )}
            </div>

            {/* Righe */}
            <div style={{ flex: 1, overflow: 'auto' }}>
              {entries.length === 0 && (
                <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-dim)', fontSize: 13 }}>
                  Aggiungi file NC per il confronto automatico
                </div>
              )}
              {/* Mancanti — con bottone esplicito */}
              {allMancanti.map(alias => (
                <div key={alias}
                  style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
                    borderBottom: '1px solid var(--border)',
                    background: 'rgba(220,38,38,0.04)' }}>
                  <StatoBadge stato="manca" />
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: '#dc2626',
                    fontWeight: 600, flex: 1 }}>{alias}</span>
                  <button
                    onClick={() => openModal(alias)}
                    style={{ flexShrink: 0, padding: '3px 10px', borderRadius: 5, fontSize: 11,
                      fontWeight: 700, cursor: 'pointer',
                      background: 'rgba(220,38,38,0.12)', border: '1px solid rgba(220,38,38,0.3)',
                      color: '#dc2626', transition: 'all 0.12s' }}
                    onMouseEnter={e => { e.currentTarget.style.background='rgba(220,38,38,0.22)' }}
                    onMouseLeave={e => { e.currentTarget.style.background='rgba(220,38,38,0.12)' }}>
                    + Scaffale
                  </button>
                </div>
              ))}
              {/* Disabilitati */}
              {allDisab.map(alias => (
                <div key={alias} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
                  borderBottom: '1px solid var(--border)', background: 'rgba(234,179,8,0.03)' }}>
                  <StatoBadge stato="disab" />
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: '#a16207',
                    flex: 1 }}>{alias}</span>
                  <span style={{ fontSize: 10, color: '#a16207', opacity: 0.7 }}>disabilitato</span>
                </div>
              ))}
              {/* Presenti */}
              {allPresenti.map(alias => (
                <div key={alias} style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '6px 12px',
                  borderBottom: '1px solid var(--border)' }}>
                  <StatoBadge stato="ok" />
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)',
                    flex: 1 }}>{alias}</span>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* ── Colonna destra: nome + percorso + MAIN + invio ── */}
        <div style={{ width: 300, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>

          {/* Riepilogo cartella macchina (solo lettura) */}
          {nomeCartella && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px' }}>
              <div style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginBottom: 4 }}>
                CARTELLA MACCHINA (WPD · EXTCALL)
              </div>
              <div style={{ fontSize: 13, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>
                {nomeCartella}
              </div>
              <div style={{ fontSize: 9, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginTop: 3 }}>
                /_N_WKS_DIR/_N_{nomeCartella.toUpperCase()}_WPD/...
              </div>
            </div>
          )}

          {/* Percorso salvataggio — collassato se arriva da Progetti (tutto già noto) */}
          <PercorsoPanel
            daProgetti={!!lancioProgetto}
            radiceNcInput={radiceNcInput} setRadiceNcInput={setRadiceNcInput}
            commessa={commessa} setCommessa={setCommessa}
            posizione={posizione} setPosizione={setPosizione}
            fase={fase} setFase={setFase}
            cartelleRecenti={cartelleRecenti}
            percorso={percorso} nomeCompleto={nomeCompleto}
            inputStyle={inputStyle}
            setMainError={setMainError}
            onSaveRadice={async (v) => { try { await api.setPercorsoNc(v) } catch {} }}
          />

          {/* Genera MAIN */}
          <div style={{ background: 'var(--bg-card)', border: '1.5px solid #D4700A44', borderRadius: 8, padding: '12px 14px' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: '#D4700A', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginBottom: 8 }}>
              GENERA MAIN <span style={{ fontWeight: 400, opacity: 0.6 }}>(opzionale)</span>
            </div>
            {mainError && <div style={{ fontSize: 11, color: '#dc2626', marginBottom: 6 }}>⚠ {mainError}</div>}
            {mainGeneratoFile && (
              <div style={{ fontSize: 11, color: '#15803d', fontFamily: 'var(--font-mono)', marginBottom: 6 }}>
                ✓ {mainGeneratoFile.name}
              </div>
            )}
            <button onClick={handleGeneraMain}
              disabled={mainBusy || !done.length || !nomeCartella.trim() || !percorso}
              style={{
                width: '100%', padding: '10px 16px', borderRadius: 7, fontSize: 13, fontWeight: 800,
                cursor: (mainBusy || !done.length || !nomeCartella.trim() || !percorso) ? 'not-allowed' : 'pointer',
                background: (mainBusy || !done.length || !nomeCartella.trim() || !percorso) ? '#E8E6E0' : '#D4700A',
                border: 'none',
                color: (mainBusy || !done.length || !nomeCartella.trim() || !percorso) ? '#9A978E' : 'white',
                transition: 'all 0.15s',
              }}>
              {mainBusy ? <><Spinner small /> Generazione...</> : '📄 Genera e salva MAIN'}
            </button>
          </div>

          {/* Config server */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '10px 14px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <span style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>SERVER</span>
              {editingCfg ? (
                <>
                  <input value={machIp} onChange={e => setMachIp(e.target.value)} style={{ ...inputStyle, width: 110, fontSize: 11 }} />
                  <input value={machPort} onChange={e => setMachPort(e.target.value)} style={{ ...inputStyle, width: 55, fontSize: 11 }} />
                  <button onClick={saveMachCfg} style={{ ...btnGhost, fontSize: 10, padding: '4px 8px' }}>✓</button>
                  <button onClick={() => setEditingCfg(false)} style={{ ...btnGhost, fontSize: 10, padding: '4px 8px' }}>✕</button>
                </>
              ) : (
                <>
                  <span style={{ fontSize: 11, fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>{machIp}:{machPort}</span>
                  <button onClick={() => setEditingCfg(true)} style={{ ...btnGhost, fontSize: 10, padding: '2px 6px', marginLeft: 'auto' }}>✎</button>
                </>
              )}
            </div>
          </div>
        </div>
      </div>

      {/* ── Modal scaffale ── */}
      {modal && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.6)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
          <div style={{ background: 'var(--bg-card)', borderRadius: 12, padding: 24, width: 440, display: 'flex', flexDirection: 'column', gap: 16, border: '1px solid var(--border)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
              <div>
                <div style={{ fontSize: 14, fontWeight: 700 }}>Aggiungi a Scaffale</div>
                <div style={{ fontSize: 11, color: 'var(--text-dim)', marginTop: 2 }}>Utensile mancante dall'analisi NC</div>
              </div>
              <button onClick={closeModal} style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: 18 }}>✕</button>
            </div>
            <div style={{ background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 6, padding: '8px 12px' }}>
              <div style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: 3 }}>ALIAS CNC</div>
              <span style={{ fontSize: 14, fontWeight: 700, fontFamily: 'var(--font-mono)', color: 'var(--cyan)' }}>{modal.alias}</span>
            </div>
            {loadingInfo ? <div style={{ fontSize: 12, color: 'var(--text-dim)', display: 'flex', gap: 8, alignItems: 'center' }}><Spinner /> Caricamento...</div>
            : holderInfo && !holderInfo.ha_holder && holderInfo.holders_disponibili.length > 0 && (
              <div>
                <div style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', marginBottom: 6 }}>SELEZIONA HOLDER</div>
                {holderInfo.holders_disponibili.map(h => (
                  <label key={h.alias_holder} style={{ display: 'flex', alignItems: 'center', gap: 10, padding: '7px 10px', marginBottom: 4,
                    background: selectedHolder===h.alias_holder ? 'rgba(0,225,255,0.08)' : 'var(--bg-base)',
                    border: `1px solid ${selectedHolder===h.alias_holder ? 'var(--cyan)' : 'var(--border)'}`,
                    borderRadius: 6, cursor: 'pointer' }}>
                    <input type="radio" name="holder" value={h.alias_holder} checked={selectedHolder===h.alias_holder} onChange={() => setSelectedHolder(h.alias_holder)} style={{ accentColor: 'var(--cyan)' }} />
                    <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 700, fontSize: 12, color: 'var(--cyan)' }}>{h.alias_holder}</span>
                    <span style={{ fontSize: 11, color: 'var(--text-secondary)', flex: 1 }}>{h.tipo_desc}</span>
                    <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>×{h.quantita}</span>
                  </label>
                ))}
              </div>
            )}
            {addError && <div style={{ fontSize: 11, color: '#dc2626' }}>⚠ {addError}</div>}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
              <button onClick={closeModal} style={btnGhost}>Annulla</button>
              <button onClick={handleAggiungi} disabled={addBusy || (!holderInfo?.ha_holder && !selectedHolder)}
                style={btnPrimary(addBusy || (!holderInfo?.ha_holder && !selectedHolder))}>
                {addBusy ? <><Spinner small /> Aggiunta...</> : '+ Aggiungi a Scaffale'}
              </button>
            </div>
          </div>
        </div>
      )}

      <style>{`@keyframes spin { to { transform: rotate(360deg) } }`}</style>
    </div>
  )
}
