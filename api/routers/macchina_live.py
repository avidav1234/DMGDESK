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
            and "_N_MPF_DIR" not in prog and prog != "0":
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
            # Classificazione Sinumerik 840D:
            # 700000-709999 = messaggi/avvertenze PLC (non fermano la macchina)
            # < 700000      = allarmi NCK (fermano la macchina)
            try:
                n = int(codice)
                if 700000 <= n <= 709999:
                    tipo = "messaggio"
                else:
                    tipo = "allarme"
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
    Chiamata dal frontend ogni 5 secondi.
    Legge programma_attivo e stato_programma dal log OpcUa e applica:
    1. Pallet in lavorazione da log (stato=3)
    2. Programma attivo → in_macchina
    3. Programma precedente → completato (cambio programma)
    4. Pallet → grezzo/finito quando macchina si ferma
    """
    from api.routers.progetti import _load_progetti, _save_progetti, _invalidate_analisi_cache
    from api.routers.pallet import _load as _load_pallet, _save as _save_pallet
    from datetime import datetime as _dt

    config   = carica_configurazione()
    log_path = _trova_log_path(config)
    if not log_path:
        return {"aggiornamenti": 0, "nota": "log non trovato"}

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
    # Se la macchina sta girando e non vediamo un nuovo PALLET nel log recente,
    # significa che siamo nel programma figlio — il pallet in_lavorazione è ancora valido
    if not pallet_num and stato_pgm in (1, 3):
        for pal in pallets:
            if (pal.get("stato") or "").lower().replace(" ","_") == "in_lavorazione":
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

    updates["progetto_rilevato"] = progetto_attivo.get("name") if progetto_attivo else None
    updates["pallet_rilevato"]   = pallet_num
    updates["_debug"] = {
        "wpd_nome": wpd_nome, "mpf_progetto": mpf_progetto,
        "pallet_num": pallet_num, "stato_pgm": stato_pgm,
        "mpf_filename": mpf_filename,
        "prog_attivo": prog_attivo, "prog_raw_full": prog_raw_full[:80] if prog_raw_full else None,
    }

    # ── Automazione 1 e 4: stato pallet ──────────────────────────────────
    # Il log è la fonte di verità assoluta:
    # - Macchina IN ESECUZIONE con progetto X → pallet di X = in_lavorazione,
    #   tutti gli altri in_lavorazione → grezzo/finito (anche se impostati manualmente)
    # - Macchina FERMA → tutti i pallet in_lavorazione → grezzo/finito

    def _a_grezzo_o_finito(pal, projects):
        pid = pal.get("progetto_id")
        if not pid:
            pal["stato"] = "grezzo"; return
        proj = next((p for p in projects if p.get("id") == pid), None)
        if not proj:
            pal["stato"] = "grezzo"; return
        all_pgm = [pg for s in proj.get("steps",[])
            for t in s.get("tasks",[])
            if t.get("text","").strip().lower()=="fresatura"
            for pg in t.get("programs",[])
            if pg.get("tipoGruppo")!="ipm"]
        pal["stato"] = "finito" if (all_pgm and all(
            pg.get("stato")=="completato" for pg in all_pgm)) else "grezzo"

    if stato_pgm in (1, 3):
        # Macchina IN ESECUZIONE
        for pal in pallets:
            is_attivo = (pal.get("numero") == pallet_num)
            cur_stato = (pal.get("stato") or "").lower().replace(" ","_")
            if is_attivo:
                if cur_stato != "in_lavorazione":
                    pal["stato"] = "in_lavorazione"
                    pal["aggiornato"] = now_str
                    pallet_dirty = True
                    updates["pallet"] += 1
            else:
                # FIX: qualsiasi altro pallet in_lavorazione viene resettato
                if cur_stato == "in_lavorazione":
                    _a_grezzo_o_finito(pal, projects)
                    pal["aggiornato"] = now_str
                    pallet_dirty = True
                    updates["pallet"] += 1

    elif stato_pgm in (0, 5):
        # Macchina FERMA → tutti i pallet in_lavorazione → grezzo/finito
        for pal in pallets:
            if (pal.get("stato") or "").lower().replace(" ","_") == "in_lavorazione":
                _a_grezzo_o_finito(pal, projects)
                pal["aggiornato"] = now_str
                pallet_dirty = True
                updates["pallet"] += 1


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

        if progetto_con_match:
            tgt = mpf_filename.upper().replace(".MPF","").strip()
            for step in progetto_con_match.get("steps", []):
                for task in step.get("tasks", []):
                    if task.get("text","").strip().lower() != "fresatura":
                        continue
                    for pgm in task.get("programs", []):
                        if pgm.get("tipoGruppo") == "ipm":
                            continue
                        fn = (pgm.get("filename") or "").upper().replace(".MPF","").strip()
                        if fn == tgt:
                            # Programma attivo → in_macchina
                            if pgm.get("stato") == "da_fare":
                                pgm["stato"] = "in_macchina"
                                pgm["tempoInizio"] = pgm.get("tempoInizio") or now_str
                                proj_dirty = True
                                updates["in_macchina"] += 1
                        else:
                            # Altro programma → se era in_macchina diventa completato
                            if pgm.get("stato") == "in_macchina":
                                pgm["stato"] = "completato"
                                pgm["tempoFine"] = pgm.get("tempoFine") or now_str
                                proj_dirty = True
                                updates["completato"] += 1

    if proj_dirty:
        _save_progetti(config, proj_data)
        _invalidate_analisi_cache()
    if pallet_dirty:
        _save_pallet(config, pallet_data)

    # ── Registrazione tempi lavorazione ──────────────────────────────────────
    try:
        from api.routers.report import aggiorna_da_log
        aggiorna_da_log(
            programma_attivo = mpf_filename,
            stato_pgm        = stato_pgm,
            pallet_num       = pallet_num,
            progetto_nome    = updates.get("progetto_rilevato"),
            utensile         = data.get("utensile_attivo"),
            t_number         = data.get("numero_utensile"),
            config           = config,
        )
    except Exception as _e:
        updates["_report_err"] = str(_e)

    return updates
