"""
DMG Desk — Backend FastAPI
Avvio:  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload
Docs:   http://localhost:8000/docs
"""

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

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


@app.on_event("startup")
async def startup():
    log.info("DMG Desk API v16.0 avviata — http://0.0.0.0:8000")

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
                _log.debug(f"Machine poller: {_e}")
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

    # ── NC Scanner — ogni 10 minuti ───────────────────────────────────────
    async def _nc_scanner_loop():
        from api.routers.nc_scanner import job_nc_scanner
        import asyncio as _aio
        _log = __import__('logging').getLogger("nc_scanner")
        _log.info("NC Scanner avviato (ogni 1 min)")
        await _aio.sleep(45)  # attendi avvio completo
        while True:
            try:
                await job_nc_scanner()
            except Exception as _e:
                _log.warning(f"NC Scanner error: {_e}")
            await _aio.sleep(60)  # 1 minuto

    _asyncio.create_task(_nc_scanner_loop())
    log.info("NC Scanner avviato (scansione directory NC ogni 1 min, solo file modificati)")

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

# Mount DOPO tutte le route API — StaticFiles non intercetta le route registrate
if (_FRONTEND_DIST / "assets").exists():
    app.mount("/assets", StaticFiles(directory=str(_FRONTEND_DIST / "assets")), name="static_assets")

# Tutti gli altri path frontend (react-router) → index.html
# Usiamo un middleware invece di una route per non bloccare le API
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

class SPAMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
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
async def debug_config():
    import os
    from database.db_handler import carica_configurazione, get_db_paths
    try:
        config = carica_configurazione()
    except Exception as e:
        return {"errore_config": str(e)}
    db_path = config.get("database_path", "")
    paths = get_db_paths(db_path)
    return {
        "config_json": config,
        "cwd": os.getcwd(),
        "file_principale": {"path": paths["principale"], "esiste": os.path.exists(paths["principale"])},
        "file_smontati":   {"path": paths["utensili_smontati"], "esiste": os.path.exists(paths["utensili_smontati"])},
    }
