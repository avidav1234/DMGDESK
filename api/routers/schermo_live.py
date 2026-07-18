"""api/routers/schermo_live.py — Schermo live del controllo (VNC → browser).

Proietta lo schermo reale della DMG DMC 160U (SINUMERIK 840D PowerLine, HMI-Advanced
su PCU 50) dentro DMG Desk. Sul PCU 50 c'è già un server VNC in ascolto sulla LAN
aziendale (`10.95.20.29:5900`, auth VNC con password) — usato dal sistema TCU.
Vedi REPORT_DMG_DESK_SCHERMO_LIVE.md.

Architettura (analoga al bridge Heidenhain, ma con auth terminata lato server):

    browser (noVNC)  ──WebSocket──▶  /api/schermo/vnc  ──TCP RFB──▶  PCU 50:5900
                                     (questo relay)

Il relay **termina l'autenticazione VNC lato backend**: legge la password da
`DMG_VNC_PASSWORD` (in `.env`, MAI hardcoded) e la usa per autenticarsi al server
VNC reale; verso noVNC presenta invece sicurezza "None". Così la password del
controllo **non arriva mai al browser**. Fatto l'handshake su entrambi i lati, il
relay diventa trasparente (pump bidirezionale dei byte RFB).

Sicurezza:
  - Il middleware globale NON protegge i WebSocket (salta gli scope non-http):
    l'auth (API key o token di sessione operatore) è verificata QUI, sull'handshake.
  - Default **sola visione**: noVNC parte con `viewOnly`; "prendi il controllo" è
    un'azione esplicita nel viewer.
  - ⚠️ Sul PCU la password VNC è il default di fabbrica: non esporre mai il VNC
    diretto, solo tramite questo relay dietro auth.

Endpoint:
    WS   /api/schermo/vnc?token=...     relay WebSocket ↔ VNC (auth terminata)
    GET  /api/schermo/viewer?token=...  pagina viewer noVNC (HTML, dietro auth)
    GET  /api/schermo/info              config non sensibile (host/porta, no password)
"""

from __future__ import annotations

import asyncio
import os

from fastapi import APIRouter, Request, WebSocket
from fastapi.responses import HTMLResponse, JSONResponse
from starlette.websockets import WebSocketDisconnect

from api import auth as _dmg_auth
from utils.logger import get_logger

# DES per l'auth VNC (challenge/response). 'cryptography' è già una dipendenza.
try:  # cryptography >= 43 sposta DES/3DES in 'decrepit'
    from cryptography.hazmat.decrepit.ciphers.algorithms import TripleDES as _DES
except Exception:  # noqa: BLE001 — fallback per versioni precedenti
    from cryptography.hazmat.primitives.ciphers.algorithms import TripleDES as _DES
from cryptography.hazmat.primitives.ciphers import Cipher, modes

log = get_logger(__name__)
router = APIRouter()

# ── Configurazione (da env / .env) ──────────────────────────────────────────
_VNC_HOST = (os.environ.get("DMG_VNC_HOST") or "10.95.20.29").strip()
_VNC_PORT = int(os.environ.get("DMG_VNC_PORT") or "5900")
# La password NON ha default hardcoded: se assente, il relay non può autenticarsi.
_VNC_PASSWORD = os.environ.get("DMG_VNC_PASSWORD") or ""

_API_KEY = (os.environ.get("DMG_API_KEY") or "").strip()
# Il relay pilota la HMI della macchina: senza auth configurata resta CHIUSO,
# salvo opt-in esplicito per lo sviluppo locale (coerente con il middleware).
_ALLOW_INSECURE = (os.environ.get("DMG_ALLOW_INSECURE") or "").strip() == "1"

import hmac as _hmac


def _api_key_uguale(fornita: str, attesa: str) -> bool:
    """Confronto a tempo costante e robusto ai non-ASCII (byte UTF-8)."""
    try:
        return _hmac.compare_digest((fornita or "").encode("utf-8"),
                                    (attesa or "").encode("utf-8"))
    except Exception:
        return False


# ── Auth VNC: risposta DES alla sfida (bit invertiti nella chiave) ──────────

