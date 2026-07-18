"""
DMG Desk — Backend FastAPI
Avvio:  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
Docs:   http://localhost:8000/docs
"""

# ── Caricamento .env all'avvio (2026-06-25) ────────────────────────────────
# Carica le variabili del file `.env` nella root del progetto IN AMBIENTE,
# prima di qualunque altro import. Necessario perche' i moduli successivi
# (telegram_monitor, api.main, ecc.) leggono `os.environ.get(...)` direttamente.
# Senza load esplicito, l'utente che modifica `.env` non vede effetto al
# restart di uvicorn (uvicorn non legge `.env` di default). Implementazione
# manuale: no dipendenza da python-dotenv.
def _bootstrap_env_from_dotenv():
    import os
    from pathlib import Path
    env_file = Path(__file__).resolve().parent.parent / ".env"
    if not env_file.exists():
        return
    try:
        for raw_line in env_file.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, _, v = line.partition("=")
            k = k.strip()
            v = v.strip().strip('"').strip("'")
            # Non sovrascrivere var gia' settate da CMD/systemd (priorita' a env esplicito)
            if k and k not in os.environ:
                os.environ[k] = v
    except Exception:
        pass  # Non blocca lo startup se .env e' corrotto

_bootstrap_env_from_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import (
    macchina, scaffale, smontati, holder_bussole,
    generatore, analisi_nc, config_router, tools,
    macchina_live, pallet, macchina_invio, report,
    cam_tracker_router,
)
from api.routers import telegram_router
from utils.logger import get_logger

log = get_logger(__name__)

app = FastAPI(
    title="DMG Desk API",
    description="Backend REST per DMG Desk — DMC 160U",
    version="16.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
    redirect_slashes=False,
)

# ── CORS — restrittivo (2026-06-22) ──────────────────────────
# Backend FastAPI sulla porta 8000 serve sia API sia frontend statico
# (`frontend/dist/`), quindi il browser parla SAME-ORIGIN nel funzionamento
# normale di produzione: il CORS in quel caso non si applica.
# Le origini in allow_origins servono per:
#   - dev locale con Vite hot-reload (porta 3000/3001/5173)
#   - eventuali tool esterni / docs interattivi su localhost
# Per esporre il backend a un frontend ospitato su un altro host della LAN
# settare l'env DMG_CORS_ORIGINS=http://host:port (lista separata da virgole).
import os as _os
_cors_env = (_os.environ.get("DMG_CORS_ORIGINS") or "").strip()
if _cors_env:
    _allowed_origins = [o.strip() for o in _cors_env.split(",") if o.strip()]
else:
    _allowed_origins = [
        "http://localhost:8000",   # backend stesso (same-origin + /docs)
        "http://127.0.0.1:8000",
        "http://localhost:3000",   # vite dev server (default Tool Manager)
        "http://localhost:3001",   # vite dev server alt
        "http://localhost:5173",   # vite dev server (default Vite)
    ]
log.info(f"CORS: allow_origins = {_allowed_origins}")

app.add_middleware(
    CORSMiddleware,
    allow_origins=_allowed_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Kill switch globale middleware custom (2026-06-25) ─────────
# In emergenza, settare DMG_DISABLE_CUSTOM_MIDDLEWARE=1 disabilita TUTTI
# i middleware aggiunti dopo CORS (_security_headers, _rate_limit_mutations,
# _body_size_guard, _api_key_guard). Util per bypass durante incidenti
# di produzione che li coinvolgono (deadlock asyncio noti su Windows con
# BaseHTTPMiddleware chain lungo). Il backend torna alla configurazione
# minima: CORS + SPAMiddleware base. Le protezioni di sicurezza che
# rimuove vengono LOGGATE all'avvio.
_DISABLE_CUSTOM_MW = (_os.environ.get("DMG_DISABLE_CUSTOM_MIDDLEWARE", "").strip() == "1")
if _DISABLE_CUSTOM_MW:
    log.warning(
        "*** MIDDLEWARE CUSTOM DISABILITATI via DMG_DISABLE_CUSTOM_MIDDLEWARE=1 ***\n"
        "    - Security headers (XCTO/XFO/CSP): OFF\n"
        "    - Rate limit mutazioni: OFF\n"
        "    - Body size limit: OFF\n"
        "    - API key auth: OFF\n"
        "  Usare solo durante incidenti — riattivare dopo investigation."
    )


# ── DMG Security Middleware — UNIFICATO (2026-06-25) ─────────────────────────
# Sostituisce i 4 middleware separati (security headers, rate limit, body size,
# API key) con UN UNICO middleware pure-ASGI. Motivazione:
#   - Riduce la chain di middleware (BaseHTTPMiddleware su Starlette ha
#     deadlock noti con chain lungo + early-return, vedi #1438).
#   - Pure-ASGI non costruisce Response intermedie -> immune ai bug di
#     stream/lifecycle che hanno causato l'incidente del 2026-06-25.
#   - Logica identica ai 4 middleware originali, registrata via add_middleware
#     (pattern Starlette standard) invece che @app.middleware("http").
#
# Kill switch globale: DMG_DISABLE_CUSTOM_MIDDLEWARE=1 -> middleware no-op
# (ritorna solo all'app sottostante, niente check, niente header).

import time as _time
from collections import deque as _deque

# Config security headers
_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
    "font-src 'self' https://fonts.gstatic.com data:; "
    "img-src 'self' data: blob:; "
    "connect-src 'self'; "
    "frame-ancestors 'self'; "
    "base-uri 'self'; "
    "form-action 'self'"
)
_SEC_HEADERS_STATIC = [
    (b"x-content-type-options", b"nosniff"),
    (b"x-frame-options", b"SAMEORIGIN"),
    (b"referrer-policy", b"strict-origin-when-cross-origin"),
    (b"permissions-policy", b"geolocation=(), microphone=(), camera=()"),
]
# Config rate limit
_RL_WINDOW_SEC = int(_os.environ.get("DMG_RL_WINDOW_SEC", "60"))
_RL_MAX_REQ    = int(_os.environ.get("DMG_RL_MAX_REQ", "120"))
_RL_WHITELIST_LOCAL = (_os.environ.get("DMG_RL_WHITELIST_LOCAL", "1").strip() != "0")
_RL_LOCAL_IPS = {"127.0.0.1", "::1", "localhost"}
_rl_state: dict[str, _deque] = {}
_RL_METHODS = {b"POST", b"PUT", b"DELETE", b"PATCH"}
# Config body size
_MAX_UPLOAD_MB = int(_os.environ.get("DMG_MAX_UPLOAD_MB", "50"))
_MAX_UPLOAD_BYTES = _MAX_UPLOAD_MB * 1024 * 1024
# Config API key + autenticazione operatori (PIN)
from api import auth as _dmg_auth
from api import ip_allowlist as _ip_allow
_API_KEY = (_os.environ.get("DMG_API_KEY") or "").strip()

