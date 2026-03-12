"""
api/routers/smontati.py
========================
Endpoint per l'archivio utensili SMONTATI.

GET    /api/smontati/            → lista utensili smontati
POST   /api/smontati/            → aggiungi utensile smontato
PATCH  /api/smontati/{id}        → modifica note/alias
DELETE /api/smontati/{id}        → elimina record
POST   /api/smontati/{id}/monta  → assembla con holder → DB principale
"""

import pandas as pd
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

from api.deps import get_db_principale, get_db_smontati, get_db_bussole
from database.db_handler import (
    aggiungi_utensile_smontato,
    modifica_utensile_smontato,
    elimina_utensile_smontato,
    salva_database,
    salva_database_utensili_smontati,
    salva_database_holder_smontati,
    salva_database_bussole_idraulico,
    STATO_IN_MACCHINA,
    STATO_SCAFFALE,
)
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()


# ── Modelli ────────────────────────────────────────────────

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


class MontaRequest(BaseModel):
    alias_holder: str           # es. "A1", "H4", "E" (base idraulico), "E3" (idraulico con bussola)
    codice_bussola: Optional[str] = None  # es. "E3" — obbligatorio solo se alias_holder == "E"
    destinazione: str           # "macchina" o "scaffale"
    posizione: Optional[str] = None       # es. "42" — obbligatoria se destinazione == "macchina"


class MontaResponse(BaseModel):
    ok: bool
    alias_finale: str
    destinazione: str
    posizione: Optional[str]
    holder_usato: str
    bussola_usata: Optional[str]
    messaggio: str


class RispostaOk(BaseModel):
    ok: bool
    messaggio: str


# ── Endpoint CRUD ──────────────────────────────────────────

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
    ok, msg = aggiungi_utensile_smontato(
        df, paths["utensili_smontati"], body.alias_utensile, body.provenienza, body.note
    )
    if not ok:
        raise HTTPException(status_code=400, detail=msg)
    log.info(f"Aggiunto smontato: {body.alias_utensile}")
    return RispostaOk(ok=True, messaggio=msg)


@router.patch("/{id_utensile}", response_model=RispostaOk, summary="Modifica utensile smontato")
async def modifica_smontato(id_utensile: str, body: ModificaRequest):
    df, _, paths = get_db_smontati()
    ok, msg = modifica_utensile_smontato(
        df, paths["utensili_smontati"], id_utensile,
        body.nuovo_alias, body.nuova_provenienza, body.nuove_note
    )
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


# ── Endpoint MONTA ─────────────────────────────────────────

@router.post("/{id_utensile}/monta", response_model=MontaResponse,
             summary="Monta utensile: assembla con holder e inserisce nel DB principale")
