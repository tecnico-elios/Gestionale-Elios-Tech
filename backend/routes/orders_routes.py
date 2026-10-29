"""Ordini cliente locali usati da spedizioni/commesse.

Notion non è una dipendenza operativa: dopo la migrazione iniziale gli ordini
vengono letti dalla collection MongoDB `crm_ordini_clienti`.
"""
from __future__ import annotations
from typing import Any, Dict
from fastapi import APIRouter, Depends, HTTPException, Query


def _clean(doc):
    if not doc:
        return None
    out = dict(doc)
    out.pop("_id", None)
    for k in ("created_at", "updated_at"):
        v = out.get(k)
        if hasattr(v, "isoformat"):
            out[k] = v.isoformat()
    return out


async def _labels(db, order: Dict[str, Any]) -> Dict[str, str]:
    cliente = await db.crm_clienti.find_one({"id": str(order.get("cliente_id") or "")}) if order.get("cliente_id") else None
    sede = await db.crm_sedi.find_one({"id": str(order.get("sede_id") or "")}) if order.get("sede_id") else None
    client_name = ""
    if cliente:
        client_name = (cliente.get("ragione_sociale") or cliente.get("ragioneSociale") or cliente.get("nome") or "").strip()
        if not client_name:
            client_name = " ".join(x for x in [cliente.get("nome"), cliente.get("cognome")] if x).strip()
    site_name = ""
    if sede:
        site_name = (sede.get("nome") or sede.get("indirizzo") or sede.get("comune") or "").strip()
    structure = " · ".join(x for x in [client_name, site_name] if x) or (order.get("cliente") or "").strip() or (order.get("numero") or "Ordine")
    title = " · ".join(x for x in [order.get("numero"), client_name, site_name] if x)
    return {"structure": structure, "title": title, "client_name": client_name, "site_name": site_name}


def build_router(db, deps) -> APIRouter:
    router = APIRouter(prefix="/orders", tags=["orders"])

    @router.get("/search")
    async def search_orders(
        q: str = Query(..., min_length=1, max_length=100),
        limit: int = Query(default=20, ge=1, le=50),
        current=Depends(deps.get_current_user),
    ) -> Dict[str, Any]:
        q_low = (q or "").strip().lower()
        docs = await db.crm_ordini_clienti.find({"stato": {"$ne": "Annullato"}}).sort("updated_at", -1).to_list(length=1000)
        matches = []
        for order in docs:
            labels = await _labels(db, order)
            hay = " ".join(str(x or "") for x in [order.get("numero"), order.get("data"), order.get("stato"), labels["client_name"], labels["site_name"], labels["structure"]]).lower()
            if q_low not in hay:
                continue
            matches.append({
                "id": order.get("id"),
                "structure": labels["structure"],
                "title": labels["title"],
                "url": None,
                "numero": order.get("numero"),
                "cliente_id": order.get("cliente_id"),
                "sede_id": order.get("sede_id"),
                "stato": order.get("stato"),
            })
            if len(matches) >= limit:
                break
        return {"items": matches, "count": len(matches), "query": q_low, "source": "gestionale"}

    @router.get("/{order_id}")
    async def get_order(order_id: str, current=Depends(deps.get_current_user)) -> Dict[str, Any]:
        if not order_id:
            raise HTTPException(400, "order_id mancante")
        order = await db.crm_ordini_clienti.find_one({"id": order_id})
        if not order or order.get("stato") == "Annullato":
            raise HTTPException(404, "Ordine non più disponibile")
        labels = await _labels(db, order)
        return {"id": order.get("id"), "structure": labels["structure"], "title": labels["title"], "exists": True, "source": "gestionale", "order": _clean(order)}

    return router
