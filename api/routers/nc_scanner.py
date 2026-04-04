"""
api/routers/nc_scanner.py
=========================
Scansione automatica della directory NC e associazione programmi ai progetti.

Struttura attesa:
  percorso_nc_base/
  └── {commessa}/          ex. 4298
      └── {posizione}/     ex. 0005, p0005, P0005, 0221
          └── {fase}/      ex. Fase-1, fase-1, fase_1, Fase 1
              └── *.MPF

Ogni minuto:
  - Scansiona ricorsivamente tutti i .MPF
  - Salta i file il cui mtime non è cambiato dall'ultima scansione (cache)
  - Per i file nuovi o modificati: normalizza, cerca progetto, aggiorna programmi
  - Non tocca mai stato di programmi in_main/completato/in_lavorazione
"""

import os
import re
import json
import logging
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter
from database.db_handler import carica_configurazione
from api.routers.progetti import _load_progetti, _save_progetti, _write_lock, _invalidate_analisi_cache

log = logging.getLogger("nc_scanner")
router = APIRouter(prefix="/api/nc-scanner", tags=["NC Scanner"])

# Cache mtime: path_str → mtime float
# Permette di saltare file non modificati dall'ultima scansione
_mtime_cache: dict[str, float] = {}


# ── Normalizzazione ────────────────────────────────────────────────────────────

def _norm_posizione(raw: str) -> str:
    """
    Normalizza la posizione a 4 cifre numeriche.
    P0005 → 0005, p609 → 0609, 0221 → 0221, P7221 → 7221
    """
    s = raw.strip().upper().lstrip("P")
    if s.isdigit():
        return s.zfill(4)
    return s  # non numerico (es. P1003) — restituisce as-is senza P

def _nome_progetto(commessa: str, posizione_raw: str) -> str:
    """
    Costruisce il nome progetto normalizzato.
    4298 + 0005 → 4298_0005
    4298 + P0005 → 4298_0005
    """
    return f"{commessa.strip()}_{_norm_posizione(posizione_raw)}"

def _estrai_info_filename(filename: str) -> dict:
    """
    Estrae commessa, posizione, fase, sequenza dal nome file.

    4 token: commessa_pos_fase_seq  → 4297_005_01_014.MPF
    3 token: commessa_pos_seq       → 4297_006_004.MPF (fase unica)
    """
    base = Path(filename).stem.upper()
    # Rimuovi eventuale suffisso WPD o altro
    tokens = base.split("_")
    # Filtra token non numerici in fondo (es. suffissi Siemens _801)
    while tokens and not tokens[-1].isdigit():
        tokens.pop()

    if len(tokens) >= 4:
        commessa  = tokens[0]
        posizione = tokens[1]
        fase      = tokens[2]
        seq       = tokens[3]
    elif len(tokens) == 3:
        commessa  = tokens[0]
        posizione = tokens[1]
        fase      = "1"   # fase unica
        seq       = tokens[2]
    else:
        commessa = posizione = fase = seq = ""

    return {
        "commessa":  commessa,
        "posizione": posizione,
        "fase":      fase,
        "seq":       seq,
    }


def _norm_fase(raw: str) -> str:
    """Fase-1 / fase-1 / fase_1 / Fase 1 → fase1"""
    return re.sub(r"[\s\-_]+", "", raw.lower())


