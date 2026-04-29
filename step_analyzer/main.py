"""
STEP Analyzer — microservizio separato porta 8002
Estrae features geometriche da file STEP e calcola similarità tra commesse.
"""

import math, json, time, hashlib, logging, asyncio, tempfile
from pathlib import Path
from datetime import datetime
from typing import Optional

from fastapi import FastAPI, HTTPException, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

logging.basicConfig(level=logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s")
log = logging.getLogger("step_analyzer")

app = FastAPI(title="STEP Analyzer", version="1.0")
app.add_middleware(CORSMiddleware, allow_origins=["*"],
    allow_methods=["*"], allow_headers=["*"])

FEATURES_FILE = Path("step_features.json")

def _load_features() -> dict:
    if FEATURES_FILE.exists():
        try: return json.loads(FEATURES_FILE.read_text(encoding="utf-8"))
        except Exception: pass
    return {}

def _save_features(data: dict):
    FEATURES_FILE.write_text(json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")


def estrai_features(path: str) -> dict:
    """Sincrona — chiamare sempre con run_in_executor."""
    import cadquery as cq
    from OCP.BRepAdaptor import BRepAdaptor_Surface
    from OCP.GeomAbs import GeomAbs_Cylinder, GeomAbs_Plane, GeomAbs_Cone, GeomAbs_Sphere

    t0 = time.time()
    shape = cq.importers.importStep(path).val()
    elapsed = round(time.time() - t0, 2)

    bb  = shape.BoundingBox()
    dx  = bb.xmax - bb.xmin
    dy  = bb.ymax - bb.ymin
    dz  = bb.zmax - bb.zmin
    bb_vol = dx * dy * dz
    vol    = shape.Volume()
    area   = shape.Area()
    max_d  = max(dx, dy, dz) or 1

    tipi = {GeomAbs_Plane:0, GeomAbs_Cylinder:0, GeomAbs_Cone:0, GeomAbs_Sphere:0}
    for f in shape.Faces():
        t = BRepAdaptor_Surface(f.wrapped).GetType()
        if t in tipi: tipi[t] += 1

    n_facce = len(shape.Faces())
    return {
        "bb_x": round(dx,2), "bb_y": round(dy,2), "bb_z": round(dz,2),
        "bb_volume": round(bb_vol,2), "volume": round(vol,2), "area": round(area,2),
        "compattezza":       round(vol/bb_vol,5) if bb_vol>0 else 0,
        "sfericita":         round((math.pi**(1/3)*(6*vol)**(2/3))/area,5) if area>0 else 0,
        "rapporto_area_vol": round(area/vol,5) if vol>0 else 0,
        "n_facce": n_facce, "n_spigoli": len(shape.Edges()), "n_vertici": len(shape.Vertices()),
        "n_piani": tipi[GeomAbs_Plane], "n_cilindri": tipi[GeomAbs_Cylinder],
        "n_conici": tipi[GeomAbs_Cone], "n_sferici": tipi[GeomAbs_Sphere],
        "ratio_cilindri_facce": round(tipi[GeomAbs_Cylinder]/n_facce,4) if n_facce else 0,
        "ratio_piani_facce":    round(tipi[GeomAbs_Plane]/n_facce,4) if n_facce else 0,
        "dim_x_norm": round(dx/max_d,4), "dim_y_norm": round(dy/max_d,4), "dim_z_norm": round(dz/max_d,4),
        "_elapsed_sec": elapsed,
    }


def similarita(f1: dict, f2: dict) -> float:
    def diff(a, b, s=1.0):
        med = (abs(a)+abs(b))/2
        return 0.0 if med<1e-9 else min(abs(a-b)/(med*s),1.0)
    g1 = [diff(f1["dim_x_norm"],f2["dim_x_norm"],.5), diff(f1["dim_y_norm"],f2["dim_y_norm"],.5),
          diff(f1["compattezza"],f2["compattezza"],.5), diff(f1["sfericita"],f2["sfericita"],.5)]
    g2 = [diff(f1["n_facce"],f2["n_facce"],2.), diff(f1["n_cilindri"],f2["n_cilindri"],2.),
          diff(f1["ratio_cilindri_facce"],f2["ratio_cilindri_facce"],1.),
          diff(f1["ratio_piani_facce"],f2["ratio_piani_facce"],1.), diff(f1["n_conici"],f2["n_conici"],3.)]
    g3 = [diff(f1["volume"],f2["volume"],3.), diff(f1["rapporto_area_vol"],f2["rapporto_area_vol"],1.)]
    d = .35*(sum(g1)/len(g1)) + .40*(sum(g2)/len(g2)) + .25*(sum(g3)/len(g3))
    return round((1-d)*100,1)


def _build_record(commessa, filename, file_hash, features, existing,
                  ore_macchina="", lead_time_giorni="", note=""):
    return {
        "commessa":         commessa,
        "path_step":        filename,
        "file_hash":        file_hash,
        "analizzato":       datetime.now().isoformat(timespec="seconds"),
        "features":         features,
        "ore_macchina":     float(ore_macchina) if ore_macchina else existing.get("ore_macchina"),
        "lead_time_giorni": int(lead_time_giorni) if lead_time_giorni else existing.get("lead_time_giorni"),
        "data_inizio":      existing.get("data_inizio"),
        "data_consegna":    existing.get("data_consegna"),
        "note":             note or existing.get("note"),
    }


class AnalizzaRequest(BaseModel):
    commessa: str; path_step: str; note: Optional[str]=None
    ore_macchina: Optional[float]=None; lead_time_giorni: Optional[int]=None
    data_inizio: Optional[str]=None; data_consegna: Optional[str]=None

class AggiornaDatiRequest(BaseModel):
    ore_macchina: Optional[float]=None; lead_time_giorni: Optional[int]=None
    data_inizio: Optional[str]=None; data_consegna: Optional[str]=None; note: Optional[str]=None


@app.get("/stato")
def stato():
    db = _load_features()
    return {"ok":True,"n_commesse":len(db),"features_file":str(FEATURES_FILE.absolute())}


@app.post("/analizza")
async def analizza(req: AnalizzaRequest):
    p = Path(req.path_step)
    if not p.exists(): raise HTTPException(404, f"File non trovato: {req.path_step}")
    file_hash = hashlib.md5(p.read_bytes()).hexdigest()
    db = _load_features()
    existing = db.get(req.commessa, {})
    if existing.get("file_hash")==file_hash and existing.get("features"):
        features, cached = existing["features"], True
    else:
        log.info(f"Analisi STEP: {req.commessa}")
        features = await asyncio.get_event_loop().run_in_executor(None, estrai_features, str(p))
        cached = False
    db[req.commessa] = _build_record(req.commessa, str(p), file_hash, features, existing,
        req.ore_macchina or "", req.lead_time_giorni or "", req.note or "")
    _save_features(db)
    return {"ok":True,"commessa":req.commessa,"features":features,"cached":cached}


@app.post("/analizza-upload")
async def analizza_upload(
    file: UploadFile = File(...),
    commessa: str = Form(...),
    ore_macchina: str = Form(""),
    lead_time_giorni: str = Form(""),
    note: str = Form(""),
):
    content = await file.read()
    file_hash = hashlib.md5(content).hexdigest()
    db = _load_features()
    existing = db.get(commessa, {})

    if existing.get("file_hash")==file_hash and existing.get("features"):
        features, cached = existing["features"], True
        log.info(f"Cache hit: {commessa}")
    else:
        suffix = Path(file.filename).suffix or ".stp"
        tmp = Path(tempfile.mktemp(suffix=suffix))
        tmp.write_bytes(content)
        try:
            log.info(f"Analisi STEP upload: {commessa} — {file.filename} ({len(content)//1024}KB)")
            features = await asyncio.get_event_loop().run_in_executor(None, estrai_features, str(tmp))
            cached = False
        finally:
            if tmp.exists(): tmp.unlink()

    db[commessa] = _build_record(commessa, file.filename, file_hash, features, existing,
        ore_macchina, lead_time_giorni, note)
    _save_features(db)
    return {"ok":True,"commessa":commessa,"features":features,"cached":cached}


@app.patch("/commessa/{commessa}")
def aggiorna_dati(commessa: str, req: AggiornaDatiRequest):
    db = _load_features()
    if commessa not in db: raise HTTPException(404, f"Commessa {commessa} non trovata")
    rec = db[commessa]
    if req.ore_macchina is not None:     rec["ore_macchina"] = req.ore_macchina
    if req.lead_time_giorni is not None: rec["lead_time_giorni"] = req.lead_time_giorni
    if req.data_inizio is not None:      rec["data_inizio"] = req.data_inizio
    if req.data_consegna is not None:    rec["data_consegna"] = req.data_consegna
    if req.note is not None:             rec["note"] = req.note
    _save_features(db)
    return {"ok":True}


@app.get("/simili/{commessa}")
def simili(commessa: str, top: int=5, soglia: float=80.0):
    # Soglia 80%: sotto questa percentuale i pezzi sono troppo diversi
    # geometricamente per essere usati come riferimento di tempo lavorazione.
    # Mostrare match al 60-70% creava aspettative sbagliate (pezzi solo
    # vagamente simili presentati come "modello simile").
    db = _load_features()
    if commessa not in db:
        return {"commessa_ref": commessa, "n_totale": 0, "simili": [], "non_in_storico": True}
    feat_ref = db[commessa]["features"]
    risultati = []
    for nome, rec in db.items():
        if nome==commessa: continue
        feat_other = rec.get("features")
        if not feat_other: continue
        sim = similarita(feat_ref, feat_other)
        if sim>=soglia:
            risultati.append({"commessa":nome,"similarita_pct":sim,
                "ore_macchina":rec.get("ore_macchina"),"lead_time_giorni":rec.get("lead_time_giorni"),
                "data_inizio":rec.get("data_inizio"),"data_consegna":rec.get("data_consegna"),
                "n_facce":feat_other.get("n_facce"),"n_cilindri":feat_other.get("n_cilindri"),
                "note":rec.get("note")})
    risultati.sort(key=lambda x: -x["similarita_pct"])
    return {"commessa_ref":commessa,"n_totale":len(risultati),"simili":risultati[:top]}


@app.get("/storico")
def storico():
    db = _load_features()
    return {"ok":True,"n":len(db),"commesse":[
        {"commessa":k,"analizzato":v.get("analizzato"),"ore_macchina":v.get("ore_macchina"),
         "lead_time_giorni":v.get("lead_time_giorni"),"n_facce":v.get("features",{}).get("n_facce"),
         "n_cilindri":v.get("features",{}).get("n_cilindri"),"compattezza":v.get("features",{}).get("compattezza")}
        for k,v in db.items()]}
