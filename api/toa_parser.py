"""
toa_parser.py — Tool Manager
Legge un file .TOA generato dalla macchina Sinumerik 840D
e restituisce una lista strutturata di utensili.

Il formato TOA è testo puro con assegnazioni $TC_* come:
    $TC_TP1[3470]=1
    $TC_TP2[3470]="FS25R2L85"
    $TC_DP3[3470,1]=110.93
    ...
"""

from __future__ import annotations
import re
from dataclasses import dataclass, field
from typing import Optional
from pathlib import Path


# ---------------------------------------------------------------------------
# Strutture dati (specchio del DB Tool Manager)
# ---------------------------------------------------------------------------

@dataclass
class CuttingEdge:
    edge_num: int
    tool_type: int = 0          # $TC_DP1
    edge_pos: float = 0.0       # $TC_DP2
    length1: float = 0.0        # $TC_DP3  (Z)
    length2: float = 0.0        # $TC_DP4  (Y)
    length3: float = 0.0        # $TC_DP5  (X)
    radius: float = 0.0         # $TC_DP6
    corner_radius: float = 0.0  # $TC_DP7
    length4: float = 0.0        # $TC_DP8
    length5: float = 0.0        # $TC_DP9
    angle1: float = 0.0         # $TC_DP10
    angle2: float = 0.0         # $TC_DP11
    wear_l1: float = 0.0        # $TC_DP12
    wear_l2: float = 0.0        # $TC_DP13
    wear_l3: float = 0.0        # $TC_DP14
    wear_r: float = 0.0         # $TC_DP15
    wear_corner: float = 0.0    # $TC_DP16
    adapter_l1: float = 0.0     # $TC_DP21
    adapter_l2: float = 0.0     # $TC_DP22
    adapter_l3: float = 0.0     # $TC_DP23
    clearance_angle: float = 0.0 # $TC_DP24
    dpc1: float = 0.0
    dpc2: float = 0.0
    dpc3: float = 0.0
    dpc4: float = 0.0
    dpc5: float = 0.0
    dpc6: float = 0.0
    dpc7: float = 0.0
    dpc8: float = 0.0
    dpc9: float = 0.0
    dpc10: float = 0.0
    mop1: float = 0.0           # preavviso vita [min]
    mop2: float = 0.0           # vita residua [min]
    mop3: float = 0.0
    mop4: float = 0.0
    mop5: float = 0.0
    mop6: float = 0.0
    mop11: float = 0.0          # vita nominale [min]
    mop13: float = 0.0
    mop15: float = 0.0


@dataclass
class MachineTool:
    """Utensile come presente in macchina — record della tabella magazzino."""
    tool_id: int                # posizione magazzino
    name: str = ""              # $TC_TP2
    duplo: int = 1              # $TC_TP1 (numero duplicato)
    status: int = 0             # $TC_TP8 (bitmask stato)
    monitoring: int = 0         # $TC_TP9
    magazine_type: int = 1      # $TC_TP7
    size_left: int = 1          # $TC_TP3
    size_right: int = 1         # $TC_TP4
    size_above: int = 1         # $TC_TP5
    size_below: int = 1         # $TC_TP6
    tp10: int = 0
    tp11: int = 0
    tpc1: int = 0
    tpc2: int = 0               # S-Max rpm
    tpc3: int = 0
    tpc4: int = 0
    tpc5: int = 0
    tpc6: int = 0
    tpc7: int = 0
    tpc8: int = 0
    tpc9: int = 0
    tpc10: int = 0
    edges: dict[int, CuttingEdge] = field(default_factory=dict)

    @property
    def is_enabled(self) -> bool:
        """Utensile abilitato (bit 1 di $TC_TP8)."""
        return bool(self.status & 0x02)

    @property
    def is_worn(self) -> bool:
        """Vita esaurita (bit 4 di $TC_TP8)."""
        return bool(self.status & 0x10)

    @property
    def life_percent(self) -> Optional[float]:
        """Percentuale vita residua del primo tagliente, None se non monitorato."""
        if self.monitoring == 0:
            return None
        e = self.edges.get(1)
        if e and e.mop11 > 0:
            return round((e.mop2 / e.mop11) * 100, 1)
        return None

    @property
    def main_length(self) -> float:
        """Lunghezza Z del primo tagliente."""
        return self.edges.get(1, CuttingEdge(1)).length1

    @property
    def main_radius(self) -> float:
        """Raggio del primo tagliente."""
        return self.edges.get(1, CuttingEdge(1)).radius


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

