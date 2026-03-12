"""
Calibration Logic Avanzata - V14 FINALE CORRETTO
Logica intelligente per CALIBRA ONLY con 5 modalità configurabili
FIX: Ricarica impostazioni ad ogni chiamata per rilevare modifiche
"""

import json
import os


class CalibraOnlyLogic:
    """Logica avanzata per determinare quando applicare CALIBRA ONLY."""
    
    # Classificazione utensili
    UTENSILI_FINITURA = ['FF']  # Frese finitura
    UTENSILI_SGROSATURA = ['FS', 'FSHSC', 'FSHPC', 'P', 'PI', 'R', 'C', 'FP', 'FR', 'SMS', 'D']
    
    def __init__(self):
        self.tool_call_count = {}  # Conta richiami per utensile
        # NON carichiamo settings qui - li ricarichiamo ogni volta!
    
    def _load_settings(self):
        """Carica settings CALIBRA ONLY dal file JSON."""
        settings_file = "calibra_only_settings.json"
        
        default_settings = {
            'mode': 'finitura_unico',
            'x_finitura': 3,
            'x_qualsiasi': 3,
            'last_updated': None
        }
        
        if os.path.exists(settings_file):
            try:
                with open(settings_file, 'r', encoding='utf-8') as f:
                    loaded = json.load(f)
                    default_settings.update(loaded)
                    return default_settings
            except:
                return default_settings
        
        return default_settings
    
    def get_current_mode(self):
        """Ritorna modalità corrente (RICARICA DA FILE OGNI VOLTA)."""
        settings = self._load_settings()
        return settings.get('mode', 'finitura_unico')
    
    def get_x_finitura(self):
        """Ritorna X per modalità finitura_x (RICARICA DA FILE)."""
        settings = self._load_settings()
        return settings.get('x_finitura', 3)
    
    def get_x_qualsiasi(self):
        """Ritorna X per modalità ogni_x (RICARICA DA FILE)."""
        settings = self._load_settings()
        return settings.get('x_qualsiasi', 3)
    
    def is_finitura(self, alias):
        """
        Determina se utensile è di finitura.
        
        Args:
            alias: Alias utensile (es: "FF10R0.5L50F60G3")
        
        Returns:
            bool: True se utensile di finitura
        """
        if not alias:  # gestisce None, "", 0
            return False
        alias_upper = str(alias).upper().strip()
        
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
        # RICARICA modalità ogni volta per rilevare modifiche
        mode = self.get_current_mode()
        
        # OPZIONE 1: MAI
        if mode == 'mai':
            return False
        
        # OPZIONE 2: INIZIO PROGRAMMA (solo primo utensile)
        if mode == 'inizio':
            return index_in_program == 0
        
        # OPZIONE 3: SOLO FINITURA (UNICO)
        if mode == 'finitura_unico':
            return self.is_finitura(alias)
        
        # OPZIONE 4: FINITURA + OGNI X RICHIAMI DI FF
        if mode == 'finitura_x':
            # Sempre per finitura al primo richiamo
            if self.is_finitura(alias):
                if alias not in self.tool_call_count:
                    self.tool_call_count[alias] = 0
                
                self.tool_call_count[alias] += 1
                
                # Primo richiamo SEMPRE
                if self.tool_call_count[alias] == 1:
                    return True
                
                # Ogni X-esimo richiamo
                x = self.get_x_finitura()
                if self.tool_call_count[alias] % x == 0:
                    return True
            
            return False
        
        # OPZIONE 5: OGNI X RICHIAMI QUALSIASI UTENSILE
        if mode == 'ogni_x':
            if alias not in self.tool_call_count:
                self.tool_call_count[alias] = 0
            
            self.tool_call_count[alias] += 1
            
            # Ogni X-esimo richiamo
            x = self.get_x_qualsiasi()
            if self.tool_call_count[alias] % x == 0:
                return True
            
            return False
        
        # Default: solo finitura
        return self.is_finitura(alias)
    
    def reset_call_count(self):
        """Reset contatore richiami (da usare all'inizio di ogni generazione MAIN)."""
        self.tool_call_count = {}
    
    def get_calibra_command(self):
        """
        Genera comando CALIBRA ONLY.
        
        Returns:
            str: Comando G-code (solo "CALIBRA_ONLY")
        """
        return "CALIBRA_ONLY"
    
    def get_mode_description(self):
        """Ritorna descrizione modalità corrente (RICARICA DA FILE)."""
        mode = self.get_current_mode()
        
        descriptions = {
            'mai': '❌ Nessun CALIBRA ONLY',
            'inizio': '▶️ Solo primo utensile',
            'finitura_unico': '✨ Solo finitura (ogni FF)',
            'finitura_x': f"⚡ Finitura + ogni {self.get_x_finitura()} richiami FF",
            'ogni_x': f"🔄 Ogni {self.get_x_qualsiasi()} richiami"
        }
        
        return descriptions.get(mode, 'Non configurato')
    
    def get_statistics(self, df_utensili_or_list):
        """
        Calcola statistiche CALIBRA ONLY per anteprima.
        
        Args:
            df_utensili_or_list: DataFrame o lista di alias utensili
        
        Returns:
            dict: Statistiche (totali, con_calibra, percentuale)
        """
        self.reset_call_count()
        
        # Se è un DataFrame pandas
        try:
            import pandas as pd
            if isinstance(df_utensili_or_list, pd.DataFrame):
                aliases = df_utensili_or_list['Alias'].tolist()
            else:
                aliases = df_utensili_or_list
        except:
            aliases = df_utensili_or_list
        
        total = len(aliases)
        with_calibra = 0
        
        for idx, alias in enumerate(aliases):
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
    """
    Ritorna istanza singleton CalibraOnlyLogic.
    L'istanza viene creata una volta ma RICARICA le impostazioni ogni volta.
    """
    global _calibra_logic
    if _calibra_logic is None:
        _calibra_logic = CalibraOnlyLogic()
    return _calibra_logic