def _parse_mpf_metadati(path: Path) -> dict:
    """
    Legge i metadati essenziali da un file MPF:
    - utensile (primo T="..." prima di M6)
    - tempoStimato (somma tutti i TEMPO: HH:MM:SS sulle righe M6)
    - tipoGruppo (ipm se filename contiene _IPM_)

    Usa apertura condivisa (read-only, share_all) per non bloccare Cimatron
    se sta scrivendo lo stesso file nello stesso momento.
    """
    content = None

    # Su Windows: apri con FILE_SHARE_READ|WRITE|DELETE per non entrare
    # in conflitto con Cimatron che potrebbe stare salvando il file.
    # Su altri OS: fallback a open() normale.
    try:
        import msvcrt, ctypes
        GENERIC_READ          = 0x80000000
        FILE_SHARE_ALL        = 0x00000007   # read+write+delete
        OPEN_EXISTING         = 3
        FILE_FLAG_SEQUENTIAL  = 0x08000000
        handle = ctypes.windll.kernel32.CreateFileW(
            str(path), GENERIC_READ, FILE_SHARE_ALL,
            None, OPEN_EXISTING, FILE_FLAG_SEQUENTIAL, None
        )
        INVALID = ctypes.c_void_p(-1).value
        if handle and handle != INVALID:
            try:
                import io
                fd   = msvcrt.open_osfhandle(handle, os.O_RDONLY)
                with io.open(fd, encoding="utf-8", errors="replace", closefd=True) as f:
                    content = f.read()
            except Exception:
                try: ctypes.windll.kernel32.CloseHandle(handle)
                except: pass
    except Exception:
        pass   # non Windows o errore import

    if content is None:
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
        except Exception:
            return {}


    lines = content.splitlines()

    # utensile: risale da primo M6
    utensile = ""
    m6_idx = next((i for i, l in enumerate(lines) if re.search(r"\bM6\b", l)), -1)
    if m6_idx > 0:
        for i in range(m6_idx - 1, max(0, m6_idx - 6), -1):
            m = re.search(r'T\s*=\s*"([^"]+)"', lines[i])
            if m:
                utensile = m.group(1).strip()
                break

    # tempoStimato: somma tutti M6 con TEMPO:
    def parse_tempo(raw):
        if not raw:
            return 0
        if ":" in raw:
            p = raw.split(":")
            if len(p) == 3:
                return int(p[0]) * 60 + int(p[1]) + round(int(p[2]) / 60)
            if len(p) == 2:
                return int(p[0]) + round(int(p[1]) / 60)
        try:
            return int(raw)
        except Exception:
            return 0

    tempo_tot = 0
    for l in lines:
        if re.search(r"\bM6\b", l) and re.search(r"TEMPO\s*:", l, re.IGNORECASE):
            m = re.search(r"TEMPO\s*:\s*([\d:]+)", l, re.IGNORECASE)
            if m:
                tempo_tot += parse_tempo(m.group(1))

    # Estrai info strutturate dal filename
    info = _estrai_info_filename(path.name)
    tipo = "ipm" if "_IPM_" in path.name.upper() else "fresatura"

    return {
        "filename":     path.name,
        "utensile":     utensile,
        "tempoStimato": tempo_tot or None,
        "tipoGruppo":   tipo,
        "numPgm":       info["seq"] or path.stem.split("_")[-1],
        "fase_da_file": info["fase"],   # fase estratta dal filename
        "commessa":     info["commessa"],
        "posizione":    info["posizione"],
    }


# ── Scanner principale ─────────────────────────────────────────────────────────

def _trova_o_crea_task_fresatura(project: dict, fase_label: str) -> dict | None:
    """
    Cerca il task 'Fresatura' nella fase corrispondente.
    Se la fase non esiste, non la crea (conservativo).
    Ritorna il task dict (reference mutabile) o None.
    """
    fase_norm = _norm_fase(fase_label)
    for step in project.get("steps", []):
        step_norm = _norm_fase(step.get("title", ""))
        if fase_norm and step_norm != fase_norm:
            continue  # fase specificata ma non corrisponde
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() == "fresatura":
                return task
    return None


def _uid():
    import uuid
    return str(uuid.uuid4())[:8]


