"""
api/opcua_live.py — Client OPC UA diretto verso la macchina (R3).
==================================================================

Oggi il backend legge SOLO `OpcUaLegacy.log` (dump testuale prodotto dal PCU e
copiato sulla share ogni ~60s → ritardo fino a ~64s, campi fissi). Questo modulo
apre un canale **diretto** verso il server OPC UA della macchina
(`opcUa_Server_xp.exe` sul PCU 50, `opc.tcp://<PCU>:4840`) per **interrogarla
on-demand** e in tempo reale.

Principi (allineati ai vincoli del progetto):
- **OFF di default** (`DMG_OPCUA_ENABLED=1` per attivarlo). Finché è spento non
  apre nessuna connessione: il comportamento del backend è identico a prima.
- **Una sola sessione condivisa** (lock): il pipe OPI/BTSS della 840D PL è
  mono-coda e lento → un solo consumer, read in blocco (un round-trip per N nodi).
- **Fallback pulito**: qualsiasi errore/indisponibilità → ritorna None e il
  chiamante continua a usare il log. Non solleva mai verso il poller.
- **Nomi campo identici a `macchina_live.VAR_MAP`** → l'output è un drop-in che
  passa per lo stesso `_normalizza`.
- `asyncua` è **dipendenza opzionale**: se assente, il modulo è inerte.

⚠ **STATO 🟡 (macchina spenta il 2026-07-19)**: endpoint, `ns`, forma dei NodeId,
policy di sicurezza e credenziali NON sono ancora confermati sulla macchina viva.
La mappa nodi qui sotto è un DEFAULT ragionato (path BTSS noti da
`lettura tab utensili/test_opcua.py` + `VAR_MAP`), da validare con
`discover_opcua.py`/browse al primo accesso. Tutto è sovrascrivibile via env.
Vedi REPORT_RICERCHE_MACCHINA_R1_R2_R3.md § R3.
"""

from __future__ import annotations

import os
import time
import asyncio
from typing import Optional

try:
    from asyncua import Client as _UaClient  # asyncua 1.1.8 presente in ambiente
    _ASYNCUA_OK = True
except Exception:  # ImportError o altro → modulo inerte, non rompe il backend
    _UaClient = None
    _ASYNCUA_OK = False

from utils.logger import get_logger

log = get_logger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Configurazione (env — OFF di default, nessun segreto nel repo)
# ─────────────────────────────────────────────────────────────────────────────
def _env(nome: str, default: str = "") -> str:
    return (os.environ.get(nome, default) or "").strip()


def abilitato() -> bool:
    return _env("DMG_OPCUA_ENABLED", "0") == "1"


ENDPOINT   = _env("DMG_OPCUA_ENDPOINT", "opc.tcp://10.95.20.29:4840")  # LAN uffici del PCU
USER       = _env("DMG_OPCUA_USER")
PASSWORD   = _env("DMG_OPCUA_PASSWORD")
# Stringa di sicurezza asyncua completa, es.
#   "Basic256Sha256,SignAndEncrypt,client_cert.der,client_key.pem"
# Vuota = SecurityPolicy None. I file client_cert.der/client_key.pem esistono già
# in "lettura tab utensili/" (via SignAndEncrypt predisposta ma non ancora provata).
SECURITY   = _env("DMG_OPCUA_SECURITY")
try:
    NS = int(_env("DMG_OPCUA_NS", "2"))   # 🟡 namespace index da confermare live
except ValueError:
    NS = 2
TIMEOUT_S  = float(_env("DMG_OPCUA_TIMEOUT", "4") or "4")
# Intervallo minimo fra due letture reali (coalescing anti-martellamento del PCU)
MIN_INTERVAL_S = float(_env("DMG_OPCUA_MIN_INTERVAL", "2") or "2")
# Backoff dopo un fallimento di connessione (macchina spenta / rete) — non ritenta
# a ogni chiamata, evita di inondare i log e la rete.
BACKOFF_S  = float(_env("DMG_OPCUA_BACKOFF", "30") or "30")


