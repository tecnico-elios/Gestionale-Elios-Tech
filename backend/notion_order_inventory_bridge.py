from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

WAREHOUSE_ELIOS = "elios-tech"

# Negli Ordini Eliostech alcuni nomi commerciali non coincidono con il codice usato
# nell'Inventario. Gli alias sono usati SOLO per cercare un prodotto già importato:
# non creano prodotti e non trasformano accessori in Wallbox.
ORDER_CODE_ALIASES = {
    "DAZE-DUO-S-2X22": "OS01IT64TCP",
    "GOE": "GO-E-CHARGER-GEMINI-FLEX",
}

# Manteniamo questa funzione per compatibilità con gli audit/versioni precedenti, ma
# R67 non usa più euristiche di nome per assegnare i seriali: la fonte autorevole è
# Inventario/Inventory Tracker.
_ACCESSORY_HINTS = (
    "MTR", "METER", "PED-", "STAND", "CABLE", "CBL", "RFID", "QUADRO",
    "FUSE", "ADATT", "STAFFA", "RAINCOVER", "HLD-", "FOREX", "POLE", "FAN",
)
_WALLBOX_HINTS = (
    "PPR", "PLP", "CPB", "WALLBOX", "AUTEL-WB", "MAXI-CHARGER", "ABL-",
    "ABL", "DAZE-DUO", "OHME", "DCF", "GOE",
)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _clean_code(value: Any) -> str:
    text = str(value or "").strip().strip("[]\"'").strip()
    text = re.sub(r"\s+SN\s*[:#-]?\s*\d+\s*$", "", text, flags=re.I).strip()
    return text


def normalize_codes(values: Any) -> List[str]:
    """Normalizza correttamente multi-select Notion, JSON e vecchie stringhe Python-list."""
    raw: List[Any] = []
    if isinstance(values, (list, tuple, set)):
        raw.extend(values)
    elif values not in (None, ""):
        text = str(values).strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text.replace("'", '"'))
                if isinstance(parsed, list):
                    raw.extend(parsed)
                else:
                    raw.append(text)
            except Exception:
                raw.extend(re.split(r"[,;\n]+", text))
        else:
            raw.extend(re.split(r"[,;\n]+", text))

    out: List[str] = []
    seen = set()
    for item in raw:
        code = _clean_code(item)
        if not code:
            continue
        key = code.casefold()
        if key not in seen:
            seen.add(key)
            out.append(code)
    return out


def normalize_serials(values: Any) -> List[str]:
    if isinstance(values, (list, tuple, set)):
        parts: Iterable[Any] = values
    else:
        parts = re.split(r"[,;.\n\s]+", str(values or ""))
    out: List[str] = []
    seen = set()
    for value in parts:
        serial = str(value or "").strip().strip("[]\"'")
        if not serial or not re.search(r"\d", serial):
            continue
        key = serial.casefold()
        if key not in seen:
            seen.add(key)
            out.append(serial)
    return out


def looks_like_wallbox_code(code: str) -> bool:
    upper = (code or "").upper().strip()
    if not upper:
        return False
    if any(hint in upper for hint in _ACCESSORY_HINTS):
        return False
    return any(hint in upper for hint in _WALLBOX_HINTS)


def canonical_order_code(code: str) -> str:
    clean = _clean_code(code)
    return ORDER_CODE_ALIASES.get(clean.upper(), clean)


def _product_is_serial(product: Optional[Dict[str, Any]]) -> bool:
    if not product:
        return False
    if str(product.get("tipo_gestione") or "").casefold() == "a_seriale":
        return True
    category = str(product.get("category") or "").casefold()
    return category in {"wallbox", "go-e"} and str(product.get("tipo_gestione") or "").casefold() != "a_quantita"


