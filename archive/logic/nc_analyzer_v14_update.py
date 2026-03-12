"""
NC Analyzer V14 - Genera MAIN con CALIBRA ONLY configurabile - FINALE
Versione FINALE con tutte le correzioni:
- CALIBRA_ONLY senza parametri T (solo testo "CALIBRA_ONLY")
- Logica conteggio richiami corretta
- Compatibile con calibra_only_logic_FINALE.py
"""

import os


def genera_programma_main_gcode_v14(program_paths, identificativo_testo, calibra_logic=None):
    """
    V14 CORRETTA: Genera MAIN con CALIBRA ONLY configurabile (5 modalità).
    
    Args:
        program_paths: Lista percorsi file NC
        identificativo_testo: Nome progetto
        calibra_logic: Istanza CalibraOnlyLogic (opzionale)
    
    Returns:
        tuple: (gcode_content, main_filename)
    """
    if not program_paths:
        return "; ERRORE: Nessun programma.", "ERROR_MAIN.MPF"
    
    # Importa logica CALIBRA ONLY
    if calibra_logic is None:
        try:
            from logic.calibra_only_logic import get_calibra_logic
            calibra_logic = get_calibra_logic()
        except:
            calibra_logic = None  # Fallback: nessun CALIBRA ONLY
    
    # Import estrazione utensili
    try:
        from logic.nc_analyzer import estrai_tutti_utensili_da_file
    except:
        # Fallback: definisci funzione base
        def estrai_tutti_utensili_da_file(file_path):
            """Estrae utensili da file NC."""
            import re
            utensili = []
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    for line in f:
                        # Cerca pattern T1 (ALIAS)
                        match = re.search(r'T(\d+)\s*\(([^)]+)\)', line)
                        if match:
                            posizione = match.group(1)
                            alias = match.group(2).strip()
                            utensili.append((alias, posizione, line.strip()))
            except:
                pass
            return utensili
    
    # Reset contatore richiami
    if calibra_logic:
        # Le impostazioni vengono ricaricate automaticamente ad ogni chiamata get_*()
        calibra_logic.reset_call_count()
    
    # Setup paths
    cleaned_id = identificativo_testo.strip().upper().replace(" ", "_").replace(".", "_")
    if not cleaned_id:
        cleaned_id = "MAIN_DEFAULT"
    
    main_file_name = f"0_MAIN_{cleaned_id}.MPF"
    wpd_folder_name = f"_N_{cleaned_id}_WPD"
    BASE_PATH = f"/_N_WKS_DIR/{wpd_folder_name}/"
    full_main_program_name = f"_N_{main_file_name.replace('.', '_')}"
    
    # Header
    gcode_output = f"; Main Program V14 - CALIBRA ONLY Configurabile\n"
    gcode_output += f"; Progetto: {cleaned_id}\n"
    
    if calibra_logic:
        mode_desc = calibra_logic.get_mode_description()
        gcode_output += f"; CALIBRA ONLY: {mode_desc}\n"
    
    gcode_output += f";{'-'*50}\n"
    gcode_output += f";EXTCALL (\"{BASE_PATH}{full_main_program_name}\")\n\n"
    
    # Analizza ogni file
    calibra_count = 0
    utensile_global_index = 0  # Contatore globale corretto
    
    for file_idx, file_path in enumerate(program_paths, 1):
        file_name_with_ext = os.path.basename(file_path)
        file_name_without_ext = os.path.splitext(file_name_with_ext)[0]
        program_name_to_call = f"_N_{file_name_without_ext}_MPF"
        extcall_path = f"\"{BASE_PATH}{program_name_to_call}\""
        
        # Estrai TUTTI gli utensili del file
        utensili_file = estrai_tutti_utensili_da_file(file_path)
        
        gcode_output += f"\n; ===== FILE {file_idx}: {file_name_with_ext} =====\n"
        
        if not utensili_file:
            gcode_output += f"; ATTENZIONE: Nessun utensile trovato\n"
            gcode_output += f"EXTCALL ({extcall_path})\n"
            gcode_output += f"IF _B_ERRNO <> 0 GOTOF FINE\n"
            gcode_output += f"STOPRE\n"
            continue
        
        gcode_output += f"; Utensili: {len(utensili_file)} cambi\n"
        
        # Processa PRIMO utensile del file
        primo_alias = utensili_file[0][0]
        primo_pos = utensili_file[0][1]
        
        # Determina se serve CALIBRA ONLY per primo utensile
        if calibra_logic:
            needs_calibra = calibra_logic.needs_calibra_only(
                primo_alias, 
                utensile_global_index,
                utensile_global_index + len(utensili_file)  # Total approssimato
            )
            
            if needs_calibra:
                gcode_output += f"\n; CALIBRA ONLY per {primo_alias}\n"
                gcode_output += f"CALIBRA_ONLY\n"
                calibra_count += 1
        
        utensile_global_index += 1  # Incrementa dopo primo utensile
        
        # Chiamata programma
        gcode_output += f"\n; Utensile principale: {primo_alias}\n"
        
        # Processa utensili INTERNI (se presenti)
        if len(utensili_file) > 1:
            altri_aliases = [u[0] for u in utensili_file[1:]]
            gcode_output += f"; + {len(utensili_file)-1} cambi interni: "
            gcode_output += ", ".join(altri_aliases[:3])
            if len(altri_aliases) > 3:
                gcode_output += f", ... +{len(altri_aliases)-3}"
            gcode_output += "\n"
            
            # IMPORTANTE: Processa TUTTI i cambi interni per conteggio
            for alias, pos, _ in utensili_file[1:]:
                if calibra_logic:
                    # Chiama needs_calibra_only per aggiornare contatore
                    # anche se non usiamo il risultato qui (cambio interno)
                    calibra_logic.needs_calibra_only(
                        alias,
                        utensile_global_index,
                        utensile_global_index + 1
                    )
                
                utensile_global_index += 1  # Incrementa per ogni cambio interno
        
        gcode_output += f"EXTCALL ({extcall_path})\n"
        gcode_output += f"IF _B_ERRNO <> 0 GOTOF FINE\n"
        gcode_output += f"STOPRE\n"
    
    # Footer statistiche
    gcode_output += f"\n; ===== STATISTICHE V14 =====\n"
    gcode_output += f"; TOTALE utensili processati: {utensile_global_index}\n"
    gcode_output += f"; CALIBRA ONLY inseriti: {calibra_count}\n"
    
    if calibra_logic:
        gcode_output += f"; Modalità: {calibra_logic.get_mode_description()}\n"
        
        # Mostra contatori interni
        mode = calibra_logic.get_current_mode()
        if mode in ['finitura_x', 'ogni_x']:
            gcode_output += f"; Contatori richiami:\n"
            for tool, count in sorted(calibra_logic.tool_call_count.items()):
                gcode_output += f";   {tool}: {count} richiami\n"
    
    gcode_output += f"; ============================\n"
    
    gcode_output += f"\nFINE:\n"
    gcode_output += f"M67\n"
    gcode_output += f"M30\n"
    
    return gcode_output, main_file_name
