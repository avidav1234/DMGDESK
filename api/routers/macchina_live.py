"""
api/routers/macchina_live.py
Legge OpcUaLegacy.log dalla share e restituisce stato macchina live.

Il log è scritto da opcUa_Server_xp.exe ogni 4 secondi.
Formato riga:
  ReadPlVar: VarName= /Channel/ProgramInfo/workPandProgName[u1]; read Value= /_N_WKS_DIR/...
  ReadPlVar: VarName= /Channel/State/actTNumber; read Value= 3700
  ReadPlVar: VarName= /Channel/State/actToolIdent; read Value= A12.04F105E4
  ReadPlVar: VarName= /Channel/State/progStatus; read Value= 3
  ReadPlVar: VarName= /Hmi/OpcUaAlarm1; read Value= 
  ReadPlVar: VarName= /PLC/DB0.DBB67; read Value= 1   ← pallet attivo
"""

import os
import re
from datetime import datetime
from pathlib import Path
from fastapi import APIRouter
from database.db_handler import carica_configurazione

router = APIRouter()

# ── Parser log ─────────────────────────────────────────────────────────────

VAR_MAP = {
    "workPandProgName":  "programma_attivo",
    "actTNumber":        "numero_utensile",
    "actToolIdent":      "utensile_attivo",
    "progStatus":        "stato_programma",
    "OpcUaAlarm1":       "allarme",
    "DB0.DBB67":         "pallet_attivo",
}

RE_LINE = re.compile(
    r"ReadPlVar:\s*VarName=\s*([^;]+);\s*read Value=\s*(.*)",
    re.IGNORECASE,
)

def _trova_log_path(config: dict) -> str | None:
    """
    Cerca OpcUaLegacy.log nella share.
    Prova percorso esplicito, radice share, e percorso_nc_base completo.
    """
    # Path esplicito in config (priorità massima)
    explicit = config.get("opcua_log_path") or ""
    if explicit and Path(explicit).exists():
        return str(Path(explicit))

    # Ricava radice share da radice, tools_toa_folder, o percorso_nc_base
    candidates_base = []

    for key in ["radice", "tools_toa_folder", "percorso_nc_base"]:
        val = (config.get(key) or "").strip().replace("/", "\\")
        if val:
            p = Path(val)
            candidates_base.append(p)
            parts = p.parts
            if len(parts) >= 2:
                candidates_base.append(Path(parts[0]) / parts[1])

    for base in candidates_base:
        for suffix in [
            "OpcUaLegacy.log",
            "logs/OpcUaLegacy.log",
            "stato/OpcUaLegacy.log",
        ]:
            full = base / suffix
            if full.exists():
                return str(full)
    return None


def _parse_log(log_path: str) -> dict:
    """
    Legge le ultime 60 righe del log e estrae le variabili più recenti.
    Restituisce un dict con i valori letti.
    """
    result = {}
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            # Legge solo le ultime 80 righe per efficienza
            lines = f.readlines()

        # Variabili cicliche: ultime 500 righe
        seen = set()
        for line in reversed(lines[-500:]):
            m = RE_LINE.search(line)
            if not m:
                continue
            var_path = m.group(1).strip()
            value    = m.group(2).strip()
            for key, campo in VAR_MAP.items():
                if key in var_path and campo not in seen:
                    result[campo] = value
                    seen.add(campo)
            if len(seen) >= len(VAR_MAP):
                break

        # PalletAttivo: cerca su tutto il log (polling raro)
        if "pallet_attivo" not in result or not result.get("pallet_attivo"):
            for line in reversed(lines):
                m = RE_LINE.search(line)
                if not m:
                    continue
                var_path = m.group(1).strip()
                if "c70,67" in var_path or "DB0.DBB67" in var_path:
                    result["pallet_attivo"] = m.group(2).strip()
                    break

    except Exception as e:
        result["errore_parse"] = str(e)

    return result


def _normalizza(raw: dict) -> dict:
    """Converte i tipi e pulisce i valori grezzi del log."""
    out = dict(raw)

    # stato_programma → int
    try:
        out["stato_programma"] = int(raw.get("stato_programma", 0))
    except (ValueError, TypeError):
        out["stato_programma"] = 0

    # numero_utensile → int
    try:
        out["numero_utensile"] = int(raw.get("numero_utensile", 0))
    except (ValueError, TypeError):
        out["numero_utensile"] = None

    # pallet_attivo → int (1-6)
    # Fonte primaria: workPandProgName — sempre nel log OpcUa
    # es. /_N_WKS_DIR/_N_PALLET_WPD/_N_PALLET4_MPF → 4
    # Fallback: DB0.DBB67 se presente nel log
    import re as _re
    pallet = None
    prog = raw.get("programma_attivo", "") or ""
    m = _re.search(r"_N_PALLET(\d)_MPF", prog, _re.IGNORECASE)
    if m:
        v = int(m.group(1))
        if 1 <= v <= 6:
            pallet = v
    if pallet is None:
        try:
            v = int(raw.get("pallet_attivo", 0))
            if 1 <= v <= 6:
                pallet = v
        except (ValueError, TypeError):
            pass
    out["pallet_attivo"] = pallet

    # programma_attivo — pulisci path lungo
    prog = raw.get("programma_attivo", "")
    out["programma_attivo"] = prog if prog and prog != "0" else None

    # utensile_attivo
    ut = raw.get("utensile_attivo", "")
    out["utensile_attivo"] = ut if ut and ut != "0" else None

    # allarme — stringa vuota = nessun allarme
    al = raw.get("allarme", "").strip()
    out["allarme"] = al if al else None

    return out


