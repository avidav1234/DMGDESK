"""Tab Analisi NC - DMGDesk V16"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter as tk
import tkinter.ttk as ttk
import os, re, sys, json
from datetime import datetime
from pathlib import Path

from config.theme import *
from config.constants import *
from logic.nc_analyzer import estrai_tutti_utensili_da_file, confronta_utensili_logica

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


# ── Helpers ───────────────────────────────────────────────────────────────────

def _carica_config() -> dict:
    try:
        from database.db_handler import carica_configurazione
        cfg = carica_configurazione()
        if isinstance(cfg, dict):
            return cfg
    except Exception:
        pass
    try:
        base = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        if getattr(sys, 'frozen', False):
            base = os.path.dirname(sys.executable)
        with open(os.path.join(base, "config.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _load_tools_machine() -> tuple[dict, str]:
    """Carica tools_machine.json. Ritorna (tools_db, label_fonte)."""
    try:
        from ui.tab_macchina import _get_tools_db_path
        tdb_path = _get_tools_db_path()
        if tdb_path.exists():
            data = json.loads(tdb_path.read_text(encoding="utf-8"))
            tools = data.get("tools", {})
            fmt   = (data.get("format_used") or "").upper() or "TOA/MPF"
            sync  = data.get("sync_time", "")
            dt    = ""
            if sync:
                try:
                    dt = datetime.fromisoformat(sync).strftime("%d/%m  %H:%M")
                except Exception:
                    dt = sync[:16]
            fonte = f"{fmt}  ·  {dt}"
            return tools, fonte
    except Exception:
        pass
    return {}, ""


# ── Tab ───────────────────────────────────────────────────────────────────────

class TabAnalisiNC:

    def __init__(self, parent, main_window):
        self.parent            = parent
        self.main              = main_window
        self.file_paths        = []
        self._main_generato_path = None
        self._create_ui()

    # ── UI ────────────────────────────────────────────────────────────────────

    def _create_ui(self):
        # ── Top bar: ordine flow ─────────────────────────────────────────
        # SINISTRA: + Aggiungi | Nome | Fase(opz.) | Genera MAIN | Reset
        # CENTRO:   Banner stato
        # DESTRA:   Invia tutto | Solo MAIN | ⚙

        top = ctk.CTkFrame(self.parent, fg_color="white",
                           corner_radius=0, height=58, border_width=0)
        top.pack(fill="x")
        top.pack_propagate(False)

        BTN_COLOR = COLOR_PRIMARY   # unico colore per tutti i pulsanti primari
        BTN_HOVER  = "#1565C0"
        BTN_H      = 36

        # ── SINISTRA ──────────────────────────────────────────────────────
        left = ctk.CTkFrame(top, fg_color="transparent")
        left.pack(side="left", padx=10, pady=10)

        # 1. Aggiungi file
        ctk.CTkButton(
            left, text="+ Aggiungi file",
            command=self._seleziona_files,
            fg_color=BTN_COLOR, hover_color=BTN_HOVER,
            font=get_font("medium", bold=True), height=BTN_H, width=120, corner_radius=6
        ).pack(side="left", padx=(0, 6))

        # 2. Nome cartella
        ctk.CTkLabel(left, text="Nome:", font=get_font("small"),
                     text_color="#90A4AE").pack(side="left", padx=(0, 3))
        self.entry_nome = ctk.CTkEntry(
            left, width=100, height=BTN_H,
            placeholder_text="es. Fase-3",
            font=get_font("body"), corner_radius=6)
        self.entry_nome.pack(side="left", padx=(0, 6))

        # 3. Genera MAIN
        self.btn_genera = ctk.CTkButton(
            left, text="📄 Genera MAIN",
            command=self._genera_main,
            fg_color=BTN_COLOR, hover_color=BTN_HOVER,
            font=get_font("medium", bold=True), height=BTN_H, width=125, corner_radius=6)
        self.btn_genera.pack(side="left", padx=(0, 4))

        # 5. Reset
        ctk.CTkButton(
            left, text="Reset",
            command=self._pulisci_lista,
            fg_color="#ECEFF1", hover_color="#CFD8DC",
            text_color="#546E7A",
            font=get_font("medium"), height=BTN_H, width=60, corner_radius=6
        ).pack(side="left")

        # ── CENTRO: banner stato ──────────────────────────────────────────
        self.frame_stato = ctk.CTkFrame(top, fg_color="transparent")
        self.frame_stato.pack(side="left", padx=14, fill="y")
        self.lbl_stato = ctk.CTkLabel(
            self.frame_stato, text="",
            font=get_font("medium", bold=True), anchor="w")
        self.lbl_stato.pack(anchor="w")
        self.lbl_fonte = ctk.CTkLabel(
            self.frame_stato, text="",
            font=get_font("small"), text_color="#90A4AE", anchor="w")
        self.lbl_fonte.pack(anchor="w")

        # ── DESTRA: invio ─────────────────────────────────────────────────
        right = ctk.CTkFrame(top, fg_color="transparent")
        right.pack(side="right", padx=10, pady=10)

        # ⚙ Calibra
        ctk.CTkButton(
            right, text="⚙",
            command=self._apri_calibra_settings,
            fg_color="transparent", hover_color="#ECEFF1",
            text_color="#B0BEC5", border_width=1, border_color="#CFD8DC",
            font=get_font("small"), height=28, width=28, corner_radius=6
        ).pack(side="right", padx=(4, 0))

        # Solo MAIN
        self.btn_solo_main = ctk.CTkButton(
            right, text="📤 Solo MAIN",
            command=self._invia_solo_main,
            fg_color=BTN_COLOR, hover_color=BTN_HOVER,
            font=get_font("medium"), height=BTN_H, width=110, corner_radius=6,
            state="disabled")
        self.btn_solo_main.pack(side="right", padx=3)

        # Invia tutto
        self.btn_invia = ctk.CTkButton(
            right, text="📤 Invia tutto",
            command=self._invia_tutto,
            fg_color=BTN_COLOR, hover_color=BTN_HOVER,
            font=get_font("medium"), height=BTN_H, width=110, corner_radius=6,
            state="disabled")
        self.btn_invia.pack(side="right", padx=3)

        # ── Separatore ────────────────────────────────────────────────────
        sep = ctk.CTkFrame(self.parent, fg_color="#E8EDF2", height=1)
        sep.pack(fill="x")

        # ── Corpo principale: lista file (sinistra) + risultati (destra) ──
        body = ctk.CTkFrame(self.parent, fg_color="transparent")
        body.pack(fill="both", expand=True, padx=12, pady=10)

        # ── Pannello sinistra: lista file ─────────────────────────────────
        pnl_sx = ctk.CTkFrame(body, fg_color="white", corner_radius=10,
                              border_width=1, border_color="#E0E6ED")
        pnl_sx.pack(side="left", fill="both", padx=(0, 8), pady=0,
                    ipadx=0, ipady=0, expand=False)
        pnl_sx.configure(width=260)
        pnl_sx.pack_propagate(False)

        hdr_sx = ctk.CTkFrame(pnl_sx, fg_color="#F5F7FA", corner_radius=0, height=36)
        hdr_sx.pack(fill="x")
        hdr_sx.pack_propagate(False)
        ctk.CTkLabel(hdr_sx, text="File NC caricati",
                     font=get_font("small", bold=True),
                     text_color="#546E7A").pack(side="left", padx=12, pady=8)
        self.lbl_n_file = ctk.CTkLabel(hdr_sx, text="",
                                        font=get_font("small"),
                                        text_color="#90A4AE")
        self.lbl_n_file.pack(side="right", padx=10)

        # Lista file come Listbox scrollabile
        list_wrapper = ctk.CTkFrame(pnl_sx, fg_color="transparent")
        list_wrapper.pack(fill="both", expand=True, padx=6, pady=6)

        sb_files = ttk.Scrollbar(list_wrapper)
        sb_files.pack(side="right", fill="y")

        self.lb_files = tk.Listbox(
            list_wrapper,
            font=("Consolas", 10),
            bg="white", fg="#37474F",
            selectbackground="#E3F2FD", selectforeground="#1565C0",
            relief="flat", bd=0,
            highlightthickness=0,
            yscrollcommand=sb_files.set,
            activestyle="none")
        self.lb_files.pack(fill="both", expand=True)
        sb_files.config(command=self.lb_files.yview)

        # Rimuovi file con tasto Canc
        self.lb_files.bind("<Delete>", self._rimuovi_selezionato)

        # ── Pannello destra: risultati ────────────────────────────────────
        pnl_dx = ctk.CTkFrame(body, fg_color="white", corner_radius=10,
                              border_width=1, border_color="#E0E6ED")
        pnl_dx.pack(side="left", fill="both", expand=True)

        hdr_dx = ctk.CTkFrame(pnl_dx, fg_color="#F5F7FA", corner_radius=0, height=36)
        hdr_dx.pack(fill="x")
        hdr_dx.pack_propagate(False)
        ctk.CTkLabel(hdr_dx, text="Risultati confronto utensili",
                     font=get_font("small", bold=True),
                     text_color="#546E7A").pack(side="left", padx=12, pady=8)
        ctk.CTkLabel(hdr_dx, text="Doppio click su un utensile mancante per aggiungerlo a scaffale",
                     font=get_font("small"), text_color="#B0BEC5").pack(side="right", padx=12)

        # Treeview risultati
        style = ttk.Style()
        style.configure("NC.Treeview",
                        font=("Consolas", 10),
                        rowheight=28,
                        background="white",
                        fieldbackground="white",
                        foreground="#37474F")
        style.configure("NC.Treeview.Heading",
                        font=("Helvetica", 9, "bold"),
                        background="#F5F7FA",
                        foreground="#546E7A",
                        relief="flat")
        style.map("NC.Treeview", background=[("selected", "#E3F2FD")],
                  foreground=[("selected", "#1565C0")])

        tree_wrap = ctk.CTkFrame(pnl_dx, fg_color="transparent")
        tree_wrap.pack(fill="both", expand=True, padx=6, pady=6)

        sb_tree = ttk.Scrollbar(tree_wrap)
        sb_tree.pack(side="right", fill="y")

        self.tree = ttk.Treeview(
            tree_wrap,
            columns=("stato", "alias", "file", "riga"),
            show="headings",
            style="NC.Treeview",
            yscrollcommand=sb_tree.set)
        sb_tree.config(command=self.tree.yview)

        self.tree.heading("stato", text="STATO",  anchor="w")
        self.tree.heading("alias", text="ALIAS",  anchor="w")
        self.tree.heading("file",  text="FILE",   anchor="w")
        self.tree.heading("riga",  text="RIGA",   anchor="w")

        self.tree.column("stato", width=90,  minwidth=70,  anchor="w")
        self.tree.column("alias", width=320, minwidth=150, anchor="w")
        self.tree.column("file",  width=220, minwidth=100, anchor="w")
        self.tree.column("riga",  width=60,  minwidth=40,  anchor="center")

        self.tree.tag_configure("ok",     background="#F1F8E9", foreground="#2E7D32")
        self.tree.tag_configure("manca",  background="#FFEBEE", foreground="#C62828")
        self.tree.tag_configure("disab",  background="#FFF8E1", foreground="#E65100")
        self.tree.tag_configure("empty",  background="white",   foreground="#90A4AE")

        self.tree.pack(fill="both", expand=True)
        self.tree.bind("<Double-Button-1>", self._on_double_click)

        # Placeholder stato vuoto
        self._show_placeholder()

    def _show_placeholder(self):
        self.tree.delete(*self.tree.get_children())
        self.tree.insert("", "end", values=("", "Carica file .MPF per iniziare il confronto", "", ""), tags=("empty",))

    # ── Lista file ────────────────────────────────────────────────────────────

    def _seleziona_files(self):
        files = filedialog.askopenfilenames(
            title="Seleziona programmi NC",
            filetypes=[("Programmi MPF", "*.MPF *.mpf"), ("Tutti i file", "*.*")])
        if files:
            for f in files:
                if f not in self.file_paths:
                    self.file_paths.append(f)
            self._aggiorna_lista()
            self._confronta()

    def _rimuovi_selezionato(self, event=None):
        sel = self.lb_files.curselection()
        if not sel:
            return
        idx = sel[0]
        self.file_paths.pop(idx)
        self._aggiorna_lista()
        if self.file_paths:
            self._confronta()
        else:
            self._pulisci_lista()

    def _pulisci_lista(self):
        self.file_paths = []
        self._main_generato_path = None
        self.lb_files.delete(0, "end")
        self.lbl_n_file.configure(text="")
        self.lbl_stato.configure(text="")
        self.lbl_fonte.configure(text="")
        self.btn_invia.configure(state="disabled")
        self.btn_solo_main.configure(state="disabled")
        self.entry_nome.delete(0, "end")
        self._show_placeholder()

    def _aggiorna_lista(self):
        self.lb_files.delete(0, "end")
        for fp in self.file_paths:
            self.lb_files.insert("end", os.path.basename(fp))
        n = len(self.file_paths)
        self.lbl_n_file.configure(text=f"{n} file" if n else "")

    # ── Confronto ─────────────────────────────────────────────────────────────

    def _confronta(self, show_message=False):
        if not self.file_paths:
            return

        tools_db, fonte = _load_tools_machine()

        if not tools_db:
            self.lbl_stato.configure(
                text="⚠  Sync non eseguito",
                text_color="#F57C00")
            self.lbl_fonte.configure(
                text="Vai in 'In Macchina' e premi Sync macchina")
            self.tree.delete(*self.tree.get_children())
            self.tree.insert("", "end",
                values=("", "Esegui il Sync TOA/MPF prima di confrontare", "", ""),
                tags=("empty",))
            return

        # Estrai alias dai file NC
        alias_richiesti = set()
        for fp in self.file_paths:
            for alias, _, _ in estrai_tutti_utensili_da_file(fp):
                alias_richiesti.add(alias.upper().strip())

        # Solo utensili con posizione nel magazzino M1
        alias_in_macchina = {
            t["name"].upper() for t in tools_db.values()
            if t.get("name") and t.get("magazine") is not None
        }
        alias_abilitati   = {
            t["name"].upper() for t in tools_db.values()
            if t.get("name") and t.get("is_enabled", True) and not t.get("is_worn", False)
        }
        mancanti     = sorted(alias_richiesti - alias_in_macchina)
        disabilitati = sorted(alias_richiesti & (alias_in_macchina - alias_abilitati))
        presenti     = sorted(alias_richiesti - set(mancanti) - set(disabilitati))
        n_problemi   = len(mancanti) + len(disabilitati)

        # Aggiorna tree
        self.tree.delete(*self.tree.get_children())
        for alias in mancanti:
            self.tree.insert("", "end", values=("❌  Mancante", alias, "—", "—"), tags=("manca",))
        for alias in disabilitati:
            self.tree.insert("", "end", values=("⚠  Disabilitato", alias, "—", "—"), tags=("disab",))
        for alias in presenti:
            self.tree.insert("", "end", values=("✓  OK", alias, "—", "—"), tags=("ok",))

        if not alias_richiesti:
            self.tree.insert("", "end",
                values=("", "Nessun utensile trovato nei file NC", "", ""),
                tags=("empty",))

        # Banner stato
        tot = len(alias_richiesti)
        if n_problemi == 0:
            self.lbl_stato.configure(
                text=f"✅  Tutti i {tot} utensili presenti in macchina",
                text_color="#2E7D32")
        else:
            parti = []
            if mancanti:     parti.append(f"❌ {len(mancanti)} mancanti")
            if disabilitati: parti.append(f"⚠ {len(disabilitati)} disabilitati")
            self.lbl_stato.configure(
                text=f"{'  ·  '.join(parti)}  di {tot} totali",
                text_color="#C62828")

        self.lbl_fonte.configure(text=fonte)
        self.btn_invia.configure(state="normal")

        if show_message:
            messagebox.showinfo("Confronto completato",
                f"Utensili richiesti: {tot}\n"
                f"Mancanti: {len(mancanti)}\n"
                f"Disabilitati: {len(disabilitati)}")

    # ── Double click → aggiungi a scaffale ───────────────────────────────────

    def _on_double_click(self, event):
        sel = self.tree.selection()
        if not sel:
            return
        item  = self.tree.item(sel[0])
        stato = item["values"][0] if item["values"] else ""
        if "Mancante" not in str(stato):
            return
        alias = item["values"][1]

        from database.db_handler import ha_holder
        if ha_holder(alias):
            messagebox.showinfo("Info",
                f"'{alias}' ha già un holder incorporato.\n"
                f"Verrà aggiunto direttamente a Scaffale.")
            try:
                import pandas as pd
                from database.db_handler import salva_database
                new_row = pd.DataFrame([{"Posizione": "", "Alias": alias, "Stato_Utensile": STATO_SCAFFALE}])
                self.main.df = pd.concat([self.main.df, new_row], ignore_index=True)
                ok, err = salva_database(self.main.df, self.main.db_path)
                if ok:
                    self.main.refresh_all_tabs()
                    self.main._update_status()
                    self.tree.delete(sel[0])
                    messagebox.showinfo("Successo", f"'{alias}' aggiunto a Scaffale")
                else:
                    messagebox.showerror("Errore", err)
            except Exception as e:
                messagebox.showerror("Errore", str(e))
            return

        if not messagebox.askyesno("Aggiungi a Scaffale",
                f"Aggiungere '{alias}' al database come SCAFFALE?\n"
                f"Dovrai selezionare un holder."):
            return

        try:
            from ui.dialogs import SelezionaHolderDialog
            dlg = SelezionaHolderDialog(self.parent, alias,
                                        self.main.df_holder_smontati,
                                        self.main.df_bussole_idraulico)
            if not dlg.success:
                return

            alias_finale  = dlg.alias_finale
            holder_usato  = dlg.holder_cod
            bussola_usata = dlg.bussola_cod

            # Decrementa holder
            df_h = self.main.df_holder_smontati
            if not df_h.empty:
                df_h["Alias_Holder"] = df_h["Alias_Holder"].astype(str).str.strip()
                hs = str(holder_usato).strip()
                if hs in df_h["Alias_Holder"].values:
                    m = df_h["Alias_Holder"] == hs
                    df_h.loc[m, "Quantita"] = df_h.loc[m, "Quantita"].astype(int) - 1
                    df_h = df_h[df_h["Quantita"] > 0].reset_index(drop=True)
                    self.main.df_holder_smontati = df_h
                    from database.db_handler import salva_database_holder_smontati
                    salva_database_holder_smontati(df_h, self.main.db_paths.get("holder_smontati", ""))

            # Decrementa bussola
            if bussola_usata:
                df_b = self.main.df_bussole_idraulico
                if not df_b.empty:
                    df_b["Codice_Bussola"] = df_b["Codice_Bussola"].astype(str).str.strip()
                    bs = str(bussola_usata).strip()
                    if bs in df_b["Codice_Bussola"].values:
                        m = df_b["Codice_Bussola"] == bs
                        df_b.loc[m, "Quantita"] = df_b.loc[m, "Quantita"].astype(int) - 1
                        df_b = df_b[df_b["Quantita"] > 0].reset_index(drop=True)
                        self.main.df_bussole_idraulico = df_b
                        from database.db_handler import salva_database_bussole_idraulico
                        salva_database_bussole_idraulico(df_b, self.main.db_paths.get("bussole_idraulico", ""))

            import pandas as pd
            from database.db_handler import salva_database
            new_row = pd.DataFrame([{"Posizione": "", "Alias": alias_finale, "Stato_Utensile": STATO_SCAFFALE}])
            self.main.df = pd.concat([self.main.df, new_row], ignore_index=True)
            ok, err = salva_database(self.main.df, self.main.db_path)
            if ok:
                self.main.refresh_all_tabs()
                self.main._update_status()
                self.tree.delete(sel[0])
                messagebox.showinfo("Successo", f"'{alias_finale}' aggiunto a Scaffale")
            else:
                messagebox.showerror("Errore", err)
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    # ── Azioni ────────────────────────────────────────────────────────────────

    def _apri_calibra_settings(self):
        try:
            from ui.calibra_only_settings_dialog import show_calibra_settings
            show_calibra_settings(self.parent)
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _invia_tutto(self):
        if not self.file_paths:
            return messagebox.showwarning("Attenzione", "Nessun file caricato")
        progetto = self.entry_nome.get().strip()
        if not progetto:
            return messagebox.showwarning("Attenzione", "Inserisci il nome progetto")
        try:
            from ui.dialog_invia_macchina import DialogInviaMacchina
            paths = list(self.file_paths)
            if self._main_generato_path and os.path.exists(self._main_generato_path):
                if self._main_generato_path not in paths:
                    paths.insert(0, self._main_generato_path)
            dlg = DialogInviaMacchina(self.parent, paths, progetto)
            self.parent.wait_window(dlg)
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _invia_solo_main(self):
        if not self._main_generato_path or not os.path.exists(self._main_generato_path):
            return messagebox.showwarning("Attenzione", "Genera prima il file MAIN")
        progetto = self.entry_nome.get().strip()
        if not progetto:
            return messagebox.showwarning("Attenzione", "Inserisci il nome progetto")
        try:
            from ui.dialog_invia_macchina import DialogInviaMacchina
            dlg = DialogInviaMacchina(self.parent, [self._main_generato_path], progetto)
            self.parent.wait_window(dlg)
        except Exception as e:
            messagebox.showerror("Errore", str(e))

    def _genera_main(self):
        if not self.file_paths:
            return messagebox.showwarning("Attenzione", "Seleziona almeno un file")
        nome = self.entry_nome.get().strip()
        if not nome:
            return messagebox.showwarning("Attenzione", "Inserisci il nome cartella")
        # fase non incide sul nome MAIN né sugli EXTCALL
        nome_completo = nome
        try:
            from logic.nc_analyzer import genera_programma_main_gcode
            gcode, filename = genera_programma_main_gcode(self.file_paths, nome_completo)
            save_path = filedialog.asksaveasfilename(
                title="Salva MAIN", initialfile=filename,
                defaultextension=".MPF",
                filetypes=[("MPF", "*.MPF"), ("Tutti", "*.*")])
            if not save_path:
                return
            with open(save_path, "w", encoding="utf-8") as f:
                f.write(gcode)
            self._main_generato_path = save_path
            self.btn_solo_main.configure(state="normal")
            messagebox.showinfo("MAIN generato",
                f"File salvato:\n{save_path}")
        except Exception as e:
            messagebox.showerror("Errore generazione", str(e))
