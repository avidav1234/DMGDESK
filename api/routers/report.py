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
    override_feed: Optional[int] = None,
    override_mandrino: Optional[int] = None,
):
    """
    Chiamato da aggiorna-stati-da-log ogni 5 secondi.
    Registra inizio/fine programmi e accumula tempi utensili.
    Registra anche periodi con override ridotto per diagnostica.
    """
    data = _load_log(config)
    sc   = data.setdefault("stato_corrente", {})
    now  = _now_iso()
    dirty = False

    # ── Sanità: chiudi sessioni orfane da riavvio backend ─────────────────────
    # Se il backend è stato riavviato mentre la macchina girava, la sessione
    # corrente è rimasta aperta (fine=None). Se ora la macchina è ferma,
    # chiudiamo la sessione orfana usando l'ultimo_tick come timestamp di fine.
    if stato_pgm in (0, 5) and sc.get("sessione_id"):
        sess_orfana = _find_sess(data, sc["sessione_id"])
        if sess_orfana and sess_orfana.get("fine") is None:
            fine_orfana = sc.get("ultimo_tick") or now
            _chiudi_sessione(data, sc, fine_orfana)
            sc.clear()
            dirty = True

    # ── Macchina FERMA ────────────────────────────────────────────────────────
    if stato_pgm in (0, 5):
        if sc.get("in_esecuzione"):
            # Chiudi sessione corrente
            _chiudi_sessione(data, sc, now)
            sc.clear()
            dirty = True

    # ── Macchina IN ESECUZIONE ────────────────────────────────────────────────
    if stato_pgm in (1, 3) and programma_attivo:
        # Filtra programmi di sistema Sinumerik (non sono lavorazioni utente)
        _FILTRI_SISTEMA = ("_N_CMA_DIR", "_N_CST_DIR", "_N_SYF_DIR",
                           "_N_MPF_DIR", "_SPF", "BPOSAXIS", "TMPCYC")
        for f in _FILTRI_SISTEMA:
            if f in programma_attivo.upper():
                programma_attivo = None
                break

    if stato_pgm in (1, 3) and programma_attivo:
        prev_prog = sc.get("programma_corrente")

        # ── Cambio data (mezzanotte): chiudi sessione del giorno precedente ──
        sess_corrente = _find_sess(data, sc["sessione_id"]) if sc.get("sessione_id") else None
        if sess_corrente and sess_corrente.get("data") != now[:10]:
            # Chiudi la sessione di ieri con il timestamp di mezzanotte
            mezzanotte = now[:10] + "T00:00:00"
            _chiudi_sessione(data, sc, mezzanotte)
            sc.clear()
            prev_prog = None  # Forza apertura nuova sessione sotto

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
            # Stesso programma — accumula tick utensile (5s) e override ridotto
            if sc.get("sessione_id") and utensile:
                sess = _find_sess(data, sc["sessione_id"])
                if sess:
                    sess.setdefault("utensili", {})
                    sess["utensili"][utensile] = sess["utensili"].get(utensile, 0) + 5
                    dirty = True
            # Registra secondi con override ridotto (feed < 90% o mandrino < 90%)
            if sc.get("sessione_id"):
                ovr_f = override_feed     if override_feed     is not None else 100
                ovr_m = override_mandrino if override_mandrino is not None else 100
                if ovr_f < 90 or ovr_m < 90:
                    sess = _find_sess(data, sc["sessione_id"])
                    if sess:
                        sess["sec_override_ridotto"] = sess.get("sec_override_ridotto", 0) + 5
                        # Registra il valore minimo visto per diagnostica
                        min_ovr = min(ovr_f, ovr_m)
                        if "min_override" not in sess or min_ovr < sess["min_override"]:
                            sess["min_override"] = min_ovr
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
    now_iso = datetime.now().isoformat(timespec="seconds")

    sessioni_giorno = [
        s for s in log.get("sessioni", [])
        if s.get("data") == target
    ]

    def _durata_effettiva(s):
        """Durata reale: usa durata_sec se chiusa, altrimenti calcola live da inizio."""
        if s.get("durata_sec") is not None:
            return s["durata_sec"]
        # Sessione ancora aperta — calcola da inizio a adesso
        inizio = s.get("inizio")
        if not inizio:
            return 0
        try:
            return int((datetime.fromisoformat(now_iso) -
                        datetime.fromisoformat(inizio)).total_seconds())
        except Exception:
            return 0

    def _programmi_effettivi(s):
        """Programmi della sessione, aggiungendo durata live all'ultimo se ancora aperto."""
        pgms = list(s.get("programmi", []))
        sc = log.get("stato_corrente", {})
        # Se questa è la sessione corrente e c'è un programma in corso non chiuso
        if s.get("id") == sc.get("sessione_id") and sc.get("programma_corrente"):
            prog_corrente = sc["programma_corrente"]
            inizio_pgm = sc.get("inizio_programma")
            # Controlla se il programma corrente non è già nell'elenco chiuso
            già_chiuso = any(p.get("filename","").upper().replace(".MPF","") ==
                             prog_corrente.upper().replace(".MPF","") and p.get("fine")
                             for p in pgms)
            if not già_chiuso and inizio_pgm:
                try:
                    dur = int((datetime.fromisoformat(now_iso) -
                               datetime.fromisoformat(inizio_pgm)).total_seconds())
                except Exception:
                    dur = None
                info = _parse_nome(prog_corrente) if prog_corrente else {}
                pgms = pgms + [{
                    "filename":    prog_corrente,
                    **info,
                    "inizio":      inizio_pgm,
                    "fine":        None,
                    "durata_sec":  dur,
                    "utensile":    sc.get("utensile_programma"),
                    "t_number":    sc.get("t_number_programma"),
                    "_live":       True,
                }]
        return pgms

    # Aggregazioni con durata live
    ore_totali  = sum(_durata_effettiva(s) for s in sessioni_giorno)
    gap_totale  = sum(s.get("gap_sec") or 0 for s in sessioni_giorno)
    n_programmi = sum(len(_programmi_effettivi(s)) for s in sessioni_giorno)

    # ── OEE — Overall Equipment Effectiveness ─────────────────────────────────
    # Turno standard 8h = 28800s. Se le ore lavorate superano 8h usiamo quelle.
    ORE_TURNO_SEC = 28800
    tempo_turno = max(ore_totali + gap_totale, ORE_TURNO_SEC)

    # Disponibilità: tempo macchina in produzione / tempo turno
    disponibilita = ore_totali / tempo_turno if tempo_turno > 0 else 0

    # Performance: paragona cicli reali con tempi stimati CAM
    # Se non ci sono tempi stimati usa disponibilità come proxy
    sec_teorici = sum(
        pgm.get("durata_sec_teorica") or pgm.get("durata_sec") or 0
        for s in sessioni_giorno
        for pgm in _programmi_effettivi(s)
        if pgm.get("durata_sec")
    )
    sec_reali = sum(
        pgm.get("durata_sec") or 0
        for s in sessioni_giorno
        for pgm in _programmi_effettivi(s)
        if pgm.get("durata_sec")
    )
    performance = min(1.0, sec_teorici / sec_reali) if sec_reali > 0 and sec_teorici > 0 else disponibilita

    # Qualità: proxy per CNC stampi (rarissimi scarti) = 98%
    # In futuro: n_pezzi_ok / n_pezzi_totali
    qualita = 0.98

    oee = round(disponibilita * performance * qualita * 100, 1)

    # Override ridotto — tempo totale con feed/mandrino < 90%
    sec_ovr_ridotto = sum(s.get("sec_override_ridotto") or 0 for s in sessioni_giorno)
    min_ovr_giorno  = min(
        (s["min_override"] for s in sessioni_giorno if "min_override" in s),
        default=None
    )

    # Utensili aggregati (usa accumulo tick — già corretto anche live)
    utensili_agg = {}
    for s in sessioni_giorno:
        for ut, sec in (s.get("utensili") or {}).items():
            utensili_agg[ut] = utensili_agg.get(ut, 0) + sec

    # Progetti aggregati con durata live
    progetti_agg = {}
    for s in sessioni_giorno:
        prog = s.get("progetto") or "—"
        if prog not in progetti_agg:
            progetti_agg[prog] = {"durata_sec": 0, "n_programmi": 0, "pallet": s.get("pallet")}
        progetti_agg[prog]["durata_sec"] += _durata_effettiva(s)
        progetti_agg[prog]["n_programmi"] += len(_programmi_effettivi(s))

    # Sessioni con programmi arricchiti (live) e durata calcolata
    sessioni_output = []
    for s in sessioni_giorno:
        s_out = dict(s)
        s_out["programmi"]  = _programmi_effettivi(s)
        s_out["durata_sec"] = _durata_effettiva(s)
        sessioni_output.append(s_out)

    return {
        "data":             target,
        "ore_lavorate":     _durata_str(ore_totali),
        "ore_lavorate_sec": ore_totali,
        "tempo_fermo_sec":  gap_totale,
        "tempo_fermo":      _durata_str(gap_totale),
        "n_sessioni":       len(sessioni_giorno),
        "n_programmi":      n_programmi,
        "efficienza_pct":   round(ore_totali / (ore_totali + gap_totale) * 100, 1)
                            if (ore_totali + gap_totale) > 0 else 0,
        # OEE
        "oee": {
            "valore":        oee,
            "disponibilita": round(disponibilita * 100, 1),
            "performance":   round(performance   * 100, 1),
            "qualita":       round(qualita       * 100, 1),
            "ore_turno_sec": tempo_turno,
        },
        # Override ridotto
        "override_ridotto": {
            "sec_totale":    sec_ovr_ridotto,
            "durata":        _durata_str(sec_ovr_ridotto),
            "pct_tempo":     round(sec_ovr_ridotto / ore_totali * 100, 1) if ore_totali > 0 else 0,
            "min_valore":    min_ovr_giorno,
        },
        "progetti":         progetti_agg,
        "utensili":         {k: {"sec": v, "ore": _durata_str(v)}
                              for k, v in sorted(utensili_agg.items(), key=lambda x: -x[1])},
        "sessioni":         sessioni_output,
    }

