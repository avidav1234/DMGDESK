"""
api/routers/tool_history.py
============================
Storico sostituzioni utensile + alert vita bassa durante lavorazione.

STORICO SOSTITUZIONI:
  Ad ogni sync TOA (cambio mtime di tools_machine.json), confronta
  i dati vecchi con i nuovi. Se un duplo ha:
    - life_percent salito significativamente (>30%) → sostituzione
    - is_worn passato da True a False → sostituzione
    - is_enabled passato da False a True → riabilitazione
  Registra in tool_replacements.json:
    { "sostituzioni": [ {ts, alias, posizione, magazine, vita_prima, vita_dopo, tipo} ] }

ALERT VITA BASSA:
  Il tick di macchina_live chiama check_low_life_alert() ogni ciclo.
  Se un utensile attivo (rilevato dal programma corrente) scende sotto
  la soglia configurata (default 20%), manda una notifica Telegram
  con throttle 30 minuti per alias.
"""

import json
import logging
from datetime import datetime, timedelta
from pathlib import Path

from fastapi import APIRouter, Body
from typing import Optional
from database.db_handler import carica_configurazione

log = logging.getLogger("tool_history")
router = APIRouter(prefix="/api/tool-history", tags=["Tool History"])

# ── Costanti ──────────────────────────────────────────────────────────────────
SOGLIA_VITA_BASSA   = 20    # % sotto cui scatta l'alert
SOGLIA_SOSTITUZIONE = 30    # delta life_percent per rilevare sostituzione
THROTTLE_MINUTES    = 30    # minuti tra due alert sullo stesso alias
MAX_RECORD          = 500   # massimo record nello storico

# ── Stato in memoria ─────────────────────────────────────────────────────────
_snapshot_precedente: dict = {}   # alias → {life_percent, is_worn, is_enabled}
_alert_inviati: dict = {}         # alias → datetime ultimo alert


# ── Path file storico ─────────────────────────────────────────────────────────

def _history_path(config: dict) -> Path | None:
    folder = (config.get("tools_toa_folder") or "").strip()
    if not folder:
        return None
    return Path(folder) / "tool_replacements.json"


def _load_history(config: dict) -> list:
    p = _history_path(config)
    if not p or not p.exists():
        return []
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        return data.get("sostituzioni", [])
    except Exception:
        return []


