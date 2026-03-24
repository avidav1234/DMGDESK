"""
Funzioni helper per estrazione alias utensili dai progetti e dai file MPF su disco.
"""
import re
import os
import json
from pathlib import Path


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


def cerca_file_mpf(filename: str, nc_base: str) -> str | None:
    """Cerca un file MPF ricorsivamente nella cartella NC. Ritorna il path o None."""
    if not nc_base or not filename:
        return None
    for root, _, files in os.walk(nc_base):
        if filename in files:
            return os.path.join(root, filename)
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
    nc_base  = (config.get("percorso_nc_base") or "").strip()

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
                    filename = pgm.get("filename", "")
                    alias = (pgm.get("utensile") or "").upper().strip()

                    if alias:
                        alias_map.setdefault(alias, []).append((pname, filename))
                    elif filename:
                        fpath = cerca_file_mpf(filename, nc_base)
                        if fpath:
                            try:
                                testo = open(fpath, encoding="utf-8", errors="replace").read()
                                for a in parse_mpf_testo(testo):
                                    alias_map.setdefault(a, []).append((pname, filename))
                            except Exception:
                                pass

    return alias_map


def estrai_alias_da_progetto(project: dict, config: dict) -> dict:
    """
    Come sopra ma per un singolo progetto.
    Ritorna: { alias_upper: [filename, ...] }
    """
    nc_base = (config.get("percorso_nc_base") or "").strip()
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
                    fpath = cerca_file_mpf(filename, nc_base)
                    if fpath:
                        try:
                            testo = open(fpath, encoding="utf-8", errors="replace").read()
                            for a in parse_mpf_testo(testo):
                                alias_refs.setdefault(a, []).append(filename)
                        except Exception:
                            pass

    return alias_refs
