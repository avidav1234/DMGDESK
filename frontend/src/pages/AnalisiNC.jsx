// pages/AnalisiNC.jsx — Flow identico al desktop:
// 1. Aggiungi file → confronto automatico
// 2. Inserisci nome cartella → Genera MAIN
// 3. Invia tutto / Solo MAIN

import { useState, useRef, useCallback, useEffect } from 'react'
import { api } from '../api/client'

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

  useEffect(() => {
    api.getPercorsoNc().then(r => { if (r.percorso_nc_base) setRadiceNcInput(r.percorso_nc_base) }).catch(() => {})
    api.cartelleRecenti().then(r => setCartelleRecenti(r.cartelle || [])).catch(() => {})
    api.getMachineConfig().then(r => { setMachIp(r.ip); setMachPort(r.port) }).catch(() => {})
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

      // Aggiorna stato programmi → in_macchina nel progetto di origine
      try {
        const lancio = sessionStorage.getItem('dmgdesk_lancio_nc')
        if (lancio) {
          const { projectId, mpfFiles } = JSON.parse(lancio)
          if (projectId && mpfFiles?.length) {
            await fetch(`/api/progetti/${projectId}/segna-in-macchina`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json' },
              body: JSON.stringify({ filenames: done.map(e => e.file.name) })
            })
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
      setInvioStatus(r.n_err === 0
        ? { type: 'ok',  msg: `✓ ${r.n_ok} file inviati` }
        : { type: 'warn', msg: `${r.n_ok} OK · ${r.n_err} errori` })
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
    <div style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 0 }}>

      {/* ── Top bar: ordine flow ── */}
      {/* SX: Aggiungi | Nome | Fase(opz.) | Genera MAIN | Reset | banner stato */}
      {/* DX: Verifica | Invia tutto | Solo MAIN */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, padding: '10px 0 8px', flexShrink: 0 }}>

        {/* 1. Aggiungi file */}
        <div onClick={() => inputRef.current?.click()}
          onDragOver={e => { e.preventDefault(); setDragging(true) }}
          onDragLeave={() => setDragging(false)}
          onDrop={e => { e.preventDefault(); setDragging(false); addFiles(e.dataTransfer.files) }}
          style={{ display: 'flex', alignItems: 'center', gap: 6, padding: '7px 14px',
            border: `1.5px dashed ${dragging ? 'var(--cyan)' : 'var(--border-bright)'}`,
            borderRadius: 7, cursor: 'pointer',
            background: dragging ? 'var(--cyan-glow)' : 'var(--navy-700)',
            transition: 'all 0.15s', flexShrink: 0 }}>
          <input ref={inputRef} type="file" accept=".mpf,.nc,.spf" multiple style={{ display: 'none' }}
            onChange={e => { addFiles(e.target.files); e.target.value = '' }} />
          <span style={{ fontSize: 13, fontWeight: 700, color: 'white' }}>+ Aggiungi file</span>
        </div>

        {/* 2. Nome cartella */}
        <input value={nomeCartella} onChange={e => { setNomeCartella(e.target.value); setMainError(null) }}
          placeholder="Nome cartella"
          style={{ ...inputStyle, width: 120, fontWeight: 600, fontSize: 12 }}
          onFocus={e => e.target.style.borderColor = 'var(--cyan)'}
          onBlur={e => e.target.style.borderColor = 'var(--border)'} />

        {/* 3. Genera MAIN */}
        <button onClick={handleGeneraMain}
          disabled={mainBusy || !done.length || !nomeCartella.trim() || !percorso}
          style={{ padding: '7px 14px', borderRadius: 7, fontSize: 12, fontWeight: 700,
            cursor: (mainBusy || !done.length || !nomeCartella.trim() || !percorso) ? 'not-allowed' : 'pointer',
            background: (!done.length || !nomeCartella.trim() || !percorso) ? 'var(--bg-hover)' : 'var(--navy-700)',
            border: 'none', color: (!done.length || !nomeCartella.trim() || !percorso) ? 'var(--text-dim)' : 'white',
            flexShrink: 0 }}>
          {mainBusy ? '⏳ ...' : '📄 Genera MAIN'}
        </button>

        {/* 5. Reset */}
        {entries.length > 0 && (
          <button onClick={clearAll} style={{ ...btnGhost, fontSize: 12 }}>Reset</button>
        )}

        {/* Spinner */}
        {analyzing && <span style={{ fontSize: 11, color: 'var(--text-dim)', display: 'flex', alignItems: 'center', gap: 5, flexShrink: 0 }}><Spinner small /> Analisi...</span>}

        {/* Banner stato */}
        {done.length > 0 && !analyzing && (
          <div style={{ display: 'flex', flexDirection: 'column', gap: 1 }}>
            {tuttoOk
              ? <span style={{ fontSize: 11, fontWeight: 700, color: '#15803d' }}>✅ Tutti i {totUtensili} utensili OK</span>
              : <span style={{ fontSize: 11, fontWeight: 700, color: '#dc2626' }}>
                  {allMancanti.length > 0 && `✕ ${allMancanti.length} mancanti`}
                  {allMancanti.length > 0 && allDisab.length > 0 && '  '}
                  {allDisab.length > 0 && `⚠ ${allDisab.length} disab.`}
                  <span style={{ color: 'var(--text-dim)', fontWeight: 400, marginLeft: 6 }}>/ {totUtensili}</span>
                </span>
            }
            {fonteDb && <span style={{ fontSize: 9, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>{fonteDb}</span>}
          </div>
        )}
        {mainGeneratoFile && (
          <span style={{ fontSize: 10, color: '#15803d', fontFamily: 'var(--font-mono)', flexShrink: 0 }}>✓ {mainGeneratoFile.name}</span>
        )}

        {/* Spazio */}
        <div style={{ flex: 1 }} />

        {/* DESTRA: invio */}
        <button onClick={doCheck} disabled={checking || sending || !fileDaInviare.length || !progetto}
          style={{ padding: '7px 12px', borderRadius: 7, fontSize: 12, fontWeight: 600,
            cursor: (checking || !fileDaInviare.length || !progetto) ? 'not-allowed' : 'pointer',
            background: 'var(--bg-hover)', border: '1px solid var(--border)', color: 'var(--text-secondary)' }}>
          {checking ? '⏳' : '🔍'} Verifica
        </button>
        <button onClick={() => doSend(false)}
          disabled={!checkResult?.reachable || sending || !fileDaInviare.length || !progetto}
          style={{ padding: '7px 14px', borderRadius: 7, fontSize: 12, fontWeight: 700,
            cursor: (!checkResult?.reachable || sending) ? 'not-allowed' : 'pointer',
            background: checkResult?.reachable && !sending ? 'var(--navy-700)' : 'var(--bg-hover)',
            border: 'none', color: checkResult?.reachable && !sending ? 'white' : 'var(--text-dim)' }}>
          {sending ? '⏳' : '📤'} Invia tutto
        </button>
        {mainGeneratoFile && (
          <button onClick={() => doSend(true)} disabled={!checkResult?.reachable || sending || !progetto}
            style={{ padding: '7px 14px', borderRadius: 7, fontSize: 12, fontWeight: 700,
              cursor: (!checkResult?.reachable || sending) ? 'not-allowed' : 'pointer',
              background: checkResult?.reachable && !sending ? 'var(--navy-700)' : 'var(--bg-hover)',
              border: 'none', color: checkResult?.reachable && !sending ? 'white' : 'var(--text-dim)' }}>
            📤 Solo MAIN
          </button>
        )}
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

      {/* ── Corpo: due colonne ── */}
      <div style={{ flex: 1, display: 'flex', gap: 10, minHeight: 0 }}>

        {/* ── Colonna sinistra: file + risultati ── */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 8, minWidth: 0 }}>

          {/* Lista file */}
          {entries.length > 0 && (
            <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', flexShrink: 0 }}>
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

          {/* Risultati confronto */}
          <div style={{ flex: 1, background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, overflow: 'hidden', display: 'flex', flexDirection: 'column' }}>

            {/* Header tabella */}
            <div style={{ display: 'grid', gridTemplateColumns: '130px 1fr', padding: '6px 12px',
              background: 'var(--bg-surface)', borderBottom: '1px solid var(--border)' }}>
              {['STATO', 'UTENSILE'].map(h => (
                <span key={h} style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-dim)',
                  fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>{h}</span>
              ))}
            </div>

            {/* Righe */}
            <div style={{ flex: 1, overflow: 'auto' }}>
              {entries.length === 0 && (
                <div style={{ padding: '40px 20px', textAlign: 'center', color: 'var(--text-dim)', fontSize: 13 }}>
                  Aggiungi file NC per il confronto automatico
                </div>
              )}
              {/* Mancanti */}
              {allMancanti.map(alias => (
                <div key={alias}
                  onClick={() => openModal(alias)}
                  title="Clicca per aggiungere a scaffale"
                  style={{ display: 'grid', gridTemplateColumns: '130px 1fr', padding: '7px 12px',
                    borderBottom: '1px solid var(--border)', cursor: 'pointer',
                    background: 'rgba(220,38,38,0.03)' }}
                  onMouseEnter={e => e.currentTarget.style.background = 'rgba(220,38,38,0.08)'}
                  onMouseLeave={e => e.currentTarget.style.background = 'rgba(220,38,38,0.03)'}>
                  <StatoBadge stato="manca" />
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: '#dc2626', fontWeight: 600 }}>
                    {alias} <span style={{ fontSize: 10, opacity: 0.6 }}>+ scaffale</span>
                  </span>
                </div>
              ))}
              {/* Disabilitati */}
              {allDisab.map(alias => (
                <div key={alias} style={{ display: 'grid', gridTemplateColumns: '130px 1fr', padding: '7px 12px',
                  borderBottom: '1px solid var(--border)', background: 'rgba(234,179,8,0.03)' }}>
                  <StatoBadge stato="disab" />
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: '#a16207' }}>{alias}</span>
                </div>
              ))}
              {/* Presenti */}
              {allPresenti.map(alias => (
                <div key={alias} style={{ display: 'grid', gridTemplateColumns: '130px 1fr', padding: '7px 12px',
                  borderBottom: '1px solid var(--border)' }}>
                  <StatoBadge stato="ok" />
                  <span style={{ fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--text-secondary)' }}>{alias}</span>
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

          {/* Percorso salvataggio */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px', display: 'flex', flexDirection: 'column', gap: 6 }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em' }}>PERCORSO SALVATAGGIO</div>
            <input value={radiceNcInput} onChange={e => setRadiceNcInput(e.target.value)} onBlur={async () => { const v = radiceNcInput.trim().replace(/[\\/]+$/, ''); if (v) { try { await api.setPercorsoNc(v) } catch {} } }} placeholder="P:\DMG_DMC_160U"
              style={{ ...inputStyle, fontSize: 11, color: 'var(--text-dim)', width: '100%' }} />
            <div style={{ display: 'flex', gap: 6 }}>
              <input value={commessa} onChange={e => setCommessa(e.target.value.replace(/[^a-zA-Z0-9_-]/g,''))} placeholder="4348"
                style={{ ...inputStyle, width: '50%', fontWeight: 700 }} />
              <input value={posizione} onChange={e => setPosizione(e.target.value.replace(/[^a-zA-Z0-9_-]/g,''))} placeholder="0221"
                style={{ ...inputStyle, width: '50%', fontWeight: 700 }} />
            </div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
              <input value={fase} onChange={e => { setFase(e.target.value); setMainError(null) }}
                placeholder="Sottocartella (opz.) — solo percorso Windows"
                style={{ ...inputStyle, width: '100%', fontSize: 10, color: 'var(--text-dim)' }}
                onFocus={e => e.target.style.borderColor = 'var(--cyan)'}
                onBlur={e => e.target.style.borderColor = 'var(--border)'} />
            </div>
            {/* Recenti */}
            {cartelleRecenti.length > 0 && (
              <div style={{ display: 'flex', flexWrap: 'wrap', gap: 4, marginTop: 2 }}>
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
            {percorso && nomeCompleto && (
              <div style={{ fontSize: 9, fontFamily: 'var(--font-mono)', color: '#15803d', marginTop: 2 }}>
                → {percorso}\0_MAIN_{nomeCompleto.toUpperCase()}.MPF
              </div>
            )}
          </div>

          {/* Genera MAIN */}
          <div style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', borderRadius: 8, padding: '12px 14px' }}>
            <div style={{ fontSize: 10, fontWeight: 700, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', letterSpacing: '0.08em', marginBottom: 8 }}>
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
              style={btnPrimary(mainBusy || !done.length || !nomeCartella.trim() || !percorso)}>
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
