"""
api/routers/holder_bussole.py
==============================
Endpoint per Holder smontati e Bussole idraulico.

GET    /api/holder-bussole/holder/          → lista holder smontati
POST   /api/holder-bussole/holder/          → aggiungi holder
PATCH  /api/holder-bussole/holder/{alias}   → modifica quantità/note
DELETE /api/holder-bussole/holder/{alias}   → elimina

GET    /api/holder-bussole/bussole/             → lista bussole
POST   /api/holder-bussole/bussole/             → aggiungi bussola
DELETE /api/holder-bussole/bussole/{codice}     → elimina bussola
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from api.deps import get_db_smontati, get_db_bussole
from database.db_handler import (
    aggiungi_holder_smontato,
    modifica_holder_smontato,
    elimina_holder_smontato,
    aggiungi_bussola_idraulico,
    decrementa_bussola_idraulico,
    elimina_bussola_idraulico,
)
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


# ── Pydantic models ────────────────────────────────────────

class HolderSm(BaseModel):
    alias_holder: str
    data_smontaggio: str
    quantita: int
    note: str

class AggiungiHolderRequest(BaseModel):
    alias_holder: str
    quantita: int = 1
    note: str = ""

class ModificaHolderRequest(BaseModel):
    nuova_quantita: Optional[int] = None
    nuove_note: Optional[str] = None

class Bussola(BaseModel):
    codice_bussola: str
    diametro: str
    quantita: int
    data_acquisizione: str
    note: str

class AggiungiBussolaRequest(BaseModel):
    codice: str
    diametro: str
    quantita: int = Field(1, ge=1)
    note: str = ""

class RispostaOk(BaseModel):
    ok: bool
    messaggio: str


# ── Holder ─────────────────────────────────────────────────

@router.get("/holder/", response_model=list[HolderSm], summary="Lista holder smontati")
async def lista_holder():
    _, df, _ = get_db_smontati()
    return [
        HolderSm(
            alias_holder=str(row["Alias_Holder"]),
            data_smontaggio=str(row.get("Data_Smontaggio", "")),
            quantita=int(row.get("Quantita", 1)),
            note=str(row.get("Note", "")),
        )
        for _, row in df.iterrows()
    ]


@router.post("/holder/", response_model=RispostaOk, summary="Aggiungi holder smontato")
async def aggiungi_holder(body: AggiungiHolderRequest):
    _, df, paths = get_db_smontati()
    ok, msg = aggiungi_holder_smontato(df, paths["holder_smontati"], body.alias_holder, body.quantita, body.note)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return RispostaOk(ok=True, messaggio=msg)


@router.patch("/holder/{alias_holder}", response_model=RispostaOk, summary="Modifica holder")
async def modifica_holder(alias_holder: str, body: ModificaHolderRequest):
    _, df, paths = get_db_smontati()
    ok, msg = modifica_holder_smontato(df, paths["holder_smontati"], alias_holder,
                                        body.nuova_quantita, body.nuove_note)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return RispostaOk(ok=True, messaggio=msg)


@router.delete("/holder/{alias_holder}", response_model=RispostaOk, summary="Elimina holder")
async def elimina_holder(alias_holder: str):
    _, df, paths = get_db_smontati()
    ok, msg = elimina_holder_smontato(df, paths["holder_smontati"], alias_holder)
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return RispostaOk(ok=True, messaggio=msg)


# ── Bussole ────────────────────────────────────────────────

@router.get("/bussole/", response_model=list[Bussola], summary="Lista bussole idraulico")
async def lista_bussole():
    df, _ = get_db_bussole()
    return [
        Bussola(
            codice_bussola=str(row["Codice_Bussola"]),
            diametro=str(row.get("Diametro", "")),
            quantita=int(row.get("Quantita", 0)),
            data_acquisizione=str(row.get("Data_Acquisizione", "")),
            note=str(row.get("Note", "")),
        )
        for _, row in df.iterrows()
    ]


@router.post("/bussole/", response_model=RispostaOk, summary="Aggiungi bussola")
async def aggiungi_bussola(body: AggiungiBussolaRequest):
    df, paths = get_db_bussole()
    ok, msg = aggiungi_bussola_idraulico(df, paths["bussole_idraulico"], body.codice, body.diametro, body.quantita, body.note)
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    return RispostaOk(ok=True, messaggio=msg)


@router.delete("/bussole/{codice}", response_model=RispostaOk, summary="Elimina bussola")
async def elimina_bussola(codice: str):
    df, paths = get_db_bussole()
    ok, msg = elimina_bussola_idraulico(df, paths["bussole_idraulico"], codice)
    if not ok:
        raise HTTPException(status_code=404, detail=msg)
    return RispostaOk(ok=True, messaggio=msg)
