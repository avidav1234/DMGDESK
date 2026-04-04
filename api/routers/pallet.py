"""
api/routers/pallet.py
Gestisce la persistenza degli stati pallet in pallet_state.json sulla share.

Stati possibili: vuoto | grezzo | in_lavorazione | finito | guasto
- in_lavorazione viene scritto dal router macchina_live (dalla macchina via log)
- vuoto / grezzo / guasto vengono impostati dall'operatore via questo router
- finito viene impostato automaticamente quando in_lavorazione → altro
"""

import json
import os
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from database.db_handler import carica_configurazione
from api.routers.progetti import (
    _load_progetti, _save_progetti, _progetti_path,
    _invalidate_analisi_cache, _write_lock as _proj_write_lock,
)

router = APIRouter()

STATI_VALIDI   = {"vuoto", "grezzo", "in_lavorazione", "finito", "guasto"}
STATI_MANUALI  = {"vuoto", "grezzo", "guasto", "finito"}   # operatore può impostare questi
N_PALLET       = 6


def _pallet_path(config: dict) -> Path:
    """Salva pallet_state.json nella stessa cartella di tools_machine.json."""
    base = (config.get("tools_toa_folder") or "").strip()
    if not base:
        # fallback: radice da percorso_nc_base
        nc = (config.get("percorso_nc_base") or "").strip()
        if nc:
            from pathlib import PurePath
            parts = PurePath(nc).parts
            base = str(Path(parts[0]) / parts[1]) if len(parts) >= 2 else nc
    if not base:
        base = "."
    return Path(base) / "pallet_state.json"


def _default_state() -> dict:
    return {
        "pallet": [
            {
                "numero":          i + 1,
                "stato":           "vuoto",
                "programma":       None,
                "main":            None,
                "commessa":        None,
                "aggiornato":      None,
                "progetto_id":     None,
                "progetto_nome":   None,
                "progetto_colore": None,
                "pct_avanzamento": None,
            }
            for i in range(N_PALLET)
        ],
        "ultimo_aggiornamento": None,
    }


_pallet_cache: dict = {"data": None, "mtime": 0.0}

def _load(config: dict) -> dict:
    path = _pallet_path(config)
    try:
        mtime = path.stat().st_mtime if path.exists() else 0.0
    except OSError:
        mtime = 0.0

    if _pallet_cache["data"] is not None and mtime == _pallet_cache["mtime"]:
        return _pallet_cache["data"]

    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(data, dict) or not isinstance(data.get("pallet"), list):
                raise ValueError("struttura pallet_state.json non valida")
            for p in data.get("pallet", []):
                p.setdefault("progetto_id", None)
                p.setdefault("progetto_nome", None)
                p.setdefault("progetto_colore", None)
                p.setdefault("pct_avanzamento", None)
            _pallet_cache["data"]  = data
            _pallet_cache["mtime"] = mtime
            return data
        except (json.JSONDecodeError, ValueError) as e:
            from utils.logger import get_logger as _get_log
            _get_log("routers.pallet").error(
                f"pallet_state.json corrotto: {e} — uso struttura di default"
            )
        except Exception:
            pass
    return _default_state()


def _save(config: dict, state: dict):
    """Scrittura atomica: scrive su .tmp poi rinomina — sicuro su crash/spegnimento."""
    _pallet_cache["data"] = None  # invalida cache
    path = _pallet_path(config)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        state["ultimo_aggiornamento"] = datetime.now().isoformat()
        tmp = path.with_suffix(".tmp")
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        try: path.with_suffix(".tmp").unlink(missing_ok=True)
        except Exception: pass
        raise HTTPException(status_code=500, detail=f"Impossibile salvare pallet_state.json: {e}")


# ── Modelli ────────────────────────────────────────────────────────────────