def _save_history(config: dict, records: list):
    p = _history_path(config)
    if not p:
        return
    try:
        # Mantieni solo gli ultimi MAX_RECORD
        records = records[-MAX_RECORD:]
        p.write_text(
            json.dumps({"sostituzioni": records}, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        log.warning(f"tool_history: impossibile salvare storico: {e}")


# ── Rilevamento sostituzioni ──────────────────────────────────────────────────

def on_tools_updated(tools_new: dict, config: dict):
    """
    Chiamato ogni volta che tools_machine.json viene ricaricato (mtime cambiato).
    Confronta con lo snapshot precedente e registra le sostituzioni.
    """
    global _snapshot_precedente

    if not _snapshot_precedente:
        # Prima volta — salva snapshot senza registrare nulla
        _snapshot_precedente = _build_snapshot(tools_new)
        return

    snap_old = _snapshot_precedente
    snap_new = _build_snapshot(tools_new)
    now      = datetime.now().isoformat(timespec="seconds")
    nuovi    = []
    existing_records = _load_history(config)  # per check duplicati

    # Indice snap_new per alias — per ricerche veloci
    snap_new_by_alias = {}
    for v in snap_new.values():
        a = (v.get("alias") or "").upper().strip()
        snap_new_by_alias.setdefault(a, []).append(v)

    # ── Rilevamento rimozioni (utensile presente prima, assente dopo) ──────────
    for key, old_t in snap_old.items():
        if key not in snap_new:
            alias_up = (old_t.get("alias") or "").upper().strip()

            # Salta se stava già in M9998/M9999 (era in transito)
            mag_old = str(old_t.get("magazine") or "")
            if mag_old in ("9998", "9999"):
                continue

            # Salta se adesso è in M9998/M9999 (ora è in mandrino/navetta)
            in_transito = any(
                str(v.get("magazine", "")) in ("9998", "9999")
                for v in snap_new_by_alias.get(alias_up, [])
            )
            if in_transito:
                continue

            # Salta se già registrato nelle ultime 2 ore (evita duplicati dello stesso evento)
            due_ore_fa = (datetime.now() - timedelta(hours=2)).isoformat(timespec="seconds")
            gia_registrato = any(
                (r.get("alias") or "").upper() == alias_up and
                (r.get("ts") or "") >= due_ore_fa
                for r in existing_records[-50:]
            )
            if gia_registrato:
                continue

            # Utensile sparito dal TOA — rimosso senza rimpiazzo
            record = {
                "ts":              now,
                "alias":           old_t.get("alias", key),
                "posizione":       old_t.get("position"),
                "magazine":        old_t.get("magazine"),
                "duplo":           old_t.get("duplo", 1),
                "vita_prima":      round(old_t.get("life_percent") or 0, 1),
                "vita_dopo":       None,
                "tipo":            "rimosso",
                "causa":           None,   # null = non classificato; liberare_spazio|rottura
                "classificato_ts": None,
            }
            nuovi.append(record)
            log.info(
                f"tool_history: rimosso — {old_t.get('alias',key)} "
                f"pos.{old_t.get('position')} vita {old_t.get('life_percent',0):.0f}%"
            )

    # ── Rilevamento sostituzioni e allungamenti vita ─────────────────────────
    for key, new in snap_new.items():
        old = snap_old.get(key)
        if not old:
            continue  # nuovo utensile aggiunto — non è una sostituzione

        lp_old = old.get("life_percent") or 0
        lp_new = new.get("life_percent") or 0
        delta  = lp_new - lp_old

        if delta > 0 and lp_new >= 99.0:
            # Vita tornata al 100% — sostituzione fisica o cambio inserti
            # vita_dopo >= 99% è il segnale affidabile di reset manuale Sinumerik
            record = {
                "ts":              now,
                "alias":           new["alias"],
                "posizione":       new.get("position"),
                "magazine":        new.get("magazine"),
                "duplo":           new.get("duplo", 1),
                "vita_prima":      round(lp_old, 1),
                "vita_dopo":       round(lp_new, 1),
                "tipo":            "sostituito",
                "causa":           None,   # null = non classificato; rottura|usura_normale|cambio_inserti
                "classificato_ts": None,
            }
            nuovi.append(record)
            log.info(
                f"tool_history: sostituito — {new['alias']} "
                f"pos.{new.get('position')} "
                f"{lp_old:.0f}% → {lp_new:.0f}%"
            )

        elif delta >= 20 and lp_new < 99.0:
            # Allungamento vita parziale — operatore ha modificato il valore manualmente
            # ma non ha resettato al 100% → non è una sostituzione
            # Registrato automaticamente senza popup — dato ML prezioso
            record = {
                "ts":              now,
                "alias":           new["alias"],
                "posizione":       new.get("position"),
                "magazine":        new.get("magazine"),
                "vita_prima":      round(lp_old, 1),
                "vita_dopo":       round(lp_new, 1),
                "tipo":            "allungamento_vita",
                "causa":           "manuale",   # classificato automaticamente
                "classificato_ts": now,
            }
            nuovi.append(record)
            log.info(
                f"tool_history: allungamento_vita — {new['alias']} "
                f"pos.{new.get('position')} "
                f"{lp_old:.0f}% → {lp_new:.0f}%"
            )

    if nuovi:
        existing = _load_history(config)
        _save_history(config, existing + nuovi)

        # Notifica Telegram per ogni sostituzione
        try:
            from telegram_monitor.notifier import send_message
            import asyncio
            for r in nuovi:
                emoji   = "🔄" if r["tipo"] == "sostituito" else "✅"
                vita_str = (
                    f"{r['vita_prima']}% → {r['vita_dopo']}%"
                    if r['vita_dopo'] is not None
                    else f"{r['vita_prima']}% → rimosso"
                )
                msg     = (
                    f"{emoji} *Utensile {r['tipo'].upper()}*\n"
                    f"`{r['alias']}` pos.{r['posizione'] or '?'}\n"
                    f"Vita: {vita_str}"
                )
                asyncio.create_task(send_message(msg))
        except Exception:
            pass

    _snapshot_precedente = snap_new


def _build_snapshot(tools: dict) -> dict:
    snap = {}
    for t in tools.values():
        alias = (t.get("name") or "").upper().strip()
        if not alias:
            continue
        key = f"{alias}_{t.get('position', '')}_{t.get('magazine', '')}"
        snap[key] = {
            "alias":        alias,
            "life_percent": t.get("life_percent"),
            "is_worn":      t.get("is_worn", False),
            "is_enabled":   t.get("is_enabled", True),
            "position":     t.get("position"),
            "magazine":     t.get("magazine"),
            "duplo":        t.get("duplo") or t.get("edge_count") or 1,
        }
    return snap


# ── Alert vita bassa ──────────────────────────────────────────────────────────

def check_low_life_alert(tools: dict, alias_attivi: list[str], config: dict):
    """
    Chiamato dal tick di macchina_live con gli alias degli utensili
    attivi nel programma corrente.
    Manda alert Telegram se vita < SOGLIA_VITA_BASSA e non già inviato
    negli ultimi THROTTLE_MINUTES minuti.
    """
    if not alias_attivi or not tools:
        return

    now = datetime.now()
    da_notificare = []

    for alias in alias_attivi:
        alias_up = alias.upper().strip()
        # Cerca il duplo con vita più bassa tra quelli abilitati
        candidati = [
            t for t in tools.values()
            if (t.get("name") or "").upper().strip() == alias_up
            and t.get("is_enabled", True)
            and not t.get("is_worn", False)
        ]
        if not candidati:
            continue

        lp_min = min((t.get("life_percent") or 100) for t in candidati)
        if lp_min > SOGLIA_VITA_BASSA:
            continue

        # Throttle: non inviare se già inviato di recente
        ultimo = _alert_inviati.get(alias_up)
        if ultimo and (now - ultimo) < timedelta(minutes=THROTTLE_MINUTES):
            continue

        _alert_inviati[alias_up] = now
        da_notificare.append((alias_up, lp_min))

    if da_notificare:
        try:
            from telegram_monitor.notifier import send_message
            import asyncio
            for alias, lp in da_notificare:
                msg = (
                    f"⚠️ *Utensile sotto soglia*\n"
                    f"`{alias}` — vita residua: *{lp:.0f}%*\n"
                    f"In lavorazione ora"
                )
                asyncio.create_task(send_message(msg))
                log.info(f"tool_history: alert vita bassa — {alias} {lp:.0f}%")
        except Exception as e:
            log.warning(f"tool_history: alert send error: {e}")


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.post("/sostituzioni/{ts}/causa")
async def classifica_sostituzione(ts: str, body: dict = Body(...)):
    """
    Classifica la causa di una sostituzione utensile.
    causa: rottura | usura | liberare_spazio
    ts: timestamp ISO della sostituzione
    """
    from database.db_handler import carica_configurazione as _cfg
    config  = _cfg()
    records = _load_history(config)
    causa   = (body.get("causa") or "").strip()
    # sostituito → rottura | usura_normale
    # rimosso    → liberare_spazio | rottura
    CAUSE_VALIDE = {"rottura", "usura_normale", "liberare_spazio"}
    if causa not in CAUSE_VALIDE:
        from fastapi import HTTPException
        raise HTTPException(400, f"causa non valida: {causa}. Valide: {CAUSE_VALIDE}")
    ts_norm = ts.strip().replace(" ", "T")
    alias_r  = (body.get("alias") or "").strip().upper()
    pos_r    = body.get("posizione")
    aggiornato = False
    for r in records:
        r_ts = (r.get("ts") or "").strip()
        if r_ts not in (ts_norm, ts):
            continue
        # Se stesso ts ma più record, discrimina per alias+posizione
        if alias_r and r.get("alias","").upper() != alias_r:
            continue
        if pos_r is not None and r.get("posizione") != pos_r:
            continue
        if r.get("causa") is not None:
            continue  # già classificato — salta
        r["causa"]            = causa
        r["classificato_ts"]  = datetime.now().isoformat(timespec="seconds")
        aggiornato = True
        log.info(f"tool_history: classificata {r.get('alias')} pos={r.get('posizione')} ts={r_ts} causa={causa}")
        break
    if not aggiornato:
        log.warning(f"tool_history: non trovata ts={ts!r} alias={alias_r!r} pos={pos_r}")
        from fastapi import HTTPException
        raise HTTPException(404, f"sostituzione non trovata")
    _save_history(config, records)
    return {"ok": True, "ts": ts, "causa": causa}


@router.post("/sostituzioni/{ts}/ignora")
async def ignora_sostituzione(ts: str, body: dict = Body({})):
    """
    Marca una sostituzione come ignorata (causa = 'ignorata').
    Non riapparirà nei popup.
    """
    from database.db_handler import carica_configurazione as _cfg
    config  = _cfg()
    records = _load_history(config)
    ts_norm  = ts.strip().replace(" ", "T")
    alias_r  = (body.get("alias") or "").strip().upper() if isinstance(body, dict) else ""
    pos_r    = body.get("posizione") if isinstance(body, dict) else None
    aggiornato = False
    for r in records:
        r_ts = (r.get("ts") or "").strip()
        if r_ts not in (ts_norm, ts):
            continue
        if alias_r and r.get("alias","").upper() != alias_r:
            continue
        if pos_r is not None and r.get("posizione") != pos_r:
            continue
        if r.get("causa") is not None:
            continue
        r["causa"]           = "ignorata"
        r["classificato_ts"] = datetime.now().isoformat(timespec="seconds")
        aggiornato = True
        log.info(f"tool_history: ignorata {r.get('alias')} pos={r.get('posizione')} ts={r_ts}")
        break
    if aggiornato:
        _save_history(config, records)
    return {"ok": True, "ts": ts, "aggiornato": aggiornato}


@router.get("/sostituzioni/non-classificate")
async def get_sostituzioni_non_classificate():
    """Restituisce sostituzioni senza causa classificata (per popup frontend)."""
    from database.db_handler import carica_configurazione as _cfg
    config  = _cfg()
    records = _load_history(config)
    non_class = [
        r for r in records
        if r.get("causa") is None
        and r.get("tipo") in ("sostituito", "rimosso")
        and str(r.get("magazine") or "") not in ("9998", "9999")
    ]
    return {"sostituzioni": list(reversed(non_class))[:10]}


@router.get("/sostituzioni")
async def get_sostituzioni(limit: int = 100):
    """Restituisce lo storico sostituzioni utensile."""
    config = carica_configurazione()
    records = _load_history(config)
    return {
        "ok":          True,
        "totale":      len(records),
        "sostituzioni": list(reversed(records))[:limit],
    }


@router.get("/vita-ottimale/{alias}")
async def get_vita_ottimale(alias: str):
    """
    Suggerimento vita ottimale per un utensile specifico.
    Ritorna None se dati insufficienti (<10 campioni).
    """
    from database.db_handler import carica_configurazione as _cfg
    from ml.vita_ottimale import calcola_vita_ottimale
    config  = _cfg()
    records = _load_history(config)
    ris     = calcola_vita_ottimale(alias, records)
    if not ris:
        return {"suggerimento": None, "motivo": "dati insufficienti"}
    return {"suggerimento": ris}


@router.get("/vita-ottimale")
async def get_vita_ottimale_magazine():
    """
    Suggerimenti vita ottimale per tutti gli utensili con abbastanza dati.
    """
    from database.db_handler import carica_configurazione as _cfg
    from ml.vita_ottimale import suggerimenti_magazine
    config  = _cfg()
    records = _load_history(config)
    ris     = suggerimenti_magazine(records)
    return {"suggerimenti": ris, "n_utensili": len(ris)}


@router.post("/pulizia-m9998")
async def pulizia_record_m9998():
    """
    Rimuove o marca come 'mandrino' i record con magazine 9998/9999
    che sono stati registrati erroneamente come rimossi.
    """
    from database.db_handler import carica_configurazione as _cfg
    config  = _cfg()
    records = _load_history(config)
    n_rimossi = 0
    records_puliti = []
    for r in records:
        if (r.get("tipo") == "rimosso" and
            str(r.get("magazine") or "") in ("9998", "9999")):
            n_rimossi += 1
            # Marca come 'mandrino' invece di rimuovere — preserva storico
            r["causa"] = "mandrino"
            r["classificato_ts"] = datetime.now().isoformat(timespec="seconds")
        records_puliti.append(r)
    _save_history(config, records_puliti)
    return {"ok": True, "record_corretti": n_rimossi}


@router.get("/stato-snapshot")
async def get_stato_snapshot():
    """Stato interno: dimensione snapshot precedente e ultimo alert per alias."""
    return {
        "snapshot_size": len(_snapshot_precedente),
        "alert_recenti": {
            k: v.isoformat() for k, v in _alert_inviati.items()
        },
    }


# ── Utilizzo magazine ─────────────────────────────────────────────────────────

@router.get("/utilizzo-magazine")
async def get_utilizzo_magazine(giorni: int = 90):
    """
    Analizza l'utilizzo degli utensili montati in macchina.

    Per ogni utensile nel TOA corrente calcola:
    - ultima_chiamata: ultima data in cui è apparso in un programma andato in macchina
    - n_chiamate: quante volte è stato chiamato nel periodo analizzato
    - n_programmi: in quanti programmi distinti compare
    - ore_stimate: somma ore stimate dei programmi che lo usano
    - categoria: attivo / dormiente / inutilizzato / nuovo

    Fonti: worktrack_projects.json (programmi + stati) + tool_replacements.json (date montaggio)
    """
    from database.db_handler import carica_configurazione as _cfg
    from api.routers.tools import _load_tools_db
    from api.routers.progetti import _load_progetti
    from datetime import datetime, timedelta

    config  = _cfg()
    now     = datetime.now()
    cutoff  = now - timedelta(days=giorni)

    # ── 1. TOA corrente ───────────────────────────────────────────────────────
    tools_db, _, _ = _load_tools_db()
    # Considera solo utensili con magazine valido (montati fisicamente)
    MAGAZINE_ESCLUSI = {9998, 9999, None}
    utensili_macchina = {
        t["name"].upper().strip(): t
        for t in tools_db.values()
        if t.get("name") and t.get("magazine") not in MAGAZINE_ESCLUSI
    }

    if not utensili_macchina:
        return {"ok": True, "utensili": [], "riepilogo": {}, "giorni_analisi": giorni}

    # ── 2. Programmi andati in macchina da worktrack_projects ─────────────────
    data = _load_progetti(config)
    progetti = data.get("projects", [])

    # Accumula per alias: {alias -> {ultima_chiamata, n_chiamate, n_programmi, ore}}
    stats: dict[str, dict] = {alias: {
        "ultima_chiamata": None,
        "n_chiamate": 0,
        "n_programmi": 0,
        "ore_stimate": 0.0,
        "programmi": [],
    } for alias in utensili_macchina}

    STATI_ESEGUITI = {"completato", "in_macchina", "in_main", "in_lavorazione"}

    for proj in progetti:
        for step in proj.get("steps", []):
            for task in step.get("tasks", []):
                if task.get("text", "").strip().lower() != "fresatura":
                    continue
                for pgm in task.get("programs", []):
                    if pgm.get("stato") not in STATI_ESEGUITI:
                        continue
                    # Data esecuzione: tempoInizio o dataPost
                    ts_str = pgm.get("tempoInizio") or pgm.get("dataPost") or ""
                    ts_pgm = None
                    if ts_str:
                        try:
                            ts_clean = ts_str[:19].strip()
                            # Supporta DD/MM/YYYY HH:MM e ISO YYYY-MM-DD
                            if ts_clean[2:3] == "/":
                                # DD/MM/YYYY HH:MM
                                parts = ts_clean.replace(" ", "/").replace(":", "/").split("/")
                                if len(parts) >= 3:
                                    d,m,y = parts[0],parts[1],parts[2]
                                    hh = parts[3] if len(parts)>3 else "00"
                                    mm = parts[4] if len(parts)>4 else "00"
                                    ts_pgm = datetime(int(y),int(m),int(d),int(hh),int(mm))
                            else:
                                ts_pgm = datetime.fromisoformat(ts_clean)
                        except Exception:
                            pass

                    # Lista alias del programma — tutte le fonti disponibili
                    utensili_pgm = list(pgm.get("utensili_lista") or [])
                    # Fallback: campo utensili [{alias, tempoMin}]
                    for u in (pgm.get("utensili") or []):
                        a = (u.get("alias") or "").strip()
                        if a and a not in utensili_pgm:
                            utensili_pgm.append(a)
                    # Fallback: campo utensile singolo
                    if not utensili_pgm and pgm.get("utensile"):
                        utensili_pgm = [pgm["utensile"]]

                    ore_pgm = (pgm.get("tempoStimato") or 0) / 60.0  # min → ore

                    for alias_raw in utensili_pgm:
                        alias_up = (alias_raw or "").upper().strip()
                        if alias_up not in stats:
                            continue
                        s = stats[alias_up]
                        s["n_chiamate"] += 1
                        s["ore_stimate"] = round(s["ore_stimate"] + ore_pgm, 2)
                        if ts_pgm:
                            if s["ultima_chiamata"] is None or ts_pgm > s["ultima_chiamata"]:
                                s["ultima_chiamata"] = ts_pgm
                        pgm_id = pgm.get("filename") or pgm.get("id") or ""
                        if pgm_id and pgm_id not in s["programmi"]:
                            s["programmi"].append(pgm_id)
                            s["n_programmi"] += 1

    # ── 3. Date montaggio da tool_replacements ────────────────────────────────
    replacements = _load_history(config)
    # Ultimo evento per alias: ts del montaggio (vita_dopo > 0 = nuovo montaggio)
    montaggio: dict[str, datetime] = {}
    for r in replacements:
        alias_up = (r.get("alias") or "").upper().strip()
        if alias_up not in utensili_macchina:
            continue
        try:
            ts = datetime.fromisoformat(r["ts"][:19])
        except Exception:
            continue
        # "sostituito" o "allungamento_vita" = utensile presente/montato
        if r.get("tipo") in ("sostituito", "allungamento_vita"):
            if alias_up not in montaggio or ts > montaggio[alias_up]:
                montaggio[alias_up] = ts

    # ── 4. Classificazione ───────────────────────────────────────────────────
    SOGLIA_ATTIVO     = 30   # giorni
    SOGLIA_DORMIENTE  = 90   # giorni
    SOGLIA_NUOVO      = 30   # giorni dal montaggio

    risultati = []
    for alias, s in stats.items():
        tool = utensili_macchina[alias]
        uc   = s["ultima_chiamata"]
        mont = montaggio.get(alias)

        # Calcola giorni dall'ultima chiamata
        giorni_silenzio = None
        if uc:
            giorni_silenzio = (now - uc).days

        # Categoria
        if mont and (now - mont).days < SOGLIA_NUOVO and not uc:
            categoria = "nuovo"
        elif uc is None:
            categoria = "inutilizzato"
        elif giorni_silenzio <= SOGLIA_ATTIVO:
            categoria = "attivo"
        elif giorni_silenzio <= SOGLIA_DORMIENTE:
            categoria = "dormiente"
        else:
            categoria = "inutilizzato"

        risultati.append({
            "alias":           alias,
            "magazine":        tool.get("magazine"),
            "posizione":       tool.get("position"),
            "life_percent":    tool.get("life_percent"),
            "is_enabled":      tool.get("is_enabled", True),
            "categoria":       categoria,
            "ultima_chiamata": uc.strftime("%d/%m/%Y") if uc else None,
            "giorni_silenzio": giorni_silenzio,
            "n_chiamate":      s["n_chiamate"],
            "n_programmi":     s["n_programmi"],
            "ore_stimate":     s["ore_stimate"],
            "data_montaggio":  mont.strftime("%d/%m/%Y") if mont else None,
        })

    # Ordina: inutilizzati prima, poi per giorni_silenzio decrescente
    ORDINE_CAT = {"inutilizzato": 0, "dormiente": 1, "nuovo": 2, "attivo": 3}
    risultati.sort(key=lambda x: (
        ORDINE_CAT.get(x["categoria"], 9),
        -(x["giorni_silenzio"] or 9999)
    ))

    # ── 5. Riepilogo ─────────────────────────────────────────────────────────
    riepilogo = {
        "totale_in_macchina": len(risultati),
        "attivi":      sum(1 for r in risultati if r["categoria"] == "attivo"),
        "dormienti":   sum(1 for r in risultati if r["categoria"] == "dormiente"),
        "inutilizzati":sum(1 for r in risultati if r["categoria"] == "inutilizzato"),
        "nuovi":       sum(1 for r in risultati if r["categoria"] == "nuovo"),
    }

    return {
        "ok": True,
        "giorni_analisi": giorni,
        "data_analisi": now.strftime("%d/%m/%Y %H:%M"),
        "riepilogo": riepilogo,
        "utensili": risultati,
    }


@router.get("/utilizzo-debug")
async def debug_utilizzo():
    """Debug: mostra quanti programmi con utensili_lista trova nel worktrack_projects."""
    from database.db_handler import carica_configurazione as _cfg
    from api.routers.tools import _load_tools_db
    from api.routers.progetti import _load_progetti

    config  = _cfg()
    tools_db, _, _ = _load_tools_db()
    data    = _load_progetti(config)
    progetti = data.get("projects", [])

    ESCLUSI = {9998, 9999, None}
    n_toa = sum(1 for t in tools_db.values()
                if t.get("name") and t.get("magazine") not in ESCLUSI)

    STATI = {"completato","in_macchina","in_main","in_lavorazione"}
    n_pgm_tot, n_pgm_con_lista, n_pgm_con_utensile, n_pgm_con_stati = 0,0,0,0
    alias_trovati = set()

    for proj in progetti:
        for step in proj.get("steps",[]):
            for task in step.get("tasks",[]):
                if task.get("text","").strip().lower() != "fresatura": continue
                for pgm in task.get("programs",[]):
                    n_pgm_tot += 1
                    if pgm.get("stato") in STATI: n_pgm_con_stati += 1
                    if pgm.get("utensili_lista"): n_pgm_con_lista += 1
                    if pgm.get("utensile"): n_pgm_con_utensile += 1
                    for a in (pgm.get("utensili_lista") or []):
                        alias_trovati.add(a.upper())
                    for u in (pgm.get("utensili") or []):
                        if u.get("alias"): alias_trovati.add(u["alias"].upper())
                    if pgm.get("utensile"): alias_trovati.add(pgm["utensile"].upper())

    toa_aliases = {t["name"].upper() for t in tools_db.values()
                   if t.get("name") and t.get("magazine") not in ESCLUSI}

    return {
        "toa_utensili_in_macchina": n_toa,
        "toa_aliases": sorted(toa_aliases)[:20],
        "progetti_totali": len(progetti),
        "programmi_totali": n_pgm_tot,
        "programmi_con_stato_eseguito": n_pgm_con_stati,
        "programmi_con_utensili_lista": n_pgm_con_lista,
        "programmi_con_utensile_singolo": n_pgm_con_utensile,
        "alias_unici_trovati_nei_pgm": len(alias_trovati),
        "alias_in_comune_toa_e_pgm": len(toa_aliases & alias_trovati),
        "esempi_alias_pgm": sorted(alias_trovati)[:20],
    }