# Pattern regex per le varie assegnazioni
_RE_TP_SCALAR = re.compile(
    r'^\$TC_TP(\d+)\[(\d+)\]\s*=\s*(.+)$'
)
_RE_TPC_SCALAR = re.compile(
    r'^\$TC_TPC(\d+)\[(\d+)\]\s*=\s*(.+)$'
)
_RE_DP = re.compile(
    r'^\$TC_DP(\d+)\[(\d+),(\d+)\]\s*=\s*(.+)$'
)
_RE_DPC = re.compile(
    r'^\$TC_DPC(\d+)\[(\d+),(\d+)\]\s*=\s*(.+)$'
)
_RE_MOP = re.compile(
    r'^\$TC_MOP(\d+)\[(\d+),(\d+)\]\s*=\s*(.+)$'
)


def _parse_value(raw: str) -> str | float | int:
    """Converte il valore raw in tipo Python appropriato."""
    raw = raw.strip()
    if raw.startswith('"') and raw.endswith('"'):
        return raw[1:-1]
    try:
        if '.' in raw:
            return float(raw)
        return int(raw)
    except ValueError:
        return raw


def parse_toa(path: str | Path) -> dict[int, MachineTool]:
    """
    Legge un file .TOA e restituisce un dizionario
    {tool_id: MachineTool} con tutti gli utensili presenti.
    """
    tools: dict[int, MachineTool] = {}
    path = Path(path)

    with open(path, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.strip()

            # Salta commenti, righe vuote, header, comandi NC
            if not line or line.startswith(';') or line.startswith('%'):
                continue
            if not line.startswith('$TC_'):
                continue

            # --- $TC_TP (dati generali utensile) ---
            m = _RE_TP_SCALAR.match(line)
            if m:
                param_num = int(m.group(1))
                tid = int(m.group(2))
                val = _parse_value(m.group(3))
                t = tools.setdefault(tid, MachineTool(tool_id=tid))
                _apply_tp(t, param_num, val)
                continue

            # --- $TC_TPC (parametri estesi DMG) ---
            m = _RE_TPC_SCALAR.match(line)
            if m:
                param_num = int(m.group(1))
                tid = int(m.group(2))
                val = _parse_value(m.group(3))
                t = tools.setdefault(tid, MachineTool(tool_id=tid))
                _apply_tpc(t, param_num, val)
                continue

            # --- $TC_DP (dati tagliente geometria/usura) ---
            m = _RE_DP.match(line)
            if m:
                param_num = int(m.group(1))
                tid = int(m.group(2))
                eid = int(m.group(3))
                val = _parse_value(m.group(4))
                t = tools.setdefault(tid, MachineTool(tool_id=tid))
                e = t.edges.setdefault(eid, CuttingEdge(edge_num=eid))
                _apply_dp(e, param_num, val)
                continue

            # --- $TC_DPC (parametri controllo tagliente) ---
            m = _RE_DPC.match(line)
            if m:
                param_num = int(m.group(1))
                tid = int(m.group(2))
                eid = int(m.group(3))
                val = _parse_value(m.group(4))
                t = tools.setdefault(tid, MachineTool(tool_id=tid))
                e = t.edges.setdefault(eid, CuttingEdge(edge_num=eid))
                _apply_dpc(e, param_num, val)
                continue

            # --- $TC_MOP (monitoraggio vita) ---
            m = _RE_MOP.match(line)
            if m:
                param_num = int(m.group(1))
                tid = int(m.group(2))
                eid = int(m.group(3))
                val = _parse_value(m.group(4))
                t = tools.setdefault(tid, MachineTool(tool_id=tid))
                e = t.edges.setdefault(eid, CuttingEdge(edge_num=eid))
                _apply_mop(e, param_num, val)
                continue

    return tools


def _apply_tp(t: MachineTool, n: int, v):
    mapping = {
        1: 'duplo', 2: 'name', 3: 'size_left', 4: 'size_right',
        5: 'size_above', 6: 'size_below', 7: 'magazine_type',
        8: 'status', 9: 'monitoring', 10: 'tp10', 11: 'tp11',
    }
    if n in mapping:
        setattr(t, mapping[n], v)


def _apply_tpc(t: MachineTool, n: int, v):
    mapping = {
        1: 'tpc1', 2: 'tpc2', 3: 'tpc3', 4: 'tpc4', 5: 'tpc5',
        6: 'tpc6', 7: 'tpc7', 8: 'tpc8', 9: 'tpc9', 10: 'tpc10',
    }
    if n in mapping:
        setattr(t, mapping[n], v)


def _apply_dp(e: CuttingEdge, n: int, v):
    mapping = {
        1: 'tool_type', 2: 'edge_pos', 3: 'length1', 4: 'length2',
        5: 'length3', 6: 'radius', 7: 'corner_radius', 8: 'length4',
        9: 'length5', 10: 'angle1', 11: 'angle2',
        12: 'wear_l1', 13: 'wear_l2', 14: 'wear_l3',
        15: 'wear_r', 16: 'wear_corner',
        21: 'adapter_l1', 22: 'adapter_l2', 23: 'adapter_l3',
        24: 'clearance_angle',
    }
    if n in mapping:
        setattr(e, mapping[n], float(v) if isinstance(v, (int, float)) else v)


def _apply_dpc(e: CuttingEdge, n: int, v):
    attr = f'dpc{n}'
    if hasattr(e, attr):
        setattr(e, attr, float(v) if isinstance(v, (int, float)) else v)


def _apply_mop(e: CuttingEdge, n: int, v):
    mapping = {
        1: 'mop1', 2: 'mop2', 3: 'mop3', 4: 'mop4',
        5: 'mop5', 6: 'mop6', 11: 'mop11', 13: 'mop13', 15: 'mop15',
    }
    if n in mapping:
        setattr(e, mapping[n], float(v) if isinstance(v, (int, float)) else v)


# ---------------------------------------------------------------------------
# Utility di confronto
# ---------------------------------------------------------------------------

def extract_tools_from_mpf(mpf_content: str) -> set[str]:
    """
    Estrae i nomi utensile da un programma MPF/SPF.
    Cerca i pattern:
      T="NOME_UTENSILE"   (chiamata per nome)
      T=1234              (chiamata per numero posizione)
    Restituisce un set di nomi (stringhe).
    """
    names: set[str] = set()

    # T="NOME" — chiamata per nome
    for m in re.finditer(r'T="([^"]+)"', mpf_content, re.IGNORECASE):
        names.add(m.group(1).upper())

    # T=NUMERO — chiamata per numero posizione (meno comune ma presente)
    # Non lo espandiamo qui senza sapere la mappatura posizione→nome
    # TODO: gestire T=numero se necessario

    return names


def check_tools_availability(
    required: set[str],
    machine_tools: dict[int, MachineTool],
) -> dict:
    """
    Confronta gli utensili richiesti dal programma con quelli in macchina.

    Restituisce:
    {
        "ok": [lista nomi presenti e abilitati],
        "missing": [lista nomi non trovati in macchina],
        "disabled": [lista nomi presenti ma disabilitati/esauriti],
        "worn": [lista nomi con vita quasi esaurita (<10%)],
    }
    """
    # Indice nome → lista utensili (possono esserci duplicati/sister tools)
    by_name: dict[str, list[MachineTool]] = {}
    for t in machine_tools.values():
        key = t.name.upper()
        by_name.setdefault(key, []).append(t)

    result = {
        "ok": [],
        "missing": [],
        "disabled": [],
        "worn": [],
    }

    for name in sorted(required):
        candidates = by_name.get(name, [])
        if not candidates:
            result["missing"].append(name)
            continue

        # Controlla se almeno uno è abilitato e non esaurito
        enabled = [c for c in candidates if c.is_enabled and not c.is_worn]
        if not enabled:
            result["disabled"].append(name)
            continue

        # Controlla vita residua
        low_life = all(
            (c.life_percent is not None and c.life_percent < 10)
            for c in enabled
        )
        if low_life:
            result["worn"].append(name)
        else:
            result["ok"].append(name)

    return result


# ---------------------------------------------------------------------------
# Test rapido
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Uso: python toa_parser.py <percorso_file.TOA>")
        sys.exit(1)

    tools = parse_toa(sys.argv[1])
    print(f"\nUtensili trovati: {len(tools)}\n")
    for tid, t in sorted(tools.items()):
        life = t.life_percent
        life_str = f"  vita: {life}%" if life is not None else ""
        print(
            f"  [{tid:4d}]  {t.name:<20s}  "
            f"L={t.main_length:8.3f}  R={t.main_radius:7.3f}  "
            f"status={t.status:3d}{life_str}"
        )


# ---------------------------------------------------------------------------
# Parser TMA — mappa magazzino
# ---------------------------------------------------------------------------

@dataclass
class MagazinePosition:
    """Una posizione fisica nel magazzino."""
    magazine: int       # numero magazine (1=Regal_120, 2=BeladeMagazin, 9998=buffer, 9999=carico)
    position: int       # numero posizione nel magazine
    tool_id: int        # T-number interno dell'utensile (0 = vuota)
    state: int = 0      # $TC_MPP4 stato posizione


@dataclass 
class MagazineInfo:
    """Dati descrittivi di un magazine."""
    number: int
    name: str           # $TC_MAP2
    mag_type: int = 0   # $TC_MAP1
    num_places: int = 0 # $TC_MAP3


def parse_tma(path: str | Path) -> tuple[dict[int, MagazineInfo], list[MagazinePosition]]:
    """
    Legge un file .TMA e restituisce:
    - dict {magazine_num: MagazineInfo}
    - lista di MagazinePosition (solo posizioni occupate, tool_id > 0)
    
    $TC_MPP66[mag, pos] = T-number interno (nota: doppio 6, non $TC_MPP6)
    $TC_MAP2[mag] = nome magazine
    """
    path = Path(path)
    magazines: dict[int, MagazineInfo] = {}
    positions: list[MagazinePosition] = []

    _RE_MAP = re.compile(r'^\$TC_MAP(\d+)\[(\d+)\]\s*=\s*(.+)$')
    _RE_MPP66 = re.compile(r'^\$TC_MPP66\[(\d+),(\d+)\]\s*=\s*(\d+)$')
    _RE_MPP4 = re.compile(r'^\$TC_MPP4\[(\d+),(\d+)\]\s*=\s*(\d+)$')

    # Prima passata: raccoglie stati posizione
    states: dict[tuple[int,int], int] = {}

    with open(path, encoding="utf-8", errors="replace") as f:
        for raw_line in f:
            line = raw_line.strip()
            if not line or line.startswith(';'):
                continue

            # $TC_MAP* — dati magazine
            m = _RE_MAP.match(line)
            if m:
                param = int(m.group(1))
                mag = int(m.group(2))
                val = _parse_value(m.group(3))
                info = magazines.setdefault(mag, MagazineInfo(number=mag, name=""))
                if param == 1:
                    info.mag_type = int(val) if isinstance(val, (int, float)) else 0
                elif param == 2:
                    info.name = str(val)
                elif param == 3:
                    info.num_places = int(val) if isinstance(val, (int, float)) else 0
                continue

            # $TC_MPP4 — stato posizione
            m = _RE_MPP4.match(line)
            if m:
                mag, pos, state = int(m.group(1)), int(m.group(2)), int(m.group(3))
                states[(mag, pos)] = state
                continue

            # $TC_MPP66 — T-number in posizione (NOTA: doppio 6)
            m = _RE_MPP66.match(line)
            if m:
                mag = int(m.group(1))
                pos = int(m.group(2))
                tid = int(m.group(3))
                if tid > 0:  # 0 = posizione vuota
                    positions.append(MagazinePosition(
                        magazine=mag,
                        position=pos,
                        tool_id=tid,
                        state=states.get((mag, pos), 0)
                    ))
                continue

    return magazines, positions


def build_position_map(
    positions: list[MagazinePosition],
    tools: dict[int, MachineTool]
) -> dict[str, list[dict]]:
    """
    Costruisce la mappa nome_utensile → lista posizioni in magazzino.
    Utile per sapere dove fisicamente si trova ogni utensile.
    
    Restituisce:
    {
        "FS25R2L85": [
            {"magazine": 1, "position": 3, "tool_id": 3470, "duplo": 1},
            {"magazine": 1, "position": 5, "tool_id": 3471, "duplo": 2},
        ],
        ...
    }
    """
    result: dict[str, list[dict]] = {}
    for pos in positions:
        tool = tools.get(pos.tool_id)
        if tool:
            name = tool.name.upper()
            result.setdefault(name, []).append({
                "magazine": pos.magazine,
                "position": pos.position,
                "tool_id": pos.tool_id,
                "duplo": tool.duplo,
                "status": tool.status,
                "life_percent": tool.life_percent,
            })
    return result


# ---------------------------------------------------------------------------
# Test TMA
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import sys
    if len(sys.argv) >= 3:
        tma_path = sys.argv[2]
        tools = parse_toa(sys.argv[1])
        magazines, positions = parse_tma(tma_path)

        print(f"\nMagazine trovati: {len(magazines)}")
        for mag in sorted(magazines.values(), key=lambda m: m.number):
            print(f"  [{mag.number:4d}] {mag.name:<25s} tipo={mag.mag_type} posti={mag.num_places}")

        print(f"\nPosizioni occupate: {len(positions)}")
        pos_map = build_position_map(positions, tools)
        for name, locs in sorted(pos_map.items()):
            for loc in locs:
                print(f"  {name:<25s} mag={loc['magazine']} pos={loc['position']:3d} T={loc['tool_id']} duplo={loc['duplo']}")