def _sincronizza_pallet_progetto(config: dict, stato_pallet: str, progetto_id: str, now: str):
    """
    Sincronizza lo stato del pallet con il progetto assegnato.

    vuoto   → rimuove pallet_assegnato dal progetto (pallet libero)
    grezzo  → nessuna azione (pronto da lavorare)
    guasto  → nessuna azione (problema hardware)
    finito  → segna tutti i programmi in_macchina come completati nel progetto
    """
    from pathlib import Path as _Path
    import json as _json

    data     = _load_progetti(config)
    projects = data.get("projects", [])
    project  = next((p for p in projects if p.get("id") == progetto_id), None)
    if not project:
        return

    changed = False

    if stato_pallet == "vuoto":
        # Pallet liberato — rimuovi il legame dal progetto
        if project.get("pallet_assegnato") is not None:
            project["pallet_assegnato"] = None
            changed = True

    elif stato_pallet == "finito":
        # Pallet finito — segna tutti i programmi in_macchina come completati
        for step in project.get("steps", []):
            for task in step.get("tasks", []):
                if task.get("text", "").strip().lower() != "fresatura":
                    continue
                for pgm in task.get("programs", []):
                    if pgm.get("stato") in ("in_macchina", "in_main", "in_lavorazione"):
                        pgm["stato"]    = "completato"
                        pgm["tempoFine"] = now
                        changed = True

        # Controlla se tutto è completato
        all_pgm = [pgm
                   for step in project.get("steps", [])
                   for task in step.get("tasks", [])
                   if task.get("text","").strip().lower() == "fresatura"
                   for pgm in task.get("programs", [])
                   if pgm.get("tipoGruppo") != "ipm"]
        if all_pgm and all(p.get("stato") == "completato" for p in all_pgm):
            # Segna anche il task fresatura come done
            for step in project.get("steps", []):
                for task in step.get("tasks", []):
                    if task.get("text","").strip().lower() == "fresatura":
                        task["done"]   = True
                        task["doneAt"] = now[:10]
                        changed = True

    if changed:
        from api.routers.progetti import _atomic_write as _aw
        path = _progetti_path(config)
        _aw(path, {"projects": projects, "ultimo_aggiornamento": now})


class SetStatoBody(BaseModel):
    stato:    str
    programma: str | None = None
    main:      str | None = None
    commessa:  str | None = None


class SetLavorazioneBody(BaseModel):
    """Usato internamente da macchina_live per aggiornare il pallet in lavorazione."""
    pallet_attivo:    int | None
    programma_attivo: str | None = None


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("")
@router.get("/")
async def get_pallet():
    """Restituisce lo stato attuale di tutti i pallet.
    Garantisce che al massimo 1 pallet sia in_lavorazione —
    se ce ne sono più di uno (inconsistenza), tieni il più recente.
    """
    config = carica_configurazione()
    state  = _load(config)
    pallets = state.get("pallet", [])

    # Trova tutti i pallet in_lavorazione
    in_lav = [p for p in pallets if (p.get("stato") or "").lower() == "in_lavorazione"]

    if len(in_lav) > 1:
        # Tieni solo quello con aggiornato più recente, rimetti gli altri a grezzo
        in_lav_sorted = sorted(
            in_lav,
            key=lambda p: p.get("aggiornato") or "",
            reverse=True
        )
        da_resettare = in_lav_sorted[1:]  # tutti tranne il più recente
        ids_reset = {p.get("numero") for p in da_resettare}
        for p in pallets:
            if p.get("numero") in ids_reset:
                p["stato"] = "grezzo"
        # Salva la correzione
        _save(config, state)

    return state

@router.get("/debug-path")
async def debug_pallet_path():
    """Debug: mostra dove viene cercato pallet_state.json."""
    config = carica_configurazione()
    path = _pallet_path(config)
    return {
        "path": str(path),
        "exists": path.exists(),
        "tools_toa_folder": config.get("tools_toa_folder"),
        "percorso_nc_base": config.get("percorso_nc_base"),
    }


