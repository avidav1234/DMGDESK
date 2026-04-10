// RiepilogoTurno.jsx — Riepilogo turno giornaliero
import { useState, useEffect, useCallback } from 'react'
import { InfoTooltip } from '../components/UI'
import { useNavigate } from 'react-router-dom'

function fmtData(iso) {
  if (!iso) return '—'
  const [y, m, d] = iso.split('T')[0].split('-')
  return `${d}/${m}/${y}`
}
function fmtOra(iso) {
  if (!iso) return '—'
  return iso.includes('T') ? iso.split('T')[1].slice(0, 5) : iso.slice(11, 16)
}
function fmtH(sec) {
  if (!sec) return '0h'
  const h = Math.floor(sec / 3600), m = Math.floor((sec % 3600) / 60)
  return m > 0 ? `${h}h ${m}m` : `${h}h`
}

// ── Barra distribuzione commessa ──────────────────────────────────────────────
function BarraCommessa({ item, maxSec, colore }) {
  const pct = maxSec > 0 ? (item.ore_sec / maxSec) * 100 : 0
  return (
    <div style={{ marginBottom: 10 }}>
      <div style={{ display: 'flex', justifyContent: 'space-between',
        fontSize: 12, marginBottom: 3 }}>
        <span style={{ fontFamily: 'var(--font-mono)', fontWeight: 600,
          color: 'var(--color-text-primary)' }}>{item.commessa}</span>
        <span style={{ color: 'var(--color-text-secondary)' }}>
          {item.ore_str} · {item.pct}%
          {item.ore_cam_sec > 0 && (
            <span style={{ color: '#0f766e', marginLeft: 8 }}>
              CAM {fmtH(item.ore_cam_sec)}
            </span>
          )}
        </span>
      </div>
      <div style={{ height: 7, background: 'var(--color-border-tertiary)',
        borderRadius: 4, overflow: 'hidden' }}>
        <div style={{ width: `${pct}%`, height: '100%',
          background: colore || '#1D5FAD', borderRadius: 4,
          transition: 'width 0.5s' }}/>
      </div>
    </div>
  )
}

