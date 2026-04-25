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
from api.constants import WATCHDOG_SOGLIA_SEC, WATCHDOG_ISTERESI_TICK, ORE_TURNO_SEC
# Import a livello modulo — nessun ciclo reale, spostate da lazy import nelle funzioni
from api.routers.progetti import (
    _load_progetti, _save_progetti, _invalidate_analisi_cache,
    _write_lock as _proj_lock,
)
from api.routers.pallet import _load as _load_pallet, _save as _save_pallet
from api.routers.report import aggiorna_da_log, _load_log, _log_path

router = APIRouter()

# ── Ultimo tick del poller interno ─────────────────────────────────────────
# Il task interno aggiorna_stati_da_log() salva qui il risultato dell'ultimo ciclo.
# Il frontend legge questo valore con GET /tick invece di chiamare POST aggiorna-stati-da-log.
# In questo modo N client leggono, 1 solo scrittore interno scrive.
_last_tick: dict = {"aggiornamenti": 0, "ts": None}

VAR_MAP = {
    "workPandProgName":  "programma_attivo",
    "actTNumber":        "numero_utensile",
    "actToolIdent":      "utensile_attivo",
    "progStatus":        "stato_programma",
    "OpcUaAlarm1":       "allarme",
    "DB0.DBB67":         "pallet_attivo",
    # Override operatore — fondamentali per rilevare rallentamenti/problemi
    "feedRateOvr":       "override_feed",       # % avanzamento (0-120)
    "spindleOvr":        "override_mandrino",   # % mandrino (0-120)
    # Valori effettivi — utili per OEE performance
    "actFeedRate":       "feed_attuale",        # mm/min effettivi
    "actSpindleSpeed":   "rpm_attuale",         # rpm effettivi
}

RE_LINE = re.compile(
    r"ReadPlVar:\s*VarName=\s*([^;]+);\s*read Value=\s*(.*)",
    re.IGNORECASE,
)

_log_path_cache: dict = {"path": None, "config_hash": None}

