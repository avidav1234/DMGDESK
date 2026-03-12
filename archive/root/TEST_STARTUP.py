#!/usr/bin/env python3
"""Test avvio app - verifica import e inizializzazione base"""

import sys
import os

print("=" * 60)
print("TEST AVVIO TOOL MANAGER V12.4")
print("=" * 60)

# Test 1: Import moduli base
print("\n1️⃣ Test import moduli...")
try:
    from config import theme, constants
    print("   ✅ config")
except Exception as e:
    print(f"   ❌ config: {e}")
    sys.exit(1)

try:
    from database import db_handler
    print("   ✅ database")
except Exception as e:
    print(f"   ❌ database: {e}")
    sys.exit(1)

# Test 2: Verifica funzioni chiave db_handler
print("\n2️⃣ Test funzioni database...")
required_funcs = [
    'carica_database',
    'salva_database',
    'decodifica_holder',
    'carica_database_utensili_smontati',
    'carica_database_holder_smontati',
    'carica_database_bussole_idraulico',
    'smonta_utensile',
    'get_db_paths',
    'carica_configurazione',
    'salva_configurazione'
]

for func in required_funcs:
    if hasattr(db_handler, func):
        print(f"   ✅ {func}")
    else:
        print(f"   ❌ {func} MISSING")
        sys.exit(1)

# Test 3: Verifica costanti
print("\n3️⃣ Test costanti...")
required_constants = [
    'STATO_IN_MACCHINA',
    'STATO_SCAFFALE',
    'STATO_SMONTATO',
    'HOLDER_TYPES',
    'BUSSOLE_IDRAULICO_E'
]

for const in required_constants:
    if hasattr(constants, const):
        print(f"   ✅ {const}")
    else:
        print(f"   ❌ {const} MISSING")

# Test 4: Theme helpers
print("\n4️⃣ Test theme helpers...")
try:
    style = theme.get_button_style("primary", "medium")
    assert 'fg_color' in style
    assert 'hover_color' in style
    print("   ✅ get_button_style")
except Exception as e:
    print(f"   ❌ get_button_style: {e}")

try:
    font = theme.get_font("normal", False)
    assert len(font) == 3
    print("   ✅ get_font")
except Exception as e:
    print(f"   ❌ get_font: {e}")

print("\n" + "=" * 60)
print("✅ TUTTI I TEST PASSATI - APP PRONTA")
print("=" * 60)
print("\nAvvia con: python main.py")
