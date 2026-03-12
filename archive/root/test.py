# Controlla tipo di TUTTE le costanti
from config import theme

for attr in dir(theme):
    val = getattr(theme, attr)
    if isinstance(val, (int, float)) and not attr.startswith('_'):
        tipo = type(val).__name__
        if tipo == 'float':
            print(f"❌ {attr} = {val} (FLOAT!)")
        else:
            print(f"✅ {attr} = {val} (int)")