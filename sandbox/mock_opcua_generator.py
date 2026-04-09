"""
sandbox/mock_opcua_generator.py
================================
Simula MchnSrv.exe — aggiorna OpcUaLegacy.log ogni 10 secondi
con stati macchina realistici. Permette di testare macchina_live.py
senza essere connessi alla macchina reale.

Uso:
    python sandbox/mock_opcua_generator.py
    (lasciare girare in background mentre si testa)
"""

import time, random, os
from pathlib import Path
from datetime import datetime

LOG_PATH = Path(__file__).parent / "data" / "OpcUaLegacy.log"

UTENSILI = [
    "FS16R2L80F100E4", "FS10R0.5L50E3", "FF6R3L30F35G1",
    "FS25R2L100F150E6", "FF10R0.5L60E3", "CENTRINO-8-F50E3",
]

PROGRAMMI = [
    "/_N_WKS_DIR/_N_SANDBOX_4201_WPD/_N_SANDBOX_4201_01_001_MPF",
    "/_N_WKS_DIR/_N_SANDBOX_4201_WPD/_N_SANDBOX_4201_01_002_MPF",
    "/_N_WKS_DIR/_N_SANDBOX_4202_WPD/_N_SANDBOX_4202_02_001_MPF",
]

# Sequenza stati simulata: la macchina lavora, si ferma, riprende
SEQUENZA_STATI = [
    # (progStatus, durata_sec, descrizione)
    (1, 30, "esecuzione"),
    (1, 30, "esecuzione"),
    (1, 30, "esecuzione"),
    (5, 15, "stop M0"),
    (1, 30, "esecuzione"),
    (1, 30, "esecuzione"),
    (0, 20, "reset"),
    (1, 30, "esecuzione"),
    (1, 30, "esecuzione"),
    (1, 30, "esecuzione"),
    (5, 10, "pausa"),
    (1, 30, "esecuzione"),
]

def scrivi_log(utensile, programma, prog_status, feed, speed):
    t = datetime.now().strftime("%m/%d/%y %H:%M:%S")
    lines = [
        f"T {t} MchnSrv: ReadPlVar: VarName= actToolIdent; read Value= {utensile}\n",
        f"T {t} MchnSrv: ReadPlVar: VarName= workPandProgName; read Value= {programma}\n",
        f"T {t} MchnSrv: ReadPlVar: VarName= progStatus; read Value= {prog_status}\n",
        f"T {t} MchnSrv: ReadPlVar: VarName= actFeedRate; read Value= {feed}\n",
        f"T {t} MchnSrv: ReadPlVar: VarName= actSpeedRate; read Value= {speed}\n",
        f"T {t} MchnSrv: ReadPlVar: VarName= $A_DBB[67]; read Value= {random.randint(1,6)}\n",
    ]
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    LOG_PATH.write_text("".join(lines), encoding="utf-8")

def main():
    print(f"[MockOpcUa] Avvio simulatore macchina → {LOG_PATH}")
    print("[MockOpcUa] Ctrl+C per fermare\n")

    utensile = random.choice(UTENSILI)
    programma = random.choice(PROGRAMMI)
    idx = 0

    while True:
        stato, durata, desc = SEQUENZA_STATI[idx % len(SEQUENZA_STATI)]

        # Cambia utensile ogni tot cicli
        if idx % 7 == 0:
            utensile = random.choice(UTENSILI)
            programma = random.choice(PROGRAMMI)

        feed  = random.randint(300, 800) if stato in (1, 3) else 0
        speed = random.randint(3000, 12000) if stato in (1, 3) else 0

        scrivi_log(utensile, programma, stato, feed, speed)
        print(f"[MockOpcUa] stato={stato} ({desc:12s}) | {utensile[:20]:20s} | F={feed} S={speed}")

        time.sleep(10)
        idx += 1

if __name__ == "__main__":
    main()
