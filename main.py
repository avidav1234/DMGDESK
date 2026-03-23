#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Tool Manager V14.0 - Entry Point
"""

import customtkinter as ctk
from tkinter import messagebox

from config.theme import APPEARANCE_MODE, DEFAULT_COLOR_THEME
from config.constants import APP_VERSION
from ui.main_window import MainWindow
from utils.logger import get_logger

log = get_logger(__name__)


def main():
    """Avvia l'applicazione."""
    log.info(f"Avvio Tool Manager v{APP_VERSION}")

    # Configurazione CustomTkinter
    ctk.set_appearance_mode(APPEARANCE_MODE)
    ctk.set_default_color_theme(DEFAULT_COLOR_THEME)

    # Crea e avvia finestra principale
    try:
        app = MainWindow()
        log.info("Finestra principale creata — avvio mainloop")
        app.mainloop()
        log.info("Applicazione chiusa normalmente")
    except Exception as e:
        import traceback
        tb = traceback.format_exc()
        log.critical("Errore critico all'avvio", exc_info=True)
        try:
            import os, sys
            log_dir = os.path.dirname(sys.executable) if getattr(sys, 'frozen', False) else '.'
            with open(os.path.join(log_dir, 'crash_log.txt'), 'w') as cf:
                cf.write(tb)
        except Exception:
            pass
        messagebox.showerror(
            "Errore Critico",
            f"Errore avvio applicazione:\n{e}\n\n{tb[-800:]}"
        )
        if 'app' in locals() and app:
            app.destroy()


if __name__ == "__main__":
    main()
