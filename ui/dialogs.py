"""
Dialogs per Tool Manager V14
"""

import customtkinter as ctk
from tkinter import messagebox
import tkinter.ttk as ttk

from config.theme import *
from config.constants import *


class SelezionaHolderDialog:
    """
    Dialog per selezionare holder (e bussola se holder E).
    Usato quando si aggiunge utensile mancante per garantire invarianza.
    """
    
    def __init__(self, parent, alias_utensile, df_holder, df_bussole):
        self.alias_utensile = alias_utensile
        self.df_holder = df_holder
        self.df_bussole = df_bussole
        self.success = False
        
        # Output
        self.alias_finale = None
        self.holder_cod = None
        self.bussola_cod = None
        
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("🔧 Seleziona Holder")
        self.dialog.geometry("700x650")
        self.dialog.transient(parent)
        self.dialog.attributes("-topmost", True)
        self.dialog.grab_set()
        
        self._create_ui()
        
        # Blocca finestra padre
        self.dialog.wait_window()
    
    def _create_ui(self):
        """Crea interfaccia dialog."""
        # Info utensile
        info = ctk.CTkFrame(self.dialog, fg_color=COLOR_PRIMARY_LIGHT, corner_radius=int(10))
        info.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(info, text=f"📦 Utensile: {self.alias_utensile}",
                    font=get_font("title", bold=True),
                    text_color=COLOR_PRIMARY_DARK).pack(pady=10)
        
        ctk.CTkLabel(info, text="Seleziona holder e bussola (se necessario)",
                    font=get_font("body"),
                    text_color=COLOR_TEXT_SECONDARY).pack(pady=(0, 10))
        
        # Holder
        ctk.CTkLabel(self.dialog, text="🔧 HOLDER DISPONIBILI:",
                    font=get_font("subtitle", bold=True)).pack(pady=(10, 5))
        
        tree_frame_h = ctk.CTkFrame(self.dialog, fg_color=COLOR_SURFACE)
        tree_frame_h.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tree_holder = ttk.Treeview(tree_frame_h,
                                       columns=("Tipo", "Cod", "Qty"),
                                       show="headings", height=int(10))
        self.tree_holder.heading("Tipo", text="TIPO")
        self.tree_holder.heading("Cod", text="CODICE")
        self.tree_holder.heading("Qty", text="QTY")
        self.tree_holder.column("Tipo", width=int(250))
        self.tree_holder.column("Cod", width=int(150))
        self.tree_holder.column("Qty", width=int(100))
        
        # Popola holder CON DIAMETRO
        if not self.df_holder.empty:
            from database.db_handler import decodifica_holder
            for _, row in self.df_holder.iterrows():
                alias_h = row['Alias_Holder']
                tipo, diam, cod_base = decodifica_holder(alias_h)
                
                # Mostra tipo + diametro se presente
                if diam:
                    tipo_display = f"{tipo} {diam}"
                else:
                    tipo_display = tipo
                
                # Mostra alias completo (con numero) come codice
                self.tree_holder.insert("", "end", values=(tipo_display, alias_h, row['Quantita']))
        
        self.tree_holder.pack(fill="both", expand=True, padx=10, pady=10)
        self.tree_holder.bind('<<TreeviewSelect>>', self._on_holder_select)
        
        # Bussole (dinamico - appare solo se holder E)
        self.bussole_frame = None
        self.tree_bussole = None
        
        # Bottoni
        btn_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=20)
        
        ctk.CTkButton(btn_frame, text="❌ Annulla", command=self._annulla,
                     **get_button_style("neutral", "medium")).pack(side="left", padx=5)
        
        ctk.CTkButton(btn_frame, text="✅ CONFERMA", command=self._conferma,
                     **get_button_style("success", "large")).pack(side="right", padx=5)
    
    def _on_holder_select(self, event):
        """Handler selezione holder."""
        sel = self.tree_holder.selection()
        if not sel:
            return
        
        cod_h = self.tree_holder.item(sel[0])['values'][1]
        
        # Se holder E, mostra bussole
        if cod_h == "E":
            self._mostra_bussole()
        else:
            self._nascondi_bussole()
    
    def _mostra_bussole(self):
        """Mostra selezione bussole."""
        if self.bussole_frame:
            return  # Già visibile
        
        self.bussole_frame = ctk.CTkFrame(self.dialog, fg_color=COLOR_SURFACE)
        self.bussole_frame.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        
        ctk.CTkLabel(self.bussole_frame, text="🔩 BUSSOLE DISPONIBILI:",
                    font=get_font("subtitle", bold=True),
                    text_color=COLOR_ACCENT).pack(pady=5)
        
        self.tree_bussole = ttk.Treeview(self.bussole_frame,
                                        columns=("Cod", "Qty"),
                                        show="headings", height=int(6))
        self.tree_bussole.heading("Cod", text="CODICE")
        self.tree_bussole.heading("Qty", text="QTY")
        self.tree_bussole.column("Cod", width=int(200))
        self.tree_bussole.column("Qty", width=int(100))
        
        # Popola bussole
        if not self.df_bussole.empty:
            for _, row in self.df_bussole.iterrows():
                self.tree_bussole.insert("", "end", values=(row['Codice_Bussola'], row['Quantita']))
        
        self.tree_bussole.pack(fill="both", expand=True, padx=10, pady=10)
    
    def _nascondi_bussole(self):
        """Nascondi selezione bussole."""
        if self.bussole_frame:
            self.bussole_frame.destroy()
            self.bussole_frame = None
            self.tree_bussole = None
    
    def _annulla(self):
        """Annulla dialog."""
        self.success = False
        self.dialog.destroy()
    
    def _conferma(self):
        """Conferma selezione."""
        # Verifica holder selezionato
        sel_h = self.tree_holder.selection()
        if not sel_h:
            return messagebox.showwarning("Attenzione", "Seleziona un holder")
        
        cod_h = self.tree_holder.item(sel_h[0])['values'][1]
        
        # Se holder E, verifica bussola
        cod_bus = None
        if cod_h == "E":
            if not self.tree_bussole or not self.tree_bussole.selection():
                return messagebox.showwarning("Attenzione", "Seleziona una bussola per holder E")
            cod_bus = self.tree_bussole.item(self.tree_bussole.selection()[0])['values'][0]
            alias_finale = f"{self.alias_utensile}{cod_bus}"
        else:
            alias_finale = f"{self.alias_utensile}{cod_h}"
        
        # Salva risultati
        self.alias_finale = alias_finale
        self.holder_cod = cod_h
        self.bussola_cod = cod_bus
        self.success = True
        
        self.dialog.destroy()
