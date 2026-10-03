"""Anagrafica prodotti del Magazzino locale."""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field

import auth as auth_mod
import inventory_local


class WarehouseSettingsBody(BaseModel):
    warehouse_id: str
    location: Optional[str] = Field(default="", max_length=120)
    low_stock_threshold: float = Field(default=0, ge=0)


class ProductBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    warehouse_id: str = Field(default="elios-tech", max_length=40)
    name: str = Field(min_length=1, max_length=180)
    code: Optional[str] = Field(default="", max_length=80)
    category: Optional[str] = Field(default="", max_length=100)
    brand: Optional[str] = Field(default="", max_length=100)
    unit: str = Field(default="pz", max_length=20)
    tipo_gestione: str
    low_stock_threshold: float = Field(default=0, ge=0)
    location: Optional[str] = Field(default="", max_length=120)
    supplier: Optional[str] = Field(default="", max_length=180)
    notes: Optional[str] = Field(default="", max_length=3000)
    unit_price: Optional[float] = Field(default=None, ge=0)
    power: Optional[str] = Field(default="", max_length=80)
    cable: Optional[str] = Field(default="", max_length=80)
    active: bool = True


def _clean(doc):
    if not doc:
        return None
    return {
        "id": doc.get("id"), "name": doc.get("name"), "code": doc.get("code") or "",
        "warehouse_id": doc.get("warehouse_id") or "elios-tech",
        "category": doc.get("category") or "", "brand": doc.get("brand") or "",
        "unit": doc.get("unit") or "pz", "tipo_gestione": doc.get("tipo_gestione"),
        "low_stock_threshold": float(doc.get("low_stock_threshold") or 0),
        "location": doc.get("location") or "", "supplier": doc.get("supplier") or "",
        "notes": doc.get("notes") or "", "unit_price": doc.get("unit_price", doc.get("notion_unit_price")),
        "power": doc.get("power") or doc.get("notion_power") or "", "cable": doc.get("cable") or doc.get("notion_cable") or "", "active": bool(doc.get("active", True)),
        "created_at": doc.get("created_at"), "updated_at": doc.get("updated_at"),
    }


