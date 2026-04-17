"""
api/routers/vita_stimata.py
===========================
Stima live della vita utensile tra un sync TOA e il successivo.

Logica:
- Fonte di verità: life_percent dal TOA (tools_machine.json)
- Il TOA ha un mtime — tutto il lavoro successivo a quel mtime è "non contabilizzato"
- Dalle sessioni in lavorazioni_log.json, sommiamo i secondi in cui ogni utensile
  era attivo DOPO il mtime del TOA
- Vita stimata = vita_toa - (sec_lavorati_dopo_toa / sec_vita_totale_stimata) * 100

sec_vita_totale_stimata:
  Se ML ha un valore (vita_ottimale), usiamo quello.
  Altrimenti: assumiamo che vita_totale corrisponda a far scendere da 100% a 0%
  in modo lineare rispetto al tempo lavorato storico (media da tool_replacements).
  Fallback conservativo: 8h (28800s) se non abbiamo dati.

Il risultato è un dict: alias → {
    "life_percent_toa":      float,   # valore reale dal TOA
    "life_percent_stimato":  float,   # stima live (può essere None se TOA recente)
    "sec_dopo_toa":          int,     # secondi lavorati dall'ultimo sync
    "toa_mtime":             str,     # ISO timestamp dell'ultimo TOA
    "stima_affidabile":      bool,    # False se sec_dopo_toa < 300s (5 min)
}

IMPORTANTE: questo modulo NON modifica mai tools_machine.json né tool_replacements.json.
La stima è solo per display — non entra nella logica di rilevamento sostituzioni.
"""

import os
import json
import logging
from datetime import datetime
from pathlib import Path

log = logging.getLogger("vita_stimata")

# Vita totale di default se non abbiamo dati ML (8 ore = 28800s)
DEFAULT_VITA_TOTALE_SEC = 28800

# Cache: non ricalcolare se TOA non è cambiato e log non ha nuove sessioni
_cache: dict = {"result": None, "toa_mtime": 0.0, "log_mtime": 0.0}


def _toa_mtime(config: dict) -> float:
    """Restituisce il mtime di tools_machine.json (0 se non esiste)."""
    folder = config.get("tools_toa_folder") or config.get("percorso_nc_base") or ""
    p = Path(folder) / "tools_machine.json"
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _log_mtime(config: dict) -> float:
    """Restituisce il mtime di lavorazioni_log.json (0 se non esiste)."""
    folder = config.get("tools_toa_folder") or config.get("percorso_nc_base") or ""
    p = Path(folder) / "lavorazioni_log.json"
    try:
        return p.stat().st_mtime
    except OSError:
        return 0.0


def _carica_tools(config: dict) -> dict:
    """Carica tools_machine.json. Ritorna dict alias_upper → tool."""
    folder = config.get("tools_toa_folder") or config.get("percorso_nc_base") or ""
    p = Path(folder) / "tools_machine.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
        tools = data.get("tools", data) if isinstance(data, dict) else {}
        result = {}
        for t in (tools.values() if isinstance(tools, dict) else tools):
            alias = (t.get("name") or "").strip().upper()
            if alias:
                # Tieni il gemello con vita migliore
                if alias not in result or (t.get("life_percent") or 0) > (result[alias].get("life_percent") or 0):
                    result[alias] = t
        return result
    except Exception as e:
        log.debug(f"vita_stimata: tools non caricati: {e}")
        return {}


def _carica_sessioni_dopo(config: dict, dopo_ts: datetime) -> dict:
    """
    Carica lavorazioni_log.json e ritorna:
    alias_upper → sec_lavorati  (solo per programmi con fine > dopo_ts)
    """
    folder = config.get("tools_toa_folder") or config.get("percorso_nc_base") or ""
    p = Path(folder) / "lavorazioni_log.json"
    try:
        data = json.loads(p.read_text(encoding="utf-8", errors="replace"))
    except Exception:
        return {}

    uso: dict[str, int] = {}
    for sess in data.get("sessioni", []):
        for pgm in sess.get("programmi", []):
            alias = (pgm.get("utensile") or "").strip().upper()
            if not alias:
                continue
            dur = pgm.get("durata_sec") or 0
            if dur <= 0:
                continue
            # Usa la fine del programma per assegnare al giorno giusto
            fine_str = pgm.get("fine") or pgm.get("inizio") or ""
            if not fine_str:
                continue
            try:
                fine_dt = datetime.fromisoformat(fine_str)
            except Exception:
                continue
            if fine_dt <= dopo_ts:
                continue
            # Programma terminato dopo il TOA — conta il tempo
            # Se il programma era già iniziato prima del TOA, conta solo la parte dopo
            inizio_str = pgm.get("inizio") or ""
            try:
                inizio_dt = datetime.fromisoformat(inizio_str)
                if inizio_dt < dopo_ts:
                    dur = int((fine_dt - dopo_ts).total_seconds())
            except Exception:
                pass
            uso[alias] = uso.get(alias, 0) + max(0, dur)

    return uso


