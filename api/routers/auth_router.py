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


def _verifica_master(request: Request) -> None:
    """Gate admin: richiede la MASTER KEY (DMG_API_KEY) via header X-API-Key.
    Non usa la sessione operatore (finché non c'è RBAC, l'admin è chi possiede
    la master key). Solleva 503 se la chiave non è configurata, 401 se errata."""
    master = (os.environ.get("DMG_API_KEY") or "").strip()
    if not master:
        raise HTTPException(503,
            "Funzione admin non disponibile: DMG_API_KEY non configurata. "
            "Usa lo script scripts/reset_pin.py sul server.")
    fornita = request.headers.get("x-api-key") or ""
    if not hmac.compare_digest(fornita, master):
        log.warning(f"[AUDIT admin-fail] ip={_client_ip(request)} master-key errata")
        raise HTTPException(401, "Master key non valida")


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
    # credenziali_non_valide / operatore_sconosciuto → 401 generico (no enum)
    raise HTTPException(401, detail="Operatore o PIN non validi")


@router.get("/me")
async def get_me(request: Request):
    op = _auth.valida_token(_token_da_request(request))
    if not op:
        raise HTTPException(401, "Sessione non valida o scaduta")
    return {"operatore": {"id": op["op_id"], "nome": op["nome"]}, "scade": op["scade"]}


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
    _verifica_master(request)

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
    _verifica_master(request)
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
    _verifica_master(request)
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
    _verifica_master(request)
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
