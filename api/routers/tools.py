"""
api/routers/tools.py
======================
Endpoint per la gestione tabella utensili macchina.

POST /api/tools/sync          → legge TOA+TMA dalla share e aggiorna DB
GET  /api/tools               → lista utensili in DB
GET  /api/tools/check         → confronta utensili richiesti da un MPF vs DB macchina
GET  /api/tools/sync-status   → data/ora ultimo sync
"""

import os
import json
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from api.toa_parser import (
    parse_toa, parse_tma, check_tools_availability,
    extract_tools_from_mpf, MachineTool, MagazinePosition,
)
from database.db_handler import carica_configurazione, salva_configurazione
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Percorsi file TOA/TMA sulla share
# ---------------------------------------------------------------------------

def _get_sync_paths() -> tuple[Path, Path]:
    """
    Restituisce i path di TOOL_SYNC.TOA e TOOL_SYNC.TMA.
    Cerca la share in questo ordine:
    1. config["radice"]           — chiave dedicata se presente
    2. config["percorso_nc_base"] — risale al primo livello (P:\DMG_DMC_160U\4297 → P:\DMG_DMC_160U)
    """
    config = carica_configurazione()

    # 1. chiave dedicata
    radice = config.get("radice", "")

    # 2. risali da percorso_nc_base
    if not radice:
        percorso_nc = config.get("percorso_nc_base", "")
        if percorso_nc:
            parts = Path(percorso_nc).parts
            if len(parts) >= 2:
                radice = str(Path(parts[0]) / parts[1])

    if not radice:
        raise HTTPException(
            status_code=500,
            detail=(
                "Percorso share non configurato. "
                "Impostare il percorso NC base dalla pagina Analisi NC "
                "(es. P:\\\\DMG_DMC_160U\\\\4297)."
            )
        )

    base = Path(radice)
    return base / "TOOL_SYNC.TOA", base / "TOOL_SYNC.TMA"


def _get_tools_db_path() -> Path:
    """Percorso del DB utensili (JSON locale)."""
    config = carica_configurazione()
    db_path = config.get("database_path", ".")
    return Path(db_path).parent / "tools_machine.json"


# ---------------------------------------------------------------------------
# Modelli risposta
# ---------------------------------------------------------------------------

class ToolSummary(BaseModel):
    tool_id: int
    name: str
    duplo: int
    status: int
    length: float
    radius: float
    life_percent: Optional[float]
    is_enabled: bool
    is_worn: bool


class SyncStatus(BaseModel):
    last_sync: Optional[str]     # ISO datetime
    tool_count: int
    toa_path: str
    tma_path: str


class CheckResult(BaseModel):
    ok: list[str]
    missing: list[str]
    disabled: list[str]
    worn: list[str]
    total_required: int
    can_run: bool


# ---------------------------------------------------------------------------
# Helpers DB locale (JSON)
# ---------------------------------------------------------------------------

def _save_tools_db(tools: dict[int, MachineTool], sync_time: str) -> None:
    """Salva il DB utensili in JSON locale."""
    db_path = _get_tools_db_path()
    data = {
        "sync_time": sync_time,
        "tools": {
            str(tid): {
                "tool_id": t.tool_id,
                "name": t.name,
                "duplo": t.duplo,
                "status": t.status,
                "monitoring": t.monitoring,
                "length": t.main_length,
                "radius": t.main_radius,
                "life_percent": t.life_percent,
                "is_enabled": t.is_enabled,
                "is_worn": t.is_worn,
            }
            for tid, t in tools.items()
            if t.name  # salta T-number 0 o senza nome
        }
    }
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_tools_db() -> tuple[dict, str | None]:
    """Carica il DB utensili dal JSON locale. Restituisce (tools_dict, sync_time)."""
    db_path = _get_tools_db_path()
    if not db_path.exists():
        return {}, None
    with open(db_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tools", {}), data.get("sync_time")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/sync",
    summary="Sincronizza tabella utensili dalla share macchina",
)
async def sync_tools():
    """
    Legge TOOL_SYNC.TOA e TOOL_SYNC.TMA dalla share configurata
    (radice in config.json) e aggiorna il DB locale utensili.

    I file vanno generati dalla macchina con:
      HMI → Servizi → Salva Attrezzaggio → Z:\\DMG_DMC_160U\\TOOL_SYNC
    """
    toa_path, tma_path = _get_sync_paths()

    if not toa_path.exists():
        raise HTTPException(
            status_code=404,
            detail=(
                f"File TOA non trovato: {toa_path}. "
                "Sulla macchina: HMI → Servizi → Salva Attrezzaggio, "
                "salvare in Z:\\\\DMG_DMC_160U\\\\ con nome TOOL_SYNC"
            )
        )

    try:
        tools = parse_toa(toa_path)
        log.info(f"TOA letto: {len(tools)} utensili da {toa_path}")
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura TOA: {e}")

    # TMA opzionale — se presente aggiunge info posizioni
    magazines, positions = {}, []
    if tma_path.exists():
        try:
            magazines, positions = parse_tma(tma_path)
            log.info(f"TMA letto: {len(magazines)} magazine, {len(positions)} posizioni occupate")
        except Exception as e:
            log.warning(f"Errore lettura TMA (non bloccante): {e}")

    sync_time = datetime.now().isoformat()
    _save_tools_db(tools, sync_time)

    return {
        "ok": True,
        "sync_time": sync_time,
        "tool_count": sum(1 for t in tools.values() if t.name),
        "magazine_count": len(magazines),
        "positions_mapped": len(positions),
    }


