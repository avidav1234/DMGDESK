"""
cimatron_query.py — Legge ActiveDocument.FullName da Cimatron in esecuzione.
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

        acc = CimAppAccess.AppAccess()

        # GetActiveApplication = aggancia istanza già in esecuzione
        app = acc.GetActiveApplication()
        sys.stderr.write(f"GetActiveApplication: {app}\n")
        sys.stderr.write(f"type: {type(app)}\n")

        if app is None:
            sys.stderr.write("Cimatron non in esecuzione\n")
            print("")
            return

        members = [x for x in dir(app) if not x.startswith('_')]
        sys.stderr.write(f"Metodi app: {members}\n")
        sys.stderr.flush()

        # Prova accesso documento
        for name in ['ActiveDocument', 'GetActiveDocument', 'Documents',
                     'ActiveDoc', 'OpenDocuments', 'GetDocument', 'ActivePart']:
            if hasattr(app, name):
                try:
                    val = getattr(app, name)
                    sys.stderr.write(f"  {name} = {val}\n")
                    if val and hasattr(val, 'FullName'):
                        print(str(val.FullName))
                        return
                except Exception as ex:
                    sys.stderr.write(f"  {name} errore: {ex}\n")

        print("")

    except Exception as e:
        sys.stderr.write(f"ERRORE: {type(e).__name__}: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
