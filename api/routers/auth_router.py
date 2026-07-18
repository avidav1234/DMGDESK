"""
api/routers/auth_router.py
==========================
Endpoint di autenticazione operatori con PIN.

Endpoint PUBBLICI (accessibili senza token, anche ad auth attiva — servono
per fare il login stesso):
  GET  /api/auth/status      → { auth_attiva }
  GET  /api/auth/operatori   → lista {id, nome, pin_impostato}
  POST /api/auth/login       → { ok, token, nome, scade, pin_creato } | 401/429

Endpoint AUTENTICATI (richiedono un token valido, gestito dal middleware):
  GET  /api/auth/me          → { operatore, scade }
  POST /api/auth/logout      → invalida il token corrente
  POST /api/auth/cambia-pin  → cambio PIN (richiede PIN attuale)

Endpoint ADMIN (protetto dalla master key DMG_API_KEY, non dalla sessione):
  POST /api/auth/admin/reset-pin  → reset PIN di un operatore dal browser

Il reset "di riserva" da console è `scripts/reset_pin.py`.
"""

import os
import hmac
from fastapi import APIRouter, Body, Request, HTTPException

from api import auth as _auth
from api import ip_allowlist as _ip_allow
from utils.logger import get_logger

log = get_logger("api.auth")
router = APIRouter(prefix="/api/auth", tags=["Autenticazione"])


def _token_da_request(request: Request) -> str | None:
    """Estrae il token da Authorization: Bearer <t> oppure header X-Session-Token."""
    h = request.headers.get("authorization") or ""
    if h.lower().startswith("bearer "):
        return h[7:].strip()
    return request.headers.get("x-session-token") or None


def _client_ip(request: Request) -> str:
    return request.client.host if request.client else "?"


_TRUST_PROXY = (os.environ.get("DMG_TRUST_PROXY", "").strip() == "1")


def _client_ip_reale(request: Request) -> str:
    """IP client come lo vede il middleware: dietro reverse proxy fidato usa il
    primo di X-Forwarded-For (coerente con l'allowlist)."""
    if _TRUST_PROXY:
        xff = request.headers.get("x-forwarded-for", "")
        if xff:
            return xff.split(",")[0].strip()
    return request.client.host if request.client else "?"


def _chiavi_uguali(a: str, b: str) -> bool:
    """Confronto a tempo costante robusto anche con caratteri non-ASCII
    (es. una password autofillata a caso dal browser): compara i byte UTF-8.
    `hmac.compare_digest` su str solleva TypeError coi non-ASCII → qui non deve
    mai far crashare l'endpoint (altrimenti 500 invece di 401)."""
    try:
        return hmac.compare_digest((a or "").encode("utf-8"), (b or "").encode("utf-8"))
    except Exception:
        return False


def _verifica_admin(request: Request):
    """Gate admin: autorizza se (a) sessione operatore con ruolo 'admin', OPPURE
    (b) master key DMG_API_KEY via X-API-Key (break-glass / servizi).
    Ritorna l'op admin (per audit) o None (via master key). Solleva 403 se né l'una
    né l'altra."""
    op = _auth.valida_token(_token_da_request(request))
    if op and op.get("ruolo") == "admin":
        return op
    master = (os.environ.get("DMG_API_KEY") or "").strip()
    if master and _chiavi_uguali(request.headers.get("x-api-key") or "", master):
        return None
    log.warning(f"[AUDIT admin-fail] ip={_client_ip(request)} "
                f"op={op['op_id'] if op else '-'} ruolo={op.get('ruolo') if op else '-'}")
    if op:   # sessione valida ma non admin → vietato
        raise HTTPException(403, "Operazione riservata agli amministratori")
    # nessuna autenticazione → richiede login admin o master key
    raise HTTPException(401, "Richiede login admin o master key")


@router.get("/status")
async def auth_status():
    """Il frontend chiama questo all'avvio: se auth_attiva mostra il login."""
    return {"auth_attiva": _auth.auth_attiva()}


@router.get("/operatori")
async def get_operatori():
    """Lista operatori per la pagina di login. Nessun hash esposto."""
    return {"operatori": _auth.lista_operatori()}


