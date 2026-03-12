"""
Script per consolidare holder/bussole duplicati esistenti.

Esegui questo script UNA VOLTA per pulire duplicati già presenti nel database.
Poi il sistema previene automaticamente nuovi duplicati.
"""

import pandas as pd
import os
from datetime import datetime

def consolida_holder_duplicati(csv_path):
    """Consolida holder duplicati raggruppando per Alias_Holder."""
    
    if not os.path.exists(csv_path):
        print(f"❌ File non trovato: {csv_path}")
        return False
    
    # Backup
    backup_path = csv_path.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    
    try:
        # Carica
        df = pd.read_csv(csv_path)
        
        print(f"\n📊 HOLDER PRIMA CONSOLIDAMENTO:")
        print(f"   Righe totali: {len(df)}")
        
        # Mostra duplicati
        if not df.empty:
            df['Alias_Holder'] = df['Alias_Holder'].astype(str).str.strip()
            duplicati = df[df.duplicated('Alias_Holder', keep=False)]
            if not duplicati.empty:
                print(f"\n🔍 DUPLICATI TROVATI:")
                for alias in duplicati['Alias_Holder'].unique():
                    righe = df[df['Alias_Holder'] == alias]
                    print(f"   {alias}: {len(righe)} righe, qty totale: {righe['Quantita'].sum()}")
        
        # Backup
        df.to_csv(backup_path, index=False)
        print(f"\n💾 Backup salvato: {backup_path}")
        
        # Consolida raggruppando per Alias_Holder
        df_consolidato = df.groupby('Alias_Holder', as_index=False).agg({
            'Quantita': 'sum',  # Somma quantità
            'Data_Smontaggio': 'first',  # Prendi prima data
            'Note': lambda x: ' | '.join(x.dropna().astype(str)) if x.notna().any() else ''
        })
        
        print(f"\n📊 HOLDER DOPO CONSOLIDAMENTO:")
        print(f"   Righe totali: {len(df_consolidato)}")
        print(f"   Righe eliminate: {len(df) - len(df_consolidato)}")
        
        # Salva
        df_consolidato.to_csv(csv_path, index=False)
        print(f"\n✅ File consolidato salvato: {csv_path}")
        
        # Mostra risultato
        print(f"\n📋 HOLDER CONSOLIDATI:")
        for _, row in df_consolidato.iterrows():
            print(f"   {row['Alias_Holder']}: qty {row['Quantita']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return False


def consolida_bussole_duplicate(csv_path):
    """Consolida bussole duplicate raggruppando per Codice_Bussola."""
    
    if not os.path.exists(csv_path):
        print(f"❌ File non trovato: {csv_path}")
        return False
    
    # Backup
    backup_path = csv_path.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
    
    try:
        # Carica
        df = pd.read_csv(csv_path)
        
        print(f"\n📊 BUSSOLE PRIMA CONSOLIDAMENTO:")
        print(f"   Righe totali: {len(df)}")
        
        # Mostra duplicati
        if not df.empty:
            df['Codice_Bussola'] = df['Codice_Bussola'].astype(str).str.strip()
            duplicati = df[df.duplicated('Codice_Bussola', keep=False)]
            if not duplicati.empty:
                print(f"\n🔍 DUPLICATI TROVATI:")
                for cod in duplicati['Codice_Bussola'].unique():
                    righe = df[df['Codice_Bussola'] == cod]
                    print(f"   {cod}: {len(righe)} righe, qty totale: {righe['Quantita'].sum()}")
        
        # Backup
        df.to_csv(backup_path, index=False)
        print(f"\n💾 Backup salvato: {backup_path}")
        
        # Consolida raggruppando per Codice_Bussola
        df_consolidato = df.groupby('Codice_Bussola', as_index=False).agg({
            'Diametro': 'first',  # Prendi primo diametro
            'Quantita': 'sum',  # Somma quantità
            'Data_Acquisizione': 'first',  # Prendi prima data
            'Note': lambda x: ' | '.join(x.dropna().astype(str)) if x.notna().any() else ''
        })
        
        print(f"\n📊 BUSSOLE DOPO CONSOLIDAMENTO:")
        print(f"   Righe totali: {len(df_consolidato)}")
        print(f"   Righe eliminate: {len(df) - len(df_consolidato)}")
        
        # Salva
        df_consolidato.to_csv(csv_path, index=False)
        print(f"\n✅ File consolidato salvato: {csv_path}")
        
        # Mostra risultato
        print(f"\n📋 BUSSOLE CONSOLIDATE:")
        for _, row in df_consolidato.iterrows():
            print(f"   {row['Codice_Bussola']}: qty {row['Quantita']}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ ERRORE: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("CONSOLIDAMENTO DUPLICATI HOLDER E BUSSOLE")
    print("=" * 60)
    
    # Path database (modifica se necessario)
    base_path = os.path.dirname(os.path.abspath(__file__))
    
    # Percorsi default
    holder_csv = os.path.join(base_path, "database", "holder_smontati.csv")
    bussole_csv = os.path.join(base_path, "database", "bussole_idraulico.csv")
    
    # Chiedi conferma
    print(f"\nFile holder:  {holder_csv}")
    print(f"File bussole: {bussole_csv}")
    print("\n⚠️  ATTENZIONE: Verrà creato un backup automatico prima di modificare.")
    
    risposta = input("\nProcedere con il consolidamento? (s/n): ")
    
    if risposta.lower() != 's':
        print("\n❌ Operazione annullata.")
        exit(0)
    
    # Consolida holder
    print("\n" + "=" * 60)
    print("CONSOLIDAMENTO HOLDER")
    print("=" * 60)
    success_h = consolida_holder_duplicati(holder_csv)
    
    # Consolida bussole
    print("\n" + "=" * 60)
    print("CONSOLIDAMENTO BUSSOLE")
    print("=" * 60)
    success_b = consolida_bussole_duplicate(bussole_csv)
    
    # Risultato finale
    print("\n" + "=" * 60)
    print("RISULTATO FINALE")
    print("=" * 60)
    
    if success_h:
        print("✅ Holder consolidati")
    else:
        print("❌ Errore consolidamento holder")
    
    if success_b:
        print("✅ Bussole consolidate")
    else:
        print("❌ Errore consolidamento bussole")
    
    print("\n💡 Da ora in poi l'app previene automaticamente nuovi duplicati!")
    print("\nPremi INVIO per chiudere...")
    input()
