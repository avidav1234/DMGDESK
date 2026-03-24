"""
Router Progetti — integrazione WorkTrack / Progetto 5
Legge e scrive worktrack_projects.json sulla share condivisa (tools_toa_folder).
"""

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, Any
from pathlib import Path
from datetime import datetime
import json

from database.db_handler import carica_configurazione

router = APIRouter()

# ── Helpers ──────────────────────────────────────────────────────────────────

def _progetti_path(config: dict) -> Path:
    base = (config.get("tools_toa_folder") or "").strip()
    if not base:
        base = "."
    return Path(base) / "worktrack_projects.json"

def _templates_path(config: dict) -> Path:
    base = (config.get("tools_toa_folder") or "").strip()
    if not base:
        base = "."
    return Path(base) / "worktrack_templates.json"

def _load_progetti(config: dict) -> dict:
    path = _progetti_path(config)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"projects": [], "ultimo_aggiornamento": None}

def _save_progetti(config: dict, data: dict):
    path = _progetti_path(config)
    data["ultimo_aggiornamento"] = datetime.now().isoformat()
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _load_templates(config: dict) -> list:
    path = _templates_path(config)
    if path.exists():
        try:
            return json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            pass
    return []

# ── Models ───────────────────────────────────────────────────────────────────

class ProgettoUpdate(BaseModel):
    data: Any  # progetto completo

class TemplateUpdate(BaseModel):
    templates: list

class PalletAssoc(BaseModel):
    pallet: Optional[int] = None   # 1-6 o null

# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/")
async def get_progetti():
    """Tutti i progetti + templates."""
    config = carica_configurazione()
    data = _load_progetti(config)
    templates = _load_templates(config)
    return {
        "projects":  data.get("projects", []),
        "templates": templates,
        "path":      str(_progetti_path(config)),
    }

@router.put("/{project_id}")
async def update_progetto(project_id: str, body: ProgettoUpdate):
    """Salva un progetto (crea o aggiorna)."""
    config = carica_configurazione()
    data = _load_progetti(config)
    projects = data.get("projects", [])
    idx = next((i for i, p in enumerate(projects) if p.get("id") == project_id), None)
    if idx is not None:
        projects[idx] = body.data
    else:
        projects.append(body.data)
    data["projects"] = projects
    _save_progetti(config, data)
    return {"ok": True}

@router.delete("/{project_id}")
async def delete_progetto(project_id: str):
    """Elimina un progetto."""
    config = carica_configurazione()
    data = _load_progetti(config)
    data["projects"] = [p for p in data.get("projects", []) if p.get("id") != project_id]
    _save_progetti(config, data)
    return {"ok": True}

@router.put("/{project_id}/pallet")
async def set_pallet_progetto(project_id: str, body: PalletAssoc):
    """Associa/rimuove un pallet a un progetto."""
    config = carica_configurazione()
    data = _load_progetti(config)
    projects = data.get("projects", [])
    found = False
    for p in projects:
        if p.get("id") == project_id:
            p["pallet_assegnato"] = body.pallet
            found = True
            break
    if not found:
        raise HTTPException(404, f"Progetto {project_id} non trovato")
    data["projects"] = projects
    _save_progetti(config, data)
    return {"ok": True, "pallet": body.pallet}

@router.get("/{project_id}/mpf")
async def get_mpf_progetto(project_id: str):
    """Restituisce la lista file MPF del task Fresatura di un progetto."""
    config = carica_configurazione()
    data = _load_progetti(config)
    project = next((p for p in data.get("projects", []) if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(404, f"Progetto {project_id} non trovato")

    # Estrai tutti i programmi dal task "fresatura"
    mpf_files = []
    for step in project.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() == "fresatura":
                for pgm in task.get("programs", []):
                    mpf_files.append({
                        "filename": pgm.get("filename"),
                        "commessa": pgm.get("commessa"),
                        "posizione": pgm.get("posizione"),
                        "fase":     pgm.get("fase"),
                        "stato":    pgm.get("stato", "da_fare"),
                        "tipo":     pgm.get("tipoGruppo", "fresatura"),
                    })

    return {"project_id": project_id, "mpf": mpf_files}

@router.put("/templates/save")
async def save_templates(body: TemplateUpdate):
    """Salva i template su file."""
    config = carica_configurazione()
    path = _templates_path(config)
    path.write_text(json.dumps(body.templates, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}
