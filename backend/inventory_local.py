"""Magazzino locale multi-deposito del Gestionale Elios Tech.

Ogni deposito possiede la propria anagrafica prodotti, oltre a giacenze e seriali.
Un prodotto creato in un deposito non compare automaticamente nell'altro.
I trasferimenti possono creare una copia tecnica del prodotto nel deposito di destinazione
solo quando materiale viene effettivamente trasferito.
Depositi standard:
- elios-tech: magazzino principale Elios Tech
- verona: magazzino Verona

Compatibilità: se un vecchio prodotto a quantità ha `products.quantity` e non esiste
ancora una riga `warehouse_stock`, quella quantità viene inizializzata nel deposito
Elios Tech. Verona parte sempre da zero finché non riceve materiale o trasferimenti.
"""
from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

WAREHOUSE_ELIOS = "elios-tech"
WAREHOUSE_VERONA = "verona"
WAREHOUSES = {
    WAREHOUSE_ELIOS: "Magazzino Elios Tech",
    WAREHOUSE_VERONA: "Magazzino Verona",
}

_db_ref = {"db": None}


def set_db(db) -> None:
    _db_ref["db"] = db


def _db():
    if _db_ref["db"] is None:
        raise RuntimeError("inventory_local: DB non inizializzato")
    return _db_ref["db"]


def is_configured() -> bool:
    return _db_ref["db"] is not None


def invalidate_inventory_cache() -> None:
    return None


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _warehouse_id(value: Optional[str]) -> str:
    wid = (value or WAREHOUSE_ELIOS).strip().lower()
    if wid not in WAREHOUSES:
        raise ValueError(f"Deposito non valido: {value}")
    return wid


async def _warehouse_row(product: Dict[str, Any], warehouse_id: str) -> Dict[str, Any]:
    """Ritorna/inizializza la configurazione del prodotto per uno specifico deposito."""
    db = _db()
    warehouse_id = _warehouse_id(warehouse_id)
    row = await db.warehouse_stock.find_one({"product_id": product["id"], "warehouse_id": warehouse_id})
    if row is not None:
        return row
    initial = float(product.get("quantity") or 0) if warehouse_id == WAREHOUSE_ELIOS else 0.0
    now = _now_iso()
    row = {
        "product_id": product["id"], "warehouse_id": warehouse_id, "quantity": initial,
        "location": (product.get("location") or "") if warehouse_id == WAREHOUSE_ELIOS else "",
        "low_stock_threshold": float(product.get("low_stock_threshold") or 0) if warehouse_id == WAREHOUSE_ELIOS else 0.0,
        "created_at": now, "updated_at": now,
    }
    await db.warehouse_stock.insert_one(row)
    return row


async def _quantity_stock(product: Dict[str, Any], warehouse_id: str) -> float:
    """Legge la giacenza del deposito, migrando in modo trasparente il legacy."""
    row = await _warehouse_row(product, warehouse_id)
    return float(row.get("quantity") or 0)


async def _set_quantity_stock(product_id: str, warehouse_id: str, quantity: float) -> None:
    warehouse_id = _warehouse_id(warehouse_id)
    await _db().warehouse_stock.update_one(
        {"product_id": product_id, "warehouse_id": warehouse_id},
        {"$set": {"quantity": max(0.0, float(quantity or 0)), "updated_at": _now_iso()}, "$setOnInsert": {"created_at": _now_iso()}},
        upsert=True,
    )


async def _serial_counts(product_id: str, warehouse_id: str = WAREHOUSE_ELIOS) -> Dict[str, int]:
    db = _db()
    warehouse_id = _warehouse_id(warehouse_id)
    avail = await db.product_serials.count_documents({"product_id": product_id, "status": "available", "warehouse_id": warehouse_id})
    shipped = await db.product_serials.count_documents({"product_id": product_id, "status": "shipped", "last_warehouse_id": warehouse_id})
    return {"available": avail, "shipped": shipped}


