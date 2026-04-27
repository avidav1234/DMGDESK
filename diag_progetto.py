"""
Script diagnostico per progetto 4360_7221.
Esegui con: python diag_progetto.py
Stampa numero task fresatura, filename per task, e tipoGruppo.
"""
import json
import sys
from pathlib import Path
from collections import Counter

# Trova il file progetti
candidates = [
    Path("worktrack_projects.json"),
    Path("backend/worktrack_projects.json"),
    Path("api/worktrack_projects.json"),
]
data_path = next((p for p in candidates if p.exists()), None)
if not data_path:
    print("ERR: worktrack_projects.json non trovato")
    sys.exit(1)

print(f"Letto: {data_path}\n")
data = json.loads(data_path.read_text(encoding="utf-8"))
projects = data.get("projects", []) or data.get("progetti", [])

target = sys.argv[1] if len(sys.argv) > 1 else "4360_7221"

for p in projects:
    if target.upper() not in (p.get("name") or "").upper():
        continue

    print(f"═══ Progetto: {p.get('name')} (id={p.get('id')}) ═══\n")

    # main_snapshot
    snap = p.get("main_snapshot")
    if snap:
        print(f"main_snapshot:")
        print(f"  path: {snap.get('main_path')}")
        print(f"  hash: {(snap.get('main_hash') or '')[:12]}")
        print(f"  programmi nel MAIN ({len(snap.get('main_programmi') or [])}):")
        for prog in (snap.get("main_programmi") or []):
            print(f"    {prog}")
        print()
    else:
        print("main_snapshot: MANCANTE\n")

    # task fresatura
    task_count = 0
    for step in p.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            task_count += 1
            programs = task.get("programs", [])
            step_title = step.get("title", "?")
            print(f"── Step '{step_title}' / Task fresatura ({len(programs)} programmi)")

            # group by stato + tipo
            counter = Counter()
            for pgm in programs:
                key = (pgm.get("stato"), pgm.get("tipoGruppo"))
                counter[key] += 1
            for (s, t), n in sorted(counter.items()):
                print(f"     {n:3d}  stato={s:15s} tipo={t}")

            # filename list
            print(f"     Programmi:")
            for pgm in programs:
                fn = pgm.get("filename", "?")
                st = pgm.get("stato", "?")
                tp = pgm.get("tipoGruppo", "?")
                ut = pgm.get("utensile", "?")
                num = pgm.get("numPgm", "?")
                print(f"       [{tp:9s}] {st:15s} num={num:5s} {fn:50s} ut={ut}")
            print()

    # cerca duplicati di filename across all tasks
    all_filenames = []
    for step in p.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in task.get("programs", []):
                all_filenames.append(pgm.get("filename", "").upper())

    dups = [fn for fn, c in Counter(all_filenames).items() if c > 1 and fn]
    if dups:
        print(f"⚠️  DUPLICATI cross-task (stesso filename in più task):")
        for d in dups:
            print(f"     {d}")

    print(f"\n=== Totale task fresatura: {task_count} ===")
