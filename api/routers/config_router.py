"""
api/routers/config_router.py
==============================
Endpoint per la configurazione globale dell'applicazione.

GET  /api/config/percorso-nc  → legge percorso_nc_base da config.json
PUT  /api/config/percorso-nc  → salva percorso_nc_base in config.json
"""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from database.db_handler import carica_configurazione, salva_configurazione
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


class PercorsoNcResponse(BaseModel):
    percorso_nc_base: str | None   # es. "P:\\DMG_DMC_160U\\4297" oppure None se non configurato


class PercorsoNcRequest(BaseModel):
    percorso_nc_base: str          # es. "P:\\DMG_DMC_160U\\4297"


@router.get(
    "/percorso-nc",
    response_model=PercorsoNcResponse,
    summary="Legge il percorso base delle cartelle NC",
)
async def get_percorso_nc():
    """
    Restituisce il percorso base configurato per le cartelle NC.
    Esempio: "P:\\DMG_DMC_160U\\4297"
    Il percorso completo di una cartella è: percorso_nc_base + \\ + nome_cartella
    """
    config = carica_configurazione()
    return PercorsoNcResponse(percorso_nc_base=config.get("percorso_nc_base"))


@router.put(
    "/percorso-nc",
    response_model=PercorsoNcResponse,
    summary="Salva il percorso base delle cartelle NC",
)
async def set_percorso_nc(body: PercorsoNcRequest):
    """
    Salva il percorso base in config.json.
    Chiamato una sola volta durante la configurazione iniziale.
    """
    percorso = body.percorso_nc_base.strip().rstrip("\\/")
    if not percorso:
        raise HTTPException(status_code=422, detail="percorso_nc_base non può essere vuoto")

    config = carica_configurazione()
    config["percorso_nc_base"] = percorso
    ok = salva_configurazione(config)
    if not ok:
        raise HTTPException(status_code=500, detail="Impossibile salvare config.json")

    log.info(f"percorso_nc_base salvato: {percorso}")
    return PercorsoNcResponse(percorso_nc_base=percorso)
