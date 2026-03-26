"""
Router Progetti — integrazione WorkTrack / Progetto 5
Legge e scrive worktrack_projects.json sulla share condivisa (tools_toa_folder).
"""

from fastapi import APIRouter, Body, HTTPException
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
    """Tutti i progetti + templates, con pallet_assegnato da pallet_state."""
    config    = carica_configurazione()
    data      = _load_progetti(config)
    templates = _load_templates(config)
    projects  = data.get("projects", [])

    # Incrocia con pallet_state per avere pallet_assegnato aggiornato
    try:
        from api.routers.pallet import _load as _load_pallet, _pallet_path
        pallet_state = _load_pallet(config)
        # Mappa progetto_id → numero pallet
        pallet_map = {
            p["progetto_id"]: p["numero"]
            for p in pallet_state.get("pallet", [])
            if p.get("progetto_id")
        }
        # Aggiorna ogni progetto con il pallet corretto
        for proj in projects:
            pid = proj.get("id")
            # pallet_map è la fonte di verità — sovrascrive sempre
            proj["pallet_assegnato"] = pallet_map.get(pid, None)
    except Exception as e:
        import traceback
        print(f"[WARN] get_progetti: errore incrocio pallet_state: {e}\n{traceback.format_exc()}")

    return {
        "projects":  projects,
        "templates": templates,
        "path":      str(_progetti_path(config)),
    }

# ── Route statiche (DEVONO stare prima di /{project_id}) ─────────────────────

@router.get("/deliveries")
async def get_deliveries():
    """Tutte le scadenze di consegna."""
    config = carica_configurazione()
    return _load_deliveries(config)


@router.put("/deliveries")
async def save_deliveries(body: Any = Body(...)):
    """Salva l'intera lista deliveries (sostituisce tutto)."""
    config = carica_configurazione()
    deliveries = body if isinstance(body, list) else []
    _save_deliveries(config, deliveries)
    return {"ok": True, "count": len(deliveries)}


@router.get("/export")
async def export_backup():
    """Esporta tutti i dati come backup JSON (compatibile con WorkTrack)."""
    from fastapi.responses import JSONResponse
    from datetime import datetime
    config = carica_configurazione()
    data = _load_progetti(config)
    templates = _load_templates(config)
    payload = {
        "_worktrack": True,
        "version": 2,
        "exportedAt": datetime.now().isoformat(),
        "label": f"Backup DMGDesk {datetime.now().strftime('%Y-%m-%d')}",
        "projects": data.get("projects", []),
        "templates": templates,
    }
    return JSONResponse(content=payload, headers={
        "Content-Disposition": f"attachment; filename=worktrack_backup_{datetime.now().strftime('%Y-%m-%d')}.json"
    })


@router.get("/debug-stato")
async def debug_stato():
    """Debug: mostra pallet_state, deliveries e config in un colpo solo."""
    import traceback
    config = carica_configurazione()
    result = {
        "tools_toa_folder": config.get("tools_toa_folder"),
        "pallet_state": None,
        "pallet_state_error": None,
        "pallet_state_path": None,
        "deliveries": None,
        "deliveries_error": None,
        "deliveries_path": None,
        "progetti_count": 0,
        "progetti_con_pallet": [],
    }
    try:
        from api.routers.pallet import _load as _load_pallet, _pallet_path
        pp = _pallet_path(config)
        result["pallet_state_path"] = str(pp)
        result["pallet_state_exists"] = pp.exists()
        ps = _load_pallet(config)
        result["pallet_state"] = [
            {"numero": p["numero"], "stato": p.get("stato"), "progetto_id": p.get("progetto_id"), "progetto_nome": p.get("progetto_nome")}
            for p in ps.get("pallet", [])
        ]
    except Exception as e:
        result["pallet_state_error"] = f"{e}\n{traceback.format_exc()}"
    try:
        dp = _deliveries_path(config)
        result["deliveries_path"] = str(dp)
        result["deliveries_exists"] = dp.exists()
        result["deliveries"] = _load_deliveries(config)
    except Exception as e:
        result["deliveries_error"] = f"{e}\n{traceback.format_exc()}"
    try:
        data = _load_progetti(config)
        projs = data.get("projects", [])
        result["progetti_count"] = len(projs)
        pallet_map = {}
        if result["pallet_state"]:
            pallet_map = {p["progetto_id"]: p["numero"] for p in result["pallet_state"] if p.get("progetto_id")}
        result["progetti_con_pallet"] = [
            {"id": p.get("id"), "name": p.get("name"), "pallet": pallet_map.get(p.get("id"))}
            for p in projs if pallet_map.get(p.get("id"))
        ]
    except Exception as e:
        result["progetti_error"] = str(e)
    return result


