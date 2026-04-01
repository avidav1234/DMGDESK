"""
cimatron_query.py
=================
Compilato con PyInstaller + manifest Cimatron.
Legge il path del documento attivo in Cimatron e lo stampa su stdout.
Il cam_tracker.py lo lancia come subprocess e legge l'output.

Output (una riga):
  - path completo se documento aperto: C:\Lavoro\4348\P0221\file.elt
  - stringa vuota se nessun documento
  - "ERROR: <messaggio>" in caso di errore
"""

import sys
from pathlib import Path

CIMATRON_PROGRAM = r"C:\Program Files\Cimatron\Cimatron\2025.0\Program"

def main():
    try:
        sys.path.insert(0, CIMATRON_PROGRAM)
        import clr
        clr.AddReference("interop.CimatronE")
        import CimatronE

        app = CimatronE.Application()
        doc = app.ActiveDocument
        if doc:
            print(str(doc.FullName))
        else:
            print("")
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