@router.patch("/{numero}")
async def set_stato_pallet(numero: int, body: SetStatoBody):
    """
    Imposta lo stato di un pallet manualmente.
    Solo stati manuali: vuoto | grezzo | guasto.
    """
    if not 1 <= numero <= N_PALLET:
        raise HTTPException(400, f"Numero pallet non valido: {numero} (1-{N_PALLET})")
    if body.stato not in STATI_MANUALI:
        raise HTTPException(400, f"Stato '{body.stato}' non impostabile manualmente. Usa: {STATI_MANUALI}")

    config = carica_configurazione()
    state  = _load(config)

    now = datetime.now().isoformat()
    pallet_found = None
    for p in state["pallet"]:
        if p["numero"] == numero:
            p["stato"]     = body.stato
            p["aggiornato"] = now
            if body.programma is not None: p["programma"] = body.programma
            if body.main      is not None: p["main"]      = body.main
            if body.commessa  is not None: p["commessa"]  = body.commessa
            pallet_found = p
            break
    else:
        raise HTTPException(404, f"Pallet {numero} non trovato")

    _save(config, state)

    # ── Storico cicli ──────────────────────────────────────────────────────
    if progetto_id:
        try:
            from api.routers.pallet_history import on_pallet_stato_changed
            from api.routers.progetti import _load_progetti
            proj_data = _load_progetti(config)
            proj = next((p for p in proj_data.get("projects", [])
                         if p.get("id") == progetto_id), None)
            n_pgm = sum(
                1 for s in (proj or {}).get("steps", [])
                for t in s.get("tasks", [])
                if t.get("text", "").lower() == "fresatura"
                for pg in t.get("programs", [])
                if pg.get("tipoGruppo") != "ipm"
            ) if proj else 0
            on_pallet_stato_changed(
                numero, body.stato,
                progetto_id, pallet_found.get("progetto_nome"),
                n_pgm, config
            )
        except Exception:
            pass

    # ── Sincronizzazione stato pallet → progetto ───────────────────────────
    progetto_id = pallet_found.get("progetto_id")
    if progetto_id:
        try:
            _sincronizza_pallet_progetto(config, body.stato, progetto_id, now)
        except Exception:
            pass  # non blocca la risposta
    return {"ok": True, "pallet": numero, "stato": body.stato}


@router.post("/sync-lavorazione")
async def sync_lavorazione(body: SetLavorazioneBody):
    """
    Chiamato automaticamente dal frontend dopo ogni poll del log.
    Aggiorna: pallet_attivo → in_lavorazione, precedente in_lavorazione → finito.
    """
    config = carica_configurazione()
    state  = _load(config)

    for p in state["pallet"]:
        if body.pallet_attivo and p["numero"] == body.pallet_attivo:
            # Pallet preso dalla macchina
            p["stato"]     = "in_lavorazione"
            p["programma"] = body.programma_attivo
            p["aggiornato"] = datetime.now().isoformat()
        elif p["stato"] == "in_lavorazione" and p["numero"] != body.pallet_attivo:
            # Pallet che era in lavorazione → finito
            p["stato"]     = "finito"
            p["aggiornato"] = datetime.now().isoformat()

    _save(config, state)
    return {"ok": True}


@router.post("/invia-programma/{numero}")
async def invia_programma(numero: int, body: SetStatoBody):
    """
    Chiamato quando l'operatore invia programmi in macchina per questo pallet.
    Imposta automaticamente stato=grezzo + associa programma/commessa.
    """
    if not 1 <= numero <= N_PALLET:
        raise HTTPException(400, f"Numero pallet non valido: {numero}")

    config = carica_configurazione()
    state  = _load(config)

    for p in state["pallet"]:
        if p["numero"] == numero:
            p["stato"]     = "grezzo"
            p["programma"] = body.programma
            p["main"]      = body.main
            p["commessa"]  = body.commessa
            p["aggiornato"] = datetime.now().isoformat()
            break

    _save(config, state)
    return {"ok": True, "pallet": numero, "stato": "grezzo"}

# ── Assegna progetto a pallet ──────────────────────────────────────────────

class AssegnaProgettoBody(BaseModel):
    progetto_id:     str | None = None
    progetto_nome:   str | None = None
    progetto_colore: str | None = None

