#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool Manager V13 - Entry Point
"""

import customtkinter as ctk
from tkinter import messagebox

from config.theme import APPEARANCE_MODE, DEFAULT_COLOR_THEME
from ui.main_window import MainWindow


def main():
    """Avvia l'applicazione."""
    # Configurazione CustomTkinter
    ctk.set_appearance_mode(APPEARANCE_MODE)
    ctk.set_default_color_theme(DEFAULT_COLOR_THEME)
    
    # Crea e avvia finestra principale
    try:
        app = MainWindow()
        app.mainloop()
    except Exception as e:
        messagebox.showerror(
            "Errore Critico",
            f"Errore avvio applicazione:\n{e}"
        )
        import traceback
        traceback.print_exc()
        if 'app' in locals() and app:
            app.destroy()


if __name__ == "__main__":
    main()
