// Progetti.jsx — WorkTrack integrato in DMGDesk
// Persistenza su file JSON via /api/progetti invece di localStorage
// Aggiunge: pallet_assegnato, bottone "Lancia in Analisi NC"

import { useState, useEffect, useCallback, useRef } from 'react'
import { useNavigate } from 'react-router-dom'

const API = '/api/progetti'

// ── Palette colori coerente con DMGDesk dark ─────────────────────────────────
const C = {
  bg:       'var(--bg-base)',
  card:     'var(--bg-card)',
  border:   'var(--border)',
  text:     'var(--text-primary)',
  sub:      'var(--text-secondary)',
  muted:    'var(--text-dim)',
  accent:   'var(--cyan)',
  green:    '#22c55e',
  red:      '#ef4444',
  orange:   '#f59e0b',
  blue:     '#3b82f6',
}

function uid() { return Math.random().toString(36).slice(2, 9) }
function nowStr() { return new Date().toLocaleString('it-IT') }

function getProgress(project) {
  const all = (project.steps || []).flatMap(s => s.tasks || [])
  if (!all.length) return 0
  return Math.round(all.filter(t => t.done).length / all.length * 100)
}

function getMpfList(project) {
  const mpf = []
  for (const step of project.steps || []) {
    for (const task of step.tasks || []) {
      if (task.text?.trim().toLowerCase() === 'fresatura') {
        for (const pgm of task.programs || []) {
          if (pgm.tipoGruppo !== 'ipm') mpf.push(pgm)
        }
      }
    }
  }
  return mpf
}

// ── ProgressBar ───────────────────────────────────────────────────────────────
function ProgressBar({ value, color = C.accent }) {
  return (
    <div style={{ height: 4, background: 'var(--bg-hover)', borderRadius: 2, overflow: 'hidden' }}>
      <div style={{ height: '100%', width: `${value}%`, background: color, borderRadius: 2, transition: 'width 0.3s' }} />
    </div>
  )
}

// ── Card singolo progetto ─────────────────────────────────────────────────────
function ProgettoCard({ project, onSelect, onPalletChange, onLanciaNC }) {
  const pct = getProgress(project)
  const mpf = getMpfList(project)
  const color = project.color || C.blue

  return (
    <div
      onClick={() => onSelect(project.id)}
      style={{
        background: C.card, border: `1px solid ${C.border}`,
        borderLeft: `3px solid ${color}`,
        borderRadius: 10, padding: '14px 16px',
        cursor: 'pointer', transition: 'all 0.15s',
        display: 'flex', flexDirection: 'column', gap: 10,
      }}
      onMouseEnter={e => e.currentTarget.style.borderColor = color}
      onMouseLeave={e => e.currentTarget.style.borderLeft = `3px solid ${color}`}
    >
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'flex-start', gap: 10 }}>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 13, fontWeight: 700, color: C.text }}>{project.name}</div>
          {project.description && (
            <div style={{ fontSize: 11, color: C.muted, marginTop: 2 }}>{project.description}</div>
          )}
        </div>
        <div style={{ fontSize: 12, fontWeight: 700, color: pct === 100 ? C.green : C.sub }}>
          {pct}%
        </div>
      </div>

      {/* Barra progresso */}
      <ProgressBar value={pct} color={pct === 100 ? C.green : color} />

      {/* Dettagli */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 8, flexWrap: 'wrap' }}>
        {/* MPF count */}
        {mpf.length > 0 && (
          <span style={{ fontSize: 10, padding: '2px 7px', borderRadius: 4,
            background: 'rgba(59,130,246,0.1)', color: C.blue, fontFamily: 'var(--font-mono)' }}>
            ⚙ {mpf.filter(p => p.stato === 'completato').length}/{mpf.length} MPF
          </span>
        )}

        {/* Pallet assegnato */}
        <div style={{ display: 'flex', alignItems: 'center', gap: 4 }} onClick={e => e.stopPropagation()}>
          <span style={{ fontSize: 10, color: C.muted }}>Pallet:</span>
          <select
            value={project.pallet_assegnato || ''}
            onChange={e => onPalletChange(project.id, e.target.value ? Number(e.target.value) : null)}
            style={{ fontSize: 10, padding: '2px 4px', borderRadius: 4,
              background: 'var(--bg-hover)', border: `1px solid ${C.border}`,
              color: project.pallet_assegnato ? C.accent : C.muted, cursor: 'pointer' }}
          >
            <option value="">—</option>
            {[1,2,3,4,5,6].map(n => <option key={n} value={n}>P{n}</option>)}
          </select>
        </div>

        <div style={{ flex: 1 }} />

        {/* Bottone Lancia NC */}
        {mpf.length > 0 && (
          <button
            onClick={e => { e.stopPropagation(); onLanciaNC(project) }}
            style={{ fontSize: 10, padding: '4px 10px', borderRadius: 5,
              background: 'var(--navy-700)', border: 'none', color: 'white',
              cursor: 'pointer', fontWeight: 700 }}
          >
            📄 Lancia in NC →
          </button>
        )}
      </div>
    </div>
  )
}