@router.patch("/{numero}/assegna-progetto")
async def assegna_progetto(numero: int, body: AssegnaProgettoBody):
    """
    Unica scrittura per il legame pallet ↔ progetto.
    - progetto_id valorizzato → assegna + passa a GREZZO se era VUOTO
    - progetto_id=null → rimuove assegnazione + passa a VUOTO
    """
    config = carica_configurazione()
    state  = _load(config)
    now    = datetime.now().isoformat()

    for p in state["pallet"]:
        if p["numero"] == numero:

            if body.progetto_id:
                stato_attuale = p.get("stato", "vuoto")
                # Blocca se non è VUOTO (a meno che non sia già lo stesso progetto)
                if stato_attuale != "vuoto" and p.get("progetto_id") != body.progetto_id:
                    raise HTTPException(409,
                        f"Pallet {numero} è '{stato_attuale}' con progetto già assegnato. "
                        f"Sgancia prima il progetto corrente.")
                # Blocca se il progetto è già assegnato a un altro pallet
                altri = [x for x in state["pallet"]
                         if x.get("progetto_id") == body.progetto_id
                         and x["numero"] != numero]
                if altri:
                    raise HTTPException(409,
                        f"Il progetto è già assegnato al Pallet {altri[0]['numero']}. "
                        f"Sgancia prima.")

            p["progetto_id"]     = body.progetto_id
            p["progetto_nome"]   = body.progetto_nome
            p["progetto_colore"] = body.progetto_colore
            p["aggiornato"]      = now

            if body.progetto_id:
                if p.get("stato", "vuoto") == "vuoto":
                    p["stato"] = "grezzo"
            else:
                if p.get("stato") not in ("in_lavorazione",):
                    p["stato"] = "vuoto"

            _save(config, state)

            # Sincronizza coda automaticamente dopo assegnazione
            try:
                await sincronizza_coda()
            except Exception:
                pass

            return {"ok": True, "pallet": numero,
                    "progetto_id": body.progetto_id,
                    "stato": p["stato"]}

    raise HTTPException(404, f"Pallet {numero} non trovato")


@router.get("/{numero}/progetto-info")
async def get_progetto_info(numero: int):
    """Ritorna info progetto + avanzamento per un pallet."""
    config = carica_configurazione()
    state  = _load(config)
    pallet = next((p for p in state["pallet"] if p["numero"] == numero), None)
    if not pallet:
        raise HTTPException(404, "Pallet non trovato")

    pid = pallet.get("progetto_id")
    if not pid:
        return {"pallet": numero, "progetto": None}

    data    = _load_progetti(config)
    project = next((p for p in data.get("projects", []) if p.get("id") == pid), None)
    if not project:
        return {"pallet": numero, "progetto": None}

    all_pgm = [pgm
               for step in project.get("steps", [])
               for task in step.get("tasks", [])
               if task.get("text","").strip().lower() == "fresatura"
               for pgm in task.get("programs", [])
               if pgm.get("tipoGruppo") != "ipm"]

    totale     = len(all_pgm)
    completati = sum(1 for p in all_pgm if p.get("stato") == "completato")
    in_mac     = sum(1 for p in all_pgm if p.get("stato") in ("in_main", "in_lavorazione"))
    pct        = round(completati / totale * 100, 1) if totale else 0

    return {
        "pallet": numero,
        "progetto": {
            "id":          project.get("id"),
            "nome":        project.get("name"),
            "colore":      project.get("color", "#1D5FAD"),
            "totale":      totale,
            "completati":  completati,
            "in_macchina": in_mac,
            "pct":         pct,
            "da_fare":     sum(1 for p in all_pgm if p.get("stato") == "da_fare"),
        }
    }


@router.get("/{numero}/programmi-in-macchina")
async def get_programmi_in_macchina(numero: int):
    """
    Restituisce i programmi in stato 'in_macchina' per il progetto assegnato al pallet.
    Ordinati numericamente. Usato dal pannello stato programmi.
    """
    config  = carica_configurazione()
    state   = _load(config)
    pallet  = next((p for p in state["pallet"] if p["numero"] == numero), None)
    if not pallet or not pallet.get("progetto_id"):
        return {"pallet": numero, "programmi": [], "progetto": None}

    pid  = pallet["progetto_id"]
    data = _load_progetti(config)
    proj = next((p for p in data.get("projects", []) if p.get("id") == pid), None)
    if not proj:
        return {"pallet": numero, "programmi": [], "progetto": None}

    programmi = []
    for step in proj.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in task.get("programs", []):
                if pgm.get("tipoGruppo") == "ipm": continue
                if pgm.get("stato") not in ("in_macchina", "in_main", "in_lavorazione"): continue
                programmi.append({
                    "id":           pgm.get("id"),
                    "filename":     pgm.get("filename", ""),
                    "numPgm":       pgm.get("numPgm", ""),
                    "utensile":     pgm.get("utensile", ""),
                    "tempoStimato": pgm.get("tempoStimato", ""),
                    "stato":        pgm.get("stato"),
                    "tempoInizio":  pgm.get("tempoInizio"),
                })

    programmi.sort(key=lambda p: str(p["numPgm"]).zfill(6))
    return {
        "pallet":    numero,
        "progetto":  {"id": proj["id"], "nome": proj.get("name"), "colore": proj.get("color", "#1D5FAD")},
        "programmi": programmi,
    }


