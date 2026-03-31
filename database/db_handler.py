# db_handler — Tool Manager V14.0
# Gestione Database Utensili e Holder Smontati

import os
import json
import pandas as pd
import numpy as np
import re
from datetime import datetime

try:
    from utils.logger import get_logger, tool_log
    _log = get_logger(__name__)
except ImportError:
    import logging
    _log = logging.getLogger(__name__)
    tool_log = None

# --- NUOVE COSTANTI STATO UTENSILE ---
STATI_UTENSILE = ["IN_MACCHINA", "SCAFFALE", "SMONTATO_DA_PORTA_UTENSILE"]
STATO_IN_MACCHINA = "IN_MACCHINA"
STATO_SCAFFALE = "SCAFFALE"
STATO_SMONTATO = "SMONTATO_DA_PORTA_UTENSILE"
STATO_DEFAULT_DB = "SCAFFALE"

# Colonne database principale
COLONNE_V2 = ['Posizione', 'Alias', 'Stato_Utensile']

# Colonne database utensili smontati (con ID univoco per duplicati)
COLONNE_UTENSILI_SMONTATI = ['ID', 'Alias_Utensile', 'Data_Smontaggio', 'Provenienza', 'Note']

# Colonne database holder smontati (quantità per gestire duplicati)
COLONNE_HOLDER_SMONTATI = ['Alias_Holder', 'Data_Smontaggio', 'Quantita', 'Note']

# 🆕 V12.3: Colonne database bussole idraulico
COLONNE_BUSSOLE_IDRAULICO = ['Codice_Bussola', 'Diametro', 'Quantita', 'Data_Acquisizione', 'Note']

# Tipi di impiego frese
IMPIEGHI_FRESE = {
    'FF': 'Fresa Finitura',
    'FP': 'Fresa Prefinitura',
    'FR': 'Fresa Riprese',
    'FS': 'Fresa Sgrossatura'
}

# --- CONFIGURAZIONE E UTILITY GLOBALI ---
CONFIG_FILE = 'config.json'

# Cache in-memory con TTL 30s.
# carica_configurazione() viene chiamata ~53 volte per request (ogni endpoint).
# Il file config cambia rarissimamente — la cache elimina letture disk ridondanti.
_config_cache: dict = {"data": None, "ts": 0.0}
_CONFIG_TTL = 30  # secondi

def carica_configurazione():
    """Carica il percorso del database dal file di configurazione. Cache 30s."""
    import time as _time
    now = _time.monotonic()
    if _config_cache["data"] is not None and (now - _config_cache["ts"]) < _CONFIG_TTL:
        return _config_cache["data"]
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, 'r') as f:
                data = json.load(f)
            _config_cache["data"] = data
            _config_cache["ts"]   = now
            return data
        except Exception:
            return {"database_path": None}
    return {"database_path": None}

def salva_configurazione(config):
    """Salva la configurazione aggiornata e invalida la cache."""
    try:
        with open(CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=4)
        # Invalida la cache — il file è cambiato
        _config_cache["data"] = None
        _config_cache["ts"]   = 0.0
        return True
    except Exception:
        return False

def get_db_paths(db_principale):
    """
    Genera i percorsi dei database correlati basati sul DB principale.
    
    Args:
        db_principale: path del database principale (es. "Database_DMG160U.csv")
    
    Returns:
        dict con i percorsi di tutti i database (V12.3: aggiunto bussole_idraulico)
    """
    if not db_principale:
        return {
            'principale': None,
            'utensili_smontati': None,
            'holder_smontati': None,
            'bussole_idraulico': None  # 🆕 V12.3
        }
    
    base_dir = os.path.dirname(db_principale)
    base_name = os.path.basename(db_principale).replace('_utensili_in_macchina.csv', '').replace('.csv', '')
    
    return {
        'principale': db_principale,
        'utensili_smontati': os.path.join(base_dir, f"{base_name}_utensili_smontati.csv"),
        'holder_smontati': os.path.join(base_dir, f"{base_name}_holder_smontati.csv"),
        'bussole_idraulico': os.path.join(base_dir, f"{base_name}_bussole_idraulico.csv")  # 🆕 V12.3
    }

def auto_find_db_paths(config: dict = None) -> dict:
    """
    Trova automaticamente i percorsi DB nella stessa cartella di tools_toa_folder.

    Nomi riconosciuti (in ordine di priorità):
      1. database_path già in config (compatibilità)
      2. Database_DMG160U_*.csv  (nomi vecchi)
      3. DMGDesk_*.csv           (nomi nuovi standard)
    Se non esistono li crea vuoti con i nomi nuovi.
    """
    if config is None:
        config = carica_configurazione()

    # 1. database_path già configurato e valido
    db_path = (config.get("database_path") or "").strip()
    if db_path and os.path.exists(db_path):
        return get_db_paths(db_path)

    # 2. Trova cartella
    folder = (config.get("tools_toa_folder") or "").strip()
    if not folder:
        percorso_nc = (config.get("percorso_nc_base") or "").strip()
        if percorso_nc:
            from pathlib import Path as _P
            parts = _P(percorso_nc).parts
            if len(parts) >= 2:
                folder = str(_P(parts[0]) / parts[1])
    if not folder:
        return get_db_paths(None)

    # 3. Cerca prima i vecchi nomi, poi i nuovi
    def _find(candidates):
        for c in candidates:
            p = os.path.join(folder, c)
            if os.path.exists(p):
                return p
        return None

    principale = (
        _find(["Database_DMG160U_utensili_in_macchina.csv",
               "Database_DMG160U.csv",
               "DMGDesk_principale.csv"])
        or os.path.join(folder, "DMGDesk_principale.csv")
    )
    smontati = (
        _find(["Database_DMG160U_utensili_smontati.csv",
               "DMGDesk_smontati.csv"])
        or os.path.join(folder, "DMGDesk_smontati.csv")
    )
    holder = (
        _find(["Database_DMG160U_holder_smontati.csv",
               "DMGDesk_holder.csv"])
        or os.path.join(folder, "DMGDesk_holder.csv")
    )
    bussole = (
        _find(["Database_DMG160U_bussole_idraulico.csv",
               "DMGDesk_bussole.csv"])
        or os.path.join(folder, "DMGDesk_bussole.csv")
    )

    # Crea i file vuoti se non esistono
    _ensure_csv(principale, COLONNE_V2)
    _ensure_csv(smontati,   COLONNE_UTENSILI_SMONTATI)
    _ensure_csv(holder,     COLONNE_HOLDER_SMONTATI)
    _ensure_csv(bussole,    COLONNE_BUSSOLE_IDRAULICO)

    # Salva database_path in config
    try:
        config["database_path"] = principale
        salva_configurazione(config)
    except Exception:
        pass

    return {
        "principale":        principale,
        "utensili_smontati": smontati,
        "holder_smontati":   holder,
        "bussole_idraulico": bussole,
    }


def _ensure_csv(path: str, columns: list):
    """Crea un CSV vuoto con le colonne corrette se non esiste."""
    if not path or os.path.exists(path):
        return
    try:
        import pandas as _pd
        _pd.DataFrame(columns=columns).to_csv(path, sep="	", index=False)
    except Exception:
        pass


# --- LOGICA DATABASE PRINCIPALE ---

