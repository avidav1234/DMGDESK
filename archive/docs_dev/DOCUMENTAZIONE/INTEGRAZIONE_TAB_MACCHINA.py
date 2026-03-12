"""
ESEMPIO INTEGRAZIONE - tab_macchina.py
Come aggiungere pulsante impostazioni CALIBRA ONLY
"""

# ============= IMPORTS DA AGGIUNGERE =============
from ui.calibra_only_settings_dialog import show_calibra_settings
from logic.main_generator_v14 import genera_programma_main_with_preview
from logic.calibra_only_logic import get_calibra_logic


# ============= NELLA SEZIONE UI (es. toolbar) =============
def _create_toolbar_section_example(self):
    """Esempio di toolbar con pulsanti MAIN."""
    
    # Frame per gruppo pulsanti MAIN
    main_group = ctk.CTkFrame(toolbar, fg_color="transparent")
    main_group.pack(side="left", padx=10)
    
    # Label gruppo
    ctk.CTkLabel(
        main_group,
        text="PROGRAMMA MAIN:",
        font=("Segoe UI", 11, "bold"),
        text_color="#616161"
    ).pack(side="left", padx=(0, 10))
    
    # Pulsante GENERA MAIN
    ctk.CTkButton(
        main_group,
        text="📝 GENERA MAIN",
        width=140,
        height=40,
        fg_color="#2196F3",
        hover_color="#1976D2",
        font=("Segoe UI", 12, "bold"),
        corner_radius=8,
        command=self._genera_main
    ).pack(side="left", padx=2)
    
    # Pulsante IMPOSTAZIONI (⚙️)
    ctk.CTkButton(
        main_group,
        text="⚙️",  # Icona ingranaggio
        width=45,
        height=40,
        fg_color="#9E9E9E",
        hover_color="#757575",
        font=("Segoe UI", 16),
        corner_radius=8,
        command=self._apri_impostazioni_calibra
    ).pack(side="left", padx=2)
    
    # Info modalità corrente (opzionale)
    self.calibra_mode_label = ctk.CTkLabel(
        main_group,
        text="",
        font=("Segoe UI", 9),
        text_color="#757575"
    )
    self.calibra_mode_label.pack(side="left", padx=10)
    
    # Aggiorna label con modalità corrente
    self._update_calibra_mode_label()


# ============= FUNZIONI DA AGGIUNGERE ALLA CLASSE =============
def _apri_impostazioni_calibra(self):
    """Apre dialog impostazioni CALIBRA ONLY."""
    show_calibra_settings(self.parent)
    
    # Aggiorna label modalità dopo chiusura dialog
    self._update_calibra_mode_label()


def _update_calibra_mode_label(self):
    """Aggiorna label con modalità CALIBRA ONLY corrente."""
    try:
        calibra_logic = get_calibra_logic()
        mode_desc = calibra_logic.get_mode_description()
        self.calibra_mode_label.configure(text=f"Modalità: {mode_desc}")
    except:
        self.calibra_mode_label.configure(text="")


def _genera_main(self):
    """Genera programma MAIN con CALIBRA ONLY configurabile."""
    if self.main.df.empty:
        messagebox.showwarning("Attenzione", "Nessun utensile in macchina")
        return
    
    # Filtra solo utensili IN_MACCHINA
    df_macchina = self.main.df[
        self.main.df['Stato_Utensile'] == 'IN_MACCHINA'
    ].copy()
    
    if df_macchina.empty:
        messagebox.showwarning("Attenzione", "Nessun utensile in macchina")
        return
    
    # Genera con preview e logica CALIBRA ONLY
    success, msg = genera_programma_main_with_preview(
        df_macchina,
        nome_cartella="MAIN",
        parent=self.parent
    )
    
    if success:
        messagebox.showinfo("✅ Successo", msg, parent=self.parent)
    else:
        if msg != "Generazione annullata" and msg != "Annullato":
            messagebox.showerror("Errore", msg, parent=self.parent)


# ============= ALTERNATIVA: PULSANTE IN MENU CONTESTUALE =============
def _add_calibra_context_menu_example(self):
    """Esempio menu contestuale con impostazioni."""
    
    menu = tk.Menu(self.tree, tearoff=0)
    
    menu.add_command(
        label="📝 Genera MAIN",
        command=self._genera_main
    )
    
    menu.add_separator()
    
    menu.add_command(
        label="⚙️ Impostazioni CALIBRA ONLY",
        command=self._apri_impostazioni_calibra
    )
    
    # Bind menu
    self.tree.bind("<Button-3>", lambda e: menu.post(e.x_root, e.y_root))


# ============= VERSIONE COMPLETA TOOLBAR =============
def create_complete_toolbar_example(self, parent_frame):
    """Esempio toolbar completa con tutte le funzioni."""
    
    toolbar = ctk.CTkFrame(parent_frame, fg_color="#FFFFFF", height=60)
    toolbar.pack(fill="x", pady=(10, 10))
    toolbar.pack_propagate(False)
    
    # Gruppo GESTIONE
    group1 = ctk.CTkFrame(toolbar, fg_color="transparent")
    group1.pack(side="left", padx=15)
    
    ctk.CTkButton(
        group1,
        text="➕ Aggiungi",
        width=120,
        fg_color="#4CAF50",
        command=self._aggiungi
    ).pack(side="left", padx=5)
    
    ctk.CTkButton(
        group1,
        text="✏️ Modifica",
        width=120,
        fg_color="#2196F3",
        command=self._modifica
    ).pack(side="left", padx=5)
    
    ctk.CTkButton(
        group1,
        text="🗑️ Elimina",
        width=120,
        fg_color="#EF5350",
        command=self._elimina
    ).pack(side="left", padx=5)
    
    # Separator
    sep1 = ctk.CTkFrame(toolbar, width=2, fg_color="#E0E0E0")
    sep1.pack(side="left", fill="y", padx=15, pady=10)
    
    # Gruppo MAIN (CON IMPOSTAZIONI!)
    main_group = ctk.CTkFrame(toolbar, fg_color="transparent")
    main_group.pack(side="left", padx=10)
    
    # Container orizzontale per MAIN + settings
    main_container = ctk.CTkFrame(main_group, fg_color="transparent")
    main_container.pack(side="left")
    
    ctk.CTkButton(
        main_container,
        text="📝 GENERA MAIN",
        width=140,
        height=40,
        fg_color="#2196F3",
        hover_color="#1976D2",
        font=("Segoe UI", 12, "bold"),
        command=self._genera_main
    ).pack(side="left", padx=2)
    
    ctk.CTkButton(
        main_container,
        text="⚙️",
        width=45,
        height=40,
        fg_color="#9E9E9E",
        hover_color="#757575",
        font=("Segoe UI", 16),
        command=self._apri_impostazioni_calibra
    ).pack(side="left", padx=2)
    
    # Info modalità
    mode_frame = ctk.CTkFrame(main_group, fg_color="#F5F5F5", corner_radius=6)
    mode_frame.pack(side="left", padx=10)
    
    self.calibra_mode_label = ctk.CTkLabel(
        mode_frame,
        text="",
        font=("Segoe UI", 9),
        text_color="#616161"
    )
    self.calibra_mode_label.pack(padx=10, pady=5)
    
    self._update_calibra_mode_label()
