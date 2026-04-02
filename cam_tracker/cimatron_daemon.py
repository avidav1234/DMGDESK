"""
cimatron_daemon.py — Daemon persistente per interrogare Cimatron.

Rimane aperto dopo il primo avvio, carica le DLL COM una sola volta,
e risponde alle query tramite stdin/stdout.

Protocollo:
  stdin  → "?\n"        richiedi path documento attivo
  stdout → "PATH\n"     path completo del documento (o stringa vuota)
  stdout → "ERROR:...\n" errore (Cimatron chiuso, documento non aperto, ecc.)
  stdout → "READY\n"    segnale di avvio — daemon pronto

Compilare con:
  pyinstaller cimatron_daemon.py -F -m cimatron_query.manifest --distpath . --noconfirm

Oppure eseguire direttamente:
  python cimatron_daemon.py
"""

import sys
import os
import time

CIMATRON_PROGRAM = r"C:\Program Files\Cimatron\Cimatron\2025.0\Program"

def stderr(msg: str):
    sys.stderr.write(msg + "\n")
    sys.stderr.flush()

def stdout(msg: str):
    sys.stdout.write(msg + "\n")
    sys.stdout.flush()


def main():
    # Configura stdout in modalità non-bufferizzata
    sys.stdout.reconfigure(line_buffering=True)
    sys.stdin.reconfigure(line_buffering=True)

    # Carica le DLL Cimatron una sola volta
    try:
        sys.path.insert(0, CIMATRON_PROGRAM)
        import clr
        clr.AddReference("interop.CimAppAccess")
        import interop.CimAppAccess as CimAppAccess
        from System.Runtime.InteropServices import Marshal
        import pythoncom

        stderr("[Daemon] DLL Cimatron caricate")
    except Exception as e:
        stdout(f"ERROR:init:{e}")
        # Fallback: rimani aperto ma rispondi sempre ERROR
        # Il tracker gestirà questo come "nessun progetto"
        while True:
            line = sys.stdin.readline()
            if not line or line.strip() == "exit":
                break
            stdout(f"ERROR:no_dll:{e}")
        return

    stdout("READY")
    sys.stdout.flush()
    stderr("[Daemon] Pronto — in attesa di query")

    # Cache dell'oggetto AppAccess — evita di ricreare ogni volta
    _acc = None
    _last_path = ""
    _consecutive_errors = 0

    def get_path() -> str:
        nonlocal _acc, _consecutive_errors

        try:
            # Ricrea AppAccess se necessario
            if _acc is None:
                _acc = CimAppAccess.AppAccess()

            app_com = _acc.GetActiveApplication()
            if app_com is None:
                _consecutive_errors += 1
                _acc = None  # forza ricreazione al prossimo tick
                return ""

            punk = Marshal.GetIUnknownForObject(app_com)
            idisp = pythoncom.ObjectFromAddress(int(str(punk)), pythoncom.IID_IDispatch)

            # DISPID=2 → GetActiveDoc
            doc_unk = idisp.Invoke(2, 0x0409, pythoncom.DISPATCH_METHOD, 1)
            if doc_unk is None:
                _consecutive_errors = 0
                return ""

            # QI IUnknown → IDispatch
            doc_disp = doc_unk.QueryInterface(pythoncom.IID_IDispatch)

            # DISPID=15 → GetPath
            path = doc_disp.Invoke(15, 0x0409, pythoncom.DISPATCH_METHOD, 1)
            _consecutive_errors = 0
            return str(path) if path else ""

        except pythoncom.com_error as e:
            _consecutive_errors += 1
            _acc = None  # Cimatron potrebbe essere stato riavviato
            if _consecutive_errors <= 2:
                stderr(f"[Daemon] COM error (#{_consecutive_errors}): {e}")
            return ""

        except Exception as e:
            _consecutive_errors += 1
            _acc = None
            stderr(f"[Daemon] Errore: {type(e).__name__}: {e}")
            return ""

    # Loop principale — legge comandi da stdin
    while True:
        try:
            line = sys.stdin.readline()
        except (EOFError, KeyboardInterrupt):
            break

        if not line:
            break  # stdin chiuso — tracker ha terminato

        cmd = line.strip()

        if cmd == "?":
            path = get_path()
            stdout(path)  # stringa vuota se nessun documento
        elif cmd == "exit":
            stderr("[Daemon] Chiusura richiesta")
            break
        elif cmd == "ping":
            stdout("pong")
        # Ignora comandi sconosciuti


if __name__ == "__main__":
    main()
