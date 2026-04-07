"""
api/routers/main_sync.py
========================
Gestisce la relazione tra il file MAIN su disco, il log lavorazioni
e lo stato dei programmi in DMGDesk.

Logica:
  stato_programma = f(MAIN, LOG)

  MAIN non contiene pgm       → da_fare
  MAIN contiene pgm
    LOG ha eseguito pgm
      in_lavorazione nel log  → in_lavorazione
      completato nel log      → completato
    LOG non ha eseguito pgm   → in_main

Regola assoluta: completato non degrada mai (irreversibile).

Il job viene schedulato ogni 5 minuti dall'applicazione.
"""

import json
import hashlib
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

from fastapi import APIRouter

from database.db_handler import carica_configurazione
from api.routers.progetti import _load_progetti, _save_progetti, _write_lock
from api.routers.report import _load_log, _log_path

log = logging.getLogger("toolmanager")
router = APIRouter(prefix="/api/main-sync", tags=["main-sync"])


# ── Parser MAIN ───────────────────────────────────────────────────────────────

def _parse_extcall(contenuto: str) -> list[str]:
    """
    Estrae i filename dei programmi chiamati dal MAIN via EXTCALL.
    Ritorna lista di filename normalizzati (senza path, senza .MPF).

    Formato atteso:
      EXTCALL ("/_N_WKS_DIR/_N_4298_0005_WPD/_N_4298_005_01_01_MPF")
    """
    filenames = []
    for line in contenuto.splitlines():
        line = line.strip()
        if not line.upper().startswith("EXTCALL"):
            continue
        # Estrae il contenuto tra parentesi
        start = line.find("(")
        end   = line.rfind(")")
        if start == -1 or end == -1:
            continue
        inner = line[start+1:end].strip().strip('"').strip("'")
        # Prende l'ultimo token dopo /
        parts = inner.replace("\\", "/").split("/")
        fname = parts[-1]
        # Siemens usa _MPF come suffisso nel path; il filename reale è con .MPF
        fname = fname.replace("_MPF", ".MPF").replace("_mpf", ".mpf")
        # Normalizza: rimuovi .MPF per il confronto, aggiungi back
        base = fname.upper().replace(".MPF", "")
        if base:
            filenames.append(base + ".MPF")
    return filenames


def _hash_file(path: Path) -> str:
    """MD5 del file — per rilevare modifiche al MAIN su disco."""
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()[:8]
    except Exception:
        return ""


# ── Log scanner ───────────────────────────────────────────────────────────────

def _build_log_index(config: dict) -> dict[str, str]:
    """
    Legge log corrente + archivio e ritorna:
      { "4298_005_01_01.MPF": "completato" | "in_lavorazione" }

    Per ogni filename, usa lo stato più avanzato trovato.
    Priorità: in_lavorazione > completato (in_lavorazione è lo stato live).
    """
    index: dict[str, str] = {}

    def _scan(sessioni: list):
        stato_corrente = None
        # Cerca stato_corrente nel log per il programma live
        sc = {}
        try:
            lp = _log_path(config)
            raw = json.loads(Path(lp).read_text(encoding="utf-8"))
            sc = raw.get("stato_corrente", {})
        except Exception:
            pass

        prog_live = (sc.get("programma_corrente") or "").upper().replace(".MPF", "") + ".MPF"
        if prog_live and prog_live != ".MPF":
            index[prog_live] = "in_lavorazione"

        for sess in sessioni:
            for pgm in sess.get("programmi", []):
                fname = (pgm.get("filename") or "").upper()
                if not fname:
                    continue
                if not fname.endswith(".MPF"):
                    fname += ".MPF"
                # completato è definitivo — non sovrascrivere con in_lavorazione
                if index.get(fname) == "completato":
                    continue
                index[fname] = "completato"

    # Log corrente
    try:
        data = _load_log(config)
        _scan(data.get("sessioni", []))
    except Exception as e:
        log.warning(f"main_sync: errore lettura log corrente: {e}")

    # Archivio (massima robustezza)
    try:
        lp = Path(_log_path(config))
        arch_path = lp.parent / "lavorazioni_log_archivio.json"
        if arch_path.exists():
            arch = json.loads(arch_path.read_text(encoding="utf-8"))
            _scan(arch.get("sessioni", []))
    except Exception as e:
        log.warning(f"main_sync: errore lettura archivio log: {e}")

    return index


# ── Sync singolo progetto ─────────────────────────────────────────────────────

