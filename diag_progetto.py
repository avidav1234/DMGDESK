"""
Script diagnostico per un progetto. Usa la configurazione DMGDesk per
trovare il file worktrack_projects.json sulla share di rete.

Esegui: python diag_progetto.py [pattern_progetto]
        python diag_progetto.py 4360_7221
"""
import json
import sys
from pathlib import Path
from collections import Counter

# Aggiungi root al path per importare moduli del progetto
ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT))

# Carica config dal database/config DMGDesk
try:
    from database.db_handler import carica_configurazione
    config = carica_configurazione()
    base = (config.get("tools_toa_folder") or "").strip()
    if not base:
        print("ERR: tools_toa_folder non configurato in DMGDesk")
        sys.exit(1)
    data_path = Path(base) / "worktrack_projects.json"
except Exception as e:
    print(f"WARN: impossibile leggere config DMGDesk ({e}), provo fallback")
    candidates = [
        Path("worktrack_projects.json"),
        Path("backend/worktrack_projects.json"),
        Path("api/worktrack_projects.json"),
    ]
    data_path = next((p for p in candidates if p.exists()), None)
    if not data_path:
        print("ERR: worktrack_projects.json non trovato")
        sys.exit(1)

if not data_path.exists():
    print(f"ERR: file non esiste: {data_path}")
    sys.exit(1)

print(f"Letto: {data_path}\n")
data = json.loads(data_path.read_text(encoding="utf-8"))
projects = data.get("projects", []) or data.get("progetti", [])
print(f"Totale progetti nel file: {len(projects)}\n")

target = sys.argv[1] if len(sys.argv) > 1 else "4360_7221"
print(f"Cerco progetti che contengono '{target}' nel nome\n")

trovati = 0
for p in projects:
    if target.upper() not in (p.get("name") or "").upper():
        continue
    trovati += 1

    print(f"═══════════════════════════════════════════════════════════════")
    print(f"Progetto: {p.get('name')} (id={p.get('id')})")
    print(f"═══════════════════════════════════════════════════════════════\n")

    snap = p.get("main_snapshot")
    if snap:
        print(f"main_snapshot:")
        print(f"  path: {snap.get('main_path')}")
        print(f"  hash: {(snap.get('main_hash') or '')[:12]}")
        prog_main = snap.get("main_programmi") or []
        print(f"  programmi nel MAIN ({len(prog_main)}):")
        for prog in prog_main:
            print(f"    {prog}")
        print()
    else:
        print("main_snapshot: MANCANTE\n")

    task_count = 0
    for step in p.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            task_count += 1
            programs = task.get("programs", [])
            step_title = step.get("title", "?")
            print(f"-- Step '{step_title}' / Task fresatura ({len(programs)} programmi)")

            counter = Counter()
            for pgm in programs:
                key = (pgm.get("stato"), pgm.get("tipoGruppo"))
                counter[key] += 1
            for (s, t), n in sorted(counter.items()):
                print(f"     {n:3d}  stato={s:15s} tipo={t}")

            print(f"     Programmi:")
            for pgm in programs:
                fn = pgm.get("filename", "?")
                st = pgm.get("stato", "?")
                tp = pgm.get("tipoGruppo", "?")
                ut = pgm.get("utensile", "?")
                num = pgm.get("numPgm", "?")
                print(f"       [{tp:9s}] {st:15s} num={num:5s} {fn:40s} ut={ut}")
            print()

    all_filenames = []
    for step in p.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in task.get("programs", []):
                all_filenames.append(pgm.get("filename", "").upper())

    dups = [fn for fn, c in Counter(all_filenames).items() if c > 1 and fn]
    if dups:
        print(f"DUPLICATI cross-task (stesso filename in piu task):")
        for d in dups:
            print(f"     {d}")
    else:
        print("Nessun duplicato cross-task")

    print(f"\nTotale task fresatura: {task_count}")
    print(f"Totale programmi: {len(all_filenames)}\n")

if trovati == 0:
    print(f"Nessun progetto trovato con pattern '{target}'")
