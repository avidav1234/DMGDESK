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

    # Gestione IPM: 4298_005_01_IPM_01 → commessa=4298, pos=005, fase=01, seq=01
    ipm_idx = next((i for i, t in enumerate(tokens) if t.upper() == "IPM"), -1)
    if ipm_idx >= 0:
        # File IPM: la fase è il token prima di IPM
        commessa  = tokens[0]
        posizione = tokens[1] if len(tokens) > 1 else ""
        fase      = tokens[ipm_idx - 1] if ipm_idx >= 2 else "1"
        seq       = tokens[ipm_idx + 1] if ipm_idx + 1 < len(tokens) else str(ipm_idx)
    elif len(tokens) >= 4:
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


def _leggi_file_mpf(path: Path) -> str | None:
    """
    Legge un file MPF con apertura condivisa (non blocca Cimatron).
    """
    try:
        import msvcrt, ctypes, io
        GENERIC_READ         = 0x80000000
        FILE_SHARE_ALL       = 0x00000007
        OPEN_EXISTING        = 3
        FILE_FLAG_SEQUENTIAL = 0x08000000
        handle = ctypes.windll.kernel32.CreateFileW(
            str(path), GENERIC_READ, FILE_SHARE_ALL,
            None, OPEN_EXISTING, FILE_FLAG_SEQUENTIAL, None
        )
        INVALID = ctypes.c_void_p(-1).value
        if handle and handle != INVALID:
            try:
                fd = msvcrt.open_osfhandle(handle, os.O_RDONLY)
                with io.open(fd, encoding="utf-8", errors="replace", closefd=True) as f:
                    return f.read()
            except Exception:
                try: ctypes.windll.kernel32.CloseHandle(handle)
                except: pass
    except Exception:
        pass
    try:
        return path.read_text(encoding="utf-8", errors="replace")
    except Exception:
        return None


