#!/usr/bin/env python3
"""Test Progressivo - Abilita componenti uno alla volta"""

import customtkinter as ctk
from tkinter import ttk
import pandas as pd

from config.theme import *
from config.constants import *

ctk.set_appearance_mode(APPEARANCE_MODE)
ctk.set_default_color_theme(DEFAULT_COLOR_THEME)

class TestProgressivo(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("TEST PROGRESSIVO")
        self.geometry(f"{WINDOW_WIDTH}x{WINDOW_HEIGHT}")
        
        # TEST 1: Header con costanti
        print("Test 1: Header...")
        header = ctk.CTkFrame(self, fg_color=COLOR_PRIMARY, height=70)
        header.pack(fill="x")
        
        label = ctk.CTkLabel(header, text="TEST HEADER", font=get_font("header", True))
        label.pack(pady=10)
        print("✅ Header OK")
        
        # TEST 2: Button con get_button_style
        print("Test 2: Button style...")
        btn = ctk.CTkButton(self, text="Test", **get_button_style("primary", "medium"))
        btn.pack(pady=10)
        print("✅ Button OK")
        
        # TEST 3: TreeView
        print("Test 3: TreeView...")
        tree_frame = ctk.CTkFrame(self)
        tree_frame.pack(fill="both", expand=True, padx=10, pady=10)
        
        tree = ttk.Treeview(tree_frame, columns=("Col1", "Col2"), show="headings", height=10)
        tree.heading("Col1", text="COLONNA 1")
        tree.heading("Col2", text="COLONNA 2")
        tree.column("Col1", width=200)
        tree.column("Col2", width=300)
        tree.pack(fill="both", expand=True)
        print("✅ TreeView OK")
        
        # TEST 4: Style TreeView (SOSPETTO!)
        print("Test 4: TreeView Style...")
        try:
            style = ttk.Style()
            style.theme_use("default")
            style.configure(
                "Treeview",
                background=COLOR_SURFACE,
                foreground=COLOR_TEXT_PRIMARY,
                font=(FONT_FAMILY, FONT_SIZE_NORMAL)
            )
            print("✅ Style OK")
        except Exception as e:
            print(f"❌ Style ERRORE: {e}")

if __name__ == "__main__":
    app = TestProgressivo()
    app.mainloop()
