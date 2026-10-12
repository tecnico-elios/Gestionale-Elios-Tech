from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

WAREHOUSE_ELIOS = "elios-tech"
GENERIC_WALLBOX_CODE = "WB-NOTION-STORICO"

_ACCESSORY_HINTS = (
    "MTR", "METER", "PED-", "STAND", "CABLE", "CBL", "RFID", "QUADRO",
    "FUSE", "ADATT", "STAFFA", "RAINCOVER", "HLD-", "FOREX", "POLE",
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
    """Normalizza multi-select Notion, JSON serializzato o stringhe separate da virgola."""
    raw: List[Any] = []
    if isinstance(values, (list, tuple, set)):
        for item in values:
            if isinstance(item, str) and item.strip().startswith("["):
                try:
                    parsed = json.loads(item)
                    if isinstance(parsed, list):
                        raw.extend(parsed)
                        continue
                except Exception:
                    pass
            raw.append(item)
    elif values not in (None, ""):
        text = str(values).strip()
        if text.startswith("["):
            try:
                parsed = json.loads(text)
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
        parts = re.split(r"[,;\n\s]+", str(values or ""))
    out: List[str] = []
    seen = set()
    for value in parts:
        serial = str(value or "").strip().strip("[]\"'")
        if not serial:
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


async def _find_product_by_code(db, code: str) -> Optional[Dict[str, Any]]:
    if not code:
        return None
    return await db.products.find_one({
        "$and": [
            {"code": {"$regex": f"^{re.escape(code)}$", "$options": "i"}},
            {"$or": [{"warehouse_id": WAREHOUSE_ELIOS}, {"warehouse_id": {"$exists": False}}]},
        ]
    })


async def _ensure_product(db, code: str, *, generic: bool = False) -> Tuple[Dict[str, Any], bool]:
    code = code or GENERIC_WALLBOX_CODE
    existing = await _find_product_by_code(db, code)
    now = _now()
    if existing:
        updates: Dict[str, Any] = {"updated_at": now}
        if not existing.get("warehouse_id"):
            updates["warehouse_id"] = WAREHOUSE_ELIOS
        if not existing.get("tipo_gestione"):
            updates["tipo_gestione"] = "a_seriale"
        if updates:
            await db.products.update_one({"id": existing.get("id")}, {"$set": updates})
            existing.update(updates)
        await db.warehouse_stock.update_one(
            {"product_id": existing.get("id"), "warehouse_id": WAREHOUSE_ELIOS},
            {"$setOnInsert": {"quantity": 0, "location": "", "low_stock_threshold": 0, "created_at": now}, "$set": {"updated_at": now}},
            upsert=True,
        )
        return existing, False

    pid = str(uuid.uuid4())
    product = {
        "id": pid,
        "warehouse_id": WAREHOUSE_ELIOS,
        "name": "Wallbox storico da Ordini Elios Tech" if generic else f"Wallbox {code}",
        "code": code,
        "category": "Wallbox",
        "tipo_gestione": "a_seriale",
        "unit": "pz",
        "quantity": 0,
        "active": True,
        "historical_only": True,
        "import_source": "notion_ordini",
        "created_at": now,
        "updated_at": now,
    }
    await db.products.insert_one(product)
    await db.warehouse_stock.update_one(
        {"product_id": pid, "warehouse_id": WAREHOUSE_ELIOS},
        {"$set": {"quantity": 0, "location": "", "low_stock_threshold": 0, "updated_at": now}, "$setOnInsert": {"created_at": now}},
        upsert=True,
    )
    return product, True


async def _resolve_wallbox_products(db, codes: Sequence[str], serial_count: int) -> Tuple[List[Dict[str, Any]], int, List[str]]:
    warnings: List[str] = []
    chosen: List[Dict[str, Any]] = []
    created = 0

    # Prima privilegia prodotti già configurati A Seriale: è la fonte più affidabile.
    existing_by_code: Dict[str, Dict[str, Any]] = {}
    for code in codes:
        prod = await _find_product_by_code(db, code)
        if prod:
            existing_by_code[code.casefold()] = prod
            if prod.get("tipo_gestione") == "a_seriale":
                chosen.append(prod)

    if not chosen:
        wallbox_codes = [code for code in codes if looks_like_wallbox_code(code)]
        if not wallbox_codes and len(codes) == 1:
            wallbox_codes = list(codes)
        for code in wallbox_codes:
            prod = existing_by_code.get(code.casefold())
            if prod is None:
                prod, was_created = await _ensure_product(db, code)
                created += int(was_created)
            elif not prod.get("tipo_gestione"):
                await db.products.update_one({"id": prod.get("id")}, {"$set": {"tipo_gestione": "a_seriale", "updated_at": _now()}})
                prod["tipo_gestione"] = "a_seriale"
            chosen.append(prod)

    # Ordini con SN ma senza codice: non perdiamo il seriale, ma lo separiamo chiaramente.
    if not chosen and serial_count:
        prod, was_created = await _ensure_product(db, GENERIC_WALLBOX_CODE, generic=True)
        chosen = [prod]
        created += int(was_created)
        warnings.append("seriali_senza_codice_wallbox")

    # Deduplica mantenendo l'ordine.
    unique: List[Dict[str, Any]] = []
    seen = set()
    for prod in chosen:
        pid = str(prod.get("id") or "")
        if pid and pid not in seen:
            seen.add(pid)
            unique.append(prod)
    if len(unique) > 1 and serial_count not in (0, len(unique)):
        warnings.append("piu_modelli_wallbox_associazione_seriali_ambigua")
    return unique, created, warnings


def _pick_timestamp(order_date: str) -> str:
    value = str(order_date or "").strip()
    if not value:
        return _now()
    if "T" in value:
        return value
    if re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
        return value + "T12:00:00+00:00"
    return _now()


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
    """Registra nel magazzino storico le wallbox vendute senza alterare la giacenza attuale.

    - prodotti mancanti: creati a quantità zero nel Magazzino Elios;
    - seriali mancanti: creati come `shipped`, quindi NON disponibili a stock;
    - seriali già presenti: non vengono spostati né resi indisponibili; si aggiunge solo lo storico ordine;
    - movimento storico: idempotente in local_picks.
    """
    normalized_codes = normalize_codes(codes)
    normalized_serials = normalize_serials(serials)
    products, products_created, warnings = await _resolve_wallbox_products(db, normalized_codes, len(normalized_serials))

    stats: Dict[str, Any] = {
        "products_created": products_created,
        "products_linked": len(products),
        "serials_created": 0,
        "serials_linked": 0,
        "movements_created": 0,
        "warnings": warnings,
    }
    if not products or not normalized_serials:
        return stats

    now = _now()
    pick_at = _pick_timestamp(order_date)
    for idx, serial in enumerate(normalized_serials):
        if len(products) == len(normalized_serials):
            target_product = products[idx]
        else:
            target_product = products[0]
        pid = str(target_product.get("id") or "")
        existing_serial = await db.product_serials.find_one({"serial_lower": serial.casefold()})

        pick_id = None
        if existing_serial:
            serial_pid = str(existing_serial.get("product_id") or pid)
            if serial_pid != pid:
                # Un seriale già noto localmente ha priorità: mai spostarlo automaticamente.
                pid = serial_pid
                target_product = await db.products.find_one({"id": pid}) or target_product
                stats["warnings"].append(f"seriale_{serial}_gia_associato_altro_prodotto")
            pick_id = str(existing_serial.get("notion_order_pick_id") or existing_serial.get("last_pick_id") or uuid.uuid4())
            history_set = {
                "notion_order_page_id": notion_page_id,
                "notion_order_id": order_id,
                "notion_order_number": order_number,
                "notion_client_id": client_id,
                "notion_client_name": company,
                "notion_order_pick_id": pick_id,
                "import_source_order": "notion_ordini",
                "updated_at": now,
            }
            # Non sovrascrivere uno stato locale più recente (es. seriale rientrato in magazzino).
            if not existing_serial.get("last_pick_at"):
                history_set.update({
                    "last_pick_id": pick_id,
                    "last_pick_at": pick_at,
                    "last_pick_date": order_date,
                    "last_pick_cliente": company,
                    "last_pick_taken_by": "Import Notion",
                    "last_warehouse_id": existing_serial.get("warehouse_id") or existing_serial.get("last_warehouse_id") or WAREHOUSE_ELIOS,
                })
            await db.product_serials.update_one({"_id": existing_serial.get("_id")}, {"$set": history_set})
            stats["serials_linked"] += 1
        else:
            pick_id = str(uuid.uuid4())
            await db.product_serials.insert_one({
                "id": str(uuid.uuid4()),
                "product_id": pid,
                "serial": serial,
                "serial_lower": serial.casefold(),
                "status": "shipped",
                "last_warehouse_id": WAREHOUSE_ELIOS,
                "last_pick_id": pick_id,
                "last_pick_at": pick_at,
                "last_pick_date": order_date,
                "last_pick_cliente": company,
                "last_pick_taken_by": "Import Notion",
                "notion_order_pick_id": pick_id,
                "notion_order_page_id": notion_page_id,
                "notion_order_id": order_id,
                "notion_order_number": order_number,
                "notion_client_id": client_id,
                "notion_client_name": company,
                "import_source": "notion_ordini",
                "created_at": now,
                "updated_at": now,
            })
            stats["serials_created"] += 1

        existing_pick = await db.local_picks.find_one({
            "import_source": "notion_ordini",
            "notion_order_page_id": notion_page_id,
            "sn": serial,
        })
        if not existing_pick:
            await db.local_picks.insert_one({
                "id": pick_id or str(uuid.uuid4()),
                "batch_id": f"notion-order:{notion_page_id}",
                "product_id": pid,
                "product_name": target_product.get("name") or target_product.get("code") or "Wallbox",
                "sn": serial,
                "quantity": 1,
                "cliente": company,
                "client_id": client_id,
                "order_id": order_id,
                "order_number": order_number,
                "taken_by": "Import Notion",
                "data_uscita": order_date,
                "unit": target_product.get("unit") or "pz",
                "warehouse_id": WAREHOUSE_ELIOS,
                "historical": True,
                "import_source": "notion_ordini",
                "notion_order_page_id": notion_page_id,
                "created_at": pick_at,
            })
            stats["movements_created"] += 1

    # Il conteggio del magazzino A Seriale deriva solo da status=available: nessun seriale storico
    # aumenta la giacenza corrente. Manteniamo esplicitamente a zero i placeholder storici.
    for product in products:
        if product.get("historical_only"):
            await db.warehouse_stock.update_one(
                {"product_id": product.get("id"), "warehouse_id": WAREHOUSE_ELIOS},
                {"$set": {"quantity": 0, "updated_at": now}},
                upsert=True,
            )
    return stats
