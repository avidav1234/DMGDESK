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
from utils.logger import get_logger

log = get_logger(__name__)

app = FastAPI(
    title="DMG Desk API",
    description="Backend REST per DMG Desk — DMC 160U",
    version="16.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
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


@app.on_event("startup")
async def startup():
    log.info("DMG Desk API v16.0 avviata — http://0.0.0.0:8000")
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
