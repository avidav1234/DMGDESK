"""
api/routers/assistente.py
==========================
Endpoint chat per l'assistente AI integrato in DMGDesk.
Usa Claude API con tool use — ogni messaggio porta il contesto
live del sistema (macchina, utensili, commesse, OEE).

POST /api/assistente/chat
GET  /api/assistente/contesto   ← contesto live per il frontend
"""

import os
import json
import logging
from datetime import datetime
from typing import Optional

import httpx
from fastapi import APIRouter, HTTPException, Body
from pydantic import BaseModel

log = logging.getLogger("assistente")
router = APIRouter()

ANTHROPIC_API_URL = "https://api.anthropic.com/v1/messages"
MODEL = "claude-haiku-4-5-20251001"   # Haiku: veloce, economico per chat interna
MAX_TOKENS = 1024
BACKEND_URL = "http://127.0.0.1:8000"


# ── Modelli ───────────────────────────────────────────────────────────────────

class Messaggio(BaseModel):
    role: str   # "user" | "assistant"
    content: str

class ChatRequest(BaseModel):
    messaggio: str
    history: list[Messaggio] = []
    pagina_corrente: Optional[str] = None   # es. "macchina", "report", "progetti"
    contesto_pagina: Optional[dict] = None  # dati extra dalla pagina corrente


# ── Tool definitions ──────────────────────────────────────────────────────────

TOOLS = [
    {
        "name": "get_stato_macchina",
        "description": "Restituisce lo stato live della macchina CNC: programma attivo, utensile, progStatus, pallet.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_report_giornaliero",
        "description": "Restituisce il report del giorno: ore lavorate, OEE, fermi anomali, sessioni.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data": {"type": "string", "description": "Data in formato YYYY-MM-DD. Se omessa usa oggi."}
            },
            "required": []
        }
    },
    {
        "name": "get_alert_utensili",
        "description": "Restituisce utensili critici: vita bassa, da ispezionare, rischio alto.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_commesse_attive",
        "description": "Restituisce le commesse/progetti attivi con stato, pallet assegnato, scadenza.",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "get_storico_fermi",
        "description": "Restituisce lo storico fermi macchina degli ultimi N giorni con classificazione anomali/pianificati.",
        "input_schema": {
            "type": "object",
            "properties": {
                "giorni": {"type": "integer", "description": "Numero di giorni. Default 7."}
            },
            "required": []
        }
    },
    {
        "name": "get_vita_utensile",
        "description": "Restituisce la vita residua e storico sessioni di un utensile specifico.",
        "input_schema": {
            "type": "object",
            "properties": {
                "alias": {"type": "string", "description": "Alias dell'utensile, es. FS16R2L80F100E4"}
            },
            "required": ["alias"]
        }
    },
    {
        "name": "get_simili_step",
        "description": "Trova commesse geometricamente simili a una commessa tramite lo STEP analyzer.",
        "input_schema": {
            "type": "object",
            "properties": {
                "commessa": {"type": "string", "description": "Nome commessa, es. COMM-4297"},
                "soglia": {"type": "number", "description": "Soglia similarità 0-100. Default 60."}
            },
            "required": ["commessa"]
        }
    },
    {
        "name": "set_pallet_stato",
        "description": "Cambia lo stato di un pallet (vuoto, grezzo, finito, guasto).",
        "input_schema": {
            "type": "object",
            "properties": {
                "pallet": {"type": "string", "description": "Es. P1, P2, P3..."},
                "stato":  {"type": "string", "enum": ["vuoto", "grezzo", "finito", "guasto"]}
            },
            "required": ["pallet", "stato"]
        }
    },
    {
        "name": "invia_telegram",
        "description": "Invia un messaggio Telegram all'operatore. Usare solo se l'utente lo chiede esplicitamente.",
        "input_schema": {
            "type": "object",
            "properties": {
                "testo": {"type": "string", "description": "Testo del messaggio da inviare."}
            },
            "required": ["testo"]
        }
    },
]


# ── Esecutori tool ─────────────────────────────────────────────────────────────

