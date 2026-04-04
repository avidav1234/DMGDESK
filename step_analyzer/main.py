"""
STEP Analyzer — microservizio separato porta 8001
Estrae features geometriche da file STEP e calcola similarità tra commesse.

Endpoints:
  POST /analizza          → estrae features da un file STEP
  GET  /simili/{commessa} → top-N commesse simili dallo storico
  GET  /storico           → lista tutte le commesse con features
  GET  /stato             → stato servizio
"""

import math
import json
import time
import hashlib
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("step_analyzer")

app = FastAPI(title="STEP Analyzer", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"])

# ── Storage features ──────────────────────────────────────────────────────────
FEATURES_FILE = Path("step_features.json")

def _load_features() -> dict:
    if FEATURES_FILE.exists():
        try:
            return json.loads(FEATURES_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {}

def _save_features(data: dict):
    FEATURES_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Estrazione features ───────────────────────────────────────────────────────

def estrai_features(path: str) -> dict:
    """Carica il file STEP ed estrae il vettore di features geometriche."""
    import cadquery as cq
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import (GeomAbs_Cylinder, GeomAbs_Plane,
                              GeomAbs_Cone, GeomAbs_Sphere)

    t0 = time.time()
    result = cq.importers.importStep(path)
    shape  = result.val()
    elapsed = round(time.time() - t0, 2)

    bb  = shape.BoundingBox()
    dx  = bb.xmax - bb.xmin
    dy  = bb.ymax - bb.ymin
    dz  = bb.zmax - bb.zmin
    bb_vol = dx * dy * dz
    vol    = shape.Volume()
    area   = shape.Area()
    max_d  = max(dx, dy, dz) or 1

    tipi = {GeomAbs_Plane: 0, GeomAbs_Cylinder: 0,
            GeomAbs_Cone: 0,  GeomAbs_Sphere: 0}
    for f in shape.Faces():
        t = BRepAdaptor_Surface(f.wrapped).GetType()
        if t in tipi:
            tipi[t] += 1

    n_facce   = len(shape.Faces())
    n_spigoli = len(shape.Edges())
    n_vertici = len(shape.Vertices())

    return {
        # Dimensioni assolute (mm)
        "bb_x": round(dx, 2),
        "bb_y": round(dy, 2),
        "bb_z": round(dz, 2),
        "bb_volume": round(bb_vol, 2),
        "volume": round(vol, 2),
        "area": round(area, 2),
        # Indici adimensionali
        "compattezza":      round(vol / bb_vol, 5) if bb_vol > 0 else 0,
        "sfericita":        round((math.pi**(1/3) * (6*vol)**(2/3)) / area, 5) if area > 0 else 0,
        "rapporto_area_vol":round(area / vol, 5) if vol > 0 else 0,
        # Topologia
        "n_facce":    n_facce,
        "n_spigoli":  n_spigoli,
        "n_vertici":  n_vertici,
        "n_piani":    tipi[GeomAbs_Plane],
        "n_cilindri": tipi[GeomAbs_Cylinder],
        "n_conici":   tipi[GeomAbs_Cone],
        "n_sferici":  tipi[GeomAbs_Sphere],
        # Ratios
        "ratio_cilindri_facce": round(tipi[GeomAbs_Cylinder] / n_facce, 4) if n_facce else 0,
        "ratio_piani_facce":    round(tipi[GeomAbs_Plane] / n_facce, 4) if n_facce else 0,
        # Dimensioni normalizzate (forma)
        "dim_x_norm": round(dx / max_d, 4),
        "dim_y_norm": round(dy / max_d, 4),
        "dim_z_norm": round(dz / max_d, 4),
        # Meta
        "_elapsed_sec": elapsed,
    }


# ── Similarità ────────────────────────────────────────────────────────────────

def similarita(f1: dict, f2: dict) -> float:
    """
    Similarità pesata 0-100%.
    Gruppo 1 (35%): forma — rapporti dimensionali, compattezza
    Gruppo 2 (40%): complessità topologica — facce, fori, conici
    Gruppo 3 (25%): volumi/aree
    """
    def diff(a, b, scala=1.0):
        med = (abs(a) + abs(b)) / 2
        if med < 1e-9:
            return 0.0
        return min(abs(a - b) / (med * scala), 1.0)

    g1 = [
        diff(f1["dim_x_norm"],        f2["dim_x_norm"],        0.5),
        diff(f1["dim_y_norm"],        f2["dim_y_norm"],        0.5),
        diff(f1["compattezza"],       f2["compattezza"],       0.5),
        diff(f1["sfericita"],         f2["sfericita"],         0.5),
    ]
    g2 = [
        diff(f1["n_facce"],              f2["n_facce"],              2.0),
        diff(f1["n_cilindri"],           f2["n_cilindri"],           2.0),
        diff(f1["ratio_cilindri_facce"], f2["ratio_cilindri_facce"], 1.0),
        diff(f1["ratio_piani_facce"],    f2["ratio_piani_facce"],    1.0),
        diff(f1["n_conici"],             f2["n_conici"],             3.0),
    ]
    g3 = [
        diff(f1["volume"],            f2["volume"],            3.0),
        diff(f1["rapporto_area_vol"], f2["rapporto_area_vol"], 1.0),
    ]

    d = 0.35 * (sum(g1)/len(g1)) + 0.40 * (sum(g2)/len(g2)) + 0.25 * (sum(g3)/len(g3))
    return round((1 - d) * 100, 1)


# ── Models ────────────────────────────────────────────────────────────────────

class AnalizzaRequest(BaseModel):
    commessa:  str           # es. "4298_0005"
    path_step: str           # path assoluto sul server, es. "P:/..."
    note:      Optional[str] = None
    # Dati lavorazione (opzionali — aggiornabili dopo)
    ore_macchina: Optional[float] = None
    lead_time_giorni: Optional[int] = None
    data_inizio: Optional[str] = None
    data_consegna: Optional[str] = None

class AggiornaDatiRequest(BaseModel):
    ore_macchina:     Optional[float] = None
    lead_time_giorni: Optional[int] = None
    data_inizio:      Optional[str] = None
    data_consegna:    Optional[str] = None
    note:             Optional[str] = None


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.get("/stato")
def stato():
    db = _load_features()
    return {
        "ok": True,
        "n_commesse": len(db),
        "features_file": str(FEATURES_FILE.absolute()),
    }


@app.post("/analizza")
def analizza(req: AnalizzaRequest):
    """
    Estrae features geometriche dal file STEP e le salva nello storico.
    Se la commessa esiste già, aggiorna le features (rianalizza).
    """
    p = Path(req.path_step)
    if not p.exists():
        raise HTTPException(404, f"File non trovato: {req.path_step}")

    # Hash del file per cache — se stesso hash → riusa features
    file_hash = hashlib.md5(p.read_bytes()).hexdigest()
    db = _load_features()

    existing = db.get(req.commessa, {})
    if existing.get("file_hash") == file_hash and existing.get("features"):
        log.info(f"Cache hit: {req.commessa} — features già presenti")
        features = existing["features"]
    else:
        log.info(f"Analisi STEP: {req.commessa} — {p.name}")
        features = estrai_features(str(p))
        log.info(f"  → {features['n_facce']} facce, {features['n_cilindri']} cilindri, "
                 f"{features['_elapsed_sec']}s")

    record = {
        "commessa":   req.commessa,
        "path_step":  str(p),
        "file_hash":  file_hash,
        "analizzato": datetime.now().isoformat(timespec="seconds"),
        "features":   features,
        # Dati lavorazione
        "ore_macchina":      req.ore_macchina     or existing.get("ore_macchina"),
        "lead_time_giorni":  req.lead_time_giorni or existing.get("lead_time_giorni"),
        "data_inizio":       req.data_inizio       or existing.get("data_inizio"),
        "data_consegna":     req.data_consegna     or existing.get("data_consegna"),
        "note":              req.note              or existing.get("note"),
    }
    db[req.commessa] = record
    _save_features(db)

    return {
        "ok": True,
        "commessa": req.commessa,
        "features": features,
        "cached": existing.get("file_hash") == file_hash,
    }


@app.patch("/commessa/{commessa}")
def aggiorna_dati(commessa: str, req: AggiornaDatiRequest):
    """Aggiorna i dati di lavorazione senza riestrarre features."""
    db = _load_features()
    if commessa not in db:
        raise HTTPException(404, f"Commessa {commessa} non trovata")
    rec = db[commessa]
    if req.ore_macchina is not None:     rec["ore_macchina"] = req.ore_macchina
    if req.lead_time_giorni is not None: rec["lead_time_giorni"] = req.lead_time_giorni
    if req.data_inizio is not None:      rec["data_inizio"] = req.data_inizio
    if req.data_consegna is not None:    rec["data_consegna"] = req.data_consegna
    if req.note is not None:             rec["note"] = req.note
    _save_features(db)
    return {"ok": True}


@app.get("/simili/{commessa}")
def simili(commessa: str, top: int = 5, soglia: float = 60.0):
    """
    Restituisce le top-N commesse simili a quella indicata.
    Esclude la commessa stessa.
    soglia: similarità minima % (default 60%)
    """
    db = _load_features()
    if commessa not in db:
        raise HTTPException(404, f"Commessa {commessa} non in storico — analizza prima il file STEP")

    feat_ref = db[commessa]["features"]
    risultati = []

    for nome, rec in db.items():
        if nome == commessa:
            continue
        feat_other = rec.get("features")
        if not feat_other:
            continue
        sim = similarita(feat_ref, feat_other)
        if sim >= soglia:
            risultati.append({
                "commessa":         nome,
                "similarita_pct":   sim,
                "ore_macchina":     rec.get("ore_macchina"),
                "lead_time_giorni": rec.get("lead_time_giorni"),
                "data_inizio":      rec.get("data_inizio"),
                "data_consegna":    rec.get("data_consegna"),
                "n_facce":          feat_other.get("n_facce"),
                "n_cilindri":       feat_other.get("n_cilindri"),
                "note":             rec.get("note"),
            })

    risultati.sort(key=lambda x: -x["similarita_pct"])
    return {
        "commessa_ref": commessa,
        "n_totale":     len(risultati),
        "simili":       risultati[:top],
    }


@app.get("/storico")
def storico():
    """Lista tutte le commesse analizzate con features e dati lavorazione."""
    db = _load_features()
    return {
        "ok": True,
        "n": len(db),
        "commesse": [
            {
                "commessa":         k,
                "analizzato":       v.get("analizzato"),
                "ore_macchina":     v.get("ore_macchina"),
                "lead_time_giorni": v.get("lead_time_giorni"),
                "n_facce":          v.get("features", {}).get("n_facce"),
                "n_cilindri":       v.get("features", {}).get("n_cilindri"),
                "compattezza":      v.get("features", {}).get("compattezza"),
            }
            for k, v in db.items()
        ]
    }
