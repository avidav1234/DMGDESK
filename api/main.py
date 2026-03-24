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
    macchina_live, pallet, macchina_invio,
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


@app.on_event("startup")
async def startup():
    log.info("DMG Desk API v16.0 avviata — http://0.0.0.0:8000")


# ── Serve frontend React (se compilato) ───────────────────────────────────
from pathlib import Path as _Path
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

_FRONTEND_DIST = _Path(__file__).parent.parent / "frontend" / "dist"

@app.get("/", include_in_schema=False)
async def root():
    index = _FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"app": "DMG Desk API", "version": "16.0.0", "docs": "/docs"})

@app.get("/health", tags=["Status"])
async def health_check():
    return {"status": "ok"}

# Catch-all SPA: serve index.html per tutte le route non-API
@app.get("/{full_path:path}", include_in_schema=False)
async def serve_spa(full_path: str):
    # Lascia passare le API (già registrate sopra con prefix /api/...)
    if full_path.startswith("api/"):
        return JSONResponse({"error": "not found"}, status_code=404)
    # Prova prima il file fisico (assets, favicon, ecc.)
    static_file = _FRONTEND_DIST / full_path
    if static_file.exists() and static_file.is_file():
        return FileResponse(str(static_file))
    # Fallback SPA
    index = _FRONTEND_DIST / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse({"error": "frontend non compilato — esegui npm run build"}, status_code=404)




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
