"""
logic/cam_classificatore.py
============================
Motore di classificazione percorsi NC — Fase 3 iniziativa classificazione.

Architettura IBRIDA (decisione 2026-07-11, vedi REGOLE_CLASSIFICAZIONE_PERCORSI.md):

  1. TABELLA decisionale (stile PLC, prima riga che matcha): condizioni SOLO
     su famiglia utensile + offset — il 64% della fiducia dell'esperto.
     Ogni riga → esito {operazione, tolleranza, presidio} + probabilità base.
  2. CONFERME (pesi dettati): commento operazione, nome P.U., strategia,
     fz, tolleranza superfici — aggiustano la CONFIDENZA, mai la classe.
  3. CONFLITTO: una conferma fortemente discorde declassa a DA_VERIFICARE
     (mai una scelta silenziosa). Nessuna riga → DA_CLASSIFICARE.

Le regole vivono in config/regole_classificazione.json (dati, non codice).
LOGICA PURA: nessun I/O oltre al caricamento del file regole.

Esiti possibili:
  - "classificato"     riga matchata, conferme concordi/neutre
  - "da_verificare"    riga matchata MA conferma fortemente discorde ⚠
  - "da_classificare"  nessuna riga applicabile (regola non ancora dettata)
"""

import json
from pathlib import Path

_REGOLE_PATH = Path(__file__).resolve().parent.parent / "config" / "regole_classificazione.json"
_regole_cache = {"mtime": None, "dati": None}


def carica_regole(path=None):
    """Carica le regole (cache su mtime: modificare il JSON basta e avanza)."""
    p = Path(path) if path else _REGOLE_PATH
    mtime = p.stat().st_mtime
    if _regole_cache["dati"] is None or _regole_cache["mtime"] != mtime or path:
        with open(p, encoding="utf-8") as f:
            dati = json.load(f)
        if path:                      # path esplicito (test): niente cache
            return dati
        _regole_cache.update(mtime=mtime, dati=dati)
    return _regole_cache["dati"]


# ─────────────────────────────────────────────────────────────────────────────
# Famiglia utensile — dal NOME CIMATRON COMPLETO (primo discriminatore dettato)
# ─────────────────────────────────────────────────────────────────────────────

def famiglia_utensile(procedura, regole):
    ut = procedura.get("utensile") or {}
    nome = (ut.get("nome") or "").upper()
    tipo = (ut.get("tipo") or "").upper()
    alias = (ut.get("alias") or "").upper()
    fallback_alias = None
    for regola in regole.get("famiglie_utensile", []):
        for pat in regola.get("match_nome", []) or []:
            if pat.upper() in nome:
                return regola["famiglia"]
        for pat in regola.get("match_tipo", []) or []:
            if pat.upper() == tipo:
                return regola["famiglia"]
        if "match_alias_prefisso" in regola and alias:
            # prefissi ordinati dal più lungo (FFPI prima di FF, PI prima di P)
            for pref, fam in sorted(regola["match_alias_prefisso"].items(),
                                    key=lambda kv: -len(kv[0])):
                if alias.startswith(pref.upper()):
                    fallback_alias = fam
                    break
    return fallback_alias


# ─────────────────────────────────────────────────────────────────────────────
# Tabella: prima riga che matcha
# ─────────────────────────────────────────────────────────────────────────────

def _offset_parete_fondo(procedura):
    """Offset (parete, fondo) con la semantica del modo Base: il combinato
    vale per entrambi (dettatura R1: 'offset parete e piano > 0.1')."""
    off = procedura.get("offset") or {}
    parete, fondo = off.get("parete"), off.get("fondo")
    if parete is None and fondo is None and off.get("parte") is not None:
        return off["parte"], off["parte"]
    return parete, fondo


def _offset_mw_effettivo(procedura):
    """Offset ModuleWorks UNIFICATO, a prescindere dal modo di posa:
    - modo Avanzate → `superfici_mw` (byte 597 del blob ModuleWorks, estrattore v1.3)
    - modo Base     → `parte` (l'offset superfici sta nell'XML2)
    L'esperto ragiona su UN solo offset per le procedure MW (Multi Asse,
    Operazioni Locali, Ripresa Guidata): questo helper lo restituisce."""
    off = procedura.get("offset") or {}
    if off.get("superfici_mw") is not None:
        return off["superfici_mw"]
    return off.get("parte")


import re as _re


