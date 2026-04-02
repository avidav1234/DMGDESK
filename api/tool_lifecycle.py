"""
api/tool_lifecycle.py
=====================
Tracking automatico smontati/montati al sync TOA.

Ad ogni sync, confronta la lista utensili precedente con quella nuova:
  - Utensile scomparso → salvato in smontati con vita residua al momento
  - Utensile comparso  → cercato in smontati per alias → vita residua recuperata

Regola di conflitto (TOA vs smontati):
  Se |TOA_pct - smontati_pct| >= 20% → vince TOA (cambio inserto probabile)
  Altrimenti → vince il valore più basso (più prudente)
"""

import json
import logging
from datetime import datetime
from pathlib import Path
from typing import Optional

log = logging.getLogger(__name__)

CONFLICT_THRESHOLD = 20.0  # % differenza oltre cui si assume cambio inserto


def _lifecycle_path(tools_folder: str) -> Path:
    return Path(tools_folder) / "tool_lifecycle.json"


def _load_lifecycle(tools_folder: str) -> dict:
    """Carica il DB lifecycle. Struttura:
    {
      "utensili_in_macchina": { "3470": {"alias": "FS25R2L85", "life_remaining": 29.1, ...} },
      "smontati": [
        {
          "alias": "FS25R2L85",
          "t_number": 3470,
          "life_remaining": 29.1,
          "life_total": 120,
          "life_percent": 24.3,
          "data_smontaggio": "2026-04-02T14:31:00",
          "data_rimontaggio": null,
          "note": ""
        }
      ]
    }
    """
    path = _lifecycle_path(tools_folder)
    if not path.exists():
        return {"utensili_in_macchina": {}, "smontati": []}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"utensili_in_macchina": {}, "smontati": []}


def _save_lifecycle(tools_folder: str, data: dict) -> None:
    path = _lifecycle_path(tools_folder)
    tmp  = path.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        tmp.replace(path)
    except Exception as e:
        log.error(f"[Lifecycle] Errore salvataggio: {e}")
        try: tmp.unlink(missing_ok=True)
        except Exception: pass


def _resolve_conflict(toa_remaining: float, toa_total: float,
                      saved_remaining: float, saved_total: float) -> tuple[float, float, str]:
    """
    Risolve il conflitto tra vita TOA e vita salvata in smontati.
    Ritorna (life_remaining, life_total, motivo).
    """
    if toa_total <= 0:
        return saved_remaining, saved_total, "toa_no_total"

    toa_pct   = (toa_remaining / toa_total) * 100
    saved_pct = (saved_remaining / saved_total) * 100 if saved_total > 0 else 0

    diff = abs(toa_pct - saved_pct)

    if diff >= CONFLICT_THRESHOLD:
        # Differenza grande → probabile cambio inserto → usa TOA
        return toa_remaining, toa_total, f"cambio_inserto (diff={diff:.1f}%)"
    else:
        # Differenza piccola → usa il valore più basso (più prudente)
        if toa_remaining <= saved_remaining:
            return toa_remaining, toa_total, f"toa_minore (diff={diff:.1f}%)"
        else:
            return saved_remaining, saved_total, f"smontati_minore (diff={diff:.1f}%)"


