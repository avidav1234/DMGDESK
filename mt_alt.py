python -c "
import ctypes, sys
from pathlib import Path

LOAD_LIBRARY_AS_DATAFILE = 0x00000002
UPDATE_RESOURCE = ctypes.windll.kernel32.UpdateResource
BEGIN_UPDATE = ctypes.windll.kernel32.BeginUpdateResourceW
END_UPDATE = ctypes.windll.kernel32.EndUpdateResourceW

manifest_path = r'C:\Program Files\Cimatron\Cimatron\2025.0\Program\python.manifest'
python_exe = r'C:\Users\i.dodon\AppData\Local\Programs\Python\Python312\python.exe'

manifest_data = Path(manifest_path).read_bytes()
# Rimuovi BOM UTF-8 se presente
if manifest_data[:3] == b'\xef\xbb\xbf':
    manifest_data = manifest_data[3:]

h = BEGIN_UPDATE(python_exe, False)
if not h:
    print('ERRORE: BeginUpdateResource fallito')
    sys.exit(1)

RT_MANIFEST = 24
ok = UPDATE_RESOURCE(h, RT_MANIFEST, 1, 0, manifest_data, len(manifest_data))
if not ok:
    print('ERRORE: UpdateResource fallito')
    sys.exit(1)

END_UPDATE(h, False)
print('Manifest associato a python.exe — OK')
"