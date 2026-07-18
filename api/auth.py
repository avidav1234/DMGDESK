"""
api/auth.py — Autenticazione operatori con PIN.
================================================

Modello (deciso 2026-07-08, vincolo "accesso da più PC" → niente bind localhost):

- Account e PIN memorizzati **localmente** (``auth_accounts.json`` accanto a
  ``config.json``), MAI sulla share di rete: gli hash restano fuori dalla
  share P: (percorso locale al backend).
- PIN hashati con PBKDF2-SHA256 + salt per account (solo stdlib, nessuna
  dipendenza aggiuntiva).
- Sessioni: token opachi in memoria con scadenza. A differenza della sola
  API key, il segreto (PIN) NON entra mai nel bundle frontend: l'operatore
  digita il PIN, il server verifica ed emette un token temporaneo.
- Anti-forza-bruta: lockout progressivo per operatore (un PIN corto senza
  lockout si forza da LAN in poco tempo).
- I client non interattivi (cam_tracker, self-call) restano su `DMG_API_KEY`
  da env: il middleware accetta token di sessione OPPURE API key.

Reset PIN (3 vie, vedi scelte utente):
  1. `POST /api/auth/admin/reset-pin` protetto da `DMG_API_KEY` (browser).
  2. Primo accesso: un operatore senza PIN lo imposta al primo login.
  3. `scripts/reset_pin.py` (CLI sul server) — riserva sempre disponibile.

Attivazione: `DMG_AUTH_ENABLED=1`. Default OFF = comportamento attuale
invariato (nessuna richiesta di login).
"""

import os
import json
import hmac
import hashlib
import secrets
import threading
from datetime import datetime, timedelta
from pathlib import Path

# ── Configurazione ────────────────────────────────────────────────────────────

def _env_int(nome: str, default: int, lo: int, hi: int) -> int:
    """Legge un intero da env con clamp [lo, hi]; default se assente/non valido."""
    try:
        v = int(os.environ.get(nome, str(default)))
    except (ValueError, TypeError):
        v = default
    return max(lo, min(hi, v))


# Lunghezza PIN — configurabile via env (default 4-10 invariati). Alzare
# DMG_PIN_MIN a 6 quando gli operatori sono avvisati: i PIN esistenti continuano a
# funzionare (la verifica non controlla la lunghezza), il vincolo scatta solo
# all'impostazione di un PIN NUOVO.
PIN_MIN_LEN = _env_int("DMG_PIN_MIN", 4, 4, 12)
PIN_MAX_LEN = _env_int("DMG_PIN_MAX", 10, PIN_MIN_LEN, 12)
_PBKDF2_ITER = 200_000            # iterazioni PBKDF2 (rallenta il brute-force offline)
_LOCKOUT_SOGLIA = 5               # tentativi errati prima del primo blocco
_LOCKOUT_BASE_SEC = 60            # durata primo blocco; poi raddoppia
_LOCKOUT_MAX_SEC = 3600           # tetto al blocco progressivo

_ACCOUNTS_FILE = "auth_accounts.json"   # locale (cwd, accanto a config.json)

# Ruoli operatore. Modello semplice (no RBAC per-endpoint): "admin" gestisce gli
# operatori; "operatore" è l'uso normale (login, vista e controllo macchina).
RUOLI_VALIDI = ("admin", "operatore")
RUOLO_DEFAULT = "operatore"

DEFAULT_OPERATORI = [
    {"id": "op1", "nome": "Operatore 1"},
    {"id": "op2", "nome": "Operatore 2"},
]

# Stato in memoria (perso al riavvio: gli operatori rifanno il login).
_lock = threading.RLock()
_sessions: dict[str, dict] = {}    # token -> {op_id, nome, scade}
_fails: dict[str, dict] = {}       # op_id -> {"n": int, "locked_until": datetime|None}


# ── Helpers configurazione runtime ────────────────────────────────────────────

def auth_attiva() -> bool:
    """True se l'autenticazione operatori è attiva (env DMG_AUTH_ENABLED=1).
    Letta dinamicamente (non a import-time) così i test e l'attivazione a caldo
    funzionano senza reimportare il modulo."""
    return os.environ.get("DMG_AUTH_ENABLED", "").strip() == "1"


def _session_durata() -> timedelta:
    try:
        ore = int(os.environ.get("DMG_AUTH_SESSION_ORE", "12"))
    except (ValueError, TypeError):
        ore = 12
    return timedelta(hours=max(1, ore))