def carica_database(db_path):
    """
    Carica il database utensili da file CSV e garantisce la presenza delle colonne V2.
    """
    if not db_path:
        return pd.DataFrame(columns=COLONNE_V2), "Errore: Percorso database non specificato."
        
    try:
        df = pd.read_csv(db_path, sep='\t')
        
        if df.empty:
            return pd.DataFrame(columns=COLONNE_V2), "Attenzione: Il file DB è vuoto."

        # Garanzia colonne
        if 'Alias' not in df.columns:
            return pd.DataFrame(columns=COLONNE_V2), "Errore: Colonna 'Alias' mancante."
        df['Alias'] = df['Alias'].astype(str).str.strip().str.upper()

        if 'Posizione' in df.columns:
            df['Posizione'] = df['Posizione'].astype(str).str.replace(r'\.0$', '', regex=True).str.strip().replace('nan', '')
        else:
            df['Posizione'] = ""
            
        if 'Stato_Utensile' not in df.columns:
            df['Stato_Utensile'] = df.apply(
                lambda row: STATO_IN_MACCHINA if row['Posizione'] and row['Posizione'].isdigit() else STATO_DEFAULT_DB, 
                axis=1
            )
        else:
            df['Stato_Utensile'] = df['Stato_Utensile'].astype(str).str.upper().str.strip()
            df['Stato_Utensile'] = df['Stato_Utensile'].apply(
                lambda x: x if x in STATI_UTENSILE else STATO_DEFAULT_DB
            )
            
        df.loc[df['Stato_Utensile'] != STATO_IN_MACCHINA, 'Posizione'] = ""
        df = df[COLONNE_V2]
        
        return df, None

    except FileNotFoundError:
        return pd.DataFrame(columns=COLONNE_V2), "Errore: File database non trovato."
    except Exception as e:
        return pd.DataFrame(columns=COLONNE_V2), f"Errore lettura database: {e}"

def salva_database(df, db_path):
    """Salva il DataFrame nel file CSV usando il delimitatore TAB."""
    try:
        df = df[COLONNE_V2]
        df.to_csv(db_path, sep='\t', index=False)
        return True, None
    except Exception as e:
        return False, f"Errore salvataggio: {e}"

# --- LOGICA DATABASE UTENSILI SMONTATI ---

def carica_database_utensili_smontati(db_path):
    """Carica il database degli utensili smontati con ID univoco."""
    try:
        if not os.path.exists(db_path):
            # Crea database vuoto se non esiste
            df = pd.DataFrame(columns=COLONNE_UTENSILI_SMONTATI)
            df.to_csv(db_path, sep='\t', index=False)
            return df, None
            
        df = pd.read_csv(db_path, sep='\t')
        
        # Garantisce colonne corrette
        for col in COLONNE_UTENSILI_SMONTATI:
            if col not in df.columns:
                if col == 'ID':
                    # Genera ID se mancante
                    df[col] = range(1, len(df) + 1)
                else:
                    df[col] = ""
        
        # Assicura che ID sia numerico
        if 'ID' in df.columns:
            df['ID'] = pd.to_numeric(df['ID'], errors='coerce').fillna(0).astype(int)
            # Rigenera ID sequenziali se ci sono buchi
            if len(df) > 0 and (df['ID'] == 0).any():
                df['ID'] = range(1, len(df) + 1)
                
        df = df[COLONNE_UTENSILI_SMONTATI]
        return df, None
        
    except Exception as e:
        return pd.DataFrame(columns=COLONNE_UTENSILI_SMONTATI), f"Errore caricamento utensili smontati: {e}"

def salva_database_utensili_smontati(df, db_path):
    """Salva il database utensili smontati."""
    try:
        df = df[COLONNE_UTENSILI_SMONTATI]
        df.to_csv(db_path, sep='\t', index=False)
        return True, None
    except Exception as e:
        return False, f"Errore salvataggio utensili smontati: {e}"

# --- LOGICA DATABASE HOLDER SMONTATI ---

def carica_database_holder_smontati(db_path):
    """Carica il database degli holder smontati."""
    try:
        if not os.path.exists(db_path):
            # Crea database vuoto se non esiste
            df = pd.DataFrame(columns=COLONNE_HOLDER_SMONTATI)
            df.to_csv(db_path, sep='\t', index=False)
            return df, None
            
        df = pd.read_csv(db_path, sep='\t')
        
        # Garantisce colonne corrette
        for col in COLONNE_HOLDER_SMONTATI:
            if col not in df.columns:
                df[col] = "" if col != "Quantita" else 1
        
        # Converti Quantita a int
        if 'Quantita' in df.columns and not df.empty:
            df['Quantita'] = pd.to_numeric(df['Quantita'], errors='coerce').fillna(1).astype(int)
        
        # Strip spazi da Alias_Holder per evitare duplicati
        if 'Alias_Holder' in df.columns and not df.empty:
            df['Alias_Holder'] = df['Alias_Holder'].astype(str).str.strip()
                
        df = df[COLONNE_HOLDER_SMONTATI]
        return df, None
        
    except Exception as e:
        return pd.DataFrame(columns=COLONNE_HOLDER_SMONTATI), f"Errore caricamento holder smontati: {e}"

def salva_database_holder_smontati(df, db_path):
    """Salva il database holder smontati."""
    try:
        df = df[COLONNE_HOLDER_SMONTATI]
        df.to_csv(db_path, sep='\t', index=False)
        return True, None
    except Exception as e:
        return False, f"Errore salvataggio holder smontati: {e}"

# --- LOGICA SEPARAZIONE HOLDER E UTENSILE ---

def separa_holder_da_alias(alias_completo):
    """
    Separa l'holder dall'alias dell'utensile secondo il sistema di codifica Vetimec.
    
    Logica di separazione:
    - Riconosce holder standard: HSK63, SK40, BT40, ER32, etc.
    - Riconosce holder sistema Vetimec: A1-A6, B1-B9, C1-C4, D1-D4, E1-E8, F1-F7, 
      G1-G7, H1-H18, I1-I18, J1-J15, K1-K8, L1-L15, M1-M23
    - Pattern integrati: "...F35H4" → utensile="...F35", holder="H4"
    
    Codici holder Vetimec:
    A = Attacco_Filettato, B = Forte_Serraggio, C = Manicotto, D = Pinza,
    E = Idraulico, F = Idraulico_Tendo_Slim, G = Idraulico_Tendo_Slim_Lungo,
    H = Caletto_BILZ, I = Caletto, J = Caletto_MST_curvo, K = Weldon,
    L = CALETTO_KAISER, M = Idraulico_Tendo_ZERO
    
    Args:
        alias_completo: stringa completa dell'alias 
                       es. "FF10-R0.5-L50-FP150 HSK63" o "FS2R0.5L20F35H4"
    
    Returns:
        tuple (alias_utensile, alias_holder)
        Esempio: ("FF10-R0.5-L50-FP150", "HSK63")
                 ("FS2R0.5L20F35", "H4")
    """
    if not alias_completo or pd.isna(alias_completo):
        return "", ""
    
    alias = str(alias_completo).strip().upper()
    
    # Pattern comuni di holder (in ordine di priorità)
    holder_patterns = [
        # 1. Holder standard internazionali (con word boundary)
        r'\b(HSK\d+[A-Z]?)\b',      # HSK63, HSK100A
        r'\b(SK\d+)\b',              # SK40, SK50
        r'\b(BT\d+)\b',              # BT40, BT50
        r'\b(CAT\d+)\b',             # CAT40, CAT50
        r'\b(ER\d+)\b',              # ER32, ER40
        r'\b(DIN\d+)\b',             # DIN69871
        r'\b(ISO\d+)\b',             # ISO40, ISO50
        r'\b(MAS\d+)\b',             # MAS403
        
        # 2. Sistema Vetimec - Holder alfanumerici (A-M + numero)
        # Pattern integrato (attaccato all'utensile, es: ...F35H4)
        r'([A-M]\d{1,2})$',          # A1-M23 alla fine senza spazio
        
        # Pattern con word boundary (con spazio, es: "...F35 H4")
        r'\b([A-M]\d{1,2})\b',       # A1-M23 con spazio
    ]
    
    holder_trovato = None
    posizione_holder = -1
    match_obj = None
    
    # Cerca pattern holder
    for pattern in holder_patterns:
        match = re.search(pattern, alias)
        if match:
            holder_trovato = match.group(1)
            posizione_holder = match.start()
            match_obj = match
            break
    
    if holder_trovato:
        # Rimuove l'holder dall'alias utensile
        alias_utensile = alias[:posizione_holder].strip()
        
        # Se l'holder era attaccato (es: F35H4), rimuovi solo la parte H4
        if not alias_utensile or (match_obj and match_obj.start() > 0 and alias[match_obj.start()-1] not in [' ', '-', '_']):
            # Holder era integrato senza separatore
            alias_utensile = alias[:match_obj.start()]
        
        return alias_utensile, holder_trovato
    else:
        # Se non trova holder con pattern, assume che l'ultima parola potrebbe essere holder
        parti = alias.split()
        if len(parti) > 1:
            # Ultima parola potrebbe essere holder se sembra un codice
            ultima_parola = parti[-1]
            if len(ultima_parola) <= 10 and not any(char in ultima_parola for char in ['.', ',']):
                alias_utensile = ' '.join(parti[:-1])
                return alias_utensile, ultima_parola
        
        # Altrimenti ritorna tutto come utensile
        return alias, ""