@router.patch("/{numero}/programmi-completa")
async def completa_programmi(numero: int, body: dict):
    """
    Segna una lista di programmi come 'completato'.
    Body: { "ids": ["abc123", "def456"] }
    """
    from datetime import datetime as _dt
    config  = carica_configurazione()
    state   = _load(config)
    pallet  = next((p for p in state["pallet"] if p["numero"] == numero), None)
    if not pallet or not pallet.get("progetto_id"):
        raise HTTPException(404, "Pallet senza progetto")

    pid  = pallet["progetto_id"]
    data = _load_progetti(config)
    proj = next((p for p in data.get("projects", []) if p.get("id") == pid), None)
    if not proj:
        raise HTTPException(404, "Progetto non trovato")

    ids     = set(body.get("ids", []))
    ora     = _dt.now().strftime("%d/%m/%Y %H:%M")
    count   = 0
    for step in proj.get("steps", []):
        for task in step.get("tasks", []):
            for pgm in task.get("programs", []):
                if pgm.get("id") in ids and pgm.get("stato") in ("in_macchina", "in_main", "in_lavorazione"):
                    pgm["stato"]    = "completato"
                    pgm["tempoFine"] = ora
                    count += 1

    _save_progetti(config, data)
    try:
        _invalidate_analisi_cache()
    except Exception: pass
    return {"ok": True, "completati": count}


@router.post("/sync-progetti")
async def sync_pallet_progetti():
    """
    Allinea i legami pallet ↔ progetti.
    Percorre tutti i pallet con progetto_id e verifica che il progetto
    abbia pallet_assegnato corretto. E viceversa.
    """
    import json as _json

    config   = carica_configurazione()
    state    = _load(config)
    proj_data = _load_progetti(config)
    projects  = proj_data.get("projects", [])
    changed   = 0

    # 1. Per ogni pallet con progetto_id → assicura che il progetto lo sappia
    for pal in state["pallet"]:
        pid = pal.get("progetto_id")
        if not pid:
            continue
        proj = next((p for p in projects if p.get("id") == pid), None)
        if proj and proj.get("pallet_assegnato") != pal["numero"]:
            proj["pallet_assegnato"] = pal["numero"]
            changed += 1

    # 2. Per ogni progetto con pallet_assegnato → assicura che il pallet lo sappia
    for proj in projects:
        pa = proj.get("pallet_assegnato")
        if not pa:
            continue
        pal = next((p for p in state["pallet"] if p["numero"] == pa), None)
        if pal and pal.get("progetto_id") != proj.get("id"):
            pal["progetto_id"]     = proj["id"]
            pal["progetto_nome"]   = proj.get("name")
            pal["progetto_colore"] = proj.get("color", "#1D5FAD")
            changed += 1

    if changed:
        now = datetime.now().isoformat()
        _save(config, state)
        from api.routers.progetti import _atomic_write as _aw
        path = _progetti_path(config)
        _aw(path, {"projects": projects, "ultimo_aggiornamento": now})

    return {"ok": True, "allineamenti": changed}

@router.get("/disponibili")
async def get_pallet_disponibili():
    """Ritorna i pallet VUOTI senza progetto assegnato."""
    config = carica_configurazione()
    state  = _load(config)
    return {
        "pallet": [
            {"numero": p["numero"], "stato": p["stato"]}
            for p in state["pallet"]
            if p.get("stato", "vuoto") == "vuoto"
            and not p.get("progetto_id")
        ]
    }