def _accounts_path() -> Path:
    """File account: locale, accanto a config.json (stesso cwd del backend).
    Override per test via env DMG_AUTH_ACCOUNTS_FILE."""
    override = os.environ.get("DMG_AUTH_ACCOUNTS_FILE")
    return Path(override) if override else Path(_ACCOUNTS_FILE)


def _now() -> datetime:
    return datetime.now()


def _now_iso() -> str:
    return _now().isoformat(timespec="seconds")


# ── Persistenza account ───────────────────────────────────────────────────────

def _carica() -> dict:
    """Carica gli account dal file locale. Se manca, crea i 2 operatori di
    default SENZA PIN (verrà impostato al primo accesso o via reset)."""
    p = _accounts_path()
    if not p.exists():
        data = {"operatori": [dict(o) for o in DEFAULT_OPERATORI]}
        _salva(data)
        return data
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("operatori"), list):
            raise ValueError("struttura auth_accounts.json non valida")
        return data
    except (json.JSONDecodeError, ValueError, OSError):
        # File corrotto: NON sovrascriviamo silenziosamente (potrebbe contenere
        # i PIN reali). Ritorniamo i default in memoria e lasciamo il file com'è
        # — il reset via CLI o la riparazione manuale restano possibili.
        from utils.logger import get_logger
        get_logger("api.auth").error(
            f"auth_accounts.json illeggibile ({p}) — uso operatori default in memoria")
        return {"operatori": [dict(o) for o in DEFAULT_OPERATORI]}


def _salva(data: dict) -> None:
    """Scrittura atomica del file account."""
    p = _accounts_path()
    tmp = p.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)


# ── Hashing PIN ───────────────────────────────────────────────────────────────

def _pin_valido(pin: str) -> bool:
    """PIN = solo cifre, lunghezza PIN_MIN_LEN..PIN_MAX_LEN."""
    return isinstance(pin, str) and pin.isdigit() and PIN_MIN_LEN <= len(pin) <= PIN_MAX_LEN


def _hash_pin(pin: str, salt: bytes | None = None) -> tuple[str, str]:
    """Ritorna (hash_hex, salt_hex) con PBKDF2-SHA256."""
    if salt is None:
        salt = secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", pin.encode("utf-8"), salt, _PBKDF2_ITER)
    return dk.hex(), salt.hex()


def _verifica_hash(pin: str, hash_hex: str, salt_hex: str) -> bool:
    """Confronto a tempo costante del PIN contro l'hash memorizzato."""
    try:
        salt = bytes.fromhex(salt_hex)
    except (ValueError, TypeError):
        return False
    calc, _ = _hash_pin(pin, salt)
    return hmac.compare_digest(calc, hash_hex or "")


def _pin_in_uso(data: dict, pin: str, escludi_op_id: str | None = None) -> bool:
    """True se un ALTRO operatore ha già questo PIN. I PIN devono essere UNICI:
    il login-solo-PIN identifica l'operatore dal PIN, quindi due operatori non
    possono condividerlo."""
    for o in data.get("operatori", []):
        if o.get("id") == escludi_op_id:
            continue
        if o.get("pin_hash") and _verifica_hash(pin, o.get("pin_hash", ""), o.get("pin_salt", "")):
            return True
    return False


# ── Lockout anti-forza-bruta ──────────────────────────────────────────────────

def _tempo_blocco(op_id: str) -> int:
    """Secondi residui di blocco per l'operatore (0 se non bloccato)."""
    rec = _fails.get(op_id)
    if not rec or not rec.get("locked_until"):
        return 0
    resto = (rec["locked_until"] - _now()).total_seconds()
    return int(resto) if resto > 0 else 0


def _registra_fail(op_id: str) -> None:
    rec = _fails.setdefault(op_id, {"n": 0, "locked_until": None})
    rec["n"] += 1
    if rec["n"] >= _LOCKOUT_SOGLIA:
        # Blocco progressivo: 60s, 120s, 240s... con tetto.
        n_blocchi = rec["n"] // _LOCKOUT_SOGLIA
        durata = min(_LOCKOUT_BASE_SEC * (2 ** (n_blocchi - 1)), _LOCKOUT_MAX_SEC)
        rec["locked_until"] = _now() + timedelta(seconds=durata)


def _reset_fail(op_id: str) -> None:
    _fails.pop(op_id, None)


