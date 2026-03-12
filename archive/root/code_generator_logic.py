"""
Code Generator Logic - V13
Logica generazione codici utensili DMG
"""

import re

# Dati utensili (da tool_code_generator v3.0)
UTENSILI = {
    'Fresa-SGR-HSC': {'nome': 'FRESA-SGR-HSC', 'commento': 'FSHSC', 'has_r2': True, 'has_l': True},
    'Fresa-SGR-PIANI': {'nome': 'FRESA-SGR-PIANI', 'commento': 'FS', 'has_r2': True, 'has_l': True},
    'Fresa-FIN-HSC': {'nome': 'FRESA-FIN-HSC', 'commento': 'FFHSC', 'has_r2': True, 'has_l': True},
    'Fresa-FIN-PIANI': {'nome': 'FRESA-FIN-PIANI', 'commento': 'FF', 'has_r2': True, 'has_l': True},
    'Disco': {'nome': 'DISCO', 'commento': 'D', 'has_r2': True, 'has_l': True},
    'Coda Rondine': {'nome': 'CODA-RONDINE', 'commento': 'R', 'has_r2': True, 'has_l': False},
    'Punta_Integrale': {'nome': 'PUNTA-INT', 'commento': 'PI', 'has_r2': False, 'has_l': False, 'has_vd': True},
    'Punta': {'nome': 'PUNTA', 'commento': 'P', 'has_r2': False, 'has_l': False, 'has_vd': True},
    'Pettine-M': {'nome': 'PETTINE-M', 'commento': 'PM', 'has_r2': False, 'has_l': False, 'has_x': True},
    'Maschio-M': {'nome': 'MASCHIO-M', 'commento': 'MM', 'has_r2': False, 'has_l': False, 'has_x': True},
    'Smussatore': {'nome': 'SMS', 'commento': 'SMS', 'has_r2': False, 'has_l': False, 'has_x': True},
    'Alesatore': {'nome': 'ALESATORE', 'commento': 'A', 'has_r2': False, 'has_l': False},
    'Incisore': {'nome': 'INCISORE', 'commento': 'INC', 'has_r2': False, 'has_l': False}
}

# Porta-utensili
PORTA_UTENSILI = {
    'Idraulico_Tendo_Slim_Lungo': {'lettera': 'G', 'abbreviato': 'HSL', 'diametri': ['D6', 'D8', 'D10', 'D12', 'D13', 'D16']},
    'Idraulico': {'lettera': 'E', 'abbreviato': 'H', 'diametri': ['D6', 'D8', 'D10', 'D12', 'D13', 'D16', 'D18', 'D20']},
    'Caletto_BILZ': {'lettera': 'H', 'abbreviato': 'CB', 'diametri': ['D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10', 'D12', 'D14', 'D16', 'D18', 'D20']},
    'Caletto': {'lettera': 'I', 'abbreviato': 'CT', 'diametri': ['D3', 'D4', 'D5', 'D6', 'D8', 'D10', 'D12', 'D16', 'D20']},
    'Caletto_MST_curvo': {'lettera': 'J', 'abbreviato': 'CMST', 'diametri': ['D3', 'D6', 'D8', 'D10', 'D12', 'D16', 'D20']},
    'CALETTO_KAISER': {'lettera': 'L', 'abbreviato': 'CK', 'diametri': ['D3', 'D6', 'D8', 'D10', 'D12', 'D16', 'D20']},
    'Weldon': {'lettera': 'K', 'abbreviato': 'W', 'diametri': ['D6', 'D8', 'D10', 'D12', 'D16', 'D20']},
    'Pinza': {'lettera': 'D', 'abbreviato': 'P', 'diametri': ['ER11', 'ER20', 'ER25', 'ER32']},
}

# Mappatura diametro -> numero
DIAMETRI_NUMERI = {
    'Idraulico_Tendo_Slim_Lungo': {'D6': 1, 'D8': 2, 'D10': 3, 'D12': 4, 'D13': 5, 'D16': 6},
    'Idraulico': {'D6': 1, 'D8': 2, 'D10': 3, 'D12': 4, 'D13': 5, 'D16': 6, 'D18': 7, 'D20': 8},
    'Caletto_BILZ': {'D3': 1, 'D4': 2, 'D5': 3, 'D6': 4, 'D7': 5, 'D8': 6, 'D9': 7, 'D10': 8, 'D12': 10, 'D14': 12, 'D16': 14, 'D18': 16, 'D20': 18},
    'Caletto': {'D3': 1, 'D4': 2, 'D5': 3, 'D6': 4, 'D8': 6, 'D10': 8, 'D12': 10, 'D16': 14, 'D20': 18},
    'Caletto_MST_curvo': {'D3': 1, 'D6': 4, 'D8': 6, 'D10': 8, 'D12': 10, 'D16': 14, 'D20': 18},
    'CALETTO_KAISER': {'D3': 1, 'D6': 4, 'D8': 6, 'D10': 8, 'D12': 10, 'D16': 14, 'D20': 18},
    'Weldon': {'D6': 1, 'D8': 2, 'D10': 3, 'D12': 4, 'D16': 6, 'D20': 8},
    'Pinza': {'ER11': 1, 'ER20': 2, 'ER25': 3, 'ER32': 4}
}


def genera_codici(tipo_utensile, diametro, r2_x='', l='', vd='', fp='', tipo_holder='', diam_holder=''):
    """
    Genera nome e commento per utensile.
    
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
    
    # NOME
    nome_parts = [dati['nome'], diametro]
    
    if dati.get('has_vd') and vd:
        nome_parts = [dati['nome'], f"{diametro}-{vd}VD"]
    elif dati.get('has_r2') and r2_x:
        nome_parts.append(f"R{r2_x}")
        if dati.get('has_l') and l:
            nome_parts.append(f"L{l}")
    elif dati.get('has_x') and r2_x:
        nome_parts.append(f"X{r2_x}")
    
    nome_parts.append(f"F{fp}")
    nome_parts.append(f"{holder_abbr}{diam_holder}")
    nome_completo = "-".join(nome_parts)
    
    # COMMENTO
    comm_parts = [dati['commento'], diametro]
    
    if dati.get('has_vd') and vd:
        comm_parts = [dati['commento'], f"{diametro}-{vd}VD"]
    elif dati.get('has_r2') and r2_x:
        comm_parts.append(f"R{r2_x}")
        if dati.get('has_l') and l:
            comm_parts.append(f"L{l}")
    elif dati.get('has_x') and r2_x:
        comm_parts.append(f"X{r2_x}")
    
    comm_parts.append(f"F{fp}")
    comm_parts.append(f"{holder_lettera}{holder_num}")
    commento = "".join(comm_parts)
    
    return nome_completo, commento, None
