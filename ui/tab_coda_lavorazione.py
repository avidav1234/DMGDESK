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

        self._pallet_frames = {}
        self._pallet_labels = {}
        for i, pid in enumerate([1,2,3,4,5,6]):
            row, col = divmod(i, 2)
            f = tk.Frame(grid, relief="flat", bd=0,
                         width=155, height=115, cursor="hand2")
            f.grid(row=row, column=col, padx=5, pady=5)
            f.pack_propagate(False)
            f.bind("<Button-1>", lambda e, p=pid: self._click_pallet(p))

            # Contenuto del frame
            top = tk.Frame(f, bd=0)
            top.place(x=10, y=8, width=135, height=30)
            lbl_num = tk.Label(top, text=f"P{pid}", font=("Helvetica", 22, "bold"), bd=0)
            lbl_num.pack(side="left")
            lbl_dot = tk.Label(top, text="●", font=("Helvetica", 9), bd=0)
            lbl_dot.pack(side="right", padx=2)

            lbl_stato = tk.Label(f, text="VUOTO",
                                  font=("Helvetica", 9, "bold"), bd=0,
                                  anchor="w")
            lbl_stato.place(x=10, y=88, width=135, height=14)

            lbl_prog = tk.Label(f, text="",
                                 font=("Helvetica", 8), bd=0,
                                 anchor="w")
            lbl_prog.place(x=10, y=100, width=135, height=12)

            for w in [f, top, lbl_num, lbl_dot, lbl_stato, lbl_prog]:
                w.bind("<Button-1>", lambda e, p=pid: self._click_pallet(p))

            self._pallet_frames[pid] = {
                "frame": f, "lbl_num": lbl_num, "lbl_dot": lbl_dot,
                "lbl_stato": lbl_stato, "lbl_prog": lbl_prog
            }

        # ── Pannello stato macchina (destra) ──────────────────────────────
        col_dx = ctk.CTkFrame(body, fg_color="transparent")
        col_dx.pack(side="left", fill="both", expand=True)

        # Card stato macchina
        self.card_stato = ctk.CTkFrame(col_dx, fg_color="#f8fafc",
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
        self.card_prog = ctk.CTkFrame(col_dx, fg_color="white",
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
        self.card_utensile = ctk.CTkFrame(col_dx, fg_color="white",
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
        self.card_allarme = ctk.CTkFrame(col_dx, fg_color="#fef2f2",
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
        self.card_errore = ctk.CTkFrame(col_dx, fg_color="#fef3c7",
                                         corner_radius=8, border_width=1,
                                         border_color="#fcd34d")
        self.lbl_errore = ctk.CTkLabel(self.card_errore, text="",
                                        font=get_font("small"),
                                        text_color="#92400e")
        self.lbl_errore.pack(padx=12, pady=6)

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
                            "FINITO": "FINITO", "GUASTO": "GUASTO"
                        }
                        pallets[pid-1]["stato"]    = stato_map.get(stato_raw, "VUOTO")
                        pallets[pid-1]["programma"] = p_saved.get("programma")
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

        self._schedule_next()

    def _update_pallet_card(self, pallet, pallet_attivo_mac):
        pid    = pallet["id"]
        stato  = pallet.get("stato", "VUOTO")
        prog   = pallet.get("programma") or ""
        colors = STATI_COLORS.get(stato, STATI_COLORS["VUOTO"])
        is_active = (pallet_attivo_mac == pid)

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

        widgets["lbl_num"].configure(
            bg=colors["bg"], fg=colors["fg"])
        widgets["lbl_stato"].configure(
            text=stato, bg=colors["bg"], fg=colors["fg"])

        prog_display = prog
        if prog and len(prog) > 20:
            # Estrai solo la parte finale dopo l'ultimo /
            prog_display = prog.split("/")[-1].replace("_N_", "").replace("_MPF", "")
        widgets["lbl_prog"].configure(
            text=prog_display, bg=colors["bg"], fg=colors["fg"])

        # Dot indicatore attivo
        dot = widgets["lbl_dot"]
        if is_active:
            dot.configure(text="●", fg="#f59e0b", bg=colors["bg"])
        else:
            dot.configure(text="", bg=colors["bg"])

    # ── Click pallet ─────────────────────────────────────────────────────────

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

        # Solo gli stati manuali — IN LAVORAZIONE viene dal PLC
        for s in ["GREZZO", "VUOTO"]:
            label = f"{'✓ ' if s == stato else '   '}{s}"
            menu.add_command(label=label, command=lambda ns=s: _set(ns))

        # Posizione del menu sotto la card cliccata
        try:
            f = self._pallet_frames[pid]["frame"]
            menu.tk_popup(f.winfo_rootx(), f.winfo_rooty() + f.winfo_height())
        except Exception:
            pass
        finally:
            menu.grab_release()

    def refresh(self):
        if self._after_id:
            self.parent.after_cancel(self._after_id)
            self._after_id = None
        self._fetch_data()

    def destroy_polling(self):
        if self._after_id:
            self.parent.after_cancel(self._after_id)
            self._after_id = None
