"""
cimatron_query.py — Legge ActiveDocument.FullName da Cimatron in esecuzione.
Compilare con: pyinstaller cimatron_query.py -F -m cimatron_query.manifest
               --distpath .
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

        # Metodo ufficiale Cimatron API docs
        aCimAppAccess = CimAppAccess.AppAccess()
        aCimApp = CimatronE.IApplication(aCimAppAccess.GetApplication())

        if aCimApp is None:
            print("")
            return

        doc = aCimApp.ActiveDocument
        if doc:
            print(str(doc.FullName))
        else:
            print("")

    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
