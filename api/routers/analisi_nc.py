"""
api/routers/analisi_nc.py
==========================
Endpoint per l'Analisi file NC e generazione MAIN O9999.

POST /api/analisi-nc/analizza           → analizza file NC caricati (upload)
GET  /api/analisi-nc/info-alias         → parse alias CNC: utensile + holder + bussola
POST /api/analisi-nc/aggiungi-a-scaffale → aggiunge utensile mancante a scaffale
GET  /api/analisi-nc/calibra-mode       → modalità CALIBRA ONLY attiva
PUT  /api/analisi-nc/calibra-mode       → cambia modalità CALIBRA ONLY
"""

import os
import tempfile
import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from pydantic import BaseModel
from typing import Optional

from api.deps import get_db_principale, get_db_smontati, get_db_bussole
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

# ── Modelli per info-alias e aggiungi-a-scaffale ───────────

class HolderDisponibile(BaseModel):
    alias_holder: str
    quantita: int
    tipo_desc: str          # es. "Caletto BILZ"

class BussolaDisponibile(BaseModel):
    codice_bussola: str
    diametro: str
    quantita: int

class InfoAliasResponse(BaseModel):
    alias: str
    utensile_base: str
    holder_cod: Optional[str]
    bussola_cod: Optional[str]
    ha_holder: bool
    holders_disponibili: list[HolderDisponibile]
    bussole_disponibili: list[BussolaDisponibile]

class AggiungiAScaffaleRequest(BaseModel):
    alias: str                          # alias completo dal file NC
    holder_override: Optional[str] = None  # solo se alias NON ha già holder

class AggiungiAScaffaleResponse(BaseModel):
    ok: bool
    alias_finale: str
    utensile_base: str
    holder_usato: Optional[str]
    bussola_usata: Optional[str]
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


# ── Info alias e aggiungi a scaffale ───────────────────────

@router.get("/info-alias", response_model=InfoAliasResponse, summary="Parsing alias CNC")
async def info_alias(alias: str = Query(..., description="Alias CNC completo, es. FS12R0.5L50F60A1")):
    """
    Analizza un alias CNC e restituisce:
    - utensile base (senza holder)
    - holder code (es. A1, H4, E3)
    - bussola code (solo per holder idraulico E, es. D12)
    - lista holder e bussole disponibili in inventario
    """
    from database.db_handler import smonta_utensile as parse_alias
    from config.constants import HOLDER_TYPES

    alias_upper = alias.strip().upper()
    utensile_base, holder_cod, bussola_cod = parse_alias(alias_upper)

    # Carica inventario holder e bussole
    _, df_holder, _ = get_db_smontati()
    df_bussole, _ = get_db_bussole()

    holders_disp = []
    for _, row in df_holder.iterrows():
        ah = str(row["Alias_Holder"]).strip()
        qty = int(row.get("Quantita", 0))
        if qty > 0:
            # Descrizione tipo dall'alias (prima lettera)
            tipo_desc = HOLDER_TYPES.get(ah[0].upper(), "—") if ah else "—"
            holders_disp.append(HolderDisponibile(
                alias_holder=ah,
                quantita=qty,
                tipo_desc=tipo_desc,
            ))

    bussole_disp = []
    for _, row in df_bussole.iterrows():
        cb = str(row["Codice_Bussola"]).strip()
        qty = int(row.get("Quantita", 0))
        if qty > 0:
            bussole_disp.append(BussolaDisponibile(
                codice_bussola=cb,
                diametro=str(row.get("Diametro", "")),
                quantita=qty,
            ))

    return InfoAliasResponse(
        alias=alias_upper,
        utensile_base=utensile_base or alias_upper,
        holder_cod=holder_cod,
        bussola_cod=bussola_cod,
        ha_holder=holder_cod is not None,
        holders_disponibili=holders_disp,
        bussole_disponibili=bussole_disp,
    )


@router.post("/aggiungi-a-scaffale", response_model=AggiungiAScaffaleResponse,
             summary="Aggiunge utensile mancante a scaffale")
