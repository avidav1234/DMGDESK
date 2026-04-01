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
        import interop.CimatronE as CimatronE
        from System.Runtime.InteropServices import Marshal
        from System import Type

        acc = CimAppAccess.AppAccess()
        raw_app = acc.GetApplication()

        if raw_app is None:
            print("")
            return

        # Prova 1: QueryInterface diretto tramite pythonnet
        try:
            app = raw_app.__cast__(CimatronE.IApplication)
            doc = app.ActiveDocument
            print(str(doc.FullName) if doc else "")
            return
        except Exception as e1:
            sys.stderr.write(f"cast1 fallito: {e1}\n")

        # Prova 2: accesso diretto con InvokeMember via reflection
        try:
            t = Type.GetTypeFromProgID("CimatronE.Application")
            sys.stderr.write(f"ProgID type: {t}\n")
        except Exception as e2:
            sys.stderr.write(f"ProgID fallito: {e2}\n")

        # Prova 3: usa IAppAccess.GetActiveDocument direttamente
        try:
            sys.stderr.write(f"Metodi AppAccess: {[x for x in dir(acc) if not x.startswith('_')]}\n")
        except Exception as e3:
            sys.stderr.write(f"dir acc fallito: {e3}\n")

    except Exception as e:
        sys.stderr.write(f"ERRORE: {type(e).__name__}: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
