"""Tab Scaffale - Utensili pronti ma non montati"""
import customtkinter as ctk
from tkinter import messagebox
import tkinter.ttk as ttk
import pandas as pd

from config.theme import *
from config.constants import *
from database.db_handler import *


class TabScaffale:
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
        
        ctk.CTkLabel(header, text="🏠 UTENSILI A SCAFFALE",
                    font=get_font("title", bold=True),
                    text_color="white").pack(pady=(12, 2))
        
        ctk.CTkLabel(header, text="Gestisci utensili in magazzino • Pronti per montaggio",
                    font=get_font("body"),
                    text_color="#F5F5F5").pack(pady=(0, 8))
        
        toolbar = ctk.CTkFrame(self.parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=(10, 10))
        
        ctk.CTkButton(toolbar, text="➕ Aggiungi", command=self._aggiungi,
                     **get_button_style("success", "medium")).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="🔧 Monta in Macchina", command=self._monta_in_macchina,
                     **get_button_style("primary", "medium")).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="📥 Smonta", command=self._smonta,
                     **get_button_style("neutral", "medium")).pack(side="left", padx=5)
        ctk.CTkButton(toolbar, text="🗑️ Elimina", command=self._elimina,
                     **get_button_style("error", "medium")).pack(side="left", padx=5)
        
        tree_frame = ctk.CTkFrame(self.parent, fg_color=COLOR_SURFACE)
        tree_frame.pack(fill="both", expand=True)
        
        scroll = ttk.Scrollbar(tree_frame)
        scroll.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(tree_frame, columns=("Alias",), show="headings",
                                yscrollcommand=scroll.set, height=int(25))
        scroll.config(command=self.tree.yview)
        
        self.tree.heading("Alias", text="ALIAS UTENSILE")
        self.tree.column("Alias", width=int(600))
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
    
    def refresh(self):
        self.tree.delete(*self.tree.get_children())
        df_scaffale = self.main.df[self.main.df['Stato_Utensile'] == STATO_SCAFFALE]
        
        for idx, row in df_scaffale.iterrows():
            self.tree.insert("", "end", values=(row['Alias'],), tags=(idx,))
    
    def _aggiungi(self):
        from utils.dialogs import InputDialog
        dialog = InputDialog(self.parent, "Aggiungi a Scaffale", [("Alias utensile", "text")])
        
        if dialog.result:
            alias_base = dialog.result[0]
            
            # DIALOG SELEZIONE HOLDER (obbligatorio!)
            from ui.dialogs import SelezionaHolderDialog
            
            holder_dialog = SelezionaHolderDialog(
                self.parent,
                alias_base,
                self.main.df_holder_smontati,
                self.main.df_bussole_idraulico
            )
            
            if not holder_dialog.success:
                return  # Annullato
            
            alias_finale = holder_dialog.alias_finale
            holder_usato = holder_dialog.holder_cod
            bussola_usata = holder_dialog.bussola_cod
            
            print(f"\n=== AGGIUNGI UTENSILE A SCAFFALE ===")
            print(f"Alias base: {alias_base}")
            print(f"Alias finale: {alias_finale}")
            print(f"Holder: {holder_usato}")
            print(f"Bussola: {bussola_usata}")
            
            # DECREMENTA HOLDER
            df_h = self.main.df_holder_smontati
            if not df_h.empty:
                df_h['Alias_Holder'] = df_h['Alias_Holder'].astype(str).str.strip()
                holder_strip = str(holder_usato).strip()
                
                if holder_strip in df_h['Alias_Holder'].values:
                    idx_h = df_h['Alias_Holder'] == holder_strip
                    qty_prima = df_h.loc[idx_h, 'Quantita'].values[0]
                    df_h.loc[idx_h, 'Quantita'] = df_h.loc[idx_h, 'Quantita'].astype(int) - 1
                    qty_dopo = df_h.loc[idx_h, 'Quantita'].values[0]
                    
                    print(f"→ Holder {holder_strip} decrementato: {qty_prima} → {qty_dopo}")
                    
                    if qty_dopo <= 0:
                        df_h = df_h[~idx_h].reset_index(drop=True)
                        print(f"→ Holder {holder_strip} rimosso (qty=0)")
                    
                    self.main.df_holder_smontati = df_h
                    from database.db_handler import salva_database_holder_smontati
                    salva_database_holder_smontati(df_h, self.main.db_paths.get('holder_smontati', ''))
            
            # DECREMENTA BUSSOLA se usata
            if bussola_usata:
                df_b = self.main.df_bussole_idraulico
                if not df_b.empty:
                    df_b['Codice_Bussola'] = df_b['Codice_Bussola'].astype(str).str.strip()
                    bussola_strip = str(bussola_usata).strip()
                    
                    if bussola_strip in df_b['Codice_Bussola'].values:
                        idx_b = df_b['Codice_Bussola'] == bussola_strip
                        qty_prima = df_b.loc[idx_b, 'Quantita'].values[0]
                        df_b.loc[idx_b, 'Quantita'] = df_b.loc[idx_b, 'Quantita'].astype(int) - 1
                        qty_dopo = df_b.loc[idx_b, 'Quantita'].values[0]
                        
                        print(f"→ Bussola {bussola_strip} decrementata: {qty_prima} → {qty_dopo}")
                        
                        if qty_dopo <= 0:
                            df_b = df_b[~idx_b].reset_index(drop=True)
                            print(f"→ Bussola {bussola_strip} rimossa (qty=0)")
                        
                        self.main.df_bussole_idraulico = df_b
                        from database.db_handler import salva_database_bussole_idraulico
                        salva_database_bussole_idraulico(df_b, self.main.db_paths.get('bussole_idraulico', ''))
            
            # Aggiungi con alias finale
            new_row = {'Posizione': '', 'Alias': alias_finale, 'Stato_Utensile': STATO_SCAFFALE}
            self.main.df = pd.concat([self.main.df, pd.DataFrame([new_row])], ignore_index=True)
            
            success, _ = salva_database(self.main.df, self.main.db_path)
            if success:
                self.main.refresh_all_tabs()
                
                msg_parts = [f"Utensile: {alias_finale}"]
                if holder_usato:
                    msg_parts.append(f"Holder {holder_usato} -1")
                if bussola_usata:
                    msg_parts.append(f"Bussola {bussola_usata} -1")
                
                messagebox.showinfo("Successo", 
                    f"Aggiunto a SCAFFALE!\n\n" + "\n".join(msg_parts))
    
    def _monta_in_macchina(self):
        sel = self.tree.selection()
        if not sel:
            return messagebox.showwarning("Attenzione", "Seleziona utensile")
        
        from tkinter import simpledialog
        pos = simpledialog.askstring("Montaggio", "Posizione in macchina (1-99):")
        if not pos:
            return
        
        item = self.tree.item(sel[0])
        idx = item['tags'][0]
        
        self.main.df.at[idx, 'Posizione'] = pos
        self.main.df.at[idx, 'Stato_Utensile'] = STATO_IN_MACCHINA
        
        success, _ = salva_database(self.main.df, self.main.db_path)
        if success:
            self.main.refresh_all_tabs()
            messagebox.showinfo("Successo", f"Montato in pos. {pos}")
    
    def _smonta(self):
        """Smonta utensile da scaffale (separa utensile da holder)."""
        sel = self.tree.selection()
        if not sel:
            return messagebox.showwarning("Attenzione", "Seleziona utensile")
        
        if not messagebox.askyesno("Conferma Smontaggio", 
                                   "Smontare l'utensile da scaffale?\n\n"
                                   "L'utensile verrà separato dal holder."):
            return
        
        item = self.tree.item(sel[0])
        idx = item['tags'][0]
        alias = self.main.df.at[idx, 'Alias']
        
        print(f"\n=== SMONTAGGIO DA SCAFFALE ===")
        print(f"Alias: {alias}")
        
        # Usa funzione completa di smontaggio
        from database.db_handler import smonta_utensile_completo
        
        success, msg, df_ut_new, df_h_new, df_b_new = smonta_utensile_completo(
            alias,
            self.main.db_paths,
            self.main.df_utensili_smontati,
            self.main.df_holder_smontati,
            self.main.df_bussole_idraulico,
            provenienza="Scaffale"
        )
        
        if success:
            # Aggiorna DataFrame
            self.main.df_utensili_smontati = df_ut_new
            self.main.df_holder_smontati = df_h_new
            self.main.df_bussole_idraulico = df_b_new
            
            # Rimuovi da database principale
            self.main.df = self.main.df.drop(idx).reset_index(drop=True)
            
            # Salva tutto
            from database.db_handler import salva_database
            salva_database(self.main.df, self.main.db_path)
            
            # Refresh
            self.main.refresh_all_tabs()
            self.main._update_status()
            
            messagebox.showinfo("Successo", msg)
        else:
            messagebox.showerror("Errore", msg)
    
    def _elimina(self):
        sel = self.tree.selection()
        if not sel or not messagebox.askyesno("Conferma", "Eliminare?"):
            return
        
        idx = self.tree.item(sel[0])['tags'][0]
        self.main.df = self.main.df.drop(idx).reset_index(drop=True)
        salva_database(self.main.df, self.main.db_path)
        self.main.refresh_all_tabs()
        messagebox.showinfo("Successo", "Eliminato")
