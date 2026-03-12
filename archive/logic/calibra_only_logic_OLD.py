"""
Calibration Logic Avanzata - V14
Logica intelligente per CALIBRA ONLY basata su impostazioni utente
"""

import json
import os


class CalibraOnlyLogic:
    """Logica avanzata per determinare quando applicare CALIBRA ONLY."""
    
    # Classificazione utensili
    UTENSILI_FINITURA = ['FF']  # Frese finitura
    UTENSILI_SGROSATURA = ['FS', 'FSHSC', 'FSHPC', 'P', 'PI', 'R', 'C', 'FP', 'FR', 'SMS', 'D']
    
    def __init__(self):
        self.settings = self._load_settings()
        self.tool_call_count = {}  # Conta richiami per utensile
    
    def _load_settings(self):
        """Carica settings CALIBRA ONLY."""
        settings_file = "calibra_only_settings.json"
        
        default_settings = {
            'mode': 'finitura',
            'last_updated': None
        }
        
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    return json.load(f)
            except:
                return default_settings
        
        return default_settings
    
    def get_current_mode(self):
        """Ritorna modalità corrente."""
        return self.settings.get('mode', 'finitura')
    
    def is_finitura(self, alias):
        """
        Determina se utensile è di finitura.
        
        Args:
            alias: Alias utensile (es: "FF10R0.5L50F60G3")
        
        Returns:
            bool: True se utensile di finitura
        """
        alias_upper = alias.upper()
        
        # Controlla se inizia con FF
        for prefix in self.UTENSILI_FINITURA:
            if alias_upper.startswith(prefix):
                return True
        
        return False
    
    def needs_calibra_only(self, alias, index_in_program=0, total_tools=0):
        """
        Determina se serve CALIBRA ONLY per questo utensile.
        
        Args:
            alias: Alias utensile
            index_in_program: Indice utensile nel programma (0-based)
            total_tools: Totale utensili nel programma
        
        Returns:
            bool: True se serve CALIBRA ONLY
        """
        mode = self.get_current_mode()
        
        # Modalità: MAI
        if mode == 'mai':
            return False
        
        # Modalità: SOLO INIZIO
        if mode == 'inizio':
            return index_in_program == 0  # Solo primo utensile
        
        # Modalità: FINITURA
        if mode == 'finitura':
            return self.is_finitura(alias)
        
        # Modalità: AVANZATO (Finitura + ogni 3 richiami)
        if mode == 'avanzato':
            # Sempre per finitura
            if self.is_finitura(alias):
                return True
            
            # Ogni terzo richiamo dello stesso utensile
            if alias not in self.tool_call_count:
                self.tool_call_count[alias] = 0
            
            self.tool_call_count[alias] += 1
            
            # Ogni terzo richiamo (3, 6, 9, ...)
            if self.tool_call_count[alias] % 3 == 0:
                return True
            
            return False
        
        # Default: finitura
        return self.is_finitura(alias)
    
    def reset_call_count(self):
        """Reset contatore richiami (da usare all'inizio di ogni generazione MAIN)."""
        self.tool_call_count = {}
    
    def get_calibra_command(self, posizione):
        """
        Genera comando CALIBRA ONLY.
        
        Args:
            posizione: Posizione utensile (1-99)
        
        Returns:
            str: Comando G-code
        """
        return f"G65 P9832 T{posizione} ;CALIBRA ONLY"
    
    def get_mode_description(self):
        """Ritorna descrizione modalità corrente."""
        mode = self.get_current_mode()
        
        descriptions = {
            'mai': '❌ Nessun CALIBRA ONLY',
            'inizio': '▶️ Solo primo utensile',
            'finitura': '✨ Tutti gli utensili FF',
            'avanzato': '⚡ FF + ogni 3 richiami'
        }
        
        return descriptions.get(mode, 'Non configurato')
    
    def get_statistics(self, df_macchina):
        """
        Calcola statistiche CALIBRA ONLY per anteprima.
        
        Args:
            df_macchina: DataFrame utensili in macchina
        
        Returns:
            dict: Statistiche (totali, con_calibra, percentuale)
        """
        self.reset_call_count()
        
        total = len(df_macchina)
        with_calibra = 0
        
        for idx, row in df_macchina.iterrows():
            alias = row['Alias']
            if self.needs_calibra_only(alias, idx, total):
                with_calibra += 1
        
        percentage = (with_calibra / total * 100) if total > 0 else 0
        
        return {
            'total': total,
            'with_calibra': with_calibra,
            'percentage': percentage,
            'mode': self.get_mode_description()
        }


# Istanza globale
_calibra_logic = None


def get_calibra_logic():
    """Ritorna istanza singleton CalibraOnlyLogic."""
    global _calibra_logic
    if _calibra_logic is None:
        _calibra_logic = CalibraOnlyLogic()
    return _calibra_logic