def _reverse_bits(b: int) -> int:
    return int(f"{b:08b}"[::-1], 2)


def _vnc_challenge_response(password: str, challenge: bytes) -> bytes:
    pw = password.encode("latin-1", "ignore")[:8].ljust(8, b"\x00")
    key = bytes(_reverse_bits(c) for c in pw)
    enc = Cipher(_DES(key), modes.ECB()).encryptor()  # 3DES con chiave 8B == DES singolo
    return enc.update(challenge) + enc.finalize()


# ── Astrazione stream (unifica WebSocket lato client e TCP lato server) ─────

class _EOF(Exception):
    """Fine stream durante una read_exact dell'handshake."""


class _Stream:
    """Stream a byte con buffer, per leggere quantità esatte durante l'handshake
    e poi passare in modalità trasparente."""

    def __init__(self) -> None:
        self._buf = bytearray()

    async def _recv(self) -> bytes:  # prossimo chunk grezzo, b"" a EOF
        raise NotImplementedError

    async def _send(self, data: bytes) -> None:
        raise NotImplementedError

    async def aclose(self) -> None:
        raise NotImplementedError

    async def read_exact(self, n: int) -> bytes:
        while len(self._buf) < n:
            chunk = await self._recv()
            if not chunk:
                raise _EOF()
            self._buf += chunk
        out = bytes(self._buf[:n])
        del self._buf[:n]
        return out

    async def read_some(self) -> bytes:
        """Byte bufferizzati residui (se presenti), altrimenti prossimo chunk."""
        if self._buf:
            out = bytes(self._buf)
            self._buf.clear()
            return out
        return await self._recv()

    async def write(self, data: bytes) -> None:
        await self._send(data)


