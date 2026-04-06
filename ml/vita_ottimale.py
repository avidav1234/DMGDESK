"""
ml/vita_ottimale.py
Suggerisce la vita ottimale da impostare per un utensile nel Sinumerik.

Algoritmo progressivo basato su dati storici:
  - 0-9  campioni → nessun output
  - 10-29 campioni → suggerimento con confidenza BASSA
  - 30+   campioni → suggerimento con confidenza ALTA

Fonti dati usate:
  1. tool_replacements.json — sostituzioni (vita al momento del cambio)
  2. tool_replacements.json — allungamenti vita (vita_prima → vita_dopo)
  3. lavorazioni_log.json  — sessioni con contesto_avvio (futuro)

Logica:
  Per ogni utensile calcola la "vita reale di consumo" — il punto percentuale
  a cui è stato effettivamente sostituito o allungato. Questo è il dato chiave:
  se un operatore allungava sistematicamente un utensile da 20% a 60%, significa
  che il contatore Sinumerik era troppo aggressivo e la vita reale è maggiore.

  vita_ottimale = percentile_80(vita_effettiva_campioni)
  → Il Sinumerik dovrebbe essere impostato a questo valore, non a 100%.
"""

import math
from datetime import datetime
from typing import Optional

# Soglie confidenza
MIN_CAMPIONI_BASSA  = 10
MIN_CAMPIONI_ALTA   = 30


def _percentile(data: list[float], p: float) -> float:
    """Percentile semplice senza numpy."""
    if not data:
        return 0.0
    s = sorted(data)
    n = len(s)
    idx = (p / 100) * (n - 1)
    lo, hi = int(idx), min(int(idx) + 1, n - 1)
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def _media(data: list[float]) -> float:
    return sum(data) / len(data) if data else 0.0


def _std(data: list[float]) -> float:
    if len(data) < 2:
        return 0.0
    m = _media(data)
    return math.sqrt(sum((x - m) ** 2 for x in data) / (len(data) - 1))


def calcola_vita_ottimale(
    alias: str,
    records: list[dict],
    commessa: Optional[str] = None,
) -> Optional[dict]:
    """
    Calcola la vita ottimale per un utensile basandosi sullo storico.

    Args:
        alias:    nome utensile (case-insensitive)
        records:  lista record da tool_replacements.json
        commessa: se fornita, filtra per commessa (futuro — quando avremo abbastanza dati)

    Returns:
        dict con suggerimento oppure None se dati insufficienti
    """
    alias_up = alias.upper().strip()

    # ── Filtra record rilevanti per questo utensile ────────────────────────
    campioni_vita = []   # vita al momento della sostituzione/allungamento

    for r in records:
        if (r.get("alias") or "").upper().strip() != alias_up:
            continue

        tipo       = r.get("tipo", "")
        vita_prima = r.get("vita_prima")
        vita_dopo  = r.get("vita_dopo")
        causa      = r.get("causa")

        if tipo == "sostituito" and vita_prima is not None:
            # Vita al momento della sostituzione = quanto consumava prima del cambio
            # Se causa = rottura, la vita_prima non è rappresentativa della vita reale
            # (l'utensile si è rotto prima del previsto) — la includiamo ma con peso minore
            if causa == "rottura":
                # Rottura = outlier basso — includi ma tienilo separato
                campioni_vita.append(("rottura", float(vita_prima)))
            else:
                # Usura normale — campione affidabile
                campioni_vita.append(("usura", float(vita_prima)))

        elif tipo == "allungamento_vita" and vita_prima is not None and vita_dopo is not None:
            # L'operatore ha allungato da vita_prima a vita_dopo
            # Questo ci dice che vita_prima era troppo bassa → vita_dopo è più corretta
            campioni_vita.append(("allungamento", float(vita_dopo)))

    if not campioni_vita:
        return None

    n_totale   = len(campioni_vita)
    n_rotture  = sum(1 for t, _ in campioni_vita if t == "rottura")
    n_normali  = sum(1 for t, _ in campioni_vita if t in ("usura", "allungamento"))

    # Confidenza
    if n_totale < MIN_CAMPIONI_BASSA:
        return None   # troppo pochi dati
    elif n_totale < MIN_CAMPIONI_ALTA:
        confidenza = "bassa"
    else:
        confidenza = "alta"

    # Calcolo vita ottimale
    # Usa solo campioni normali (non rotture) per la stima principale
    valori_normali = [v for t, v in campioni_vita if t in ("usura", "allungamento")]
    valori_tutti   = [v for _, v in campioni_vita]

    if valori_normali:
        # Percentile 80 dei campioni normali = vita sicura senza sprechi
        vita_ott = _percentile(valori_normali, 80)
        media    = _media(valori_normali)
        std      = _std(valori_normali)
    else:
        vita_ott = _percentile(valori_tutti, 80)
        media    = _media(valori_tutti)
        std      = _std(valori_tutti)

    vita_ott = round(vita_ott, 1)
    media    = round(media, 1)

    # Range sicuro (± std, clampato 5-100)
    range_min = max(5.0,   round(vita_ott - std, 1))
    range_max = min(100.0, round(vita_ott + std, 1))

    # Messaggio
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
        "media":           media,
        "n_campioni":      n_totale,
        "n_normali":       n_normali,
        "n_rotture":       n_rotture,
        "pct_rotture":     pct_rotture,
        "confidenza":      confidenza,
        "messaggio":       msg,
        "calcolato_ts":    datetime.now().isoformat(timespec="seconds"),
    }


def suggerimenti_magazine(records: list[dict]) -> list[dict]:
    """
    Calcola suggerimenti vita ottimale per tutti gli utensili con abbastanza dati.
    Ritorna lista ordinata per numero campioni decrescente.
    """
    # Trova tutti gli alias unici
    aliases = set()
    for r in records:
        a = (r.get("alias") or "").strip()
        if a:
            aliases.add(a.upper())

    risultati = []
    for alias in aliases:
        ris = calcola_vita_ottimale(alias, records)
        if ris:
            risultati.append(ris)

    return sorted(risultati, key=lambda x: x["n_campioni"], reverse=True)
