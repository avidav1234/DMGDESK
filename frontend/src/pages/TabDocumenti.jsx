// TabDocumenti.jsx — Tab allegati di progetto
import { useState, useEffect, useRef } from 'react'

const API = '/api/allegati'

const ICONE = {
  setup_cam: { label:'XL', bg:'#E6F1FB', color:'#0C447C' },
  immagine:  { label:'IMG', bg:'#EAF3DE', color:'#27500A' },
  documento: { label:'DOC', bg:'#FAEEDA', color:'#633806' },
  disegno:   { label:'DWG', bg:'#EEEDFE', color:'#3C3489' },
}

function BadgeTipo({ tipo }) {
  const ic = ICONE[tipo] || { label:'FILE', bg:'#f1f5f9', color:'#475569' }
  return (
    <div style={{ width:32, height:32, borderRadius:6, flexShrink:0,
      background:ic.bg, color:ic.color,
      display:'flex', alignItems:'center', justifyContent:'center',
      fontSize:9, fontWeight:800, letterSpacing:'0.04em' }}>
      {ic.label}
    </div>
  )
}

function BadgeFase({ fase, color }) {
  if (!fase) return null
  return (
    <span style={{ fontSize:10, fontWeight:700, padding:'2px 8px', borderRadius:4,
      background: color + '22', color, border:`1px solid ${color}44`,
      flexShrink:0 }}>{fase}</span>
  )
}

