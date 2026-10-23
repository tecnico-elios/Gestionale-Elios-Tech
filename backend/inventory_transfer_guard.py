"""R4 — guardia aggiuntiva per i trasferimenti di magazzino.

Valida e riserva prima lo stock sorgente; il prodotto-clone del deposito di
destinazione viene creato solo quando il trasferimento e' realmente eseguibile.
"""
from __future__ import annotations

import uuid
from typing import Any, Dict, List

import inventory_integrity


async def transfer_stock(
    inv,
    item_page_id: str,
    quantity: float,
    from_warehouse_id: str,
    to_warehouse_id: str,
    serials: List[str] | None = None,
    operator: str | None = None,
    note: str = "",
) -> Dict[str, Any]:
    db = inv._db()
    src = inv._warehouse_id(from_warehouse_id)
    dst = inv._warehouse_id(to_warehouse_id)
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

    tid = str(uuid.uuid4())
    now = inv._now_iso()

    if prod.get("tipo_gestione") == "a_seriale":
        clean = [str(x).strip() for x in (serials or []) if str(x).strip()]
        lowers = [x.lower() for x in clean]
        if not clean:
            raise RuntimeError("Seleziona almeno un seriale")
        if len(lowers) != len(set(lowers)):
            raise RuntimeError("Lo stesso seriale è stato selezionato più volte")

        op = f"transfer:{tid}"
        locks = await inventory_integrity._acquire_serial_locks(inv, clean, op)
        snapshots: List[Dict[str, Any]] = []
        moved: List[str] = []
        target = None
        try:
            # Prima validiamo TUTTI i seriali sorgente. Nessun clone destinazione
            # viene creato se il payload e' invalido o manca anche un solo seriale.
            for sn in clean:
                row = await db.product_serials.find_one({
                    "product_id": item_page_id,
                    "serial_lower": sn.lower(),
                    "status": "available",
                    "warehouse_id": src,
                })
                if not row:
                    raise RuntimeError(
                        f"Seriale {sn} non disponibile in {inv.WAREHOUSES[src]}"
                    )
                snapshots.append(row)

            target = await inv._target_product_for_transfer(prod, dst)
            try:
                for row in snapshots:
                    res = await db.product_serials.update_one(
                        {"_id": row["_id"], "status": "available", "warehouse_id": src},
                        {"$set": {
                            "product_id": target["id"],
                            "warehouse_id": dst,
                            "updated_at": now,
                            "last_transfer_id": tid,
                            "last_transfer_at": now,
                        }},
                    )
                    if res.matched_count != 1:
                        raise RuntimeError(
                            f"Seriale {row.get('serial')} non più disponibile"
                        )
                    moved.append(row.get("serial") or "")

                doc = {
                    "id": tid,
                    "product_id": item_page_id,
                    "target_product_id": target.get("id"),
                    "product_name": prod.get("name"),
                    "quantity": float(len(moved)),
                    "unit": prod.get("unit") or "pz",
                    "serials": moved,
                    "from_warehouse_id": src,
                    "to_warehouse_id": dst,
                    "operator": operator,
                    "note": (note or "").strip(),
                    "created_at": now,
                }
                await db.local_transfers.insert_one(doc)
                return doc
            except Exception:
                for row in snapshots:
                    if (row.get("serial") or "") in moved:
                        snap = dict(row)
                        snap.pop("_id", None)
                        await db.product_serials.replace_one(
                            {"_id": row["_id"]}, {"_id": row["_id"], **snap}
                        )
                raise
        finally:
            await inventory_integrity._release_serial_locks(inv, locks, op)

    qty = float(quantity or 0)
    if qty <= 0:
        raise RuntimeError("Quantità da trasferire non valida")

    # Riserviamo prima la quantita' dalla sorgente. Se non c'e' disponibilita'
    # non viene creato alcun prodotto nel deposito destinazione.
    await inventory_integrity._atomic_quantity_change(inv, prod, src, -qty)
    target = None
    dest_changed = False
    try:
        target = await inv._target_product_for_transfer(prod, dst)
        await inv._warehouse_row(target, dst)
        await inventory_integrity._atomic_quantity_change(inv, target, dst, qty)
        dest_changed = True
        doc = {
            "id": tid,
            "product_id": item_page_id,
            "target_product_id": target.get("id"),
            "product_name": prod.get("name"),
            "quantity": qty,
            "unit": prod.get("unit") or "pz",
            "serials": [],
            "from_warehouse_id": src,
            "to_warehouse_id": dst,
            "operator": operator,
            "note": (note or "").strip(),
            "created_at": now,
        }
        await db.local_transfers.insert_one(doc)
        return doc
    except Exception:
        if dest_changed and target:
            await inventory_integrity._atomic_quantity_change(inv, target, dst, -qty)
        await inventory_integrity._atomic_quantity_change(inv, prod, src, qty)
        raise


def install(inv) -> None:
    if getattr(inv, "_r4_transfer_guard_installed", False):
        return

    async def transfer(*args, **kwargs):
        return await transfer_stock(inv, *args, **kwargs)

    inv.transfer_stock = transfer
    inv._r4_transfer_guard_installed = True
