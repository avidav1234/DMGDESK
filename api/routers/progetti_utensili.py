"""
Funzioni helper per estrazione alias utensili dai progetti e dai file MPF su disco.
"""
import re
import os
import json
from pathlib import Path



def classify_tool(alias: str, tools_db: dict) -> str:
    """
    Classifica un alias utensile rispetto al tools_machine.json.
    Considera i gemelli (duplo): se il tool principale è disabilitato/worn
    ma esiste un gemello abilitato con lo stesso nome → usa il gemello.

    Ritorna: 'ok' | 'fin_vita' | 'disabilitato' | 'mancante'
    """
    if not alias or not tools_db:
        return "mancante"

    key = alias.upper().strip()

    # Raccogli tutti i tool con questo alias (tool + gemelli)
    tutti = [t for t in tools_db.values()
             if (t.get("name") or "").upper().strip() == key]

    if not tutti:
        return "mancante"

    # Cerca gemelli abilitati e non worn
    abilitati = [t for t in tutti
                 if t.get("is_enabled", True) and not t.get("is_worn", False)]

    if not abilitati:
        return "disabilitato"  # tutti i gemelli sono KO

    # Tra gli abilitati, prendi quello con vita migliore
    best = max(abilitati, key=lambda t: t.get("life_percent") or 100)
    lp = best.get("life_percent")
    if lp is not None and lp < 15:
        return "fin_vita"
    return "ok"


def parse_mpf_testo(testo: str) -> set:
    """Estrae alias utensili (T='alias' + M6) dal testo di un file MPF."""
    pattern = re.compile(r"T\s*=\s*[\"']?([A-Z0-9.\-_\s]+)[\"']?", re.IGNORECASE)
    righe = testo.splitlines()
    risultati = set()
    last_alias, last_idx = None, -1
    for i, riga in enumerate(righe):
        riga_up = riga.strip().upper()
        m = pattern.search(riga_up)
        if m:
            a = m.group(1).strip()
            if a:
                last_alias = a
                last_idx = i
        if last_alias and (i - last_idx) < 5:
            if "M6" in riga_up.replace("M06", "M6"):
                risultati.add(last_alias.upper())
                last_alias = None
    return risultati


def cerca_file_mpf(filename: str, nc_base: str, extra_dirs: list | None = None) -> str | None:
    """Cerca un file MPF nella cartella NC e in cartelle extra. Ritorna il path o None."""
    if not filename:
        return None
    search_dirs = [d for d in ([nc_base] + (extra_dirs or [])) if d]
    for base in search_dirs:
        for root, _, files in os.walk(base):
            # Confronto case-insensitive su Windows
            for f in files:
                if f.upper() == filename.upper():
                    return os.path.join(root, f)
    return None


def estrai_alias_da_progetti(config: dict) -> dict:
    """
    Per ogni progetto attivo, estrae tutti gli alias richiesti dai programmi MPF.
    Usa il campo 'utensile' già parsato nel FresaturaPanel;
    se vuoto, legge il file dal disco.
    Ritorna: { alias_upper: [(project_name, filename), ...] }
    """
    from api.routers.progetti import _load_progetti
    data     = _load_progetti(config)
    projects = [p for p in data.get("projects", []) if not p.get("archived")]
    nc_base     = (config.get("percorso_nc_base") or "").strip()
    tools_folder = (config.get("tools_toa_folder") or "").strip()
    extra_dirs = [tools_folder] if tools_folder and tools_folder != nc_base else []

    alias_map: dict[str, list] = {}

    for project in projects:
        pname = project.get("name", "?")
        for step in project.get("steps", []):
            for task in step.get("tasks", []):
                if task.get("text", "").strip().lower() != "fresatura":
                    continue
                for pgm in task.get("programs", []):
                    if pgm.get("tipoGruppo") == "ipm":
                        continue
                    # SOLO programmi in_macchina — da_fare e completati ignorati
                    if pgm.get("stato") != "in_macchina":
                        continue
                    filename = pgm.get("filename", "")
                    alias = (pgm.get("utensile") or "").upper().strip()

                    if alias:
                        alias_map.setdefault(alias, []).append((pname, filename))
                    else:
                        # Prova a leggere il file da disco
                        found = False
                        if filename:
                            fpath = cerca_file_mpf(filename, nc_base, extra_dirs)
                            if fpath:
                                try:
                                    testo = open(fpath, encoding="utf-8", errors="replace").read()
                                    parsed = parse_mpf_testo(testo)
                                    for a in parsed:
                                        alias_map.setdefault(a, []).append((pname, filename))
                                    if parsed:
                                        found = True
                                except Exception:
                                    pass
                        # Fallback: usa diametro dal nome file o tipoOp
                        if not found and pgm.get("diametro"):
                            pass  # non abbastanza info per ricostruire alias

    return alias_map


def estrai_alias_da_progetto(project: dict, config: dict) -> dict:
    """
    Come sopra ma per un singolo progetto.
    Ritorna: { alias_upper: [filename, ...] }
    """
    nc_base     = (config.get("percorso_nc_base") or "").strip()
    tools_folder = (config.get("tools_toa_folder") or "").strip()
    extra_dirs   = [tools_folder] if tools_folder and tools_folder != nc_base else []
    alias_refs: dict[str, list] = {}

    for step in project.get("steps", []):
        for task in step.get("tasks", []):
            if task.get("text", "").strip().lower() != "fresatura":
                continue
            for pgm in task.get("programs", []):
                if pgm.get("tipoGruppo") == "ipm":
                    continue
                filename = pgm.get("filename", "")
                alias = (pgm.get("utensile") or "").upper().strip()

                if alias:
                    alias_refs.setdefault(alias, []).append(filename)
                elif filename:
                    fpath = cerca_file_mpf(filename, nc_base, extra_dirs)
                    if fpath:
                        try:
                            testo = open(fpath, encoding="utf-8", errors="replace").read()
                            for a in parse_mpf_testo(testo):
                                alias_refs.setdefault(a, []).append(filename)
                        except Exception:
                            pass

    return alias_refs