def _parse_mpf_metadati(path: Path) -> dict:
    """
    Estrae metadati completi da un file MPF usando la stessa logica
    del caricamento manuale (nc_analyzer):
    - utensile: primo utensile (T="..." prima di M6)
    - utensili_lista: tutti gli utensili in ordine di apparizione
    - tempoStimato: somma TEMPO: sulle righe M6 (minuti)
    - num_m6: numero di cambi utensile
    - tipoGruppo: ipm / fresatura
    - numPgm: numero sequenziale estratto dal filename
    """
    content = _leggi_file_mpf(path)
    if content is None:
        return {}

    lines = content.splitlines()

    # ── Usa nc_analyzer per estrarre utensili in modo robusto ──────────
    utensile      = ""
    utensili_lista = []
    try:
        from logic.nc_analyzer import estrai_tutti_utensili_da_file
        utensili_raw = estrai_tutti_utensili_da_file(str(path))
        if utensili_raw:
            utensile       = utensili_raw[0][0]          # primo utensile
            utensili_lista = [u[0] for u in utensili_raw]  # tutti in ordine
    except Exception:
        # fallback parser interno
        m6_idx = next((i for i, l in enumerate(lines) if re.search(r"\bM6\b", l)), -1)
        if m6_idx > 0:
            for i in range(m6_idx - 1, max(0, m6_idx - 6), -1):
                m = re.search(r'T\s*=\s*"([^"]+)"', lines[i])
                if m:
                    utensile = m.group(1).strip()
                    break

    # ── Tempo stimato: somma tutti M6 con TEMPO: ───────────────────────
    def parse_tempo(raw):
        if not raw: return 0
        if ":" in raw:
            p = raw.split(":")
            if len(p) == 3: return int(p[0]) * 60 + int(p[1]) + round(int(p[2]) / 60)
            if len(p) == 2: return int(p[0]) + round(int(p[1]) / 60)
        try: return int(raw)
        except: return 0

    tempo_tot = 0
    for l in lines:
        if re.search(r"\bM6\b", l) and re.search(r"TEMPO\s*:", l, re.IGNORECASE):
            m = re.search(r"TEMPO\s*:\s*([\d:]+)", l, re.IGNORECASE)
            if m:
                tempo_tot += parse_tempo(m.group(1))

    # ── Tipo IPM ───────────────────────────────────────────────────────
    # Regola primaria: filename contiene "_IPM_" → ipm
    # Fallback (Q3 v2): se utensile principale è RENISHAW E la lista utensili
    # contiene SOLO RENISHAW (programma di sola misurazione, no fresatura)
    # → ipm. Programmi di fresatura che usano RENISHAW per misurazione
    # preliminare seguita da fresatura mantengono tipo=fresatura.
    tipo = "ipm" if "_IPM_" in path.name.upper() else "fresatura"
    if tipo != "ipm" and "RENISHAW" in (utensile or "").upper():
        # Lista utensili: se contiene SOLO RENISHAW (uno o più, ma tutti sonde)
        # è programma di sola misurazione → IPM.
        utensili_set = {(u or "").upper().strip() for u in utensili_lista}
        if utensili_set and all("RENISHAW" in u for u in utensili_set):
            tipo = "ipm"

    # ── tipoOp: parte dal PRIMO M6 e risale cercando il commento operazione ─
    # L'intestazione generale del file (CIMATRON, DOCUMENTO NC, NOME POST...)
    # non è la procedura. La procedura è il commento "N<nnn>; <descrizione>"
    # più vicino al richiamo utensile, es:
    #     N18; FORATURA AUTO 3X_122 - NESSUN TESTO
    #     N19; DIAMETER: 12 CORNER RADIUS: 0
    #     N20; TOOL COMMENT: PI12-5VDF100H10
    #     N21 T = "PI12-5VDF100H10"; T261
    #     N22 M6
    _HDR_RE = re.compile(r"^\s*N\d+\s*;\s*(.+?)\s*$")
    _SKIP_KW = [
        "DIAMETER", "TOOL COMMENT", "CIMATRON", "DOCUMENTO NC",
        "NOME POST", "VERSIONE POST", "REVISIONE", "DATA MODIFICA",
        "DATA ESECUZIONE", "N.UT", "UTENTE", "COMMESSA", "PROGRAMMA:",
        "AUTORE", "OPERATORE", "CLIENTE", "MACCHINA:",
    ]

    def _estrai_procedura_da_m6(m6_idx: int, max_su: int = 30) -> str:
        """Risale da M6 fino a max_su righe cercando il commento operazione."""
        for i in range(m6_idx - 1, max(-1, m6_idx - max_su), -1):
            mh = _HDR_RE.match(lines[i])
            if not mh:
                continue
            body = mh.group(1).strip()
            if len(body) < 3:
                continue
            body_up = body.upper()
            if any(kw in body_up for kw in _SKIP_KW):
                continue
            # Salta "CHIAVE: valore numerico" (es. DIAMETER residuo, TEMPO:, ecc.)
            if re.match(r"^[A-Z_\s\.]+:\s*[\d\.\-]", body):
                continue
            return body
        return ""

    tipo_op = ""
    primo_m6_idx = next((i for i, l in enumerate(lines) if re.search(r"\bM6\b", l)), -1)
    if primo_m6_idx > 0:
        tipo_op = _estrai_procedura_da_m6(primo_m6_idx)

    # ── diametro ───────────────────────────────────────────────────────
    diametro = ""
    for l in lines:
        if "DIAMETER:" in l.upper():
            import re as _re
            d = _re.sub(r".*DIAMETER:\s*", "", l, flags=_re.IGNORECASE)
            d = _re.sub(r"CORNER.*", "", d, flags=_re.IGNORECASE).strip()
            if d:
                diametro = d
            break

    # ── dataPost ───────────────────────────────────────────────────────
    data_post = ""
    for l in lines:
        if "DATA ESECUZIONE POST" in l.upper():
            raw = l[l.index(":")+1:].strip() if ":" in l else ""
            if raw:
                import re as _re
                m = _re.search(r"(\d{1,2})/(\d{1,2})/(\d{4}).*?(\d{1,2}):(\d{2})", raw)
                if m:
                    d, mo, y, h, mi = m.groups()
                    data_post = f"{d.zfill(2)}/{mo.zfill(2)}/{y} {h}:{mi}"
                else:
                    data_post = raw
            break

    # ── utensili con tempi per M6 (compatibile con caricamento manuale) ─
    utensili_con_tempi = []
    for idx, line in enumerate(lines):
        if not re.search(r"\bM6\b", line):
            continue
        alias_m6 = ""
        for i in range(idx - 1, max(-1, idx - 5), -1):
            m = re.search(r'T\s*=\s*"([^"]+)"', lines[i])
            if m:
                alias_m6 = m.group(1).strip()
                break
        if not alias_m6:
            continue
        raw_t = (re.search(r"TEMPO\s*:\s*([\d:]+)", line, re.IGNORECASE) or [None, None])[1]
        tempo_min = parse_tempo(raw_t) if raw_t else None
        procedura_m6 = _estrai_procedura_da_m6(idx)
        utensili_con_tempi.append({
            "alias":     alias_m6,
            "tempoMin":  tempo_min,
            "procedura": procedura_m6,
        })

    # ── Info da filename ───────────────────────────────────────────────
    info = _estrai_info_filename(path.name)

    return {
        "filename":          path.name,
        "utensile":          utensile,
        "utensili_lista":    utensili_lista,
        "utensili":          utensili_con_tempi,   # compatibile con caricamento manuale
        "num_m6":            len(utensili_lista),
        "tempoStimato":      tempo_tot or None,
        "tipoGruppo":        tipo,
        "tipoOp":            tipo_op,
        "diametro":          diametro,
        "dataPost":          data_post,
        "numPgm":            info["seq"] or path.stem.split("_")[-1],
        "fase_da_file":      info["fase"],
        "commessa":          info["commessa"],
        "posizione":         info["posizione"],
    }


