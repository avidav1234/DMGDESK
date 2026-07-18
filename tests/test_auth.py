"""
Test dell'autenticazione operatori con PIN (api/auth.py).

Copre: primo accesso imposta il PIN, login corretto/errato, lockout
progressivo anti-forza-bruta, sessioni/scadenza, cambio PIN, reset (azzera +
imposta), validazione lunghezza PIN 4-10, isolamento hash (mai in chiaro),
storage fuori dalla share.

Esecuzione:  pytest -p no:asyncio tests/test_auth.py
(sincroni; le route async sono provate con asyncio.run dove serve)
"""

import asyncio
import importlib
import json

import pytest


@pytest.fixture()
def auth(tmp_path, monkeypatch):
    """Modulo api.auth con file account isolato in tmp e stato in memoria pulito."""
    accounts = tmp_path / "auth_accounts.json"
    monkeypatch.setenv("DMG_AUTH_ACCOUNTS_FILE", str(accounts))
    monkeypatch.setenv("DMG_AUTH_ENABLED", "1")
    import api.auth as auth_mod
    importlib.reload(auth_mod)
    # Reset stato in memoria (i moduli sono singleton fra i test)
    auth_mod._sessions.clear()
    auth_mod._fails.clear()
    return auth_mod


# ── Storage / hashing ─────────────────────────────────────────────────────────

def test_file_default_creato_con_due_operatori_senza_pin(auth, tmp_path):
    ops = auth.lista_operatori()
    assert [o["id"] for o in ops] == ["op1", "op2"]
    assert all(o["pin_impostato"] is False for o in ops)
    # File creato in tmp (NON sulla share)
    assert (tmp_path / "auth_accounts.json").exists()


def test_pin_mai_in_chiaro_su_disco(auth, tmp_path):
    auth.imposta_pin("op1", "12345")
    raw = (tmp_path / "auth_accounts.json").read_text(encoding="utf-8")
    assert "12345" not in raw
    data = json.loads(raw)
    op1 = next(o for o in data["operatori"] if o["id"] == "op1")
    assert op1.get("pin_hash") and op1.get("pin_salt")
    assert op1["pin_hash"] != "12345"


# ── Validazione PIN ───────────────────────────────────────────────────────────

@pytest.mark.parametrize("pin,valido", [
    ("1234", True), ("1234567890", True), ("12345", True),
    ("123", False),          # < 4
    ("12345678901", False),  # > 10
    ("12a4", False),         # non numerico
    ("", False),
])
def test_validazione_lunghezza_pin(auth, pin, valido):
    assert auth._pin_valido(pin) is valido


def test_imposta_pin_rifiuta_pin_corto(auth):
    res = auth.imposta_pin("op1", "12")
    assert res["ok"] is False and res["motivo"] == "pin_non_valido"


# ── Primo accesso imposta il PIN ──────────────────────────────────────────────

def test_primo_accesso_imposta_pin_e_apre_sessione(auth):
    res = auth.login("op1", "5678")
    assert res["ok"] is True
    assert res["pin_creato"] is True
    assert res["token"]
    # Ora il PIN è impostato
    assert auth.lista_operatori()[0]["pin_impostato"] is True
    # Login successivo con lo stesso PIN NON è più "creazione"
    res2 = auth.login("op1", "5678")
    assert res2["ok"] is True and res2["pin_creato"] is False


def test_primo_accesso_con_pin_invalido_non_crea(auth):
    res = auth.login("op1", "12")  # troppo corto
    assert res["ok"] is False and res["motivo"] == "pin_non_valido"
    assert auth.lista_operatori()[0]["pin_impostato"] is False


# ── Login e sessioni ──────────────────────────────────────────────────────────

def test_login_pin_errato_non_apre_sessione(auth):
    auth.imposta_pin("op1", "1111")
    res = auth.login("op1", "9999")
    assert res["ok"] is False
    assert "token" not in res


def test_token_valido_poi_logout(auth):
    auth.imposta_pin("op1", "1111")
    res = auth.login("op1", "1111")
    tok = res["token"]
    assert auth.valida_token(tok)["op_id"] == "op1"
    assert auth.logout(tok) is True
    assert auth.valida_token(tok) is None


