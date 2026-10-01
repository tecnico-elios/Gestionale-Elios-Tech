"""F20 (26/02/2026) — Tool AI: schema JSON + dispatcher che chiama le funzioni REALI dell'app.

Regole:
- L'AI NON accede mai al DB direttamente. Chiama solo questi tool.
- I tool riutilizzano i servizi già presenti (notion_service, inventory_router, db.audit_logs, db.app_events).
- Tool operativi (execute_*) NON esistono qui: le operazioni modificative passano SEMPRE
  attraverso `ai_routes.execute_pending_operation` che invoca gli endpoint HTTP interni
  esistenti (submit_checklist, submit_arrivo, retro/*) con l'auth del user chiamante.
"""
from __future__ import annotations

import re
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger(__name__)


# ─── Normalizzazione query/prodotto (F21 — matching intelligente) ────────────
def _normalize_text(s: str) -> str:
    """Normalizza stringa per matching: lowercase, unifica unità di misura e potenze,
    normalizza decimali, collassa spazi. NON altera i dati originali di Notion."""
    if not s:
        return ""
    s = str(s).lower()
    # Decimali: 7,4 → 7.4
    s = s.replace(",", ".")
    # Unità metriche: "5 metri" | "5 mt" | "5 mts" | "5 m" | "5m" → "5m"
    s = re.sub(r"(\d+(?:\.\d+)?)\s*(?:metri|metres|meters|mts|mt|m)\b", r"\1m", s)
    # Potenze: "22 kw" | "22kW" | "22 kilowatt" | "22kilowatts" → "22kw"
    s = re.sub(r"(\d+(?:\.\d+)?)\s*(?:kilowatts|kilowatt|kws|kw)\b", r"\1kw", s)
    # Rimuovi punteggiatura tranne "." nei decimali (già gestita sopra)
    s = re.sub(r"[^\w\s.]", " ", s)
    # Collassa spazi
    s = re.sub(r"\s+", " ", s).strip()
    return s


_STOPWORDS = {"quante", "quanti", "quanto", "quanta", "abbiamo", "ho", "hai", "ci", "sono",
              "il", "la", "lo", "i", "gli", "le", "un", "una", "uno", "di", "del", "della",
              "dei", "delle", "in", "con", "per", "che", "sono", "ne", "cerca", "trova",
              "mostra", "dimmi", "voglio", "mi", "servono", "disponibili", "disponibile"}


def _tokens(s: str) -> List[str]:
    """Tokenizza dopo la normalizzazione e rimuove stopword italiane."""
    return [t for t in _normalize_text(s).split() if t and t not in _STOPWORDS]


def _is_tech_feature(t: str) -> bool:
    """True se il token è una caratteristica tecnica numerica: 22kw, 5m, 7.4kw."""
    return bool(re.match(r"^\d+(?:\.\d+)?(?:kw|m)$", t))


def _is_bare_number(t: str) -> bool:
    """True se è solo un numero (senza unità): 22, 7.4."""
    return bool(re.match(r"^\d+(?:\.\d+)?$", t))


def _same_number_prefix(bare: str, tech: str) -> bool:
    """True se `bare` (es. "22") è il prefisso numerico di `tech` (es. "22kw"), evitando 22 vs 220."""
    if not tech.startswith(bare):
        return False
    rest = tech[len(bare):]
    return not rest or not rest[0].isdigit()


def _token_score(qt: str, product_tokens: List[str]) -> float:
    """Score 0..1 di un singolo token query rispetto ai token del prodotto."""
    if qt in product_tokens:
        return 1.0
    # Numero puro nella query → matcha caratteristica tecnica del prodotto con stesso numero
    if _is_bare_number(qt):
        for pt in product_tokens:
            if _is_tech_feature(pt) and _same_number_prefix(qt, pt):
                return 0.9
    # Substring reciproca (parole troncate come "pulsar" vs "pulsar" già coperte)
    for pt in product_tokens:
        if len(qt) >= 3 and (qt in pt or (len(pt) >= 3 and pt in qt)):
            return 0.5
    return 0.0


def _product_haystack_tokens(p: Dict[str, Any]) -> List[str]:
    """Combina nome + codice + categoria, normalizza e tokenizza."""
    parts = [p.get("name") or "", p.get("code") or "", p.get("category") or ""]
    return _tokens(" ".join(parts))


def _match_score(query: str, product: Dict[str, Any]) -> float:
    """Calcola score 0..1 di quanto il prodotto matcha la query.
    - Priorità: codice esatto → tutti i token → caratteristiche tecniche numeriche
    - Penalità: caratteristica tecnica richiesta ma diversa nel prodotto → penalità forte.
    """
    q_tokens = _tokens(query)
    if not q_tokens:
        return 0.0
    p_tokens = _product_haystack_tokens(product)
    if not p_tokens:
        return 0.0

    # Match esatto sul codice (case-insensitive)
    code_norm = _normalize_text(product.get("code") or "")
    query_norm = _normalize_text(query)
    if code_norm and query_norm == code_norm:
        return 1.0

    # Somma pesata degli score per token
    total = 0.0
    for qt in q_tokens:
        total += _token_score(qt, p_tokens)
    score = total / len(q_tokens)

    # Penalità: se la query richiede caratteristiche tecniche (5m, 22kw) e il prodotto
    # ha caratteristiche differenti, penalizza pesantemente per evitare falsi positivi.
    q_tech = [t for t in q_tokens if _is_tech_feature(t)]
    p_tech = {t for t in p_tokens if _is_tech_feature(t)}
    if q_tech:
        matched_tech = sum(1 for t in q_tech if t in p_tech)
        # Se non TUTTE le tech feature richieste sono presenti nel prodotto → penalità
        if matched_tech < len(q_tech):
            score *= matched_tech / len(q_tech)

    # Penalità aggiuntiva: bare number (es. "22", "7.4") che NON compaiono come prefisso di
    # nessuna caratteristica tecnica del prodotto → penalità forte (evita "pro 22" che
    # matcha erroneamente prodotti da 7.4kw solo perché "pro" combacia).
    q_bare = [t for t in q_tokens if _is_bare_number(t)]
    if q_bare and p_tech:
        for bn in q_bare:
            if not any(_same_number_prefix(bn, pt) for pt in p_tech):
                score *= 0.4

    return score


logger = logging.getLogger(__name__)