def _trova_log_path(config: dict) -> str | None:
    """
    Cerca OpcUaLegacy.log nella share.
    Risultato in cache — il path non cambia a runtime.
    """
    # Cache key basata sui campi rilevanti della config
    key = (config.get("opcua_log_path"), config.get("radice"),
           config.get("tools_toa_folder"), config.get("percorso_nc_base"))
    if _log_path_cache["config_hash"] == key and _log_path_cache["path"] is not None:
        # Verifica che il file esista ancora
        if Path(_log_path_cache["path"]).exists():
            return _log_path_cache["path"]
        else:
            _log_path_cache["path"] = None  # file sparito — ricerca

    # Path esplicito in config (priorità massima)
    explicit = config.get("opcua_log_path") or ""
    if explicit and Path(explicit).exists():
        _log_path_cache["path"] = str(Path(explicit))
        _log_path_cache["config_hash"] = key
        return _log_path_cache["path"]

    # Ricava radice share da radice, tools_toa_folder, o percorso_nc_base
    candidates_base = []
    for k in ["radice", "tools_toa_folder", "percorso_nc_base"]:
        val = (config.get(k) or "").strip().replace("/", "\\")
        if val:
            p = Path(val)
            candidates_base.append(p)
            parts = p.parts
            if len(parts) >= 2:
                candidates_base.append(Path(parts[0]) / parts[1])

    for base in candidates_base:
        for suffix in ["OpcUaLegacy.log", "logs/OpcUaLegacy.log", "stato/OpcUaLegacy.log"]:
            full = base / suffix
            if full.exists():
                _log_path_cache["path"] = str(full)
                _log_path_cache["config_hash"] = key
                return _log_path_cache["path"]

    _log_path_cache["config_hash"] = key
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

        # Pallet da workPandProgName: cerca solo nelle righe RECENTI (ultime 20)
        # Se non trovato, il pallet corrente viene mantenuto dallo stato salvato
        import re as _re_tmp
        RE_PALLET_PATH = _re_tmp.compile(
            r"_N_PALLET_WPD/_N_PALLET(\d)_MPF", _re_tmp.IGNORECASE)
        for line in reversed(lines[-20:]):
            mp = RE_PALLET_PATH.search(line)
            if mp:
                result["pallet_da_path"] = int(mp.group(1))
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
    # Fonte 1 (priorità massima): _N_PALLET_WPD/_N_PALLETn_MPF nel log recente
    # Fonte 2: workPandProgName corrente se contiene PALLET
    # Fonte 3: DB0.DBB67 dal PLC
    import re as _re
    pallet = None

    # Fonte 1: pallet_da_path trovato da _parse_log
    if raw.get("pallet_da_path"):
        v = int(raw["pallet_da_path"])
        if 1 <= v <= 6:
            pallet = v

    # Fonte 2: programma_attivo corrente contiene PALLET
    if pallet is None:
        prog = raw.get("programma_attivo", "") or ""
        m = _re.search(r"_N_PALLET(\d)_MPF", prog, _re.IGNORECASE)
        if m:
            v = int(m.group(1))
            if 1 <= v <= 6:
                pallet = v

    # Fonte 3: DB0.DBB67
    if pallet is None:
        try:
            v = int(raw.get("pallet_attivo", 0))
            if 1 <= v <= 6:
                pallet = v
        except (ValueError, TypeError):
            pass
    out["pallet_attivo"] = pallet

    # programma_attivo — filtra path di sistema, estrai solo nome file
    prog = raw.get("programma_attivo", "") or ""
    if prog and "_N_SYF_DIR" not in prog and "_N_CST_DIR" not in prog \
            and "_N_MPF_DIR" not in prog and "_N_CMA_DIR" not in prog and prog != "0":
        # Estrai nome file dal path: /_N_WKS_DIR/_N_WPD/_N_NOME_MPF → NOME.MPF
        m_mpf = _re.search(r"/_N_([^/]+)_MPF$", prog)
        if m_mpf:
            out["programma_attivo"] = m_mpf.group(1) + ".MPF"
        else:
            out["programma_attivo"] = prog
    else:
        out["programma_attivo"] = None

    # utensile_attivo
    ut = raw.get("utensile_attivo", "")
    out["utensile_attivo"] = ut if ut and ut != "0" else None

    # allarme — formato Sinumerik: |702028|30.03.26 08:48:47| MESS.,  testo
    al = raw.get("allarme", "").strip()
    if al:
        import re as _re2
        m_al = _re2.match(r"\|(\d+)\|[^|]+\|\s*(?:MESS\.\s*,\s*)?(.+)", al)
        if m_al:
            codice = m_al.group(1)
            testo  = m_al.group(2).strip()
            # Classificazione Sinumerik 840D PowerLine — documentazione ufficiale:
            #   000000-099999  NCK allarmi (fermano macchina, critici)
            #   100000-399999  SINAMICS/drive allarmi (critici)
            #   400000-499999  Safety Integrated (critici)
            #   500000-599999  PLC allarmi configurabili (possono fermare)
            #   600000-699999  PLC allarmi utente (possono fermare)
            #   700000-709999  PLC messaggi informativi (NON fermano) ← solo display
            #   710000-719999  PLC messaggi avvertenza (NON fermano) ← solo display
            #   720000-799999  PLC allarmi utente avanzati (fermano)
            try:
                n = int(codice)
                if 700000 <= n <= 719999:
                    tipo = "messaggio"   # solo display, non notificare
                else:
                    tipo = "allarme"     # ferma o può fermare la macchina
            except ValueError:
                tipo = "allarme"
            out["allarme"]      = f"{codice}: {testo}"
            out["allarme_tipo"] = tipo   # "allarme" | "messaggio"
            out["allarme_codice"] = codice
        else:
            out["allarme"]      = al
            out["allarme_tipo"] = "allarme"
            out["allarme_codice"] = None
    else:
        out["allarme"]      = None
        out["allarme_tipo"] = None
        out["allarme_codice"] = None

    # ── Override feed e mandrino ──────────────────────────────────────────────
    # Sinumerik esprime override come intero 0-120 (100 = 100%)
    def _parse_ovr(key):
        try:
            v = int(raw.get(key, 100) or 100)
            return max(0, min(200, v))  # clamp ragionevole
        except (ValueError, TypeError):
            return None

    ovr_feed     = _parse_ovr("override_feed")
    ovr_mandrino = _parse_ovr("override_mandrino")
    out["override_feed"]     = ovr_feed
    out["override_mandrino"] = ovr_mandrino

    # Classificazione override:
    # NORMALE  ≥ 90%   (tolleranza ±10% per aggiustamenti fini)
    # RIDOTTO  50-89%  (operatore ha rallentato — attenzione)
    # BASSO    < 50%   (problema significativo o setup)
    def _classifica_ovr(v):
        if v is None: return None
        if v >= 90:   return "normale"
        if v >= 50:   return "ridotto"
        return "basso"

    out["override_feed_stato"]     = _classifica_ovr(ovr_feed)
    out["override_mandrino_stato"] = _classifica_ovr(ovr_mandrino)

    # Flag unico: True se almeno uno dei due override è ridotto/basso
    ovr_ridotto = (
        (ovr_feed is not None and ovr_feed < 90) or
        (ovr_mandrino is not None and ovr_mandrino < 90)
    )
    out["override_ridotto"] = ovr_ridotto

    # Valori effettivi feed e rpm
    try:    out["feed_attuale"] = float(raw.get("feed_attuale") or 0) or None
    except: out["feed_attuale"] = None
    try:    out["rpm_attuale"]  = float(raw.get("rpm_attuale") or 0) or None
    except: out["rpm_attuale"]  = None

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

    # Timestamp e controllo stale
    log_stale = False
    log_age_sec = None
    try:
        mtime = os.path.getmtime(log_path)
        ts    = datetime.fromtimestamp(mtime).strftime("%d/%m/%Y %H:%M:%S")
        log_age_sec = int((datetime.now() - datetime.fromtimestamp(mtime)).total_seconds())
        if log_age_sec > WATCHDOG_SOGLIA_SEC:
            log_stale = True
    except Exception:
        ts = None

    return {
        "connessa":             True,
        "log_path":             log_path,
        "log_stale":            log_stale,
        "log_age_sec":          log_age_sec,
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

    # Fallback: se prog_raw è null ma la macchina è in esecuzione,
    # usa il programma_corrente dallo stato_corrente del log sessioni
    _fallback_filename = None
    # Fallback solo su stato 3 (in esecuzione con conferma), non su stato 2
    # Stato 2 con prog_raw=None = USERENDPROG o fine ciclo — NON usare il programma precedente
    if not prog_raw and stato_pgm == 3:
        try:
            from api.routers.report import _load_log as _rl
            _sc = _rl(config).get("stato_corrente", {})
            _pc = _sc.get("programma_corrente")
            if _pc:
                # Imposta direttamente il filename — bypassa il parsing del path
                _fallback_filename = _pc if _pc.upper().endswith(".MPF") else _pc + ".MPF"
        except Exception:
            pass

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
        elif prog_raw.upper().endswith('.MPF'):
            # prog_raw è già un filename pulito (non formato OPC UA)
            mpf_filename = prog_raw
        # Estrai cartella WPD (commessa)
        mw = _re.search(r'_N_([^/]+)_WPD', prog_raw, _re.IGNORECASE)
        if mw:
            cartella_wpd = mw.group(1)  # es. "4349_0221"

    # Usa fallback se mpf_filename non estratto dal path
    if not mpf_filename and _fallback_filename:
        mpf_filename = _fallback_filename

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
                           for pgm in task.get("programs", [])]

                # Cerca il programma attivo nella lista
                pgm_match = next(
                    (p for p in all_pgm
                     if p.get("filename","").upper() == mpf_filename.upper()),
                    None
                )
                if pgm_match is None:
                    continue

                # Trovato — calcola statistiche
                # Progetto totale
                totale     = len(all_pgm)
                completati = sum(1 for p in all_pgm if p.get("stato") == "completato")
                in_mac     = sum(1 for p in all_pgm if p.get("stato") == "in_lavorazione")
                idx_corrente = all_pgm.index(pgm_match)
                pct = round(completati / totale * 100, 1) if totale else 0

                # Batch corrente (solo programmi in_main + completati — già caricati in macchina)
                batch = [p for p in all_pgm if p.get("stato") in ("in_main", "completato", "in_lavorazione")]
                batch_totale     = len(batch)
                batch_completati = sum(1 for p in batch if p.get("stato") == "completato")
                batch_pct        = round(batch_completati / batch_totale * 100, 1) if batch_totale else 0

                # Prossimi programmi (da_fare o in_main dopo quello corrente)
                prossimi = [
                    {"filename": p.get("filename"), "utensile": p.get("utensile"),
                     "stato": p.get("stato"), "numPgm": p.get("numPgm")}
                    for p in all_pgm[idx_corrente+1:]
                    if p.get("stato") in ("da_fare", "in_main")
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
                            tools_dict = tm.get("tools", {})
                            for t in tools_dict.values():
                                if (t.get("name") or "").upper().strip() == alias:
                                    lp = t.get("life_percent")
                                    if not t.get("is_enabled", True) or t.get("is_worn"):
                                        allerta = "disabilitato"
                                    elif lp is not None:
                                        # Soglia dinamica ML, fallback a 15%
                                        try:
                                            from ml.vita_ottimale import soglia_fin_vita as _sfv
                                            from api.routers.tool_history import _load_history as _th_load
                                            _sfv_val = _sfv(alias, _th_load(config))
                                        except Exception:
                                            _sfv_val = 15.0
                                        if lp < _sfv_val:
                                            allerta = "fin_vita"
                                    break
                            # Alert Telegram vita bassa durante lavorazione
                            try:
                                from api.routers.tool_history import check_low_life_alert
                                check_low_life_alert(tools_dict, [alias], config)
                            except Exception:
                                pass
                        except Exception:
                            pass

                match = {
                    "progetto_id":           project.get("id"),
                    "progetto_nome":         project.get("name"),
                    # batch corrente
                    "batch_completati":      batch_completati,
                    "batch_totale":          batch_totale,
                    "batch_pct":             batch_pct,
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
        "progetto_attivo":      match.get("progetto_nome") if match and "progetto_nome" in match else None,
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




# ── Helper: scenario detection ───────────────────────────────────────────────
# Funzioni pure estratte dal tick per leggibilità e riuso.
# Ricevono e modificano i dati in-place; restituiscono (proj_dirty, pallet_dirty).

def _itera_programmi_fresatura(progetto: dict):
    """Genera tutti i programmi fresatura di un progetto (incluso IPM, v2)."""
    for s in progetto.get("steps", []):
        for t in s.get("tasks", []):
            if t.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in t.get("programs", []):
                yield pgm


def _progetto_mai_iniziato(progetto: dict) -> bool:
    """
    True se il progetto non ha mai avuto programmi in esecuzione o completati.
    Usato per distinguere 'pianificato in anticipo' da 'interrotto a metà'.
    Considera anche IPM — fanno parte del lavoro.
    """
    for s in progetto.get("steps", []):
        for t in s.get("tasks", []):
            if t.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in t.get("programs", []):
                if pgm.get("stato") in ("completato", "in_lavorazione"):
                    return False
    return True


# _ha_main_valido RIMOSSA (feature/pallet-logic-v2):
# La protezione "MAIN esiste su disco" mascherava interruzioni reali.
# Con la regola d'oro, un pallet in_lavorazione che esce va sempre a finito o
# guasto in base allo stato dei programmi — il MAIN non è rilevante qui.


def _gestisci_cross_pallet(
    p_altro: dict,
    pallet_data: dict,
    now_str: str,
    updates: dict,
) -> tuple[bool, bool]:
    """
    Quando parte un programma di un progetto diverso da `p_altro`, chiude i
    programmi in_lavorazione di p_altro (erano attivi ma ora non più).

    NOTA v2: questa funzione NON decide più lo stato del pallet.
    La transizione del pallet (finito/guasto) è centralizzata in
    _chiudi_pallet_in_lavorazione, chiamata dal blocco principale del tick
    quando vede il pallet in_lavorazione non più attivo.

    I programmi in_main residui NON vengono resettati a `da_fare`:
    servono alla regola d'oro (pallet → guasto se esistono `in_main`).
    Il reset dei programmi avviene solo alla rigenerazione del MAIN.

    Restituisce (proj_dirty, pallet_dirty).
    """
    proj_dirty = False

    pgm_in_lav = [p for p in _itera_programmi_fresatura(p_altro) if p.get("stato") == "in_lavorazione"]

    if not pgm_in_lav:
        return False, False

    # I programmi che erano in esecuzione su p_altro sono ora interrotti.
    # Li lasciamo in "in_main" (riavviabili) oppure "completato" in base a
    # utensili — delega a _verifica_utensili_pgm per coerenza con regola d'oro.
    # Qui applichiamo solo la logica "chiude programma che era in_lavorazione":
    # se utensili OK → completato, altrimenti → in_main.
    for pgm in pgm_in_lav:
        attesi = [
            (u.get("alias") or "").upper().strip()
            for u in (pgm.get("utensili") or [])
            if u.get("alias")
        ]
        visti = [
            (u or "").upper().strip()
            for u in (pgm.get("_utensili_visti") or [])
        ]
        mancanti = [a for a in attesi if a not in visti]

        if mancanti:
            # Utensili mancanti → programma ri-eseguibile
            pgm["stato"] = "in_main"
            pgm["tempoInizio"] = None
            pgm["tempoFine"]   = None
        else:
            # Tutti gli utensili visti → completato
            pgm["stato"] = "completato"
            pgm["tempoFine"] = pgm.get("tempoFine") or now_str
            updates["completato"] += 1

        # NOTA v2: NON pop _utensili_visti. La regola d'oro li consulta al
        # chiusura pallet. Verranno puliti alla rigenerazione del MAIN.
        proj_dirty = True

    return proj_dirty, False  # pallet_dirty=False: lo decide il caller


def _verifica_utensili_pgm(
    pgm: dict,
    progetto: dict,
    pallet_data: dict,
    now_str: str,
    updates: dict,
) -> tuple[str, bool, bool]:
    """
    Verifica se tutti gli utensili attesi sono stati visti durante l'esecuzione.

    v2: NON scrive più direttamente lo stato del pallet. Marca solo il programma:
    - utensili mancanti → stato `in_main` (il programma va rifatto)
    - utensili OK       → stato `completato`
    La decisione pallet finito/guasto è centralizzata in
    _chiudi_pallet_in_lavorazione, che si attiva al cambio pallet o al timeout stop.

    Restituisce (nuovo_stato, proj_dirty, pallet_dirty).
    """
    utensili_attesi = [
        u["alias"].upper().strip()
        for u in (pgm.get("utensili") or [])
        if u.get("alias")
    ]
    utensili_visti = [
        u.upper().strip()
        for u in (pgm.get("_utensili_visti") or [])
    ]
    mancanti = [u for u in utensili_attesi if u not in utensili_visti]

    # NOTA v2: NON pop _utensili_visti. La regola d'oro li consulta al
    # chiusura pallet. Verranno puliti alla rigenerazione del MAIN.

    if utensili_attesi and mancanti:
        pgm["stato"] = "in_main"
        pgm["tempoInizio"] = None
        pgm["tempoFine"]   = None
        updates.setdefault("interruzioni_utensile", []).append({
            "programma": pgm.get("filename", "?"),
            "mancanti":  mancanti,
            "msg": f"{pgm.get('filename','?')}: utensili mancanti {mancanti}"
        })
        return "in_main", True, False

    pgm["stato"] = "completato"
    pgm["tempoFine"] = pgm.get("tempoFine") or now_str
    updates["completato"] += 1
    return "completato", True, False


@router.post("/aggiorna-stati-da-log")
async def aggiorna_stati_da_log():
    """
    Chiamata dal frontend ogni 5 secondi.
    Legge programma_attivo e stato_programma dal log OpcUa e applica:
    1. Pallet in lavorazione da log (stato=3)
    2. Programma attivo → in_macchina
    3. Programma precedente → completato (cambio programma)
    4. Pallet → grezzo/finito quando macchina si ferma
    """
    import asyncio as _asyncio
    from datetime import datetime as _dt

    config   = carica_configurazione()
    log_path = _trova_log_path(config)
    if not log_path:
        return {"aggiornamenti": 0, "nota": "log non trovato"}

    # ── Watchdog MchnSrv: rileva log stale con isteresi ──────────────────────
    # Se MchnSrv smette di copiare il log dalla PCU50, il file rimane congelato.
    # ISTERESI: segnala stale solo dopo WATCHDOG_ISTERESI_TICK tick consecutivi
    # sopra soglia — evita falsi positivi da picchi momentanei di rete/I/O.

    # Contatore tick stale persistente in memoria del processo
    if not hasattr(aggiorna_stati_da_log, "_stale_count"):
        aggiorna_stati_da_log._stale_count = 0

    LOG_STALE_SOGLIA_SEC = WATCHDOG_SOGLIA_SEC
    try:
        mtime = os.path.getmtime(log_path)
        log_age_sec = (_dt.now() - _dt.fromtimestamp(mtime)).total_seconds()
        if log_age_sec > LOG_STALE_SOGLIA_SEC:
            aggiorna_stati_da_log._stale_count += 1
            if aggiorna_stati_da_log._stale_count >= WATCHDOG_ISTERESI_TICK:
                return {
                    "aggiornamenti": 0,
                    "log_stale": True,
                    "log_age_sec": int(log_age_sec),
                    "stale_ticks": aggiorna_stati_da_log._stale_count,
                    "nota": f"Log non aggiornato da {int(log_age_sec)}s ({aggiorna_stati_da_log._stale_count} tick consecutivi) — MchnSrv potrebbe essere fermo",
                    "stato_macchina": -1,
                }
            else:
                # Sotto soglia tick — non segnalare ancora, procedi normalmente
                pass
        else:
            # Log aggiornato — resetta contatore
            aggiorna_stati_da_log._stale_count = 0
    except OSError:
        pass  # se non riesce a leggere mtime, procede normalmente

    raw  = _parse_log(log_path)
    data = _normalizza(raw)

    # programma_attivo è già il nome file estratto: "4297_005_01_12.MPF"
    # prog_raw_full è il path completo dal log grezzo (per estrarre WPD)
    prog_attivo = data.get("programma_attivo") or ""   # "4297_005_01_12.MPF"
    prog_raw_full = raw.get("programma_attivo") or ""  # "/_N_WKS_DIR/_N_.._WPD/_N_.._MPF"
    stato_pgm = data.get("stato_programma", 0)
    now_str   = _dt.now().strftime("%d/%m/%Y %H:%M")

    # Estrai WPD dal path grezzo
    wpd_m    = re.search(r"_N_([^/]+)_WPD", prog_raw_full)
    wpd_nome = wpd_m.group(1) if wpd_m else None   # "4298_0008"

    # mpf_filename = il nome file già estratto
    mpf_filename = prog_attivo if prog_attivo else None   # "4297_005_01_12.MPF"

    # Estrai commessa_posizione dal nome file: "4297_005_01_12.MPF" → "4297_0005"
    mpf_progetto = None
    if mpf_filename:
        nome_bare = mpf_filename.upper().replace(".MPF", "")
        parts = nome_bare.split("_")
        if len(parts) >= 2:
            comm = parts[0]
            pos  = parts[1].zfill(4)
            mpf_progetto = f"{comm}_{pos}"
            mpf_progetto = f"{comm}_{pos}"

    def _norm_nome(n):
        """Normalizza nome progetto: spazi→_, maiuscolo, posizione con zeri."""
        n = (n or "").upper().replace(" ","_").replace("-","_")
        # Normalizza la seconda parte a 4 cifre se è numerica
        parts = n.split("_")
        if len(parts) >= 2 and parts[1].isdigit():
            parts[1] = parts[1].zfill(4)
        return "_".join(parts)

    updates = {
        "pallet": 0, "in_macchina": 0, "completato": 0,
        "progetto_rilevato": None, "pallet_rilevato": None,
        "programma_attivo": mpf_filename, "stato_macchina": stato_pgm,
        # Override operatore — propagati al frontend per alert live
        "override_feed":           data.get("override_feed"),
        "override_mandrino":       data.get("override_mandrino"),
        "override_ridotto":        data.get("override_ridotto", False),
        "override_feed_stato":     data.get("override_feed_stato"),
        "override_mandrino_stato": data.get("override_mandrino_stato"),
    }

    proj_data   = _load_progetti(config)
    pallet_data = _load_pallet(config)
    projects    = proj_data.get("projects", [])
    pallets     = pallet_data.get("pallet", [])
    proj_dirty = pallet_dirty = False

    # Trova progetto:
    # Fonte 1: commessa_posizione dal nome MPF (normalizzata con zeri)
    # Fonte 2: nome WPD
    progetto_attivo = None
    for nome_ricerca in [mpf_progetto, wpd_nome]:
        if not nome_ricerca:
            continue
        nr_norm = _norm_nome(nome_ricerca)
        for p in projects:
            pname = _norm_nome(p.get("name") or "")
            if pname == nr_norm or nr_norm in pname or pname in nr_norm:
                progetto_attivo = p
                break
        if progetto_attivo:
            break

    # Trova pallet:
    # Fonte 1 (priorità): pallet_attivo dal log — _N_PALLETn_MPF nelle ultime 20 righe
    # Fonte 2: prog_raw corrente contiene direttamente _N_PALLETn_MPF
    # Fonte 3: pallet già in_lavorazione nello stato salvato (persistenza)
    #          → rimane finché non appare un nuovo PALLETn nel log
    # Fonte 4: pallet assegnato al progetto nei dati DMGDesk
    pallet_num = data.get("pallet_attivo")  # int 1-6 o None

    # Fonte 2: cerca PALLET nel path grezzo del log
    if not pallet_num:
        m_pal = re.search(r"_N_PALLET_WPD/_N_PALLET(\d)_MPF",
                          prog_raw_full, re.IGNORECASE)
        if not m_pal:
            m_pal = re.search(r"_N_PALLET(\d)_MPF", prog_raw_full, re.IGNORECASE)
        if m_pal:
            v = int(m_pal.group(1))
            if 1 <= v <= 6:
                pallet_num = v

    # Fonte 3: pallet già in_lavorazione nello stato salvato
    # ATTENZIONE: usa questo fallback SOLO se il progetto del pallet in_lavorazione
    # coincide con il progetto rilevato dal log corrente.
    # Se il progetto è cambiato (nuovo pezzo in macchina), non usare il pallet vecchio.
    if not pallet_num and stato_pgm in (1, 3):
        for pal in pallets:
            if (pal.get("stato") or "").lower().replace(" ","_") == "in_lavorazione":
                # Verifica coerenza progetto
                pal_proj_id   = pal.get("progetto_id") or ""
                pal_proj_nome = _norm_nome(pal.get("progetto_nome") or "")
                att_proj_id   = progetto_attivo.get("id") if progetto_attivo else ""
                att_proj_nome = _norm_nome(progetto_attivo.get("name") if progetto_attivo else "")
                mpf_proj_norm = _norm_nome(mpf_progetto or "")

                # Match se: stesso project_id, o stesso nome, o nome MPF coincide
                match = (
                    (pal_proj_id and att_proj_id and pal_proj_id == att_proj_id) or
                    (pal_proj_nome and att_proj_nome and pal_proj_nome == att_proj_nome) or
                    (pal_proj_nome and mpf_proj_norm and pal_proj_nome == mpf_proj_norm)
                )
                if match:
                    pallet_num = pal.get("numero")
                    break
                # Se non c'è progetto attivo rilevato, usa comunque il pallet in lavorazione
                # (non abbiamo informazioni sufficienti per contraddirlo)
                if not progetto_attivo and not mpf_progetto:
                    pallet_num = pal.get("numero")
                    break

    # Fonte 4: pallet assegnato al progetto (per id o per nome progetto)
    if not pallet_num and progetto_attivo:
        proj_id   = progetto_attivo.get("id")
        proj_nome = _norm_nome(progetto_attivo.get("name") or "")
        for pal in pallets:
            if pal.get("progetto_id") == proj_id:
                pallet_num = pal.get("numero"); break
            pal_nome = _norm_nome(pal.get("progetto_nome") or "")
            if pal_nome and pal_nome == proj_nome:
                pallet_num = pal.get("numero"); break

    # Fonte 5: cerca il pallet che ha questo progetto assegnato cercando
    # tra tutti i progetti quale pallet ha progetto_id = progetto_attivo.id
    # Già fatto sopra — se ancora None, cerca per nome del progetto in tutti i pallet
    if not pallet_num and mpf_progetto:
        mp_norm = _norm_nome(mpf_progetto)
        for pal in pallets:
            # Cerca nei dati del pallet il nome del progetto assegnato
            for key in ["progetto_nome", "progetto_id"]:
                v = _norm_nome(str(pal.get(key) or ""))
                if v and v == mp_norm:
                    pallet_num = pal.get("numero")
                    break
            if pallet_num:
                break

    # Quando macchina si ferma → nessun pallet attivo (gestito da automazione 4)
    if stato_pgm in (0, 5):
        pallet_num = None

    updates["progetto_rilevato"]    = progetto_attivo.get("name") if progetto_attivo else None
    updates["progetto_id_rilevato"] = progetto_attivo.get("id")   if progetto_attivo else None
    updates["pallet_rilevato"]   = pallet_num

    # Classifica il tipo di fermo — importante per OEE e diagnostica
    # Sinumerik 840D progStatus:
    #   0 = reset / spento / pronto senza programma  → fermo non pianificato
    #   1 = in esecuzione
    #   2 = ricerca blocco (jog, posizionamento)
    #   3 = in esecuzione (conferma)
    #   5 = stop / interrotto (M0, M1, E-Stop, allarme NCK) → fermo pianificato o anomalia
    if stato_pgm == 0:
        updates["stop_type"] = "reset"       # fermo non pianificato / riavvio
    elif stato_pgm == 5:
        updates["stop_type"] = "stop"        # M0/M1/E-Stop — può essere pianificato
    elif stato_pgm == 2:
        updates["stop_type"] = "search"      # ricerca blocco, non è un vero fermo
    else:
        updates["stop_type"] = None          # in esecuzione

    updates["_debug"] = {
        "wpd_nome": wpd_nome, "mpf_progetto": mpf_progetto,
        "pallet_num": pallet_num, "stato_pgm": stato_pgm,
        "mpf_filename": mpf_filename,
        "prog_attivo": prog_attivo, "prog_raw_full": prog_raw_full[:80] if prog_raw_full else None,
    }

    # ── Automazione 1 e 4: stato pallet ──────────────────────────────────
    # Regola d'oro (feature/pallet-logic-v2):
    # - Un pallet che era `in_lavorazione` può uscire SOLO verso `finito` o `guasto`,
    #   mai a `grezzo`.
    #   FINITO: tutti i programmi del MAIN (stato != da_fare) sono `completato` E
    #           per ognuno tutti gli utensili attesi sono stati visti.
    #   GUASTO: altrimenti.
    # - Un pallet in stato passivo (vuoto/grezzo/finito/guasto) NON viene toccato
    #   dall'automatismo di chiusura; la sua transizione avviene in altri punti
    #   (assegnazione progetto, rigenerazione MAIN, reset manuale).
    # - La rigenerazione del MAIN è l'UNICO evento che può far tornare un pallet
    #   a `grezzo` dopo essere stato `in_lavorazione`/`finito`/`guasto` — gestito
    #   in analisi_nc.py al momento della rigenerazione.

    def _chiudi_pallet_in_lavorazione(pal, projects):
        """
        Applica la regola d'oro a un pallet che era `in_lavorazione`.
        Tutti i programmi del MAIN `completato` e utensili OK → FINITO, altrimenti GUASTO.
        Un utensile "visto per sequenza" (retro-marcato) è considerato OK.
        """
        pid = pal.get("progetto_id")
        if not pid:
            # Pallet in_lavorazione senza progetto: anomalia, torna a vuoto
            pal["stato"] = "vuoto"
            return
        proj = next((p for p in projects if p.get("id") == pid), None)
        if not proj:
            pal["stato"] = "vuoto"
            return

        pgm_fresatura = [
            pg for s in proj.get("steps", [])
            for t in s.get("tasks", [])
            if t.get("text", "").strip().lower() == "fresatura"
            for pg in t.get("programs", [])
        ]

        # Solo programmi nel MAIN (in_main/completato/in_lavorazione). I `da_fare`
        # non facevano parte di questo ciclo e vengono ignorati.
        pgm_nel_main = [
            pg for pg in pgm_fresatura
            if pg.get("stato") in ("in_main", "completato", "in_lavorazione")
        ]

        if not pgm_nel_main:
            # Anomalia: pallet era in_lavorazione ma nessun programma nel MAIN.
            pal["stato"] = "guasto"
            return

        # Regola d'oro: TUTTI completato E utensili attesi tutti visti
        tutti_completati = all(pg.get("stato") == "completato" for pg in pgm_nel_main)
        if not tutti_completati:
            pal["stato"] = "guasto"
            return

        # Check utensili per ogni programma
        for pg in pgm_nel_main:
            attesi = [
                (u.get("alias") or "").upper().strip()
                for u in (pg.get("utensili") or [])
                if u.get("alias")
            ]
            visti = [
                (u or "").upper().strip()
                for u in (pg.get("_utensili_visti") or [])
            ]
            mancanti = [a for a in attesi if a not in visti]
            if mancanti:
                pal["stato"] = "guasto"
                return

        pal["stato"] = "finito"

    def _calcola_stato_pallet_passivo(pal, projects):
        """
        Calcola lo stato di un pallet NON in lavorazione basandosi sui programmi
        del progetto associato. Usato solo per pallet che non erano in_lavorazione
        (es. cambio progetto_id, assegnazione iniziale).
        Stati possibili: vuoto | grezzo | finito | guasto (preserva guasto).
        """
        cur = (pal.get("stato") or "").lower()
        if cur in ("guasto", "finito"):
            return  # stati terminali, non toccare

        pid = pal.get("progetto_id")
        if not pid:
            pal["stato"] = "vuoto"; return
        proj = next((p for p in projects if p.get("id") == pid), None)
        if not proj:
            pal["stato"] = "vuoto"; return
        pgm_fresatura = [
            pg for s in proj.get("steps", [])
            for t in s.get("tasks", [])
            if t.get("text", "").strip().lower() == "fresatura"
            for pg in t.get("programs", [])
        ]
        if not pgm_fresatura:
            pal["stato"] = "vuoto"; return
        pgm_main = [pg for pg in pgm_fresatura if pg.get("stato") in ("in_main", "completato")]
        if pgm_main and all(pg.get("stato") == "completato" for pg in pgm_main):
            pal["stato"] = "finito"
        elif any(pg.get("stato") == "in_main" for pg in pgm_fresatura):
            pal["stato"] = "grezzo"
        else:
            pal["stato"] = "vuoto"

    if stato_pgm in (1, 3):
        # Macchina IN ESECUZIONE — marca il pallet attivo come in_lavorazione.
        # La CHIUSURA dei pallet non più attivi viene fatta DOPO l'aggiornamento
        # dei programmi (vedi fine tick), così la regola d'oro valuta lo stato
        # finale corretto (es. ultimo programma appena completato).
        # G4: se pallet_num è None/0, non tocca nulla (macchina fa programma non mappato).
        if pallet_num:
            for pal in pallets:
                is_attivo = (pal.get("numero") == pallet_num)
                cur_stato = (pal.get("stato") or "").lower().replace(" ", "_")
                if is_attivo:
                    if cur_stato != "in_lavorazione":
                        pal["stato"] = "in_lavorazione"
                        pal["aggiornato"] = now_str
                        pal.pop("stop_iniziato_ts", None)
                        pallet_dirty = True
                        updates["pallet"] += 1
                    else:
                        # già in_lavorazione: azzera il timer (macchina ripresa)
                        if pal.get("stop_iniziato_ts"):
                            pal.pop("stop_iniziato_ts", None)
                            pallet_dirty = True

    elif stato_pgm == 2:
        # stato 2 = ricerca blocco / JOG — non toccare i pallet né il timer.
        pass

    elif stato_pgm in (0, 5):
        # Macchina FERMA
        # Comportamento:
        # - Entro grace period (15min, gestito da report.py): NO transizione pallet,
        #   il programma potrebbe riprendere.
        # - Oltre 1h di stop continuo: pallet in_lavorazione → GUASTO (timeout C1).
        # - Reset anomalo (stato_pgm=0): immediato timeout. Stop (stato_pgm=5): aspetta 1h.
        try:
            _lav_log  = _load_log(config)
            _sc       = _lav_log.get("stato_corrente", {})
            in_pausa  = _sc.get("in_pausa", False)
        except Exception:
            in_pausa = False

        from datetime import datetime as _dt, timedelta as _td
        TIMEOUT_STOP = _td(hours=1)

        for pal in pallets:
            cur_stato = (pal.get("stato") or "").lower().replace(" ", "_")
            if cur_stato != "in_lavorazione":
                continue

            # Inizializza timer di stop alla prima rilevazione
            if not pal.get("stop_iniziato_ts"):
                pal["stop_iniziato_ts"] = now_str
                pallet_dirty = True
                continue  # primo tick di stop, non chiudere ancora

            # Timeout check
            try:
                iniz = _dt.fromisoformat(pal["stop_iniziato_ts"])
                # Bug 11 fix: usa now_str del tick (non _dt.now() reale)
                elapsed = _dt.fromisoformat(now_str) - iniz
            except Exception:
                elapsed = _td(0)

            if elapsed >= TIMEOUT_STOP:
                _chiudi_pallet_in_lavorazione(pal, projects)
                pal["aggiornato"] = now_str
                pal.pop("stop_iniziato_ts", None)
                pallet_dirty = True
                updates["pallet"] += 1
                updates.setdefault("timeout_stop", []).append({
                    "pallet": pal.get("numero"),
                    "msg": f"Pallet {pal.get('numero')}: stop > 1h → {pal['stato'].upper()}"
                })


    # ── Automazione 2 e 3: stati programmi ───────────────────────────────
    if mpf_filename and stato_pgm in (1, 3):
        # Cerca il programma attivo in TUTTI i progetti (non solo quello dal WPD)
        # perché WPD e nome progetto possono differire (es. 4298_0008 vs 4297_0008)
        progetto_con_match = progetto_attivo  # già trovato sopra

        # Se non trovato, cerca in tutti i progetti quale contiene questo filename
        if not progetto_con_match:
            tgt_search = mpf_filename.upper().replace(".MPF","").strip()
            for p in projects:
                for s in p.get("steps",[]):
                    for t in s.get("tasks",[]):
                        if t.get("text","").strip().lower() != "fresatura": continue
                        for pgm in t.get("programs",[]):
                            fn = (pgm.get("filename") or "").upper().replace(".MPF","").strip()
                            if fn == tgt_search:
                                progetto_con_match = p
                                break
                        if progetto_con_match: break
                    if progetto_con_match: break
                if progetto_con_match: break

        # ── Scenario detection cross-pallet ─────────────────────────────────
        if progetto_con_match:
            pid_corrente = (progetto_con_match.get("id") or "")
            for p_altro in projects:
                if (p_altro.get("id") or "") == pid_corrente:
                    continue
                pd, pal_d = _gestisci_cross_pallet(p_altro, pallet_data, now_str, updates)
                if pd:   proj_dirty   = True
                if pal_d: pallet_dirty = True

        # ── Logica sequenziale (v2) ─────────────────────────────────────────
        # Se il programma in esecuzione è alla posizione N nel MAIN, tutti i
        # programmi del MAIN con posizione < N e stato `in_main` vengono
        # marcati `completato`. Si fidiamo dell'ordine EXTCALL del MAIN: il log
        # Siemens può perdere qualche notifica, e se l'operatore ha saltato
        # un programma è sua responsabilità (il MAIN è la verità).
        # - programmi `da_fare` (mai in MAIN) non vengono toccati
        # - programmi `completato` restano `completato`
        # - match case-insensitive su filename, con/senza .MPF
        if progetto_con_match:
            snap = progetto_con_match.get("main_snapshot") or {}
            main_pgm_list = snap.get("main_programmi") or []
            if main_pgm_list:
                def _norm(fn):
                    return (fn or "").upper().replace(".MPF", "").strip()
                main_norm = [_norm(p) for p in main_pgm_list]
                tgt_norm = _norm(mpf_filename)
                try:
                    idx_corrente = main_norm.index(tgt_norm)
                except ValueError:
                    idx_corrente = -1

                if idx_corrente > 0:
                    # Programmi del MAIN PRIMA del corrente, se `in_main` → completato
                    precedenti = set(main_norm[:idx_corrente])
                    for step in progetto_con_match.get("steps", []):
                        for task in step.get("tasks", []):
                            if task.get("text", "").strip().lower() != "fresatura":
                                continue
                            for pgm in task.get("programs", []):
                                # v2: IPM trattati come fresatura
                                if pgm.get("stato") != "in_main":
                                    continue
                                fn_norm = _norm(pgm.get("filename"))
                                if fn_norm in precedenti:
                                    # Retro-marca: completato con utensili attesi
                                    # pre-riempiti (regola d'oro considera OK).
                                    # Bug 7 fix: setta anche tempoInizio = tempoFine
                                    # (durata zero, ma evita NoneType in consumer).
                                    pgm["stato"] = "completato"
                                    pgm["tempoInizio"] = pgm.get("tempoInizio") or now_str
                                    pgm["tempoFine"] = pgm.get("tempoFine") or now_str
                                    attesi = [
                                        (u.get("alias") or "").upper().strip()
                                        for u in (pgm.get("utensili") or [])
                                        if u.get("alias")
                                    ]
                                    pgm["_utensili_visti"] = attesi
                                    pgm["_completato_per_sequenza"] = True
                                    proj_dirty = True
                                    updates["completato"] += 1
                                    updates.setdefault("sequenziali", []).append({
                                        "programma": pgm.get("filename"),
                                        "msg": f"{pgm.get('filename')}: retro-marcato (sequenza MAIN)"
                                    })

        if progetto_con_match:
            tgt = mpf_filename.upper().replace(".MPF","").strip()
            for step in progetto_con_match.get("steps", []):
                for task in step.get("tasks", []):
                    if task.get("text","").strip().lower() != "fresatura":
                        continue
                    for pgm in task.get("programs", []):
                        # v2: IPM trattati come fresatura (operatore decide cosa mettere in MAIN)
                        fn = (pgm.get("filename") or "").upper().replace(".MPF","").strip()
                        if fn == tgt:
                            # Log dice che questo programma sta girando → forza in_lavorazione
                            if pgm.get("stato") != "in_lavorazione":
                                # Transizione a in_lavorazione: RESET pulito (Bug 1, 2, 10)
                                # tempoInizio e _utensili_visti partono da zero per ogni
                                # nuova esecuzione del programma.
                                pgm["stato"] = "in_lavorazione"
                                pgm["tempoInizio"] = now_str
                                pgm["tempoFine"]   = None
                                pgm["_utensili_visti"] = []
                                pgm.pop("_completato_per_sequenza", None)
                                proj_dirty = True
                                updates["in_macchina"] += 1
                            else:
                                # Già in_lavorazione: nulla da resettare
                                if not pgm.get("tempoInizio"):
                                    pgm["tempoInizio"] = now_str
                                    proj_dirty = True

                            # Accumula utensile corrente nei visti (dedup)
                            utensile_corrente = (data.get("utensile_attivo") or "").upper().strip()
                            if utensile_corrente:
                                visti = pgm.get("_utensili_visti") or []
                                if utensile_corrente not in visti:
                                    visti.append(utensile_corrente)
                                    pgm["_utensili_visti"] = visti
                                    proj_dirty = True

                        else:
                            # Altro programma dello stesso progetto → verifica utensili
                            if pgm.get("stato") == "in_lavorazione":
                                _, pd, pal_d = _verifica_utensili_pgm(
                                    pgm, progetto_con_match, pallet_data, now_str, updates)
                                if pd:   proj_dirty   = True
                                if pal_d: pallet_dirty = True

    # ── Automazione 5: stop macchina → completa ultimo programma ─────────
    # Quando stato_pgm torna a 0/5, l'ultimo programma girato resta in_lavorazione
    # perché non c'è un "programma successivo" che triggera la transizione.
    # Fix: al fermo, tutti i programmi in_lavorazione del progetto attivo → completato.
    # Usiamo progetto_attivo (identificato dall'ultimo programma noto prima dello stop).
    elif stato_pgm in (0, 5):
        # Recupera l'ultimo progetto noto dal log precedente (salvato nello stato)
        # attraverso tutti i progetti con programmi in_lavorazione
        for p in projects:
            pgm_in_lav = []
            for s in p.get("steps", []):
                for t in s.get("tasks", []):
                    if t.get("text","").strip().lower() != "fresatura": continue
                    for pgm in t.get("programs", []):
                        # v2: IPM trattati come fresatura
                        if pgm.get("stato") == "in_lavorazione":
                            pgm_in_lav.append(pgm)
            if pgm_in_lav:
                for pgm in pgm_in_lav:
                    _, pd, pal_d = _verifica_utensili_pgm(
                        pgm, p, pallet_data, now_str, updates)
                    if pd:   proj_dirty   = True
                    if pal_d: pallet_dirty = True

    # ── Chiusura DIFFERITA dei pallet uscenti (regola d'oro v2) ───────────────
    # Dopo aver aggiornato tutti i programmi (cross-pallet, sequenziali, corrente,
    # fratelli), i pallet che erano in_lavorazione ma non sono più attivi vengono
    # chiusi con la regola d'oro: finito se tutto completo+utensili OK, altrimenti
    # guasto. Questa fase è DIFFERITA rispetto a "marca nuovo pallet" così la
    # valutazione vede lo stato finale corretto dei programmi.
    # G4: se pallet_num è None/0 non chiude nulla.
    # G5: pallet_num valido ma programma non mappato → chiudi comunque gli altri
    #     in_lavorazione (è un cambio pallet verso programma orfano).
    if stato_pgm in (1, 3) and pallet_num:
        for pal in pallets:
            is_attivo = (pal.get("numero") == pallet_num)
            cur_stato = (pal.get("stato") or "").lower().replace(" ", "_")
            if not is_attivo and cur_stato == "in_lavorazione":
                _chiudi_pallet_in_lavorazione(pal, projects)
                pal["aggiornato"] = now_str
                pal.pop("stop_iniziato_ts", None)
                pallet_dirty = True
                updates["pallet"] += 1

    if proj_dirty:
        # Lock serializza con update_progetto dalla UI (stesso asyncio.Lock)
        async with _proj_lock:
            _save_progetti(config, proj_data)
            _invalidate_analisi_cache()
    if pallet_dirty:
        _save_pallet(config, pallet_data)

    # ── Registrazione tempi lavorazione ──────────────────────────────────────
    try:
        aggiorna_da_log(
            programma_attivo   = mpf_filename,
            stato_pgm          = stato_pgm,
            pallet_num         = pallet_num,
            progetto_nome      = updates.get("progetto_rilevato"),
            progetto_id        = updates.get("progetto_id_rilevato"),
            utensile           = data.get("utensile_attivo"),
            t_number           = data.get("numero_utensile"),
            config             = config,
            override_feed      = data.get("override_feed"),
            override_mandrino  = data.get("override_mandrino"),
            stop_type          = updates.get("stop_type"),
            allarme_testo      = data.get("allarme"),   # testo allarme Sinumerik attivo
        )
    except Exception as _e:
        updates["_report_err"] = str(_e)

    # Salva l'ultimo tick per il frontend (GET /tick)
    from datetime import datetime as _dtnow
    updates["ts"] = _dtnow.now().isoformat(timespec="seconds")
    _last_tick.update(updates)

    return updates


@router.get("/tick")
async def get_last_tick():
    """
    Restituisce il risultato dell'ultimo ciclo del poller interno.
    Usato dal GlobalPoller del frontend — sola lettura, nessuna scrittura.
    Sostituisce POST aggiorna-stati-da-log chiamato dai client.
    """
    return _last_tick