# ─────────────────────────────────────────────────────────────────────────────
# Mappa nodi 🟡 — path BTSS noti → nome campo (identico a VAR_MAP dove esiste).
# Il NodeId effettivo è costruito come  ns=<NS>;s=<path>  salvo override esplicito
# via DMG_OPCUA_NODES ("campo=nodeid;campo=nodeid;...").
# ─────────────────────────────────────────────────────────────────────────────
_PATH_DEFAULT = {
    # campo backend           # path BTSS (da test_opcua.py / VAR_MAP)
    "stato_programma":        "/Channel/State/progStatus",
    "programma_attivo":       "/Channel/ProgramInfo/workPandProgName[u1]",
    "numero_utensile":        "/Channel/State/actTNumber",
    "utensile_attivo":        "/Channel/State/actToolIdent",
    "allarme":                "/Hmi/OpcUaAlarm1",
    "allarme_numeri":         "/Hmi/OpcUaAlarmNumbers",
    "modo_operativo":         "/BAG/State/opmode",
    # 🟡 path da CONFERMARE nel NodeTreeConfig.ini del server (non elencati in test_opcua):
    "override_feed":          "/Channel/State/feedRateOvr",
    "override_mandrino":      "/Channel/Spindle/spindleOvr",
    "feed_attuale":           "/Channel/State/actFeedRate",
    "rpm_attuale":            "/Channel/Spindle/actSpindleSpeed",
    "pallet_attivo":          "/PLC/DB0.DBB67",
}


def _costruisci_nodemap() -> dict[str, str]:
    """campo → stringa NodeId. Override completo via DMG_OPCUA_NODES."""
    override = _env("DMG_OPCUA_NODES")
    if override:
        m: dict[str, str] = {}
        for coppia in override.split(";"):
            if "=" in coppia:
                k, v = coppia.split("=", 1)
                k, v = k.strip(), v.strip()
                if k and v:
                    m[k] = v
        if m:
            return m
    return {campo: f"ns={NS};s={path}" for campo, path in _PATH_DEFAULT.items()}


NODEMAP = _costruisci_nodemap()


# ─────────────────────────────────────────────────────────────────────────────
# Stato modulo (sessione unica condivisa)
# ─────────────────────────────────────────────────────────────────────────────
_client = None                 # istanza asyncua.Client (o None)
_lock = asyncio.Lock()         # serializza l'accesso al singolo consumer
_connesso = False
_ultimo_errore: Optional[str] = None
_prossimo_retry_ts = 0.0       # backoff: non riconnette prima di questo istante
_ultima_lettura_ts = 0.0
_ultimo_valori: dict = {}      # cache dell'ultima lettura riuscita
_ultima_lettura_ok_ts: Optional[float] = None


def stato() -> dict:
    """Snapshot sincrono dello stato (nessun I/O). Per diagnostica/UI."""
    return {
        "abilitato": abilitato(),
        "asyncua_disponibile": _ASYNCUA_OK,
        "endpoint": ENDPOINT,
        "connesso": _connesso,
        "sicurezza": SECURITY or "None",
        "ns": NS,
        "n_nodi": len(NODEMAP),
        "ultimo_errore": _ultimo_errore,
        "ultima_lettura_ok_ts": _ultima_lettura_ok_ts,
        "ultimi_valori": dict(_ultimo_valori),
    }


async def _chiudi_client():
    global _client, _connesso
    if _client is not None:
        try:
            await _client.disconnect()
        except Exception:
            pass
    _client = None
    _connesso = False


async def _assicura_connessione() -> bool:
    """Connette se serve. Ritorna True se connesso. Applica backoff dopo un errore
    così a macchina spenta non ritenta a ogni tick. Non solleva."""
    global _client, _connesso, _ultimo_errore, _prossimo_retry_ts

    if not abilitato():
        _ultimo_errore = "disabilitato (DMG_OPCUA_ENABLED != 1)"
        return False
    if not _ASYNCUA_OK:
        _ultimo_errore = "asyncua non installato"
        return False
    if _connesso and _client is not None:
        return True

    now = time.monotonic()
    if now < _prossimo_retry_ts:
        return False  # ancora in backoff

    try:
        client = _UaClient(url=ENDPOINT, timeout=TIMEOUT_S)
        if USER:
            client.set_user(USER)
        if PASSWORD:
            client.set_password(PASSWORD)
        if SECURITY:
            await client.set_security_string(SECURITY)
        await asyncio.wait_for(client.connect(), timeout=TIMEOUT_S)
        _client = client
        _connesso = True
        _ultimo_errore = None
        log.info(f"OPC UA: connesso a {ENDPOINT}")
        return True
    except Exception as e:
        _ultimo_errore = f"connessione fallita: {type(e).__name__}: {e}"
        _prossimo_retry_ts = now + BACKOFF_S
        await _chiudi_client()
        # WARNING solo al primo fallimento del ciclo di backoff (evita spam)
        log.warning(f"OPC UA: {_ultimo_errore} — retry fra {BACKOFF_S:.0f}s")
        return False


