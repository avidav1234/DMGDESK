"""Bridge HTTP di sola lettura per il TNC 640 — app FastAPI standalone.

Avvio (dalla root del repo):
    set TNC_IP=192.168.244.149        # (PowerShell: $env:TNC_IP="192.168.244.149")
    py -m uvicorn heidenhain.bridge:app --host 0.0.0.0 --port 8010

Endpoint:
    GET /                 -> visualizzatore live (auto-refresh dello screenshot)
    GET /screenshot.png   -> un fotogramma PNG dello schermo del controllo (via VNC/RFB)
    GET /api/info         -> versione + messaggi attivi + connettivita' (via LSV2)
    GET /api/connettivita -> check rapido porte 5900/19000
    GET /healthz          -> stato bridge

NOTA: questo bridge fa SOLO lettura. Lo schermo "fluido" vero (streaming + comando
mouse) sara' il client noVNC nel frontend React — vedi README (🟡 prossimo passo).
"""

from __future__ import annotations

import os
from pathlib import Path

from fastapi import FastAPI, Response
from fastapi.responses import HTMLResponse, JSONResponse

try:  # esecuzione come pacchetto (uvicorn heidenhain.bridge:app)
    from heidenhain import tnc_client
except ImportError:  # esecuzione come script diretto
    import tnc_client  # type: ignore

TNC_IP = os.environ.get("TNC_IP", "192.168.244.149")
VIEWER_HTML = (Path(__file__).parent / "viewer.html").read_text(encoding="utf-8")

app = FastAPI(title="Yellow Hub — TNC 640 bridge", version="0.1.0")


@app.get("/", response_class=HTMLResponse)
def viewer() -> str:
    return VIEWER_HTML.replace("{{TNC_IP}}", TNC_IP)


@app.get("/screenshot.png")
def screenshot() -> Response:
    try:
        png = tnc_client.screenshot_png(TNC_IP)
        return Response(
            content=png,
            media_type="image/png",
            headers={"Cache-Control": "no-store"},
        )
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=502, content={"errore": f"{type(e).__name__}: {e}"})


@app.get("/api/info")
def info() -> JSONResponse:
    return JSONResponse(tnc_client.lsv2_info(TNC_IP))


@app.get("/api/connettivita")
def connettivita() -> JSONResponse:
    return JSONResponse(tnc_client.connectivity(TNC_IP))


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "tnc_ip": TNC_IP}
