"""
Tab In Macchina - Gestione utensili montati in macchina
"""

import customtkinter as ctk
from tkinter import messagebox, simpledialog
import tkinter.ttk as ttk

from config.theme import *
from config.constants import *
from database.db_handler import *
from database.db_handler import smonta_utensile_completo
from logic.main_generator import genera_programma_main


class TabMacchina:
    """Tab gestione utensili in macchina."""
    
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main = main_window
        self._create_ui()
    
    def _create_ui(self):
        """Crea interfaccia tab."""
        # Header con descrizione
        # Header - BLU come Analisi NC
        header = ctk.CTkFrame(self.parent, fg_color=COLOR_PRIMARY, height=int(80))
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="🔧 UTENSILI IN MACCHINA",
                    font=get_font("title", bold=True),
                    text_color="white").pack(pady=(12, 2))
        
        ctk.CTkLabel(header, text="Gestisci utensili montati in macchina • Smonta e modifica",
                    font=get_font("body"),
                    text_color="#E8F5E9").pack(pady=(0, 8))
        
        # Toolbar
        toolbar = ctk.CTkFrame(self.parent, fg_color="transparent")
        toolbar.pack(fill="x", pady=(10, 10))
        
        ctk.CTkButton(
            toolbar,
            text="➕ Aggiungi",
            command=self._aggiungi,
            **get_button_style("success", "medium")
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar,
            text="✏️ Modifica",
            command=self._modifica,
            **get_button_style("primary", "medium")
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar,
            text="🏠 A Scaffale",
            command=self._a_scaffale,
            **get_button_style("primary", "medium")
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar,
            text="📥 Smonta",
            command=self._smonta,
            **get_button_style("neutral", "medium")
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            toolbar,
            text="🗑️ Elimina",
            command=self._elimina,
            **get_button_style("error", "medium")
        ).pack(side="left", padx=5)
        
        # TreeView
        tree_frame = ctk.CTkFrame(self.parent, fg_color=COLOR_SURFACE)
        tree_frame.pack(fill="both", expand=True)
        
        scroll = ttk.Scrollbar(tree_frame)
        scroll.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(
            tree_frame,
            columns=("Posizione", "Alias"),
            show="headings",
            yscrollcommand=scroll.set,
            height=int(25)
        )
        scroll.config(command=self.tree.yview)
        
        self.tree.heading("Posizione", text="POSIZIONE")
        self.tree.heading("Alias", text="ALIAS UTENSILE")
        
        self.tree.column("Posizione", width=int(TREEVIEW_COL_WIDTH_POS), anchor="center")
        self.tree.column("Alias", width=int(TREEVIEW_COL_WIDTH_ALIAS))
        
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Stile TreeView
        self._configure_treeview_style()
    
    def _configure_treeview_style(self):
        """Configura stile TreeView."""
        style = ttk.Style()
        style.theme_use("default")
        
        style.configure(
            "Treeview",
            background=COLOR_SURFACE,
            foreground=COLOR_TEXT_PRIMARY,
            fieldbackground=COLOR_SURFACE,
            borderwidth=0,
            font=(FONT_FAMILY, int(FONT_SIZE_NORMAL))
        )
        
        style.map(
            'Treeview',
            background=[('selected', COLOR_PRIMARY)],
            foreground=[('selected', 'white')]
        )
        
        style.configure(
            "Treeview.Heading",
            background=COLOR_DIVIDER,
            foreground=COLOR_TEXT_PRIMARY,
            borderwidth=int(1),
            relief="flat",
            font=(FONT_FAMILY, int(FONT_SIZE_NORMAL), "bold")
        )
    
    def refresh(self):
        """Aggiorna TreeView."""
        self.tree.delete(*self.tree.get_children())
        
        df_macchina = self.main.df[
            self.main.df['Stato_Utensile'] == STATO_IN_MACCHINA
        ].copy()
        
        # Ordina per posizione
        df_macchina['Pos_Int'] = pd.to_numeric(
            df_macchina['Posizione'], errors='coerce'
        )
        df_macchina = df_macchina.sort_values('Pos_Int')
        
        for _, row in df_macchina.iterrows():
            self.tree.insert(
                "", "end",
                values=(row['Posizione'], row['Alias']),
                tags=(row.name,)  # Salva index come tag
            )
    
    def _aggiungi(self):
        """Aggiunge utensile in macchina."""
        from utils.dialogs import InputDialog
        
        dialog = InputDialog(
            self.parent,
            "Aggiungi Utensile in Macchina",
            [
                ("Posizione (1-99)", "text"),
                ("Alias utensile", "text")
            ]
        )
        
        if dialog.result:
            pos, alias_base = dialog.result
            
            if not pos or not alias_base:
                messagebox.showerror("Errore", "Compila tutti i campi")
                return
            
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
            
            print(f"\n=== AGGIUNGI UTENSILE IN MACCHINA ===")
            print(f"Posizione: {pos}")
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
            
            # Aggiungi al DataFrame con alias finale
            new_row = {
                'Posizione': pos,
                'Alias': alias_finale,  # CON HOLDER!
                'Stato_Utensile': STATO_IN_MACCHINA
            }
            self.main.df = pd.concat([
                self.main.df,
                pd.DataFrame([new_row])
            ], ignore_index=True)
            
            # Salva
            success, err = salva_database(self.main.df, self.main.db_path)
            if success:
                self.main.refresh_all_tabs()
                
                print("=== UTENSILE AGGIUNTO CON SUCCESSO ===\n")
                
                msg_parts = [f"Utensile: {alias_finale}", f"Posizione: {pos}"]
                if holder_usato:
                    msg_parts.append(f"Holder {holder_usato} -1")
                if bussola_usata:
                    msg_parts.append(f"Bussola {bussola_usata} -1")
                
                messagebox.showinfo("Successo", 
                    f"Aggiunto in macchina!\n\n" + "\n".join(msg_parts))
            else:
                messagebox.showerror("Errore", err)
    
    def _modifica(self):
        """Modifica utensile selezionato."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona un utensile")
            return
        
        # Ottieni index dal tag
        item = self.tree.item(sel[0])
        idx = item['tags'][0]
        
        row = self.main.df.loc[idx]
        
        from utils.dialogs import InputDialog
        dialog = InputDialog(
            self.parent,
            "Modifica Utensile",
            [
                ("Posizione", "text", row['Posizione']),
                ("Alias", "text", row['Alias'])
            ]
        )
        
        if dialog.result:
            pos, alias = dialog.result
            
            self.main.df.at[idx, 'Posizione'] = pos
            self.main.df.at[idx, 'Alias'] = alias
            
            success, err = salva_database(self.main.df, self.main.db_path)
            if success:
                self.main.refresh_all_tabs()
                messagebox.showinfo("Successo", "Utensile modificato")
            else:
                messagebox.showerror("Errore", err)
    
    def _a_scaffale(self):
        """Sposta utensile a scaffale."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona un utensile")
            return
        
        if not messagebox.askyesno("Conferma Spostamento", 
                                   "Spostare l'utensile a scaffale?\n\n"
                                   "L'utensile manterrà posizione e alias."):
            return
        
        item = self.tree.item(sel[0])
        idx = item['tags'][0]
        
        # Cambia stato a "Scaffale"
        self.main.df.at[idx, 'Stato'] = 'Scaffale'
        
        # Salva database
        success, err = salva_database(self.main.df, self.main.db_path)
        
        if success:
            self.main.refresh_all_tabs()
            self.main._update_status()
            messagebox.showinfo("Successo", "Utensile spostato a scaffale")
        else:
            messagebox.showerror("Errore", err)
    
    def _smonta(self):
        """Smonta utensile."""
        try:
            print("\n=== DEBUG SMONTAGGIO ===")
            
            sel = self.tree.selection()
            print(f"1. Selezione: {sel}")
            
            if not sel:
                messagebox.showwarning("Attenzione", "Seleziona un utensile")
                return
            
            if not messagebox.askyesno("Conferma", "Smontare utensile?"):
                print("2. Utente ha annullato")
                return
            
            print("2. Conferma OK")
            
            item = self.tree.item(sel[0])
            idx = item['tags'][0]
            print(f"3. Item idx: {idx}")
            
            alias = self.main.df.at[idx, 'Alias']
            pos = self.main.df.at[idx, 'Posizione']
            print(f"4. Alias: {alias}, Pos: {pos}")
            
            # Verifica db_paths
            print(f"5. db_paths: {self.main.db_paths}")
            
            # Verifica DataFrame prima
            print(f"6. df_utensili_smontati len: {len(self.main.df_utensili_smontati)}")
            print(f"   df_holder_smontati len: {len(self.main.df_holder_smontati)}")
            print(f"   df_bussole len: {len(self.main.df_bussole_idraulico)}")
            
            # Smonta con separazione holder + bussola
            print("7. Chiamata smonta_utensile_completo...")
            success, msg, df_ut, df_h, df_b = smonta_utensile_completo(
                alias,
                self.main.db_paths,
                self.main.df_utensili_smontati,
                self.main.df_holder_smontati,
                self.main.df_bussole_idraulico,
                provenienza=f"Pos. {pos}"
            )
            
            print(f"8. Success: {success}, Msg: {msg}")
            
            if success:
                # Aggiorna DataFrame in memoria
                self.main.df_utensili_smontati = df_ut
                self.main.df_holder_smontati = df_h
                self.main.df_bussole_idraulico = df_b
                
                print(f"9. DataFrame aggiornati in memoria")
                print(f"   df_utensili_smontati len: {len(df_ut)}")
                print(f"   df_holder_smontati len: {len(df_h)}")
                print(f"   df_bussole len: {len(df_b)}")
                
                # Rimuovi da principale
                self.main.df = self.main.df.drop(idx).reset_index(drop=True)
                success_save, err = salva_database(self.main.df, self.main.db_path)
                print(f"10. Salvataggio DB principale: {success_save}")
                
                # Refresh UI
                print("11. Refresh UI...")
                self.main.refresh_all_tabs()
                self.main._update_status()
                
                print("12. Mostra messaggio successo")
                messagebox.showinfo("Successo", msg)
                print("=== SMONTAGGIO COMPLETATO ===\n")
            else:
                print(f"ERRORE: {msg}")
                messagebox.showerror("Errore", msg)
                
        except Exception as e:
            import traceback
            error_msg = f"ERRORE CRITICO:\n{e}\n\nStacktrace:\n{traceback.format_exc()}"
            print(error_msg)
            messagebox.showerror("Errore Critico", error_msg)
            
            # Refresh UI
            self.main.refresh_all_tabs()
            self.main._update_status()
            
            messagebox.showinfo("Successo", msg)
        else:
            messagebox.showerror("Errore", msg)
    
    def _elimina(self):
        """Elimina utensile."""
        sel = self.tree.selection()
        if not sel:
            messagebox.showwarning("Attenzione", "Seleziona un utensile")
            return
        
        if not messagebox.askyesno("Conferma", "Eliminare utensile?"):
            return
        
        item = self.tree.item(sel[0])
        idx = item['tags'][0]
        
        self.main.df = self.main.df.drop(idx).reset_index(drop=True)
        success, err = salva_database(self.main.df, self.main.db_path)
        
        if success:
            self.main.refresh_all_tabs()
            messagebox.showinfo("Successo", "Utensile eliminato")
        else:
            messagebox.showerror("Errore", err)
    
    def _genera_main(self):
            messagebox.showerror("Errore", err)
