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
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional

log = logging.getLogger("step_client")
router = APIRouter(prefix="/api/step", tags=["STEP Analyzer"])

STEP_ANALYZER_URL = "http://localhost:8002"
TIMEOUT = 60  # secondi — l'analisi STEP può richiedere 5-10s


async def _call(method: str, path: str, **kwargs):
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT) as client:
            r = await getattr(client, method)(f"{STEP_ANALYZER_URL}{path}", **kwargs)
            r.raise_for_status()
            return r.json()
    except httpx.ConnectError:
        raise HTTPException(503,
            "STEP Analyzer non raggiungibile — avvia step_analyzer/start.bat")
    except httpx.HTTPStatusError as e:
        raise HTTPException(e.response.status_code, e.response.text)
    except Exception as e:
        raise HTTPException(500, str(e))


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


@router.get("/simili/{commessa}")
async def simili(commessa: str, top: int = 5, soglia: float = 60.0):
    return await _call("get", f"/simili/{commessa}",
                       params={"top": top, "soglia": soglia})


@router.get("/storico")
async def storico():
    return await _call("get", "/storico")
