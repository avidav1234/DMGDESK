"""Tab Holder & Bussole - Split view affiancato"""
import customtkinter as ctk
from tkinter import messagebox, simpledialog
import tkinter.ttk as ttk
import pandas as pd

from config.theme import *
from config.constants import *
from database.db_handler import *


class TabHolderBussole:
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main = main_window
        self._create_ui()
    
    def _create_ui(self):
        # Header principale tab - BLU come altri tab
        main_header = ctk.CTkFrame(self.parent, fg_color=COLOR_PRIMARY, height=int(80))
        main_header.pack(fill="x")
        main_header.pack_propagate(False)
        
        ctk.CTkLabel(main_header, text="🔩 HOLDER E BUSSOLE",
                    font=get_font("title", bold=True),
                    text_color="white").pack(pady=(12, 2))
        
        ctk.CTkLabel(main_header, text="Gestisci inventario holder smontati e bussole idrauliche",
                    font=get_font("body"),
                    text_color="white").pack(pady=(0, 8))  # Bianco invece di rosa
        
        # Split container
        container = ctk.CTkFrame(self.parent, fg_color="transparent")
        container.pack(fill="both", expand=True, pady=(10, 0))
        
        # LEFT: Holder - BLU SCURO
        left = ctk.CTkFrame(container, fg_color=COLOR_SURFACE, corner_radius=int(10))
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        header_h = ctk.CTkFrame(left, fg_color=COLOR_PRIMARY_DARK, height=int(70), corner_radius=int(10))
        header_h.pack(fill="x")
        header_h.pack_propagate(False)
        ctk.CTkLabel(header_h, text="🔧 HOLDER SMONTATI", font=get_font("subtitle", bold=True),
                    text_color="white").pack(pady=(10, 2))
        ctk.CTkLabel(header_h, text="Holder disponibili per montaggio", font=get_font("caption"),
                    text_color="white").pack(pady=(0, 8))
        
        toolbar_h = ctk.CTkFrame(left, fg_color="transparent")
        toolbar_h.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(toolbar_h, text="➕", command=self._aggiungi_holder,
                     **get_button_style("success", "small")).pack(side="left", padx=3)  # Verde
        ctk.CTkButton(toolbar_h, text="✏️", command=self._modifica_holder,
                     **get_button_style("primary", "small")).pack(side="left", padx=3)  # Blu
        ctk.CTkButton(toolbar_h, text="🗑️", command=self._elimina_holder,
                     **get_button_style("error", "small")).pack(side="left", padx=3)    # Rosso
        
        self.tree_holder = ttk.Treeview(left, columns=("Tipo", "Cod", "Qty"),
                                       show="headings")
        self.tree_holder.heading("Tipo", text="TIPO")
        self.tree_holder.heading("Cod", text="CODICE")
        self.tree_holder.heading("Qty", text="QTY")
        self.tree_holder.column("Tipo", width=int(200))
        self.tree_holder.column("Cod", width=int(100))
        self.tree_holder.column("Qty", width=int(80))
        self.tree_holder.pack(fill="both", expand=True, padx=10, pady=10)
        
        # RIGHT: Bussole - VERDE TENUE
        right = ctk.CTkFrame(container, fg_color=COLOR_SURFACE, corner_radius=int(10))
        right.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        header_b = ctk.CTkFrame(right, fg_color=COLOR_SUCCESS, height=int(70), corner_radius=int(10))
        header_b.pack(fill="x")
        header_b.pack_propagate(False)
        ctk.CTkLabel(header_b, text="🔩 BUSSOLE IDRAULICO", font=get_font("subtitle", bold=True),
                    text_color="white").pack(pady=(10, 2))
        ctk.CTkLabel(header_b, text="Bussole E disponibili per holder", font=get_font("caption"),
                    text_color="white").pack(pady=(0, 8))
        
        toolbar_b = ctk.CTkFrame(right, fg_color="transparent")
        toolbar_b.pack(fill="x", padx=10, pady=10)
        
        ctk.CTkButton(toolbar_b, text="➕", command=self._aggiungi_bussola,
                     **get_button_style("success", "small")).pack(side="left", padx=3)  # Verde
        ctk.CTkButton(toolbar_b, text="✏️", command=self._modifica_bussola,
                     **get_button_style("primary", "small")).pack(side="left", padx=3)  # Blu
        ctk.CTkButton(toolbar_b, text="🗑️", command=self._elimina_bussola,
                     **get_button_style("error", "small")).pack(side="left", padx=3)    # Rosso
        
        self.tree_bussole = ttk.Treeview(right, columns=("Cod", "Ø", "Qty"),
                                        show="headings")
        self.tree_bussole.heading("Cod", text="CODICE")
        self.tree_bussole.heading("Ø", text="Ø FINALE")
        self.tree_bussole.heading("Qty", text="QTY")
        self.tree_bussole.column("Cod", width=int(120))
        self.tree_bussole.column("Ø", width=int(120))
        self.tree_bussole.column("Qty", width=int(80))
        self.tree_bussole.pack(fill="both", expand=True, padx=10, pady=10)
    
    def refresh(self):
        # Holder CON DIAMETRO
        self.tree_holder.delete(*self.tree_holder.get_children())
        for idx, row in self.main.df_holder_smontati.iterrows():
            alias_h = row['Alias_Holder']
            tipo, diam, cod_base = decodifica_holder(alias_h)
            
            # Mostra tipo + diametro se presente
            if diam:
                tipo_display = f"{tipo} {diam}"
            else:
                tipo_display = tipo
            
            # Mostra alias completo (con numero) come codice
            self.tree_holder.insert("", "end", values=(tipo_display, alias_h, row['Quantita']), tags=(idx,))
        
        # Bussole
        self.tree_bussole.delete(*self.tree_bussole.get_children())
        for idx, row in self.main.df_bussole_idraulico.iterrows():
            self.tree_bussole.insert("", "end", values=(
                row['Codice_Bussola'], row['Diametro'], row['Quantita']
            ), tags=(idx,))
    
    def _aggiungi_holder(self):
        from utils.dialogs import InputDialog
        dialog = InputDialog(self.parent, "Aggiungi Holder",
                           [("Codice (es: E, H4, K3)", "text"), ("Quantità", "text", "1")])
        
        if dialog.result:
            cod, qty = dialog.result
            cod_upper = cod.upper().strip()
            qty_int = int(qty)
            
            # CONTROLLA SE ESISTE GIÀ
            if not self.main.df_holder_smontati.empty:
                # Strip spazi per confronto
                self.main.df_holder_smontati['Alias_Holder'] = \
                    self.main.df_holder_smontati['Alias_Holder'].astype(str).str.strip()
                
                if cod_upper in self.main.df_holder_smontati['Alias_Holder'].values:
                    # ESISTE → INCREMENTA quantità
                    idx = self.main.df_holder_smontati['Alias_Holder'] == cod_upper
                    qty_prima = self.main.df_holder_smontati.loc[idx, 'Quantita'].values[0]
                    self.main.df_holder_smontati.loc[idx, 'Quantita'] = \
                        self.main.df_holder_smontati.loc[idx, 'Quantita'].astype(int) + qty_int
                    qty_dopo = self.main.df_holder_smontati.loc[idx, 'Quantita'].values[0]
                    
                    print(f"Holder {cod_upper} incrementato: {qty_prima} → {qty_dopo}")
                    
                    salva_database_holder_smontati(
                        self.main.df_holder_smontati,
                        self.main.db_paths.get('holder_smontati', '')
                    )
                    self.main.refresh_all_tabs()
                    messagebox.showinfo("Successo", 
                        f"Holder {cod_upper} incrementato!\n"
                        f"Quantità: {qty_prima} → {qty_dopo}")
                    return
            
            # NON ESISTE → CREA NUOVO
            new_row = {
                'Alias_Holder': cod_upper,
                'Quantita': qty_int,
                'Data_Smontaggio': pd.Timestamp.now().strftime('%Y-%m-%d'),
                'Note': ''
            }
            self.main.df_holder_smontati = pd.concat([
                self.main.df_holder_smontati, pd.DataFrame([new_row])
            ], ignore_index=True)
            
            print(f"Holder {cod_upper} aggiunto nuovo (qty: {qty_int})")
            
            salva_database_holder_smontati(
                self.main.df_holder_smontati,
                self.main.db_paths.get('holder_smontati', '')
            )
            self.main.refresh_all_tabs()
            messagebox.showinfo("Successo", f"Holder {cod_upper} aggiunto (qty: {qty_int})")
    
    def _modifica_holder(self):
        sel = self.tree_holder.selection()
        if not sel:
            return messagebox.showwarning("Attenzione", "Seleziona holder")
        
        idx = self.tree_holder.item(sel[0])['tags'][0]
        cod = self.main.df_holder_smontati.at[idx, 'Alias_Holder']
        qty_att = self.main.df_holder_smontati.at[idx, 'Quantita']
        
        nuova = simpledialog.askinteger("Modifica", f"Holder {cod}\n\nNuova quantità:",
                                       initialvalue=qty_att, minvalue=0)
        if nuova is not None:
            self.main.df_holder_smontati.at[idx, 'Quantita'] = nuova
            salva_database_holder_smontati(
                self.main.df_holder_smontati,
                self.main.db_paths.get('holder_smontati', '')
            )
            self.main.refresh_all_tabs()
            messagebox.showinfo("Successo", f"Qty → {nuova}")
    
    def _elimina_holder(self):
        sel = self.tree_holder.selection()
        if not sel or not messagebox.askyesno("Conferma", "Eliminare?"):
            return
        
        idx = self.tree_holder.item(sel[0])['tags'][0]
        self.main.df_holder_smontati = self.main.df_holder_smontati.drop(idx).reset_index(drop=True)
        salva_database_holder_smontati(
            self.main.df_holder_smontati,
            self.main.db_paths.get('holder_smontati', '')
        )
        self.main.refresh_all_tabs()
        messagebox.showinfo("Successo", "Eliminato")
    
    def _aggiungi_bussola(self):
        from utils.dialogs import InputDialog
        dialog = InputDialog(self.parent, "Aggiungi Bussola",
                           [("Codice (E1-E8)", "text"), ("Quantità", "text", "1")])
        
        if dialog.result:
            cod, qty = dialog.result
            cod = cod.upper().strip()
            qty_int = int(qty)
            
            import re
            if not re.match(r'^E[1-8]$', cod):
                return messagebox.showerror("Errore", "Codice non valido (E1-E8)")
            
            numero = int(cod[1])
            diametro = BUSSOLE_IDRAULICO_E.get(numero, '')
            
            # CONTROLLA SE ESISTE GIÀ
            if not self.main.df_bussole_idraulico.empty:
                # Strip spazi per confronto
                self.main.df_bussole_idraulico['Codice_Bussola'] = \
                    self.main.df_bussole_idraulico['Codice_Bussola'].astype(str).str.strip()
                
                if cod in self.main.df_bussole_idraulico['Codice_Bussola'].values:
                    # ESISTE → INCREMENTA quantità
                    idx = self.main.df_bussole_idraulico['Codice_Bussola'] == cod
                    qty_prima = self.main.df_bussole_idraulico.loc[idx, 'Quantita'].values[0]
                    self.main.df_bussole_idraulico.loc[idx, 'Quantita'] = \
                        self.main.df_bussole_idraulico.loc[idx, 'Quantita'].astype(int) + qty_int
                    qty_dopo = self.main.df_bussole_idraulico.loc[idx, 'Quantita'].values[0]
                    
                    print(f"Bussola {cod} incrementata: {qty_prima} → {qty_dopo}")
                    
                    salva_database_bussole_idraulico(
                        self.main.df_bussole_idraulico,
                        self.main.db_paths.get('bussole_idraulico', '')
                    )
                    self.main.refresh_all_tabs()
                    messagebox.showinfo("Successo", 
                        f"Bussola {cod} incrementata!\n"
                        f"Quantità: {qty_prima} → {qty_dopo}")
                    return
            
            # NON ESISTE → CREA NUOVO
            new_row = {
                'Codice_Bussola': cod,
                'Diametro': diametro,
                'Quantita': qty_int,
                'Data_Acquisizione': pd.Timestamp.now().strftime('%Y-%m-%d'),
                'Note': ''
            }
            self.main.df_bussole_idraulico = pd.concat([
                self.main.df_bussole_idraulico, pd.DataFrame([new_row])
            ], ignore_index=True)
            
            print(f"Bussola {cod} aggiunta nuova (qty: {qty_int})")
            
            salva_database_bussole_idraulico(
                self.main.df_bussole_idraulico,
                self.main.db_paths.get('bussole_idraulico', '')
            )
            self.main.refresh_all_tabs()
            messagebox.showinfo("Successo", f"Bussola {cod} aggiunta (qty: {qty_int})")
    
    def _modifica_bussola(self):
        sel = self.tree_bussole.selection()
        if not sel:
            return messagebox.showwarning("Attenzione", "Seleziona bussola")
        
        idx = self.tree_bussole.item(sel[0])['tags'][0]
        cod = self.main.df_bussole_idraulico.at[idx, 'Codice_Bussola']
        qty_att = self.main.df_bussole_idraulico.at[idx, 'Quantita']
        
        nuova = simpledialog.askinteger("Modifica", f"Bussola {cod}\n\nNuova quantità:",
                                       initialvalue=qty_att, minvalue=0)
        if nuova is not None:
            self.main.df_bussole_idraulico.at[idx, 'Quantita'] = nuova
            salva_database_bussole_idraulico(
                self.main.df_bussole_idraulico,
                self.main.db_paths.get('bussole_idraulico', '')
            )
            self.main.refresh_all_tabs()
            messagebox.showinfo("Successo", f"Qty → {nuova}")
    
    def _elimina_bussola(self):
        sel = self.tree_bussole.selection()
        if not sel or not messagebox.askyesno("Conferma", "Eliminare?"):
            return
        
        idx = self.tree_bussole.item(sel[0])['tags'][0]
        self.main.df_bussole_idraulico = self.main.df_bussole_idraulico.drop(idx).reset_index(drop=True)
        salva_database_bussole_idraulico(
            self.main.df_bussole_idraulico,
            self.main.db_paths.get('bussole_idraulico', '')
        )
        self.main.refresh_all_tabs()
        messagebox.showinfo("Successo", "Eliminato")
