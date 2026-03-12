"""
api/routers/scaffale.py
========================
Endpoint per gli utensili sullo SCAFFALE (assemblati, non in macchina).

GET    /api/scaffale/                → lista utensili a scaffale
POST   /api/scaffale/sposta-in-macchina → sposta da scaffale a macchina (lookup per alias)
DELETE /api/scaffale/{alias}         → rimuovi da scaffale
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.deps import get_db_principale
from database.db_handler import STATO_SCAFFALE, STATO_IN_MACCHINA, salva_database
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


class UtensileScaffale(BaseModel):
    posizione: Optional[int] = None   # None per utensili senza posizione fissa
    alias: str
    stato: str


class SpostaRequest(BaseModel):
    alias: str                   # identificatore (alias è unico per scaffale)
    nuova_posizione_macchina: int


class RispostaOk(BaseModel):
    ok: bool
    messaggio: str


@router.get("/", response_model=list[UtensileScaffale], summary="Lista utensili a scaffale")
async def lista_scaffale():
    """Restituisce tutti gli utensili assemblati presenti sullo scaffale."""
    df, _ = get_db_principale()
    df_scaffale = df[df["Stato_Utensile"] == STATO_SCAFFALE].copy()
    df_scaffale = df_scaffale.sort_values("Alias")

    result = []
    for _, row in df_scaffale.iterrows():
        pos_str = str(row["Posizione"]).strip()
        posizione = int(pos_str) if pos_str.isdigit() else None
        result.append(UtensileScaffale(
            posizione=posizione,
            alias=str(row["Alias"]),
            stato=str(row["Stato_Utensile"]),
        ))
    return result


@router.post("/sposta-in-macchina", response_model=RispostaOk, summary="Sposta da scaffale a macchina")
async def sposta_in_macchina(body: SpostaRequest):
    """
    Sposta un utensile dallo scaffale alla posizione specificata nel carosello.
    Identifica l'utensile per alias (non per posizione, che può essere vuota).
    """
    df, paths = get_db_principale()

    # Cerca per alias tra gli utensili a scaffale
    riga = df[
        (df["Alias"] == body.alias) &
        (df["Stato_Utensile"] == STATO_SCAFFALE)
    ]
    if riga.empty:
        raise HTTPException(
            status_code=404,
            detail=f"Utensile '{body.alias}' non trovato a scaffale"
        )

    # Verifica che la posizione destinazione sia libera
    dest = df[
        (df["Posizione"].astype(str) == str(body.nuova_posizione_macchina)) &
        (df["Stato_Utensile"] == STATO_IN_MACCHINA)
    ]
    if not dest.empty:
        raise HTTPException(
            status_code=409,
            detail=f"Posizione {body.nuova_posizione_macchina} già occupata in macchina"
        )

    idx = riga.index[0]
    df.at[idx, "Stato_Utensile"] = STATO_IN_MACCHINA
    df.at[idx, "Posizione"] = str(body.nuova_posizione_macchina)

    ok, err = salva_database(df, paths["principale"])
    if not ok:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio: {err}")

    log.info(f"Spostato '{body.alias}' da scaffale → macchina pos {body.nuova_posizione_macchina}")
    return RispostaOk(
        ok=True,
        messaggio=f"{body.alias} spostato in macchina pos. {body.nuova_posizione_macchina}"
    )


@router.delete("/{alias_encoded}", response_model=RispostaOk, summary="Rimuovi utensile da scaffale")
async def rimuovi_da_scaffale(alias_encoded: str):
    """Rimuove completamente un utensile dallo scaffale."""
    from urllib.parse import unquote
    alias = unquote(alias_encoded)

    df, paths = get_db_principale()
    riga = df[
        (df["Alias"] == alias) &
        (df["Stato_Utensile"] == STATO_SCAFFALE)
    ]
    if riga.empty:
        raise HTTPException(status_code=404, detail=f"Utensile '{alias}' non trovato a scaffale")

    idx = riga.index[0]
    df = df.drop(idx).reset_index(drop=True)

    ok, err = salva_database(df, paths["principale"])
    if not ok:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio: {err}")

    log.info(f"Rimosso '{alias}' da scaffale")
    return RispostaOk(ok=True, messaggio=f"'{alias}' rimosso da scaffale")