// ── Card snapshot ─────────────────────────────────────────────────────────────
function CardSnapshot({ snap, titolo, colore, icon, onRigenera, caricando }) {
  const navigate = useNavigate()
  if (!snap) return null
  const errore = snap.errore
  const isLive = snap._live
  const maxSec = Math.max(...(snap.distribuzione || []).map(d => d.ore_sec), 1)

  return (
    <div style={{ background: 'var(--color-background-primary)',
      border: '1px solid var(--color-border-tertiary)',
      borderRadius: 12, overflow: 'hidden', flex: 1, minWidth: 280 }}>

      {/* Header */}
      <div style={{ background: colore, padding: '14px 20px',
        display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
        <div>
          <div style={{ fontSize: 13, fontWeight: 600, color: '#fff' }}>
            {icon} {titolo}
          </div>
          {!errore && (
            <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.7)', marginTop: 2 }}>
              {fmtOra(snap.inizio)} → {fmtOra(snap.fine)}
              {isLive && ' · live'}
            </div>
          )}
        </div>
        <button onClick={onRigenera} disabled={caricando}
          style={{ fontSize: 11, padding: '4px 10px', borderRadius: 5,
            background: 'rgba(255,255,255,0.2)', border: '1px solid rgba(255,255,255,0.3)',
            color: '#fff', cursor: caricando ? 'default' : 'pointer',
            opacity: caricando ? 0.6 : 1 }}>
          {caricando ? '...' : '↺ Rigenera'}
        </button>
      </div>

      {errore ? (
        <div style={{ padding: 20, color: 'var(--color-text-danger)', fontSize: 13 }}>
          Errore: {errore}
        </div>
      ) : (
        <div style={{ padding: '16px 20px' }}>

          {/* KPI row */}
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)',
            gap: 12, marginBottom: 20 }}>
            {[
              { label: 'Ore macchina', value: snap.ore_macchina_str || '0h', color: colore,
                tooltip: 'Ore totali in cui la macchina ha eseguito programmi NC nella finestra selezionata (turno/giorno/settimana).' },
              { label: 'Programmi', value: snap.n_programmi || 0,
                tooltip: 'Numero di programmi NC completati nella finestra selezionata, su tutte le commesse.' },
              { label: 'Commesse', value: snap.n_commesse || 0,
                tooltip: 'Numero di commesse distinte lavorate nella finestra selezionata.' },
            ].map(k => (
              <div key={k.label} style={{ textAlign: 'center',
                background: 'var(--color-background-secondary)',
                borderRadius: 8, padding: '10px 8px' }}>
                <div style={{ fontSize: 20, fontWeight: 700,
                  color: k.color || 'var(--color-text-primary)',
                  fontFamily: 'var(--font-mono)' }}>{k.value}</div>
                <div style={{ fontSize: 10, color: 'var(--color-text-secondary)',
                  marginTop: 2, display:'flex', alignItems:'center', justifyContent:'center', gap:3 }}>
                  {k.label}{k.tooltip && <InfoTooltip text={k.tooltip} />}
                </div>
              </div>
            ))}
          </div>

          {/* CAM (solo finestra giorno) */}
          {snap.finestra === 'giorno' && snap.ore_cam_sec > 0 && (
            <div style={{ background: '#E1F5EE', border: '1px solid #9FE1CB',
              borderRadius: 8, padding: '10px 14px', marginBottom: 16,
              display: 'flex', alignItems: 'center', gap: 12 }}>
              <div style={{ fontSize: 18, fontWeight: 700, color: '#085041',
                fontFamily: 'var(--font-mono)' }}>{snap.ore_cam_str}</div>
              <div style={{ fontSize: 12, color: '#0F6E56', display:'flex', alignItems:'center', gap:4 }}>
                ore CAM · {snap.distribuzione?.filter(d => d.ore_cam_sec > 0).length || 0} commesse
                <InfoTooltip text={"Ore di programmazione Cimatron registrate dal CAM Tracker su CAM35 oggi.\nMostrate solo per la finestra giornaliera — non disponibile per turno/settimana."} />
              </div>
            </div>
          )}

          {/* Distribuzione commesse */}
          {snap.distribuzione?.length > 0 ? (
            <div>
              <div style={{ fontSize: 10, fontWeight: 700,
                color: 'var(--color-text-secondary)',
                textTransform: 'uppercase', letterSpacing: '0.06em',
                marginBottom: 12, display:'flex', alignItems:'center', gap:4 }}>
                Distribuzione ore macchina
                <InfoTooltip text={"Ripartizione delle ore di lavorazione per commessa nella finestra selezionata.\nLa barra mostra la proporzione di ogni commessa sul totale ore macchina."} />
              </div>
              {snap.distribuzione.map(d => (
                <div key={d.commessa}>
                  <BarraCommessa item={d} maxSec={maxSec} colore={colore}/>
                  {d.progetto_id && (
                    <div style={{ textAlign: 'right', marginTop: -6, marginBottom: 8 }}>
                      <button onClick={() => navigate(`/rendiconto/${d.progetto_id}`)}
                        style={{ fontSize: 11, color: colore, background: 'transparent',
                          border: 'none', cursor: 'pointer', textDecoration: 'underline',
                          padding: 0 }}>
                        Apri rendiconto →
                      </button>
                    </div>
                  )}
                </div>
              ))}
            </div>
          ) : (
            <div style={{ textAlign: 'center', padding: '20px 0',
              color: 'var(--color-text-secondary)', fontSize: 13 }}>
              Nessuna lavorazione in questa finestra
            </div>
          )}

        </div>
      )}
    </div>
  )
}