# ─── Schema OpenAI-compatible ────────────────────────────────────────────────
TOOLS_SCHEMA: List[Dict[str, Any]] = [
    {"type": "function", "function": {
        "name": "search_products",
        "description": "Cerca prodotti nell'inventario con matching intelligente (tollera abbreviazioni, unità di misura sinonime tipo 5m/5mt/5 metri, potenze 22kw/22 kW, ordine parole diverso). Ritorna lista ordinata per confidenza (match_score) con name, code, quantity, tipo_gestione. Esempio query: 'pro 22 5 mt' → trova 'Pulsar Pro 22kw 5M'. Se ambiguo, ritorna più risultati.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Testo di ricerca. Può contenere abbreviazioni: '5m', '5 mt', '5 metri' sono equivalenti; '22kw', '22 kW' sono equivalenti."},
            "low_stock_only": {"type": "boolean", "description": "Solo prodotti sotto soglia scorta"},
            "limit": {"type": "integer", "default": 20},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "get_product",
        "description": "Recupera un singolo prodotto per page_id o nome esatto.",
        "parameters": {"type": "object", "properties": {
            "page_id": {"type": "string"}, "name": {"type": "string"},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "check_serial_availability",
        "description": "Verifica se un seriale è ATTUALMENTE disponibile in inventario (non spedito). Ritorna {sn, available: bool, product: name, used_in_shipment?}.",
        "parameters": {"type": "object", "properties": {
            "serial": {"type": "string"},
        }, "required": ["serial"]}}},
    {"type": "function", "function": {
        "name": "search_shipments",
        "description": "Cerca spedizioni recenti. Filtri opzionali su cliente, prodotto, data.",
        "parameters": {"type": "object", "properties": {
            "cliente": {"type": "string"}, "product": {"type": "string"},
            "date_from": {"type": "string", "description": "YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "YYYY-MM-DD"},
            "limit": {"type": "integer", "default": 20},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "search_arrivals",
        "description": "Cerca arrivi/receipts recenti. Filtri opzionali su prodotto, data.",
        "parameters": {"type": "object", "properties": {
            "product": {"type": "string"},
            "date_from": {"type": "string"}, "date_to": {"type": "string"},
            "limit": {"type": "integer", "default": 20},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "search_movements",
        "description": "Cerca movimenti (arrivi + spedizioni unificati) recenti.",
        "parameters": {"type": "object", "properties": {
            "product": {"type": "string"}, "limit": {"type": "integer", "default": 30},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "get_anomalies",
        "description": "Recupera le anomalie di magazzino rilevate dall'app (seriali duplicati, spediti-ma-disponibili, quantità incoerenti).",
        "parameters": {"type": "object", "properties": {
            "limit": {"type": "integer", "default": 30},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "search_logs",
        "description": "Cerca nel Registro Log applicativo (app_events).",
        "parameters": {"type": "object", "properties": {
            "category": {"type": "string", "enum": ["INVENTARIO", "ARRIVO", "SPEDIZIONE", "CANCELLAZIONE", "ANOMALIA", "AUTH", "NOTION", "RETRO", "AI"]},
            "user": {"type": "string"}, "product": {"type": "string"},
            "serial": {"type": "string"}, "status": {"type": "string"},
            "limit": {"type": "integer", "default": 30},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "get_dashboard_summary",
        "description": "Riepilogo KPI magazzino: totale prodotti, valore inventario, sotto scorta, esauriti, ultime attività.",
        "parameters": {"type": "object", "properties": {}, "required": []}}},
    {"type": "function", "function": {
        "name": "search_commesse",
        "description": (
            "Cerca commesse (ordini di preparazione magazzino) per stato/priorità/cliente. "
            "Stati validi: da_preparare, in_preparazione, parziale, pronta, spedita, annullata. "
            "Sinonimi accettati (li normalizzo io): 'parzialmente preparata'='parziale', "
            "'pronta per spedizione'='pronta', 'da fare/da preparare'='da_preparare'. "
            "Ritorna commesse con avanzamento (prelevato/richiesto), operatore in carico, data prevista. "
            "Rispetta il feature flag: se disabilitato ritorna commesse_disabled e items vuoti (NON inventare)."
        ),
        "parameters": {"type": "object", "properties": {
            "stato": {"type": "string", "description": "Stato o sinonimo (vedi description)"},
            "cliente": {"type": "string"},
            "priorita": {"type": "string", "enum": ["urgente", "alta", "normale", "bassa"]},
            "limit": {"type": "integer", "default": 20},
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "get_commessa",
        "description": (
            "Recupera dettagli COMPLETI di una commessa: cliente, stato, priorità, operatore in carico, "
            "righe con quantità richiesta/prelevata, seriali già prelevati, e sommario 'materiale mancante' "
            "(cosa non è ancora stato preso). Usa il number della commessa (es. '125'). "
            "Utile per rispondere a: 'cosa manca alla commessa X', 'chi ha preso in carico X', "
            "'quali seriali sono stati prelevati per X', 'abbiamo tutto per la commessa X'."
        ),
        "parameters": {"type": "object", "properties": {
            "number": {"type": "string"},
        }, "required": ["number"]}}},
    {"type": "function", "function": {
        "name": "get_product_serials",
        "description": "Recupera l'elenco COMPLETO dei seriali di un prodotto A Seriale. Riconosce query in linguaggio naturale con stesso matching di search_products (es. 'Pro 22 5M' = 'Pulsar Pro 22kw 5M'). Se la query è ambigua e matcha più prodotti, ritorna i seriali raggruppati per prodotto. Usa `include_shipped=true` per includere anche i seriali già spediti.",
        "parameters": {"type": "object", "properties": {
            "product_name_or_code": {"type": "string", "description": "Nome/codice/descrizione del prodotto (matching intelligente)."},
            "include_shipped": {"type": "boolean", "default": False, "description": "Se true, include anche i seriali già spediti con riferimento a data e cliente."},
        }, "required": ["product_name_or_code"]}}},
    {"type": "function", "function": {
        "name": "search_installation_reports",
        "description": "Cerca i report di installazione REALI già salvati/generati. Filtra per tecnico (es. Riccardo), cliente, sede, data o testo libero. Ritorna solo risultati sintetici con installazione_id, cliente, sede, tecnico, data, stato report e document_id. Usalo SEMPRE per richieste tipo 'recuperami i report installazioni', senza caricare tutto il CRM.",
        "parameters": {"type": "object", "properties": {
            "query": {"type": "string", "description": "Testo libero da cercare tra tecnico, cliente, sede, note e dati report"},
            "tecnico": {"type": "string"},
            "cliente": {"type": "string"},
            "date_from": {"type": "string", "description": "YYYY-MM-DD"},
            "date_to": {"type": "string", "description": "YYYY-MM-DD"},
            "limit": {"type": "integer", "default": 20}
        }, "required": []}}},
    {"type": "function", "function": {
        "name": "prepare_create_product",
        "description": "PREPARA la creazione di un nuovo prodotto nel catalogo. Usalo quando l'utente chiede di creare un articolo che non esiste. Per accessori/materiali comuni, se non specificato diversamente, usa tipo_gestione=a_quantita. Per dispositivi identificati singolarmente con seriale usa a_seriale. L'operazione reale avviene solo dopo conferma e rispetta i permessi inventario dell'utente.",
        "parameters": {"type": "object", "properties": {
            "name": {"type": "string"},
            "code": {"type": "string"},
            "category": {"type": "string"},
            "brand": {"type": "string"},
            "warehouse_id": {"type": "string", "enum": ["elios-tech", "verona"], "description": "Magazzino in cui creare il prodotto"},
            "unit": {"type": "string", "enum": ["pz", "m"], "description": "Unità: pz per pezzi oppure m per metri"},
            "tipo_gestione": {"type": "string", "enum": ["a_seriale", "a_quantita"], "default": "a_quantita"},
            "low_stock_threshold": {"type": "number", "default": 0},
            "location": {"type": "string"},
            "supplier": {"type": "string"},
            "notes": {"type": "string"}
        }, "required": ["name"]}}},
    {"type": "function", "function": {
        "name": "prepare_update_product",
        "description": "PREPARA la modifica di un prodotto esistente. Usa search_products prima per identificare il prodotto. Passa solo i campi da modificare; il backend conserva gli altri valori esistenti. L'operazione reale avviene solo dopo conferma e rispetta i permessi inventario.",
        "parameters": {"type": "object", "properties": {
            "product_id": {"type": "string"},
            "data": {"type": "object", "additionalProperties": True}
        }, "required": ["product_id", "data"]}}},
    {"type": "function", "function": {
        "name": "prepare_archive_product",
        "description": "PREPARA la disattivazione di un prodotto. Il backend la consentirà solo se non ha giacenza residua, e solo se l'utente ha il permesso necessario.",
        "parameters": {"type": "object", "properties": {
            "product_id": {"type": "string"},
            "product_name": {"type": "string"}
        }, "required": ["product_id"]}}},

    {"type": "function", "function": {
        "name": "prepare_shipment",
        "description": "PREPARA una spedizione (SENZA eseguirla). Ritorna preview con validazione. La spedizione parte solo dopo conferma esplicita utente via execute_pending_operation.",
        "parameters": {"type": "object", "properties": {
            "product_name_or_code": {"type": "string"},
            "quantity": {"type": "number"},
            "serials": {"type": "array", "items": {"type": "string"}, "description": "Solo per prodotti A Seriale"},
            "cliente": {"type": "string"},
            "taken_by": {"type": "string", "description": "Persona che ha ritirato la merce"},
        }, "required": ["product_name_or_code", "cliente"]}}},
    {"type": "function", "function": {
        "name": "prepare_arrival",
        "description": "PREPARA un arrivo (SENZA eseguirlo). Ritorna preview con validazione.",
        "parameters": {"type": "object", "properties": {
            "product_name_or_code": {"type": "string"},
            "quantity": {"type": "number"},
            "serials": {"type": "array", "items": {"type": "string"}},
            "fornitore": {"type": "string"},
            "warehouse_id": {"type": "string", "enum": ["elios-tech", "verona"]},
        }, "required": ["product_name_or_code", "warehouse_id"]}}},
    {"type": "function", "function": {
        "name": "search_crm",
        "description": "Cerca dati del gestionale in clienti, contatti, sedi, sopralluoghi, preventivi, ordini cliente, installazioni o assistenza. Usa questo tool prima di creare collegamenti per trovare gli ID corretti.",
        "parameters": {"type": "object", "properties": {
            "resource": {"type": "string", "enum": ["clienti","contatti","sedi","sopralluoghi","preventivi","ordini-clienti","installazioni","assistenza"]},
            "query": {"type": "string"},
            "limit": {"type": "integer", "default": 20}
        }, "required": ["resource"]}}},
    {"type": "function", "function": {
        "name": "prepare_create_record",
        "description": "PREPARA la creazione di un record gestionale. Può creare cliente, contatto, sede, sopralluogo, preventivo, ordine cliente, installazione o assistenza. I dati devono usare i nomi campo reali del gestionale. Non esegue finché l'utente non conferma.",
        "parameters": {"type": "object", "properties": {
            "resource": {"type": "string", "enum": ["clienti","contatti","sedi","sopralluoghi","preventivi","ordini-clienti","installazioni","assistenza"]},
            "data": {"type": "object", "additionalProperties": True}
        }, "required": ["resource","data"]}}},
    {"type": "function", "function": {
        "name": "prepare_update_record",
        "description": "PREPARA la modifica di un record gestionale esistente. Richiede resource, id e soli campi da modificare. Non esegue finché l'utente non conferma.",
        "parameters": {"type": "object", "properties": {
            "resource": {"type": "string", "enum": ["clienti","contatti","sedi","sopralluoghi","preventivi","ordini-clienti","installazioni","assistenza"]},
            "id": {"type": "string"},
            "data": {"type": "object", "additionalProperties": True}
        }, "required": ["resource","id","data"]}}},
    {"type": "function", "function": {
        "name": "prepare_commessa_action",
        "description": "PREPARA un'azione operativa su una commessa. Usa search_commesse/get_commessa prima. Può prendere in carico, prelevare quantità o seriali, completare, riaprire preparazione, creare o annullare bozza spedizione. L'azione reale avviene solo dopo conferma utente.",
        "parameters": {"type": "object", "properties": {
            "commessa_id": {"type": "string"},
            "action": {"type": "string", "enum": ["take","pick","complete","reopen-preparation","draft","draft-cancel"]},
            "data": {"type": "object", "additionalProperties": True}
        }, "required": ["commessa_id","action"]}}},
]


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _sanitize(v: Any, maxlen: int = 800) -> Any:
    if isinstance(v, str) and len(v) > maxlen:
        return v[:maxlen] + "…"
    return v


def _match_product(items: List[Dict[str, Any]], q: str) -> Optional[Dict[str, Any]]:
    ql = (q or "").strip().lower()
    if not ql:
        return None
    # exact code
    exact = next((i for i in items if (i.get("code") or "").lower() == ql), None)
    if exact: return exact
    # exact name
    exact = next((i for i in items if (i.get("name") or "").strip().lower() == ql), None)
    if exact: return exact
    # partial match
    return next((i for i in items if ql in (i.get("name") or "").lower() or ql in (i.get("code") or "").lower()), None)


# ─── Dispatcher ───────────────────────────────────────────────────────────────
async def dispatch_tool(db, svc, tool_name: str, args: Dict[str, Any], current_user: Dict[str, Any]) -> Dict[str, Any]:
    """Esegue un tool e ritorna il risultato JSON-serializable.
    `svc` = inventory_service (Notion/Local). `current_user` per audit."""
    try:
        if tool_name == "search_products":
            data = await svc.list_inventory()
            items = data.get("items") if isinstance(data, dict) else data
            items = items or []
            q = (args.get("query") or "").strip()
            low = bool(args.get("low_stock_only"))
            limit = int(args.get("limit") or 20)

            # F21 (26/02/2026) — Matching intelligente: normalizzazione + token + tech features
            candidates: List[Tuple[float, Dict[str, Any]]] = []
            for it in items:
                qty = it.get("quantity") or 0
                thresh = it.get("low_stock_threshold") or 0
                if low and qty > (thresh or 0):
                    continue
                if q:
                    score = _match_score(q, it)
                    if score < 0.5:  # threshold minima per evitare falsi positivi
                        continue
                    candidates.append((score, it))
                else:
                    candidates.append((0.0, it))

            # Ordina per score decrescente, poi per nome
            candidates.sort(key=lambda x: (-x[0], (x[1].get("name") or "").lower()))

            out = []
            for score, it in candidates[:limit]:
                out.append({
                    "page_id": it.get("id") or it.get("page_id"),
                    "name": it.get("name") or "",
                    "code": it.get("code") or "",
                    "category": it.get("category") or "",
                    "quantity": it.get("quantity") or 0,
                    "unit": it.get("unit"),
                    "tipo_gestione": it.get("tipo_gestione"),
                    "low_stock_threshold": it.get("low_stock_threshold") or 0,
                    "match_score": round(score, 3) if q else None,
                })
            return {"items": out, "total_found": len(candidates), "query_normalized": _normalize_text(q) if q else None}

        if tool_name == "get_product":
            data = await svc.list_inventory()
            items = (data.get("items") if isinstance(data, dict) else data) or []
            pid = (args.get("page_id") or "").strip()
            nm = (args.get("name") or "").strip()
            found = None
            if pid:
                found = next((i for i in items if (i.get("id") or i.get("page_id")) == pid), None)
            if not found and nm:
                found = _match_product(items, nm)
            if not found:
                return {"error": "not_found"}
            return {"product": {
                "page_id": found.get("id") or found.get("page_id"),
                "name": found.get("name"), "code": found.get("code"),
                "category": found.get("category"),
                "quantity": found.get("quantity"), "unit": found.get("unit"),
                "tipo_gestione": found.get("tipo_gestione"),
                "serials": found.get("serials") or [],
            }}

        if tool_name == "check_serial_availability":
            sn = (args.get("serial") or "").strip()
            if not sn:
                return {"error": "missing_serial"}
            data = await svc.list_inventory()
            items = (data.get("items") if isinstance(data, dict) else data) or []
            hit = None
            for it in items:
                for s in (it.get("serials") or []):
                    if str(s).strip().lower() == sn.lower():
                        hit = it; break
                if hit: break
            if hit:
                return {"serial": sn, "available": True, "product": hit.get("name"), "product_code": hit.get("code")}
            # Verifica se compare in una spedizione (già usato)
            try:
                exits = await svc.list_exits()
                match = next((e for e in exits if sn.lower() in (str(e.get("sn") or "")).lower()), None)
                if match:
                    return {"serial": sn, "available": False,
                            "used_in_shipment": {"id": match.get("id"), "date": match.get("date"),
                                                 "cliente": match.get("cliente"), "product": match.get("item_name")}}
            except Exception:
                pass
            return {"serial": sn, "available": False, "reason": "not_found_in_inventory"}

        if tool_name == "search_shipments":
            limit = int(args.get("limit") or 20)
            exits = await svc.list_exits(
                date_from=args.get("date_from"), date_to=args.get("date_to"),
            )
            cliente = (args.get("cliente") or "").strip().lower()
            product = (args.get("product") or "").strip().lower()
            out = []
            for e in exits:
                if cliente and cliente not in (str(e.get("cliente") or "").lower()): continue
                if product and product not in (str(e.get("item_name") or "").lower()): continue
                out.append({k: _sanitize(v) for k, v in e.items() if k in ("id", "date", "item_name", "sn", "quantity", "cliente", "taken_by", "unit")})
                if len(out) >= limit: break
            return {"items": out, "total_returned": len(out)}

        if tool_name == "search_arrivals":
            limit = int(args.get("limit") or 20)
            recs = await svc.list_receipts_all(date_from=args.get("date_from"), date_to=args.get("date_to"))
            product = (args.get("product") or "").strip().lower()
            out = []
            for r in recs:
                if product and product not in (str(r.get("item_name") or "").lower()): continue
                out.append({k: _sanitize(v) for k, v in r.items() if k in ("id", "date", "item_name", "sn", "quantity", "unit")})
                if len(out) >= limit: break
            return {"items": out, "total_returned": len(out)}

        if tool_name == "search_movements":
            limit = int(args.get("limit") or 30)
            recs = await svc.list_receipts_all()
            exits = await svc.list_exits()
            product = (args.get("product") or "").strip().lower()
            mv = []
            for r in recs:
                mv.append({"tipo": "arrivo", "date": r.get("date"), "item_name": r.get("item_name"),
                           "sn": r.get("sn"), "quantity": r.get("quantity")})
            for e in exits:
                mv.append({"tipo": "spedizione", "date": e.get("date"), "item_name": e.get("item_name"),
                           "sn": e.get("sn"), "quantity": e.get("quantity"), "cliente": e.get("cliente")})
            if product:
                mv = [m for m in mv if product in (str(m.get("item_name") or "").lower())]
            mv.sort(key=lambda x: x.get("date") or "", reverse=True)
            return {"items": mv[:limit], "total_returned": min(len(mv), limit)}

        if tool_name == "get_anomalies":
            limit = int(args.get("limit") or 30)
            docs = []
            async for d in db.anomalies.find({}).sort("at", -1).limit(limit):
                d.pop("_id", None)
                if isinstance(d.get("at"), datetime):
                    d["at"] = d["at"].isoformat()
                docs.append(d)
            return {"items": docs, "total_returned": len(docs)}

        if tool_name == "search_logs":
            limit = int(args.get("limit") or 30)
            q: Dict[str, Any] = {}
            if args.get("category"): q["category"] = args["category"].upper()
            if args.get("user"): q["user"] = {"$regex": re.escape(args["user"]), "$options": "i"}
            if args.get("product"): q["product"] = {"$regex": re.escape(args["product"]), "$options": "i"}
            if args.get("serial"): q["serial"] = {"$regex": re.escape(args["serial"]), "$options": "i"}
            if args.get("status"): q["status"] = args["status"].upper()
            docs = []
            async for d in db.app_events.find(q).sort("created_at", -1).limit(limit):
                d.pop("_id", None)
                if isinstance(d.get("created_at"), datetime):
                    d["created_at"] = d["created_at"].isoformat()
                docs.append(d)
            return {"items": docs, "total_returned": len(docs)}

        if tool_name == "get_dashboard_summary":
            data = await svc.list_inventory()
            items = (data.get("items") if isinstance(data, dict) else data) or []
            tot_products = len(items)
            low = [i for i in items if (i.get("quantity") or 0) <= (i.get("low_stock_threshold") or 0) and (i.get("quantity") or 0) > 0]
            empty = [i for i in items if (i.get("quantity") or 0) == 0]
            return {
                "total_products": tot_products,
                "low_stock": [{"name": i.get("name"), "quantity": i.get("quantity"), "threshold": i.get("low_stock_threshold")} for i in low[:15]],
                "empty": [{"name": i.get("name")} for i in empty[:15]],
                "total_low_stock": len(low), "total_empty": len(empty),
            }

        if tool_name == "search_commesse":
            # F23 — Rispetta feature flag: se OFF, ritorna vuoto senza inventare
            feat = await db.settings.find_one({"_id": "features"}) or {}
            if not feat.get("commesse_enabled"):
                return {"error": "commesse_disabled", "items": [], "hint": "Modulo Commesse disattivato in Admin → Funzioni"}
            # Normalizza sinonimi stato
            STATE_SYN = {
                "parzialmente preparata": "parziale", "parzialmente preparate": "parziale",
                "parzialmente": "parziale",
                "pronta per spedizione": "pronta", "pronte per spedizione": "pronta",
                "pronta per la spedizione": "pronta",
                "da fare": "da_preparare", "da preparare": "da_preparare",
                "in preparazione": "in_preparazione",
                "bozza": "bozza_spedizione", "bozza spedizione": "bozza_spedizione",
                "in bozza": "bozza_spedizione",
            }
            q: Dict[str, Any] = {}
            raw_stato = (args.get("stato") or "").strip().lower()
            if raw_stato:
                q["stato"] = STATE_SYN.get(raw_stato, raw_stato.replace(" ", "_"))
            if args.get("priorita"): q["priorita"] = args["priorita"]
            if args.get("cliente"): q["cliente"] = {"$regex": re.escape(args["cliente"]), "$options": "i"}
            limit = int(args.get("limit") or 20)
            items = []
            async for d in db.commesse.find(q).sort([("priorita", 1), ("data_prevista", 1), ("created_at", -1)]).limit(limit):
                d.pop("_id", None)
                for k in ("created_at", "updated_at", "presa_in_carico_at"):
                    if isinstance(d.get(k), datetime): d[k] = d[k].isoformat()
                righe = d.get("righe") or []
                tot_req = sum(float(r.get("qty_richiesta") or 0) for r in righe)
                tot_prev = sum(float(r.get("qty_prelevata") or 0) for r in righe)
                items.append({
                    "number": d.get("number"),
                    "cliente": d.get("cliente"),
                    "stato": d.get("stato"),
                    "priorita": d.get("priorita"),
                    "data_prevista": d.get("data_prevista"),
                    "operatore_carico": d.get("operatore_carico"),
                    "avanzamento": f"{tot_prev:g}/{tot_req:g}",
                    "righe_count": len(righe),
                    "operation_id": d.get("operation_id"),
                })
            return {"items": items, "total_returned": len(items)}

        if tool_name == "get_commessa":
            feat = await db.settings.find_one({"_id": "features"}) or {}
            if not feat.get("commesse_enabled"):
                return {"error": "commesse_disabled", "hint": "Modulo Commesse disattivato in Admin → Funzioni"}
            num = (args.get("number") or "").strip()
            if not num: return {"error": "missing_number"}
            # Supporta sia number esatto sia "125" quando salvato come "#125"
            d = await db.commesse.find_one({"number": num})
            if not d:
                d = await db.commesse.find_one({"number": {"$regex": f"^#?{re.escape(num)}$", "$options": "i"}})
            if not d: return {"error": "not_found", "hint": f"Nessuna commessa con number '{num}'"}
            d.pop("_id", None)
            for k in ("created_at", "updated_at", "presa_in_carico_at", "completed_at", "shipped_at"):
                if isinstance(d.get(k), datetime): d[k] = d[k].isoformat()
            righe = d.get("righe") or []
            materiale_mancante = []
            materiale_prelevato = []
            for r in righe:
                req = float(r.get("qty_richiesta") or 0)
                prev = float(r.get("qty_prelevata") or 0)
                miss = req - prev
                base = {"product_name": r.get("product_name"), "product_code": r.get("product_code"),
                        "tipo_gestione": r.get("tipo_gestione"),
                        "qty_richiesta": req, "qty_prelevata": prev}
                if miss > 0:
                    materiale_mancante.append({**base, "qty_mancante": miss})
                if prev > 0:
                    materiale_prelevato.append({**base, "seriali_prelevati": r.get("seriali_prelevati") or []})
            return {
                "commessa": d,
                "materiale_mancante": materiale_mancante,
                "materiale_prelevato": materiale_prelevato,
                "completa": len(materiale_mancante) == 0,
            }

        if tool_name == "get_product_serials":
            # F22 (26/02/2026) — Elenco seriali completo per prodotto (solo A Seriale).
            # Usa lo stesso matching di search_products per riconoscere abbreviazioni.
            q = (args.get("product_name_or_code") or "").strip()
            if not q:
                return {"error": "missing_query", "hint": "Specifica quale prodotto"}
            include_shipped = bool(args.get("include_shipped"))
            data = await svc.list_inventory()
            items = (data.get("items") if isinstance(data, dict) else data) or []
            # Solo prodotti A Seriale (i seriali non hanno senso per A Quantità)
            serial_items = [it for it in items if it.get("tipo_gestione") == "a_seriale"]
            scored = sorted(
                [(_match_score(q, it), it) for it in serial_items],
                key=lambda x: -x[0],
            )
            matches = [(s, it) for s, it in scored if s >= 0.5]
            if not matches:
                return {"error": "not_found", "hint": f"Nessun prodotto A Seriale trovato per '{q}'"}

            # Se il top match ha score >> secondo → univoco. Altrimenti mostra i pari-merito.
            top_score = matches[0][0]
            selected = [(s, it) for s, it in matches if (top_score - s) < 0.05]

            # Recupera i seriali spediti se richiesto (in un colpo solo per efficienza)
            shipped_by_product: Dict[str, List[Dict[str, Any]]] = {}
            if include_shipped:
                try:
                    exits = await svc.list_exits()
                    for e in exits or []:
                        sn = str(e.get("sn") or "").strip()
                        if not sn or sn == "—":
                            continue
                        # Può contenere N seriali (separati da \n, virgola, spazi)
                        pieces = [p.strip() for p in re.split(r"[,;\n\s]+", sn) if p.strip()]
                        item_ids = e.get("item_ids") or []
                        item_name = (e.get("item_name") or "").lower()
                        for pid in item_ids or [None]:
                            key = pid or item_name
                            shipped_by_product.setdefault(key, []).extend([
                                {"serial": p, "date": e.get("date"), "cliente": e.get("cliente"), "shipment_id": e.get("id")}
                                for p in pieces
                            ])
                except Exception as ex:
                    logger.warning(f"list_exits nel get_product_serials fallito: {ex}")

            products_out: List[Dict[str, Any]] = []
            for score, it in selected:
                available = [str(s).strip() for s in (it.get("serials") or []) if str(s).strip()]
                pid = it.get("id") or it.get("page_id")
                shipped = []
                if include_shipped:
                    shipped = shipped_by_product.get(pid) or shipped_by_product.get((it.get("name") or "").lower()) or []
                inventory_qty = it.get("quantity") or 0
                coherent = (len(available) == inventory_qty)
                products_out.append({
                    "page_id": pid,
                    "name": it.get("name"),
                    "code": it.get("code"),
                    "quantity_inventory": inventory_qty,
                    "serials_available_count": len(available),
                    "serials_available": available,
                    "shipped_count": len(shipped) if include_shipped else None,
                    "shipped": (shipped if include_shipped else None),
                    "quantity_vs_serials_coherent": coherent,
                    "possible_anomaly": (None if coherent else f"Quantità inventario ({inventory_qty}) ≠ numero seriali disponibili ({len(available)}) — POSSIBILE ANOMALIA"),
                    "match_score": round(score, 3),
                })

            return {
                "ambiguous": len(selected) > 1,
                "products": products_out,
                "total_available_serials": sum(p["serials_available_count"] for p in products_out),
                "query_normalized": _normalize_text(q),
            }

        if tool_name == "search_installation_reports":
            limit = max(1, min(int(args.get("limit") or 20), 50))
            q = _normalize_text(str(args.get("query") or ""))
            tecnico_q = _normalize_text(str(args.get("tecnico") or ""))
            cliente_q = _normalize_text(str(args.get("cliente") or ""))
            date_from = str(args.get("date_from") or "").strip()
            date_to = str(args.get("date_to") or "").strip()

            # Carica solo installazioni che hanno almeno un report salvato o generato.
            docs = await db.crm_installazioni.find({
                "$or": [
                    {"report_installazione_document_id": {"$exists": True, "$nin": [None, ""]}},
                    {"report_installazione_data": {"$exists": True, "$ne": {}}},
                ]
            }).sort("report_updated_at", -1).to_list(length=300)

            # Cache nomi cliente/sede per evitare N query duplicate.
            client_ids = {str(d.get("cliente_id") or "") for d in docs if d.get("cliente_id")}
            site_ids = {str(d.get("sede_id") or "") for d in docs if d.get("sede_id")}
            clients = {}
            sites = {}
            if client_ids:
                for c in await db.crm_clienti.find({"id": {"$in": list(client_ids)}}).to_list(length=len(client_ids)):
                    clients[str(c.get("id") or "")] = c
            if site_ids:
                for x in await db.crm_sedi.find({"id": {"$in": list(site_ids)}}).to_list(length=len(site_ids)):
                    sites[str(x.get("id") or "")] = x

            out = []
            for d in docs:
                c = clients.get(str(d.get("cliente_id") or ""), {})
                site = sites.get(str(d.get("sede_id") or ""), {})
                client_name = c.get("ragione_sociale") or " ".join(x for x in [c.get("nome"), c.get("cognome")] if x) or d.get("cliente_nome") or ""
                site_name = site.get("nome") or site.get("denominazione") or site.get("comune") or ""
                tech = d.get("tecnico") or d.get("installatore") or d.get("report_updated_by") or d.get("report_generated_by") or ""
                date_val = str(d.get("data") or d.get("report_generated_at") or d.get("report_updated_at") or "")
                if date_from and date_val and date_val[:10] < date_from:
                    continue
                if date_to and date_val and date_val[:10] > date_to:
                    continue
                if tecnico_q and tecnico_q not in _normalize_text(str(tech)):
                    continue
                if cliente_q and cliente_q not in _normalize_text(str(client_name)):
                    continue
                searchable = _normalize_text(" ".join([
                    str(client_name), str(site_name), str(tech), str(date_val),
                    str(d.get("note") or ""), str(d.get("report_updated_by") or ""),
                    str(d.get("report_generated_by") or ""),
                    str(d.get("report_installazione_data") or "")[:1200],
                ]))
                if q and q not in searchable:
                    # Token tolerant: tutte le parole significative devono comparire.
                    toks = [t for t in q.split() if len(t) > 2 and t not in {"report", "installazione", "installazioni", "fatto", "fatti", "recupera", "recuperami"}]
                    if toks and not all(t in searchable for t in toks):
                        continue
                out.append({
                    "installation_id": str(d.get("id") or ""),
                    "cliente": client_name,
                    "sede": site_name,
                    "tecnico": tech,
                    "data": date_val[:10] if date_val else "",
                    "report_salvato": bool(d.get("report_installazione_data")),
                    "report_generato": bool(d.get("report_installazione_document_id")),
                    "document_id": d.get("report_installazione_document_id") or "",
                    "aggiornato_da": d.get("report_updated_by") or d.get("report_generated_by") or "",
                })
                if len(out) >= limit:
                    break
            return {"items": out, "total_returned": len(out), "query": args.get("query") or ""}

        if tool_name == "search_crm":
            resource = str(args.get("resource") or "").strip()
            mapping = {
                "clienti": "crm_clienti", "contatti": "crm_contatti", "sedi": "crm_sedi",
                "sopralluoghi": "crm_sopralluoghi", "preventivi": "crm_preventivi",
                "ordini-clienti": "crm_ordini_clienti", "installazioni": "crm_installazioni",
                "assistenza": "crm_assistenza",
            }
            collection = mapping.get(resource)
            if not collection:
                return {"error": "invalid_resource"}
            limit = max(1, min(int(args.get("limit") or 20), 50))
            docs = await db[collection].find({}).sort("updated_at", -1).to_list(length=500)
            q = _normalize_text(str(args.get("query") or ""))
            out = []
            for d in docs:
                d.pop("_id", None)
                if q and q not in _normalize_text(" ".join(str(v) for v in d.values())):
                    continue
                safe = {k: _sanitize(v, 500) for k, v in d.items() if k not in ("pdf_signature",)}
                out.append(safe)
                if len(out) >= limit:
                    break
            return {"resource": resource, "items": out, "total_returned": len(out)}

        if tool_name == "prepare_create_product":
            name = str(args.get("name") or "").strip()
            if not name:
                return {"error": "product_name_required"}
            warehouse_id = str(args.get("warehouse_id") or "").strip().lower()
            unit = str(args.get("unit") or "").strip().lower()
            if warehouse_id not in ("elios-tech", "verona"):
                return {"error": "warehouse_required", "hint": "Chiedi in quale magazzino creare il prodotto: Elios Tech oppure Verona"}
            if unit not in ("pz", "m"):
                return {"error": "unit_required", "hint": "Chiedi se il prodotto è gestito a pezzi oppure a metri"}
            # Evita duplicati evidenti nel solo deposito scelto.
            data = await svc.list_inventory(warehouse_id=warehouse_id)
            items = data.get("items") if isinstance(data, dict) else (data or [])
            exact = _match_product(items or [], name)
            if exact and _match_score(name, exact) >= 0.95:
                return {"error": "product_already_exists", "product": {
                    "id": exact.get("page_id") or exact.get("id"),
                    "name": exact.get("name"), "code": exact.get("code")
                }}
            product_data = {
                "name": name,
                "code": str(args.get("code") or "").strip(),
                "category": str(args.get("category") or "").strip(),
                "brand": str(args.get("brand") or "").strip(),
                "warehouse_id": warehouse_id,
                "unit": unit,
                "tipo_gestione": str(args.get("tipo_gestione") or "a_quantita").strip(),
                "low_stock_threshold": float(args.get("low_stock_threshold") or 0),
                "location": str(args.get("location") or "").strip(),
                "supplier": str(args.get("supplier") or "").strip(),
                "notes": str(args.get("notes") or "").strip(),
                "active": True,
            }
            if product_data["tipo_gestione"] not in ("a_seriale", "a_quantita"):
                return {"error": "invalid_product_management_type"}
            if product_data["tipo_gestione"] == "a_seriale" and unit != "pz":
                return {"error": "invalid_serial_unit", "hint": "Un prodotto a seriale deve essere gestito a pezzi"}
            preview_id = f"ai-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-product-create"
            op = {"operation_type": "product_create", "data": product_data}
            summary = {"operation_type": "product_create", "resource": "prodotti",
                       "description": name, "data": product_data}
            await db.ai_pending_ops.insert_one({
                "preview_id": preview_id, "user_id": str(current_user.get("_id")),
                "status": "pending", "operation": op, "summary": summary,
                "created_at": datetime.now(timezone.utc),
            })
            return {"preview_ready": True, "preview_id": preview_id, "summary": summary}

        if tool_name == "prepare_update_product":
            product_id = str(args.get("product_id") or "").strip()
            data = args.get("data") or {}
            if not product_id or not isinstance(data, dict) or not data:
                return {"error": "product_id_and_data_required"}
            preview_id = f"ai-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-product-update"
            op = {"operation_type": "product_update", "product_id": product_id, "data": data}
            summary = {"operation_type": "product_update", "resource": "prodotti",
                       "description": str(data.get("name") or product_id), "data": data}
            await db.ai_pending_ops.insert_one({
                "preview_id": preview_id, "user_id": str(current_user.get("_id")),
                "status": "pending", "operation": op, "summary": summary,
                "created_at": datetime.now(timezone.utc),
            })
            return {"preview_ready": True, "preview_id": preview_id, "summary": summary}

        if tool_name == "prepare_archive_product":
            product_id = str(args.get("product_id") or "").strip()
            if not product_id:
                return {"error": "product_id_required"}
            pname = str(args.get("product_name") or product_id)
            preview_id = f"ai-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S%f')}-product-archive"
            op = {"operation_type": "product_archive", "product_id": product_id}
            summary = {"operation_type": "product_archive", "resource": "prodotti",
                       "description": pname}
            await db.ai_pending_ops.insert_one({
                "preview_id": preview_id, "user_id": str(current_user.get("_id")),
                "status": "pending", "operation": op, "summary": summary,
                "created_at": datetime.now(timezone.utc),
            })
            return {"preview_ready": True, "preview_id": preview_id, "summary": summary}

        if tool_name in ("prepare_create_record", "prepare_update_record"):
            resource = str(args.get("resource") or "").strip()
            allowed = {"clienti","contatti","sedi","sopralluoghi","preventivi","ordini-clienti","installazioni","assistenza"}
            if resource not in allowed:
                return {"error": "invalid_resource"}
            data = args.get("data") or {}
            if not isinstance(data, dict) or not data:
                return {"error": "missing_data"}
            record_id = str(args.get("id") or "").strip()
            if tool_name == "prepare_update_record" and not record_id:
                return {"error": "missing_id"}
            operation_type = "crm_create" if tool_name == "prepare_create_record" else "crm_update"
            preview = {
                "operation_type": operation_type,
                "resource": resource,
                "record_id": record_id or None,
                "data": data,
                "description": (data.get("ragione_sociale") or data.get("numero") or data.get("nome") or data.get("descrizione") or resource),
            }
            preview_id = f"AIOP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{abs(hash(str(preview))) % 100000:05d}"
            await db.ai_pending_ops.insert_one({
                "preview_id": preview_id,
                "user": current_user.get("username"),
                "user_id": str(current_user.get("_id")),
                "created_at": datetime.now(timezone.utc),
                "operation": preview,
                "status": "pending",
            })
            return {"preview_ready": True, "preview_id": preview_id, "summary": preview}

        if tool_name == "prepare_commessa_action":
            cid = str(args.get("commessa_id") or "").strip()
            action = str(args.get("action") or "").strip()
            allowed_actions = {"take", "pick", "complete", "reopen-preparation", "draft", "draft-cancel"}
            if not cid or action not in allowed_actions:
                return {"error": "invalid_commessa_action"}
            comm = await db.commesse.find_one({"id": cid})
            if not comm:
                return {"error": "commessa_not_found"}
            data = args.get("data") or {}
            preview = {
                "operation_type": "commessa_action",
                "commessa_id": cid,
                "action": action,
                "data": data if isinstance(data, dict) else {},
                "description": f"Commessa #{comm.get('number') or cid}",
            }
            preview_id = f"AIOP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{abs(hash(str(preview))) % 100000:05d}"
            await db.ai_pending_ops.insert_one({
                "preview_id": preview_id, "user": current_user.get("username"),
                "user_id": str(current_user.get("_id")), "created_at": datetime.now(timezone.utc),
                "operation": preview, "status": "pending",
            })
            return {"preview_ready": True, "preview_id": preview_id, "summary": preview}

        # ── Operazioni preparatorie (nessuna esecuzione — solo preview) ──
        if tool_name == "prepare_shipment":
            data = await svc.list_inventory()
            items = (data.get("items") if isinstance(data, dict) else data) or []
            p = _match_product(items, args.get("product_name_or_code") or "")
            if not p:
                return {"error": "product_not_found", "hint": "Il prodotto non esiste in inventario"}
            tg = p.get("tipo_gestione")
            qty = float(args.get("quantity") or 0)
            serials = [s.strip() for s in (args.get("serials") or []) if str(s or "").strip()]
            cliente = (args.get("cliente") or "").strip()
            taken_by = (args.get("taken_by") or current_user.get("username") or "").strip()
            if not cliente:
                return {"error": "missing_cliente"}
            errors: List[str] = []
            if tg == "a_seriale":
                if not serials:
                    return {"error": "missing_serials", "hint": "Prodotto A Seriale: fornisci almeno un seriale"}
                available_sns = {str(s).strip().lower() for s in (p.get("serials") or [])}
                for s in serials:
                    if s.lower() not in available_sns:
                        errors.append(f"SN '{s}' non disponibile in inventario")
                qty = float(len(serials))
            elif tg == "a_quantita":
                if qty <= 0:
                    return {"error": "missing_quantity", "hint": "Prodotto A Quantità: specifica quantity > 0"}
                current_qty = float(p.get("quantity") or 0)
                if qty > current_qty:
                    errors.append(f"Quantità richiesta ({qty}) > disponibile ({current_qty})")
            else:
                return {"error": "tipo_gestione_missing", "hint": f"Prodotto '{p.get('name')}' senza tipo_gestione configurato"}
            if errors:
                return {"validation_failed": True, "errors": errors,
                        "product": p.get("name"), "product_code": p.get("code"), "tipo_gestione": tg}
            preview = {
                "operation_type": "shipment",
                "product_page_id": p.get("id") or p.get("page_id"),
                "product_name": p.get("name"),
                "product_code": p.get("code"),
                "tipo_gestione": tg,
                "quantity": qty,
                "serials": serials,
                "cliente": cliente,
                "taken_by": taken_by or current_user.get("username"),
                "current_quantity_before": p.get("quantity"),
            }
            preview_id = f"AIOP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{abs(hash(str(preview))) % 100000:05d}"
            await db.ai_pending_ops.insert_one({
                "preview_id": preview_id,
                "user": current_user.get("username"),
                "user_id": str(current_user.get("_id")),
                "created_at": datetime.now(timezone.utc),
                "operation": preview,
                "status": "pending",
            })
            return {"preview_ready": True, "preview_id": preview_id, "summary": preview}

        if tool_name == "prepare_arrival":
            warehouse_id = str(args.get("warehouse_id") or "").strip().lower()
            if warehouse_id not in ("elios-tech", "verona"):
                return {"error": "warehouse_required"}
            data = await svc.list_inventory(warehouse_id=warehouse_id)
            items = (data.get("items") if isinstance(data, dict) else data) or []
            p = _match_product(items, args.get("product_name_or_code") or "")
            if not p:
                return {"error": "product_not_found"}
            tg = p.get("tipo_gestione")
            qty = float(args.get("quantity") or 0)
            serials = [s.strip() for s in (args.get("serials") or []) if str(s or "").strip()]
            errors: List[str] = []
            if tg == "a_seriale":
                if not serials:
                    return {"error": "missing_serials"}
                existing = {str(s).strip().lower() for s in (p.get("serials") or [])}
                for s in serials:
                    if s.lower() in existing:
                        errors.append(f"SN '{s}' già presente in inventario")
                qty = float(len(serials))
            elif tg == "a_quantita":
                if qty <= 0:
                    return {"error": "missing_quantity"}
            else:
                return {"error": "tipo_gestione_missing"}
            if errors:
                return {"validation_failed": True, "errors": errors}
            preview = {
                "operation_type": "arrival",
                "product_page_id": p.get("id") or p.get("page_id"),
                "product_name": p.get("name"),
                "product_code": p.get("code"),
                "tipo_gestione": tg,
                "quantity": qty,
                "serials": serials,
                "fornitore": (args.get("fornitore") or "").strip() or None,
                "warehouse_id": warehouse_id,
                "unit": p.get("unit") or "pz",
                "current_quantity_before": p.get("quantity"),
            }
            preview_id = f"AIOP-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M%S')}-{abs(hash(str(preview))) % 100000:05d}"
            await db.ai_pending_ops.insert_one({
                "preview_id": preview_id,
                "user": current_user.get("username"),
                "user_id": str(current_user.get("_id")),
                "created_at": datetime.now(timezone.utc),
                "operation": preview,
                "status": "pending",
            })
            return {"preview_ready": True, "preview_id": preview_id, "summary": preview}

        return {"error": "unknown_tool", "tool": tool_name}
    except Exception as e:
        logger.exception(f"dispatch_tool({tool_name}) failed")
        return {"error": "tool_execution_failed", "message": str(e)[:200]}
