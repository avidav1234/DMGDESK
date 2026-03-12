"""
api/routers/scaffale.py
========================
Endpoint per gli utensili sullo SCAFFALE (assemblati, non in macchina).

GET  /api/scaffale/      → lista utensili a scaffale
POST /api/scaffale/sposta → sposta da scaffale a macchina (cambia stato)
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from api.deps import get_db_principale
from database.db_handler import STATO_SCAFFALE, STATO_IN_MACCHINA, salva_database
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


class UtensileScaffale(BaseModel):
    posizione: int
    alias: str
    stato: str


class SpostaRequest(BaseModel):
    posizione: int
    nuova_posizione_macchina: int


class RispostaOk(BaseModel):
    ok: bool
    messaggio: str


@router.get("/", response_model=list[UtensileScaffale], summary="Lista utensili a scaffale")
async def lista_scaffale():
    """Restituisce tutti gli utensili assemblati presenti sullo scaffale."""
    df, _ = get_db_principale()
    df_scaffale = df[df["Stato_Utensile"] == STATO_SCAFFALE].sort_values("Posizione")

    return [
        UtensileScaffale(
            posizione=int(row["Posizione"]),
            alias=str(row["Alias"]),
            stato=str(row["Stato_Utensile"]),
        )
        for _, row in df_scaffale.iterrows()
    ]


@router.post("/sposta-in-macchina", response_model=RispostaOk, summary="Sposta da scaffale a macchina")
async def sposta_in_macchina(body: SpostaRequest):
    """
    Sposta un utensile dallo scaffale alla posizione specificata nel carosello.
    """
    df, paths = get_db_principale()

    riga = df[df["Posizione"] == body.posizione]
    if riga.empty or riga.iloc[0]["Stato_Utensile"] != STATO_SCAFFALE:
        raise HTTPException(status_code=404, detail=f"Utensile non trovato a scaffale (pos {body.posizione})")

    # Controlla che la posizione destinazione sia libera
    dest = df[
        (df["Posizione"] == body.nuova_posizione_macchina) &
        (df["Stato_Utensile"] == STATO_IN_MACCHINA)
    ]
    if not dest.empty:
        raise HTTPException(status_code=409, detail=f"Posizione {body.nuova_posizione_macchina} già occupata in macchina")

    alias = str(riga.iloc[0]["Alias"])

    # Aggiorna stato e posizione
    idx = df[df["Posizione"] == body.posizione].index[0]
    df.at[idx, "Stato_Utensile"] = STATO_IN_MACCHINA
    df.at[idx, "Posizione"] = body.nuova_posizione_macchina

    ok, err = salva_database(df, paths["principale"])
    if not ok:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio: {err}")

    log.info(f"Spostato {alias} da scaffale → macchina pos {body.nuova_posizione_macchina}")
    return RispostaOk(ok=True, messaggio=f"{alias} spostato in macchina posizione {body.nuova_posizione_macchina}")