@router.post("/login")
async def post_login(request: Request, body: dict = Body(...)):
    op_id = (body.get("operatore_id") or "").strip()
    pin   = str(body.get("pin") or "")
    if not op_id:
        raise HTTPException(400, "operatore_id richiesto")

    res = _auth.login(op_id, pin)
    if res.get("ok"):
        # Auto-ammissione: se un ADMIN si logga, il suo IP entra nell'allowlist
        # (basta un login admin per autorizzare una nuova postazione).
        if _auth.is_admin(op_id):
            ip_reale = _client_ip_reale(request)
            _ip_allow.aggiungi(ip_reale)
            log.info(f"[AUDIT ip-auto-admit] ip={ip_reale} op={op_id} (login admin)")
        log.info(f"[AUDIT login] ip={_client_ip(request)} op={op_id} "
                 f"pin_creato={res.get('pin_creato', False)}")
        return {
            "ok": True,
            "token": res["token"],
            "nome": res.get("nome"),
            "scade": res.get("scade"),
            "pin_creato": res.get("pin_creato", False),
        }

    motivo = res.get("motivo")
    log.warning(f"[AUDIT login-fail] ip={_client_ip(request)} op={op_id} motivo={motivo}")
    if motivo == "bloccato":
        raise HTTPException(429, detail={
            "motivo": "bloccato",
            "riprova_sec": res.get("riprova_sec", 60),
            "detail": f"Troppi tentativi. Riprova fra {res.get('riprova_sec', 60)}s",
        })
    if motivo == "pin_non_valido":
        raise HTTPException(400, detail=res.get("detail", "PIN non valido"))
    if motivo == "pin_duplicato":
        raise HTTPException(409, detail=res.get("detail", "PIN già usato da un altro operatore"))
    # credenziali_non_valide / operatore_sconosciuto → 401 generico (no enum)
    raise HTTPException(401, detail="Operatore o PIN non validi")


@router.post("/login-pin")
async def post_login_pin(request: Request, body: dict = Body(...)):
    """Login SOLO col PIN (senza selezionare l'operatore): il PIN identifica
    l'operatore. Body: { pin }."""
    pin = str(body.get("pin") or "")
    res = _auth.login_con_pin(pin, _client_ip(request))
    if res.get("ok"):
        # Auto-ammissione IP se chi entra è admin (autorizza la postazione).
        if res.get("ruolo") == "admin":
            ip_reale = _client_ip_reale(request)
            _ip_allow.aggiungi(ip_reale)
            log.info(f"[AUDIT ip-auto-admit] ip={ip_reale} op={res.get('nome')!r} (login-pin admin)")
        log.info(f"[AUDIT login-pin] ip={_client_ip(request)} op={res.get('nome')!r}")
        return {"ok": True, "token": res["token"], "nome": res.get("nome"),
                "ruolo": res.get("ruolo"), "scade": res.get("scade")}
    motivo = res.get("motivo")
    log.warning(f"[AUDIT login-pin-fail] ip={_client_ip(request)} motivo={motivo}")
    if motivo == "bloccato":
        raise HTTPException(429, detail={
            "motivo": "bloccato", "riprova_sec": res.get("riprova_sec", 60),
            "detail": f"Troppi tentativi. Riprova fra {res.get('riprova_sec', 60)}s"})
    raise HTTPException(401, detail="PIN non valido")


@router.get("/me")
async def get_me(request: Request):
    op = _auth.valida_token(_token_da_request(request))
    if not op:
        raise HTTPException(401, "Sessione non valida o scaduta")
    return {"operatore": {"id": op["op_id"], "nome": op["nome"],
                          "ruolo": op.get("ruolo")}, "scade": op["scade"]}


@router.post("/logout")
async def post_logout(request: Request):
    _auth.logout(_token_da_request(request))
    return {"ok": True}


