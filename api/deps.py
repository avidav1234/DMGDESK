"""
api/deps.py — Dipendenze condivise FastAPI
==========================================
Gestisce il caricamento del database e lo stato condiviso
tra tutti i router tramite il sistema di dependency injection di FastAPI.

Ogni request ottiene i DataFrame freschi dal disco — semplice e sicuro
per 2-3 utenti concorrenti in LAN (il CSV è la fonte di verità).
"""

import os
from functools import lru_cache
from fastapi import HTTPException

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from database.db_handler import (
    carica_configurazione,
    get_db_paths,
    carica_database,
    carica_database_utensili_smontati,
    carica_database_holder_smontati,
    carica_database_bussole_idraulico,
)
from utils.logger import get_logger

log = get_logger(__name__)


def get_config():
    """Carica config.json — percorso del database principale."""
    config = carica_configurazione()
    db_path = config.get("database_path")
    if not db_path or not os.path.exists(db_path):
        raise HTTPException(
            status_code=503,
            detail="Database non configurato. Imposta il percorso in config.json."
        )
    return config


def get_db_principale():
    """Restituisce il DataFrame del database principale (utensili in macchina + scaffale)."""
    config = get_config()
    paths = get_db_paths(config["database_path"])
    df, err = carica_database(paths["principale"])
    if err:
        log.error(f"Errore caricamento DB principale: {err}")
        raise HTTPException(status_code=500, detail=f"Errore database: {err}")
    return df, paths


def get_db_smontati():
    """Restituisce i DataFrame per utensili e holder smontati."""
    config = get_config()
    paths = get_db_paths(config["database_path"])

    df_utensili, err1 = carica_database_utensili_smontati(paths["utensili_smontati"])
    df_holder, err2   = carica_database_holder_smontati(paths["holder_smontati"])

    if err1: raise HTTPException(status_code=500, detail=f"Errore DB smontati: {err1}")
    if err2: raise HTTPException(status_code=500, detail=f"Errore DB holder: {err2}")

    return df_utensili, df_holder, paths


def get_db_bussole():
    """Restituisce il DataFrame delle bussole idraulico."""
    config = get_config()
    paths = get_db_paths(config["database_path"])
    df, err = carica_database_bussole_idraulico(paths["bussole_idraulico"])
    if err: raise HTTPException(status_code=500, detail=f"Errore DB bussole: {err}")
    return df, paths
