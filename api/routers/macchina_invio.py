"""
api/routers/macchina_invio.py
==============================
Endpoint per l'invio di file NC alla macchina CNC tramite MachineServer.

POST /api/macchina-invio/check     → verifica connessione e file già presenti
POST /api/macchina-invio/invia     → invia file alla macchina
GET  /api/macchina-invio/config    → legge IP/porta dal config.json
PUT  /api/macchina-invio/config    → salva IP/porta nel config.json
"""

import os
import sys
import json
import tempfile
from typing import List, Optional

from fastapi import APIRouter, HTTPException, UploadFile, File, Form
from pydantic import BaseModel

from database.db_handler import carica_configurazione, salva_configurazione
from utils.logger import get_logger

# MachineClient è nel root del progetto
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from machine_client import MachineClient

log = get_logger(__name__)
router = APIRouter()

DEFAULT_IP   = "10.95.20.29"
DEFAULT_PORT = 9999


# ---------------------------------------------------------------------------
# Helpers config
# ---------------------------------------------------------------------------

def _get_machine_config():
    config = carica_configurazione()
    return (
        config.get("machine_ip",   DEFAULT_IP),
        int(config.get("machine_port", DEFAULT_PORT)),
    )


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class MachineConfigRequest(BaseModel):
    ip:   str
    port: int = DEFAULT_PORT


class MachineConfigResponse(BaseModel):
    ip:   str
    port: int


class CheckResponse(BaseModel):
    reachable:  bool
    esistenti:  List[str]
    dest_dir:   str
    error:      Optional[str] = None


class InvioResult(BaseModel):
    filename: str
    ok:       bool
    msg:      str


class InvioResponse(BaseModel):
    n_ok:     int
    n_err:    int
    risultati: List[InvioResult]


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.get(
    "/config",
    response_model=MachineConfigResponse,
    summary="Legge IP e porta del server macchina",
)
async def get_machine_config():
    ip, port = _get_machine_config()
    return MachineConfigResponse(ip=ip, port=port)


@router.put(
    "/config",
    response_model=MachineConfigResponse,
    summary="Salva IP e porta del server macchina",
)
async def set_machine_config(body: MachineConfigRequest):
    config = carica_configurazione()
    config["machine_ip"]   = body.ip.strip()
    config["machine_port"] = str(body.port)
    salva_configurazione(config)
    log.info(f"Macchina configurata: {body.ip}:{body.port}")
    return MachineConfigResponse(ip=body.ip, port=body.port)


@router.post(
    "/check",
    response_model=CheckResponse,
    summary="Verifica connessione e file già presenti nella macchina",
)
async def check_macchina(
    progetto:  str = Form(...),
    filenames: str = Form(...),   # JSON array di nomi file es. '["A.MPF","B.MPF"]'
):
    ip, port = _get_machine_config()
    try:
        names = json.loads(filenames)
    except Exception:
        names = [f.strip() for f in filenames.split(",") if f.strip()]

    client = MachineClient(ip, port)

    import asyncio
    loop = asyncio.get_event_loop()
    esistenti, dest_dir, err = await loop.run_in_executor(
        None, lambda: client.check_esistenti(names, progetto)
    )

    return CheckResponse(
        reachable=err is None,
        esistenti=esistenti,
        dest_dir=dest_dir,
        error=err,
    )


@router.post(
    "/invia",
    response_model=InvioResponse,
    summary="Invia file NC alla macchina tramite MachineServer",
)
async def invia_alla_macchina(
    progetto: str = Form(...),
    files:    List[UploadFile] = File(...),
):
    ip, port = _get_machine_config()
    client   = MachineClient(ip, port)
    risultati: List[InvioResult] = []

    # Salva i file in temp e inviali uno per uno
    tmp_dir = tempfile.mkdtemp(prefix="toolmgr_invia_")
    try:
        for upload in files:
            tmp_path = os.path.join(tmp_dir, upload.filename)
            content  = await upload.read()
            with open(tmp_path, "wb") as f:
                f.write(content)

            ok, msg = client.invia_file(tmp_path, progetto)
            risultati.append(InvioResult(filename=upload.filename, ok=ok, msg=msg))
            log.info(f"Inviato {upload.filename} → {'OK' if ok else 'ERRORE: ' + msg}")
    finally:
        # Pulizia temp
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)

    n_ok  = sum(1 for r in risultati if r.ok)
    n_err = sum(1 for r in risultati if not r.ok)
    return InvioResponse(n_ok=n_ok, n_err=n_err, risultati=risultati)


@router.post(
    "/invia-batch",
    response_model=InvioResponse,
    summary="Invia tutti i file NC in una sola connessione TCP (INVIA_BATCH)",
)
async def invia_batch_alla_macchina(
    progetto: str = Form(...),
    files:    List[UploadFile] = File(...),
):
    """
    Invia tutti i file in una sola connessione TCP usando INVIA_BATCH.
    Molto più veloce di /invia per batch grandi:
    - Nessuna attesa tra un file e l'altro
    - TransferAutom chiamato una sola volta alla fine
    """
    ip, port = _get_machine_config()
    client   = MachineClient(ip, port)

    tmp_dir = tempfile.mkdtemp(prefix="toolmgr_batch_")
    tmp_paths = []
    try:
        for upload in files:
            tmp_path = os.path.join(tmp_dir, upload.filename)
            content  = await upload.read()
            with open(tmp_path, "wb") as f:
                f.write(content)
            tmp_paths.append((upload.filename, tmp_path))

        n_ok, n_err, dettaglio = client.invia_batch(
            [p for _, p in tmp_paths], progetto
        )

        # Costruisce risultati per file dal dettaglio del server
        risultati = []
        nome_map = {os.path.splitext(fname)[0].upper(): fname
                    for fname, _ in tmp_paths}
        for d in dettaglio:
            fname_orig = nome_map.get(d.get("nome", "").upper(),
                                      d.get("nome", "") + ".MPF")
            risultati.append(InvioResult(
                filename=fname_orig,
                ok=d.get("ok", False),
                msg=d.get("msg", "")
            ))

        # File non presenti nel dettaglio (errori prima dell'invio)
        nomi_in_det = {d.get("nome","").upper() for d in dettaglio}
        for fname, _ in tmp_paths:
            if os.path.splitext(fname)[0].upper() not in nomi_in_det:
                risultati.append(InvioResult(filename=fname, ok=False,
                                              msg="non ricevuto dal server"))

        log.info(f"[BATCH] {progetto}: {n_ok} OK, {n_err} ERR")
        return InvioResponse(n_ok=n_ok, n_err=n_err, risultati=risultati)
    finally:
        import shutil
        shutil.rmtree(tmp_dir, ignore_errors=True)
