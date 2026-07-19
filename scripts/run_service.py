"""
scripts/run_service.py
======================
Launcher robusto per i servizi DMGDesk avviati da Task Scheduler
(vedi scripts/installa_autostart.py).

Uso:
    python scripts/run_service.py backend        # uvicorn api.main:app :8000
    python scripts/run_service.py step           # uvicorn main:app     :8002
    python scripts/run_service.py backend --dry-run   # preflight, NON avvia

Cosa fa (prima di avviare uvicorn):
  1. Libera la porta da eventuali processi orfani (es. avvio precedente col
     .bat non chiuso) — Task Scheduler impedisce doppi TASK, non doppi processi.
  2. (solo backend) verifica frontend/dist; se manca prova a buildarlo
     (best-effort: il backend parte comunque, l'API funziona senza UI).
  3. Esegue uvicorn in foreground: il task resta "running" finché uvicorn
     vive; se uvicorn esce, RestartOnFailure del task lo rilancia.

Progettato per girare SENZA console visibile: ogni output va nei log
(logs/uvicorn_<servizio>.log) oltre ai log applicativi di utils/logger.
"""

import argparse
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

SERVIZI = {
    "backend": {
        "porta": 8000,
        "cwd": ROOT,
        # --timeout-graceful-shutdown: senza, uvicorn aspetta ALL'INFINITO che le
        # connessioni/task in background si chiudano allo stop. Un long-poll Telegram
        # o una connessione inbound che non si chiude lasciava un processo ZOMBIE
        # (socket 8000 chiuso ma processo vivo) che il riavvio successivo non
        # ripuliva. 10s = si spegne comunque, il supervisor riparte pulito.
        "uvicorn": ["api.main:app", "--host", "0.0.0.0", "--port", "8000",
                    "--timeout-graceful-shutdown", "10"],
        "log": ROOT / "logs" / "uvicorn_backend.log",
        # Sottostringa unica della command line uvicorn: serve a stanare processi
        # orfani NON più in LISTENING (zombie in shutdown), che _libera_porta non vede.
        "match": "api.main:app",
    },
    "step": {
        "porta": 8002,
        "cwd": ROOT / "step_analyzer",
        "uvicorn": ["main:app", "--host", "127.0.0.1", "--port", "8002",
                    "--timeout-graceful-shutdown", "10"],
        "log": ROOT / "logs" / "uvicorn_step.log",
        "match": "main:app --host 127.0.0.1 --port 8002",
    },
}


def _pids_su_porta(porta: int) -> list[int]:
    """PID in LISTENING sulla porta data (parsing netstat -ano, Windows)."""
    pids: set[int] = set()
    try:
        out = subprocess.run(
            ["netstat", "-ano"], capture_output=True, text=True, timeout=15
        ).stdout
    except Exception as e:
        print(f"[warn] netstat non disponibile: {e}")
        return []
    suffisso = f":{porta}"
    for riga in out.splitlines():
        parti = riga.split()
        # Formato: Proto  Local  Foreign  State  PID
        if len(parti) < 5:
            continue
        if "LISTENING" not in parti:
            continue
        local = parti[1]
        # Deve terminare esattamente con :porta (evita :80002 o :18000)
        if local.rsplit(":", 1)[-1] != str(porta):
            continue
        try:
            pids.add(int(parti[-1]))
        except ValueError:
            pass
    # Non uccidere se stessi
    pids.discard(os.getpid())
    return sorted(pids)


def _libera_porta(porta: int, dry_run: bool) -> None:
    pids = _pids_su_porta(porta)
    if not pids:
        print(f"[ok] porta {porta} libera")
        return
    for pid in pids:
        print(f"[cleanup] processo orfano PID {pid} su :{porta}"
              + (" (dry-run, non terminato)" if dry_run else ""))
        if not dry_run:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True)


