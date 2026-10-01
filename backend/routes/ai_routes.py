"""F20 (26/02/2026) — Endpoints Assistente AI.

- POST /api/ai/chat            — invia messaggio → LLM → tool-use loop → risposta
- GET  /api/ai/status          — stato AI (abilitato, quota rimanente, modalità)
- GET  /api/ai/settings        — settings (Admin)
- PUT  /api/ai/settings        — aggiorna settings (Admin)
- POST /api/ai/execute/{pid}   — esegue una pending operation dopo conferma utente
- POST /api/ai/pending/{pid}/cancel — annulla una pending operation

L'AI usa Groq (o altro provider configurato via env). Chiavi mai al frontend.
"""
from __future__ import annotations

import json
import os
import logging
import base64
import hashlib
from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field
from cryptography.fernet import Fernet, InvalidToken

import auth as auth_mod
import event_logger
from ai_provider import create_ai_provider, AIProviderError
from ai_tools import TOOLS_SCHEMA, dispatch_tool

logger = logging.getLogger(__name__)


DEFAULT_AI_SETTINGS = {
    "enabled": False,
    "mode": "consultation",  # consultation | operational | full_operational
    "confirm_before_modify": True,
    "auto_execute": False,   # solo se mode=full_operational
    "daily_limit": 20,
    "provider": None,        # info-only, mostrato in Admin
    "model": None,
}


class ChatBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    message: str = Field(min_length=1, max_length=4000)
    session_id: Optional[str] = None
    context_section: Optional[str] = None  # inventario|arrivi|spedizioni|movimenti|anomalie|dashboard|retroattivita


class SettingsBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: Optional[bool] = None
    mode: Optional[str] = None
    confirm_before_modify: Optional[bool] = None
    auto_execute: Optional[bool] = None
    daily_limit: Optional[int] = Field(default=None, ge=0, le=10000)


class ProviderConfigBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    provider: Optional[str] = Field(default=None, min_length=1, max_length=40)
    model: Optional[str] = Field(default=None, min_length=1, max_length=120)
    api_key: Optional[str] = Field(default=None, max_length=500)


def _fernet() -> Fernet:
    # Chiave derivata dal JWT_SECRET locale: la API key non viene salvata in chiaro nel DB.
    secret = (os.environ.get("JWT_SECRET") or "elios-tech-local").encode("utf-8")
    key = base64.urlsafe_b64encode(hashlib.sha256(secret).digest())
    return Fernet(key)


