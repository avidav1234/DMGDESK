"""
ml/vita_ottimale.py
===================
CERVELLO UNICO per la gestione della vita utensile in DMGDesk.

Tutti i moduli del sistema che riguardano la vita utensile passano da qui:
  - tool_history.py  → check_low_life_alert usa soglia_alert()
  - progetti.py      → fin_vita usa soglia_fin_vita()
  - progetti_utensili.py → classify_tool_state usa soglia_fin_vita()
  - macchina_live.py → allerta_utensile usa soglia_fin_vita()
  - report.py        → contesto_avvio usa soglia_alert()

Gerarchia soglie (per utensile specifico):
  1. ML alta confidenza  → range_min calcolato dallo storico
  2. ML bassa confidenza → range_min con margine di sicurezza +5%
  3. Nessun dato ML      → SOGLIA_DEFAULT (20%)

Algoritmo progressivo basato su dati storici:
  - 0-9  campioni → nessun output ML
  - 10-29 campioni → suggerimento con confidenza BASSA
  - 30+   campioni → suggerimento con confidenza ALTA

  vita_ottimale = percentile_80(vita_effettiva_campioni)
"""

import math
from datetime import datetime
from typing import Optional

# ── Soglie di sistema (fallback quando ML non ha dati) ────────────────────────
SOGLIA_ALERT_DEFAULT   = 20   # % — alert Telegram e contesto_avvio
SOGLIA_FIN_VITA_DEFAULT = 15  # % — badge fin_vita nel setup analisi
SOGLIA_CONTESTO_BASSA  = 20   # % — conta utensili_sotto_20 nel contesto avvio
SOGLIA_CONTESTO_MEDIA  = 40   # % — conta utensili_sotto_40 nel contesto avvio

# ── Soglie confidenza ML ──────────────────────────────────────────────────────
MIN_CAMPIONI_BASSA = 10
MIN_CAMPIONI_ALTA  = 30

# ── Cache soglie in memoria (si svuota al riavvio backend) ────────────────────
_cache_soglie: dict = {}   # alias_upper → {soglia_alert, soglia_fin_vita, ts}