// ── Vista dettaglio progetto ──────────────────────────────────────────────────
function ProgettoDetail({ project, onUpdate, onBack }) {
  const toggleTask = (stepId, taskId) => {
    const updated = {
      ...project,
      steps: project.steps.map(s => s.id !== stepId ? s : {
        ...s,
        tasks: s.tasks.map(t => t.id !== taskId ? t : {
          ...t, done: !t.done, doneAt: !t.done ? new Date().toISOString().slice(0,10) : null
        })
      })
    }
    onUpdate(updated)
  }

  const pct = getProgress(project)
  const color = project.color || C.blue

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: 12, height: '100%', overflow: 'auto' }}>
      {/* Header */}
      <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
        <button onClick={onBack} style={{ background: 'none', border: `1px solid ${C.border}`,
          borderRadius: 6, padding: '4px 10px', cursor: 'pointer', color: C.sub, fontSize: 12 }}>
          ← Indietro
        </button>
        <div style={{ flex: 1 }}>
          <div style={{ fontSize: 16, fontWeight: 800, color: C.text }}>{project.name}</div>
          {project.description && <div style={{ fontSize: 12, color: C.muted }}>{project.description}</div>}
        </div>
        <div style={{ fontSize: 18, fontWeight: 900, color: pct === 100 ? C.green : color }}>{pct}%</div>
      </div>
      <ProgressBar value={pct} color={pct === 100 ? C.green : color} />

      {/* Steps e task */}
      {(project.steps || []).map(step => (
        <div key={step.id} style={{ background: C.card, border: `1px solid ${C.border}`,
          borderRadius: 8, overflow: 'hidden' }}>
          {/* Step header */}
          <div style={{ padding: '8px 14px', background: 'var(--bg-hover)',
            borderBottom: `1px solid ${C.border}`, fontSize: 11, fontWeight: 700,
            color: C.sub, letterSpacing: '0.06em' }}>
            {step.title}
          </div>
          {/* Task list */}
          {(step.tasks || []).map(task => (
            <div key={task.id} style={{ display: 'flex', alignItems: 'center', gap: 10,
              padding: '9px 14px', borderBottom: `1px solid ${C.border}`,
              opacity: task.done ? 0.6 : 1 }}>
              <div
                onClick={() => toggleTask(step.id, task.id)}
                style={{ width: 18, height: 18, borderRadius: 4, flexShrink: 0,
                  border: `2px solid ${task.done ? C.green : C.border}`,
                  background: task.done ? C.green : 'transparent',
                  cursor: 'pointer', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
                {task.done && <span style={{ color: 'white', fontSize: 11, fontWeight: 900 }}>✓</span>}
              </div>
              <span style={{ flex: 1, fontSize: 13, color: C.text,
                textDecoration: task.done ? 'line-through' : 'none' }}>
                {task.text}
              </span>
              {task.doneAt && <span style={{ fontSize: 10, color: C.muted }}>{task.doneAt}</span>}
              {/* Sottopannello MPF per task "fresatura" */}
              {task.text?.trim().toLowerCase() === 'fresatura' && (task.programs || []).length > 0 && (
                <span style={{ fontSize: 10, padding: '2px 6px', borderRadius: 4,
                  background: 'rgba(59,130,246,0.1)', color: C.blue }}>
                  ⚙ {(task.programs||[]).filter(p=>p.stato==='completato').length}/{(task.programs||[]).length}
                </span>
              )}
            </div>
          ))}
        </div>
      ))}
    </div>
  )
}

