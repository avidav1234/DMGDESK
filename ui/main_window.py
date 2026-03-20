"""
Main Window - Tool Manager V14
Finestra principale con TabView
"""

import customtkinter as ctk
from tkinter import messagebox
import pandas as pd

from config.theme import *
from config.constants import *
from database.db_handler import *

from .tab_macchina import TabMacchina
from .tab_scaffale import TabScaffale
from .tab_smontati import TabSmontati
from .tab_holder_bussole import TabHolderBussole
from .tab_analisi_nc import TabAnalisiNC
from .tab_generatore import TabGeneratore
from .tab_utensili_macchina import TabUtensiliMacchina


class MainWindow(ctk.CTk):
    """Finestra principale applicazione."""
    
    def __init__(self):
        super().__init__()
        
        # Configurazione
        self.title(APP_TITLE)
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        
        # Database
        self.config = carica_configurazione()
        self.db_path = self.config.get('database_path')
        self.db_paths = {}
        
        # DataFrames
        self.df = pd.DataFrame(columns=DB_COLUMNS_PRINCIPALE)
        self.df_utensili_smontati = pd.DataFrame()
        self.df_holder_smontati = pd.DataFrame()
        self.df_bussole_idraulico = pd.DataFrame()
        
        # Crea UI
        self._create_ui()
        
        # Carica dati iniziali
        if self.db_path:
            self._load_all_data()
    
    def _create_ui(self):
        """Crea interfaccia utente."""
        # Header - BLU come i tab
        header = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, height=int(70), corner_radius=0)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text=APP_TITLE,
            font=get_font("header", bold=True),
            text_color="white"
        ).pack(side="left", padx=20)
        
        # Pulsanti header - Chiari su blu
        btn_frame = ctk.CTkFrame(header, fg_color="transparent")
        btn_frame.pack(side="right", padx=20)
        
        # Bottoni header con stile chiaro su blu
        for text, cmd in [
            ("📁 DATABASE", self._seleziona_database),
            ("📊 ANALIZZA NC", self._analizza_nc),
            ("🔄 RICARICA", self._load_all_data)
        ]:
            ctk.CTkButton(
                btn_frame,
                text=text,
                command=cmd,
                fg_color="white",              # Bianco
                hover_color="#E3F2FD",         # Azzurro chiaro
                text_color=COLOR_PRIMARY,      # Testo blu
                width=140,
                height=36,
                font=(FONT_FAMILY, 11, "bold"),
                corner_radius=6
            ).pack(side="left", padx=5)
        
        # Status bar
        self.status_label = ctk.CTkLabel(
            self,
            text="Nessun database caricato",
            font=get_font("normal"),
            anchor="w"
        )
        self.status_label.pack(fill="x", padx=20, pady=5)
        
        # TabView - Tab BIANCHI quando non selezionati, BLU quando selezionati
        self.tabview = ctk.CTkTabview(
            self,
            fg_color=COLOR_BACKGROUND,
            # TAB BIANCHI/BLU con contrasto perfetto
            segmented_button_fg_color="#FFFFFF",              # BIANCO per sfondo generale
            segmented_button_selected_color="#2196F3",        # BLU quando selezionato
            segmented_button_selected_hover_color="#1976D2",  # BLU scuro hover
            segmented_button_unselected_color="#FFFFFF",      # BIANCO quando non selezionato
            segmented_button_unselected_hover_color="#F5F5F5",# Grigio chiarissimo hover
            text_color="#616161",                             # Grigio scuro per testo
            text_color_disabled="#9E9E9E",
            border_width=1,
            border_color="#E0E0E0"                            # Bordo sottile per separare tab
        )
        self.tabview.pack(fill="both", expand=True, padx=10, pady=10)
        
        # TAB MOLTO PIÙ GRANDI - 70px height, font 16pt
        self.tabview._segmented_button.configure(
            font=(FONT_FAMILY, TAB_FONT_SIZE, "bold"),        # 16pt bold
            height=TAB_HEIGHT                                 # 70px
        )
        
        # Crea tabs - ANALISI NC PRIMO!
        self.tabview.add("📄 Analisi NC")
        self.tabview.add("📝 Generatore")
        self.tabview.add("🗂 Utensili Macchina")
        self.tabview.add("🔧 In Macchina")
        self.tabview.add("🏠 Scaffale")
        self.tabview.add("📦 Smontati")
        self.tabview.add("🔩 Holder & Bussole")
        
        # Inizializza tabs
        self.tab_analisi_nc = TabAnalisiNC(
            self.tabview.tab("📄 Analisi NC"),
            self
        )
        
        self.tab_generatore = TabGeneratore(
            self.tabview.tab("📝 Generatore"),
            self
        )

        self.tab_utensili_macchina = TabUtensiliMacchina(
            self.tabview.tab("🗂 Utensili Macchina"),
            self
        )

        self.tab_macchina = TabMacchina(
            self.tabview.tab("🔧 In Macchina"),
            self
        )
        
        self.tab_scaffale = TabScaffale(
            self.tabview.tab("🏠 Scaffale"),
            self
        )
        
        self.tab_smontati = TabSmontati(
            self.tabview.tab("📦 Smontati"),
            self
        )
        
        self.tab_holder_bussole = TabHolderBussole(
            self.tabview.tab("🔩 Holder & Bussole"),
            self
        )
        
        # Imposta tab Analisi NC come default
        self.tabview.set("📄 Analisi NC")
    
    def _seleziona_database(self):
        """Apre dialog selezione database."""
        from tkinter import filedialog
        
        path = filedialog.askopenfilename(
            title="Seleziona Database Principale",
            filetypes=[("CSV", "*.csv"), ("Tutti", "*.*")]
        )
        
        if path:
            self.db_path = path
            config = {"database_path": path}
            salva_configurazione(config)
            self._load_all_data()
    
    def _load_all_data(self):
        """Carica tutti i database."""
        print("\n=== _LOAD_ALL_DATA ===")
        
        if not self.db_path:
            print("ERRORE: db_path è None!")
            return
        
        print(f"db_path: {self.db_path}")
        
        # Ottieni paths
        self.db_paths = get_db_paths(self.db_path)
        print(f"db_paths generati:")
        for k, v in self.db_paths.items():
            print(f"  {k}: {v}")
        
        # Carica principale
        self.df, err = carica_database(self.db_path)
        if err:
            messagebox.showerror("Errore", err)
            return
        
        print(f"DB principale caricato: {len(self.df)} righe")
        
        # Carica smontati
        self.df_utensili_smontati, _ = carica_database_utensili_smontati(
            self.db_paths.get('utensili_smontati', '')
        )
        
        print(f"DB utensili_smontati caricato: {len(self.df_utensili_smontati)} righe")
        
        # Carica holder
        self.df_holder_smontati, _ = carica_database_holder_smontati(
            self.db_paths.get('holder_smontati', '')
        )
        
        # Carica bussole
        self.df_bussole_idraulico, _ = carica_database_bussole_idraulico(
            self.db_paths.get('bussole_idraulico', '')
        )
        
        # Aggiorna UI
        self.refresh_all_tabs()
        self._update_status()
    
    def refresh_all_tabs(self):
        """Aggiorna tutti i tab."""
        self.tab_generatore.refresh()
        self.tab_macchina.refresh()
        self.tab_scaffale.refresh()
        self.tab_smontati.refresh()
        self.tab_holder_bussole.refresh()
    
    def _update_status(self):
        """Aggiorna status bar."""
        n_macchina = len(self.df[self.df['Stato_Utensile'] == STATO_IN_MACCHINA])
        n_scaffale = len(self.df[self.df['Stato_Utensile'] == STATO_SCAFFALE])
        n_smontati = len(self.df_utensili_smontati)
        n_holder = len(self.df_holder_smontati)
        n_bussole = len(self.df_bussole_idraulico)
        
        status = f"📊 In Macchina: {n_macchina} | Scaffale: {n_scaffale} | "
        status += f"Smontati: {n_smontati} | Holder: {n_holder} | Bussole: {n_bussole}"
        
        self.status_label.configure(text=status)
    
    def _analizza_nc(self):
        """Analizza programma NC."""
        if self.df.empty:
            messagebox.showwarning("Attenzione", "Carica prima il database")
            return
        
        from logic.nc_analyzer import analizza_programma_nc_dialog
        analizza_programma_nc_dialog(self, self.df)