async def _find_product_by_code(db, code: str) -> Optional[Dict[str, Any]]:
    clean = canonical_order_code(code)
    if not clean:
        return None
    low = clean.casefold()
    product = await db.products.find_one({
        "$and": [
            {"$or": [
                {"code_lower": low},
                {"code": {"$regex": f"^{re.escape(clean)}$", "$options": "i"}},
            ]},
            {"$or": [
                {"warehouse_id": WAREHOUSE_ELIOS},
                {"warehouse_id": {"$exists": False}},
                {"warehouse_id": ""},
            ]},
        ]
    })
    return product


async def _serial_products_for_codes(db, codes: Sequence[str]) -> List[Dict[str, Any]]:
    out: List[Dict[str, Any]] = []
    seen = set()
    for code in normalize_codes(codes):
        product = await _find_product_by_code(db, code)
        if not _product_is_serial(product):
            continue
        pid = str(product.get("id") or "")
        if pid and pid not in seen:
            seen.add(pid)
            out.append(product)
    return out


def _order_link(
    *, order_id: str, notion_page_id: str, order_number: str, order_date: str,
    client_id: str, company: str,
) -> Dict[str, str]:
    return {
        "order_id": str(order_id or ""),
        "notion_page_id": str(notion_page_id or ""),
        "order_number": str(order_number or ""),
        "order_date": str(order_date or ""),
        "client_id": str(client_id or ""),
        "client_name": str(company or ""),
    }


async def _link_order_to_existing_serial(
    db,
    serial: str,
    *, order_id: str, notion_page_id: str, order_number: str, order_date: str,
    client_id: str, company: str,
) -> bool:
    existing = await db.product_serials.find_one({"serial_lower": serial.casefold()})
    if not existing:
        return False
    link = _order_link(
        order_id=order_id, notion_page_id=notion_page_id, order_number=order_number,
        order_date=order_date, client_id=client_id, company=company,
    )
    update: Dict[str, Any] = {
        "$addToSet": {"notion_order_links": link},
        "$set": {"updated_at": _now()},
    }
    previous_date = str(existing.get("notion_order_date") or "")
    if not previous_date or str(order_date or "") >= previous_date:
        update["$set"].update({
            "notion_order_page_id": notion_page_id,
            "notion_order_id": order_id,
            "notion_order_number": order_number,
            "notion_order_date": order_date,
            "notion_client_id": client_id,
            "notion_client_name": company,
        })
    await db.product_serials.update_one({"_id": existing.get("_id")}, update)
    return True


async def sync_order_wallbox_serials(
    db,
    *,
    codes: Any,
    serials: Any,
    client_id: str,
    order_id: str,
    order_number: str,
    order_date: str,
    company: str,
    notion_page_id: str,
    actor: str = "notion-import",
) -> Dict[str, Any]:
    """R67: durante la lettura Ordini NON inventa più prodotti o movimenti.

    L'Inventario viene importato prima e l'Inventory Tracker dopo. In questa fase
    colleghiamo solo eventuali seriali già esistenti. La riconciliazione definitiva
    viene eseguita da :func:`reconcile_order_wallbox_serials` dopo il Tracker.
    """
    normalized_serials = normalize_serials(serials)
    linked = 0
    for serial in normalized_serials:
        if await _link_order_to_existing_serial(
            db, serial,
            order_id=order_id, notion_page_id=notion_page_id,
            order_number=order_number, order_date=order_date,
            client_id=client_id, company=company,
        ):
            linked += 1
    return {
        "products_created": 0,
        "products_linked": 0,
        "serials_created": 0,
        "serials_linked": linked,
        "movements_created": 0,
        "warnings": [],
        "deferred_to_tracker_reconciliation": True,
    }


def _pick_date(pick: Dict[str, Any]) -> str:
    return str(pick.get("data_uscita") or pick.get("created_at") or "")


