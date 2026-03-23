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

    # Ricava radice share da radice o da percorso_nc_base
    candidates_base = []

    radice = (config.get("radice") or "").strip()
    if radice:
        candidates_base.append(Path(radice))

    percorso_nc = (config.get("percorso_nc_base") or "").strip()
    if percorso_nc:
        p = Path(percorso_nc)
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

    # pallet_attivo → int (1-6) oppure None
    try:
        v = int(raw.get("pallet_attivo", 0))
        out["pallet_attivo"] = v if 1 <= v <= 6 else None
    except (ValueError, TypeError):
        out["pallet_attivo"] = None

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