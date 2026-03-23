"""
api/toa_parser.py
Parser TOA generato da SYNC_ALL_V2.MPF
Legge TOOL_SYN1.TOA, TOOL_SYN2.TOA, TOOL_SYN3.TOA dalla share
e li unisce in una lista utensili.

Formato file (generato dalla NC, senza virgolette):
    METRIC
    ; FILE=1
    $TC_TP2[2802]=RENISHAW
    $TC_DP3[2802,1]=231.7696953
    $TC_DP6[2802,1]=2.83916183
    $TC_MOP2[2802,1]=0
    $TC_MOP11[2802,1]=11
    $TC_TP8[2802]=195
    $TC_MPP6[1,1]=2802
    ; ---
"""

import re
import os
from pathlib import Path


def _parse_toa_file(path: str) -> dict:
    """Legge un singolo file TOA e restituisce dict {T: {dati}}."""
    tools = {}
    try:
        with open(path, 'rb') as f:
            raw = f.read()
        text = raw.decode('latin-1')
        lines = text.split('\n')

        current_t = None
        for line in lines:
            line = line.strip()
            if not line or line.startswith(';'):
                continue

            # Nome utensile
            m = re.match(r'^\$TC_TP2\[(\d+)\]=(.+)', line)
            if m:
                current_t = int(m.group(1))
                if current_t not in tools:
                    tools[current_t] = {'t_number': current_t}
                tools[current_t]['name'] = m.group(2).strip().strip('"')
                continue

            if current_t is None:
                continue

            # Lunghezza Z
            m = re.match(r'^\$TC_DP3\[(\d+),1\]=(.+)', line)
            if m and int(m.group(1)) == current_t:
                try:
                    tools[current_t]['length'] = float(m.group(2))
                except ValueError:
                    pass
                continue

            # Raggio
            m = re.match(r'^\$TC_DP6\[(\d+),1\]=(.+)', line)
            if m and int(m.group(1)) == current_t:
                try:
                    tools[current_t]['radius'] = float(m.group(2))
                except ValueError:
                    pass
                continue

            # Vita residua (minuti)
            m = re.match(r'^\$TC_MOP2\[(\d+),1\]=(.+)', line)
            if m and int(m.group(1)) == current_t:
                try:
                    tools[current_t]['life_remaining'] = float(m.group(2))
                except ValueError:
                    pass
                continue

            # Vita totale (minuti)
            m = re.match(r'^\$TC_MOP11\[(\d+),1\]=(.+)', line)
            if m and int(m.group(1)) == current_t:
                try:
                    tools[current_t]['life_total'] = float(m.group(2))
                except ValueError:
                    pass
                continue

            # Status utensile
            m = re.match(r'^\$TC_TP8\[(\d+)\]=(.+)', line)
            if m and int(m.group(1)) == current_t:
                try:
                    tools[current_t]['status'] = int(m.group(2))
                    # Bit 0x0004 = disabilitato, Bit 0x0001 = attivo
                    status = tools[current_t]['status']
                    tools[current_t]['is_enabled'] = not bool(status & 0x0004)
                except ValueError:
                    pass
                continue

            # Posizione magazzino
            m = re.match(r'^\$TC_MPP6\[1,(\d+)\]=(\d+)', line)
            if m and int(m.group(2)) == current_t:
                pos = int(m.group(1))
                tools[current_t]['magazine'] = 1
                tools[current_t]['position'] = pos
                tools[current_t]['pos_label'] = f"M1.{pos:03d}"
                continue

    except Exception as e:
        pass

    return tools


def parse_toa_files(share_path: str) -> list:
    """
    Legge TOOL_SYN1.TOA, TOOL_SYN2.TOA, TOOL_SYN3.TOA dalla share
    e restituisce lista utensili unificata.
    """
    base = Path(share_path)
    all_tools = {}

    for n in [1, 2, 3]:
        fname = base / f"TOOL_SYN{n}.TOA"
        if fname.exists():
            tools = _parse_toa_file(str(fname))
            all_tools.update(tools)

    # Calcola percentuale vita residua
    result = []
    for t_num, tool in sorted(all_tools.items(), key=lambda x: x[1].get('position', 999)):
        total = tool.get('life_total', 0)
        remaining = tool.get('life_remaining', 0)
        if total and total > 0:
            pct = (remaining / total) * 100
            tool['life_percent'] = round(pct, 1)
            tool['is_worn'] = pct < 10
        else:
            tool['life_percent'] = None
            tool['is_worn'] = False

        # duplo — per ora sempre 1 (un T per posizione)
        tool['duplo'] = 1
        tool['tool_id'] = t_num

        result.append(tool)

    return result


def get_sync_info(share_path: str) -> dict:
    """Info su quali file TOA sono presenti sulla share."""
    base = Path(share_path)
    info = {'files': {}, 'total_tools': 0}
    all_tools = {}

    for n in [1, 2, 3]:
        fname = base / f"TOOL_SYN{n}.TOA"
        if fname.exists():
            tools = _parse_toa_file(str(fname))
            mtime = os.path.getmtime(str(fname))
            info['files'][f'TOOL_SYN{n}.TOA'] = {
                'present': True,
                'tools': len(tools),
                'mtime': mtime,
            }
            all_tools.update(tools)
        else:
            info['files'][f'TOOL_SYN{n}.TOA'] = {'present': False, 'tools': 0}

    info['total_tools'] = len(all_tools)
    return info


# ── Retrocompatibilità con tools.py ─────────────────────────────
# tools.py importa: parse_toa, parse_tma, MachineTool, MagazinePosition

from dataclasses import dataclass

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
    magazine:       int   = 1
    position:       int   = 0
    pos_label:      str   = ""

@dataclass
class MagazinePosition:
    magazine:  int
    position:  int
    t_number:  int
    pos_label: str = ""


def parse_toa(toa_path: str) -> list[MachineTool]:
    """Retrocompatibilità — legge un singolo file TOA."""
    import re
    raw = _parse_toa_file(toa_path)
    result = []
    for t_num, tool in sorted(raw.items()):
        result.append(MachineTool(
            t_number       = t_num,
            name           = tool.get("name", ""),
            length         = tool.get("length", 0.0),
            radius         = tool.get("radius", 0.0),
            life_remaining = tool.get("life_remaining", 0.0),
            life_total     = tool.get("life_total", 0.0),
            life_percent   = tool.get("life_percent"),
            is_worn        = tool.get("is_worn", False),
            is_enabled     = tool.get("is_enabled", True),
            status         = tool.get("status", 0),
            duplo          = tool.get("duplo", 1),
            magazine       = tool.get("magazine", 1),
            position       = tool.get("position", 0),
            pos_label      = tool.get("pos_label", ""),
        ))
    return result


def parse_tma(tma_path: str) -> list[MagazinePosition]:
    """Retrocompatibilità — legge un singolo file TMA."""
    import re
    result = []
    try:
        with open(tma_path, "rb") as f:
            raw = f.read()
        text  = raw.decode("latin-1")
        lines = text.split("\n")
        for line in lines:
            m = re.match(r"^\$TC_MPP6\[1,(\d+)\]=(\d+)", line.strip())
            if m:
                pos = int(m.group(1))
                t   = int(m.group(2))
                if t > 0:
                    result.append(MagazinePosition(
                        magazine  = 1,
                        position  = pos,
                        t_number  = t,
                        pos_label = f"M1.{pos:03d}",
                    ))
    except Exception:
        pass
    return result
