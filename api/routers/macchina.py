"""
api/routers/macchina.py
========================
Endpoint per la gestione degli utensili IN MACCHINA (carosello CNC).

GET    /api/macchina/               → lista utensili in macchina
GET    /api/macchina/{posizione}    → singolo utensile per posizione
POST   /api/macchina/monta          → monta utensile in posizione
DELETE /api/macchina/{posizione}    → smonta utensile dalla posizione
GET    /api/macchina/posizione-libera → prima posizione disponibile
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

from api.deps import get_db_principale, get_db_smontati, get_db_bussole
from database.db_handler import (
    STATO_IN_MACCHINA,
    smonta_utensile_completo,
    monta_utensile,
    monta_utensile_con_bussola,
    trova_prima_posizione_libera,
    salva_database,
)
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


# ── Modelli Pydantic (validazione input/output) ────────────

class UtensileInMacchina(BaseModel):
    posizione: int
    alias: str
    stato: str

class MontaRequest(BaseModel):
    id_utensile: str = Field(..., description="ID utensile dalla lista smontati")
    alias_holder: str = Field(..., description="Alias holder da usare")
    posizione: int    = Field(..., description="Posizione nel carosello (1-120)")
    usa_bussola: bool = Field(False, description="True se serve bussola idraulico")

class RispostaOk(BaseModel):
    ok: bool
    messaggio: str


# ── Endpoint ───────────────────────────────────────────────

@router.get("/", response_model=list[UtensileInMacchina], summary="Lista utensili in macchina")
async def lista_utensili_macchina():
    """Restituisce tutti gli utensili attualmente nel carosello CNC."""
    df, _ = get_db_principale()
    df_macchina = df[df["Stato_Utensile"] == STATO_IN_MACCHINA].copy()
    df_macchina = df_macchina.sort_values("Posizione")

    return [
        UtensileInMacchina(
            posizione=int(row["Posizione"]),
            alias=str(row["Alias"]),
            stato=str(row["Stato_Utensile"]),
        )
        for _, row in df_macchina.iterrows()
    ]


@router.get("/posizione-libera", summary="Prima posizione libera nel carosello")
async def prima_posizione_libera():
    """Trova la prima posizione libera disponibile nel carosello."""
    df, _ = get_db_principale()
    pos = trova_prima_posizione_libera(df)
    return {"posizione_libera": pos}


@router.get("/{posizione}", response_model=UtensileInMacchina, summary="Utensile per posizione")
async def get_utensile_per_posizione(posizione: int):
    """Restituisce l'utensile in una specifica posizione del carosello."""
    df, _ = get_db_principale()
    df_macchina = df[df["Stato_Utensile"] == STATO_IN_MACCHINA]
    risultato = df_macchina[df_macchina["Posizione"] == posizione]

    if risultato.empty:
        raise HTTPException(status_code=404, detail=f"Posizione {posizione} vuota o non in macchina")

    row = risultato.iloc[0]
    return UtensileInMacchina(
        posizione=int(row["Posizione"]),
        alias=str(row["Alias"]),
        stato=str(row["Stato_Utensile"]),
    )


@router.post("/monta", response_model=RispostaOk, summary="Monta utensile in macchina")
async def monta_utensile_endpoint(body: MontaRequest):
    """
    Monta un utensile (dagli smontati) nella posizione specificata del carosello.
    Se usa_bussola=True viene scalata anche la quantità di bussole.
    """
    df_principale, paths = get_db_principale()
    df_utensili, df_holder, _ = get_db_smontati()

    try:
        if body.usa_bussola:
            df_bussole, _ = get_db_bussole()
            ok, msg = monta_utensile_con_bussola(
                df_principale, df_utensili, df_holder, df_bussole,
                paths, body.id_utensile, body.alias_holder, body.posizione
            )
        else:
            ok, msg = monta_utensile(
                df_principale, df_utensili, df_holder,
                paths, body.id_utensile, body.alias_holder, body.posizione
            )

        if not ok:
            raise HTTPException(status_code=400, detail=msg)

        log.info(f"Montato utensile ID={body.id_utensile} → pos {body.posizione}")
        return RispostaOk(ok=True, messaggio=msg)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Errore montaggio: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))


@router.delete("/{posizione}", response_model=RispostaOk, summary="Smonta utensile dalla posizione")
async def smonta_utensile_endpoint(posizione: int, note: str = ""):
    """
    Smonta l'utensile dalla posizione indicata.
    Sposta l'utensile negli smontati e libera holder/bussole.
    """
    df_principale, paths = get_db_principale()
    df_utensili, df_holder, _ = get_db_smontati()
    df_bussole, _ = get_db_bussole()

    # Trova l'alias nella posizione
    df_macchina = df_principale[df_principale["Stato_Utensile"] == STATO_IN_MACCHINA]
    riga = df_macchina[df_macchina["Posizione"] == posizione]

    if riga.empty:
        raise HTTPException(status_code=404, detail=f"Nessun utensile in posizione {posizione}")

    alias = str(riga.iloc[0]["Alias"])

    try:
        ok, msg = smonta_utensile_completo(
            alias, paths, df_utensili, df_holder, df_bussole,
            provenienza=f"Posizione {posizione}"
        )
        if not ok:
            raise HTTPException(status_code=400, detail=msg)

        log.info(f"Smontato {alias} da pos {posizione}")
        return RispostaOk(ok=True, messaggio=msg)

    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Errore smontaggio pos {posizione}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=str(e))
