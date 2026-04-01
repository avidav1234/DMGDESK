"""
cimatron_query.py — Legge il path del documento attivo in Cimatron.
Compilare con: pyinstaller cimatron_query.py -F --manifest=cimatron_query.manifest --distpath .
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
        import pythoncom

        acc = CimAppAccess.AppAccess()
        app_com = acc.GetActiveApplication()
        if app_com is None:
            print("")
            return

        punk = Marshal.GetIUnknownForObject(app_com)
        idisp = pythoncom.ObjectFromAddress(int(str(punk)), pythoncom.IID_IDispatch)

        # DISPID=2 → GetActiveDoc
        doc_unk = idisp.Invoke(2, 0x0409, pythoncom.DISPATCH_METHOD, 1)
        if doc_unk is None:
            print("")
            return

        # QI IUnknown → IDispatch
        doc_disp = doc_unk.QueryInterface(pythoncom.IID_IDispatch)

        # DISPID=15 → GetPath
        path = doc_disp.Invoke(15, 0x0409, pythoncom.DISPATCH_METHOD, 1)
        print(str(path) if path else "")

    except Exception as e:
        sys.stderr.write(f"ERROR: {type(e).__name__}: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