async def monta_utensile(id_utensile: str, body: MontaRequest):
    """
    Workflow completo di montaggio da smontati → DB principale:

    1. Trova l'utensile in smontati per ID
    2. Costruisce alias_finale:
       - holder "E" (base idraulico) + bussola (es. "E3") → utensile + "E3"
       - qualsiasi altro holder (es. "H4")               → utensile + "H4"
    3. Decrementa holder dall'inventario holder_smontati
    4. Decrementa bussola dall'inventario bussole_idraulico (solo per "E")
    5. Aggiunge alias_finale al DB principale (stato: IN_MACCHINA o SCAFFALE)
    6. Rimuove l'utensile dal DB smontati
    """
    # ── Validazione input ──────────────────────────────────
    if body.destinazione not in ("macchina", "scaffale"):
        raise HTTPException(status_code=422,
                            detail="destinazione deve essere 'macchina' o 'scaffale'")

    if body.destinazione == "macchina":
        if not body.posizione or not str(body.posizione).strip().isdigit():
            raise HTTPException(status_code=422,
                                detail="posizione numerica obbligatoria per destinazione 'macchina'")

    holder_base = body.alias_holder.strip().upper()

    # Holder "E" senza numero = idraulico base → serve bussola
    if holder_base == "E" and not body.codice_bussola:
        raise HTTPException(status_code=422,
                            detail="codice_bussola obbligatorio per holder idraulico 'E'")

    # ── Carica DB ─────────────────────────────────────────
    df_principale, paths = get_db_principale()
    df_ut, df_holder, _ = get_db_smontati()
    df_bussole, _ = get_db_bussole()

    # ── 1. Trova utensile ─────────────────────────────────
    try:
        id_int = int(id_utensile)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"ID non valido: {id_utensile}")

    riga = df_ut[df_ut["ID"] == id_int]
    if riga.empty:
        raise HTTPException(status_code=404,
                            detail=f"Utensile smontato ID {id_int} non trovato")

    alias_utensile = str(riga.iloc[0]["Alias_Utensile"]).strip().upper()

    # ── 2. Costruisce alias_finale ────────────────────────
    bussola_usata = None
    if holder_base == "E":
        # Idraulico base: il suffisso nell'alias è il codice bussola (es. E3)
        bussola_usata = body.codice_bussola.strip().upper()
        alias_finale = f"{alias_utensile}{bussola_usata}"
    else:
        alias_finale = f"{alias_utensile}{holder_base}"

    # ── 3. Decrementa holder ──────────────────────────────
    holder_decrementato = False
    if not df_holder.empty:
        df_holder["Alias_Holder"] = df_holder["Alias_Holder"].astype(str).str.strip()
        mask_h = df_holder["Alias_Holder"] == holder_base
        if mask_h.any():
            idx_h = df_holder[mask_h].index[0]
            qty_h = int(df_holder.at[idx_h, "Quantita"])
            if qty_h < 1:
                raise HTTPException(status_code=409,
                                    detail=f"Holder '{holder_base}' esaurito (qty=0)")
            if qty_h - 1 <= 0:
                df_holder = df_holder.drop(idx_h).reset_index(drop=True)
            else:
                df_holder.at[idx_h, "Quantita"] = qty_h - 1
            salva_database_holder_smontati(df_holder, paths["holder_smontati"])
            holder_decrementato = True
        else:
            # Holder non in inventario — avviso ma non blocca
            log.warning(f"Holder '{holder_base}' non trovato in inventario — montaggio proseguito")

    # ── 4. Decrementa bussola ─────────────────────────────
    bussola_decrementata = False
    if bussola_usata and not df_bussole.empty:
        df_bussole["Codice_Bussola"] = df_bussole["Codice_Bussola"].astype(str).str.strip()
        mask_b = df_bussole["Codice_Bussola"] == bussola_usata
        if mask_b.any():
            idx_b = df_bussole[mask_b].index[0]
            qty_b = int(df_bussole.at[idx_b, "Quantita"])
            if qty_b < 1:
                raise HTTPException(status_code=409,
                                    detail=f"Bussola '{bussola_usata}' esaurita (qty=0)")
            if qty_b - 1 <= 0:
                df_bussole = df_bussole.drop(idx_b).reset_index(drop=True)
            else:
                df_bussole.at[idx_b, "Quantita"] = qty_b - 1
            salva_database_bussole_idraulico(df_bussole, paths["bussole_idraulico"])
            bussola_decrementata = True
        else:
            log.warning(f"Bussola '{bussola_usata}' non trovata in inventario — montaggio proseguito")

    # ── 5. Aggiunge al DB principale ──────────────────────
    if body.destinazione == "macchina":
        stato = STATO_IN_MACCHINA
        posizione = str(body.posizione).strip()
    else:
        stato = STATO_SCAFFALE
        posizione = ""

    new_row = pd.DataFrame([{
        "Posizione": posizione,
        "Alias": alias_finale,
        "Stato_Utensile": stato,
    }])
    df_principale = pd.concat([df_principale, new_row], ignore_index=True)
    ok_p, err_p = salva_database(df_principale, paths["principale"])
    if not ok_p:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio DB principale: {err_p}")

    # ── 6. Rimuove da smontati ────────────────────────────
    df_ut = df_ut[df_ut["ID"] != id_int].reset_index(drop=True)
    ok_s, err_s = salva_database_utensili_smontati(df_ut, paths["utensili_smontati"])
    if not ok_s:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio smontati: {err_s}")

    # ── Messaggio riepilogo ───────────────────────────────
    parti = [f"'{alias_finale}' montato"]
    dest_label = f"macchina pos. {posizione}" if stato == STATO_IN_MACCHINA else "scaffale"
    parti.append(f"Destinazione: {dest_label}")
    if holder_decrementato:
        parti.append(f"Holder {holder_base} −1")
    if bussola_decrementata:
        parti.append(f"Bussola {bussola_usata} −1")

    log.info(f"Montato: {alias_utensile} + {holder_base} → {alias_finale} [{stato}]")

    return MontaResponse(
        ok=True,
        alias_finale=alias_finale,
        destinazione=stato,
        posizione=posizione or None,
        holder_usato=holder_base,
        bussola_usata=bussola_usata,
        messaggio=" · ".join(parti),
    )
