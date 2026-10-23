"""R4 — protezioni di integrità per il magazzino locale.

Questo modulo applica correzioni conservative a ``inventory_local`` senza duplicarne
l'intera implementazione storica. Le normali letture restano in inventory_local;
qui vengono rinforzate solo le mutazioni critiche (arrivi, uscite, trasferimenti).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Iterable, List

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError


_LOCK_TTL_SECONDS = 120


def _now() -> datetime:
    return datetime.now(timezone.utc)


async def _acquire_serial_locks(inv, serials: Iterable[str], owner: str) -> List[str]:
    """Lock distribuito breve basato su ``_id`` Mongo, valido anche con più istanze."""
    db = inv._db()
    keys = sorted({str(x or "").strip().lower() for x in serials if str(x or "").strip()})
    acquired: List[str] = []
    for key in keys:
        lock_id = f"serial:{key}"
        now = _now()
        doc = {"_id": lock_id, "owner": owner, "created_at": now, "expires_at": now + timedelta(seconds=_LOCK_TTL_SECONDS)}
        try:
            await db.inventory_operation_locks.insert_one(doc)
            acquired.append(lock_id)
            continue
        except DuplicateKeyError:
            # Recupera in sicurezza un eventuale lock rimasto dopo un crash.
            res = await db.inventory_operation_locks.update_one(
                {"_id": lock_id, "expires_at": {"$lt": now}},
                {"$set": {"owner": owner, "created_at": now, "expires_at": doc["expires_at"]}},
            )
            if res.matched_count:
                acquired.append(lock_id)
                continue
        await _release_serial_locks(inv, acquired, owner)
        raise RuntimeError(f"Seriale {key} già in elaborazione: riprova")
    return acquired


async def _release_serial_locks(inv, lock_ids: Iterable[str], owner: str) -> None:
    ids = list(lock_ids)
    if ids:
        await inv._db().inventory_operation_locks.delete_many({"_id": {"$in": ids}, "owner": owner})


async def _atomic_quantity_change(inv, product: Dict[str, Any], warehouse_id: str, delta: float) -> float:
    """Applica un delta atomico e impedisce che la giacenza scenda sotto zero."""
    wid = inv._warehouse_id(warehouse_id)
    await inv._warehouse_row(product, wid)
    delta = float(delta)
    query: Dict[str, Any] = {"product_id": product["id"], "warehouse_id": wid}
    if delta < 0:
        query["quantity"] = {"$gte": abs(delta)}
    row = await inv._db().warehouse_stock.find_one_and_update(
        query,
        {"$inc": {"quantity": delta}, "$set": {"updated_at": inv._now_iso()}},
        return_document=ReturnDocument.AFTER,
    )
    if row is None:
        current = await inv._quantity_stock(product, wid)
        raise RuntimeError(f"Quantità non disponibile in {inv.WAREHOUSES[wid]}: disponibili {current:g}")
    return float(row.get("quantity") or 0)


async def create_receipt(inv, item_page_id: str, sn_title: str, quantity: float, data_consegna: str, warehouse_id: str) -> str:
    db = inv._db(); wid = inv._warehouse_id(warehouse_id)
    prod = await db.products.find_one({"id": item_page_id})
    if not prod:
        raise RuntimeError(f"Prodotto locale non trovato: {item_page_id}")
    owner_wh = prod.get("warehouse_id") or inv.WAREHOUSE_ELIOS
    if owner_wh != wid:
        raise RuntimeError(f"Prodotto non presente in {inv.WAREHOUSES[wid]}")

    qty = float(quantity or 0)
    if qty <= 0:
        raise RuntimeError("Quantità arrivo deve essere maggiore di zero")
    rid = str(uuid.uuid4()); now = inv._now_iso()
    is_serial = prod.get("tipo_gestione") == "a_seriale"
    sn = (sn_title or "").strip()

    if not is_serial:
        await _atomic_quantity_change(inv, prod, wid, qty)
        try:
            await db.local_receipts.insert_one({
                "id": rid, "product_id": item_page_id, "product_name": prod.get("name"),
                "sn": prod.get("name") or "", "quantity": qty, "data_consegna": data_consegna,
                "unit": prod.get("unit") or "pz", "warehouse_id": wid, "created_at": now,
            })
        except Exception:
            await _atomic_quantity_change(inv, prod, wid, -qty)
            raise
        return rid

    if not sn:
        raise RuntimeError("Seriale mancante per prodotto A Seriale")
    op = f"receipt:{rid}"
    locks = await _acquire_serial_locks(inv, [sn], op)
    try:
        existing = await db.product_serials.find_one({"serial_lower": sn.lower()})
        if existing and str(existing.get("product_id")) != str(item_page_id):
            other = await db.products.find_one({"id": existing.get("product_id")})
            raise RuntimeError(f"Seriale {sn} già associato a {((other or {}).get('name') or 'un altro prodotto')}")
        if existing and existing.get("status") == "available":
            existing_wid = existing.get("warehouse_id") or inv.WAREHOUSE_ELIOS
            raise RuntimeError(f"Seriale {sn} già presente in {inv.WAREHOUSES.get(existing_wid, existing_wid)}")

        await db.local_receipts.insert_one({
            "id": rid, "product_id": item_page_id, "product_name": prod.get("name"),
            "sn": sn, "quantity": 1, "data_consegna": data_consegna,
            "unit": prod.get("unit") or "pz", "warehouse_id": wid, "created_at": now,
        })
        try:
            await db.product_serials.update_one(
                {"serial_lower": sn.lower(), "product_id": item_page_id},
                {"$set": {
                    "product_id": item_page_id, "serial": sn, "serial_lower": sn.lower(),
                    "status": "available", "warehouse_id": wid,
                    "last_receipt_id": rid, "last_receipt_at": now,
                    "last_receipt_date": data_consegna, "updated_at": now,
                }, "$setOnInsert": {"created_at": now}},
                upsert=True,
            )
        except Exception:
            await db.local_receipts.delete_one({"id": rid})
            raise
        return rid
    finally:
        await _release_serial_locks(inv, locks, op)


async def create_pick(inv, item_page_id: str, sn_title: str, quantity: float, cliente: str | None, data_uscita: str, taken_by: str | None, warehouse_id: str, batch_id: str | None) -> str:
    db = inv._db(); wid = inv._warehouse_id(warehouse_id)
    prod = await db.products.find_one({"id": item_page_id})
    if not prod:
        raise RuntimeError(f"Prodotto locale non trovato: {item_page_id}")
    owner_wh = prod.get("warehouse_id") or inv.WAREHOUSE_ELIOS
    if owner_wh != wid:
        raise RuntimeError(f"Prodotto non presente in {inv.WAREHOUSES[wid]}")

    qty = float(quantity or 0)
    if qty <= 0:
        raise RuntimeError("Quantità uscita deve essere maggiore di zero")
    pid = str(uuid.uuid4()); now = inv._now_iso(); sn = (sn_title or "").strip()
    is_serial = prod.get("tipo_gestione") == "a_seriale"

    if not is_serial:
        await _atomic_quantity_change(inv, prod, wid, -qty)
        try:
            await db.local_picks.insert_one({
                "id": pid, "batch_id": batch_id or pid, "product_id": item_page_id,
                "product_name": prod.get("name"), "sn": prod.get("name") or "", "quantity": qty,
                "cliente": cliente, "taken_by": taken_by, "data_uscita": data_uscita,
                "unit": prod.get("unit") or "pz", "warehouse_id": wid, "created_at": now,
            })
        except Exception:
            await _atomic_quantity_change(inv, prod, wid, qty)
            raise
        return pid

    if not sn:
        raise RuntimeError("Seriale mancante per prodotto A Seriale")
    op = f"pick:{pid}"
    locks = await _acquire_serial_locks(inv, [sn], op)
    try:
        before = await db.product_serials.find_one({
            "serial_lower": sn.lower(), "product_id": item_page_id,
            "status": "available", "warehouse_id": wid,
        })
        if not before:
            raise RuntimeError(f"Seriale {sn} non disponibile in {inv.WAREHOUSES[wid]}")
        res = await db.product_serials.update_one(
            {"_id": before["_id"], "status": "available", "warehouse_id": wid},
            {"$set": {
                "status": "shipped", "last_warehouse_id": wid, "last_pick_id": pid,
                "last_pick_at": now, "last_pick_date": data_uscita,
                "last_pick_cliente": cliente, "last_pick_taken_by": taken_by, "updated_at": now,
            }, "$unset": {"warehouse_id": ""}},
        )
        if res.matched_count != 1:
            raise RuntimeError(f"Seriale {sn} non più disponibile in {inv.WAREHOUSES[wid]}")
        try:
            await db.local_picks.insert_one({
                "id": pid, "batch_id": batch_id or pid, "product_id": item_page_id,
                "product_name": prod.get("name"), "sn": sn, "quantity": 1,
                "cliente": cliente, "taken_by": taken_by, "data_uscita": data_uscita,
                "unit": prod.get("unit") or "pz", "warehouse_id": wid, "created_at": now,
            })
        except Exception:
            snapshot = dict(before); snapshot.pop("_id", None)
            await db.product_serials.replace_one({"_id": before["_id"]}, {"_id": before["_id"], **snapshot})
            raise
        return pid
    finally:
        await _release_serial_locks(inv, locks, op)


async def transfer_stock(inv, item_page_id: str, quantity: float, from_warehouse_id: str, to_warehouse_id: str, serials: List[str] | None, operator: str | None, note: str) -> Dict[str, Any]:
    db = inv._db(); src = inv._warehouse_id(from_warehouse_id); dst = inv._warehouse_id(to_warehouse_id)
    if src == dst:
        raise RuntimeError("Il deposito di origine e destinazione devono essere diversi")
    if not (note or "").strip():
        raise RuntimeError("La nota del trasferimento è obbligatoria")
    prod = await db.products.find_one({"id": item_page_id})
    if not prod:
        raise RuntimeError("Prodotto non trovato")
    owner_wh = prod.get("warehouse_id") or inv.WAREHOUSE_ELIOS
    if owner_wh != src:
        raise RuntimeError(f"Il prodotto non appartiene a {inv.WAREHOUSES[src]}")
    target = await inv._target_product_for_transfer(prod, dst)
    tid = str(uuid.uuid4()); now = inv._now_iso(); moved: List[str] = []

    if prod.get("tipo_gestione") == "a_seriale":
        clean = [str(x).strip() for x in (serials or []) if str(x).strip()]
        lowers = [x.lower() for x in clean]
        if not clean:
            raise RuntimeError("Seleziona almeno un seriale")
        if len(lowers) != len(set(lowers)):
            raise RuntimeError("Lo stesso seriale è stato selezionato più volte")
        op = f"transfer:{tid}"
        locks = await _acquire_serial_locks(inv, clean, op)
        snapshots: List[Dict[str, Any]] = []
        try:
            for sn in clean:
                row = await db.product_serials.find_one({
                    "product_id": item_page_id, "serial_lower": sn.lower(),
                    "status": "available", "warehouse_id": src,
                })
                if not row:
                    raise RuntimeError(f"Seriale {sn} non disponibile in {inv.WAREHOUSES[src]}")
                snapshots.append(row)
            try:
                for row in snapshots:
                    res = await db.product_serials.update_one(
                        {"_id": row["_id"], "status": "available", "warehouse_id": src},
                        {"$set": {
                            "product_id": target["id"], "warehouse_id": dst,
                            "updated_at": now, "last_transfer_id": tid, "last_transfer_at": now,
                        }},
                    )
                    if res.matched_count != 1:
                        raise RuntimeError(f"Seriale {row.get('serial')} non più disponibile")
                    moved.append(row.get("serial") or "")
                doc = {
                    "id": tid, "product_id": item_page_id, "target_product_id": target.get("id"),
                    "product_name": prod.get("name"), "quantity": float(len(moved)),
                    "unit": prod.get("unit") or "pz", "serials": moved,
                    "from_warehouse_id": src, "to_warehouse_id": dst,
                    "operator": operator, "note": (note or "").strip(), "created_at": now,
                }
                await db.local_transfers.insert_one(doc)
                return doc
            except Exception:
                for row in snapshots:
                    if (row.get("serial") or "") in moved:
                        snap = dict(row); snap.pop("_id", None)
                        await db.product_serials.replace_one({"_id": row["_id"]}, {"_id": row["_id"], **snap})
                raise
        finally:
            await _release_serial_locks(inv, locks, op)

    qty = float(quantity or 0)
    if qty <= 0:
        raise RuntimeError("Quantità da trasferire non valida")
    await inv._warehouse_row(target, dst)
    await _atomic_quantity_change(inv, prod, src, -qty)
    dest_changed = False
    try:
        await _atomic_quantity_change(inv, target, dst, qty)
        dest_changed = True
        doc = {
            "id": tid, "product_id": item_page_id, "target_product_id": target.get("id"),
            "product_name": prod.get("name"), "quantity": qty, "unit": prod.get("unit") or "pz",
            "serials": [], "from_warehouse_id": src, "to_warehouse_id": dst,
            "operator": operator, "note": (note or "").strip(), "created_at": now,
        }
        await db.local_transfers.insert_one(doc)
        return doc
    except Exception:
        if dest_changed:
            await _atomic_quantity_change(inv, target, dst, -qty)
        await _atomic_quantity_change(inv, prod, src, qty)
        raise


def install(inv) -> None:
    """Applica una sola volta le protezioni al modulo inventory_local condiviso."""
    if getattr(inv, "_r4_integrity_installed", False):
        return

    async def receipt(*args, **kwargs):
        return await create_receipt(inv, *args, **kwargs)

    async def pick(*args, **kwargs):
        return await create_pick(inv, *args, **kwargs)

    async def transfer(*args, **kwargs):
        return await transfer_stock(inv, *args, **kwargs)

    inv.create_receipt = receipt
    inv.create_pick = pick
    inv.transfer_stock = transfer
    inv._r4_integrity_installed = True
