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
    GET  /m/{mid}                   -> viewer LIVE fluido (noVNC) + pannello dati
    WS   /m/{mid}/vnc               -> relay WebSocket <-> VNC 5900 del controllo
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


def _login_page(next_url: str = "/", error: str = "") -> str:
    err = f'<p style="color:#f85149;margin:0;font-size:.85rem">{error}</p>' if error else ""
    safe_next = next_url if next_url.startswith("/") else "/"
    return (
        "<!doctype html><meta charset='utf-8'><title>Accesso — TNC 640</title>"
        "<style>body{font-family:system-ui,sans-serif;background:#111;color:#eee;"
        "display:flex;height:100vh;margin:0;align-items:center;justify-content:center}"
        "form{background:#1c1c1c;padding:1.6rem;border-radius:10px;border:1px solid #333;"
        "display:flex;flex-direction:column;gap:.7rem;min-width:260px}"
        "input{padding:.5rem;border-radius:6px;border:1px solid #444;background:#0d0d0d;color:#eee}"
        "button{padding:.5rem;border-radius:6px;border:none;background:#2563eb;color:#fff;"
        "font-weight:600;cursor:pointer}h1{font-size:1rem;margin:0}</style>"
        "<form method='get' action='/login'>"
        "<h1>Accesso admin — TNC 640</h1>" + err +
        f"<input type='hidden' name='next' value='{safe_next}'>"
        "<input name='api_key' type='password' placeholder='chiave admin' autofocus>"
        "<button>Accedi</button></form>"
    )


@app.get("/login")
def login(api_key: str = "", next: str = "/") -> Response:
    safe_next = next if next.startswith("/") else "/"
    if not _ADMIN_KEY:
        raise HTTPException(status_code=503, detail="bridge chiuso: DMG_API_KEY non configurata")
    if not api_key:
        return HTMLResponse(_login_page(safe_next))
    if secrets.compare_digest(api_key, _ADMIN_KEY):
        resp = RedirectResponse(safe_next, status_code=303)
        resp.set_cookie(_COOKIE, api_key, httponly=True, samesite="lax")
        return resp
    return HTMLResponse(_login_page(safe_next, "chiave non valida"), status_code=401)


@app.get("/healthz")
def healthz() -> dict:
    return {"ok": True, "admin_configurato": bool(_ADMIN_KEY), "macchine": list(MACHINES.keys())}


# ── Pagine e API (protette admin) ────────────────────────────────────────────


@app.get("/", response_class=HTMLResponse)
def index(request: Request) -> Response:
    if not _is_admin(request.headers, request.query_params, request.cookies):
        return HTMLResponse(_login_page("/"))
    righe = "\n".join(
        f'<li><a href="/m/{mid}">{m["nome"]}</a> '
        f'<span class="muted">{m["ip"]}</span></li>'
        for mid, m in MACHINES.items()
    )
    return HTMLResponse(
        "<!doctype html><meta charset='utf-8'>"
        "<title>TNC 640 — macchine</title>"
        "<style>body{font-family:system-ui,sans-serif;background:#111;color:#eee;"
        "padding:2rem}a{color:#58a6ff}li{margin:.5rem 0;font-size:1.1rem}"
        ".muted{opacity:.6;font-size:.85rem}</style>"
        "<h1>Macchine TNC 640</h1><ul>" + righe + "</ul>"
    )


@app.get("/m/{mid}", response_class=HTMLResponse)
def live(mid: str, request: Request) -> Response:
    m = MACHINES.get(mid)
    if not m:
        raise HTTPException(status_code=404, detail=f"macchina '{mid}' sconosciuta")
    if not _is_admin(request.headers, request.query_params, request.cookies):
        return HTMLResponse(_login_page(f"/m/{mid}"))
    return HTMLResponse(
        _LIVE_TPL.replace("{{MID}}", mid).replace("{{NOME}}", m["nome"]).replace("{{IP}}", m["ip"])
    )


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
