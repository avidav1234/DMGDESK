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
        import interop.CimAppAccess as CimAppAccess
        from System.Runtime.InteropServices import Marshal

        acc = CimAppAccess.AppAccess()
        app = acc.GetActiveApplication()

        if app is None:
            print("")
            return

        # Ottieni il puntatore IUnknown e convertilo in IDispatch via win32com
        punk = Marshal.GetIUnknownForObject(app)
        sys.stderr.write(f"IUnknown ptr: {punk}\n")

        import win32com.client
        import pythoncom

        # Converti IUnknown pointer in oggetto win32com Dispatch
        ptr_int = int(str(punk))
        disp = win32com.client.Dispatch(
            pythoncom.ObjectFromAddress(ptr_int, pythoncom.IID_IDispatch)
        )
        sys.stderr.write(f"win32com disp: {disp}\n")

        doc = disp.ActiveDocument
        if doc:
            print(str(doc.FullName))
        else:
            print("")

    except Exception as e:
        sys.stderr.write(f"ERRORE: {type(e).__name__}: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
