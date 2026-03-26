"""
Main Window - Tool Manager V12.4
Finestra principale con TabView
"""

import customtkinter as ctk
from tkinter import messagebox
import pandas as pd

from config.theme import *
from config.constants import *
from database.db_handler import *

from .tab_coda_lavorazione import TabCodaLavorazione
from .tab_macchina import TabMacchina
from .tab_progetti import TabProgetti
from .tab_scaffale import TabScaffale
from .tab_smontati import TabSmontati
from .tab_holder_bussole import TabHolderBussole
from .tab_analisi_nc import TabAnalisiNC
from .tab_home import TabHome
from .tab_generatore import TabGeneratore


class MainWindow(ctk.CTk):
    """Finestra principale applicazione."""
    
    def __init__(self):
        super().__init__()
        
        # Configurazione
        self.title(APP_TITLE)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        
        # Database — auto-discovery dalla cartella TOA/MPF
        self.config = carica_configurazione()
        self.db_paths = auto_find_db_paths(self.config)
        self.db_path = self.db_paths.get('principale')
        
        # DataFrames
        self.df = pd.DataFrame(columns=DB_COLUMNS_PRINCIPALE)
        self.df_utensili_smontati = pd.DataFrame()
        self.df_holder_smontati = pd.DataFrame()
        self.df_bussole_idraulico = pd.DataFrame()
        
        # Crea UI
        self._create_ui()
        
        # Carica sempre — auto_find_db_paths crea i file vuoti se mancano
        self._load_all_data()
    
    def _create_ui(self):
        """Crea interfaccia — sidebar verticale navy + content area."""
        import tkinter as _tk

        NAVY    = "#0d2d5e"
        NAVY_LT = "#144080"
        ACCENT  = "#7eb8f5"
        BG      = "#eef2f7"

        # ── Layout principale: sidebar sx + content dx ──────────────────────
        root_frame = _tk.Frame(self, bg=BG)
        root_frame.pack(fill="both", expand=True)

        # ── Sidebar ─────────────────────────────────────────────────────────
        sidebar = _tk.Frame(root_frame, bg=NAVY, width=88)
        sidebar.pack(side="left", fill="y")
        sidebar.pack_propagate(False)

        # Logo
        logo_frame = _tk.Frame(sidebar, bg=NAVY)
        logo_frame.pack(pady=(14,4))
        logo_box = _tk.Frame(logo_frame, bg="#1a3f6f", width=48, height=48)
        logo_box.pack()
        logo_box.pack_propagate(False)
        _tk.Label(logo_box, text="DMG", font=("Inter",11,"bold"),
                  fg="#fff", bg="#1a3f6f").place(relx=0.5,rely=0.5,anchor="center")
        _tk.Label(sidebar, text="LIVE", font=("Inter",7,"bold"),
                  fg=ACCENT, bg=NAVY).pack(pady=(2,10))

        # Content stack — un Frame per tab, uno alla volta visibile
        self._content = _tk.Frame(root_frame, bg=BG)
        self._content.pack(side="left", fill="both", expand=True)

        # Status bar in basso
        self.status_label = _tk.Label(
            self._content, text="", font=("Inter",9),
            fg="#94a3b8", bg=BG, anchor="w")
        self.status_label.pack(side="bottom", fill="x", padx=12, pady=2)

        # ── Pagine (frame) ──────────────────────────────────────────────────
        self._pages   = {}   # nome → frame
        self._current = None

        def make_page(name):
            f = _tk.Frame(self._content, bg=BG)
            self._pages[name] = f
            return f

        # ── Bottoni sidebar ─────────────────────────────────────────────────
        self._sidebar_btns = {}

        NAV = [
            ("home",      "🏠", "Home"),
            ("lavori",    "📋", "Lavori"),
            ("macchina",  "○",  "Macchina"),
            ("analisi",   "📄", "Analisi NC"),
            ("utensili",  "🔧", "Utensili"),
        ]
        SEP = ("sep", None, None)
        UTILITA = [
            ("generatore","📝","Generatore"),
            ("scaffale",  "📦","Scaffale"),
            ("smontati",  "🔩","Smontati"),
            ("holder",    "⚙", "Holder"),
        ]

        def switch(name):
            if self._current and self._current in self._pages:
                self._pages[self._current].pack_forget()
            if name in self._pages:
                self._pages[name].pack(fill="both", expand=True)
            self._current = name
            for n, btn_data in self._sidebar_btns.items():
                active = (n == name)
                btn_data["frame"].config(
                    bg="#1a5599" if active else NAVY,
                    highlightbackground=ACCENT if active else "#1a3060",
                    highlightthickness=4 if active else 1)
                btn_data["icon_lbl"].config(
                    bg="#1a5599" if active else NAVY,
                    fg="#ffffff" if active else "#c8dff4")
                btn_data["text_lbl"].config(
                    bg="#1a5599" if active else NAVY,
                    fg=ACCENT if active else "#a0c4e8")

        self._switch = switch

        def make_nav_btn(parent, key, icon, label, small=False):
            sz  = 68 if not small else 56
            fsz = 26 if not small else 18
            lsz = 10 if not small else 9
            fr  = _tk.Frame(parent, bg=NAVY, width=sz, height=sz if not small else 46,
                            cursor="hand2", highlightthickness=0)
            fr.pack(pady=1)
            fr.pack_propagate(False)
            il = _tk.Label(fr, text=icon, font=("Arial",fsz), fg="#c8dff4", bg=NAVY)
            il.place(relx=0.5, rely=0.42, anchor="center")
            tl = _tk.Label(fr, text=label, font=("Inter",lsz,"bold"),
                           fg="#a0c4e8", bg=NAVY)
            tl.place(relx=0.5, rely=0.82, anchor="center")
            fr.bind("<Button-1>", lambda e, k=key: switch(k))
            il.bind("<Button-1>", lambda e, k=key: switch(k))
            tl.bind("<Button-1>", lambda e, k=key: switch(k))
            fr.bind("<Enter>", lambda e: fr.config(bg=NAVY_LT) if self._current!=key else None)
            fr.bind("<Leave>", lambda e: fr.config(bg="#1a5599" if self._current==key else NAVY))
            self._sidebar_btns[key] = {"frame":fr,"icon_lbl":il,"text_lbl":tl}

        for key, icon, label in NAV:
            make_nav_btn(sidebar, key, icon, label)

        # Separatore
        sep = _tk.Frame(sidebar, bg="#1a3f6f", height=1, width=50)
        sep.pack(pady=6)

        # Utilità toggle
        self._utilita_open = _tk.BooleanVar(value=False)

        uf = _tk.Frame(sidebar, bg=NAVY, width=60, height=56, cursor="hand2", highlightthickness=0)
        uf.pack(pady=1)
        uf.pack_propagate(False)
        uil = _tk.Label(uf, text="⚙", font=("Arial",22), fg="#c8dff4", bg=NAVY)
        uil.place(relx=0.5, rely=0.38, anchor="center")
        utl = _tk.Label(uf, text="Utilità ▾", font=("Inter",9,"bold"), fg="#a0c4e8", bg=NAVY)
        utl.place(relx=0.5, rely=0.80, anchor="center")

        util_sub = _tk.Frame(sidebar, bg="#0d2d5e")

        def toggle_utilita():
            if self._utilita_open.get():
                util_sub.pack_forget()
                self._utilita_open.set(False)
                utl.config(text="Utilità ▾")
            else:
                util_sub.pack(fill="x")
                self._utilita_open.set(True)
                utl.config(text="Utilità ▴")

        uf.bind("<Button-1>", lambda e: toggle_utilita())
        uil.bind("<Button-1>", lambda e: toggle_utilita())
        utl.bind("<Button-1>", lambda e: toggle_utilita())

        for key, icon, label in UTILITA:
            make_nav_btn(util_sub, key, icon, label, small=True)

        # ── Crea le pagine e assegna i tab ai frame ─────────────────────────
        # Usa CTkTabview nascosto per compatibilità con le tab esistenti
        # In realtà usiamo frame diretti
        self.tabview = type('FakeTabview', (), {
            'tab': lambda self_inner, name: self._pages.get(name),
            'set': lambda self_inner, name: switch(
                {"🏠 Home":"home","○ Macchina":"macchina","📋 Lavori":"lavori",
                 "📄 Analisi NC":"analisi","🔧 Utensili":"utensili",
                 "⚙ Utilità":"lavori"}.get(name, name)),
            'get': lambda self_inner: self._current,
        })()

        # Crea i frame per ogni pagina
        for key in ["home","macchina","lavori","analisi","utensili",
                    "generatore","scaffale","smontati","holder"]:
            make_page(key)

        # Remap tab() per i nomi che usano i tab figli
        _tab_map = {
            "🏠 Home":       "home",
            "○ Macchina":    "macchina",
            "📋 Lavori":     "lavori",
            "📄 Analisi NC": "analisi",
            "🔧 Utensili":   "utensili",
            "📝 Generatore": "generatore",
            "🏗 Scaffale":   "scaffale",
            "📦 Smontati":   "smontati",
            "🔩 Holder & Bussole": "holder",
        }
        _pages_ref = self._pages

        class FakeTabview:
            def tab(self, name):
                return _pages_ref.get(_tab_map.get(name, name))
            def set(self, name):
                switch(_tab_map.get(name, name))
            def get(self):
                return self._current
            def add(self, name):
                pass  # già creati
        self.tabview = FakeTabview()
        
        # Inizializza i componenti direttamente sui frame della sidebar
        self.tab_analisi_nc = TabAnalisiNC(
            self._pages["analisi"], self)
        
        self.tab_coda = TabCodaLavorazione(
            self._pages["macchina"], self)

        self.tab_macchina = TabMacchina(
            self._pages["utensili"], self)

        self.tab_progetti = TabProgetti(
            self._pages["lavori"], self)

        self.tab_generatore = TabGeneratore(
            self._pages["generatore"], self)
        self.tab_scaffale = TabScaffale(
            self._pages["scaffale"], self)
        self.tab_smontati = TabSmontati(
            self._pages["smontati"], self)
        self.tab_holder_bussole = TabHolderBussole(
            self._pages["holder"], self)

        self.tab_home = TabHome(
            self._pages["home"], self)

        # Avvia su Home
        switch("home")
    
    def _seleziona_database(self):
        """Obsoleto — i DB vengono trovati automaticamente dalla cartella TOA."""
        pass
    
    def _load_all_data(self):
        """Carica tutti i database dalla cartella condivisa (TOA/MPF)."""
        # Ri-esegue auto-discovery per aggiornare i path
        self.config  = carica_configurazione()
        self.db_paths = auto_find_db_paths(self.config)
        self.db_path  = self.db_paths.get('principale')

        if not self.db_path:
            # tools_toa_folder non ancora configurato — UI vuota, nessun errore
            self.refresh_all_tabs()
            self._update_status()
            return

        # Carica principale
        self.df, err = carica_database(self.db_path)
        if err and not self.df.empty:
            messagebox.showerror("Errore DB", err)

        # Carica utensili smontati
        self.df_utensili_smontati, _ = carica_database_utensili_smontati(
            self.db_paths.get('utensili_smontati', ''))

        # Carica holder
        self.df_holder_smontati, _ = carica_database_holder_smontati(
            self.db_paths.get('holder_smontati', ''))

        # Carica bussole
        self.df_bussole_idraulico, _ = carica_database_bussole_idraulico(
            self.db_paths.get('bussole_idraulico', ''))

        self.refresh_all_tabs()
        self._update_status()
    
    def refresh_all_tabs(self):
        """Aggiorna tutti i tab."""
        self.tab_generatore.refresh()
        self.tab_coda.refresh()
        self.tab_macchina.refresh()
        self.tab_scaffale.refresh()
        self.tab_smontati.refresh()
        self.tab_holder_bussole.refresh()
    
    def _update_status(self):
        """Aggiorna status bar."""
        # In Macchina: da tools_machine.json (TOA/MPF sync)
        n_macchina = 0
        try:
            import json as _j
            from pathlib import Path as _P
            from ui.tab_macchina import _get_tools_db_path
            tdb = _get_tools_db_path()
            if tdb.exists():
                data = _j.loads(tdb.read_text(encoding="utf-8"))
                n_macchina = len(data.get("tools", {}))
        except Exception:
            n_macchina = len(self.df[self.df['Stato_Utensile'] == STATO_IN_MACCHINA])

        # Scaffale/Smontati/Holder/Bussole: da CSV
        n_scaffale = len(self.df[self.df['Stato_Utensile'] == STATO_SCAFFALE])
        n_smontati = len(self.df_utensili_smontati)
        n_holder   = len(self.df_holder_smontati)
        n_bussole  = len(self.df_bussole_idraulico)

        status = f"In Macchina: {n_macchina} | Scaffale: {n_scaffale} | "
        status += f"Smontati: {n_smontati} | Holder: {n_holder} | Bussole: {n_bussole}"
        self.status_label.configure(text=status)
    
    def _analizza_nc(self):
        """Analizza programma NC."""
        if self.df.empty:
            messagebox.showwarning("Attenzione", "Carica prima il database")
            return
        
        from logic.nc_analyzer import analizza_programma_nc_dialog
        analizza_programma_nc_dialog(self, self.df)
