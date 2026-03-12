"""Dialog riutilizzabili"""
import customtkinter as ctk
from tkinter import Toplevel

from config.theme import *


class InputDialog:
    """Dialog input generico."""
    
    def __init__(self, parent, title, fields):
        """
        Args:
            parent: Parent window
            title: Titolo dialog
            fields: Lista di tuple (label, tipo, [default])
        """
        self.result = None
        
        # Crea dialog
        self.dialog = Toplevel(parent)
        self.dialog.title(title)
        self.dialog.geometry("450x300")
        self.dialog.transient(parent)
        self.dialog.attributes("-topmost", True)
        self.dialog.grab_set()
        
        # Center dialog (posizionamento automatico)
        self.dialog.update_idletasks()
        
        # Background
        self.dialog.configure(bg=COLOR_BACKGROUND)
        
        # Fields
        self.entries = []
        for field in fields:
            label_text = field[0]
            default = field[2] if len(field) > 2 else ""
            
            ctk.CTkLabel(
                self.dialog,
                text=label_text,
                font=get_font("normal")
            ).pack(pady=5)
            
            entry = ctk.CTkEntry(
                self.dialog,
                width=350,
                height=40,
                font=get_font("normal")
            )
            entry.insert(0, str(default))
            entry.pack(pady=5)
            self.entries.append(entry)
        
        # Buttons
        btn_frame = ctk.CTkFrame(self.dialog, fg_color="transparent")
        btn_frame.pack(pady=20)
        
        ctk.CTkButton(
            btn_frame,
            text="✅ OK",
            command=self._ok,
            **get_button_style("success", "medium")
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="❌ Annulla",
            command=self._cancel,
            **get_button_style("danger", "medium")
        ).pack(side="left", padx=5)
        
        self.dialog.wait_window()
    
    def _ok(self):
        self.result = [e.get() for e in self.entries]
        self.dialog.destroy()
    
    def _cancel(self):
        self.result = None
        self.dialog.destroy()