# ── Sessioni ──────────────────────────────────────────────────────────────────

def _prune_sessioni() -> None:
    ora = _now()
    scaduti = [t for t, s in _sessions.items() if s["scade"] <= ora]
    for t in scaduti:
        _sessions.pop(t, None)


def _crea_sessione(op: dict) -> dict:
    token = secrets.token_urlsafe(32)
    scade = _now() + _session_durata()
    _sessions[token] = {"op_id": op["id"], "nome": op.get("nome"),
                        "ruolo": op.get("ruolo", RUOLO_DEFAULT), "scade": scade}
    return {"token": token, "scade": scade.isoformat(timespec="seconds")}


def valida_token(token: str | None) -> dict | None:
    """Ritorna {op_id, nome, ruolo, scade} se il token è valido e non scaduto,
    else None. Usata dal middleware su ogni richiesta protetta."""
    if not token:
        return None
    with _lock:
        _prune_sessioni()
        s = _sessions.get(token)
        if not s:
            return None
        return {"op_id": s["op_id"], "nome": s["nome"],
                "ruolo": s.get("ruolo", RUOLO_DEFAULT),
                "scade": s["scade"].isoformat(timespec="seconds")}


def logout(token: str | None) -> bool:
    if not token:
        return False
    with _lock:
        return _sessions.pop(token, None) is not None


# ── API pubblica del modulo ───────────────────────────────────────────────────

def lista_operatori() -> list[dict]:
    """Lista operatori SENZA hash: {id, nome, pin_impostato}. Per la pagina login."""
    with _lock:
        data = _carica()
        return [
            {"id": o["id"], "nome": o.get("nome", o["id"]),
             "pin_impostato": bool(o.get("pin_hash")),
             "ruolo": o.get("ruolo", RUOLO_DEFAULT)}
            for o in data.get("operatori", [])
        ]


def _trova_op(data: dict, op_id: str) -> dict | None:
    return next((o for o in data.get("operatori", []) if o.get("id") == op_id), None)


def imposta_pin(op_id: str, nuovo_pin: str) -> dict:
    """Imposta/sostituisce il PIN di un operatore. Usata da reset (master/CLI)
    e da cambia_pin. Ritorna {ok, motivo?}."""
    if not _pin_valido(nuovo_pin):
        return {"ok": False, "motivo": "pin_non_valido",
                "detail": f"Il PIN deve avere {PIN_MIN_LEN}-{PIN_MAX_LEN} cifre numeriche"}
    with _lock:
        data = _carica()
        op = _trova_op(data, op_id)
        if not op:
            return {"ok": False, "motivo": "operatore_sconosciuto"}
        if _pin_in_uso(data, nuovo_pin, escludi_op_id=op_id):
            return {"ok": False, "motivo": "pin_duplicato",
                    "detail": "PIN già usato da un altro operatore — scegline un altro"}
        h, s = _hash_pin(nuovo_pin)
        op["pin_hash"] = h
        op["pin_salt"] = s
        op["pin_impostato_il"] = _now_iso()
        _salva(data)
        _reset_fail(op_id)
        return {"ok": True}


def azzera_pin(op_id: str) -> dict:
    """Cancella il PIN: il prossimo login lo re-imposta (reset 'soft')."""
    with _lock:
        data = _carica()
        op = _trova_op(data, op_id)
        if not op:
            return {"ok": False, "motivo": "operatore_sconosciuto"}
        op.pop("pin_hash", None)
        op.pop("pin_salt", None)
        op.pop("pin_impostato_il", None)
        _salva(data)
        _reset_fail(op_id)
        # Invalida eventuali sessioni aperte dell'operatore
        for t in [t for t, sess in _sessions.items() if sess["op_id"] == op_id]:
            _sessions.pop(t, None)
        return {"ok": True}


