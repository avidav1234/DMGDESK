"""
Tab Coda Lavorazione - V16
Stato pallet live + stato macchina.
Allineato con CodaLavorazione.jsx della web app.
"""

import customtkinter as ctk
import tkinter as tk
import tkinter.ttk as ttk
import json, os, threading, sys, re
from datetime import datetime
from pathlib import Path

from config.theme import *
from config.constants import *

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# ── Helpers config ────────────────────────────────────────────────────────────

def _get_base_dir() -> str:
    if getattr(sys, 'frozen', False):
        return os.path.dirname(sys.executable)
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _carica_config() -> dict:
    try:
        from database.db_handler import carica_configurazione
        cfg = carica_configurazione()
        if isinstance(cfg, dict):
            return cfg
    except Exception:
        pass
    try:
        with open(os.path.join(_get_base_dir(), "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _pallet_path(config: dict) -> Path:
    """Salva pallet_state.json nella stessa cartella di tools_machine.json."""
    base = (config.get("tools_toa_folder") or "").strip()
    if not base:
        nc = (config.get("percorso_nc_base") or "").strip()
        if nc:
            from pathlib import PurePath
            parts = PurePath(nc).parts
            base = str(Path(parts[0]) / parts[1]) if len(parts) >= 2 else nc
    if not base:
        return None
    return Path(base) / "pallet_state.json"


def _opcua_log_path(config: dict) -> str | None:
    """Cerca OpcUaLegacy.log nella share.
    Prova: percorso esplicito, radice share, percorso_nc_base completo.
    """
    # Path esplicito in config (priorità massima)
    explicit = (config.get("opcua_log_path") or "")
    if explicit and Path(explicit).exists():
        return explicit

    # Ricava la radice della share (es. P:\DMG_DMC_160U)
    # da radice, tools_toa_folder, o percorso_nc_base
    candidates_base = []

    for key in ["radice", "tools_toa_folder", "percorso_nc_base"]:
        val = (config.get(key) or "").strip().replace("/", "\\")
        if val:
            p = Path(val)
            candidates_base.append(p)
            # Risale anche ai primi 2 livelli (es. P:\DMG_DMC_160U da P:\DMG_DMC_160U\4348\0221)
            parts = p.parts
            if len(parts) >= 2:
                candidates_base.append(Path(parts[0]) / parts[1])

    for base in candidates_base:
        for suffix in [
            "OpcUaLegacy.log",
            "logs/OpcUaLegacy.log",
            "stato/OpcUaLegacy.log",
        ]:
            full = base / suffix
            if full.exists():
                return str(full)
    return None


# ── Parser log OpcUa ─────────────────────────────────────────────────────────

VAR_MAP = {
    "workPandProgName": "programma_attivo",
    "actTNumber":       "numero_utensile",
    "actToolIdent":     "utensile_attivo",
    "progStatus":       "stato_programma",
    "OpcUaAlarm1":      "allarme",
    "DB0.DBB67":        "pallet_attivo",
}
RE_LINE = re.compile(
    r"ReadPlVar:\s*VarName=\s*([^;]+);\s*read Value=\s*(.*)",
    re.IGNORECASE)


def _parse_log(log_path: str) -> dict:
    result = {}
    try:
        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            lines = f.readlines()
        seen = set()
        for line in reversed(lines[-500:]):
            m = RE_LINE.search(line)
            if not m:
                continue
            var_path = m.group(1).strip()
            value    = m.group(2).strip()
            for key, campo in VAR_MAP.items():
                if key in var_path and campo not in seen:
                    result[campo] = value
                    seen.add(campo)
            if len(seen) >= len(VAR_MAP):
                break
    except Exception as e:
        result["errore_parse"] = str(e)
    return result


def _normalizza(raw: dict) -> dict:
    out = dict(raw)
    try:
        out["stato_programma"] = int(raw.get("stato_programma", 0))
    except Exception:
        out["stato_programma"] = 0
    try:
        out["numero_utensile"] = int(raw.get("numero_utensile", 0))
    except Exception:
        out["numero_utensile"] = None
    # Fonte primaria: workPandProgName — sempre presente nel log OpcUa
    # es. /_N_WKS_DIR/_N_PALLET_WPD/_N_PALLET4_MPF → pallet 4
    # Fallback: DB0.DBB67 se disponibile nel log
    pallet = None
    prog = raw.get("programma_attivo", "") or ""
    m = re.search(r"_N_PALLET(\d)_MPF", prog, re.IGNORECASE)
    if m:
        v = int(m.group(1))
        if 1 <= v <= 6:
            pallet = v
    if pallet is None:
        try:
            v = int(raw.get("pallet_attivo", 0))
            if 1 <= v <= 6:
                pallet = v
        except Exception:
            pass
    out["pallet_attivo"] = pallet
    prog = raw.get("programma_attivo", "")
    out["programma_attivo"] = prog if prog and prog != "0" else None
    ut = raw.get("utensile_attivo", "")
    out["utensile_attivo"] = ut if ut and ut != "0" else None
    al = raw.get("allarme", "").strip()
    out["allarme"] = al if al else None
    return out


def _parse_program(path: str) -> dict | None:
    """Estrae commessa/posizione/fase dal path NC."""
    if not path:
        return None
    m = re.search(r'_N_(\d+)_(\d+)_WPD/_N_\d+_\d+_(.+?)_MPF', path)
    if m:
        return {"commessa": m.group(1), "posizione": m.group(2), "fase": m.group(3)}
    m2 = re.search(r'_N_([^/]+?)_(?:MPF|SPF)$', path)
    if m2:
        return {"fase": m2[1]}
    return None


# ── Costanti colori pallet ────────────────────────────────────────────────────

STATI_COLORS = {
    "IN LAVORAZIONE": {"bg": "#0d2d5e", "fg": "white",   "border": "#1a4080"},
    "GREZZO":         {"bg": "#fefce8", "fg": "#854d0e",  "border": "#eab308"},
    "FINITO":         {"bg": "#dcfce7", "fg": "#14532d",  "border": "#22c55e"},
    "VUOTO":          {"bg": "#f1f5f9", "fg": "#94a3b8",  "border": "#e2e8f0"},
    "GUASTO":         {"bg": "#fef2f2", "fg": "#991b1b",  "border": "#f87171"},
}
STATI_ORDER  = ["VUOTO", "GREZZO", "FINITO", "GUASTO"]
STATI_MANUAL = {"VUOTO", "GREZZO", "GUASTO"}

REFRESH_MS = 5000


# ── Tab ──────────────────────────────────────────────────────────────────────

class TabCodaLavorazione:
    """Tab Coda Lavorazione — pallet live + stato macchina."""

    def __init__(self, parent, main_window):
        self.parent      = parent
        self.main        = main_window
        self._pallets    = [{"id": i+1, "stato": "VUOTO", "programma": None} for i in range(6)]
        self._macchina   = {}
        self._after_id   = None
        self._create_ui()
        self._start_polling()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _create_ui(self):
        # Header
        header = ctk.CTkFrame(self.parent, fg_color=COLOR_PRIMARY, height=64)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="CODA LAVORAZIONE",
                     font=get_font("title", bold=True), text_color="white").pack(pady=(10, 2))
        ctk.CTkLabel(header, text="Stato pallet  |  Stato macchina live",
                     font=get_font("body"), text_color="#E8F5E9").pack(pady=(0, 6))

        # Corpo principale: sinistra (pallet) + destra (stato)
        body = ctk.CTkFrame(self.parent, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=10, pady=10)

        # ── Griglia pallet (sinistra) ─────────────────────────────────────
        col_sx = ctk.CTkFrame(body, fg_color="transparent", width=340)
        col_sx.pack(side="left", fill="y", padx=(0, 10))
        col_sx.pack_propagate(False)

        hdr_row = ctk.CTkFrame(col_sx, fg_color="transparent")
        hdr_row.pack(fill="x", pady=(0, 6))
        ctk.CTkLabel(hdr_row, text="PALLET",
                     font=get_font("small", bold=True),
                     text_color=COLOR_PRIMARY).pack(side="left")
        self.lbl_update = ctk.CTkLabel(hdr_row, text="",
                                        font=get_font("small"),
                                        text_color=COLOR_TEXT_SECONDARY)
        self.lbl_update.pack(side="right")

        # Canvas grid 2×3
        grid = ctk.CTkFrame(col_sx, fg_color="transparent")
        grid.pack(fill="both", expand=True)

        # ── Info macchina (sotto pallet) ──────────────────────────
        # Card stato macchina
        self.card_stato = ctk.CTkFrame(col_sx, fg_color="#f8fafc",
                                        corner_radius=12, border_width=1,
                                        border_color="#e2e8f0")
        self.card_stato.pack(fill="x", pady=(0, 8))
        stato_inner = ctk.CTkFrame(self.card_stato, fg_color="transparent")
        stato_inner.pack(fill="x", padx=16, pady=12)
        self.canvas_dot = tk.Canvas(stato_inner, width=14, height=14,
                                     bg="#f8fafc", bd=0, highlightthickness=0)
        self.canvas_dot.pack(side="left", padx=(0, 10))
        self._dot = self.canvas_dot.create_oval(2, 2, 12, 12, fill="#94a3b8", outline="")
        self.lbl_stato_mac = ctk.CTkLabel(stato_inner, text="FERMA",
                                           font=get_font("medium", bold=True),
                                           text_color="#374151")
        self.lbl_stato_mac.pack(side="left")
        self.lbl_pallet_mac = ctk.CTkLabel(stato_inner, text="",
                                            font=get_font("small"),
                                            text_color=COLOR_TEXT_SECONDARY)
        self.lbl_pallet_mac.pack(side="left", padx=8)

        # Card programma
        self.card_prog = ctk.CTkFrame(col_sx, fg_color="white",
                                       corner_radius=12, border_width=1,
                                       border_color="#e2e8f0")
        self.card_prog.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self.card_prog, text="PROGRAMMA",
                     font=get_font("small"), text_color=COLOR_TEXT_SECONDARY).pack(
                     anchor="w", padx=16, pady=(10, 4))
        prog_inner = ctk.CTkFrame(self.card_prog, fg_color="transparent")
        prog_inner.pack(fill="x", padx=16, pady=(0, 12))

        self.lbl_commessa  = self._make_info_block(prog_inner, "COMMESSA",  side="left")
        self.lbl_posizione = self._make_info_block(prog_inner, "POSIZIONE", side="left")
        self.lbl_fase      = self._make_info_block(prog_inner, "FASE",      side="left")

        # Card utensile
        self.card_utensile = ctk.CTkFrame(col_sx, fg_color="white",
                                           corner_radius=12, border_width=1,
                                           border_color="#e2e8f0")
        self.card_utensile.pack(fill="x", pady=(0, 8))
        ctk.CTkLabel(self.card_utensile, text="UTENSILE ATTIVO",
                     font=get_font("small"), text_color=COLOR_TEXT_SECONDARY).pack(
                     anchor="w", padx=16, pady=(10, 4))
        self.lbl_utensile = ctk.CTkLabel(self.card_utensile, text="—",
                                          font=get_font("title", bold=True),
                                          text_color=COLOR_PRIMARY)
        self.lbl_utensile.pack(anchor="w", padx=16)
        self.lbl_tnum = ctk.CTkLabel(self.card_utensile, text="",
                                      font=get_font("small"),
                                      text_color=COLOR_TEXT_SECONDARY)
        self.lbl_tnum.pack(anchor="w", padx=16, pady=(0, 10))

        # Card allarme (nascosta se nessun allarme)
        self.card_allarme = ctk.CTkFrame(col_sx, fg_color="#fef2f2",
                                          corner_radius=12, border_width=1,
                                          border_color="#fca5a5")
        ctk.CTkLabel(self.card_allarme, text="ALLARME",
                     font=get_font("small"), text_color="#991b1b").pack(
                     anchor="w", padx=16, pady=(10, 2))
        self.lbl_allarme = ctk.CTkLabel(self.card_allarme, text="",
                                         font=get_font("body"),
                                         text_color="#991b1b", anchor="w",
                                         wraplength=300, justify="left")
        self.lbl_allarme.pack(anchor="w", padx=16, pady=(0, 10))

        # Errore connessione
        self.card_errore = ctk.CTkFrame(col_sx, fg_color="#fef3c7",
                                         corner_radius=8, border_width=1,
                                         border_color="#fcd34d")
        self.lbl_errore = ctk.CTkLabel(self.card_errore, text="",
                                        font=get_font("small"),
                                        text_color="#92400e")
        self.lbl_errore.pack(padx=12, pady=6)



        self._pallet_frames = {}
        self._pallet_labels = {}
        for i, pid in enumerate([1,2,3,4,5,6]):
            row, col = divmod(i, 2)
            f = tk.Frame(grid, relief="flat", bd=0,
                         width=180, height=200, cursor="hand2")
            f.grid(row=row, column=col, padx=5, pady=5)
            f.pack_propagate(False)
            f.bind("<Button-1>", lambda e, p=pid: self._click_pallet(p))

            # Contenuto del frame
            top = tk.Frame(f, bd=0)
            top.place(x=10, y=8, width=160, height=34)
            lbl_num = tk.Label(top, text=f"P{pid}", font=("Helvetica", 28, "bold"), bd=0)
            lbl_num.pack(side="left")
            lbl_dot = tk.Label(top, text="●", font=("Helvetica", 9), bd=0)
            lbl_dot.pack(side="right", padx=2)

            lbl_stato = tk.Label(f, text="VUOTO",
                                  font=("Helvetica", 9, "bold"), bd=0,
                                  anchor="w")
            lbl_stato.place(x=10, y=105, width=160, height=14)

            lbl_prog = tk.Label(f, text="",
                                 font=("Helvetica", 8), bd=0,
                                 anchor="w")
            lbl_prog.place(x=10, y=118, width=160, height=12)

            for w in [f, top, lbl_num, lbl_dot, lbl_stato, lbl_prog]:
                w.bind("<Button-1>", lambda e, p=pid: self._click_pallet(p))

            self._pallet_frames[pid] = {
                "frame": f, "lbl_num": lbl_num, "lbl_dot": lbl_dot,
                "lbl_stato": lbl_stato, "lbl_prog": lbl_prog
            }

        # ── Pannello destro: coda + programmi ────────────────────────────
        col_dx = ctk.CTkScrollableFrame(body, fg_color="transparent")
        col_dx.pack(side="left", fill="both", expand=True)

        # ── Coda Esecuzione ──────────────────────────────────────────────
        self.card_coda = ctk.CTkFrame(col_dx, fg_color="white",
                                       corner_radius=10, border_width=1,
                                       border_color="#e2e8f0")
        self.card_coda.pack(fill="x", pady=(8, 0))
        coda_hdr = ctk.CTkFrame(self.card_coda, fg_color="transparent")
        coda_hdr.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(coda_hdr, text="📋 CODA ESECUZIONE",
                     font=get_font("small", bold=True),
                     text_color=COLOR_PRIMARY).pack(side="left")
        self.lbl_coda_status2 = ctk.CTkLabel(coda_hdr, text="",
                                              font=get_font("small"),
                                              text_color=COLOR_TEXT_SECONDARY)
        self.lbl_coda_status2.pack(side="right")
        self.frame_coda_body2 = tk.Frame(self.card_coda, bg="white")
        self.frame_coda_body2.pack(fill="x", padx=12, pady=(0, 8))

        # ── Programmi in macchina ─────────────────────────────────────────
        self.card_pgm_mac = ctk.CTkFrame(col_dx, fg_color="white",
                                          corner_radius=10, border_width=1,
                                          border_color="#e2e8f0")
        self.card_pgm_mac.pack(fill="both", expand=True, pady=(8, 0))
        pgm_hdr = ctk.CTkFrame(self.card_pgm_mac, fg_color="transparent")
        pgm_hdr.pack(fill="x", padx=12, pady=(8, 4))
        ctk.CTkLabel(pgm_hdr, text="⚙ PROGRAMMI IN MACCHINA",
                     font=get_font("small", bold=True),
                     text_color=COLOR_PRIMARY).pack(side="left")
        self.lbl_pgm_completa = ctk.CTkLabel(pgm_hdr, text="",
                                              font=get_font("small"),
                                              text_color="#166534")
        self.lbl_pgm_completa.pack(side="right")
        # Scrollable per la lista programmi
        self.frame_pgm_mac_body = ctk.CTkScrollableFrame(
            self.card_pgm_mac, fg_color="transparent", height=200)
        self.frame_pgm_mac_body.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        # Selezionati
        self._pgm_sel = {}   # {pgm_id: (pallet_num, BooleanVar)}
        self._pgm_data = {}  # {pallet_num: {progetto, programmi}}

    def _make_info_block(self, parent, label_text, side="left"):
        """Crea un blocco label/valore stile card."""
        f = ctk.CTkFrame(parent, fg_color="transparent")
        f.pack(side=side, padx=(0, 20))
        ctk.CTkLabel(f, text=label_text, font=get_font("small"),
                     text_color=COLOR_TEXT_SECONDARY).pack(anchor="w")
        lbl = ctk.CTkLabel(f, text="—", font=get_font("title", bold=True),
                            text_color=COLOR_PRIMARY)
        lbl.pack(anchor="w")
        return lbl

    # ── Polling ──────────────────────────────────────────────────────────────

    def _start_polling(self):
        self._fetch_data()

    def _schedule_next(self):
        self._after_id = self.parent.after(REFRESH_MS, self._fetch_data)

    def _fetch_data(self):
        config = _carica_config()
        def _worker():
            macchina = self._fetch_macchina(config)
            pallets  = self._fetch_pallets(config, macchina)
            self.parent.after(0, lambda: self._update_ui(macchina, pallets))
        threading.Thread(target=_worker, daemon=True).start()

    def _fetch_macchina(self, config) -> dict:
        log_path = _opcua_log_path(config)
        if not log_path:
            return {"connessa": False}
        raw = _parse_log(log_path)
        data = _normalizza(raw)
        try:
            mtime = os.path.getmtime(log_path)
            data["ultimo_aggiornamento"] = datetime.fromtimestamp(mtime).strftime("%H:%M:%S")
        except Exception:
            data["ultimo_aggiornamento"] = None
        data["connessa"] = True
        return data

    def _fetch_pallets(self, config, macchina) -> list:
        path = _pallet_path(config)
        pallets = [{"id": i+1, "stato": "VUOTO", "programma": None} for i in range(6)]
        if path and path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                for p_saved in data.get("pallet", []):
                    pid = p_saved.get("numero", 0)
                    if 1 <= pid <= 6:
                        stato_raw = p_saved.get("stato", "vuoto").upper()
                        stato_map = {
                            "VUOTO": "VUOTO", "GREZZO": "GREZZO",
                            "IN_LAVORAZIONE": "IN LAVORAZIONE",
                            "IN LAVORAZIONE": "IN LAVORAZIONE",
                            "FINITO": "FINITO", "GUASTO": "GUASTO"
                        }
                        pallets[pid-1]["stato"]      = stato_map.get(stato_raw, "VUOTO")
                        pallets[pid-1]["programma"]   = p_saved.get("programma")
                        pallets[pid-1]["progetto_id"] = p_saved.get("progetto_id")
                        pallets[pid-1]["progetto_nome"] = p_saved.get("progetto_nome")
                        pallets[pid-1]["progetto_colore"] = p_saved.get("progetto_colore")
            except Exception:
                pass

        # Sovrascrive con IN LAVORAZIONE se la macchina lo conferma
        pallet_attivo = macchina.get("pallet_attivo")
        stato_prog    = macchina.get("stato_programma", 0)
        if pallet_attivo and stato_prog == 3:
            for p in pallets:
                if p["id"] == pallet_attivo:
                    p["stato"] = "IN LAVORAZIONE"

        return pallets

    # ── Aggiornamento UI ─────────────────────────────────────────────────────

    def _update_ui(self, macchina, pallets):
        self._macchina = macchina
        self._pallets  = pallets

        # Timestamp
        ts = macchina.get("ultimo_aggiornamento", "")
        self.lbl_update.configure(text=ts or "")

        # Errore connessione
        if not macchina.get("connessa", False):
            if macchina.get("connessa") is False:
                self.card_errore.pack(fill="x", pady=(0, 4))
                self.lbl_errore.configure(text="⚠  Log OpcUa non trovato — stato macchina non disponibile")
        else:
            self.card_errore.pack_forget()

        # Stato macchina
        in_lav = macchina.get("stato_programma", 0) == 3
        pallet_attivo = macchina.get("pallet_attivo")
        if in_lav:
            self.card_stato.configure(fg_color="#0d2d5e", border_color="#1a4080")
            self.canvas_dot.configure(bg="#0d2d5e")
            self.canvas_dot.itemconfig(self._dot, fill="#22c55e")
            self.lbl_stato_mac.configure(text="IN LAVORAZIONE", text_color="white")
            pallet_txt = f"Pallet {pallet_attivo} in macchina" if pallet_attivo else ""
            self.lbl_pallet_mac.configure(text=pallet_txt, text_color="#93c5fd")
        else:
            self.card_stato.configure(fg_color="#f8fafc", border_color="#e2e8f0")
            self.canvas_dot.configure(bg="#f8fafc")
            self.canvas_dot.itemconfig(self._dot, fill="#94a3b8")
            self.lbl_stato_mac.configure(text="FERMA", text_color="#374151")
            self.lbl_pallet_mac.configure(text="", text_color=COLOR_TEXT_SECONDARY)

        # Programma
        prog = _parse_program(macchina.get("programma_attivo"))
        if prog:
            self.lbl_commessa.configure(text=prog.get("commessa", "—"))
            self.lbl_posizione.configure(text=prog.get("posizione", "—"))
            self.lbl_fase.configure(text=prog.get("fase", "—"))
        else:
            self.lbl_commessa.configure(text="—")
            self.lbl_posizione.configure(text="—")
            self.lbl_fase.configure(text="—")

        # Utensile
        utensile = macchina.get("utensile_attivo")
        tnum     = macchina.get("numero_utensile")
        self.lbl_utensile.configure(text=utensile or "—")
        self.lbl_tnum.configure(text=f"T{tnum}" if tnum else "")

        # Allarme
        alarm = macchina.get("allarme")
        if alarm:
            alarm_clean = re.sub(r'^\|[^|]*\|[^|]*\| ?', '', alarm)
            self.lbl_allarme.configure(text=alarm_clean)
            self.card_allarme.pack(fill="x", pady=(0, 8))
        else:
            self.card_allarme.pack_forget()

        # Pallet cards
        for p in pallets:
            self._update_pallet_card(p, pallet_attivo)

        # Coda esecuzione + programmi in macchina
        self._render_coda_dx(pallets)
        self._render_pgm_macchina(pallets)

        self._schedule_next()

    def _update_pallet_card(self, pallet, pallet_attivo_mac):
        pid    = pallet["id"]
        stato  = pallet.get("stato", "VUOTO")
        prog   = pallet.get("programma") or ""
        is_active = (pallet_attivo_mac == pid)
        is_lav = stato == "IN LAVORAZIONE"

        # Calcola info progetto per colori semantici
        proj_nome   = pallet.get("progetto_nome") or ""
        proj_colore = pallet.get("progetto_colore") or "#1D5FAD"
        info = self._calc_pct(proj_nome) if proj_nome else None

        # Colori semantici: blu=IN LAVORAZIONE, verde=completato, giallo=grezzo
        is_completo = info and info["pct"] >= 100
        if is_lav:
            colors = {"bg": "#dbeafe", "fg": "#0d2d5e", "border": "#1D5FAD"}
        elif is_completo:
            colors = {"bg": "#dcfce7", "fg": "#14532d", "border": "#16a34a"}
        else:
            colors = STATI_COLORS.get(stato, STATI_COLORS["VUOTO"])

        widgets = self._pallet_frames[pid]
        f       = widgets["frame"]
        border  = "#f59e0b" if is_active else colors["border"]
        border_w = 3 if is_active else 2

        f.configure(bg=colors["bg"],
                    highlightbackground=border,
                    highlightthickness=border_w)

        for w in [f, widgets["lbl_stato"], widgets["lbl_prog"]]:
            try: w.configure(bg=colors["bg"])
            except: pass

        widgets["lbl_num"].configure(bg=colors["bg"], fg=colors["fg"])
        widgets["lbl_stato"].configure(text=stato, bg=colors["bg"], fg=colors["fg"])

        prog_display = prog
        if prog and len(prog) > 20:
            prog_display = prog.split("/")[-1].replace("_N_", "").replace("_MPF", "")
        widgets["lbl_prog"].configure(text=prog_display, bg=colors["bg"], fg=colors["fg"])

        # Dot indicatore attivo
        dot = widgets["lbl_dot"]
        if is_active:
            dot.configure(text="●", fg="#f59e0b", bg=colors["bg"])
        else:
            dot.configure(text="", bg=colors["bg"])

        # Rimuovi widget dinamici precedenti
        for w in f.winfo_children():
            if getattr(w, "_dmg_pallet_proj", False):
                w.destroy()

        if not proj_nome:
            return

        # Nome progetto
        lbl_proj = tk.Label(f, text=f"● {proj_nome}",
                            font=("DM Sans", 9, "bold"),
                            fg=proj_colore, bg=colors["bg"],
                            anchor="w")
        lbl_proj._dmg_pallet_proj = True
        lbl_proj.place(x=10, y=48, width=160, height=16)

        if info:
            # Barra avanzamento
            bar_bg = tk.Frame(f, bg="#e2e8f0", height=6)
            bar_bg._dmg_pallet_proj = True
            bar_bg.place(x=10, y=70, width=160, height=6)
            bar_bg.configure(bg="#e2e8f0")
            pct_w = max(2, int(info["pct"] * 160 / 100))
            bar_fill = tk.Frame(bar_bg, bg=proj_colore, height=6)
            bar_fill.place(x=0, y=0, width=pct_w, height=6)

            # Percentuale
            lbl_pct = tk.Label(f, text=f"{info['done']}/{info['tot']} pgm   {int(info['pct'])}%",
                               font=("DM Sans", 8), fg=colors["fg"], bg=colors["bg"], anchor="w")
            lbl_pct._dmg_pallet_proj = True
            lbl_pct.place(x=10, y=80, width=160, height=14)

            # Pulsante Avvia — solo se non già IN LAVORAZIONE e ci sono pgm rimasti
            pgm_rimasti = info.get("da_fare", 0) + info.get("in_macchina", 0)
            if not is_lav and pgm_rimasti > 0:
                pid_progetto = pallet.get("progetto_id", "")
                btn = tk.Button(f, text=f"▶ Avvia ({pgm_rimasti})",
                                font=("DM Sans", 8, "bold"),
                                fg="#fff", bg="#1D5FAD",
                                relief="flat", cursor="hand2",
                                command=lambda n=pid, p=pid_progetto: self._avvia_pallet_coda(n, p))
                btn._dmg_pallet_proj = True
                btn.place(x=10, y=160, width=160, height=26)

    # ── Click pallet ─────────────────────────────────────────────────────────

    def _render_coda_dx(self, pallets):
        """Renderizza la coda esecuzione nella colonna destra."""
        for w in self.frame_coda_body2.winfo_children():
            w.destroy()

        # Legge ordine coda dalla API
        try:
            import urllib.request as _ur
            r = _ur.urlopen("http://localhost:8000/api/pallet/ordine-esecuzione", timeout=2)
            data = json.loads(r.read())
            ordine = data.get("ordine", [])
        except Exception:
            ordine = []

        assegnati = {p["id"]: p for p in pallets if p.get("progetto_nome")}
        if not assegnati:
            tk.Label(self.frame_coda_body2, text="Nessun pallet in coda",
                     font=("Inter",8), fg="#94a3b8", bg="white").pack(anchor="w")
            return

        in_coda   = [assegnati[n] for n in ordine if n in assegnati]
        fuori     = [p for pid, p in assegnati.items() if pid not in ordine]

        row = tk.Frame(self.frame_coda_body2, bg="white")
        row.pack(fill="x")

        for i, p in enumerate(in_coda):
            is_lav = p.get("stato","") == "IN LAVORAZIONE"
            col_bg = "#dbeafe" if is_lav else "#eef4fb"
            col_border = "#1D5FAD"
            card = tk.Frame(row, bg=col_bg, highlightbackground=col_border,
                            highlightthickness=1)
            card.pack(side="left", padx=(0,4), pady=2)
            tk.Label(card, text=f"{i+1}° P{p['id']}",
                     font=("Inter",7,"bold"), fg=col_border, bg=col_bg).pack(
                     side="left", padx=(4,2), pady=3)
            tk.Label(card, text=p.get("progetto_nome","?"),
                     font=("Inter",8,"bold"), fg=col_border, bg=col_bg).pack(
                     side="left", padx=(0,4))

        for p in fuori:
            btn = tk.Button(row, text=f"+ P{p['id']} {p.get('progetto_nome','')}",
                            font=("Inter",7), fg="#475569", bg="#f1f5f9",
                            relief="flat", cursor="hand2",
                            command=lambda n=p["id"]: self._aggiungi_coda(n))
            btn.pack(side="left", padx=2)

        if ordine:
            self.lbl_coda_status2.configure(
                text=" → ".join(f"P{n}" for n in ordine))

    def _aggiungi_coda(self, num):
        """Aggiunge pallet alla coda via API."""
        import threading, urllib.request as _ur
        def _w():
            try:
                r = _ur.urlopen(
                    "http://localhost:8000/api/pallet/ordine-esecuzione", timeout=2)
                data = json.loads(r.read())
                ordine = data.get("ordine", [])
                if num not in ordine:
                    ordine.append(num)
                    req = _ur.Request(
                        "http://localhost:8000/api/pallet/ordine-esecuzione",
                        data=json.dumps({"ordine": ordine}).encode(),
                        method="PUT",
                        headers={"Content-Type": "application/json"})
                    _ur.urlopen(req, timeout=2)
            except Exception as e:
                print(f"[CODA] {e}")
        threading.Thread(target=_w, daemon=True).start()

    def _render_pgm_macchina(self, pallets):
        """Renderizza la lista programmi in_macchina con checkbox → completa."""
        for w in self.frame_pgm_mac_body.winfo_children():
            w.destroy()
        self._pgm_sel = {}
        self._pgm_data = {}

        # Carica programmi in_macchina per ogni pallet assegnato
        PAL_COLORS = ["#0d2d5e","#0891b2","#7c3aed","#059669","#d97706","#dc2626"]
        has_any = False

        for p in pallets:
            if not p.get("progetto_nome"): continue
            info = self._calc_pct(p["progetto_nome"])
            if not info or info.get("in_macchina", 0) == 0: continue

            # Carica programmi dettagliati
            try:
                cfg = _carica_config()
                from pathlib import Path as _P
                folder = (cfg.get("tools_toa_folder") or "").strip()
                pf = _P(folder) / "worktrack_projects.json"
                data = json.loads(pf.read_text(encoding="utf-8"))
                proj = next((pr for pr in data.get("projects",[])
                             if pr.get("name")==p["progetto_nome"]), None)
                if not proj: continue
                pgms_in_mac = []
                for step in proj.get("steps",[]):
                    for task in step.get("tasks",[]):
                        if task.get("text","").strip().lower()!="fresatura": continue
                        for pgm in task.get("programs",[]):
                            if pgm.get("tipoGruppo")=="ipm": continue
                            if pgm.get("stato")=="in_macchina":
                                pgms_in_mac.append(pgm)
                if not pgms_in_mac: continue
                pgms_in_mac.sort(key=lambda x: str(x.get("numPgm","")).zfill(6))
                self._pgm_data[p["id"]] = {"progetto_id": proj["id"],
                                            "progetto_nome": p["progetto_nome"],
                                            "programmi": pgms_in_mac}
            except Exception:
                continue

            col = PAL_COLORS[(p["id"]-1) % len(PAL_COLORS)]
            has_any = True

            # Header progetto
            hdr = tk.Frame(self.frame_pgm_mac_body, bg="#f0f4ff")
            hdr.pack(fill="x", pady=(4,1))
            tk.Frame(hdr, bg=col, width=3).pack(side="left", fill="y")
            tk.Label(hdr, text=f"P{p['id']} — {p['progetto_nome']}",
                     font=("Inter",8,"bold"), fg=col,
                     bg="#f0f4ff").pack(side="left", padx=6, pady=2)

            # Righe programma
            for pgm in self._pgm_data[p["id"]]["programmi"]:
                pgm_id = pgm.get("id","")
                var = tk.BooleanVar(value=False)
                self._pgm_sel[pgm_id] = (p["id"], var)

                row = tk.Frame(self.frame_pgm_mac_body, bg="#f8fafc",
                               highlightbackground="#e2e8f0", highlightthickness=1)
                row.pack(fill="x", pady=1)

                chk = tk.Checkbutton(row, variable=var, bg="#f8fafc",
                                      activebackground="#f8fafc",
                                      command=self._aggiorna_btn_completa)
                chk.pack(side="left", padx=2)

                fn = (pgm.get("filename","") or "").replace(".MPF","").replace(".mpf","")
                tk.Label(row, text=fn or pgm.get("numPgm",""),
                         font=("Consolas",8,"bold"), fg=col,
                         bg="#f8fafc").pack(side="left", padx=(0,4))
                tk.Label(row, text=pgm.get("utensile","—") or "—",
                         font=("Consolas",8), fg="#475569",
                         bg="#f8fafc").pack(side="left")
                if pgm.get("tempoStimato"):
                    tk.Label(row, text=f"⏱{pgm['tempoStimato']}m",
                             font=("Inter",7,"bold"), fg="#475569",
                             bg="#f8fafc").pack(side="right", padx=4)

        if has_any:
            # Bottone completa
            self._btn_completa = tk.Button(
                self.frame_pgm_mac_body,
                text="✓ Segna selezionati completati",
                font=("Inter",8,"bold"), fg="white", bg="#166534",
                relief="flat", cursor="hand2",
                command=self._completa_selezionati)
            self._btn_completa.pack(fill="x", pady=(6,0))
            self._btn_completa.pack_forget()  # nascosto finché nessuna selezione
        else:
            tk.Label(self.frame_pgm_mac_body,
                     text="Nessun programma in macchina",
                     font=("Inter",8), fg="#94a3b8",
                     bg="white").pack(anchor="w", pady=4)

    def _aggiorna_btn_completa(self):
        """Mostra/nasconde il bottone completa in base alle selezioni."""
        n = sum(1 for pid, var in self._pgm_sel.values() if var.get())
        if hasattr(self, "_btn_completa") and self._btn_completa.winfo_exists():
            if n > 0:
                self._btn_completa.configure(
                    text=f"✓ Segna {n} completat{'o' if n==1 else 'i'}")
                self._btn_completa.pack(fill="x", pady=(6,0))
            else:
                self._btn_completa.pack_forget()

    def _completa_selezionati(self):
        """Segna i programmi selezionati come completati via API."""
        import threading, urllib.request as _ur
        # Raggruppa per pallet
        per_pallet = {}
        for pgm_id, (pallet_num, var) in self._pgm_sel.items():
            if var.get():
                per_pallet.setdefault(pallet_num, []).append(pgm_id)

        def _w():
            for pallet_num, ids in per_pallet.items():
                try:
                    req = _ur.Request(
                        f"http://localhost:8000/api/pallet/{pallet_num}/programmi-completa",
                        data=json.dumps({"ids": ids}).encode(),
                        method="PATCH",
                        headers={"Content-Type": "application/json"})
                    _ur.urlopen(req, timeout=3)
                except Exception as e:
                    print(f"[COMPLETA] {e}")
        threading.Thread(target=_w, daemon=True).start()

    def _calc_pct(self, proj_nome: str) -> dict | None:
        """Calcola avanzamento programmi di un progetto per nome."""
        try:
            cfg = _carica_config()
            from pathlib import Path as _P
            folder = (cfg.get("tools_toa_folder") or "").strip()
            if not folder: return None
            pf = _P(folder) / "worktrack_projects.json"
            if not pf.exists(): return None
            data = json.loads(pf.read_text(encoding="utf-8"))
            proj = next((p for p in data.get("projects",[]) if p.get("name")==proj_nome), None)
            if not proj: return None
            pgms = [pgm for step in proj.get("steps",[]) for task in step.get("tasks",[])
                    if task.get("text","").strip().lower()=="fresatura"
                    for pgm in task.get("programs",[]) if pgm.get("tipoGruppo")!="ipm"]
            if not pgms: return None
            done      = sum(1 for p in pgms if p.get("stato")=="completato")
            da_fare   = sum(1 for p in pgms if p.get("stato")=="da_fare")
            in_mac    = sum(1 for p in pgms if p.get("stato")=="in_macchina")
            return {"pct": round(done/len(pgms)*100, 1), "done": done,
                    "tot": len(pgms), "da_fare": da_fare, "in_macchina": in_mac}
        except Exception:
            return None

    def _avvia_pallet_coda(self, num_pallet: int, progetto_id: str):
        """Avvia pallet tramite API — IN LAVORAZIONE + cima coda."""
        import threading, urllib.request
        def _worker():
            try:
                req = urllib.request.Request(
                    f"http://localhost:8000/api/pallet/{num_pallet}/avvia",
                    data=b"", method="POST",
                    headers={"Content-Type": "application/json"})
                urllib.request.urlopen(req, timeout=3)
            except Exception as e:
                print(f"[AVVIA] {e}")
        threading.Thread(target=_worker, daemon=True).start()

    def _click_pallet(self, pid):
        pallet = next((p for p in self._pallets if p["id"] == pid), None)
        if not pallet:
            return
        stato = pallet.get("stato", "VUOTO")
        if stato == "IN LAVORAZIONE":
            return  # gestito solo dal log PLC — non modificabile manualmente

        # Menu popup: solo GREZZO e VUOTO come stati manuali
        import tkinter as _tk
        menu = _tk.Menu(self.parent, tearoff=0)

        def _set(nuovo_stato):
            def _save():
                config = _carica_config()
                path = _pallet_path(config)
                if not path:
                    return
                try:
                    if path.exists():
                        data = json.loads(path.read_text(encoding="utf-8"))
                    else:
                        data = {"pallet": [
                            {"numero": i+1, "stato": "vuoto", "programma": None,
                             "main": None, "commessa": None, "aggiornato": None}
                            for i in range(6)
                        ]}
                    for p in data.get("pallet", []):
                        if p.get("numero") == pid:
                            p["stato"]      = nuovo_stato.lower().replace(" ", "_")
                            p["aggiornato"] = datetime.now().isoformat()
                            break
                    data["ultimo_aggiornamento"] = datetime.now().isoformat()
                    path.parent.mkdir(parents=True, exist_ok=True)
                    path.write_text(json.dumps(data, ensure_ascii=False, indent=2),
                                    encoding="utf-8")
                except Exception:
                    pass
                self.parent.after(0, self._fetch_data)
            threading.Thread(target=_save, daemon=True).start()

        # ── Sezione progetto ──────────────────────────────────────────────
        pallet_data = next((p for p in self._pallets if p.get("id") == pid), {})
        proj_nome   = pallet_data.get("progetto_nome") or ""
        proj_id     = pallet_data.get("progetto_id")   or ""

        if proj_nome:
            menu.add_command(
                label=f"📋 Apri: {proj_nome[:28]}",
                command=lambda pi=proj_id: self._apri_progetto(pi)
            )
            menu.add_command(
                label="🔄 Cambia progetto...",
                command=lambda: self._apri_assegna_pallet(pid)
            )
        else:
            menu.add_command(
                label="📋 Assegna progetto...",
                command=lambda: self._apri_assegna_pallet(pid)
            )
        menu.add_separator()

        # ── Sezione stati (4 voci) ─────────────────────────────────────────
        STATI_LABEL = {
            "GREZZO": "🟡 GREZZO",
            "FINITO": "🟢 FINITO",
            "GUASTO": "🔴 GUASTO",
            "VUOTO":  "⬜ VUOTO",
        }
        for s, label in STATI_LABEL.items():
            check = "✓ " if s == stato else "   "
            menu.add_command(
                label=f"{check}{label}",
                command=lambda ns=s: _set(ns)
            )

        # Posizione del menu sotto la card cliccata
        try:
            f = self._pallet_frames[pid]["frame"]
            menu.tk_popup(f.winfo_rootx(), f.winfo_rooty() + f.winfo_height())
        except Exception:
            pass
        finally:
            menu.grab_release()

    def _apri_progetto(self, progetto_id: str):
        """Naviga al progetto nella tab Progetti."""
        if not progetto_id:
            return
        try:
            tab_proj = self.main.tab_progetti
            tab_proj.set_selected_id(progetto_id)
            self.main.tabview.set("📋 Progetti")
        except Exception:
            pass

    def _apri_assegna_pallet(self, pallet_num: int):
        """Apre dialog per assegnare/cambiare progetto al pallet."""
        import tkinter as _tk
        win = _tk.Toplevel(self.parent)
        win.title(f"Assegna progetto — Pallet {pallet_num}")
        win.geometry("440x400")
        win.grab_set()
        win.configure(bg="#F5F4F0")

        import customtkinter as _ctk
        _tk.Label(win, text=f"Seleziona progetto per Pallet {pallet_num}",
                  font=("DM Sans", 12, "bold"), fg="#1A1814", bg="#F5F4F0"
                  ).pack(anchor="w", padx=20, pady=(16,8))

        # Lista progetti
        try:
            from ui.tab_progetti import _load_progetti
            projects = [p for p in _load_progetti() if not p.get("archived")]
        except Exception:
            projects = []

        frame = _ctk.CTkScrollableFrame(win, fg_color="#FFFFFF", corner_radius=8)
        frame.pack(fill="both", expand=True, padx=16, pady=(0,12))

        def _assegna(proj):
            import urllib.request, json as _j
            base = "http://localhost:8000"
            try:
                body = _j.dumps({
                    "progetto_id":     proj["id"],
                    "progetto_nome":   proj.get("name",""),
                    "progetto_colore": proj.get("color","#1D5FAD")
                }).encode()
                req = urllib.request.Request(
                    f"{base}/api/pallet/{pallet_num}/assegna-progetto",
                    data=body, headers={"Content-Type":"application/json"}, method="PATCH")
                urllib.request.urlopen(req, timeout=2)
                # Imposta GREZZO se VUOTO
                r = urllib.request.urlopen(f"{base}/api/pallet/", timeout=2)
                pallets = _j.loads(r.read()).get("pallet", [])
                pal = next((p for p in pallets if p.get("numero")==pallet_num), None)
                if pal and pal.get("stato","vuoto") == "vuoto":
                    body2 = _j.dumps({"stato": "grezzo"}).encode()
                    req2 = urllib.request.Request(
                        f"{base}/api/pallet/{pallet_num}",
                        data=body2, headers={"Content-Type":"application/json"}, method="PATCH")
                    urllib.request.urlopen(req2, timeout=2)
            except urllib.error.HTTPError as he:
                import json as _je
                try:
                    msg = _je.loads(he.read()).get("detail", str(he))
                except Exception:
                    msg = str(he)
                _tk.messagebox.showerror("Errore", msg, parent=win)
                return
            except Exception as e:
                _tk.messagebox.showerror("Errore", str(e), parent=win)
                return
            win.destroy()
            self._fetch_data()

        # Progetti non assegnati ad altri pallet
        pallet_occupati = {}
        try:
            r2 = urllib.request.urlopen(f"{base}/api/pallet/", timeout=2)
            pd = _j.loads(r2.read())
            pallet_occupati = {p["progetto_id"]: p["numero"]
                               for p in pd.get("pallet",[]) if p.get("progetto_id")}
        except Exception:
            pass

        progetti_liberi = [p for p in projects
                           if p["id"] not in pallet_occupati]

        for proj in progetti_liberi:
            row = _tk.Frame(frame, bg="#FFFFFF")
            row.pack(fill="x", pady=1)
            dot = _tk.Frame(row, width=8, height=8, bg=proj.get("color","#1D5FAD"))
            dot.pack(side="left", padx=(8,6), pady=8)
            _tk.Label(row, text=proj.get("name","?"),
                      font=("DM Sans",11,"bold"), fg="#1A1814", bg="#FFFFFF",
                      anchor="w").pack(side="left", fill="x", expand=True)
            _ctk.CTkButton(row, text="Assegna", width=80, height=26,
                           fg_color="#1D5FAD", corner_radius=5,
                           command=lambda p=proj: _assegna(p)).pack(side="right", padx=8, pady=4)

        if not projects:
            _tk.Label(frame, text="Nessun progetto attivo",
                      font=("DM Sans",11), fg="#9A978E", bg="#FFFFFF").pack(pady=20)

    def refresh(self):
        if self._after_id:
            self.parent.after_cancel(self._after_id)
            self._after_id = None
        self._fetch_data()

    def destroy_polling(self):
        if self._after_id:
            self.parent.after_cancel(self._after_id)
            self._after_id = None
