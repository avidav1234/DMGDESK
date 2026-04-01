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
    # Auto-detect versione
    base = Path(program_dir).parent.parent
    candidates = [program_dir]
    if base.exists():
        versioni = sorted(
            [str(d / "Program") for d in base.iterdir()
             if d.is_dir() and (d / "Program").exists()],
            reverse=True
        )
        candidates = versioni + [program_dir]
    print(f"  [COM] Cartelle candidate: {candidates[:3]}")
    try:
        for path in candidates:
            if Path(path).exists():
                sys.path.insert(0, path)
                print(f"  [COM] Path usato: {path}")
                break
        import clr
        clr.AddReference("interop.CimatronE")
        import CimatronE
        app = CimatronE.Application()
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
        r"\[([^\]:]+?)\s*:\s*NC-Standard\s*\]",
        r"\[(?!CimExtSimul)([^\]:]+?)\s*:\s*[^\]]+\]",
        r"Cimatron\s+\S+\s*[-–—]\s*(.+?)(?:\.elt|\.icd)?$",
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

        cim_titles = [t for t in titles if "Cimatron" in t and "NC-Standard" in t and "CimExtSimul" not in t]
        cim_all    = [t for t in titles if "Cimatron" in t]
        if not cim_all:
            print("  [WIN] Nessuna finestra Cimatron trovata")
            return None

        print(f"  [WIN] Finestre Cimatron totali: {len(cim_all)}")
        print(f"  [WIN] Finestre NC-Standard (escluso simulatore): {len(cim_titles)}")
        for t in cim_all:
            marker = " ✓" if t in cim_titles else " (simulatore/altro)"
            print(f"        '{t}'{marker}")

        if not cim_titles:
            print("  [WIN] Nessun file NC-Standard aperto")
            return None

        for title in cim_titles:
            for pat in PATTERNS:
                m = re.search(pat, title, re.IGNORECASE)
                if m:
                    proj = m.group(1).strip().upper()
                    proj = re.sub(r'\s+', '_', proj)
                    print(f"  [WIN] Progetto rilevato: {proj}")
                    return proj

        print("  [WIN] Titolo trovato ma nessun pattern applicabile")
        return None


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
    import sys
    sys.path.insert(0, str(Path(__file__).parent))
    from cam_tracker import parse_project_from_path, parse_project_from_title

    cfg = configparser.ConfigParser()
    cfg.read(Path(__file__).parent / "cam_tracker_config.ini", encoding="utf-8")

    program_dir = cfg.get("cimatron", "program_dir",
                          fallback=r"C:\Program Files\Cimatron\Cimatron\2025.0\Program")
    dmgdesk_url = cfg.get("dmgdesk", "url", fallback="http://localhost:8000")

    print("=" * 60)
    print("  CAMTracker — Test rilevamento Cimatron")
    print("=" * 60)

    # ── Test parser path ────────────────────────────────────────
    print("\n── Test parser path → commessa/operazione ──────────────────")
    test_paths = [
        r"C:\Lavoro\4348\P0221\file.elt",
        r"C:\Lavoro\4349\0301\PEZZO.elt",
        r"H:\0CellaMikron\0Cella_DMG-Test\Backup Archivi\4349\0221\x.elt",
        r"C:\Lavoro\4360\P7221\operazione.elt",
    ]
    for tp in test_paths:
        result = parse_project_from_path(tp)
        if result:
            print(f"  {tp.split(chr(92))[-3]}\\{tp.split(chr(92))[-2]} → id={result['project_id']}")
        else:
            print(f"  FAIL: {tp}")

    print("\n── Test parser titolo finestra ─────────────────────────────")
    test_titles = [
        "E541540221_0221_A#1_V3",
        "1D24103D.20201A1#1-v4-off0",
        "4348_0221_OP1",
    ]
    for tt in test_titles:
        r = parse_project_from_title(tt)
        print(f"  {tt!r:35s} → commessa={r['commessa']} op={r['operazione']} id={r['project_id']}")

    proj_com = test_com(program_dir)
    proj_win = test_window()
    test_api(dmgdesk_url)

    print("\n── Risultato ───────────────────────────────────────────────")
    final = proj_com or proj_win
    if final:
        # Compatibilità: gestisce sia dict (nuovo) che stringa (vecchio)
        if isinstance(final, dict):
            print(f"  Progetto attivo: {final['project_id']}")
            print(f"  Commessa:        {final['commessa']}")
            print(f"  Operazione:      {final['operazione']}")
            print(f"  Metodo:          {'COM API (path)' if proj_com else 'Window Title'}")
            if final.get('full_path'):
                print(f"  Path:            {final['full_path']}")
        else:
            print(f"  Progetto attivo: {final}")
            print(f"  Metodo:          {'COM API' if proj_com else 'Window Title'}")
    else:
        print("  Nessun progetto rilevato.")
        print("  Verificare che Cimatron sia aperto con un file .elt attivo.")
    print("=" * 60)