async def _load_authoritative_tracker(db) -> Tuple[Dict[str, Dict[str, Any]], List[str]]:
    """Restituisce l'ultima uscita Notion per seriale, mantenendo il prodotto relazionato."""
    products = {str(p.get("id")): p for p in await db.products.find({}).to_list(length=50000)}
    by_serial: Dict[str, Dict[str, Any]] = {}
    warnings: List[str] = []
    rows = await db.local_picks.find({"import_source": "notion"}).to_list(length=100000)
    for row in rows:
        product = products.get(str(row.get("product_id") or ""))
        if not _product_is_serial(product):
            continue
        for serial in normalize_serials(row.get("sn")):
            key = serial.casefold()
            previous = by_serial.get(key)
            if previous and str(previous.get("product_id") or "") != str(row.get("product_id") or ""):
                warnings.append(f"tracker_seriale_{serial}_su_prodotti_diversi")
            if not previous or _pick_date(row) >= _pick_date(previous):
                by_serial[key] = row
    return by_serial, warnings


async def _choose_existing_serial_doc(db, serial: str, target_product_id: str) -> Tuple[Optional[Dict[str, Any]], List[Dict[str, Any]]]:
    docs = await db.product_serials.find({"serial_lower": serial.casefold()}).to_list(length=100)
    if not docs:
        return None, []
    for doc in docs:
        if str(doc.get("product_id") or "") == target_product_id:
            return doc, docs
    # La disponibilità corrente importata dall'Inventario ha priorità su una vecchia
    # associazione storica in conflitto.
    for doc in docs:
        if doc.get("status") == "available":
            return doc, docs
    return docs[0], docs


async def _upsert_reconciled_serial(
    db,
    *, serial: str, target_product: Dict[str, Any], tracker_pick: Optional[Dict[str, Any]],
    order: Dict[str, Any], warnings: List[str],
) -> Tuple[bool, bool, int]:
    """Ritorna (created, moved, duplicates_removed)."""
    pid = str(target_product.get("id") or "")
    chosen, docs = await _choose_existing_serial_doc(db, serial, pid)
    created = False
    moved = False
    removed = 0
    now = _now()

    if chosen and chosen.get("status") == "available" and str(chosen.get("product_id") or "") != pid:
        warnings.append(f"seriale_{serial}_conflitto_inventario_tracker")
        actual = await db.products.find_one({"id": chosen.get("product_id")})
        if _product_is_serial(actual):
            target_product = actual
            pid = str(actual.get("id") or pid)
    elif chosen and str(chosen.get("product_id") or "") != pid:
        await db.product_serials.update_one({"_id": chosen.get("_id")}, {"$set": {"product_id": pid, "updated_at": now}})
        chosen["product_id"] = pid
        moved = True

    if not chosen:
        status = "shipped" if tracker_pick else "assigned"
        doc = {
            "id": str(__import__("uuid").uuid4()),
            "product_id": pid,
            "serial": serial,
            "serial_lower": serial.casefold(),
            "status": status,
            "last_warehouse_id": WAREHOUSE_ELIOS,
            "import_source": "notion_reconciled",
            "created_at": now,
            "updated_at": now,
        }
        await db.product_serials.insert_one(doc)
        chosen = await db.product_serials.find_one({"id": doc["id"]}) or doc
        docs = [chosen]
        created = True

    link = _order_link(
        order_id=str(order.get("id") or ""),
        notion_page_id=str(order.get("notion_page_id") or ""),
        order_number=str(order.get("numero") or ""),
        order_date=str(order.get("data_firma") or order.get("data") or ""),
        client_id=str(order.get("cliente_id") or ""),
        company=str(order.get("_client_name") or ""),
    )
    set_fields: Dict[str, Any] = {"updated_at": now, "reconciled_from_notion": True}
    previous_date = str(chosen.get("notion_order_date") or "")
    if not previous_date or link["order_date"] >= previous_date:
        set_fields.update({
            "notion_order_page_id": link["notion_page_id"],
            "notion_order_id": link["order_id"],
            "notion_order_number": link["order_number"],
            "notion_order_date": link["order_date"],
            "notion_client_id": link["client_id"],
            "notion_client_name": link["client_name"],
        })

    if tracker_pick:
        # Il movimento reale prevale sul semplice dato Ordine.
        if chosen.get("status") != "available":
            set_fields["status"] = "shipped"
        set_fields.update({
            "last_pick_id": str(tracker_pick.get("id") or ""),
            "last_pick_at": tracker_pick.get("created_at") or tracker_pick.get("data_uscita") or "",
            "last_pick_date": tracker_pick.get("data_uscita") or "",
            "last_pick_cliente": tracker_pick.get("cliente") or "",
            "last_pick_taken_by": tracker_pick.get("taken_by") or "",
            "last_warehouse_id": tracker_pick.get("warehouse_id") or WAREHOUSE_ELIOS,
            "tracker_source_id": str(tracker_pick.get("id") or ""),
        })

    await db.product_serials.update_one(
        {"_id": chosen.get("_id")},
        {"$set": set_fields, "$addToSet": {"notion_order_links": link}},
    )

    # Elimina soltanto duplicati creati dalle migrazioni; non tocchiamo record manuali.
    for duplicate in docs:
        if duplicate.get("_id") == chosen.get("_id"):
            continue
        migrated = (
            duplicate.get("source") == "notion_initial_import"
            or duplicate.get("import_source") in {"notion_ordini", "notion_reconciled", "notion"}
        )
        if migrated:
            await db.product_serials.delete_one({"_id": duplicate.get("_id")})
            removed += 1
        else:
            warnings.append(f"seriale_{serial}_duplicato_locale_non_rimosso")
    return created, moved, removed