# ── Endpoints ──────────────────────────────────────────────────────────────

@router.get("/stato")
async def get_stato_macchina():
    """
    Restituisce lo stato live della macchina letto da OpcUaLegacy.log.
    Se il log non è disponibile, restituisce connessa=False.
    """
    config   = carica_configurazione()
    log_path = _trova_log_path(config)

    if not log_path:
        return {
            "connessa": False,
            "motivo":   "Log non trovato — verifica percorso_nc_base in config.json o aggiungi opcua_log_path",
            "programma_attivo": None,
            "numero_utensile":  None,
            "utensile_attivo":  None,
            "stato_programma":  0,
            "pallet_attivo":    None,
            "allarme":          None,
            "ultimo_aggiornamento": None,
        }

    raw  = _parse_log(log_path)
    data = _normalizza(raw)

    # Timestamp ultimo aggiornamento del file
    try:
        mtime = os.path.getmtime(log_path)
        ts    = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        ts = None

    return {
        "connessa": True,
        "log_path": log_path,
        **data,
        "ultimo_aggiornamento": ts,
    }


@router.get("/config-log")
async def get_log_config():
    """Mostra dove il sistema cerca il log — utile per diagnostica."""
    config   = carica_configurazione()
    log_path = _trova_log_path(config)
    share    = config.get("percorso_nc_base", "")
    return {
        "percorso_nc_base": share,
        "opcua_log_path":   config.get("opcua_log_path"),
        "log_trovato":      log_path is not None,
        "log_path":         log_path,
    }

# ── Live Context ───────────────────────────────────────────────────────────────
# Quando il log fornirà il programma attivo, questo endpoint fa il matching
# con i progetti e ritorna il contesto completo: commessa, avanzamento, ETA.

