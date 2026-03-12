#!/usr/bin/env python3
"""Main con Debug - Trova punto esatto crash"""

import customtkinter as ctk
from tkinter import messagebox
import traceback

from config.theme import APPEARANCE_MODE, DEFAULT_COLOR_THEME

def test_import():
    """Test import moduli"""
    try:
        print("1. Import ui.main_window...")
        from ui.main_window import MainWindow
        print("   ✅ Import OK")
        return MainWindow
    except Exception as e:
        print(f"   ❌ Import ERRORE: {e}")
        traceback.print_exc()
        return None

def main():
    print("=" * 60)
    print("DEBUG AVVIO TOOL MANAGER")
    print("=" * 60)
    
    # Test 1: Configurazione CTk
    print("\n1. Configurazione CustomTkinter...")
    try:
        ctk.set_appearance_mode(APPEARANCE_MODE)
        ctk.set_default_color_theme(DEFAULT_COLOR_THEME)
        print("   ✅ Configurazione OK")
    except Exception as e:
        print(f"   ❌ Configurazione ERRORE: {e}")
        return
    
    # Test 2: Import MainWindow
    print("\n2. Import MainWindow...")
    MainWindow = test_import()
    if not MainWindow:
        return
    
    # Test 3: Creazione finestra
    print("\n3. Creazione MainWindow...")
    try:
        app = MainWindow()
        print("   ✅ MainWindow creato")
    except Exception as e:
        print(f"   ❌ MainWindow ERRORE: {e}")
        print("\nSTACKTRACE COMPLETO:")
        traceback.print_exc()
        return
    
    # Test 4: Avvio mainloop
    print("\n4. Avvio mainloop...")
    try:
        app.mainloop()
    except Exception as e:
        print(f"   ❌ Mainloop ERRORE: {e}")
        traceback.print_exc()

if __name__ == "__main__":
    main()
