#!/usr/bin/env python3
"""
Test logica smonta_utensile() per verificare riconoscimento holder.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_handler import smonta_utensile

# Test cases
test_cases = [
    # (alias_input, expected_utensile, expected_holder, expected_bussola, descrizione)
    
    # Casi CON holder
    ("PUNTA-10H4", "PUNTA-10", "H4", None, "Holder H4 semplice"),
    ("CENTRINO-8-F50E3", "CENTRINO-8-F50", "E", "E3", "Holder E + bussola E3"),
    ("FRESA-12-FSH4", "FRESA-12-FS", "H4", None, "Impiego FS + holder H4"),
    ("ALESATORE-20K2", "ALESATORE-20", "K2", None, "Holder K2 (Weldon)"),
    ("MASCHIO-M6G1", "MASCHIO-M6", "G1", None, "Holder G1 (Idraulico Tendo Slim Lungo)"),
    
    # Casi SENZA holder (parametri fresa)
    ("FF10R0.5L50F60", "FF10R0.5L50F60", None, None, "Impiego FF + diametro F60 (NO holder!)"),
    ("FS20R1L100F80", "FS20R1L100F80", None, None, "Impiego FS + diametro F80 (NO holder!)"),
    ("FP15R0.8L75F50", "FP15R0.8L75F50", None, None, "Impiego FP + diametro F50 (NO holder!)"),
    
    # Casi MISTI (impiego + holder vero)
    ("FF10R0.5L50F60H4", "FF10R0.5L50F60", "H4", None, "Impiego FF + diametro F60 + holder H4"),
    ("FS20R1L100F80K2", "FS20R1L100F80", "K2", None, "Impiego FS + diametro F80 + holder K2"),
    
    # Edge cases
    ("UTENSILE-SEMPLICE", "UTENSILE-SEMPLICE", None, None, "Nessun holder (nessuna lettera finale)"),
    ("PUNTA-10", "PUNTA-10", None, None, "Nessun holder (solo numero finale)"),
]

def run_tests():
    """Esegue tutti i test."""
    print("=" * 80)
    print("TEST LOGICA SMONTA_UTENSILE()")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for alias, exp_ut, exp_h, exp_b, desc in test_cases:
        print(f"\n📝 Test: {desc}")
        print(f"   Input: '{alias}'")
        
        # Esegui
        result_ut, result_h, result_b = smonta_utensile(alias)
        
        # Verifica
        ok_ut = result_ut == exp_ut
        ok_h = result_h == exp_h
        ok_b = result_b == exp_b
        
        if ok_ut and ok_h and ok_b:
            print(f"   ✅ PASS")
            print(f"      Utensile: '{result_ut}'")
            if result_h:
                print(f"      Holder: '{result_h}'")
            if result_b:
                print(f"      Bussola: '{result_b}'")
            passed += 1
        else:
            print(f"   ❌ FAIL")
            print(f"      Expected: utensile='{exp_ut}', holder='{exp_h}', bussola='{exp_b}'")
            print(f"      Got:      utensile='{result_ut}', holder='{result_h}', bussola='{result_b}'")
            failed += 1
    
    # Risultato finale
    print("\n" + "=" * 80)
    print("RISULTATO FINALE")
    print("=" * 80)
    print(f"✅ Passed: {passed}/{len(test_cases)}")
    print(f"❌ Failed: {failed}/{len(test_cases)}")
    
    if failed == 0:
        print("\n🎉 TUTTI I TEST PASSATI!")
        return 0
    else:
        print(f"\n⚠️  {failed} test falliti")
        return 1

if __name__ == "__main__":
    exit_code = run_tests()
    
    print("\nPremi INVIO per chiudere...")
    input()
    
    sys.exit(exit_code)
