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
import asyncio

from database.db_handler import carica_configurazione

router = APIRouter()

# ── Lock globale per scritture concorrenti ────────────────────────────────────
# FastAPI è async — senza lock due richieste parallele fanno:
#   req1: load → modifica → (sospeso) → salva dati VECCHI sovrascrivendo req2
# Il lock serializza tutte le scritture su worktrack_projects.json.
_write_lock = asyncio.Lock()

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

_progetti_cache: dict = {"data": None, "path": None, "mtime": 0}


def _load_progetti(config: dict) -> dict:
    import os as _os
    path = _progetti_path(config)
    if path.exists():
        try:
            mtime = _os.path.getmtime(path)
            if (_progetti_cache["path"] == str(path) and
                    _progetti_cache["mtime"] == mtime and
                    _progetti_cache["data"] is not None):
                return _progetti_cache["data"]
            data = json.loads(path.read_text(encoding="utf-8"))
            # Verifica integrità struttura minima
            if not isinstance(data, dict):
                raise ValueError("Root non è un oggetto JSON")
            if "projects" not in data:
                data["projects"] = []
            if not isinstance(data["projects"], list):
                raise ValueError("projects non è una lista")
            _progetti_cache["data"]  = data
            _progetti_cache["path"]  = str(path)
            _progetti_cache["mtime"] = mtime
            return data
        except (json.JSONDecodeError, ValueError) as e:
            from utils.logger import get_logger as _get_log
            _get_log("routers.progetti").error(
                f"worktrack_projects.json corrotto: {e} — uso struttura vuota"
            )
        except Exception:
            pass
    return {"projects": [], "ultimo_aggiornamento": None}

def _save_progetti(config: dict, data: dict):
    """Scrittura atomica: scrive su .tmp poi rinomina — sicuro su crash/spegnimento."""
    path = _progetti_path(config)
    data["ultimo_aggiornamento"] = datetime.now().isoformat()
    tmp = path.with_suffix(".tmp")
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)   # atomico sullo stesso filesystem
    except Exception:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        raise
    # Invalida cache — il file è cambiato
    _progetti_cache["mtime"] = 0
    _invalidate_analisi_cache()


def _atomic_write(path: Path, data) -> None:
    """Scrittura atomica generica: serializza data in JSON su path in modo sicuro."""
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception:
        try: tmp.unlink(missing_ok=True)
        except Exception: pass
        raise

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

@router.get("")
@router.get("/")
async def get_progetti():
    """Tutti i progetti + templates, con pallet_assegnato da pallet_state."""
    config    = carica_configurazione()
    data      = _load_progetti(config)
    templates = _load_templates(config)
    projects  = data.get("projects", [])

    # Migrazione: in_macchina → in_main (aggiunto stato in_lavorazione per log OpcUa)
    migrated = False
    for proj in projects:
        for step in proj.get("steps", []):
            for task in step.get("tasks", []):
                for pgm in task.get("programs", []):
                    if pgm.get("stato") == "in_macchina":
                        pgm["stato"] = "in_main"
                        migrated = True
    if migrated:
        _save_progetti(config, data)

    # Incrocia con pallet_state per avere pallet_assegnato aggiornato
    try:
        from api.routers.pallet import _load as _load_pallet, _pallet_path
        pallet_state = _load_pallet(config)
        pallet_map = {
            p["progetto_id"]: p["numero"]
            for p in pallet_state.get("pallet", [])
            if p.get("progetto_id")
        }
        for proj in projects:
            pid = proj.get("id")
            proj["pallet_assegnato"] = pallet_map.get(pid, None)
    except Exception as e:
        import traceback
        from utils.logger import get_logger as _gl; _gl("routers.progetti").warning(f"get_progetti: errore incrocio pallet_state: {e}", exc_info=True)

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


# ── Quick Tasks ──────────────────────────────────────────────────────────────

def _quick_tasks_path(config):
    folder = (config.get("tools_toa_folder") or "").strip()
    return Path(folder) / "quick_tasks.json" if folder else Path("quick_tasks.json")

@router.get("/quick-tasks")
async def get_quick_tasks():
    config = carica_configurazione()
    p = _quick_tasks_path(config)
    if p.exists():
        return json.loads(p.read_text(encoding="utf-8"))
    return {"tasks": []}

