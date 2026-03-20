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
from api.toa_parser import parse_toa, parse_tma
from logic.nc_analyzer import estrai_tutti_utensili_da_file


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


def _save_tools_db(tools, sync_time, positions=None):
    db_path = _get_tools_db_path()
    # Mappa tool_id → posizione magazzino
    pos_map = {}
    if positions:
        for pos in positions:
            pos_map[pos.tool_id] = {"magazine": pos.magazine, "position": pos.position}
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
                "magazine": pos_map.get(tid, {}).get("magazine"),
                "position": pos_map.get(tid, {}).get("position"),
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

        cols = ("pos", "name", "duplo", "length", "radius", "life", "status")
        self.tree = ttk.Treeview(tbl_frame, columns=cols, show="headings", height=18)

        headers = {
            "pos":    ("Pos",             65),
            "name":   ("Nome utensile",  200),
            "duplo":  ("Duplo",           50),
            "length": ("L (mm)",          88),
            "radius": ("R (mm)",          78),
            "life":   ("Vita %",          75),
            "status": ("Stato",           88),
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
                tma_warning = None

                if tma_path is None:
                    # Prova a trovare il TMA nella stessa cartella con ogni variante
                    for suffix in (".TMA", ".tma", ".Tma"):
                        candidate = Path(str(toa_path)).with_suffix(suffix)
                        if candidate.exists():
                            tma_path_found = candidate
                            break
                    else:
                        tma_path_found = None
                        tma_warning = f"File TMA non trovato accanto a {toa_path.name} — posizioni magazzino non disponibili"
                else:
                    tma_path_found = tma_path

                if tma_path_found:
                    try:
                        magazines, positions = parse_tma(tma_path_found)
                        if not positions:
                            tma_warning = f"TMA letto ({tma_path_found.name}) ma nessuna posizione occupata trovata — magazzino vuoto al momento del salvataggio?"
                    except Exception as e:
                        tma_warning = f"Errore lettura TMA: {e}"

                sync_time = datetime.now().isoformat()
                _save_tools_db(tools, sync_time, positions)
                n_tools = sum(1 for t in tools.values() if t.name)
                self.parent.after(0, lambda: self._after_sync(n_tools, len(positions), sync_time, tma_warning))
            except Exception as e:
                self.parent.after(0, lambda: self._sync_error(str(e)))

        threading.Thread(target=_worker, daemon=True).start()

    def _after_sync(self, n_tools, n_pos, sync_time, tma_warning=None):
        self.btn_sync.configure(state="normal", text="⟳  Sync da Macchina")
        self._load_existing_db()
        msg = f"✓ {n_tools} utensili sincronizzati
✓ {n_pos} posizioni magazzino mappate"
        if tma_warning:
            msg += f"

⚠️ {tma_warning}"
        messagebox.showinfo("Sync completato", msg)

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
        # Ordina per posizione magazzino (come in macchina), poi nome
        filtered.sort(key=lambda t: (
            t.get("magazine") or 9999,
            t.get("position") or 9999,
            t["name"],
            t["duplo"],
        ))

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

            mag = t.get("magazine")
            pos = t.get("position")
            pos_str = f"M{mag}·{pos:03d}" if mag is not None and pos is not None else "—"

            self.tree.insert("", "end", values=(
                pos_str,
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
        """
        Stessa logica di TabAnalisiNC._confronta:
        usa estrai_tutti_utensili_da_file per estrarre gli alias T="..." + M6
        e confronta con il DB sync TOA (nomi utensili).
        """
        # Estrai utensili richiesti dal file MPF (alias + riga)
        utensili_file = estrai_tutti_utensili_da_file(str(mpf_path))
        if not utensili_file:
            messagebox.showinfo(
                "Nessun utensile trovato",
                f"Il file {mpf_path.name} non contiene chiamate T=\"...\" seguite da M6."
            )
            return

        # Set alias richiesti (uppercase)
        alias_richiesti = {alias.upper() for alias, _, _ in utensili_file}

        # Set alias presenti nel DB sync (nome utensile)
        alias_in_macchina = {
            t["name"].upper()
            for t in self._tools_data.values()
            if t.get("name")
        }

        # Utensili abilitati (non disabilitati e non esauriti)
        alias_abilitati = {
            t["name"].upper()
            for t in self._tools_data.values()
            if t.get("name") and t.get("is_enabled", True) and not t.get("is_worn", False)
        }

        # Vita bassa (< 10%) ma ancora abilitati
        alias_vita_bassa = {
            t["name"].upper()
            for t in self._tools_data.values()
            if t.get("name")
            and t.get("life_percent") is not None
            and t["life_percent"] < 10
            and t.get("is_enabled", True)
        }

        mancanti  = sorted(alias_richiesti - alias_in_macchina)
        disabilitati = sorted(alias_richiesti & (alias_in_macchina - alias_abilitati))
        vita_bassa   = sorted(alias_richiesti & alias_vita_bassa - set(disabilitati))
        ok = sorted(alias_richiesti - set(mancanti) - set(disabilitati) - set(vita_bassa))

        # Dettaglio righe per utensili mancanti (come in _confronta)
        dettaglio = {}
        for alias, riga_num, riga_testo in utensili_file:
            if alias.upper() in set(mancanti):
                dettaglio[alias.upper()] = (mpf_path.name, riga_num, riga_testo)

        self._mostra_risultato_check(
            mpf_path.name,
            mancanti, disabilitati, vita_bassa, ok,
            len(alias_richiesti), dettaglio
        )

    def _mostra_risultato_check(self, filename, mancanti, disabilitati, vita_bassa, ok, total, dettaglio):
        """Mostra dialog con risultato check — stesso stile di TabAnalisiNC."""
        win = ctk.CTkToplevel(self.parent)
        win.title(f"Verifica MPF — {filename}")
        win.geometry("560x520")
        win.grab_set()

        can_run = not mancanti and not disabilitati
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

        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=8)

        sections = [
            ("❌  Mancanti in macchina",   mancanti,    "#FFEBEE", COLOR_ERROR),
            ("⚠️  Disabilitati / Esauriti", disabilitati,"#FFF8E1", "#F57C00"),
            ("🟣  Vita residua < 10%",      vita_bassa,  "#EDE7F6", "#7B1FA2"),
            ("✅  Disponibili",             ok,          "#F1F8E9", COLOR_SUCCESS),
        ]

        for title, items, bg, color in sections:
            if not items:
                continue
            ctk.CTkLabel(scroll, text=title,
                         font=get_font("body", bold=True),
                         text_color=color).pack(anchor="w", pady=(10, 3))
            frame = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=6)
            frame.pack(fill="x", pady=(0, 4))

            # Per i mancanti mostra anche numero riga come in _confronta
            if items is mancanti and dettaglio:
                for alias in items:
                    info = dettaglio.get(alias)
                    riga_str = f"  riga {info[1]}" if info else ""
                    ctk.CTkLabel(frame,
                                 text=f"  ❌  {alias}{riga_str}",
                                 font=get_font("small"),
                                 text_color=COLOR_TEXT_PRIMARY,
                                 anchor="w").pack(fill="x", padx=10, pady=2)
            else:
                ctk.CTkLabel(frame,
                             text="   ".join(items),
                             font=get_font("small"),
                             text_color=COLOR_TEXT_PRIMARY,
                             wraplength=480,
                             justify="left").pack(padx=10, pady=8, anchor="w")

        ctk.CTkButton(win, text="Chiudi",
                      command=win.destroy,
                      **get_button_style("neutral", "medium")).pack(pady=12)

    def refresh(self):
        """Chiamato da main_window quando si cambia tab."""
        self._load_existing_db()
