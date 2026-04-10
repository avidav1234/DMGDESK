// pages/Generatore.jsx — Generatore codici utensili CNC
import { useState, useEffect } from 'react'
import { InfoTooltip } from '../components/UI'
import { api } from '../api/client'
import { Loader, ErrorBanner, SectionHeader } from '../components/UI'

export default function Generatore() {
  const [tipologie, setTipologie] = useState([])
  const [holders, setHolders]     = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [result, setResult]       = useState(null)
  const [busy, setBusy]           = useState(false)
  const [copied, setCopied]       = useState(null)

  const [form, setForm] = useState({
    tipo_utensile: '', diametro: '', r2_x: '', l: '', vd: '', fp: '',
    tipo_holder: '', diam_holder: '', fresa_dedicata: false, speciale: false,
  })

  useEffect(() => {
    Promise.all([api.getTipologie(), api.getHolderTypes()])
      .then(([t, h]) => {
        setTipologie(t); setHolders(h)
        setForm(f => ({ ...f, tipo_utensile: t[0]?.chiave || '', tipo_holder: h[0]?.chiave || '', diam_holder: h[0]?.diametri[0] || '' }))
      })
      .catch(e => setError(e.message))
      .finally(() => setLoading(false))
  }, [])

  const f = (field, val) => setForm(prev => ({ ...prev, [field]: val }))

  const tipoAttivo = tipologie.find(t => t.chiave === form.tipo_utensile)
  const holderAttivo = holders.find(h => h.chiave === form.tipo_holder)

  const genera = async () => {
    try {
      setBusy(true); setError(null); setResult(null)
      const data = await api.generaCodice(form)
      setResult(data)
    } catch (e) { setError(e.message) } finally { setBusy(false) }
  }

  const copia = (text, key) => {
    // navigator.clipboard richiede HTTPS — fallback execCommand per HTTP su LAN
    if (navigator.clipboard && window.isSecureContext) {
      navigator.clipboard.writeText(text)
        .then(() => { setCopied(key); setTimeout(() => setCopied(null), 2000) })
        .catch(() => copiaFallback(text, key))
    } else {
      copiaFallback(text, key)
    }
  }

  const copiaFallback = (text, key) => {
    const el = document.createElement('textarea')
    el.value = text
    el.style.cssText = 'position:fixed;top:-9999px;left:-9999px;opacity:0'
    document.body.appendChild(el)
    el.focus()
    el.select()
    try {
      document.execCommand('copy')
      setCopied(key)
      setTimeout(() => setCopied(null), 2000)
    } catch (_) {}
    document.body.removeChild(el)
  }

  if (loading) return <Loader text="Caricamento catalogo..." />

  return (
    <div className="fade-in" style={{ height: '100%', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <SectionHeader title="Generatore Codici" subtitle="Genera Nome CAM e Alias CNC per utensile" />
      <ErrorBanner message={error} onClose={() => setError(null)} />

      <div style={{ display: 'flex', gap: 16, flex: 1, overflow: 'hidden' }}>
        {/* Form sinistra */}
        <div className="card" style={{ flex: '0 0 340px', padding: 20, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 14 }}>

          <Field label="Tipologia Utensile">
            <select className="input" value={form.tipo_utensile} onChange={e => f('tipo_utensile', e.target.value)}>
              {tipologie.map(t => <option key={t.chiave} value={t.chiave}>{t.nome}</option>)}
            </select>
          </Field>

          <Field label="Diametro (mm)">
            <input className="input" type="number" step="0.1" min="0" value={form.diametro} onChange={e => f('diametro', e.target.value)} placeholder="es. 12" />
          </Field>

          {tipoAttivo?.ha_r2 && (
            <Field label="R2 / Raggio (mm)">
              <input className="input" type="number" step="0.1" value={form.r2_x} onChange={e => f('r2_x', e.target.value)} placeholder="es. 2" />
            </Field>
          )}
          {tipoAttivo?.ha_l && (
            <Field label="Lunghezza L (mm)">
              <input className="input" type="number" value={form.l} onChange={e => f('l', e.target.value)} placeholder="es. 80" />
            </Field>
          )}
          {tipoAttivo?.ha_vd && (
            <Field label="Velocità Discesa VD">
              <input className="input" type="number" step="0.1" value={form.vd} onChange={e => f('vd', e.target.value)} placeholder="es. 5.0" />
            </Field>
          )}
          {tipoAttivo?.ha_x && (
            <Field label="X (Passo)">
              <input className="input" value={form.r2_x} onChange={e => f('r2_x', e.target.value)} placeholder="es. 1.5" />
            </Field>
          )}

          <Field label="FP (Frequenza Passate)">
            <input className="input" type="number" value={form.fp} onChange={e => f('fp', e.target.value)} placeholder="es. 80" />
          </Field>

          <Field label="Porta-utensile">
            <select className="input" value={form.tipo_holder} onChange={e => {
              const h = holders.find(x => x.chiave === e.target.value)
              f('tipo_holder', e.target.value); f('diam_holder', h?.diametri[0] || '')
            }}>
              {holders.map(h => <option key={h.chiave} value={h.chiave}>{h.chiave.replace(/_/g,' ')} ({h.lettera})</option>)}
            </select>
          </Field>

          {holderAttivo && (
            <Field label="Diametro Holder">
              <select className="input" value={form.diam_holder} onChange={e => f('diam_holder', e.target.value)}>
                {holderAttivo.diametri.map(d => <option key={d} value={d}>{d}</option>)}
              </select>
            </Field>
          )}

          <div style={{ display: 'flex', gap: 16 }}>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)' }}>
              <input type="checkbox" checked={form.speciale} onChange={e => f('speciale', e.target.checked)} />
              Speciale (X)
            </label>
            <label style={{ display: 'flex', alignItems: 'center', gap: 6, cursor: 'pointer', fontSize: 13, color: 'var(--text-secondary)' }}>
              <input type="checkbox" checked={form.fresa_dedicata} onChange={e => f('fresa_dedicata', e.target.checked)} />
              Dedicata
            </label>
          </div>

          <button className="btn btn-primary" onClick={genera} disabled={busy || !form.diametro || !form.fp}
            style={{ marginTop: 4 }}>
            {busy ? 'Generazione...' : '⌨ Genera Codice'}
          </button>
        </div>

        {/* Risultato destra */}
        <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: 12 }}>
          {result ? (
            <div className="fade-in" style={{ display: 'flex', flexDirection: 'column', gap: 12 }}>
              {[
                { label: 'NOME CAM', value: result.nome, key: 'nome',
                  tooltip: 'Nome file usato in Cimatron per il post-processing.\nConvention: TipoFresaDiamRLungFHz[GruppoPasso]\nEs: FS25R2L85 = Fresa sferica Ø25mm R2 L85mm' },
                { label: 'NOME CNC (ALIAS)', value: result.commento, key: 'commento',
                  tooltip: 'Alias utensile da inserire nel TOA Sinumerik (campo Kommentar).\nUsato da DMGDesk per abbinare il consumo utensile ai cicli lavorazione rilevati dal LOG macchina.' },
              ].map(({ label, value, key }) => (
                <div key={key} className="card" style={{ padding: 20 }}>
                  <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>{label}</div>
                  <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
                    <div className="mono" style={{ fontSize: 22, fontWeight: 700, color: key === 'nome' ? 'var(--navy-700)' : 'var(--green)', flex: 1, wordBreak: 'break-all' }}>
                      {value}
                    </div>
                    <button className="btn btn-ghost" style={{ fontSize: 12, flexShrink: 0 }} onClick={() => copia(value, key)}>
                      {copied === key ? '✓ Copiato' : '⎘ Copia'}
                    </button>
                  </div>
                </div>
              ))}

              {/* Anteprima NC */}
              <div className="card" style={{ padding: 20 }}>
                <div style={{ fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.1em', textTransform: 'uppercase', marginBottom: 10 }}>ANTEPRIMA CODICE NC</div>
                <pre className="mono" style={{ fontSize: 13, color: 'var(--text-secondary)', lineHeight: 1.8, background: 'var(--bg-base)', padding: 16, borderRadius: 'var(--radius-sm)', overflow: 'auto' }}>
{`T="${result.commento}"
D1
M6
; ${result.nome}`}
                </pre>
              </div>
            </div>
          ) : (
            <div className="card" style={{ flex: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', flexDirection: 'column', gap: 12, color: 'var(--text-dim)' }}>
              <div style={{ fontSize: 48 }}>⌨</div>
              <div style={{ fontSize: 14, fontWeight: 600, color: 'var(--text-secondary)' }}>Compila il form e clicca Genera</div>
              <div style={{ fontSize: 12 }}>Il codice NC apparirà qui</div>
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

function Field({ label, children }) {
  return (
    <div>
      <label style={{ display: 'block', fontSize: 10, fontFamily: 'var(--font-mono)', color: 'var(--text-dim)', letterSpacing: '0.08em', textTransform: 'uppercase', marginBottom: 5 }}>{label}</label>
      {children}
    </div>
  )
}
