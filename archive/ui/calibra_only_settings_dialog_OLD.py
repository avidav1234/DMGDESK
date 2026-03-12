"""
Dialog Impostazioni CALIBRA ONLY - V14
Popup per configurare quando applicare CALIBRA ONLY nel MAIN
"""

import customtkinter as ctk
from tkinter import messagebox
import json
import os


class CalibraOnlySettingsDialog(ctk.CTkToplevel):
    """Dialog impostazioni CALIBRA ONLY."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("⚙️ Impostazioni CALIBRA ONLY")
        self.geometry("500x400")
        self.resizable(False, False)
        
        # Centra finestra
        self.transient(parent)
        self.grab_set()
        
        # Settings correnti (caricati da file)
        self.settings = self._load_settings()
        
        self._create_ui()
        
        # Focus
        self.focus()
    
    def _create_ui(self):
        """Crea interfaccia dialog."""
        
        # Header
        header = ctk.CTkFrame(self, fg_color="#2196F3", height=60)
        header.pack(fill="x")
        header.pack_propagate(False)
        
        ctk.CTkLabel(
            header,
            text="⚙️ CONFIGURAZIONE CALIBRA ONLY",
            font=("Segoe UI", 16, "bold"),
            text_color="white"
        ).pack(pady=15)
        
        # Content
        content = ctk.CTkFrame(self, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=20, pady=20)
        
        # Info
        info = ctk.CTkLabel(
            content,
            text="Scegli quando inserire CALIBRA ONLY nel programma MAIN:",
            font=("Segoe UI", 11),
            anchor="w"
        )
        info.pack(fill="x", pady=(0, 15))
        
        # Opzioni Radio
        self.mode_var = ctk.StringVar(value=self.settings.get('mode', 'mai'))
        
        options_frame = ctk.CTkFrame(content, fg_color="#F5F5F5", corner_radius=8)
        options_frame.pack(fill="both", expand=True, pady=10)
        
        # Opzione 1: MAI
        opt1 = ctk.CTkRadioButton(
            options_frame,
            text="❌ Mai - Nessun CALIBRA ONLY",
            variable=self.mode_var,
            value="mai",
            font=("Segoe UI", 12),
            command=self._on_mode_change
        )
        opt1.pack(anchor="w", padx=15, pady=10)
        
        desc1 = ctk.CTkLabel(
            options_frame,
            text="   Il MAIN non conterrà alcun comando di calibrazione",
            font=("Segoe UI", 10),
            text_color="#757575",
            anchor="w"
        )
        desc1.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Opzione 2: SOLO INIZIO
        opt2 = ctk.CTkRadioButton(
            options_frame,
            text="▶️ Solo Inizio - CALIBRA ONLY per primo richiamo",
            variable=self.mode_var,
            value="inizio",
            font=("Segoe UI", 12),
            command=self._on_mode_change
        )
        opt2.pack(anchor="w", padx=15, pady=10)
        
        desc2 = ctk.CTkLabel(
            options_frame,
            text="   CALIBRA ONLY solo per il primo utensile del programma",
            font=("Segoe UI", 10),
            text_color="#757575",
            anchor="w"
        )
        desc2.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Opzione 3: FINITURA
        opt3 = ctk.CTkRadioButton(
            options_frame,
            text="✨ Finitura - Ogni utensile di finitura (FF)",
            variable=self.mode_var,
            value="finitura",
            font=("Segoe UI", 12),
            command=self._on_mode_change
        )
        opt3.pack(anchor="w", padx=15, pady=10)
        
        desc3 = ctk.CTkLabel(
            options_frame,
            text="   CALIBRA ONLY per tutti gli utensili FF (frese finitura)",
            font=("Segoe UI", 10),
            text_color="#757575",
            anchor="w"
        )
        desc3.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Opzione 4: FINITURA + OGNI 3
        opt4 = ctk.CTkRadioButton(
            options_frame,
            text="⚡ Avanzato - Finitura + ogni 3 richiami",
            variable=self.mode_var,
            value="avanzato",
            font=("Segoe UI", 12),
            command=self._on_mode_change
        )
        opt4.pack(anchor="w", padx=15, pady=10)
        
        desc4 = ctk.CTkLabel(
            options_frame,
            text="   FF sempre + ogni terzo uso dello stesso utensile",
            font=("Segoe UI", 10),
            text_color="#757575",
            anchor="w"
        )
        desc4.pack(anchor="w", padx=15, pady=(0, 10))
        
        # Buttons
        btn_frame = ctk.CTkFrame(self, fg_color="transparent")
        btn_frame.pack(fill="x", padx=20, pady=(0, 20))
        
        ctk.CTkButton(
            btn_frame,
            text="✅ Salva",
            width=120,
            height=40,
            fg_color="#4CAF50",
            hover_color="#43A047",
            font=("Segoe UI", 12, "bold"),
            command=self._save
        ).pack(side="right", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="❌ Annulla",
            width=120,
            height=40,
            fg_color="#9E9E9E",
            hover_color="#757575",
            font=("Segoe UI", 12, "bold"),
            command=self.destroy
        ).pack(side="right", padx=5)
    
    def _on_mode_change(self):
        """Callback cambio modalità."""
        pass  # Può essere usato per mostrare preview
    
    def _load_settings(self):
        """Carica settings da file JSON."""
        settings_file = "calibra_only_settings.json"
        
        default_settings = {
            'mode': 'finitura',  # Default: finitura
            'last_updated': None
        }
        
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default_settings
        
        return default_settings
    
    def _save_settings(self, settings):
        """Salva settings su file JSON."""
        settings_file = "calibra_only_settings.json"
        
        from datetime import datetime
        settings['last_updated'] = datetime.now().isoformat()
        
        try:
            with open(settings_file, 'w', encoding='utf-8') as f:
                json.dump(settings, f, indent=2, ensure_ascii=False)
            return True
        except Exception as e:
            print(f"Errore salvataggio settings: {e}")
            return False
    
    def _save(self):
        """Salva impostazioni e chiudi."""
        mode = self.mode_var.get()
        
        self.settings['mode'] = mode
        
        if self._save_settings(self.settings):
            messagebox.showinfo(
                "✅ Salvato",
                f"Impostazioni CALIBRA ONLY aggiornate!\n\nModalità: {self._get_mode_name(mode)}",
                parent=self
            )
            self.destroy()
        else:
            messagebox.showerror(
                "Errore",
                "Impossibile salvare le impostazioni",
                parent=self
            )
    
    def _get_mode_name(self, mode):
        """Ritorna nome leggibile della modalità."""
        names = {
            'mai': '❌ Mai',
            'inizio': '▶️ Solo Inizio',
            'finitura': '✨ Finitura',
            'avanzato': '⚡ Avanzato'
        }
        return names.get(mode, mode)


def show_calibra_settings(parent):
    """
    Mostra dialog impostazioni CALIBRA ONLY.
    
    Args:
        parent: Finestra parent
    """
    dialog = CalibraOnlySettingsDialog(parent)
    parent.wait_window(dialog)