@router.get("/debug-setup")
async def debug_setup():
    """Debug: mostra cosa vede analisi setup."""
    from api.routers.progetti_utensili import estrai_alias_da_progetti
    config = carica_configurazione()
    alias_map = estrai_alias_da_progetti(config)
    return {
        "nc_base": config.get("percorso_nc_base"),
        "tools_folder": config.get("tools_toa_folder"),
        "n_alias": len(alias_map),
        "alias_sample": {k: v[:2] for k, v in list(alias_map.items())[:10]},
    }


@router.put("/{project_id}")
async def update_progetto(project_id: str, body: ProgettoUpdate):
    """Salva un progetto (crea o aggiorna)."""
    config = carica_configurazione()
    data = _load_progetti(config)
    projects = data.get("projects", [])
    idx = next((i for i, p in enumerate(projects) if p.get("id") == project_id), None)
    incoming = body.data if isinstance(body.data, dict) else {}
    # pallet_assegnato è gestito SOLO da pallet_state — rimuovilo sempre dal JSON progetti
    incoming.pop("pallet_assegnato", None)
    if idx is not None:
        projects[idx] = incoming
    else:
        projects.append(incoming)
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


class ImportBody(BaseModel):
    projects: list
    templates: list
    mode: str = "merge"   # merge | replace