def _product_to_item(doc: Dict[str, Any], available_qty: Optional[float] = None, warehouse_id: str = WAREHOUSE_ELIOS, warehouse_row: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    tipo = doc.get("tipo_gestione") or None
    if tipo not in ("a_seriale", "a_quantita"):
        tipo = None
    return {
        "id": doc["id"],
        "name": doc.get("name") or "Senza nome",
        "code": doc.get("code") or "",
        "quantity": available_qty if available_qty is not None else 0,
        "unit": doc.get("unit") or "pz",
        "category": doc.get("category"),
        "brand": doc.get("brand") or "",
        "low_stock_threshold": float((warehouse_row or {}).get("low_stock_threshold", doc.get("low_stock_threshold") or 0) or 0),
        "location": (warehouse_row or {}).get("location", doc.get("location") or "") or "",
        "supplier": doc.get("supplier") or "",
        "notes": doc.get("notes") or "",
        "unit_price": doc.get("unit_price", doc.get("notion_unit_price")),
        "power": doc.get("power") or doc.get("notion_power") or "",
        "cable": doc.get("cable") or doc.get("notion_cable") or "",
        "active": bool(doc.get("active", True)),
        "tipo_gestione": tipo,
        "warehouse_id": warehouse_id,
        "warehouse_name": WAREHOUSES.get(warehouse_id, warehouse_id),
        "url": None,
    }


async def _migrate_legacy_shared_stock(warehouse_id: str) -> None:
    """Migra trasparentemente eventuale stock creato con il vecchio catalogo condiviso."""
    warehouse_id = _warehouse_id(warehouse_id)
    if warehouse_id == WAREHOUSE_ELIOS:
        return
    db = _db()
    rows = await db.warehouse_stock.find({"warehouse_id": warehouse_id, "quantity": {"$gt": 0}}).to_list(length=5000)
    product_ids = {str(r.get("product_id")) for r in rows if r.get("product_id")}
    async for serial in db.product_serials.find({"warehouse_id": warehouse_id, "status": "available"}):
        if serial.get("product_id"):
            product_ids.add(str(serial.get("product_id")))
    for pid in product_ids:
        source = await db.products.find_one({"id": pid})
        if not source:
            continue
        owner = source.get("warehouse_id") or WAREHOUSE_ELIOS
        if owner == warehouse_id:
            continue
        target = await _target_product_for_transfer(source, warehouse_id)
        legacy_row = await db.warehouse_stock.find_one({"product_id": pid, "warehouse_id": warehouse_id}) or {}
        qty = float(legacy_row.get("quantity") or 0)
        if qty > 0:
            current = await _quantity_stock(target, warehouse_id)
            await _set_quantity_stock(target["id"], warehouse_id, current + qty)
            await _set_quantity_stock(pid, warehouse_id, 0)
        await db.product_serials.update_many(
            {"product_id": pid, "warehouse_id": warehouse_id, "status": "available"},
            {"$set": {"product_id": target["id"], "updated_at": _now_iso()}},
        )


async def list_inventory(force_refresh: bool = False, warehouse_id: str = WAREHOUSE_ELIOS) -> List[Dict[str, Any]]:
    db = _db()
    warehouse_id = _warehouse_id(warehouse_id)
    await _migrate_legacy_shared_stock(warehouse_id)
    out: List[Dict[str, Any]] = []
    query: Dict[str, Any] = {"active": {"$ne": False}}
    if warehouse_id == WAREHOUSE_ELIOS:
        query["$or"] = [{"warehouse_id": WAREHOUSE_ELIOS}, {"warehouse_id": {"$exists": False}}]
    else:
        query["warehouse_id"] = warehouse_id
    async for doc in db.products.find(query):
        row = await _warehouse_row(doc, warehouse_id)
        if doc.get("tipo_gestione") == "a_seriale":
            c = await _serial_counts(doc["id"], warehouse_id)
            qty = c["available"]
        else:
            qty = float(row.get("quantity") or 0)
        out.append(_product_to_item(doc, available_qty=qty, warehouse_id=warehouse_id, warehouse_row=row))
    return out


async def get_item(page_id: str, warehouse_id: str = WAREHOUSE_ELIOS) -> Dict[str, Any]:
    db = _db()
    warehouse_id = _warehouse_id(warehouse_id)
    doc = await db.products.find_one({"id": page_id})
    if not doc:
        raise RuntimeError(f"Prodotto locale non trovato: {page_id}")
    owner = doc.get("warehouse_id") or WAREHOUSE_ELIOS
    if owner != warehouse_id:
        raise RuntimeError(f"Prodotto non presente in {WAREHOUSES.get(warehouse_id, warehouse_id)}")
    row = await _warehouse_row(doc, warehouse_id)
    if doc.get("tipo_gestione") == "a_seriale":
        qty = (await _serial_counts(doc["id"], warehouse_id))["available"]
    else:
        qty = float(row.get("quantity") or 0)
    return _product_to_item(doc, available_qty=qty, warehouse_id=warehouse_id, warehouse_row=row)


async def update_warehouse_settings(product_id: str, warehouse_id: str, *, location: str = "", low_stock_threshold: float = 0) -> Dict[str, Any]:
    db = _db(); warehouse_id = _warehouse_id(warehouse_id)
    product = await db.products.find_one({"id": product_id})
    if not product:
        raise RuntimeError("Prodotto non trovato")
    owner = product.get("warehouse_id") or WAREHOUSE_ELIOS
    if owner != warehouse_id:
        raise RuntimeError("Il prodotto appartiene a un altro magazzino")
    await _warehouse_row(product, warehouse_id)
    await db.warehouse_stock.update_one(
        {"product_id": product_id, "warehouse_id": warehouse_id},
        {"$set": {"location": (location or "").strip(), "low_stock_threshold": max(0.0, float(low_stock_threshold or 0)), "updated_at": _now_iso()}},
    )
    return await get_item(product_id, warehouse_id=warehouse_id)


async def update_tipo_gestione(page_id: str, tipo: str) -> None:
    if tipo not in ("a_seriale", "a_quantita"):
        raise ValueError("tipo must be 'a_seriale' or 'a_quantita'")
    r = await _db().products.update_one({"id": page_id}, {"$set": {"tipo_gestione": tipo, "updated_at": _now_iso()}})
    if r.matched_count == 0:
        raise RuntimeError(f"Prodotto non trovato: {page_id}")


async def update_inventory_serials(page_id: str, serials_to_add: List[str]) -> Dict[str, Any]:
    return {"added": [], "prop_found": True}


async def remove_inventory_serials(page_id: str, serials_to_remove: List[str]) -> Dict[str, Any]:
    return {"removed": list(serials_to_remove or []), "missing": [], "prop_found": True}


async def find_serial_in_inventory(sn: str, warehouse_id: Optional[str] = WAREHOUSE_ELIOS) -> Optional[Dict[str, Any]]:
    sn_clean = (sn or "").strip()
    if not sn_clean:
        return None
    db = _db()
    q: Dict[str, Any] = {"serial_lower": sn_clean.lower(), "status": "available"}
    if warehouse_id:
        q["warehouse_id"] = _warehouse_id(warehouse_id)
    row = await db.product_serials.find_one(q)
    if not row:
        return None
    product = await db.products.find_one({"id": row["product_id"]})
    if not product:
        return None
    wid = row.get("warehouse_id") or WAREHOUSE_ELIOS
    qty = (await _serial_counts(product["id"], wid))["available"]
    row_meta = await _warehouse_row(product, wid)
    item = _product_to_item(product, available_qty=qty, warehouse_id=wid, warehouse_row=row_meta)
    item["serials"] = [row["serial"]]
    return item


async def latest_serial_status(sn: str, warehouse_id: Optional[str] = None) -> Dict[str, Any]:
    """Stato globale del seriale, con indicazione del deposito corrente/ultimo deposito."""
    db = _db()
    sn_clean = (sn or "").strip()
    if not sn_clean:
        return {"status": "unseen"}
    # Cerca globalmente: serve distinguere seriali presenti in un altro deposito dai seriali mai visti.
    row = await db.product_serials.find_one({"serial_lower": sn_clean.lower()})
    if not row:
        return {"status": "unseen"}
    last_receipt = None
    last_pick = None
    if row.get("last_receipt_at"):
        last_receipt = {"id": row.get("last_receipt_id"), "matched_serial": row["serial"], "date": row.get("last_receipt_date"), "created_time": row.get("last_receipt_at"), "item_ids": [row["product_id"]], "warehouse_id": row.get("warehouse_id") or row.get("last_warehouse_id"), "url": None}
    if row.get("last_pick_at"):
        last_pick = {"id": row.get("last_pick_id"), "matched_serial": row["serial"], "cliente": row.get("last_pick_cliente"), "date": row.get("last_pick_date"), "created_time": row.get("last_pick_at"), "item_ids": [row["product_id"]], "warehouse_id": row.get("last_warehouse_id"), "url": None}
    common = {"product_id": row.get("product_id"), "serial": row.get("serial")}
    if row.get("status") == "available":
        wid = row.get("warehouse_id") or WAREHOUSE_ELIOS
        return {**common, "status": "in_warehouse", "last": last_receipt or {}, "receipt": last_receipt, "exit": last_pick, "warehouse_id": wid, "warehouse_name": WAREHOUSES.get(wid, wid)}
    wid = row.get("last_warehouse_id") or WAREHOUSE_ELIOS
    return {**common, "status": "out", "last": last_pick or {}, "receipt": last_receipt, "exit": last_pick, "warehouse_id": wid, "warehouse_name": WAREHOUSES.get(wid, wid)}


async def create_receipt(item_page_id: str, sn_title: str, quantity: float, data_consegna: str, warehouse_id: str = WAREHOUSE_ELIOS) -> str:
    db = _db(); warehouse_id = _warehouse_id(warehouse_id)
    prod = await db.products.find_one({"id": item_page_id})
    if not prod: raise RuntimeError(f"Prodotto locale non trovato: {item_page_id}")
    owner = prod.get("warehouse_id") or WAREHOUSE_ELIOS
    if owner != warehouse_id: raise RuntimeError(f"Prodotto non presente in {WAREHOUSES[warehouse_id]}")
    rid = str(uuid.uuid4()); now = _now_iso(); is_serial = prod.get("tipo_gestione") == "a_seriale"; sn_clean = (sn_title or "").strip()
    if is_serial:
        if not sn_clean: raise RuntimeError("Seriale mancante per prodotto A Seriale")
        # Un seriale può essere disponibile in un solo deposito alla volta.
        existing = await db.product_serials.find_one({"serial_lower": sn_clean.lower(), "product_id": item_page_id, "status": "available"})
        if existing and existing.get("warehouse_id") != warehouse_id:
            raise RuntimeError(f"Seriale {sn_clean} già disponibile in {WAREHOUSES.get(existing.get('warehouse_id'), existing.get('warehouse_id'))}")
        await db.product_serials.update_one(
            {"serial_lower": sn_clean.lower(), "product_id": item_page_id},
            {"$set": {"product_id": item_page_id, "serial": sn_clean, "serial_lower": sn_clean.lower(), "status": "available", "warehouse_id": warehouse_id, "last_receipt_id": rid, "last_receipt_at": now, "last_receipt_date": data_consegna, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    else:
        current = await _quantity_stock(prod, warehouse_id)
        await _set_quantity_stock(item_page_id, warehouse_id, current + float(quantity or 0))
    await db.local_receipts.insert_one({"id": rid, "product_id": item_page_id, "product_name": prod.get("name"), "sn": sn_clean if is_serial else (prod.get("name") or ""), "quantity": 1 if is_serial else float(quantity or 0), "data_consegna": data_consegna, "unit": prod.get("unit") or "pz", "warehouse_id": warehouse_id, "created_at": now})
    return rid


async def create_pick(item_page_id: str, sn_title: str, quantity: float, cliente: Optional[str], data_uscita: str, taken_by: Optional[str] = None, warehouse_id: str = WAREHOUSE_ELIOS, batch_id: Optional[str] = None) -> str:
    db = _db(); warehouse_id = _warehouse_id(warehouse_id)
    prod = await db.products.find_one({"id": item_page_id})
    if not prod: raise RuntimeError(f"Prodotto locale non trovato: {item_page_id}")
    owner = prod.get("warehouse_id") or WAREHOUSE_ELIOS
    if owner != warehouse_id: raise RuntimeError(f"Prodotto non presente in {WAREHOUSES[warehouse_id]}")
    pid = str(uuid.uuid4()); now = _now_iso(); is_serial = prod.get("tipo_gestione") == "a_seriale"; sn_clean = (sn_title or "").strip()
    if is_serial:
        if not sn_clean: raise RuntimeError("Seriale mancante per prodotto A Seriale")
        r = await db.product_serials.update_one(
            {"serial_lower": sn_clean.lower(), "product_id": item_page_id, "status": "available", "warehouse_id": warehouse_id},
            {"$set": {"status": "shipped", "last_warehouse_id": warehouse_id, "last_pick_id": pid, "last_pick_at": now, "last_pick_date": data_uscita, "last_pick_cliente": cliente, "last_pick_taken_by": taken_by, "updated_at": now}, "$unset": {"warehouse_id": ""}},
        )
        if r.matched_count == 0: raise RuntimeError(f"Seriale {sn_clean} non disponibile in {WAREHOUSES[warehouse_id]}")
    else:
        current = await _quantity_stock(prod, warehouse_id); qty = float(quantity or 0)
        if current < qty: raise RuntimeError(f"Quantità non disponibile in {WAREHOUSES[warehouse_id]}")
        await _set_quantity_stock(item_page_id, warehouse_id, current - qty)
    await db.local_picks.insert_one({"id": pid, "batch_id": batch_id or pid, "product_id": item_page_id, "product_name": prod.get("name"), "sn": sn_clean if is_serial else (prod.get("name") or ""), "quantity": 1 if is_serial else float(quantity or 0), "cliente": cliente, "taken_by": taken_by, "data_uscita": data_uscita, "unit": prod.get("unit") or "pz", "warehouse_id": warehouse_id, "created_at": now})
    return pid


async def _target_product_for_transfer(source: Dict[str, Any], target_warehouse_id: str) -> Dict[str, Any]:
    """Trova o crea l'anagrafica equivalente nel deposito di destinazione."""
    db = _db(); target_warehouse_id = _warehouse_id(target_warehouse_id)
    code = (source.get("code") or "").strip()
    query: Dict[str, Any] = {"warehouse_id": target_warehouse_id, "active": {"$ne": False}}
    if code:
        query["code_lower"] = code.lower()
    else:
        query.update({"name": source.get("name"), "unit": source.get("unit") or "pz", "tipo_gestione": source.get("tipo_gestione")})
    existing = await db.products.find_one(query)
    if existing:
        return existing
    now = _now_iso(); new_id = str(uuid.uuid4())
    clone = {k: v for k, v in source.items() if k not in {"_id", "id", "quantity", "created_at", "updated_at", "created_by", "updated_by", "location", "low_stock_threshold"}}
    clone.update({
        "id": new_id, "warehouse_id": target_warehouse_id, "quantity": 0,
        "location": "", "low_stock_threshold": 0, "created_at": now, "updated_at": now,
        "created_by": "trasferimento", "source_product_id": source.get("id"),
    })
    await db.products.insert_one(clone)
    await db.warehouse_stock.insert_one({"product_id": new_id, "warehouse_id": target_warehouse_id, "quantity": 0, "location": "", "low_stock_threshold": 0, "created_at": now, "updated_at": now})
    return clone


async def transfer_stock(item_page_id: str, quantity: float, from_warehouse_id: str, to_warehouse_id: str, serials: Optional[List[str]] = None, operator: Optional[str] = None, note: str = "") -> Dict[str, Any]:
    db = _db(); src = _warehouse_id(from_warehouse_id); dst = _warehouse_id(to_warehouse_id)
    if src == dst: raise RuntimeError("Il deposito di origine e destinazione devono essere diversi")
    if not (note or "").strip(): raise RuntimeError("La nota del trasferimento è obbligatoria")
    prod = await db.products.find_one({"id": item_page_id})
    if not prod: raise RuntimeError("Prodotto non trovato")
    owner = prod.get("warehouse_id") or WAREHOUSE_ELIOS
    if owner != src: raise RuntimeError(f"Il prodotto non appartiene a {WAREHOUSES[src]}")
    target = await _target_product_for_transfer(prod, dst)
    now = _now_iso(); tid = str(uuid.uuid4()); moved_serials: List[str] = []
    if prod.get("tipo_gestione") == "a_seriale":
        serials = [str(x).strip() for x in (serials or []) if str(x).strip()]
        if not serials: raise RuntimeError("Seleziona almeno un seriale")
        for sn in serials:
            row = await db.product_serials.find_one({"product_id": item_page_id, "serial_lower": sn.lower(), "status": "available", "warehouse_id": src})
            if not row: raise RuntimeError(f"Seriale {sn} non disponibile in {WAREHOUSES[src]}")
        for sn in serials:
            await db.product_serials.update_one(
                {"product_id": item_page_id, "serial_lower": sn.lower(), "status": "available", "warehouse_id": src},
                {"$set": {"product_id": target["id"], "warehouse_id": dst, "updated_at": now, "last_transfer_id": tid, "last_transfer_at": now}}
            )
            moved_serials.append(sn)
        quantity = len(moved_serials)
    else:
        qty = float(quantity or 0)
        if qty <= 0: raise RuntimeError("Quantità da trasferire non valida")
        src_qty = await _quantity_stock(prod, src)
        if src_qty < qty: raise RuntimeError(f"Giacenza insufficiente in {WAREHOUSES[src]}")
        dst_qty = await _quantity_stock(target, dst)
        await _set_quantity_stock(item_page_id, src, src_qty - qty)
        await _set_quantity_stock(target["id"], dst, dst_qty + qty)
    doc = {
        "id": tid, "product_id": item_page_id, "target_product_id": target.get("id"),
        "product_name": prod.get("name"), "quantity": float(quantity), "unit": prod.get("unit") or "pz",
        "serials": moved_serials, "from_warehouse_id": src, "to_warehouse_id": dst,
        "operator": operator, "note": (note or "").strip(), "created_at": now
    }
    await db.local_transfers.insert_one(doc)
    return doc


async def archive_page(page_id: str) -> None:
    db = _db()
    r_recv = await db.local_receipts.find_one({"id": page_id})
    if r_recv:
        await db.local_receipts.delete_one({"id": page_id}); prod_id = r_recv["product_id"]; wid = r_recv.get("warehouse_id") or WAREHOUSE_ELIOS; prod = await db.products.find_one({"id": prod_id})
        if prod and prod.get("tipo_gestione") == "a_quantita":
            current = await _quantity_stock(prod, wid); await _set_quantity_stock(prod_id, wid, current - float(r_recv.get("quantity") or 0))
        elif prod:
            await db.product_serials.delete_one({"last_receipt_id": page_id, "status": "available", "warehouse_id": wid})
        return
    r_pick = await db.local_picks.find_one({"id": page_id})
    if r_pick:
        await db.local_picks.delete_one({"id": page_id}); prod_id = r_pick["product_id"]; wid = r_pick.get("warehouse_id") or WAREHOUSE_ELIOS; prod = await db.products.find_one({"id": prod_id})
        if prod and prod.get("tipo_gestione") == "a_quantita":
            current = await _quantity_stock(prod, wid); await _set_quantity_stock(prod_id, wid, current + float(r_pick.get("quantity") or 0))
        elif prod:
            await db.product_serials.update_one({"last_pick_id": page_id}, {"$set": {"status": "available", "warehouse_id": wid}, "$unset": {"last_pick_id": "", "last_pick_at": "", "last_pick_date": "", "last_pick_cliente": "", "last_pick_taken_by": ""}})


async def list_receipts_all(date_from: Optional[str] = None, date_to: Optional[str] = None, warehouse_id: Optional[str] = None) -> List[Dict[str, Any]]:
    db = _db(); q: Dict[str, Any] = {}
    if date_from: q.setdefault("data_consegna", {})["$gte"] = date_from
    if date_to: q.setdefault("data_consegna", {})["$lte"] = date_to
    if warehouse_id: q["warehouse_id"] = _warehouse_id(warehouse_id)
    out = []
    async for row in db.local_receipts.find(q).sort("data_consegna", -1):
        wid = row.get("warehouse_id") or WAREHOUSE_ELIOS
        out.append({"id": row.get("id"), "sn": row.get("sn"), "quantity": row.get("quantity"), "date": row.get("data_consegna"), "item_ids": [row.get("product_id")] if row.get("product_id") else [], "item_name": row.get("product_name"), "unit": row.get("unit") or "pz", "warehouse_id": wid, "warehouse_name": WAREHOUSES.get(wid, wid), "created_time": row.get("created_at")})
    return out


async def list_exits(date_from: Optional[str] = None, date_to: Optional[str] = None, warehouse_id: Optional[str] = None) -> List[Dict[str, Any]]:
    db = _db(); q: Dict[str, Any] = {}
    if date_from: q.setdefault("data_uscita", {})["$gte"] = date_from
    if date_to: q.setdefault("data_uscita", {})["$lte"] = date_to
    if warehouse_id: q["warehouse_id"] = _warehouse_id(warehouse_id)
    out = []
    async for row in db.local_picks.find(q).sort("data_uscita", -1):
        wid = row.get("warehouse_id") or WAREHOUSE_ELIOS
        out.append({"id": row.get("id"), "batch_id": row.get("batch_id"), "product_id": row.get("product_id"), "sn": row.get("sn"), "cliente": row.get("cliente"), "taken_by": row.get("taken_by"), "quantity": row.get("quantity"), "date": row.get("data_uscita"), "item_ids": [row.get("product_id")] if row.get("product_id") else [], "item_names": [row.get("product_name")] if row.get("product_name") else [], "item_name": row.get("product_name"), "unit": row.get("unit") or "pz", "category": None, "warehouse_id": wid, "warehouse_name": WAREHOUSES.get(wid, wid), "url": None, "created_time": row.get("created_at")})
    return out


async def list_transfers(limit: int = 500) -> List[Dict[str, Any]]:
    out = []
    async for row in _db().local_transfers.find({}).sort("created_at", -1).limit(limit):
        d = dict(row); d.pop("_id", None); d["from_warehouse_name"] = WAREHOUSES.get(d.get("from_warehouse_id"), d.get("from_warehouse_id")); d["to_warehouse_name"] = WAREHOUSES.get(d.get("to_warehouse_id"), d.get("to_warehouse_id")); out.append(d)
    return out

async def reconcile_report_consumption(
    installation_id: str,
    desired: List[Dict[str, Any]],
    *,
    cliente: str = "",
    operator: str = "",
    report_date: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """Allinea il consumo materiali del report con il Magazzino Verona.

    Applica soltanto la differenza rispetto all'ultima versione del report.
    Prima valida tutte le righe, così una giacenza insufficiente non lascia
    aggiornamenti parziali su altri prodotti.
    """
    db = _db(); wid = WAREHOUSE_VERONA; now = _now_iso()
    report_date = report_date or datetime.now(timezone.utc).date().isoformat()
    previous_rows = await db.local_report_consumptions.find({"installation_id": installation_id}).to_list(length=500)
    previous = {str(x.get("product_id")): float(x.get("quantity") or 0) for x in previous_rows}
    normalized: Dict[str, float] = {}
    for row in desired or []:
        pid = str(row.get("product_id") or "").strip()
        qty = float(row.get("quantity") or 0)
        if pid and qty > 0:
            normalized[pid] = normalized.get(pid, 0.0) + qty

    plan: List[Dict[str, Any]] = []
    for pid in set(previous) | set(normalized):
        old = previous.get(pid, 0.0); new = normalized.get(pid, 0.0); delta_consumption = new - old
        if abs(delta_consumption) < 1e-9:
            continue
        product = await db.products.find_one({"id": pid})
        if not product:
            raise RuntimeError(f"Prodotto Verona non trovato: {pid}")
        owner = product.get("warehouse_id") or WAREHOUSE_ELIOS
        if owner != wid:
            raise RuntimeError(f"{product.get('name') or 'Prodotto'} non appartiene al Magazzino Verona")
        if product.get("tipo_gestione") != "a_quantita":
            raise RuntimeError(f"{product.get('name') or 'Prodotto'} deve essere gestito a quantità per il consumo da report")
        current = await _quantity_stock(product, wid)
        if delta_consumption > 0 and current + 1e-9 < delta_consumption:
            raise RuntimeError(f"Giacenza insufficiente in Magazzino Verona per {product.get('name')}: disponibili {current:g}, richiesti {delta_consumption:g}")
        plan.append({"pid": pid, "delta": delta_consumption, "product": product, "current": current})

    changes: List[Dict[str, Any]] = []
    for step in plan:
        pid = step["pid"]; delta_consumption = step["delta"]; product = step["product"]; current = step["current"]
        new_stock = current - delta_consumption
        await _set_quantity_stock(pid, wid, new_stock)
        await db.local_stock_adjustments.insert_one({
            "id": str(uuid.uuid4()), "installation_id": installation_id, "product_id": pid,
            "product_name": product.get("name"), "warehouse_id": wid,
            "quantity_change": -delta_consumption, "unit": product.get("unit") or "pz",
            "reason": "report_installazione", "cliente": cliente, "operator": operator,
            "date": report_date, "created_at": now,
        })
        changes.append({"product_id": pid, "product_name": product.get("name"), "difference": delta_consumption, "stock_after": new_stock, "unit": product.get("unit") or "pz"})

    for pid, qty in normalized.items():
        await db.local_report_consumptions.update_one(
            {"installation_id": installation_id, "product_id": pid},
            {"$set": {"quantity": qty, "updated_at": now}, "$setOnInsert": {"created_at": now}},
            upsert=True,
        )
    await db.local_report_consumptions.delete_many({"installation_id": installation_id, "product_id": {"$nin": list(normalized)}})
    return changes

