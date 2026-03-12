"""Tab Generatore - Code Generator integrato in ToolManager V14 con SPECIALE"""
import customtkinter as ctk
from tkinter import messagebox, simpledialog
import pandas as pd
from datetime import datetime

from config.theme import *
from config.constants import *
from logic.code_generator_logic import UTENSILI, PORTA_UTENSILI, genera_codici
from database.db_handler import (
    smonta_utensile, salva_database, salva_database_utensili_smontati,
    salva_database_holder_smontati, salva_database_bussole_idraulico
)


class TabGeneratore:
    def __init__(self, parent, main_window):
        self.parent = parent
        self.main = main_window
        self._create_ui()
    
    def _create_ui(self):
        # Header
        header = ctk.CTkFrame(self.parent, fg_color=COLOR_PRIMARY, height=80)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(header, text="📝 GENERATORE CODICI UTENSILI",
                    font=get_font("title", bold=True),
                    text_color="white").pack(pady=(12, 2))
        
        ctk.CTkLabel(header, text="Crea codici DMG • Aggiungi direttamente a inventario",
                    font=get_font("body"),
                    text_color="#F5F5F5").pack(pady=(0, 8))
        
        # Container
        container = ctk.CTkFrame(self.parent, fg_color="transparent")
        container.pack(fill="both", expand=True, pady=(10, 0))
        
        # LEFT: Parametri
        left = ctk.CTkFrame(container, fg_color=COLOR_SURFACE, corner_radius=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 5))
        
        h = ctk.CTkFrame(left, fg_color=COLOR_TABLE_HEADER, height=35, corner_radius=0)
        h.pack(fill="x")
        h.pack_propagate(False)
        ctk.CTkLabel(h, text="PARAMETRI UTENSILE", font=get_font("subtitle", bold=True)).pack(pady=8)
        
        params = ctk.CTkFrame(left, fg_color="transparent")
        params.pack(fill="both", expand=True, padx=15, pady=15)
        
        row = 0
        
        # Tipologia
        ctk.CTkLabel(params, text="Tipologia:", font=get_font("body")).grid(row=row, column=0, sticky="w", pady=8)
        self.tipo_var = ctk.StringVar()
        self.tipo_combo = ctk.CTkComboBox(params, variable=self.tipo_var, 
                                         values=list(UTENSILI.keys()),
                                         width=300, state="readonly")
        self.tipo_combo.grid(row=row, column=1, pady=8, sticky="ew")
        self.tipo_combo.set("Seleziona...")
        row += 1
        
        # Diametro
        ctk.CTkLabel(params, text="Diametro (mm):", font=get_font("body")).grid(row=row, column=0, sticky="w", pady=8)
        self.diam_var = ctk.StringVar()
        ctk.CTkEntry(params, textvariable=self.diam_var, width=300).grid(row=row, column=1, pady=8, sticky="ew")
        row += 1
        
        # R2/X
        self.r2_label = ctk.CTkLabel(params, text="R2/X:", font=get_font("body"))
        self.r2_label.grid(row=row, column=0, sticky="w", pady=8)
        self.r2_var = ctk.StringVar()
        self.r2_entry = ctk.CTkEntry(params, textvariable=self.r2_var, width=300, state="disabled")
        self.r2_entry.grid(row=row, column=1, pady=8, sticky="ew")
        row += 1
        
        # L
        self.l_label = ctk.CTkLabel(params, text="L:", font=get_font("body"))
        self.l_label.grid(row=row, column=0, sticky="w", pady=8)
        self.l_var = ctk.StringVar()
        self.l_entry = ctk.CTkEntry(params, textvariable=self.l_var, width=300, state="disabled")
        self.l_entry.grid(row=row, column=1, pady=8, sticky="ew")
        row += 1
        
        # VD
        self.vd_label = ctk.CTkLabel(params, text="VD:", font=get_font("body"))
        self.vd_label.grid(row=row, column=0, sticky="w", pady=8)
        self.vd_var = ctk.StringVar()
        self.vd_entry = ctk.CTkEntry(params, textvariable=self.vd_var, width=300, state="disabled")
        self.vd_entry.grid(row=row, column=1, pady=8, sticky="ew")
        row += 1
        
        # FP
        ctk.CTkLabel(params, text="Fuori Pinza:", font=get_font("body")).grid(row=row, column=0, sticky="w", pady=8)
        self.fp_var = ctk.StringVar()
        ctk.CTkEntry(params, textvariable=self.fp_var, width=300).grid(row=row, column=1, pady=8, sticky="ew")
        row += 1
        
        # ========== FLAGS (Fresa Dedicata + SPECIALE) ==========
        # Frame per checkbox allineati
        flags_frame = ctk.CTkFrame(params, fg_color="transparent")
        flags_frame.grid(row=row, column=1, pady=8, sticky="w")
        
        # Fresa Dedicata
        self.dedicata_var = ctk.BooleanVar(value=False)
        self.dedicata_check = ctk.CTkCheckBox(flags_frame, text="Fresa Dedicata", 
                                             variable=self.dedicata_var,
                                             font=get_font("body"))
        self.dedicata_check.pack(side="left", padx=(0, 15))
        
        # ⭐ SPECIALE (NUOVO)
        self.speciale_var = ctk.BooleanVar(value=False)
        self.speciale_check = ctk.CTkCheckBox(flags_frame, text="⚠️ SPECIALE", 
                                              variable=self.speciale_var,
                                              font=get_font("body"))
        self.speciale_check.pack(side="left")
        
        row += 1
        
        # Holder
        ctk.CTkLabel(params, text="Porta-Utensile:", font=get_font("body")).grid(row=row, column=0, sticky="w", pady=8)
        self.holder_var = ctk.StringVar()
        self.holder_combo = ctk.CTkComboBox(params, variable=self.holder_var,
                                           values=list(PORTA_UTENSILI.keys()),
                                           width=300, state="readonly",
                                           command=self._on_holder_change)
        self.holder_combo.grid(row=row, column=1, pady=8, sticky="ew")
        self.holder_combo.set("Seleziona...")
        row += 1
        
        # Diametro Holder
        ctk.CTkLabel(params, text="Diametro Porta:", font=get_font("body")).grid(row=row, column=0, sticky="w", pady=8)
        self.hdiam_var = ctk.StringVar()
        self.hdiam_combo = ctk.CTkComboBox(params, variable=self.hdiam_var, values=[],
                                          width=300, state="disabled")
        self.hdiam_combo.grid(row=row, column=1, pady=8, sticky="ew")
        
        params.columnconfigure(1, weight=1)
        
        # Binds
        self.tipo_var.trace('w', self._on_tipo_change)
        
        # RIGHT: Output
        right = ctk.CTkFrame(container, fg_color=COLOR_SURFACE, corner_radius=10)
        right.pack(side="right", fill="both", expand=True, padx=(5, 0))
        
        h2 = ctk.CTkFrame(right, fg_color=COLOR_TABLE_HEADER, height=35, corner_radius=0)
        h2.pack(fill="x")
        h2.pack_propagate(False)
        ctk.CTkLabel(h2, text="CODICI GENERATI", font=get_font("subtitle", bold=True)).pack(pady=8)
        
        output = ctk.CTkFrame(right, fg_color="transparent")
        output.pack(fill="both", expand=True, padx=15, pady=15)
        
        # ========== ALIAS CNC (Commento) ==========
        ctk.CTkLabel(output, text="Alias CNC (Macchina):", font=get_font("body", bold=True)).pack(anchor="w", pady=(10, 5))
        self.comm_text = ctk.CTkTextbox(output, height=60, font=("Consolas", 14))
        self.comm_text.pack(fill="x", pady=(0, 5))
        self.comm_text.insert("1.0", "...")
        self.comm_text.configure(state="disabled")
        
        ctk.CTkButton(output, text="📋 Copia Alias",
                     **get_button_style("primary", "small"),
                     command=self._copia_comm).pack(anchor="w", pady=(0, 15))
        
        # ========== NOME CIMATRON (CAM) ==========
        ctk.CTkLabel(output, text="Nome Cimatron (CAM):", font=get_font("body", bold=True)).pack(anchor="w", pady=(10, 5))
        self.nome_text = ctk.CTkTextbox(output, height=60, font=("Consolas", 12))
        self.nome_text.pack(fill="x", pady=(0, 5))
        self.nome_text.insert("1.0", "...")
        self.nome_text.configure(state="disabled")
        
        ctk.CTkButton(output, text="📋 Copia Nome",
                     **get_button_style("primary", "small"),
                     command=self._copia_nome).pack(anchor="w", pady=(0, 15))
        
        # Genera
        ctk.CTkButton(output, text="✅ GENERA CODICE",
                     **get_button_style("success", "large"),
                     command=self._genera).pack(pady=(10, 20))
        
        # Separator
        sep = ctk.CTkFrame(output, height=2, fg_color=COLOR_BORDER)
        sep.pack(fill="x", pady=15)
        
        # Aggiungi Inventario
        ctk.CTkLabel(output, text="AGGIUNGI A INVENTARIO:", 
                    font=get_font("body", bold=True)).pack(anchor="w", pady=(10, 10))
        
        btn_frame = ctk.CTkFrame(output, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        ctk.CTkButton(btn_frame, text="🏠 SCAFFALE",
                     **get_button_style("success", "large"),
                     command=self._aggiungi_scaffale).pack(side="left", padx=5)
        
        ctk.CTkButton(btn_frame, text="🔧 MACCHINA",
                     **get_button_style("primary", "large"),
                     command=self._aggiungi_macchina).pack(side="left", padx=5)
        
        ctk.CTkButton(btn_frame, text="📦 SMONTATI",
                     **get_button_style("neutral", "large"),
                     command=self._aggiungi_smontati).pack(side="left", padx=5)
    
    def _on_tipo_change(self, *args):
        tipo = self.tipo_var.get()
        if tipo == "Seleziona...":
            return
        
        dati = UTENSILI.get(tipo)
        if not dati:
            return
        
        # R2/X
        if dati.get('has_r2') or dati.get('has_x'):
            self.r2_entry.configure(state="normal")
            if dati.get('has_r2'):
                self.r2_label.configure(text="R2:")
            else:
                self.r2_label.configure(text="X (passo):")
        else:
            self.r2_entry.configure(state="disabled")
            self.r2_var.set('')
        
        # L
        if dati.get('has_l'):
            self.l_entry.configure(state="normal")
        else:
            self.l_entry.configure(state="disabled")
            self.l_var.set('')
        
        # VD
        if dati.get('has_vd'):
            self.vd_entry.configure(state="normal")
        else:
            self.vd_entry.configure(state="disabled")
            self.vd_var.set('')
    
    def _on_holder_change(self, choice):
        if choice == "Seleziona...":
            return
        diametri = PORTA_UTENSILI[choice]['diametri']
        self.hdiam_combo.configure(values=diametri, state="readonly")
        self.hdiam_combo.set("Seleziona...")
    
    def _genera(self):
        nome, comm, err = genera_codici(
            self.tipo_var.get(),
            self.diam_var.get(),
            self.r2_var.get(),
            self.l_var.get(),
            self.vd_var.get(),
            self.fp_var.get(),
            self.holder_var.get(),
            self.hdiam_var.get(),
            self.dedicata_var.get(),  # Fresa Dedicata
            self.speciale_var.get()   # ⭐ SPECIALE (NUOVO)
        )
        
        if err:
            # Reset entrambi i campi in caso di errore
            self.comm_text.configure(state="normal")
            self.comm_text.delete("1.0", "end")
            self.comm_text.insert("1.0", "...")
            self.comm_text.configure(state="disabled")
            
            self.nome_text.configure(state="normal")
            self.nome_text.delete("1.0", "end")
            self.nome_text.insert("1.0", "...")
            self.nome_text.configure(state="disabled")
            
            return messagebox.showerror("Errore", err)
        
        # Popola Alias CNC
        self.comm_text.configure(state="normal")
        self.comm_text.delete("1.0", "end")
        self.comm_text.insert("1.0", comm)
        self.comm_text.configure(state="disabled")
        
        # Popola Nome Cimatron
        self.nome_text.configure(state="normal")
        self.nome_text.delete("1.0", "end")
        self.nome_text.insert("1.0", nome)
        self.nome_text.configure(state="disabled")
    
    def _copia_comm(self):
        comm = self.comm_text.get("1.0", "end").strip()
        if comm != "...":
            self.parent.clipboard_clear()
            self.parent.clipboard_append(comm)
            messagebox.showinfo("✅", f"Alias CNC copiato:\n{comm}")
    
    def _copia_nome(self):
        """Copia il Nome Cimatron negli appunti"""
        nome = self.nome_text.get("1.0", "end").strip()
        if nome != "...":
            self.parent.clipboard_clear()
            self.parent.clipboard_append(nome)
            messagebox.showinfo("✅", f"Nome Cimatron copiato:\n{nome}")
    
    def _aggiungi_scaffale(self):
        codice = self.comm_text.get("1.0", "end").strip()
        if codice == "...":
            return messagebox.showwarning("Attenzione", "Genera prima un codice")
        
        # Estrae holder
        _, holder_cod, bussola_cod = smonta_utensile(codice)
        if not holder_cod:
            return messagebox.showerror("Errore", "Nessun holder nel codice")
        
        # Decrementa holder
        df_h = self.main.df_holder_smontati
        if not df_h.empty:
            df_h['Alias_Holder'] = df_h['Alias_Holder'].astype(str).str.strip()
            if holder_cod not in df_h['Alias_Holder'].values:
                return messagebox.showerror("Errore", f"Holder {holder_cod} non disponibile")
            
            idx = df_h['Alias_Holder'] == holder_cod
            df_h.loc[idx, 'Quantita'] -= 1
            if df_h.loc[idx, 'Quantita'].values[0] <= 0:
                df_h = df_h[~idx].reset_index(drop=True)
            
            self.main.df_holder_smontati = df_h
            salva_database_holder_smontati(df_h, self.main.db_paths['holder_smontati'])
        
        # Decrementa bussola se presente
        if bussola_cod:
            df_b = self.main.df_bussole_idraulico
            if not df_b.empty:
                df_b['Codice_Bussola'] = df_b['Codice_Bussola'].astype(str).str.strip()
                if bussola_cod in df_b['Codice_Bussola'].values:
                    idx = df_b['Codice_Bussola'] == bussola_cod
                    df_b.loc[idx, 'Quantita'] -= 1
                    if df_b.loc[idx, 'Quantita'].values[0] <= 0:
                        df_b = df_b[~idx].reset_index(drop=True)
                    
                    self.main.df_bussole_idraulico = df_b
                    salva_database_bussole_idraulico(df_b, self.main.db_paths['bussole_idraulico'])
        
        # Aggiungi a database
        new_row = {'Posizione': '', 'Alias': codice, 'Stato_Utensile': 'SCAFFALE'}
        self.main.df = pd.concat([self.main.df, pd.DataFrame([new_row])], ignore_index=True)
        salva_database(self.main.df, self.main.db_path)
        self.main.refresh_all_tabs()
        
        msg = f"Utensile aggiunto a SCAFFALE!\n{codice}\n\nHolder {holder_cod} -1"
        if bussola_cod:
            msg += f"\nBussola {bussola_cod} -1"
        messagebox.showinfo("✅", msg)
    
    def _aggiungi_macchina(self):
        codice = self.comm_text.get("1.0", "end").strip()
        if codice == "...":
            return messagebox.showwarning("Attenzione", "Genera prima un codice")
        
        pos = simpledialog.askstring("Posizione", "Posizione in macchina (1-99):")
        if not pos:
            return
        
        # Estrae holder
        _, holder_cod, bussola_cod = smonta_utensile(codice)
        if not holder_cod:
            return messagebox.showerror("Errore", "Nessun holder nel codice")
        
        # Decrementa holder
        df_h = self.main.df_holder_smontati
        if not df_h.empty:
            df_h['Alias_Holder'] = df_h['Alias_Holder'].astype(str).str.strip()
            if holder_cod not in df_h['Alias_Holder'].values:
                return messagebox.showerror("Errore", f"Holder {holder_cod} non disponibile")
            
            idx = df_h['Alias_Holder'] == holder_cod
            df_h.loc[idx, 'Quantita'] -= 1
            if df_h.loc[idx, 'Quantita'].values[0] <= 0:
                df_h = df_h[~idx].reset_index(drop=True)
            
            self.main.df_holder_smontati = df_h
            salva_database_holder_smontati(df_h, self.main.db_paths['holder_smontati'])
        
        # Decrementa bussola
        if bussola_cod:
            df_b = self.main.df_bussole_idraulico
            if not df_b.empty:
                df_b['Codice_Bussola'] = df_b['Codice_Bussola'].astype(str).str.strip()
                if bussola_cod in df_b['Codice_Bussola'].values:
                    idx = df_b['Codice_Bussola'] == bussola_cod
                    df_b.loc[idx, 'Quantita'] -= 1
                    if df_b.loc[idx, 'Quantita'].values[0] <= 0:
                        df_b = df_b[~idx].reset_index(drop=True)
                    
                    self.main.df_bussole_idraulico = df_b
                    salva_database_bussole_idraulico(df_b, self.main.db_paths['bussole_idraulico'])
        
        # Aggiungi a database
        new_row = {'Posizione': pos, 'Alias': codice, 'Stato_Utensile': 'IN_MACCHINA'}
        self.main.df = pd.concat([self.main.df, pd.DataFrame([new_row])], ignore_index=True)
        salva_database(self.main.df, self.main.db_path)
        self.main.refresh_all_tabs()
        
        msg = f"Utensile montato in pos. {pos}!\n{codice}\n\nHolder {holder_cod} -1"
        if bussola_cod:
            msg += f"\nBussola {bussola_cod} -1"
        messagebox.showinfo("✅", msg)
    
    def _aggiungi_smontati(self):
        codice = self.comm_text.get("1.0", "end").strip()
        if codice == "...":
            return messagebox.showwarning("Attenzione", "Genera prima un codice")
        
        # Estrae utensile base (SENZA holder)
        utensile_base, holder_cod, bussola_cod = smonta_utensile(codice)
        
        # Aggiungi a smontati (solo base, senza holder)
        new_row = {
            'ID': len(self.main.df_utensili_smontati) + 1,
            'Alias_Utensile': utensile_base,
            'Data_Smontaggio': datetime.now().strftime('%Y-%m-%d'),
            'Provenienza': 'Generatore',
            'Note': ''
        }
        
        self.main.df_utensili_smontati = pd.concat([
            self.main.df_utensili_smontati,
            pd.DataFrame([new_row])
        ], ignore_index=True)
        
        salva_database_utensili_smontati(
            self.main.df_utensili_smontati,
            self.main.db_paths['utensili_smontati']
        )
        
        # NON decrementa holder (non lo stiamo usando)
        
        self.main.refresh_all_tabs()
        
        msg = f"Utensile aggiunto a SMONTATI!\n{utensile_base}"
        if holder_cod:
            msg += f"\n\n(Holder {holder_cod} rimosso dal codice)"
        messagebox.showinfo("✅", msg)
    
    def refresh(self):
        pass  # Non serve refresh per questo tab