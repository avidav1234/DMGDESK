"""
api/routers/step_client.py
===========================
Client proxy verso il microservizio STEP Analyzer (porta 8001).
DMGDesk chiama questi endpoint — il frontend non parla mai direttamente
con il microservizio.

GET  /api/step/stato
POST /api/step/analizza        { commessa, path_step }
GET  /api/step/simili/{commessa}?top=5&soglia=60
GET  /api/step/storico
"""

import logging
import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel
from typing import Optional

log = logging.getLogger("step_client")
router = APIRouter(prefix="/api/step", tags=["STEP Analyzer"])

STEP_ANALYZER_URL = "http://127.0.0.1:8002"
TIMEOUT = 120  # secondi — cadquery può impiegare 10-15s su file grandi


async def _call(method: str, path: str, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await getattr(client, method)(f"{STEP_ANALYZER_URL}{path}", **kwargs)
            r.raise_for_status()
            return r.json()
    except httpx.ConnectError as e:
        log.error(f"step_client ConnectError: {e}")
        raise HTTPException(503,
            "STEP Analyzer non raggiungibile — avvia step_analyzer/start.bat")
    except httpx.HTTPStatusError as e:
        log.error(f"step_client HTTP {e.response.status_code}: {e.response.text}")
        raise HTTPException(e.response.status_code, e.response.text)
    except Exception as e:
        log.error(f"step_client errore: {type(e).__name__}: {e}")
        raise HTTPException(500, f"{type(e).__name__}: {e}")


class AnalizzaRequest(BaseModel):
    commessa:  str
    path_step: str
    note:      Optional[str] = None
    ore_macchina:     Optional[float] = None
    lead_time_giorni: Optional[int]   = None
    data_inizio:      Optional[str]   = None
    data_consegna:    Optional[str]   = None


@router.get("/stato")
async def stato():
    return await _call("get", "/stato")


@router.post("/analizza")
async def analizza(req: AnalizzaRequest):
    return await _call("post", "/analizza", json=req.dict())


@router.post("/analizza-upload")
async def analizza_upload(
    file: UploadFile = File(...),
    commessa: str = Form(...),
    ore_macchina: str = Form(""),
    lead_time_giorni: str = Form(""),
    note: str = Form(""),
):
    """Proxy upload file STEP verso il microservizio."""
    content = await file.read()
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        try:
            r = await client.post(
                f"{STEP_ANALYZER_URL}/analizza-upload",
                files={"file": (file.filename, content, "application/octet-stream")},
                data={
                    "commessa":         commessa,
                    "ore_macchina":     ore_macchina or "",
                    "lead_time_giorni": lead_time_giorni or "",
                    "note":             note or "",
                }
            )
            r.raise_for_status()
            return r.json()
        except httpx.ConnectError:
            raise HTTPException(503, "STEP Analyzer non raggiungibile")


@router.get("/simili/{commessa}")
async def simili(commessa: str, top: int = 5, soglia: float = 60.0):
    return await _call("get", f"/simili/{commessa}",
                       params={"top": top, "soglia": soglia})


@router.get("/storico")
async def storico():
    return await _call("get", "/storico")
