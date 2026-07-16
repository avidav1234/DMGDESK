"""Bridge HTTP di sola lettura per le macchine TNC 640 — app FastAPI standalone.

Avvio (dalla root del repo):
    py -m uvicorn heidenhain.bridge:app --host 0.0.0.0 --port 8010

Le macchine sono definite in config.py (override via env TNC_MACHINES).

Endpoint:
    GET /                          -> elenco macchine (dashboard)
    GET /m/{mid}                   -> visualizzatore live di una macchina
    GET /m/{mid}/screenshot.png    -> un fotogramma PNG dello schermo (via VNC/RFB)
    GET /api/machines              -> lista macchine configurate
    GET /api/m/{mid}/info          -> stato live (versione, assi, programma, override)
    GET /api/m/{mid}/connettivita  -> check porte 5900/19000
    GET /healthz

NOTA: solo lettura. Nessun comando inviato alla macchina (safe_mode=True; il login
DNC e' abilitato solo per la LETTURA dei dati di stato).
"""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, Response

try:  # esecuzione come pacchetto (uvicorn heidenhain.bridge:app)
    from heidenhain import tnc_client
    from heidenhain.config import MACHINES
except ImportError:  # esecuzione come script diretto
    import tnc_client  # type: ignore
    from config import MACHINES  # type: ignore

_VIEWER_TPL = (Path(__file__).parent / "viewer.html").read_text(encoding="utf-8")

app = FastAPI(title="Yellow Hub — TNC 640 bridge", version="0.2.0")


def _ip(mid: str) -> str:
    m = MACHINES.get(mid)
    if not m:
        raise HTTPException(status_code=404, detail=f"macchina '{mid}' sconosciuta")
    return m["ip"]


@app.get("/", response_class=HTMLResponse)
def index() -> str:
    righe = "\n".join(
        f'<li><a href="/m/{mid}">{m["nome"]}</a> '
        f'<span class="muted">{m["ip"]}</span></li>'
        for mid, m in MACHINES.items()
    )
    return (
        "<!doctype html><meta charset='utf-8'>"
        "<title>TNC 640 — macchine</title>"
        "<style>body{font-family:system-ui,sans-serif;background:#111;color:#eee;"
        "padding:2rem}a{color:#58a6ff}li{margin:.4rem 0;font-size:1.1rem}"
        ".muted{opacity:.6;font-size:.85rem}</style>"
        "<h1>Macchine TNC 640</h1><ul>" + righe + "</ul>"
    )


@app.get("/m/{mid}", response_class=HTMLResponse)
def viewer(mid: str) -> str:
    m = MACHINES.get(mid)
    if not m:
        raise HTTPException(status_code=404, detail=f"macchina '{mid}' sconosciuta")
    return (
        _VIEWER_TPL.replace("{{MID}}", mid)
        .replace("{{NOME}}", m["nome"])
        .replace("{{IP}}", m["ip"])
    )


@app.get("/m/{mid}/screenshot.png")
def screenshot(mid: str) -> Response:
    ip = _ip(mid)
    try:
        png = tnc_client.screenshot_png(ip)
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=502, content={"errore": f"{type(e).__name__}: {e}"})


@app.get("/api/machines")
def machines() -> JSONResponse:
    return JSONResponse(MACHINES)


@app.get("/api/m/{mid}/info")
def info(mid: str) -> JSONResponse:
    return JSONResponse(tnc_client.lsv2_info(_ip(mid)))


@app.get("/api/m/{mid}/connettivita")
def connettivita(mid: str) -> JSONResponse:
    return JSONResponse(tnc_client.connectivity(_ip(mid)))


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "macchine": list(MACHINES.keys())}
