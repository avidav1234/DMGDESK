"""
cimatron_query.py
=================
Compilato con PyInstaller + manifest CimAppAccess embedded.
Usa IAppAccess.GetActiveApplication() — stesso metodo di PCamCimatronMonitor.
"""

import sys

CIMATRON_PROGRAM = r"C:\Program Files\Cimatron\Cimatron\2025.0\Program"

def main():
    try:
        sys.path.insert(0, CIMATRON_PROGRAM)
        import clr
        clr.AddReference("interop.CimAppAccess")
        from interop.CimAppAccess import AppAccessClass

        appAccess = AppAccessClass()
        app = appAccess.GetActiveApplication()
        if app is None:
            print("")
            return

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
