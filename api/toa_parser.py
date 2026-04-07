"""
api/toa_parser.py
=================
Parser utensili dalla share DMG DMC 160U.

Supporta due formati:

  FORMATO A — TOA + TMA (HMI → Servizi → Salva Attrezzaggio):
    TOOL_SYNC.TOA   — geometria + vita di TUTTI gli utensili
    TOOL_SYNC.TMA   — posizioni magazzino

  FORMATO B — MPF (programma NC SYNC_ALL_V2):
    TOOL_SYN1_TOA.MPF  — posizioni 1..40
    TOOL_SYN2_TOA.MPF  — posizioni 41..80
    TOOL_SYN3_TOA.MPF  — posizioni 81..120
    (geometria + vita + posizioni già integrate)

Logica auto-selezione:
  - Se presenti entrambi → usa il gruppo con timestamp più recente
  - Se solo uno → usa quello disponibile
  - Se nessuno → FileNotFoundError
"""

import re
import os
from datetime import datetime
from pathlib import Path
from dataclasses import dataclass


# ── Dataclass pubblici ────────────────────────────────────────────────────────

@dataclass
class MachineTool:
    t_number:       int
    name:           str
    length:         float = 0.0
    radius:         float = 0.0
    life_remaining: float = 0.0
    life_total:     float = 0.0
    life_percent:   float = None
    is_worn:        bool  = False
    is_enabled:     bool  = True
    status:         int   = 0
    duplo:          int   = 1
    magazine:       int   = None
    position:       int   = None
    pos_label:      str   = ""

@dataclass
class MagazinePosition:
    magazine:  int
    position:  int
    t_number:  int
    pos_label: str = ""


# ── Parser core (identico per TOA e MPF) ─────────────────────────────────────

def _parse_tool_file(path) -> dict:
    """Legge un file TOA o MPF e restituisce dict {t_number: {...}}."""
    tools = {}
    try:
        with open(path, 'rb') as f:
            raw = f.read()
        text = raw.decode('latin-1')
        current_t = None
        for line in text.split('\n'):
            line = line.strip()
            if not line or line.startswith(';'):
                continue

            m = re.match(r'^\$TC_TP1\[(\d+)\]=(.+)', line)
            if m:
                t = int(m.group(1))
                if t not in tools:
                    tools[t] = {'t_number': t}
                try: tools[t]['duplo'] = int(float(m.group(2)))
                except ValueError: pass
                continue

            m = re.match(r'^\$TC_TP2\[(\d+)\]=(.+)', line)
            if m:
                current_t = int(m.group(1))
                if current_t not in tools:
                    tools[current_t] = {'t_number': current_t}
                tools[current_t]['name'] = m.group(2).strip().strip('"')
                continue
            if current_t is None:
                continue

            m = re.match(r'^\$TC_DP3\[(\d+),1\]=(.+)', line)
            if m and int(m.group(1)) == current_t:
                try: tools[current_t]['length'] = float(m.group(2))
                except ValueError: pass
                continue

            m = re.match(r'^\$TC_DP6\[(\d+),1\]=(.+)', line)
            if m and int(m.group(1)) == current_t:
                try: tools[current_t]['radius'] = float(m.group(2))
                except ValueError: pass
                continue

            m = re.match(r'^\$TC_MOP2\[(\d+),1\]=(.+)', line)
            if m and int(m.group(1)) == current_t:
                try: tools[current_t]['life_remaining'] = float(m.group(2))
                except ValueError: pass
                continue

            m = re.match(r'^\$TC_MOP11\[(\d+),1\]=(.+)', line)
            if m and int(m.group(1)) == current_t:
                try: tools[current_t]['life_total'] = float(m.group(2))
                except ValueError: pass
                continue

            m = re.match(r'^\$TC_TP8\[(\d+)\]=(.+)', line)
            if m and int(m.group(1)) == current_t:
                try:
                    status = int(m.group(2))
                    tools[current_t]['status'] = status
                    tools[current_t]['is_enabled'] = not bool(status & 0x0004)
                except ValueError: pass
                continue

            m = re.match(r'^\$TC_MPP6\[(\d+),(\d+)\]=(\d+)', line)
            if m:
                mag, pos, t = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if t == current_t:
                    tools[current_t]['magazine']  = mag
                    tools[current_t]['position']  = pos
                    tools[current_t]['pos_label'] = f"M{mag}.{pos:03d}"
                continue
    except Exception:
        pass
    return tools


