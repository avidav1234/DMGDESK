/**
 * api/client.js — DMG Desk API client
 */

const BASE = import.meta.env.VITE_API_URL || '/api'

async function request(method, path, body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } }
  if (body && !(body instanceof FormData)) {
    opts.body = JSON.stringify(body)
  } else if (body instanceof FormData) {
    opts.body = body
    delete opts.headers['Content-Type']
  }
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

async function download(method, path, body = null) {
  const opts = { method, headers: { 'Content-Type': 'application/json' } }
  if (body) opts.body = JSON.stringify(body)
  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  const cd = res.headers.get('Content-Disposition') || ''
  const match = cd.match(/filename="?([^"]+)"?/)
  const filename = match ? match[1] : 'file.MPF'
  const blob = await res.blob()
  return { blob, filename }
}

export const api = {
  // ── Macchina ──────────────────────────────────────────
  getMacchina:          ()          => request('GET',    '/macchina/'),
  getPosizionelibera:   ()          => request('GET',    '/macchina/posizione-libera'),
  montaUtensile:        (body)      => request('POST',   '/macchina/monta', body),
  smontaUtensile:       (pos, note) => request('DELETE', `/macchina/${pos}?note=${encodeURIComponent(note || '')}`),

  // ── Scaffale ──────────────────────────────────────────
  getScaffale:          ()          => request('GET',    '/scaffale/'),
  spostaInMacchina:     (body)      => request('POST',   '/scaffale/sposta-in-macchina', body),
  rimuoviDaScaffale:    (alias)     => request('DELETE', `/scaffale/${encodeURIComponent(alias)}`),

  // ── Smontati ──────────────────────────────────────────
  getSmontati:          ()          => request('GET',    '/smontati/'),
  aggiungiSmontato:     (body)      => request('POST',   '/smontati/', body),
  modificaSmontato:     (id, body)  => request('PATCH',  `/smontati/${id}`, body),
  eliminaSmontato:      (id)        => request('DELETE', `/smontati/${id}`),
  montaSmontato:        (id, body)  => request('POST',   `/smontati/${id}/monta`, body),

  // ── Holder & Bussole ──────────────────────────────────
  getHolder:            ()          => request('GET',    '/holder-bussole/holder/'),
  aggiungiHolder:       (body)      => request('POST',   '/holder-bussole/holder/', body),
  modificaHolder:       (alias, b)  => request('PATCH',  `/holder-bussole/holder/${encodeURIComponent(alias)}`, b),
  eliminaHolder:        (alias)     => request('DELETE', `/holder-bussole/holder/${encodeURIComponent(alias)}`),
  getBussole:           ()          => request('GET',    '/holder-bussole/bussole/'),
  aggiungiBussola:      (body)      => request('POST',   '/holder-bussole/bussole/', body),
  eliminaBussola:       (codice)    => request('DELETE', `/holder-bussole/bussole/${encodeURIComponent(codice)}`),

  // ── Generatore ────────────────────────────────────────
  getTipologie:         ()          => request('GET',    '/generatore/tipologie'),
  getHolderTypes:       ()          => request('GET',    '/generatore/holders'),
  generaCodice:         (body)      => request('POST',   '/generatore/genera', body),

  // ── Analisi NC ────────────────────────────────────────
  analizzaNC:           (file)      => { const fd = new FormData(); fd.append('file', file); return request('POST', '/analisi-nc/analizza', fd) },
  infoAlias:            (alias)     => request('GET',    `/analisi-nc/info-alias?alias=${encodeURIComponent(alias)}`),
  aggiungiAScaffale:    (body)      => request('POST',   '/analisi-nc/aggiungi-a-scaffale', body),
  getCalibraMode:       ()          => request('GET',    '/analisi-nc/calibra-mode'),
  setCalibraMode:       (body)      => request('PUT',    '/analisi-nc/calibra-mode', body),
  anteprimaMain:        (body)      => request('POST',   '/analisi-nc/anteprima-main', body),
  generaMain:           (body)      => download('POST',  '/analisi-nc/genera-main', body),
  salvaMain:            (body)      => request('POST',   '/analisi-nc/salva-main', body),
  cartelleSfoglia:      ()          => request('GET',    '/analisi-nc/sfoglia-cartella'),
  cartelleRecenti:      ()          => request('GET',    '/analisi-nc/cartelle-recenti'),

  // ── Config ────────────────────────────────────────────
  getPercorsoNc:        ()          => request('GET',    '/config/percorso-nc'),
  setPercorsoNc:        (p)         => request('PUT',    '/config/percorso-nc', { percorso_nc_base: p }),

  // ── TOA Sync ──────────────────────────────────────────
  syncTools:            ()          => request('POST',   '/tools/sync'),
  getToolsSyncStatus:   ()          => request('GET',    '/tools/sync-status'),
  getTools:             (onlyOk)    => request('GET',    `/tools${onlyOk ? '?only_enabled=true' : ''}`),
  checkToolsMpf:        (file)      => { const fd = new FormData(); fd.append('file', file); return request('POST', '/tools/check', fd) },
  checkToolsText:       (mpf)       => request('POST',   '/tools/check-text', { mpf_content: mpf }),

  // ── Stato Macchina Live ────────────────────────────────
  getStatoMacchina:     ()          => request('GET',    '/macchina-live/stato'),
  getLogConfig:         ()          => request('GET',    '/macchina-live/config-log'),

  // ── Pallet ────────────────────────────────────────────
  getPallet:            ()          => request('GET',    '/pallet/'),
  setStatoPallet:       (n, body)   => request('PATCH',  `/pallet/${n}`, body),
  syncLavorazione:      (body)      => request('POST',   '/pallet/sync-lavorazione', body),
  inviaProgramma:       (n, body)   => request('POST',   `/pallet/invia-programma/${n}`, body),

  // ── Health ────────────────────────────────────────────
  health:               ()          => fetch('/health').then(r => r.json()),
}
