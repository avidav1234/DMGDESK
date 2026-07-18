"""
api/routers/cam_params.py
==========================
Parametri CAM per-procedura estratti da Cimatron (cam_tracker/cimatron_extract.py
su CAM35) — Fase 1 iniziativa "Classificazione percorsi NC + MAIN builder".

Router ADDITIVO: nessuna interazione con i flussi esistenti (nc_scanner,
regola d'oro, progetti). Vedi DATI_ESTRAIBILI_CIMATRON.md per la mappa campi.

POST /api/cam-params/upload                   multipart: dati(json) + anteprima(png, opz.)
GET  /api/cam-params/                         elenco progetti con parametri disponibili
GET  /api/cam-params/{commessa}/{posizione}   latest.json (ultima estrazione)
GET  /api/cam-params/{commessa}/{posizione}/versioni    lista versioni storiche
GET  /api/cam-params/{commessa}/{posizione}/versioni/{nome}   versione specifica
GET  /api/cam-params/{commessa}/{posizione}/anteprima   PNG anteprima pezzo

Storage (con STORICO — decisione 2026-07-10: ogni estrazione conservata per
la futura correlazione con le rotture):
    <tools_toa_folder>/parametri_cam/<commessa>_<posizione>/<ts>.json
                                                            /latest.json
                                                            /<ts>_anteprima.png
                                                            /latest_anteprima.png
Override cartella per test/dev: env DMG_CAM_PARAMS_DIR.
"""

import json
import os
import re
import shutil
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile
from fastapi.responses import FileResponse

from database.db_handler import carica_configurazione
from utils.logger import get_logger

log = get_logger(__name__)
router = APIRouter()

# Nome file versione: timestamp compatto, ordinabile lessicograficamente
_RE_TOKEN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_RE_VERSIONE = re.compile(r"^\d{8}-\d{6}\.json$")

# Limite difensivo sul payload JSON (il dump tipico è 50-200 KB)
MAX_JSON_BYTES = 20 * 1024 * 1024
MAX_PNG_BYTES = 10 * 1024 * 1024


def _base_dir() -> Path:
    override = (os.environ.get("DMG_CAM_PARAMS_DIR") or "").strip()
    if override:
        return Path(override)
    config = carica_configurazione()
    base = (config.get("tools_toa_folder") or ".").strip() or "."
    return Path(base) / "parametri_cam"


def _token(valore: str, campo: str) -> str:
    """Valida un componente path (anti-traversal): solo [A-Za-z0-9._-]."""
    v = (valore or "").strip()
    if not _RE_TOKEN.match(v) or v in (".", ".."):
        raise HTTPException(status_code=400, detail=f"{campo} non valido: {valore!r}")
    return v


def _proj_dir(commessa: str, posizione: str, must_exist: bool = True) -> Path:
    d = _base_dir() / f"{_token(commessa, 'commessa')}_{_token(posizione, 'posizione')}"
    if must_exist and not d.is_dir():
        raise HTTPException(status_code=404,
                            detail=f"nessun parametro CAM per {commessa}/{posizione}")
    return d


# ─────────────────────────────────────────────────────────────────────────────
# Upload dall'estrattore (CAM35)
# ─────────────────────────────────────────────────────────────────────────────