def _finalize(raw: dict) -> dict:
    """Calcola life_percent, is_worn, duplo → dict {t_num: MachineTool}."""
    # Duplo: letto direttamente da $TC_TP1 nel TOA
    result = {}
    for t_num, tool in raw.items():
        if not tool.get('name'):
            continue
        total = tool.get('life_total', 0)
        rem   = tool.get('life_remaining', 0)
        if total and total > 0:
            pct  = max(0.0, min(100.0, (rem / total) * 100))
            worn = pct < 10
        else:
            pct = None; worn = False
        result[t_num] = MachineTool(
            t_number       = t_num,
            name           = tool.get('name', ''),
            length         = tool.get('length', 0.0),
            radius         = tool.get('radius', 0.0),
            life_remaining = tool.get('life_remaining', 0.0),
            life_total     = tool.get('life_total', 0.0),
            life_percent   = round(pct, 1) if pct is not None else None,
            is_worn        = worn,
            is_enabled     = tool.get('is_enabled', True),
            status         = tool.get('status', 0),
            duplo          = tool.get('duplo', 1),
            magazine       = tool.get('magazine'),
            position       = tool.get('position'),
            pos_label      = tool.get('pos_label', ''),
        )
    return result


# ── Rilevamento formato ───────────────────────────────────────────────────────

def _mtime(p: Path) -> float:
    try: return p.stat().st_mtime
    except: return 0.0

def _fmt_ts(ts: float) -> str:
    if ts == 0: return "—"
    return datetime.fromtimestamp(ts).strftime('%d/%m/%Y %H:%M')


def detect_format(share_path: str) -> dict:
    """
    Rileva quale formato è disponibile sulla share e quale usare.
    Restituisce dict con chiavi: format, use, toa_mtime, mpf_mtime,
                                 toa_files, mpf_files, reason.
    """
    base = Path(share_path)

    toa_files = [p for p in [base / "TOOL_SYNC.TOA"] if p.exists()]
    mpf_files = [p for p in [
        base / "TOOL_SYN1_TOA.MPF",
        base / "TOOL_SYN2_TOA.MPF",
        base / "TOOL_SYN3_TOA.MPF",
    ] if p.exists()]

    toa_mtime = max((_mtime(p) for p in toa_files), default=0.0)
    mpf_mtime = max((_mtime(p) for p in mpf_files), default=0.0)

    has_toa = bool(toa_files)
    has_mpf = bool(mpf_files)

    if has_toa and has_mpf:
        fmt = "both"
        if mpf_mtime >= toa_mtime:
            use = "mpf"
            reason = (f"MPF più recente ({_fmt_ts(mpf_mtime)}) "
                      f"vs TOA ({_fmt_ts(toa_mtime)}) — uso MPF")
        else:
            use = "toa"
            reason = (f"TOA più recente ({_fmt_ts(toa_mtime)}) "
                      f"vs MPF ({_fmt_ts(mpf_mtime)}) — uso TOA")
    elif has_toa:
        fmt = use = "toa"
        reason = f"Solo TOA disponibile ({_fmt_ts(toa_mtime)})"
    elif has_mpf:
        fmt = use = "mpf"
        reason = f"Solo MPF disponibile ({_fmt_ts(mpf_mtime)})"
    else:
        fmt = use = "none"
        reason = "Nessun file TOA o MPF trovato sulla share"

    return dict(format=fmt, use=use, toa_mtime=toa_mtime, mpf_mtime=mpf_mtime,
                toa_files=toa_files, mpf_files=mpf_files, reason=reason)