@router.put("/quick-tasks")
async def put_quick_tasks(body: dict):
    config = carica_configurazione()
    p = _quick_tasks_path(config)
    _atomic_write(p, body)
    return {"ok": True}


@router.put("/{project_id}")
async def update_progetto(project_id: str, body: ProgettoUpdate):
    """Salva un progetto (crea o aggiorna). Lock serializza con il poller."""
    config = carica_configurazione()
    async with _write_lock:
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


class BatchUpdate(BaseModel):
    projects: list  # lista completa dei progetti da salvare


@router.put("/batch/save")
async def batch_save_progetti(body: BatchUpdate):
    """
    Salva tutti i progetti in una singola scrittura atomica.
    Usato da persistProjects nel frontend — sostituisce N PUT sequenziali con 1.
    Riduce il carico sulla share Windows e la finestra di race condition.
    """
    config = carica_configurazione()
    async with _write_lock:
        data = _load_progetti(config)
        # Rimuove pallet_assegnato da tutti i progetti (gestito da pallet_state)
        cleaned = []
        for p in body.projects:
            if isinstance(p, dict):
                pc = dict(p)
                pc.pop("pallet_assegnato", None)
                cleaned.append(pc)
        data["projects"] = cleaned
        _save_progetti(config, data)
    return {"ok": True, "n_salvati": len(cleaned)}

@router.delete("/{project_id}")
async def delete_progetto(project_id: str):
    """Elimina un progetto."""
    config = carica_configurazione()
    async with _write_lock:
        data = _load_progetti(config)
        data["projects"] = [p for p in data.get("projects", []) if p.get("id") != project_id]
        _save_progetti(config, data)
    return {"ok": True}

@router.put("/{project_id}/pallet")
async def set_pallet_progetto(project_id: str, body: PalletAssoc):
    """Associa/rimuove un pallet a un progetto."""
    config = carica_configurazione()
    async with _write_lock:
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
    _atomic_write(path, body.templates)
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
        _atomic_write(path, body.templates)
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
        _atomic_write(path, list(existing_t.values()))

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


