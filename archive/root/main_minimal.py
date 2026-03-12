#!/usr/bin/env python3
"""Test Minimal - Trova dove crasha"""

import customtkinter as ctk

ctk.set_appearance_mode("light")
ctk.set_default_color_theme("blue")

class TestMinimal(ctk.CTk):
    def __init__(self):
        super().__init__()
        
        self.title("TEST MINIMAL")
        self.geometry("800x600")
        
        # Test 1: Label semplice
        label = ctk.CTkLabel(self, text="✅ APP AVVIATA", font=("Arial", 20))
        label.pack(pady=50)
        
        # Test 2: Button
        btn = ctk.CTkButton(self, text="Test Button", width=150, height=40)
        btn.pack(pady=20)
        
        # Test 3: Frame
        frame = ctk.CTkFrame(self, width=400, height=200)
        frame.pack(pady=20)
        
        ctk.CTkLabel(frame, text="Frame OK").pack(pady=10)

if __name__ == "__main__":
    app = TestMinimal()
    app.mainloop()