# ── Scanner principale ─────────────────────────────────────────────────────────

def _trova_o_crea_task_fresatura(project: dict, fase_label: str) -> dict | None:
    """
    Cerca il task 'Fresatura' nella fase corrispondente.
    Supporta matching flessibile: "01" == "1" == "fase1" == "fase-1" == "Fase 1"
    """
    if not fase_label:
        # Nessuna fase specificata: prendi la prima task Fresatura disponibile
        for step in project.get("steps", []):
            for task in step.get("tasks", []):
                if task.get("text", "").strip().lower() == "fresatura":
                    return task
        return None

    fase_norm = _norm_fase(fase_label)
    # Varianti numeriche: "01" → ["01", "1", "fase01", "fase1"]
    fase_num  = fase_label.lstrip("0") or "1"
    varianti  = {fase_norm, _norm_fase(fase_num), _norm_fase(f"fase{fase_num}"),
                 _norm_fase(f"fase{fase_label}"), _norm_fase(fase_label)}

    for step in project.get("steps", []):
        step_norm = _norm_fase(step.get("title", ""))
        if step_norm and step_norm in varianti:
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
        "rimossi_orfani": 0,  # Q1 v2: programmi nel JSON ma file non più su disco
        "errori":      [],
    }
    dirty = False

    # Cartelle da ignorare
    IGNORE_DIRS = {
        "allegati", "attrezzatura_interna", "db_toolmanager", "dnc",
        "ipm.wpd", "machine server", "mcis", "oem", "opc", "tabella_utensili",
        "test", "tool_sync", "vbs", "wzv.dir", "xp_scripts_dmgdesk",
    }

    # Q1 v2 — Enumerazione file su disco per rilevare orfani
    # Costruisce un set di filename normalizzati (UPPER) per ogni progetto.
    # Verrà usato dopo il loop principale per rimuovere programmi nel JSON
    # che non hanno più corrispondenza su disco.
    file_su_disco_per_progetto: dict[str, set[str]] = {}
    try:
        for mpf_path in base.rglob("*.[Mm][Pp][Ff]"):
            if mpf_path.name.upper().startswith("0_MAIN_"):
                continue
            try:
                _parts = mpf_path.relative_to(base).parts
            except ValueError:
                continue
            if len(_parts) < 3:
                continue
            _top = _parts[0].lower()
            if _top in IGNORE_DIRS or _top.startswith("."):
                continue
            _commessa = _parts[0]
            _posizione = _parts[1]
            _nome_proj = _nome_progetto(_commessa, _posizione)
            file_su_disco_per_progetto.setdefault(
                _nome_proj.upper(), set()
            ).add(mpf_path.name.upper())
    except Exception as _e:
        log.warning(f"nc_scanner: errore enumerazione disco per orfani: {_e}")
        file_su_disco_per_progetto = {}  # fallback: niente pulizia

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

        # Q2 fix v2: validazione filename vs cartella.
        # La cartella è la verità. Se il filename contiene una commessa diversa
        # (es. typo: 4360_*.mpf nella cartella 4360 → OK; 43460_*.mpf nella
        # cartella 4360 → REJECT), il file viene rifiutato.
        # Eccezione: file 0_MAIN_*.mpf, file di servizio _scar.mpf e simili
        # non sono soggetti alla validazione (non hanno commessa nel formato
        # standard nel filename).
        info_fname = _estrai_info_filename(mpf_path.name)
        commessa_fname = (info_fname.get("commessa") or "").strip()
        # File "0_*": template macchina (0_MAIN_, 0_UT_, 0_M6_, …). Non sono
        # programmi di lavorazione e parsano commessa="0" → falso mismatch.
        # Stessa logica per SCAR e IPM. Saltati silenziosamente, niente log
        # rumoroso che blocca lo stream sync su share di rete.
        is_servizio = (
            mpf_path.name.upper().startswith("0_")
            or "SCAR" in mpf_path.stem.upper()
            or "_IPM_" in mpf_path.name.upper()
        )
        if commessa_fname and not is_servizio:
            if commessa_fname.upper() != commessa.upper():
                # Aggregato: incrementa contatore + lista, log singolo a fine scansione.
                # Logging sync su share di rete con N warning blocca per minuti.
                stats.setdefault("rifiutati_mismatch", []).append(
                    f"cartella={commessa} filename={commessa_fname} → {mpf_path.name}"
                )
                stats["orfani"] += 1
                continue
        elif is_servizio and mpf_path.name.upper().startswith("0_") and \
             not mpf_path.name.upper().startswith("0_MAIN"):
            # File di servizio (0_UT_, 0_M6_, ecc.) NON sono programmi di
            # lavorazione veri. Salta del tutto la registrazione come programma.
            continue

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

        # Trova task Fresatura nella fase corretta
        # Per IPM: la fase è estratta dal filename (es. 4298_005_01_IPM_01 → fase "01")
        # Non usare fallback senza fase — evita che IPM di fasi diverse si mescolino
        task = _trova_o_crea_task_fresatura(project, fase_label)
        if not task and fase_label:
            # Prova anche con fase numerica pura (es. "01" → cerca "Fase 1" o "Fase-1")
            fase_num = fase_label.lstrip("0") or "1"
            task = _trova_o_crea_task_fresatura(project, fase_num)
        if not task and fase_label:
            # Prova con numero senza zero iniziale
            task = _trova_o_crea_task_fresatura(project, fase_label.lstrip("0") or fase_label)
        if not task:
            # Solo se non c'è nessuna fase specificata, prendi la prima disponibile
            if not fase_label:
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
                # Non cambiamo lo stato, ma aggiorniamo i metadati
                # tipoOp/diametro/dataPost/utensili sono nuovi — sempre aggiorna se mancanti
                # utensile/tempoStimato — aggiorna solo se il nuovo valore è migliore
                meta_changed = False
                for c in ["tipoOp", "diametro", "dataPost", "utensili", "utensili_lista"]:
                    if meta.get(c) and existing.get(c) != meta[c]:
                        existing[c] = meta[c]
                        meta_changed = True
                for c in ["utensile", "tempoStimato", "num_m6"]:
                    if meta.get(c) and not existing.get(c):
                        existing[c] = meta[c]
                        meta_changed = True
                # Q3 fix v2: ricalcola tipoGruppo anche per programmi attivi
                if meta.get("tipoGruppo") and existing.get("tipoGruppo") != meta["tipoGruppo"]:
                    old_tipo = existing.get("tipoGruppo")
                    existing["tipoGruppo"] = meta["tipoGruppo"]
                    meta_changed = True
                    log.info(
                        f"nc_scanner: tipoGruppo corretto per {existing.get('filename')}: "
                        f"{old_tipo} → {meta['tipoGruppo']} (stato={stato})"
                    )
                if meta_changed:
                    stats["aggiornati"] += 1
                    dirty = True
                else:
                    stats["ignorati"] += 1
                continue
            # Aggiorna metadati se cambiati
            changed = False
            for campo in ["utensile", "tempoStimato", "tipoOp", "diametro", "dataPost"]:
                if meta.get(campo) and existing.get(campo) != meta[campo]:
                    existing[campo] = meta[campo]
                    changed = True
            if meta.get("utensili_lista") and existing.get("utensili_lista") != meta["utensili_lista"]:
                existing["utensili_lista"] = meta["utensili_lista"]
                existing["utensili"]       = meta.get("utensili", [])
                existing["num_m6"]         = meta.get("num_m6", 0)
                changed = True
            # Q3 fix v2: ricalcola tipoGruppo ad ogni scansione per programmi
            # esistenti, così gli IPM storici sbagliati (es. fresatura con
            # RENISHAW erroneamente marcato ipm) vengono corretti.
            if meta.get("tipoGruppo") and existing.get("tipoGruppo") != meta["tipoGruppo"]:
                old_tipo = existing.get("tipoGruppo")
                existing["tipoGruppo"] = meta["tipoGruppo"]
                changed = True
                log.info(
                    f"nc_scanner: tipoGruppo corretto per {existing.get('filename')}: "
                    f"{old_tipo} → {meta['tipoGruppo']}"
                )
            if changed:
                stats["aggiornati"] += 1
                dirty = True
        else:
            # Nuovo programma — aggiunge con stato da_fare
            now = datetime.now().isoformat(timespec="seconds")
            programs.append({
                "id":            _uid(),
                "filename":      filename,
                "utensile":      meta["utensile"],
                "utensili_lista": meta.get("utensili_lista", []),
                "utensili":      meta.get("utensili", []),
                "num_m6":        meta.get("num_m6", 0),
                "tempoStimato":  meta["tempoStimato"],
                "tipoGruppo":    meta["tipoGruppo"],
                "tipoOp":        meta.get("tipoOp", ""),
                "diametro":      meta.get("diametro", ""),
                "dataPost":      meta.get("dataPost", ""),
                "numPgm":        meta["numPgm"],
                "stato":         "da_fare",
                "operatore":     "",
                "tempoInizio":   None,
                "tempoFine":     None,
                "rilevato_da":   "nc_scanner",
                "rilevato_il":   now,
            })
            stats["aggiunti"] += 1
            dirty = True
            log.info(f"nc_scanner: aggiunto {filename} → {nome_proj} ({fase_label})")

        # Aggiorna cache mtime — file processato correttamente
        _mtime_cache[path_key] = mtime

    # ── Q1 v2: Pulizia orfani ────────────────────────────────────────────
    # Rimuove dal JSON i programmi con stato `da_fare` che NON esistono più
    # su disco. Programmi con stato attivo (in_main/in_lavorazione/completato)
    # sono mantenuti per preservare la storia (Legge 1 v2.2).
    # Solo se l'enumerazione disco è andata a buon fine.
    if file_su_disco_per_progetto:
        for project in projects:
            nome_proj = (project.get("name") or "").upper().strip()
            file_disco = file_su_disco_per_progetto.get(nome_proj, set())
            if not file_disco:
                # Nessun file su disco per questo progetto: sospetto. Skip pulizia
                # per evitare cancellazioni accidentali se la share è offline.
                continue

            for step in project.get("steps", []):
                for task in step.get("tasks", []):
                    if task.get("text", "").strip().lower() != "fresatura":
                        continue
                    programs = task.get("programs", [])
                    nuova_lista = []
                    for pgm in programs:
                        fname = (pgm.get("filename") or "").upper().strip()
                        stato = pgm.get("stato", "da_fare")
                        if stato == "da_fare" and fname and fname not in file_disco:
                            # Orfano da_fare: rimuovi
                            stats["rimossi_orfani"] += 1
                            log.info(
                                f"nc_scanner: rimosso orfano da_fare {fname} "
                                f"da progetto {nome_proj}"
                            )
                            dirty = True
                            continue
                        nuova_lista.append(pgm)
                    if len(nuova_lista) != len(programs):
                        task["programs"] = nuova_lista

    if dirty:
        _save_progetti(config, proj_data)
        _invalidate_analisi_cache()
        log.info(
            f"nc_scanner: salvato — +{stats['aggiunti']} aggiunti, "
            f"{stats['aggiornati']} aggiornati, "
            f"-{stats['rimossi_orfani']} orfani da_fare rimossi"
        )

    # Log aggregato dei mismatch (max 5 esempi nel testo, count totale)
    rifiutati = stats.get("rifiutati_mismatch") or []
    if rifiutati:
        esempi = "; ".join(rifiutati[:5])
        suffix = f" (+{len(rifiutati)-5} altri)" if len(rifiutati) > 5 else ""
        log.warning(
            f"nc_scanner: {len(rifiutati)} file rifiutati per commessa mismatch — {esempi}{suffix}"
        )

    stats["ok"] = True
    return stats


