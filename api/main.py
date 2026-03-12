"""
Tool Manager V14 — Backend FastAPI
====================================
Avvio:  uvicorn api.main:app --host 0.0.0.0 --port 8000 --reload

Docs interattive:  http://localhost:8000/docs
"""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.routers import macchina, scaffale, smontati, holder_bussole, generatore, analisi_nc
from utils.logger import get_logger

log = get_logger(__name__)

app = FastAPI(
    title="Tool Manager API",
    description="Backend REST per gestione utensili CNC — DMG 160U",
    version="14.0.0",
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


@app.on_event("startup")
async def startup():
    log.info("Tool Manager API avviata — http://0.0.0.0:8000")
    log.info("Docs: http://localhost:8000/docs")


@app.get("/", tags=["Status"])
async def root():
    return {
        "app": "Tool Manager API",
        "version": "14.0.0",
        "status": "running",
        "docs": "/docs",
    }


@app.get("/health", tags=["Status"])
async def health():
    """Endpoint di health check — utile per monitoraggio."""
    return {"status": "ok"}
