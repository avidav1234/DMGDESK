"""
api/routers/pallet_history.py
==============================
Storico cicli per pallet: contatore, tempi, guasti, interruzioni.

Un "ciclo" inizia quando il pallet passa a GREZZO con un progetto assegnato
e termina quando passa a FINITO, GUASTO o VUOTO (interruzione).

File: pallet_history.json nella stessa cartella di pallet_state.json
{
  "cicli": [
    {
      "id":         "uuid8",
      "pallet":     3,
      "progetto_id": "abc123",
      "progetto":   "4351_0221",
      "ts_inizio":  "2026-04-04T08:00:00",
      "ts_fine":    "2026-04-04T16:30:00",
      "durata_sec": 30600,
      "esito":      "completato" | "guasto" | "interruzione",
      "n_pgm":      40,
    }
  ]
}
"""

import json
import logging
import uuid
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from database.db_handler import carica_configurazione

log = logging.getLogger("pallet_history")
router = APIRouter(prefix="/api/pallet-history", tags=["Pallet History"])

MAX_CICLI = 1000

# Stato in memoria: pallet_numero → {ts_inizio, progetto_id, progetto_nome}
_cicli_aperti: dict[int, dict] = {}


# ── Path ──────────────────────────────────────────────────────────────────────

def _history_path(config: dict) -> Path | None:
    from api.routers.pallet import _pallet_path
    pp = _pallet_path(config)
    return pp.parent / "pallet_history.json"


def _load_history(config: dict) -> list:
    p = _history_path(config)
    if not p or not p.exists():
        return []
    try:
        return json.loads(p.read_text(encoding="utf-8")).get("cicli", [])
    except Exception:
        return []


def _save_history(config: dict, cicli: list):
    p = _history_path(config)
    if not p:
        return
    try:
        cicli = cicli[-MAX_CICLI:]
        p.write_text(
            json.dumps({"cicli": cicli}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        log.warning(f"pallet_history: save error: {e}")


# ── API pubblica ──────────────────────────────────────────────────────────────

def on_pallet_stato_changed(numero: int, nuovo_stato: str,
                             progetto_id: str | None, progetto_nome: str | None,
                             n_pgm: int, config: dict):
    """
    Chiamato da pallet.py ad ogni cambio stato.
    Gestisce apertura/chiusura cicli.
    """
    ora = datetime.now().isoformat(timespec="seconds")

    if nuovo_stato == "grezzo" and progetto_id:
        # Nuovo ciclo inizia
        _cicli_aperti[numero] = {
            "ts_inizio":    ora,
            "progetto_id":  progetto_id,
            "progetto":     progetto_nome or progetto_id,
        }
        log.info(f"pallet_history: P{numero} ciclo aperto — {progetto_nome}")

    elif nuovo_stato in ("finito", "guasto", "vuoto"):
        aperto = _cicli_aperti.pop(numero, None)
        if not aperto:
            return  # nessun ciclo aperto per questo pallet

        # Calcola durata
        try:
            ts_i = datetime.fromisoformat(aperto["ts_inizio"])
            ts_f = datetime.fromisoformat(ora)
            durata = int((ts_f - ts_i).total_seconds())
        except Exception:
            durata = None

        esito = {
            "finito":   "completato",
            "guasto":   "guasto",
            "vuoto":    "interruzione",
        }.get(nuovo_stato, "interruzione")

        ciclo = {
            "id":          uuid.uuid4().hex[:8],
            "pallet":      numero,
            "progetto_id": aperto["progetto_id"],
            "progetto":    aperto["progetto"],
            "ts_inizio":   aperto["ts_inizio"],
            "ts_fine":     ora,
            "durata_sec":  durata,
            "esito":       esito,
            "n_pgm":       n_pgm,
        }

        storico = _load_history(config)
        storico.append(ciclo)
        _save_history(config, storico)
        log.info(f"pallet_history: P{numero} ciclo chiuso — {esito} ({durata}s)")


def _statistiche(cicli: list) -> dict:
    """Calcola statistiche aggregate per pallet."""
    stats: dict[int, dict] = {}
    for c in cicli:
        n = c.get("pallet")
        if not n:
            continue
        if n not in stats:
            stats[n] = {
                "pallet":        n,
                "n_completati":  0,
                "n_guasti":      0,
                "n_interruzioni":0,
                "durate_sec":    [],
                "ultimo_ciclo":  None,
            }
        s = stats[n]
        esito = c.get("esito")
        if esito == "completato":
            s["n_completati"] += 1
        elif esito == "guasto":
            s["n_guasti"] += 1
        else:
            s["n_interruzioni"] += 1
        if c.get("durata_sec"):
            s["durate_sec"].append(c["durata_sec"])
        if not s["ultimo_ciclo"] or c.get("ts_fine", "") > s["ultimo_ciclo"]:
            s["ultimo_ciclo"] = c.get("ts_fine")

    # Calcola medie e riepilogo
    result = []
    for n in sorted(stats.keys()):
        s = stats[n]
        durate = s.pop("durate_sec")
        s["n_totale"]      = s["n_completati"] + s["n_guasti"] + s["n_interruzioni"]
        s["durata_media_sec"] = int(sum(durate) / len(durate)) if durate else None
        s["affidabilita_pct"] = (
            round(s["n_completati"] / s["n_totale"] * 100)
            if s["n_totale"] else None
        )
        result.append(s)
    return result


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/statistiche")
async def get_statistiche():
    """Statistiche aggregate per pallet."""
    config = carica_configurazione()
    cicli  = _load_history(config)
    return {
        "ok":         True,
        "n_cicli":    len(cicli),
        "statistiche": _statistiche(cicli),
        "aperti":     {k: v["progetto"] for k, v in _cicli_aperti.items()},
    }


@router.get("/cicli")
async def get_cicli(pallet: int | None = None, limit: int = 50):
    """Lista cicli, opzionalmente filtrati per pallet."""
    config = carica_configurazione()
    cicli  = _load_history(config)
    if pallet:
        cicli = [c for c in cicli if c.get("pallet") == pallet]
    return {
        "ok":     True,
        "totale": len(cicli),
        "cicli":  list(reversed(cicli))[:limit],
    }
