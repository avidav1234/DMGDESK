"""
api/routers/pallet.py
Gestisce la persistenza degli stati pallet in pallet_state.json sulla share.

Stati possibili: vuoto | grezzo | in_lavorazione | finito | guasto
- in_lavorazione viene scritto dal router macchina_live (dalla macchina via log)
- vuoto / grezzo / guasto vengono impostati dall'operatore via questo router
- finito viene impostato automaticamente quando in_lavorazione → altro
"""

import json
import os
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database.db_handler import carica_configurazione

router = APIRouter()

STATI_VALIDI   = {"vuoto", "grezzo", "in_lavorazione", "finito", "guasto"}
STATI_MANUALI  = {"vuoto", "grezzo", "guasto"}   # operatore può impostare solo questi
N_PALLET       = 6


def _pallet_path(config: dict) -> Path:
    base = config.get("percorso_nc_base", ".")
    return Path(base) / "pallet_state.json"


def _default_state() -> dict:
    return {
        "pallet": [
            {
                "numero":    i + 1,
                "stato":     "vuoto",
                "programma": None,
                "main":      None,
                "commessa":  None,
                "aggiornato": None,
            }
            for i in range(N_PALLET)
        ],
        "ultimo_aggiornamento": None,
    }


def _load(config: dict) -> dict:
    path = _pallet_path(config)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _default_state()


def _save(config: dict, state: dict):
    path = _pallet_path(config)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        state["ultimo_aggiornamento"] = datetime.now().isoformat()
        path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Impossibile salvare pallet_state.json: {e}")


# ── Modelli ────────────────────────────────────────────────────────────────

class SetStatoBody(BaseModel):
    stato:    str
    programma: str | None = None
    main:      str | None = None
    commessa:  str | None = None


class SetLavorazioneBody(BaseModel):
    """Usato internamente da macchina_live per aggiornare il pallet in lavorazione."""
    pallet_attivo:    int | None
    programma_attivo: str | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/")
async def get_pallet():
    """Restituisce lo stato attuale di tutti i pallet."""
    config = carica_configurazione()
    return _load(config)


@router.patch("/{numero}")
async def set_stato_pallet(numero: int, body: SetStatoBody):
    """
    Imposta lo stato di un pallet manualmente.
    Solo stati manuali: vuoto | grezzo | guasto.
    """
    if not 1 <= numero <= N_PALLET:
        raise HTTPException(400, f"Numero pallet non valido: {numero} (1-{N_PALLET})")
    if body.stato not in STATI_MANUALI:
        raise HTTPException(400, f"Stato '{body.stato}' non impostabile manualmente. Usa: {STATI_MANUALI}")

    config = carica_configurazione()
    state  = _load(config)

    for p in state["pallet"]:
        if p["numero"] == numero:
            p["stato"]     = body.stato
            p["aggiornato"] = datetime.now().isoformat()
            if body.programma is not None: p["programma"] = body.programma
            if body.main      is not None: p["main"]      = body.main
            if body.commessa  is not None: p["commessa"]  = body.commessa
            break
    else:
        raise HTTPException(404, f"Pallet {numero} non trovato")

    _save(config, state)
    return {"ok": True, "pallet": numero, "stato": body.stato}


@router.post("/sync-lavorazione")
async def sync_lavorazione(body: SetLavorazioneBody):
    """
    Chiamato automaticamente dal frontend dopo ogni poll del log.
    Aggiorna: pallet_attivo → in_lavorazione, precedente in_lavorazione → finito.
    """
    config = carica_configurazione()
    state  = _load(config)

    for p in state["pallet"]:
        if body.pallet_attivo and p["numero"] == body.pallet_attivo:
            # Pallet preso dalla macchina
            p["stato"]     = "in_lavorazione"
            p["programma"] = body.programma_attivo
            p["aggiornato"] = datetime.now().isoformat()
        elif p["stato"] == "in_lavorazione" and p["numero"] != body.pallet_attivo:
            # Pallet che era in lavorazione → finito
            p["stato"]     = "finito"
            p["aggiornato"] = datetime.now().isoformat()

    _save(config, state)
    return {"ok": True}


@router.post("/invia-programma/{numero}")
async def invia_programma(numero: int, body: SetStatoBody):
    """
    Chiamato quando l'operatore invia programmi in macchina per questo pallet.
    Imposta automaticamente stato=grezzo + associa programma/commessa.
    """
    if not 1 <= numero <= N_PALLET:
        raise HTTPException(400, f"Numero pallet non valido: {numero}")

    config = carica_configurazione()
    state  = _load(config)

    for p in state["pallet"]:
        if p["numero"] == numero:
            p["stato"]     = "grezzo"
            p["programma"] = body.programma
            p["main"]      = body.main
            p["commessa"]  = body.commessa
            p["aggiornato"] = datetime.now().isoformat()
            break

    _save(config, state)
    return {"ok": True, "pallet": numero, "stato": "grezzo"}