def _calcola_previsione_vita(projects: list, tools_db: dict, classify_fn, ordine_pallet: list = None, pallet_state_data: dict = None) -> list:
    """
    Per ogni utensile con vita_rimanente, simula il consumo cumulato
    scorrendo i progetti nell'ordine della coda macchina (ordine_pallet),
    poi i programmi di ciascun progetto in ordine numerico.

    life_remaining dal Sinumerik 840D è in MINUTI.
    TEMPO nei file MPF è in MINUTI.
    """
    # Costruisce mappa progetto_id → lista programmi da fare ordinati numericamente
    proj_map = {}
    for project in projects:
        p_id   = project.get("id")
        p_name = project.get("name", "?")
        pgm_list = []
        for step in project.get("steps", []):
            s_title = step.get("title", "")
            for task in step.get("tasks", []):
                if task.get("text", "").strip().lower() != "fresatura":
                    continue
                for pgm in task.get("programs", []):
                    if pgm.get("tipoGruppo") == "ipm": continue
                    stato = pgm.get("stato", "da_fare")
                    if stato not in ("in_main", "in_lavorazione", "in_macchina"): continue
                    alias = (pgm.get("utensile") or "").upper().strip()
                    try: tempo = int(pgm.get("tempoStimato") or 0)
                    except: tempo = 0
                    if not alias or not tempo: continue
                    pgm_list.append({
                        "progetto_id": p_id,
                        "progetto":    p_name,
                        "fase":        s_title,
                        "filename":    pgm.get("filename", ""),
                        "numPgm":      pgm.get("numPgm", ""),
                        "stato":       pgm.get("stato", "da_fare"),
                        "tempo":       tempo,
                        "alias":       alias,
                    })
        # Ordina numericamente per numPgm
        pgm_list.sort(key=lambda p: p["numPgm"].zfill(6))
        proj_map[p_id] = pgm_list

    # Costruisce la sequenza globale rispettando l'ordine pallet
    # ordine_pallet = [3, 4, 5] → pallet 3 prima, poi 4, poi 5
    sequenza_globale = []
    if ordine_pallet:
        # Usa pallet_state per sapere quale progetto è ATTUALMENTE sul pallet
        pallet_progetto = {}
        psd = pallet_state_data or {}
        for pal in psd.get("pallet", []):
            pid = pal.get("progetto_id")
            pnum = pal.get("numero")
            if pid and pnum:
                pallet_progetto[pnum] = pid

        for num_pallet in ordine_pallet:
            pid = pallet_progetto.get(num_pallet)
            if pid and pid in proj_map:
                sequenza_globale.extend(proj_map[pid])
        # Poi i progetti non in coda (senza ordine definito)
        pid_in_coda = set(pallet_progetto.get(n) for n in ordine_pallet if pallet_progetto.get(n))
        for project in projects:
            if project.get("id") not in pid_in_coda:
                sequenza_globale.extend(proj_map.get(project.get("id"), []))
    else:
        # Fallback: ordine array progetti
        for project in projects:
            sequenza_globale.extend(proj_map.get(project.get("id"), []))

    if not sequenza_globale:
        return []

    # Raggruppa la sequenza globale per utensile mantenendo l'ordine
    from collections import defaultdict
    utensile_queue: dict[str, list] = defaultdict(list)
    for pgm in sequenza_globale:
        utensile_queue[pgm["alias"]].append(pgm)

    alerts = []
    for alias, pgm_list in utensile_queue.items():
        abilitati = [
            t for t in tools_db.values()
            if (t.get("name") or "").upper().strip() == alias
            and t.get("is_enabled", True)
            and not t.get("is_worn", False)
        ]
        if not abilitati: continue

        # ── Logica gemelli corretta ───────────────────────────────────────────
        # Ogni programma è calibrato per consumare ~1 vita di utensile.
        # Al termine del programma il duplo usato viene inibito.
        # Il programma successivo chiama lo stesso alias e Siemens prende
        # il PRIMO gemello non inibito — quindi i gemelli si consumano uno per programma.
        #
        # Algoritmo: ordina i gemelli per vita rimanente decrescente
        # (Siemens prende il primo disponibile, che è tipicamente quello con più vita).
        # Poi assegna un gemello per programma e verifica se la vita copre il consumo.

        def vita_gemello(t):
            lr = t.get("life_remaining")
            lt = t.get("life_total")
            lp = t.get("life_percent")
            if lr is not None and lr > 0:
                return round(lr)
            if lt and lp is not None:
                return round((lp / 100) * lt)
            return 0

        # Ordina gemelli per vita decrescente (Siemens prende il più "fresco")
        gemelli_ordinati = sorted(abilitati, key=vita_gemello, reverse=True)
        n_gemelli = len(gemelli_ordinati)

        critico = None
        # Simulazione sequenziale: ogni programma consuma vita dal gemello corrente.
        # Quando la vita del gemello corrente si esaurisce, passa al successivo.
        # Alert solo quando nessun gemello riesce a coprire il programma corrente.
        gemelli_vita = [vita_gemello(g) for g in gemelli_ordinati]  # vita residua per gemello
        g_idx = 0  # gemello attuale

        for pgm in pgm_list:
            consumo = pgm["tempo"]
            if not consumo:
                continue

            # Consuma dal gemello corrente; se non basta, passa al successivo
            while g_idx < len(gemelli_vita):
                vita_disponibile = gemelli_vita[g_idx]
                if vita_disponibile >= consumo:
                    # Il gemello corrente copre questo programma
                    gemelli_vita[g_idx] -= consumo
                    break
                elif vita_disponibile > 0:
                    # Il gemello corrente copre parzialmente — passa al successivo
                    consumo -= vita_disponibile
                    gemelli_vita[g_idx] = 0
                    g_idx += 1
                else:
                    # Gemello esaurito — passa al successivo
                    g_idx += 1
            else:
                # Nessun gemello disponibile per questo programma
                critico = {
                    **pgm,
                    "minuto_rottura":   0,
                    "consumo_al_punto": pgm["tempo"],
                    "vita_gemello":     0,
                    "nessun_gemello":   True,
                }
                break

            # Controlla se il gemello corrente ha vita sufficiente dall'inizio
            # (non durante il while — verifica se il programma avrebbe causato alert)
            # Nota: se siamo arrivati qui senza break, il programma è coperto

        # Calcola consumo totale per il report
        consumo_tot = sum(p["tempo"] for p in pgm_list)
        vita_tot = sum(vita_gemello(g) for g in gemelli_ordinati)

        # surplus_mancante = quanto manca al punto critico (sempre positivo se è un vero problema)
        # - nessun_gemello: il programma non ha gemello disponibile → surplus = tempo del pgm
        # - consumo > vita: surplus = consumo - vita del gemello assegnato
        if critico:
            if critico.get("nessun_gemello"):
                surplus = critico["consumo_al_punto"]
            else:
                surplus = critico["consumo_al_punto"] - critico.get("vita_gemello", vita_tot)
                surplus = max(0, surplus)  # sempre >= 0
            alerts.append({
                "alias":              alias,
                "vita_rimanente":     vita_tot,
                "n_gemelli":          n_gemelli,
                "consumo_totale":     consumo_tot,
                "surplus_mancante":   surplus,
                "nessun_gemello":     critico.get("nessun_gemello", False),
                "programmi_n":        len(pgm_list),
                "programma_critico":  critico,
                "ok":                 False,
            })

    return sorted(alerts, key=lambda x: x["surplus_mancante"], reverse=True)


