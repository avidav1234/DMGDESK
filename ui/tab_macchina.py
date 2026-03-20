"""
Tab In Macchina - Tool Manager V14 (Unificato)
Gestione CRUD utensili (DB manuale) + Sync TOA/TMA + Verifica MPF
"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
import json, os, threading
from datetime import datetime
from pathlib import Path
import pandas as pd

from config.theme import *
from config.constants import *
from database.db_handler import (
    carica_configurazione, salva_database, salva_configurazione
)
from database.db_handler import smonta_utensile_completo
from logic.main_generator import genera_programma_main
from logic.nc_analyzer import estrai_tutti_utensili_da_file, confronta_utensili_logica

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from api.toa_parser import parse_toa, parse_tma

from ui.calibra_only_settings_dialog import show_calibra_settings
from logic.calibra_only_logic import get_calibra_logic


# ---------------------------------------------------------------------------
# Helpers TOA/TMA
# ---------------------------------------------------------------------------

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
                "tool_id":     t.tool_id,
                "name":        t.name,
                "duplo":       t.duplo,
                "status":      t.status,
                "monitoring":  t.monitoring,
                "length":      t.main_length,
                "radius":      t.main_radius,
                "life_percent":t.life_percent,
                "is_enabled":  t.is_enabled,
                "is_worn":     t.is_worn,
                "magazine":    pos_map.get(tid, {}).get("magazine"),
                "position":    pos_map.get(tid, {}).get("position"),
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


# ---------------------------------------------------------------------------

class TabMacchina:
    """Tab In Macchina unificato: DB manuale + Sync TOA/TMA + Check MPF."""

    def __init__(self, parent, main_window):
        self.parent = parent
        self.main   = main_window
        self._tools_data  = {}
        self._sync_time   = None
        self._mpf_paths   = []   # file MPF per confronto multi-programma
        self._create_ui()
        self._load_existing_db()

    # -------------------------------------------------------------------------
    # UI
    # -------------------------------------------------------------------------

    def _create_ui(self):
        header = ctk.CTkFrame(self.parent, fg_color=COLOR_PRIMARY, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        ctk.CTkLabel(header, text="\U0001f527 IN MACCHINA",
                     font=get_font("title", bold=True), text_color="white").pack(pady=(12, 2))
        ctk.CTkLabel(header, text="Gestione utensili  \u2022  Sync TOA/TMA  \u2022  Verifica MPF",
                     font=get_font("body"), text_color="#E8F5E9").pack(pady=(0, 8))

        self.vista_var = ctk.StringVar(value="DB Manuale")
        ctk.CTkSegmentedButton(
            self.parent,
            values=["DB Manuale", "Sync Macchina"],
            variable=self.vista_var,
            command=self._on_vista_change,
            font=get_font("body", bold=True),
        ).pack(fill="x", padx=20, pady=(10, 0))

        self.frame_db   = ctk.CTkFrame(self.parent, fg_color="transparent")
        self.frame_sync = ctk.CTkFrame(self.parent, fg_color="transparent")
        self._build_db_view(self.frame_db)
        self._build_sync_view(self.frame_sync)
        self.frame_db.pack(fill="both", expand=True)

    def _on_vista_change(self, value):
        if value == "DB Manuale":
            self.frame_sync.pack_forget()
            self.frame_db.pack(fill="both", expand=True)
        else:
            self.frame_db.pack_forget()
            self.frame_sync.pack(fill="both", expand=True)

    # -------------------------------------------------------------------------
    # VISTA DB MANUALE
    # -------------------------------------------------------------------------

    def _build_db_view(self, parent):
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=(10, 6), padx=4)
        for text, cmd, style in [
            ("\u2795 Aggiungi",   self._aggiungi,   "success"),
            ("\u270f\ufe0f Modifica",   self._modifica,   "primary"),
            ("\U0001f3e0 A Scaffale",  self._a_scaffale, "primary"),
            ("\U0001f4e5 Smonta",     self._smonta,     "neutral"),
            ("\U0001f5d1\ufe0f Elimina",   self._elimina,    "error"),
        ]:
            ctk.CTkButton(toolbar, text=text, command=cmd,
                          **get_button_style(style, "medium")).pack(side="left", padx=4)
        sep = ctk.CTkFrame(toolbar, width=2, fg_color=COLOR_BORDER, height=35)
        sep.pack(side="left", padx=12, fill="y")
        mg = ctk.CTkFrame(toolbar, fg_color="transparent")
        mg.pack(side="left")
        ctk.CTkButton(mg, text="\U0001f4dd GENERA MAIN", width=140, height=40,
                      fg_color="#2196F3", hover_color="#1976D2",
                      font=get_font("body", bold=True), corner_radius=8,
                      command=self._genera_main).pack(side="left", padx=2)
        ctk.CTkButton(mg, text="\u2699\ufe0f", width=45, height=40,
                      fg_color="#9E9E9E", hover_color="#757575",
                      font=("Segoe UI", 16), corner_radius=8,
                      command=self._apri_impostazioni_calibra).pack(side="left", padx=2)

        tf = ctk.CTkFrame(parent, fg_color=COLOR_SURFACE)
        tf.pack(fill="both", expand=True, padx=4, pady=4)
        sb = ttk.Scrollbar(tf)
        sb.pack(side="right", fill="y")
        self.tree_db = ttk.Treeview(tf, columns=("Posizione", "Alias"),
                                     show="headings", yscrollcommand=sb.set, height=25)
        sb.config(command=self.tree_db.yview)
        self.tree_db.heading("Posizione", text="POSIZIONE")
        self.tree_db.heading("Alias",     text="ALIAS UTENSILE")
        self.tree_db.column("Posizione",  width=int(TREEVIEW_COL_WIDTH_POS), anchor="center")
        self.tree_db.column("Alias",      width=int(TREEVIEW_COL_WIDTH_ALIAS))
        self.tree_db.pack(fill="both", expand=True, padx=10, pady=10)
        self._configure_treeview_style()

    def _configure_treeview_style(self):
        style = ttk.Style()
        style.theme_use("default")
        style.configure("Treeview",
            background=COLOR_SURFACE, foreground=COLOR_TEXT_PRIMARY,
            fieldbackground=COLOR_SURFACE, borderwidth=0,
            font=(FONT_FAMILY, int(FONT_SIZE_NORMAL)))
        style.map("Treeview",
            background=[("selected", COLOR_PRIMARY)],
            foreground=[("selected", "white")])
        style.configure("Treeview.Heading",
            background=COLOR_DIVIDER, foreground=COLOR_TEXT_PRIMARY,
            borderwidth=1, relief="flat",
            font=(FONT_FAMILY, int(FONT_SIZE_NORMAL), "bold"))

    def refresh(self):
        self._refresh_db()
        self._load_existing_db()

    def _refresh_db(self):
        self.tree_db.delete(*self.tree_db.get_children())
        df_m = self.main.df[self.main.df["Stato_Utensile"] == STATO_IN_MACCHINA].copy()
        df_m["Pos_Int"] = pd.to_numeric(df_m["Posizione"], errors="coerce")
        df_m = df_m.sort_values("Pos_Int")
        for _, row in df_m.iterrows():
            self.tree_db.insert("", "end",
                values=(row["Posizione"], row["Alias"]), tags=(row.name,))

    # CRUD ----------------------------------------------------------------

    def _aggiungi(self):
        from utils.dialogs import InputDialog
        dialog = InputDialog(self.parent, "Aggiungi Utensile in Macchina",
                             [("Posizione (1-99)", "text"), ("Alias utensile", "text")])
        if not dialog.result:
            return
        pos, alias_base = dialog.result
        if not pos or not alias_base:
            messagebox.showerror("Errore", "Compila tutti i campi")
            return
        from ui.dialogs import SelezionaHolderDialog
        hd = SelezionaHolderDialog(self.parent, alias_base,
                                    self.main.df_holder_smontati, self.main.df_bussole_idraulico)
        if not hd.success:
            return
        alias_finale, holder_usato, bussola_usata = hd.alias_finale, hd.holder_cod, hd.bussola_cod
        df_h = self.main.df_holder_smontati
        if not df_h.empty:
            df_h["Alias_Holder"] = df_h["Alias_Holder"].astype(str).str.strip()
            hs = str(holder_usato).strip()
            if hs in df_h["Alias_Holder"].values:
                idx_h = df_h["Alias_Holder"] == hs
                df_h.loc[idx_h, "Quantita"] = df_h.loc[idx_h, "Quantita"].astype(int) - 1
                if df_h.loc[idx_h, "Quantita"].values[0] <= 0:
                    df_h = df_h[~idx_h].reset_index(drop=True)
                self.main.df_holder_smontati = df_h
                from database.db_handler import salva_database_holder_smontati
                salva_database_holder_smontati(df_h, self.main.db_paths.get("holder_smontati", ""))
        if bussola_usata:
            df_b = self.main.df_bussole_idraulico
            if not df_b.empty:
                df_b["Codice_Bussola"] = df_b["Codice_Bussola"].astype(str).str.strip()
                bs = str(bussola_usata).strip()
                if bs in df_b["Codice_Bussola"].values:
                    idx_b = df_b["Codice_Bussola"] == bs
                    df_b.loc[idx_b, "Quantita"] = df_b.loc[idx_b, "Quantita"].astype(int) - 1
                    if df_b.loc[idx_b, "Quantita"].values[0] <= 0:
                        df_b = df_b[~idx_b].reset_index(drop=True)
                    self.main.df_bussole_idraulico = df_b
                    from database.db_handler import salva_database_bussole_idraulico
                    salva_database_bussole_idraulico(df_b, self.main.db_paths.get("bussole_idraulico", ""))
        self.main.df = pd.concat([
            self.main.df,
            pd.DataFrame([{"Posizione": pos, "Alias": alias_finale, "Stato_Utensile": STATO_IN_MACCHINA}])
        ], ignore_index=True)
        success, err = salva_database(self.main.df, self.main.db_path)
        if success:
            self.main.refresh_all_tabs()
            parts = ["Utensile: " + alias_finale, "Posizione: " + pos]
            if holder_usato:  parts.append("Holder " + str(holder_usato) + " -1")
            if bussola_usata: parts.append("Bussola " + str(bussola_usata) + " -1")
            messagebox.showinfo("Successo", "Aggiunto in macchina!\n\n" + "\n".join(parts))
        else:
            messagebox.showerror("Errore", err)

    def _modifica(self):
        sel = self.tree_db.selection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona un utensile"); return
        idx = self.tree_db.item(sel[0])["tags"][0]
        row = self.main.df.loc[idx]
        from utils.dialogs import InputDialog
        dialog = InputDialog(self.parent, "Modifica Utensile",
                             [("Posizione", "text", row["Posizione"]),
                              ("Alias",     "text", row["Alias"])])
        if not dialog.result: return
        pos, alias = dialog.result
        self.main.df.at[idx, "Posizione"] = pos
        self.main.df.at[idx, "Alias"]     = alias
        success, err = salva_database(self.main.df, self.main.db_path)
        if success:
            self.main.refresh_all_tabs(); messagebox.showinfo("Successo", "Utensile modificato")
        else:
            messagebox.showerror("Errore", err)

    def _a_scaffale(self):
        sel = self.tree_db.selection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona un utensile"); return
        idx   = self.tree_db.item(sel[0])["tags"][0]
        alias = self.main.df.at[idx, "Alias"]
        pos   = self.main.df.at[idx, "Posizione"]
        if not messagebox.askyesno("Conferma", "Spostare a scaffale?\n\nAlias: " + alias + "\nPosizione liberata: " + str(pos)): return
        self.main.df.at[idx, "Stato_Utensile"] = STATO_SCAFFALE
        self.main.df.at[idx, "Posizione"] = ""
        success, err = salva_database(self.main.df, self.main.db_path)
        if success:
            self.main.refresh_all_tabs(); self.main._update_status()
            messagebox.showinfo("Successo", "Utensile spostato a scaffale\n" + alias)
        else:
            messagebox.showerror("Errore", err)

    def _smonta(self):
        sel = self.tree_db.selection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona un utensile"); return
        idx   = self.tree_db.item(sel[0])["tags"][0]
        alias = self.main.df.at[idx, "Alias"]
        pos   = self.main.df.at[idx, "Posizione"]
        if not messagebox.askyesno("Conferma Smontaggio",
            "Smontare utensile in posizione " + str(pos) + "?\n\nAlias: " + alias +
            "\n\nUtensile, holder e bussola verranno separati."): return
        try:
            success, msg, df_ut, df_h, df_b = smonta_utensile_completo(
                alias, self.main.db_paths,
                self.main.df_utensili_smontati, self.main.df_holder_smontati,
                self.main.df_bussole_idraulico, provenienza="Pos. " + str(pos))
            if success:
                self.main.df_utensili_smontati = df_ut
                self.main.df_holder_smontati   = df_h
                self.main.df_bussole_idraulico = df_b
                self.main.df = self.main.df.drop(idx).reset_index(drop=True)
                salva_database(self.main.df, self.main.db_path)
                self.main.refresh_all_tabs(); self.main._update_status()
                messagebox.showinfo("Smontaggio completato", msg)
            else:
                messagebox.showerror("Errore smontaggio", msg)
        except Exception as e:
            import traceback
            messagebox.showerror("Errore Critico",
                "Errore durante lo smontaggio:\n" + str(e) + "\n\n" + traceback.format_exc())
            self.main.refresh_all_tabs(); self.main._update_status()

    def _elimina(self):
        sel = self.tree_db.selection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona un utensile"); return
        if not messagebox.askyesno("Conferma", "Eliminare utensile?"): return
        idx = self.tree_db.item(sel[0])["tags"][0]
        self.main.df = self.main.df.drop(idx).reset_index(drop=True)
        success, err = salva_database(self.main.df, self.main.db_path)
        if success:
            self.main.refresh_all_tabs(); messagebox.showinfo("Successo", "Utensile eliminato")
        else:
            messagebox.showerror("Errore", err)

    def _genera_main(self):
        if self.main.df.empty:
            messagebox.showwarning("Attenzione", "Nessun utensile nel database"); return
        df_m = self.main.df[self.main.df["Stato_Utensile"] == STATO_IN_MACCHINA].copy()
        if df_m.empty:
            messagebox.showwarning("Attenzione", "Nessun utensile in macchina"); return
        success, msg = genera_programma_main(df_m, "MAIN")
        if success:
            messagebox.showinfo("\u2705 Successo", msg, parent=self.parent)
        elif msg not in ["Annullato", "Generazione annullata"]:
            messagebox.showerror("Errore", msg, parent=self.parent)

    def _apri_impostazioni_calibra(self):
        show_calibra_settings(self.parent)

    # -------------------------------------------------------------------------
    # VISTA SYNC MACCHINA
    # -------------------------------------------------------------------------

    def _build_sync_view(self, parent):
        import tkinter as tk

        # ── Toolbar sync ──────────────────────────────────────────────────────
        toolbar = ctk.CTkFrame(parent, fg_color="transparent")
        toolbar.pack(fill="x", padx=4, pady=(10, 4))

        self.btn_sync = ctk.CTkButton(toolbar, text="Sync da Macchina",
                                       command=self._do_sync,
                                       **get_button_style("primary", "medium"))
        self.btn_sync.pack(side="left", padx=4)

        ctk.CTkButton(toolbar, text="Scegli TOA manuale",
                      command=self._scegli_toa_manuale,
                      **get_button_style("neutral", "medium")).pack(side="left", padx=4)

        ctk.CTkButton(toolbar, text="Verifica MPF singolo",
                      command=self._scegli_mpf_check,
                      **get_button_style("neutral", "medium")).pack(side="left", padx=4)

        self.lbl_sync_status = ctk.CTkLabel(toolbar, text="Nessun sync",
                                             font=get_font("small"),
                                             text_color=COLOR_TEXT_SECONDARY)
        self.lbl_sync_status.pack(side="right", padx=10)

        # ── Istruzioni primo sync ─────────────────────────────────────────────
        self.frame_istruzioni = ctk.CTkFrame(parent, fg_color="#E3F2FD", corner_radius=8)
        self.frame_istruzioni.pack(fill="x", padx=4, pady=(0, 4))
        ctk.CTkLabel(self.frame_istruzioni,
                     text=("Come sincronizzare:\n"
                           "1.  HMI -> Servizi -> Salva Attrezzaggio\n"
                           "2.  Salvare in  Z:\\DMG_DMC_160U\\  con nome  TOOL_SYNC\n"
                           "3.  Premere  Sync da Macchina  oppure  Scegli TOA manuale"),
                     font=get_font("body"), text_color=COLOR_PRIMARY, justify="left",
                     ).pack(padx=14, pady=8, anchor="w")

        # ── PanedWindow: confronto (alto) | tabella utensili (basso) ─────────
        paned = tk.PanedWindow(parent, orient=tk.VERTICAL,
                                sashwidth=6, sashrelief="raised",
                                background=COLOR_BORDER)
        paned.pack(fill="both", expand=True, padx=4, pady=(2, 4))
        # Imposta posizione iniziale sash: ~200px per pannello confronto
        paned.after(100, lambda: paned.sash_place(0, 0, 220))

        # ─ Pannello superiore: confronto multi-MPF ─
        top_frame = ctk.CTkFrame(paned, fg_color="transparent")
        paned.add(top_frame, minsize=120)

        confronto_toolbar = ctk.CTkFrame(top_frame, fg_color="transparent")
        confronto_toolbar.pack(fill="x", pady=(4, 2))

        ctk.CTkLabel(confronto_toolbar,
                     text="Confronto MPF vs TOA",
                     font=get_font("body", bold=True),
                     text_color=COLOR_TEXT_PRIMARY).pack(side="left", padx=4)

        self.lbl_file_count = ctk.CTkLabel(confronto_toolbar, text="",
                                            font=get_font("small"),
                                            text_color=COLOR_TEXT_SECONDARY)
        self.lbl_file_count.pack(side="left", padx=6)

        ctk.CTkButton(confronto_toolbar, text="+ Aggiungi MPF",
                      command=self._aggiungi_mpf,
                      **get_button_style("primary", "small")).pack(side="left", padx=3)

        ctk.CTkButton(confronto_toolbar, text="Confronta",
                      command=self._confronta_mpf,
                      **get_button_style("success", "small")).pack(side="left", padx=3)

        ctk.CTkButton(confronto_toolbar, text="Reset",
                      command=self._reset_mpf,
                      **get_button_style("neutral", "small")).pack(side="left", padx=3)

        # Lista file caricati (1 riga di altezza)
        self.list_mpf = ctk.CTkTextbox(top_frame, height=36, font=get_font("small"),
                                        fg_color=COLOR_SURFACE,
                                        text_color=COLOR_TEXT_SECONDARY)
        self.list_mpf.pack(fill="x", pady=(2, 2))
        self.list_mpf.insert("end", "Nessun file caricato — clicca + Aggiungi MPF")
        self.list_mpf.configure(state="disabled")

        # Tabella risultati confronto — expand=True per prendere il pannello
        confronto_tbl = ctk.CTkFrame(top_frame, fg_color=COLOR_SURFACE, corner_radius=6)
        confronto_tbl.pack(fill="both", expand=True)

        self.tree_confronto = ttk.Treeview(
            confronto_tbl,
            columns=("stato", "alias", "file", "riga"),
            show="headings",
        )
        sb_c = ttk.Scrollbar(confronto_tbl, orient="vertical",
                              command=self.tree_confronto.yview)
        self.tree_confronto.configure(yscrollcommand=sb_c.set)

        self.tree_confronto.heading("stato", text="STATO")
        self.tree_confronto.heading("alias", text="ALIAS UTENSILE")
        self.tree_confronto.heading("file",  text="FILE")
        self.tree_confronto.heading("riga",  text="RIGA")
        self.tree_confronto.column("stato", width=90,  anchor="center")
        self.tree_confronto.column("alias", width=260, anchor="w")
        self.tree_confronto.column("file",  width=210, anchor="w")
        self.tree_confronto.column("riga",  width=60,  anchor="center")

        self.tree_confronto.tag_configure("ok",       background="#F1F8E9")
        self.tree_confronto.tag_configure("mancante", background="#FFEBEE")
        self.tree_confronto.tag_configure("disab",    background="#FFF8E1")
        self.tree_confronto.tag_configure("worn",     background="#EDE7F6")

        self.tree_confronto.pack(side="left", fill="both", expand=True, padx=(6, 0), pady=4)
        sb_c.pack(side="right", fill="y", pady=4, padx=(0, 2))

        # ─ Pannello inferiore: tabella utensili TOA ─
        bot_frame = ctk.CTkFrame(paned, fg_color="transparent")
        paned.add(bot_frame, minsize=200)

        ctrl = ctk.CTkFrame(bot_frame, fg_color="transparent")
        ctrl.pack(fill="x", pady=(4, 2))
        self.entry_search = ctk.CTkEntry(ctrl, placeholder_text="Cerca utensile...",
                                          font=get_font("body"), width=260)
        self.entry_search.pack(side="left", padx=4)
        self.entry_search.bind("<KeyRelease>", lambda e: self._refresh_sync_table())
        self.lbl_count = ctk.CTkLabel(ctrl, text="",
                                       font=get_font("small"),
                                       text_color=COLOR_TEXT_SECONDARY)
        self.lbl_count.pack(side="right", padx=8)

        tbl_frame = ctk.CTkFrame(bot_frame, fg_color=COLOR_SURFACE, corner_radius=8)
        tbl_frame.pack(fill="both", expand=True)

        cols = ("pos", "name", "duplo", "length", "radius", "life", "status")
        self.tree_sync = ttk.Treeview(tbl_frame, columns=cols, show="headings")
        for col, label, w in [
            ("pos",    "Pos",           68),
            ("name",   "Nome utensile", 220),
            ("duplo",  "Duplo",         55),
            ("length", "L (mm)",        90),
            ("radius", "R (mm)",        80),
            ("life",   "Vita %",        75),
            ("status", "Stato",         90),
        ]:
            self.tree_sync.heading(col, text=label, anchor="w")
            self.tree_sync.column(col, width=w, minwidth=40, anchor="w")

        self.tree_sync.tag_configure("ok",       background="#F1F8E9")
        self.tree_sync.tag_configure("worn",     background="#EDE7F6")
        self.tree_sync.tag_configure("disabled", background="#FFEBEE")

        sb2 = ttk.Scrollbar(tbl_frame, orient="vertical", command=self.tree_sync.yview)
        self.tree_sync.configure(yscrollcommand=sb2.set)
        self.tree_sync.pack(side="left", fill="both", expand=True, padx=(8, 0), pady=6)
        sb2.pack(side="right", fill="y", pady=6, padx=(0, 4))


    # ---- Sync ---------------------------------------------------------------

    def _do_sync(self):
        toa_path, _ = _get_sync_paths()
        if toa_path is None:
            messagebox.showerror("Configurazione mancante",
                "Percorso share non configurato.\n"
                "Impostare percorso_nc_base dalla pagina Analisi NC\n"
                "oppure usare Scegli TOA manuale.")
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
        self.btn_sync.configure(state="disabled", text="Sincronizzazione...")

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
                                tma_warning = ("TMA letto ma nessuna posizione trovata "
                                               "- magazzino vuoto al momento del salvataggio?")
                        except Exception as ex:
                            tma_warning = "Errore lettura TMA: " + str(ex)
                        break
                else:
                    tma_warning = ("File TMA non trovato accanto a " + toa_path.name +
                                   " - posizioni magazzino non disponibili")
                sync_time = datetime.now().isoformat()
                _save_tools_db(tools, sync_time, positions)
                n = sum(1 for t in tools.values() if t.name)
                self.parent.after(0, lambda: self._after_sync(n, len(positions), sync_time, tma_warning))
            except Exception as ex:
                msg = str(ex)
                self.parent.after(0, lambda: self._sync_error(msg))

        threading.Thread(target=_worker, daemon=True).start()

    def _after_sync(self, n_tools, n_pos, sync_time, tma_warning=None):
        self.btn_sync.configure(state="normal", text="Sync da Macchina")
        self._load_existing_db()
        lines = [
            str(n_tools) + " utensili sincronizzati",
            str(n_pos)   + " posizioni magazzino mappate",
        ]
        if tma_warning:
            lines += ["", "Attenzione: " + tma_warning]
        messagebox.showinfo("Sync completato", chr(10).join(lines))

    def _sync_error(self, msg):
        self.btn_sync.configure(state="normal", text="Sync da Macchina")
        messagebox.showerror("Errore sync", msg)

    def _load_existing_db(self):
        self._tools_data, self._sync_time = _load_tools_db()
        if self._sync_time:
            dt = datetime.fromisoformat(self._sync_time)
            self.lbl_sync_status.configure(
                text="Ultimo sync: " + dt.strftime("%d/%m/%Y %H:%M") +
                     "  -  " + str(len(self._tools_data)) + " utensili",
                text_color=COLOR_SUCCESS)
            self.frame_istruzioni.pack_forget()
        self._refresh_sync_table()

    def _refresh_sync_table(self):
        search = self.entry_search.get().strip().lower()
        self.tree_sync.delete(*self.tree_sync.get_children())
        filtered = [t for t in self._tools_data.values()
                    if not search or search in t["name"].lower()]
        filtered.sort(key=lambda t: (
            t.get("magazine") or 9999,
            t.get("position") or 9999,
            t["name"], t["duplo"]))
        for t in filtered:
            life        = t.get("life_percent")
            life_str    = (str(round(life)) + "%") if life is not None else "-"
            is_disabled = not t.get("is_enabled", True) or t.get("is_worn", False)
            is_worn     = life is not None and life < 10
            if is_disabled: tag, stato = "disabled", "DISAB."
            elif is_worn:   tag, stato = "worn",     "VITA BASSA"
            else:           tag, stato = "ok",       "OK"
            mag = t.get("magazine")
            pos = t.get("position")
            pos_str = ("M" + str(mag) + "." + str(pos).zfill(3)
                       if mag is not None and pos is not None else "-")
            self.tree_sync.insert("", "end", values=(
                pos_str, t["name"], "#" + str(t["duplo"]),
                str(round(t.get("length", 0), 3)),
                str(round(t.get("radius", 0), 3)),
                life_str, stato,
            ), tags=(tag,))
        self.lbl_count.configure(
            text=str(len(filtered)) + " / " + str(len(self._tools_data)) + " utensili")

    # ---- Check MPF ----------------------------------------------------------

    def _scegli_mpf_check(self):
        if not self._tools_data:
            messagebox.showwarning("Nessun sync", "Eseguire prima un sync dalla macchina."); return
        path = filedialog.askopenfilename(
            title="Seleziona file MPF da verificare",
            filetypes=[("NC Programs", "*.mpf *.nc *.spf"), ("Tutti", "*.*")])
        if path:
            self._esegui_check(Path(path))

    def _esegui_check(self, mpf_path):
        utensili_file = estrai_tutti_utensili_da_file(str(mpf_path))
        if not utensili_file:
            messagebox.showinfo("Nessun utensile trovato",
                "Il file " + mpf_path.name + " non contiene chiamate T=\"...\" seguite da M6.")
            return
        alias_req = {a.upper() for a, _, _ in utensili_file}
        alias_mac = {t["name"].upper() for t in self._tools_data.values() if t.get("name")}
        alias_abl = {t["name"].upper() for t in self._tools_data.values()
                     if t.get("name") and t.get("is_enabled", True) and not t.get("is_worn", False)}
        alias_vit = {t["name"].upper() for t in self._tools_data.values()
                     if t.get("name") and t.get("life_percent") is not None
                     and t["life_percent"] < 10 and t.get("is_enabled", True)}
        mancanti     = sorted(alias_req - alias_mac)
        disabilitati = sorted(alias_req & (alias_mac - alias_abl))
        vita_bassa   = sorted((alias_req & alias_vit) - set(disabilitati))
        ok           = sorted(alias_req - set(mancanti) - set(disabilitati) - set(vita_bassa))
        dettaglio    = {a.upper(): (mpf_path.name, r, t)
                        for a, r, t in utensili_file if a.upper() in set(mancanti)}
        self._mostra_risultato_check(mpf_path.name, mancanti, disabilitati,
                                      vita_bassa, ok, len(alias_req), dettaglio)

    # ---- Confronto multi-MPF vs TOA -----------------------------------------

    def _aggiungi_mpf(self):
        """Aggiunge uno o piu file MPF alla lista di confronto."""
        files = filedialog.askopenfilenames(
            title="Seleziona programmi MPF",
            filetypes=[("Programmi MPF", "*.mpf *.MPF *.nc *.spf"), ("Tutti", "*.*")]
        )
        if not files:
            return
        for f in files:
            if f not in self._mpf_paths:
                self._mpf_paths.append(f)
        self._aggiorna_lista_mpf()
        # Confronto automatico come in analisi NC
        self._confronta_mpf()

    def _reset_mpf(self):
        """Pulisce lista file e risultati confronto."""
        self._mpf_paths = []
        self._aggiorna_lista_mpf()
        self.tree_confronto.delete(*self.tree_confronto.get_children())

    def _aggiorna_lista_mpf(self):
        """Aggiorna textbox con lista file caricati."""
        self.list_mpf.configure(state="normal")
        self.list_mpf.delete("1.0", "end")
        if self._mpf_paths:
            for i, fp in enumerate(self._mpf_paths, 1):
                self.list_mpf.insert("end", str(i) + ". " + os.path.basename(fp) + chr(10))
            self.lbl_file_count.configure(
                text=str(len(self._mpf_paths)) + " file caricati",
                text_color=COLOR_SUCCESS)
        else:
            self.list_mpf.insert("end", "Nessun file caricato — aggiungi uno o piu file .MPF")
            self.lbl_file_count.configure(text="", text_color=COLOR_TEXT_SECONDARY)
        self.list_mpf.configure(state="disabled")

    def _confronta_mpf(self):
        """
        Confronta utensili nei file MPF vs DB TOA (stessa logica di TabAnalisiNC._confronta).
        Usa confronta_utensili_logica ma con il DB TOA come sorgente invece del CSV.
        Mostra: mancanti in TOA, disabilitati, vita bassa, OK.
        """
        if not self._mpf_paths:
            messagebox.showwarning("Attenzione", "Aggiungi almeno un file MPF prima di confrontare.")
            return
        if not self._tools_data:
            messagebox.showwarning("Nessun sync",
                                    "Eseguire prima un sync dalla macchina (TOA/TMA).")
            return

        # Set alias dal DB TOA per ogni categoria
        alias_in_toa   = {t["name"].upper() for t in self._tools_data.values() if t.get("name")}
        alias_abilitati = {t["name"].upper() for t in self._tools_data.values()
                           if t.get("name") and t.get("is_enabled", True) and not t.get("is_worn", False)}
        alias_vita_bassa = {t["name"].upper() for t in self._tools_data.values()
                            if t.get("name") and t.get("life_percent") is not None
                            and t["life_percent"] < 10 and t.get("is_enabled", True)}

        # Estrai utensili richiesti da tutti i file MPF
        # {alias: [(file_name, riga_num, riga_testo), ...]}
        richiesti_dettaglio = {}
        for fp in self._mpf_paths:
            file_name = os.path.basename(fp)
            for alias, riga_num, riga_testo in estrai_tutti_utensili_da_file(fp):
                alias_up = alias.upper()
                if alias_up not in richiesti_dettaglio:
                    richiesti_dettaglio[alias_up] = []
                richiesti_dettaglio[alias_up].append((file_name, riga_num, riga_testo))

        if not richiesti_dettaglio:
            messagebox.showinfo("Nessun utensile trovato",
                                 "I file MPF non contengono chiamate T=ALIAS seguite da M6.")
            return

        alias_req = set(richiesti_dettaglio.keys())
        mancanti     = sorted(alias_req - alias_in_toa)
        disabilitati = sorted(alias_req & (alias_in_toa - alias_abilitati))
        vita_bassa   = sorted((alias_req & alias_vita_bassa) - set(disabilitati))
        ok_set       = alias_req - set(mancanti) - set(disabilitati) - set(vita_bassa)

        # Popola tabella — stessa struttura di TabAnalisiNC
        self.tree_confronto.delete(*self.tree_confronto.get_children())

        # Prima i mancanti (più importanti)
        for alias in mancanti:
            file_n, riga_n, _ = richiesti_dettaglio[alias][0]
            self.tree_confronto.insert("", "end",
                values=("MANCA", alias, file_n, riga_n),
                tags=("mancante",))

        for alias in disabilitati:
            file_n, riga_n, _ = richiesti_dettaglio[alias][0]
            self.tree_confronto.insert("", "end",
                values=("DISAB.", alias, file_n, riga_n),
                tags=("disab",))

        for alias in vita_bassa:
            file_n, riga_n, _ = richiesti_dettaglio[alias][0]
            self.tree_confronto.insert("", "end",
                values=("VITA <10%", alias, file_n, riga_n),
                tags=("worn",))

        for alias in sorted(ok_set):
            # Per gli OK mostra tutti i file che lo richiedono
            file_n, riga_n, _ = richiesti_dettaglio[alias][0]
            extra = " (+" + str(len(richiesti_dettaglio[alias]) - 1) + ")" if len(richiesti_dettaglio[alias]) > 1 else ""
            self.tree_confronto.insert("", "end",
                values=("OK", alias, file_n + extra, riga_n),
                tags=("ok",))

        # Nessun problema
        if not mancanti and not disabilitati:
            # Aggiungi riga riepilogo verde se tutto ok
            pass

        # Messaggio riepilogo
        if mancanti or disabilitati:
            messagebox.showwarning(
                "Problemi rilevati",
                str(len(mancanti)) + " utensili MANCANTI in TOA" + chr(10) +
                str(len(disabilitati)) + " utensili DISABILITATI" + chr(10) +
                str(len(vita_bassa)) + " utensili con vita < 10%" + chr(10) +
                chr(10) + "Vedi tabella per dettagli.")
        else:
            messagebox.showinfo(
                "OK",
                "Tutti i " + str(len(alias_req)) + " utensili richiesti " +
                "sono presenti e disponibili in TOA.")

    def _mostra_risultato_check(self, filename, mancanti, disabilitati,
                                 vita_bassa, ok, total, dettaglio):
        win = ctk.CTkToplevel(self.parent)
        win.title("Verifica MPF - " + filename)
        win.geometry("560x540")
        win.grab_set()
        can_run = not mancanti and not disabilitati
        ctk.CTkLabel(win,
                     text=("OK - Programma eseguibile" if can_run else "ERRORE - Utensili mancanti"),
                     font=get_font("title", bold=True), text_color="white",
                     fg_color=COLOR_SUCCESS if can_run else COLOR_ERROR,
                     corner_radius=0, height=50).pack(fill="x")
        ctk.CTkLabel(win, text="File: " + filename + "  -  " + str(total) + " utensili richiesti",
                     font=get_font("small"), text_color=COLOR_TEXT_SECONDARY).pack(pady=6)
        scroll = ctk.CTkScrollableFrame(win, fg_color="transparent")
        scroll.pack(fill="both", expand=True, padx=16, pady=8)
        sections = [
            ("Mancanti in macchina",    mancanti,     "#FFEBEE", COLOR_ERROR),
            ("Disabilitati / Esauriti", disabilitati, "#FFF8E1", "#F57C00"),
            ("Vita residua < 10%",      vita_bassa,   "#EDE7F6", "#7B1FA2"),
            ("Disponibili",             ok,           "#F1F8E9", COLOR_SUCCESS),
        ]
        for title, items, bg, color in sections:
            if not items: continue
            ctk.CTkLabel(scroll, text=title, font=get_font("body", bold=True),
                         text_color=color).pack(anchor="w", pady=(10, 3))
            frame = ctk.CTkFrame(scroll, fg_color=bg, corner_radius=6)
            frame.pack(fill="x", pady=(0, 4))
            if items is mancanti and dettaglio:
                for alias in items:
                    info = dettaglio.get(alias)
                    riga = ("  riga " + str(info[1])) if info else ""
                    ctk.CTkLabel(frame, text="  X  " + alias + riga,
                                 font=get_font("small"), text_color=COLOR_TEXT_PRIMARY,
                                 anchor="w").pack(fill="x", padx=10, pady=2)
            else:
                ctk.CTkLabel(frame, text="   ".join(items),
                             font=get_font("small"), text_color=COLOR_TEXT_PRIMARY,
                             wraplength=490, justify="left").pack(padx=10, pady=8, anchor="w")
        ctk.CTkButton(win, text="Chiudi", command=win.destroy,
                      **get_button_style("neutral", "medium")).pack(pady=12)
