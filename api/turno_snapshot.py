"""
api/turno_snapshot.py
=====================
Calcola e salva snapshot riepilogo turno.

Due finestre fisse per giorno solare:
  - NOTTE:  16:30 (ieri) → 07:30 (oggi)  — macchina in autonomia
  - GIORNO: 07:30 (oggi) → 16:30 (oggi)  — operatore presente

Snapshot salvati in turni_snapshot.json (array di snapshot storici).
Ogni snapshot contiene ore macchina, programmi eseguiti, utensili,
ore CAM, distribuzione per commessa.

Task automatici (creati in main.py startup):
  - 07:30 → genera snapshot NOTTE
  - 16:30 → genera snapshot GIORNO
"""

import json
import asyncio
from datetime import datetime, date, timedelta, time
from pathlib import Path
from typing import Literal

from database.db_handler import carica_configurazione
from api.constants import (
    INIZIO_TURNO_ORA, INIZIO_TURNO_MIN,
    FINE_TURNO_ORA,   FINE_TURNO_MIN,
)

SNAPSHOT_FILE = Path("turni_snapshot.json")
MAX_SNAPSHOTS = 90  # giorni di storico


def _load_snapshots() -> list:
    if SNAPSHOT_FILE.exists():
        try:
            data = json.loads(SNAPSHOT_FILE.read_text(encoding="utf-8"))
            return data if isinstance(data, list) else []
        except Exception:
            pass
    return []


def _save_snapshots(snapshots: list):
    SNAPSHOT_FILE.write_text(
        json.dumps(snapshots, ensure_ascii=False, indent=2),
        encoding="utf-8"
    )


def _durata_str(sec: int) -> str:
    if not sec:
        return "0h"
    h = sec // 3600
    m = (sec % 3600) // 60
    return f"{h}h {m}m" if m else f"{h}h"


def calcola_snapshot(
    finestra: Literal["notte", "giorno"],
    data_rif: date | None = None,
) -> dict:
    """
    Calcola il riepilogo per la finestra richiesta.

    finestra="notte":  16:30 (data_rif - 1) → 07:30 (data_rif)
    finestra="giorno": 07:30 (data_rif) → 16:30 (data_rif)

    data_rif default = oggi
    """
    config = carica_configurazione()
    if data_rif is None:
        data_rif = date.today()

    # ── Definisci i limiti temporali ─────────────────────────────────────────
    if finestra == "notte":
        # 16:30 ieri → 07:30 oggi
        inizio_dt = datetime.combine(
            data_rif - timedelta(days=1),
            time(FINE_TURNO_ORA, FINE_TURNO_MIN)
        )
        fine_dt = datetime.combine(
            data_rif,
            time(INIZIO_TURNO_ORA, INIZIO_TURNO_MIN)
        )
    else:
        # 07:30 oggi → 16:30 oggi
        inizio_dt = datetime.combine(
            data_rif,
            time(INIZIO_TURNO_ORA, INIZIO_TURNO_MIN)
        )
        fine_dt = datetime.combine(
            data_rif,
            time(FINE_TURNO_ORA, FINE_TURNO_MIN)
        )

    inizio_iso = inizio_dt.isoformat()
    fine_iso   = fine_dt.isoformat()

    # ── Carica log lavorazioni ───────────────────────────────────────────────
    from api.routers.report import _load_log, _log_path
    log_data = _load_log(config)
    sessioni = log_data.get("sessioni", [])

    # Filtra sessioni che si sovrappongono alla finestra
    sessioni_finestra = []
    for s in sessioni:
        s_inizio = s.get("inizio", "")
        s_fine   = s.get("fine") or ""
        if not s_inizio:
            continue
        # Includi se la sessione ha sovrapposizione con la finestra
        if s_fine and s_fine < inizio_iso:
            continue  # finita prima della finestra
        if s_inizio > fine_iso:
            continue  # iniziata dopo la finestra
        sessioni_finestra.append(s)

    # ── Calcola ore macchina nella finestra ──────────────────────────────────
    ore_mac_sec = 0
    programmi_eseguiti = []
    utensili_usati = set()
    commesse_ore: dict[str, int] = {}

    for s in sessioni_finestra:
        prog_nome = s.get("progetto", "—")
        for pgm in s.get("programmi", []):
            p_inizio = pgm.get("inizio", "")
            p_fine   = pgm.get("fine", "")
            dur      = pgm.get("durata_sec") or 0
            if not p_fine or not dur:
                continue
            # Clip alla finestra
            p_start = max(p_inizio, inizio_iso)
            p_end   = min(p_fine, fine_iso)
            if p_start >= p_end:
                continue
            # Proporzione del ciclo dentro la finestra
            try:
                ratio = (
                    datetime.fromisoformat(p_end) -
                    datetime.fromisoformat(p_start)
                ).total_seconds() / max(dur, 1)
                ratio = min(ratio, 1.0)
            except Exception:
                ratio = 1.0
            dur_clip = round(dur * ratio)
            ore_mac_sec += dur_clip
            commesse_ore[prog_nome] = commesse_ore.get(prog_nome, 0) + dur_clip
            if pgm.get("utensile"):
                utensili_usati.add(pgm["utensile"])
            programmi_eseguiti.append({
                "filename":   pgm.get("filename"),
                "progetto":   prog_nome,
                "durata_sec": dur_clip,
                "inizio":     p_inizio,
                "fine":       p_fine,
                "utensile":   pgm.get("utensile"),
            })

    # ── Ore CAM nella finestra (solo per finestra giorno) ────────────────────
    ore_cam_sec = 0
    cam_per_commessa: dict[str, int] = {}
    if finestra == "giorno":
        try:
            cam_file = Path("cam_tracker_data.json")
            if cam_file.exists():
                cam_data = json.loads(cam_file.read_text(encoding="utf-8"))
                for e in cam_data:
                    # Controlla timestamp sessione CAM
                    ts_start = e.get("start") or e.get("timestamp", "")
                    ts_end   = e.get("end") or ""
                    if ts_start and ts_start > fine_iso:
                        continue
                    if ts_end and ts_end < inizio_iso:
                        continue
                    sec = e.get("seconds", 0)
                    proj = (e.get("project") or "").upper()
                    ore_cam_sec += sec
                    cam_per_commessa[proj] = cam_per_commessa.get(proj, 0) + sec
        except Exception:
            pass

    # ── Distribuzione commesse (con project_id per link rendiconto) ──────────
    from api.routers.progetti import _load_progetti
    proj_data = _load_progetti(config)
    # Mappa nome → id
    nome_to_id = {p.get("name", ""): p.get("id", "") for p in proj_data.get("projects", [])}

    distribuzione = sorted(
        [
            {
                "commessa":    k,
                "progetto_id": nome_to_id.get(k, ""),
                "ore_sec":     v,
                "ore_str":     _durata_str(v),
                "pct":         round(v / ore_mac_sec * 100, 1) if ore_mac_sec else 0,
                "ore_cam_sec": cam_per_commessa.get(k.upper(), 0),
            }
            for k, v in commesse_ore.items()
        ],
        key=lambda x: -x["ore_sec"]
    )

    return {
        "finestra":           finestra,
        "data":               data_rif.isoformat(),
        "generato_il":        datetime.now().isoformat(),
        "inizio":             inizio_iso,
        "fine":               fine_iso,
        "ore_macchina_sec":   ore_mac_sec,
        "ore_macchina_str":   _durata_str(ore_mac_sec),
        "ore_cam_sec":        ore_cam_sec,
        "ore_cam_str":        _durata_str(ore_cam_sec),
        "n_programmi":        len(programmi_eseguiti),
        "n_utensili":         len(utensili_usati),
        "n_commesse":         len(commesse_ore),
        "distribuzione":      distribuzione,
        "programmi":          programmi_eseguiti[:50],  # max 50 per non appesantire
        "utensili":           sorted(utensili_usati),
    }