def _encrypt_secret(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def _decrypt_secret(value: str) -> str:
    if not value:
        return ""
    try:
        return _fernet().decrypt(value.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, TypeError):
        return ""


async def get_provider_config(db, include_secret: bool = False) -> Dict[str, Any]:
    doc = await db.settings.find_one({"_id": "ai_provider_config"}) or {}
    provider = (doc.get("provider") or os.environ.get("AI_PROVIDER") or "groq").strip().lower()
    model = (doc.get("model") or os.environ.get("AI_MODEL") or "openai/gpt-oss-120b").strip()
    # Groq Free/Developer: il vecchio Llama 3.3 70B è stato dismesso.
    # Migrazione trasparente per configurazioni salvate in versioni precedenti.
    if provider == "groq" and model == "llama-3.3-70b-versatile":
        model = "openai/gpt-oss-120b"
        await db.settings.update_one({"_id": "ai_provider_config"}, {"$set": {"model": model}}, upsert=True)
    api_key = _decrypt_secret(doc.get("api_key_encrypted") or "") or (os.environ.get("AI_API_KEY") or "").strip()
    masked = ""
    if api_key:
        masked = (api_key[:4] + "••••" + api_key[-4:]) if len(api_key) > 10 else "••••••••"
    out = {
        "provider": provider,
        "model": model,
        "configured": bool(api_key and model),
        "api_key_configured": bool(api_key),
        "api_key_masked": masked,
    }
    if include_secret:
        out["api_key"] = api_key
    return out


async def get_ai_settings(db) -> Dict[str, Any]:
    doc = await db.settings.find_one({"_id": "ai_settings"}) or {}
    out = dict(DEFAULT_AI_SETTINGS)
    for k, v in doc.items():
        if k in out and v is not None:
            out[k] = v
    cfg = await get_provider_config(db)
    out["provider"] = cfg["provider"]
    out["model"] = cfg["model"]
    out["provider_configured"] = cfg["configured"]
    return out


async def _count_today_requests(db, user_id: str) -> int:
    since = datetime.now(timezone.utc) - timedelta(hours=24)
    return await db.ai_requests.count_documents({"user_id": user_id, "created_at": {"$gte": since}})


SYSTEM_PROMPT_BASE = """Sei l'Assistente AI del Gestionale Elios Tech. Rispondi SEMPRE in italiano.
Usa i tool a disposizione per rispondere: non inventare mai dati (prodotti, quantità, seriali, spedizioni).
Sii conciso, diretto e professionale. Rispondi in modo naturale, come una normale chat tra colleghi.
NON usare Markdown visibile: niente asterischi, cancelleti, elenchi con trattini, tabelle o blocchi di codice salvo richiesta esplicita.
Preferisci frasi e paragrafi brevi e puliti. NON usare etichette in maiuscolo come "DATO CERTO", "DATO VERIFICATO" o simili.
REGOLA FONDAMENTALE DI EFFICIENZA: usa prima il tool più specifico per recuperare i dati reali e non chiedere dati che il gestionale può già trovare. Per report installazione usa search_installation_reports; per clienti/sedi/assistenza usa search_crm; per commesse usa search_commesse/get_commessa; per inventario usa i tool prodotto/seriale. Non chiamare tool non pertinenti. Se una ricerca diretta basta, non fare ulteriori passaggi.
Quando fornisci risultati, includi nome prodotto, codice, quantità, seriale, cliente e data se disponibili.
Se un tool non trova risultati, dillo semplicemente e in modo utile (es. "Non ho trovato un prodotto
corrispondente. Prova con il nome completo, il codice o una caratteristica del prodotto.").
NON usare mai l'etichetta "POSSIBILE ANOMALIA" per un semplice mancato match o ricerca senza risultati.

REGOLE OPERAZIONI MODIFICATIVE:
Se l'utente chiede una spedizione o un arrivo usa prepare_shipment o prepare_arrival.
Se chiede di creare un prodotto/articolo usa prepare_create_product. Se chiede di modificarlo o disattivarlo usa search_products e poi prepare_update_product / prepare_archive_product. Non dire mai che la chat non può creare prodotti: se l'utente ha i permessi, prepara l'operazione. I prodotti dei due magazzini sono separati: se l'utente non dice il magazzino, chiedi se deve essere creato in Magazzino Elios Tech o Magazzino Verona. Se non specifica l'unità, chiedi se è a pezzi o a metri. Per accessori e materiali comuni (es. stand, meter, cavi, protezioni) usa normalmente gestione a quantità; per dispositivi gestiti singolarmente con seriale usa a_seriale e unità pz.
Se chiede di creare o modificare clienti, contatti, sedi, sopralluoghi, preventivi, ordini cliente, installazioni o assistenze usa search_crm quando serve trovare gli ID e poi prepare_create_record / prepare_update_record.
Per azioni operative sulle commesse usa search_commesse/get_commessa e poi prepare_commessa_action; per arrivi e spedizioni usa i relativi tool preparatori. Ogni azione deve rispettare i permessi dell'utente connesso.
I tool prepare_* non eseguono direttamente: preparano un'anteprima che l'utente conferma nella UI. Non dichiarare mai che l'operazione è stata eseguita prima della conferma.
Non mostrare preview_id o dettagli tecnici se non sono utili: descrivi semplicemente in linguaggio naturale cosa verrà fatto.

ANOMALIE REALI:
Continua a segnalare le VERE incoerenze quando le rilevi (es. quantità dichiarata ≠ numero di seriali disponibili,
seriali duplicati, dati contraddittori). Fallo con linguaggio naturale — esempio:
"Ho rilevato un'incoerenza: risultano 26 pezzi disponibili ma sono presenti solo 24 seriali."
Le ipotesi e i pattern sospetti vanno presentati come tali, non come fatti certi.
"""

MODE_ADDENDUM = {
    "consultation": "\nMODALITÀ: SOLO CONSULTAZIONE. Non hai accesso a tool operativi (`prepare_*` non disponibili). Rispondi con analisi/report/riepiloghi.",
    "operational": "\nMODALITÀ: OPERATIVA. Puoi preparare operazioni con `prepare_*` ma l'esecuzione richiede conferma esplicita dell'utente.",
    "full_operational": "\nMODALITÀ: OPERATIVA COMPLETA. Puoi preparare operazioni. L'esecuzione avviene comunque dopo conferma utente (o automatica se abilitato dall'Admin).",
}


def _tools_for_mode(mode: str) -> List[Dict[str, Any]]:
    if mode == "consultation":
        return [t for t in TOOLS_SCHEMA if not t["function"]["name"].startswith("prepare_")]
    return TOOLS_SCHEMA



def _compact_history(messages: List[Dict[str, Any]], max_messages: int = 10, max_chars_each: int = 1200) -> List[Dict[str, Any]]:
    """Mantiene memoria conversazionale utile senza rispedire intere conversazioni al provider."""
    out: List[Dict[str, Any]] = []
    for msg in (messages or [])[-max_messages:]:
        role = msg.get("role")
        if role not in ("user", "assistant"):
            continue
        content = str(msg.get("content") or "")
        if len(content) > max_chars_each:
            content = content[:max_chars_each] + "…"
        out.append({"role": role, "content": content})
    return out


def _selected_tool_names(message: str, mode: str, context_section: Optional[str] = None) -> set[str]:
    """Router leggero: invia al modello solo i tool coerenti con la richiesta corrente.
    Riduce drasticamente i token dello schema e rende l'assistente più rapido/stabile.
    """
    q = (message or "").lower()
    ctx = (context_section or "").lower()
    txt = f"{q} {ctx}"
    names: set[str] = set()

    # Report/installazioni e calendario tecnico
    if any(k in txt for k in ("report", "installaz", "tecnico", "intervento", "calendario")):
        names.update({"search_installation_reports", "search_crm"})
        if mode != "consultation":
            names.update({"prepare_create_record", "prepare_update_record"})

    # CRM cliente/sedi/assistenza/backend
    if any(k in txt for k in ("client", "sede", "contatt", "smart", "backend", "password", " psw", "id wb", "assistenza", "preventiv", "ordine cliente", "sopralluog")):
        names.add("search_crm")
        if mode != "consultation":
            names.update({"prepare_create_record", "prepare_update_record"})

    # Commesse
    if any(k in txt for k in ("commessa", "preparazione", "materiale mancante", "pronta", "prelev")):
        names.update({"search_commesse", "get_commessa"})
        if mode != "consultation":
            names.add("prepare_commessa_action")

    # Magazzino/prodotti/seriali
    if any(k in txt for k in ("magazz", "prodot", "articol", "serial", "giacenz", "scorta", "disponib", "wallbox", "daze", "pulsar", "meter", "cavo")):
        names.update({"search_products", "get_product", "get_product_serials", "check_serial_availability", "get_dashboard_summary"})
        if mode != "consultation" and any(k in txt for k in ("crea", "aggiungi", "modifica", "disattiva", "archivia")):
            names.update({"prepare_create_product", "prepare_update_product", "prepare_archive_product"})

    # Movimenti logistici
    if any(k in txt for k in ("spedizion", "spedito", "arriv", "ricevut", "moviment")):
        names.update({"search_shipments", "search_arrivals", "search_movements"})
        if mode != "consultation":
            names.update({"prepare_shipment", "prepare_arrival"})

    # Anomalie/log
    if any(k in txt for k in ("anomali", "errore", "log", "registro", "duplicat")):
        names.update({"get_anomalies", "search_logs"})

    # Domande generiche: piccolo set trasversale, non l'intero catalogo tool.
    if not names:
        names.update({"search_crm", "search_commesse", "search_products", "search_installation_reports"})

    return names


def _tools_for_request(message: str, mode: str, context_section: Optional[str] = None) -> List[Dict[str, Any]]:
    allowed = _selected_tool_names(message, mode, context_section)
    base = _tools_for_mode(mode)
    selected = [t for t in base if t.get("function", {}).get("name") in allowed]
    # Difesa: il modello deve avere almeno un tool di ricerca, ma mai tutti per default.
    return selected or [t for t in base if t.get("function", {}).get("name") in {"search_crm", "search_products"}]


def _compact_tool_result(value: Any, limit: int = 3600) -> str:
    """Serializzazione compatta dei risultati tool per evitare 413/TPM eccessivi."""
    try:
        raw = json.dumps(value, ensure_ascii=False, default=str, separators=(",", ":"))
    except Exception:
        raw = str(value)
    if len(raw) <= limit:
        return raw
    return raw[:limit] + '…"}'

def build_router(db, deps: auth_mod.AuthDependencies) -> APIRouter:
    router = APIRouter(prefix="/ai", tags=["ai"], dependencies=[Depends(deps.get_current_user)])

    @router.get("/status")
    async def status(current=Depends(deps.get_current_user)):
        settings = await get_ai_settings(db)
        used = await _count_today_requests(db, str(current.get("_id")))
        remaining = max(0, int(settings.get("daily_limit") or 0) - used)
        return {
            "enabled": settings["enabled"], "mode": settings["mode"],
            "confirm_before_modify": settings["confirm_before_modify"],
            "auto_execute": settings["auto_execute"],
            "daily_limit": settings["daily_limit"],
            "requests_today": used, "requests_remaining": remaining,
            "provider": settings["provider"], "model": settings["model"],
        }

    @router.get("/settings", dependencies=[Depends(deps.require_admin)])
    async def get_settings():
        return await get_ai_settings(db)

    @router.put("/settings", dependencies=[Depends(deps.require_admin)])
    async def put_settings(body: SettingsBody, current=Depends(deps.require_admin)):
        updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
        # Validazioni
        if "mode" in updates and updates["mode"] not in ("consultation", "operational", "full_operational"):
            raise HTTPException(400, "mode non valido")
        # auto_execute solo se full_operational
        current_doc = await get_ai_settings(db)
        merged = {**current_doc, **updates}
        if merged.get("auto_execute") and merged.get("mode") != "full_operational":
            raise HTTPException(400, "auto_execute richiede mode=full_operational")
        await db.settings.update_one({"_id": "ai_settings"}, {"$set": updates}, upsert=True)
        # Audit
        await event_logger.log_event(
            db, category="AI", event_type="AI_SETTINGS_CHANGED",
            action="ai.settings.update", level="INFO", status="SUCCESS",
            user=current.get("username"), user_role=current.get("role"),
            endpoint="PUT /api/ai/settings",
            message=f"Impostazioni AI aggiornate: {list(updates.keys())}",
            details={"updates": updates},
        )
        return await get_ai_settings(db)

    @router.get("/provider-config", dependencies=[Depends(deps.require_admin)])
    async def provider_config_get():
        return await get_provider_config(db)

    @router.put("/provider-config", dependencies=[Depends(deps.require_admin)])
    async def provider_config_put(body: ProviderConfigBody, current=Depends(deps.require_admin)):
        updates: Dict[str, Any] = {}
        if body.provider is not None:
            provider = body.provider.strip().lower()
            if provider not in ("groq",):
                raise HTTPException(400, "Provider non supportato")
            updates["provider"] = provider
        if body.model is not None and body.model.strip():
            updates["model"] = body.model.strip()
        if body.api_key is not None and body.api_key.strip():
            updates["api_key_encrypted"] = _encrypt_secret(body.api_key.strip())
        if updates:
            await db.settings.update_one({"_id": "ai_provider_config"}, {"$set": updates}, upsert=True)
        await event_logger.log_event(
            db, category="AI", event_type="AI_PROVIDER_CONFIG_CHANGED",
            action="ai.provider_config.update", level="INFO", status="SUCCESS",
            user=current.get("username"), endpoint="PUT /api/ai/provider-config",
            message="Configurazione provider AI aggiornata",
            details={"provider": updates.get("provider"), "model": updates.get("model"), "api_key_updated": "api_key_encrypted" in updates},
        )
        return await get_provider_config(db)

    @router.post("/provider-test", dependencies=[Depends(deps.require_admin)])
    async def provider_test():
        cfg = await get_provider_config(db, include_secret=True)
        if not cfg.get("configured"):
            raise HTTPException(400, "Configura prima provider, modello e API key")
        try:
            provider = create_ai_provider(cfg["provider"], cfg["api_key"], cfg["model"])
            await provider.chat([{ "role": "user", "content": "Rispondi solo con OK" }], tools=None, temperature=0, max_tokens=8)
        except AIProviderError as e:
            raise HTTPException(502, str(e))
        return {"ok": True, "message": "Connessione AI funzionante", "provider": cfg["provider"], "model": cfg["model"]}

    @router.get("/sessions/latest")
    async def latest_session(current=Depends(deps.get_current_user)):
        """Ricarica l'ultima conversazione dell'utente quando torna nella pagina AI."""
        user_id = str(current.get("_id"))
        doc = await db.ai_sessions.find_one({"user_id": user_id}, sort=[("updated_at", -1)])
        pending = await db.ai_pending_ops.find_one(
            {"user_id": user_id, "status": "pending"}, sort=[("created_at", -1)]
        )
        if not doc:
            return {"session_id": None, "messages": [], "pending_operation": None}
        safe_messages = []
        for msg in (doc.get("messages") or [])[-60:]:
            role = msg.get("role")
            if role not in ("user", "assistant"):
                continue
            safe_messages.append({"role": "ai" if role == "assistant" else "user", "content": msg.get("content") or ""})
        pending_out = None
        if pending:
            pending_out = {"preview_id": pending.get("preview_id"), "summary": pending.get("summary") or {}}
        return {"session_id": doc.get("session_id"), "messages": safe_messages, "pending_operation": pending_out}

    @router.post("/sessions/new")
    async def new_session(current=Depends(deps.get_current_user)):
        """Avvia esplicitamente una nuova conversazione senza cancellare lo storico precedente."""
        return {"session_id": None, "messages": []}

    @router.post("/chat")
    async def chat(body: ChatBody, request: Request, current=Depends(deps.get_current_user)):
        settings = await get_ai_settings(db)
        if not settings.get("enabled"):
            raise HTTPException(403, "Assistente AI disabilitato dall'Admin")
        # Quota giornaliera
        user_id = str(current.get("_id"))
        used = await _count_today_requests(db, user_id)
        if used >= int(settings.get("daily_limit") or 0):
            await event_logger.log_event(
                db, category="AI", event_type="AI_LIMIT_REACHED",
                action="ai.chat", level="WARNING", status="FAILURE",
                user=current.get("username"), endpoint="POST /api/ai/chat",
                message=f"Limite giornaliero AI raggiunto ({used}/{settings.get('daily_limit')})",
            )
            raise HTTPException(429, f"Limite giornaliero AI raggiunto ({used}/{settings.get('daily_limit')}). Riprova domani.")

        # Persisti la richiesta (per quota + log)
        req_at = datetime.now(timezone.utc)
        op_id = event_logger.new_operation_id("AI")
        await db.ai_requests.insert_one({
            "user_id": user_id, "username": current.get("username"),
            "created_at": req_at, "operation_id": op_id,
            "context_section": body.context_section,
        })

        # Costruisci provider e messaggi
        try:
            provider_cfg = await get_provider_config(db, include_secret=True)
            provider = create_ai_provider(provider_cfg["provider"], provider_cfg.get("api_key") or "", provider_cfg["model"])
        except AIProviderError as e:
            await event_logger.log_event(
                db, category="AI", event_type="AI_PROVIDER_ERROR",
                action="ai.chat.provider_init", level="ERROR", status="FAILURE",
                user=current.get("username"), operation_id=op_id,
                message=f"Provider AI non configurato: {e.kind} — {str(e)}",
            )
            raise HTTPException(503, f"Provider AI non configurato: {str(e)}")

        # Recupera sessione (thread) se session_id fornito
        session_id = body.session_id or f"session-{user_id}-{req_at.timestamp()}"
        prior: List[Dict[str, Any]] = []
        if body.session_id:
            doc = await db.ai_sessions.find_one({"session_id": body.session_id, "user_id": user_id})
            if doc:
                prior = _compact_history(doc.get("messages", []), max_messages=10, max_chars_each=1200)  # memoria compatta

        mode = settings.get("mode") or "consultation"
        system = SYSTEM_PROMPT_BASE + MODE_ADDENDUM.get(mode, "")
        if body.context_section:
            system += f"\n\nCONTESTO CORRENTE UTENTE: {body.context_section}. Se la domanda è ambigua, interpreta rispetto a questa sezione."

        messages = [{"role": "system", "content": system}] + prior + [{"role": "user", "content": body.message}]

        # Salva subito il messaggio dell'utente: anche se il provider va in rate limit
        # o cade la rete, tornando nella pagina la conversazione non perde ciò che è stato scritto.
        await db.ai_sessions.update_one(
            {"session_id": session_id, "user_id": user_id},
            {"$set": {"session_id": session_id, "user_id": user_id, "updated_at": datetime.now(timezone.utc),
                      "messages": (prior + [{"role": "user", "content": body.message}])[-60:]}},
            upsert=True,
        )

        # Loop tool-use — max 4 giri: i tool sono già preselezionati dal router
        # Ottieni inventory service condiviso
        from inventory_router import get_svc as _get_svc
        svc = await _get_svc(db)

        tools = _tools_for_request(body.message, mode, body.context_section)
        tool_calls_used: List[Dict[str, Any]] = []
        final_reply = ""
        pending_operation: Optional[Dict[str, Any]] = None

        try:
            for turn in range(4):
                result = await provider.chat(messages, tools=tools, temperature=0.2, max_tokens=1024)
                reply = result.get("content") or ""
                calls = result.get("tool_calls") or []
                if not calls:
                    final_reply = reply
                    break
                # Aggiungi il turno assistant al thread
                messages.append({"role": "assistant", "content": reply or None, "tool_calls": calls})
                # Esegui ogni tool call
                for tc in calls:
                    fn = tc.get("function") or {}
                    tname = fn.get("name") or ""
                    try:
                        targs = json.loads(fn.get("arguments") or "{}")
                    except json.JSONDecodeError:
                        targs = {}
                    if mode == "consultation" and tname.startswith("prepare_"):
                        tres = {"error": "not_allowed_in_consultation_mode"}
                    else:
                        tres = await dispatch_tool(db, svc, tname, targs, current)
                    tool_calls_used.append({"tool": tname, "args": targs, "result_summary": {k: v for k, v in tres.items() if k in ("error", "preview_id", "preview_ready", "total_found", "total_returned")}})
                    # Se ha preparato un'operazione, salvala per il popup di conferma
                    if isinstance(tres, dict) and tres.get("preview_ready"):
                        pending_operation = {"preview_id": tres.get("preview_id"), "summary": tres.get("summary")}
                    # Log del tool call
                    await event_logger.log_event(
                        db, category="AI", event_type="AI_TOOL_CALL",
                        action=f"ai.tool.{tname}", level="INFO",
                        status="FAILURE" if (isinstance(tres, dict) and tres.get("error")) else "SUCCESS",
                        user=current.get("username"), operation_id=op_id,
                        message=f"Tool {tname} chiamato",
                        details={"args_keys": list(targs.keys()), "result_type": type(tres).__name__},
                    )
                    messages.append({
                        "role": "tool", "tool_call_id": tc.get("id"),
                        "name": tname,
                        "content": _compact_tool_result(tres, 3600),
                    })
            else:
                final_reply = final_reply or "Ho eseguito troppi passaggi senza completare. Riprova con una domanda più specifica."
        except AIProviderError as e:
            await event_logger.log_event(
                db, category="AI", event_type="AI_PROVIDER_ERROR",
                action="ai.chat", level="ERROR", status="FAILURE",
                user=current.get("username"), operation_id=op_id,
                message=f"Provider {e.kind}: {str(e)}",
            )
            if e.kind in ("rate_limit", "timeout", "offline"):
                raise HTTPException(503, str(e))
            raise HTTPException(502, f"Errore provider AI: {str(e)}")

        # Aggiorna sessione
        new_msgs = prior + [{"role": "user", "content": body.message}, {"role": "assistant", "content": final_reply}]
        await db.ai_sessions.update_one(
            {"session_id": session_id, "user_id": user_id},
            {"$set": {"session_id": session_id, "user_id": user_id, "updated_at": datetime.now(timezone.utc),
                      "messages": new_msgs[-60:]}},
            upsert=True,
        )

        # Log risposta AI
        await event_logger.log_event(
            db, category="AI", event_type="AI_RESPONSE",
            action="ai.chat", level="INFO", status="SUCCESS",
            user=current.get("username"), operation_id=op_id,
            endpoint="POST /api/ai/chat",
            message=f"AI risposta ({len(tool_calls_used)} tool calls){' — pending op' if pending_operation else ''}",
            details={"context_section": body.context_section, "tool_calls_count": len(tool_calls_used),
                     "message_preview": body.message[:200], "provider": provider.name, "model": provider.model,
                     "pending_operation_id": (pending_operation or {}).get("preview_id")},
        )

        return {
            "reply": final_reply, "session_id": session_id,
            "operation_id": op_id, "tool_calls": tool_calls_used,
            "pending_operation": pending_operation,
            "requests_remaining": max(0, int(settings.get("daily_limit") or 0) - used - 1),
        }

    @router.post("/execute/{preview_id}")
    async def execute_pending(preview_id: str, request: Request, current=Depends(deps.get_current_user)):
        """Esegue una pending operation. Chiama gli endpoint HTTP esistenti (submit_checklist,
        submit_arrivo) con l'auth JWT del user → SSOT/logging/inventory update automatici."""
        settings = await get_ai_settings(db)
        if not settings.get("enabled"):
            raise HTTPException(403, "Assistente AI disabilitato")
        if settings.get("mode") == "consultation":
            raise HTTPException(403, "Modalità solo consultazione: nessuna operazione consentita")
        doc = await db.ai_pending_ops.find_one({"preview_id": preview_id, "user_id": str(current.get("_id"))})
        if not doc:
            raise HTTPException(404, "Preview non trovata (o scaduta)")
        if doc.get("status") != "pending":
            raise HTTPException(409, f"Preview già in stato {doc.get('status')}")
        op = doc.get("operation") or {}
        auth_header = request.headers.get("Authorization") or ""
        # Base URL loopback: preserviamo Notion/DB via HTTP interno all'app
        base = os.environ.get("INTERNAL_API_BASE") or "http://localhost:8001"
        result: Dict[str, Any] = {}
        try:
            async with httpx.AsyncClient(timeout=60.0, headers={"Authorization": auth_header}) as client:
                if op.get("operation_type") == "shipment":
                    payload = {
                        "operator": current.get("username"), "structure": op.get("cliente"),
                        "taken_by": op.get("taken_by") or current.get("username"),
                        "items": [{
                            "page_id": op.get("product_page_id"), "name": op.get("product_name"),
                            "serialized": (op.get("tipo_gestione") == "a_seriale"),
                            "serials": op.get("serials") or [],
                            "quantity": op.get("quantity"), "unit": "pz",
                        }],
                    }
                    r = await client.post(f"{base}/api/checklist/send", json=payload)
                elif op.get("operation_type") == "arrival":
                    payload = {
                        "operator": current.get("username"),
                        "warehouse_id": op.get("warehouse_id") or "elios-tech",
                        "fornitore": op.get("fornitore") or "AI",
                        "items": [{
                            "page_id": op.get("product_page_id"), "name": op.get("product_name"),
                            "serialized": (op.get("tipo_gestione") == "a_seriale"),
                            "serials": op.get("serials") or [],
                            "quantity": op.get("quantity"), "unit": op.get("unit") or "pz",
                        }],
                    }
                    r = await client.post(f"{base}/api/arrivi/send", json=payload)
                elif op.get("operation_type") == "product_create":
                    r = await client.post(f"{base}/api/products", json=op.get("data") or {})
                elif op.get("operation_type") == "product_update":
                    pid = str(op.get("product_id") or "")
                    wh = str((op.get("data") or {}).get("warehouse_id") or "elios-tech")
                    existing = await client.get(f"{base}/api/products", params={"warehouse_id": wh})
                    if existing.status_code >= 400:
                        r = existing
                    else:
                        items = (existing.json() or {}).get("items") or []
                        current_product = next((x for x in items if str(x.get("id")) == pid), None)
                        if not current_product:
                            raise HTTPException(404, "Prodotto non trovato")
                        merged = dict(current_product)
                        merged.update(op.get("data") or {})
                        allowed = {"name","code","category","brand","unit","tipo_gestione","low_stock_threshold","location","supplier","notes","active","warehouse_id"}
                        payload = {k: merged.get(k) for k in allowed if k in merged}
                        payload.setdefault("name", current_product.get("name") or "")
                        payload.setdefault("tipo_gestione", current_product.get("tipo_gestione") or "a_quantita")
                        r = await client.put(f"{base}/api/products/{pid}", json=payload)
                elif op.get("operation_type") == "product_archive":
                    pid = str(op.get("product_id") or "")
                    r = await client.delete(f"{base}/api/products/{pid}")
                elif op.get("operation_type") == "crm_create":
                    resource = str(op.get("resource") or "")
                    r = await client.post(f"{base}/api/crm/{resource}", json=op.get("data") or {})
                elif op.get("operation_type") == "crm_update":
                    resource = str(op.get("resource") or "")
                    record_id = str(op.get("record_id") or "")
                    r = await client.put(f"{base}/api/crm/{resource}/{record_id}", json=op.get("data") or {})
                elif op.get("operation_type") == "commessa_action":
                    cid = str(op.get("commessa_id") or "")
                    action = str(op.get("action") or "")
                    endpoint_action = {"draft-cancel": "draft/cancel"}.get(action, action)
                    r = await client.post(f"{base}/api/commesse/{cid}/{endpoint_action}", json=op.get("data") or {})
                else:
                    raise HTTPException(400, f"Tipo operazione non supportato: {op.get('operation_type')}")
                if r.status_code >= 400:
                    await db.ai_pending_ops.update_one({"preview_id": preview_id},
                        {"$set": {"status": "failed", "error": r.text[:500], "executed_at": datetime.now(timezone.utc)}})
                    await event_logger.log_event(
                        db, category="AI", event_type="AI_OPERATION_FAILED",
                        action="ai.execute", level="ERROR", status="FAILURE",
                        user=current.get("username"),
                        message=f"Esecuzione AI fallita ({op.get('operation_type')}): {r.status_code}",
                        details={"preview_id": preview_id, "status_code": r.status_code, "error": r.text[:400]},
                    )
                    raise HTTPException(r.status_code, f"Operazione fallita: {r.text[:200]}")
                result = r.json()
        except HTTPException:
            raise
        except Exception as e:
            await db.ai_pending_ops.update_one({"preview_id": preview_id},
                {"$set": {"status": "failed", "error": str(e)[:500]}})
            raise HTTPException(500, f"Errore esecuzione AI: {e}")

        # Verifica coerenza — leggi l'esito dal backend
        await db.ai_pending_ops.update_one(
            {"preview_id": preview_id},
            {"$set": {"status": "executed", "executed_at": datetime.now(timezone.utc), "backend_result": result}},
        )
        await event_logger.log_event(
            db, category="AI", event_type="AI_OPERATION_EXECUTED",
            action="ai.execute", level="INFO", status="SUCCESS",
            user=current.get("username"),
            product=op.get("product_name"), product_code=op.get("product_code"),
            customer=op.get("cliente"),
            quantity_change=op.get("quantity"),
            message=f"AI ha eseguito {op.get('operation_type')} — {op.get('description') or op.get('product_name') or op.get('resource') or ''}",
            details={"preview_id": preview_id, "backend": {k: v for k, v in (result or {}).items() if k in ("status", "message", "checklist_id", "arrivo_id")}},
        )
        return {"ok": True, "backend_result": result}

    @router.post("/pending/{preview_id}/cancel")
    async def cancel_pending(preview_id: str, current=Depends(deps.get_current_user)):
        doc = await db.ai_pending_ops.find_one({"preview_id": preview_id, "user_id": str(current.get("_id"))})
        if not doc:
            raise HTTPException(404, "Preview non trovata")
        await db.ai_pending_ops.update_one({"preview_id": preview_id},
            {"$set": {"status": "cancelled", "cancelled_at": datetime.now(timezone.utc)}})
        await event_logger.log_event(
            db, category="AI", event_type="AI_OPERATION_CANCELLED",
            action="ai.cancel", level="INFO", status="SUCCESS",
            user=current.get("username"),
            message=f"AI operation annullata dall'utente",
            details={"preview_id": preview_id},
        )
        return {"ok": True}

    return router
