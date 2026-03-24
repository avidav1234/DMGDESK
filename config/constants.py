"""Constants - Tool Manager V16"""

# STATI
STATO_IN_MACCHINA = "IN_MACCHINA"
STATO_SCAFFALE = "SCAFFALE"
STATO_SMONTATO = "SMONTATO_DA_PORTA_UTENSILE"
STATO_DEFAULT_DB = STATO_IN_MACCHINA
STATI_UTENSILE = [STATO_IN_MACCHINA, STATO_SCAFFALE, STATO_SMONTATO]

# HOLDER TYPES
HOLDER_TYPES = {
    'A': 'Attacco Filettato', 'B': 'Forte Serraggio', 'C': 'Manicotto',
    'D': 'Pinza', 'E': 'Idraulico', 'F': 'Idraulico Tendo Slim',
    'G': 'Idraulico Tendo Slim Lungo', 'H': 'Caletto BILZ',
    'I': 'Caletto', 'J': 'Caletto MST Curvo', 'K': 'Weldon',
    'L': 'Caletto KAISER', 'M': 'Idraulico Tendo ZERO'
}

# WHITELIST HOLDER VALIDI (da CSV Vetimec)
# Lista esplicita di TUTTI i codici holder possibili
HOLDER_VALIDI = {
    # Attacco Filettato (A)
    'A1', 'A2', 'A3', 'A4', 'A5', 'A6', 'A7',
    # Forte Serraggio (B)
    'B1', 'B2', 'B3', 'B4', 'B5', 'B6', 'B7', 'B8', 'B9',
    # Manicotto (C)
    'C1', 'C2', 'C3', 'C4', 'C5',
    # Pinza (D) - include anche ER
    'D1', 'D2', 'D3', 'D4', 'D5', 'D6', 'D7', 'D8', 'D9', 'D10',
    'D11', 'D12', 'D13', 'D14', 'D15', 'D16', 'D17', 'D18', 'D19', 'D20',
    'D22', 'D25', 'D27', 'D32', 'D40',
    # Idraulico (E)
    'E', 'E1', 'E2', 'E3', 'E4', 'E5', 'E6', 'E7', 'E8',
    # Idraulico Tendo Slim (F)
    'F1', 'F2', 'F3', 'F4', 'F5',
    # Idraulico Tendo Slim Lungo (G)
    'G1', 'G2', 'G3', 'G4', 'G5',
    # Caletto BILZ (H)
    'H1', 'H2', 'H3', 'H4', 'H5', 'H6', 'H7', 'H8', 'H9', 'H10',
    'H11', 'H12', 'H13', 'H14', 'H15', 'H16', 'H17', 'H18',
    # Caletto (I)
    'I1', 'I2', 'I3', 'I4', 'I5', 'I6', 'I7', 'I8', 'I9', 'I10',
    'I11', 'I12', 'I13', 'I14', 'I15', 'I16', 'I17', 'I18',
    # Caletto MST Curvo (J)
    'J1', 'J2', 'J3', 'J4', 'J5', 'J6', 'J7', 'J8', 'J9', 'J10',
    'J11', 'J12', 'J13', 'J14', 'J15', 'J16', 'J17', 'J18',
    # Weldon (K)
    'K1', 'K2', 'K3', 'K4', 'K5', 'K6', 'K7', 'K8',
    # Caletto KAISER (L)
    'L1', 'L2', 'L3', 'L4', 'L5', 'L6', 'L7', 'L8', 'L9', 'L10',
    'L11', 'L12', 'L13', 'L14', 'L15', 'L16', 'L17', 'L18',
    # Idraulico Tendo ZERO / Filettati (M)
    'M6', 'M8', 'M10', 'M12', 'M16', 'M20', 'M23', 'M24',
}

# HOLDER DIAMETERS
HOLDER_DIAMETER_MAP = {
    ('H', 1): 'D3', ('H', 4): 'D6', ('H', 10): 'D10', ('H', 18): 'D20',
    ('K', 1): 'D6', ('K', 2): 'D8', ('K', 3): 'D10', ('K', 6): 'D16',
    ('G', 1): 'D6', ('G', 3): 'D10', ('G', 4): 'D12',
    ('E', 1): 'D6', ('E', 2): 'D8', ('E', 3): 'D10', ('E', 4): 'D12',
    ('E', 5): 'D13', ('E', 6): 'D16', ('E', 7): 'D18', ('E', 8): 'D20'
}

# BUSSOLE
BUSSOLE_IDRAULICO_E = {
    1: 'D6', 2: 'D8', 3: 'D10', 4: 'D12',
    5: 'D13', 6: 'D16', 7: 'D18', 8: 'D20'
}

# IMPIEGHI
IMPIEGHI_FRESA = ['FF', 'FS', 'FP', 'FR']

# FILES
NC_EXTENSIONS = ['.nc', '.NC', '.spf', '.SPF', '.mpf', '.MPF']
CONFIG_FILE = 'config.json'

# DATABASE COLUMNS
DB_COLUMNS_PRINCIPALE = ['Posizione', 'Alias', 'Stato_Utensile']
DB_COLUMNS_SMONTATI = ['ID', 'Alias_Utensile', 'Data_Smontaggio', 'Provenienza', 'Note']
DB_COLUMNS_HOLDER = ['Alias_Holder', 'Data_Smontaggio', 'Quantita', 'Note']
DB_COLUMNS_BUSSOLE = ['Codice_Bussola', 'Diametro', 'Quantita', 'Data_Acquisizione', 'Note']

# REGEX
PATTERN_DIAMETRO = r'(?:^|[^0-9])(\d{1,2}(?:\.\d+)?)[^0-9]'
PATTERN_HOLDER_VETIMEC = r'([A-M])(\d{1,2})$'
PATTERN_T_COMMAND = r'T(\d+)'

# APP INFO
APP_VERSION = "16.0"
APP_TITLE = "DMGDesk"
APP_SUBTITLE = "Modulare - Tab Separati"
