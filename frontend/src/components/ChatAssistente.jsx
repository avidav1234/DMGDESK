/**
 * ChatAssistente.jsx
 * Pannello chat AI laterale — si apre come drawer destro
 * disponibile in tutte le pagine di DMGDesk.
 */

import { useState, useEffect, useRef, useCallback } from 'react'
import { useLocation } from 'react-router-dom'

const API = (path) => path

// ── Icone SVG inline ───────────────────────────────────────────────────────

const IcoChat = () => (
  <svg width="20" height="20" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
    <path d="M21 15a2 2 0 01-2 2H7l-4 4V5a2 2 0 012-2h14a2 2 0 012 2z"/>
  </svg>
)

const IcoClose = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/>
  </svg>
)

const IcoSend = () => (
  <svg width="16" height="16" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <line x1="22" y1="2" x2="11" y2="13"/>
    <polygon points="22 2 15 22 11 13 2 9 22 2"/>
  </svg>
)

const IcoTrash = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <polyline points="3 6 5 6 21 6"/>
    <path d="M19 6l-1 14a2 2 0 01-2 2H8a2 2 0 01-2-2L5 6"/>
    <path d="M10 11v6M14 11v6"/>
  </svg>
)

const IcoBot = () => (
  <svg width="14" height="14" viewBox="0 0 24 24" fill="none"
    stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
    <rect x="3" y="11" width="18" height="10" rx="2"/>
    <circle cx="12" cy="5" r="2"/>
    <path d="M12 7v4"/>
    <line x1="8" y1="16" x2="8" y2="16"/>
    <line x1="16" y1="16" x2="16" y2="16"/>
  </svg>
)

// ── Suggerimenti rapidi per pagina ─────────────────────────────────────────

const SUGGERIMENTI = {
  home:          ["Stato macchina adesso", "OEE di oggi", "Utensili critici"],
  macchina:      ["Quale utensile ha vita più bassa?", "Serve sostituire qualcosa?", "Ore utensile attivo"],
  report:        ["Perché l'OEE è calato?", "Fermi anomali questa settimana", "Confronto ieri vs oggi"],
  progetti:      ["Commesse in ritardo?", "Prossime scadenze", "Commessa con più ore"],
  coda:          ["Stato pallet attuale", "Programma in esecuzione", "Quanto manca al prossimo cambio"],
  "step-analyzer": ["Commesse simili a questa", "Media ore commesse simili", "Stima tempo lavorazione"],
  "alert-utensili": ["Utensili da sostituire oggi", "Priorità ispezioni", "Utensile più a rischio"],
  turno:         ["Riepilogo turno corrente", "Ore produttive oggi", "Problemi aperti"],
  default:       ["Stato macchina", "OEE oggi", "Alert utensili", "Commesse attive"],
}

// ── Componente messaggio ───────────────────────────────────────────────────

function Messaggio({ msg }) {
  const isUser = msg.role === 'user'
  const isSystem = msg.role === 'system'

  if (isSystem) {
    return (
      <div style={{
        textAlign: 'center', padding: '4px 12px',
        fontSize: 11, color: 'var(--text-dim)',
        borderTop: '1px solid var(--border)', margin: '8px 0',
      }}>
        {msg.content}
      </div>
    )
  }

  return (
    <div style={{
      display: 'flex',
      flexDirection: isUser ? 'row-reverse' : 'row',
      gap: 8, marginBottom: 12, alignItems: 'flex-start',
    }}>
      {/* Avatar */}
      {!isUser && (
        <div style={{
          width: 26, height: 26, borderRadius: '50%', flexShrink: 0,
          background: 'var(--navy-700)', color: '#fff',
          display: 'flex', alignItems: 'center', justifyContent: 'center',
          marginTop: 2,
        }}>
          <IcoBot />
        </div>
      )}

      {/* Bubble */}
      <div style={{
        maxWidth: '82%',
        background: isUser ? 'var(--navy-700)' : 'var(--bg-panel)',
        color: isUser ? '#fff' : 'var(--text-primary)',
        border: isUser ? 'none' : '1px solid var(--border)',
        borderRadius: isUser ? '12px 12px 2px 12px' : '12px 12px 12px 2px',
        padding: '9px 13px',
        fontSize: 13,
        lineHeight: 1.55,
        whiteSpace: 'pre-wrap',
        wordBreak: 'break-word',
      }}>
        {msg.content}
        <div style={{
          fontSize: 10, color: isUser ? 'rgba(255,255,255,0.5)' : 'var(--text-dim)',
          marginTop: 4, textAlign: 'right',
        }}>
          {msg.ts}
        </div>
      </div>
    </div>
  )
}

