"""Tab Smontati - Montaggio utensili con holder/bussole"""
import customtkinter as ctk
from tkinter import messagebox
import tkinter.ttk as ttk
import pandas as pd

from config.theme import *
from config.constants import *
from database.db_handler import *


class TabSmontati:
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main = main_window
        self._create_ui()
    
    def _create_ui(self):
        # Header con descrizione
        # Header - BLU come Analisi NC
        header = ctk.CTkFrame(self.parent, fg_color=COLOR_PRIMARY, height=int(80))
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="📦 UTENSILI SMONTATI",
                    font=get_font("title", bold=True),
                    text_color="white").pack(pady=(12, 2))
        
        ctk.CTkLabel(header, text="Utensili rimossi da macchina • Monta con holder e bussole",
                    font=get_font("body"),
                    text_color="white").pack(pady=(0, 8))
        
        toolbar = ctk.CTkFrame(self.parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=(10, 10))
        
        ctk.CTkButton(toolbar, text="🔧 Monta", command=self._monta,
                     **get_button_style("success", "medium")).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="➕ Aggiungi", command=self._aggiungi,
                     **get_button_style("primary", "medium")).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="🗑️ Elimina", command=self._elimina,
                     **get_button_style("error", "medium")).pack(side="left", padx=5)
        
        tree_frame = ctk.CTkFrame(self.parent, fg_color=COLOR_SURFACE)
        tree_frame.pack(fill="both", expand=True)
        
        scroll = ttk.Scrollbar(tree_frame)
        scroll.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(tree_frame,
                                columns=("Alias", "Data", "Prov"),
                                show="headings",
                                yscrollcommand=scroll.set, height=int(25))
        scroll.config(command=self.tree.yview)
        
        self.tree.heading("Alias", text="ALIAS UTENSILE")
        self.tree.heading("Data", text="DATA")
        self.tree.heading("Prov", text="PROVENIENZA")
        
        self.tree.column("Alias", width=int(400))
        self.tree.column("Data", width=int(150))
        self.tree.column("Prov", width=int(200))
        
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        for idx, row in self.main.df_utensili_smontati.iterrows():
            self.tree.insert("", "end", values=(
                row['Alias_Utensile'],
                row.get('Data_Smontaggio', ''),
                row.get('Provenienza', '')
            ), tags=(idx,))
    
    def _monta(self):
        """Apre dialog montaggio completo."""
        sel = self.tree.selection()
        if not sel:
            return messagebox.showwarning("Attenzione", "Seleziona utensile")
        
        item = self.tree.item(sel[0])
        idx = item['tags'][0]
        alias = self.main.df_utensili_smontati.at[idx, 'Alias_Utensile']
        
        # Dialog montaggio
        dialog = MontaggioDialog(self.parent, alias, self.main)
        
        if dialog.success:
            # Rimuovi da smontati
            self.main.df_utensili_smontati = self.main.df_utensili_smontati.drop(idx).reset_index(drop=True)
            salva_database_utensili_smontati(
                self.main.df_utensili_smontati,
                self.main.db_paths.get('utensili_smontati', '')
            )
            
            # Ricarica tutto
            self.main._load_all_data()
    
    def _aggiungi(self):
        from utils.dialogs import InputDialog
        dialog = InputDialog(self.parent, "Aggiungi Utensile Smontato",
                           [("Alias", "text"), ("Provenienza", "text", "Acquisto")])
        
        if dialog.result:
            alias, prov = dialog.result
            new_row = {
                'ID': len(self.main.df_utensili_smontati) + 1,
                'Alias_Utensile': alias,
                'Data_Smontaggio': pd.Timestamp.now().strftime('%Y-%m-%d %H:%M'),
                'Provenienza': prov,
                'Note': ''
            }
            self.main.df_utensili_smontati = pd.concat([
                self.main.df_utensili_smontati,
                pd.DataFrame([new_row])
            ], ignore_index=True)
            
            salva_database_utensili_smontati(
                self.main.df_utensili_smontati,
                self.main.db_paths.get('utensili_smontati', '')
            )
            self.main.refresh_all_tabs()
            messagebox.showinfo("Successo", "Aggiunto a smontati")
    
    def _elimina(self):
        sel = self.tree.selection()
        if not sel or not messagebox.askyesno("Conferma", "Eliminare?"):
            return
        
        idx = self.tree.item(sel[0])['tags'][0]
        self.main.df_utensili_smontati = self.main.df_utensili_smontati.drop(idx).reset_index(drop=True)
        salva_database_utensili_smontati(
            self.main.df_utensili_smontati,
            self.main.db_paths.get('utensili_smontati', '')
        )
        self.main.refresh_all_tabs()
        messagebox.showinfo("Successo", "Eliminato")


