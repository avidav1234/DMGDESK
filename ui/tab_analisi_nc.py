"""Tab Analisi NC - Confronto programmi con database"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
import os
import re
import sys

from config.theme import *
from config.constants import *
from logic.nc_analyzer import estrai_tutti_utensili_da_file, confronta_utensili_logica

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


class TabAnalisiNC:
    """Tab per analisi programmi NC multipli."""
    
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main = main_window
        self.file_paths = []
        self._main_generato_path = None   # path del MAIN generato (per Solo MAIN)
        
        self._create_ui()
    
    def _create_ui(self):
        """Crea interfaccia."""
        # Header con descrizione
        header = ctk.CTkFrame(self.parent, fg_color=COLOR_PRIMARY, height=int(80))
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="📄 ANALISI PROGRAMMI NC",
                    font=get_font("title", bold=True),
                    text_color="white").pack(pady=(12, 2))
        
        ctk.CTkLabel(header, text="Confronta file NC con database • Genera programma MAIN",
                    font=get_font("body"),
                    text_color=COLOR_PRIMARY_LIGHT).pack(pady=(0, 8))
        
        # Toolbar
        toolbar = ctk.CTkFrame(self.parent, fg_color="transparent")
        toolbar.pack(fill="x", padx=20, pady=10)
        
        ctk.CTkButton(toolbar, text="📁 Seleziona File .MPF",
                     command=self._seleziona_files,
                     **get_button_style("primary", "medium")).pack(side="left", padx=5)
        
        ctk.CTkButton(toolbar, text="🔄 Reset",
                     command=self._pulisci_lista,
                     **get_button_style("neutral", "medium")).pack(side="left", padx=5)
        
        # Nome cartella + GENERA MAIN
        ctk.CTkLabel(toolbar, text="📁", font=get_font("normal")).pack(side="right", padx=2)
        self.entry_nome_cartella = ctk.CTkEntry(toolbar, width=int(120), height=int(35),
                                                placeholder_text="Nome")
        self.entry_nome_cartella.pack(side="right", padx=5)
        
        ctk.CTkButton(toolbar, text="📄 GENERA MAIN",
                     command=self._genera_main,
                     **get_button_style("accent", "large")).pack(side="right", padx=5)
        
        self.btn_invia_main = ctk.CTkButton(toolbar, text="📤 Solo MAIN",
                     command=self._invia_solo_main,
                     fg_color="#1565C0", hover_color="#0D47A1",
                     font=get_font("medium"), height=35, width=110,
                     state="disabled")
        self.btn_invia_main.pack(side="right", padx=3)
        
        self.btn_invia_tutto = ctk.CTkButton(toolbar, text="📤 Invia tutto",
                     command=self._invia_tutto,
                     fg_color="#2E7D32", hover_color="#1B5E20",
                     font=get_font("medium"), height=35, width=110,
                     state="disabled")
        self.btn_invia_tutto.pack(side="right", padx=3)
        
        # Lista file selezionati
        list_frame = ctk.CTkFrame(self.parent, fg_color=COLOR_SURFACE, corner_radius=int(10))
        list_frame.pack(fill="both", expand=True, padx=20, pady=10)
        
        ctk.CTkLabel(list_frame, text="File selezionati:",
                    font=get_font("medium", bold=True)).pack(anchor="w", padx=10, pady=5)
        
        self.list_files = ctk.CTkTextbox(list_frame, height=int(150), font=get_font("normal"))
        self.list_files.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Risultati
        result_frame = ctk.CTkFrame(self.parent, fg_color=COLOR_SURFACE, corner_radius=int(10))
        result_frame.pack(fill="both", expand=True, padx=20, pady=(0, 20))
        
        ctk.CTkLabel(result_frame, text="Risultati confronto:",
                    font=get_font("medium", bold=True)).pack(anchor="w", padx=10, pady=5)
        
        tree_scroll = ttk.Scrollbar(result_frame)
        tree_scroll.pack(side="right", fill="y")
        
        self.tree = ttk.Treeview(result_frame, columns=("Stato", "Alias", "File", "Riga"),
                                show="headings", height=int(15), yscrollcommand=tree_scroll.set)
        tree_scroll.config(command=self.tree.yview)
        
        self.tree.heading("Stato", text="STATO")
        self.tree.heading("Alias", text="ALIAS")
        self.tree.heading("File", text="FILE")
        self.tree.heading("Riga", text="N°RIGA")
        
        self.tree.column("Stato", width=int(80))
        self.tree.column("Alias", width=int(300))
        self.tree.column("File", width=int(250))
        self.tree.column("Riga", width=int(80))
        
        self.tree.pack(fill="both", expand=True, padx=10, pady=10)
        
        # Binding doppio click per aggiungere utensile mancante
        self.tree.bind("<Double-Button-1>", self._on_double_click)
    
    def _seleziona_files(self):
        """Selezione multipla file .MPF con confronto automatico."""
        files = filedialog.askopenfilenames(
            title="Seleziona programmi NC",
            filetypes=[("Programmi MPF", "*.MPF"), ("Tutti i file", "*.*")]
        )
        
        if files:
            self.file_paths.extend(files)
            self._aggiorna_lista()
            # CONFRONTO AUTOMATICO dopo selezione
            self._confronta()
    
    def _pulisci_lista(self):
        """Pulisce lista file."""
        self.file_paths = []
        self._main_generato_path = None
        self.list_files.delete("1.0", "end")
        self.tree.delete(*self.tree.get_children())
        self.btn_invia_tutto.configure(state="disabled")
        self.btn_invia_main.configure(state="disabled")
    
    def _aggiorna_lista(self):
        """Aggiorna visualizzazione lista file."""
        self.list_files.delete("1.0", "end")
        for i, fp in enumerate(self.file_paths, 1):
            self.list_files.insert("end", f"{i}. {os.path.basename(fp)}\n")
    
    def _confronta(self, show_message=False):
        """Confronta utensili richiesti con database."""
        if not self.file_paths:
            if show_message:
                return messagebox.showwarning("Attenzione", "Seleziona almeno un file")
            return
        
        if self.main.df.empty:
            if show_message:
                return messagebox.showwarning("Attenzione", "Carica database prima")
            return
        
        # Confronto
        utensili_richiesti, utensili_mancanti_report = confronta_utensili_logica(
            self.main.df, self.file_paths
        )
        
        # Pulisci tree
        self.tree.delete(*self.tree.get_children())
        
        # Aggiungi risultati
        if not utensili_mancanti_report:
            self.tree.insert("", "end", values=("✅ OK", "Tutti gli utensili presenti", "-", "-"))
        else:
            for alias, file_name, riga_esempio in utensili_mancanti_report:
                # Estrai numero riga
                match = re.search(r'(\d+)', str(riga_esempio))
                riga_num = match.group(1) if match else "-"
                
                self.tree.insert("", "end", values=("❌ MANCA", alias, file_name, riga_num))
        
        # Abilita pulsante invio se ci sono file
        if self.file_paths:
            self.btn_invia_tutto.configure(state="normal")
        
        # Mostra messaggio solo se richiesto (confronto manuale)
        if show_message:
            messagebox.showinfo("Confronto completato",
                               f"Utensili richiesti: {len(utensili_richiesti)}\n"
                               f"Mancanti: {len(utensili_mancanti_report)}")
    
    def _on_double_click(self, event):
        """Doppio click su utensile mancante per aggiungerlo."""
        sel = self.tree.selection()
        if not sel:
            return
        
        item = self.tree.item(sel[0])
        values = item['values']
        
        # Verifica che sia un utensile mancante
        if values[0] != "❌ MANCA":
            return
        
        alias = values[1]
        
        # VERIFICA SE HA GIÀ HOLDER
        from database.db_handler import ha_holder
        
        if ha_holder(alias):
            # Ha già holder! Non serve aggiungerlo
            messagebox.showinfo("Info", 
                f"Utensile '{alias}' contiene già un holder.\n\n"
                f"Verrà aggiunto direttamente senza selezione holder.")
            
            try:
                # Aggiungi direttamente senza dialog
                import pandas as pd
                from database.db_handler import salva_database
                from config.constants import STATO_SCAFFALE
                
                new_row = pd.DataFrame([{
                    'Posizione': '',
                    'Alias': alias,  # Mantiene holder esistente
                    'Stato_Utensile': STATO_SCAFFALE
                }])
                
                self.main.df = pd.concat([self.main.df, new_row], ignore_index=True)
                
                success, err = salva_database(self.main.df, self.main.db_path)
                
                if success:
                    self.main.refresh_all_tabs()
                    self.main._update_status()
                    self.tree.delete(sel[0])
                    messagebox.showinfo("Successo", f"Utensile '{alias}' aggiunto a SCAFFALE")
                else:
                    messagebox.showerror("Errore", err)
                    
            except Exception as e:
                import traceback
                traceback.print_exc()
                messagebox.showerror("Errore", f"Errore aggiunta utensile:\n{e}")
            
            return  # STOP - non continuare con dialog holder
        
        # Dialog conferma
        if not messagebox.askyesno("Aggiungi Utensile", 
                                   f"Aggiungere '{alias}' al database?\n\n"
                                   f"Verrà aggiunto come SCAFFALE.\n"
                                   f"DEVI selezionare un holder."):
            return
        
        try:
            # DIALOG SELEZIONE HOLDER (obbligatorio per invarianza!)
            from ui.dialogs import SelezionaHolderDialog
            
            dialog = SelezionaHolderDialog(
                self.parent,
                alias,
                self.main.df_holder_smontati,
                self.main.df_bussole_idraulico
            )
            
            if not dialog.success:
                return  # Annullato
            
            # Ottieni alias finale con holder
            alias_finale = dialog.alias_finale
            holder_usato = dialog.holder_cod
            bussola_usata = dialog.bussola_cod
            
            print(f"\n=== AGGIUNGI UTENSILE MANCANTE ===")
            print(f"Alias originale: {alias}")
            print(f"Alias finale: {alias_finale}")
            print(f"Holder: {holder_usato}")
            print(f"Bussola: {bussola_usata}")
            
            # DECREMENTA HOLDER da smontati
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
                    
                    # Rimuovi se qty=0
                    if qty_dopo <= 0:
                        df_h = df_h[~idx_h].reset_index(drop=True)
                        print(f"→ Holder {holder_strip} rimosso (qty=0)")
                    
                    # Salva
                    self.main.df_holder_smontati = df_h
                    from database.db_handler import salva_database_holder_smontati
                    salva_database_holder_smontati(df_h, self.main.db_paths.get('holder_smontati', ''))
                else:
                    messagebox.showwarning("Attenzione", 
                        f"Holder {holder_strip} non disponibile in smontati!\n"
                        f"Verrà usato comunque ma TOTALE aumenterà.")
            
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
                        
                        # Salva
                        self.main.df_bussole_idraulico = df_b
                        from database.db_handler import salva_database_bussole_idraulico
                        salva_database_bussole_idraulico(df_b, self.main.db_paths.get('bussole_idraulico', ''))
            
            # Aggiungi al database come SCAFFALE con alias finale
            import pandas as pd
            from database.db_handler import salva_database
            from config.constants import STATO_SCAFFALE
            
            new_row = pd.DataFrame([{
                'Posizione': '',
                'Alias': alias_finale,  # CON HOLDER!
                'Stato_Utensile': STATO_SCAFFALE
            }])
            
            self.main.df = pd.concat([self.main.df, new_row], ignore_index=True)
            
            success, err = salva_database(self.main.df, self.main.db_path)
            
            if success:
                # Refresh UI
                self.main.refresh_all_tabs()
                self.main._update_status()
                
                # Aggiorna tree - rimuovi riga mancante
                self.tree.delete(sel[0])
                
                print("=== UTENSILE AGGIUNTO CON SUCCESSO ===\n")
                
                msg_parts = [f"Utensile: {alias_finale}"]
                if holder_usato:
                    msg_parts.append(f"Holder {holder_usato} -1")
                if bussola_usata:
                    msg_parts.append(f"Bussola {bussola_usata} -1")
                
                messagebox.showinfo("Successo", 
                    f"Aggiunto a SCAFFALE!\n\n" + "\n".join(msg_parts))
            else:
                messagebox.showerror("Errore", err)
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            messagebox.showerror("Errore", f"Errore aggiunta utensile:\n{e}")
    
    
    def _invia_tutto(self):
        """Invia tutti i file analizzati alla macchina."""
        if not self.file_paths:
            return messagebox.showwarning("Attenzione", "Seleziona almeno un file MPF")
        try:
            from ui.dialog_invia_macchina import DialogInviaMacchina
            import os
            # Usa il nome della cartella come progetto
            progetto = self.entry_nome_cartella.get().strip()
            if not progetto:
                return messagebox.showwarning("Attenzione",
                    "Inserisci il nome progetto/cartella prima di inviare")
            # Includi MAIN se esiste
            paths = list(self.file_paths)
            if self._main_generato_path and os.path.exists(self._main_generato_path):
                if self._main_generato_path not in paths:
                    paths.insert(0, self._main_generato_path)
            dlg = DialogInviaMacchina(self.parent, paths, progetto)
            self.parent.wait_window(dlg)
        except Exception as e:
            messagebox.showerror("Errore", f"Errore apertura dialog invio:\n{e}")

    def _invia_solo_main(self):
        """Invia solo il file MAIN generato."""
        if not self._main_generato_path:
            return messagebox.showwarning("Attenzione",
                "Genera prima il file MAIN con '📄 GENERA MAIN'")
        import os
        if not os.path.exists(self._main_generato_path):
            return messagebox.showwarning("File non trovato",
                f"Il file MAIN non esiste più:\n{self._main_generato_path}\n\n"
                "Rigenera il MAIN prima di inviare.")
        try:
            from ui.dialog_invia_macchina import DialogInviaMacchina
            progetto = self.entry_nome_cartella.get().strip()
            if not progetto:
                return messagebox.showwarning("Attenzione",
                    "Inserisci il nome progetto/cartella prima di inviare")
            dlg = DialogInviaMacchina(self.parent, [self._main_generato_path], progetto)
            self.parent.wait_window(dlg)
        except Exception as e:
            messagebox.showerror("Errore", f"Errore apertura dialog invio:\n{e}")

    def _genera_main(self):
        """Genera programma MAIN dai file analizzati."""
        if not self.file_paths:
            return messagebox.showwarning("Attenzione", "Seleziona almeno un file")
        
        nome_progetto = self.entry_nome_cartella.get().strip()
        if not nome_progetto:
            return messagebox.showwarning("Attenzione", "Inserisci nome progetto")
        
        try:
            # Importa funzione generazione V12
            from logic.nc_analyzer import genera_programma_main_gcode
            
            # Genera MAIN con logica V12 completa
            gcode_content, main_filename = genera_programma_main_gcode(
                self.file_paths,
                nome_progetto
            )
            
            # Dialog salvataggio
            from tkinter import filedialog
            
            save_path = filedialog.asksaveasfilename(
                title="Salva Programma MAIN",
                initialfile=main_filename,
                defaultextension=".MPF",
                filetypes=[("MPF Program", "*.MPF"), ("All", "*.*")]
            )
            
            if not save_path:
                return
            
            # Salva file
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(gcode_content)
            
            self._main_generato_path = save_path
            self.btn_invia_main.configure(state="normal")
            messagebox.showinfo("Successo", 
                              f"MAIN generato:\n{save_path}\n\n"
                              f"Usa logica calibrazione V12:\n"
                              f"• CALIBRA_ONLY iniziale\n"
                              f"• Finitura: sempre su cambio\n"
                              f"• Standard: ogni 3 cambi")
            
        except Exception as e:
            messagebox.showerror("Errore", f"Errore generazione: {e}")
