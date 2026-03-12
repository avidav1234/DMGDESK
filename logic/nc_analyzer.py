# cnc_analyzer_v12.py - Analisi MULTIPLI utensili per programma
# ToolManager V12 - Gestione utensili/holder smontati + cambio impiego frese FF

import re
import os
import pandas as pd
from datetime import datetime

try:
    from utils.logger import get_logger
    _log = get_logger(__name__)
except ImportError:
    import logging
    _log = logging.getLogger(__name__)

# Import da architettura modulare
try:
    from config.constants import STATO_IN_MACCHINA
except ImportError:
    # Fallback per compatibilità
    STATO_IN_MACCHINA = "IN_MACCHINA"

# ============= CONFIGURAZIONE CALIBRAZIONE =============
class CalibrationLogic:
    """Gestione logica calibrazione per generazione G-code"""
    
    def __init__(self):
        self.prefissi_finitura = ['FF', 'FFPI']
        self.contatore_cambi_standard = 0
        self.contatore_programmi_finitura = 0
        self.ultimo_utensile = None
        self.ultimo_tipo = None
        self.soglia_cambi_standard = 3
        self.soglia_programmi_finitura = 3
        self.log_calibrazioni = []
    
    def classifica_utensile(self, alias):
        """Classifica utensile come FINITURA o STANDARD"""
        if not alias:
            return 'STANDARD'
        alias_upper = str(alias).upper().strip()
        for prefisso in self.prefissi_finitura:
            if alias_upper.startswith(prefisso):
                return 'FINITURA'
        return 'STANDARD'
    
    def necessita_calibrazione(self, utensile_corrente, nuovo_programma=True):
        """
        Determina se serve calibrazione basandosi sulla logica V10
        """
        if not utensile_corrente:
            return False, "Nessun utensile"
        
        tipo_corrente = self.classifica_utensile(utensile_corrente)
        cambio_utensile = (self.ultimo_utensile is not None and
                          utensile_corrente != self.ultimo_utensile)
        
        calibra = False
        motivo = ""
        
        if tipo_corrente == 'FINITURA':
            if cambio_utensile:
                calibra = True
                motivo = f"Finitura - Cambio da {self.ultimo_utensile} a {utensile_corrente}"
                self.contatore_programmi_finitura = 0
            elif nuovo_programma:
                self.contatore_programmi_finitura += 1
                if self.contatore_programmi_finitura >= self.soglia_programmi_finitura:
                    calibra = True
                    motivo = f"Finitura - Dopo {self.contatore_programmi_finitura} programmi"
                    self.contatore_programmi_finitura = 0
            if self.ultimo_utensile is None:
                calibra = True
                motivo = f"Finitura - Primo: {utensile_corrente}"
        else:
            if cambio_utensile or self.ultimo_utensile is None:
                self.contatore_cambi_standard += 1
                if self.contatore_cambi_standard >= self.soglia_cambi_standard:
                    calibra = True
                    motivo = f"Standard - {self.contatore_cambi_standard} cambi"
                    self.contatore_cambi_standard = 0
                else:
                    motivo = f"Standard - Cambio {self.contatore_cambi_standard}/{self.soglia_cambi_standard}"
            if self.ultimo_utensile is None and not calibra:
                self.contatore_cambi_standard = 1
                motivo = f"Standard - Primo ({self.contatore_cambi_standard}/{self.soglia_cambi_standard})"
        
        self.ultimo_utensile = utensile_corrente
        self.ultimo_tipo = tipo_corrente
        
        if calibra:
            self.log_calibrazioni.append({
                'utensile': utensile_corrente,
                'tipo': tipo_corrente,
                'motivo': motivo,
                'timestamp': datetime.now().isoformat()
            })
        
        return calibra, motivo
    
    def get_statistiche(self):
        """Ritorna statistiche calibrazioni"""
        return {
            'totale_calibrazioni': len(self.log_calibrazioni),
            'contatore_cambi_standard': self.contatore_cambi_standard,
            'contatore_programmi_finitura': self.contatore_programmi_finitura,
            'ultimo_utensile': self.ultimo_utensile,
            'ultimo_tipo': self.ultimo_tipo
        }


