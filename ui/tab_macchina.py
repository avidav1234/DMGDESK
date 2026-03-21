"""
Tab In Macchina - Tool Manager V16
Solo Sync TOA/TMA + Tabella utensili. Nessun DB manuale, nessun carica MPF.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
import json, os, threading, sys
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


# ── Dialog Impostazioni ───────────────────────────────────────────────────────

class _DialogImpostazioni(ctk.CTkToplevel):
    """Dialog modale: cartella TOA + ricarica DB."""

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
                      command=self._salva,
                      fg_color="#43A047", hover_color="#2E7D32",
                      font=get_font("medium", bold=True), height=38).pack(side="left", padx=(0, 10))

        ctk.CTkButton(btns, text="↺ Solo ricarica DB",
                      command=self._ricarica,
                      fg_color="#607D8B", hover_color="#455A64",
                      font=get_font("medium"), height=38).pack(side="left", padx=(0, 10))

        ctk.CTkButton(btns, text="Annulla",
                      command=self.destroy,
                      fg_color="#9E9E9E", hover_color="#757575",
                      font=get_font("medium"), height=38).pack(side="right")

    def _sfoglia(self):
        folder = filedialog.askdirectory(
            title="Seleziona cartella TOA/TMA",
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
    """Tab In Macchina V16 — Sync TOA/TMA + Tabella utensili."""

    def __init__(self, parent, main_window):
        self.parent      = parent
        self.main        = main_window
        self._tools_data = {}
        self._sync_time  = None
        self._create_ui()
        self._load_existing_db()

    # ── UI ───────────────────────────────────────────────────────────────────

    def _create_ui(self):
        import tkinter as tk

        # Header
        header = ctk.CTkFrame(self.parent, fg_color=COLOR_PRIMARY, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="IN MACCHINA  — V16",
                     font=get_font("title", bold=True), text_color="white").pack(pady=(12, 2))
        ctk.CTkLabel(header, text="Sync TOA/TMA  |  Tabella utensili",
                     font=get_font("body"), text_color="#E8F5E9").pack(pady=(0, 8))

        # Toolbar
        toolbar = ctk.CTkFrame(self.parent, fg_color="transparent")
        toolbar.pack(fill="x", padx=8, pady=(8, 4))

        # DESTRA — sync + impostazioni
        ctk.CTkButton(toolbar, text="⚙ Impostazioni",
                      command=self._apri_impostazioni,
                      fg_color="#5C6BC0", hover_color="#3949AB",
                      font=get_font("small"), height=36, width=130,
                      corner_radius=6).pack(side="right", padx=4)

        ctk.CTkButton(toolbar, text="TOA manuale",
                      command=self._scegli_toa_manuale,
                      fg_color="#607D8B", hover_color="#455A64",
                      font=get_font("small"), height=36, width=110,
                      corner_radius=6).pack(side="right", padx=3)

        self.btn_sync = ctk.CTkButton(toolbar, text="Sync macchina",
                                       command=self._do_sync,
                                       fg_color="#607D8B", hover_color="#455A64",
                                       font=get_font("small"), height=36, width=130,
                                       corner_radius=6)
        self.btn_sync.pack(side="right", padx=3)

        # SINISTRA — stato sync
        self.lbl_sync_status = ctk.CTkLabel(toolbar, text="Nessun sync",
                                             font=get_font("small"),
                                             text_color=COLOR_TEXT_SECONDARY)
        self.lbl_sync_status.pack(side="left", padx=8)

        # Istruzioni primo sync
        self.frame_istruzioni = ctk.CTkFrame(self.parent, fg_color="#E3F2FD", corner_radius=8)
        self.frame_istruzioni.pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkLabel(self.frame_istruzioni,
                     text=("Prima sincronizzazione: "
                           "HMI → Servizi → Salva Attrezzaggio → Z:\\DMG_DMC_160U\\TOOL_SYNC  "
                           "poi premi  Sync macchina  oppure  TOA manuale"),
                     font=get_font("small"), text_color=COLOR_PRIMARY, justify="left",
                     ).pack(padx=12, pady=6, anchor="w")

        # Tabella utensili
        bot = ctk.CTkFrame(self.parent, fg_color="transparent")
        bot.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        ctrl = ctk.CTkFrame(bot, fg_color="transparent")
        ctrl.pack(fill="x", pady=(4, 2))
        self.entry_search = ctk.CTkEntry(ctrl, placeholder_text="Cerca utensile...",
                                          font=get_font("body"), width=260)
        self.entry_search.pack(side="left", padx=4)
        self.entry_search.bind("<KeyRelease>", lambda e: self._refresh_sync_table())
        self.lbl_count = ctk.CTkLabel(ctrl, text="",
                                       font=get_font("small"), text_color=COLOR_TEXT_SECONDARY)
        self.lbl_count.pack(side="right", padx=8)

        tbl = ctk.CTkFrame(bot, fg_color=COLOR_SURFACE, corner_radius=8)
        tbl.pack(fill="both", expand=True)
        cols = ("pos", "name", "duplo", "length", "radius", "life", "status")
        self.tree_sync = ttk.Treeview(tbl, columns=cols, show="headings")
        for col, label, w in [
            ("pos",    "Pos",            68),
            ("name",   "Nome utensile", 220),
            ("duplo",  "Duplo",          55),
            ("length", "L (mm)",         90),
            ("radius", "R (mm)",         80),
            ("life",   "Vita %",         75),
            ("status", "Stato",          90)]:
            self.tree_sync.heading(col, text=label, anchor="w")
            self.tree_sync.column(col, width=w, minwidth=40, anchor="w")
        self.tree_sync.tag_configure("ok",       background="#F1F8E9")
        self.tree_sync.tag_configure("worn",     background="#EDE7F6")
        self.tree_sync.tag_configure("disabled", background="#FFEBEE")
        sb2 = ttk.Scrollbar(tbl, orient="vertical", command=self.tree_sync.yview)
        self.tree_sync.configure(yscrollcommand=sb2.set)
        self.tree_sync.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=6)
        sb2.pack(side="right", fill="y", pady=6, padx=(0, 4))

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
                            magazines, positions = parse_tma(candidate)
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
        self.btn_sync.configure(state="normal", text="Sync macchina")
        self._load_existing_db()
        lines = [str(n_tools) + " utensili", str(n_pos) + " posizioni mappate"]
        if tma_warning:
            lines.append("Attenzione TMA: " + tma_warning)
        messagebox.showinfo("Sync completato", chr(10).join(lines))

    def _sync_error(self, msg):
        self.btn_sync.configure(state="normal", text="Sync macchina")
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
        self.tree_sync.delete(*self.tree_sync.get_children())
        filtered = [t for t in self._tools_data.values()
                    if not search or search in t["name"].lower()]
        filtered.sort(key=lambda t: (
            t.get("magazine") or 9999, t.get("position") or 9999,
            t["name"], t["duplo"]))
        for t in filtered:
            life     = t.get("life_percent")
            life_str = (str(round(life)) + "%") if life is not None else "-"
            is_dis   = not t.get("is_enabled", True) or t.get("is_worn", False)
            is_worn  = life is not None and life < 10
            if is_dis:    tag, stato = "disabled", "DISAB."
            elif is_worn: tag, stato = "worn",     "VITA BASSA"
            else:         tag, stato = "ok",       "OK"
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
