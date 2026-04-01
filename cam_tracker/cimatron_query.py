"""
cimatron_query.py — Legge ActiveDocument.FullName da Cimatron in esecuzione.
Compilare con: pyinstaller cimatron_query.py -F --manifest=cimatron_query.manifest --distpath .
"""

import sys

CIMATRON_PROGRAM = r"C:\Program Files\Cimatron\Cimatron\2025.0\Program"

def main():
    try:
        sys.path.insert(0, CIMATRON_PROGRAM)
        import clr
        clr.AddReference("interop.CimAppAccess")
        clr.AddReference("interop.CimatronE")
        import interop.CimAppAccess as CimAppAccess
        import interop.CimatronE as CimatronE

        acc = CimAppAccess.AppAccess()
        raw_app = acc.GetApplication()

        if raw_app is None:
            print("")
            return

        # Ispeziona i metodi disponibili
        members = [x for x in dir(raw_app) if not x.startswith('_')]
        print(f"DEBUG members: {members}", file=sys.stderr)

        # Cerca metodo per documento attivo
        for name in ['ActiveDocument', 'GetActiveDocument', 'Documents',
                     'ActiveDoc', 'OpenDocuments', 'GetDocument']:
            if hasattr(raw_app, name):
                val = getattr(raw_app, name)
                print(f"DEBUG {name} = {val}", file=sys.stderr)

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