// ── Nuovo progetto dialog ─────────────────────────────────────────────────────
function NuovoProgettoDialog({ templates, onCrea, onClose }) {
  const [name, setName] = useState('')
  const [desc, setDesc] = useState('')
  const [color, setColor] = useState('#3b82f6')
  const [tmplId, setTmplId] = useState(templates[0]?.id || '')

  const COLORS = ['#3b82f6','#22c55e','#f59e0b','#ef4444','#8b5cf6','#06b6d4','#f97316']

  const crea = () => {
    if (!name.trim()) return
    const tmpl = templates.find(t => t.id === tmplId)
    const steps = tmpl
      ? tmpl.steps.map(s => ({
          ...s, id: uid(),
          tasks: s.tasks.map(t => ({ ...t, id: uid(), done: false, doneAt: null, note: '' }))
        }))
      : []
    onCrea({ id: uid(), name: name.trim(), description: desc.trim(),
             color, steps, createdAt: new Date().toISOString().slice(0,10),
             archived: false, pallet_assegnato: null, log: [] })
  }

  return (
    <div style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.5)',
      display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 200 }}>
      <div style={{ background: C.card, borderRadius: 12, padding: 24,
        width: 420, border: `1px solid ${C.border}`, display: 'flex', flexDirection: 'column', gap: 14 }}>
        <div style={{ fontSize: 16, fontWeight: 700, color: C.text }}>Nuovo Progetto</div>

        <input value={name} onChange={e => setName(e.target.value)}
          placeholder="Nome commessa / progetto"
          style={{ padding: '8px 12px', borderRadius: 7, fontSize: 13,
            background: 'var(--bg-base)', border: `1px solid ${C.border}`, color: C.text }}
          onFocus={e => e.target.style.borderColor = C.accent}
          onBlur={e => e.target.style.borderColor = C.border} />

        <input value={desc} onChange={e => setDesc(e.target.value)}
          placeholder="Descrizione (opzionale)"
          style={{ padding: '8px 12px', borderRadius: 7, fontSize: 13,
            background: 'var(--bg-base)', border: `1px solid ${C.border}`, color: C.text }} />

        {/* Template */}
        {templates.length > 0 && (
          <div>
            <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>TEMPLATE</div>
            <div style={{ display: 'flex', flexDirection: 'column', gap: 4 }}>
              {templates.map(t => (
                <label key={t.id} style={{ display: 'flex', alignItems: 'center', gap: 8,
                  padding: '7px 10px', borderRadius: 6, cursor: 'pointer',
                  background: tmplId === t.id ? 'rgba(0,225,255,0.06)' : 'var(--bg-base)',
                  border: `1px solid ${tmplId === t.id ? C.accent : C.border}` }}>
                  <input type="radio" name="tmpl" checked={tmplId===t.id}
                    onChange={() => setTmplId(t.id)} style={{ accentColor: C.accent }} />
                  <span style={{ fontSize: 12, color: C.text }}>{t.name}</span>
                  <span style={{ fontSize: 10, color: C.muted }}>
                    {t.steps?.length} fasi · {t.steps?.flatMap(s=>s.tasks||[]).length} task
                  </span>
                </label>
              ))}
            </div>
          </div>
        )}

        {/* Colore */}
        <div>
          <div style={{ fontSize: 11, color: C.muted, marginBottom: 6 }}>COLORE</div>
          <div style={{ display: 'flex', gap: 6 }}>
            {COLORS.map(c => (
              <div key={c} onClick={() => setColor(c)}
                style={{ width: 22, height: 22, borderRadius: '50%', background: c,
                  cursor: 'pointer', border: `2px solid ${color===c ? 'white' : 'transparent'}`,
                  outline: color===c ? `2px solid ${c}` : 'none' }} />
            ))}
          </div>
        </div>

        <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end', marginTop: 4 }}>
          <button onClick={onClose} style={{ padding: '8px 16px', borderRadius: 7,
            background: 'var(--bg-hover)', border: `1px solid ${C.border}`,
            color: C.sub, cursor: 'pointer', fontSize: 12 }}>Annulla</button>
          <button onClick={crea} disabled={!name.trim()}
            style={{ padding: '8px 20px', borderRadius: 7,
              background: name.trim() ? 'var(--navy-700)' : 'var(--bg-hover)',
              border: 'none', color: name.trim() ? 'white' : C.muted,
              cursor: name.trim() ? 'pointer' : 'not-allowed', fontSize: 12, fontWeight: 700 }}>
            Crea Progetto
          </button>
        </div>
      </div>
    </div>
  )
}

