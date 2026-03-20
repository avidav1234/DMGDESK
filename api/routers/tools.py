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
import re
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, HTTPException, UploadFile, File
from pydantic import BaseModel

from api.toa_parser import parse_toa, parse_tma, MachineTool, MagazinePosition
from database.db_handler import carica_configurazione, salva_configurazione
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()

# ---------------------------------------------------------------------------
# Estrazione utensili da MPF — logica identica a logic/nc_analyzer.py
# usa pattern T="ALIAS" seguito da M6 nelle 5 righe successive
# ---------------------------------------------------------------------------

def _estrai_utensili_da_testo(testo: str) -> list[tuple[str, int, str]]:
    """
    Estrae alias utensili da testo MPF.
    Restituisce lista di (alias, riga_num, riga_testo).
    Identica a estrai_tutti_utensili_da_file in logic/nc_analyzer.py.
    """
    import re
    pattern = re.compile(r'T\\s*=\\s*[\\\"\\'']?([A-Z0-9.\\-_\\s]+)[\\\"\\'']?', re.IGNORECASE)
    righe = testo.splitlines()
    risultati = []
    last_alias = None
    last_idx = -1
    last_testo = ""

    for i, riga in enumerate(righe):
        riga_up = riga.strip().upper()
        m = pattern.search(riga_up)
        if m:
            alias = m.group(1).strip()
            if alias:
                last_alias = alias
                last_idx = i
                last_testo = riga.strip()
        if last_alias and (i - last_idx) < 5:
            if "M6" in riga_up.replace("M06", "M6"):
                risultati.append((last_alias.upper(), last_idx + 1, last_testo))
                last_alias = None
    return risultati



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
    magazine: Optional[int]   # numero magazine (1=Regal_120, 2=buffer, None=non mappato)
    position: Optional[int]   # posizione nel magazine


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

def _save_tools_db(tools: dict[int, MachineTool], sync_time: str, positions=None) -> None:
    """Salva il DB utensili in JSON locale, incluse posizioni magazzino."""
    db_path = _get_tools_db_path()

    # Mappa tool_id → posizione magazzino dal TMA
    pos_map: dict[int, dict] = {}
    if positions:
        for pos in positions:
            pos_map[pos.tool_id] = {
                "magazine": pos.magazine,
                "position": pos.position,
            }

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
                "magazine": pos_map.get(tid, {}).get("magazine"),
                "position": pos_map.get(tid, {}).get("position"),
            }
            for tid, t in tools.items()
            if t.name
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

    # TMA opzionale — cerca con varie estensioni
    magazines, positions = {}, []
    tma_found = None
    for suffix in (".TMA", ".tma", ".Tma"):
        candidate = toa_path.with_suffix(suffix)
        if candidate.exists():
            tma_found = candidate
            break

    if tma_found:
        try:
            magazines, positions = parse_tma(tma_found)
            log.info(f"TMA letto: {tma_found.name} — {len(magazines)} magazine, {len(positions)} posizioni occupate")
            if not positions:
                log.warning("TMA letto ma nessuna posizione occupata — magazzino vuoto al momento del salvataggio")
        except Exception as e:
            log.warning(f"Errore lettura TMA (non bloccante): {e}")
    else:
        log.warning(f"File TMA non trovato accanto a {toa_path.name} — posizioni magazzino non disponibili")

    sync_time = datetime.now().isoformat()
    _save_tools_db(tools, sync_time, positions)

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
            magazine=t.get("magazine"),
            position=t.get("position"),
        ))

    # Ordina per posizione magazzino (come in macchina), poi per nome
    return sorted(result, key=lambda x: (
        x.magazine if x.magazine is not None else 9999,
        x.position if x.position is not None else 9999,
        x.name,
        x.duplo,
    ))


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

    # Estrai utensili richiesti (T="alias" + M6) — logica identica a nc_analyzer
    utensili_file = _estrai_utensili_da_testo(mpf_text)
    if not utensili_file:
        return CheckResult(
            ok=[], missing=[], disabled=[], worn=[],
            total_required=0, can_run=True
        )

    alias_richiesti = {alias for alias, _, _ in utensili_file}

    alias_in_macchina = {
        t["name"].upper() for t in tools_db.values() if t.get("name")
    }
    alias_abilitati = {
        t["name"].upper() for t in tools_db.values()
        if t.get("name") and t.get("is_enabled", True) and not t.get("is_worn", False)
    }
    alias_vita_bassa = {
        t["name"].upper() for t in tools_db.values()
        if t.get("name") and t.get("life_percent") is not None
        and t["life_percent"] < 10 and t.get("is_enabled", True)
    }

    missing  = sorted(alias_richiesti - alias_in_macchina)
    disabled = sorted(alias_richiesti & (alias_in_macchina - alias_abilitati))
    worn     = sorted((alias_richiesti & alias_vita_bassa) - set(disabled))
    ok       = sorted(alias_richiesti - set(missing) - set(disabled) - set(worn))

    return CheckResult(
        ok=ok,
        missing=missing,
        disabled=disabled,
        worn=worn,
        total_required=len(alias_richiesti),
        can_run=not missing and not disabled,
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
    utensili_file = _estrai_utensili_da_testo(mpf_text)
    if not utensili_file:
        return CheckResult(
            ok=[], missing=[], disabled=[], worn=[],
            total_required=0, can_run=True
        )

    alias_richiesti = {alias for alias, _, _ in utensili_file}
    alias_in_macchina = {
        t["name"].upper() for t in tools_db.values() if t.get("name")
    }
    alias_abilitati = {
        t["name"].upper() for t in tools_db.values()
        if t.get("name") and t.get("is_enabled", True) and not t.get("is_worn", False)
    }
    alias_vita_bassa = {
        t["name"].upper() for t in tools_db.values()
        if t.get("name") and t.get("life_percent") is not None
        and t["life_percent"] < 10 and t.get("is_enabled", True)
    }

    missing  = sorted(alias_richiesti - alias_in_macchina)
    disabled = sorted(alias_richiesti & (alias_in_macchina - alias_abilitati))
    worn     = sorted((alias_richiesti & alias_vita_bassa) - set(disabled))
    ok       = sorted(alias_richiesti - set(missing) - set(disabled) - set(worn))

    return CheckResult(
        ok=ok, missing=missing, disabled=disabled, worn=worn,
        total_required=len(alias_richiesti),
        can_run=not missing and not disabled,
    )