def _sync_progetto(progetto: dict, log_index: dict[str, str]) -> bool:
    """
    Applica la formula MAIN + LOG agli stati dei programmi del progetto.
    Ritorna True se ha modificato qualcosa.
    """
    snap = progetto.get("main_snapshot")
    if not snap:
        return False

    main_path = snap.get("main_path")
    if not main_path:
        return False

    mp = Path(main_path)
    if not mp.exists():
        log.warning(f"main_sync: MAIN non trovato su disco: {main_path}")
        return False

    # Rileggi il MAIN — se è cambiato su disco, aggiorna lo snapshot
    try:
        contenuto = mp.read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        log.warning(f"main_sync: errore lettura MAIN {main_path}: {e}")
        return False

    hash_attuale = _hash_file(mp)
    if hash_attuale != snap.get("main_hash"):
        # MAIN cambiato su disco — aggiorna snapshot
        pgm_nel_main = _parse_extcall(contenuto)
        snap["main_hash"]         = hash_attuale
        snap["main_programmi"]    = pgm_nel_main
        snap["main_sync_ts"]      = datetime.now().isoformat(timespec="seconds")
        log.info(f"main_sync: MAIN aggiornato {mp.name} ({len(pgm_nel_main)} pgm)")

    pgm_nel_main_set = {f.upper() for f in snap.get("main_programmi", [])}

    dirty = False
    for s in progetto.get("steps", []):
        for t in s.get("tasks", []):
            if t.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in t.get("programs", []):
                fname = (pgm.get("filename") or "").upper()
                stato_attuale = pgm.get("stato", "da_fare")

                # Mai degradare completato
                if stato_attuale == "completato":
                    continue

                # Determina nuovo stato dalla formula
                if fname not in pgm_nel_main_set:
                    nuovo = "da_fare"
                elif log_index.get(fname) == "in_lavorazione":
                    nuovo = "in_lavorazione"
                elif log_index.get(fname) == "completato":
                    nuovo = "completato"
                else:
                    nuovo = "in_main"

                if nuovo != stato_attuale:
                    pgm["stato"] = nuovo
                    # Pulisci tempi se torna in_main da da_fare
                    if nuovo == "in_main" and stato_attuale == "da_fare":
                        pgm["tempoInizio"] = pgm.get("tempoInizio")  # preserva se c'era
                    dirty = True

    return dirty


# ── Job periodico ─────────────────────────────────────────────────────────────

async def job_sync_main_log():
    """
    Chiamato ogni 5 minuti dallo scheduler.
    Sincronizza stato programmi di tutti i progetti che hanno un main_snapshot.
    """
    config = carica_configurazione()
    proj_data = _load_progetti(config)
    projects  = proj_data.get("projects", [])

    progetti_con_main = [p for p in projects if p.get("main_snapshot")]
    if not progetti_con_main:
        return

    log_index = _build_log_index(config)
    any_dirty = False

    for progetto in progetti_con_main:
        if _sync_progetto(progetto, log_index):
            any_dirty = True
            log.info(f"main_sync: aggiornato {progetto.get('name')}")

    if any_dirty:
        async with _write_lock:
            from api.routers.progetti import _invalidate_analisi_cache
            _save_progetti(config, proj_data)
            _invalidate_analisi_cache()
        log.info("main_sync: salvataggio completato")


# ── Endpoint: salva snapshot quando il MAIN viene generato ───────────────────

@router.post("/snapshot")
async def salva_main_snapshot(body: dict = Body(...)):
    """
    Chiamato da salva_main (analisi_nc) dopo aver scritto il file su disco.
    Salva nel progetto il main_snapshot con path, hash e lista programmi.

    Body: { project_id, main_path, programmi: [filename, ...] }
    """
    project_id = body.get("project_id")
    main_path  = body.get("main_path")
    programmi  = body.get("programmi", [])

    if not project_id or not main_path:
        return {"ok": False, "detail": "project_id e main_path richiesti"}

    config    = carica_configurazione()
    proj_data = _load_progetti(config)
    projects  = proj_data.get("projects", [])

    progetto = next((p for p in projects if p.get("id") == project_id), None)
    if not progetto:
        return {"ok": False, "detail": f"Progetto {project_id} non trovato"}

    mp = Path(main_path)
    hash_val = _hash_file(mp) if mp.exists() else ""

    progetto["main_snapshot"] = {
        "main_path":      main_path,
        "main_hash":      hash_val,
        "main_programmi": [f.upper() if not f.upper().endswith(".MPF")
                           else f.upper() for f in programmi],
        "generato_il":    datetime.now().isoformat(timespec="seconds"),
        "main_sync_ts":   datetime.now().isoformat(timespec="seconds"),
    }

    async with _write_lock:
        _save_progetti(config, proj_data)

    log.info(f"main_sync: snapshot salvato per {progetto.get('name')} → {main_path}")
    return {"ok": True, "n_programmi": len(programmi), "hash": hash_val}


@router.post("/reset-guasto/{project_id}")
async def reset_guasto(project_id: str):
    """
    Ripristina un progetto da GUASTO a stato coerente con MAIN + LOG.
    - Pallet → grezzo
    - Programmi: ricalcola da MAIN + LOG
    """
    from api.routers.pallet import _load as _load_pallet, _save as _save_pallet

    config    = carica_configurazione()
    proj_data = _load_progetti(config)
    projects  = proj_data.get("projects", [])
    progetto  = next((p for p in projects if p.get("id") == project_id), None)

    if not progetto:
        return {"ok": False, "detail": "Progetto non trovato"}

    # Pallet → grezzo
    pallet_data = _load_pallet(config)
    for pal in pallet_data.get("pallet", []):
        if pal.get("progetto_id") == project_id:
            if pal.get("stato") == "guasto":
                pal["stato"] = "grezzo"
            break
    _save_pallet(config, pallet_data)

    # Se c'è uno snapshot, risincronizza da MAIN + LOG
    if progetto.get("main_snapshot"):
        log_index = _build_log_index(config)
        _sync_progetto(progetto, log_index)
    else:
        # Senza MAIN: rimetti tutti i programmi in_main/da_fare a da_fare
        for s in progetto.get("steps", []):
            for t in s.get("tasks", []):
                if t.get("text", "").strip().lower() != "fresatura":
                    continue
                for pgm in t.get("programs", []):
                    if pgm.get("stato") not in ("completato", "in_lavorazione"):
                        pgm["stato"] = "da_fare"

    async with _write_lock:
        _save_progetti(config, proj_data)

    log.info(f"main_sync: reset GUASTO → {progetto.get('name')}")
    return {"ok": True, "progetto": progetto.get("name")}