def _vita_totale_stimata_sec(alias: str, config: dict) -> float:
    """
    Stima quanti secondi di lavoro corrispondono al 100% di vita.
    Usa vita_ottimale ML se disponibile, altrimenti storico sostituzioni, altrimenti default.
    """
    try:
        from ml.vita_ottimale import calcola_vita_ottimale
        from api.routers.tool_history import _load_history
        records = _load_history(config)
        ris = calcola_vita_ottimale(alias, records)
        if ris and ris.get("ore_ottimali") and ris["ore_ottimali"] > 0:
            return ris["ore_ottimali"] * 3600
    except Exception:
        pass

    # Fallback: dal tool_replacements, media delle durate ciclo vita completo
    try:
        from api.routers.tool_history import _load_history
        records = _load_history(config)
        campioni = [
            r for r in records
            if (r.get("alias") or "").upper() == alias
            and r.get("tipo") == "sostituito"
            and r.get("vita_prima") is not None
            and r.get("vita_dopo") is not None
        ]
        if campioni:
            # Stima: se l'utensile è sceso da vita_prima a ~0 in un certo periodo
            # usa il rapporto vita_prima/durata per stimare la vita totale
            pass  # dati non sufficienti senza tempo lavorato per sostituzione
    except Exception:
        pass

    return float(DEFAULT_VITA_TOTALE_SEC)


def calcola_stime(config: dict) -> dict:
    """
    Calcola la vita stimata per tutti gli utensili in macchina.
    Usa cache se TOA e LOG non sono cambiati.
    """
    global _cache

    toa_mt = _toa_mtime(config)
    log_mt = _log_mtime(config)

    if (_cache["result"] is not None
            and _cache["toa_mtime"] == toa_mt
            and _cache["log_mtime"] == log_mt):
        return _cache["result"]

    if toa_mt == 0:
        return {}

    tools = _carica_tools(config)
    if not tools:
        return {}

    # Timestamp dell'ultimo TOA come datetime
    dopo_ts = datetime.fromtimestamp(toa_mt)
    toa_iso = dopo_ts.isoformat(timespec="seconds")

    # Secondi lavorati per utensile DOPO il TOA
    uso = _carica_sessioni_dopo(config, dopo_ts)

    result = {}
    for alias, tool in tools.items():
        vita_toa = tool.get("life_percent")
        if vita_toa is None:
            continue

        sec_dopo = uso.get(alias, 0)

        if sec_dopo < 60:
            # Meno di 1 minuto — non stimare, usa valore TOA
            result[alias] = {
                "life_percent_toa":     round(vita_toa, 1),
                "life_percent_stimato": None,
                "sec_dopo_toa":         sec_dopo,
                "toa_mtime":            toa_iso,
                "stima_affidabile":     False,
            }
            continue

        vita_totale_sec = _vita_totale_stimata_sec(alias, config)
        # Consumo percentuale = sec_lavorati / vita_totale * 100
        consumo_pct = (sec_dopo / vita_totale_sec) * 100.0
        stimato = max(0.0, vita_toa - consumo_pct)

        result[alias] = {
            "life_percent_toa":     round(vita_toa, 1),
            "life_percent_stimato": round(stimato, 1),
            "sec_dopo_toa":         sec_dopo,
            "toa_mtime":            toa_iso,
            "stima_affidabile":     sec_dopo >= 300,   # affidabile dopo 5 min
        }

    _cache["result"]    = result
    _cache["toa_mtime"] = toa_mt
    _cache["log_mtime"] = log_mt
    return result
