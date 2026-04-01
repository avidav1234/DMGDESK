"""
installa_avvio_automatico.py
=============================
Installa CAMTracker come task di Windows (Task Scheduler) su CAM35.
Eseguire UNA VOLTA con privilegi di amministratore:

    python installa_avvio_automatico.py

Il task si avvia automaticamente al login dell'utente corrente.
"""

import subprocess
import sys
import os
from pathlib import Path

TASK_NAME = "DMGDesk_CAMTracker"
SCRIPT    = Path(__file__).parent / "cam_tracker.py"
PYTHON    = sys.executable  # usa lo stesso python da cui si lancia lo script

def installa():
    # Verifica che lo script esista
    if not SCRIPT.exists():
        print(f"[ERRORE] Script non trovato: {SCRIPT}")
        sys.exit(1)

    # XML del task
    xml = f"""<?xml version="1.0" encoding="UTF-16"?>
<Task version="1.2" xmlns="http://schemas.microsoft.com/windows/2004/02/mit/task">
  <RegistrationInfo>
    <Description>DMGDesk CAMTracker — monitora Cimatron e invia ore a DMGDesk</Description>
  </RegistrationInfo>
  <Triggers>
    <LogonTrigger>
      <Enabled>true</Enabled>
      <Delay>PT30S</Delay>
    </LogonTrigger>
  </Triggers>
  <Principals>
    <Principal id="Author">
      <LogonType>InteractiveToken</LogonType>
      <RunLevel>LeastPrivilege</RunLevel>
    </Principal>
  </Principals>
  <Settings>
    <MultipleInstancesPolicy>IgnoreNew</MultipleInstancesPolicy>
    <DisallowStartIfOnBatteries>false</DisallowStartIfOnBatteries>
    <StopIfGoingOnBatteries>false</StopIfGoingOnBatteries>
    <ExecutionTimeLimit>PT0S</ExecutionTimeLimit>
    <RestartOnFailure>
      <Interval>PT1M</Interval>
      <Count>999</Count>
    </RestartOnFailure>
  </Settings>
  <Actions>
    <Exec>
      <Command>{PYTHON}</Command>
      <Arguments>"{SCRIPT}"</Arguments>
      <WorkingDirectory>{SCRIPT.parent}</WorkingDirectory>
    </Exec>
  </Actions>
</Task>"""

    xml_file = SCRIPT.parent / "_task_temp.xml"
    xml_file.write_text(xml, encoding="utf-16")

    try:
        # Elimina task esistente (ignora errore se non esiste)
        subprocess.run(
            ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
            capture_output=True
        )

        # Crea il nuovo task
        result = subprocess.run(
            ["schtasks", "/Create", "/TN", TASK_NAME, "/XML", str(xml_file), "/F"],
            capture_output=True, text=True
        )
        if result.returncode == 0:
            print(f"[OK] Task '{TASK_NAME}' installato con successo.")
            print(f"     Python: {PYTHON}")
            print(f"     Script: {SCRIPT}")
            print(f"\n     Il tracker partirà automaticamente al prossimo login.")
            print(f"     Per avviarlo subito:")
            print(f"       schtasks /Run /TN {TASK_NAME}")
        else:
            print(f"[ERRORE] schtasks: {result.stderr}")
    finally:
        xml_file.unlink(missing_ok=True)


def rimuovi():
    result = subprocess.run(
        ["schtasks", "/Delete", "/TN", TASK_NAME, "/F"],
        capture_output=True, text=True
    )
    if result.returncode == 0:
        print(f"[OK] Task '{TASK_NAME}' rimosso.")
    else:
        print(f"[ERRORE] {result.stderr}")


if __name__ == "__main__":
    if "--rimuovi" in sys.argv:
        rimuovi()
    else:
        installa()