async def esegui_tool(nome: str, params: dict) -> str:
    """Esegue un tool chiamando le API interne del backend."""
    async with httpx.AsyncClient(timeout=15) as client:
        try:
            if nome == "get_stato_macchina":
                r = await client.get(f"{BACKEND_URL}/api/macchina-live/stato")
                return json.dumps(r.json(), ensure_ascii=False)

            elif nome == "get_report_giornaliero":
                data = params.get("data", "")
                url = f"{BACKEND_URL}/api/report/giornaliero"
                if data:
                    url += f"?data={data}"
                r = await client.get(url)
                return json.dumps(r.json(), ensure_ascii=False)

            elif nome == "get_alert_utensili":
                r = await client.get(f"{BACKEND_URL}/api/report/alert-utensili")
                return json.dumps(r.json(), ensure_ascii=False)

            elif nome == "get_commesse_attive":
                r = await client.get(f"{BACKEND_URL}/api/progetti/")
                progetti = r.json()
                # Filtra solo attivi per non sovraccaricare il contesto
                attivi = [p for p in (progetti if isinstance(progetti, list) else [])
                          if p.get("status") not in ("consegnato", "annullato")][:10]
                return json.dumps(attivi, ensure_ascii=False)

            elif nome == "get_storico_fermi":
                giorni = params.get("giorni", 7)
                r = await client.get(f"{BACKEND_URL}/api/report/storico?giorni={giorni}")
                return json.dumps(r.json(), ensure_ascii=False)

            elif nome == "get_vita_utensile":
                alias = params["alias"]
                r = await client.get(f"{BACKEND_URL}/api/tools/vita/{alias}")
                return json.dumps(r.json(), ensure_ascii=False)

            elif nome == "get_simili_step":
                commessa = params["commessa"]
                soglia = params.get("soglia", 60)
                r = await client.get(
                    f"{BACKEND_URL}/api/step/simili/{commessa}",
                    params={"soglia": soglia}
                )
                return json.dumps(r.json(), ensure_ascii=False)

            elif nome == "set_pallet_stato":
                r = await client.patch(
                    f"{BACKEND_URL}/api/pallet/{params['pallet']}/stato",
                    json={"stato": params["stato"]}
                )
                return json.dumps(r.json(), ensure_ascii=False)

            elif nome == "invia_telegram":
                r = await client.post(
                    f"{BACKEND_URL}/api/telegram/invia",
                    json={"testo": params["testo"]}
                )
                return json.dumps(r.json(), ensure_ascii=False)

            else:
                return json.dumps({"errore": f"Tool '{nome}' non implementato"})

        except Exception as e:
            log.warning(f"Tool {nome} errore: {e}")
            return json.dumps({"errore": str(e)})


# ── System prompt dinamico ────────────────────────────────────────────────────

def build_system_prompt(pagina: str, contesto: dict) -> str:
    ora = datetime.now().strftime("%H:%M del %d/%m/%Y")
    pagina_desc = {
        "home":          "Dashboard principale con stato macchina e pallet",
        "macchina":      "Gestione utensili in macchina",
        "report":        "Report lavorazioni e OEE",
        "progetti":      "Gestione commesse e lavori",
        "scaffale":      "Utensili a scaffale",
        "step-analyzer": "Analisi geometrica file STEP e similitudini commesse",
        "analytics":     "Analytics commesse e statistiche",
        "alert-utensili":"Alert utensili critici",
        "coda":          "Coda lavorazione e stato pallet",
        "turno":         "Riepilogo turno corrente",
    }.get(pagina or "", "DMGDesk")

    contesto_str = ""
    if contesto:
        try:
            contesto_str = f"\nContesto pagina corrente:\n{json.dumps(contesto, ensure_ascii=False, indent=2)}"
        except Exception:
            pass

    return f"""Sei l'assistente AI integrato in DMGDesk, il sistema di gestione del reparto CNC di Vetimec.
Macchina: DMG DMC 160U con Siemens Sinumerik 840D PowerLine.
Ora attuale: {ora}
Pagina aperta: {pagina_desc}{contesto_str}

Comportamento:
- Rispondi in italiano, in modo conciso e tecnico
- Usa i tool per ottenere dati aggiornati prima di rispondere a domande sui dati
- Per azioni (cambia pallet, invia Telegram) chiedi sempre conferma esplicita all'utente prima di eseguire
- Se non sai qualcosa, dillo chiaramente invece di inventare
- Usa terminologia CNC appropriata (utensile, commessa, pallet, sgrossatura, finitura, ecc.)
- Le risposte devono essere brevi e dirette — l'utente è in officina, non vuole testi lunghi
- Quando mostri dati numerici usa unità di misura (h, min, %, mm, ecc.)"""


