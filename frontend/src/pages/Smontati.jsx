// pages/Smontati.jsx — Archivio utensili smontati con workflow montaggio
import { useState, useEffect, useCallback } from 'react'
import { api } from '../api/client'
import { Loader, EmptyState, ErrorBanner, SuccessBanner, StatCard, SectionHeader , InfoTooltip } from '../components/UI'

export default function Smontati() {
  const [lista, setLista]         = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [success, setSuccess]     = useState(null)
  const [showAdd, setShowAdd]     = useState(false)
  const [form, setForm]           = useState({ alias_utensile: '', provenienza: 'Manuale', note: '' })
  const [busy, setBusy]           = useState(false)
  const [search, setSearch]       = useState('')

  // ── Stato modal montaggio ──────────────────────────────
  const [montaItem, setMontaItem]       = useState(null)   // utensile da montare
  const [holders, setHolders]           = useState([])
  const [bussole, setBussole]           = useState([])
  const [loadingModal, setLoadingModal] = useState(false)
  const [selectedHolder, setSelectedHolder] = useState(null)  // oggetto holder
  const [selectedBussola, setSelectedBussola] = useState(null)
  const [destinazione, setDestinazione] = useState('scaffale')
  const [posizione, setPosizione]       = useState('')
  const [montaBusy, setMontaBusy]       = useState(false)
  const [montaError, setMontaError]     = useState(null)

  const load = useCallback(async () => {
    try { setLoading(true); setError(null); setLista(await api.getSmontati()) }
    catch (e) { setError(e.message) } finally { setLoading(false) }
  }, [])

  useEffect(() => { load() }, [load])

  // ── Aggiungi manuale ──────────────────────────────────
  const handleAggiungi = async () => {
    if (!form.alias_utensile.trim()) return
    try {
      setBusy(true)
      await api.aggiungiSmontato(form)
      setSuccess(`Aggiunto: ${form.alias_utensile}`)
      setShowAdd(false)
      setForm({ alias_utensile: '', provenienza: 'Manuale', note: '' })
      load()
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  // ── Elimina ───────────────────────────────────────────
  const handleElimina = async (id, alias) => {
    if (!confirm(`Eliminare "${alias}"?`)) return
    try {
      await api.eliminaSmontato(id)
      setSuccess(`Eliminato: ${alias}`)
      load()
    } catch (e) { setError(e.message) }
  }

  // ── Apri modal montaggio ──────────────────────────────
  const openMonta = async (utensile) => {
    setMontaItem(utensile)
    setSelectedHolder(null)
    setSelectedBussola(null)
    setDestinazione('scaffale')
    setPosizione('')
    setMontaError(null)
    setLoadingModal(true)
    try {
      const [h, b] = await Promise.all([api.getHolder(), api.getBussole()])
      setHolders(h)
      setBussole(b)
    } catch (e) {
      setMontaError(`Impossibile caricare inventario: ${e.message}`)
    } finally {
      setLoadingModal(false)
    }
  }

  const closeMonta = () => {
    setMontaItem(null)
    setMontaError(null)
  }

  // ── Conferma montaggio ────────────────────────────────
  const handleMonta = async () => {
    if (!selectedHolder) return
    // Holder "E" base idraulico: serve bussola
    if (selectedHolder.alias_holder === 'E' && !selectedBussola) {
      setMontaError('Seleziona una bussola per holder idraulico E')
      return
    }
    if (destinazione === 'macchina' && !posizione.trim()) {
      setMontaError('Inserisci la posizione in macchina')
      return
    }

    setMontaBusy(true)
    setMontaError(null)
    try {
      const body = {
        alias_holder: selectedHolder.alias_holder,
        codice_bussola: selectedHolder.alias_holder === 'E' ? selectedBussola.codice_bussola : null,
        destinazione,
        posizione: destinazione === 'macchina' ? posizione.trim() : null,
      }
      const result = await api.montaSmontato(montaItem.id, body)
      setSuccess(result.messaggio)
      closeMonta()
      load()
    } catch (e) {
      setMontaError(e.message)
    } finally {
      setMontaBusy(false)
    }
  }

  // ── Anteprima alias finale ────────────────────────────
  const aliasFinale = (() => {
    if (!montaItem || !selectedHolder) return null
    const base = montaItem.alias_utensile.toUpperCase()
    if (selectedHolder.alias_holder === 'E') {
      return selectedBussola ? `${base}${selectedBussola.codice_bussola}` : null
    }
    return `${base}${selectedHolder.alias_holder}`
  })()

  const serveNucleare = selectedHolder?.alias_holder === 'E'

  const filtered = lista.filter(u =>
    u.alias_utensile.toLowerCase().includes(search.toLowerCase()) ||
    u.provenienza?.toLowerCase().includes(search.toLowerCase())
  )

  return (
    <div className="fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader
        title="Smontati"
        subtitle="Utensili base senza holder — monta per inserire nel DB principale"
        action={
          <button className="btn btn-primary" onClick={() => setShowAdd(true)} style={{ fontSize: 12 }}>
            + Aggiungi
          </button>
        }
      />

      <div style={{ display: 'flex', gap: 12 }}>
        <StatCard label="Totale Smontati"  value={lista.length}  color="var(--purple)" tooltip="Totale utensili nell'archivio smontati — utensili rimossi dalla macchina in attesa di valutazione o smaltimento." />
        <StatCard tooltip="Utensili smontati direttamente dalla macchina — rimossi dal magazine Sinumerik per usura, rottura o fine vita." label="Da Macchina"
          value={lista.filter(u => u.provenienza?.toLowerCase().includes('pos')).length}
          color="var(--text-secondary)" />
        <StatCard tooltip="Utensili registrati manualmente nell'archivio — acquistati nuovi, ricevuti da fornitore o aggiunti senza provenienza dalla macchina." label="Manuali / Acquisto"
          value={lista.filter(u => !u.provenienza?.toLowerCase().includes('pos')).length}
          color="var(--text-dim)" />
      </div>

      <ErrorBanner   message={error}   onClose={() => setError(null)} />
      <SuccessBanner message={success} onClose={() => setSuccess(null)} />

      <input className="input" placeholder="Cerca per alias o provenienza..."
        value={search} onChange={e => setSearch(e.target.value)} style={{ maxWidth: 340 }} />

      {/* Tabella */}
      <div className="card" style={{ flex: 1, overflow: 'auto' }}>
        {loading ? <Loader /> : filtered.length === 0 ? (
          <EmptyState icon="🔧" title="Archivio vuoto" subtitle="Nessun utensile smontato registrato" />
        ) : (
          <table className="table">
            <thead>
              <tr>
                <th>ID</th>
                <th>Alias Utensile Base</th>
                <th>Data</th>
                <th>Provenienza</th>
                <th>Note</th>
                <th style={{ textAlign: 'right' }}>Azioni</th>
              </tr>
            </thead>
            <tbody>
              {filtered.map(u => (
                <tr key={u.id}>
                  <td><span className="mono" style={{ color: 'var(--text-dim)', fontSize: 11 }}>{u.id}</span></td>
                  <td><span className="mono" style={{ fontWeight: 600, color: 'var(--text-primary)' }}>{u.alias_utensile}</span></td>
                  <td><span className="mono" style={{ fontSize: 11, color: 'var(--text-secondary)' }}>{u.data_smontaggio?.slice(0, 10)}</span></td>
                  <td><span style={{ fontSize: 12, color: 'var(--text-secondary)' }}>{u.provenienza}</span></td>
                  <td><span style={{ fontSize: 11, color: 'var(--text-dim)' }}>{u.note || '—'}</span></td>
                  <td style={{ textAlign: 'right', display: 'flex', gap: 6, justifyContent: 'flex-end' }}>
                    <button
                      className="btn btn-primary"
                      style={{ fontSize: 11, padding: '4px 12px' }}
                      onClick={() => openMonta(u)}
                    >
                      🔧 Monta
                    </button>
                    <button
                      className="btn btn-danger"
                      style={{ fontSize: 11, padding: '4px 10px' }}
                      onClick={() => handleElimina(u.id, u.alias_utensile)}
                    >
                      Elimina
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>

      {/* ── Modal aggiungi manuale ── */}
      {showAdd && (
        <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.7)', display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 100 }}>
          <div className="card fade-in" style={{ padding: 24, width: 400, display: 'flex', flexDirection: 'column', gap: 14 }}>
            <h3 style={{ fontSize: 16, fontWeight: 700 }}>Aggiungi Utensile Smontato</h3>
            {[
              { key: 'alias_utensile', label: 'Alias Utensile Base', placeholder: 'es. FS12R0.5L50F60' },
              { key: 'provenienza',    label: 'Provenienza',          placeholder: 'es. Macchina, Acquisto...' },
              { key: 'note',           label: 'Note',                 placeholder: 'Opzionale' },
            ].map(({ key, label, placeholder }) => (
              <div key={key}>
                <label style={{ fontSize: 10, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)', display: 'block', marginBottom: 4, textTransform: 'uppercase', letterSpacing: '0.08em' }}>{label}</label>
                <input className="input" value={form[key]} placeholder={placeholder}
                  onChange={e => setForm(f => ({ ...f, [key]: e.target.value }))} />
              </div>
            ))}
            <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
              <button className="btn btn-ghost" onClick={() => setShowAdd(false)}>Annulla</button>
              <button className="btn btn-primary" onClick={handleAggiungi} disabled={busy || !form.alias_utensile.trim()}>
                {busy ? 'Salvataggio...' : 'Aggiungi'}
              </button>
            </div>
          </div>
        </div>
      )}

      {/* ── Modal montaggio ── */}
      {montaItem && (
        <ModalMontaggio
          utensile={montaItem}
          holders={holders}
          bussole={bussole}
          loading={loadingModal}
          selectedHolder={selectedHolder}
          onSelectHolder={(h) => { setSelectedHolder(h); setSelectedBussola(null) }}
          selectedBussola={selectedBussola}
          onSelectBussola={setSelectedBussola}
          serveNucleare={serveNucleare}
          destinazione={destinazione}
          onDestinazione={setDestinazione}
          posizione={posizione}
          onPosizione={setPosizione}
          aliasFinale={aliasFinale}
          error={montaError}
          busy={montaBusy}
          onConferma={handleMonta}
          onClose={closeMonta}
        />
      )}
    </div>
  )
}

// ── Componente Modal Montaggio ─────────────────────────────

function ModalMontaggio({
  utensile, holders, bussole, loading,
  selectedHolder, onSelectHolder,
  selectedBussola, onSelectBussola,
  serveNucleare,
  destinazione, onDestinazione,
  posizione, onPosizione,
  aliasFinale,
  error, busy,
  onConferma, onClose,
}) {
  const canConfirm = !loading && !busy && selectedHolder &&
    (!serveNucleare || selectedBussola) &&
    (destinazione !== 'macchina' || posizione.trim())

  return (
    <div style={{
      position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.8)',
      display: 'flex', alignItems: 'center', justifyContent: 'center',
      zIndex: 200, padding: 20,
    }}>
      <div className="card fade-in" style={{
        width: 560, maxHeight: '90vh', display: 'flex', flexDirection: 'column',
        overflow: 'hidden',
      }}>

        {/* Header */}
        <div style={{ padding: '20px 24px 16px', borderBottom: '1px solid var(--border)', flexShrink: 0 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
            <div>
              <h3 style={{ fontSize: 16, fontWeight: 700, marginBottom: 4 }}>Monta Utensile</h3>
              <p style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                Associa holder → inserisci nel DB principale
              </p>
            </div>
            <button onClick={onClose} style={{ background: 'none', border: 'none', color: 'var(--text-dim)', cursor: 'pointer', fontSize: 20, padding: 4 }}>✕</button>
          </div>

          {/* Utensile base */}
          <div style={{ marginTop: 12, background: 'var(--bg-base)', border: '1px solid var(--border)', borderRadius: 'var(--radius-sm)', padding: '10px 14px' }}>
            <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.08em', marginBottom: 4 }}>UTENSILE BASE</div>
            <span className="mono" style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-primary)' }}>
              {utensile.alias_utensile}
            </span>
            <span style={{ fontSize: 11, color: 'var(--text-dim)', marginLeft: 10 }}>{utensile.provenienza}</span>
          </div>
        </div>

        {/* Body scrollabile */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '16px 24px', display: 'flex', flexDirection: 'column', gap: 20 }}>

          {loading ? (
            <div style={{ display: 'flex', alignItems: 'center', gap: 10, color: 'var(--text-secondary)', fontSize: 13, padding: '20px 0' }}>
              <Spinner /> Caricamento inventario...
            </div>
          ) : (
            <>
              {/* Selezione holder */}
              <div>
                <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.08em', marginBottom: 10 }}>
                  HOLDER DISPONIBILI — seleziona uno
                </div>
                {holders.length === 0 ? (
                  <div style={{ fontSize: 12, color: 'var(--amber)', fontFamily: 'var(--font-mono)' }}>
                    ⚠ Nessun holder in inventario
                  </div>
                ) : (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: 6, maxHeight: 220, overflowY: 'auto' }}>
                    {holders.map(h => {
                      const sel = selectedHolder?.alias_holder === h.alias_holder
                      return (
                        <label key={h.alias_holder} style={{
                          display: 'flex', alignItems: 'center', gap: 10,
                          padding: '8px 12px',
                          background: sel ? 'rgba(0,225,255,0.08)' : 'var(--bg-base)',
                          border: `1px solid ${sel ? 'var(--cyan)' : 'var(--border)'}`,
                          borderRadius: 'var(--radius-sm)',
                          cursor: 'pointer', transition: 'all 0.12s',
                        }}>
                          <input type="radio" name="holder" checked={sel}
                            onChange={() => onSelectHolder(h)}
                            style={{ accentColor: 'var(--cyan)', flexShrink: 0 }} />
                          <span className="mono" style={{ fontWeight: 700, fontSize: 14, color: 'var(--cyan)', width: 44, flexShrink: 0 }}>
                            {h.alias_holder}
                          </span>
                          <span style={{ fontSize: 12, color: 'var(--text-secondary)', flex: 1 }}>
                            {h.alias_holder === 'E' ? 'Idraulico base (richiede bussola)' : decodificaTipoHolder(h.alias_holder)}
                          </span>
                          <span style={{ fontSize: 11, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>
                            ×{h.quantita}
                          </span>
                        </label>
                      )
                    })}
                  </div>
                )}
              </div>

              {/* Selezione bussola (solo se holder "E") */}
              {serveNucleare && (
                <div>
                  <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--amber)', letterSpacing: '0.08em', marginBottom: 10 }}>
                    BUSSOLA IDRAULICO — seleziona diametro
                  </div>
                  {bussole.length === 0 ? (
                    <div style={{ fontSize: 12, color: 'var(--red)', fontFamily: 'var(--font-mono)' }}>
                      ⚠ Nessuna bussola in inventario
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexWrap: 'wrap', gap: 8 }}>
                      {bussole.map(b => {
                        const sel = selectedBussola?.codice_bussola === b.codice_bussola
                        return (
                          <button key={b.codice_bussola}
                            onClick={() => onSelectBussola(b)}
                            style={{
                              padding: '7px 14px',
                              background: sel ? 'rgba(255,170,0,0.15)' : 'var(--bg-base)',
                              border: `1px solid ${sel ? 'var(--amber)' : 'var(--border)'}`,
                              borderRadius: 'var(--radius-sm)',
                              cursor: 'pointer', transition: 'all 0.12s',
                              display: 'flex', flexDirection: 'column', alignItems: 'center', gap: 2,
                            }}>
                            <span className="mono" style={{ fontWeight: 700, fontSize: 13, color: sel ? 'var(--amber)' : 'var(--text-primary)' }}>
                              {b.codice_bussola}
                            </span>
                            <span style={{ fontSize: 10, color: 'var(--text-dim)' }}>{b.diametro}</span>
                            <span style={{ fontSize: 9, color: 'var(--text-dim)', fontFamily: 'var(--font-mono)' }}>×{b.quantita}</span>
                          </button>
                        )
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* Anteprima alias finale */}
              {aliasFinale && (
                <div style={{ background: 'rgba(0,225,255,0.06)', border: '1px solid rgba(0,225,255,0.2)', borderRadius: 'var(--radius-sm)', padding: '10px 14px' }}>
                  <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', marginBottom: 4 }}>ALIAS FINALE NEL DB</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                    <span className="mono" style={{ fontSize: 15, fontWeight: 700, color: 'var(--text-secondary)' }}>
                      {utensile.alias_utensile.toUpperCase()}
                    </span>
                    <span style={{ color: 'var(--text-dim)', fontSize: 14 }}>+</span>
                    <span className="mono" style={{ fontSize: 15, fontWeight: 700, color: 'var(--cyan)' }}>
                      {serveNucleare ? selectedBussola?.codice_bussola : selectedHolder?.alias_holder}
                    </span>
                    <span style={{ color: 'var(--text-dim)', fontSize: 14 }}>=</span>
                    <span className="mono" style={{ fontSize: 15, fontWeight: 800, color: 'var(--green)' }}>
                      {aliasFinale}
                    </span>
                  </div>
                </div>
              )}

              {/* Destinazione */}
              <div>
                <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.08em', marginBottom: 10 }}>
                  DESTINAZIONE
                </div>
                <div style={{ display: 'flex', gap: 10 }}>
                  {[
                    { val: 'scaffale', label: '🏠 Scaffale',   desc: 'Pronto, senza posizione fissa' },
                    { val: 'macchina', label: '🔧 In Macchina', desc: 'Inserisci posizione carosello' },
                  ].map(({ val, label, desc }) => (
                    <label key={val} style={{
                      flex: 1, display: 'flex', flexDirection: 'column', gap: 4,
                      padding: '10px 14px',
                      background: destinazione === val ? 'rgba(0,225,255,0.08)' : 'var(--bg-base)',
                      border: `1px solid ${destinazione === val ? 'var(--cyan)' : 'var(--border)'}`,
                      borderRadius: 'var(--radius-sm)', cursor: 'pointer',
                    }}>
                      <div style={{ display: 'flex', alignItems: 'center', gap: 8 }}>
                        <input type="radio" name="dest" value={val} checked={destinazione === val}
                          onChange={() => onDestinazione(val)} style={{ accentColor: 'var(--cyan)' }} />
                        <span style={{ fontWeight: 600, fontSize: 13 }}>{label}</span>
                      </div>
                      <span style={{ fontSize: 11, color: 'var(--text-dim)', paddingLeft: 22 }}>{desc}</span>
                    </label>
                  ))}
                </div>

                {/* Campo posizione */}
                {destinazione === 'macchina' && (
                  <div style={{ marginTop: 10 }}>
                    <label style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', display: 'block', marginBottom: 4, letterSpacing: '0.08em' }}>
                      POSIZIONE NEL CAROSELLO (1-120)
                    </label>
                    <input
                      className="input"
                      type="number" min="1" max="120"
                      placeholder="es. 42"
                      value={posizione}
                      onChange={e => onPosizione(e.target.value)}
                      style={{ maxWidth: 140 }}
                    />
                  </div>
                )}
              </div>
            </>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '16px 24px', borderTop: '1px solid var(--border)', flexShrink: 0 }}>
          {error && (
            <div style={{ marginBottom: 12, padding: '8px 12px', background: 'rgba(255,68,85,0.1)', border: '1px solid rgba(255,68,85,0.3)', borderRadius: 'var(--radius-sm)', fontSize: 12, fontFamily: 'var(--font-mono)', color: 'var(--red)' }}>
              ⚠ {error}
            </div>
          )}
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button className="btn btn-ghost" onClick={onClose} disabled={busy}>Annulla</button>
            <button className="btn btn-primary" onClick={onConferma} disabled={!canConfirm} style={{ minWidth: 160 }}>
              {busy ? <><Spinner small /> Montaggio...</> : '✓ Conferma Montaggio'}
            </button>
          </div>
        </div>

      </div>
    </div>
  )
}

// ── Helpers ────────────────────────────────────────────────

const HOLDER_TYPES = {
  A: 'Attacco Filettato', B: 'Forte Serraggio', C: 'Manicotto',
  D: 'Pinza ER', E: 'Idraulico', F: 'Idraulico Tendo Slim',
  G: 'Idraulico Tendo Slim Lungo', H: 'Caletto BILZ',
  I: 'Caletto', J: 'Caletto MST Curvo', K: 'Weldon',
  L: 'Caletto KAISER', M: 'Idraulico Tendo ZERO',
}

function decodificaTipoHolder(cod) {
  if (!cod) return '—'
  const lettera = cod[0].toUpperCase()
  const num = cod.slice(1)
  const tipo = HOLDER_TYPES[lettera] || '—'
  return num ? `${tipo} (${cod})` : tipo
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
