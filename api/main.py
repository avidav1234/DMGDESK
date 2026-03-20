"""
Tool Manager V16 — Backend FastAPI
====================================
Avvio:  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Docs interattive:  http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import macchina, scaffale, smontati, holder_bussole, generatore, analisi_nc, config_router, tools
from utils.logger import get_logger

log = get_logger(__name__)

app = FastAPI(
    title="Tool Manager API",
    description="Backend REST per gestione utensili CNC — DMG 160U",
    version="16.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS: permetti al browser sulla LAN di chiamare l'API ──
# In produzione limita origins agli IP della rete aziendale
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],        # es. ["http://192.168.1.0/24"]
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Router per ogni tab dell'applicazione ──────────────────
app.include_router(macchina.router,       prefix="/api/macchina",       tags=["In Macchina"])
app.include_router(scaffale.router,       prefix="/api/scaffale",       tags=["Scaffale"])
app.include_router(smontati.router,       prefix="/api/smontati",       tags=["Smontati"])
app.include_router(holder_bussole.router, prefix="/api/holder-bussole", tags=["Holder & Bussole"])
app.include_router(generatore.router,     prefix="/api/generatore",     tags=["Generatore Codici"])
app.include_router(analisi_nc.router,     prefix="/api/analisi-nc",     tags=["Analisi NC"])
app.include_router(config_router.router,  prefix="/api/config",         tags=["Configurazione"])
app.include_router(tools.router,          prefix="/api/tools",          tags=["Utensili Macchina"])


@app.on_event("startup")
async def startup():
    log.info("Tool Manager API avviata — http://0.0.0.0:8000")
    log.info("Docs: http://localhost:8000/docs")


@app.get("/", tags=["Status"])
async def root():
    return {
        "app": "Tool Manager API",
        "version": "16.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Status"])
async def health():
    """Endpoint di health check — utile per monitoraggio."""
    return {"status": "ok"}


@app.get("/api/debug", tags=["Status"])
async def debug_config():
    """Diagnostica configurazione — mostra cosa vede il server (percorsi, colonne CSV, errori)."""
    import os, json
    from database.db_handler import carica_configurazione, get_db_paths, carica_database

    try:
        config = carica_configurazione()
    except Exception as e:
        return {"errore_config": str(e)}

    db_path = config.get("database_path", "")
    paths = get_db_paths(db_path)

    result = {
        "config_json": config,
        "cwd": os.getcwd(),
        "file_principale": {
            "path": paths["principale"],
            "esiste": os.path.exists(paths["principale"]),
        },
        "file_smontati": {
            "path": paths["utensili_smontati"],
            "esiste": os.path.exists(paths["utensili_smontati"]),
        },
    }

    if os.path.exists(paths["principale"]):
        df, err = carica_database(paths["principale"])
        result["db_principale"] = {
            "errore": err,
            "righe": len(df),
            "colonne": df.columns.tolist(),
            "stati_utensile": df["Stato_Utensile"].value_counts().to_dict() if "Stato_Utensile" in df.columns else "COLONNA MANCANTE",
        }
    else:
        result["db_principale"] = {"errore": "File non trovato"}

    return result
