"""
Code Generator Logic - V14 con SPECIALE
Logica generazione codici utensili DMG - 27 utensili, 13 porta-utensili
NUOVO: Flag SPECIALE aggiunge "X" dopo FP (es: F100X)
"""

import re

# ============= 27 UTENSILI COMPLETI =============
UTENSILI = {
    'Fresa': {
        'nome': 'FRESA', 'commento': 'F', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': False,
        'dedicato': ''
    },
    'Fresa-SGR-PIANI': {
        'nome': 'FRESA-SGR-PIANI', 'commento': 'FS', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': 'PI'
    },
    'Fresa-SGR-HSC': {
        'nome': 'FRESA-SGR-HSC', 'commento': 'FS', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': 'HSC'
    },
    'Fresa-SGR-HPC': {
        'nome': 'FRESA-SGR-HPC', 'commento': 'FS', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': 'HPC'
    },
    'Fresa-FIN-PIANI': {
        'nome': 'FRESA-FIN-PIANI', 'commento': 'FF', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': 'PI'
    },
    'Fresa-FIN-HSC': {
        'nome': 'FRESA-FIN-HSC', 'commento': 'FF', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': 'HSC'
    },
    'Fresa-FIN-HPC': {
        'nome': 'FRESA-FIN-HPC', 'commento': 'FF', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': 'HPC'
    },
    'Fresa-FIN-Plunging': {
        'nome': 'FRESA-FIN-PLU', 'commento': 'FF', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': 'PL'
    },
    'Fresa-PREF': {
        'nome': 'FRESA-PREF', 'commento': 'FS', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': ''
    },
    'Fresa-PREF-Spazzolatura': {
        'nome': 'FRESA-PREF-SPA', 'commento': 'FS', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': 'SP'
    },
    'Fresa-PREF-Plunging': {
        'nome': 'FRESA-PREF-PLU', 'commento': 'FS', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': 'PL'
    },
    'Fresa-Riprese': {
        'nome': 'FRESA-RIP', 'commento': 'FS', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': ''
    },
    'Punta': {
        'nome': 'PUNTA', 'commento': 'P', 
        'has_r2': False, 'has_l': False, 'has_vd': True, 'has_x': False,
        'dedicato': ''
    },
    'Punta_Integrale': {
        'nome': 'PUNTA-INT', 'commento': 'PI', 
        'has_r2': False, 'has_l': False, 'has_vd': True, 'has_x': False,
        'dedicato': ''
    },
    'Pettine': {
        'nome': 'PETTINE', 'commento': 'PE', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': True,
        'dedicato': ''
    },
    'Pettine-M': {
        'nome': 'PETTINE-M', 'commento': 'PM', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': True,
        'dedicato': ''
    },
    'Pettine-Gas': {
        'nome': 'PETTINE-GAS', 'commento': 'PG', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': True,
        'dedicato': ''
    },
    'Pettine-NPT': {
        'nome': 'PETTINE-NPT', 'commento': 'PN', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': True,
        'dedicato': ''
    },
    'Maschio-M': {
        'nome': 'MASCHIO-M', 'commento': 'MM', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': True,
        'dedicato': ''
    },
    'Maschio-Gas': {
        'nome': 'MASCHIO-GAS', 'commento': 'G', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': True,
        'dedicato': ''
    },
    'Maschio': {
        'nome': 'MASCHIO', 'commento': 'M', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': True,
        'dedicato': ''
    },
    'Alesatore': {
        'nome': 'ALESATORE', 'commento': 'A', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': False,
        'dedicato': ''
    },
    'Coda Rondine dal pieno': {
        'nome': 'CODA-RONDINE', 'commento': 'R', 
        'has_r2': True, 'has_l': False, 'has_vd': False, 'has_x': False,
        'dedicato': ''
    },
    'Coda Rondine laterale': {
        'nome': 'CODA-RONDINE', 'commento': 'R', 
        'has_r2': True, 'has_l': False, 'has_vd': False, 'has_x': False,
        'dedicato': ''
    },
    'Disco': {
        'nome': 'DISCO', 'commento': 'D', 
        'has_r2': True, 'has_l': True, 'has_vd': False, 'has_x': False,
        'dedicato': ''
    },
    'Smussatore': {
        'nome': 'SMS', 'commento': 'SMS', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': True,
        'dedicato': ''
    },
    'Incisore': {
        'nome': 'INCISORE', 'commento': 'INC', 
        'has_r2': False, 'has_l': False, 'has_vd': False, 'has_x': False,
        'dedicato': ''
    }
}

