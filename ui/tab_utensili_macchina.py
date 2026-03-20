"""
Tab Utensili Macchina - Tool Manager V14
Sincronizzazione tabella utensili da file TOA/TMA generati dalla macchina.
Verifica disponibilità utensili per programmi MPF.
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
import json
import os
import threading
from pathlib import Path

from config.theme import *
from config.constants import *
from database.db_handler import carica_configurazione

# Import parser TOA/TMA
import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.toa_parser import (
    parse_toa, parse_tma,
    check_tools_availability, extract_tools_from_mpf,
)


def _get_tools_db_path() -> Path:
    config = carica_configurazione()
    db_path = config.get("database_path", ".")
    return Path(db_path).parent / "tools_machine.json"


def _get_sync_paths():
    config = carica_configurazione()
    # 1. chiave dedicata
    radice = config.get("radice", "")
    # 2. risali da percorso_nc_base (es. P:\DMG_DMC_160U\4297 → P:\DMG_DMC_160U)
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


def _save_tools_db(tools, sync_time):
    db_path = _get_tools_db_path()
    data = {
        "sync_time": sync_time,
        "tools": {
            str(tid): {
                "tool_id": t.tool_id,
                "name": t.name,
                "duplo": t.duplo,
                "status": t.status,
                "monitoring": t.monitoring,
                "length": t.main_length,
                "radius": t.main_radius,
                "life_percent": t.life_percent,
                "is_enabled": t.is_enabled,
                "is_worn": t.is_worn,
            }
            for tid, t in tools.items()
            if t.name
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


class TabUtensiliMacchina:
    """Tab per sincronizzazione e verifica utensili macchina."""

    def __init__(self, parent, main_window):
        self.parent = parent
        self.main = main_window
        self._tools_data = {}
        self._sync_time = None
        self._create_ui()
        self._load_existing_db()

    # ── UI ──────────────────────────────────────────────────────────────────

    def _create_ui(self):
        # Header
        header = ctk.CTkFrame(self.parent, fg_color=COLOR_PRIMARY, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="🗂 UTENSILI MACCHINA",
                     font=get_font("title", bold=True),
                     text_color="white").pack(pady=(12, 2))
        ctk.CTkLabel(header, text="Sync da TOA/TMA  •  Verifica programmi MPF",
                     font=get_font("body"),
                     text_color=COLOR_PRIMARY_LIGHT).pack(pady=(0, 8))

        # Toolbar
        toolbar = ctk.CTkFrame(self.parent, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=10)

        self.btn_sync = ctk.CTkButton(
            toolbar, text="⟳  Sync da Macchina",
            command=self._do_sync,
            **get_button_style("primary", "medium"))
        self.btn_sync.pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar, text="📁  Scegli TOA manuale",
            command=self._scegli_toa_manuale,
            **get_button_style("neutral", "medium")).pack(side="left", padx=5)

        ctk.CTkButton(
            toolbar, text="🔍  Verifica MPF",
            command=self._scegli_mpf_check,
            **get_button_style("neutral", "medium")).pack(side="left", padx=5)

        # Status sync
        self.lbl_status = ctk.CTkLabel(
            toolbar, text="Nessun sync",
            font=get_font("small"),
            text_color=COLOR_TEXT_SECONDARY)
        self.lbl_status.pack(side="right", padx=10)

        # Istruzioni (visibili finché non c'è sync)
        self.frame_istruzioni = ctk.CTkFrame(self.parent, fg_color="#E3F2FD", corner_radius=8)
        self.frame_istruzioni.pack(fill="x", padx=20, pady=(0, 8))
        ctk.CTkLabel(
            self.frame_istruzioni,
            text=(
                "Come sincronizzare:\n"
                "1. Sulla macchina:  HMI → Servizi → Salva Attrezzaggio\n"
                "2. Navigare in  Z:\\DMG_DMC_160U\\  e salvare con nome  TOOL_SYNC\n"
                "3. Premere  ⟳ Sync da Macchina  oppure  📁 Scegli TOA manuale"
            ),
            font=get_font("body"),
            text_color=COLOR_PRIMARY,
            justify="left",
        ).pack(padx=16, pady=10, anchor="w")

        # Pannello check MPF (inizialmente nascosto)
        self.frame_check = ctk.CTkFrame(self.parent, fg_color=COLOR_SURFACE,
                                         border_width=1, border_color=COLOR_BORDER,
                                         corner_radius=8)
        # non lo pack ancora

        # Separatore + ricerca
        ctrl_frame = ctk.CTkFrame(self.parent, fg_color="transparent")
        ctrl_frame.pack(fill="x", padx=20, pady=(4, 0))

        self.entry_search = ctk.CTkEntry(
            ctrl_frame, placeholder_text="🔎  Cerca utensile…",
            font=get_font("body"), width=260)
        self.entry_search.pack(side="left")
        self.entry_search.bind("<KeyRelease>", lambda e: self._refresh_table())

        self.lbl_count = ctk.CTkLabel(
            ctrl_frame, text="",
            font=get_font("small"), text_color=COLOR_TEXT_SECONDARY)
        self.lbl_count.pack(side="right", padx=8)

        # Tabella utensili
        tbl_frame = ctk.CTkFrame(self.parent, fg_color=COLOR_SURFACE,
                                  corner_radius=8)
        tbl_frame.pack(fill="both", expand=True, padx=20, pady=10)

        cols = ("name", "duplo", "length", "radius", "life", "status")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=18)

        headers = {
            "name":   ("Nome utensile",  220),
            "duplo":  ("Duplo",           55),
            "length": ("L (mm)",          90),
            "radius": ("R (mm)",          80),
            "life":   ("Vita %",          80),
            "status": ("Stato",           90),
        }
        for col, (label, w) in headers.items():
            self.tree.heading(col, text=label, anchor="w")
            self.tree.column(col,  width=w, minwidth=40, anchor="w")

        # Tag colori riga
        self.tree.tag_configure("ok",       background="#F1F8E9")
        self.tree.tag_configure("worn",     background="#EDE7F6")
        self.tree.tag_configure("disabled", background="#FFEBEE")

        sb = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=8)
        sb.pack(side="right", fill="y", pady=8, padx=(0, 4))

    # ── Sync ────────────────────────────────────────────────────────────────

    def _do_sync(self):
        """Sync da path configurato in radice."""
        toa_path, tma_path = _get_sync_paths()
        if toa_path is None:
            messagebox.showerror(
                "Configurazione mancante",
                "Radice share non configurata.\n"
                "Impostare 'radice' in config.json\n"
                "oppure usare '📁 Scegli TOA manuale'."
            )
            return
        if not toa_path.exists():
            messagebox.showerror(
                "File non trovato",
                f"File TOA non trovato:\n{toa_path}\n\n"
                "Generare da HMI → Servizi → Salva Attrezzaggio\n"
                "e salvare in Z:\\DMG_DMC_160U\\TOOL_SYNC"
            )
            return
        self._esegui_sync(toa_path, tma_path if tma_path.exists() else None)

    def _scegli_toa_manuale(self):
        """Selezione manuale del file TOA."""
        path = filedialog.askopenfilename(
            title="Seleziona file TOA",
            filetypes=[("Tool Offset Archive", "*.toa *.TOA"), ("Tutti", "*.*")]
        )
        if not path:
            return
        toa = Path(path)
        tma = toa.with_suffix(".TMA")
        if not tma.exists():
            tma = toa.with_suffix(".tma")
        self._esegui_sync(toa, tma if tma.exists() else None)

    def _esegui_sync(self, toa_path, tma_path):
        """Esegue sync in thread separato per non bloccare la UI."""
        self.btn_sync.configure(state="disabled", text="⟳  Sincronizzazione…")

        def _worker():
            try:
                from datetime import datetime
                tools = parse_toa(toa_path)
                magazines, positions = {}, []
                if tma_path:
                    try:
                        magazines, positions = parse_tma(tma_path)
                    except Exception:
                        pass
                sync_time = datetime.now().isoformat()
                _save_tools_db(tools, sync_time)
                n_tools = sum(1 for t in tools.values() if t.name)
                self.parent.after(0, lambda: self._after_sync(n_tools, len(positions), sync_time))
            except Exception as e:
                self.parent.after(0, lambda: self._sync_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _after_sync(self, n_tools, n_pos, sync_time):
        self.btn_sync.configure(state="normal", text="⟳  Sync da Macchina")
        self._load_existing_db()
        messagebox.showinfo(
            "Sync completato",
            f"✓ {n_tools} utensili sincronizzati\n"
            f"✓ {n_pos} posizioni magazzino mappate"
        )

    def _sync_error(self, msg):
        self.btn_sync.configure(state="normal", text="⟳  Sync da Macchina")
        messagebox.showerror("Errore sync", msg)

    # ── Carica DB esistente ──────────────────────────────────────────────────

    def _load_existing_db(self):
        self._tools_data, self._sync_time = _load_tools_db()
        if self._sync_time:
            from datetime import datetime
            dt = datetime.fromisoformat(self._sync_time)
            self.lbl_status.configure(
                text=f"Ultimo sync: {dt.strftime('%d/%m/%Y %H:%M')}  —  {len(self._tools_data)} utensili",
                text_color=COLOR_SUCCESS
            )
            self.frame_istruzioni.pack_forget()
        self._refresh_table()

    # ── Tabella ─────────────────────────────────────────────────────────────

    def _refresh_table(self):
        search = self.entry_search.get().strip().lower()
        self.tree.delete(*self.tree.get_children())

        filtered = [
            t for t in self._tools_data.values()
            if not search or search in t["name"].lower()
        ]
        # Ordina per nome poi duplo
        filtered.sort(key=lambda t: (t["name"], t["duplo"]))

        for t in filtered:
            life = t.get("life_percent")
            life_str = f"{life:.0f}%" if life is not None else "—"

            is_disabled = not t.get("is_enabled", True) or t.get("is_worn", False)
            is_worn     = life is not None and life < 10

            if is_disabled:
                tag, stato = "disabled", "DISAB."
            elif is_worn:
                tag, stato = "worn",     "VITA BASSA"
            else:
                tag, stato = "ok",       "OK"

            self.tree.insert("", "end", values=(
                t["name"],
                f"#{t['duplo']}",
                f"{t.get('length', 0):.3f}",
                f"{t.get('radius', 0):.3f}",
                life_str,
                stato,
            ), tags=(tag,))

        self.lbl_count.configure(
            text=f"{len(filtered)} / {len(self._tools_data)} utensili"
        )

    # ── Check MPF ───────────────────────────────────────────────────────────

    def _scegli_mpf_check(self):
        if not self._tools_data:
            messagebox.showwarning(
                "Nessun sync",
                "Eseguire prima un sync dalla macchina."
            )
            return
        path = filedialog.askopenfilename(
            title="Seleziona file MPF da verificare",
            filetypes=[("NC Programs", "*.mpf *.nc *.spf"), ("Tutti", "*.*")]
        )
        if not path:
            return
        self._esegui_check(Path(path))

    def _esegui_check(self, mpf_path):
        try:
            with open(mpf_path, encoding="utf-8", errors="replace") as f:
                content = f.read()
        except Exception as e:
            messagebox.showerror("Errore lettura MPF", str(e))
            return

        required = extract_tools_from_mpf(content)
        if not required:
            messagebox.showinfo(
                "Nessun utensile trovato",
                f"Il file {mpf_path.name} non contiene chiamate utensile T=\"...\"."
            )
            return

        # Ricostruisce MachineTool leggero dal DB JSON
        from api.toa_parser import MachineTool as MT
        machine_tools = {}
        for tid_str, t in self._tools_data.items():
            mt = MT(tool_id=t["tool_id"])
            mt.name       = t["name"]
            mt.duplo      = t["duplo"]
            mt.status     = t["status"]
            mt.monitoring = t.get("monitoring", 0)
            machine_tools[t["tool_id"]] = mt

        result = check_tools_availability(required, machine_tools)

        self._mostra_risultato_check(mpf_path.name, result, len(required))

    def _mostra_risultato_check(self, filename, result, total):
        """Mostra dialog con risultato check."""
        win = ctk.CTkToplevel(self.parent)
        win.title(f"Verifica MPF — {filename}")
        win.geometry("520x480")
        win.grab_set()

        can_run = not result["missing"] and not result["disabled"]
        banner_color = COLOR_SUCCESS if can_run else COLOR_ERROR
        banner_text  = "✅  Programma eseguibile" if can_run else "❌  Utensili mancanti o non disponibili"

        ctk.CTkLabel(win, text=banner_text,
                     font=get_font("title", bold=True),
                     text_color="white",
                     fg_color=banner_color,
                     corner_radius=0,
                     height=50).pack(fill="x")

        ctk.CTkLabel(win,
                     text=f"File: {filename}  •  {total} utensili richiesti",
                     font=get_font("small"),
                     text_color=COLOR_TEXT_SECONDARY).pack(pady=6)

        # Sezioni risultato
        sections = [
            ("❌  Mancanti in macchina",    result["missing"],  "#FFEBEE", COLOR_ERROR),
            ("⚠️  Disabilitati / Esauriti",  result["disabled"], "#FFF8E1", "#F57C00"),
            ("🟣  Vita residua < 10%",       result["worn"],     "#EDE7F6", "#7B1FA2"),
            ("✅  Disponibili",              result["ok"],       "#F1F8E9", COLOR_SUCCESS),
        ]

        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=8)

        for title, items, bg, color in sections:
            if not items:
                continue
            ctk.CTkLabel(scroll, text=title,
                         font=get_font("body", bold=True),
                         text_color=color).pack(anchor="w", pady=(10, 3))
            frame = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=6)
            frame.pack(fill="x", pady=(0, 4))
            ctk.CTkLabel(frame,
                         text="   ".join(items),
                         font=get_font("small"),
                         text_color=COLOR_TEXT_PRIMARY,
                         wraplength=450,
                         justify="left").pack(padx=10, pady=8, anchor="w")

        ctk.CTkButton(win, text="Chiudi",
                      command=win.destroy,
                      **get_button_style("neutral", "medium")).pack(pady=12)

    def refresh(self):
        """Chiamato da main_window quando si cambia tab."""
        self._load_existing_db()