def test_token_scaduto_non_valido(auth, monkeypatch):
    from datetime import timedelta
    auth.imposta_pin("op1", "1111")
    tok = auth.login("op1", "1111")["token"]
    # Forza la scadenza nel passato
    auth._sessions[tok]["scade"] = auth._now() - timedelta(seconds=1)
    assert auth.valida_token(tok) is None


def test_token_inesistente(auth):
    assert auth.valida_token("non-esiste") is None
    assert auth.valida_token(None) is None


# ── Lockout anti-forza-bruta ──────────────────────────────────────────────────

def test_lockout_dopo_soglia_tentativi(auth):
    auth.imposta_pin("op1", "1111")
    # SOGLIA-1 tentativi errati: ancora sbloccato
    for _ in range(auth._LOCKOUT_SOGLIA - 1):
        r = auth.login("op1", "0000")
        assert r["motivo"] == "credenziali_non_valide"
    # Tentativo che raggiunge la soglia → bloccato
    r = auth.login("op1", "0000")
    assert r["motivo"] == "bloccato" and r["riprova_sec"] > 0
    # Anche con il PIN GIUSTO resta bloccato finché il timer non scade
    r = auth.login("op1", "1111")
    assert r["motivo"] == "bloccato"


def test_login_corretto_azzera_i_tentativi(auth):
    auth.imposta_pin("op1", "1111")
    for _ in range(auth._LOCKOUT_SOGLIA - 1):
        auth.login("op1", "0000")
    # Login corretto prima della soglia
    assert auth.login("op1", "1111")["ok"] is True
    assert "op1" not in auth._fails


def test_operatore_sconosciuto_non_apre_e_non_perde_isolamento(auth):
    r = auth.login("ghost", "1111")
    assert r["ok"] is False
    assert r["motivo"] == "credenziali_non_valide"  # generico, no enumeration


# ── Cambio PIN ────────────────────────────────────────────────────────────────

def test_cambia_pin_con_vecchio_corretto(auth):
    auth.imposta_pin("op1", "1111")
    assert auth.cambia_pin("op1", "1111", "2222")["ok"] is True
    assert auth.login("op1", "2222")["ok"] is True
    assert auth.login("op1", "1111")["ok"] is False


def test_cambia_pin_con_vecchio_errato_fallisce(auth):
    auth.imposta_pin("op1", "1111")
    r = auth.cambia_pin("op1", "9999", "2222")
    assert r["ok"] is False and r["motivo"] == "pin_attuale_errato"


# ── Reset ─────────────────────────────────────────────────────────────────────

def test_azzera_pin_richiede_reimpostazione_al_login(auth):
    auth.imposta_pin("op1", "1111")
    tok = auth.login("op1", "1111")["token"]
    assert auth.azzera_pin("op1")["ok"] is True
    # Le sessioni aperte dell'operatore sono invalidate
    assert auth.valida_token(tok) is None
    assert auth.lista_operatori()[0]["pin_impostato"] is False
    # Il prossimo login re-imposta il PIN
    r = auth.login("op1", "7777")
    assert r["ok"] is True and r["pin_creato"] is True


def test_imposta_pin_reset_diretto(auth):
    auth.imposta_pin("op1", "1111")
    assert auth.imposta_pin("op1", "8888")["ok"] is True
    assert auth.login("op1", "8888")["ok"] is True


# ── Endpoint admin reset (master key) ─────────────────────────────────────────

def test_admin_reset_pin_richiede_master_key(auth, monkeypatch):
    import api.routers.auth_router as ar
    importlib.reload(ar)
    monkeypatch.setenv("DMG_API_KEY", "MASTER-SECRET")

    class FakeReq:
        def __init__(self, headers):
            self.headers = headers
            self.client = type("C", (), {"host": "10.0.0.5"})()

    # Master key errata → 401
    from fastapi import HTTPException
    with pytest.raises(HTTPException) as ei:
        asyncio.run(ar.post_admin_reset_pin(
            FakeReq({"x-api-key": "sbagliata"}),
            {"operatore_id": "op1", "nuovo_pin": "4321"}))
    assert ei.value.status_code == 401

    # Master key giusta → imposta il PIN
    res = asyncio.run(ar.post_admin_reset_pin(
        FakeReq({"x-api-key": "MASTER-SECRET"}),
        {"operatore_id": "op1", "nuovo_pin": "4321"}))
    assert res["ok"] is True and res["modo"] == "impostato"
    assert auth.login("op1", "4321")["ok"] is True


