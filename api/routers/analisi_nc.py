"""
api/routers/analisi_nc.py
==========================
Endpoint per l'Analisi file NC e generazione MAIN O9999.

POST /api/analisi-nc/analizza      → analizza file NC caricati (upload)
POST /api/analisi-nc/genera-main   → genera MAIN O9999 (upload file NC)
GET  /api/analisi-nc/calibra-mode  → modalità CALIBRA ONLY attiva
PUT  /api/analisi-nc/calibra-mode  → cambia modalità CALIBRA ONLY
"""

import os
import tempfile
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

from api.deps import get_db_principale
from logic.nc_analyzer import estrai_tutti_utensili_da_file, confronta_utensili_logica
from logic.calibra_only_logic import get_calibra_logic
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


# ── Modelli ────────────────────────────────────────────────

class UtensileNC(BaseModel):
    alias: str
    riga: int
    testo_riga: str

class RisultatoAnalisi(BaseModel):
    utensili_nel_file: list[UtensileNC]
    presenti_in_macchina: list[str]
    mancanti: list[str]
    totale_file: int
    totale_mancanti: int

class CalibraMode(BaseModel):
    mode: str
    x_finitura: int
    x_qualsiasi: int
    descrizione: str

class SetCalibraMode(BaseModel):
    mode: str
    x_finitura: int = 3
    x_qualsiasi: int = 3

class RispostaOk(BaseModel):
    ok: bool
    messaggio: str


# ── Endpoint ───────────────────────────────────────────────

@router.post("/analizza", response_model=RisultatoAnalisi, summary="Analizza file NC")
async def analizza_file_nc(file: UploadFile = File(..., description="File NC (.MPF, .NC, .SPF)")):
    """
    Carica un file NC e confronta gli utensili richiesti con il database macchina.
    Restituisce la lista completa con presenti e mancanti.
    """
    # Salva il file caricato in una cartella temporanea
    suffix = os.path.splitext(file.filename)[1] or ".mpf"
    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
        content = await file.read()
        tmp.write(content)
        tmp_path = tmp.name

    try:
        df, _ = get_db_principale()
        utensili_raw = estrai_tutti_utensili_da_file(tmp_path)
        richiesti_set, mancanti_report = confronta_utensili_logica(df, [tmp_path])

        # Alias presenti nel database macchina (IN_MACCHINA)
        alias_macchina = set(df[df["Stato_Utensile"] == "IN_MACCHINA"]["Alias"].str.upper())
        richiesti_upper = {a.upper() for a in richiesti_set}

        presenti = sorted(richiesti_upper & alias_macchina)
        mancanti = sorted(richiesti_upper - alias_macchina)

        utensili_nc = [
            UtensileNC(alias=alias, riga=riga_num, testo_riga=testo)
            for alias, riga_num, testo in utensili_raw
        ]

        log.info(f"Analisi NC: {file.filename} — {len(utensili_nc)} utensili, {len(mancanti)} mancanti")

        return RisultatoAnalisi(
            utensili_nel_file=utensili_nc,
            presenti_in_macchina=presenti,
            mancanti=mancanti,
            totale_file=len(utensili_nc),
            totale_mancanti=len(mancanti),
        )

    finally:
        os.unlink(tmp_path)


@router.get("/calibra-mode", response_model=CalibraMode, summary="Modalità CALIBRA ONLY attiva")
async def get_calibra_mode():
    """Restituisce la configurazione attuale del sistema CALIBRA ONLY."""
    logic = get_calibra_logic()
    settings = logic._load_settings()
    return CalibraMode(
        mode=settings.get("mode", "mai"),
        x_finitura=settings.get("x_finitura", 3),
        x_qualsiasi=settings.get("x_qualsiasi", 3),
        descrizione=logic.get_mode_description(),
    )


@router.put("/calibra-mode", response_model=RispostaOk, summary="Cambia modalità CALIBRA ONLY")
async def set_calibra_mode(body: SetCalibraMode):
    """
    Aggiorna la modalità CALIBRA ONLY.
    Valori validi per mode: mai | inizio | finitura_unico | finitura_x | ogni_x
    """
    modi_validi = {"mai", "inizio", "finitura_unico", "finitura_x", "ogni_x"}
    if body.mode not in modi_validi:
        raise HTTPException(
            status_code=422,
            detail=f"Modalità non valida. Valori accettati: {', '.join(sorted(modi_validi))}"
        )

    import json
    settings_file = "calibra_only_settings.json"
    settings = {
        "mode": body.mode,
        "x_finitura": body.x_finitura,
        "x_qualsiasi": body.x_qualsiasi,
    }
    try:
        with open(settings_file, "w", encoding="utf-8") as f:
            json.dump(settings, f, indent=2)
        log.info(f"CALIBRA ONLY impostato: {body.mode}")
        return RispostaOk(ok=True, messaggio=f"Modalità aggiornata: {body.mode}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
