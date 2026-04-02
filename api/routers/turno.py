"""
api/routers/turno.py
====================
Endpoint per riepilogo turno giornaliero.

GET  /api/turno/oggi          → snapshot notte + giorno di oggi (o più recenti)
GET  /api/turno/storico       → lista snapshot storici (ultimi N giorni)
POST /api/turno/genera        → genera/rigenera snapshot manualmente
GET  /api/turno/snapshot      → snapshot specifico per data e finestra
"""

from datetime import date, timedelta
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Literal, Optional

from api.turno_snapshot import (
    calcola_snapshot, salva_snapshot,
    _load_snapshots,
)

router = APIRouter()


@router.get("/oggi")
async def get_turno_oggi():
    """
    Restituisce i due snapshot (notte + giorno) più recenti.
    Se lo snapshot automatico non è ancora stato generato oggi,
    calcola al volo senza salvare.
    """
    oggi = date.today()
    snapshots = _load_snapshots()

    # Cerca snapshot salvati per oggi
    notte  = next((s for s in reversed(snapshots)
                   if s.get("data") == oggi.isoformat() and s.get("finestra") == "notte"), None)
    giorno = next((s for s in reversed(snapshots)
                   if s.get("data") == oggi.isoformat() and s.get("finestra") == "giorno"), None)

    # Se non ci sono, cerca ieri per notte (più comune al mattino)
    if not notte:
        ieri = (oggi - timedelta(days=1)).isoformat()
        notte = next((s for s in reversed(snapshots)
                      if s.get("data") == oggi.isoformat() and s.get("finestra") == "notte"
                      or s.get("data") == ieri and s.get("finestra") == "notte"), None)

    # Calcola live se ancora mancanti (senza salvare)
    if not notte:
        try:
            notte = calcola_snapshot("notte", oggi)
            notte["_live"] = True  # non salvato
        except Exception as e:
            notte = {"errore": str(e), "finestra": "notte"}

    if not giorno:
        try:
            giorno = calcola_snapshot("giorno", oggi)
            giorno["_live"] = True
        except Exception as e:
            giorno = {"errore": str(e), "finestra": "giorno"}

    return {
        "data":   oggi.isoformat(),
        "notte":  notte,
        "giorno": giorno,
    }


@router.get("/storico")
async def get_storico(giorni: int = 14):
    """Lista snapshot degli ultimi N giorni, raggruppati per data."""
    snapshots = _load_snapshots()
    cutoff = (date.today() - timedelta(days=giorni)).isoformat()
    recenti = [s for s in snapshots if s.get("data", "") >= cutoff]

    # Raggruppa per data
    per_data: dict[str, dict] = {}
    for s in recenti:
        d = s.get("data", "")
        if d not in per_data:
            per_data[d] = {"data": d, "notte": None, "giorno": None}
        per_data[d][s.get("finestra", "")] = s

    return {
        "giorni": sorted(per_data.values(), key=lambda x: x["data"], reverse=True),
        "n_giorni": len(per_data),
    }


class GeneraRequest(BaseModel):
    finestra: Literal["notte", "giorno"]
    data: Optional[str] = None  # YYYY-MM-DD, default oggi


@router.post("/genera")
async def genera_snapshot(body: GeneraRequest):
    """
    Genera (o rigenera) snapshot per la finestra richiesta.
    Può essere chiamato manualmente dal frontend.
    """
    try:
        data_rif = date.fromisoformat(body.data) if body.data else date.today()
    except ValueError:
        raise HTTPException(status_code=400, detail="Formato data non valido — usa YYYY-MM-DD")

    try:
        snap = salva_snapshot(body.finestra, data_rif)
        return {"ok": True, "snapshot": snap}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/snapshot")
async def get_snapshot(data: str, finestra: Literal["notte", "giorno"]):
    """Restituisce uno snapshot specifico per data e finestra."""
    snapshots = _load_snapshots()
    snap = next(
        (s for s in reversed(snapshots)
         if s.get("data") == data and s.get("finestra") == finestra),
        None
    )
    if not snap:
        # Calcola live se non salvato
        try:
            snap = calcola_snapshot(finestra, date.fromisoformat(data))
            snap["_live"] = True
        except Exception as e:
            raise HTTPException(status_code=404, detail=f"Snapshot non trovato: {e}")
    return snap