# --- OPERAZIONI SMONTAGGIO ---

def smonta_utensile(df_principale, db_paths, posizione_o_alias, note=""):
    """
    Smonta un utensile dalla macchina e lo divide in utensile e holder.
    
    Args:
        df_principale: DataFrame database principale
        db_paths: dict con percorsi dei database
        posizione_o_alias: posizione numerica o alias dell'utensile
        note: note opzionali sullo smontaggio
    
    Returns:
        tuple (success, message, df_principale_updated, df_utensili_updated, df_holder_updated)
    """
    # Trova l'utensile
    if str(posizione_o_alias).isdigit():
        utensile = df_principale[df_principale['Posizione'] == str(posizione_o_alias)]
    else:
        utensile = df_principale[df_principale['Alias'].str.upper() == str(posizione_o_alias).upper()]
    
    if utensile.empty:
        return False, f"Utensile non trovato: {posizione_o_alias}", df_principale, None, None
    
    alias_completo = utensile.iloc[0]['Alias']
    posizione = utensile.iloc[0]['Posizione']
    
    # Separa utensile e holder
    alias_utensile, alias_holder = separa_holder_da_alias(alias_completo)
    
    if not alias_utensile:
        return False, f"Impossibile separare holder da: {alias_completo}", df_principale, None, None
    
    data_smontaggio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    provenienza = f"Pos. {posizione}" if posizione else "Scaffale"
    
    # Carica database smontati
    df_utensili, err1 = carica_database_utensili_smontati(db_paths['utensili_smontati'])
    if err1:
        return False, err1, df_principale, None, None
    
    df_holder, err2 = carica_database_holder_smontati(db_paths['holder_smontati'])
    if err2:
        return False, err2, df_principale, None, None
    
    # Aggiungi utensile al database smontati
    nuova_riga_utensile = pd.DataFrame([{
        'Alias_Utensile': alias_utensile,
        'Data_Smontaggio': data_smontaggio,
        'Provenienza': provenienza,
        'Note': note
    }])
    df_utensili = pd.concat([df_utensili, nuova_riga_utensile], ignore_index=True)
    
    # Aggiungi holder al database smontati (o incrementa quantità)
    if alias_holder:
        holder_esistente = df_holder[df_holder['Alias_Holder'] == alias_holder]
        if not holder_esistente.empty:
            # Incrementa quantità
            idx = holder_esistente.index[0]
            df_holder.at[idx, 'Quantita'] = int(df_holder.at[idx, 'Quantita']) + 1
            df_holder.at[idx, 'Data_Smontaggio'] = data_smontaggio
        else:
            # Nuovo holder
            nuova_riga_holder = pd.DataFrame([{
                'Alias_Holder': alias_holder,
                'Data_Smontaggio': data_smontaggio,
                'Quantita': 1,
                'Note': ""
            }])
            df_holder = pd.concat([df_holder, nuova_riga_holder], ignore_index=True)
    
    # Rimuovi utensile dal database principale
    df_principale = df_principale[df_principale['Alias'] != alias_completo].reset_index(drop=True)
    
    # Salva tutti i database
    success1, err1 = salva_database(df_principale, db_paths['principale'])
    success2, err2 = salva_database_utensili_smontati(df_utensili, db_paths['utensili_smontati'])
    success3, err3 = salva_database_holder_smontati(df_holder, db_paths['holder_smontati'])
    
    if not all([success1, success2, success3]):
        errors = [e for e in [err1, err2, err3] if e]
        return False, f"Errori salvataggio: {'; '.join(errors)}", df_principale, df_utensili, df_holder
    
    msg = f"Utensile smontato con successo!\n"
    msg += f"Utensile: {alias_utensile}\n"
    if alias_holder:
        msg += f"Holder: {alias_holder}"
    
    return True, msg, df_principale, df_utensili, df_holder

# --- CAMBIO IMPIEGO FRESE ---

def cambia_impiego_fresa(df_principale, db_path, alias_fresa, nuovo_impiego):
    """
    Cambia l'impiego di una fresa FF in FP, FR o FS.
    
    Args:
        df_principale: DataFrame database principale
        db_path: percorso database principale
        alias_fresa: alias della fresa da modificare
        nuovo_impiego: nuovo codice impiego ('FP', 'FR', 'FS')
    
    Returns:
        tuple (success, message, df_updated)
    """
    if nuovo_impiego not in ['FP', 'FR', 'FS']:
        return False, f"Impiego non valido: {nuovo_impiego}. Usare: FP, FR, FS", df_principale
    
    # Trova la fresa
    fresa = df_principale[df_principale['Alias'].str.upper() == alias_fresa.upper()]
    
    if fresa.empty:
        return False, f"Fresa non trovata: {alias_fresa}", df_principale
    
    alias_originale = fresa.iloc[0]['Alias']
    
    # Verifica che sia una fresa FF
    if not alias_originale.upper().startswith('FF'):
        return False, f"L'utensile {alias_originale} non è una fresa di finitura (FF)", df_principale
    
    # Sostituisci FF con il nuovo impiego
    nuovo_alias = nuovo_impiego + alias_originale[2:]
    
    # Aggiorna nel dataframe
    idx = fresa.index[0]
    df_principale.at[idx, 'Alias'] = nuovo_alias
    
    # Salva
    success, error = salva_database(df_principale, db_path)
    
    if not success:
        return False, f"Errore salvataggio: {error}", df_principale
    
    msg = f"Impiego cambiato con successo!\n"
    msg += f"Da: {alias_originale} ({IMPIEGHI_FRESE.get('FF', 'FF')})\n"
    msg += f"A:  {nuovo_alias} ({IMPIEGHI_FRESE.get(nuovo_impiego, nuovo_impiego)})"
    
    return True, msg, df_principale

# --- RICERCA UTENSILI ESTESA ---