@router.post("/cambia-pin")
async def post_cambia_pin(request: Request, body: dict = Body(...)):
    op = _auth.valida_token(_token_da_request(request))
    if not op:
        raise HTTPException(401, "Sessione non valida o scaduta")
    pin_vecchio = str(body.get("pin_vecchio") or "")
    pin_nuovo   = str(body.get("pin_nuovo") or "")
    res = _auth.cambia_pin(op["op_id"], pin_vecchio, pin_nuovo)
    if res.get("ok"):
        log.info(f"[AUDIT cambia-pin] ip={_client_ip(request)} op={op['op_id']}")
        return {"ok": True}
    if res.get("motivo") == "pin_attuale_errato":
        raise HTTPException(403, "PIN attuale errato")
    if res.get("motivo") == "pin_non_valido":
        raise HTTPException(400, res.get("detail", "PIN nuovo non valido"))
    raise HTTPException(400, res.get("motivo", "Errore cambio PIN"))


@router.post("/admin/reset-pin")
async def post_admin_reset_pin(request: Request, body: dict = Body(...)):
    """Reset del PIN di un operatore, protetto dalla MASTER KEY (DMG_API_KEY),
    non da una sessione operatore. Consente il reset dal browser a chi possiede
    la chiave master, senza andare alla console del server.

    Body: { operatore_id, nuovo_pin? }
      - con `nuovo_pin`: imposta direttamente quel PIN (nessuna finestra aperta)
      - senza `nuovo_pin`: azzera il PIN → l'operatore lo re-imposta al login
    """
    _verifica_admin(request)

    op_id = (body.get("operatore_id") or "").strip()
    if not op_id:
        raise HTTPException(400, "operatore_id richiesto")
    nuovo_pin = body.get("nuovo_pin")

    if nuovo_pin:
        res = _auth.imposta_pin(op_id, str(nuovo_pin))
        modo = "impostato"
    else:
        res = _auth.azzera_pin(op_id)
        modo = "azzerato"

    if not res.get("ok"):
        if res.get("motivo") == "operatore_sconosciuto":
            raise HTTPException(404, f"Operatore {op_id} non trovato")
        raise HTTPException(400, res.get("detail", res.get("motivo", "Errore reset")))

    log.info(f"[AUDIT reset-pin] ip={_client_ip(request)} op={op_id} modo={modo}")
    return {"ok": True, "operatore_id": op_id, "modo": modo}


@router.post("/admin/operatori")
async def post_admin_aggiungi(request: Request, body: dict = Body(...)):
    """Crea un nuovo operatore (senza PIN, lo imposta al primo accesso).
    Protetto dalla master key. Body: { nome }."""
    _verifica_admin(request)
    nome = (body.get("nome") or "").strip()
    res = _auth.aggiungi_operatore(nome)
    if not res.get("ok"):
        if res.get("motivo") == "nome_duplicato":
            raise HTTPException(409, "Esiste già un operatore con questo nome")
        raise HTTPException(400, "Nome operatore richiesto")
    log.info(f"[AUDIT op-aggiungi] ip={_client_ip(request)} "
             f"id={res['operatore']['id']} nome={nome!r}")
    return res


@router.post("/admin/rinomina")
async def post_admin_rinomina(request: Request, body: dict = Body(...)):
    """Rinomina un operatore. Protetto dalla master key.
    Body: { operatore_id, nuovo_nome }."""
    _verifica_admin(request)
    op_id = (body.get("operatore_id") or "").strip()
    nuovo = (body.get("nuovo_nome") or "").strip()
    res = _auth.rinomina_operatore(op_id, nuovo)
    if not res.get("ok"):
        if res.get("motivo") == "operatore_sconosciuto":
            raise HTTPException(404, f"Operatore {op_id} non trovato")
        if res.get("motivo") == "nome_duplicato":
            raise HTTPException(409, "Esiste già un operatore con questo nome")
        raise HTTPException(400, "Nuovo nome richiesto")
    log.info(f"[AUDIT op-rinomina] ip={_client_ip(request)} op={op_id} nome={nuovo!r}")
    return res