class _TcpStream(_Stream):
    def __init__(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        super().__init__()
        self._reader = reader
        self._writer = writer

    async def _recv(self) -> bytes:
        return await self._reader.read(65536)

    async def _send(self, data: bytes) -> None:
        self._writer.write(data)
        await self._writer.drain()

    async def aclose(self) -> None:
        try:
            self._writer.close()
            await self._writer.wait_closed()
        except Exception:  # noqa: BLE001
            pass


class _WsStream(_Stream):
    def __init__(self, ws: WebSocket) -> None:
        super().__init__()
        self._ws = ws

    async def _recv(self) -> bytes:
        try:
            return await self._ws.receive_bytes()
        except (WebSocketDisconnect, RuntimeError):
            return b""

    async def _send(self, data: bytes) -> None:
        await self._ws.send_bytes(data)

    async def aclose(self) -> None:
        try:
            await self._ws.close()
        except Exception:  # noqa: BLE001
            pass


# ── Handshake RFB ────────────────────────────────────────────────────────────

async def _auth_verso_server(server: _Stream, password: str) -> None:
    """Handshake lato server VNC reale: parla RFB 3.3 e, se richiesto (sec type 2),
    esegue l'autenticazione VNC con `password`. Al ritorno, il server è in attesa
    del ClientInit (confine su cui allineiamo anche il client)."""
    pv = await server.read_exact(12)                 # ProtocolVersion del server
    if not pv.startswith(b"RFB "):
        raise ConnectionError(f"banner RFB inatteso dal server: {pv!r}")
    await server.write(b"RFB 003.003\n")             # forziamo 3.3 (percorso verificato sul PCU)
    sectype = int.from_bytes(await server.read_exact(4), "big")
    if sectype == 0:
        ln = int.from_bytes(await server.read_exact(4), "big")
        motivo = (await server.read_exact(ln)).decode("latin-1", "replace")
        raise ConnectionError(f"server VNC rifiuta l'handshake: {motivo}")
    if sectype == 2:                                  # VNC Authentication
        if not password:
            raise ConnectionError("il server VNC richiede password ma DMG_VNC_PASSWORD non è impostata")
        challenge = await server.read_exact(16)
        await server.write(_vnc_challenge_response(password, challenge))
        res = int.from_bytes(await server.read_exact(4), "big")
        if res != 0:
            raise ConnectionError("autenticazione VNC fallita (password errata?)")
    elif sectype != 1:                                # 1 = None (nessuna password)
        raise ConnectionError(f"tipo sicurezza VNC non gestito: {sectype}")
    # sectype 1/2 ok → il server ora attende ClientInit.


async def _presenta_none_al_client(client: _Stream) -> None:
    """Handshake lato noVNC: parla RFB 3.8 e presenta sicurezza 'None', così il
    browser si collega SENZA password. Al ritorno, il client sta per inviare il
    ClientInit (stesso confine del server)."""
    await client.write(b"RFB 003.008\n")             # ProtocolVersion offerta a noVNC
    cpv = await client.read_exact(12)                # ProtocolVersion scelta dal client
    if not cpv.startswith(b"RFB "):
        raise ConnectionError(f"banner RFB inatteso dal client: {cpv!r}")
    await client.write(bytes([1, 1]))                # 1 tipo di sicurezza: None(1)
    sel = await client.read_exact(1)                 # tipo scelto dal client
    if sel != b"\x01":
        raise ConnectionError(f"il client ha scelto un tipo di sicurezza inatteso: {sel!r}")
    await client.write((0).to_bytes(4, "big"))       # SecurityResult = OK (richiesto in 3.8)
    # Il client ora invierà ClientInit → lo lasciamo passare dal pump.


async def _pump(a: _Stream, b: _Stream) -> None:
    """Copia trasparente bidirezionale finché un lato non chiude."""
    async def one(src: _Stream, dst: _Stream) -> None:
        try:
            while True:
                data = await src.read_some()
                if not data:
                    break
                await dst.write(data)
        except Exception:  # noqa: BLE001 — chiusura/reset normali a fine sessione
            pass

    t1 = asyncio.create_task(one(a, b))
    t2 = asyncio.create_task(one(b, a))
    try:
        await asyncio.wait({t1, t2}, return_when=asyncio.FIRST_COMPLETED)
    finally:
        t1.cancel()
        t2.cancel()


async def proxy_core(client: _Stream, host: str, port: int, password: str) -> None:
    """Nucleo del relay, indipendente dal trasporto del client (WS o TCP nei test).
    Autentica al server reale, presenta 'None' al client, poi diventa trasparente."""
    reader, writer = await asyncio.open_connection(host, port)
    server = _TcpStream(reader, writer)
    try:
        await _auth_verso_server(server, password)
        await _presenta_none_al_client(client)
        await _pump(client, server)
    finally:
        await server.aclose()


# ── Auth dell'handshake (API key o token di sessione operatore) ─────────────

def _autorizzato(api_key: str, token: str) -> bool:
    """Autorizzato se l'API key combacia OPPURE il token di sessione è valido.
    Senza alcuna protezione configurata il relay resta CHIUSO (deny-by-default):
    apre solo con opt-in esplicito DMG_ALLOW_INSECURE=1 (sviluppo)."""
    auth_enabled = _dmg_auth.auth_attiva()
    if not _API_KEY and not auth_enabled:
        return _ALLOW_INSECURE  # nessuna auth configurata → chiuso salvo dev
    if _API_KEY and api_key and _api_key_uguale(api_key, _API_KEY):
        return True
    if auth_enabled and _dmg_auth.valida_token(token) is not None:
        return True
    return False


# ── Endpoint ─────────────────────────────────────────────────────────────────

@router.websocket("/vnc")
async def vnc_relay(ws: WebSocket) -> None:
    api_key = ws.query_params.get("api_key", "") or ws.headers.get("x-api-key", "")
    token = ws.query_params.get("token", "")
    if not _autorizzato(api_key, token):
        await ws.close(code=1008)  # policy violation
        return

    offered = ws.headers.get("sec-websocket-protocol", "")
    subproto = "binary" if "binary" in offered else None
    await ws.accept(subprotocol=subproto)

    client = _WsStream(ws)
    try:
        await proxy_core(client, _VNC_HOST, _VNC_PORT, _VNC_PASSWORD)
    except _EOF:
        pass
    except (OSError, ConnectionError) as e:
        log.warning(f"schermo-live: relay verso {_VNC_HOST}:{_VNC_PORT} interrotto — {e}")
    except Exception as e:  # noqa: BLE001
        log.warning(f"schermo-live: errore relay — {e}", exc_info=True)
    finally:
        await client.aclose()


@router.get("/info")
async def info() -> JSONResponse:
    """Config non sensibile per la UI (nessuna password)."""
    return JSONResponse({
        "host": _VNC_HOST,
        "port": _VNC_PORT,
        "password_configurata": bool(_VNC_PASSWORD),
    })


_VIEWER_HTML = """<!doctype html>
<html lang="it">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Schermo macchina — live</title>
<style>
  html,body{margin:0;height:100%;overflow:hidden}
  body{display:flex;flex-direction:column;height:100vh;background:#20242a;color:#e6e6e6;
       font-family:'Segoe UI',system-ui,sans-serif}
  #bar{flex:0 0 auto;display:flex;align-items:center;gap:.6rem;padding:.35rem .7rem;
       background:#12151a;border-bottom:1px solid #0a0c0f;font-size:.82rem}
  #stato{display:inline-flex;align-items:center;gap:.4rem}
  #dot{width:.6rem;height:.6rem;border-radius:50%;background:#f0b400}
  #dot.ok{background:#22c55e}#dot.ko{background:#ef4444}
  .spacer{flex:1}
  #bar button{padding:.35rem .9rem;border-radius:5px;border:1px solid #3a4048;background:#262b31;
       color:#e6e6e6;font-weight:600;cursor:pointer;font-size:.82rem}
  #bar button.attivo{background:#b91c1c;border-color:#b91c1c}
  #lockhint{font-size:.68rem;color:#f0b400}
  body.controllo #lockhint{display:none}
  /* Schermo a sinistra, pannello tasti di sistema a destra (come sul pannello OP) */
  #stage{flex:1 1 auto;display:flex;min-height:0}
  #screen{flex:1;min-width:0;background:#000}
  #screen canvas{display:block;margin:0 auto}
  #syskeys{flex:0 0 auto;display:flex;align-items:center;justify-content:center;
           padding:10px;background:#171a1e;border-left:2px solid #0a0c0f}
  #menucol .k{width:76px;height:60px}           /* MENU SELECT */
  /* Tasto stile membrana Siemens: antracite di sfondo, tasto grigio chiaro */
  .k{border:1px solid #868d96;border-radius:3px;color:#1b1f24;cursor:pointer;
     font:700 .72rem/1.05 'Segoe UI',system-ui,sans-serif;
     display:flex;align-items:center;justify-content:center;white-space:pre-line;text-align:center;
     background:linear-gradient(180deg,#eef1f4 0%,#d6dce2 55%,#c3cad1 100%);
     box-shadow:inset 0 1px 0 #ffffff, 0 1px 1px rgba(0,0,0,.4)}
  .k:active{background:linear-gradient(180deg,#c3cad1,#d6dce2);
            box-shadow:inset 0 2px 4px rgba(0,0,0,.45);transform:translateY(1px)}
  .sp{background:linear-gradient(180deg,#dfe9ec,#c2d2d6);border-color:#5f8f95;border-top:2px solid #23a2ab}
  body:not(.controllo) .k{opacity:.4;cursor:not-allowed;filter:grayscale(.35)}
</style>
</head>
<body>
  <div id="bar">
    <span id="stato"><span id="dot"></span><span id="stato-txt">connessione…</span></span>
    <span class="spacer"></span>
    <span id="lockhint">🔒 attiva il controllo per usare i tasti</span>
    <span id="modo">sola visione</span>
    <button id="btn-controllo" type="button">Prendi il controllo</button>
  </div>
  <div id="stage">
    <div id="screen"></div>
    <div id="syskeys">
      <div id="menucol"></div>
    </div>
  </div>
  <script type="module" src="/schermo-assets/viewer.js?v=7"></script>
</body>
</html>
"""


@router.get("/viewer", response_class=HTMLResponse)
async def viewer(request: Request) -> HTMLResponse:
    """Pagina viewer noVNC. Protetta dal middleware globale (token/api_key in query).
    Gli script sono same-origin (CSP `script-src 'self'`): nessuno script inline."""
    return HTMLResponse(_VIEWER_HTML)