@router.get("/storico")
async def get_storico(giorni: int = Query(default=7)):
    """Ultimi N giorni — per grafici trend."""
    config = carica_configurazione()
    log    = _load_log(config)
    now_iso = datetime.now().isoformat(timespec="seconds")
    today   = datetime.now().strftime("%Y-%m-%d")
    result = []
    for i in range(giorni - 1, -1, -1):
        d    = (datetime.now() - timedelta(days=i)).strftime("%Y-%m-%d")
        sess = [s for s in log.get("sessioni", []) if s.get("data") == d]
        # Per il giorno corrente usa durata live se sessione ancora aperta
        def _dur(s):
            if s.get("durata_sec") is not None:
                return s["durata_sec"]
            if d == today:
                inizio = s.get("inizio")
                if inizio:
                    try:
                        return int((datetime.fromisoformat(now_iso) -
                                    datetime.fromisoformat(inizio)).total_seconds())
                    except Exception:
                        pass
            return 0
        ore  = sum(_dur(s) for s in sess)
        gap  = sum(s.get("gap_sec") or 0 for s in sess)
        # OEE semplificato per lo storico (disponibilità * 0.98 qualità)
        ORE_TURNO = 28800
        tempo_turno = max(ore + gap, ORE_TURNO)
        disponibilita = ore / tempo_turno if tempo_turno > 0 else 0
        oee_valore = round(disponibilita * 1.0 * 0.98 * 100, 1)  # performance=1.0 senza cicli teorici
        sec_ovr = sum(s.get("sec_override_ridotto") or 0 for s in sess)
        result.append({
            "data": d,
            "ore_lavorate_sec": ore,
            "ore_lavorate": _durata_str(ore),
            "tempo_fermo_sec": gap,
            "n_programmi": sum(len(s.get("programmi", [])) for s in sess),
            "efficienza_pct": round(ore / (ore + gap) * 100, 1) if (ore + gap) > 0 else 0,
            "oee": {"valore": oee_valore, "disponibilita": round(disponibilita*100,1)} if ore > 0 else None,
            "sec_override_ridotto": sec_ovr,
        })
    return result

