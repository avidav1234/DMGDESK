"""
Tab In Macchina - Tool Manager V16
Solo Sync TOA/TMA + Confronto multi-MPF. Nessun DB manuale.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
import json, os, threading
from datetime import datetime
from pathlib import Path

from config.theme import *
from config.constants import *
from database.db_handler import carica_configurazione
from logic.nc_analyzer import estrai_tutti_utensili_da_file

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.toa_parser import parse_toa, parse_tma


# ── Helpers TOA/TMA ──────────────────────────────────────────────────────────

def _get_tools_db_path():
    config = carica_configurazione()
    db_path = config.get("database_path", ".")
    return Path(db_path).parent / "tools_machine.json"


def _get_sync_paths():
    config = carica_configurazione()
    radice = config.get("radice", "")
    if not radice:
        percorso_nc = config.get("percorso_nc_base", "")
        if percorso_nc:
            parts = Path(percorso_nc).parts
            if len(parts) >= 2:
                radice = str(Path(parts[0]) / parts[1])
    if not radice:
        return None, None
    base = Path(radice)
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
    with open(db_path, encoding="utf-8") as f:
        data = json.load(f)
    return data.get("tools", {}), data.get("sync_time")


# ── Tab ──────────────────────────────────────────────────────────────────────

class TabMacchina:
    """Tab In Macchina V16 — Sync TOA/TMA + Confronto multi-MPF."""

    def __init__(self, parent, main_window):
        self.parent      = parent
        self.main        = main_window
        self._tools_data = {}
        self._sync_time  = None
        self._mpf_paths  = []
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
        ctk.CTkLabel(header, text="Sync TOA/TMA  |  Confronto MPF  |  Tabella utensili",
                     font=get_font("body"), text_color="#E8F5E9").pack(pady=(0, 8))

        # Toolbar: MPF a sinistra (grande), TOA a destra (piccolo)
        toolbar = ctk.CTkFrame(self.parent, fg_color="transparent")
        toolbar.pack(fill="x", padx=8, pady=(8, 4))

        # SINISTRA — azioni primarie
        ctk.CTkButton(toolbar, text="+ Aggiungi MPF",
                      command=self._aggiungi_mpf,
                      fg_color="#1976D2", hover_color="#0D47A1",
                      font=get_font("medium", bold=True), height=44, width=160,
                      corner_radius=8).pack(side="left", padx=4)

        ctk.CTkButton(toolbar, text="Reset",
                      command=self._reset_mpf,
                      **get_button_style("neutral", "medium")).pack(side="left", padx=4)

        # DESTRA — sync secondario
        self.lbl_sync_status = ctk.CTkLabel(toolbar, text="Nessun sync",
                                             font=get_font("small"),
                                             text_color=COLOR_TEXT_SECONDARY)
        self.lbl_sync_status.pack(side="right", padx=8)

        ctk.CTkButton(toolbar, text="TOA manuale",
                      command=self._scegli_toa_manuale,
                      fg_color="#607D8B", hover_color="#455A64",
                      font=get_font("small"), height=32, width=110,
                      corner_radius=6).pack(side="right", padx=3)

        self.btn_sync = ctk.CTkButton(toolbar, text="Sync macchina",
                                       command=self._do_sync,
                                       fg_color="#607D8B", hover_color="#455A64",
                                       font=get_font("small"), height=32, width=120,
                                       corner_radius=6)
        self.btn_sync.pack(side="right", padx=3)

        # Istruzioni primo sync
        self.frame_istruzioni = ctk.CTkFrame(self.parent, fg_color="#E3F2FD", corner_radius=8)
        self.frame_istruzioni.pack(fill="x", padx=8, pady=(0, 4))
        ctk.CTkLabel(self.frame_istruzioni,
                     text=("Prima sincronizzazione: "
                           "HMI -> Servizi -> Salva Attrezzaggio -> Z:\\DMG_DMC_160U\\TOOL_SYNC  "
                           "poi premi  Sync macchina  oppure  TOA manuale"),
                     font=get_font("small"), text_color=COLOR_PRIMARY, justify="left",
                     ).pack(padx=12, pady=6, anchor="w")

        # PanedWindow verticale: confronto (alto) | tabella utensili (basso)
        paned = tk.PanedWindow(self.parent, orient=tk.VERTICAL,
                                sashwidth=6, sashrelief="raised",
                                background=COLOR_BORDER)
        paned.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        # ── Pannello confronto MPF ────────────────────────────────────────────
        top = ctk.CTkFrame(paned, fg_color="transparent")
        paned.add(top, minsize=110)

        # Riga file caricati
        row_files = ctk.CTkFrame(top, fg_color="transparent")
        row_files.pack(fill="x", pady=(4, 0))
        ctk.CTkLabel(row_files, text="Confronto MPF vs TOA:",
                     font=get_font("body", bold=True),
                     text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=4)
        self.lbl_file_count = ctk.CTkLabel(row_files, text="",
                                            font=get_font("small"),
                                            text_color=COLOR_TEXT_SECONDARY)
        self.lbl_file_count.pack(side="left", padx=6)

        self.list_mpf = ctk.CTkTextbox(top, height=34, font=get_font("small"),
                                        fg_color=COLOR_SURFACE,
                                        text_color=COLOR_TEXT_SECONDARY)
        self.list_mpf.pack(fill="x", padx=4, pady=(2, 2))
        self.list_mpf.insert("end", "Nessun file caricato — clicca + Aggiungi MPF")
        self.list_mpf.configure(state="disabled")

        # Tabella confronto
        cf = ctk.CTkFrame(top, fg_color=COLOR_SURFACE, corner_radius=6)
        cf.pack(fill="both", expand=True, padx=4, pady=(0, 4))
        self.tree_confronto = ttk.Treeview(cf,
            columns=("stato", "alias", "file", "riga"), show="headings")
        sb_c = ttk.Scrollbar(cf, orient="vertical", command=self.tree_confronto.yview)
        self.tree_confronto.configure(yscrollcommand=sb_c.set)
        for col, label, w in [("stato","STATO",90),("alias","ALIAS UTENSILE",260),
                                ("file","FILE",210),("riga","RIGA",60)]:
            self.tree_confronto.heading(col, text=label, anchor="w")
            self.tree_confronto.column(col, width=w, minwidth=40, anchor="w")
        self.tree_confronto.tag_configure("ok",       background="#F1F8E9")
        self.tree_confronto.tag_configure("mancante", background="#FFEBEE")
        self.tree_confronto.tag_configure("disab",    background="#FFF8E1")
        self.tree_confronto.tag_configure("worn",     background="#EDE7F6")
        self.tree_confronto.pack(side="left", fill="both", expand=True, padx=(6,0), pady=4)
        sb_c.pack(side="right", fill="y", pady=4, padx=(0,2))

        # ── Pannello tabella utensili ─────────────────────────────────────────
        bot = ctk.CTkFrame(paned, fg_color="transparent")
        paned.add(bot, minsize=200)

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
        cols = ("pos","name","duplo","length","radius","life","status")
        self.tree_sync = ttk.Treeview(tbl, columns=cols, show="headings")
        for col, label, w in [
            ("pos","Pos",68),("name","Nome utensile",220),("duplo","Duplo",55),
            ("length","L (mm)",90),("radius","R (mm)",80),("life","Vita %",75),("status","Stato",90)]:
            self.tree_sync.heading(col, text=label, anchor="w")
            self.tree_sync.column(col, width=w, minwidth=40, anchor="w")
        self.tree_sync.tag_configure("ok",       background="#F1F8E9")
        self.tree_sync.tag_configure("worn",     background="#EDE7F6")
        self.tree_sync.tag_configure("disabled", background="#FFEBEE")
        sb2 = ttk.Scrollbar(tbl, orient="vertical", command=self.tree_sync.yview)
        self.tree_sync.configure(yscrollcommand=sb2.set)
        self.tree_sync.pack(side="left", fill="both", expand=True, padx=(8,0), pady=6)
        sb2.pack(side="right", fill="y", pady=6, padx=(0,4))

        paned.after(100, lambda: paned.sash_place(0, 0, 220))

    # ── Sync ─────────────────────────────────────────────────────────────────

    def _do_sync(self):
        toa_path, _ = _get_sync_paths()
        if toa_path is None:
            messagebox.showerror("Configurazione mancante",
                "Percorso share non configurato.\n"
                "Impostare percorso_nc_base dalla pagina Analisi NC.")
            return
        if not toa_path.exists():
            messagebox.showerror("File non trovato",
                "File TOA non trovato:\n" + str(toa_path) + "\n\n"
                "Generare da HMI -> Servizi -> Salva Attrezzaggio")
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
        # Aggiorna anche confronto se ci sono file caricati
        if self._mpf_paths:
            self._confronta_mpf()
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
            if is_dis:   tag, stato = "disabled", "DISAB."
            elif is_worn: tag, stato = "worn",    "VITA BASSA"
            else:         tag, stato = "ok",      "OK"
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

    # ── Confronto MPF ────────────────────────────────────────────────────────

    def _aggiungi_mpf(self):
        files = filedialog.askopenfilenames(
            title="Seleziona programmi MPF",
            filetypes=[("Programmi MPF", "*.mpf *.MPF *.nc *.spf"), ("Tutti", "*.*")])
        if not files:
            return
        for f in files:
            if f not in self._mpf_paths:
                self._mpf_paths.append(f)
        self._aggiorna_lista_mpf()
        self._confronta_mpf()

    def _reset_mpf(self):
        self._mpf_paths = []
        self._aggiorna_lista_mpf()
        self.tree_confronto.delete(*self.tree_confronto.get_children())

    def _aggiorna_lista_mpf(self):
        self.list_mpf.configure(state="normal")
        self.list_mpf.delete("1.0", "end")
        if self._mpf_paths:
            for i, fp in enumerate(self._mpf_paths, 1):
                self.list_mpf.insert("end", str(i) + ". " + os.path.basename(fp) + chr(10))
            self.lbl_file_count.configure(
                text=str(len(self._mpf_paths)) + " file",
                text_color=COLOR_SUCCESS)
        else:
            self.list_mpf.insert("end", "Nessun file — clicca + Aggiungi MPF")
            self.lbl_file_count.configure(text="", text_color=COLOR_TEXT_SECONDARY)
        self.list_mpf.configure(state="disabled")

    def _confronta_mpf(self):
        self.tree_confronto.delete(*self.tree_confronto.get_children())
        if not self._mpf_paths:
            return
        if not self._tools_data:
            self.tree_confronto.insert("", "end",
                values=("! NO TOA", "Nessun sync TOA — usa Sync macchina o TOA manuale", "", ""),
                tags=("disab",))
            return

        alias_in_toa    = {t["name"].upper() for t in self._tools_data.values() if t.get("name")}
        alias_abilitati = {t["name"].upper() for t in self._tools_data.values()
                           if t.get("name") and t.get("is_enabled", True) and not t.get("is_worn", False)}
        alias_vita_bassa = {t["name"].upper() for t in self._tools_data.values()
                            if t.get("name") and t.get("life_percent") is not None
                            and t["life_percent"] < 10 and t.get("is_enabled", True)}

        richiesti = {}
        for fp in self._mpf_paths:
            fname = os.path.basename(fp)
            for alias, riga_num, _ in estrai_tutti_utensili_da_file(fp):
                au = alias.upper()
                if au not in richiesti:
                    richiesti[au] = (fname, riga_num)

        if not richiesti:
            self.tree_confronto.insert("", "end",
                values=("OK", "Nessun utensile trovato nei file MPF", "", ""),
                tags=("ok",))
            return

        alias_req    = set(richiesti.keys())
        mancanti     = sorted(alias_req - alias_in_toa)
        disabilitati = sorted(alias_req & (alias_in_toa - alias_abilitati))
        vita_bassa   = sorted((alias_req & alias_vita_bassa) - set(disabilitati))
        ok_list      = sorted(alias_req - set(mancanti) - set(disabilitati) - set(vita_bassa))

        for alias in mancanti:
            fn, rn = richiesti[alias]
            self.tree_confronto.insert("", "end", values=("MANCA", alias, fn, rn), tags=("mancante",))
        for alias in disabilitati:
            fn, rn = richiesti[alias]
            self.tree_confronto.insert("", "end", values=("DISAB.", alias, fn, rn), tags=("disab",))
        for alias in vita_bassa:
            fn, rn = richiesti[alias]
            self.tree_confronto.insert("", "end", values=("VITA<10%", alias, fn, rn), tags=("worn",))
        for alias in ok_list:
            fn, rn = richiesti[alias]
            self.tree_confronto.insert("", "end", values=("OK", alias, fn, rn), tags=("ok",))

    def refresh(self):
        self._load_existing_db()
        if self._mpf_paths:
            self._confronta_mpf()