# ============= NUOVE FUNZIONI MULTI-UTENSILE =============

def estrai_tutti_utensili_da_file(file_path):
    """
    🆕 V11: Estrae TUTTI gli utensili da un file in ORDINE di apparizione.
    
    Returns: list di tuple [(alias, riga_numero, riga_testo), ...]
    """
    pattern_t_alias = re.compile(r'T\s*=\s*[\"\']?([A-Z0-9.\-_\s]+)[\"\']?', re.IGNORECASE)
    utensili_trovati = []
    
    try:
        with open(file_path, 'r', errors='ignore') as f:
            righe = f.readlines()
            
            last_alias_match = None
            last_alias_line_index = -1
            last_riga_testo = ""
            
            for i in range(len(righe)):
                riga_corrente = righe[i].strip().upper()
                
                match = pattern_t_alias.search(riga_corrente)
                
                if match:
                    alias = match.group(1).strip()
                    if alias:
                        last_alias_match = alias
                        last_alias_line_index = i
                        last_riga_testo = righe[i].strip()
                        
                # Cerca M6 nelle successive 5 righe
                if last_alias_match and (i - last_alias_line_index) < 5:
                    if 'M6' in riga_corrente.replace('M06', 'M6'):
                        utensili_trovati.append((
                            last_alias_match.upper(),
                            last_alias_line_index + 1,  # Numero riga (1-indexed)
                            last_riga_testo
                        ))
                        last_alias_match = None
                        
    except Exception as e:
        print(f"Errore estrazione utensili da {os.path.basename(file_path)}: {e}")
    
    return utensili_trovati


def estrai_utensile_da_file(file_path):
    """
    LEGACY: Mantiene compatibilità - ritorna PRIMO utensile.
    Usa estrai_tutti_utensili_da_file per lista completa.
    """
    utensili = estrai_tutti_utensili_da_file(file_path)
    return utensili[0][0] if utensili else None


def confronta_utensili_logica(df_macchina, file_percorsi):
    """
    🆕 V11: Estrae TUTTI gli alias da TUTTI i file e confronta con macchina.
    
    Returns: (utensili_richiesti_set, utensili_mancanti_report)
    """
    if 'Stato_Utensile' in df_macchina.columns:
        df_in_macchina = df_macchina[df_macchina['Stato_Utensile'] == STATO_IN_MACCHINA].copy()
    else:
        df_in_macchina = df_macchina.copy()
        
    utensili_in_macchina = set(df_in_macchina['Alias'].astype(str).str.upper().tolist())
    
    # Dizionario: {Alias: [(file_name, riga_num, riga_testo), ...]}
    utensili_richiesti_dettaglio = {}
    
    for file_path in file_percorsi:
        file_name = os.path.basename(file_path)
        utensili_file = estrai_tutti_utensili_da_file(file_path)
        
        for alias, riga_num, riga_testo in utensili_file:
            if alias not in utensili_richiesti_dettaglio:
                utensili_richiesti_dettaglio[alias] = []
            utensili_richiesti_dettaglio[alias].append((file_name, riga_num, riga_testo))
    
    utensili_richiesti = set(utensili_richiesti_dettaglio.keys())
    utensili_mancanti = utensili_richiesti - utensili_in_macchina
    
    utensili_mancanti_report = []
    for alias in sorted(list(utensili_mancanti)):
        # Prende primo riferimento per ogni alias mancante
        file_richiedente, riga_num, riga_esempio = utensili_richiesti_dettaglio[alias][0]
        utensili_mancanti_report.append((alias, file_richiedente, riga_esempio))
    
    return utensili_richiesti, utensili_mancanti_report