# ── Sessione live ─────────────────────────────────────────────────────────────

@router.get("/sessione-live")
async def get_sessione_live():
    """
    Restituisce i dati della sessione di lavorazione attualmente in corso.
    Chiamato dalla Home ogni 10s per mostrare il timer del pallet attivo.

    Risposta:
    {
      "attiva": true,
      "inizio_sessione": "2026-03-30T08:12:00",
      "durata_sec": 7543,
      "durata_str": "02:05:43",
      "inizio_programma": "2026-03-30T10:16:46",
      "durata_programma_sec": 312,
      "programma_corrente": "4297_005_01_14.MPF",
      "utensile": "FS16R2L80F85E6",
      "n_programmi_sessione": 14
    }
    """
    config  = carica_configurazione()
    data    = _load_log(config)
    sc      = data.get("stato_corrente", {})
    now_iso = datetime.now().isoformat(timespec="seconds")

    if not sc.get("in_esecuzione") or not sc.get("sessione_id"):
        return {"attiva": False}

    sess = _find_sess(data, sc["sessione_id"])
    if not sess:
        return {"attiva": False}

    # Durata totale sessione (da inizio pallet)
    inizio_sess = sess.get("inizio")
    durata_sess = 0
    if inizio_sess:
        try:
            durata_sess = int((datetime.fromisoformat(now_iso) -
                               datetime.fromisoformat(inizio_sess)).total_seconds())
        except Exception:
            pass

    # Durata programma corrente
    inizio_pgm = sc.get("inizio_programma")
    durata_pgm = 0
    if inizio_pgm:
        try:
            durata_pgm = int((datetime.fromisoformat(now_iso) -
                              datetime.fromisoformat(inizio_pgm)).total_seconds())
        except Exception:
            pass

    n_pgm = len(sess.get("programmi", []))  # già chiusi + quello corrente
    if sc.get("programma_corrente"):
        n_pgm += 1  # aggiungi quello in corso

    return {
        "attiva":                True,
        "inizio_sessione":       inizio_sess,
        "durata_sec":            durata_sess,
        "durata_str":            _durata_str(durata_sess),
        "inizio_programma":      inizio_pgm,
        "durata_programma_sec":  durata_pgm,
        "durata_programma_str":  _durata_str(durata_pgm),
        "programma_corrente":    sc.get("programma_corrente"),
        "utensile":              sc.get("utensile_programma"),
        "t_number":              sc.get("t_number_programma"),
        "n_programmi_sessione":  n_pgm,
        "progetto":              sess.get("progetto"),
        "pallet":                sess.get("pallet"),
    }


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


