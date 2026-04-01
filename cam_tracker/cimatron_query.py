"""
cimatron_query.py — Debug versione
"""

import sys

CIMATRON_PROGRAM = r"C:\Program Files\Cimatron\Cimatron\2025.0\Program"

def main():
    sys.stderr.write("cimatron_query avviato\n")
    sys.stderr.flush()
    try:
        sys.path.insert(0, CIMATRON_PROGRAM)
        import clr
        sys.stderr.write("clr importato\n")
        sys.stderr.flush()

        clr.AddReference("interop.CimAppAccess")
        clr.AddReference("interop.CimatronE")
        import interop.CimAppAccess as CimAppAccess
        import interop.CimatronE as CimatronE
        sys.stderr.write("DLL caricate\n")
        sys.stderr.flush()

        acc = CimAppAccess.AppAccess()
        sys.stderr.write(f"AppAccess creato: {acc}\n")
        sys.stderr.flush()

        raw_app = acc.GetApplication()
        sys.stderr.write(f"GetApplication: {raw_app}\n")
        sys.stderr.flush()

        if raw_app is None:
            sys.stderr.write("Cimatron non in esecuzione\n")
            print("")
            return

        members = [x for x in dir(raw_app) if not x.startswith('_')]
        sys.stderr.write(f"Metodi: {members}\n")
        sys.stderr.flush()

    except Exception as e:
        sys.stderr.write(f"ECCEZIONE: {type(e).__name__}: {e}\n")
        sys.stderr.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()