# Cache per analisi-setup — TTL 60 secondi
_analisi_setup_cache: dict = {"data": None, "ts": 0}
_ANALISI_SETUP_TTL = 300  # secondi (5 min — lettura disco è costosa)


def _invalidate_analisi_cache():
    """Invalida la cache di analisi-setup (chiamare dopo sync/modifiche)."""
    _analisi_setup_cache["data"] = None
    _analisi_setup_cache["ts"]   = 0


@router.get("/analisi-setup/non-utilizzati")
async def get_analisi_setup():
    """
    Confronta utensili in macchina con richiesti dai progetti attivi.
    Cache TTL 60s per evitare calcoli ripetuti.
    """
    import time as _time
    global _analisi_setup_cache
    now = _time.time()
    if _analisi_setup_cache["data"] and (now - _analisi_setup_cache["ts"]) < _ANALISI_SETUP_TTL:
        return _analisi_setup_cache["data"]
    from api.routers.progetti_utensili import estrai_alias_da_progetti
    from database.db_handler import auto_find_db_paths, carica_database, carica_database_utensili_smontati

    config      = carica_configurazione()
    alias_map   = estrai_alias_da_progetti(config)
    alias_attivi = set(alias_map.keys())

    # Carica progetti attivi per la previsione vita
    data_proj = _load_progetti(config)
    projects  = [p for p in data_proj.get("projects", [])
                 if not p.get("archived")]

    # Carica pallet_state per ordine_esecuzione e associazione pallet↔progetto
    try:
        from api.routers.pallet import _load as _load_pallet
        pallet_state_data = _load_pallet(config)
        # Inietta pallet_numero nei progetti
        for pal in pallet_state_data.get("pallet", []):
            pid = pal.get("progetto_id")
            if pid:
                for p in projects:
                    if p.get("id") == pid:
                        p["pallet_numero"] = pal["numero"]
    except Exception:
        pallet_state_data = {}

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

    result = {
        "non_utilizzati": sorted(non_utilizzati, key=lambda x: x["alias"]),
        "da_montare":     da_montare,
        "fin_vita":       sorted(fin_vita, key=lambda x: x.get("life_percent") or 0),
        "sync_time":      sync_time,
        "previsione_vita": _calcola_previsione_vita(
            projects, tools_db, _ct,
            ordine_pallet=pallet_state_data.get("ordine_esecuzione", []),
            pallet_state_data=pallet_state_data,
        ),
    }
    import time as _time
    _analisi_setup_cache["data"] = result
    _analisi_setup_cache["ts"]   = _time.time()
    return result


# ── Segna programmi in_macchina ────────────────────────────────────────────