def cerca_utensile_ovunque(alias_ricerca, db_paths):
    """
    Cerca un utensile in tutti i database disponibili.
    
    Args:
        alias_ricerca: alias dell'utensile da cercare
        db_paths: dict con percorsi dei database
    
    Returns:
        dict con informazioni sulla posizione dell'utensile
        {
            'trovato': bool,
            'database': 'principale'/'utensili_smontati'/'holder_smontati'/None,
            'dettagli': dict con info specifiche
        }
    """
    risultato = {
        'trovato': False,
        'database': None,
        'dettagli': {}
    }
    
    alias_upper = alias_ricerca.upper().strip()
    
    # Cerca nel database principale
    df_principale, _ = carica_database(db_paths['principale'])
    utensile_principale = df_principale[df_principale['Alias'].str.upper() == alias_upper]
    
    if not utensile_principale.empty:
        risultato['trovato'] = True
        risultato['database'] = 'principale'
        risultato['dettagli'] = {
            'posizione': utensile_principale.iloc[0]['Posizione'],
            'stato': utensile_principale.iloc[0]['Stato_Utensile'],
            'alias': utensile_principale.iloc[0]['Alias']
        }
        return risultato
    
    # Cerca negli utensili smontati
    df_utensili, _ = carica_database_utensili_smontati(db_paths['utensili_smontati'])
    utensile_smontato = df_utensili[df_utensili['Alias_Utensile'].str.upper() == alias_upper]
    
    if not utensile_smontato.empty:
        risultato['trovato'] = True
        risultato['database'] = 'utensili_smontati'
        risultato['dettagli'] = {
            'alias': utensile_smontato.iloc[0]['Alias_Utensile'],
            'data_smontaggio': utensile_smontato.iloc[0]['Data_Smontaggio'],
            'provenienza': utensile_smontato.iloc[0]['Provenienza'],
            'note': utensile_smontato.iloc[0]['Note']
        }
        return risultato
    
    # Cerca anche con holder negli utensili smontati
    for _, row in df_utensili.iterrows():
        alias_utensile = str(row['Alias_Utensile']).upper()
        if alias_upper in alias_utensile or alias_utensile in alias_upper:
            risultato['trovato'] = True
            risultato['database'] = 'utensili_smontati'
            risultato['dettagli'] = {
                'alias': row['Alias_Utensile'],
                'data_smontaggio': row['Data_Smontaggio'],
                'provenienza': row['Provenienza'],
                'note': row['Note'],
                'match_parziale': True
            }
            return risultato
    
    return risultato

# NUOVE FUNZIONI DA AGGIUNGERE A db_handler_v12.py
# Copiare queste funzioni alla fine del file db_handler_v12.py prima di "def trova_prima_posizione_libera"

# --- GESTIONE UTENSILI SMONTATI ---

def aggiungi_utensile_smontato(df_utensili, db_path, alias_utensile, provenienza="Manuale", note=""):
    """
    Aggiunge un utensile al database smontati.
    Permette duplicati (stesso alias più volte).
    
    Returns:
        tuple (success, message, df_updated)
    """
    try:
        # Genera ID univoco
        if len(df_utensili) > 0:
            nuovo_id = df_utensili['ID'].max() + 1
        else:
            nuovo_id = 1
        
        data_smontaggio = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        nuova_riga = pd.DataFrame([{
            'ID': nuovo_id,
            'Alias_Utensile': alias_utensile.strip().upper(),
            'Data_Smontaggio': data_smontaggio,
            'Provenienza': provenienza,
            'Note': note
        }])
        
        df_updated = pd.concat([df_utensili, nuova_riga], ignore_index=True)
        
        success, error = salva_database_utensili_smontati(df_updated, db_path)
        if not success:
            return False, error, df_utensili
        
        return True, f"Utensile '{alias_utensile}' aggiunto (ID: {nuovo_id})", df_updated
        
    except Exception as e:
        return False, f"Errore aggiunta utensile: {e}", df_utensili


def modifica_utensile_smontato(df_utensili, db_path, id_utensile, nuovo_alias=None, nuova_provenienza=None, nuove_note=None):
    """
    Modifica un utensile smontato per ID.
    
    Returns:
        tuple (success, message, df_updated)
    """
    try:
        if id_utensile not in df_utensili['ID'].values:
            return False, f"ID {id_utensile} non trovato", df_utensili
        
        idx = df_utensili[df_utensili['ID'] == id_utensile].index[0]
        
        if nuovo_alias:
            df_utensili.at[idx, 'Alias_Utensile'] = nuovo_alias.strip().upper()
        if nuova_provenienza:
            df_utensili.at[idx, 'Provenienza'] = nuova_provenienza
        if nuove_note is not None:  # Permette di svuotare le note
            df_utensili.at[idx, 'Note'] = nuove_note
        
        success, error = salva_database_utensili_smontati(df_utensili, db_path)
        if not success:
            return False, error, df_utensili
        
        return True, f"Utensile ID {id_utensile} modificato", df_utensili
        
    except Exception as e:
        return False, f"Errore modifica utensile: {e}", df_utensili


def elimina_utensile_smontato(df_utensili, db_path, id_utensile):
    """
    Elimina un utensile smontato per ID.
    
    Returns:
        tuple (success, message, df_updated)
    """
    try:
        if id_utensile not in df_utensili['ID'].values:
            return False, f"ID {id_utensile} non trovato", df_utensili
        
        df_updated = df_utensili[df_utensili['ID'] != id_utensile].reset_index(drop=True)
        
        success, error = salva_database_utensili_smontati(df_updated, db_path)
        if not success:
            return False, error, df_utensili
        
        return True, f"Utensile ID {id_utensile} eliminato", df_updated
        
    except Exception as e:
        return False, f"Errore eliminazione utensile: {e}", df_utensili


def cambia_impiego_utensile_smontato(df_utensili, db_path, id_utensile, nuovo_impiego):
    """
    Cambia l'impiego di una fresa FF nei DB smontati.
    
    Returns:
        tuple (success, message, df_updated)
    """
    if nuovo_impiego not in ['FP', 'FR', 'FS']:
        return False, f"Impiego non valido: {nuovo_impiego}", df_utensili
    
    try:
        if id_utensile not in df_utensili['ID'].values:
            return False, f"ID {id_utensile} non trovato", df_utensili
        
        idx = df_utensili[df_utensili['ID'] == id_utensile].index[0]
        alias_originale = df_utensili.at[idx, 'Alias_Utensile']
        
        if not alias_originale.upper().startswith('FF'):
            return False, f"L'utensile non è una fresa FF", df_utensili
        
        nuovo_alias = nuovo_impiego + alias_originale[2:]
        df_utensili.at[idx, 'Alias_Utensile'] = nuovo_alias
        
        success, error = salva_database_utensili_smontati(df_utensili, db_path)
        if not success:
            return False, error, df_utensili
        
        msg = f"Impiego cambiato!\n"
        msg += f"Da: {alias_originale} (Finitura)\n"
        msg += f"A:  {nuovo_alias} ({IMPIEGHI_FRESE.get(nuovo_impiego, nuovo_impiego)})"
        
        return True, msg, df_utensili
        
    except Exception as e:
        return False, f"Errore cambio impiego: {e}", df_utensili


# --- GESTIONE HOLDER SMONTATI ---