class MontaggioDialog:
    """Dialog montaggio con holder/bussole."""
    
    def __init__(self, parent, alias_utensile, main_window):
        self.alias_utensile = alias_utensile
        self.main = main_window
        self.success = False
        self.holder_selezionato = None
        self.bussola_selezionata = None
        
        self.dialog = ctk.CTkToplevel(parent)
        self.dialog.title("🔧 Montaggio Utensile")
        self.dialog.geometry("900x750")
        self.dialog.transient(parent)
        self.dialog.attributes("-topmost", True)
        self.dialog.grab_set()
        
        # Info utensile - GRIGIO invece di azzurro
        info = ctk.CTkFrame(self.dialog, fg_color="#F5F5F5", corner_radius=int(10))
        info.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkLabel(info, text=f"📦 Utensile: {alias_utensile}",
                    font=get_font("large", bold=True)).pack(pady=10)
        
        # Holder
        ctk.CTkLabel(self.dialog, text="🔧 Seleziona Holder:",
                    font=get_font("medium", bold=True)).pack(pady=5)
        
        tree_frame_h = ctk.CTkFrame(self.dialog, fg_color=COLOR_SURFACE)
        tree_frame_h.pack(fill="both", expand=True, padx=20, pady=10)
        
        self.tree_holder = ttk.Treeview(tree_frame_h,
                                       columns=("Tipo", "Cod", "Qty"),
                                       show="headings", height=int(8))
        self.tree_holder.heading("Tipo", text="TIPO")
        self.tree_holder.heading("Cod", text="CODICE")
        self.tree_holder.heading("Qty", text="QTY")
        
        for _, row in main_window.df_holder_smontati.iterrows():
            from database.db_handler import decodifica_holder
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
        
        # Bussole (dinamico)
        self.bussole_frame = None
        self.tree_bussole = None
        
        # Posizione
        pos_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        pos_frame.pack(fill="x", padx=20, pady=10)
        
        self.var_dest = ctk.StringVar(value="macchina")
        ctk.CTkRadioButton(pos_frame, text="🔧 In Macchina - Pos:",
                          variable=self.var_dest, value="macchina").pack(side="left")
        
        self.entry_pos = ctk.CTkEntry(pos_frame, width=int(100), height=int(35))
        self.entry_pos.pack(side="left", padx=5)
        
        ctk.CTkRadioButton(pos_frame, text="🏠 Scaffale",
                          variable=self.var_dest, value="scaffale").pack(side="left", padx=20)
        
        # Monta
        ctk.CTkButton(self.dialog, text="✅ MONTA", command=self._conferma_monta,
                     **get_button_style("success", "large")).pack(pady=20)
        
        self.dialog.wait_window()
    
    def _on_holder_select(self, event):
        sel = self.tree_holder.selection()
        if not sel:
            if self.bussole_frame:
                self.bussole_frame.destroy()
                self.bussole_frame = None
            return
        
        cod = self.tree_holder.item(sel[0])['values'][1]
        
        if cod != "E":
            if self.bussole_frame:
                self.bussole_frame.destroy()
                self.bussole_frame = None
            return
        
        # Mostra bussole - GRIGIO invece di arancione
        if not self.bussole_frame:
            self.bussole_frame = ctk.CTkFrame(self.dialog, fg_color="#F5F5F5", corner_radius=int(10))
            self.bussole_frame.pack(fill="x", padx=20, pady=10)
            
            ctk.CTkLabel(self.bussole_frame, text="🔩 Seleziona Bussola:",
                        font=get_font("medium", bold=True)).pack(pady=5)
            
            self.tree_bussole = ttk.Treeview(self.bussole_frame,
                                            columns=("Cod", "Ø", "Qty"),
                                            show="headings", height=int(5))
            self.tree_bussole.heading("Cod", text="CODICE")
            self.tree_bussole.heading("Ø", text="Ø")
            self.tree_bussole.heading("Qty", text="QTY")
            
            for _, row in self.main.df_bussole_idraulico.iterrows():
                self.tree_bussole.insert("", "end", values=(
                    row['Codice_Bussola'],
                    row['Diametro'],
                    row['Quantita']
                ))
            
            self.tree_bussole.pack(fill="x", padx=10, pady=10)
    
    def _conferma_monta(self):
        sel_h = self.tree_holder.selection()
        if not sel_h:
            return messagebox.showwarning("Attenzione", "Seleziona holder")
        
        cod_h = self.tree_holder.item(sel_h[0])['values'][1]
        pos = self.entry_pos.get() if self.var_dest.get() == "macchina" else ""
        
        if self.var_dest.get() == "macchina" and not pos:
            return messagebox.showwarning("Attenzione", "Inserisci posizione")
        
        # Montaggio con o senza bussola
        cod_bus = None
        if cod_h == "E":
            if not self.tree_bussole or not self.tree_bussole.selection():
                return messagebox.showwarning("Attenzione", "Seleziona bussola")
            cod_bus = self.tree_bussole.item(self.tree_bussole.selection()[0])['values'][0]
            alias_finale = f"{self.alias_utensile}{cod_bus}"
        else:
            alias_finale = f"{self.alias_utensile}{cod_h}"
        
        print(f"\n=== MONTAGGIO UTENSILE ===")
        print(f"Utensile: {self.alias_utensile}")
        print(f"Holder: {cod_h}")
        print(f"Bussola: {cod_bus}")
        print(f"Alias finale: {alias_finale}")
        
        # DECREMENTA HOLDER
        df_h = self.main.df_holder_smontati
        if not df_h.empty:
            # Strip per confronto
            df_h['Alias_Holder'] = df_h['Alias_Holder'].astype(str).str.strip()
            cod_h_strip = str(cod_h).strip()
            
            if cod_h_strip in df_h['Alias_Holder'].values:
                idx_h = df_h['Alias_Holder'] == cod_h_strip
                qty_prima = df_h.loc[idx_h, 'Quantita'].values[0]
                df_h.loc[idx_h, 'Quantita'] = df_h.loc[idx_h, 'Quantita'].astype(int) - 1
                qty_dopo = df_h.loc[idx_h, 'Quantita'].values[0]
                
                print(f"→ Holder {cod_h_strip} decrementato: {qty_prima} → {qty_dopo}")
                
                # Rimuovi riga se qty = 0
                if qty_dopo <= 0:
                    df_h = df_h[~idx_h].reset_index(drop=True)
                    print(f"→ Holder {cod_h_strip} rimosso (qty=0)")
                
                # Aggiorna in memoria e salva
                self.main.df_holder_smontati = df_h
                from database.db_handler import salva_database_holder_smontati
                salva_database_holder_smontati(df_h, self.main.db_paths.get('holder_smontati', ''))
            else:
                print(f"⚠️  Holder {cod_h_strip} non trovato in smontati!")
        
        # DECREMENTA BUSSOLA se usata
        if cod_bus:
            df_b = self.main.df_bussole_idraulico
            if not df_b.empty:
                # Strip per confronto
                df_b['Codice_Bussola'] = df_b['Codice_Bussola'].astype(str).str.strip()
                cod_bus_strip = str(cod_bus).strip()
                
                if cod_bus_strip in df_b['Codice_Bussola'].values:
                    idx_b = df_b['Codice_Bussola'] == cod_bus_strip
                    qty_prima = df_b.loc[idx_b, 'Quantita'].values[0]
                    df_b.loc[idx_b, 'Quantita'] = df_b.loc[idx_b, 'Quantita'].astype(int) - 1
                    qty_dopo = df_b.loc[idx_b, 'Quantita'].values[0]
                    
                    print(f"→ Bussola {cod_bus_strip} decrementata: {qty_prima} → {qty_dopo}")
                    
                    # Rimuovi riga se qty = 0
                    if qty_dopo <= 0:
                        df_b = df_b[~idx_b].reset_index(drop=True)
                        print(f"→ Bussola {cod_bus_strip} rimossa (qty=0)")
                    
                    # Aggiorna in memoria e salva
                    self.main.df_bussole_idraulico = df_b
                    from database.db_handler import salva_database_bussole_idraulico
                    salva_database_bussole_idraulico(df_b, self.main.db_paths.get('bussole_idraulico', ''))
                else:
                    print(f"⚠️  Bussola {cod_bus_strip} non trovata in smontati!")
        
        # Aggiungi a database principale
        stato = STATO_IN_MACCHINA if self.var_dest.get() == "macchina" else STATO_SCAFFALE
        new_row = {
            'Posizione': pos,
            'Alias': alias_finale,
            'Stato_Utensile': stato
        }
        self.main.df = pd.concat([self.main.df, pd.DataFrame([new_row])], ignore_index=True)
        
        # Salva database principale
        from database.db_handler import salva_database
        salva_database(self.main.df, self.main.db_path)
        
        print(f"=== MONTAGGIO COMPLETATO ===\n")
        
        self.success = True
        self.dialog.destroy()
        
        # Messaggio successo dettagliato
        msg_parts = [f"Utensile: {alias_finale}"]
        if cod_h:
            msg_parts.append(f"Holder {cod_h} -1")
        if cod_bus:
            msg_parts.append(f"Bussola {cod_bus} -1")
        
        messagebox.showinfo("Successo", "Montato con successo!\n\n" + "\n".join(msg_parts))
