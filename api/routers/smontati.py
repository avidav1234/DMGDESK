"""
api/routers/smontati.py
========================
Endpoint per l'archivio utensili SMONTATI.

GET    /api/smontati/            → lista utensili smontati
POST   /api/smontati/            → aggiungi utensile smontato
PATCH  /api/smontati/{id}        → modifica note/alias
DELETE /api/smontati/{id}        → elimina record
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.deps import get_db_smontati
from database.db_handler import (
    aggiungi_utensile_smontato,
    modifica_utensile_smontato,
    elimina_utensile_smontato,
)
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


class UtensileSm(BaseModel):
    id: str
    alias_utensile: str
    data_smontaggio: str
    provenienza: str
    note: str


class AggiungiRequest(BaseModel):
    alias_utensile: str
    provenienza: str = "Manuale"
    note: str = ""


class ModificaRequest(BaseModel):
    nuovo_alias: Optional[str] = None
    nuova_provenienza: Optional[str] = None
    nuove_note: Optional[str] = None


class RispostaOk(BaseModel):
    ok: bool
    messaggio: str


@router.get("/", response_model=list[UtensileSm], summary="Lista utensili smontati")
async def lista_smontati():
    df, _, _ = get_db_smontati()
    return [
        UtensileSm(
            id=str(row["ID"]),
            alias_utensile=str(row["Alias_Utensile"]),
            data_smontaggio=str(row["Data_Smontaggio"]),
            provenienza=str(row.get("Provenienza", "")),
            note=str(row.get("Note", "")),
        )
        for _, row in df.iterrows()
    ]


@router.post("/", response_model=RispostaOk, summary="Aggiungi utensile smontato")
async def aggiungi_smontato(body: AggiungiRequest):
    df, _, paths = get_db_smontati()
    ok, msg = aggiungi_utensile_smontato(df, paths["utensili_smontati"], body.alias_utensile, body.provenienza, body.note)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    log.info(f"Aggiunto smontato: {body.alias_utensile}")
    return RispostaOk(ok=True, messaggio=msg)


@router.patch("/{id_utensile}", response_model=RispostaOk, summary="Modifica utensile smontato")
async def modifica_smontato(id_utensile: str, body: ModificaRequest):
    df, _, paths = get_db_smontati()
    ok, msg = modifica_utensile_smontato(df, paths["utensili_smontati"], id_utensile,
                                          body.nuovo_alias, body.nuova_provenienza, body.nuove_note)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return RispostaOk(ok=True, messaggio=msg)


@router.delete("/{id_utensile}", response_model=RispostaOk, summary="Elimina utensile smontato")
async def elimina_smontato(id_utensile: str):
    df, _, paths = get_db_smontati()
    ok, msg = elimina_utensile_smontato(df, paths["utensili_smontati"], id_utensile)
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    log.info(f"Eliminato smontato ID={id_utensile}")
    return RispostaOk(ok=True, messaggio=msg)