// ── Viewer Setup CAM ────────────────────────────────────────────────────────
function ViewerSetupCam({ projectId, allegato, onClose, projectColor }) {
  const [data, setData] = useState(null)
  const [loading, setLoading] = useState(true)
  const [tabV, setTabV] = useState('operazioni')

  useEffect(() => {
    fetch(`${API}/${projectId}/setup-cam/${allegato.id}`)
      .then(r => r.ok ? r.json() : null)
      .then(d => { setData(d); setLoading(false) })
      .catch(() => setLoading(false))
  }, [projectId, allegato.id])

  const col = projectColor || '#1D5FAD'

  return (
    <div style={{ position:'fixed', inset:0, zIndex:1000,
      display:'flex', alignItems:'center', justifyContent:'center',
      background:'rgba(0,0,0,0.45)' }}>
      <div style={{ background:'#fff', borderRadius:16, width:'min(900px, 95vw)',
        maxHeight:'90vh', display:'flex', flexDirection:'column',
        overflow:'hidden', boxShadow:'0 20px 60px rgba(0,0,0,0.2)' }}>

        {/* Header */}
        <div style={{ padding:'14px 20px', borderBottom:'1px solid #e2e8f0',
          display:'flex', alignItems:'center', gap:10, flexShrink:0 }}>
          <BadgeFase fase={allegato.fase} color={col}/>
          <div style={{ flex:1 }}>
            <div style={{ fontSize:14, fontWeight:700, color:'#0d2d5e' }}>
              {allegato.filename}
            </div>
            <div style={{ fontSize:11, color:'#64748b' }}>
              {allegato.data_upload} · {allegato.size_kb}KB
            </div>
          </div>
          <a href={`${API}/${projectId}/file/${allegato.id}`}
            download={allegato.filename}
            style={{ fontSize:11, padding:'5px 12px', borderRadius:7,
              background:'#f1f5f9', color:'#475569', textDecoration:'none',
              border:'1px solid #e2e8f0', fontWeight:600 }}>
            ⬇ Scarica
          </a>
          <button onClick={onClose} style={{ background:'none', border:'none',
            fontSize:18, cursor:'pointer', color:'#94a3b8', padding:'4px 8px' }}>×</button>
        </div>

        {/* Stats strip */}
        {data?.data?.statistiche && (
          <div style={{ display:'grid', gridTemplateColumns:'repeat(5,1fr)',
            borderBottom:'1px solid #e2e8f0', flexShrink:0 }}>
            {[
              ['Operazioni', data.data.statistiche.n_operazioni],
              ['Utensili', data.data.statistiche.n_utensili],
              ['Air time', data.data.statistiche.air_time],
              ['Feed time', data.data.statistiche.feed_time],
              ['Tempo totale', data.data.statistiche.total_time],
            ].map(([l,v],i) => (
              <div key={l} style={{ padding:'10px 14px',
                borderRight: i<4 ? '1px solid #e2e8f0' : 'none' }}>
                <div style={{ fontSize:9, color:'#94a3b8', textTransform:'uppercase',
                  letterSpacing:'0.06em', marginBottom:2 }}>{l}</div>
                <div style={{ fontSize:15, fontWeight:700,
                  fontFamily:'monospace', color:'#0d2d5e' }}>{v || '—'}</div>
              </div>
            ))}
          </div>
        )}

        {/* Sub-tab */}
        <div style={{ display:'flex', borderBottom:'1px solid #e2e8f0', flexShrink:0 }}>
          {[['operazioni','Operazioni'],['utensili','Elenco utensili'],
            ['meta','Intestazione']].map(([id,lbl]) => (
            <button key={id} onClick={() => setTabV(id)}
              style={{ background:'none', border:'none', padding:'10px 18px',
                fontSize:12, fontWeight:600, cursor:'pointer',
                color: tabV===id ? col : '#64748b',
                borderBottom: tabV===id ? `2px solid ${col}` : '2px solid transparent' }}>
              {lbl}
            </button>
          ))}
        </div>

        {/* Contenuto */}
        <div style={{ flex:1, overflow:'auto' }}>
          {loading && (
            <div style={{ padding:32, textAlign:'center', color:'#94a3b8' }}>
              Caricamento…
            </div>
          )}
          {!loading && tabV === 'operazioni' && data?.data?.operazioni && (
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11 }}>
              <thead>
                <tr style={{ background:'#f8fafc', position:'sticky', top:0 }}>
                  {['#','Alias','Utensile','Lung.','Offset','Z Step','Z min','Tempo','S','F','Axis'].map(h => (
                    <th key={h} style={{ padding:'7px 10px', textAlign:h==='#'?'center':'left',
                      color:'#64748b', fontWeight:700, fontSize:10,
                      borderBottom:'1px solid #e2e8f0', whiteSpace:'nowrap' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.data.operazioni.map((op, i) => (
                  <tr key={op.proc} style={{ borderBottom:'1px solid #f1f5f9',
                    background: i%2===0 ? '#fff' : '#fafafa' }}>
                    <td style={{ padding:'6px 10px', textAlign:'center',
                      color:'#94a3b8', fontWeight:700 }}>{op.proc}</td>
                    <td style={{ padding:'6px 10px', fontFamily:'monospace',
                      color: col, fontWeight:700, fontSize:10 }}>
                      {op.alias.replace(/^\s+/,'')}
                    </td>
                    <td style={{ padding:'6px 10px', color:'#334155', maxWidth:200,
                      overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}
                      title={op.utensile}>{op.utensile}</td>
                    <td style={{ padding:'6px 10px', textAlign:'right',
                      color:'#64748b', fontFamily:'monospace' }}>{op.lung_ut}</td>
                    <td style={{ padding:'6px 10px', textAlign:'right',
                      color:'#64748b', fontFamily:'monospace' }}>{op.offset}</td>
                    <td style={{ padding:'6px 10px', textAlign:'right',
                      color:'#64748b', fontFamily:'monospace' }}>{op.z_step}</td>
                    <td style={{ padding:'6px 10px', textAlign:'right',
                      color:'#334155', fontFamily:'monospace', fontWeight:600 }}>{op.z_min}</td>
                    <td style={{ padding:'6px 10px', fontFamily:'monospace',
                      color:'#15803d', fontWeight:700 }}>{op.tempo}</td>
                    <td style={{ padding:'6px 10px', textAlign:'right',
                      color:'#64748b', fontFamily:'monospace' }}>{op.s}</td>
                    <td style={{ padding:'6px 10px', textAlign:'right',
                      color:'#64748b', fontFamily:'monospace' }}>{op.f}</td>
                    <td style={{ padding:'6px 10px', color:'#475569' }}>{op.axis}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!loading && tabV === 'utensili' && data?.data?.utensili && (
            <table style={{ width:'100%', borderCollapse:'collapse', fontSize:11 }}>
              <thead>
                <tr style={{ background:'#f8fafc', position:'sticky', top:0 }}>
                  {['T#','Nome','Alias','Ø','R','Fuori pinza','Porta utensile'].map(h => (
                    <th key={h} style={{ padding:'7px 10px', textAlign:'left',
                      color:'#64748b', fontWeight:700, fontSize:10,
                      borderBottom:'1px solid #e2e8f0' }}>{h}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {data.data.utensili.map((u, i) => (
                  <tr key={i} style={{ borderBottom:'1px solid #f1f5f9',
                    background: i%2===0 ? '#fff' : '#fafafa' }}>
                    <td style={{ padding:'6px 10px', fontFamily:'monospace',
                      color: col, fontWeight:700 }}>{u.t_number}</td>
                    <td style={{ padding:'6px 10px', color:'#334155',
                      maxWidth:180, overflow:'hidden', textOverflow:'ellipsis',
                      whiteSpace:'nowrap' }} title={u.nome}>{u.nome}</td>
                    <td style={{ padding:'6px 10px', fontFamily:'monospace',
                      color:'#0d2d5e', fontWeight:600 }}>{u.alias.replace(/^\s+/,'')}</td>
                    <td style={{ padding:'6px 10px', textAlign:'right',
                      color:'#64748b', fontFamily:'monospace' }}>{u.diametro}</td>
                    <td style={{ padding:'6px 10px', textAlign:'right',
                      color:'#64748b', fontFamily:'monospace' }}>{u.raggio}</td>
                    <td style={{ padding:'6px 10px', textAlign:'right',
                      color:'#64748b', fontFamily:'monospace' }}>{u.fuori_pinza}</td>
                    <td style={{ padding:'6px 10px', color:'#475569',
                      fontSize:10 }}>{u.porta_utensile}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
          {!loading && tabV === 'meta' && data?.data?.meta && (
            <div style={{ padding:20 }}>
              {Object.entries(data.data.meta).map(([k,v]) => (
                <div key={k} style={{ display:'flex', padding:'8px 0',
                  borderBottom:'1px solid #f1f5f9', gap:16 }}>
                  <span style={{ fontSize:11, color:'#94a3b8', minWidth:140,
                    textTransform:'capitalize' }}>{k.replace(/_/g,' ')}</span>
                  <span style={{ fontSize:12, fontWeight:600, color:'#0d2d5e' }}>{v}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>
    </div>
  )
}

// ── Viewer immagine ──────────────────────────────────────────────────────────
function ViewerImmagine({ projectId, allegato, onClose }) {
  return (
    <div style={{ position:'fixed', inset:0, zIndex:1000,
      display:'flex', alignItems:'center', justifyContent:'center',
      background:'rgba(0,0,0,0.8)' }}
      onClick={onClose}>
      <div style={{ maxWidth:'90vw', maxHeight:'90vh', position:'relative' }}
        onClick={e => e.stopPropagation()}>
        <button onClick={onClose} style={{ position:'absolute', top:-16, right:-16,
          width:32, height:32, borderRadius:'50%', background:'#fff',
          border:'none', fontSize:16, cursor:'pointer', color:'#0d2d5e',
          display:'flex', alignItems:'center', justifyContent:'center',
          zIndex:1, lineHeight:1 }}>×</button>
        <img
          src={`${API}/${projectId}/preview/${allegato.id}`}
          alt={allegato.filename}
          style={{ maxWidth:'100%', maxHeight:'85vh', borderRadius:8,
            display:'block', objectFit:'contain' }}
        />
        <div style={{ background:'rgba(0,0,0,0.6)', color:'#fff', fontSize:11,
          padding:'6px 12px', borderRadius:'0 0 8px 8px', textAlign:'center' }}>
          {allegato.filename}
          {allegato.fase && <span style={{ marginLeft:8, opacity:0.7 }}>· {allegato.fase}</span>}
          <a href={`${API}/${projectId}/file/${allegato.id}`} download={allegato.filename}
            style={{ marginLeft:12, color:'#93c5fd', textDecoration:'none' }}>⬇ scarica</a>
        </div>
      </div>
    </div>
  )
}

// ── Componente principale ────────────────────────────────────────────────────
export default function TabDocumenti({ project }) {
  const [allegati, setAllegati]   = useState([])
  const [loading, setLoading]     = useState(true)
  const [uploading, setUploading] = useState(false)
  const [viewer, setViewer]       = useState(null)  // { allegato }
  const [errore, setErrore]       = useState(null)
  const [faseFilter, setFaseFilter] = useState('tutti')
  const fileRef = useRef()
  const col = project?.color || '#1D5FAD'

  const carica = () => {
    setLoading(true)
    fetch(`${API}/${project.id}`)
      .then(r => r.ok ? r.json() : { allegati:[] })
      .then(d => { setAllegati(d.allegati || []); setLoading(false) })
      .catch(() => setLoading(false))
  }

  useEffect(() => { if (project?.id) carica() }, [project?.id])

  const handleUpload = async (e) => {
    const files = Array.from(e.target.files || [])
    if (!files.length) return
    setUploading(true)
    setErrore(null)
    for (const file of files) {
      const fd = new FormData()
      fd.append('file', file)
      // Cerca di indovinare la fase dal nome file
      const faseMatch = file.name.match(/[_-](F\d+)[_-]/i)
      fd.append('fase', faseMatch ? faseMatch[1].toUpperCase() : '')
      try {
        const r = await fetch(`${API}/${project.id}/upload`, { method:'POST', body:fd })
        if (!r.ok) {
          const err = await r.json().catch(() => ({}))
          setErrore(err.detail || `Errore upload: ${file.name}`)
        }
      } catch (e) {
        setErrore(`Errore rete: ${e.message}`)
      }
    }
    setUploading(false)
    e.target.value = ''
    carica()
  }

  const elimina = async (id) => {
    if (!window.confirm('Eliminare questo allegato?')) return
    await fetch(`${API}/${project.id}/file/${id}`, { method:'DELETE' })
    carica()
  }

  const openViewer = (allegato) => setViewer(allegato)

  // Fasi disponibili
  const fasi = ['tutti', ...new Set(allegati.map(a => a.fase).filter(Boolean))]
  const filtered = faseFilter === 'tutti'
    ? allegati
    : allegati.filter(a => a.fase === faseFilter)

  // Separa per tipo
  const setupCam = filtered.filter(a => a.tipo === 'setup_cam')
  const immagini = filtered.filter(a => a.tipo === 'immagine')
  const altri    = filtered.filter(a => !['setup_cam','immagine'].includes(a.tipo))

  return (
    <div style={{ display:'flex', flexDirection:'column', gap:16 }}>

      {/* Toolbar */}
      <div style={{ display:'flex', alignItems:'center', gap:10, flexWrap:'wrap' }}>
        {/* Filtro fase */}
        {fasi.length > 1 && (
          <div style={{ display:'flex', gap:4 }}>
            {fasi.map(f => (
              <button key={f} onClick={() => setFaseFilter(f)}
                style={{ background: faseFilter===f ? col : 'none',
                  color: faseFilter===f ? '#fff' : '#64748b',
                  border: `1px solid ${faseFilter===f ? col : '#e2e8f0'}`,
                  borderRadius:6, padding:'4px 12px', fontSize:11,
                  fontWeight:600, cursor:'pointer' }}>
                {f === 'tutti' ? `Tutti (${allegati.length})` : f}
              </button>
            ))}
          </div>
        )}
        <div style={{ marginLeft:'auto', display:'flex', gap:8, alignItems:'center' }}>
          {errore && (
            <span style={{ fontSize:11, color:'#dc2626', background:'#fef2f2',
              padding:'4px 10px', borderRadius:6 }}>{errore}</span>
          )}
          <input ref={fileRef} type="file" multiple accept=".xlsx,.xls,.pdf,.jpg,.jpeg,.png,.bmp,.dwg,.dxf,.txt"
            style={{ display:'none' }} onChange={handleUpload}/>
          <button onClick={() => fileRef.current?.click()}
            disabled={uploading}
            style={{ background: col, color:'#fff', border:'none',
              borderRadius:8, padding:'7px 16px', fontSize:12,
              fontWeight:700, cursor:'pointer', opacity: uploading ? 0.6 : 1 }}>
            {uploading ? 'Caricamento…' : '+ Allega file'}
          </button>
        </div>
      </div>

      {loading && (
        <div style={{ textAlign:'center', color:'#94a3b8', padding:32 }}>
          Caricamento allegati…
        </div>
      )}

      {!loading && allegati.length === 0 && (
        <div style={{ textAlign:'center', padding:'40px 20px',
          border:'2px dashed #e2e8f0', borderRadius:12, color:'#94a3b8' }}>
          <div style={{ fontSize:32, marginBottom:8 }}>📎</div>
          <div style={{ fontSize:14, fontWeight:600, marginBottom:4 }}>Nessun allegato</div>
          <div style={{ fontSize:12 }}>
            Carica report Setup CAM (.xlsx), foto, disegni o documenti
          </div>
        </div>
      )}

      {/* Setup CAM */}
      {setupCam.length > 0 && (
        <div>
          <div style={{ fontSize:10, fontWeight:800, color:'#94a3b8',
            letterSpacing:'0.08em', textTransform:'uppercase', marginBottom:8 }}>
            Report Setup CAM
          </div>
          <div style={{ display:'flex', flexDirection:'column', gap:4 }}>
            {setupCam.map(a => (
              <div key={a.id} style={{ display:'flex', alignItems:'center', gap:10,
                padding:'10px 14px', background:'#fff',
                border:'1px solid #e2e8f0', borderRadius:10,
                cursor:'pointer', transition:'border-color 0.1s' }}
                onMouseEnter={e => e.currentTarget.style.borderColor=col}
                onMouseLeave={e => e.currentTarget.style.borderColor='#e2e8f0'}
                onClick={() => openViewer(a)}>
                <BadgeTipo tipo={a.tipo}/>
                <div style={{ flex:1, minWidth:0 }}>
                  <div style={{ fontSize:12, fontWeight:700, color:'#0d2d5e',
                    overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                    {a.filename}
                  </div>
                  <div style={{ fontSize:10, color:'#94a3b8', marginTop:1 }}>
                    {a.data_upload} · {a.size_kb}KB
                    {a.meta?.statistiche?.total_time && (
                      <span style={{ marginLeft:8, color:'#15803d', fontWeight:600 }}>
                        ⏱ {a.meta.statistiche.total_time}
                      </span>
                    )}
                    {a.meta?.statistiche?.n_operazioni && (
                      <span style={{ marginLeft:8 }}>
                        {a.meta.statistiche.n_operazioni} op.
                      </span>
                    )}
                  </div>
                </div>
                <BadgeFase fase={a.fase} color={col}/>
                <span style={{ fontSize:10, color:'#1D5FAD',
                  fontWeight:600, flexShrink:0 }}>Apri →</span>
                <button onClick={e => { e.stopPropagation(); elimina(a.id) }}
                  style={{ background:'none', border:'none', cursor:'pointer',
                    color:'#cbd5e1', fontSize:16, padding:'2px 6px',
                    borderRadius:4, flexShrink:0 }}
                  onMouseEnter={e => e.currentTarget.style.color='#ef4444'}
                  onMouseLeave={e => e.currentTarget.style.color='#cbd5e1'}>
                  ×
                </button>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Immagini */}
      {immagini.length > 0 && (
        <div>
          <div style={{ fontSize:10, fontWeight:800, color:'#94a3b8',
            letterSpacing:'0.08em', textTransform:'uppercase', marginBottom:8 }}>
            Immagini e disegni
          </div>
          <div style={{ display:'grid', gridTemplateColumns:'repeat(auto-fill, minmax(140px,1fr))',
            gap:8 }}>
            {immagini.map(a => (
              <div key={a.id} style={{ border:'1px solid #e2e8f0', borderRadius:8,
                overflow:'hidden', cursor:'pointer', position:'relative',
                transition:'border-color 0.1s', background:'#f8fafc' }}
                onMouseEnter={e => e.currentTarget.style.borderColor=col}
                onMouseLeave={e => e.currentTarget.style.borderColor='#e2e8f0'}
                onClick={() => openViewer(a)}>
                <img src={`${API}/${project.id}/preview/${a.id}`}
                  alt={a.filename}
                  style={{ width:'100%', aspectRatio:'4/3',
                    objectFit:'cover', display:'block' }}
                  onError={e => { e.target.style.display='none' }}
                />
                <div style={{ padding:'5px 8px' }}>
                  <div style={{ fontSize:10, fontWeight:600, color:'#334155',
                    overflow:'hidden', textOverflow:'ellipsis', whiteSpace:'nowrap' }}>
                    {a.filename.replace(/\.[^.]+$/, '')}
                  </div>
                  <div style={{ display:'flex', justifyContent:'space-between',
                    alignItems:'center' }}>
                    <BadgeFase fase={a.fase} color={col}/>
                    <button onClick={e => { e.stopPropagation(); elimina(a.id) }}
                      style={{ background:'none', border:'none', cursor:'pointer',
                        color:'#cbd5e1', fontSize:14, padding:'0 2px' }}
                      onMouseEnter={e => e.currentTarget.style.color='#ef4444'}
                      onMouseLeave={e => e.currentTarget.style.color='#cbd5e1'}>
                      ×
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      {/* Altri documenti */}
      {altri.length > 0 && (
        <div>
          <div style={{ fontSize:10, fontWeight:800, color:'#94a3b8',
            letterSpacing:'0.08em', textTransform:'uppercase', marginBottom:8 }}>
            Altri documenti
          </div>
          {altri.map(a => (
            <div key={a.id} style={{ display:'flex', alignItems:'center', gap:10,
              padding:'8px 12px', border:'1px solid #e2e8f0', borderRadius:8,
              marginBottom:4 }}>
              <BadgeTipo tipo={a.tipo}/>
              <div style={{ flex:1 }}>
                <div style={{ fontSize:12, fontWeight:600, color:'#0d2d5e' }}>
                  {a.filename}
                </div>
                <div style={{ fontSize:10, color:'#94a3b8' }}>
                  {a.data_upload} · {a.size_kb}KB
                </div>
              </div>
              <BadgeFase fase={a.fase} color={col}/>
              <a href={`${API}/${project.id}/file/${a.id}`} download={a.filename}
                style={{ fontSize:11, color:'#1D5FAD', textDecoration:'none',
                  padding:'3px 10px', border:'1px solid #bfdbfe', borderRadius:6 }}>
                ⬇
              </a>
              <button onClick={() => elimina(a.id)}
                style={{ background:'none', border:'none', cursor:'pointer',
                  color:'#cbd5e1', fontSize:16 }}
                onMouseEnter={e => e.currentTarget.style.color='#ef4444'}
                onMouseLeave={e => e.currentTarget.style.color='#cbd5e1'}>×</button>
            </div>
          ))}
        </div>
      )}

      {/* Viewer */}
      {viewer && viewer.tipo === 'setup_cam' && (
        <ViewerSetupCam
          projectId={project.id}
          allegato={viewer}
          onClose={() => setViewer(null)}
          projectColor={col}
        />
      )}
      {viewer && viewer.tipo === 'immagine' && (
        <ViewerImmagine
          projectId={project.id}
          allegato={viewer}
          onClose={() => setViewer(null)}
        />
      )}
    </div>
  )
}