def _pids_uvicorn_orfani(match: str) -> list[int]:
    """PID di python la cui command line contiene `match` (es. 'api.main:app').
    Serve a stanare uvicorn ZOMBIE bloccati in shutdown: hanno già chiuso il
    socket, quindi _libera_porta (che guarda solo i LISTENING) non li vede, ma
    restano vivi tenendo il long-poll Telegram e i loop di background → il nuovo
    avvio va in conflitto. Usa PowerShell CIM (command line non disponibile via
    tasklist/netstat)."""
    ps = (
        "Get-CimInstance Win32_Process -Filter \"Name='python.exe'\" | "
        "Where-Object { $_.CommandLine -like '*" + match + "*' } | "
        "Select-Object -ExpandProperty ProcessId"
    )
    try:
        out = subprocess.run(
            ["powershell", "-NoProfile", "-NonInteractive", "-Command", ps],
            capture_output=True, text=True, timeout=20,
        ).stdout
    except Exception as e:
        print(f"[warn] scan command line non disponibile: {e}")
        return []
    pids: set[int] = set()
    for tok in out.split():
        try:
            pids.add(int(tok))
        except ValueError:
            pass
    pids.discard(os.getpid())  # run_service stesso non fa match, ma per sicurezza
    return sorted(pids)


def _libera_orfani(match: str, dry_run: bool) -> None:
    pids = _pids_uvicorn_orfani(match)
    if not pids:
        print(f"[ok] nessun uvicorn orfano ('{match}')")
        return
    for pid in pids:
        print(f"[cleanup] uvicorn orfano/zombie PID {pid} ('{match}')"
              + (" (dry-run, non terminato)" if dry_run else ""))
        if not dry_run:
            subprocess.run(["taskkill", "/F", "/PID", str(pid)],
                           capture_output=True)


def _assicura_dist(dry_run: bool) -> None:
    dist_index = ROOT / "frontend" / "dist" / "index.html"
    if dist_index.exists():
        print("[ok] frontend/dist presente")
        return
    print("[warn] frontend/dist mancante")
    node_modules = ROOT / "frontend" / "node_modules"
    if not node_modules.exists():
        print("[warn] frontend/node_modules assente — impossibile buildare; "
              "il backend parte comunque (solo API, UI non servita)")
        return
    if dry_run:
        print("[dry-run] eseguirei: npm run build in frontend/")
        return
    print("[build] npm run build in corso...")
    try:
        subprocess.run(["npm", "run", "build"], cwd=str(ROOT / "frontend"),
                       shell=True, timeout=600)
    except Exception as e:
        print(f"[warn] build fallita ({e}) — il backend parte comunque")


def main() -> int:
    ap = argparse.ArgumentParser(description="Launcher servizi DMGDesk")
    ap.add_argument("servizio", choices=sorted(SERVIZI.keys()))
    ap.add_argument("--dry-run", action="store_true",
                    help="esegue solo il preflight, NON avvia uvicorn")
    args = ap.parse_args()

    cfg = SERVIZI[args.servizio]
    print(f"=== DMGDesk service: {args.servizio} (porta {cfg['porta']}) ===")

    _libera_porta(cfg["porta"], args.dry_run)
    # Anche gli zombie NON in LISTENING (uvicorn impiantato in shutdown).
    if cfg.get("match"):
        _libera_orfani(cfg["match"], args.dry_run)
    if args.servizio == "backend":
        _assicura_dist(args.dry_run)

    cfg["log"].parent.mkdir(parents=True, exist_ok=True)
    cmd = [sys.executable, "-m", "uvicorn", *cfg["uvicorn"]]

    if args.dry_run:
        print(f"[dry-run] avvierei: {' '.join(cmd)}")
        print(f"[dry-run] cwd={cfg['cwd']}  log={cfg['log']}")
        return 0

    print(f"[start] {' '.join(cmd)}  (cwd={cfg['cwd']})")
    # Foreground: il task resta "running" finché uvicorn vive.
    # Output su file (nessuna console visibile sotto Task Scheduler).
    with open(cfg["log"], "a", encoding="utf-8") as logf:
        proc = subprocess.run(cmd, cwd=str(cfg["cwd"]), stdout=logf, stderr=logf)
    return proc.returncode


if __name__ == "__main__":
    sys.exit(main())