// ── Storico mini-tabella ──────────────────────────────────────────────────────
function TabellaStorico({ giorni }) {
  if (!giorni?.length) return null
  return (
    <div style={{ background: 'var(--color-background-primary)',
      border: '1px solid var(--color-border-tertiary)',
      borderRadius: 12, overflow: 'hidden', marginTop: 16 }}>
      <div style={{ padding: '12px 20px', borderBottom: '1px solid var(--color-border-tertiary)',
        fontSize: 11, fontWeight: 700, color: 'var(--color-text-secondary)',
        textTransform: 'uppercase', letterSpacing: '0.06em' }}>
        Storico turni
      </div>
      <table style={{ width: '100%', borderCollapse: 'collapse', fontSize: 12 }}>
        <thead>
          <tr style={{ background: 'var(--color-background-secondary)' }}>
            {['Data', 'Notte (mac)', 'Giorno (mac)', 'CAM', 'Commesse'].map(h => (
              <th key={h} style={{ padding: '8px 16px', textAlign: 'left',
                fontWeight: 600, color: 'var(--color-text-secondary)',
                fontSize: 11 }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {giorni.map(g => (
            <tr key={g.data} style={{ borderTop: '1px solid var(--color-border-tertiary)' }}>
              <td style={{ padding: '8px 16px', fontFamily: 'var(--font-mono)',
                color: 'var(--color-text-primary)' }}>
                {fmtData(g.data)}
              </td>
              <td style={{ padding: '8px 16px', color: '#1D5FAD', fontWeight: 600 }}>
                {g.notte?.ore_macchina_str || '—'}
              </td>
              <td style={{ padding: '8px 16px', color: '#0d2d5e', fontWeight: 600 }}>
                {g.giorno?.ore_macchina_str || '—'}
              </td>
              <td style={{ padding: '8px 16px', color: '#0f766e' }}>
                {g.giorno?.ore_cam_str || '—'}
              </td>
              <td style={{ padding: '8px 16px', color: 'var(--color-text-secondary)' }}>
                {Math.max(g.notte?.n_commesse || 0, g.giorno?.n_commesse || 0) || '—'}
              </td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  )
}

// ── Pagina principale ─────────────────────────────────────────────────────────
export default function RiepilogoTurno() {
  const [oggi, setOggi] = useState(null)
  const [storico, setStorico] = useState(null)
  const [loading, setLoading] = useState(true)
  const [generando, setGenerando] = useState({ notte: false, giorno: false })
  const [dataSelezionata, setDataSelezionata] = useState(
    new Date().toISOString().slice(0, 10)
  )

  const caricaOggi = useCallback(() => {
    setLoading(true)
    fetch('/api/turno/oggi')
      .then(r => r.ok ? r.json() : null)
      .then(d => { setOggi(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [])

  const caricaStorico = useCallback(() => {
    fetch('/api/turno/storico?giorni=14')
      .then(r => r.ok ? r.json() : null)
      .then(d => setStorico(d))
      .catch(() => {})
  }, [])

  useEffect(() => {
    caricaOggi()
    caricaStorico()
  }, [caricaOggi, caricaStorico])

  const rigenera = async (finestra) => {
    setGenerando(g => ({ ...g, [finestra]: true }))
    try {
      await fetch('/api/turno/genera', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ finestra, data: dataSelezionata }),
      })
      caricaOggi()
      caricaStorico()
    } catch {}
    setGenerando(g => ({ ...g, [finestra]: false }))
  }

  return (
    <div style={{ display: 'flex', flexDirection: 'column', height: '100%',
      background: 'var(--color-background-tertiary)', overflow: 'auto' }}>

      {/* Header */}
      <div style={{ background: '#0d2d5e', color: '#fff',
        padding: '14px 24px', display: 'flex', alignItems: 'center',
        gap: 12, flexShrink: 0 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontWeight: 700, fontSize: 15 }}>Riepilogo Turno</div>
          <div style={{ fontSize: 11, color: 'rgba(255,255,255,0.55)',
            fontFamily: 'var(--font-mono)' }}>
            Notte 16:30→07:30 · Giorno 07:30→16:30
          </div>
        </div>
        <input type="date" value={dataSelezionata}
          onChange={e => setDataSelezionata(e.target.value)}
          style={{ padding: '5px 10px', borderRadius: 6, fontSize: 12,
            border: '1px solid rgba(255,255,255,0.3)',
            background: 'rgba(255,255,255,0.1)', color: '#fff' }}/>
        <button onClick={caricaOggi}
          style={{ fontSize: 12, padding: '5px 12px', borderRadius: 6,
            background: 'rgba(255,255,255,0.15)',
            border: '1px solid rgba(255,255,255,0.3)',
            color: '#fff', cursor: 'pointer' }}>
          ↺ Aggiorna
        </button>
      </div>

      <div style={{ padding: '16px 24px', flex: 1 }}>

        {loading ? (
          <div style={{ textAlign: 'center', padding: 40,
            color: 'var(--color-text-secondary)', fontSize: 13 }}>
            Caricamento...
          </div>
        ) : (
          <>
            {/* Le due card affiancate */}
            <div style={{ display: 'flex', gap: 16, flexWrap: 'wrap' }}>
              <CardSnapshot
                snap={oggi?.notte}
                titolo="Finestra notte"
                colore="#1D5FAD"
                icon="🌙"
                onRigenera={() => rigenera('notte')}
                caricando={generando.notte}
              />
              <CardSnapshot
                snap={oggi?.giorno}
                titolo="Finestra giorno"
                colore="#0f766e"
                icon="☀"
                onRigenera={() => rigenera('giorno')}
                caricando={generando.giorno}
              />
            </div>

            {/* Storico */}
            {storico?.giorni?.length > 0 && (
              <TabellaStorico giorni={storico.giorni}/>
            )}
          </>
        )}
      </div>
    </div>
  )
}