def aggiungi_holder_smontato(df_holder, db_path, alias_holder, quantita=1, note=""):
    """
    Aggiunge holder al database smontati.
    Se già esiste, incrementa la quantità.
    
    Returns:
        tuple (success, message, df_updated)
    """
    try:
        alias_holder = alias_holder.strip().upper()
        data_aggiornamento = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        holder_esistente = df_holder[df_holder['Alias_Holder'] == alias_holder]
        
        if not holder_esistente.empty:
            # Incrementa quantità
            idx = holder_esistente.index[0]
            qty_attuale = int(df_holder.at[idx, 'Quantita'])
            df_holder.at[idx, 'Quantita'] = qty_attuale + quantita
            df_holder.at[idx, 'Data_Smontaggio'] = data_aggiornamento
            if note:
                df_holder.at[idx, 'Note'] = note
            
            success, error = salva_database_holder_smontati(df_holder, db_path)
            if not success:
                return False, error, df_holder
            
            return True, f"Holder '{alias_holder}' aggiornato (qty: {qty_attuale} → {qty_attuale + quantita})", df_holder
        else:
            # Nuovo holder
            nuova_riga = pd.DataFrame([{
                'Alias_Holder': alias_holder,
                'Data_Smontaggio': data_aggiornamento,
                'Quantita': quantita,
                'Note': note
            }])
            
            df_updated = pd.concat([df_holder, nuova_riga], ignore_index=True)
            
            success, error = salva_database_holder_smontati(df_updated, db_path)
            if not success:
                return False, error, df_holder
            
            return True, f"Holder '{alias_holder}' aggiunto (qty: {quantita})", df_updated
        
    except Exception as e:
        return False, f"Errore aggiunta holder: {e}", df_holder


