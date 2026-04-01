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
        import pythoncom

        acc = CimAppAccess.AppAccess()
        app_com = acc.GetActiveApplication()

        if app_com is None:
            print("")
            return

        punk = Marshal.GetIUnknownForObject(app_com)
        idisp = pythoncom.ObjectFromAddress(int(str(punk)), pythoncom.IID_IDispatch)

        # DISPID=2 → GetActiveDoc
        doc_com = idisp.Invoke(2, 0x0409, pythoncom.DISPATCH_METHOD, 1)
        sys.stderr.write(f"GetActiveDoc: {doc_com}\n")

        if doc_com is None:
            print("")
            return

        # Ora ottieni i metodi del documento
        try:
            ti = doc_com.GetTypeInfo()
            ta = ti.GetTypeAttr()
            sys.stderr.write(f"Doc funcs: {ta[6]}\n")
            for i in range(min(ta[6], 20)):
                try:
                    fd = ti.GetFuncDesc(i)
                    name = ti.GetNames(fd[0])[0]
                    sys.stderr.write(f"  doc func[{i}] id={fd[0]} name={name}\n")
                except:
                    pass
        except Exception as et:
            sys.stderr.write(f"Doc TypeInfo: {et}\n")

        print("")

    except Exception as e:
        sys.stderr.write(f"ERRORE: {type(e).__name__}: {e}\n")
        sys.exit(1)

if __name__ == "__main__":
    main()