@router.post("/import")
async def import_backup(body: ImportBody):
    """
    Importa un backup WorkTrack.
    mode=replace: sovrascrive tutto
    mode=merge:   aggiunge/aggiorna senza cancellare
    """
    config = carica_configurazione()

    if body.mode == "replace":
        data = {"projects": body.projects}
        _save_progetti(config, data)
        path = _templates_path(config)
        path.write_text(json.dumps(body.templates, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        # Merge: aggiorna esistenti, aggiunge nuovi
        data = _load_progetti(config)
        existing = {p["id"]: p for p in data.get("projects", [])}
        for p in body.projects:
            existing[p["id"]] = p
        data["projects"] = list(existing.values())
        _save_progetti(config, data)

        # Template merge
        existing_t = {t["id"]: t for t in _load_templates(config)}
        for t in body.templates:
            existing_t[t["id"]] = t
        path = _templates_path(config)
        path.write_text(json.dumps(list(existing_t.values()), ensure_ascii=False, indent=2), encoding="utf-8")

    return {
        "ok": True,
        "progetti": len(body.projects),
        "templates": len(body.templates),
        "mode": body.mode,
    }


# ── Utensili check ──────────────────────────────────────────────────────────

@router.get("/{project_id}/utensili-check")
async def check_utensili_progetto(project_id: str):
    """
    Incrocia gli utensili richiesti dai programmi MPF del progetto
    con tools_machine.json, scaffale CSV e smontati CSV.
    Ritorna per ogni alias: stato (ok|scaffale|smontato|mancante|fin_vita|disabilitato)
    """
    import sys, os
    sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

    config = carica_configurazione()

    # Carica progetto
    data    = _load_progetti(config)
    project = next((p for p in data.get("projects", []) if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(404, f"Progetto {project_id} non trovato")

    # Estrai alias MPF dal FresaturaPanel
    alias_richiesti = set()
    for step in project.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() == "fresatura":
                for pgm in task.get("programs", []):
                    if pgm.get("tipoGruppo") != "ipm" and pgm.get("utensile"):
                        alias_richiesti.add(pgm["utensile"].upper().strip())

    if not alias_richiesti:
        return {"project_id": project_id, "utensili": [], "summary": {
            "ok": 0, "scaffale": 0, "smontato": 0, "mancante": 0,
            "fin_vita": 0, "disabilitato": 0, "totale": 0
        }}

    # Carica tools_machine.json
    tools_folder = (config.get("tools_toa_folder") or "").strip()
    tools_db = {}
    if tools_folder:
        tm_path = Path(tools_folder) / "tools_machine.json"
        if tm_path.exists():
            try:
                raw = json.loads(tm_path.read_text(encoding="utf-8"))
                tools_db = raw.get("tools", {})
            except Exception:
                pass

    # Indice tools_machine per alias
    in_macchina = {}  # alias_upper -> tool_dict
    for t in tools_db.values():
        n = (t.get("name") or "").upper().strip()
        if n:
            in_macchina[n] = t

    # Carica scaffale e smontati CSV
    from database.db_handler import (
        auto_find_db_paths, carica_database, carica_database_utensili_smontati
    )
    db_paths = auto_find_db_paths(config)

    scaffale_alias = set()
    if db_paths.get("principale"):
        try:
            df, _ = carica_database(db_paths["principale"])
            scaffale_alias = set(df["Alias"].str.upper().str.strip().tolist())
        except Exception:
            pass

    smontati_alias = set()
    if db_paths.get("utensili_smontati"):
        try:
            df_s, _ = carica_database_utensili_smontati(db_paths["utensili_smontati"])
            if "Alias_Utensile" in df_s.columns:
                smontati_alias = set(df_s["Alias_Utensile"].str.upper().str.strip().tolist())
        except Exception:
            pass

    # Classifica ogni alias
    result = []
    summary = {"ok": 0, "scaffale": 0, "smontato": 0, "mancante": 0,
               "fin_vita": 0, "disabilitato": 0, "totale": len(alias_richiesti)}

    for alias in sorted(alias_richiesti):
        tool = in_macchina.get(alias)
        if tool:
            lp = tool.get("life_percent")
            if not tool.get("is_enabled", True) or tool.get("is_worn", False):
                stato = "disabilitato"
            elif lp is not None and lp < 15:
                stato = "fin_vita"
            else:
                stato = "ok"
        elif alias in scaffale_alias:
            stato = "scaffale"
        elif alias in smontati_alias:
            stato = "smontato"
        else:
            stato = "mancante"

        summary[stato] = summary.get(stato, 0) + 1

        result.append({
            "alias":        alias,
            "stato":        stato,
            "magazine":     tool.get("magazine")     if tool else None,
            "position":     tool.get("position")     if tool else None,
            "life_percent": tool.get("life_percent") if tool else None,
            "length":       tool.get("length")       if tool else None,
        })

    return {"project_id": project_id, "utensili": result, "summary": summary}


@router.get("/analisi-setup/non-utilizzati")
async def get_analisi_setup():
    """
    Confronta utensili in macchina con richiesti dai progetti attivi.
    Legge alias anche dai file MPF su disco.
    """
    from api.routers.progetti_utensili import estrai_alias_da_progetti
    from database.db_handler import auto_find_db_paths, carica_database, carica_database_utensili_smontati

    config      = carica_configurazione()
    alias_map   = estrai_alias_da_progetti(config)
    alias_attivi = set(alias_map.keys())

    tools_folder = (config.get("tools_toa_folder") or "").strip()
    tools_db, sync_time = {}, None
    if tools_folder:
        tm_path = Path(tools_folder) / "tools_machine.json"
        if tm_path.exists():
            try:
                raw = json.loads(tm_path.read_text(encoding="utf-8"))
                tools_db  = raw.get("tools", {})
                sync_time = raw.get("sync_time")
            except Exception:
                pass

    in_macchina = {}
    for t in tools_db.values():
        n = (t.get("name") or "").upper().strip()
        if n: in_macchina[n] = t

    db_paths = auto_find_db_paths(config)
    scaffale_alias, smontati_alias = set(), set()
    scaffale_rows, smontati_rows   = [], []
    try:
        df, _ = carica_database(db_paths["principale"])
        scaffale_alias = set(df["Alias"].str.upper().str.strip())
        scaffale_rows  = df.to_dict("records")
    except Exception:
        pass
    try:
        df_s, _ = carica_database_utensili_smontati(db_paths["utensili_smontati"])
        if "Alias_Utensile" in df_s.columns:
            smontati_alias = set(df_s["Alias_Utensile"].str.upper().str.strip())
            smontati_rows  = df_s.to_dict("records")
    except Exception:
        pass

    from api.routers.progetti_utensili import classify_tool as _ct

    # Non utilizzati: in macchina ma non richiesti (considera alias unici)
    alias_in_macchina_unici = {}
    for t in tools_db.values():
        n = (t.get("name") or "").upper().strip()
        if not n: continue
        if n not in alias_in_macchina_unici:
            alias_in_macchina_unici[n] = t

    non_utilizzati = []
    fin_vita        = []
    for n, t in alias_in_macchina_unici.items():
        stato = _ct(n, tools_db)  # usa tools_db con tutti i gemelli, non in_macchina
        lp_best = None
        # Vita migliore tra gemelli abilitati
        abilitati = [x for x in in_macchina.values()
                     if (x.get("name") or "").upper().strip() == n
                     and x.get("is_enabled", True) and not x.get("is_worn", False)]
        if abilitati:
            lp_best = max((x.get("life_percent") or 0) for x in abilitati)

        if stato == "fin_vita":
            refs = alias_map.get(n, [])
            fin_vita.append({"alias":n,"magazine":t.get("magazine"),
                             "position":t.get("position"),"life_percent":lp_best,
                             "progetti": [{"progetto": r[0], "file": r[1]} for r in refs[:3]]})
        if stato == "disabilitato" and n in alias_attivi:
            # In macchina ma worn/disabilitato E richiesto da un progetto → trattalo come fin_vita
            refs = alias_map.get(n, [])
            fin_vita.append({"alias":n,"magazine":t.get("magazine"),
                             "position":t.get("position"),"life_percent":0,
                             "disabilitato": True,
                             "progetti": [{"progetto": r[0], "file": r[1]} for r in refs[:3]]})
        if n not in alias_attivi:
            non_utilizzati.append({"alias":n,"magazine":t.get("magazine"),
                                   "position":t.get("position"),"life_percent":lp_best})

    # Da montare: richiesti ma FISICAMENTE ASSENTI dalla macchina
    # - ok, fin_vita, disabilitato → è fisicamente in macchina (worn/KO ma presente) → NON montare
    # - mancante → non trovato in tools_machine.json → va in "Da montare"
    da_montare = []
    for alias in sorted(alias_attivi):
        stato_alias = _ct(alias, tools_db)  # tutti i gemelli
        if stato_alias in ("ok", "fin_vita", "disabilitato"):
            continue  # fisicamente presente in macchina (anche se worn)
        # stato_alias == "mancante" → non è in tools_machine.json
        provenienza = ("scaffale" if alias in scaffale_alias
                       else "smontato" if alias in smontati_alias
                       else "mancante")
        refs = alias_map.get(alias, [])
        da_montare.append({
            "alias":     alias,
            "provenienza": provenienza,
            "progetti":  [{"progetto": r[0], "file": r[1]} for r in refs[:5]],
        })

    return {
        "non_utilizzati": sorted(non_utilizzati, key=lambda x: x["alias"]),
        "da_montare":     da_montare,
        "fin_vita":       sorted(fin_vita, key=lambda x: x.get("life_percent") or 0),
        "sync_time":      sync_time,
    }


# ── Segna programmi in_macchina ────────────────────────────────────────────

@router.post("/{project_id}/segna-in-macchina")
async def segna_in_macchina(project_id: str, body: dict):
    """
    Quando si genera il MAIN, i programmi inclusi passano a stato 'in_macchina'.
    Body: { filenames: ["file1.MPF", "file2.MPF", ...] }
    """
    config   = carica_configurazione()
    data     = _load_progetti(config)
    projects = data.get("projects", [])
    project  = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(404, f"Progetto {project_id} non trovato")

    filenames = {f.upper() for f in body.get("filenames", [])}
    if not filenames:
        return {"aggiornati": 0}

    now = datetime.now().isoformat()
    aggiornati = 0

    for step in project.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in task.get("programs", []):
                if pgm.get("filename", "").upper() in filenames:
                    if pgm.get("stato") == "da_fare":
                        pgm["stato"] = "in_macchina"
                        pgm["tempoInizio"] = now
                        aggiornati += 1

    if aggiornati > 0:
        # Salva
        tools_folder = (config.get("tools_toa_folder") or "").strip()
        if tools_folder:
            path = Path(tools_folder) / "worktrack_projects.json"
        else:
            path = Path("worktrack_projects.json")
        data_to_save = {"projects": projects, "ultimo_aggiornamento": now}
        path.write_text(json.dumps(data_to_save, ensure_ascii=False, indent=2), encoding="utf-8")

    return {"aggiornati": aggiornati, "project_id": project_id}


@router.get("/{project_id}/debug-utensili")
async def debug_utensili(project_id: str):
    """Debug: mostra gli alias estratti dai programmi del progetto."""
    config  = carica_configurazione()
    data    = _load_progetti(config)
    project = next((p for p in data.get("projects", []) if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(404, "Progetto non trovato")

    result = []
    for step in project.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in task.get("programs", []):
                result.append({
                    "filename": pgm.get("filename"),
                    "stato":    pgm.get("stato"),
                    "utensile": pgm.get("utensile"),
                    "diametro": pgm.get("diametro"),
                    "tipoGruppo": pgm.get("tipoGruppo"),
                })
    return {"project_id": project_id, "programs": result}



@router.patch("/{project_id}")
async def patch_project(project_id: str, body: dict = Body(...)):
    """Aggiorna campi semplici di un progetto (es. pallet_assegnato)."""
    config   = carica_configurazione()
    data     = _load_progetti(config)
    projects = data.get("projects", [])
    project  = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(404, "Progetto non trovato")

    ALLOWED = {"pallet_assegnato", "color", "description"}
    for k, v in body.items():
        if k in ALLOWED:
            project[k] = v

    now  = datetime.now().isoformat()
    path = _progetti_path(config)
    path.write_text(json.dumps({"projects": projects, "ultimo_aggiornamento": now},
                               ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True, "project_id": project_id}


# ── Deliveries (scadenze consegne) ────────────────────────────────────────────

def _deliveries_path(config: dict) -> Path:
    base = (config.get("tools_toa_folder") or "").strip()
    if not base:
        base = "."
    return Path(base) / "worktrack_deliveries.json"

def _load_deliveries(config: dict) -> list:
    path = _deliveries_path(config)
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, list):
                return data
            if isinstance(data, dict):
                return data.get("deliveries", data.get("projects", []))
        except Exception:
            pass
    return []

def _save_deliveries(config: dict, deliveries: list):
    path = _deliveries_path(config)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(deliveries, ensure_ascii=False, indent=2), encoding="utf-8")


@router.post("/{project_id}/riparsing-utensili")
async def riparsing_utensili(project_id: str):
    """
    Rilegge i file MPF dal disco e aggiorna il campo 'utensile'
    per tutti i programmi che ce l'hanno vuoto.
    """
    from api.routers.progetti_utensili import cerca_file_mpf, parse_mpf_testo

    config  = carica_configurazione()
    data    = _load_progetti(config)
    projects = data.get("projects", [])
    project = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(404, "Progetto non trovato")

    nc_base      = (config.get("percorso_nc_base") or "").strip()
    tools_folder = (config.get("tools_toa_folder") or "").strip()
    extra_dirs   = [tools_folder] if tools_folder and tools_folder != nc_base else []

    aggiornati = 0
    for step in project.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in task.get("programs", []):
                if pgm.get("tipoGruppo") == "ipm":
                    continue
                if pgm.get("utensile"):
                    continue  # già popolato
                filename = pgm.get("filename", "")
                if not filename:
                    continue
                fpath = cerca_file_mpf(filename, nc_base, extra_dirs)
                if not fpath:
                    continue
                try:
                    testo = open(fpath, encoding="utf-8", errors="replace").read()
                    # Cerca TOOL COMMENT nel header Cimatron
                    for line in testo.splitlines():
                        if "TOOL COMMENT:" in line.upper():
                            alias = line.split("TOOL COMMENT:")[-1].strip()
                            if alias:
                                pgm["utensile"] = alias.upper()
                                aggiornati += 1
                            break
                    # Fallback: usa parse_mpf_testo (T= + M6)
                    if not pgm.get("utensile"):
                        aliases = parse_mpf_testo(testo)
                        if aliases:
                            pgm["utensile"] = sorted(aliases)[0]
                            aggiornati += 1
                except Exception:
                    pass

    if aggiornati > 0:
        now = datetime.now().isoformat()
        tools_folder2 = (config.get("tools_toa_folder") or "").strip()
        path = Path(tools_folder2) / "worktrack_projects.json" if tools_folder2 else Path("worktrack_projects.json")
        path.write_text(json.dumps({"projects": projects, "ultimo_aggiornamento": now},
                                   ensure_ascii=False, indent=2), encoding="utf-8")

    return {"aggiornati": aggiornati, "project_id": project_id}


# ── Quick Tasks ────────────────────────────────────────────────────────────────

def _qt_path(config):
    folder = (config.get("tools_toa_folder") or "").strip()
    return Path(folder) / "quick_tasks.json" if folder else Path("quick_tasks.json")

@router.get("/quick-tasks")
async def get_quick_tasks():
    config = carica_configurazione()
    p = _qt_path(config)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"tasks": []}

@router.put("/quick-tasks")
async def put_quick_tasks(body: dict):
    config = carica_configurazione()
    p = _qt_path(config)
    p.write_text(json.dumps(body, ensure_ascii=False, indent=2), encoding="utf-8")
    return {"ok": True}
