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
        import win32com.client
        import pythoncom

        acc = CimAppAccess.AppAccess()
        app_com = acc.GetActiveApplication()

        if app_com is None:
            print("")
            return

        punk = Marshal.GetIUnknownForObject(app_com)
        ptr_int = int(str(punk))

        # Ottieni IDispatch
        idisp = pythoncom.ObjectFromAddress(ptr_int, pythoncom.IID_IDispatch)

        # Prova a ottenere i nomi dei metodi disponibili via IDispatch
        try:
            ti = idisp.GetTypeInfo()
            ta = ti.GetTypeAttr()
            sys.stderr.write(f"TypeAttr funcs: {ta[6]}\n")  # numero di funzioni
            for i in range(min(ta[6], 30)):
                try:
                    fd = ti.GetFuncDesc(i)
                    name = ti.GetNames(fd[0])[0]
                    sys.stderr.write(f"  func[{i}] id={fd[0]} name={name}\n")
                except:
                    pass
        except Exception as et:
            sys.stderr.write(f"TypeInfo fallito: {et}\n")

        # Prova accesso diretto per DISPID noti
        try:
            # DISPID_VALUE = 0, proviamo dispid comuni
            for dispid in [1, 2, 3, 4, 5, 100, 101]:
                try:
                    val = idisp.Invoke(dispid, 0x0409, pythoncom.DISPATCH_PROPERTYGET, 1)
                    sys.stderr.write(f"  DISPID {dispid} = {val}\n")
                except:
                    pass
        except Exception as ed:
            sys.stderr.write(f"Invoke test fallito: {ed}\n")

        print("")

    except Exception as e:
        sys.stderr.write(f"ERRORE: {type(e).__name__}: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