def test_auth_attiva_riflette_env(auth, monkeypatch):
    monkeypatch.setenv("DMG_AUTH_ENABLED", "1")
    assert auth.auth_attiva() is True
    monkeypatch.setenv("DMG_AUTH_ENABLED", "0")
    assert auth.auth_attiva() is False


# ── Ruoli operatore (Fase 1) ──────────────────────────────────────────────────

def test_operatore_nasce_operatore_e_bootstrap_promuove_primo(auth):
    assert all(o["ruolo"] == "operatore" for o in auth.lista_operatori())
    assert auth.assicura_admin_bootstrap() == "op1"     # nessun admin → promuove il primo
    assert auth.is_admin("op1") and not auth.is_admin("op2")
    assert auth.assicura_admin_bootstrap() is None       # idempotente


def test_bootstrap_preferisce_operatore_con_pin(auth):
    auth.imposta_pin("op2", "12345")                     # op2 ha il PIN, op1 no
    assert auth.assicura_admin_bootstrap() == "op2"
    assert auth.is_admin("op2")


def test_token_porta_il_ruolo(auth):
    auth.assicura_admin_bootstrap()                      # op1 admin
    auth.imposta_pin("op1", "4917")
    sess = auth.valida_token(auth.login("op1", "4917")["token"])
    assert sess["ruolo"] == "admin"


def test_imposta_ruolo_e_guardia_ultimo_admin(auth):
    auth.assicura_admin_bootstrap()                      # op1 admin
    assert auth.imposta_ruolo("op1", "operatore")["motivo"] == "ultimo_admin"
    assert auth.imposta_ruolo("op2", "admin")["ok"]      # ora ci sono 2 admin
    assert auth.imposta_ruolo("op1", "operatore")["ok"]  # op1 declassabile
    assert auth.imposta_ruolo("op2", "root")["motivo"] == "ruolo_non_valido"


def test_aggiungi_operatore_nasce_operatore(auth):
    r = auth.aggiungi_operatore("Mario")
    assert r["ok"] and r["operatore"]["ruolo"] == "operatore"


# ── Login solo-PIN + unicità PIN ──────────────────────────────────────────────

def test_login_con_pin_identifica_operatore(auth):
    auth.imposta_pin("op1", "4917")
    auth.imposta_pin("op2", "6285")
    assert auth.login_con_pin("4917", ip="1.1.1.1")["nome"] == "Operatore 1"
    assert auth.login_con_pin("6285", ip="1.1.1.1")["nome"] == "Operatore 2"
    assert auth.login_con_pin("0000", ip="1.1.1.1")["ok"] is False


def test_pin_devono_essere_unici(auth):
    assert auth.imposta_pin("op1", "4917")["ok"] is True
    assert auth.imposta_pin("op2", "4917")["motivo"] == "pin_duplicato"


def test_lockout_login_pin_per_ip(auth):
    auth.imposta_pin("op1", "4917")
    for _ in range(5):
        auth.login_con_pin("0000", ip="9.9.9.9")
    assert auth.login_con_pin("0000", ip="9.9.9.9")["motivo"] == "bloccato"
    # un IP diverso non è bloccato
    assert auth.login_con_pin("4917", ip="8.8.8.8")["ok"] is True


# ── Fase 1 hardening ──────────────────────────────────────────────────────────

def test_pin_min_configurabile_via_env(monkeypatch, tmp_path):
    """DMG_PIN_MIN alza il minimo senza toccare il codice (default 4 invariato)."""
    monkeypatch.setenv("DMG_AUTH_ACCOUNTS_FILE", str(tmp_path / "a.json"))
    monkeypatch.setenv("DMG_PIN_MIN", "6")
    import api.auth as m
    importlib.reload(m)
    try:
        assert m.PIN_MIN_LEN == 6
        assert m._pin_valido("12345") is False    # 5 cifre < 6
        assert m._pin_valido("123456") is True
    finally:
        monkeypatch.delenv("DMG_PIN_MIN", raising=False)
        importlib.reload(m)                        # ripristina default per gli altri test


