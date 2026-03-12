#!/usr/bin/env python3
"""
Test completo:
1. Parsing alias reali Vetimec
2. Smontaggio da macchina
3. Smontaggio da scaffale
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from database.db_handler import smonta_utensile, smonta_utensile_completo
import pandas as pd

# Alias reali forniti dall'utente
ALIAS_REALI = [
    "FS25R2L85FS25R2L125F128",
    "FS16R2L80F85E6",
    "FS10R2L50F55G3",
    "FS6R1.5L30F35G1",
    "FS2R0.5L10F25H4",
    "FS16R1L48F63K6",
    "000A6F65E1",
    "P17.6-5VDF125K7",
    "PI12-5VDF100H10",
    "PM20X2.5F64E6",
    "FF20R10F80H18",
    "FF10R5L50F60H8",
    "FF6R3L30F35H4",
    "FF16R1L48F63E6",
    "SMUSSO-12INCD0.5F25",
]

def test_parsing():
    """Test 1: Parsing alias reali."""
    print("=" * 80)
    print("TEST 1: PARSING ALIAS REALI VETIMEC")
    print("=" * 80)
    
    risultati = []
    
    for alias in ALIAS_REALI:
        utensile, holder, bussola = smonta_utensile(alias)
        has_holder = holder is not None
        risultati.append((alias, has_holder, utensile, holder, bussola))
        
        status = "✅" if has_holder else "❌"
        print(f"\n{status} {alias}")
        print(f"   Utensile: {utensile}")
        if holder:
            print(f"   Holder: {holder}")
        if bussola:
            print(f"   Bussola: {bussola}")
    
    # Statistiche
    con_holder = sum(1 for _, h, _, _, _ in risultati if h)
    senza_holder = len(risultati) - con_holder
    
    print(f"\n{'=' * 80}")
    print(f"RISULTATO PARSING:")
    print(f"  ✅ Con holder: {con_holder}/{len(risultati)}")
    print(f"  ❌ Senza holder: {senza_holder}/{len(risultati)}")
    
    return risultati


def test_smontaggio_completo():
    """Test 2: Smontaggio completo (logica)."""
    print("\n" + "=" * 80)
    print("TEST 2: LOGICA SMONTAGGIO COMPLETO")
    print("=" * 80)
    
    # Setup database vuoti
    df_ut = pd.DataFrame(columns=['ID', 'Alias_Utensile', 'Data_Smontaggio', 'Provenienza', 'Note'])
    df_h = pd.DataFrame(columns=['Alias_Holder', 'Data_Smontaggio', 'Quantita', 'Note'])
    df_b = pd.DataFrame(columns=['Codice_Bussola', 'Diametro', 'Quantita', 'Data_Acquisizione', 'Note'])
    
    # Test casi
    test_cases = [
        ("FF20R10F80H18", "Macchina"),
        ("FS16R2L80F85E6", "Scaffale"),
        ("PM20X2.5F64E6", "Macchina"),
        ("SMUSSO-12INCD0.5F25", "Scaffale"),  # Senza holder
    ]
    
    for alias, provenienza in test_cases:
        print(f"\n📋 Test: {alias} (da {provenienza})")
        
        success, msg, df_ut_new, df_h_new, df_b_new = smonta_utensile_completo(
            alias,
            {},  # db_paths vuoto per test
            df_ut, df_h, df_b,
            provenienza=provenienza
        )
        
        if success:
            print(f"   ✅ {msg}")
            
            # Mostra cosa è stato aggiunto
            if len(df_ut_new) > len(df_ut):
                new_ut = df_ut_new.iloc[-1]
                print(f"   → Utensile smontato: {new_ut['Alias_Utensile']}")
            
            if len(df_h_new) > len(df_h):
                new_h = df_h_new.iloc[-1]
                print(f"   → Holder aggiunto: {new_h['Alias_Holder']} (qty: {new_h['Quantita']})")
            elif not df_h_new.empty and not df_h.empty:
                # Incrementato
                if df_h_new['Quantita'].sum() > df_h['Quantita'].sum():
                    print(f"   → Holder incrementato")
            
            if len(df_b_new) > len(df_b):
                new_b = df_b_new.iloc[-1]
                print(f"   → Bussola aggiunta: {new_b['Codice_Bussola']} (qty: {new_b['Quantita']})")
            
            # Aggiorna per test successivo
            df_ut, df_h, df_b = df_ut_new, df_h_new, df_b_new
        else:
            print(f"   ❌ {msg}")
    
    print(f"\n{'=' * 80}")
    print("STATO FINALE DATABASE:")
    print(f"  Utensili smontati: {len(df_ut)}")
    print(f"  Holder smontati: {len(df_h)}")
    print(f"  Bussole: {len(df_b)}")


if __name__ == "__main__":
    print("=" * 80)
    print("TEST COMPLETO: ALIAS REALI + SMONTAGGIO")
    print("=" * 80)
    
    # Test 1: Parsing
    risultati = test_parsing()
    
    # Test 2: Smontaggio
    test_smontaggio_completo()
    
    print("\n" + "=" * 80)
    print("✅ TUTTI I TEST COMPLETATI")
    print("=" * 80)
    
    print("\nPremi INVIO per chiudere...")
    input()
