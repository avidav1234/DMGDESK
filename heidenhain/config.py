"""Configurazione macchine TNC 640 del bridge.

Default: le due Mikron P800 dell'officina (verificate sul campo 2026-07-16).
Override possibile via variabile d'ambiente TNC_MACHINES (JSON), es:
    TNC_MACHINES='{"p800-1":{"nome":"Mikron P800 #1","ip":"192.168.244.149"}}'
"""

from __future__ import annotations

import json
import os

_DEFAULT: dict[str, dict[str, str]] = {
    "p800-1": {"nome": "Mikron P800 #1", "ip": "192.168.244.149"},
    "p800-2": {"nome": "Mikron P800 #2", "ip": "192.168.244.150"},
}


def load_machines() -> dict[str, dict[str, str]]:
    raw = os.environ.get("TNC_MACHINES")
    if raw:
        try:
            data = json.loads(raw)
            if isinstance(data, dict) and data:
                return data
        except (ValueError, TypeError):
            pass
    return dict(_DEFAULT)


MACHINES = load_machines()