def analizza_dettaglio_file(file_path):
    """
    🆕 V11: Analizza un singolo file e ritorna info dettagliate.
    
    Returns: {
        'file': str,
        'totale_utensili': int,
        'utensili': [{'alias', 'riga', 'tipo'}, ...],
        'utensili_unici': set
    }
    """
    file_name = os.path.basename(file_path)
    utensili_raw = estrai_tutti_utensili_da_file(file_path)
    
    calibration = CalibrationLogic()
    utensili_dettaglio = []
    utensili_unici = set()
    
    for alias, riga_num, riga_testo in utensili_raw:
        tipo = calibration.classifica_utensile(alias)
        utensili_dettaglio.append({
            'alias': alias,
            'riga': riga_num,
            'tipo': tipo
        })
        utensili_unici.add(alias)
    
    return {
        'file': file_name,
        'totale_utensili': len(utensili_raw),
        'utensili_unici': len(utensili_unici),
        'utensili': utensili_dettaglio,
        'set_unici': utensili_unici
    }


def genera_report_dettaglio_multiprogrammi(file_percorsi):
    """
    🆕 V11: Report dettagliato con TUTTI gli utensili per ogni file.
    """
    report = "="*80 + "\n"
    report += "REPORT ANALISI UTENSILI V11 - MULTI-UTENSILE PER FILE\n"
    report += "="*80 + "\n\n"
    
    totale_files = len(file_percorsi)
    totale_cambi = 0
    totale_utensili_unici_globali = set()
    
    for idx, file_path in enumerate(file_percorsi, 1):
        analisi = analizza_dettaglio_file(file_path)
        
        report += f"\n{idx}. FILE: {analisi['file']}\n"
        report += "-"*80 + "\n"
        report += f"   Cambi utensile: {analisi['totale_utensili']}\n"
        report += f"   Utensili unici: {analisi['utensili_unici']}\n\n"
        
        report += "   Sequenza cambi:\n"
        for i, ut in enumerate(analisi['utensili'], 1):
            report += f"      {i:2}. Riga {ut['riga']:5} | {ut['alias']:30} | {ut['tipo']}\n"
        
        totale_cambi += analisi['totale_utensili']
        totale_utensili_unici_globali.update(analisi['set_unici'])
    
    report += "\n" + "="*80 + "\n"
    report += "TOTALI:\n"
    report += f"  - File analizzati: {totale_files}\n"
    report += f"  - Cambi utensile totali: {totale_cambi}\n"
    report += f"  - Utensili unici totali: {len(totale_utensili_unici_globali)}\n"
    report += "="*80 + "\n\n"
    
    report += "UTENSILI UNICI:\n"
    for ut in sorted(totale_utensili_unici_globali):
        report += f"  - {ut}\n"
    
    return report


# ============= GENERAZIONE MAIN CON MULTI-UTENSILE =============