@router.post("/{numero}/avvia")
async def avvia_pallet(numero: int):
    """
    Avvia un pallet — lo segna IN LAVORAZIONE.
    NON cambia lo stato dei programmi (quello avviene quando si genera il MAIN).
    Gestisce il pallet precedentemente IN LAVORAZIONE:
      - ha ancora programmi in_macchina → torna GREZZO
      - tutti completati → FINITO
    Solo un pallet IN LAVORAZIONE alla volta.
    """
    from datetime import datetime as _dt
    config = carica_configurazione()
    state  = _load(config)
    data   = _load_progetti(config)

    pallet_target = next((p for p in state["pallet"] if p["numero"] == numero), None)
    if not pallet_target:
        raise HTTPException(404, f"Pallet {numero} non trovato")

    now = _dt.now().strftime("%d/%m/%Y %H:%M")

    # Gestisci il pallet precedentemente IN LAVORAZIONE
    for p in state["pallet"]:
        if p["numero"] != numero and \
           (p.get("stato") or "").lower().replace(" ","_") == "in_lavorazione":
            pid = p.get("progetto_id")
            if pid:
                proj = next((pr for pr in data.get("projects",[]) if pr.get("id")==pid), None)
                if proj:
                    all_pgm = [pg for s in proj.get("steps",[])
                               for t in s.get("tasks",[])
                               if t.get("text","").strip().lower()=="fresatura"
                               for pg in t.get("programs",[])
                               if pg.get("tipoGruppo")!="ipm"]
                    all_done = all_pgm and all(pg.get("stato")=="completato" for pg in all_pgm)
                    p["stato"] = "finito" if all_done else "grezzo"
            else:
                p["stato"] = "grezzo"

    # Imposta il pallet target IN LAVORAZIONE
    pallet_target["stato"]      = "in_lavorazione"
    pallet_target["aggiornato"] = now

    _save(config, state)
    try:
        _invalidate_analisi_cache()
    except Exception: pass
    return {"ok": True, "pallet": numero, "stato": "in_lavorazione"}

@router.get("/ordine-esecuzione")
async def get_ordine_esecuzione():
    """Legge l'ordine di esecuzione pallet dalla coda macchina."""
    config = carica_configurazione()
    state  = _load(config)
    return {
        "ordine": state.get("ordine_esecuzione", []),
        "pallet": state.get("pallet", [])
    }


@router.put("/ordine-esecuzione")
async def set_ordine_esecuzione(body: dict):
    """
    Salva l'ordine di esecuzione pallet.
    Body: { "ordine": [3, 4, 5] }  — lista di numeri pallet in ordine
    """
    config = carica_configurazione()
    state  = _load(config)
    ordine = body.get("ordine", [])
    # Valida: solo numeri pallet validi (1-6)
    ordine = [int(n) for n in ordine if 1 <= int(n) <= N_PALLET]
    state["ordine_esecuzione"] = ordine
    _save(config, state)
    return {"ok": True, "ordine": ordine}


@router.post("/sincronizza-coda")
async def sincronizza_coda():
    """
    Sincronizza automaticamente la coda di esecuzione:
    - Aggiunge pallet che hanno programmi in_main non ancora in coda
    - Rimuove pallet i cui programmi sono tutti completati
    - Preserva l'ordine manuale esistente

    Chiamato da:
    - assegna-progetto (quando si assegna un progetto con programmi in_main)
    - segna-in-macchina (quando si genera il MAIN)
    - frontend al mount della pagina CodaLavorazione
    """
    config = carica_configurazione()
    state  = _load(config)
    data   = _load_progetti(config)
    pallets = state.get("pallet", [])
    ordine  = list(state.get("ordine_esecuzione", []))
    dirty   = False

    STATI_ATTIVI = {"in_main", "in_lavorazione", "in_macchina"}

    for pal in pallets:
        num = pal.get("numero")
        pid = pal.get("progetto_id")
        if not pid:
            # Pallet senza progetto → rimuovi dalla coda se c'era
            if num in ordine:
                ordine.remove(num)
                dirty = True
            continue

        proj = next((p for p in data.get("projects", []) if p.get("id") == pid), None)
        if not proj:
            continue

        all_pgm = [pg for s in proj.get("steps", [])
                   for t in s.get("tasks", [])
                   if t.get("text", "").strip().lower() == "fresatura"
                   for pg in t.get("programs", [])
                   if pg.get("tipoGruppo") != "ipm"]

        if not all_pgm:
            continue

        ha_attivi   = any(pg.get("stato") in STATI_ATTIVI for pg in all_pgm)
        tutti_done  = all(pg.get("stato") == "completato" for pg in all_pgm)

        if ha_attivi and num not in ordine:
            # Aggiungi in fondo alla coda
            ordine.append(num)
            dirty = True
        elif tutti_done and num in ordine:
            # Rimuovi dalla coda — lavoro finito
            ordine.remove(num)
            dirty = True

    if dirty:
        state["ordine_esecuzione"] = ordine
        _save(config, state)

    return {
        "ok":    True,
        "ordine": ordine,
        "aggiornato": dirty,
    }
