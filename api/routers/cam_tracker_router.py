"""
api/routers/cam_tracker_router.py
===================================
Router FastAPI per il modulo CAMTracker.
Riceve le sessioni CAM da CAM35, le aggrega per progetto/giorno
e le espone per il frontend DMGDesk.

Prefisso: /api/cam-tracker
"""

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date as date_type, datetime
import json
import os
from pathlib import Path

from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()

# ── Storage ────────────────────────────────────────────────────────────────────
# Path dati CAM tracker — usa la directory della config se disponibile, altrimenti root progetto
def _get_data_file() -> Path:
    try:
        from database.db_handler import carica_configurazione
        cfg = carica_configurazione()
        base = cfg.get("tools_toa_folder") or cfg.get("percorso_nc_base")
        if base:
            return Path(base) / "cam_tracker_data.json"
    except Exception:
        pass
    return Path(__file__).parent.parent.parent / "cam_tracker_data.json"

_DATA_FILE = _get_data_file()


def _load() -> list[dict]:
    if not _DATA_FILE.exists():
        return []
    try:
        with open(_DATA_FILE, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _save(data: list[dict]):
    tmp = _DATA_FILE.with_suffix(".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    tmp.replace(_DATA_FILE)


# ── Modelli ────────────────────────────────────────────────────────────────────
class CamSessionItem(BaseModel):
    project: str = Field(..., description="project_id (commessa_operazione)")
    commessa: str = Field(default="")
    operazione: str = Field(default="")
    full_path: Optional[str] = Field(default=None)
    seconds: int = Field(..., ge=0)
    hours: float = Field(..., ge=0)


class CamSessionBatch(BaseModel):
    source: str = Field(default="cimatron")
    workstation: str = Field(..., description="Nome host CAM (es. CAM35)")
    date: str = Field(..., description="Data ISO (YYYY-MM-DD)")
    flushed_at: str = Field(..., description="Timestamp invio")
    sessions: List[CamSessionItem]


class CamRecord(BaseModel):
    id: str
    project: str
    date: str
    seconds: int
    hours: float
    workstation: str
    source: str
    last_updated: str


# ── POST /sessions — riceve dati da CAM35 ────────────────────────────────────
@router.post("/sessions", summary="Ricevi sessioni CAM da CAM35")
def receive_sessions(batch: CamSessionBatch):
    data = _load()

    updated = 0
    created = 0

    for s in batch.sessions:
        project_key = s.project.strip().upper()
        # Cerca record esistente per stesso progetto+data
        existing = next(
            (r for r in data
             if r["project"] == project_key and r["date"] == batch.date),
            None
        )
        if existing:
            existing["seconds"] += s.seconds
            existing["hours"] = round(existing["seconds"] / 3600, 3)
            existing["last_updated"] = datetime.now().isoformat()
            # Aggiorna path se ora disponibile (COM vs title)
            if s.full_path:
                existing["full_path"] = s.full_path
            updated += 1
        else:
            data.append({
                "id":         f"{s.project}_{batch.date}_{batch.workstation}",
                "project":    s.project,
                "commessa":   s.commessa or s.project.split("_")[0],
                "operazione": s.operazione,
                "full_path":  s.full_path,
                "date":       batch.date,
                "seconds":    s.seconds,
                "hours":      s.hours,
                "workstation": batch.workstation,
                "source":     batch.source,
                "last_updated": datetime.now().isoformat(),
            })
            created += 1

    try:
        _save(data)
    except Exception as _e:
        log.warning(f"[CAMTracker] _save fallita (non critico): {_e}")
    log.info(
        f"[CAMTracker] Sessioni ricevute da {batch.workstation} — "
        f"create={created} aggiornate={updated}"
    )
    return {
        "ok": True,
        "created": created,
        "updated": updated,
        "total_records": len(data),
    }


# ── GET /sessions — lista sessioni filtrabili ─────────────────────────────────
@router.get("/sessions", response_model=List[dict], summary="Lista sessioni CAM")
def get_sessions(
    project: Optional[str] = Query(None, description="Filtra per nome progetto"),
    date_from: Optional[str] = Query(None, description="Data inizio (YYYY-MM-DD)"),
    date_to: Optional[str] = Query(None, description="Data fine (YYYY-MM-DD)"),
    workstation: Optional[str] = Query(None),
    limit: int = Query(200, le=1000),
):
    data = _load()

    if project:
        data = [d for d in data if d["project"].upper() == project.upper()]
    if date_from:
        data = [d for d in data if d["date"] >= date_from]
    if date_to:
        data = [d for d in data if d["date"] <= date_to]
    if workstation:
        data = [d for d in data if d["workstation"].upper() == workstation.upper()]

    data.sort(key=lambda x: x["date"], reverse=True)
    return data[:limit]


# ── GET /summary — ore totali per progetto ────────────────────────────────────
@router.get("/summary", summary="Ore totali per progetto (tutti i giorni)")
def get_summary(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    data = _load()

    if date_from:
        data = [d for d in data if d["date"] >= date_from]
    if date_to:
        data = [d for d in data if d["date"] <= date_to]

    summary: dict[str, float] = {}
    for r in data:
        summary[r["project"]] = summary.get(r["project"], 0) + r["seconds"]

    result = [
        {
            "project": p,
            "total_seconds": int(s),
            "total_hours": round(s / 3600, 2),
        }
        for p, s in sorted(summary.items(), key=lambda x: -x[1])
    ]
    return result


# ── GET /today — sessione corrente di oggi ───────────────────────────────────
@router.get("/today", summary="Sessioni di oggi")
def get_today():
    today = date_type.today().isoformat()
    data = _load()
    today_data = [d for d in data if d["date"] == today]
    total_sec = sum(d["seconds"] for d in today_data)
    return {
        "date": today,
        "sessions": today_data,
        "total_seconds": total_sec,
        "total_hours": round(total_sec / 3600, 2),
    }


# ── DELETE /sessions/{project} — reset per progetto ──────────────────────────
@router.get("/commesse", summary="Ore totali per commessa (aggregato su operazioni)")
def get_commesse(
    date_from: Optional[str] = Query(None),
    date_to: Optional[str] = Query(None),
):
    data = _load()
    if date_from:
        data = [d for d in data if d["date"] >= date_from]
    if date_to:
        data = [d for d in data if d["date"] <= date_to]

    commesse: dict[str, dict] = {}
    for r in data:
        c = r.get("commessa") or r["project"].split("_")[0]
        if c not in commesse:
            commesse[c] = {"commessa": c, "total_seconds": 0, "operazioni": {}}
        commesse[c]["total_seconds"] += r["seconds"]
        op = r.get("operazione", "")
        if op:
            commesse[c]["operazioni"][op] = (
                commesse[c]["operazioni"].get(op, 0) + r["seconds"]
            )

    return [
        {
            "commessa": c,
            "total_hours": round(d["total_seconds"] / 3600, 2),
            "operazioni": [
                {"operazione": op, "hours": round(s / 3600, 2)}
                for op, s in sorted(d["operazioni"].items(), key=lambda x: -x[1])
            ],
        }
        for c, d in sorted(commesse.items(), key=lambda x: -x[1]["total_seconds"])
    ]



def delete_project_sessions(project: str):
    data = _load()
    before = len(data)
    data = [d for d in data if d["project"].upper() != project.upper()]
    _save(data)
    return {"deleted": before - len(data)}