def genera_programma_main_gcode(program_paths, identificativo_testo):
    """
    🆕 V11: Genera MAIN considerando MULTIPLI utensili per file.
    Calibrazione basata su SEQUENZA COMPLETA di tutti gli utensili.
    """
    if not program_paths:
        return "; ERRORE: Nessun programma.", "ERROR_MAIN.MPF"

    calibration = CalibrationLogic()
    
    cleaned_id = identificativo_testo.strip().upper().replace(" ", "_").replace(".", "_")
    if not cleaned_id:
        cleaned_id = "MAIN_DEFAULT"
    
    main_file_name = f"0_MAIN_{cleaned_id}.MPF"
    wpd_folder_name = f"_N_{cleaned_id}_WPD"
    BASE_PATH = f"/_N_WKS_DIR/{wpd_folder_name}/"
    full_main_program_name = f"_N_{main_file_name.replace('.', '_')}"

    gcode_output = f"; Main Program V11 - Multi-Utensile per File\n"
    gcode_output += f"; Progetto: {cleaned_id}\n"
    gcode_output += f"; Logica: Traccia TUTTI gli utensili in OGNI file\n"
    gcode_output += f";{'-'*50}\n"
    gcode_output += f";EXTCALL (\"{BASE_PATH}{full_main_program_name}\")\n\n"
    
    # Calibrazione iniziale
    gcode_output += f"; ===== CALIBRAZIONE INIZIALE =====\n"
    gcode_output += f"CALIBRA_ONLY\n\n"
    
    # 🔧 V12 FIX: Traccia che abbiamo fatto calibrazione iniziale
    calibrazione_iniziale_fatta = True
    ultima_calibrazione_idx = -1  # Traccia l'ultimo file dove abbiamo calibrato
    
    # Analizza ogni file
    for idx, file_path in enumerate(program_paths, 1):
        file_name_with_ext = os.path.basename(file_path)
        file_name_without_ext = os.path.splitext(file_name_with_ext)[0]
        program_name_to_call = f"_N_{file_name_without_ext}_MPF"
        extcall_path = f"\"{BASE_PATH}{program_name_to_call}\""
        
        # Estrai TUTTI gli utensili del file
        utensili_file = estrai_tutti_utensili_da_file(file_path)
        
        gcode_output += f"\n; ===== FILE {idx}: {file_name_with_ext} =====\n"
        
        if not utensili_file:
            gcode_output += f"; ATTENZIONE: Nessun utensile trovato\n"
            gcode_output += f"EXTCALL ({extcall_path})\n"
            gcode_output += f"IF _B_ERRNO <> 0 GOTOF FINE\n"
            gcode_output += f"STOPRE\n"
            continue
        
        gcode_output += f"; Utensili: {len(utensili_file)} cambi\n"
        
        # Primo utensile del file
        primo_alias = utensili_file[0][0]
        necessita, motivo = calibration.necessita_calibrazione(primo_alias, nuovo_programma=True)
        
        # 🔧 V12 FIX ROBUSTO: Anti-duplicato CALIBRA_ONLY
        # NON generare CALIBRA_ONLY se:
        # 1. È il primo file E abbiamo già fatto calibrazione iniziale
        # 2. Abbiamo appena fatto calibrazione nel file precedente (ultima_calibrazione_idx == idx-1)
        dovrebbe_calibrare = (
            necessita and 
            not (idx == 1 and calibrazione_iniziale_fatta) and
            not (ultima_calibrazione_idx == idx - 1)
        )
        
        if dovrebbe_calibrare:
            gcode_output += f"\n; {motivo}\n"
            gcode_output += f"CALIBRA_ONLY\n"
            ultima_calibrazione_idx = idx  # Aggiorna ultima calibrazione
        
        # Chiamata programma
        tipo_primo = calibration.classifica_utensile(primo_alias)
        gcode_output += f"\n; Utensile principale: {primo_alias} ({tipo_primo})\n"
        
        # Mostra tutti gli utensili del file nel commento
        if len(utensili_file) > 1:
            gcode_output += f"; + {len(utensili_file)-1} cambi interni: "
            altri = [u[0] for u in utensili_file[1:]]
            gcode_output += ", ".join(altri[:3])  # Max 3 per leggibilità
            if len(altri) > 3:
                gcode_output += f", ... +{len(altri)-3}"
            gcode_output += "\n"
        
        gcode_output += f"EXTCALL ({extcall_path})\n"
        gcode_output += f"IF _B_ERRNO <> 0 GOTOF FINE\n"
        gcode_output += f"STOPRE\n"
        
        # Traccia cambi interni per calibrazioni successive
        if len(utensili_file) > 1:
            for alias, _, _ in utensili_file[1:]:
                calibration.necessita_calibrazione(alias, nuovo_programma=False)
    
    # Footer statistiche
    stats = calibration.get_statistiche()
    totale_calibrazioni = stats['totale_calibrazioni'] + 1
    
    gcode_output += f"\n; ===== STATISTICHE V11 =====\n"
    gcode_output += f"; TOTALE calibrazioni: {totale_calibrazioni}\n"
    gcode_output += f"; Standard: {stats['contatore_cambi_standard']}/{calibration.soglia_cambi_standard}\n"
    gcode_output += f"; Finitura: {stats['contatore_programmi_finitura']}/{calibration.soglia_programmi_finitura}\n"
    gcode_output += f"; ============================\n"
    
    gcode_output += f"\nFINE:\n"
    gcode_output += f"M67\n"
    gcode_output += f"M30\n"
    
    return gcode_output, main_file_name


