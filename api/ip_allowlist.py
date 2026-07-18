"""
api/ip_allowlist.py — Allowlist degli IP che possono raggiungere DMG Desk.
=========================================================================

Difesa in profondità (IEC 62443 — restrizione del condotto): oltre a TLS + login
PIN, si può limitare l'accesso web ai soli PC noti (le postazioni operatore). Gli
altri host della LAN ricevono 403 e non vedono nemmeno la pagina di login.

Gestita dall'admin dalla UI (Gestione operatori → "Accesso per IP") o dalla CLI di
riserva `scripts/ip_allowlist.py`.

Modello (coerente con api/auth.py):
- Stato in `ip_allowlist.json` LOCALE (accanto a config.json), gitignored.
- `{ "enabled": bool, "ips": ["10.0.0.5", "192.168.1.0/24", ...] }`.
- **Loopback sempre ammesso** (127.0.0.1/::1): CAM35 e il cam_tracker locale non
  vengono mai bloccati → recupero sempre possibile dalla macchina stessa.
- `enabled=false` o lista vuota → nessun filtro (tutti passano): scelta di sicurezza
  per non chiudere fuori tutti per sbaglio.

L'IP client reale è determinato dal middleware (rispetta DMG_TRUST_PROXY dietro il
reverse proxy). Questo modulo riceve già l'IP da valutare.
"""

import os
import copy
import json
import ipaddress
import threading
from datetime import datetime
from pathlib import Path

_FILE = "ip_allowlist.json"
_lock = threading.RLock()
_cache = {"mtime": None, "data": None}

# Registro in memoria dei tentativi BLOCCATI (ip → conteggio/ultimo/path). Si
# azzera al riavvio: serve all'admin per vedere chi ha provato a collegarsi e,
# se legittimo, autorizzarlo con un click. Capacità limitata per non crescere.
_tentativi: dict[str, dict] = {}
_TENT_MAX = 300


def _path() -> Path:
    override = os.environ.get("DMG_IP_ALLOWLIST_FILE")
    return Path(override) if override else Path(_FILE)


def _default() -> dict:
    return {"enabled": False, "ips": []}


def _carica() -> dict:
    """Carica lo stato (con cache invalidata da mtime). Ritorna sempre una COPIA
    così i caller possono mutarla senza inquinare la cache."""
    p = _path()
    if not p.exists():
        return _default()
    try:
        m = p.stat().st_mtime
        if _cache["mtime"] == m and _cache["data"] is not None:
            return copy.deepcopy(_cache["data"])
        d = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(d, dict):
            raise ValueError("struttura ip_allowlist.json non valida")
        d.setdefault("enabled", False)
        if not isinstance(d.get("ips"), list):
            d["ips"] = []
        _cache["mtime"] = m
        _cache["data"] = copy.deepcopy(d)
        return d
    except (json.JSONDecodeError, ValueError, OSError):
        # File illeggibile: non filtrare (fail-open sull'allowlist per non chiudere
        # fuori tutti); l'auth resta comunque attiva a valle.
        return _default()


def _salva(d: dict) -> None:
    p = _path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(d, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)
    _cache["mtime"] = None  # forza rilettura al prossimo accesso


def _normalizza(v: str) -> str | None:
    """Valida un IP singolo o una rete CIDR. Ritorna la forma canonica o None."""
    v = (v or "").strip()
    if not v:
        return None
    try:
        if "/" in v:
            return str(ipaddress.ip_network(v, strict=False))
        return str(ipaddress.ip_address(v))
    except ValueError:
        return None


def stato() -> dict:
    with _lock:
        d = _carica()
        return {"enabled": bool(d.get("enabled")), "ips": list(d.get("ips", []))}


def aggiungi(ip: str) -> dict:
    v = _normalizza(ip)
    if not v:
        return {"ok": False, "motivo": "ip_non_valido"}
    with _lock:
        d = _carica()
        if v not in d["ips"]:
            d["ips"].append(v)
        _salva(d)
        return {"ok": True, "enabled": bool(d.get("enabled")), "ips": d["ips"]}


def rimuovi(ip: str) -> dict:
    v = (ip or "").strip()
    with _lock:
        d = _carica()
        # Confronta sia sul valore grezzo sia sulla forma canonica
        vn = _normalizza(v)
        d["ips"] = [x for x in d.get("ips", []) if x != v and x != vn]
        _salva(d)
        return {"ok": True, "enabled": bool(d.get("enabled")), "ips": d["ips"]}


def imposta_abilitato(flag: bool) -> dict:
    with _lock:
        d = _carica()
        d["enabled"] = bool(flag)
        _salva(d)
        return {"ok": True, "enabled": d["enabled"], "ips": d.get("ips", [])}


def registra_tentativo(ip: str, path: str) -> None:
    """Registra un tentativo BLOCCATO da un IP non ammesso (per la UI admin)."""
    ora = datetime.now().isoformat(timespec="seconds")
    with _lock:
        rec = _tentativi.get(ip)
        if rec:
            rec["count"] += 1
            rec["ultimo"] = ora
            rec["path"] = path
        else:
            if len(_tentativi) >= _TENT_MAX:
                # rimuovi il più vecchio per fare spazio
                piu_vecchio = min(_tentativi.items(), key=lambda kv: kv[1]["ultimo"])
                _tentativi.pop(piu_vecchio[0], None)
            _tentativi[ip] = {"count": 1, "ultimo": ora, "path": path}


def tentativi() -> list[dict]:
    """Lista dei tentativi bloccati, più recenti prima."""
    with _lock:
        return [
            {"ip": k, **v}
            for k, v in sorted(_tentativi.items(),
                               key=lambda kv: kv[1]["ultimo"], reverse=True)
        ]


def pulisci_tentativi() -> None:
    with _lock:
        _tentativi.clear()


def _is_loopback(ip: str) -> bool:
    try:
        return ipaddress.ip_address(ip).is_loopback
    except ValueError:
        return False


def is_consentito(ip: str) -> bool:
    """True se l'IP può accedere. Loopback SEMPRE ammesso. Se disabilitato o lista
    vuota → tutti ammessi (nessun filtro)."""
    with _lock:
        d = _carica()
    if not d.get("enabled"):
        return True
    if _is_loopback(ip):
        return True
    ips = d.get("ips", [])
    if not ips:
        return True  # abilitato ma vuoto → non bloccare tutti (safety)
    try:
        addr = ipaddress.ip_address(ip)
    except ValueError:
        return False
    for entry in ips:
        try:
            if "/" in entry:
                if addr in ipaddress.ip_network(entry, strict=False):
                    return True
            elif str(addr) == entry:
                return True
        except ValueError:
            continue
    return False