def _percentile(data: list, p: float) -> float:
    if not data:
        return 0.0
    s = sorted(data)
    n = len(s)
    idx = (p / 100) * (n - 1)
    lo, hi = int(idx), min(int(idx) + 1, n - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def _media(data: list) -> float:
    return sum(data) / len(data) if data else 0.0


def _std(data: list) -> float:
    if len(data) < 2:
        return 0.0
    m = _media(data)
    return math.sqrt(sum((x - m) ** 2 for x in data) / (len(data) - 1))


def calcola_vita_ottimale(
    alias: str,
    records: list,
    commessa: Optional[str] = None,
) -> Optional[dict]:
    """
    Calcola la vita ottimale per un utensile basandosi sullo storico classificato.
    Ritorna None se dati insufficienti (< MIN_CAMPIONI_BASSA).
    """
    alias_up = alias.upper().strip()
    campioni_vita = []

    for r in records:
        if (r.get("alias") or "").upper().strip() != alias_up:
            continue
        tipo       = r.get("tipo", "")
        vita_prima = r.get("vita_prima")
        vita_dopo  = r.get("vita_dopo")
        causa      = r.get("causa")

        if tipo == "sostituito" and vita_prima is not None:
            if causa == "rottura":
                campioni_vita.append(("rottura", float(vita_prima)))
            else:
                campioni_vita.append(("usura", float(vita_prima)))
        elif tipo == "allungamento_vita" and vita_prima is not None and vita_dopo is not None:
            campioni_vita.append(("allungamento", float(vita_dopo)))

    if not campioni_vita:
        return None

    n_totale  = len(campioni_vita)
    n_rotture = sum(1 for t, _ in campioni_vita if t == "rottura")
    n_normali = sum(1 for t, _ in campioni_vita if t in ("usura", "allungamento"))

    if n_totale < MIN_CAMPIONI_BASSA:
        return None

    confidenza = "alta" if n_totale >= MIN_CAMPIONI_ALTA else "bassa"

    valori_normali = [v for t, v in campioni_vita if t in ("usura", "allungamento")]
    valori_tutti   = [v for _, v in campioni_vita]

    if valori_normali:
        vita_ott = _percentile(valori_normali, 80)
        media    = _media(valori_normali)
        std      = _std(valori_normali)
    else:
        vita_ott = _percentile(valori_tutti, 80)
        media    = _media(valori_tutti)
        std      = _std(valori_tutti)

    vita_ott  = round(vita_ott, 1)
    media     = round(media, 1)
    range_min = max(5.0,   round(vita_ott - std, 1))
    range_max = min(100.0, round(vita_ott + std, 1))

    # Soglie derivate dal ML
    # soglia_alert: il punto in cui avvisare l'operatore
    #   Alta confidenza  → range_min (statisticamente affidabile)
    #   Bassa confidenza → range_min + 5% (margine di sicurezza)
    margine = 0 if confidenza == "alta" else 5.0
    soglia_alert    = round(min(range_min + margine, vita_ott), 1)
    soglia_fin_vita = round(max(range_min - 5.0, 5.0), 1)  # soglia critica

    if vita_ott >= 90:
        msg = f"Il Sinumerik è già impostato in modo ottimale — l'utensile dura fino al {vita_ott:.0f}%."
    elif vita_ott >= 70:
        msg = f"Considera di impostare la vita a {vita_ott:.0f}% invece di 100% — eviti sprechi senza rischi."
    else:
        msg = (
            f"Questo utensile viene tipicamente sostituito intorno al {vita_ott:.0f}%. "
            f"Impostare la vita a {vita_ott:.0f}% nel Sinumerik ottimizza i cambi utensile."
        )

    pct_rotture = round(n_rotture / n_totale * 100) if n_totale else 0

    return {
        "alias":           alias,
        "vita_ottimale":   vita_ott,
        "range_min":       range_min,
        "range_max":       range_max,
        "soglia_alert":    soglia_alert,    # ← NUOVO: soglia alert derivata ML
        "soglia_fin_vita": soglia_fin_vita, # ← NUOVO: soglia critica derivata ML
        "media":           media,
        "n_campioni":      n_totale,
        "n_normali":       n_normali,
        "n_rotture":       n_rotture,
        "pct_rotture":     pct_rotture,
        "confidenza":      confidenza,
        "messaggio":       msg,
        "calcolato_ts":    datetime.now().isoformat(timespec="seconds"),
    }


def soglia_alert(alias: str, records: list) -> float:
    """
    Ritorna la soglia di alert per questo utensile.
    Se ML ha dati sufficienti → soglia derivata dallo storico.
    Altrimenti → SOGLIA_ALERT_DEFAULT (20%).
    
    Usato da: check_low_life_alert, contesto_avvio
    """
    alias_up = alias.upper().strip()
    cached = _cache_soglie.get(alias_up)
    if cached:
        return cached["soglia_alert"]

    ris = calcola_vita_ottimale(alias, records)
    if ris:
        _cache_soglie[alias_up] = ris
        return ris["soglia_alert"]
    return float(SOGLIA_ALERT_DEFAULT)


def soglia_fin_vita(alias: str, records: list) -> float:
    """
    Ritorna la soglia critica (fin_vita) per questo utensile.
    Se ML ha dati sufficienti → soglia derivata dallo storico.
    Altrimenti → SOGLIA_FIN_VITA_DEFAULT (15%).
    
    Usato da: classify_tool_state, analisi setup, macchina_live allerta
    """
    alias_up = alias.upper().strip()
    cached = _cache_soglie.get(alias_up)
    if cached:
        return cached["soglia_fin_vita"]

    ris = calcola_vita_ottimale(alias, records)
    if ris:
        _cache_soglie[alias_up] = ris
        return ris["soglia_fin_vita"]
    return float(SOGLIA_FIN_VITA_DEFAULT)


def invalida_cache(alias: Optional[str] = None):
    """
    Invalida la cache soglie. Chiamare dopo ogni nuova classificazione.
    Se alias è None, svuota tutta la cache.
    """
    global _cache_soglie
    if alias is None:
        _cache_soglie = {}
    else:
        _cache_soglie.pop(alias.upper().strip(), None)


def suggerimenti_magazine(records: list) -> list:
    """Calcola suggerimenti vita ottimale per tutti gli utensili con dati."""
    aliases = {(r.get("alias") or "").upper().strip() for r in records if r.get("alias")}
    risultati = [r for a in aliases if (r := calcola_vita_ottimale(a, records))]
    return sorted(risultati, key=lambda x: x["n_campioni"], reverse=True)
