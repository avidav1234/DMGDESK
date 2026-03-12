"""
SCRIPT DI DIAGNOSI - Verifica CALIBRA ONLY Settings
Esegui questo per vedere se le impostazioni vengono caricate correttamente
"""

import json
import os

print("=" * 60)
print("DIAGNOSI CALIBRA ONLY - V14")
print("=" * 60)
print()

# 1. Verifica file settings
settings_file = "calibra_only_settings.json"
print(f"1. Verifica file impostazioni...")
print(f"   Percorso: {os.path.abspath(settings_file)}")

if os.path.exists(settings_file):
    print(f"   ✅ File ESISTE")
    
    try:
        with open(settings_file, 'r', encoding='utf-8') as f:
            settings = json.load(f)
        
        print(f"   ✅ File LEGGIBILE")
        print()
        print("   Contenuto:")
        for key, value in settings.items():
            print(f"      {key}: {value}")
    except Exception as e:
        print(f"   ❌ ERRORE lettura: {e}")
else:
    print(f"   ❌ File NON ESISTE")
    print(f"   → Usa impostazioni default")

print()
print("-" * 60)
print()

# 2. Testa logica
print(f"2. Test logica CALIBRA ONLY...")

try:
    from logic.calibra_only_logic import get_calibra_logic
    
    calibra_logic = get_calibra_logic()
    print(f"   ✅ Logica importata")
    
    # Mostra modalità corrente
    mode = calibra_logic.get_current_mode()
    mode_desc = calibra_logic.get_mode_description()
    
    print()
    print(f"   Modalità corrente: {mode}")
    print(f"   Descrizione: {mode_desc}")
    
    if mode == 'finitura_x':
        x = calibra_logic.get_x_finitura()
        print(f"   X finitura: {x}")
    
    if mode == 'ogni_x':
        x = calibra_logic.get_x_qualsiasi()
        print(f"   X qualsiasi: {x}")
    
    print()
    print("   Test simulazione:")
    print()
    
    # Simula alcuni utensili
    utensili_test = [
        ("FF10R0.5L50F60G3", "FF"),
        ("FS12R1L60F70H8", "FS"),
        ("FF10R0.5L50F60G3", "FF"),  # 2° richiamo FF10
        ("P10-30VDF60E3", "P"),
        ("FF10R0.5L50F60G3", "FF"),  # 3° richiamo FF10
        ("FF8R0.3L40F50G2", "FF"),   # 1° richiamo FF8
        ("FS12R1L60F70H8", "FS"),    # 2° richiamo FS12
        ("FF10R0.5L50F60G3", "FF"),  # 4° richiamo FF10
    ]
    
    calibra_logic.reset_call_count()
    
    for idx, (alias, tipo) in enumerate(utensili_test, 1):
        needs = calibra_logic.needs_calibra_only(alias, idx-1, len(utensili_test))
        symbol = "✅ CALIBRA" if needs else "⏹️ No"
        print(f"   T{idx} ({alias}): {symbol}")
    
    print()
    print("   Contatori finali:")
    for tool, count in sorted(calibra_logic.tool_call_count.items()):
        print(f"      {tool}: {count} richiami")
    
except Exception as e:
    print(f"   ❌ ERRORE: {e}")
    import traceback
    traceback.print_exc()

print()
print("-" * 60)
print()

# 3. Verifica file nc_analyzer_v14_update
print(f"3. Verifica nc_analyzer_v14_update...")

try:
    from logic.nc_analyzer_v14_update import genera_programma_main_gcode_v14
    print(f"   ✅ File TROVATO e importabile")
except ImportError as e:
    print(f"   ❌ File NON TROVATO")
    print(f"   → Verrà usato fallback (vecchia logica)")
    print(f"   Errore: {e}")

print()
print("=" * 60)
print("DIAGNOSI COMPLETATA")
print("=" * 60)