def test_chiavi_uguali_robusto_non_ascii():
    """La master key autofillata a caso (non-ASCII) non deve far crashare (era 500)."""
    import api.routers.auth_router as ar
    assert ar._chiavi_uguali("abc", "abc") is True
    assert ar._chiavi_uguali("abc", "abd") is False
    assert ar._chiavi_uguali("PÀSSWORD-àé", "x") is False   # non solleva
    assert ar._chiavi_uguali("x", "PÀSSWORD-àé") is False


def test_relay_vnc_deny_by_default(monkeypatch):
    """Senza auth configurata il relay VNC resta CHIUSO (era fail-open)."""
    monkeypatch.delenv("DMG_API_KEY", raising=False)
    monkeypatch.delenv("DMG_AUTH_ENABLED", raising=False)
    monkeypatch.delenv("DMG_ALLOW_INSECURE", raising=False)
    import api.routers.schermo_live as sl
    importlib.reload(sl)
    try:
        assert sl._autorizzato("", "") is False          # deny-by-default
        monkeypatch.setenv("DMG_ALLOW_INSECURE", "1")
        importlib.reload(sl)
        assert sl._autorizzato("", "") is True            # opt-in dev esplicito
    finally:
        monkeypatch.delenv("DMG_ALLOW_INSECURE", raising=False)
        importlib.reload(sl)


# ── Allowlist IP (accesso ristretto ai PC noti) ───────────────────────────────

def test_ip_allowlist_logica(monkeypatch, tmp_path):
    monkeypatch.setenv("DMG_IP_ALLOWLIST_FILE", str(tmp_path / "ipal.json"))
    import api.ip_allowlist as m
    importlib.reload(m)
    assert m.is_consentito("8.8.8.8") is True             # disabilitato → tutti
    m.imposta_abilitato(True)
    assert m.is_consentito("8.8.8.8") is True             # lista vuota → safety
    m.aggiungi("192.168.1.10")
    assert m.is_consentito("192.168.1.10") is True
    assert m.is_consentito("127.0.0.1") is True           # loopback sempre ok
    assert m.is_consentito("8.8.8.8") is False            # non in lista → bloccato
    m.aggiungi("10.0.0.0/24")
    assert m.is_consentito("10.0.0.9") is True            # dentro CIDR
    assert m.is_consentito("10.0.1.9") is False
    assert m.aggiungi("non-un-ip")["ok"] is False
    m.registra_tentativo("8.8.8.8", "/api/progetti")
    m.registra_tentativo("8.8.8.8", "/api/pallet")
    assert m.tentativi()[0]["ip"] == "8.8.8.8" and m.tentativi()[0]["count"] == 2
    m.rimuovi("192.168.1.10")
    assert m.is_consentito("192.168.1.10") is False


def test_login_admin_auto_ammette_ip(auth, monkeypatch, tmp_path):
    """Un login ADMIN aggiunge automaticamente il proprio IP all'allowlist."""
    monkeypatch.setenv("DMG_IP_ALLOWLIST_FILE", str(tmp_path / "ipal.json"))
    import api.ip_allowlist as ipa
    importlib.reload(ipa)
    import api.routers.auth_router as ar
    importlib.reload(ar)

    auth.assicura_admin_bootstrap()          # op1 → admin
    auth.imposta_pin("op1", "4917")
    ipa.imposta_abilitato(True)
    ipa.aggiungi("127.0.0.1")                 # solo loopback all'inizio

    class FakeReq:
        def __init__(self, ip):
            self.headers = {}
            self.client = type("C", (), {"host": ip})()

    # Prima del login l'IP esterno è bloccato
    assert ipa.is_consentito("203.0.113.7") is False
    res = asyncio.run(ar.post_login_pin(FakeReq("203.0.113.7"), {"pin": "4917"}))
    assert res["ok"] and res["ruolo"] == "admin"
    # Dopo il login admin, l'IP è stato auto-ammesso
    assert ipa.is_consentito("203.0.113.7") is True