@router.get(
    "/sync-status",
    response_model=SyncStatus,
    summary="Stato e data dell'ultimo sync",
)
async def sync_status():
    """Restituisce quando è stato fatto l'ultimo sync e quanti utensili ci sono nel DB."""
    toa_path, tma_path = _get_sync_paths()
    _, sync_time = _load_tools_db()
    tools_db, _ = _load_tools_db()

    return SyncStatus(
        last_sync=sync_time,
        tool_count=len(tools_db),
        toa_path=str(toa_path),
        tma_path=str(tma_path),
    )


@router.get(
    "",
    response_model=list[ToolSummary],
    summary="Lista utensili nel DB macchina",
)
async def list_tools(only_enabled: bool = False):
    """
    Restituisce tutti gli utensili nell'ultimo sync.
    Parametro opzionale: only_enabled=true per filtrare solo gli abilitati.
    """
    tools_db, sync_time = _load_tools_db()
    if not tools_db:
        return []

    result = []
    for t in tools_db.values():
        if only_enabled and not t.get("is_enabled", True):
            continue
        result.append(ToolSummary(
            tool_id=t["tool_id"],
            name=t["name"],
            duplo=t["duplo"],
            status=t["status"],
            length=t.get("length", 0.0),
            radius=t.get("radius", 0.0),
            life_percent=t.get("life_percent"),
            is_enabled=t.get("is_enabled", True),
            is_worn=t.get("is_worn", False),
        ))

    return sorted(result, key=lambda x: x.name)


@router.post(
    "/check",
    response_model=CheckResult,
    summary="Controlla utensili richiesti da un programma MPF vs DB macchina",
)
async def check_tools(file: UploadFile = File(...)):
    """
    Carica un file MPF e confronta gli utensili richiesti con il DB macchina.

    Restituisce:
    - ok: utensili presenti e disponibili
    - missing: utensili non trovati in macchina
    - disabled: utensili presenti ma disabilitati/esauriti
    - worn: utensili con vita residua < 10%
    - can_run: True se tutti gli utensili required sono ok
    """
    tools_db, sync_time = _load_tools_db()
    if not tools_db:
        raise HTTPException(
            status_code=409,
            detail="Nessun sync disponibile. Eseguire prima POST /api/tools/sync"
        )

    content = await file.read()
    try:
        mpf_text = content.decode("utf-8", errors="replace")
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Errore lettura file: {e}")

    # Estrai utensili richiesti dal programma
    required = extract_tools_from_mpf(mpf_text)
    if not required:
        return CheckResult(
            ok=[], missing=[], disabled=[], worn=[],
            total_required=0, can_run=True
        )

    # Ricostruisci MachineTool dal DB semplificato per il check
    # (il DB JSON ha già i campi che servono)
    from api.toa_parser import MachineTool as MT

    machine_tools = {}
    for tid_str, t in tools_db.items():
        mt = MT(tool_id=t["tool_id"])
        mt.name = t["name"]
        mt.duplo = t["duplo"]
        mt.status = t["status"]
        mt.monitoring = t.get("monitoring", 0)
        machine_tools[t["tool_id"]] = mt

    result = check_tools_availability(required, machine_tools)

    return CheckResult(
        ok=result["ok"],
        missing=result["missing"],
        disabled=result["disabled"],
        worn=result["worn"],
        total_required=len(required),
        can_run=len(result["missing"]) == 0 and len(result["disabled"]) == 0,
    )


@router.post(
    "/check-text",
    response_model=CheckResult,
    summary="Controlla utensili da testo MPF passato come stringa",
)
async def check_tools_text(body: dict):
    """
    Alternativa a /check che accetta il testo MPF come JSON.
    Body: {"mpf_content": "...testo programma..."}
    """
    tools_db, _ = _load_tools_db()
    if not tools_db:
        raise HTTPException(
            status_code=409,
            detail="Nessun sync disponibile. Eseguire prima POST /api/tools/sync"
        )

    mpf_text = body.get("mpf_content", "")
    required = extract_tools_from_mpf(mpf_text)

    if not required:
        return CheckResult(
            ok=[], missing=[], disabled=[], worn=[],
            total_required=0, can_run=True
        )

    from api.toa_parser import MachineTool as MT
    machine_tools = {}
    for tid_str, t in tools_db.items():
        mt = MT(tool_id=t["tool_id"])
        mt.name = t["name"]
        mt.duplo = t["duplo"]
        mt.status = t["status"]
        mt.monitoring = t.get("monitoring", 0)
        machine_tools[t["tool_id"]] = mt

    result = check_tools_availability(required, machine_tools)

    return CheckResult(
        ok=result["ok"],
        missing=result["missing"],
        disabled=result["disabled"],
        worn=result["worn"],
        total_required=len(required),
        can_run=len(result["missing"]) == 0 and len(result["disabled"]) == 0,
    )