import hmac as _hmac


def _api_key_uguale(fornita: str, attesa: str) -> bool:
    """Confronto a tempo costante e robusto ai non-ASCII (autofill del browser):
    compara i byte UTF-8. `hmac.compare_digest` su str non-ASCII solleva TypeError
    → qui diventerebbe un 500 invece di un 401; lo trattiamo come 'non combacia'."""
    try:
        return _hmac.compare_digest((fornita or "").encode("utf-8"),
                                    (attesa or "").encode("utf-8"))
    except Exception:
        return False


# Deny-by-default: senza alcuna auth configurata (né master key né PIN) le API
# restano CHIUSE, salvo opt-in esplicito per lo sviluppo locale.
_ALLOW_INSECURE = (_os.environ.get("DMG_ALLOW_INSECURE", "").strip() == "1")
# Dietro reverse proxy (nginx/Caddy) il vero IP client è in X-Forwarded-For.
# Attivare SOLO se il backend è raggiungibile ESCLUSIVAMENTE tramite il proxy,
# altrimenti l'header è falsificabile e il rate-limit aggirabile.
_TRUST_PROXY = (_os.environ.get("DMG_TRUST_PROXY", "").strip() == "1")
# Path pubblici: raggiungibili SENZA credenziali anche ad auth attiva.
# Includono gli endpoint necessari a fare il login stesso e il reset admin
# (quest'ultimo si protegge da solo con la master key DMG_API_KEY).
_AUTH_PUBLIC_PATHS = {
    "/", "/health", "/docs", "/redoc", "/openapi.json",
    "/api/auth/status", "/api/auth/login", "/api/auth/login-pin", "/api/auth/operatori",
    "/api/auth/admin/reset-pin",
}
# Endpoint del flusso di LOGIN raggiungibili da QUALSIASI IP anche col filtro IP
# attivo: servono a fare login da un PC non ancora autorizzato (che così vede solo
# la pagina di login). Tutte le altre API dati sono filtrate per IP.
_IP_LOGIN_PATHS = {
    "/api/auth/status", "/api/auth/login", "/api/auth/login-pin", "/api/auth/operatori",
}

if _API_KEY:
    log.info(f"API key auth: ATTIVA (lunghezza chiave: {len(_API_KEY)})")
else:
    log.warning("API key auth: DISATTIVA — DMG_API_KEY non settata. "
                "Backend accessibile senza autenticazione (modalita' dev).")

if _dmg_auth.auth_attiva():
    log.info("Autenticazione operatori (PIN): ATTIVA (DMG_AUTH_ENABLED=1)")
else:
    log.warning("Autenticazione operatori (PIN): DISATTIVA — DMG_AUTH_ENABLED non =1. "
                "Nessun login richiesto (modalita' dev).")

# Deny-by-default: stato quando NESSUNA auth è configurata.
if not _API_KEY and not _dmg_auth.auth_attiva():
    if _ALLOW_INSECURE:
        log.warning("*** SICUREZZA: nessuna auth configurata + DMG_ALLOW_INSECURE=1 "
                    "→ API APERTE sulla LAN. Usare SOLO in sviluppo. ***")
    else:
        log.warning("SICUREZZA: nessuna auth configurata → API CHIUSE (deny-by-default). "
                    "Configurare DMG_AUTH_ENABLED/DMG_API_KEY, oppure DMG_ALLOW_INSECURE=1 per lo sviluppo.")


def _build_error_response(status: int, detail: str, extra_headers: list = None) -> tuple:
    """Costruisce response JSON ASGI per errori 4xx/5xx."""
    import json as _json
    body = _json.dumps({"detail": detail}).encode("utf-8")
    headers = [
        (b"content-type", b"application/json; charset=utf-8"),
        (b"content-length", str(len(body)).encode()),
    ]
    if extra_headers:
        headers.extend(extra_headers)
    return status, headers, body