# ============= 13 PORTA-UTENSILI COMPLETI =============
PORTA_UTENSILI = {
    'Attacco_Filettato': {
        'lettera': 'A', 'abbreviato': 'AF',
        'diametri': ['M6', 'M8', 'M10', 'M12', 'M16', 'M20', 'M24']
    },
    'Forte_Serraggio': {
        'lettera': 'B', 'abbreviato': 'FS',
        'diametri': ['D6', 'D8', 'D10', 'D12', 'D14', 'D16', 'D20', 'D25', 'D32']
    },
    'Manicotto': {
        'lettera': 'C', 'abbreviato': 'MAN',
        'diametri': ['D16', 'D22', 'D27', 'D32', 'D40']
    },
    'Pinza': {
        'lettera': 'D', 'abbreviato': 'P',
        'diametri': ['ER11', 'ER20', 'ER25', 'ER32', 'ER40', 'ER50']
    },
    'Idraulico': {
        'lettera': 'E', 'abbreviato': 'H',
        'diametri': ['D6', 'D8', 'D10', 'D12', 'D13', 'D16', 'D18', 'D20']
    },
    'idraulico_Tendo_Slim': {
        'lettera': 'F', 'abbreviato': 'HTS',
        'diametri': ['D6', 'D8', 'D10', 'D12', 'D16', 'D16']
    },
    'Idraulico_Tendo_Slim_Lungo': {
        'lettera': 'G', 'abbreviato': 'HSL',
        'diametri': ['D6', 'D8', 'D10', 'D12', 'D13', 'D16']
    },
    'Caletto_BILZ': {
        'lettera': 'H', 'abbreviato': 'CB',
        'diametri': ['D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10', 'D12', 'D14', 'D16', 'D18', 'D20']
    },
    'Caletto': {
        'lettera': 'I', 'abbreviato': 'CT',
        'diametri': ['D3', 'D4', 'D5', 'D6', 'D8', 'D10', 'D12', 'D16', 'D20']
    },
    'Caletto_MST_curvo': {
        'lettera': 'J', 'abbreviato': 'CMST',
        'diametri': ['D3', 'D6', 'D8', 'D10', 'D12', 'D16', 'D20']
    },
    'Weldon': {
        'lettera': 'K', 'abbreviato': 'W',
        'diametri': ['D6', 'D8', 'D10', 'D12', 'D16', 'D20', 'D25']
    },
    'CALETTO_KAISER': {
        'lettera': 'L', 'abbreviato': 'CK',
        'diametri': ['D3', 'D6', 'D8', 'D10', 'D12', 'D16', 'D20']
    },
    'idraulico_Tendo_ZERO': {
        'lettera': 'M', 'abbreviato': 'HTZ',
        'diametri': ['D6', 'D8', 'D10', 'D12', 'D16', 'D20']
    }
}

# ============= MAPPATURA DIAMETRI → NUMERI =============
DIAMETRI_NUMERI = {
    'Attacco_Filettato': {'M6': 1, 'M8': 2, 'M10': 3, 'M12': 4, 'M16': 5, 'M20': 6, 'M24': 7},
    'Forte_Serraggio': {'D6': 1, 'D8': 2, 'D10': 3, 'D12': 4, 'D14': 5, 'D16': 6, 'D20': 7, 'D25': 8, 'D32': 9},
    'Manicotto': {'D16': 1, 'D22': 2, 'D27': 3, 'D32': 4, 'D40': 5},
    'Pinza': {'ER11': 1, 'ER20': 2, 'ER25': 3, 'ER32': 4, 'ER40': 5, 'ER50': 6},
    'Idraulico': {'D6': 1, 'D8': 2, 'D10': 3, 'D12': 4, 'D13': 5, 'D16': 6, 'D18': 7, 'D20': 8},
    'idraulico_Tendo_Slim': {'D6': 1, 'D8': 2, 'D10': 3, 'D12': 4, 'D16': 5, 'D16': 6},
    'Idraulico_Tendo_Slim_Lungo': {'D6': 1, 'D8': 2, 'D10': 3, 'D12': 4, 'D13': 5, 'D16': 6},
    'Caletto_BILZ': {'D3': 1, 'D4': 2, 'D5': 3, 'D6': 4, 'D7': 5, 'D8': 6, 'D9': 7, 'D10': 8, 'D12': 10, 'D14': 12, 'D16': 14, 'D18': 16, 'D20': 18},
    'Caletto': {'D3': 1, 'D4': 2, 'D5': 3, 'D6': 4, 'D8': 6, 'D10': 8, 'D12': 10, 'D16': 14, 'D20': 18},
    'Caletto_MST_curvo': {'D3': 1, 'D6': 4, 'D8': 6, 'D10': 8, 'D12': 10, 'D16': 14, 'D20': 18},
    'Weldon': {'D6': 1, 'D8': 2, 'D10': 3, 'D12': 4, 'D16': 6, 'D20': 8, 'D25': 9},
    'CALETTO_KAISER': {'D3': 1, 'D6': 4, 'D8': 6, 'D10': 8, 'D12': 10, 'D16': 14, 'D20': 18},
    'idraulico_Tendo_ZERO': {'D6': 1, 'D8': 2, 'D10': 3, 'D12': 4, 'D16': 6, 'D20': 8}
}


