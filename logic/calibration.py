"""
Calibration Logic - Gestione calibrazione utensili
"""

class CalibrationLogic:
    """Logica calibrazione laser utensili."""
    
    def __init__(self):
        self.calibration_history = []
    
    def needs_calibration(self, alias_utensile, last_calibration=None):
        """
        Determina se utensile necessita calibrazione.
        
        Args:
            alias_utensile: Alias utensile
            last_calibration: Data ultima calibrazione
        
        Returns:
            bool: True se serve calibrazione
        """
        # Logica base: calibra sempre utensili finitura
        if any(x in alias_utensile.upper() for x in ['FF', 'F50', 'F40']):
            return True
        
        # Altri utensili: calibra se mai calibrato
        if last_calibration is None:
            return True
        
        return False
    
    def get_calibration_command(self, posizione):
        """
        Genera comando calibrazione per posizione.
        
        Args:
            posizione: Posizione utensile (1-99)
        
        Returns:
            str: Comando G-code calibrazione
        """
        return f"G65 P9832 T{posizione}"
    
    def record_calibration(self, alias_utensile, posizione):
        """Registra calibrazione eseguita."""
        from datetime import datetime
        
        record = {
            'alias': alias_utensile,
            'posizione': posizione,
            'timestamp': datetime.now(),
            'type': 'laser'
        }
        
        self.calibration_history.append(record)
        return True
