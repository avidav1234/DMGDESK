"""Bridge HTTP di sola lettura per le macchine TNC 640 — app FastAPI standalone.

Avvio (dalla root del repo):
    # PowerShell: $env:DMG_API_KEY = "la-tua-master-key"
    py -m uvicorn heidenhain.bridge:app --host 0.0.0.0 --port 8010

ACCESSO ADMIN: tutte le pagine/endpoint macchina sono protetti dalla master key
`DMG_API_KEY` (la stessa "admin" del backend principale). Vie ammesse:
  - browser: apri  /login?api_key=LA_CHIAVE  (imposta un cookie e poi naviga)
  - header:  X-API-Key: LA_CHIAVE
  - query:   ?api_key=LA_CHIAVE
Se DMG_API_KEY non e' configurata, il bridge e' CHIUSO (nessun accesso).

Endpoint (multi-macchina, `{mid}` = p800-1 | p800-2):
    GET  /                          -> elenco macchine (admin)
    GET  /m/{mid}                   -> viewer a screenshot (auto-refresh)
    GET  /m/{mid}/live              -> viewer LIVE fluido (noVNC via WebSocket)
    WS   /m/{mid}/vnc               -> relay WebSocket <-> VNC 5900 del controllo
    GET  /m/{mid}/screenshot.png    -> un fotogramma PNG (via VNC/RFB)
    GET  /api/machines              -> lista macchine
    GET  /api/m/{mid}/info          -> stato live (versione, assi, programma, override)
    GET  /api/m/{mid}/connettivita  -> check porte 5900/19000
    GET  /login?api_key=...         -> imposta cookie admin
    GET  /healthz                   -> stato bridge (aperto)

NOTA: solo lettura dei dati. Lo schermo live e' comandabile dal client (noVNC) ma
di default in SOLA VISIONE; il "comando" e' un'azione esplicita nel viewer.
"""

from __future__ import annotations

import asyncio
import os
import secrets
from pathlib import Path

from fastapi import Depends, FastAPI, HTTPException, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles

try:  # esecuzione come pacchetto (uvicorn heidenhain.bridge:app)
    from heidenhain import tnc_client
    from heidenhain.config import MACHINES
except ImportError:  # esecuzione come script diretto
    import tnc_client  # type: ignore
    from config import MACHINES  # type: ignore

_HERE = Path(__file__).parent
_VIEWER_TPL = (_HERE / "viewer.html").read_text(encoding="utf-8")
_LIVE_TPL = (_HERE / "live.html").read_text(encoding="utf-8")
_NOVNC_DIR = _HERE / "vendor" / "noVNC"

# ── Gate admin (master key DMG_API_KEY) ──────────────────────────────────────
_ADMIN_KEY = (os.environ.get("DMG_BRIDGE_KEY") or os.environ.get("DMG_API_KEY") or "").strip()
_COOKIE = "dmg_bridge_admin"


def _key_from(headers, query, cookies) -> str | None:
    return (
        headers.get("x-api-key")
        or query.get("api_key")
        or cookies.get(_COOKIE)
    )


def _is_admin(headers, query, cookies) -> bool:
    if not _ADMIN_KEY:
        return False  # nessuna chiave configurata => bridge chiuso
    provided = _key_from(headers, query, cookies)
    return bool(provided) and secrets.compare_digest(provided, _ADMIN_KEY)


def require_admin(request: Request) -> None:
    """Dependency: blocca l'accesso se l'admin non e' 'acceso' (master key)."""
    if not _is_admin(request.headers, request.query_params, request.cookies):
        if not _ADMIN_KEY:
            raise HTTPException(status_code=503, detail="bridge chiuso: DMG_API_KEY non configurata")
        raise HTTPException(status_code=403, detail="accesso admin richiesto (/login?api_key=...)")


app = FastAPI(title="Yellow Hub — TNC 640 bridge", version="0.3.0")

if _NOVNC_DIR.exists():
    app.mount("/novnc", StaticFiles(directory=str(_NOVNC_DIR)), name="novnc")


def _ip(mid: str) -> str:
    m = MACHINES.get(mid)
    if not m:
        raise HTTPException(status_code=404, detail=f"macchina '{mid}' sconosciuta")
    return m["ip"]


# ── Login / healthz (aperti) ─────────────────────────────────────────────────


@app.get("/login")
def login(api_key: str = "") -> Response:
    if _ADMIN_KEY and api_key and secrets.compare_digest(api_key, _ADMIN_KEY):
        resp = RedirectResponse("/", status_code=303)
        resp.set_cookie(_COOKIE, api_key, httponly=True, samesite="lax")
        return resp
    raise HTTPException(status_code=403, detail="chiave non valida")


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "admin_configurato": bool(_ADMIN_KEY), "macchine": list(MACHINES.keys())}


