"""
Tab In Macchina - V16
Sync TOA/TMA + Tabella utensili + Confronto MPF
Allineato con Macchina.jsx della web app.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
import json, os, threading, sys, re
from datetime import datetime
from pathlib import Path

from config.theme import *
from config.constants import *
from logic.nc_analyzer import estrai_tutti_utensili_da_file

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.toa_parser import parse_toa, parse_tma


# ── Helpers config/TOA ────────────────────────────────────────────────────────

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


def _salva_config(cfg: dict):
    try:
        config_path = os.path.join(_get_base_dir(), "config.json")
        with open(config_path, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2, ensure_ascii=False)
    except Exception as e:
        messagebox.showwarning("Config", f"Impossibile salvare config.json:\n{e}")


def _get_tools_db_path() -> Path:
    config = _carica_config()
    folder = config.get("tools_toa_folder", "").strip()
    if not folder:
        db_path = config.get("database_path", "").strip()
        if db_path:
            folder = str(Path(db_path).parent)
    if not folder:
        folder = "."
    return Path(folder) / "tools_machine.json"


def _get_sync_paths():
    config = _carica_config()
    folder = config.get("tools_toa_folder", "").strip()
    if not folder:
        percorso_nc = config.get("percorso_nc_base", "")
        if percorso_nc:
            parts = Path(percorso_nc).parts
            if len(parts) >= 2:
                folder = str(Path(parts[0]) / parts[1])
    if not folder:
        return None, None
    base = Path(folder)
    return base / "TOOL_SYNC.TOA", base / "TOOL_SYNC.TMA"


def _save_tools_db(tools, sync_time, positions=None):
    db_path = _get_tools_db_path()
    pos_map = {}
    if positions:
        for pos in positions:
            pos_map[pos.tool_id] = {"magazine": pos.magazine, "position": pos.position}
    data = {
        "sync_time": sync_time,
        "tools": {
            str(tid): {
                "tool_id":      t.tool_id,
                "name":         t.name,
                "duplo":        t.duplo,
                "status":       t.status,
                "monitoring":   t.monitoring,
                "length":       t.main_length,
                "radius":       t.main_radius,
                "life_percent": t.life_percent,
                "is_enabled":   t.is_enabled,
                "is_worn":      t.is_worn,
                "magazine":     pos_map.get(tid, {}).get("magazine"),
                "position":     pos_map.get(tid, {}).get("position"),
            }
            for tid, t in tools.items() if t.name
        }
    }
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with open(db_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return data


def _load_tools_db():
    db_path = _get_tools_db_path()
    if not db_path.exists():
        return {}, None
    try:
        with open(db_path, encoding="utf-8") as f:
            data = json.load(f)
        return data.get("tools", {}), data.get("sync_time")
    except Exception:
        return {}, None


def _estrai_utensili_da_file_mpf(filepath: str) -> set:
    """Estrae alias utensili da file MPF (T='alias' + M6)."""
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            testo = f.read()
    except Exception:
        return set()
    pattern = re.compile(r'T\s*=\s*["\']?([A-Z0-9.\-_\s]+)["\']?', re.IGNORECASE)
    righe = testo.splitlines()
    risultati = set()
    last_alias = None
    last_idx = -1
    for i, riga in enumerate(righe):
        riga_up = riga.strip().upper()
        m = pattern.search(riga_up)
        if m:
            alias = m.group(1).strip()
            if alias:
                last_alias = alias
                last_idx = i
        if last_alias and (i - last_idx) < 5:
            if "M6" in riga_up.replace("M06", "M6"):
                risultati.add(last_alias.upper())
                last_alias = None
    return risultati


def _confronta_utensili(alias_richiesti: set, tools_db: dict) -> dict:
    """Confronta alias richiesti con DB utensili in macchina."""
    alias_in_macchina = {t["name"].upper() for t in tools_db.values() if t.get("name")}
    alias_abilitati = {
        t["name"].upper() for t in tools_db.values()
        if t.get("name") and t.get("is_enabled", True) and not t.get("is_worn", False)
    }
    alias_vita_bassa = {
        t["name"].upper() for t in tools_db.values()
        if t.get("name") and t.get("life_percent") is not None
        and t["life_percent"] < 10 and t.get("is_enabled", True)
    }
    missing  = sorted(alias_richiesti - alias_in_macchina)
    disabled = sorted(alias_richiesti & (alias_in_macchina - alias_abilitati))
    worn     = sorted((alias_richiesti & alias_vita_bassa) - set(disabled))
    ok       = sorted(alias_richiesti - set(missing) - set(disabled) - set(worn))
    return {
        "ok": ok, "missing": missing, "disabled": disabled, "worn": worn,
        "total_required": len(alias_richiesti),
        "can_run": not missing and not disabled,
    }


# ── Dialog Impostazioni ───────────────────────────────────────────────────────

class _DialogImpostazioni(ctk.CTkToplevel):
    def __init__(self, parent, on_saved):
        super().__init__(parent)
        self.title("Impostazioni — Cartella TOA/TMA")
        self.geometry("560x220")
        self.resizable(False, False)
        self.grab_set()
        self._on_saved = on_saved

        config = _carica_config()
        folder = config.get("tools_toa_folder", "").strip()
        if not folder:
            db_path = config.get("database_path", "").strip()
            if db_path:
                folder = str(Path(db_path).parent)

        pad = {"padx": 20, "pady": 8}
        ctk.CTkLabel(self, text="Cartella contenente i file TOA/TMA e tools_machine.json:",
                     font=get_font("body")).pack(anchor="w", **pad)

        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=20)
        self.entry = ctk.CTkEntry(row, height=36, font=get_font("body"))
        self.entry.pack(side="left", fill="x", expand=True, padx=(0, 8))
        if folder:
            self.entry.insert(0, folder)
        ctk.CTkButton(row, text="📂", width=40, height=36,
                      fg_color="#5C6BC0", hover_color="#3949AB",
                      command=self._sfoglia).pack(side="left")

        ctk.CTkLabel(self, text="Es: P:\\DMG_DMC_160U",
                     font=get_font("small"), text_color=COLOR_TEXT_SECONDARY).pack(anchor="w", padx=20)

        btns = ctk.CTkFrame(self, fg_color="transparent")
        btns.pack(fill="x", padx=20, pady=(16, 10))
        ctk.CTkButton(btns, text="✔ Salva e ricarica DB",
                      command=self._salva, fg_color="#43A047", hover_color="#2E7D32",
                      font=get_font("medium", bold=True), height=38).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btns, text="↺ Solo ricarica DB",
                      command=self._ricarica, fg_color="#607D8B", hover_color="#455A64",
                      font=get_font("medium"), height=38).pack(side="left", padx=(0, 10))
        ctk.CTkButton(btns, text="Annulla",
                      command=self.destroy, fg_color="#9E9E9E", hover_color="#757575",
                      font=get_font("medium"), height=38).pack(side="right")

    def _sfoglia(self):
        folder = filedialog.askdirectory(title="Seleziona cartella TOA/TMA",
                                         initialdir=self.entry.get() or "P:\\")
        if folder:
            self.entry.delete(0, "end")
            self.entry.insert(0, folder)

    def _salva(self):
        folder = self.entry.get().strip()
        if not folder:
            messagebox.showwarning("Attenzione", "Inserisci una cartella.", parent=self)
            return
        if not os.path.isdir(folder):
            if not messagebox.askyesno("Cartella non trovata",
                    f"La cartella non esiste:\n{folder}\n\nSalvare comunque?", parent=self):
                return
        cfg = _carica_config()
        cfg["tools_toa_folder"] = folder
        _salva_config(cfg)
        self.destroy()
        self._on_saved()

    def _ricarica(self):
        self.destroy()
        self._on_saved()


# ── Tab ──────────────────────────────────────────────────────────────────────

class TabMacchina:
    """Tab In Macchina V16 — Sync TOA/TMA + Confronto MPF + Tabella utensili."""

    def __init__(self, parent, main_window):
        self.parent       = parent
        self.main         = main_window
        self._tools_data  = {}
        self._sync_time   = None
        self._mpf_files   = []   # lista path MPF caricati per confronto
        self._check_result = None
        self._create_ui()
        self._load_existing_db()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _create_ui(self):
        # Header
        header = ctk.CTkFrame(self.parent, fg_color=COLOR_PRIMARY, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="IN MACCHINA  — V16",
                     font=get_font("title", bold=True), text_color="white").pack(pady=(12, 2))
        ctk.CTkLabel(header, text="Sync TOA/TMA  |  Confronto MPF  |  Tabella utensili",
                     font=get_font("body"), text_color="#E8F5E9").pack(pady=(0, 8))

        # Toolbar principale
        toolbar = ctk.CTkFrame(self.parent, fg_color="transparent")
        toolbar.pack(fill="x", padx=8, pady=(8, 4))

        # Sinistra: MPF (azione primaria)
        self.btn_mpf = ctk.CTkButton(
            toolbar, text="+ Aggiungi MPF",
            command=self._aggiungi_mpf,
            fg_color=COLOR_PRIMARY, hover_color="#1A237E",
            font=get_font("medium", bold=True), height=40, corner_radius=6)
        self.btn_mpf.pack(side="left", padx=4)

        self.btn_reset_mpf = ctk.CTkButton(
            toolbar, text="Reset",
            command=self._reset_mpf,
            fg_color="#607D8B", hover_color="#455A64",
            font=get_font("small"), height=40, width=70, corner_radius=6)
        self.btn_reset_mpf.pack(side="left", padx=2)

        self.lbl_mpf_count = ctk.CTkLabel(
            toolbar, text="", font=get_font("small"), text_color="#1565C0")
        self.lbl_mpf_count.pack(side="left", padx=6)

        # Destra: sync + impostazioni
        ctk.CTkButton(toolbar, text="⚙ Impostazioni",
                      command=self._apri_impostazioni,
                      fg_color="#5C6BC0", hover_color="#3949AB",
                      font=get_font("small"), height=36, width=120,
                      corner_radius=6).pack(side="right", padx=4)

        ctk.CTkButton(toolbar, text="TOA manuale",
                      command=self._scegli_toa_manuale,
                      fg_color="#607D8B", hover_color="#455A64",
                      font=get_font("small"), height=36, width=110,
                      corner_radius=6).pack(side="right", padx=3)

        self.btn_sync = ctk.CTkButton(
            toolbar, text="↻ Sync macchina",
            command=self._do_sync,
            fg_color="#607D8B", hover_color="#455A64",
            font=get_font("small"), height=36, width=130, corner_radius=6)
        self.btn_sync.pack(side="right", padx=3)

        self.lbl_sync_status = ctk.CTkLabel(
            toolbar, text="Nessun sync",
            font=get_font("small"), text_color=COLOR_TEXT_SECONDARY)
        self.lbl_sync_status.pack(side="right", padx=8)

        # Istruzioni primo sync
        self.frame_istruzioni = ctk.CTkFrame(self.parent, fg_color="#E3F2FD", corner_radius=8)
        self.frame_istruzioni.pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkLabel(self.frame_istruzioni,
                     text=("Prima sincronizzazione: "
                           "HMI → Servizi → Salva Attrezzaggio → Z:\\DMG_DMC_160U\\TOOL_SYNC  "
                           "poi premi  ↻ Sync macchina  oppure  TOA manuale"),
                     font=get_font("small"), text_color=COLOR_PRIMARY, justify="left",
                     ).pack(padx=12, pady=6, anchor="w")

        # Frame lista file MPF caricati
        self.frame_mpf_list = ctk.CTkFrame(self.parent, fg_color="#F5F5F5", corner_radius=6)
        self.lbl_mpf_list = ctk.CTkLabel(
            self.frame_mpf_list, text="",
            font=get_font("small"), text_color=COLOR_TEXT_SECONDARY,
            justify="left", anchor="w")
        self.lbl_mpf_list.pack(padx=10, pady=4, anchor="w")

        # Frame risultati confronto
        self.frame_check = ctk.CTkFrame(self.parent, fg_color=COLOR_SURFACE, corner_radius=8)

        # Banner can_run
        self.frame_banner = ctk.CTkFrame(self.frame_check, fg_color="transparent")
        self.frame_banner.pack(fill="x", padx=8, pady=(8, 4))
        self.lbl_banner = ctk.CTkLabel(
            self.frame_banner, text="",
            font=get_font("medium", bold=True))
        self.lbl_banner.pack(side="left", padx=8)
        self.lbl_totale = ctk.CTkLabel(
            self.frame_banner, text="",
            font=get_font("small"), text_color=COLOR_TEXT_SECONDARY)
        self.lbl_totale.pack(side="left", padx=4)

        # Gruppi badge per categoria
        self._frames_categorie = {}
        for key, label in [
            ("missing",  "MANCANTI"),
            ("disabled", "DISABILITATI"),
            ("worn",     "VITA < 10%"),
            ("ok",       "DISPONIBILI"),
        ]:
            f = ctk.CTkFrame(self.frame_check, fg_color="transparent")
            lbl_header = ctk.CTkLabel(f, text=label, font=get_font("small", bold=True))
            lbl_header.pack(anchor="w", padx=8)
            lbl_badges = ctk.CTkLabel(f, text="", font=get_font("small"),
                                       anchor="w", justify="left", wraplength=700)
            lbl_badges.pack(anchor="w", padx=8, pady=(0, 4))
            self._frames_categorie[key] = (f, lbl_header, lbl_badges)

        # Separatore + tabella utensili
        sep_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        sep_frame.pack(fill="x", padx=8, pady=(4, 2))

        ctrl = ctk.CTkFrame(sep_frame, fg_color="transparent")
        ctrl.pack(fill="x")
        self.entry_search = ctk.CTkEntry(ctrl, placeholder_text="Cerca utensile...",
                                          font=get_font("body"), width=260)
        self.entry_search.pack(side="left", padx=4)
        self.entry_search.bind("<KeyRelease>", lambda e: self._refresh_sync_table())
        self.lbl_count = ctk.CTkLabel(ctrl, text="",
                                       font=get_font("small"), text_color=COLOR_TEXT_SECONDARY)
        self.lbl_count.pack(side="right", padx=8)

        tbl = ctk.CTkFrame(self.parent, fg_color=COLOR_SURFACE, corner_radius=8)
        tbl.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        cols = ("pos", "name", "duplo", "length", "radius", "life", "status")
        self.tree_sync = ttk.Treeview(tbl, columns=cols, show="headings")
        for col, label, w in [
            ("pos",    "Pos",           68),
            ("name",   "Nome utensile", 220),
            ("duplo",  "Duplo",         55),
            ("length", "L (mm)",        90),
            ("radius", "R (mm)",        80),
            ("life",   "Vita %",        75),
            ("status", "Stato",         90)]:
            self.tree_sync.heading(col, text=label, anchor="w")
            self.tree_sync.column(col, width=w, minwidth=40, anchor="w")

        self.tree_sync.tag_configure("ok",       background="#F1F8E9")
        self.tree_sync.tag_configure("worn",     background="#EDE7F6")
        self.tree_sync.tag_configure("disabled", background="#FFEBEE")
        self.tree_sync.tag_configure("highlight",background="#FFF9C4")

        sb2 = ttk.Scrollbar(tbl, orient="vertical", command=self.tree_sync.yview)
        self.tree_sync.configure(yscrollcommand=sb2.set)
        self.tree_sync.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=6)
        sb2.pack(side="right", fill="y", pady=6, padx=(0, 4))

    # ── Confronto MPF ────────────────────────────────────────────────────────

    def _aggiungi_mpf(self):
        paths = filedialog.askopenfilenames(
            title="Seleziona file MPF da confrontare",
            filetypes=[("Programmi MPF", "*.MPF *.mpf *.nc *.spf"), ("Tutti", "*.*")])
        if not paths:
            return
        # Aggiungi solo file non già presenti
        for p in paths:
            if p not in self._mpf_files:
                self._mpf_files.append(p)
        self._aggiorna_lista_mpf()
        self._esegui_confronto()

    def _reset_mpf(self):
        self._mpf_files = []
        self._check_result = None
        self._aggiorna_lista_mpf()
        self._aggiorna_risultati_confronto(None)
        self._refresh_sync_table()

    def _aggiorna_lista_mpf(self):
        if not self._mpf_files:
            self.frame_mpf_list.pack_forget()
            self.lbl_mpf_count.configure(text="")
        else:
            nomi = "  ".join(f"{i+1}. {Path(p).name}" for i, p in enumerate(self._mpf_files))
            self.lbl_mpf_list.configure(text=nomi)
            self.frame_mpf_list.pack(fill="x", padx=8, pady=(0, 4))
            self.lbl_mpf_count.configure(
                text=f"{len(self._mpf_files)} file caricati")

    def _esegui_confronto(self):
        if not self._mpf_files or not self._tools_data:
            return
        # Aggrega alias da tutti i file
        alias_totali = set()
        for fp in self._mpf_files:
            alias_totali |= _estrai_utensili_da_file_mpf(fp)

        if not alias_totali:
            self._aggiorna_risultati_confronto({
                "ok": [], "missing": [], "disabled": [], "worn": [],
                "total_required": 0, "can_run": True})
            return

        result = _confronta_utensili(alias_totali, self._tools_data)
        self._check_result = result
        self._aggiorna_risultati_confronto(result)
        self._refresh_sync_table()

    def _aggiorna_risultati_confronto(self, result):
        COLORI = {
            "missing":  ("#B71C1C", "#FFEBEE"),
            "disabled": ("#E65100", "#FFF3E0"),
            "worn":     ("#4527A0", "#EDE7F6"),
            "ok":       ("#1B5E20", "#F1F8E9"),
        }
        LABELS = {
            "missing": "MANCANTI", "disabled": "DISABILITATI",
            "worn": "VITA < 10%", "ok": "DISPONIBILI",
        }

        if result is None:
            self.frame_check.pack_forget()
            return

        self.frame_check.pack(fill="x", padx=8, pady=(0, 4))

        # Banner can_run
        if result["can_run"]:
            self.lbl_banner.configure(
                text="✅  Tutti gli utensili disponibili",
                text_color="#1B5E20")
        else:
            self.lbl_banner.configure(
                text="❌  Utensili mancanti o non disponibili",
                text_color="#B71C1C")
        self.lbl_totale.configure(
            text=f"{result['total_required']} utensili richiesti")

        # Gruppi per categoria
        for key, (frame, lbl_header, lbl_badges) in self._frames_categorie.items():
            lista = result.get(key, [])
            if not lista:
                frame.pack_forget()
                continue
            fg, bg = COLORI[key]
            lbl_header.configure(text=LABELS[key], text_color=fg)
            lbl_badges.configure(text="  ".join(lista), text_color=fg)
            frame.pack(fill="x", padx=8, pady=(0, 2))

    # ── Impostazioni ─────────────────────────────────────────────────────────

    def _apri_impostazioni(self):
        _DialogImpostazioni(self.parent, on_saved=self._load_existing_db)

    # ── Sync ─────────────────────────────────────────────────────────────────

    def _do_sync(self):
        toa_path, _ = _get_sync_paths()
        if toa_path is None:
            messagebox.showerror("Configurazione mancante",
                "Percorso share non configurato.\n"
                "Usa ⚙ Impostazioni per configurare la cartella TOA.")
            return
        if not toa_path.exists():
            messagebox.showerror("File non trovato",
                "File TOA non trovato:\n" + str(toa_path) + "\n\n"
                "Generare da HMI → Servizi → Salva Attrezzaggio")
            return
        self._esegui_sync(Path(toa_path))

    def _scegli_toa_manuale(self):
        path = filedialog.askopenfilename(
            title="Seleziona file TOA",
            filetypes=[("Tool Offset Archive", "*.toa *.TOA"), ("Tutti", "*.*")])
        if path:
            self._esegui_sync(Path(path))

    def _esegui_sync(self, toa_path):
        self.btn_sync.configure(state="disabled", text="Sync...")
        def _worker():
            try:
                tools = parse_toa(toa_path)
                magazines, positions, tma_warning = {}, [], None
                for suffix in (".TMA", ".tma", ".Tma"):
                    candidate = toa_path.with_suffix(suffix)
                    if candidate.exists():
                        try:
                            result_tma = parse_tma(candidate)
                            # parse_tma può restituire (magazines, positions) o solo [positions]
                            if isinstance(result_tma, tuple):
                                magazines, positions = result_tma
                            else:
                                magazines, positions = {}, result_tma
                            if not positions:
                                tma_warning = "TMA vuoto"
                        except Exception as ex:
                            tma_warning = "Errore TMA: " + str(ex)
                        break
                else:
                    tma_warning = "TMA non trovato"
                sync_time = datetime.now().isoformat()
                _save_tools_db(tools, sync_time, positions)
                n = sum(1 for t in tools.values() if t.name)
                self.parent.after(0, lambda: self._after_sync(n, len(positions), sync_time, tma_warning))
            except Exception as ex:
                msg = str(ex)
                self.parent.after(0, lambda: self._sync_error(msg))
        threading.Thread(target=_worker, daemon=True).start()

    def _after_sync(self, n_tools, n_pos, sync_time, tma_warning=None):
        self.btn_sync.configure(state="normal", text="↻ Sync macchina")
        self._load_existing_db()
        # Riesegui confronto se ci sono file MPF caricati
        if self._mpf_files:
            self._esegui_confronto()
        lines = [f"{n_tools} utensili", f"{n_pos} posizioni mappate"]
        if tma_warning:
            lines.append("Attenzione TMA: " + tma_warning)
        messagebox.showinfo("Sync completato", "\n".join(lines))

    def _sync_error(self, msg):
        self.btn_sync.configure(state="normal", text="↻ Sync macchina")
        messagebox.showerror("Errore sync", msg)

    def _load_existing_db(self):
        self._tools_data, self._sync_time = _load_tools_db()
        if self._sync_time:
            dt = datetime.fromisoformat(self._sync_time)
            self.lbl_sync_status.configure(
                text="Sync: " + dt.strftime("%d/%m/%Y %H:%M") + "  " + str(len(self._tools_data)) + " ut.",
                text_color=COLOR_SUCCESS)
            self.frame_istruzioni.pack_forget()
        else:
            config = _carica_config()
            folder = config.get("tools_toa_folder", "non configurata")
            self.lbl_sync_status.configure(
                text="Nessun sync  (cartella: " + folder + ")",
                text_color="#F57C00")
        self._refresh_sync_table()

    # ── Tabella utensili ─────────────────────────────────────────────────────

    def _refresh_sync_table(self):
        search = self.entry_search.get().strip().lower()

        # Alias da evidenziare (risultati confronto MPF)
        alias_ok       = set(self._check_result["ok"])       if self._check_result else set()
        alias_missing  = set(self._check_result["missing"])  if self._check_result else set()
        alias_disabled = set(self._check_result["disabled"]) if self._check_result else set()
        alias_worn     = set(self._check_result["worn"])      if self._check_result else set()
        alias_usati    = alias_ok | alias_missing | alias_disabled | alias_worn

        self.tree_sync.delete(*self.tree_sync.get_children())
        filtered = [t for t in self._tools_data.values()
                    if not search or search in t["name"].lower()]
        filtered.sort(key=lambda t: (
            t.get("magazine") or 9999, t.get("position") or 9999,
            t["name"], t["duplo"]))

        for t in filtered:
            life      = t.get("life_percent")
            life_str  = (str(round(life)) + "%") if life is not None else "-"
            is_dis    = not t.get("is_enabled", True) or t.get("is_worn", False)
            is_worn   = life is not None and life < 10
            nome_up   = t["name"].upper()

            if nome_up in alias_missing:
                tag, stato = "disabled", "MANCANTE"
            elif nome_up in alias_disabled:
                tag, stato = "disabled", "DISAB."
            elif nome_up in alias_worn:
                tag, stato = "worn", "VITA BASSA"
            elif nome_up in alias_ok:
                tag, stato = "highlight", "OK (usato)"
            elif is_dis:
                tag, stato = "disabled", "DISAB."
            elif is_worn:
                tag, stato = "worn", "VITA BASSA"
            else:
                tag, stato = "ok", "OK"

            mag = t.get("magazine"); pos = t.get("position")
            pos_str = ("M" + str(mag) + "." + str(pos).zfill(3)
                       if mag is not None and pos is not None else "-")
            self.tree_sync.insert("", "end", values=(
                pos_str, t["name"], "#" + str(t["duplo"]),
                str(round(t.get("length", 0), 3)),
                str(round(t.get("radius", 0), 3)),
                life_str, stato), tags=(tag,))

        self.lbl_count.configure(
            text=str(len(filtered)) + " / " + str(len(self._tools_data)) + " utensili")

    def refresh(self):
        self._load_existing_db()
