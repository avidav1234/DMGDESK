"""
Generatore programma MAIN O9999 - V14
Con supporto CALIBRA ONLY configurabile
"""

from tkinter import filedialog, messagebox
from datetime import datetime
import pandas as pd

try:
    from utils.logger import get_logger, tool_log
    _log = get_logger(__name__)
except ImportError:
    import logging
    _log = logging.getLogger(__name__)
    tool_log = None


def genera_programma_main(df_macchina, nome_cartella="MAIN", calibra_logic=None):
    """
    Genera programma MAIN O9999 con CALIBRA ONLY intelligente.
    
    Args:
        df_macchina: DataFrame utensili in macchina
        nome_cartella: Nome cartella per output (default: "MAIN")
        calibra_logic: Istanza CalibraOnlyLogic (opzionale)
    
    Returns:
        tuple: (success, message)
    """
    default_name = f"O9999_{nome_cartella}.MPF"
    
    save_path = filedialog.asksaveasfilename(
        title="Salva Programma MAIN",
        initialfile=default_name,
        defaultextension=".MPF",
        filetypes=[("MPF Program", "*.MPF"), ("NC Program", "*.nc"), ("All", "*.*")]
    )
    
    if not save_path:
        return False, "Annullato"
    
    # Importa logica CALIBRA ONLY se non fornita
    if calibra_logic is None:
        try:
            from logic.calibra_only_logic import get_calibra_logic
            calibra_logic = get_calibra_logic()
        except:
            calibra_logic = None  # Fallback: nessun CALIBRA ONLY
    
    try:
        # Reset contatore richiami
        if calibra_logic:
            calibra_logic.reset_call_count()
        
        # Ordina per posizione
        df = df_macchina.copy()
        df['Pos_Int'] = pd.to_numeric(df['Posizione'], errors='coerce')
        df = df.sort_values('Pos_Int')
        
        # Statistiche CALIBRA ONLY
        calibra_count = 0
        
        with open(save_path, 'w', encoding='utf-8') as f:
            # Header
            f.write(f"; PROGRAMMA MAIN O9999 - {nome_cartella}\n")
            f.write(f"; Generato: {datetime.now().strftime('%Y-%m-%d %H:%M')}\n")
            f.write(f"; Utensili: {len(df)}\n")
            
            # Info CALIBRA ONLY
            if calibra_logic:
                mode_desc = calibra_logic.get_mode_description()
                f.write(f"; CALIBRA ONLY: {mode_desc}\n")
            
            f.write("%\n")
            f.write("O9999\n")
            f.write(";\n")
            
            # Genera righe utensili
            total_tools = len(df)
            
            for idx, row in df.iterrows():
                pos = row['Posizione']
                alias = row['Alias']
                
                # Riga utensile standard
                f.write(f"T{pos} ({alias})\n")
                
                # Aggiungi CALIBRA ONLY se necessario
                if calibra_logic and calibra_logic.needs_calibra_only(alias, idx, total_tools):
                    calibra_cmd = calibra_logic.get_calibra_command()
                    f.write(f"{calibra_cmd}\n")
                    calibra_count += 1
            
            f.write(";\n")
            f.write("M30\n")
            f.write("%\n")
        
        # Messaggio success con statistiche
        _log.info(f"MAIN generato: {save_path} ({len(df)} utensili, {calibra_count} CALIBRA ONLY)")
        if tool_log: tool_log.main_generato(save_path, len(df), calibra_count)
        msg = f"✅ MAIN generato con successo!\n\n"
        msg += f"📁 File: {save_path}\n"
        msg += f"🔧 Utensili totali: {len(df)}\n"
        msg += f"📏 CALIBRA ONLY: {calibra_count}\n"
        
        if calibra_logic:
            msg += f"\n⚙️ Modalità: {calibra_logic.get_mode_description()}"
        
        return True, msg
        
    except Exception as e:
        _log.error(f"Errore generazione MAIN: {e}", exc_info=True)
        return False, f"Errore generazione MAIN:\n{e}"


def genera_programma_main_with_preview(df_macchina, nome_cartella="MAIN", parent=None):
    """
    Genera MAIN con anteprima CALIBRA ONLY.
    
    Args:
        df_macchina: DataFrame utensili
        nome_cartella: Nome cartella
        parent: Finestra parent per messagebox
    
    Returns:
        tuple: (success, message)
    """
    try:
        from logic.calibra_only_logic import get_calibra_logic
        calibra_logic = get_calibra_logic()
    except:
        # Fallback senza preview
        return genera_programma_main(df_macchina, nome_cartella)
    
    # Mostra preview
    stats = calibra_logic.get_statistics(df_macchina)
    
    preview_msg = f"📊 ANTEPRIMA CALIBRA ONLY\n\n"
    preview_msg += f"⚙️ Modalità: {stats['mode']}\n\n"
    preview_msg += f"🔧 Utensili totali: {stats['total']}\n"
    preview_msg += f"📏 Con CALIBRA ONLY: {stats['with_calibra']}\n"
    preview_msg += f"📈 Percentuale: {stats['percentage']:.1f}%\n\n"
    preview_msg += "Procedere con la generazione?"
    
    from tkinter import messagebox as mb
    
    if parent:
        result = mb.askyesno("Anteprima MAIN", preview_msg, parent=parent)
    else:
        result = mb.askyesno("Anteprima MAIN", preview_msg)
    
    if not result:
        return False, "Generazione annullata"
    
    # Genera MAIN
    return genera_programma_main(df_macchina, nome_cartella, calibra_logic)