# ── Job periodico ──────────────────────────────────────────────────────────────

async def job_nc_scanner():
    """Chiamato dallo scheduler in main.py.

    `scansiona_directory` è una funzione SINCRONA che fa rglob ricorsivo +
    stat su ogni file su una share di rete (potenzialmente migliaia di file)
    e parse di MPF. Eseguita inline nell'event loop bloccava per decine di
    secondi tutto il backend (poller, GET pallet/tick, ecc.).
    Spostata in un thread executor per non bloccare l'asyncio loop.
    """
    import asyncio as _aio
    config = carica_configurazione()
    loop = _aio.get_running_loop()
    try:
        async with _write_lock:
            result = await loop.run_in_executor(None, scansiona_directory, config)
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
    """Esegue la scansione immediatamente (senza attendere lo scheduler).
    Eseguita in thread executor: non blocca l'event loop asyncio."""
    import asyncio as _aio
    config = carica_configurazione()
    loop = _aio.get_running_loop()
    async with _write_lock:
        result = await loop.run_in_executor(None, scansiona_directory, config)
    return result


@router.post("/riscansiona-tutto")
async def riscansiona_tutto():
    """
    Forza la riscansione di tutti i file (reset cache mtime).
    Utile dopo aggiornamenti al parser per riacquisire metadati mancanti.
    Eseguita in thread executor: non blocca l'event loop asyncio.
    """
    import asyncio as _aio
    global _mtime_cache
    _mtime_cache = {}
    config = carica_configurazione()
    loop = _aio.get_running_loop()
    async with _write_lock:
        result = await loop.run_in_executor(None, scansiona_directory, config)
    result["cache_reset"] = True
    return result