def _riga_matcha(riga, procedura, famiglia):
    se = riga.get("se") or {}
    if "famiglia" in se and se["famiglia"] != famiglia:
        return False
    if "strategia_contiene" in se:
        strat = f"{procedura.get('strategia') or ''} {procedura.get('sotto_strategia') or ''}".upper()
        voci = se["strategia_contiene"]
        if isinstance(voci, str):
            voci = [voci]
        if not any(v.upper() in strat for v in voci):
            return False
    if "pu_contiene" in se:
        if se["pu_contiene"].upper() not in (procedura.get("pu") or "").upper():
            return False
    if "testo_regex" in se:
        testo = f"{procedura.get('commento') or ''} {procedura.get('pu') or ''}"
        if not _re.search(se["testo_regex"], testo, _re.IGNORECASE):
            return False
    parete, fondo = _offset_parete_fondo(procedura)
    off = procedura.get("offset") or {}
    contorno = off.get("contorno")
    # "min" = strettamente maggiore (dettatura R1: offset "maggiore di 0.1")
    if "offset_parete_min" in se:
        if parete is None or parete <= se["offset_parete_min"] + 1e-9:
            return False
    if "offset_fondo_min" in se:
        if fondo is None or fondo <= se["offset_fondo_min"] + 1e-9:
            return False
    if "offset_parete_tra" in se:
        lo, hi = se["offset_parete_tra"]
        if parete is None or not (lo - 1e-9 <= parete <= hi + 1e-9):
            return False
    if "offset_fondo_uguale" in se:
        if fondo is None or abs(fondo - se["offset_fondo_uguale"]) > 1e-9:
            return False
    if "offset_fondo_tra" in se:
        lo, hi = se["offset_fondo_tra"]
        if fondo is None or not (lo - 1e-9 <= fondo <= hi + 1e-9):
            return False
    if se.get("offset_fondo_assente"):
        # fondo NON scritto (≠ fondo 0): distingue prefinitura piano (#4 round2,
        # solo parete) dalla finitura piano R2 (parete + fondo esplicito a 0)
        if (procedura.get("offset") or {}).get("fondo") is not None:
            return False
    if "offset_contorno_tra" in se:
        lo, hi = se["offset_contorno_tra"]
        if contorno is None or not (lo - 1e-9 <= contorno <= hi + 1e-9):
            return False
    if "offset_contorno_max" in se:      # contorno <= soglia (negativi "forti")
        if contorno is None or contorno > se["offset_contorno_max"] + 1e-9:
            return False
    if "offset_mw_tra" in se:            # offset superfici MW unificato (Avanzate: byte 597; Base: parte)
        mw = _offset_mw_effettivo(procedura)
        lo, hi = se["offset_mw_tra"]
        if mw is None or not (lo - 1e-9 <= mw <= hi + 1e-9):
            return False
    if "offset_mw_min" in se:            # offset MW strettamente maggiore (sgrossatura: > 0.1)
        mw = _offset_mw_effettivo(procedura)
        if mw is None or mw <= se["offset_mw_min"] + 1e-9:
            return False
    return True


# ─────────────────────────────────────────────────────────────────────────────
# Conferme: concordi (+peso), discordi (-peso), assenti (0)
# ─────────────────────────────────────────────────────────────────────────────

def _match_keywords(testo, keywords_per_op, operazione):
    """(+1 concorde, -1 discorde, 0 assente/neutro) su un testo libero.
    Discorde solo se matcha keyword di UN'ALTRA operazione e non della propria
    (i vocabolari si sovrappongono: 'fin piani' contiene 'fin')."""
    t = (testo or "").lower()
    if not t.strip():
        return 0, None
    proprie = keywords_per_op.get(operazione, [])
    if any(k in t for k in proprie):
        return 1, None
    for op, kws in keywords_per_op.items():
        if op == operazione:
            continue
        for k in kws:
            if k in t:
                return -1, op
    return 0, None


def _in_range(valore, rng):
    if valore is None or not rng:
        return None
    lo, hi = rng
    return lo <= valore <= hi


def _valuta_conferme(procedura, operazione, regole):
    cfg = regole.get("conferme", {})
    esiti = []

    def keyword_conferma(tipo, testo):
        c = cfg.get(tipo) or {}
        segno, contro = _match_keywords(testo, c.get("keywords", {}), operazione)
        if segno:
            esiti.append({"tipo": tipo, "delta": segno * c.get("peso", 0),
                          "contro": contro})

    keyword_conferma("commento_operazione", procedura.get("commento"))
    keyword_conferma("commento_pu", procedura.get("pu"))
    keyword_conferma("strategia",
                     f"{procedura.get('strategia') or ''} {procedura.get('sotto_strategia') or ''}")

    for tipo, campo in (("fz", (procedura.get("macchina") or {}).get("fz")),
                        ("tolleranza_superfici",
                         (procedura.get("tolleranze") or {}).get("superfici"))):
        c = cfg.get(tipo) or {}
        rng = (c.get("range") or {}).get(operazione)
        dentro = _in_range(campo, rng)
        if dentro is True:
            esiti.append({"tipo": tipo, "delta": c.get("peso", 0), "contro": None})
        elif dentro is False:
            esiti.append({"tipo": tipo, "delta": -c.get("peso", 0), "contro": None})
    return esiti


