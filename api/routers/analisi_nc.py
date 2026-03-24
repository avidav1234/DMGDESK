"""
api/routers/analisi_nc.py
==========================
Endpoint per l'Analisi file NC e generazione MAIN O9999.

POST /api/analisi-nc/analizza           → analizza file NC caricati (upload)
GET  /api/analisi-nc/info-alias         → parse alias CNC: utensile + holder + bussola
POST /api/analisi-nc/aggiungi-a-scaffale → aggiunge utensile mancante a scaffale
GET  /api/analisi-nc/calibra-mode       → modalità CALIBRA ONLY attiva
PUT  /api/analisi-nc/calibra-mode       → cambia modalità CALIBRA ONLY
POST /api/analisi-nc/genera-main        → genera e scarica il file MAIN .MPF
POST /api/analisi-nc/anteprima-main     → restituisce preview testuale del MAIN
"""

import io
import os
import json as _json
import pathlib
import tempfile
from datetime import datetime
from typing import List, Optional

import pandas as pd
from fastapi import APIRouter, HTTPException, UploadFile, File, Query
from fastapi.responses import Response
from pydantic import BaseModel

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
        utensili_raw = estrai_tutti_utensili_da_file(tmp_path)
        richiesti_upper = {a.upper().strip() for a, _, _ in utensili_raw}

        utensili_nc = [
            UtensileNC(alias=alias, riga=riga_num, testo_riga=testo)
            for alias, riga_num, testo in utensili_raw
        ]

        # ── Confronto con tools_machine.json (TOA/MPF sync) ──────────────
        from pathlib import Path as _Path
        from api.routers.tools import _load_tools_db, _get_tools_db_path
        tools_db, sync_time, fmt_used = _load_tools_db()

        presenti     = []
        mancanti     = []
        disabilitati = []
        fonte_db     = ""

        if tools_db:
            alias_in_macchina = {t["name"].upper() for t in tools_db.values() if t.get("name")}
            alias_abilitati   = {
                t["name"].upper() for t in tools_db.values()
                if t.get("name") and t.get("is_enabled", True) and not t.get("is_worn", False)
            }
            mancanti     = sorted(richiesti_upper - alias_in_macchina)
            disabilitati = sorted(richiesti_upper & (alias_in_macchina - alias_abilitati))
            presenti     = sorted(richiesti_upper - set(mancanti) - set(disabilitati))
            dt_str = ""
            if sync_time:
                try:
                    from datetime import datetime
                    dt_str = datetime.fromisoformat(sync_time).strftime("%d/%m %H:%M")
                except Exception:
                    dt_str = sync_time[:16]
            fonte_db = f"tools_machine.json ({(fmt_used or 'TOA/MPF').upper()} — {dt_str})"
        else:
            # Fallback al database CSV
            df, _ = get_db_principale()
            if not df.empty:
                alias_macchina = set(df[df["Stato_Utensile"] == "IN_MACCHINA"]["Alias"].str.upper())
                mancanti = sorted(richiesti_upper - alias_macchina)
                presenti = sorted(richiesti_upper & alias_macchina)
                fonte_db = "database CSV principale (sync TOA non disponibile)"
            else:
                mancanti = sorted(richiesti_upper)
                fonte_db = "nessun DB disponibile — eseguire Sync in Macchina"

        n_mancanti = len(mancanti) + len(disabilitati)
        log.info(f"Analisi NC: {file.filename} — {len(utensili_nc)} utensili, "
                 f"{len(mancanti)} mancanti, {len(disabilitati)} disabilitati — fonte: {fonte_db}")

        return RisultatoAnalisi(
            utensili_nel_file=utensili_nc,
            presenti_in_macchina=presenti,
            mancanti=mancanti,
            disabilitati=disabilitati,
            totale_file=len(utensili_nc),
            totale_mancanti=n_mancanti,
            fonte_db=fonte_db,
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


# ── Genera MAIN ────────────────────────────────────────────

class ProgrammaNC(BaseModel):
    nome_file: str                   # es. "4297_007_03_001.mpf"
    utensile_principale: str         # primo alias trovato nel file (per commento)
    num_cambi: int = 1               # numero cambi utensile nel programma

class GeneraMainRequest(BaseModel):
    nome_cartella: str               # es. "TEST"
    programmi: List[ProgrammaNC]     # programmi selezionati dall'operatore

class SalvaMainRequest(BaseModel):
    nome_cartella: str               # es. "TEST"
    percorso_cartella: str           # es. "C:/Tool_App/TEST" — cartella dove scrivere
    programmi: List[ProgrammaNC]

class SalvaMainResponse(BaseModel):
    ok: bool
    percorso_file: str               # percorso completo del file scritto
    nome_file: str
    messaggio: str

class AnteprimeMainResponse(BaseModel):
    contenuto: str                   # testo del file MAIN
    nome_file: str                   # es. "0_MAIN_TEST.MPF"


def _build_main_content(nome_cartella: str, programmi: List[ProgrammaNC]) -> str:
    """
    Genera il contenuto testuale del file MAIN secondo il formato V14.
    Esempio di output atteso: vedi 0_MAIN_TEST.MPF allegato.
    """
    cartella_upper = nome_cartella.strip().upper()
    lines = []

    # ── Header ──────────────────────────────────────────────
    lines.append(f"; Main Program V14 - CALIBRA ONLY Configurabile")
    lines.append(f"; Progetto: {cartella_upper}")
    lines.append(f"; CALIBRA ONLY: \u274c Nessun CALIBRA ONLY")
    lines.append(f";--------------------------------------------------")
    # La riga EXTCALL del MAIN stesso è commentata (come nel file esempio)
    nome_main = f"0_MAIN_{cartella_upper}"
    lines.append(f";EXTCALL (\"/_N_WKS_DIR/_N_{cartella_upper}_WPD/_N_{nome_main}_MPF\")")
    lines.append("")
    lines.append("")

    # ── Un blocco per ogni programma ────────────────────────
    for i, pgm in enumerate(programmi, start=1):
        nome_base = pgm.nome_file.upper().replace(".", "_")
        # rimuove eventuale estensione se già inclusa nel nome_base
        if nome_base.endswith("_MPF"):
            nome_path = nome_base
        else:
            nome_path = nome_base + "_MPF"

        lines.append(f"; ===== FILE {i}: {pgm.nome_file} =====")
        lines.append(f"; Utensili: {pgm.num_cambi} cambi")
        lines.append("")
        lines.append(f"; Utensile principale: {pgm.utensile_principale}")
        lines.append(f"EXTCALL (\"/_N_WKS_DIR/_N_{cartella_upper}_WPD/_N_{nome_path}\")")
        lines.append("IF _B_ERRNO <> 0 GOTOF FINE")
        lines.append("STOPRE")
        lines.append("")

    # ── Statistiche ─────────────────────────────────────────
    lines.append("; ===== STATISTICHE V14 =====")
    lines.append(f"; TOTALE utensili processati: {len(programmi)}")
    lines.append(f"; CALIBRA ONLY inseriti: 0")
    lines.append(f"; Modalità: \u274c Nessun CALIBRA ONLY")
    lines.append("; ============================")
    lines.append("")
    lines.append("FINE:")
    lines.append("M67")
    lines.append("M30")
    lines.append("")

    return "\n".join(lines)


@router.post(
    "/anteprima-main",
    response_model=AnteprimeMainResponse,
    summary="Anteprima testuale del file MAIN",
)
async def anteprima_main(body: GeneraMainRequest):
    """
    Restituisce il contenuto testuale del MAIN senza scaricarlo.
    Utile per mostrare un'anteprima all'operatore prima di confermare.
    """
    if not body.nome_cartella.strip():
        raise HTTPException(status_code=422, detail="nome_cartella non può essere vuoto")
    if not body.programmi:
        raise HTTPException(status_code=422, detail="Seleziona almeno un programma")

    cartella_upper = body.nome_cartella.strip().upper()
    contenuto = _build_main_content(cartella_upper, body.programmi)
    nome_file = f"0_MAIN_{cartella_upper}.MPF"

    log.info(f"Anteprima MAIN: {nome_file} ({len(body.programmi)} programmi)")
    return AnteprimeMainResponse(contenuto=contenuto, nome_file=nome_file)


@router.post(
    "/genera-main",
    summary="Genera e scarica il file MAIN .MPF",
    response_class=Response,
    responses={
        200: {
            "content": {"application/octet-stream": {}},
            "description": "File .MPF scaricabile",
        }
    },
)
async def genera_main(body: GeneraMainRequest):
    """
    Genera il file MAIN O9999 secondo il formato V14 e lo restituisce
    come file da scaricare (.MPF).

    Il nome del file scaricato sarà: 0_MAIN_{NOME_CARTELLA}.MPF
    """
    if not body.nome_cartella.strip():
        raise HTTPException(status_code=422, detail="nome_cartella non può essere vuoto")
    if not body.programmi:
        raise HTTPException(status_code=422, detail="Seleziona almeno un programma")

    cartella_upper = body.nome_cartella.strip().upper()
    contenuto = _build_main_content(cartella_upper, body.programmi)
    nome_file = f"0_MAIN_{cartella_upper}.MPF"

    log.info(f"MAIN generato: {nome_file} ({len(body.programmi)} programmi)")

    return Response(
        content=contenuto.encode("utf-8"),
        media_type="application/octet-stream",
        headers={"Content-Disposition": f'attachment; filename="{nome_file}"'},
    )


@router.post(
    "/salva-main",
    response_model=SalvaMainResponse,
    summary="Genera e salva il MAIN direttamente sul disco del server",
)
async def salva_main(body: SalvaMainRequest):
    """
    Genera il file MAIN e lo scrive direttamente nella cartella indicata
    dall'operatore (percorso sul filesystem del server/PC locale).
    
    Usato quando il browser non supporta File System Access API o
    quando l'app gira in rete locale — il backend scrive direttamente
    nella cartella sorgente dei programmi NC.
    """
    if not body.nome_cartella.strip():
        raise HTTPException(status_code=422, detail="nome_cartella non può essere vuoto")
    if not body.percorso_cartella.strip():
        raise HTTPException(status_code=422, detail="percorso_cartella non può essere vuoto")
    if not body.programmi:
        raise HTTPException(status_code=422, detail="Seleziona almeno un programma")

    cartella_upper = body.nome_cartella.strip().upper()
    contenuto = _build_main_content(cartella_upper, body.programmi)
    nome_file = f"0_MAIN_{cartella_upper}.MPF"

    # Normalizza il percorso — NON usare .resolve() su percorsi UNC (\\server\share)
    # perché su Linux/server potrebbe alterare il path. Usiamo il percorso così com'è.
    try:
        percorso_raw = body.percorso_cartella.strip()
        # Normalizza separatori ma preserva il prefisso UNC \\
        dest_dir = pathlib.PureWindowsPath(percorso_raw)
        # Per le operazioni reali sul filesystem usiamo Path diretto
        dest_dir = pathlib.Path(percorso_raw)
    except Exception as e:
        raise HTTPException(status_code=422, detail=f"Percorso non valido: {e}")

    if not dest_dir.exists():
        raise HTTPException(
            status_code=422,
            detail=f"Cartella non trovata: {dest_dir}. Verifica il percorso."
        )
    if not dest_dir.is_dir():
        raise HTTPException(status_code=422, detail=f"Il percorso non è una cartella: {dest_dir}")

    percorso_file = dest_dir / nome_file
    try:
        percorso_file.write_text(contenuto, encoding="utf-8")
    except PermissionError:
        raise HTTPException(
            status_code=403,
            detail=f"Permesso negato: impossibile scrivere in {dest_dir}"
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore scrittura file: {e}")

    _save_recente(str(dest_dir))
    log.info(f"MAIN salvato su disco: {percorso_file} ({len(body.programmi)} programmi)")
    return SalvaMainResponse(
        ok=True,
        percorso_file=str(percorso_file),
        nome_file=nome_file,
        messaggio=f"File salvato in: {percorso_file}",
    )


# ── Cartelle recenti + sfoglia filesystem ──────────────────

_RECENTI_FILE = pathlib.Path("cartelle_recenti.json")
_MAX_RECENTI  = 8

def _load_recenti() -> list:
    try:
        return _json.loads(_RECENTI_FILE.read_text(encoding="utf-8"))
    except Exception:
        return []

def _save_recente(percorso: str):
    try:
        items = _load_recenti()
        percorso = str(pathlib.Path(percorso).resolve())
        if percorso in items:
            items.remove(percorso)
        items.insert(0, percorso)
        _RECENTI_FILE.write_text(
            _json.dumps(items[:_MAX_RECENTI], ensure_ascii=False, indent=2),
            encoding="utf-8"
        )
    except Exception:
        pass


class CartelleBrowseResponse(BaseModel):
    percorso: str


@router.get(
    "/cartelle-recenti",
    summary="Lista cartelle usate di recente per il MAIN",
)
async def cartelle_recenti():
    """Restituisce le ultime cartelle usate per salvare il MAIN."""
    return {"cartelle": _load_recenti()}


@router.get(
    "/sfoglia-cartella",
    response_model=CartelleBrowseResponse,
    summary="Apre dialog nativa Windows per scegliere cartella",
)
async def sfoglia_cartella():
    """
    Apre tkinter.filedialog.askdirectory() sul server (stesso PC).
    Restituisce il percorso scelto dall'operatore.
    Funziona solo quando backend e schermo sono sullo stesso PC.
    """
    try:
        import tkinter as tk
        from tkinter import filedialog
        root = tk.Tk()
        root.withdraw()
        root.attributes('-topmost', True)
        percorso = filedialog.askdirectory(
            title="Seleziona la cartella dei programmi NC",
            parent=root,
        )
        root.destroy()
        if not percorso:
            raise HTTPException(status_code=204, detail="Nessuna cartella selezionata")
        return CartelleBrowseResponse(percorso=str(pathlib.Path(percorso)))
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore dialog: {e}")
