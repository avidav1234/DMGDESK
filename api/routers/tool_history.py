"""
api/routers/tool_history.py
============================
Storico sostituzioni utensile + alert vita bassa durante lavorazione.

STORICO SOSTITUZIONI:
  Ad ogni sync TOA (cambio mtime di tools_machine.json), confronta
  i dati vecchi con i nuovi. Se un duplo ha:
    - life_percent salito significativamente (>30%) → sostituzione
    - is_worn passato da True a False → sostituzione
    - is_enabled passato da False a True → riabilitazione
  Registra in tool_replacements.json:
    { "sostituzioni": [ {ts, alias, posizione, magazine, vita_prima, vita_dopo, tipo} ] }

ALERT VITA BASSA:
  Il tick di macchina_live chiama check_low_life_alert() ogni ciclo.
  Se un utensile attivo (rilevato dal programma corrente) scende sotto
  la soglia configurata (default 20%), manda una notifica Telegram
  con throttle 30 minuti per alias.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Body
from typing import Optional
from database.db_handler import carica_configurazione

log = logging.getLogger("tool_history")
router = APIRouter(prefix="/api/tool-history", tags=["Tool History"])

# ── Costanti ──────────────────────────────────────────────────────────────────
SOGLIA_VITA_BASSA         = 20    # % sotto cui scatta l'alert
SOGLIA_SOSTITUZIONE_PCT   = 80    # life_percent nuovo > questa soglia → sostituzione completa
DELTA_MIN_AUMENTO         = 1.0   # delta minimo per considerare vita "aumentata" (no noise floating)
THROTTLE_MINUTES          = 30    # minuti tra due alert sullo stesso alias
MAX_RECORD                = 500   # massimo record nello storico

# ── Stato in memoria ─────────────────────────────────────────────────────────
# snapshot: { tool_id (int) → {alias, life_percent, life_remaining, life_total,
#                              is_worn, is_enabled, position, magazine, duplo} }
_snapshot_precedente: dict = {}
_alert_inviati: dict = {}         # alias → datetime ultimo alert


# ── Path file storico ─────────────────────────────────────────────────────────

def _history_path(config: dict) -> Path | None:
    folder = (config.get("tools_toa_folder") or "").strip()
    if not folder:
        return None
    return Path(folder) / "tool_replacements.json"


def _snapshot_path(config: dict) -> Path | None:
    """Path del file di persistenza snapshot (accanto a tool_replacements.json)."""
    folder = (config.get("tools_toa_folder") or "").strip()
    if not folder:
        return None
    return Path(folder) / "tool_snapshot.json"


def _load_snapshot_from_disk(config: dict) -> dict:
    """Carica snapshot persistito. Chiavi JSON sono stringhe → ri-convertite in int."""
    p = _snapshot_path(config)
    if not p or not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
        data = raw.get("snapshot", {})
        return {int(k): v for k, v in data.items()}
    except Exception as e:
        log.warning(f"tool_history: impossibile caricare snapshot: {e}")
        return {}


def _save_snapshot_to_disk(config: dict, snap: dict):
    """Persiste snapshot corrente su disco (così i riavvii non perdono eventi)."""
    p = _snapshot_path(config)
    if not p:
        return
    try:
        payload = {
            "ts":       datetime.now().isoformat(timespec="seconds"),
            "snapshot": {str(k): v for k, v in snap.items()},
        }
        tmp = p.with_suffix(".tmp")
        tmp.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
        tmp.replace(p)
    except Exception as e:
        log.warning(f"tool_history: impossibile salvare snapshot: {e}")


def _load_history(config: dict) -> list:
    p = _history_path(config)
    if not p or not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("sostituzioni", [])
    except Exception:
        return []


def _save_history(config: dict, records: list):
    p = _history_path(config)
    if not p:
        return
    try:
        # Mantieni solo gli ultimi MAX_RECORD
        records = records[-MAX_RECORD:]
        p.write_text(
            json.dumps({"sostituzioni": records}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        log.warning(f"tool_history: impossibile salvare storico: {e}")


# ── Rilevamento sostituzioni ──────────────────────────────────────────────────

def on_tools_updated(tools_new: dict, config: dict):
    """
    Chiamato ogni volta che tools_machine.json viene ricaricato (mtime cambiato).

    Confronta lo snapshot precedente con il TOA corrente tramite `tool_id`
    (Identnummer Sinumerik, stabile per utensile fisico).

    Casi rilevati:
      - tool_id sparito (non più in TOA, non in 9998/9999) → RIMOSSO
      - tool_id nuovo (mai visto)                         → INSERITO
      - tool_id comune, delta vita > 0 e life_new > 80%   → SOSTITUITO
      - tool_id comune, delta vita > 0 e life_new ≤ 80%   → ALLUNGAMENTO_VITA
      - tool_id comune, posizione cambiata, vita invariata/scesa → solo log
      - tool_id comune, vita scesa (ha lavorato)          → nessun evento
    """
    global _snapshot_precedente

    # Bootstrap: carica snapshot persistito al primo tick dopo un restart
    if not _snapshot_precedente:
        persisted = _load_snapshot_from_disk(config)
        if persisted:
            _snapshot_precedente = persisted
            log.info(f"tool_history: snapshot ripristinato da disco ({len(persisted)} utensili)")
        else:
            # Primissimo avvio: memorizza senza registrare eventi
            _snapshot_precedente = _build_snapshot(tools_new)
            _save_snapshot_to_disk(config, _snapshot_precedente)
            return

    snap_old = _snapshot_precedente
    snap_new = _build_snapshot(tools_new)
    now      = datetime.now().isoformat(timespec="seconds")
    nuovi    = []
    existing_records = _load_history(config)

    old_ids = set(snap_old.keys())
    new_ids = set(snap_new.keys())

    spariti = old_ids - new_ids   # utensile non più in TOA
    arrivati = new_ids - old_ids  # tool_id mai visto prima
    comuni   = old_ids & new_ids  # stesso utensile fisico

    # Finestra anti-duplicato — guarda solo gli ultimi 50 record delle ultime 2h
    due_ore_fa = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
    recent_tail = existing_records[-50:]

    def _gia_registrato(tool_id: int, tipo: str) -> bool:
        return any(
            r.get("tool_id") == tool_id
            and r.get("tipo") == tipo
            and (r.get("ts") or "") >= due_ore_fa
            for r in recent_tail
        )

    # ── 1. RIMOSSI: tool_id sparito dal TOA ──────────────────────────────────
    for tid in spariti:
        old = snap_old[tid]
        mag_old = str(old.get("magazine") or "")

        # Era in buffer/mandrino → uscita naturale, non è una rimozione reale
        if mag_old in ("9998", "9999"):
            continue

        if _gia_registrato(tid, "rimosso"):
            continue

        record = {
            "ts":              now,
            "tool_id":         tid,
            "alias":           old.get("alias", ""),
            "posizione":       old.get("position"),
            "magazine":        old.get("magazine"),
            "duplo":           old.get("duplo", 1),
            "vita_prima":      round(old.get("life_percent") or 0, 1),
            "vita_dopo":       None,
            "tipo":            "rimosso",
            "causa":           None,   # popup: rottura | liberare_spazio
            "classificato_ts": None,
        }
        nuovi.append(record)
        log.info(
            f"tool_history: rimosso — T{tid} {old.get('alias','')} "
            f"pos.{old.get('position')} vita {old.get('life_percent') or 0:.0f}%"
        )

    # ── 2. INSERITI: tool_id nuovo ───────────────────────────────────────────
    for tid in arrivati:
        new = snap_new[tid]
        mag_new = str(new.get("magazine") or "")

        # Entrata in buffer/mandrino non è un vero inserimento
        if mag_new in ("9998", "9999"):
            continue

        if _gia_registrato(tid, "inserito"):
            continue

        record = {
            "ts":              now,
            "tool_id":         tid,
            "alias":           new.get("alias", ""),
            "posizione":       new.get("position"),
            "magazine":        new.get("magazine"),
            "duplo":           new.get("duplo", 1),
            "vita_prima":      None,
            "vita_dopo":       round(new.get("life_percent") or 0, 1),
            "tipo":            "inserito",
            "causa":           "montaggio",   # auto-classificato
            "classificato_ts": now,
        }
        nuovi.append(record)
        log.info(
            f"tool_history: inserito — T{tid} {new.get('alias','')} "
            f"pos.{new.get('position')} vita {new.get('life_percent') or 0:.0f}%"
        )

    # ── 3. COMUNI: stesso tool_id, analisi indipendente di posizione e vita ──
    for tid in comuni:
        old = snap_old[tid]
        new = snap_new[tid]

        # 3a. Posizione cambiata → solo log, nessun record
        pos_old = (old.get("magazine"), old.get("position"))
        pos_new = (new.get("magazine"), new.get("position"))
        if pos_old != pos_new:
            log.info(
                f"tool_history: spostato — T{tid} {new.get('alias','')} "
                f"{pos_old} → {pos_new}"
            )

        # 3b. Analisi vita (indipendente dalla posizione)
        lp_old = old.get("life_percent") or 0
        lp_new = new.get("life_percent") or 0
        delta  = lp_new - lp_old

        if delta < DELTA_MIN_AUMENTO:
            continue  # vita invariata o scesa → ha lavorato, nessun evento

        # Vita aumentata: sostituzione completa vs allungamento manuale
        if lp_new > SOGLIA_SOSTITUZIONE_PCT:
            tipo  = "sostituito"
            causa = None       # popup: rottura | usura_normale
            cl_ts = None
        else:
            tipo  = "allungamento_vita"
            causa = "manuale"  # auto-classificato, prezioso per ML
            cl_ts = now

        if _gia_registrato(tid, tipo):
            continue

        record = {
            "ts":              now,
            "tool_id":         tid,
            "alias":           new.get("alias", ""),
            "posizione":       new.get("position"),
            "magazine":        new.get("magazine"),
            "duplo":           new.get("duplo", 1),
            "vita_prima":      round(lp_old, 1),
            "vita_dopo":       round(lp_new, 1),
            "tipo":            tipo,
            "causa":           causa,
            "classificato_ts": cl_ts,
        }
        nuovi.append(record)
        log.info(
            f"tool_history: {tipo} — T{tid} {new.get('alias','')} "
            f"pos.{new.get('position')} {lp_old:.0f}% → {lp_new:.0f}%"
        )

    # ── Persistenza ──────────────────────────────────────────────────────────
    if nuovi:
        existing = _load_history(config)
        _save_history(config, existing + nuovi)

        # Notifiche Telegram
        try:
            from telegram_monitor.notifier import send_message
            import asyncio
            EMOJI = {
                "rimosso":            "❌",
                "inserito":           "🆕",
                "sostituito":         "🔄",
                "allungamento_vita":  "✅",
            }
            for r in nuovi:
                emoji = EMOJI.get(r["tipo"], "ℹ️")
                vp, vd = r.get("vita_prima"), r.get("vita_dopo")
                if vp is None:
                    vita_str = f"nuovo → {vd}%"
                elif vd is None:
                    vita_str = f"{vp}% → rimosso"
                else:
                    vita_str = f"{vp}% → {vd}%"
                msg = (
                    f"{emoji} *Utensile {r['tipo'].replace('_',' ').upper()}*\n"
                    f"`{r['alias']}` T{r['tool_id']} pos.{r['posizione'] or '?'}\n"
                    f"Vita: {vita_str}"
                )
                asyncio.create_task(send_message(msg))
        except Exception:
            pass

    # Aggiorna snapshot in RAM + persisti su disco (sempre, anche se no eventi,
    # perché la posizione potrebbe essere cambiata)
    _snapshot_precedente = snap_new
    _save_snapshot_to_disk(config, snap_new)


def _build_snapshot(tools: dict) -> dict:
    """
    Costruisce snapshot indicizzato per tool_id (Identnummer Sinumerik).

    Utensili senza tool_id valido (es. record corrotti) vengono esclusi.
    """
    snap = {}
    for t in tools.values():
        tid = t.get("tool_id")
        if tid is None:
            continue
        try:
            tid = int(tid)
        except (TypeError, ValueError):
            continue

        alias = (t.get("name") or "").upper().strip()
        snap[tid] = {
            "alias":          alias,
            "life_percent":   t.get("life_percent"),
            "life_remaining": t.get("life_remaining"),
            "life_total":     t.get("life_total"),
            "is_worn":        t.get("is_worn", False),
            "is_enabled":     t.get("is_enabled", True),
            "position":       t.get("position"),
            "magazine":       t.get("magazine"),
            "duplo":          t.get("duplo", 1),
        }
    return snap


# ── Alert vita bassa ──────────────────────────────────────────────────────────

def check_low_life_alert(tools: dict, alias_attivi: list[str], config: dict):
    """
    Chiamato dal tick di macchina_live con gli alias degli utensili
    attivi nel programma corrente.
    Manda alert Telegram se vita < SOGLIA_VITA_BASSA e non già inviato
    negli ultimi THROTTLE_MINUTES minuti.
    """
    if not alias_attivi or not tools:
        return

    now = datetime.now()
    da_notificare = []

    for alias in alias_attivi:
        alias_up = alias.upper().strip()
        # Cerca il duplo con vita più bassa tra quelli abilitati
        candidati = [
            t for t in tools.values()
            if (t.get("name") or "").upper().strip() == alias_up
            and t.get("is_enabled", True)
            and not t.get("is_worn", False)
        ]
        if not candidati:
            continue

        lp_min = min((t.get("life_percent") or 100) for t in candidati)
        if lp_min > SOGLIA_VITA_BASSA:
            continue

        # Throttle: non inviare se già inviato di recente
        ultimo = _alert_inviati.get(alias_up)
        if ultimo and (now - ultimo) < timedelta(minutes=THROTTLE_MINUTES):
            continue

        _alert_inviati[alias_up] = now
        da_notificare.append((alias_up, lp_min))

    if da_notificare:
        try:
            from telegram_monitor.notifier import send_message
            import asyncio
            for alias, lp in da_notificare:
                msg = (
                    f"⚠️ *Utensile sotto soglia*\n"
                    f"`{alias}` — vita residua: *{lp:.0f}%*\n"
                    f"In lavorazione ora"
                )
                asyncio.create_task(send_message(msg))
                log.info(f"tool_history: alert vita bassa — {alias} {lp:.0f}%")
        except Exception as e:
            log.warning(f"tool_history: alert send error: {e}")


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/sostituzioni/{ts}/causa")
async def classifica_sostituzione(ts: str, body: dict = Body(...)):
    """
    Classifica la causa di una sostituzione utensile.
    causa: rottura | usura | liberare_spazio
    ts: timestamp ISO della sostituzione
    """
    from database.db_handler import carica_configurazione as _cfg
    config  = _cfg()
    records = _load_history(config)
    causa   = (body.get("causa") or "").strip()
    # sostituito → rottura | usura_normale
    # rimosso    → liberare_spazio | rottura
    CAUSE_VALIDE = {"rottura", "usura_normale", "liberare_spazio"}
    if causa not in CAUSE_VALIDE:
        from fastapi import HTTPException
        raise HTTPException(400, f"causa non valida: {causa}. Valide: {CAUSE_VALIDE}")
    ts_norm = ts.strip().replace(" ", "T")
    alias_r  = (body.get("alias") or "").strip().upper()
    pos_r    = body.get("posizione")
    aggiornato = False
    for r in records:
        r_ts = (r.get("ts") or "").strip()
        if r_ts not in (ts_norm, ts):
            continue
        # Se stesso ts ma più record, discrimina per alias+posizione
        if alias_r and r.get("alias","").upper() != alias_r:
            continue
        if pos_r is not None and r.get("posizione") != pos_r:
            continue
        if r.get("causa") is not None:
            continue  # già classificato — salta
        r["causa"]            = causa
        r["classificato_ts"]  = datetime.now().isoformat(timespec="seconds")
        aggiornato = True
        log.info(f"tool_history: classificata {r.get('alias')} pos={r.get('posizione')} ts={r_ts} causa={causa}")
        break
    if not aggiornato:
        log.warning(f"tool_history: non trovata ts={ts!r} alias={alias_r!r} pos={pos_r}")
        from fastapi import HTTPException
        raise HTTPException(404, f"sostituzione non trovata")
    _save_history(config, records)
    return {"ok": True, "ts": ts, "causa": causa}


@router.post("/sostituzioni/{ts}/ignora")
async def ignora_sostituzione(ts: str, body: dict = Body({})):
    """
    Marca una sostituzione come ignorata (causa = 'ignorata').
    Non riapparirà nei popup.
    """
    from database.db_handler import carica_configurazione as _cfg
    config  = _cfg()
    records = _load_history(config)
    ts_norm  = ts.strip().replace(" ", "T")
    alias_r  = (body.get("alias") or "").strip().upper() if isinstance(body, dict) else ""
    pos_r    = body.get("posizione") if isinstance(body, dict) else None
    aggiornato = False
    for r in records:
        r_ts = (r.get("ts") or "").strip()
        if r_ts not in (ts_norm, ts):
            continue
        if alias_r and r.get("alias","").upper() != alias_r:
            continue
        if pos_r is not None and r.get("posizione") != pos_r:
            continue
        if r.get("causa") is not None:
            continue
        r["causa"]           = "ignorata"
        r["classificato_ts"] = datetime.now().isoformat(timespec="seconds")
        aggiornato = True
        log.info(f"tool_history: ignorata {r.get('alias')} pos={r.get('posizione')} ts={r_ts}")
        break
    if aggiornato:
        _save_history(config, records)
    return {"ok": True, "ts": ts, "aggiornato": aggiornato}


@router.get("/sostituzioni/non-classificate")
async def get_sostituzioni_non_classificate():
    """Restituisce sostituzioni senza causa classificata (per popup frontend)."""
    from database.db_handler import carica_configurazione as _cfg
    config  = _cfg()
    records = _load_history(config)
    non_class = [
        r for r in records
        if r.get("causa") is None
        and r.get("tipo") in ("sostituito", "rimosso")
        and str(r.get("magazine") or "") not in ("9998", "9999")
    ]
    return {"sostituzioni": list(reversed(non_class))[:10]}


@router.get("/sostituzioni")
async def get_sostituzioni(limit: int = 100):
    """Restituisce lo storico sostituzioni utensile."""
    config = carica_configurazione()
    records = _load_history(config)
    return {
        "ok":          True,
        "totale":      len(records),
        "sostituzioni": list(reversed(records))[:limit],
    }


@router.get("/vita-ottimale/{alias}")
async def get_vita_ottimale(alias: str):
    """
    Suggerimento vita ottimale per un utensile specifico.
    Ritorna None se dati insufficienti (<10 campioni).
    """
    from database.db_handler import carica_configurazione as _cfg
    from ml.vita_ottimale import calcola_vita_ottimale
    config  = _cfg()
    records = _load_history(config)
    ris     = calcola_vita_ottimale(alias, records)
    if not ris:
        return {"suggerimento": None, "motivo": "dati insufficienti"}
    return {"suggerimento": ris}


@router.get("/vita-ottimale")
async def get_vita_ottimale_magazine():
    """
    Suggerimenti vita ottimale per tutti gli utensili con abbastanza dati.
    """
    from database.db_handler import carica_configurazione as _cfg
    from ml.vita_ottimale import suggerimenti_magazine
    config  = _cfg()
    records = _load_history(config)
    ris     = suggerimenti_magazine(records)
    return {"suggerimenti": ris, "n_utensili": len(ris)}


@router.post("/pulizia-m9998")
async def pulizia_record_m9998():
    """
    Rimuove o marca come 'mandrino' i record con magazine 9998/9999
    che sono stati registrati erroneamente come rimossi.
    """
    from database.db_handler import carica_configurazione as _cfg
    config  = _cfg()
    records = _load_history(config)
    n_rimossi = 0
    records_puliti = []
    for r in records:
        if (r.get("tipo") == "rimosso" and
            str(r.get("magazine") or "") in ("9998", "9999")):
            n_rimossi += 1
            # Marca come 'mandrino' invece di rimuovere — preserva storico
            r["causa"] = "mandrino"
            r["classificato_ts"] = datetime.now().isoformat(timespec="seconds")
        records_puliti.append(r)
    _save_history(config, records_puliti)
    return {"ok": True, "record_corretti": n_rimossi}


@router.get("/stato-snapshot")
async def get_stato_snapshot():
    """Stato interno: dimensione snapshot precedente e ultimo alert per alias."""
    return {
        "snapshot_size": len(_snapshot_precedente),
        "alert_recenti": {
            k: v.isoformat() for k, v in _alert_inviati.items()
        },
    }


# ── Utilizzo magazine ─────────────────────────────────────────────────────────



@router.get("/utilizzo-magazine")
async def get_utilizzo_magazine(giorni: int = 90):
    """
    Analizza l'utilizzo degli utensili montati in macchina.
    Incrocia TOA corrente con programmi eseguiti in worktrack_projects.json.
    """
    import traceback as _tb
    from database.db_handler import carica_configurazione as _cfg
    from api.routers.tools import _load_tools_db
    from api.routers.progetti import _load_progetti

    config = _cfg()
    now    = datetime.now()

    try:
        # ── 1. TOA corrente ──────────────────────────────────────────────────
        tools_db, _, _ = _load_tools_db()
        ESCLUSI = {9998, 9999, None}
        utensili_macchina = {
            t["name"].upper().strip(): t
            for t in tools_db.values()
            if t.get("name") and t.get("magazine") not in ESCLUSI
        }
        if not utensili_macchina:
            return {"ok": True, "utensili": [], "riepilogo": {
                "totale_in_macchina": 0, "attivi": 0, "dormienti": 0,
                "inutilizzati": 0, "nuovi": 0
            }, "giorni_analisi": giorni, "data_analisi": now.strftime("%d/%m/%Y %H:%M")}

        # ── 2. Statistiche per alias ─────────────────────────────────────────
        stats = {alias: {"ultima_chiamata": None, "n_chiamate": 0,
                         "n_programmi": 0, "ore_stimate": 0.0, "pgm_ids": set()}
                 for alias in utensili_macchina}

        STATI_OK = {"completato", "in_macchina", "in_main", "in_lavorazione"}

        data_proj = _load_progetti(config)
        for proj in data_proj.get("projects", []):
            for step in proj.get("steps", []):
                for task in step.get("tasks", []):
                    if task.get("text", "").strip().lower() != "fresatura":
                        continue
                    for pgm in task.get("programs", []):
                        if pgm.get("stato") not in STATI_OK:
                            continue

                        # Parse timestamp
                        ts_pgm = None
                        for ts_key in ("tempoInizio", "tempoFine", "dataPost"):
                            ts_str = (pgm.get(ts_key) or "").strip()[:19]
                            if not ts_str:
                                continue
                            try:
                                if ts_str[2:3] == "/":
                                    p = ts_str.replace(" ", "/").replace(":", "/").split("/")
                                    if len(p) >= 3:
                                        ts_pgm = datetime(int(p[2]), int(p[1]), int(p[0]),
                                                          int(p[3]) if len(p)>3 else 0,
                                                          int(p[4]) if len(p)>4 else 0)
                                else:
                                    ts_pgm = datetime.fromisoformat(ts_str)
                                break
                            except Exception:
                                continue

                        # Alias del programma — tutte le fonti
                        alias_set = set()
                        for a in (pgm.get("utensili_lista") or []):
                            if a: alias_set.add(a.upper().strip())
                        for u in (pgm.get("utensili") or []):
                            a = (u.get("alias") or "").strip()
                            if a: alias_set.add(a.upper())
                        a_single = (pgm.get("utensile") or "").strip()
                        if a_single: alias_set.add(a_single.upper())

                        ore = (float(pgm.get("tempoStimato") or 0) or 0.0) / 60.0
                        pgm_id = pgm.get("filename") or pgm.get("id") or ""

                        for alias in alias_set:
                            if alias not in stats:
                                continue
                            s = stats[alias]
                            s["n_chiamate"] += 1
                            s["ore_stimate"] = round(s["ore_stimate"] + ore, 2)
                            if ts_pgm and (s["ultima_chiamata"] is None or ts_pgm > s["ultima_chiamata"]):
                                s["ultima_chiamata"] = ts_pgm
                            if pgm_id and pgm_id not in s["pgm_ids"]:
                                s["pgm_ids"].add(pgm_id)
                                s["n_programmi"] += 1

        # ── 3. Data montaggio da tool_replacements ───────────────────────────
        replacements = _load_history(config)
        montaggio: dict = {}
        for r in replacements:
            alias_up = (r.get("alias") or "").upper().strip()
            if alias_up not in utensili_macchina:
                continue
            try:
                ts = datetime.fromisoformat(r["ts"][:19])
            except Exception:
                continue
            if r.get("tipo") in ("sostituito", "allungamento_vita"):
                if alias_up not in montaggio or ts > montaggio[alias_up]:
                    montaggio[alias_up] = ts

        # ── 4. Classificazione ───────────────────────────────────────────────
        SOGLIA_ATTIVO    = 30
        SOGLIA_DORMIENTE = 90
        SOGLIA_NUOVO     = 30

        risultati = []
        for alias, s in stats.items():
            tool = utensili_macchina[alias]
            uc   = s["ultima_chiamata"]
            mont = montaggio.get(alias)
            giorni_silenzio = (now - uc).days if uc else None

            if mont and (now - mont).days < SOGLIA_NUOVO and not uc:
                categoria = "nuovo"
            elif uc is None:
                categoria = "inutilizzato"
            elif giorni_silenzio <= SOGLIA_ATTIVO:
                categoria = "attivo"
            elif giorni_silenzio <= SOGLIA_DORMIENTE:
                categoria = "dormiente"
            else:
                categoria = "inutilizzato"

            risultati.append({
                "alias":           alias,
                "magazine":        tool.get("magazine"),
                "posizione":       tool.get("position"),
                "life_percent":    tool.get("life_percent"),
                "is_enabled":      tool.get("is_enabled", True),
                "categoria":       categoria,
                "ultima_chiamata": uc.strftime("%d/%m/%Y") if uc else None,
                "giorni_silenzio": giorni_silenzio,
                "n_chiamate":      s["n_chiamate"],
                "n_programmi":     s["n_programmi"],
                "ore_stimate":     s["ore_stimate"],
                "data_montaggio":  mont.strftime("%d/%m/%Y") if mont else None,
            })

        ORDINE = {"inutilizzato": 0, "dormiente": 1, "nuovo": 2, "attivo": 3}
        risultati.sort(key=lambda x: (ORDINE.get(x["categoria"], 9), -(x["giorni_silenzio"] or 9999)))

        riepilogo = {
            "totale_in_macchina": len(risultati),
            "attivi":       sum(1 for r in risultati if r["categoria"] == "attivo"),
            "dormienti":    sum(1 for r in risultati if r["categoria"] == "dormiente"),
            "inutilizzati": sum(1 for r in risultati if r["categoria"] == "inutilizzato"),
            "nuovi":        sum(1 for r in risultati if r["categoria"] == "nuovo"),
        }

        return {
            "ok": True,
            "giorni_analisi": giorni,
            "data_analisi": now.strftime("%d/%m/%Y %H:%M"),
            "riepilogo": riepilogo,
            "utensili": risultati,
        }

    except Exception as _e:
        import logging as _log
        _log.getLogger("tool_history").error(f"utilizzo-magazine: {_e}", exc_info=True)
        return {"ok": False, "error": str(_e), "detail": _tb.format_exc()[-1500:]}


@router.get("/utilizzo-debug")
async def debug_utilizzo():
    """Debug: mostra cosa trova nel TOA e nei programmi."""
    from database.db_handler import carica_configurazione as _cfg
    from api.routers.tools import _load_tools_db
    from api.routers.progetti import _load_progetti

    config   = _cfg()
    tools_db, _, _ = _load_tools_db()
    data     = _load_progetti(config)
    progetti = data.get("projects", [])

    ESCLUSI = {9998, 9999, None}
    toa_aliases = {t["name"].upper() for t in tools_db.values()
                   if t.get("name") and t.get("magazine") not in ESCLUSI}

    STATI = {"completato", "in_macchina", "in_main", "in_lavorazione"}
    n_pgm_tot = n_stati = n_lista = n_utensile = 0
    alias_pgm: set = set()

    for proj in progetti:
        for step in proj.get("steps", []):
            for task in step.get("tasks", []):
                if task.get("text", "").strip().lower() != "fresatura": continue
                for pgm in task.get("programs", []):
                    n_pgm_tot += 1
                    if pgm.get("stato") in STATI:     n_stati    += 1
                    if pgm.get("utensili_lista"):      n_lista    += 1
                    if pgm.get("utensile"):            n_utensile += 1
                    for a in (pgm.get("utensili_lista") or []):
                        if a: alias_pgm.add(a.upper())
                    for u in (pgm.get("utensili") or []):
                        if u.get("alias"): alias_pgm.add(u["alias"].upper())
                    if pgm.get("utensile"): alias_pgm.add(pgm["utensile"].upper())

    return {
        "toa_in_macchina":                len(toa_aliases),
        "toa_esempi":                     sorted(toa_aliases)[:15],
        "progetti":                       len(progetti),
        "programmi_totali":               n_pgm_tot,
        "programmi_stato_eseguito":       n_stati,
        "programmi_con_utensili_lista":   n_lista,
        "programmi_con_utensile_singolo": n_utensile,
        "alias_nei_programmi":            len(alias_pgm),
        "alias_in_comune_toa_pgm":        len(toa_aliases & alias_pgm),
        "alias_pgm_esempi":               sorted(alias_pgm)[:15],
    }