# ── Agent loop ─────────────────────────────────────────────────────────────────

async def run_agent(messages: list, system: str, api_key: str) -> str:
    """
    Esegue il loop agente: chiama Claude, esegue tool se necessario,
    ritorna la risposta finale testuale.
    """
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }

    async with httpx.AsyncClient(timeout=60) as client:
        for _step in range(6):  # max 6 iterazioni tool use
            payload = {
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "system": system,
                "tools": TOOLS,
                "messages": messages,
            }

            r = await client.post(ANTHROPIC_API_URL, headers=headers, json=payload)
            if r.status_code != 200:
                log.error(f"Anthropic API error {r.status_code}: {r.text[:200]}")
                raise HTTPException(502, f"Claude API error {r.status_code}")

            resp = r.json()
            stop_reason = resp.get("stop_reason")
            content = resp.get("content", [])

            # Risposta finale — estrai testo
            if stop_reason == "end_turn":
                testo = " ".join(
                    b["text"] for b in content if b.get("type") == "text"
                ).strip()
                return testo or "✓"

            # Claude vuole usare tool
            if stop_reason == "tool_use":
                # Aggiungi risposta assistant alla history
                messages.append({"role": "assistant", "content": content})

                # Esegui tutti i tool richiesti
                tool_results = []
                for block in content:
                    if block.get("type") == "tool_use":
                        log.info(f"Tool: {block['name']} {block.get('input', {})}")
                        risultato = await esegui_tool(block["name"], block.get("input", {}))
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block["id"],
                            "content": risultato,
                        })

                messages.append({"role": "user", "content": tool_results})
                continue

            # Stop inatteso
            break

    return "Non sono riuscito a completare la risposta."


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.post("/api/assistente/chat")
async def chat(req: ChatRequest):
    """
    Endpoint principale chat. Riceve messaggio + history,
    ritorna la risposta dell'assistente.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise HTTPException(503, "ANTHROPIC_API_KEY non configurata — aggiungi al .env")

    # Costruisci history messaggi
    messages = []
    for m in req.history[-12:]:  # ultimi 12 messaggi per non sprecare token
        messages.append({"role": m.role, "content": m.content})

    # Aggiungi messaggio corrente
    messages.append({"role": "user", "content": req.messaggio})

    # System prompt con contesto
    system = build_system_prompt(req.pagina_corrente, req.contesto_pagina)

    try:
        risposta = await run_agent(messages, system, api_key)
        return {
            "ok": True,
            "risposta": risposta,
            "ts": datetime.now().isoformat(timespec="seconds"),
        }
    except HTTPException:
        raise
    except Exception as e:
        log.error(f"Chat error: {e}")
        raise HTTPException(500, str(e))


@router.get("/api/assistente/contesto")
async def get_contesto():
    """
    Snapshot contesto live per il frontend.
    Usato per popolare il pannello chat con dati iniziali.
    """
    async with httpx.AsyncClient(timeout=10) as client:
        ctx = {}
        try:
            r = await client.get(f"{BACKEND_URL}/api/macchina-live/stato")
            ctx["macchina"] = r.json()
        except Exception:
            ctx["macchina"] = None
        try:
            r = await client.get(f"{BACKEND_URL}/api/report/alert-utensili")
            alerts = r.json()
            ctx["n_alert_utensili"] = len(alerts) if isinstance(alerts, list) else 0
        except Exception:
            ctx["n_alert_utensili"] = 0
    return ctx


@router.get("/api/assistente/stato")
async def stato_assistente():
    """Verifica se la chiave API è configurata."""
    api_key = os.environ.get("ANTHROPIC_API_KEY", "")
    return {
        "ok": bool(api_key),
        "configurato": bool(api_key),
        "modello": MODEL,
        "messaggio": "Assistente pronto" if api_key else "Configura ANTHROPIC_API_KEY nel .env",
    }
