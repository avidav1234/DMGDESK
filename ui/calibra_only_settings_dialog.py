"""
Dialog Impostazioni CALIBRA ONLY - V14 FINALE
Popup per configurare quando applicare CALIBRA ONLY nel MAIN
Con 5 opzioni e campi numerici configurabili
"""

import customtkinter as ctk
from tkinter import messagebox
import json
import os


class CalibraOnlySettingsDialog(ctk.CTkToplevel):
    """Dialog impostazioni CALIBRA ONLY con 5 opzioni."""
    
    def __init__(self, parent):
        super().__init__(parent)
        
        self.title("⚙️ Impostazioni CALIBRA ONLY")
        self.geometry("550x550")
        self.resizable(False, False)
        
        # Centra finestra
        self.transient(parent)
        self.grab_set()
        
        # Settings correnti
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
        
        # Opzioni Frame
        options_frame = ctk.CTkFrame(content, fg_color="#F5F5F5", corner_radius=8)
        options_frame.pack(fill="both", expand=True, pady=10)
        
        # Variabili
        self.mode_var = ctk.StringVar(value=self.settings.get('mode', 'finitura_unico'))
        self.x_finitura_var = ctk.StringVar(value=str(self.settings.get('x_finitura', 3)))
        self.x_qualsiasi_var = ctk.StringVar(value=str(self.settings.get('x_qualsiasi', 3)))
        
        # OPZIONE 1: MAI
        opt1 = ctk.CTkRadioButton(
            options_frame,
            text="❌ Mai - Nessun CALIBRA ONLY",
            variable=self.mode_var,
            value="mai",
            font=("Segoe UI", 11),
            command=self._on_mode_change
        )
        opt1.pack(anchor="w", padx=15, pady=(10, 5))
        
        # OPZIONE 2: INIZIO PROGRAMMA
        opt2 = ctk.CTkRadioButton(
            options_frame,
            text="▶️ Inizio Programma - Solo primo utensile",
            variable=self.mode_var,
            value="inizio",
            font=("Segoe UI", 11),
            command=self._on_mode_change
        )
        opt2.pack(anchor="w", padx=15, pady=5)
        
        # OPZIONE 3: SOLO FINITURA (UNICO)
        opt3 = ctk.CTkRadioButton(
            options_frame,
            text="✨ Solo Finitura - Ogni utensile FF (unico)",
            variable=self.mode_var,
            value="finitura_unico",
            font=("Segoe UI", 11),
            command=self._on_mode_change
        )
        opt3.pack(anchor="w", padx=15, pady=5)
        
        # OPZIONE 4: FINITURA + OGNI X RICHIAMI DI FF
        opt4_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        opt4_frame.pack(anchor="w", padx=15, pady=5, fill="x")
        
        opt4 = ctk.CTkRadioButton(
            opt4_frame,
            text="⚡ Finitura + ogni",
            variable=self.mode_var,
            value="finitura_x",
            font=("Segoe UI", 11),
            command=self._on_mode_change
        )
        opt4.pack(side="left")
        
        self.entry_x_finitura = ctk.CTkEntry(
            opt4_frame,
            width=50,
            height=28,
            textvariable=self.x_finitura_var,
            font=("Segoe UI", 11)
        )
        self.entry_x_finitura.pack(side="left", padx=5)
        
        ctk.CTkLabel(
            opt4_frame,
            text="richiami di FF",
            font=("Segoe UI", 11)
        ).pack(side="left")
        
        desc4 = ctk.CTkLabel(
            options_frame,
            text="   FF sempre + ogni X-esimo richiamo di utensili finitura",
            font=("Segoe UI", 9),
            text_color="#757575",
            anchor="w"
        )
        desc4.pack(anchor="w", padx=15, pady=(0, 5))
        
        # OPZIONE 5: OGNI X RICHIAMI QUALSIASI
        opt5_frame = ctk.CTkFrame(options_frame, fg_color="transparent")
        opt5_frame.pack(anchor="w", padx=15, pady=5, fill="x")
        
        opt5 = ctk.CTkRadioButton(
            opt5_frame,
            text="🔄 Ogni",
            variable=self.mode_var,
            value="ogni_x",
            font=("Segoe UI", 11),
            command=self._on_mode_change
        )
        opt5.pack(side="left")
        
        self.entry_x_qualsiasi = ctk.CTkEntry(
            opt5_frame,
            width=50,
            height=28,
            textvariable=self.x_qualsiasi_var,
            font=("Segoe UI", 11)
        )
        self.entry_x_qualsiasi.pack(side="left", padx=5)
        
        ctk.CTkLabel(
            opt5_frame,
            text="richiami di qualsiasi utensile",
            font=("Segoe UI", 11)
        ).pack(side="left")
        
        desc5 = ctk.CTkLabel(
            options_frame,
            text="   Ogni X-esimo richiamo di ogni utensile (FF, FS, P, ecc.)",
            font=("Segoe UI", 9),
            text_color="#757575",
            anchor="w"
        )
        desc5.pack(anchor="w", padx=15, pady=(0, 10))
        
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
        """Callback cambio modalità - Abilita/disabilita campi numerici."""
        mode = self.mode_var.get()
        
        # Abilita campo X finitura solo se modalità finitura_x
        if mode == "finitura_x":
            self.entry_x_finitura.configure(state="normal")
        else:
            self.entry_x_finitura.configure(state="disabled")
        
        # Abilita campo X qualsiasi solo se modalità ogni_x
        if mode == "ogni_x":
            self.entry_x_qualsiasi.configure(state="normal")
        else:
            self.entry_x_qualsiasi.configure(state="disabled")
    
    def _load_settings(self):
        """Carica settings da file JSON."""
        settings_file = "calibra_only_settings.json"
        
        default_settings = {
            'mode': 'finitura_unico',
            'x_finitura': 3,
            'x_qualsiasi': 3,
            'last_updated': None
        }
        
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    # Merge con default per nuovi campi
                    default_settings.update(loaded)
                    return default_settings
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
    
    def _validate_number(self, value_str, field_name):
        """Valida che il valore sia un numero intero positivo."""
        try:
            num = int(value_str)
            if num < 1:
                messagebox.showerror(
                    "Errore",
                    f"{field_name} deve essere almeno 1",
                    parent=self
                )
                return None
            if num > 100:
                messagebox.showerror(
                    "Errore",
                    f"{field_name} non può essere maggiore di 100",
                    parent=self
                )
                return None
            return num
        except ValueError:
            messagebox.showerror(
                "Errore",
                f"{field_name} deve essere un numero intero",
                parent=self
            )
            return None
    
    def _save(self):
        """Salva impostazioni e chiudi."""
        mode = self.mode_var.get()
        
        # Valida campi numerici
        x_finitura = self._validate_number(self.x_finitura_var.get(), "Richiami finitura")
        if x_finitura is None and mode == "finitura_x":
            return
        
        x_qualsiasi = self._validate_number(self.x_qualsiasi_var.get(), "Richiami qualsiasi")
        if x_qualsiasi is None and mode == "ogni_x":
            return
        
        # Aggiorna settings
        self.settings['mode'] = mode
        self.settings['x_finitura'] = x_finitura if x_finitura else int(self.x_finitura_var.get())
        self.settings['x_qualsiasi'] = x_qualsiasi if x_qualsiasi else int(self.x_qualsiasi_var.get())
        
        if self._save_settings(self.settings):
            mode_name = self._get_mode_name(mode)
            messagebox.showinfo(
                "✅ Salvato",
                f"Impostazioni CALIBRA ONLY aggiornate!\n\nModalità: {mode_name}",
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
        mode_names = {
            'mai': '❌ Mai',
            'inizio': '▶️ Inizio Programma',
            'finitura_unico': '✨ Solo Finitura',
            'finitura_x': f"⚡ Finitura + ogni {self.settings.get('x_finitura', 3)} richiami FF",
            'ogni_x': f"🔄 Ogni {self.settings.get('x_qualsiasi', 3)} richiami"
        }
        return mode_names.get(mode, mode)


def show_calibra_settings(parent):
    """
    Mostra dialog impostazioni CALIBRA ONLY.
    
    Args:
        parent: Finestra parent
    """
    dialog = CalibraOnlySettingsDialog(parent)
    parent.wait_window(dialog)
