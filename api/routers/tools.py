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

from api.toa_parser import sync_from_share, detect_format, MachineTool, MagazinePosition
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

def _get_share_path() -> str:
    """Restituisce il percorso della share (es. P:\\DMG_DMC_160U)."""
    config = carica_configurazione()
    radice = config.get("radice", "")
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
    return radice


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
    format_used: Optional[str]   # "toa" | "mpf"
    toa_path: str
    tma_path: str
    reason: Optional[str]        # spiegazione formato scelto


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

def _save_tools_db(tools: dict, sync_time: str, positions=None, format_used: str = "") -> None:
    """Salva il DB utensili in JSON locale. tools = dict {t_num: MachineTool}."""
    db_path = _get_tools_db_path()

    # Posizioni dal TMA (se non già nel tool)
    pos_map: dict[int, dict] = {}
    if positions:
        for pos in positions:
            pos_map[pos.t_number] = {"magazine": pos.magazine, "position": pos.position}

    data = {
        "sync_time":   sync_time,
        "format_used": format_used,
        "tools": {
            str(t_num): {
                "tool_id":      t.t_number,
                "name":         t.name,
                "duplo":        t.duplo,
                "status":       t.status,
                "length":       t.length,
                "radius":       t.radius,
                "life_percent": t.life_percent,
                "is_enabled":   t.is_enabled,
                "is_worn":      t.is_worn,
                "magazine":     t.magazine if t.magazine is not None else pos_map.get(t_num, {}).get("magazine"),
                "position":     t.position if t.position is not None else pos_map.get(t_num, {}).get("position"),
            }
            for t_num, t in tools.items()
            if t.name
        }
    }
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


def _load_tools_db() -> tuple[dict, str | None, str]:
    """Carica il DB utensili dal JSON locale. Restituisce (tools_dict, sync_time, format_used)."""
    db_path = _get_tools_db_path()
    if not db_path.exists():
        return {}, None, ""
    with open(db_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tools", {}), data.get("sync_time"), data.get("format_used", "")


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post(
    "/sync",
    summary="Sincronizza tabella utensili dalla share macchina",
)
async def sync_tools():
    """
    Auto-rileva il formato più aggiornato (TOA+TMA o MPF) e aggiorna il DB.

    Formati supportati sulla share:
      - TOOL_SYNC.TOA + TOOL_SYNC.TMA  (HMI → Servizi → Salva Attrezzaggio)
      - TOOL_SYN1_TOA.MPF + TOOL_SYN2_TOA.MPF + TOOL_SYN3_TOA.MPF  (programma NC)
    Il formato con timestamp più recente viene usato automaticamente.
    """
    share = _get_share_path()
    try:
        result = sync_from_share(share)
    except FileNotFoundError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        import traceback
        detail = f"Errore lettura share: {e}\n{traceback.format_exc()}"
        log.error(detail)
        raise HTTPException(status_code=500, detail=str(e))

    tools     = result["tools"]
    positions = result["positions"]
    sync_time = datetime.now().isoformat()

    try:
        _save_tools_db(tools, sync_time, positions, format_used=result["format_used"])
    except Exception as e:
        import traceback
        log.error(f"Errore _save_tools_db: {e}\n{traceback.format_exc()}")
        raise HTTPException(status_code=500, detail=f"Errore salvataggio DB: {e}")

    log.info(f"Sync OK: {len(tools)} utensili via {result['format_used'].upper()} — {result['reason']}")

    return {
        "ok":              True,
        "sync_time":       sync_time,
        "tool_count":      len(tools),
        "positions_mapped": len(positions),
        "format_used":     result["format_used"],
        "reason":          result["reason"],
    }


@router.get(
    "/sync-status",
    response_model=SyncStatus,
    summary="Stato e data dell'ultimo sync",
)
async def sync_status():
    """Restituisce stato ultimo sync, formato usato e quanti utensili ci sono nel DB."""
    try:
        share = _get_share_path()
        info  = detect_format(share)
        toa_p = str(info["toa_files"][0]) if info["toa_files"] else share + "/TOOL_SYNC.TOA"
        tma_p = str(Path(share) / "TOOL_SYNC.TMA")
    except Exception:
        toa_p = ""; tma_p = ""; info = {}

    tools_db, sync_time, fmt_used = _load_tools_db()

    return SyncStatus(
        last_sync=sync_time,
        tool_count=len(tools_db),
        format_used=fmt_used or None,
        toa_path=toa_p,
        tma_path=tma_p,
        reason=info.get("reason"),
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
    tools_db, sync_time, format_used = _load_tools_db()
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
    tools_db, sync_time, _ = _load_tools_db()
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
    tools_db, _, _ = _load_tools_db()
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
