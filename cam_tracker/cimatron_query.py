"""
cimatron_query.py
=================
Compilato con PyInstaller + manifest Cimatron.
Legge il path del documento attivo in Cimatron e lo stampa su stdout.
"""

import sys
from pathlib import Path

CIMATRON_PROGRAM = r"C:\Program Files\Cimatron\Cimatron\2025.0\Program"

def main():
    try:
        sys.path.insert(0, CIMATRON_PROGRAM)
        import clr
        clr.AddReference("interop.CimatronE")
        from interop.CimatronE import CimApplicationClass

        app = CimApplicationClass()
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
