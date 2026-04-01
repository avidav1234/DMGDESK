"""
applica_manifest.py
Associa python.manifest a python.exe senza mt.exe.
Eseguire come amministratore:
    python cam_tracker\applica_manifest.py
"""
import ctypes
import sys
from pathlib import Path

MANIFEST_PATH = r"C:\Program Files\Cimatron\Cimatron\2025.0\Program\python.manifest"
PYTHON_EXE    = r"C:\Users\i.dodon\AppData\Local\Programs\Python\Python312\python.exe"

def main():
    manifest_data = Path(MANIFEST_PATH).read_bytes()
    # Rimuovi BOM UTF-8 se presente
    if manifest_data[:3] == b'\xef\xbb\xbf':
        manifest_data = manifest_data[3:]

    k32 = ctypes.windll.kernel32
    h = k32.BeginUpdateResourceW(PYTHON_EXE, False)
    if not h:
        err = ctypes.GetLastError()
        print(f"ERRORE: BeginUpdateResource fallito (errore Windows {err})")
        print("Assicurarsi di eseguire come amministratore e che python.exe non sia in uso.")
        sys.exit(1)

    RT_MANIFEST = 24
    buf = ctypes.create_string_buffer(manifest_data)
    ok = k32.UpdateResource(h, RT_MANIFEST, 1, 0, buf, len(manifest_data))
    if not ok:
        err = ctypes.GetLastError()
        print(f"ERRORE: UpdateResource fallito (errore Windows {err})")
        k32.EndUpdateResourceW(h, True)  # annulla
        sys.exit(1)

    k32.EndUpdateResourceW(h, False)
    print("Manifest associato a python.exe — OK")
    print(f"  exe:      {PYTHON_EXE}")
    print(f"  manifest: {MANIFEST_PATH}")
    print()
    print("Ora esegui: python cam_tracker\\test_detection.py")

if __name__ == "__main__":
    main()