// ── App principale ────────────────────────────────────────────────────────────
export default function Progetti() {
  const navigate = useNavigate()
  const [projects, setProjects]     = useState([])
  const [templates, setTemplates]   = useState([])
  const [loading, setLoading]       = useState(true)
  const [error, setError]           = useState(null)
  const [selected, setSelected]     = useState(null)   // id progetto aperto
  const [showNuovo, setShowNuovo]   = useState(false)
  const [search, setSearch]         = useState('')
  const [lanciaMsg, setLanciaMsg]   = useState(null)
  const saveTimer = useRef(null)

  // ── Carica dati ─────────────────────────────────────────────────────────────
  const load = useCallback(async () => {
    try {
      const r = await fetch(API + '/')
      if (!r.ok) throw new Error('Errore server')
      const d = await r.json()
      setProjects(d.projects || [])
      setTemplates(d.templates || [])
      setError(null)
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [])

  useEffect(() => { load() }, [load])

  // ── Salva progetto (debounced) ───────────────────────────────────────────────
  const saveProject = useCallback(async (project) => {
    setProjects(prev => prev.map(p => p.id === project.id ? project : p))
    clearTimeout(saveTimer.current)
    saveTimer.current = setTimeout(async () => {
      try {
        await fetch(`${API}/${project.id}`, {
          method: 'PUT',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ data: project })
        })
      } catch {}
    }, 800)
  }, [])

  // ── Crea progetto ────────────────────────────────────────────────────────────
  const creaProgetto = async (project) => {
    setProjects(prev => [...prev, project])
    setShowNuovo(false)
    setSelected(project.id)
    try {
      await fetch(`${API}/${project.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ data: project })
      })
    } catch {}
  }

  // ── Elimina progetto ─────────────────────────────────────────────────────────
  const eliminaProgetto = async (id) => {
    setProjects(prev => prev.filter(p => p.id !== id))
    setSelected(null)
    try { await fetch(`${API}/${id}`, { method: 'DELETE' }) } catch {}
  }

  // ── Imposta pallet ───────────────────────────────────────────────────────────
  const setPallet = async (projectId, pallet) => {
    setProjects(prev => prev.map(p => p.id === projectId ? { ...p, pallet_assegnato: pallet } : p))
    try {
      await fetch(`${API}/${projectId}/pallet`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ pallet })
      })
    } catch {}
  }

  // ── Lancia in Analisi NC ─────────────────────────────────────────────────────
  const lanciaInNC = (project) => {
    const mpf = getMpfList(project)
    if (!mpf.length) return
    // Passa i nomi file via sessionStorage — AnalisiNC li intercetta
    sessionStorage.setItem('dmgdesk_lancio_nc', JSON.stringify({
      projectId: project.id,
      projectName: project.name,
      nomeCartella: project.name.replace(/[^a-zA-Z0-9_-]/g, '_').toUpperCase(),
      mpfFiles: mpf.map(p => p.filename),
    }))
    setLanciaMsg(`✓ ${mpf.length} file pronti — apertura Analisi NC...`)
    setTimeout(() => { navigate('/analisi-nc') }, 1200)
  }

  const selectedProject = projects.find(p => p.id === selected)
  const filtered = projects.filter(p =>
    !p.archived &&
    (search === '' || p.name.toLowerCase().includes(search.toLowerCase()))
  )

  if (loading) return (
    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'center', height: '100%', color: C.muted }}>
      Caricamento progetti...
    </div>
  )

  return (
    <div style={{ height: '100%', display: 'flex', gap: 12 }}>

      {/* ── Lista progetti (sinistra) ── */}
      <div style={{ width: 320, flexShrink: 0, display: 'flex', flexDirection: 'column', gap: 8 }}>

        {/* Toolbar */}
        <div style={{ display: 'flex', gap: 6 }}>
          <input value={search} onChange={e => setSearch(e.target.value)}
            placeholder="Cerca progetto..."
            style={{ flex: 1, padding: '7px 10px', borderRadius: 7, fontSize: 12,
              background: 'var(--bg-card)', border: `1px solid ${C.border}`, color: C.text }} />
          <button onClick={() => setShowNuovo(true)}
            style={{ padding: '7px 14px', borderRadius: 7, fontSize: 12, fontWeight: 700,
              background: 'var(--navy-700)', border: 'none', color: 'white', cursor: 'pointer' }}>
            + Nuovo
          </button>
        </div>

        {/* Messaggio lancio NC */}
        {lanciaMsg && (
          <div style={{ padding: '8px 12px', borderRadius: 7, fontSize: 12,
            background: 'rgba(22,163,74,0.1)', border: '1px solid rgba(22,163,74,0.2)',
            color: '#15803d' }}>{lanciaMsg}</div>
        )}

        {error && (
          <div style={{ padding: '8px 12px', borderRadius: 7, fontSize: 12,
            background: 'rgba(239,68,68,0.1)', color: '#ef4444' }}>
            ⚠ {error} — <span style={{ cursor: 'pointer', textDecoration: 'underline' }} onClick={load}>Riprova</span>
          </div>
        )}

        {/* Lista */}
        <div style={{ flex: 1, overflow: 'auto', display: 'flex', flexDirection: 'column', gap: 8 }}>
          {filtered.length === 0 && (
            <div style={{ padding: '40px 20px', textAlign: 'center', color: C.muted, fontSize: 13 }}>
              {search ? 'Nessun progetto trovato' : 'Nessun progetto — crea il primo'}
            </div>
          )}
          {filtered.map(p => (
            <ProgettoCard key={p.id}
              project={p}
              onSelect={id => setSelected(id === selected ? null : id)}
              onPalletChange={setPallet}
              onLanciaNC={lanciaInNC}
            />
          ))}
        </div>
      </div>

      {/* ── Dettaglio progetto (destra) ── */}
      <div style={{ flex: 1, background: 'var(--bg-card)', border: `1px solid ${C.border}`,
        borderRadius: 10, padding: 16, overflow: 'auto' }}>
        {selectedProject ? (
          <ProgettoDetail
            project={selectedProject}
            onUpdate={saveProject}
            onBack={() => setSelected(null)}
          />
        ) : (
          <div style={{ height: '100%', display: 'flex', flexDirection: 'column',
            alignItems: 'center', justifyContent: 'center', gap: 8, color: C.muted }}>
            <div style={{ fontSize: 32 }}>📋</div>
            <div style={{ fontSize: 14 }}>Seleziona un progetto per vedere i dettagli</div>
            <div style={{ fontSize: 12 }}>o crea un nuovo progetto con il pulsante +</div>
          </div>
        )}
      </div>

      {/* ── Dialog nuovo progetto ── */}
      {showNuovo && (
        <NuovoProgettoDialog
          templates={templates}
          onCrea={creaProgetto}
          onClose={() => setShowNuovo(false)}
        />
      )}
    </div>
  )
}
