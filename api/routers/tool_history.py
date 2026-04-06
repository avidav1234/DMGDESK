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

from fastapi import APIRouter
from database.db_handler import carica_configurazione

log = logging.getLogger("tool_history")
router = APIRouter(prefix="/api/tool-history", tags=["Tool History"])

# ── Costanti ──────────────────────────────────────────────────────────────────
SOGLIA_VITA_BASSA   = 20    # % sotto cui scatta l'alert
SOGLIA_SOSTITUZIONE = 30    # delta life_percent per rilevare sostituzione
THROTTLE_MINUTES    = 30    # minuti tra due alert sullo stesso alias
MAX_RECORD          = 500   # massimo record nello storico

# ── Stato in memoria ─────────────────────────────────────────────────────────
_snapshot_precedente: dict = {}   # alias → {life_percent, is_worn, is_enabled}
_alert_inviati: dict = {}         # alias → datetime ultimo alert


# ── Path file storico ─────────────────────────────────────────────────────────

def _history_path(config: dict) -> Path | None:
    folder = (config.get("tools_toa_folder") or "").strip()
    if not folder:
        return None
    return Path(folder) / "tool_replacements.json"


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
    Confronta con lo snapshot precedente e registra le sostituzioni.
    """
    global _snapshot_precedente

    if not _snapshot_precedente:
        # Prima volta — salva snapshot senza registrare nulla
        _snapshot_precedente = _build_snapshot(tools_new)
        return

    snap_old = _snapshot_precedente
    snap_new = _build_snapshot(tools_new)
    now      = datetime.now().isoformat(timespec="seconds")
    nuovi    = []

    # ── Rilevamento rimozioni (utensile presente prima, assente dopo) ──────────
    for key, old_t in snap_old.items():
        if key not in snap_new:
            # Utensile sparito dal TOA — rimosso senza rimpiazzo
            record = {
                "ts":              now,
                "alias":           old_t.get("alias", key),
                "posizione":       old_t.get("position"),
                "magazine":        old_t.get("magazine"),
                "vita_prima":      round(old_t.get("life_percent") or 0, 1),
                "vita_dopo":       None,
                "tipo":            "rimosso",
                "causa":           None,   # null = non classificato; liberare_spazio|rottura
                "classificato_ts": None,
            }
            nuovi.append(record)
            log.info(
                f"tool_history: rimosso — {old_t.get('alias',key)} "
                f"pos.{old_t.get('position')} vita {old_t.get('life_percent',0):.0f}%"
            )

    # ── Rilevamento sostituzioni e allungamenti vita ─────────────────────────
    for key, new in snap_new.items():
        old = snap_old.get(key)
        if not old:
            continue  # nuovo utensile aggiunto — non è una sostituzione

        lp_old = old.get("life_percent") or 0
        lp_new = new.get("life_percent") or 0
        delta  = lp_new - lp_old

        if delta >= 70:
            # Sostituzione fisica — utensile nuovo montato
            record = {
                "ts":              now,
                "alias":           new["alias"],
                "posizione":       new.get("position"),
                "magazine":        new.get("magazine"),
                "vita_prima":      round(lp_old, 1),
                "vita_dopo":       round(lp_new, 1),
                "tipo":            "sostituito",
                "causa":           None,   # null = non classificato; rottura|usura_normale
                "classificato_ts": None,
            }
            nuovi.append(record)
            log.info(
                f"tool_history: sostituito — {new['alias']} "
                f"pos.{new.get('position')} "
                f"{lp_old:.0f}% → {lp_new:.0f}%"
            )

        elif 20 <= delta < 70:
            # Allungamento vita — operatore ha modificato il valore vita manualmente
            # Registrato automaticamente senza popup — dato ML prezioso
            record = {
                "ts":              now,
                "alias":           new["alias"],
                "posizione":       new.get("position"),
                "magazine":        new.get("magazine"),
                "vita_prima":      round(lp_old, 1),
                "vita_dopo":       round(lp_new, 1),
                "tipo":            "allungamento_vita",
                "causa":           "manuale",   # classificato automaticamente
                "classificato_ts": now,
            }
            nuovi.append(record)
            log.info(
                f"tool_history: allungamento_vita — {new['alias']} "
                f"pos.{new.get('position')} "
                f"{lp_old:.0f}% → {lp_new:.0f}%"
            )

    if nuovi:
        existing = _load_history(config)
        _save_history(config, existing + nuovi)

        # Notifica Telegram per ogni sostituzione
        try:
            from telegram_monitor.notifier import send_message
            import asyncio
            for r in nuovi:
                emoji   = "🔄" if r["tipo"] == "sostituito" else "✅"
                msg     = (
                    f"{emoji} *Utensile {r['tipo'].upper()}*\n"
                    f"`{r['alias']}` pos.{r['posizione'] or '?'}\n"
                    f"Vita: {r['vita_prima']}% → {r['vita_dopo']}%"
                )
                asyncio.create_task(send_message(msg))
        except Exception:
            pass

    _snapshot_precedente = snap_new


def _build_snapshot(tools: dict) -> dict:
    snap = {}
    for t in tools.values():
        alias = (t.get("name") or "").upper().strip()
        if not alias:
            continue
        key = f"{alias}_{t.get('position', '')}_{t.get('magazine', '')}"
        snap[key] = {
            "alias":        alias,
            "life_percent": t.get("life_percent"),
            "is_worn":      t.get("is_worn", False),
            "is_enabled":   t.get("is_enabled", True),
            "position":     t.get("position"),
            "magazine":     t.get("magazine"),
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
async def classifica_sostituzione(ts: str, body: dict):
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
    aggiornato = False
    for r in records:
        if r.get("ts") == ts:
            r["causa"]            = causa
            r["classificato_ts"]  = datetime.now().isoformat(timespec="seconds")
            aggiornato = True
            break
    if not aggiornato:
        from fastapi import HTTPException
        raise HTTPException(404, "sostituzione non trovata")
    _save_history(config, records)
    return {"ok": True, "ts": ts, "causa": causa}


@router.get("/sostituzioni/non-classificate")
async def get_sostituzioni_non_classificate():
    """Restituisce sostituzioni senza causa classificata (per popup frontend)."""
    from database.db_handler import carica_configurazione as _cfg
    config  = _cfg()
    records = _load_history(config)
    non_class = [r for r in records if r.get("causa") is None and r.get("tipo") in ("sostituito", "rimosso")]
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


@router.get("/stato-snapshot")
async def get_stato_snapshot():
    """Stato interno: dimensione snapshot precedente e ultimo alert per alias."""
    return {
        "snapshot_size": len(_snapshot_precedente),
        "alert_recenti": {
            k: v.isoformat() for k, v in _alert_inviati.items()
        },
    }
