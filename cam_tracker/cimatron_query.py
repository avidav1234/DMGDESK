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

        acc = CimAppAccess.AppAccess()
        raw_app = acc.GetApplication()

        if raw_app is None:
            print("")
            return

        # Cast esplicito da ComObject a IApplication
        app = Marshal.GetTypedObjectForIUnknown(
            Marshal.GetIUnknownForObject(raw_app),
            CimatronE.IApplication
        )

        sys.stderr.write(f"IApplication ottenuto: {app}\n")
        sys.stderr.write(f"Metodi: {[x for x in dir(app) if not x.startswith('_')]}\n")
        sys.stderr.flush()

        doc = app.ActiveDocument
        if doc:
            print(str(doc.FullName))
        else:
            print("")

    except Exception as e:
        sys.stderr.write(f"ERRORE: {type(e).__name__}: {e}\n")
        sys.stderr.flush()
        sys.exit(1)

if __name__ == "__main__":
    main()
