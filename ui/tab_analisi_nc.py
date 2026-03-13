"""Tab Analisi NC - Confronto programmi con database"""

import customtkinter as ctk
from tkinter import filedialog, messagebox
import tkinter.ttk as ttk
import os
import re
import shutil

from config.theme import *
from config.constants import *
from logic.nc_analyzer import estrai_tutti_utensili_da_file, confronta_utensili_logica

# CALIBRA ONLY V14 - Nuovi import
from ui.calibra_only_settings_dialog import show_calibra_settings
from logic.calibra_only_logic import get_calibra_logic


class TabAnalisiNC:
    """Tab per analisi programmi NC multipli."""
    
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main = main_window
        self.file_paths = []
        self._main_generato_path = None   # path dell'ultimo MAIN generato
        
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

        # Pulsante INVIA ALLA MACCHINA (abilitato solo dopo GENERA MAIN)
        self.btn_invia = ctk.CTkButton(
            toolbar,
            text="📤 INVIA ALLA MACCHINA",
            command=self._invia_alla_macchina,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            font=get_font("medium", bold=True),
            height=40,
            state="disabled"
        )
        self.btn_invia.pack(side="left", padx=10)
        
        # Nome cartella + GENERA MAIN + Impostazioni
        ctk.CTkLabel(toolbar, text="📁", font=get_font("normal")).pack(side="right", padx=2)
        self.entry_nome_cartella = ctk.CTkEntry(toolbar, width=int(120), height=int(35),
                                                placeholder_text="Nome")
        self.entry_nome_cartella.pack(side="right", padx=5)
        
        # Pulsante IMPOSTAZIONI ⚙️
        ctk.CTkButton(
            toolbar, 
            text="⚙️",
            width=45,
            height=40,
            fg_color="#9E9E9E",
            hover_color="#757575",
            font=("Segoe UI", 16),
            corner_radius=8,
            command=self._apri_impostazioni_calibra
        ).pack(side="right", padx=2)
        
        # Pulsante GENERA MAIN
        ctk.CTkButton(toolbar, text="📄 GENERA MAIN",
                     command=self._genera_main,
                     **get_button_style("accent", "large")).pack(side="right", padx=5)
        
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
        self._sorgente_dir = ""
        self.list_files.delete("1.0", "end")
        self.tree.delete(*self.tree.get_children())
        self.btn_invia.configure(state="disabled")
    
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
    
    
    def _genera_main(self):
        """Genera programma MAIN dai file analizzati con CALIBRA ONLY configurabile."""
        if not self.file_paths:
            return messagebox.showwarning("Attenzione", "Seleziona almeno un file")
        
        nome_progetto = self.entry_nome_cartella.get().strip()
        if not nome_progetto:
            return messagebox.showwarning("Attenzione", "Inserisci nome progetto")
        
        try:
            # Importa logica CALIBRA ONLY V14
            calibra_logic = get_calibra_logic()
            
            # Importa funzione generazione V14
            try:
                from logic.nc_analyzer_v14_update import genera_programma_main_gcode_v14
                gcode_content, main_filename = genera_programma_main_gcode_v14(
                    self.file_paths, nome_progetto, calibra_logic)
            except ImportError:
                from logic.nc_analyzer import genera_programma_main_gcode
                gcode_content, main_filename = genera_programma_main_gcode(
                    self.file_paths, nome_progetto)
            
            # Dialog salvataggio — propone la stessa cartella dei file sorgente
            sorgente_dir = os.path.dirname(self.file_paths[0]) if self.file_paths else ""
            
            from tkinter import filedialog
            save_path = filedialog.asksaveasfilename(
                title="Salva Programma MAIN",
                initialdir=sorgente_dir,
                initialfile=main_filename,
                defaultextension=".MPF",
                filetypes=[("MPF Program", "*.MPF"), ("All", "*.*")]
            )
            
            if not save_path:
                return
            
            # Salva file
            with open(save_path, 'w', encoding='utf-8') as f:
                f.write(gcode_content)
            
            # Memorizza la cartella sorgente per il pulsante INVIA
            self._sorgente_dir = os.path.dirname(save_path)
            
            # Abilita pulsante INVIA ALLA MACCHINA
            self.btn_invia.configure(state="normal")
            
            mode_desc = calibra_logic.get_mode_description()
            messagebox.showinfo("Successo", 
                              f"✅ MAIN generato:\n{save_path}\n\n"
                              f"⚙️ Modalità CALIBRA ONLY:\n{mode_desc}\n\n"
                              f"Puoi ora inviare i programmi alla macchina\n"
                              f"con il pulsante 📤 INVIA ALLA MACCHINA")
            
        except Exception as e:
            import traceback
            error_details = traceback.format_exc()
            messagebox.showerror("Errore", f"Errore generazione:\n{e}\n\nDettagli:\n{error_details}")
    
    def _invia_alla_macchina(self):
        """Apre il dialog di invio programmi alla macchina."""
        nome_progetto = self.entry_nome_cartella.get().strip()
        if not nome_progetto:
            return messagebox.showwarning("Attenzione", "Nome progetto mancante")
        
        sorgente_dir = getattr(self, "_sorgente_dir", "")
        if not sorgente_dir or not os.path.isdir(sorgente_dir):
            return messagebox.showwarning(
                "Attenzione",
                "Cartella sorgente non trovata.\n"
                "Genera prima il MAIN per impostare la cartella di origine."
            )
        
        from ui.dialog_invia_macchina import apri_dialog_invia
        apri_dialog_invia(self.parent, sorgente_dir, nome_progetto)

    def _apri_impostazioni_calibra(self):
        """Apre dialog impostazioni CALIBRA ONLY."""
        show_calibra_settings(self.parent)
