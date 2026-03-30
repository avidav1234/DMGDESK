"""
api/routers/report.py
=====================
Sistema di raccolta e reportistica tempi lavorazione.

Struttura lavorazioni_log.json:
{
  "sessioni": [
    {
      "id": "uuid",
      "data": "2026-03-30",
      "progetto": "4297_0008",
      "pallet": 6,
      "inizio": "2026-03-30T10:16:46",
      "fine": "2026-03-30T14:30:00",
      "durata_sec": 15194,
      "programmi": [
        {
          "filename": "4297_0008_01_023.MPF",
          "commessa": "4297", "posizione": "0008", "fase": "01", "seq": "023",
          "inizio": "2026-03-30T10:16:54",
          "fine": "2026-03-30T10:23:11",
          "durata_sec": 377,
          "utensile": "FFPI42R0.8L114",
          "t_number": 3524
        }
      ],
      "gap_sec": 120,           # tempo fermo tra programmi
      "utensili": {             # accumulo ore per utensile
        "FFPI42R0.8L114": 1240,
        "RENISHAW": 45
      }
    }
  ]
}
"""

import json
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Query
from fastapi.responses import FileResponse
from database.db_handler import carica_configurazione

router = APIRouter()

# ── Helpers percorso ──────────────────────────────────────────────────────────

def _log_path(config: dict) -> Path:
    base = (config.get("tools_toa_folder") or
            config.get("percorso_nc_base") or ".")
    return Path(base) / "lavorazioni_log.json"

