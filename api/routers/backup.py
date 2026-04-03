"""
api/routers/backup.py
=====================
Backup giornaliero automatico di tutti i dati DMGDesk.

Destinazioni:
  1. C:\\Tool_App\\tool_manager_v2\\ToolManager_V14_Fase1\\tool_manager\\backup\\
  2. H:\\0CellaMikron\\0Cella_DMG-Test\\0Librerie\\DMGDesk\\backup\\

Struttura backup:
  backup/
  └── 2026-04-03/
      ├── worktrack_projects.json
      ├── pallet_state.json
      ├── lavorazioni_log.json
      ├── lavorazioni_log_archivio.json  (se esiste)
      ├── deliveries.json
      ├── config.json
      └── MANIFEST.json   ← lista file + hash + timestamp

Retention: ultimi 30 giorni (rimuove cartelle più vecchie).
"""

import json
import shutil
import hashlib
import logging
from datetime import datetime, date, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter
from database.db_handler import carica_configurazione

log = logging.getLogger("backup")
router = APIRouter(prefix="/api/backup", tags=["Backup"])

# ── Destinazioni backup ───────────────────────────────────────────────────────
BACKUP_DESTINATIONS = [
    Path(r"C:\Tool_App\tool_manager_v2\ToolManager_V14_Fase1\tool_manager\backup"),
    Path(r"H:\0CellaMikron\0Cella_DMG-Test\0Librerie\DMGDesk\backup"),
]

RETENTION_DAYS = 30


# ── Helpers ───────────────────────────────────────────────────────────────────

def _md5(path: Path) -> str:
    try:
        return hashlib.md5(path.read_bytes()).hexdigest()
    except Exception:
        return ""


def _collect_files(config: dict) -> list[Path]:
    """
    Raccoglie tutti i file dati da includere nel backup.
    Ritorna lista di Path esistenti.
    """
    files = []

    # Percorsi dal config
    candidates = []

    # worktrack_projects.json
    proj_path = config.get("projects_path") or config.get("worktrack_path")
    if proj_path:
        candidates.append(Path(proj_path))

    # pallet_state.json — stessa cartella dei progetti
    if proj_path:
        candidates.append(Path(proj_path).parent / "pallet_state.json")
        candidates.append(Path(proj_path).parent / "deliveries.json")
        candidates.append(Path(proj_path).parent / "quick_tasks.json")

    # lavorazioni_log.json
    log_path = config.get("log_path")
    if log_path:
        lp = Path(log_path)
        candidates.append(lp)
        # Archivio
        candidates.append(lp.parent / "lavorazioni_log_archivio.json")

    # cam_tracker
    cam_path = config.get("cam_tracker_data_path")
    if cam_path:
        candidates.append(Path(cam_path))

    # turno snapshots
    turno_path = config.get("turno_snapshot_path")
    if turno_path:
        candidates.append(Path(turno_path))

    # Config stesso
    try:
        from database.db_handler import CONFIG_FILE
        cfg_path = Path(CONFIG_FILE)
        if cfg_path.exists():
            candidates.append(cfg_path)
    except Exception:
        pass

    # Filtra esistenti
    for p in candidates:
        try:
            if p.exists() and p.is_file():
                files.append(p)
        except Exception:
            pass

    return files


def _cleanup_old_backups(dest: Path, retention_days: int):
    """Rimuove cartelle di backup più vecchie di retention_days."""
    cutoff = date.today() - timedelta(days=retention_days)
    try:
        for d in dest.iterdir():
            if not d.is_dir():
                continue
            try:
                # Cartelle nel formato YYYY-MM-DD
                folder_date = date.fromisoformat(d.name)
                if folder_date < cutoff:
                    shutil.rmtree(d)
                    log.info(f"Backup: rimossa cartella vecchia {d}")
            except ValueError:
                pass  # non è una cartella data — ignora
    except Exception as e:
        log.warning(f"Backup cleanup error su {dest}: {e}")


async def job_backup_giornaliero():
    """
    Esegue il backup giornaliero su tutte le destinazioni configurate.
    Crea la cartella del giorno, copia i file, scrive MANIFEST.
    """
    config = carica_configurazione()
    oggi   = date.today().isoformat()
    files  = _collect_files(config)

    if not files:
        log.warning("Backup: nessun file trovato da backuppare")
        return

    successi = 0
    errori   = 0

    for dest_base in BACKUP_DESTINATIONS:
        try:
            dest_dir = dest_base / oggi
            dest_dir.mkdir(parents=True, exist_ok=True)
        except Exception as e:
            log.warning(f"Backup: impossibile creare {dest_base / oggi}: {e}")
            errori += 1
            continue

        manifest = {
            "data":      oggi,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "files":     [],
            "errori":    [],
        }

        for src in files:
            try:
                dst = dest_dir / src.name
                shutil.copy2(src, dst)
                manifest["files"].append({
                    "nome":   src.name,
                    "sorgente": str(src),
                    "hash":   _md5(src),
                    "bytes":  src.stat().st_size,
                })
            except Exception as e:
                log.warning(f"Backup: errore copia {src.name} → {dest_dir}: {e}")
                manifest["errori"].append({"file": src.name, "errore": str(e)})
                errori += 1

        # Scrivi MANIFEST
        try:
            manifest_path = dest_dir / "MANIFEST.json"
            manifest_path.write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2),
                encoding="utf-8"
            )
        except Exception as e:
            log.warning(f"Backup: errore scrittura MANIFEST: {e}")

        # Cleanup vecchi backup
        _cleanup_old_backups(dest_base, RETENTION_DAYS)

        n = len(manifest["files"])
        n_err = len(manifest["errori"])
        log.info(f"Backup: {n} file → {dest_dir} ({'OK' if not n_err else f'{n_err} errori'})")
        successi += 1

    log.info(f"Backup giornaliero completato: {successi}/{len(BACKUP_DESTINATIONS)} destinazioni")
    return {"ok": True, "data": oggi, "files": len(files), "destinazioni": successi}


# ── Endpoint manuale ──────────────────────────────────────────────────────────

@router.post("/esegui")
async def esegui_backup():
    """Esegue il backup immediatamente (senza attendere lo scheduler)."""
    result = await job_backup_giornaliero()
    return result or {"ok": False, "detail": "Nessun file trovato"}


@router.get("/stato")
async def stato_backup():
    """Mostra l'ultimo backup disponibile su ogni destinazione."""
    stato = []
    for dest in BACKUP_DESTINATIONS:
        entry = {"destinazione": str(dest), "esiste": False, "ultimo": None, "files": 0}
        try:
            if dest.exists():
                entry["esiste"] = True
                cartelle = sorted(
                    [d for d in dest.iterdir() if d.is_dir()],
                    reverse=True
                )
                if cartelle:
                    ultima = cartelle[0]
                    entry["ultimo"] = ultima.name
                    manifest_p = ultima / "MANIFEST.json"
                    if manifest_p.exists():
                        m = json.loads(manifest_p.read_text(encoding="utf-8"))
                        entry["files"]     = len(m.get("files", []))
                        entry["timestamp"] = m.get("timestamp")
                        entry["errori"]    = len(m.get("errori", []))
        except Exception as e:
            entry["errore"] = str(e)
        stato.append(entry)
    return {"destinazioni": stato}