def scansiona_directory(config: dict) -> dict:
    """
    Scansiona percorso_nc_base e sincronizza i programmi con i progetti DMGDesk.
    Ritorna un dizionario con le statistiche dell'operazione.
    """
    nc_base = (config.get("percorso_nc_base") or "").strip()
    if not nc_base:
        return {"ok": False, "errore": "percorso_nc_base non configurato"}

    base = Path(nc_base)
    if not base.exists():
        return {"ok": False, "errore": f"Percorso non trovato: {nc_base}"}

    proj_data = _load_progetti(config)
    projects  = proj_data.get("projects", [])

    # Indice progetti per nome normalizzato
    proj_index: dict[str, dict] = {}
    for p in projects:
        nome = (p.get("name") or "").strip()
        proj_index[nome.upper()] = p

    stats = {
        "scansionati": 0,
        "aggiunti":    0,
        "aggiornati":  0,
        "orfani":      0,
        "ignorati":    0,   # già presenti con stato avanzato
        "saltati":     0,   # non modificati (mtime cache)
        "errori":      [],
    }
    dirty = False

    # Cartelle da ignorare
    IGNORE_DIRS = {
        "allegati", "attrezzatura_interna", "db_toolmanager", "dnc",
        "ipm.wpd", "machine server", "mcis", "oem", "opc", "tabella_utensili",
        "test", "tool_sync", "vbs", "wzv.dir", "xp_scripts_dmgdesk",
    }

    # Scansione: commessa/posizione/fase/*.MPF
    for mpf_path in base.rglob("*.MPF"):
        stats["scansionati"] += 1

        # Ignora i file MAIN generati da DMGDesk
        if mpf_path.name.upper().startswith("0_MAIN_"):
            continue

        # Salta file non modificati dall'ultima scansione (cache mtime)
        path_key = str(mpf_path)
        try:
            mtime = mpf_path.stat().st_mtime
        except OSError:
            continue
        if _mtime_cache.get(path_key) == mtime:
            stats["saltati"] += 1
            continue

        parts = mpf_path.relative_to(base).parts
        # Struttura attesa: commessa / posizione / [fase /] file.MPF
        if len(parts) < 3:
            stats["orfani"] += 1
            continue

        cartella_top = parts[0].lower()
        if cartella_top in IGNORE_DIRS or cartella_top.startswith("."):
            continue

        commessa   = parts[0]   # es. 4298
        posizione  = parts[1]   # es. 0005, P0005
        nome_proj  = _nome_progetto(commessa, posizione)

        # Fase: la cartella tra posizione e file
        # Se len==3: commessa/posizione/file.MPF → nessuna fase esplicita
        # Se len==4: commessa/posizione/fase/file.MPF → fase = parts[2]
        # Se len>=5: commessa/posizione/fase/sotto/file.MPF → fase = parts[2]
        if len(parts) >= 4:
            fase_cartella = parts[2]
            # Verifica che sembri una fase (contiene "fase" o è numerica)
            fc_lower = fase_cartella.lower()
            if not (re.search(r"fase", fc_lower) or fc_lower.isdigit()):
                fase_cartella = ""  # cartella non è una fase (es. WPD, OLD, report)
        else:
            fase_cartella = ""  # file direttamente in posizione, nessuna fase

        # Cerca progetto
        project = proj_index.get(nome_proj.upper())
        if not project:
            stats["orfani"] += 1
            continue

        # Leggi metadati MPF
        try:
            meta = _parse_mpf_metadati(mpf_path)
        except Exception as e:
            stats["errori"].append(f"{mpf_path.name}: {e}")
            continue

        # Aggiorna cache mtime — file letto con successo
        _mtime_cache[path_key] = mtime

        fase_label = fase_cartella or meta.get("fase_da_file") or ""

        # Trova task Fresatura
        task = _trova_o_crea_task_fresatura(project, fase_label)
        if not task:
            # Nessun task Fresatura trovato in questa fase — cerca in qualsiasi fase
            task = _trova_o_crea_task_fresatura(project, "")
        if not task:
            stats["orfani"] += 1
            continue

        programs = task.setdefault("programs", [])
        filename = meta["filename"]

        # Cerca programma esistente
        existing = next((p for p in programs if p.get("filename", "").upper() == filename.upper()), None)

        if existing:
            stato = existing.get("stato", "da_fare")
            if stato in ("in_main", "in_lavorazione", "completato", "in_macchina"):
                stats["ignorati"] += 1
                continue
            # Aggiorna metadati se cambiati
            changed = False
            if meta["utensile"] and existing.get("utensile") != meta["utensile"]:
                existing["utensile"] = meta["utensile"]
                changed = True
            if meta["tempoStimato"] and existing.get("tempoStimato") != meta["tempoStimato"]:
                existing["tempoStimato"] = meta["tempoStimato"]
                changed = True
            if changed:
                stats["aggiornati"] += 1
                dirty = True
        else:
            # Nuovo programma — aggiunge con stato da_fare
            now = datetime.now().isoformat(timespec="seconds")
            programs.append({
                "id":           _uid(),
                "filename":     filename,
                "utensile":     meta["utensile"],
                "tempoStimato": meta["tempoStimato"],
                "tipoGruppo":   meta["tipoGruppo"],
                "numPgm":       meta["numPgm"],
                "stato":        "da_fare",
                "operatore":    "",
                "tempoInizio":  None,
                "tempoFine":    None,
                "rilevato_da":  "nc_scanner",
                "rilevato_il":  now,
            })
            stats["aggiunti"] += 1
            dirty = True
            log.info(f"nc_scanner: aggiunto {filename} → {nome_proj} ({fase_label})")

        # Aggiorna cache mtime — file processato correttamente
        _mtime_cache[path_key] = mtime

    if dirty:
        _save_progetti(config, proj_data)
        _invalidate_analisi_cache()
        log.info(f"nc_scanner: salvato — +{stats['aggiunti']} aggiunti, {stats['aggiornati']} aggiornati")

    stats["ok"] = True
    return stats