def modifica_holder_smontato(df_holder, db_path, alias_holder, nuova_quantita=None, nuove_note=None):
    """
    Modifica un holder smontato.
    
    Returns:
        tuple (success, message, df_updated)
    """
    try:
        holder = df_holder[df_holder['Alias_Holder'] == alias_holder.upper()]
        if holder.empty:
            return False, f"Holder '{alias_holder}' non trovato", df_holder
        
        idx = holder.index[0]
        
        if nuova_quantita is not None:
            df_holder.at[idx, 'Quantita'] = int(nuova_quantita)
        if nuove_note is not None:
            df_holder.at[idx, 'Note'] = nuove_note
        
        df_holder.at[idx, 'Data_Smontaggio'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        success, error = salva_database_holder_smontati(df_holder, db_path)
        if not success:
            return False, error, df_holder
        
        return True, f"Holder '{alias_holder}' modificato", df_holder
        
    except Exception as e:
        return False, f"Errore modifica holder: {e}", df_holder


def elimina_holder_smontato(df_holder, db_path, alias_holder):
    """
    Elimina un holder smontato completamente.
    
    Returns:
        tuple (success, message, df_updated)
    """
    try:
        df_updated = df_holder[df_holder['Alias_Holder'] != alias_holder.upper()].reset_index(drop=True)
        
        success, error = salva_database_holder_smontati(df_updated, db_path)
        if not success:
            return False, error, df_holder
        
        return True, f"Holder '{alias_holder}' eliminato", df_updated
        
    except Exception as e:
        return False, f"Errore eliminazione holder: {e}", df_holder


def decrementa_holder_smontato(df_holder, db_path, alias_holder, quantita=1):
    """
    Decrementa la quantità di un holder (usato nel montaggio).
    Se arriva a 0, rimuove la riga.
    
    Returns:
        tuple (success, message, df_updated)
    """
    try:
        holder = df_holder[df_holder['Alias_Holder'] == alias_holder.upper()]
        if holder.empty:
            return False, f"Holder '{alias_holder}' non disponibile", df_holder
        
        idx = holder.index[0]
        qty_attuale = int(df_holder.at[idx, 'Quantita'])
        
        if qty_attuale < quantita:
            return False, f"Quantità insufficiente (disponibili: {qty_attuale})", df_holder
        
        nuova_qty = qty_attuale - quantita
        
        if nuova_qty <= 0:
            # Rimuovi holder se quantità è 0
            df_updated = df_holder[df_holder['Alias_Holder'] != alias_holder.upper()].reset_index(drop=True)
        else:
            df_holder.at[idx, 'Quantita'] = nuova_qty
            df_holder.at[idx, 'Data_Smontaggio'] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            df_updated = df_holder
        
        success, error = salva_database_holder_smontati(df_updated, db_path)
        if not success:
            return False, error, df_holder
        
        return True, f"Holder '{alias_holder}' decrementato (qty: {qty_attuale} → {nuova_qty})", df_updated
        
    except Exception as e:
        return False, f"Errore decremento holder: {e}", df_holder


# --- OPERAZIONE MONTAGGIO (INVERSO DELLO SMONTAGGIO) ---

def monta_utensile(df_principale, df_utensili, df_holder, db_paths, id_utensile, alias_holder, posizione_destinazione):
    """
    Monta un utensile combinandolo con un holder e mettendolo in macchina.
    
    Operazioni:
    1. Prende utensile da DB smontati (per ID)
    2. Prende holder da DB smontati (decrementa qty)
    3. Combina: alias_completo = alias_utensile + alias_holder
    4. Aggiunge in DB principale con posizione e stato IN_MACCHINA
    5. Rimuove utensile da DB smontati
    
    Args:
        df_principale: DataFrame database principale
        df_utensili: DataFrame utensili smontati
        df_holder: DataFrame holder smontati
        db_paths: dict percorsi database
        id_utensile: ID utensile da montare
        alias_holder: alias holder da usare
        posizione_destinazione: posizione in macchina (1-99) o "" per scaffale
    
    Returns:
        tuple (success, message, df_principale_updated, df_utensili_updated, df_holder_updated)
    """
    try:
        # 1. Verifica utensile esiste
        utensile = df_utensili[df_utensili['ID'] == id_utensile]
        if utensile.empty:
            return False, f"Utensile ID {id_utensile} non trovato", df_principale, df_utensili, df_holder
        
        alias_utensile = utensile.iloc[0]['Alias_Utensile']
        
        # 2. Verifica holder disponibile
        holder = df_holder[df_holder['Alias_Holder'] == alias_holder.upper()]
        if holder.empty:
            return False, f"Holder '{alias_holder}' non disponibile", df_principale, df_utensili, df_holder
        
        qty_holder = int(holder.iloc[0]['Quantita'])
        if qty_holder < 1:
            return False, f"Holder '{alias_holder}' quantità insufficiente", df_principale, df_utensili, df_holder
        
        # 3. Combina alias
        alias_completo = f"{alias_utensile}{alias_holder}"
        
        # 4. Determina stato
        if posizione_destinazione and str(posizione_destinazione).strip().isdigit():
            posizione = str(posizione_destinazione).strip()
            stato = STATO_IN_MACCHINA
        else:
            posizione = ""
            stato = STATO_SCAFFALE
        
        # 5. Aggiungi a DB principale
        nuova_riga = pd.DataFrame([{
            'Posizione': posizione,
            'Alias': alias_completo,
            'Stato_Utensile': stato
        }])
        df_principale_updated = pd.concat([df_principale, nuova_riga], ignore_index=True)
        
        # 6. Rimuovi utensile da DB smontati
        df_utensili_updated = df_utensili[df_utensili['ID'] != id_utensile].reset_index(drop=True)
        
        # 7. Decrementa holder
        success_holder, msg_holder, df_holder_updated = decrementa_holder_smontato(
            df_holder, db_paths['holder_smontati'], alias_holder, 1
        )
        if not success_holder:
            return False, msg_holder, df_principale, df_utensili, df_holder
        
        # 8. Salva tutti i database
        success1, err1 = salva_database(df_principale_updated, db_paths['principale'])
        success2, err2 = salva_database_utensili_smontati(df_utensili_updated, db_paths['utensili_smontati'])
        # holder già salvato da decrementa_holder_smontato
        
        if not all([success1, success2]):
            errors = [e for e in [err1, err2] if e]
            return False, f"Errori salvataggio: {'; '.join(errors)}", df_principale, df_utensili, df_holder
        
        msg = f"Montaggio completato!\n\n"
        msg += f"Utensile: {alias_utensile} (ID: {id_utensile})\n"
        msg += f"Holder: {alias_holder}\n"
        msg += f"Alias completo: {alias_completo}\n"
        if posizione:
            msg += f"Posizione: {posizione} ({stato})"
        else:
            msg += f"Stato: {stato}"
        
        return True, msg, df_principale_updated, df_utensili_updated, df_holder_updated
        
    except Exception as e:
        return False, f"Errore montaggio: {e}", df_principale, df_utensili, df_holder

# 🆕 V12.3: MONTAGGIO CON SISTEMA BUSSOLE
def monta_utensile_con_bussola(df_principale, df_utensili, df_holder, df_bussole, db_paths, 
                                id_utensile, holder_base, codice_bussola, posizione_destinazione):
    """
    Monta utensile con holder idraulico E + bussola separata (V12.3).
    
    Operazioni:
    1. Prende utensile da DB smontati
    2. Decrementa holder BASE (es: "E")
    3. Decrementa bussola (es: "E2")
    4. Combina: alias_completo = utensile + codice_bussola (es: "CENTRINO-8-F50E2")
    5. Aggiunge in DB principale
    
    Args:
        df_principale: DataFrame database principale
        df_utensili: DataFrame utensili smontati
        df_holder: DataFrame holder smontati
        df_bussole: DataFrame bussole idraulico
        db_paths: dict percorsi database
        id_utensile: ID utensile da montare
        holder_base: holder base (es: "E" per idraulico)
        codice_bussola: codice bussola (es: "E2" per D8)
        posizione_destinazione: posizione macchina (1-99) o "" per scaffale
    
    Returns:
        tuple (success, message, df_principale, df_utensili, df_holder, df_bussole)
    """
    try:
        # 1. Verifica utensile
        utensile = df_utensili[df_utensili['ID'] == id_utensile]
        if utensile.empty:
            return False, f"Utensile ID {id_utensile} non trovato", df_principale, df_utensili, df_holder, df_bussole
        
        alias_utensile = utensile.iloc[0]['Alias_Utensile']
        
        # 2. Verifica holder base disponibile
        holder = df_holder[df_holder['Alias_Holder'] == holder_base.upper()]
        if holder.empty:
            return False, f"Holder base '{holder_base}' non disponibile", df_principale, df_utensili, df_holder, df_bussole
        
        qty_holder = int(holder.iloc[0]['Quantita'])
        if qty_holder < 1:
            return False, f"Holder '{holder_base}' quantità insufficiente", df_principale, df_utensili, df_holder, df_bussole
        
        # 3. Verifica bussola disponibile
        bussola = df_bussole[df_bussole['Codice_Bussola'] == codice_bussola]
        if bussola.empty:
            return False, f"Bussola '{codice_bussola}' non disponibile", df_principale, df_utensili, df_holder, df_bussole
        
        qty_bussola = int(bussola.iloc[0]['Quantita'])
        if qty_bussola < 1:
            return False, f"Bussola '{codice_bussola}' quantità insufficiente", df_principale, df_utensili, df_holder, df_bussole
        
        # 4. Combina alias (utensile + codice bussola completo)
        alias_completo = f"{alias_utensile}{codice_bussola}"
        
        # 5. Determina stato
        if posizione_destinazione and str(posizione_destinazione).strip().isdigit():
            posizione = str(posizione_destinazione).strip()
            stato = STATO_IN_MACCHINA
        else:
            posizione = ""
            stato = STATO_SCAFFALE
        
        # 6. Aggiungi a DB principale
        nuova_riga = pd.DataFrame([{
            'Posizione': posizione,
            'Alias': alias_completo,
            'Stato_Utensile': stato
        }])
        df_principale_updated = pd.concat([df_principale, nuova_riga], ignore_index=True)
        
        # 7. Rimuovi utensile da DB smontati
        df_utensili_updated = df_utensili[df_utensili['ID'] != id_utensile].reset_index(drop=True)
        
        # 8. Decrementa holder base
        success_h, msg_h, df_holder_updated = decrementa_holder_smontato(
            df_holder, db_paths['holder_smontati'], holder_base, 1
        )
        if not success_h:
            return False, msg_h, df_principale, df_utensili, df_holder, df_bussole
        
        # 9. Decrementa bussola
        success_b, msg_b, df_bussole_updated = decrementa_bussola_idraulico(
            df_bussole, db_paths['bussole_idraulico'], codice_bussola, 1
        )
        if not success_b:
            return False, msg_b, df_principale, df_utensili, df_holder_updated, df_bussole
        
        # 10. Salva database
        success1, err1 = salva_database(df_principale_updated, db_paths['principale'])
        success2, err2 = salva_database_utensili_smontati(df_utensili_updated, db_paths['utensili_smontati'])
        # holder e bussole già salvati dalle funzioni decrementa
        
        if not all([success1, success2]):
            errors = [e for e in [err1, err2] if e]
            return False, f"Errori salvataggio: {'; '.join(errors)}", df_principale, df_utensili, df_holder_updated, df_bussole_updated
        
        msg = f"✅ Montaggio completato!\n\n"
        msg += f"📦 Utensile: {alias_utensile} (ID: {id_utensile})\n"
        msg += f"🔧 Holder: {holder_base} (D20)\n"
        msg += f"🔩 Bussola: {codice_bussola} ({bussola.iloc[0]['Diametro']})\n"
        msg += f"🔗 Alias finale: {alias_completo}\n"
        if posizione:
            msg += f"📍 Posizione: {posizione} ({stato})"
        else:
            msg += f"📍 Stato: {stato}"
        
        return True, msg, df_principale_updated, df_utensili_updated, df_holder_updated, df_bussole_updated
        
    except Exception as e:
        return False, f"Errore montaggio con bussola: {e}", df_principale, df_utensili, df_holder, df_bussole

# --- UTILITY ---

def trova_prima_posizione_libera(df):
    """Trova la prima posizione numerica libera nell'intervallo 1-99."""
    df_posizioni = df.copy()
    df_posizioni = df_posizioni[df_posizioni['Stato_Utensile'] == STATO_IN_MACCHINA]
    posizioni_occupate = df_posizioni['Posizione'].dropna().astype(str).str.extract(r'(\d+)')[0].astype(float).astype('Int64').tolist()
    
    for i in range(1, 100):
        if i not in posizioni_occupate:
            return i
            
    return 100

# ═══════════════════════════════════════════════════════════════════════
# 🆕 V12.3: GESTIONE DATABASE BUSSOLE IDRAULICO
# ═══════════════════════════════════════════════════════════════════════

def carica_database_bussole_idraulico(db_path):
    """
    Carica il database delle bussole idraulico E.
    
    Returns:
        tuple: (DataFrame, messaggio_errore)
    """
    if not db_path or not os.path.exists(db_path):
        # Crea DataFrame vuoto con struttura corretta
        df = pd.DataFrame(columns=COLONNE_BUSSOLE_IDRAULICO)
        return df, None
    
    try:
        # 🆕 Usa TAB separator come altri database
        df = pd.read_csv(db_path, sep='\t', dtype=str)
        
        # Assicura colonne corrette
        for col in COLONNE_BUSSOLE_IDRAULICO:
            if col not in df.columns:
                df[col] = ''
        
        # Converti Quantita a int
        if 'Quantita' in df.columns and not df.empty:
            df['Quantita'] = pd.to_numeric(df['Quantita'], errors='coerce').fillna(0).astype(int)
        
        # Strip spazi da Codice_Bussola per evitare duplicati
        if 'Codice_Bussola' in df.columns and not df.empty:
            df['Codice_Bussola'] = df['Codice_Bussola'].astype(str).str.strip()
        
        # Riordina colonne
        df = df[COLONNE_BUSSOLE_IDRAULICO]
        
        return df, None
        
    except Exception as e:
        df = pd.DataFrame(columns=COLONNE_BUSSOLE_IDRAULICO)
        return df, f"Errore caricamento bussole: {e}"

def salva_database_bussole_idraulico(df, db_path):
    """
    Salva il database delle bussole idraulico.
    
    Returns:
        tuple: (success, messaggio_errore)
    """
    if not db_path:
        return False, "Percorso database bussole non specificato"
    
    try:
        # 🆕 Usa TAB separator come altri database
        df.to_csv(db_path, sep='\t', index=False)
        return True, None
    except Exception as e:
        return False, f"Errore salvataggio bussole: {e}"

def aggiungi_bussola_idraulico(df_bussole, db_path, codice, diametro, quantita, note=""):
    """
    Aggiunge o incrementa una bussola nel database.
    
    Returns:
        tuple: (success, messaggio, df_aggiornato)
    """
    try:
        # Verifica se bussola esiste già
        esistente = df_bussole[df_bussole['Codice_Bussola'] == codice]
        
        if not esistente.empty:
            # Incrementa quantità
            idx = esistente.index[0]
            qty_old = int(df_bussole.at[idx, 'Quantita'])
            df_bussole.at[idx, 'Quantita'] = str(qty_old + quantita)
            msg = f"Bussola {codice} ({diametro}): qty {qty_old} → {qty_old + quantita}"
        else:
            # Aggiungi nuova bussola
            nuova_riga = pd.DataFrame([{
                'Codice_Bussola': codice,
                'Diametro': diametro,
                'Quantita': str(quantita),
                'Data_Acquisizione': datetime.now().strftime('%Y-%m-%d'),
                'Note': note
            }])
            df_bussole = pd.concat([df_bussole, nuova_riga], ignore_index=True)
            msg = f"Bussola {codice} ({diametro}) aggiunta: qty {quantita}"
        
        # Salva
        success, err = salva_database_bussole_idraulico(df_bussole, db_path)
        if not success:
            return False, err, df_bussole
        
        return True, msg, df_bussole
        
    except Exception as e:
        return False, f"Errore aggiunta bussola: {e}", df_bussole

def decrementa_bussola_idraulico(df_bussole, db_path, codice, quantita_da_togliere):
    """
    Decrementa la quantità di una bussola.
    
    Returns:
        tuple: (success, messaggio, df_aggiornato)
    """
    try:
        # Trova bussola
        bussola = df_bussole[df_bussole['Codice_Bussola'] == codice]
        
        if bussola.empty:
            return False, f"Bussola {codice} non trovata!", df_bussole
        
        idx = bussola.index[0]
        qty_attuale = int(df_bussole.at[idx, 'Quantita'])
        
        if qty_attuale < quantita_da_togliere:
            return False, f"Bussola {codice}: qty insufficiente ({qty_attuale} disponibili, richiesti {quantita_da_togliere})", df_bussole
        
        nuova_qty = qty_attuale - quantita_da_togliere
        
        if nuova_qty == 0:
            # Rimuovi completamente
            df_bussole = df_bussole[df_bussole['Codice_Bussola'] != codice].reset_index(drop=True)
            msg = f"Bussola {codice}: qty {qty_attuale} → 0 (rimossa)"
        else:
            # Aggiorna quantità
            df_bussole.at[idx, 'Quantita'] = str(nuova_qty)
            msg = f"Bussola {codice}: qty {qty_attuale} → {nuova_qty}"
        
        # Salva
        success, err = salva_database_bussole_idraulico(df_bussole, db_path)
        if not success:
            return False, err, df_bussole
        
        return True, msg, df_bussole
        
    except Exception as e:
        return False, f"Errore decremento bussola: {e}", df_bussole

def elimina_bussola_idraulico(df_bussole, db_path, codice):
    """
    Elimina completamente una bussola dal database.
    
    Returns:
        tuple: (success, messaggio, df_aggiornato)
    """
    try:
        if codice not in df_bussole['Codice_Bussola'].values:
            return False, f"Bussola {codice} non trovata!", df_bussole
        
        df_bussole = df_bussole[df_bussole['Codice_Bussola'] != codice].reset_index(drop=True)
        
        success, err = salva_database_bussole_idraulico(df_bussole, db_path)
        if not success:
            return False, err, df_bussole
        
        return True, f"Bussola {codice} eliminata", df_bussole
        
    except Exception as e:
        return False, f"Errore eliminazione bussola: {e}", df_bussole
def decodifica_holder(alias_holder):
    """
    Decodifica alias holder Vetimec.
    
    Args:
        alias_holder: Codice holder (es: E, H4, K3)
    
    Returns:
        tuple: (tipo_completo, diametro, codice_base)
    """
    import re
    from config.constants import HOLDER_TYPES, HOLDER_DIAMETER_MAP
    
    # Pattern: lettera + numero opzionale
    match = re.match(r'^([A-M])(\d*)$', alias_holder.upper())
    
    if not match:
        return ("Sconosciuto", "", alias_holder)
    
    lettera = match.group(1)
    numero_str = match.group(2)
    numero = int(numero_str) if numero_str else None
    
    # Tipo
    tipo = HOLDER_TYPES.get(lettera, "Sconosciuto")
    
    # Diametro
    diametro = ""
    if numero is not None:
        diametro = HOLDER_DIAMETER_MAP.get((lettera, numero), "")
    
    return (tipo, diametro, lettera)


def smonta_utensile(alias_completo):
    """
    Smonta utensile in componenti base + holder + bussola.
    
    VERSIONE V14 - CORRETTA per gestire:
    - "X" di SPECIALE dopo FP (es: F100X)
    - Bussole idraulico (D12, D16, etc.)
    - Tutti i tipi di holder [A-M]
    
    LOGICA:
    1. Holder è sempre alla fine: [A-M]\\d+$
    2. Bussola (se presente) è prima dell'holder: D\\d+[A-M]\\d+$
    3. Utensile base:
       - SENZA bussola: tutto MENO holder (la X rimane)
       - CON bussola: tutto MENO bussola ma CON holder
    
    ESEMPI:
    - F6F100F6        → utensile: F6F100,   holder: F6,  bussola: None
    - F6F100XF6       → utensile: F6F100X,  holder: F6,  bussola: None ⭐
    - FS6R2L50F100XF6 → utensile: FS6R2L50F100X, holder: F6, bussola: None ⭐
    - F6F100D12E6     → utensile: F6F100E6, holder: E6,  bussola: D12
    - F6F100XD12E6    → utensile: F6F100XE6, holder: E6, bussola: D12 ⭐
    
    Args:
        alias_completo: es. "FS6R2L50F100XF6" o "F6F100D12E6"
    
    Returns:
        tuple: (utensile_base, holder_cod, bussola_cod)
    """
    import re
    
    alias = str(alias_completo).strip().upper()
    
    # 1. ESTRAI HOLDER (sempre alla fine)
    # Pattern: [A-M] seguito da numeri alla fine della stringa
    holder_pattern = r'([A-M])(\d+)$'
    match_holder = re.search(holder_pattern, alias)
    
    if not match_holder:
        # Nessun holder trovato
        return alias_completo, None, None
    
    holder_lettera = match_holder.group(1)
    holder_numero = match_holder.group(2)
    holder_cod = holder_lettera + holder_numero
    
    # 2. VERIFICA SE C'È BUSSOLA prima dell'holder
    # Pattern: D seguito da numeri immediatamente prima dell'holder
    # Es: ...F100D12E6 → bussola D12, holder E6
    bussola_pattern = r'(D\d+)([A-M]\d+)$'
    match_bussola = re.search(bussola_pattern, alias)
    
    bussola_cod = None
    utensile_base = None
    
    if match_bussola:
        # C'È BUSSOLA: utensile base include holder ma non bussola
        # Es: F6F100D12E6 → F6F100 + E6 = F6F100E6
        # Es: F6F100XD12E6 → F6F100X + E6 = F6F100XE6 ⭐
        bussola_cod = match_bussola.group(1)
        parte_prima_bussola = alias[:match_bussola.start(1)]
        utensile_base = parte_prima_bussola + holder_cod
    else:
        # NO BUSSOLA: utensile base NON include holder
        # Es: F6F100F6 → F6F100
        # Es: F6F100XF6 → F6F100X ⭐ (la X rimane!)
        # Es: FS6R2L50F100XF6 → FS6R2L50F100X ⭐
        utensile_base = alias[:match_holder.start()]
    
    return utensile_base, holder_cod, bussola_cod



def ha_holder(alias):
    """
    Verifica se un alias utensile contiene già un holder.
    
    Args:
        alias: Nome utensile (es: "PUNTA-10H4" o "PUNTA-10")
    
    Returns:
        bool: True se contiene holder, False altrimenti
    """
    _, holder_cod, _ = smonta_utensile(alias)
    return holder_cod is not None


def smonta_utensile_completo(alias_completo, db_paths, df_utensili_sm, df_holder_sm, df_bussole, provenienza=""):
    """
    Smonta utensile COMPLETO con separazione holder + bussola.
    
    Args:
        alias_completo: es. "CENTRINO-8-F50E3"
        db_paths: dict paths database
        df_utensili_sm, df_holder_sm, df_bussole: DataFrame da aggiornare
        provenienza: Provenienza smontaggio
    
    Returns:
        tuple: (success, message, df_utensili_sm_new, df_holder_sm_new, df_bussole_new)
    """
    from datetime import datetime
    import pandas as pd
    
    print(f"\n=== SMONTA_UTENSILE_COMPLETO ===")
    print(f"Alias: {alias_completo}")
    print(f"Provenienza: {provenienza}")
    
    # Smonta in componenti
    utensile_base, holder_cod, bussola_cod = smonta_utensile(alias_completo)
    print(f"Parsing: utensile={utensile_base}, holder={holder_cod}, bussola={bussola_cod}")
    
    # 1. Aggiungi utensile a smontati
    new_ut = pd.DataFrame([{
        'ID': '',  # Verrà generato automaticamente
        'Alias_Utensile': utensile_base,
        'Data_Smontaggio': datetime.now().strftime('%Y-%m-%d %H:%M'),
        'Provenienza': provenienza,
        'Note': ''
    }])
    df_utensili_sm = pd.concat([df_utensili_sm, new_ut], ignore_index=True)
    print(f"1. Utensile aggiunto a smontati (tot: {len(df_utensili_sm)})")
    
    # 2. Incrementa holder se presente
    if holder_cod:
        # DEBUG: mostra cosa c'è nel DataFrame
        print(f"\n   DEBUG HOLDER:")
        print(f"   holder_cod cercato: '{holder_cod}'")
        if not df_holder_sm.empty:
            print(f"   Holder esistenti: {df_holder_sm['Alias_Holder'].values.tolist()}")
            print(f"   Holder esistenti (stripped): {[str(x).strip() for x in df_holder_sm['Alias_Holder'].values]}")
        else:
            print(f"   DataFrame holder VUOTO")
        
        # Strip spazi da colonna Alias_Holder
        if not df_holder_sm.empty:
            df_holder_sm['Alias_Holder'] = df_holder_sm['Alias_Holder'].astype(str).str.strip()
        
        holder_cod_strip = str(holder_cod).strip()
        
        if not df_holder_sm.empty and holder_cod_strip in df_holder_sm['Alias_Holder'].values:
            # Converti Quantita a int prima di incrementare
            idx = df_holder_sm['Alias_Holder'] == holder_cod_strip
            df_holder_sm.loc[idx, 'Quantita'] = df_holder_sm.loc[idx, 'Quantita'].astype(int) + 1
            new_qty = df_holder_sm.loc[idx, 'Quantita'].values[0]
            print(f"2. Holder {holder_cod_strip} incrementato (tot: {new_qty})")
        else:
            new_h = pd.DataFrame([{
                'Alias_Holder': holder_cod_strip,
                'Data_Smontaggio': datetime.now().strftime('%Y-%m-%d %H:%M'),
                'Quantita': 1,
                'Note': ''
            }])
            df_holder_sm = pd.concat([df_holder_sm, new_h], ignore_index=True)
            print(f"2. Holder {holder_cod_strip} aggiunto nuovo (qty: 1)")
    
    # 3. Incrementa bussola se presente
    if bussola_cod:
        # DEBUG: mostra cosa c'è nel DataFrame
        print(f"\n   DEBUG BUSSOLA:")
        print(f"   bussola_cod cercato: '{bussola_cod}'")
        if not df_bussole.empty:
            print(f"   Bussole esistenti: {df_bussole['Codice_Bussola'].values.tolist()}")
            print(f"   Bussole esistenti (stripped): {[str(x).strip() for x in df_bussole['Codice_Bussola'].values]}")
        else:
            print(f"   DataFrame bussole VUOTO")
        
        # Strip spazi da colonna Codice_Bussola
        if not df_bussole.empty:
            df_bussole['Codice_Bussola'] = df_bussole['Codice_Bussola'].astype(str).str.strip()
        
        bussola_cod_strip = str(bussola_cod).strip()
        
        if not df_bussole.empty and bussola_cod_strip in df_bussole['Codice_Bussola'].values:
            # Converti Quantita a int prima di incrementare
            idx = df_bussole['Codice_Bussola'] == bussola_cod_strip
            df_bussole.loc[idx, 'Quantita'] = df_bussole.loc[idx, 'Quantita'].astype(int) + 1
            new_qty = df_bussole.loc[idx, 'Quantita'].values[0]
            print(f"3. Bussola {bussola_cod_strip} incrementata (tot: {new_qty})")
        else:
            # Estrai diametro da codice (es: E3 → D10)
            diametri_map = {'E1': 'D4', 'E2': 'D6', 'E3': 'D10', 'E4': 'D12',
                           'E5': 'D14', 'E6': 'D16', 'E7': 'D18', 'E8': 'D19'}
            diam = diametri_map.get(bussola_cod_strip, '')
            new_b = pd.DataFrame([{
                'Codice_Bussola': bussola_cod_strip,
                'Diametro': diam,
                'Quantita': 1,
                'Data_Acquisizione': datetime.now().strftime('%Y-%m-%d'),
                'Note': ''
            }])
            df_bussole = pd.concat([df_bussole, new_b], ignore_index=True)
            print(f"3. Bussola {bussola_cod_strip} aggiunta nuova (qty: 1)")
    
    # Salva
    try:
        df_utensili_sm.to_csv(db_paths['utensili_smontati'], sep='\t', index=False)
        df_holder_sm.to_csv(db_paths['holder_smontati'], sep='\t', index=False)
        df_bussole.to_csv(db_paths['bussole_idraulico'], sep='\t', index=False)
        
        # Messaggio successo - usa doppio newline per Windows
        parts = [f"Utensile: {utensile_base}"]
        if holder_cod:
            parts.append(f"Holder {holder_cod} +1")
        if bussola_cod:
            parts.append(f"Bussola {bussola_cod} +1")
        
        msg = "Smontato con successo!\n\n" + "\n".join(parts)
        
        return True, msg, df_utensili_sm, df_holder_sm, df_bussole
    except Exception as e:
        return False, f"Errore salvataggio: {e}", df_utensili_sm, df_holder_sm, df_bussole