def process_sync(tools_folder: str, new_tools: dict) -> dict:
    """
    Confronta nuova lista utensili (dal sync TOA) con quella precedente.
    Aggiorna il DB lifecycle: smonta i spariti, monta i nuovi.

    Args:
        tools_folder: cartella dove salvare tool_lifecycle.json
        new_tools: dict {t_number: MachineTool} dal sync TOA

    Returns:
        dict con statistiche: smontati, montati, aggiornati, conflitti
    """
    now     = datetime.now().isoformat(timespec="seconds")
    db      = _load_lifecycle(tools_folder)
    prev    = db.get("utensili_in_macchina", {})   # {str(t_num): {...}}
    smontati = db.get("smontati", [])

    prev_tnums = set(prev.keys())
    new_tnums  = set(str(t) for t in new_tools.keys())

    scomparsi = prev_tnums - new_tnums   # erano in macchina, ora non ci sono
    comparsi  = new_tnums - prev_tnums   # non c'erano, ora ci sono
    rimasti   = prev_tnums & new_tnums   # erano e ci sono ancora

    stats = {"smontati": 0, "montati": 0, "aggiornati": 0,
             "conflitti_risolti": 0, "conflitti_dettaglio": []}

    # ── Utensili scomparsi → aggiungi a smontati ──────────────────────────────
    for tnum_str in scomparsi:
        prev_tool = prev[tnum_str]
        alias = prev_tool.get("alias", "")
        if not alias:
            continue

        life_rem   = prev_tool.get("life_remaining", 0)
        life_total = prev_tool.get("life_total", 0)
        life_pct   = (life_rem / life_total * 100) if life_total > 0 else None

        entry = {
            "alias":           alias,
            "t_number":        int(tnum_str),
            "life_remaining":  round(life_rem, 3),
            "life_total":      round(life_total, 3),
            "life_percent":    round(life_pct, 1) if life_pct is not None else None,
            "data_smontaggio": now,
            "data_rimontaggio": None,
            "note":            "auto",
        }
        smontati.append(entry)
        stats["smontati"] += 1
        log.info(f"[Lifecycle] Smontato T{tnum_str} {alias} "
                 f"({life_rem:.1f}/{life_total:.0f} min, {life_pct:.1f}%)" if life_pct else
                 f"[Lifecycle] Smontato T{tnum_str} {alias} (vita non tracciata)")

    # ── Utensili comparsi → cerca in smontati per alias ──────────────────────
    new_in_machine = {}
    for tnum_str in comparsi:
        t_num = int(tnum_str)
        tool  = new_tools[t_num]
        alias = tool.name

        # Cerca in smontati per alias (più recente prima)
        candidati = [
            (i, s) for i, s in enumerate(smontati)
            if s.get("alias", "").upper() == alias.upper()
            and s.get("data_rimontaggio") is None
            and s.get("life_total", 0) > 0
        ]
        candidati.sort(key=lambda x: x[1].get("data_smontaggio", ""), reverse=True)

        toa_remaining = tool.life_remaining or 0
        toa_total     = tool.life_total     or 0

        if candidati and toa_total > 0:
            idx, saved = candidati[0]
            saved_rem   = saved.get("life_remaining", 0)
            saved_total = saved.get("life_total", 0)

            final_rem, final_total, motivo = _resolve_conflict(
                toa_remaining, toa_total, saved_rem, saved_total
            )

            if motivo.startswith("smontati"):
                stats["conflitti_risolti"] += 1
                stats["conflitti_dettaglio"].append({
                    "alias":  alias,
                    "t_num":  t_num,
                    "toa":    f"{toa_remaining:.1f}/{toa_total:.0f}",
                    "saved":  f"{saved_rem:.1f}/{saved_total:.0f}",
                    "usato":  "smontati",
                    "motivo": motivo,
                })

            # Marca il record smontato come rimontato
            smontati[idx]["data_rimontaggio"] = now
            smontati[idx]["t_number_nuovo"]   = t_num

            log.info(f"[Lifecycle] Montato T{t_num} {alias} → "
                     f"vita: {final_rem:.1f}/{final_total:.0f} min ({motivo})")

            new_in_machine[tnum_str] = {
                "alias":         alias,
                "life_remaining": round(final_rem, 3),
                "life_total":     round(final_total, 3),
                "life_percent":   round(final_rem / final_total * 100, 1) if final_total > 0 else None,
                "sync_time":     now,
            }
        else:
            # Utensile nuovo o senza storico
            new_in_machine[tnum_str] = {
                "alias":          alias,
                "life_remaining": round(toa_remaining, 3),
                "life_total":     round(toa_total, 3),
                "life_percent":   round(toa_remaining / toa_total * 100, 1) if toa_total > 0 else None,
                "sync_time":      now,
            }
        stats["montati"] += 1

    # ── Utensili rimasti → aggiorna vita dal TOA (fonte più accurata) ─────────
    for tnum_str in rimasti:
        t_num = int(tnum_str)
        tool  = new_tools[t_num]
        toa_rem   = tool.life_remaining or 0
        toa_total = tool.life_total     or 0
        new_in_machine[tnum_str] = {
            "alias":          tool.name,
            "life_remaining": round(toa_rem, 3),
            "life_total":     round(toa_total, 3),
            "life_percent":   round(toa_rem / toa_total * 100, 1) if toa_total > 0 else None,
            "sync_time":      now,
        }
        stats["aggiornati"] += 1

    # ── Salva ─────────────────────────────────────────────────────────────────
    db["utensili_in_macchina"] = new_in_machine
    db["smontati"]             = smontati
    db["ultimo_sync"]          = now
    _save_lifecycle(tools_folder, db)

    log.info(f"[Lifecycle] Sync: +{stats['smontati']} smontati, "
             f"+{stats['montati']} montati, {stats['aggiornati']} aggiornati, "
             f"{stats['conflitti_risolti']} conflitti risolti")

    return stats


def get_smontati(tools_folder: str, solo_con_vita: bool = False) -> list:
    """Ritorna lista utensili smontati (non ancora rimontati)."""
    db = _load_lifecycle(tools_folder)
    smontati = [
        s for s in db.get("smontati", [])
        if s.get("data_rimontaggio") is None
    ]
    if solo_con_vita:
        smontati = [s for s in smontati if (s.get("life_total") or 0) > 0]
    smontati.sort(key=lambda s: s.get("data_smontaggio", ""), reverse=True)
    return smontati


def get_vita_utensile(tools_folder: str, alias: str) -> Optional[dict]:
    """
    Ritorna la vita residua di un utensile cercando per alias.
    Prima cerca in macchina (TOA attuale), poi in smontati.
    """
    db = _load_lifecycle(tools_folder)

    # In macchina
    for entry in db.get("utensili_in_macchina", {}).values():
        if entry.get("alias", "").upper() == alias.upper():
            return {**entry, "posizione": "in_macchina"}

    # Smontati (più recente)
    candidati = [
        s for s in db.get("smontati", [])
        if s.get("alias", "").upper() == alias.upper()
        and s.get("data_rimontaggio") is None
    ]
    if candidati:
        candidati.sort(key=lambda s: s.get("data_smontaggio", ""), reverse=True)
        return {**candidati[0], "posizione": "smontato"}

    return None