// ── Indicatore typing ──────────────────────────────────────────────────────

function Typing() {
  return (
    <div style={{ display: 'flex', gap: 8, marginBottom: 12, alignItems: 'flex-start' }}>
      <div style={{
        width: 26, height: 26, borderRadius: '50%',
        background: 'var(--navy-700)', color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
      }}>
        <IcoBot />
      </div>
      <div style={{
        background: 'var(--bg-panel)', border: '1px solid var(--border)',
        borderRadius: '12px 12px 12px 2px', padding: '12px 16px',
        display: 'flex', gap: 5, alignItems: 'center',
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: 6, height: 6, borderRadius: '50%',
            background: 'var(--navy-accent)',
            animation: `typingDot 1.2s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
      </div>
    </div>
  )
}

// ── Pannello principale ────────────────────────────────────────────────────

export default function ChatAssistente() {
  const [aperto, setAperto] = useState(false)
  const [messaggi, setMessaggi] = useState([])
  const [input, setInput] = useState('')
  const [loading, setLoading] = useState(false)
  const [configurato, setConfigurato] = useState(null)
  const [badgeAlert, setBadgeAlert] = useState(false)
  const messagesEndRef = useRef(null)
  const inputRef = useRef(null)
  const location = useLocation()

  // Pagina corrente dal path
  const paginaCorrente = location.pathname.replace('/', '').split('/')[0] || 'home'
  const suggerimenti = SUGGERIMENTI[paginaCorrente] || SUGGERIMENTI.default

  // ── Scroll automatico ────────────────────────────────────────────────────
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messaggi, loading])

  // ── Focus input quando aperto ────────────────────────────────────────────
  useEffect(() => {
    if (aperto) {
      setTimeout(() => inputRef.current?.focus(), 150)
    }
  }, [aperto])

  // ── Verifica configurazione API ──────────────────────────────────────────
  useEffect(() => {
    fetch(API('/api/assistente/stato'))
      .then(r => r.json())
      .then(d => setConfigurato(d.configurato))
      .catch(() => setConfigurato(false))
  }, [])

  // ── Messaggio di benvenuto ───────────────────────────────────────────────
  useEffect(() => {
    if (aperto && messaggi.length === 0) {
      const ora = new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
      setMessaggi([{
        role: 'assistant',
        content: 'Ciao! Sono l\'assistente DMGDesk. Posso aiutarti con informazioni sulla macchina, utensili, commesse e report. Cosa ti serve?',
        ts: ora,
      }])
    }
  }, [aperto])

  // ── Invio messaggio ──────────────────────────────────────────────────────
  const invia = useCallback(async (testo) => {
    const msg = (testo || input).trim()
    if (!msg || loading) return

    setInput('')
    const ora = new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })

    // Aggiungi messaggio utente
    const nuoviMessaggi = [...messaggi, { role: 'user', content: msg, ts: ora }]
    setMessaggi(nuoviMessaggi)
    setLoading(true)

    try {
      // Prepara history (escludi messaggi system)
      const history = nuoviMessaggi
        .filter(m => m.role !== 'system')
        .slice(-10)
        .map(m => ({ role: m.role, content: m.content }))

      const res = await fetch(API('/api/assistente/chat'), {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          messaggio: msg,
          history: history.slice(0, -1), // history senza l'ultimo (quello che stiamo mandando)
          pagina_corrente: paginaCorrente,
        }),
      })

      const data = await res.json()
      const oraResp = new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })

      if (data.ok) {
        setMessaggi(prev => [...prev, {
          role: 'assistant',
          content: data.risposta,
          ts: oraResp,
        }])
      } else {
        throw new Error(data.detail || 'Errore risposta')
      }
    } catch (e) {
      const oraErr = new Date().toLocaleTimeString('it-IT', { hour: '2-digit', minute: '2-digit' })
      setMessaggi(prev => [...prev, {
        role: 'assistant',
        content: `⚠️ Errore: ${e.message}`,
        ts: oraErr,
      }])
    } finally {
      setLoading(false)
    }
  }, [input, loading, messaggi, paginaCorrente])

  // ── Tasto Enter ──────────────────────────────────────────────────────────
  const onKeyDown = (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      invia()
    }
  }

  // ── Pulisci chat ─────────────────────────────────────────────────────────
  const pulisci = () => {
    setMessaggi([])
    setBadgeAlert(false)
  }

  // ── Render ───────────────────────────────────────────────────────────────
  return (
    <>
      {/* CSS animazione typing dots */}
      <style>{`
        @keyframes typingDot {
          0%, 60%, 100% { transform: translateY(0); opacity: 0.4; }
          30% { transform: translateY(-4px); opacity: 1; }
        }
        .chat-btn-fab:hover { transform: scale(1.05); }
        .chat-btn-fab:active { transform: scale(0.97); }
        .chat-suggerimento:hover {
          background: var(--navy-700) !important;
          color: #fff !important;
          border-color: var(--navy-700) !important;
        }
      `}</style>

      {/* ── FAB pulsante apri ─────────────────────────────────────────── */}
      {!aperto && (
        <button
          className="chat-btn-fab"
          onClick={() => setAperto(true)}
          title="Assistente AI"
          style={{
            position: 'fixed', bottom: 24, right: 24, zIndex: 1000,
            width: 52, height: 52, borderRadius: '50%',
            background: 'var(--navy-700)', color: '#fff',
            border: 'none', cursor: 'pointer',
            display: 'flex', alignItems: 'center', justifyContent: 'center',
            boxShadow: '0 4px 16px rgba(13,45,94,0.35)',
            transition: 'transform 150ms ease',
          }}
        >
          <IcoChat />
          {badgeAlert && (
            <div style={{
              position: 'absolute', top: 4, right: 4,
              width: 10, height: 10, borderRadius: '50%',
              background: '#ef4444', border: '2px solid white',
            }} />
          )}
        </button>
      )}

      {/* ── Drawer laterale ───────────────────────────────────────────── */}
      {aperto && (
        <div style={{
          position: 'fixed', top: 0, right: 0, bottom: 0,
          width: 360, zIndex: 1000,
          display: 'flex', flexDirection: 'column',
          background: 'var(--bg-surface)',
          borderLeft: '1px solid var(--border)',
          boxShadow: '-4px 0 20px rgba(0,0,0,0.10)',
          animation: 'slideIn 200ms ease',
        }}>

          {/* Header */}
          <div style={{
            padding: '14px 16px',
            background: 'var(--navy-700)',
            display: 'flex', alignItems: 'center', gap: 10,
            flexShrink: 0,
          }}>
            <div style={{
              width: 32, height: 32, borderRadius: '50%',
              background: 'rgba(255,255,255,0.15)',
              display: 'flex', alignItems: 'center', justifyContent: 'center',
            }}>
              <IcoBot />
            </div>
            <div style={{ flex: 1 }}>
              <div style={{ color: '#fff', fontWeight: 600, fontSize: 14 }}>
                Assistente DMGDesk
              </div>
              <div style={{ color: 'var(--navy-accent)', fontSize: 11 }}>
                {configurato === false
                  ? '⚠️ API key mancante'
                  : configurato === true
                    ? '● Online'
                    : '○ Connessione...'}
              </div>
            </div>
            <button onClick={pulisci} title="Pulisci chat" style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'rgba(255,255,255,0.6)', padding: 6, borderRadius: 4,
              display: 'flex',
            }}>
              <IcoTrash />
            </button>
            <button onClick={() => setAperto(false)} title="Chiudi" style={{
              background: 'none', border: 'none', cursor: 'pointer',
              color: 'rgba(255,255,255,0.8)', padding: 6, borderRadius: 4,
              display: 'flex',
            }}>
              <IcoClose />
            </button>
          </div>

          {/* Avviso API non configurata */}
          {configurato === false && (
            <div style={{
              padding: '10px 16px', background: '#fef2f2',
              borderBottom: '1px solid #fca5a5',
              fontSize: 12, color: '#991b1b',
            }}>
              ⚠️ Aggiungi <code>ANTHROPIC_API_KEY=sk-...</code> al file <code>.env</code> e riavvia il backend.
            </div>
          )}

          {/* Lista messaggi */}
          <div style={{
            flex: 1, overflowY: 'auto', padding: '16px 14px',
            display: 'flex', flexDirection: 'column',
          }}>
            {messaggi.map((m, i) => <Messaggio key={i} msg={m} />)}
            {loading && <Typing />}
            <div ref={messagesEndRef} />
          </div>

          {/* Suggerimenti rapidi */}
          {messaggi.length <= 1 && !loading && (
            <div style={{
              padding: '8px 14px 0',
              display: 'flex', flexWrap: 'wrap', gap: 6,
              flexShrink: 0,
            }}>
              {suggerimenti.map((s, i) => (
                <button
                  key={i}
                  className="chat-suggerimento"
                  onClick={() => invia(s)}
                  style={{
                    background: 'var(--bg-panel)',
                    border: '1px solid var(--border)',
                    borderRadius: 20, padding: '5px 12px',
                    fontSize: 12, color: 'var(--text-secondary)',
                    cursor: 'pointer', transition: 'all 120ms ease',
                  }}
                >
                  {s}
                </button>
              ))}
            </div>
          )}

          {/* Input */}
          <div style={{
            padding: '12px 14px',
            borderTop: '1px solid var(--border)',
            background: 'var(--bg-panel)',
            flexShrink: 0,
          }}>
            <div style={{ display: 'flex', gap: 8, alignItems: 'flex-end' }}>
              <textarea
                ref={inputRef}
                value={input}
                onChange={e => setInput(e.target.value)}
                onKeyDown={onKeyDown}
                placeholder="Scrivi un messaggio..."
                disabled={loading || configurato === false}
                rows={1}
                style={{
                  flex: 1, resize: 'none', border: '1px solid var(--border)',
                  borderRadius: 8, padding: '9px 12px',
                  fontSize: 13, fontFamily: 'var(--font-display)',
                  background: 'var(--bg-surface)', color: 'var(--text-primary)',
                  outline: 'none', lineHeight: 1.5,
                  minHeight: 38, maxHeight: 100, overflowY: 'auto',
                }}
                onInput={e => {
                  e.target.style.height = 'auto'
                  e.target.style.height = Math.min(e.target.scrollHeight, 100) + 'px'
                }}
              />
              <button
                onClick={() => invia()}
                disabled={!input.trim() || loading || configurato === false}
                style={{
                  background: 'var(--navy-700)', color: '#fff',
                  border: 'none', borderRadius: 8,
                  width: 38, height: 38, cursor: 'pointer',
                  display: 'flex', alignItems: 'center', justifyContent: 'center',
                  flexShrink: 0, opacity: (!input.trim() || loading) ? 0.4 : 1,
                  transition: 'opacity 120ms',
                }}
              >
                <IcoSend />
              </button>
            </div>
            <div style={{ fontSize: 10, color: 'var(--text-dim)', marginTop: 6, textAlign: 'center' }}>
              Enter per inviare · Shift+Enter per nuova riga
            </div>
          </div>
        </div>
      )}

      {/* Animazione slide-in */}
      <style>{`
        @keyframes slideIn {
          from { transform: translateX(100%); opacity: 0; }
          to   { transform: translateX(0);   opacity: 1; }
        }
      `}</style>
    </>
  )
}