async def aggiungi_a_scaffale(body: AggiungiAScaffaleRequest):
    """
    Aggiunge un utensile mancante (rilevato dall'analisi NC) al database come SCAFFALE.

    Flusso:
    1. Se l'alias contiene già un holder (es. FS12R0.5L50F60A1 → holder A1):
       - usa l'holder integrato
       - decrementa A1 dall'inventario holder smontati
    2. Se l'alias NON ha holder:
       - usa holder_override (obbligatorio)
       - costruisce alias_finale = alias + holder_override
       - decrementa holder dall'inventario
    3. Se è presente una bussola idraulico (es. E3), decrementa anche quella
    4. Aggiunge alias_finale al DB principale con Stato_Utensile=SCAFFALE
    """
    from database.db_handler import (
        smonta_utensile as parse_alias,
        salva_database,
        salva_database_holder_smontati,
        salva_database_bussole_idraulico,
        STATO_SCAFFALE,
    )

    alias_upper = body.alias.strip().upper()
    utensile_base, holder_cod, bussola_cod = parse_alias(alias_upper)

    # Determina alias_finale e holder da usare
    if holder_cod:
        alias_finale = alias_upper
    else:
        if not body.holder_override:
            raise HTTPException(
                status_code=422,
                detail="L'alias non contiene un holder e 'holder_override' non è stato fornito."
            )
        holder_cod = body.holder_override.strip().upper()
        alias_finale = f"{alias_upper}{holder_cod}"
        utensile_base = alias_upper

    # Carica DB principale + inventari
    df_principale, paths = get_db_principale()
    _, df_holder, _ = get_db_smontati()
    df_bussole, _ = get_db_bussole()

    # Decrementa holder dall'inventario (se disponibile)
    holder_decrementato = False
    if holder_cod and not df_holder.empty:
        df_holder["Alias_Holder"] = df_holder["Alias_Holder"].astype(str).str.strip()
        mask = df_holder["Alias_Holder"] == holder_cod
        if mask.any():
            idx_h = df_holder[mask].index[0]
            qty = int(df_holder.at[idx_h, "Quantita"])
            if qty > 1:
                df_holder.at[idx_h, "Quantita"] = qty - 1
            else:
                df_holder = df_holder.drop(idx_h).reset_index(drop=True)
            salva_database_holder_smontati(df_holder, paths["holder_smontati"])
            holder_decrementato = True
            log.info(f"Holder {holder_cod} decrementato (aggiungi-a-scaffale)")

    # Decrementa bussola (se presente e disponibile)
    bussola_decrementata = False
    if bussola_cod and not df_bussole.empty:
        df_bussole["Codice_Bussola"] = df_bussole["Codice_Bussola"].astype(str).str.strip()
        mask_b = df_bussole["Codice_Bussola"] == bussola_cod
        if mask_b.any():
            idx_b = df_bussole[mask_b].index[0]
            qty_b = int(df_bussole.at[idx_b, "Quantita"])
            if qty_b > 1:
                df_bussole.at[idx_b, "Quantita"] = qty_b - 1
            else:
                df_bussole = df_bussole.drop(idx_b).reset_index(drop=True)
            salva_database_bussole_idraulico(df_bussole, paths["bussole_idraulico"])
            bussola_decrementata = True
            log.info(f"Bussola {bussola_cod} decrementata (aggiungi-a-scaffale)")

    # Aggiunge al DB principale come SCAFFALE
    new_row = pd.DataFrame([{
        "Posizione": "",
        "Alias": alias_finale,
        "Stato_Utensile": STATO_SCAFFALE,
    }])
    df_principale = pd.concat([df_principale, new_row], ignore_index=True)

    ok, err = salva_database(df_principale, paths["principale"])
    if not ok:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio DB: {err}")

    # Costruisce messaggio riepilogo
    parti = [f"'{alias_finale}' aggiunto a scaffale"]
    if holder_decrementato:
        parti.append(f"Holder {holder_cod} −1 dall'inventario")
    elif holder_cod:
        parti.append(f"Holder {holder_cod} non in inventario — aggiunto comunque")
    if bussola_decrementata:
        parti.append(f"Bussola {bussola_cod} −1 dall'inventario")

    log.info(f"Aggiunto a scaffale: {alias_finale}")
    return AggiungiAScaffaleResponse(
        ok=True,
        alias_finale=alias_finale,
        utensile_base=utensile_base or alias_upper,
        holder_usato=holder_cod,
        bussola_usata=bussola_cod,
        messaggio=" · ".join(parti),
    )