@router.post("/cleanup-orphans")
async def cleanup_orphans(progetto_id: str | None = None):
    """
    Q4 v2: Pulizia mirata dei programmi orfani.

    Per progetto_id specifico (o tutti se None): rimuove dal JSON i programmi
    con stato `da_fare` il cui filename non esiste più sulla cartella su disco.
    Programmi con stato attivo (in_main/in_lavorazione/completato) sono SEMPRE
    preservati per coerenza con la Legge 1 v2.2.

    Restituisce statistiche dei programmi rimossi.
    """
    config = carica_configurazione()
    nc_base = (config.get("percorso_nc_base") or "").strip()
    if not nc_base:
        return {"ok": False, "errore": "percorso_nc_base non configurato"}

    base = Path(nc_base)
    if not base.exists():
        return {"ok": False, "errore": f"Percorso non trovato: {nc_base}"}

    IGNORE_DIRS = {
        "allegati", "attrezzatura_interna", "db_toolmanager", "dnc",
        "ipm.wpd", "machine server", "mcis", "oem", "opc", "tabella_utensili",
        "test", "tool_sync", "vbs", "wzv.dir", "xp_scripts_dmgdesk",
    }

    async with _write_lock:
        proj_data = _load_progetti(config)
        projects = proj_data.get("projects", [])

        # Enumera file su disco per ogni progetto
        file_su_disco_per_progetto: dict[str, set[str]] = {}
        for mpf_path in base.rglob("*.[Mm][Pp][Ff]"):
            if mpf_path.name.upper().startswith("0_MAIN_"):
                continue
            try:
                _parts = mpf_path.relative_to(base).parts
            except ValueError:
                continue
            if len(_parts) < 3:
                continue
            _top = _parts[0].lower()
            if _top in IGNORE_DIRS or _top.startswith("."):
                continue
            _nome_proj = _nome_progetto(_parts[0], _parts[1])
            file_su_disco_per_progetto.setdefault(
                _nome_proj.upper(), set()
            ).add(mpf_path.name.upper())

        rimossi = []
        for project in projects:
            nome_proj = (project.get("name") or "").upper().strip()
            if progetto_id and project.get("id") != progetto_id:
                continue
            file_disco = file_su_disco_per_progetto.get(nome_proj, set())
            if not file_disco:
                continue
            for step in project.get("steps", []):
                for task in step.get("tasks", []):
                    if task.get("text", "").strip().lower() != "fresatura":
                        continue
                    programs = task.get("programs", [])
                    nuova_lista = []
                    for pgm in programs:
                        fname = (pgm.get("filename") or "").upper().strip()
                        stato = pgm.get("stato", "da_fare")
                        if stato == "da_fare" and fname and fname not in file_disco:
                            rimossi.append({
                                "progetto": project.get("name"),
                                "filename": pgm.get("filename"),
                                "step":     step.get("title"),
                            })
                            continue
                        nuova_lista.append(pgm)
                    if len(nuova_lista) != len(programs):
                        task["programs"] = nuova_lista

        if rimossi:
            _save_progetti(config, proj_data)
            _invalidate_analisi_cache()
            log.info(f"cleanup-orphans: rimossi {len(rimossi)} programmi orfani da_fare")

    return {"ok": True, "rimossi": rimossi, "totale": len(rimossi)}


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