def build_router(db, deps: auth_mod.AuthDependencies) -> APIRouter:
    router = APIRouter(prefix="/products", tags=["products"])

    def require(current, action):
        if not auth_mod.has_permission(current, "inventario", action):
            raise HTTPException(403, "Non hai il permesso per gestire i prodotti")

    @router.get("")
    async def list_products(warehouse_id: str = "elios-tech", current=Depends(deps.require_password_current)):
        require(current, "view")
        if warehouse_id not in {"elios-tech", "verona"}:
            raise HTTPException(400, "Magazzino non valido")
        # I prodotti sono anagrafiche separate per deposito. I record legacy senza
        # warehouse_id appartengono al Magazzino Elios Tech.
        query = {"warehouse_id": warehouse_id} if warehouse_id != "elios-tech" else {"$or": [{"warehouse_id": "elios-tech"}, {"warehouse_id": {"$exists": False}}]}
        docs = await db.products.find(query).sort("name", 1).to_list(length=5000)
        return {"items": [_clean(x) for x in docs], "count": len(docs)}

    @router.post("")
    async def create_product(body: ProductBody, current=Depends(deps.require_password_current)):
        require(current, "create")
        if body.tipo_gestione not in {"a_seriale", "a_quantita"}:
            raise HTTPException(400, "Seleziona una gestione valida: A Seriale oppure A Quantità")
        warehouse_id = (body.warehouse_id or "elios-tech").strip().lower()
        if warehouse_id not in {"elios-tech", "verona"}:
            raise HTTPException(400, "Magazzino non valido")
        unit = (body.unit or "pz").strip().lower()
        if unit not in {"pz", "m"}:
            raise HTTPException(400, "Unità di misura non valida: scegli Pezzi oppure Metri")
        if body.tipo_gestione == "a_seriale" and unit != "pz":
            raise HTTPException(400, "I prodotti a seriale devono essere gestiti a pezzi")
        code = (body.code or "").strip()
        scope = {"warehouse_id": warehouse_id, "active": {"$ne": False}}
        if code and await db.products.find_one({**scope, "code_lower": code.lower()}):
            raise HTTPException(409, "Esiste già un prodotto con questo codice in questo magazzino")
        now = datetime.now(timezone.utc)
        data = body.model_dump()
        data.update({
            "id": str(uuid.uuid4()), "name": body.name.strip(), "code": code,
            "code_lower": code.lower(), "unit": unit, "warehouse_id": warehouse_id,
            "quantity": 0, "created_at": now, "updated_at": now,
            "created_by": current.get("username"),
        })
        await db.products.insert_one(data)
        await db.warehouse_stock.insert_one({
            "product_id": data["id"], "warehouse_id": warehouse_id, "quantity": 0,
            "location": "", "low_stock_threshold": 0, "created_at": now, "updated_at": now,
        })
        return _clean(data)

    @router.put("/{product_id}/warehouse-settings")
    async def update_product_warehouse_settings(product_id: str, body: WarehouseSettingsBody, current=Depends(deps.require_password_current)):
        require(current, "edit")
        if body.warehouse_id not in {"elios-tech", "verona"}:
            raise HTTPException(400, "Magazzino non valido")
        try:
            return await inventory_local.update_warehouse_settings(
                product_id,
                body.warehouse_id,
                location=body.location or "",
                low_stock_threshold=body.low_stock_threshold,
            )
        except RuntimeError as exc:
            raise HTTPException(404, str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(400, str(exc)) from exc

    @router.put("/{product_id}")
    async def update_product(product_id: str, body: ProductBody, current=Depends(deps.require_password_current)):
        require(current, "edit")
        existing = await db.products.find_one({"id": product_id})
        if not existing:
            raise HTTPException(404, "Prodotto non trovato")
        if body.tipo_gestione not in {"a_seriale", "a_quantita"}:
            raise HTTPException(400, "Tipo di gestione non valido")
        old_type = existing.get("tipo_gestione")
        if old_type and old_type != body.tipo_gestione:
            serial_count = await db.product_serials.count_documents({"product_id": product_id})
            movement_count = await db.local_receipts.count_documents({"product_id": product_id}) + await db.local_picks.count_documents({"product_id": product_id})
            stocks = await db.warehouse_stock.find({"product_id": product_id}).to_list(length=20)
            stock_nonzero = any(abs(float(x.get("quantity") or 0)) > 1e-9 for x in stocks)
            legacy_nonzero = abs(float(existing.get("quantity") or 0)) > 1e-9
            if serial_count or movement_count or stock_nonzero or legacy_nonzero:
                raise HTTPException(409, "Non puoi cambiare il tipo di gestione dopo che il prodotto ha avuto giacenze o movimenti")
        existing_wh = existing.get("warehouse_id") or "elios-tech"
        requested_wh = (body.warehouse_id or existing_wh).strip().lower()
        if requested_wh != existing_wh:
            raise HTTPException(409, "Il magazzino del prodotto non si modifica: usa Trasferimenti")
        unit = (body.unit or "pz").strip().lower()
        if unit not in {"pz", "m"}:
            raise HTTPException(400, "Unità di misura non valida: scegli Pezzi oppure Metri")
        if body.tipo_gestione == "a_seriale" and unit != "pz":
            raise HTTPException(400, "I prodotti a seriale devono essere gestiti a pezzi")
        code = (body.code or "").strip()
        dup = await db.products.find_one({"id": {"$ne": product_id}, "warehouse_id": existing_wh, "code_lower": code.lower(), "active": {"$ne": False}}) if code else None
        if dup:
            raise HTTPException(409, "Esiste già un prodotto con questo codice in questo magazzino")
        data = body.model_dump()
        data.update({"warehouse_id": existing_wh, "unit": unit, "name": body.name.strip(), "code": code, "code_lower": code.lower(), "updated_at": datetime.now(timezone.utc), "updated_by": current.get("username")})
        await db.products.update_one({"id": product_id}, {"$set": data})
        return _clean(await db.products.find_one({"id": product_id}))


    @router.get("/{product_id}/serials")
    async def list_product_serials(product_id: str, warehouse_id: str = "elios-tech", current=Depends(deps.require_password_current)):
        require(current, "view")
        if warehouse_id not in {"elios-tech", "verona"}:
            raise HTTPException(400, "Magazzino non valido")
        product = await db.products.find_one({"id": product_id})
        if not product:
            raise HTTPException(404, "Prodotto non trovato")
        rows = await db.product_serials.find({"product_id": product_id, "warehouse_id": warehouse_id, "status": "available"}).sort("serial", 1).to_list(length=5000)
        return {"items": [str(x.get("serial") or "") for x in rows if x.get("serial")], "count": len(rows)}

    @router.delete("/{product_id}")
    async def archive_product(product_id: str, current=Depends(deps.require_password_current)):
        require(current, "delete")
        existing = await db.products.find_one({"id": product_id})
        if not existing:
            raise HTTPException(404, "Prodotto non trovato")
        serial_avail = await db.product_serials.count_documents({"product_id": product_id, "status": "available"})
        stocks = await db.warehouse_stock.find({"product_id": product_id}).to_list(length=20)
        qty = sum(float(x.get("quantity") or 0) for x in stocks)
        qty += float(existing.get("quantity") or 0) if not stocks else 0
        if serial_avail or abs(qty) > 1e-9:
            raise HTTPException(409, "Prima di disattivare il prodotto devi azzerare la giacenza in tutti i magazzini")
        await db.products.update_one({"id": product_id}, {"$set": {"active": False, "updated_at": datetime.now(timezone.utc), "updated_by": current.get("username")}})
        return {"ok": True}

    return router