@router.get("/live-context")
async def get_live_context():
    """
    Incrocia lo stato live della macchina con i progetti WorkTrack.

    Struttura risposta:
    {
      "programma_attivo":  "SGROSSATURA_SPIRALE_14.MPF" | null,
      "pallet_attivo":     3 | null,
      "stato_programma":   3,
      "connessa":          true,
      "match": {
        "progetto_id":    "abc123",
        "progetto_nome":  "4349_0221",
        "progetto_colore": "#D4700A",
        "programma_idx":  5,          # indice nel FresaturaPanel
        "programmi_totali": 23,
        "programmi_completati": 4,
        "programmi_in_macchina": 19,
        "pct_avanzamento": 17.4,
        "utensile_corrente": "FS25R2L85",
        "prossimi_programmi": [        # i prossimi 3 da_fare/in_macchina
          {"filename": "SGROSSATURA_SPIRALE_15.MPF", "utensile": "FS25R2L85"},
          ...
        ],
        "allerta_utensile": null | "fin_vita" | "mancante",
      } | null,
      "ultimo_aggiornamento": "24/03/2026 18:57:29"
    }
    """
    from pathlib import Path as _Path
    from api.routers.progetti import _load_progetti

    config   = carica_configurazione()
    log_path = _trova_log_path(config)

    # Stato macchina base
    if not log_path:
        return {"connessa": False, "programma_attivo": None, "pallet_attivo": None,
                "stato_programma": 0, "match": None, "ultimo_aggiornamento": None,
                "_nota": "Log OpcUa non trovato. Quando disponibile, questo endpoint "
                         "mostrerà commessa attiva, avanzamento e allerte utensile in tempo reale."}

    raw  = _parse_log(log_path)
    data = _normalizza(raw)

    prog_raw     = data.get("programma_attivo")    # es. "/_N_WKS_DIR/_N_4349_0221_WPD/_N_SGROSSATURA_SPIRALE_14_MPF"
    pallet       = data.get("pallet_attivo")
    stato_pgm    = data.get("stato_programma", 0)

    try:
        mtime = os.path.getmtime(log_path)
        ts    = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S")
    except Exception:
        ts = None

    # Estrai nome file MPF dal path OpcUa
    # formato: /_N_WKS_DIR/_N_CARTELLA_WPD/_N_NOME_PROGRAMMA_MPF
    mpf_filename = None
    cartella_wpd = None
    if prog_raw:
        import re as _re
        # Estrai nome file: ultimo segmento _N_XXX_MPF → XXX.MPF
        m = _re.search(r'_N_([^/]+)_MPF', prog_raw, _re.IGNORECASE)
        if m:
            mpf_filename = m.group(1).replace('_', '_') + '.MPF'
            # Potrebbe avere underscore → es _N_SGROSSATURA_SPIRALE_14_MPF
            # → SGROSSATURA_SPIRALE_14.MPF
        # Estrai cartella WPD (commessa)
        mw = _re.search(r'_N_([^/]+)_WPD', prog_raw, _re.IGNORECASE)
        if mw:
            cartella_wpd = mw.group(1)  # es. "4349_0221"

    # Matching con progetti WorkTrack
    match = None
    if mpf_filename:
        try:
            progetti_data = _load_progetti(config)
            projects = [p for p in progetti_data.get("projects", []) if not p.get("archived")]

            for project in projects:
                all_pgm = [pgm
                           for step in project.get("steps", [])
                           for task in step.get("tasks", [])
                           if task.get("text","").strip().lower() == "fresatura"
                           for pgm in task.get("programs", [])
                           if pgm.get("tipoGruppo") != "ipm"]

                # Cerca il programma attivo nella lista
                pgm_match = next(
                    (p for p in all_pgm
                     if p.get("filename","").upper() == mpf_filename.upper()),
                    None
                )
                if pgm_match is None:
                    continue

                # Trovato — calcola statistiche
                totale     = len(all_pgm)
                completati = sum(1 for p in all_pgm if p.get("stato") == "completato")
                in_mac     = sum(1 for p in all_pgm if p.get("stato") == "in_macchina")
                idx_corrente = all_pgm.index(pgm_match)
                pct = round(completati / totale * 100, 1) if totale else 0

                # Prossimi programmi (da_fare o in_macchina dopo quello corrente)
                prossimi = [
                    {"filename": p.get("filename"), "utensile": p.get("utensile"),
                     "stato": p.get("stato"), "numPgm": p.get("numPgm")}
                    for p in all_pgm[idx_corrente+1:]
                    if p.get("stato") in ("da_fare", "in_macchina")
                ][:4]

                # Allerta utensile corrente
                allerta = None
                tools_folder = (config.get("tools_toa_folder") or "").strip()
                if tools_folder and pgm_match.get("utensile"):
                    tm_path = _Path(tools_folder) / "tools_machine.json"
                    if tm_path.exists():
                        try:
                            tm = json.loads(tm_path.read_text(encoding="utf-8"))
                            alias = pgm_match["utensile"].upper().strip()
                            for t in tm.get("tools", {}).values():
                                if (t.get("name") or "").upper().strip() == alias:
                                    lp = t.get("life_percent")
                                    if not t.get("is_enabled", True) or t.get("is_worn"):
                                        allerta = "disabilitato"
                                    elif lp is not None and lp < 15:
                                        allerta = "fin_vita"
                                    break
                        except Exception:
                            pass

                match = {
                    "progetto_id":           project.get("id"),
                    "progetto_nome":         project.get("name"),
                    "progetto_colore":       project.get("color", "#D4700A"),
                    "programma_corrente":    mpf_filename,
                    "programma_idx":         idx_corrente + 1,
                    "programmi_totali":      totale,
                    "programmi_completati":  completati,
                    "programmi_in_macchina": in_mac,
                    "pct_avanzamento":       pct,
                    "utensile_corrente":     pgm_match.get("utensile"),
                    "tempo_inizio":          pgm_match.get("tempoInizio"),
                    "prossimi_programmi":    prossimi,
                    "allerta_utensile":      allerta,
                    "cartella_wpd":          cartella_wpd,
                    "pallet":                pallet,
                }
                break  # trovato il progetto

        except Exception as e:
            match = {"_errore_matching": str(e)}

    return {
        "connessa":             True,
        "programma_attivo":     mpf_filename,
        "programma_attivo_raw": prog_raw,
        "pallet_attivo":        pallet,
        "stato_programma":      stato_pgm,
        "utensile_attivo":      data.get("utensile_attivo"),
        "numero_utensile":      data.get("numero_utensile"),
        "allarme":              data.get("allarme"),
        "match":                match,
        "ultimo_aggiornamento": ts,
        "_nota": (
            "programma_attivo è null perché il log OpcUa non fornisce ancora "
            "workPandProgName. Quando disponibile, il matching con i progetti "
            "WorkTrack avverrà automaticamente."
            if not prog_raw else None
        ),
    }


@router.post("/aggiorna-stati-da-log")
async def aggiorna_stati_da_log():
    """
    FUTURO: chiamata dal frontend ogni N secondi.
    Legge il programma attivo dal log e aggiorna automaticamente
    lo stato dei programmi nei progetti:
    - programma che sta girando → in_macchina (se era da_fare)
    - programma appena finito (cambio programma) → completato

    Oggi ritorna solo il contesto senza modificare nulla.
    Quando il log sarà affidabile, abilitare la scrittura.
    """
    ctx = await get_live_context()

    return {
        "contesto": ctx,
        "aggiornamenti_applicati": 0,
        "_nota": "Aggiornamento automatico stati disabilitato — "
                 "abilitare quando il log OpcUa è stabile e affidabile."
    }