@router.post("/upload", summary="Riceve un'estrazione parametri da CAM35")
async def upload_parametri(
    dati: UploadFile = File(...),
    anteprima: UploadFile | None = File(None),
):
    raw = await dati.read()
    if len(raw) > MAX_JSON_BYTES:
        raise HTTPException(status_code=413, detail="JSON parametri troppo grande")
    try:
        payload = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=400, detail=f"JSON non valido: {e}")

    # Validazione minima dello schema (bordo di ingresso)
    doc = payload.get("documento") or {}
    procedure = payload.get("procedure")
    if not isinstance(procedure, list) or not doc.get("commessa") or not doc.get("posizione"):
        raise HTTPException(status_code=400,
                            detail="payload incompleto: servono documento.commessa/posizione e procedure[]")

    commessa = _token(str(doc["commessa"]), "commessa")
    posizione = _token(str(doc["posizione"]), "posizione")

    # timestamp versione dal payload (estratto_il ISO) o adesso
    ts = None
    try:
        ts = datetime.fromisoformat(payload.get("estratto_il", "")) \
                     .strftime("%Y%m%d-%H%M%S")
    except (TypeError, ValueError):
        ts = datetime.now().strftime("%Y%m%d-%H%M%S")

    proj = _proj_dir(commessa, posizione, must_exist=False)
    try:
        proj.mkdir(parents=True, exist_ok=True)

        json_path = proj / f"{ts}.json"
        tmp = json_path.with_suffix(".tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(payload, f, ensure_ascii=False, indent=1)
        os.replace(tmp, json_path)                       # atomico

        # latest = SOLO se questa è la versione più recente: la coda di
        # recupero dell'estrattore può consegnare versioni vecchie DOPO le
        # nuove (retry fuori ordine) e non deve mai regredire il latest.
        # I nomi versione (YYYYMMDD-HHMMSS) ordinano lessicograficamente.
        piu_recente = max(p.name for p in proj.glob("*.json")
                          if _RE_VERSIONE.match(p.name))
        e_latest = json_path.name == piu_recente
        if e_latest:
            shutil.copyfile(json_path, proj / "latest.json")

        png_salvata = False
        if anteprima is not None:
            png_raw = await anteprima.read()
            if png_raw and len(png_raw) <= MAX_PNG_BYTES:
                png_path = proj / f"{ts}_anteprima.png"
                tmp_png = png_path.with_suffix(".tmp")
                with open(tmp_png, "wb") as f:
                    f.write(png_raw)
                os.replace(tmp_png, png_path)
                if e_latest:
                    shutil.copyfile(png_path, proj / "latest_anteprima.png")
                png_salvata = True
    except OSError as e:
        log.error(f"[cam-params] salvataggio fallito per {commessa}/{posizione}: {e}")
        raise HTTPException(status_code=500, detail=f"salvataggio fallito: {e}")

    log.info(f"[cam-params] upload {commessa}/{posizione}: "
             f"{len(procedure)} procedure, versione {ts}, png={png_salvata}")
    return {"ok": True, "commessa": commessa, "posizione": posizione,
            "versione": f"{ts}.json", "n_procedure": len(procedure),
            "anteprima": png_salvata}


# ─────────────────────────────────────────────────────────────────────────────
# Lettura (frontend / classificatore)
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/", summary="Elenco progetti con parametri CAM disponibili")
async def lista_progetti():
    base = _base_dir()
    if not base.is_dir():
        return {"progetti": []}
    out = []
    for d in sorted(base.iterdir()):
        latest = d / "latest.json"
        if not (d.is_dir() and latest.is_file()):
            continue
        voce = {"cartella": d.name}
        try:
            with open(latest, encoding="utf-8") as f:
                dati = json.load(f)
            voce.update({
                "commessa": (dati.get("documento") or {}).get("commessa"),
                "posizione": (dati.get("documento") or {}).get("posizione"),
                "titolo": (dati.get("documento") or {}).get("titolo"),
                "estratto_il": dati.get("estratto_il"),
                "n_procedure": dati.get("n_procedure"),
                "anteprima": (d / "latest_anteprima.png").is_file(),
            })
        except (OSError, json.JSONDecodeError) as e:
            voce["errore"] = str(e)
        out.append(voce)
    return {"progetti": out}


@router.get("/{commessa}/{posizione}", summary="Ultima estrazione (latest)")
async def get_latest(commessa: str, posizione: str):
    proj = _proj_dir(commessa, posizione)
    latest = proj / "latest.json"
    if not latest.is_file():
        raise HTTPException(status_code=404, detail="latest.json assente")
    try:
        with open(latest, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"lettura fallita: {e}")


@router.get("/{commessa}/{posizione}/versioni", summary="Versioni storiche disponibili")
async def lista_versioni(commessa: str, posizione: str):
    proj = _proj_dir(commessa, posizione)
    versioni = sorted((p.name for p in proj.glob("*.json")
                       if _RE_VERSIONE.match(p.name)), reverse=True)
    return {"versioni": versioni}


@router.get("/{commessa}/{posizione}/versioni/{nome}", summary="Versione specifica")
async def get_versione(commessa: str, posizione: str, nome: str):
    if not _RE_VERSIONE.match(nome):
        raise HTTPException(status_code=400, detail=f"nome versione non valido: {nome!r}")
    path = _proj_dir(commessa, posizione) / nome
    if not path.is_file():
        raise HTTPException(status_code=404, detail="versione non trovata")
    try:
        with open(path, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"lettura fallita: {e}")


@router.get("/{commessa}/{posizione}/anteprima", summary="Anteprima PNG del pezzo")
async def get_anteprima(commessa: str, posizione: str):
    png = _proj_dir(commessa, posizione) / "latest_anteprima.png"
    if not png.is_file():
        raise HTTPException(status_code=404, detail="anteprima non disponibile")
    return FileResponse(str(png), media_type="image/png")


@router.get("/{commessa}/{posizione}/matching",
            summary="Matching procedure CAM ↔ programmi MPF del progetto DD")
async def get_matching(commessa: str, posizione: str):
    """
    Calcola on-demand il matching fra l'ultima estrazione e i programmi del
    progetto DD `<commessa>_<posizione>` (logica pura in logic/cam_matching.py).
    Sola lettura: non modifica né l'estrazione né il progetto.
    """
    # estrazione (latest)
    proj_dir = _proj_dir(commessa, posizione)
    latest = proj_dir / "latest.json"
    if not latest.is_file():
        raise HTTPException(status_code=404, detail="nessuna estrazione disponibile")
    try:
        with open(latest, encoding="utf-8") as f:
            estrazione = json.load(f)
    except (OSError, json.JSONDecodeError) as e:
        raise HTTPException(status_code=500, detail=f"lettura estrazione fallita: {e}")

    # progetto DD con name esatto "<commessa>_<posizione>"
    from api.routers.progetti import _load_progetti
    from database.db_handler import carica_configurazione as _cfg
    from logic.cam_matching import match_progetto

    nome_atteso = f"{_token(commessa, 'commessa')}_{_token(posizione, 'posizione')}"
    dati = _load_progetti(_cfg())
    progetto = next((p for p in dati.get("projects", [])
                     if str(p.get("name") or "").strip() == nome_atteso), None)
    if progetto is None:
        candidati = [str(p.get("name")) for p in dati.get("projects", [])
                     if str(p.get("name") or "").startswith(nome_atteso)]
        raise HTTPException(
            status_code=404,
            detail=f"progetto DD {nome_atteso!r} non trovato"
                   + (f" — simili: {candidati}" if candidati else ""))

    programmi = [pg for s in progetto.get("steps", [])
                 for t in s.get("tasks", [])
                 for pg in t.get("programs", [])]
    risultato = match_progetto(estrazione.get("procedure", []), programmi)

    # Arricchimento: parametri compatti + CLASSE (motore di classificazione)
    # per ogni procedura matchata, così il frontend non fa alcun join.
    from logic.cam_classificatore import classifica_procedura, carica_regole
    try:
        regole = carica_regole()
    except Exception as e:
        log.warning(f"[cam-params] regole classificazione non caricabili: {e}")
        regole = None

    per_numero = {p.get("numero"): p for p in estrazione.get("procedure", [])
                  if p.get("numero") is not None}
    for r in risultato["programmi"]:
        for pr in r["procedure"]:
            src = per_numero.get(pr.get("numero"))
            if not src:
                continue
            if regole is not None:
                try:
                    c = classifica_procedura(src, regole)
                    pr["classe"] = {
                        "esito": c["esito"], "operazione": c["operazione"],
                        "tolleranza": c["tolleranza"], "presidio": c["presidio"],
                        "confidenza": c["confidenza"], "riga": c["riga"],
                        "motivo": c["motivo"],
                    }
                except Exception as e:
                    log.warning(f"[cam-params] classificazione fallita "
                                f"proc {pr.get('numero')}: {e}")
            off = src.get("offset") or {}
            mac = src.get("macchina") or {}
            ut = src.get("utensile") or {}
            tra = src.get("traiettoria") or {}
            # ap = profondità di passata (passo Z), ae = larghezza di passata
            # (passo laterale, o passo orizzontale per le finiture piani)
            ap = tra.get("passo_z_fisso")
            if ap is None:
                ap = tra.get("passo_z")
            ae = tra.get("passo_laterale")
            if ae is None:
                ae = tra.get("passo_orizzontale")
            pr["parametri"] = {
                "strategia": src.get("strategia"),
                "sotto_strategia": src.get("sotto_strategia"),
                "pu": src.get("pu"),
                "commento": src.get("commento"),
                "sr": src.get("sr"),
                # Offset "principale" mostrato: parete → parte → superfici_mw.
                # Le procedure ModuleWorks in modo Avanzate (Multi Asse, Operazioni
                # Locali, Ripresa Guidata) hanno l'offset solo in superfici_mw, letto
                # dal blob GetModuleworksParameters al byte 597 (estrattore v1.3, NON
                # invasivo): senza questo fallback la vista non mostrava alcun offset MW.
                "offset_parete": next((v for v in (off.get("parete"), off.get("parte"),
                                                    off.get("superfici_mw")) if v is not None), None),
                "offset_fondo": off.get("fondo"),
                "offset_contorno": off.get("contorno"),
                "offset_superfici_mw": off.get("superfici_mw"),
                "toll_superfici": (src.get("tolleranze") or {}).get("superfici"),
                "fz": mac.get("fz"),
                "vc": mac.get("vc"),
                "ap": ap,
                "ae": ae,
                "alias": ut.get("alias"),
                "fori": (src.get("foratura") or {}).get("designazioni")
                        if src.get("foratura") else None,
            }

    risultato["estrazione"] = {
        "estratto_il": estrazione.get("estratto_il"),
        "titolo": (estrazione.get("documento") or {}).get("titolo"),
    }
    risultato["progetto_dd"] = {"id": progetto.get("id"), "name": progetto.get("name")}
    return risultato
