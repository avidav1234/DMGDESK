"""
api/routers/generatore.py
==========================
Endpoint per il Generatore Codici Utensili.

GET  /api/generatore/tipologie   → lista tipologie utensili disponibili
GET  /api/generatore/holders     → lista porta-utensili disponibili
POST /api/generatore/genera      → genera nome + commento CNC
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from logic.code_generator_logic import UTENSILI, PORTA_UTENSILI, genera_codici
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


class GeneraRequest(BaseModel):
    tipo_utensile: str
    diametro: str
    r2_x: str = ""
    l: str = ""
    vd: str = ""
    fp: str
    tipo_holder: str
    diam_holder: str
    fresa_dedicata: bool = False
    speciale: bool = False


class GeneraResponse(BaseModel):
    nome: str
    commento: str


class Tipologia(BaseModel):
    chiave: str
    nome: str
    commento_base: str
    ha_r2: bool
    ha_vd: bool
    ha_l: bool
    ha_x: bool

class Holder(BaseModel):
    chiave: str
    lettera: str
    abbreviato: str
    diametri: list[str]


@router.get("/tipologie", response_model=list[Tipologia], summary="Lista tipologie utensili")
async def lista_tipologie():
    """Restituisce tutte le 27 tipologie utensili del catalogo."""
    return [
        Tipologia(
            chiave=k,
            nome=v.get("nome", k),
            commento_base=v.get("commento", ""),
            ha_r2=bool(v.get("has_r2")),
            ha_vd=bool(v.get("has_vd")),
            ha_l=bool(v.get("has_l")),
            ha_x=bool(v.get("has_x")),
        )
        for k, v in UTENSILI.items()
    ]


@router.get("/holders", response_model=list[Holder], summary="Lista porta-utensili")
async def lista_holders():
    """Restituisce tutti i 13 tipi di porta-utensili con i diametri disponibili."""
    return [
        Holder(
            chiave=k,
            lettera=v.get("lettera", ""),
            abbreviato=v.get("abbreviato", ""),
            diametri=v.get("diametri", []),
        )
        for k, v in PORTA_UTENSILI.items()
    ]


@router.post("/genera", response_model=GeneraResponse, summary="Genera codice utensile")
async def genera_codice(body: GeneraRequest):
    """
    Genera il nome CNC e il commento per un utensile dato i parametri.
    Stessa logica del Tab Generatore dell'app desktop.
    """
    nome, commento, errore = genera_codici(
        tipo_utensile=body.tipo_utensile,
        diametro=body.diametro,
        r2_x=body.r2_x,
        l=body.l,
        vd=body.vd,
        fp=body.fp,
        tipo_holder=body.tipo_holder,
        diam_holder=body.diam_holder,
        fresa_dedicata=body.fresa_dedicata,
        speciale=body.speciale,
    )

    if errore:
        raise HTTPException(status_code=422, detail=errore)

    log.info(f"Generato: {nome}")
    return GeneraResponse(nome=nome, commento=commento)