# ─────────────────────────────────────────────────────────────────────────────
# Classificazione di una procedura
# ─────────────────────────────────────────────────────────────────────────────

def classifica_procedura(procedura, regole=None):
    regole = regole or carica_regole()

    # Elementi STRUTTURA del documento (Parte Finale, Parte Staffaggio,
    # Grezzo x Mesh, Grezzo Statico...): nessun utensile → non sono
    # lavorazioni, escluse dalla classificazione.
    ut = procedura.get("utensile") or {}
    if not (ut.get("nome") or ut.get("alias")):
        return {"numero": procedura.get("numero"), "nome": procedura.get("nome"),
                "famiglia_utensile": None, "esito": "struttura", "riga": None,
                "operazione": None, "tolleranza": None, "presidio": None,
                "confidenza": None, "conferme": [],
                "motivo": "elemento struttura documento (nessun utensile)"}

    famiglia = famiglia_utensile(procedura, regole)

    riga_match = None
    for riga in regole.get("tabella", []):
        if "esito" not in riga:        # righe di sola documentazione (_commento_*)
            continue
        if _riga_matcha(riga, procedura, famiglia):
            riga_match = riga
            break

    base = {"numero": procedura.get("numero"), "nome": procedura.get("nome"),
            "famiglia_utensile": famiglia}

    if riga_match is None:
        return {**base, "esito": "da_classificare", "riga": None,
                "operazione": None, "tolleranza": None, "presidio": None,
                "confidenza": None, "conferme": [],
                "motivo": f"nessuna regola dettata per famiglia={famiglia}, "
                          f"offset={procedura.get('offset')}"}

    esito_riga = dict(riga_match["esito"])
    operazione = esito_riga["operazione"]

    # specializzazione da testo (es. R2: 'chiusur' → FINITURA_CHIUSURE)
    spec = riga_match.get("specializza_se_testo") or {}
    testo = f"{procedura.get('commento') or ''} {procedura.get('pu') or ''}".lower()
    for chiave, override in spec.items():
        if chiave in testo:
            esito_riga.update(override)
            operazione = esito_riga["operazione"]
            break

    # zone non critiche (dettatura round2: es. 'CULO' nel P.U. = niente
    # tolleranze precise, né in sgrossatura né in finitura)
    zona_nc = None
    zone = (regole.get("zone_non_critiche") or {}).get("pu_contiene", [])
    pu_up = (procedura.get("pu") or "").upper()
    for z in zone:
        if z.upper() in pu_up:
            esito_riga["tolleranza"] = "OFF"
            zona_nc = z
            break

    conferme = _valuta_conferme(procedura, operazione, regole)
    soglia = (regole.get("conflitto") or {}).get("soglia_discordanza_singola", 10)
    discordi_forti = [c for c in conferme if c["delta"] <= -soglia]

    confidenza = riga_match.get("prob", 0.9) * 100 + sum(c["delta"] for c in conferme)
    confidenza = max(0, min(100, round(confidenza)))

    return {**base,
            "esito": "da_verificare" if discordi_forti else "classificato",
            "riga": riga_match["id"],
            "operazione": operazione,
            "tolleranza": esito_riga.get("tolleranza"),
            "presidio": esito_riga.get("presidio"),
            "confidenza": confidenza,
            "conferme": conferme,
            "zona_non_critica": zona_nc,
            "motivo": ("; ".join(
                f"{c['tipo']} discorde" + (f" (indica {c['contro']})" if c.get("contro") else "")
                for c in discordi_forti) if discordi_forti else
                (f"tolleranza OFF: zona non critica '{zona_nc}' nel P.U." if zona_nc else None))}


def classifica_estrazione(estrazione, regole=None):
    """Classifica tutte le procedure di un'estrazione. Ritorna lista + stats."""
    regole = regole or carica_regole()
    risultati = [classifica_procedura(p, regole)
                 for p in estrazione.get("procedure", [])]
    stats = {"totale": len(risultati),
             "classificati": sum(1 for r in risultati if r["esito"] == "classificato"),
             "da_verificare": sum(1 for r in risultati if r["esito"] == "da_verificare"),
             "da_classificare": sum(1 for r in risultati if r["esito"] == "da_classificare"),
             "struttura": sum(1 for r in risultati if r["esito"] == "struttura")}
    per_op = {}
    for r in risultati:
        if r["operazione"]:
            per_op[r["operazione"]] = per_op.get(r["operazione"], 0) + 1
    stats["per_operazione"] = per_op
    return {"procedure": risultati, "stats": stats,
            "regole_versione": regole.get("versione"),
            "regole_stato": regole.get("stato")}