# ── Job periodico ──────────────────────────────────────────────────────────────

async def job_nc_scanner():
    """Chiamato ogni 10 minuti dallo scheduler in main.py."""
    config = carica_configurazione()
    try:
        async with _write_lock:
            result = scansiona_directory(config)
        if result.get("aggiunti") or result.get("aggiornati"):
            log.info(
                f"nc_scanner: {result['scansionati']} file, "
                f"+{result['aggiunti']} nuovi, "
                f"~{result['aggiornati']} aggiornati, "
                f"{result['orfani']} orfani"
            )
    except Exception as e:
        log.warning(f"nc_scanner job error: {e}")


# ── Endpoint manuali ───────────────────────────────────────────────────────────

@router.post("/scansiona")
@router.get("/scansiona")
async def scansiona_ora():
    """Esegue la scansione immediatamente (senza attendere lo scheduler)."""
    config = carica_configurazione()
    async with _write_lock:
        result = scansiona_directory(config)
    return result


@router.get("/anteprima")
async def anteprima_scansione():
    """
    Mostra cosa troverebbe la scansione senza modificare nulla.
    Utile per verificare prima di attivare il job automatico.
    """
    config = carica_configurazione()
    nc_base = (config.get("percorso_nc_base") or "").strip()
    if not nc_base:
        return {"ok": False, "errore": "percorso_nc_base non configurato"}

    base = Path(nc_base)
    if not base.exists():
        return {"ok": False, "errore": f"Percorso non trovato: {nc_base}"}

    proj_data = _load_progetti(config)
    projects  = proj_data.get("projects", [])
    proj_index = {(p.get("name") or "").strip().upper(): p for p in projects}

    IGNORE_DIRS = {
        "allegati", "attrezzatura_interna", "db_toolmanager", "dnc",
        "ipm.wpd", "machine server", "mcis", "oem", "opc", "tabella_utensili",
        "test", "tool_sync", "vbs", "wzv.dir", "xp_scripts_dmgdesk",
    }

    trovati, orfani = [], []
    for mpf_path in base.rglob("*.MPF"):
        if mpf_path.name.upper().startswith("0_MAIN_"):
            continue
        parts = mpf_path.relative_to(base).parts
        if len(parts) < 3:
            continue
        if parts[0].lower() in IGNORE_DIRS:
            continue
        nome_proj = _nome_progetto(parts[0], parts[1])
        # Fase: solo se cartella contiene "fase" o è numerica
        if len(parts) >= 4:
            fc = parts[2].lower()
            fase = parts[2] if (re.search(r"fase", fc) or fc.isdigit()) else ""
        else:
            fase = ""
        # Se fase da cartella vuota, usa fase da filename
        if not fase:
            info = _estrai_info_filename(mpf_path.name)
            fase = f"fase {info['fase']}" if info["fase"] and info["fase"] != "1" else ("unica" if info["fase"] == "1" else "")
        project   = proj_index.get(nome_proj.upper())
        if project:
            trovati.append({"file": mpf_path.name, "progetto": nome_proj, "fase": fase})
        else:
            orfani.append({"file": mpf_path.name, "path": str(mpf_path.relative_to(base)), "progetto_atteso": nome_proj})

    return {
        "ok":      True,
        "trovati": len(trovati),
        "orfani":  len(orfani),
        "campione_trovati": trovati[:20],
        "campione_orfani":  orfani[:20],
    }