def _load_log(config: dict) -> dict:
    p = _log_path(config)
    if p.exists():
        try:
            return json.loads(p.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {"sessioni": [], "stato_corrente": {}}

def _save_log(config: dict, data: dict):
    p = _log_path(config)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

def _now_iso() -> str:
    return datetime.now().isoformat(timespec="seconds")

def _now_str() -> str:
    return datetime.now().strftime("%d/%m/%Y %H:%M")

def _parse_nome(filename: str) -> dict:
    """4297_0008_01_023.MPF → commessa/posizione/fase/seq"""
    n = filename.upper().replace(".MPF", "")
    p = n.split("_")
    return {
        "commessa":  p[0] if len(p) > 0 else n,
        "posizione": p[1] if len(p) > 1 else "",
        "fase":      p[2] if len(p) > 2 else "",
        "seq":       p[3] if len(p) > 3 else "",
    }

def _durata_str(sec: int) -> str:
    if sec is None: return "—"
    h, r = divmod(int(sec), 3600)
    m, s = divmod(r, 60)
    return f"{h:02d}:{m:02d}:{s:02d}"

# ── Aggiornamento da log OpcUa (chiamato da macchina_live) ───────────────────

def aggiorna_da_log(
    programma_attivo: Optional[str],
    stato_pgm: int,
    pallet_num: Optional[int],
    progetto_nome: Optional[str],
    utensile: Optional[str],
    t_number: Optional[str],
    config: dict,
):
    """
    Chiamato da aggiorna-stati-da-log ogni 5 secondi.
    Registra inizio/fine programmi e accumula tempi utensili.
    """
    data = _load_log(config)
    sc   = data.setdefault("stato_corrente", {})
    now  = _now_iso()
    dirty = False

    # ── Macchina FERMA ────────────────────────────────────────────────────────
    if stato_pgm in (0, 5):
        if sc.get("in_esecuzione"):
            # Chiudi sessione corrente
            _chiudi_sessione(data, sc, now)
            sc.clear()
            dirty = True

    # ── Macchina IN ESECUZIONE ────────────────────────────────────────────────
    # Filtra programmi di sistema Sinumerik (non sono lavorazioni utente)
    _FILTRI_SISTEMA = ("_N_CMA_DIR", "_N_CST_DIR", "_N_SYF_DIR",
                       "_N_MPF_DIR", "_SPF", "BPOSAXIS", "TMPCYC")
    if programma_attivo:
        for f in _FILTRI_SISTEMA:
            if f in programma_attivo.upper():
                programma_attivo = None
                break

    elif stato_pgm in (1, 3) and programma_attivo:
        prev_prog = sc.get("programma_corrente")

        # Prima volta o cambio programma
        if prev_prog != programma_attivo:

            # Chiudi programma precedente
            if prev_prog and sc.get("sessione_id"):
                _chiudi_programma(data, sc, now)

            # Avvia nuova sessione se non esiste
            if not sc.get("sessione_id"):
                sess_id = str(uuid.uuid4())[:8]
                sessione = {
                    "id":        sess_id,
                    "data":      now[:10],
                    "progetto":  progetto_nome or "—",
                    "pallet":    pallet_num,
                    "inizio":    now,
                    "fine":      None,
                    "durata_sec": None,
                    "programmi": [],
                    "gap_sec":   0,
                    "utensili":  {},
                }
                data["sessioni"].append(sessione)
                sc["sessione_id"]  = sess_id
                sc["inizio_fermo"] = None

            # Avvia nuovo programma
            sc["programma_corrente"]  = programma_attivo
            sc["inizio_programma"]    = now
            sc["utensile_programma"]  = utensile
            sc["t_number_programma"]  = t_number
            sc["in_esecuzione"]       = True
            sc["ultimo_tick"]         = now
            dirty = True

        else:
            # Stesso programma — accumula tick utensile (5s)
            if sc.get("sessione_id") and utensile:
                sess = _find_sess(data, sc["sessione_id"])
                if sess:
                    sess.setdefault("utensili", {})
                    sess["utensili"][utensile] = sess["utensili"].get(utensile, 0) + 5
                    dirty = True
            sc["ultimo_tick"] = now

    if dirty:
        _save_log(config, data)

def _find_sess(data: dict, sess_id: str) -> Optional[dict]:
    for s in data.get("sessioni", []):
        if s.get("id") == sess_id:
            return s
    return None

def _chiudi_programma(data: dict, sc: dict, now: str):
    sess = _find_sess(data, sc["sessione_id"])
    if not sess:
        return
    inizio = sc.get("inizio_programma")
    if not inizio:
        return
    try:
        durata = int((datetime.fromisoformat(now) -
                      datetime.fromisoformat(inizio)).total_seconds())
    except Exception:
        durata = None

    info = _parse_nome(sc["programma_corrente"])
    sess["programmi"].append({
        "filename":  sc["programma_corrente"],
        **info,
        "inizio":    inizio,
        "fine":      now,
        "durata_sec": durata,
        "utensile":  sc.get("utensile_programma"),
        "t_number":  sc.get("t_number_programma"),
    })

def _chiudi_sessione(data: dict, sc: dict, now: str):
    if not sc.get("sessione_id"):
        return
    _chiudi_programma(data, sc, now)
    sess = _find_sess(data, sc["sessione_id"])
    if not sess:
        return
    inizio = sess.get("inizio")
    if inizio:
        try:
            sess["durata_sec"] = int(
                (datetime.fromisoformat(now) -
                 datetime.fromisoformat(inizio)).total_seconds())
        except Exception:
            pass
    sess["fine"] = now
    # Calcola gap totale (fermo tra programmi)
    programmi = sess.get("programmi", [])
    gap = 0
    for i in range(1, len(programmi)):
        try:
            prev_fine = programmi[i-1]["fine"]
            curr_inizio = programmi[i]["inizio"]
            if prev_fine and curr_inizio:
                g = int((datetime.fromisoformat(curr_inizio) -
                         datetime.fromisoformat(prev_fine)).total_seconds())
                if g > 0:
                    gap += g
        except Exception:
            pass
    sess["gap_sec"] = gap

# ── Endpoint: dati giornalieri ────────────────────────────────────────────────

@router.get("/giornaliero")
async def get_report_giornaliero(data: str = Query(default=None)):
    """
    Restituisce report giornaliero.
    data = YYYY-MM-DD (default: oggi)
    """
    config = carica_configurazione()
    log    = _load_log(config)
    target = data or datetime.now().strftime("%Y-%m-%d")

    sessioni_giorno = [
        s for s in log.get("sessioni", [])
        if s.get("data") == target
    ]

    # Aggregazioni
    ore_totali   = sum(s.get("durata_sec") or 0 for s in sessioni_giorno)
    gap_totale   = sum(s.get("gap_sec") or 0 for s in sessioni_giorno)
    n_programmi  = sum(len(s.get("programmi", [])) for s in sessioni_giorno)

    # Utensili aggregati
    utensili_agg = {}
    for s in sessioni_giorno:
        for ut, sec in (s.get("utensili") or {}).items():
            utensili_agg[ut] = utensili_agg.get(ut, 0) + sec

    # Progetti aggregati
    progetti_agg = {}
    for s in sessioni_giorno:
        prog = s.get("progetto") or "—"
        if prog not in progetti_agg:
            progetti_agg[prog] = {"durata_sec": 0, "n_programmi": 0, "pallet": s.get("pallet")}
        progetti_agg[prog]["durata_sec"] += s.get("durata_sec") or 0
        progetti_agg[prog]["n_programmi"] += len(s.get("programmi", []))

    return {
        "data":          target,
        "ore_lavorate":  _durata_str(ore_totali),
        "ore_lavorate_sec": ore_totali,
        "tempo_fermo_sec": gap_totale,
        "tempo_fermo":   _durata_str(gap_totale),
        "n_sessioni":    len(sessioni_giorno),
        "n_programmi":   n_programmi,
        "efficienza_pct": round(ore_totali / (ore_totali + gap_totale) * 100, 1)
                          if (ore_totali + gap_totale) > 0 else 0,
        "progetti":      progetti_agg,
        "utensili":      {k: {"sec": v, "ore": _durata_str(v)}
                          for k, v in sorted(utensili_agg.items(),
                                             key=lambda x: -x[1])},
        "sessioni":      sessioni_giorno,
    }

@router.get("/storico")
async def get_storico(giorni: int = Query(default=7)):
    """Ultimi N giorni — per grafici trend."""
    config = carica_configurazione()
    log    = _load_log(config)
    result = []
    for i in range(giorni - 1, -1, -1):
        d = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        sess = [s for s in log.get("sessioni", []) if s.get("data") == d]
        ore  = sum(s.get("durata_sec") or 0 for s in sess)
        gap  = sum(s.get("gap_sec") or 0 for s in sess)
        result.append({
            "data": d,
            "ore_lavorate_sec": ore,
            "ore_lavorate": _durata_str(ore),
            "tempo_fermo_sec": gap,
            "n_programmi": sum(len(s.get("programmi", [])) for s in sess),
            "efficienza_pct": round(ore / (ore + gap) * 100, 1) if (ore + gap) > 0 else 0,
        })
    return result

# ── Export Excel ──────────────────────────────────────────────────────────────

@router.get("/export-excel")
async def export_excel(data: str = Query(default=None)):
    """Genera report Excel giornaliero."""
    import openpyxl
    from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
    from openpyxl.utils import get_column_letter

    config = carica_configurazione()
    target = data or datetime.now().strftime("%Y-%m-%d")
    rpt    = (await get_report_giornaliero(target))

    wb = openpyxl.Workbook()

    # ── Colori ────────────────────────────────────────────────────────────────
    BLU_HEADER = "1D5FAD"
    BLU_LIGHT  = "DBEAFE"
    GRIGIO     = "F1F5F9"
    VERDE      = "16A34A"
    ARANCIONE  = "D97706"

    def hdr(ws, row, col, val, bold=True, bg=BLU_HEADER, fg="FFFFFF", size=11):
        c = ws.cell(row=row, column=col, value=val)
        c.font = Font(bold=bold, color=fg, size=size, name="Arial")
        c.fill = PatternFill("solid", start_color=bg)
        c.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        return c

    def cell(ws, row, col, val, bold=False, align="left", fmt=None):
        c = ws.cell(row=row, column=col, value=val)
        c.font = Font(bold=bold, name="Arial", size=10)
        c.alignment = Alignment(horizontal=align, vertical="center")
        if fmt: c.number_format = fmt
        return c

    thin = Border(
        left=Side(style="thin", color="CBD5E1"),
        right=Side(style="thin", color="CBD5E1"),
        top=Side(style="thin", color="CBD5E1"),
        bottom=Side(style="thin", color="CBD5E1"),
    )

    # ════════════════════════════════════════════════════════════════════════
    # Foglio 1 — Riepilogo
    # ════════════════════════════════════════════════════════════════════════
    ws1 = wb.active
    ws1.title = "Riepilogo"
    ws1.sheet_view.showGridLines = False

    # Titolo
    ws1.merge_cells("A1:F1")
    t = ws1.cell(row=1, column=1,
                 value=f"REPORT LAVORAZIONE — {target}")
    t.font = Font(bold=True, size=14, color="FFFFFF", name="Arial")
    t.fill = PatternFill("solid", start_color=BLU_HEADER)
    t.alignment = Alignment(horizontal="center", vertical="center")
    ws1.row_dimensions[1].height = 30

    # KPI box
    kpi = [
        ("Ore lavorate",    rpt["ore_lavorate"]),
        ("Tempo fermo",     rpt["tempo_fermo"]),
        ("Efficienza",      f"{rpt['efficienza_pct']}%"),
        ("N° programmi",    rpt["n_programmi"]),
        ("N° sessioni",     rpt["n_sessioni"]),
    ]
    ws1.row_dimensions[3].height = 15
    for i, (label, val) in enumerate(kpi, 1):
        c = ws1.cell(row=3, column=i, value=label)
        c.font = Font(bold=True, size=9, color="64748B", name="Arial")
        c.alignment = Alignment(horizontal="center")
        c2 = ws1.cell(row=4, column=i, value=val)
        c2.font = Font(bold=True, size=14, name="Arial",
                       color=VERDE if i == 3 else "0D2D5E")
        c2.alignment = Alignment(horizontal="center")
        c2.fill = PatternFill("solid", start_color=BLU_LIGHT)
        c2.border = thin
        ws1.row_dimensions[4].height = 30

    # Sezione Progetti
    r = 7
    ws1.merge_cells(f"A{r}:F{r}")
    hdr(ws1, r, 1, "PROGETTI LAVORATI", bg=BLU_HEADER)
    r += 1
    for col, (lbl, w) in enumerate([
        ("Progetto", 20), ("Pallet", 10), ("Ore lavorate", 16),
        ("N° programmi", 15), ("—", 10), ("—", 10)
    ], 1):
        hdr(ws1, r, col, lbl, bg="334155", size=10)
        ws1.column_dimensions[get_column_letter(col)].width = w
    r += 1
    for prog, info in rpt["progetti"].items():
        fill = PatternFill("solid", start_color=GRIGIO if r % 2 == 0 else "FFFFFF")
        cell(ws1, r, 1, prog, bold=True).fill = fill
        cell(ws1, r, 2, f"P{info['pallet']}" if info.get("pallet") else "—", align="center").fill = fill
        cell(ws1, r, 3, _durata_str(info["durata_sec"]), align="center").fill = fill
        cell(ws1, r, 4, info["n_programmi"], align="center").fill = fill
        for col in [1,2,3,4]:
            ws1.cell(row=r, column=col).border = thin
        r += 1

    # Sezione Utensili
    r += 2
    ws1.merge_cells(f"A{r}:D{r}")
    hdr(ws1, r, 1, "UTILIZZO UTENSILI", bg=BLU_HEADER)
    r += 1
    for col, lbl in enumerate(["Alias utensile", "Ore utilizzo", "% sul totale", "—"], 1):
        hdr(ws1, r, col, lbl, bg="334155", size=10)
    r += 1
    ore_tot = sum(v["sec"] for v in rpt["utensili"].values()) or 1
    for alias, info in rpt["utensili"].items():
        pct = round(info["sec"] / ore_tot * 100, 1)
        fill = PatternFill("solid", start_color=GRIGIO if r % 2 == 0 else "FFFFFF")
        cell(ws1, r, 1, alias, bold=True).fill = fill
        cell(ws1, r, 2, info["ore"], align="center").fill = fill
        cell(ws1, r, 3, f"{pct}%", align="center").fill = fill
        for col in [1,2,3]:
            ws1.cell(row=r, column=col).border = thin
        r += 1

    # ════════════════════════════════════════════════════════════════════════
    # Foglio 2 — Dettaglio programmi
    # ════════════════════════════════════════════════════════════════════════
    ws2 = wb.create_sheet("Dettaglio Programmi")
    ws2.sheet_view.showGridLines = False
    ws2.merge_cells("A1:I1")
    t2 = ws2.cell(row=1, column=1, value=f"DETTAGLIO PROGRAMMI — {target}")
    t2.font = Font(bold=True, size=13, color="FFFFFF", name="Arial")
    t2.fill = PatternFill("solid", start_color=BLU_HEADER)
    t2.alignment = Alignment(horizontal="center", vertical="center")
    ws2.row_dimensions[1].height = 28

    cols2 = [
        ("Progetto", 18), ("Pallet", 8), ("Commessa", 10),
        ("Posizione", 10), ("Fase", 8), ("N°", 8),
        ("Inizio", 18), ("Fine", 18), ("Durata", 12),
        ("Utensile", 20),
    ]
    for i, (lbl, w) in enumerate(cols2, 1):
        hdr(ws2, 2, i, lbl, bg="334155", size=10)
        ws2.column_dimensions[get_column_letter(i)].width = w

    r2 = 3
    for sess in rpt["sessioni"]:
        for pgm in sess.get("programmi", []):
            fill = PatternFill("solid", start_color=GRIGIO if r2 % 2 == 0 else "FFFFFF")
            vals = [
                sess.get("progetto"), f"P{sess.get('pallet','')}" if sess.get("pallet") else "—",
                pgm.get("commessa"), pgm.get("posizione"),
                pgm.get("fase"), pgm.get("seq"),
                pgm.get("inizio","")[:16].replace("T"," "),
                pgm.get("fine","")[:16].replace("T"," ") if pgm.get("fine") else "—",
                _durata_str(pgm.get("durata_sec")),
                pgm.get("utensile") or "—",
            ]
            for col, val in enumerate(vals, 1):
                c = ws2.cell(row=r2, column=col, value=val)
                c.font = Font(name="Arial", size=10)
                c.fill = fill
                c.border = thin
                c.alignment = Alignment(horizontal="center" if col > 2 else "left",
                                        vertical="center")
            r2 += 1

    # ════════════════════════════════════════════════════════════════════════
    # Foglio 3 — Tempi fermo
    # ════════════════════════════════════════════════════════════════════════
    ws3 = wb.create_sheet("Fermi Macchina")
    ws3.sheet_view.showGridLines = False
    ws3.merge_cells("A1:E1")
    t3 = ws3.cell(row=1, column=1, value=f"FERMI MACCHINA — {target}")
    t3.font = Font(bold=True, size=13, color="FFFFFF", name="Arial")
    t3.fill = PatternFill("solid", start_color=ARANCIONE)
    t3.alignment = Alignment(horizontal="center", vertical="center")
    ws3.row_dimensions[1].height = 28

    cols3 = [("Progetto",18),("Prog. prev.",20),("Prog. succ.",20),("Inizio fermo",18),("Durata fermo",14)]
    for i,(lbl,w) in enumerate(cols3,1):
        hdr(ws3, 2, i, lbl, bg="92400E", size=10)
        ws3.column_dimensions[get_column_letter(i)].width = w

    r3 = 3
    for sess in rpt["sessioni"]:
        pgms = sess.get("programmi",[])
        for i in range(1, len(pgms)):
            prev = pgms[i-1]; curr = pgms[i]
            if not (prev.get("fine") and curr.get("inizio")): continue
            try:
                gap = int((datetime.fromisoformat(curr["inizio"]) -
                           datetime.fromisoformat(prev["fine"])).total_seconds())
            except: continue
            if gap < 10: continue
            fill = PatternFill("solid", start_color="FEF3C7" if r3%2==0 else "FFFBEB")
            vals = [
                sess.get("progetto"),
                prev.get("filename",""),
                curr.get("filename",""),
                prev.get("fine","")[:16].replace("T"," "),
                _durata_str(gap),
            ]
            for col, val in enumerate(vals, 1):
                c = ws3.cell(row=r3, column=col, value=val)
                c.font = Font(name="Arial", size=10)
                c.fill = fill; c.border = thin
                c.alignment = Alignment(horizontal="center" if col>2 else "left", vertical="center")
            r3 += 1

    # Salva
    out = Path("/home/claude/report_temp.xlsx")
    wb.save(str(out))
    return out

@router.get("/export-excel-download")
async def export_excel_download(data: str = Query(default=None)):
    target = data or datetime.now().strftime("%Y-%m-%d")
    out    = await export_excel(data)
    fname  = f"report_lavorazione_{target}.xlsx"
    import shutil
    dest = Path(f"/mnt/user-data/outputs/{fname}")
    shutil.copy(str(out), str(dest))
    return FileResponse(str(dest), filename=fname,
                        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