@router.post("/{project_id}/avvia-tutti")
async def avvia_tutti(project_id: str):
    """
    Segna tutti i programmi 'da_fare' come 'in_macchina'.
    Usato dal pulsante Avvia nella pagina Macchina.
    """
    config   = carica_configurazione()
    data     = _load_progetti(config)
    projects = data.get("projects", [])
    project  = next((p for p in projects if p.get("id") == project_id), None)
    if not project:
        raise HTTPException(404, f"Progetto {project_id} non trovato")

    now = datetime.now().strftime("%d/%m/%Y %H:%M")
    aggiornati = 0
    for step in project.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in task.get("programs", []):
                if pgm.get("tipoGruppo") == "ipm":
                    continue
                if pgm.get("stato") == "da_fare":
                    pgm["stato"] = "in_main"
                    if not pgm.get("tempoInizio"):
                        pgm["tempoInizio"] = now
                    aggiornati += 1

    if aggiornati > 0:
        _save_progetti(config, data)

    return {"ok": True, "aggiornati": aggiornati}


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
                        pgm["stato"] = "in_main"
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
        _atomic_write(path, data_to_save)

        # Sincronizza la coda automaticamente:
        # se questo progetto ha un pallet assegnato, entra in coda
        try:
            from api.routers.pallet import sincronizza_coda
            await sincronizza_coda()
        except Exception:
            pass

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
    _atomic_write(path, {"projects": projects, "ultimo_aggiornamento": now})
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
    _atomic_write(path, deliveries)


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
                    import re as _re
                    testo = open(fpath, encoding="utf-8", errors="replace").read()
                    lines_mpf = testo.splitlines()
                    # Trova M6 e risale cercando T = "alias" nelle righe precedenti
                    alias = None
                    for idx_l, line in enumerate(lines_mpf):
                        if _re.search(r'\bM6\b', line):
                            for j in range(idx_l - 1, max(-1, idx_l - 6), -1):
                                m = _re.search(r'T\s*=\s*"([^"]+)"', lines_mpf[j])
                                if m:
                                    alias = m.group(1).strip().upper()
                                    break
                            break
                    # Fallback a TOOL COMMENT
                    if not alias:
                        for line in lines_mpf:
                            if "TOOL COMMENT:" in line.upper():
                                alias = line.split("TOOL COMMENT:")[-1].strip().upper()
                                break
                    # Fallback a parse_mpf_testo
                    if not alias:
                        aliases = parse_mpf_testo(testo)
                        if aliases:
                            alias = sorted(aliases)[0]
                    if alias:
                        pgm["utensile"] = alias
                        aggiornati += 1
                except Exception:
                    pass

    if aggiornati > 0:
        now = datetime.now().isoformat()
        tools_folder2 = (config.get("tools_toa_folder") or "").strip()
        path = Path(tools_folder2) / "worktrack_projects.json" if tools_folder2 else Path("worktrack_projects.json")
        _atomic_write(path, {"projects": projects, "ultimo_aggiornamento": now})

    return {"aggiornati": aggiornati, "project_id": project_id}



@router.post("/{project_id}/reset-stati-programmi")
async def reset_stati_programmi(project_id: str, body: dict = {}):
    """
    Resetta i programmi in_main/in_macchina/in_lavorazione → da_fare.
    Usato quando i programmi sono rimasti 'in corso' dopo un riavvio/reset sessione.
    
    body: { "escludi_corrente": "4350_0221_01_002.MPF" }  ← opzionale
    """
    config = carica_configurazione()
    data   = _load_progetti(config)
    projects = data.get("projects", [])

    progetto = next((p for p in projects if p.get("id") == project_id), None)
    if not progetto:
        raise HTTPException(status_code=404, detail="Progetto non trovato")

    escludi = (body.get("escludi_corrente") or "").upper().replace(".MPF", "")
    STATI_DA_RESETTARE = {"in_main", "in_macchina", "in_lavorazione"}
    resettati = 0

    for step in progetto.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in task.get("programs", []):
                if pgm.get("tipoGruppo") == "ipm":
                    continue
                stato = pgm.get("stato", "da_fare")
                fn = (pgm.get("filename") or "").upper().replace(".MPF", "")
                if stato in STATI_DA_RESETTARE and fn != escludi:
                    pgm["stato"] = "da_fare"
                    pgm["tempoInizio"] = None
                    pgm["tempoFine"] = None
                    resettati += 1

    if resettati > 0:
        async with _write_lock:
            _save_progetti(config, data)
            _invalidate_analisi_cache()

    return {"ok": True, "resettati": resettati, "progetto": progetto.get("name")}