# ── Lettura per formato ───────────────────────────────────────────────────────

def _read_tma(tma_path: Path) -> list:
    result = []
    try:
        text = tma_path.read_bytes().decode('latin-1')
        for line in text.split('\n'):
            m = re.match(r'^\$TC_MPP6\[(\d+),(\d+)\]=(\d+)', line.strip())
            if m:
                mag, pos, t = int(m.group(1)), int(m.group(2)), int(m.group(3))
                if t > 0:
                    result.append(MagazinePosition(magazine=mag, position=pos,
                                                   t_number=t, pos_label=f"M{mag}.{pos:03d}"))
    except Exception:
        pass
    return result


def read_toa_format(share_path: str) -> tuple:
    """Legge TOOL_SYNC.TOA + TOOL_SYNC.TMA. Ritorna (tools_dict, positions_list)."""
    base = Path(share_path)
    raw  = _parse_tool_file(base / "TOOL_SYNC.TOA")
    positions = []
    tma = base / "TOOL_SYNC.TMA"
    if tma.exists():
        positions = _read_tma(tma)
        for pos in positions:
            if pos.t_number in raw:
                raw[pos.t_number]['magazine']  = pos.magazine
                raw[pos.t_number]['position']  = pos.position
                raw[pos.t_number]['pos_label'] = pos.pos_label
    return _finalize(raw), positions


def read_mpf_format(share_path: str) -> tuple:
    """Legge TOOL_SYN1/2/3_TOA.MPF. Ritorna (tools_dict, positions_list)."""
    base = Path(share_path)
    raw  = {}
    for n in [1, 2, 3]:
        p = base / f"TOOL_SYN{n}_TOA.MPF"
        if p.exists():
            raw.update(_parse_tool_file(p))
    tools = _finalize(raw)
    positions = [
        MagazinePosition(magazine=t.magazine, position=t.position,
                         t_number=t.t_number, pos_label=t.pos_label)
        for t in tools.values()
        if t.magazine is not None and t.position is not None
    ]
    return tools, positions


# ── Funzione principale ───────────────────────────────────────────────────────

def sync_from_share(share_path: str) -> dict:
    """
    Auto-rileva il formato più aggiornato e legge i dati.

    Ritorna:
    {
        "tools":       dict {t_num: MachineTool},
        "positions":   list [MagazinePosition],
        "format_used": "toa" | "mpf",
        "reason":      str,
        "toa_mtime":   float,
        "mpf_mtime":   float,
    }
    """
    info = detect_format(share_path)
    if info["use"] == "none":
        raise FileNotFoundError(info["reason"])
    if info["use"] == "toa":
        tools, positions = read_toa_format(share_path)
    else:
        tools, positions = read_mpf_format(share_path)
    return dict(tools=tools, positions=positions,
                format_used=info["use"], reason=info["reason"],
                toa_mtime=info["toa_mtime"], mpf_mtime=info["mpf_mtime"])


# ── Retrocompatibilità ────────────────────────────────────────────────────────

def parse_toa(toa_path: str) -> dict:
    """Legge un singolo file TOA o MPF. Ritorna dict {t_num: MachineTool}."""
    return _finalize(_parse_tool_file(str(toa_path)))

def parse_tma(tma_path: str) -> list:
    """Legge un singolo file TMA. Ritorna list[MagazinePosition]."""
    return _read_tma(Path(tma_path))

def parse_toa_files(share_path: str) -> list:
    """Retrocompatibilità — ritorna list[MachineTool] (auto-detect)."""
    return list(sync_from_share(share_path)["tools"].values())

def get_sync_info(share_path: str) -> dict:
    info = detect_format(share_path)
    return dict(format=info["format"], use=info["use"], reason=info["reason"],
                toa_files=[str(p) for p in info["toa_files"]],
                mpf_files=[str(p) for p in info["mpf_files"]],
                toa_mtime=info["toa_mtime"], mpf_mtime=info["mpf_mtime"])