# ============= ANALISI SEQUENZA COMPLETA =============

def analizza_sequenza_completa_utensili(program_paths):
    """
    🆕 V11: Analizza sequenza COMPLETA di tutti gli utensili in tutti i file.
    """
    calibration = CalibrationLogic()
    risultati = []
    
    for file_path in program_paths:
        file_name = os.path.basename(file_path)
        utensili_file = estrai_tutti_utensili_da_file(file_path)
        
        if not utensili_file:
            risultati.append({
                'file': file_name,
                'utensile': 'N/A',
                'tipo': 'N/A',
                'calibra': 'NO',
                'motivo': 'Nessun utensile',
                'cambi_interni': 0
            })
            continue
        
        # Primo utensile
        primo_alias = utensili_file[0][0]
        necessita, motivo = calibration.necessita_calibrazione(primo_alias, True)
        tipo = calibration.classifica_utensile(primo_alias)
        
        risultati.append({
            'file': file_name,
            'utensile': primo_alias,
            'tipo': tipo,
            'calibra': 'SÌ' if necessita else 'NO',
            'motivo': motivo,
            'cambi_interni': len(utensili_file) - 1
        })
        
        # Traccia cambi interni
        for alias, _, _ in utensili_file[1:]:
            calibration.necessita_calibrazione(alias, False)
    
    return risultati


def genera_report_calibrazione(program_paths):
    """
    🆕 V11: Report calibrazione con analisi multi-utensile.
    """
    analisi = analizza_sequenza_completa_utensili(program_paths)
    
    report = "REPORT CALIBRAZIONE V11 - MULTI-UTENSILE\n"
    report += "="*80 + "\n\n"
    
    totale_files = len(analisi)
    totale_calibrazioni_durante = sum(1 for a in analisi if a['calibra'] == 'SÌ')
    totale_calibrazioni = totale_calibrazioni_durante + 1
    totale_cambi_interni = sum(a['cambi_interni'] for a in analisi)
    
    report += f"RIEPILOGO:\n"
    report += f"  - File analizzati: {totale_files}\n"
    report += f"  - Calibrazione iniziale: 1\n"
    report += f"  - Calibrazioni durante: {totale_calibrazioni_durante}\n"
    report += f"  - TOTALE calibrazioni: {totale_calibrazioni}\n"
    report += f"  - Cambi utensile interni: {totale_cambi_interni}\n\n"
    
    report += "DETTAGLIO:\n"
    report += "-"*80 + "\n"
    report += "  0. CALIBRAZIONE INIZIALE - Obbligatoria\n"
    report += "-"*80 + "\n"
    
    for idx, info in enumerate(analisi, 1):
        report += f"{idx:3}. {info['file']:<40}\n"
        report += f"     Utensile: {info['utensile']:<25} Tipo: {info['tipo']:<10}\n"
        report += f"     Calibra: {info['calibra']:<3} - {info['motivo']}\n"
        if info['cambi_interni'] > 0:
            report += f"     ⚠️  +{info['cambi_interni']} cambi interni nel file\n"
        report += "-"*80 + "\n"
    
    tempo_risparmiato = (totale_files + 1 - totale_calibrazioni) * 2
    report += f"\nTEMPO RISPARMIATO: ~{tempo_risparmiato} minuti\n"
    
    return report