class DMGSecurityMiddleware:
    """Middleware unificato di sicurezza in pure-ASGI.

    Esegue, IN ORDINE, su ogni richiesta HTTP:
      1. Body size check (Content-Length > MAX_UPLOAD_BYTES -> 413)
      2. API key check (whitelist + header/query) -> 401 se manca
      3. Rate limit (POST/PUT/DELETE/PATCH per IP non whitelist) -> 429
      4. Forward all'app downstream
      5. Iniezione security headers nella response

    Tutto in un singolo `__call__` ASGI -> niente Response intermedie,
    niente call_next, niente bug Starlette #1438.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        # Lascia passare lifespan/websocket senza modifiche
        if scope["type"] != "http":
            return await self.app(scope, receive, send)

        # Kill switch globale: bypass totale, niente check
        if _DISABLE_CUSTOM_MW:
            return await self.app(scope, receive, send)

        method  = scope["method"].encode() if isinstance(scope["method"], str) else scope["method"]
        path    = scope["path"]
        headers = dict(scope.get("headers") or [])
        client  = scope.get("client") or ("unknown", 0)
        ip      = client[0] if client else "unknown"
        # Dietro reverse proxy fidato, il vero IP client è in X-Forwarded-For
        # (il primo della lista). Opt-in: senza proxy l'header è falsificabile.
        if _TRUST_PROXY:
            _xff = headers.get(b"x-forwarded-for", b"").decode()
            if _xff:
                ip = _xff.split(",")[0].strip()

        # ── 0. IP allowlist (difesa in profondità: solo PC noti usano le API) ──
        # La SPA e il flusso di LOGIN restano visibili da qualsiasi IP (un PC non
        # autorizzato vede solo la pagina di login); tutte le ALTRE API dati sono
        # bloccate se l'IP non è ammesso. Gli endpoint di gestione allowlist sono
        # esentati (l'admin non si chiude mai fuori). Loopback sempre ammesso
        # (dentro is_consentito). I tentativi bloccati vengono registrati.
        _ip_filtrato = (
            path.startswith("/api/")
            and path not in _IP_LOGIN_PATHS
            and not path.startswith("/api/auth/admin/ip-allowlist")
        )
        if _ip_filtrato and not _ip_allow.is_consentito(ip):
            _ip_allow.registra_tentativo(ip, path)
            log.warning(f"ip-allowlist: bloccato {ip} su {path}")
            status, hdrs, body = _build_error_response(
                403, "Accesso non consentito da questo dispositivo")
            await send({"type": "http.response.start", "status": status, "headers": hdrs})
            await send({"type": "http.response.body", "body": body})
            return

        # ── 1. Body size ─────────────────────────────────────
        cl = headers.get(b"content-length", b"").decode()
        if cl.isdigit() and int(cl) > _MAX_UPLOAD_BYTES:
            log.warning(f"body_size: rifiutata richiesta {method.decode()} {path} "
                        f"da {ip} — Content-Length {int(cl)/1024/1024:.1f}MB > "
                        f"limite {_MAX_UPLOAD_MB}MB")
            status, hdrs, body = _build_error_response(
                413, f"Payload troppo grande — limite {_MAX_UPLOAD_MB}MB")
            await send({"type": "http.response.start", "status": status, "headers": hdrs})
            await send({"type": "http.response.body", "body": body})
            return

        # ── 2. Autenticazione (API key servizi e/o sessione PIN operatori) ──
        # Richiesta protetta se è configurata la master key OPPURE se
        # l'autenticazione operatori è attiva. È autorizzata da UNA delle due:
        #   a) X-API-Key valida  → client di servizio (cam_tracker, self-call)
        #   b) token di sessione → operatore che ha fatto login col PIN
        _auth_enabled = _dmg_auth.auth_attiva()
        need_auth = (
            path.startswith("/api/")
            and path not in _AUTH_PUBLIC_PATHS
            and not path.startswith("/assets/")
            and not path.startswith("/favicon")
            and method != b"OPTIONS"
        )
        if need_auth:
            if not (_API_KEY or _auth_enabled):
                # Nessuna auth configurata → deny-by-default: API CHIUSE.
                # Escape hatch esplicito per lo sviluppo: DMG_ALLOW_INSECURE=1.
                if not _ALLOW_INSECURE:
                    log.warning(f"auth: API chiuse (deny-by-default, nessuna auth "
                                f"configurata) — {path} da {ip}")
                    status, hdrs, body = _build_error_response(
                        503, "Autenticazione non configurata sul server (deny-by-default). "
                             "Impostare DMG_AUTH_ENABLED/DMG_API_KEY.")
                    await send({"type": "http.response.start", "status": status, "headers": hdrs})
                    await send({"type": "http.response.body", "body": body})
                    return
                # else: modalità dev insicura esplicita → lascia passare
            else:
                # a) API key: header X-API-Key oppure query string ?api_key=
                api_ok = False
                if _API_KEY:
                    provided = headers.get(b"x-api-key", b"").decode()
                    if not provided:
                        qs = scope.get("query_string", b"").decode()
                        for pair in qs.split("&"):
                            if pair.startswith("api_key="):
                                provided = pair[len("api_key="):]
                                break
                    api_ok = _api_key_uguale(provided, _API_KEY)

                # b) token di sessione operatore. Fonti, in ordine:
                #    Authorization: Bearer <t>  → fetch API (interceptor)
                #    X-Session-Token: <t>       → header alternativo
                #    ?token=<t> in query string → link diretti <img>/<a>
                sess_ok = False
                if _auth_enabled and not api_ok:
                    tok = ""
                    _authz = headers.get(b"authorization", b"").decode()
                    if _authz.lower().startswith("bearer "):
                        tok = _authz[7:].strip()
                    if not tok:
                        tok = headers.get(b"x-session-token", b"").decode()
                    if not tok:
                        qs = scope.get("query_string", b"").decode()
                        for pair in qs.split("&"):
                            if pair.startswith("token="):
                                from urllib.parse import unquote as _unq
                                tok = _unq(pair[len("token="):])
                                break
                    sess_ok = _dmg_auth.valida_token(tok) is not None

                if not (api_ok or sess_ok):
                    log.warning(f"auth: rifiutata richiesta a {path} da {ip}")
                    status, hdrs, body = _build_error_response(
                        401, "Unauthorized — login operatore o X-API-Key richiesto")
                    await send({"type": "http.response.start", "status": status, "headers": hdrs})
                    await send({"type": "http.response.body", "body": body})
                    return

        # ── 3. Rate limit (POST/PUT/DELETE/PATCH, no localhost) ──
        if method in _RL_METHODS and path.startswith("/api/"):
            if not (_RL_WHITELIST_LOCAL and ip in _RL_LOCAL_IPS):
                now = _time.monotonic()
                window_start = now - _RL_WINDOW_SEC
                bucket = _rl_state.setdefault(ip, _deque())
                while bucket and bucket[0] < window_start:
                    bucket.popleft()
                if len(bucket) >= _RL_MAX_REQ:
                    log.warning(f"rate_limit: bloccata mutazione da {ip} "
                                f"({len(bucket)} richieste in {_RL_WINDOW_SEC}s)")
                    status, hdrs, body = _build_error_response(
                        429,
                        f"Troppe richieste — limite {_RL_MAX_REQ} mutazioni / {_RL_WINDOW_SEC}s",
                        extra_headers=[(b"retry-after", str(_RL_WINDOW_SEC).encode())],
                    )
                    await send({"type": "http.response.start", "status": status, "headers": hdrs})
                    await send({"type": "http.response.body", "body": body})
                    return
                bucket.append(now)

        # ── 4+5. Forward + inietta security headers nella response ──
        # Wrap `send` per intercettare http.response.start e aggiungere
        # gli header di sicurezza prima che vengano emessi al client.
        async def send_wrapper(message):
            if message["type"] == "http.response.start":
                msg = dict(message)
                hdrs = list(msg.get("headers") or [])
                existing_keys = {h[0].lower() for h in hdrs}
                for k, v in _SEC_HEADERS_STATIC:
                    if k not in existing_keys:
                        hdrs.append((k, v))
                # CSP SOLO su risposte HTML (rispetta JSON e file binari)
                ctype = b""
                for k, v in hdrs:
                    if k.lower() == b"content-type":
                        ctype = v
                        break
                if ctype.startswith(b"text/html") and b"content-security-policy" not in existing_keys:
                    hdrs.append((b"content-security-policy", _CSP.encode()))
                msg["headers"] = hdrs
                await send(msg)
            else:
                await send(message)

        await self.app(scope, receive, send_wrapper)


# Registrazione: usa add_middleware (pattern Starlette standard, no decorator).
app.add_middleware(DMGSecurityMiddleware)


# ── Router esistenti ───────────────────────────────────────
app.include_router(macchina.router,       prefix="/api/macchina",       tags=["Utensili in Macchina"])
app.include_router(scaffale.router,       prefix="/api/scaffale",       tags=["Scaffale"])
app.include_router(smontati.router,       prefix="/api/smontati",       tags=["Smontati"])
app.include_router(holder_bussole.router, prefix="/api/holder-bussole", tags=["Holder & Bussole"])
app.include_router(generatore.router,     prefix="/api/generatore",     tags=["Generatore Codici"])
app.include_router(analisi_nc.router,     prefix="/api/analisi-nc",     tags=["Analisi NC"])
app.include_router(config_router.router,  prefix="/api/config",         tags=["Configurazione"])
app.include_router(tools.router,          prefix="/api/tools",          tags=["TOA Sync"])

# ── Router nuovi DMG Desk ──────────────────────────────────
app.include_router(macchina_live.router,  prefix="/api/macchina-live",  tags=["Stato Macchina Live"])
app.include_router(pallet.router,         prefix="/api/pallet",         tags=["Gestione Pallet"])
app.include_router(macchina_invio.router,  prefix="/api/macchina-invio",  tags=["Invio Macchina"])
from api.routers import progetti
app.include_router(progetti.router,       prefix="/api/progetti",         tags=["Progetti WorkTrack"])
app.include_router(report.router,         prefix="/api/report",           tags=["Report & Statistiche"])
from api.routers import allegati
app.include_router(allegati.router)

# ── CAM Tracker ───────────────────────────────────────────────────────────────
app.include_router(cam_tracker_router.router, prefix="/api/cam-tracker", tags=["CAM Tracker"])

# ── Turno snapshot ─────────────────────────────────────────────────────────────
from api.routers import turno as turno_router
app.include_router(turno_router.router, prefix="/api/turno", tags=["Turno"])

# ── Telegram Monitor ───────────────────────────────────────────────────────────
app.include_router(telegram_router.router, prefix="/api/telegram", tags=["Telegram"])

# ── Main Sync ─────────────────────────────────────────────────────────────────
from api.routers import main_sync as main_sync_router
app.include_router(main_sync_router.router)

# ── Backup ────────────────────────────────────────────────────────────────────
from api.routers import backup as backup_router
app.include_router(backup_router.router)

from api.routers import tool_history as tool_history_router
app.include_router(tool_history_router.router)

from api.routers import step_client as step_client_router
app.include_router(step_client_router.router)

from api.routers import pallet_history as pallet_history_router
app.include_router(pallet_history_router.router)

# ── NC Scanner ────────────────────────────────────────────────────────────────
from api.routers import nc_scanner as nc_scanner_router
app.include_router(nc_scanner_router.router)

# ── Autenticazione operatori (PIN) ──────────────────────────────────────────────
from api.routers import auth_router
app.include_router(auth_router.router)

# ── Parametri CAM da Cimatron (estrattore su CAM35) — additivo ──────────────────
from api.routers import cam_params as cam_params_router
app.include_router(cam_params_router.router, prefix="/api/cam-params",
                   tags=["Parametri CAM"])

# ── Schermo live macchina (relay VNC → noVNC) ───────────────────────────────────
from api.routers import schermo_live as schermo_live_router
app.include_router(schermo_live_router.router, prefix="/api/schermo",
                   tags=["Schermo Live"])


@app.on_event("startup")
async def startup():
    log.info("DMG Desk API v16.0 avviata — http://0.0.0.0:8000")

    # ── Bootstrap admin operatori ─────────────────────────────────────────
    # Se nessun operatore è admin, promuove il primo registrato → così il primo
    # operatore (es. op1) diventa admin in autonomia, senza master key.
    try:
        from api import auth as _auth_boot
        _promosso = _auth_boot.assicura_admin_bootstrap()
        if _promosso:
            log.info(f"Bootstrap admin: operatore '{_promosso}' promosso ad admin")
    except Exception as _e:
        log.warning(f"Bootstrap admin fallito: {_e}")

    # ── Migrazione v2 one-shot (pallet-logic-v2, estensione 5) ─────────────
    # Riconcilia stati pallet incoerenti dovuti al bug pre-v2 (es. pallet
    # `grezzo` con programmi `completato`). Eseguita una sola volta dopo il
    # deploy del v2; flag `migrazione_v2_eseguita` salvato per skip successivi.
    try:
        from database.db_handler import carica_configurazione
        from api.routers.progetti import _load_progetti, _save_progetti
        from api.routers.pallet import _load as _load_pallet, _save as _save_pallet
        from api.routers.macchina_live import _riconcilia_pallet_se_incoerente

        _cfg = carica_configurazione()
        _proj = _load_progetti(_cfg)
        _pal_data = _load_pallet(_cfg)

        if not _pal_data.get("migrazione_v2_eseguita"):
            log.info("Migrazione v2: avvio riconciliazione stati pallet (one-shot)")
            modificati = []
            projects = _proj.get("progetti", []) or _proj.get("projects", [])
            for pal in _pal_data.get("pallet", []):
                old = pal.get("stato")
                # Riconcilia senza considerare timeout (passiamo stato_pgm=None)
                new_stato = _riconcilia_pallet_se_incoerente(pal, projects)
                if new_stato:
                    modificati.append({
                        "pallet": pal.get("numero"),
                        "old": old, "new": new_stato
                    })
            _pal_data["migrazione_v2_eseguita"] = True
            _pal_data["migrazione_v2_ts"] = __import__('datetime').datetime.now().isoformat(timespec="seconds")
            _save_pallet(_cfg, _pal_data)
            if modificati:
                log.info(f"Migrazione v2 completata: {len(modificati)} pallet riconciliati")
                for m in modificati:
                    log.info(f"  Pallet {m['pallet']}: {m['old']} → {m['new']}")
            else:
                log.info("Migrazione v2 completata: nessun pallet da riconciliare")
        else:
            log.debug("Migrazione v2 già eseguita, skip")

        # ── Migrazione v2.3 one-shot — Pulizia programmi orfani + tipoGruppo ──
        # Q4: rimuove programmi 'da_fare' fantasma e ricalcola tipoGruppo.
        # Flag separato dalla migrazione pallet così possiamo deployare
        # indipendentemente.
        if not _pal_data.get("migrazione_v23_eseguita"):
            log.info("Migrazione v2.3: pulizia orfani + ricalcolo tipoGruppo")
            try:
                from api.routers.nc_scanner import scansiona_directory, _mtime_cache
                _mtime_cache.clear()  # forza rilettura completa per ricalcolare tipoGruppo
                result = scansiona_directory(_cfg)
                log.info(
                    f"Migrazione v2.3 completata: "
                    f"{result.get('aggiornati', 0)} programmi aggiornati, "
                    f"{result.get('rimossi_orfani', 0)} orfani rimossi"
                )
                # Riserva il flag SOLO se la scansione è andata bene
                if result.get("ok"):
                    _pal_data["migrazione_v23_eseguita"] = True
                    _pal_data["migrazione_v23_ts"] = __import__('datetime').datetime.now().isoformat(timespec="seconds")
                    _save_pallet(_cfg, _pal_data)
            except Exception as _e2:
                log.error(f"Migrazione v2.3 fallita: {_e2}", exc_info=True)
        else:
            log.debug("Migrazione v2.3 già eseguita, skip")

        # ── Migrazione v2.4 one-shot — Riparazione bug riconciliatore ─────────
        # Il riconciliatore v2.1 aveva una regola "grezzo + completato → guasto"
        # troppo aggressiva che ha rovinato pallet legittimamente grezzo dopo
        # rigenerazione MAIN multi-fase.
        # Riparazione: se un pallet è 'guasto' ma il MAIN snapshot ha programmi
        # in_main TUTTI con _utensili_visti vuoti (mai eseguiti) → ripristina
        # a 'grezzo'.
        if not _pal_data.get("migrazione_v24_eseguita"):
            log.info("Migrazione v2.4: riparazione pallet guastati erroneamente dal riconciliatore")
            riparati = []
            projects = _proj.get("progetti", []) or _proj.get("projects", [])
            for pal in _pal_data.get("pallet", []):
                if (pal.get("stato") or "").lower() != "guasto":
                    continue
                pid = pal.get("progetto_id")
                if not pid:
                    continue
                proj = next((p for p in projects if p.get("id") == pid), None)
                if not proj:
                    continue
                snap = proj.get("main_snapshot") or {}
                main_set = set(snap.get("main_programmi") or [])
                if not main_set:
                    continue

                def _norm(fn):
                    n = (fn or "").upper().strip()
                    if not n.endswith(".MPF"): n += ".MPF"
                    return n

                # Trova programmi del progetto che sono nel MAIN
                pgm_in_main_attivi = []
                for s in proj.get("steps", []):
                    for t in s.get("tasks", []):
                        if t.get("text", "").strip().lower() != "fresatura":
                            continue
                        for pgm in t.get("programs", []):
                            if _norm(pgm.get("filename")) in main_set:
                                pgm_in_main_attivi.append(pgm)

                if not pgm_in_main_attivi:
                    continue

                # Tutti i programmi del nuovo MAIN sono in_main con _utensili_visti vuoti?
                # Allora il MAIN è stato rigenerato e nessuno l'ha ancora eseguito.
                # Pallet doveva essere grezzo, non guasto.
                tutti_in_main_freschi = all(
                    pgm.get("stato") == "in_main"
                    and not pgm.get("_utensili_visti")
                    and not pgm.get("tempoInizio")
                    for pgm in pgm_in_main_attivi
                )

                if tutti_in_main_freschi:
                    pal["stato"] = "grezzo"
                    pal["aggiornato"] = __import__('datetime').datetime.now().isoformat(timespec="seconds")
                    riparati.append({
                        "pallet": pal.get("numero"),
                        "progetto": proj.get("name"),
                    })

            _pal_data["migrazione_v24_eseguita"] = True
            _pal_data["migrazione_v24_ts"] = __import__('datetime').datetime.now().isoformat(timespec="seconds")
            _save_pallet(_cfg, _pal_data)

            if riparati:
                log.info(f"Migrazione v2.4 completata: {len(riparati)} pallet riparati guasto→grezzo")
                for r in riparati:
                    log.info(f"  Pallet {r['pallet']} ({r['progetto']}): guasto → grezzo")
            else:
                log.info("Migrazione v2.4 completata: nessun pallet da riparare")
        else:
            log.debug("Migrazione v2.4 già eseguita, skip")
    except Exception as _e:
        log.error(f"Migrazione v2 fallita: {_e}", exc_info=True)
        # Non bloccare lo startup: la migrazione si può rilanciare al riavvio successivo

    # ── Scheduler snapshot turno ───────────────────────────────────────────
    import asyncio as _asyncio
    from api.turno_snapshot import _scheduler_loop
    _asyncio.create_task(_scheduler_loop())
    log.info("Scheduler snapshot turno avviato (07:30 notte / 16:30 giorno)")

    # ── Poller macchina interno ────────────────────────────────────────────
    # Legge OpcUaLegacy.log ogni 5s e aggiorna stati programmi/pallet.
    # Sostituisce le chiamate dal frontend — un solo scrittore, nessuna race condition.
    async def _machine_poller_loop():
        from api.routers.macchina_live import aggiorna_stati_da_log as _aggiorna
        import asyncio as _aio
        _log = __import__('logging').getLogger("machine_poller")
        _log.info("Machine poller interno avviato (ogni 5s)")
        await _aio.sleep(2)  # attendi startup completo prima del primo tick
        while True:
            try:
                await _aio.wait_for(_aggiorna(), timeout=10)
            except _aio.TimeoutError:
                _log.warning("Machine poller: timeout 10s sul tick")
            except Exception as _e:
                # WARNING con traceback (era DEBUG: un tick che moriva
                # sistematicamente non lasciava alcuna traccia in produzione)
                _log.warning(f"Machine poller: {_e}", exc_info=True)
            await _aio.sleep(5)

    _asyncio.create_task(_machine_poller_loop())
    log.info("Machine poller interno avviato — frontend non deve più chiamare aggiorna-stati-da-log")

    # ── Main sync job — ogni 5 minuti ─────────────────────────────────────
    async def _main_sync_loop():
        from api.routers.main_sync import job_sync_main_log
        import asyncio as _aio
        _log = __import__('logging').getLogger("main_sync")
        _log.info("Main sync job avviato (ogni 5 minuti)")
        await _aio.sleep(30)  # attendi avvio completo prima del primo sync
        while True:
            try:
                await job_sync_main_log()
                # Dopo ogni sync, ricalcola stati pallet
                from api.routers.pallet import ricalcola_stati_pallet as _ricalcola
                await _ricalcola()
            except Exception as _e:
                _log.warning(f"Main sync error: {_e}")
            await _aio.sleep(300)  # 5 minuti

    _asyncio.create_task(_main_sync_loop())
    log.info("Main sync job avviato (MAIN+LOG → stati programmi, ogni 5 min)")

    # ── Backup giornaliero ────────────────────────────────────────────────
    async def _backup_loop():
        from api.routers.backup import job_backup_giornaliero
        import asyncio as _aio
        _log = __import__('logging').getLogger("backup")
        _log.info("Backup job avviato (ogni 24h, prima esecuzione tra 60s)")
        await _aio.sleep(60)
        while True:
            try:
                await job_backup_giornaliero()
            except Exception as _e:
                _log.warning(f"Backup error: {_e}")
            await _aio.sleep(86400)  # 24 ore

    _asyncio.create_task(_backup_loop())
    log.info("Backup giornaliero avviato")

    # ── Backup notturno archivi (cartelle ELT su H:) ──────────────────────
    # Schedulato all'01:00 ora locale. Se H: non raggiungibile -> retry alle 03:00,
    # poi rinuncia fino al giorno successivo.
    # Kill switch: DMG_DISABLE_BACKUP_NOTTURNO=1 per disabilitarlo (rotture imminenti).
    async def _backup_notturno_archivi_loop():
        import asyncio as _aio
        import os as _os
        from datetime import datetime as _dt, timedelta as _td
        from api.routers.backup import job_backup_notturno_archivi
        _log = __import__('logging').getLogger("backup")

        if _os.environ.get("DMG_DISABLE_BACKUP_NOTTURNO", "").strip() == "1":
            _log.warning("Backup notturno archivi DISATTIVATO via DMG_DISABLE_BACKUP_NOTTURNO=1")
            return

        # Orari schedulati nella giornata: primary 01:00, retry 03:00
        ORE_SCHEDULATE = [(1, 0), (3, 0)]

        def _secondi_fino_a(hh: int, mm: int) -> float:
            now = _dt.now()
            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
            if target <= now:
                target += _td(days=1)
            return (target - now).total_seconds()

        _log.info("Backup notturno archivi avviato (primary 01:00, retry 03:00)")

        while True:
            try:
                # Trova prossimo slot (01:00 di oggi/domani, oppure 03:00 di oggi
                # se siamo passati le 01:00 ma non ancora le 03:00)
                now = _dt.now()
                slot_oggi_primary = now.replace(hour=ORE_SCHEDULATE[0][0], minute=ORE_SCHEDULATE[0][1], second=0, microsecond=0)
                slot_oggi_retry = now.replace(hour=ORE_SCHEDULATE[1][0], minute=ORE_SCHEDULATE[1][1], second=0, microsecond=0)

                if now < slot_oggi_primary:
                    sleep_sec = (slot_oggi_primary - now).total_seconds()
                    is_retry = False
                elif now < slot_oggi_retry:
                    sleep_sec = (slot_oggi_retry - now).total_seconds()
                    is_retry = True
                else:
                    # Dopo 03:00 -> domani 01:00
                    sleep_sec = _secondi_fino_a(*ORE_SCHEDULATE[0])
                    is_retry = False

                hours = int(sleep_sec // 3600)
                mins = int((sleep_sec % 3600) // 60)
                _log.info(
                    f"Backup notturno: prossima esecuzione fra {hours}h{mins:02d}m "
                    f"({'retry' if is_retry else 'primary'})"
                )
                await _aio.sleep(sleep_sec)

                # Esegui
                _log.info(f"Backup notturno: esecuzione {'(retry)' if is_retry else '(primary)'} in corso...")
                try:
                    result = await job_backup_notturno_archivi()
                    if result and result.get("ok"):
                        _log.info(
                            f"Backup notturno OK: {result.get('progetti_processati', 0)} progetti, "
                            f"{result.get('file_copiati', 0)} file"
                        )
                        # Notifica Telegram se attiva.
                        # FIX 2026-07-02: `invia_messaggio_telegram` non è mai
                        # esistita — l'ImportError era inghiottito dal pass e la
                        # notifica non è mai partita. Canale reale: TelegramNotifier
                        # via _notifica_telegram (best-effort, non solleva).
                        from api.routers.backup import _notifica_telegram
                        msg = (
                            f"✅ Backup notturno DMG Desk completato\n"
                            f"📁 Progetti: {result.get('progetti_processati', 0)}\n"
                            f"📄 File copiati: {result.get('file_copiati', 0)}\n"
                            f"⏱ Durata: {result.get('durata_sec', 0)}s\n"
                            f"⚠ Errori: {result.get('errori', 0)}"
                        )
                        await _notifica_telegram(msg)
                    else:
                        _log.warning(f"Backup notturno: risultato negativo: {result}")
                except RuntimeError as e:
                    # H: non raggiungibile
                    _log.warning(f"Backup notturno SKIP (dest non raggiungibile): {e}")
                except Exception as e:
                    _log.exception(f"Backup notturno: errore inatteso: {e}")
            except Exception as e:
                _log.exception(f"Backup notturno loop: errore generico: {e}")
                # Evita tight loop in caso di errori ripetuti
                await _aio.sleep(300)

    _asyncio.create_task(_backup_notturno_archivi_loop())

    # ── NC Scanner — ogni 60 secondi ──────────────────────────────────────
    async def _nc_scanner_loop():
        from api.routers.nc_scanner import job_nc_scanner
        import asyncio as _aio
        _log = __import__('logging').getLogger("nc_scanner")
        _log.info("NC Scanner loop avviato (tick ogni 60 s, primo dopo 45 s)")
        await _aio.sleep(45)  # attendi avvio completo
        tick_n = 0
        while True:
            tick_n += 1
            try:
                await job_nc_scanner()
            except Exception as _e:
                # exc_info=True per traceback completo: prima dei fix 2026-05-28
                # un crash silenzioso poteva ammazzare il task senza traccia.
                _log.warning(f"NC Scanner tick #{tick_n} eccezione: {_e}", exc_info=True)
            await _aio.sleep(60)  # 1 minuto fra l'inizio di due tick consecutivi

    _asyncio.create_task(_nc_scanner_loop())
    log.info("NC Scanner avviato (scansione directory NC ogni 60 s)")

    # Pulizia file .tmp orfani da atomic write interrotti (crash/spegnimento)
    from pathlib import Path as _P
    from database.db_handler import carica_configurazione as _cfg
    try:
        config = _cfg()
        base = (config.get("tools_toa_folder") or ".").strip()
        cleaned = 0
        for tmp in _P(base).glob("*.tmp"):
            try: tmp.unlink(); cleaned += 1
            except Exception: pass
        if cleaned:
            log.info(f"Rimossi {cleaned} file .tmp orfani da {base}")
    except Exception:
        pass  # non bloccare lo startup se la config non è disponibile

    # ── Check pallet completati ──────────────────────────────────────────────
    try:
        from api.routers.pallet import check_pallet_completati as _check_pallet
        _cfg_pallet = _cfg()
        _n = _check_pallet(_cfg_pallet)
        if _n:
            log.info(f"Startup: {_n} pallet portati a FINITO (tutti i programmi completati)")
    except Exception as _e:
        log.warning(f"Startup check pallet: {_e}")

    # ── Telegram Monitor ──────────────────────────────────────────────────
    # KILL SWITCH 2026-06-25: disattivare via env DMG_DISABLE_TELEGRAM=1
    # quando la rete aziendale blocca/intermittente verso api.telegram.org —
    # le ConnectionResetError ricorrenti saturano il ProactorEventLoop su
    # Windows (handle non chiusi in callback _call_connection_lost) e dopo
    # poche ore mandano in blocco l'intero backend (event loop affamato di
    # callback non risolti). Riattiva quando la connessione e' stabile.
    if (_os.environ.get("DMG_DISABLE_TELEGRAM", "").strip() == "1"):
        log.warning("Telegram Monitor DISATTIVATO via env DMG_DISABLE_TELEGRAM=1")
        return  # Fine startup_event — non parte ne monitor ne listener

    import asyncio as _asyncio
    from telegram_monitor.config import load_telegram_config
    from telegram_monitor.notifier import TelegramNotifier
    from telegram_monitor.monitor import MachineMonitor
    from telegram_monitor.bot_listener import BotListener
    from api.routers.macchina_live import get_stato_macchina as _get_stato
    from api.routers.report import _load_log as _load_report_log, _log_path as _report_log_path
    from database.db_handler import carica_configurazione as _cfg_tg

    async def _get_report():
        """Ritorna dati report per daily summary / comando /summary."""
        import json
        _cfg = _cfg_tg()
        p = _report_log_path(_cfg)
        try:
            raw = json.loads(p.read_text(encoding="utf-8")) if p.exists() else {}
        except Exception:
            raw = {}
        return raw

    tg_cfg = load_telegram_config()
    if tg_cfg:
        _notifier = TelegramNotifier(token=tg_cfg["token"], chat_id=tg_cfg["chat_id"])

        # Istanza monitor globale — esposta per notify_batch da altri router
        from telegram_monitor import monitor as _tg_monitor_module
        _monitor = MachineMonitor(
            notifier        = _notifier,
            get_stato_fn    = _get_stato,
            get_report_fn   = _get_report,
            interval_sec    = tg_cfg["interval_sec"],
            stale_alert_sec = tg_cfg["stale_alert_sec"],
        )
        _tg_monitor_module._instance = _monitor   # rende accessibile da altri moduli

        from api.routers.macchina_live import get_live_context as _get_live_context

        _listener = BotListener(
            token                = tg_cfg["token"],
            chat_id              = tg_cfg["chat_id"],
            get_stato_fn         = _get_stato,
            get_live_context_fn  = _get_live_context,
            get_report_fn        = _get_report,
        )

        _asyncio.create_task(_monitor.run())
        _asyncio.create_task(_listener.run())
        log.info(f"Telegram Monitor + BotListener avviati — check ogni {tg_cfg['interval_sec']}s")
    else:
        log.warning(
            "Telegram Monitor disabilitato — "
            "aggiungi TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID nel file .env"
        )


# ── Exception handler globale ─────────────────────────────────────────────────
from fastapi import Request as _Request
from fastapi.responses import JSONResponse as _JSONResponse

@app.exception_handler(Exception)
async def unhandled_exception_handler(request: _Request, exc: Exception):
    """Logga le eccezioni non gestite in errors.log invece di lasciarle silenziose."""
    log.error(
        f"Eccezione non gestita: {request.method} {request.url.path} — {type(exc).__name__}: {exc}",
        exc_info=True,
    )
    return _JSONResponse(
        status_code=500,
        content={"detail": f"Errore interno: {type(exc).__name__}", "path": str(request.url.path)},
    )


# ── Serve frontend React ──────────────────────────────────────────────────
from pathlib import Path as _Path
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.staticfiles import NotModifiedResponse

_FRONTEND_DIST = _Path(__file__).parent.parent / "frontend" / "dist"

@app.get("/health", tags=["Status"])
async def health_check():
    return {"status": "ok"}

@app.get("/", include_in_schema=False)
async def root():
    index = _FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"app": "DMG Desk API", "docs": "/docs"})


_SCRIPTS_DIR = _Path(__file__).parent.parent / "scripts"

@app.get("/api/scripts/dmgdesk-apertura-cartelle.reg", tags=["Status"])
async def download_reg_apertura_cartelle():
    """Scarica il file .reg per registrare il protocollo dmgopen:// sul client.
    L'utente fa doppio click sul file per installare l'handler (HKCU, no admin).
    """
    reg_file = _SCRIPTS_DIR / "dmgdesk-apertura-cartelle.reg"
    if not reg_file.exists():
        return JSONResponse({"detail": "File .reg non trovato sul server"}, status_code=404)
    return FileResponse(
        str(reg_file),
        media_type="application/octet-stream",
        filename="dmgdesk-apertura-cartelle.reg",
    )

# Mount DOPO tutte le route API — StaticFiles non intercetta le route registrate
if (_FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="static_assets")

# ── Statici Schermo Live (pubblici, nessun segreto) ─────────────────────────────
# noVNC (client VNC in-browser) e il glue viewer.js. Serviti senza auth: sono
# codice open-source e glue non sensibile. Il gate è su /api/schermo/viewer (HTML)
# e sull'handshake WebSocket di /api/schermo/vnc.
_NOVNC_DIR = _Path(__file__).parent.parent / "heidenhain" / "vendor" / "noVNC"
if (_NOVNC_DIR / "core").exists():
    app.mount("/novnc", StaticFiles(directory=str(_NOVNC_DIR)), name="novnc")
else:
    log.warning(f"Schermo Live: noVNC non trovato in {_NOVNC_DIR} — il viewer non caricherà")
class _NoCacheStatic(StaticFiles):
    """StaticFiles che disabilita la cache: durante la taratura dei tasti il
    viewer.js cambia spesso e i browser lo tengono in cache (specie come modulo
    dentro un iframe). no-store forza il refetch ad ogni ricarica."""
    async def get_response(self, path, scope):
        resp = await super().get_response(path, scope)
        resp.headers["Cache-Control"] = "no-store, must-revalidate"
        return resp

_SCHERMO_ASSETS = _Path(__file__).parent.parent / "web" / "schermo"
if _SCHERMO_ASSETS.exists():
    app.mount("/schermo-assets", _NoCacheStatic(directory=str(_SCHERMO_ASSETS)), name="schermo_assets")

# Tutti gli altri path frontend (react-router) → index.html
# Usiamo un middleware invece di una route per non bloccare le API
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SPAMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        # Difesa contro bug noto di BaseHTTPMiddleware in starlette/anyio:
        # se un middleware downstream solleva durante lo streaming della
        # response, call_next puo' propagare un RuntimeError("No response
        # returned.") rumoroso che floods nei log. Catturiamo e ritorniamo
        # 503 senza tracebak gigante. Refs: encode/starlette#1438.
        try:
            response = await call_next(request)
        except RuntimeError as e:
            if "No response returned" in str(e):
                log.warning(
                    f"SPAMiddleware: response stream interrotto su "
                    f"{request.method} {request.url.path} (client disconnesso?)"
                )
                return JSONResponse(
                    {"detail": "Connessione interrotta"},
                    status_code=503,
                )
            raise
        except Exception:
            # Lasciamo passare le altre eccezioni - le gestisce starlette
            raise
        # Se 404 e non è una API, servi index.html (SPA fallback)
        if (response.status_code == 404
                and not request.url.path.startswith("/api/")
                and not request.url.path.startswith("/assets/")
                and request.url.path != "/docs"
                and request.url.path != "/openapi.json"):
            index = _FRONTEND_DIST / "index.html"
            if index.exists():
                return FileResponse(str(index))
        return response

app.add_middleware(SPAMiddleware)




@app.get("/api/debug", tags=["Status"])
async def debug_minimal():
    """Health check minimo.

    NOTA SICUREZZA (2026-06-22): la vecchia implementazione esponeva l'intero
    config + path filesystem + IP macchina senza autenticazione, leggibile
    dalla LAN. Sostituita con un check binario senza data leak. Per
    diagnostica completa usare i log lato server o un endpoint protetto.
    """
    from database.db_handler import carica_configurazione, get_db_paths
    import os
    try:
        config = carica_configurazione()
        db_path = config.get("database_path", "")
        paths = get_db_paths(db_path)
        config_ok = True
        files_ok = os.path.exists(paths["principale"]) and os.path.exists(paths["utensili_smontati"])
    except Exception:
        config_ok = False
        files_ok = False
    return {"ok": config_ok and files_ok, "config_ok": config_ok, "files_ok": files_ok}