async def _cleanup_r66_artifacts(db) -> int:
    """Rimuove i placeholder creati da R66 solo quando non sono più referenziati."""
    removed = 0
    # I movimenti `notion_ordini` erano sintetici: la fonte corretta è Inventory Tracker.
    await db.local_picks.delete_many({"import_source": "notion_ordini"})
    placeholders = await db.products.find({"import_source": "notion_ordini", "historical_only": True}).to_list(length=10000)
    for product in placeholders:
        pid = str(product.get("id") or "")
        if not pid:
            continue
        serial_refs = await db.product_serials.count_documents({"product_id": pid})
        pick_refs = await db.local_picks.count_documents({"product_id": pid})
        if serial_refs or pick_refs:
            continue
        await db.warehouse_stock.delete_many({"product_id": pid})
        await db.products.delete_one({"id": pid})
        removed += 1
    return removed


async def reconcile_order_wallbox_serials(db, *, actor: str = "notion-import") -> Dict[str, Any]:
    """Riconcilia le tre fonti Notion in ordine di autorità.

    1. Inventario: anagrafica prodotto + seriali attualmente disponibili.
    2. Inventory Tracker: storico reale delle uscite e relazione seriale/prodotto.
    3. Eliostech Ordini: cliente/ordine e integrazione solo dei seriali non risolvibili sopra.

    Non viene più assegnato un seriale "al primo codice". Se il modello resta ambiguo,
    il seriale rimane nell'ordine ma non viene inventata una voce di magazzino.
    """
    tracker, warnings = await _load_authoritative_tracker(db)
    clients = {str(c.get("id")): str(c.get("ragione_sociale") or c.get("nome_struttura") or "")
               for c in await db.crm_clienti.find({}).to_list(length=50000)}
    orders = await db.crm_ordini_clienti.find({"import_source": {"$in": ["notion", "notion_storico"]}}).to_list(length=100000)

    stats: Dict[str, Any] = {
        "products_created": 0,
        "products_linked": 0,
        "serials_created": 0,
        "serials_linked": 0,
        "serials_moved_to_authoritative_product": 0,
        "duplicate_serial_records_removed": 0,
        "movements_created": 0,
        "tracker_serials_used": 0,
        "order_only_serials_resolved": 0,
        "unresolved_serials": [],
        "quantity_serial_mismatches": [],
        "duplicate_order_serials": [],
        "placeholder_products_removed": 0,
        "warnings": warnings,
    }

    serial_usage: Dict[str, List[str]] = {}
    for order in orders:
        for serial in normalize_serials(order.get("sn_wb")):
            serial_usage.setdefault(serial.casefold(), []).append(str(order.get("numero") or order.get("id") or ""))
    for key, refs in serial_usage.items():
        unique_refs = list(dict.fromkeys(refs))
        if len(unique_refs) > 1:
            stats["duplicate_order_serials"].append({"serial": key, "orders": unique_refs})

    for order in orders:
        order["_client_name"] = clients.get(str(order.get("cliente_id") or ""), "")
        serials = normalize_serials(order.get("sn_wb"))
        codes = normalize_codes(order.get("prodotti_notion"))
        candidates = await _serial_products_for_codes(db, codes)
        qty_raw = order.get("qty_wb")
        try:
            qty = int(float(qty_raw)) if qty_raw not in (None, "") else 0
        except Exception:
            qty = 0
        if qty and len(serials) != qty:
            stats["quantity_serial_mismatches"].append({
                "order": str(order.get("numero") or order.get("id") or ""),
                "qty_wb": qty,
                "serial_count": len(serials),
            })

        for idx, serial in enumerate(serials):
            key = serial.casefold()
            tracker_pick = tracker.get(key)
            target: Optional[Dict[str, Any]] = None
            source = ""
            if tracker_pick and tracker_pick.get("product_id"):
                target = await db.products.find_one({"id": tracker_pick.get("product_id")})
                if _product_is_serial(target):
                    source = "tracker"
                    stats["tracker_serials_used"] += 1
                else:
                    target = None

            if target is None:
                existing_docs = await db.product_serials.find({"serial_lower": key}).to_list(length=100)
                available = next((d for d in existing_docs if d.get("status") == "available"), None)
                if available:
                    product = await db.products.find_one({"id": available.get("product_id")})
                    if _product_is_serial(product):
                        target = product
                        source = "inventory"

            if target is None and len(candidates) == 1:
                target = candidates[0]
                source = "order_exact_product"
            elif target is None and len(candidates) == len(serials) and len(candidates) > 1:
                target = candidates[idx]
                source = "order_position"
                stats["warnings"].append(f"ordine_{order.get('numero')}_abbinamento_per_posizione")

            if target is None:
                # Se il solo record esistente è un artefatto R66, lo rimuoviamo: meglio
                # un seriale visibile nell'Ordine ma non associato che un modello sbagliato.
                stale = await db.product_serials.find({"serial_lower": key, "import_source": "notion_ordini"}).to_list(length=100)
                for doc in stale:
                    await db.product_serials.delete_one({"_id": doc.get("_id")})
                stats["unresolved_serials"].append({
                    "serial": serial,
                    "order": str(order.get("numero") or order.get("id") or ""),
                    "codes": codes,
                })
                continue

            created, moved, removed = await _upsert_reconciled_serial(
                db,
                serial=serial,
                target_product=target,
                tracker_pick=tracker_pick,
                order=order,
                warnings=stats["warnings"],
            )
            stats["serials_created"] += int(created)
            stats["serials_moved_to_authoritative_product"] += int(moved)
            stats["duplicate_serial_records_removed"] += int(removed)
            stats["serials_linked"] += 1
            stats["products_linked"] += 1
            if source != "tracker":
                stats["order_only_serials_resolved"] += 1

    stats["placeholder_products_removed"] = await _cleanup_r66_artifacts(db)
    # Mantieni la risposta leggibile anche con archivi molto grandi.
    stats["warnings"] = list(dict.fromkeys(stats["warnings"]))[:100]
    stats["unresolved_serials"] = stats["unresolved_serials"][:200]
    stats["quantity_serial_mismatches"] = stats["quantity_serial_mismatches"][:200]
    stats["duplicate_order_serials"] = stats["duplicate_order_serials"][:200]
    return stats