# ── Tempi ciclo reali per ETA ─────────────────────────────────────────────────

@router.get("/tempi-ciclo")
async def get_tempi_ciclo():
    """
    Analizza lavorazioni_log.json e calcola statistiche del ciclo reale
    per ogni filename MPF: media, deviazione standard, n campioni.

    Usato per:
    - ETA programma corrente nella Home (media * n_programmi_rimanenti)
    - Aggiornamento automatico tempoStimato nei progetti
    - Rilevamento cicli anomali (durata > media + 2σ)

    Risposta:
    {
      "cicli": {
        "4297_005_01_18.MPF": {
          "media_sec":  342,
          "std_sec":    28,
          "min_sec":    310,
          "max_sec":    398,
          "n":          7,
          "ultimo":     "2026-03-30T22:04:00"
        },
        ...
      },
      "n_programmi_con_dati": 45,
      "sessioni_analizzate":  12
    }
    """
    config = carica_configurazione()
    log    = _load_log(config)
    sessioni = log.get("sessioni", [])

    # Accumula durate per filename
    from collections import defaultdict
    import statistics

    dati: dict[str, list] = defaultdict(list)
    ultimi: dict[str, str] = {}

    for sess in sessioni:
        for pgm in sess.get("programmi", []):
            fname = pgm.get("filename", "").strip().upper()
            dur   = pgm.get("durata_sec")
            fine  = pgm.get("fine")
            if not fname or dur is None or dur <= 0:
                continue
            # Filtra durate anomale (> 8h = quasi certamente un bug di timing)
            if dur > 28800:
                continue
            dati[fname].append(dur)
            if fine and (fname not in ultimi or fine > ultimi[fname]):
                ultimi[fname] = fine

    cicli = {}
    for fname, durate in dati.items():
        if len(durate) < 1:
            continue
        media = sum(durate) / len(durate)
        std   = statistics.stdev(durate) if len(durate) > 1 else 0
        cicli[fname] = {
            "media_sec": round(media),
            "std_sec":   round(std),
            "min_sec":   min(durate),
            "max_sec":   max(durate),
            "n":         len(durate),
            "ultimo":    ultimi.get(fname),
        }

    return {
        "cicli":                  cicli,
        "n_programmi_con_dati":   len(cicli),
        "sessioni_analizzate":    len(sessioni),
    }