async def leggi_segnali(campi: Optional[list[str]] = None) -> Optional[dict]:
    """Legge in BLOCCO i nodi richiesti (default: tutti) in un solo round-trip.

    Ritorna un dict {campo: valore_stringa} con gli STESSI nomi campo del log
    (drop-in per macchina_live._normalizza), oppure **None** se non disponibile
    (disattivo / asyncua assente / macchina irraggiungibile / errore lettura).
    Non solleva mai. Coalescing: entro MIN_INTERVAL_S ritorna l'ultima lettura.
    """
    global _ultima_lettura_ts, _ultimo_valori, _ultimo_errore, _ultima_lettura_ok_ts

    if not abilitato() or not _ASYNCUA_OK:
        return None

    nomi = campi or list(NODEMAP.keys())
    nodeids = [NODEMAP[c] for c in nomi if c in NODEMAP]
    if not nodeids:
        return None

    async with _lock:
        # Coalescing: non interrogare il PCU più spesso di MIN_INTERVAL_S
        now = time.monotonic()
        if _ultimo_valori and (now - _ultima_lettura_ts) < MIN_INTERVAL_S:
            return {c: _ultimo_valori[c] for c in nomi if c in _ultimo_valori}

        if not await _assicura_connessione():
            return None

        try:
            nodi = [_client.get_node(nid) for nid in nodeids]
            valori = await asyncio.wait_for(
                _client.read_values(nodi), timeout=TIMEOUT_S)
            out = {}
            campi_validi = [c for c in nomi if c in NODEMAP]
            for campo, val in zip(campi_validi, valori):
                out[campo] = "" if val is None else str(val)
            _ultimo_valori = out
            _ultima_lettura_ts = now
            _ultima_lettura_ok_ts = time.time()
            _ultimo_errore = None
            return dict(out)
        except Exception as e:
            _ultimo_errore = f"lettura fallita: {type(e).__name__}: {e}"
            log.warning(f"OPC UA: {_ultimo_errore}")
            # Connessione probabilmente caduta → forza riconnessione al prossimo giro
            await _chiudi_client()
            return None


async def diagnostica() -> dict:
    """Prova connessione + lettura una tantum e ritorna un rapporto ricco.
    Sicura da chiamare anche a macchina spenta (ritorna lo stato, non crasha).
    È il motore del pulsante/endpoint 'interroga adesso'."""
    rapporto = {"config": stato(), "tentativo": None, "valori": None}
    if not abilitato():
        rapporto["tentativo"] = "disabilitato"
        return rapporto
    if not _ASYNCUA_OK:
        rapporto["tentativo"] = "asyncua_assente"
        return rapporto
    valori = await leggi_segnali()
    if valori is None:
        rapporto["tentativo"] = "non_raggiungibile"
        rapporto["errore"] = _ultimo_errore
    else:
        rapporto["tentativo"] = "ok"
        rapporto["valori"] = valori
    rapporto["config"] = stato()
    return rapporto


async def chiudi():
    """Chiusura pulita (da chiamare nello shutdown del backend, se attivo)."""
    async with _lock:
        await _chiudi_client()


# Esecuzione diretta: diagnostica offline-safe.
#   py api/opcua_live.py           → mostra stato (di default disabilitato)
#   DMG_OPCUA_ENABLED=1 py api/opcua_live.py  → tenta la connessione reale
if __name__ == "__main__":
    import json as _json

    async def _main():
        r = await diagnostica()
        print(_json.dumps(r, indent=2, ensure_ascii=False, default=str))
        await chiudi()

    asyncio.run(_main())