def login(op_id: str, pin: str) -> dict:
    """Autentica un operatore.
    - Operatore senza PIN → il PIN fornito diventa il suo (primo accesso).
    - Operatore con PIN → verifica; lockout progressivo sui fallimenti.
    Ritorna {ok, token?, nome?, scade?, pin_creato?, motivo?, riprova_sec?}.
    """
    with _lock:
        bloccato = _tempo_blocco(op_id)
        if bloccato > 0:
            return {"ok": False, "motivo": "bloccato", "riprova_sec": bloccato}

        data = _carica()
        op = _trova_op(data, op_id)
        if not op:
            # Registriamo comunque il fail: evita enumerazione a tentativi liberi.
            _registra_fail(op_id)
            return {"ok": False, "motivo": "credenziali_non_valide"}

        # Primo accesso: nessun PIN impostato → lo impostiamo ora.
        if not op.get("pin_hash"):
            if not _pin_valido(pin):
                return {"ok": False, "motivo": "pin_non_valido",
                        "detail": f"Scegli un PIN di {PIN_MIN_LEN}-{PIN_MAX_LEN} cifre"}
            if _pin_in_uso(data, pin, escludi_op_id=op_id):
                return {"ok": False, "motivo": "pin_duplicato",
                        "detail": "PIN già usato da un altro operatore — scegline un altro"}
            h, s = _hash_pin(pin)
            op["pin_hash"] = h
            op["pin_salt"] = s
            op["pin_impostato_il"] = _now_iso()
            _salva(data)
            _reset_fail(op_id)
            sess = _crea_sessione(op)
            return {"ok": True, "token": sess["token"], "scade": sess["scade"],
                    "nome": op.get("nome"), "pin_creato": True}

        # Verifica PIN esistente.
        if _verifica_hash(pin, op.get("pin_hash", ""), op.get("pin_salt", "")):
            _reset_fail(op_id)
            sess = _crea_sessione(op)
            return {"ok": True, "token": sess["token"], "scade": sess["scade"],
                    "nome": op.get("nome"), "pin_creato": False}

        _registra_fail(op_id)
        bloccato = _tempo_blocco(op_id)
        res = {"ok": False, "motivo": "credenziali_non_valide"}
        if bloccato > 0:
            res["motivo"] = "bloccato"
            res["riprova_sec"] = bloccato
        return res


def login_con_pin(pin: str, ip: str | None = None) -> dict:
    """Login SOLO col PIN: identifica l'operatore dal PIN (unico). Nessuna
    selezione operatore. Il lockout è per IP (prima del match non c'è un op_id
    a cui attribuire il tentativo). Ritorna {ok, token, nome, ruolo, scade} |
    {ok:False, motivo, riprova_sec?}."""
    chiave = f"ip:{ip or '?'}"
    with _lock:
        bloccato = _tempo_blocco(chiave)
        if bloccato > 0:
            return {"ok": False, "motivo": "bloccato", "riprova_sec": bloccato}

        if _pin_valido(pin):
            data = _carica()
            for op in data.get("operatori", []):
                if op.get("pin_hash") and _verifica_hash(pin, op.get("pin_hash", ""),
                                                         op.get("pin_salt", "")):
                    _reset_fail(chiave)
                    sess = _crea_sessione(op)
                    return {"ok": True, "token": sess["token"], "scade": sess["scade"],
                            "nome": op.get("nome"), "ruolo": op.get("ruolo", RUOLO_DEFAULT)}

        # PIN non valido o nessun operatore corrisponde → tentativo fallito.
        _registra_fail(chiave)
        bloccato = _tempo_blocco(chiave)
        if bloccato > 0:
            return {"ok": False, "motivo": "bloccato", "riprova_sec": bloccato}
        return {"ok": False, "motivo": "credenziali_non_valide"}


def cambia_pin(op_id: str, pin_vecchio: str, pin_nuovo: str) -> dict:
    """Cambio PIN da parte dell'operatore autenticato (richiede il PIN attuale)."""
    with _lock:
        data = _carica()
        op = _trova_op(data, op_id)
        if not op or not op.get("pin_hash"):
            return {"ok": False, "motivo": "operatore_sconosciuto"}
        if not _verifica_hash(pin_vecchio, op.get("pin_hash", ""), op.get("pin_salt", "")):
            return {"ok": False, "motivo": "pin_attuale_errato"}
    # imposta_pin riacquisisce il lock (RLock → rientrante)
    return imposta_pin(op_id, pin_nuovo)


# ── Gestione operatori (admin, dietro master key) ─────────────────────────────

import re as _re


def _genera_id(data: dict) -> str:
    """Nuovo id operatore univoco 'opN' (N = massimo esistente + 1)."""
    massimo = 0
    for o in data.get("operatori", []):
        m = _re.fullmatch(r"op(\d+)", str(o.get("id") or ""))
        if m:
            massimo = max(massimo, int(m.group(1)))
    return f"op{massimo + 1}"