@router.post("/admin/elimina")
async def post_admin_elimina(request: Request, body: dict = Body(...)):
    """Elimina un operatore (non l'ultimo rimasto). Protetto dalla master key.
    Body: { operatore_id }."""
    _verifica_admin(request)
    op_id = (body.get("operatore_id") or "").strip()
    if not op_id:
        raise HTTPException(400, "operatore_id richiesto")
    res = _auth.elimina_operatore(op_id)
    if not res.get("ok"):
        if res.get("motivo") == "operatore_sconosciuto":
            raise HTTPException(404, f"Operatore {op_id} non trovato")
        if res.get("motivo") == "ultimo_operatore":
            raise HTTPException(409, "Non puoi eliminare l'ultimo operatore rimasto")
        raise HTTPException(400, "Errore eliminazione")
    log.info(f"[AUDIT op-elimina] ip={_client_ip(request)} op={op_id}")
    return res


@router.post("/admin/ruolo")
async def post_admin_ruolo(request: Request, body: dict = Body(...)):
    """Cambia il ruolo di un operatore (admin/operatore). Protetto da _verifica_admin.
    Body: { operatore_id, ruolo }."""
    _verifica_admin(request)
    op_id = (body.get("operatore_id") or "").strip()
    ruolo = (body.get("ruolo") or "").strip()
    res = _auth.imposta_ruolo(op_id, ruolo)
    if not res.get("ok"):
        if res.get("motivo") == "operatore_sconosciuto":
            raise HTTPException(404, f"Operatore {op_id} non trovato")
        if res.get("motivo") == "ultimo_admin":
            raise HTTPException(409, "Deve restare almeno un admin")
        raise HTTPException(400, "Ruolo non valido (admin | operatore)")
    log.info(f"[AUDIT op-ruolo] ip={_client_ip(request)} op={op_id} ruolo={ruolo}")
    return res


# ── Allowlist IP (accesso web ristretto ai PC noti) ───────────────────────────
# Questi endpoint sono ESENTATI dal filtro IP nel middleware (vedi main.py) così
# un admin non può mai auto-chiudersi fuori: restano raggiungibili da qualsiasi IP,
# ma protetti da _verifica_admin.

@router.get("/admin/ip-allowlist")
async def get_ip_allowlist(request: Request):
    """Stato allowlist + IP del chiamante (per 'aggiungi il mio') + tentativi bloccati."""
    _verifica_admin(request)
    s = _ip_allow.stato()
    return {"enabled": s["enabled"], "ips": s["ips"],
            "tuo_ip": _client_ip_reale(request),
            "tentativi": _ip_allow.tentativi()}


@router.post("/admin/ip-allowlist/tentativi/pulisci")
async def post_ip_pulisci_tentativi(request: Request):
    """Svuota il registro dei tentativi bloccati."""
    _verifica_admin(request)
    _ip_allow.pulisci_tentativi()
    log.info(f"[AUDIT ip-allowlist-tentativi-pulisci] ip={_client_ip(request)}")
    return {"ok": True}


@router.post("/admin/ip-allowlist/abilita")
async def post_ip_abilita(request: Request, body: dict = Body(...)):
    """Attiva/disattiva il filtro IP. Body: { enabled: bool }."""
    _verifica_admin(request)
    flag = bool(body.get("enabled"))
    res = _ip_allow.imposta_abilitato(flag)
    log.info(f"[AUDIT ip-allowlist-abilita] ip={_client_ip(request)} enabled={flag}")
    return res


@router.post("/admin/ip-allowlist/aggiungi")
async def post_ip_aggiungi(request: Request, body: dict = Body(...)):
    """Aggiunge un IP o una rete CIDR alla allowlist. Body: { ip }."""
    _verifica_admin(request)
    ip = (body.get("ip") or "").strip()
    res = _ip_allow.aggiungi(ip)
    if not res.get("ok"):
        raise HTTPException(400, "IP o rete CIDR non validi (es. 192.168.1.10 oppure 192.168.1.0/24)")
    log.info(f"[AUDIT ip-allowlist-aggiungi] ip={_client_ip(request)} nuovo={ip!r}")
    return res


@router.post("/admin/ip-allowlist/rimuovi")
async def post_ip_rimuovi(request: Request, body: dict = Body(...)):
    """Rimuove un IP/CIDR dalla allowlist. Body: { ip }."""
    _verifica_admin(request)
    ip = (body.get("ip") or "").strip()
    res = _ip_allow.rimuovi(ip)
    log.info(f"[AUDIT ip-allowlist-rimuovi] ip={_client_ip(request)} rimosso={ip!r}")
    return res
