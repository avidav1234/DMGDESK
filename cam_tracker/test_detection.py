"""
test_detection.py — Verifica rilevamento Cimatron su CAM35
===========================================================
Eseguire su CAM35 con Cimatron aperto su un progetto qualsiasi.

    python test_detection.py

Output atteso:
    [COM] Connesso: SI / NO
    [WIN] Titolo finestra: "Cimatron 2024 - FLANGIA_BASE.elt"
    [WIN] Progetto rilevato: FLANGIA_BASE
    Progetto attivo finale: FLANGIA_BASE
"""

import sys
import re
from pathlib import Path


def test_com(program_dir: str):
    print("\n── Test COM API Cimatron ───────────────────────────────────")
    try:
        sys.path.insert(0, program_dir)
        import clr
        clr.AddReference("Interop.CimAppAPI")
        import CimAppAPI
        app = CimAppAPI.CimApplication()
        doc = app.ActiveDocument
        if doc:
            full = str(doc.FullName)
            stem = Path(full).stem.upper()
            print(f"  [COM] Connesso: SI")
            print(f"  [COM] File attivo: {full}")
            print(f"  [COM] Progetto: {stem}")
            return stem
        else:
            print(f"  [COM] Connesso ma nessun documento aperto")
            return None
    except ImportError:
        print(f"  [COM] pythonnet non disponibile")
        return None
    except Exception as e:
        print(f"  [COM] Errore: {e}")
        return None


def test_window():
    print("\n── Test Window Title Fallback ──────────────────────────────")
    PATTERNS = [
        r"Cimatron\s+\S+\s*[-–—]\s*(.+?)(?:\.elt|\.icd)?$",
        r"[-–—]\s*.*[/\\](.+?)(?:\.elt|\.icd)?$",
    ]
    try:
        import win32gui
        titles = []

        def cb(hwnd, _):
            if win32gui.IsWindowVisible(hwnd):
                t = win32gui.GetWindowText(hwnd)
                if t:
                    titles.append(t)

        win32gui.EnumWindows(cb, None)

        cim_titles = [t for t in titles if "cimatron" in t.lower()]
        if not cim_titles:
            print("  [WIN] Nessuna finestra Cimatron trovata")
            print(f"  [WIN] Finestre visibili totali: {len(titles)}")
            return None

        print(f"  [WIN] Finestre Cimatron trovate: {len(cim_titles)}")
        for t in cim_titles:
            print(f"        '{t}'")

        for title in cim_titles:
            for pat in PATTERNS:
                m = re.search(pat, title, re.IGNORECASE)
                if m:
                    proj = m.group(1).strip().upper()
                    print(f"  [WIN] Progetto rilevato: {proj}")
                    return proj

        print("  [WIN] Titolo trovato ma nessun pattern applicabile")
        return None

    except ImportError:
        print("  [WIN] pywin32 non installato (pip install pywin32)")
        return None
    except Exception as e:
        print(f"  [WIN] Errore: {e}")
        return None


def test_api(base_url: str):
    print("\n── Test connessione DMGDesk ────────────────────────────────")
    try:
        import requests
        r = requests.get(f"{base_url}/health", timeout=3)
        if r.status_code == 200:
            print(f"  [API] DMGDesk raggiungibile: {base_url}")
            # Test endpoint cam-tracker
            r2 = requests.get(f"{base_url}/api/cam-tracker/today", timeout=3)
            if r2.status_code == 200:
                data = r2.json()
                print(f"  [API] /api/cam-tracker/today: OK ({data.get('total_seconds', 0)}s oggi)")
            else:
                print(f"  [API] /api/cam-tracker/today: HTTP {r2.status_code} — router non registrato?")
        else:
            print(f"  [API] HTTP {r.status_code}")
    except Exception as e:
        print(f"  [API] Non raggiungibile: {e}")


if __name__ == "__main__":
    import configparser

    cfg = configparser.ConfigParser()
    cfg.read(Path(__file__).parent / "cam_tracker_config.ini", encoding="utf-8")

    program_dir = cfg.get("cimatron", "program_dir",
                          fallback=r"C:\Program Files\Cimatron\Cimatron\2024.0\Program")
    dmgdesk_url = cfg.get("dmgdesk", "url", fallback="http://localhost:8000")

    print("=" * 60)
    print("  CAMTracker — Test rilevamento Cimatron")
    print("=" * 60)

    proj_com = test_com(program_dir)
    proj_win = test_window()
    test_api(dmgdesk_url)

    print("\n── Risultato ───────────────────────────────────────────────")
    final = proj_com or proj_win
    if final:
        print(f"  Progetto attivo rilevato: {final}")
        print(f"  Metodo: {'COM API' if proj_com else 'Window Title'}")
    else:
        print("  Nessun progetto rilevato.")
        print("  Verificare che Cimatron sia aperto con un file .elt attivo.")
    print("=" * 60)
