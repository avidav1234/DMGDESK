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
from .tab_scaffale import TabScaffale
from .tab_smontati import TabSmontati
from .tab_holder_bussole import TabHolderBussole
from .tab_analisi_nc import TabAnalisiNC
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
        self.tabview.add("⬡ Coda")
        self.tabview.add("📄 Analisi NC")
        self.tabview.add("📝 Generatore")
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
        
        self.tab_coda = TabCodaLavorazione(
            self.tabview.tab("⬡ Coda"),
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
        self.tabview.set("⬡ Coda")
    
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
