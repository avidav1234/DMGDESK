/**
 * api/client.js — Client HTTP centralizzato
 * Tutti i componenti importano da qui — mai fetch() diretti.
 */

const BASE = import.meta.env.VITE_API_URL || '/api'

async function request(method, path, body = null) {
  const opts = {
    method,
    headers: { 'Content-Type': 'application/json' },
  }
  if (body && !(body instanceof FormData)) {
    opts.body = JSON.stringify(body)
    opts.headers['Content-Type'] = 'application/json'
  } else if (body instanceof FormData) {
    opts.body = body
    delete opts.headers['Content-Type']  // browser setta multipart automaticamente
  }

  const res = await fetch(`${BASE}${path}`, opts)
  if (!res.ok) {
    const err = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(err.detail || `HTTP ${res.status}`)
  }
  return res.json()
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

  // ── Smontati ──────────────────────────────────────────
  getSmontati:          ()          => request('GET',    '/smontati/'),
  aggiungiSmontato:     (body)      => request('POST',   '/smontati/', body),
  modificaSmontato:     (id, body)  => request('PATCH',  `/smontati/${id}`, body),
  eliminaSmontato:      (id)        => request('DELETE', `/smontati/${id}`),

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
  getCalibraMode:       ()          => request('GET',    '/analisi-nc/calibra-mode'),
  setCalibraMode:       (body)      => request('PUT',    '/analisi-nc/calibra-mode', body),

  // ── Health ────────────────────────────────────────────
  health:               ()          => fetch('/health').then(r => r.json()),
}