def genera_codici(tipo_utensile, diametro, r2_x='', l='', vd='', fp='', 
                  tipo_holder='', diam_holder='', fresa_dedicata=False, speciale=False):
    """
    Genera nome e commento per utensile.
    
    Args:
        fresa_dedicata: Se True, aggiunge acronimo dedicato al commento
        speciale: Se True, aggiunge "X" dopo FP (es: F100X) ⭐ NUOVO
    
    Returns:
        tuple: (nome_completo, commento, errore)
    """
    # Validazione base
    if not all([tipo_utensile, diametro, fp, tipo_holder, diam_holder]):
        return None, None, "Campi obbligatori mancanti"
    
    if not re.match(r'^\d+(\.\d+)?$', diametro.replace(',', '.')):
        return None, None, "Diametro non valido"
    
    if not re.match(r'^\d+$', fp):
        return None, None, "Fuori Pinza non valido"
    
    # Dati utensile
    dati = UTENSILI.get(tipo_utensile)
    if not dati:
        return None, None, "Tipo utensile non valido"
    
    # Dati holder
    holder_info = PORTA_UTENSILI.get(tipo_holder)
    if not holder_info:
        return None, None, "Tipo holder non valido"
    
    holder_lettera = holder_info['lettera']
    holder_abbr = holder_info['abbreviato']
    holder_num = DIAMETRI_NUMERI[tipo_holder].get(diam_holder, '?')
    
    diametro = diametro.replace(',', '.')
    
    # ========== NOME CIMATRON ==========
    nome_parts = [dati['nome'], diametro]
    
    if dati.get('has_vd') and vd:
        nome_parts = [dati['nome'], f"{diametro}-{vd}VD"]
    elif dati.get('has_r2') and r2_x:
        nome_parts.append(f"R{r2_x}")
        if dati.get('has_l') and l:
            nome_parts.append(f"L{l}")
    elif dati.get('has_x') and r2_x:
        nome_parts.append(f"X{r2_x}")
    
    # FP con eventuale X per speciale
    fp_nome = f"F{fp}"
    if speciale:
        fp_nome += "X"  # ⭐ F100 → F100X
    
    nome_parts.append(fp_nome)
    nome_parts.append(f"{holder_abbr}{diam_holder}")
    nome_completo = "-".join(nome_parts)
    
    # ========== COMMENTO CNC ==========
    comm_base = dati['commento']
    
    # Aggiungi acronimo dedicato SE checkbox attivo
    if fresa_dedicata and dati.get('dedicato'):
        comm_base += dati['dedicato']
    
    comm_parts = [comm_base, diametro]
    
    if dati.get('has_vd') and vd:
        comm_parts = [comm_base, f"{diametro}-{vd}VD"]
    elif dati.get('has_r2') and r2_x:
        comm_parts.append(f"R{r2_x}")
        if dati.get('has_l') and l:
            comm_parts.append(f"L{l}")
    elif dati.get('has_x') and r2_x:
        comm_parts.append(f"X{r2_x}")
    
    # FP con eventuale X per speciale
    fp_comm = f"F{fp}"
    if speciale:
        fp_comm += "X"  # ⭐ F100 → F100X
    
    comm_parts.append(fp_comm)
    comm_parts.append(f"{holder_lettera}{holder_num}")
    commento = "".join(comm_parts)
    
    return nome_completo, commento, None