# ── Pagine e API (protette admin) ────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def index() -> str:
    righe = "\n".join(
        f'<li><a href="/m/{mid}/live">{m["nome"]}</a> '
        f'<span class="muted">{m["ip"]}</span> '
        f'&middot; <a href="/m/{mid}">screenshot</a></li>'
        for mid, m in MACHINES.items()
    )
    return (
        "<!doctype html><meta charset='utf-8'>"
        "<title>TNC 640 — macchine</title>"
        "<style>body{font-family:system-ui,sans-serif;background:#111;color:#eee;"
        "padding:2rem}a{color:#58a6ff}li{margin:.5rem 0;font-size:1.1rem}"
        ".muted{opacity:.6;font-size:.85rem}</style>"
        "<h1>Macchine TNC 640</h1><ul>" + righe + "</ul>"
    )


@app.get("/m/{mid}", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def viewer(mid: str) -> str:
    m = MACHINES.get(mid)
    if not m:
        raise HTTPException(status_code=404, detail=f"macchina '{mid}' sconosciuta")
    return _fill(_VIEWER_TPL, mid, m)


@app.get("/m/{mid}/live", response_class=HTMLResponse, dependencies=[Depends(require_admin)])
def live(mid: str) -> str:
    m = MACHINES.get(mid)
    if not m:
        raise HTTPException(status_code=404, detail=f"macchina '{mid}' sconosciuta")
    return _fill(_LIVE_TPL, mid, m)


def _fill(tpl: str, mid: str, m: dict) -> str:
    return tpl.replace("{{MID}}", mid).replace("{{NOME}}", m["nome"]).replace("{{IP}}", m["ip"])


@app.get("/m/{mid}/screenshot.png", dependencies=[Depends(require_admin)])
def screenshot(mid: str) -> Response:
    ip = _ip(mid)
    try:
        png = tnc_client.screenshot_png(ip)
        return Response(content=png, media_type="image/png", headers={"Cache-Control": "no-store"})
    except Exception as e:  # noqa: BLE001
        return JSONResponse(status_code=502, content={"errore": f"{type(e).__name__}: {e}"})


@app.get("/api/machines", dependencies=[Depends(require_admin)])
def machines() -> JSONResponse:
    return JSONResponse(MACHINES)


@app.get("/api/m/{mid}/info", dependencies=[Depends(require_admin)])
def info(mid: str) -> JSONResponse:
    return JSONResponse(tnc_client.lsv2_info(_ip(mid)))


@app.get("/api/m/{mid}/connettivita", dependencies=[Depends(require_admin)])
def connettivita(mid: str) -> JSONResponse:
    return JSONResponse(tnc_client.connectivity(_ip(mid)))


# ── Relay WebSocket <-> VNC (5900) ───────────────────────────────────────────


@app.websocket("/m/{mid}/vnc")
async def vnc_relay(ws: WebSocket, mid: str) -> None:
    # gate admin sull'handshake WS (cookie/query/header)
    if not _is_admin(ws.headers, ws.query_params, ws.cookies):
        await ws.close(code=1008)  # policy violation
        return
    m = MACHINES.get(mid)
    if not m:
        await ws.close(code=1008)
        return

    # noVNC storicamente richiede il subprotocol 'binary'; lo concediamo se offerto.
    offered = ws.headers.get("sec-websocket-protocol", "")
    subproto = "binary" if "binary" in offered else None
    await ws.accept(subprotocol=subproto)

    try:
        reader, writer = await asyncio.open_connection(m["ip"], 5900)
    except OSError as e:
        await ws.close(code=1011)  # internal error
        return

    async def tcp_to_ws() -> None:
        try:
            while True:
                data = await reader.read(65536)
                if not data:
                    break
                await ws.send_bytes(data)
        except Exception:  # noqa: BLE001
            pass

    async def ws_to_tcp() -> None:
        try:
            while True:
                data = await ws.receive_bytes()
                writer.write(data)
                await writer.drain()
        except Exception:  # noqa: BLE001
            pass

    t_out = asyncio.create_task(tcp_to_ws())
    t_in = asyncio.create_task(ws_to_tcp())
    try:
        await asyncio.wait({t_out, t_in}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        t_out.cancel()
        t_in.cancel()
        try:
            writer.close()
            await writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass
        try:
            await ws.close()
        except Exception:  # noqa: BLE001
            pass