def aggiungi_operatore(nome: str) -> dict:
    """Crea un nuovo operatore SENZA PIN (lo imposterà al primo accesso)."""
    nome = (nome or "").strip()
    if not nome:
        return {"ok": False, "motivo": "nome_richiesto"}
    with _lock:
        data = _carica()
        if any((o.get("nome") or "").strip().lower() == nome.lower()
               for o in data.get("operatori", [])):
            return {"ok": False, "motivo": "nome_duplicato"}
        op_id = _genera_id(data)
        data.setdefault("operatori", []).append(
            {"id": op_id, "nome": nome, "ruolo": RUOLO_DEFAULT})
        _salva(data)
        return {"ok": True,
                "operatore": {"id": op_id, "nome": nome, "pin_impostato": False,
                              "ruolo": RUOLO_DEFAULT}}


def rinomina_operatore(op_id: str, nuovo_nome: str) -> dict:
    """Rinomina un operatore (l'id resta stabile: PIN e sessioni non cambiano)."""
    nuovo_nome = (nuovo_nome or "").strip()
    if not nuovo_nome:
        return {"ok": False, "motivo": "nome_richiesto"}
    with _lock:
        data = _carica()
        op = _trova_op(data, op_id)
        if not op:
            return {"ok": False, "motivo": "operatore_sconosciuto"}
        if any(o.get("id") != op_id
               and (o.get("nome") or "").strip().lower() == nuovo_nome.lower()
               for o in data.get("operatori", [])):
            return {"ok": False, "motivo": "nome_duplicato"}
        op["nome"] = nuovo_nome
        _salva(data)
        return {"ok": True, "operatore": {"id": op_id, "nome": nuovo_nome,
                                          "pin_impostato": bool(op.get("pin_hash"))}}


def elimina_operatore(op_id: str) -> dict:
    """Rimuove un operatore. Non consente di restare con zero operatori.
    Invalida le sessioni aperte dell'operatore eliminato."""
    with _lock:
        data = _carica()
        ops = data.get("operatori", [])
        if not _trova_op(data, op_id):
            return {"ok": False, "motivo": "operatore_sconosciuto"}
        if len(ops) <= 1:
            return {"ok": False, "motivo": "ultimo_operatore"}
        data["operatori"] = [o for o in ops if o.get("id") != op_id]
        _salva(data)
        for t in [t for t, s in _sessions.items() if s["op_id"] == op_id]:
            _sessions.pop(t, None)
        _reset_fail(op_id)
        return {"ok": True}


def imposta_ruolo(op_id: str, ruolo: str) -> dict:
    """Cambia il ruolo di un operatore. Non permette di rimuovere l'ultimo admin
    (altrimenti nessuno potrebbe più gestire gli operatori dal pannello)."""
    if ruolo not in RUOLI_VALIDI:
        return {"ok": False, "motivo": "ruolo_non_valido"}
    with _lock:
        data = _carica()
        op = _trova_op(data, op_id)
        if not op:
            return {"ok": False, "motivo": "operatore_sconosciuto"}
        if op.get("ruolo") == "admin" and ruolo != "admin":
            n_admin = sum(1 for o in data.get("operatori", []) if o.get("ruolo") == "admin")
            if n_admin <= 1:
                return {"ok": False, "motivo": "ultimo_admin"}
        op["ruolo"] = ruolo
        _salva(data)
        # allinea le sessioni attive dell'operatore (il ruolo cambia subito)
        for s in _sessions.values():
            if s["op_id"] == op_id:
                s["ruolo"] = ruolo
        return {"ok": True,
                "operatore": {"id": op_id, "nome": op.get("nome"), "ruolo": ruolo}}


def is_admin(op_id: str) -> bool:
    with _lock:
        op = _trova_op(_carica(), op_id)
        return bool(op and op.get("ruolo") == "admin")


def assicura_admin_bootstrap() -> str | None:
    """Se NESSUN operatore è admin, promuove ad admin il primo con PIN impostato
    (fallback: il primo in lista). Così il primo operatore registrato diventa
    admin in autonomia, senza master key. Ritorna l'id promosso, o None."""
    with _lock:
        data = _carica()
        ops = data.get("operatori", [])
        if any(o.get("ruolo") == "admin" for o in ops):
            return None
        target = next((o for o in ops if o.get("pin_hash")), ops[0] if ops else None)
        if not target:
            return None
        target["ruolo"] = "admin"
        _salva(data)
        for s in _sessions.values():
            if s["op_id"] == target["id"]:
                s["ruolo"] = "admin"
        return target["id"]
