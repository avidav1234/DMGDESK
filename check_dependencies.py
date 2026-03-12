"""
Tool Manager V14 - Verifica Dipendenze
Controlla che tutti i pacchetti necessari siano installati
"""

import sys

def check_dependencies():
    """Verifica tutte le dipendenze necessarie per la build."""
    
    print("\n" + "="*50)
    print("  VERIFICA DIPENDENZE - TOOL MANAGER V14")
    print("="*50 + "\n")
    
    dependencies = {
        'customtkinter': 'UI Framework',
        'pandas': 'Data handling',
        'PIL': 'Image handling (Pillow)',
        'PyInstaller': 'Build tool',
    }
    
    missing = []
    installed = []
    
    for module, desc in dependencies.items():
        try:
            __import__(module)
            installed.append((module, desc))
            print(f"✅ {module:20s} - {desc}")
        except ImportError:
            missing.append((module, desc))
            print(f"❌ {module:20s} - {desc} [MANCANTE]")
    
    print("\n" + "="*50)
    
    if missing:
        print("\n⚠️  DIPENDENZE MANCANTI:")
        print("\nInstalla con:")
        print("pip install " + " ".join(m[0].lower() for m in missing))
        print("\nOppure:")
        print("pip install -r requirements.txt")
        return False
    else:
        print("\n✅ TUTTE LE DIPENDENZE INSTALLATE!")
        print("\nPuoi procedere con la build:")
        print("  - build_exe.bat (Windows)")
        print("  - pyinstaller tool_manager.spec")
        return True


if __name__ == "__main__":
    success = check_dependencies()
    print("\n" + "="*50 + "\n")
    
    if not success:
        sys.exit(1)
    else:
        sys.exit(0)