def salva_snapshot(finestra: Literal["notte", "giorno"], data_rif: date | None = None) -> dict:
    """Calcola e persiste snapshot. Sovrascrive se stesso giorno+finestra già presente."""
    snap = calcola_snapshot(finestra, data_rif)
    snapshots = _load_snapshots()

    # Rimuovi eventuale snapshot precedente per stesso giorno+finestra
    snapshots = [
        s for s in snapshots
        if not (s.get("data") == snap["data"] and s.get("finestra") == snap["finestra"])
    ]
    snapshots.append(snap)

    # Mantieni solo ultimi MAX_SNAPSHOTS giorni (2 snap/giorno)
    snapshots = snapshots[-(MAX_SNAPSHOTS * 2):]
    _save_snapshots(snapshots)
    return snap


# ── Task schedulatore ─────────────────────────────────────────────────────────

async def _scheduler_loop():
    """
    Loop asincrono che gira in background.
    Alle 07:30 → snapshot notte
    Alle 16:30 → snapshot giorno
    """
    import logging
    log = logging.getLogger("turno_scheduler")
    triggered_today: set[str] = set()  # "notte-YYYY-MM-DD", "giorno-YYYY-MM-DD"

    while True:
        now = datetime.now()
        oggi = now.date().isoformat()

        # Controlla finestra notte (07:30)
        chiave_notte = f"notte-{oggi}"
        if (now.hour == INIZIO_TURNO_ORA and now.minute >= INIZIO_TURNO_MIN
                and chiave_notte not in triggered_today):
            try:
                snap = salva_snapshot("notte")
                log.info(f"Snapshot NOTTE generato: {snap['ore_macchina_str']} macchina, "
                         f"{snap['n_commesse']} commesse")
                triggered_today.add(chiave_notte)
            except Exception as e:
                log.error(f"Errore snapshot notte: {e}")

        # Controlla finestra giorno (16:30)
        chiave_giorno = f"giorno-{oggi}"
        if (now.hour == FINE_TURNO_ORA and now.minute >= FINE_TURNO_MIN
                and chiave_giorno not in triggered_today):
            try:
                snap = salva_snapshot("giorno")
                log.info(f"Snapshot GIORNO generato: {snap['ore_macchina_str']} macchina, "
                         f"{snap['ore_cam_str']} CAM, {snap['n_commesse']} commesse")
                triggered_today.add(chiave_giorno)
            except Exception as e:
                log.error(f"Errore snapshot giorno: {e}")

        # Pulizia triggered_today a mezzanotte
        if now.hour == 0 and now.minute == 0:
            triggered_today.clear()

        await asyncio.sleep(60)  # check ogni minuto
