from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
notion_path = ROOT / "notion_service.py"
admin_path = ROOT / "routes" / "admin_extra_routes.py"

notion = notion_path.read_text(encoding="utf-8")
admin = admin_path.read_text(encoding="utf-8")
notion_original = notion
admin_original = admin


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if new in text and old not in text:
        print(f"[R69] {label}: già applicato")
        return text
    count = text.count(old)
    if count != 1:
        raise RuntimeError(f"R69 {label}: atteso 1 blocco, trovati {count}")
    print(f"[R69] {label}: OK")
    return text.replace(old, new, 1)


# 1) Seriali Inventario: supporta rich_text/title ma anche formula, rollup e multi_select.
old_serial_parse = '''    sn_prop = _get_prop(props, "SN /codice", "SN / CODICI", "SN /CODICI", "SN/codice")\n    serials_list = _parse_serials(_plain_text(sn_prop)) if sn_prop else []\n'''
new_serial_parse = '''    sn_prop = _get_prop(props, "SN /codice", "SN / CODICI", "SN /CODICI", "SN/codice", "SN")\n\n    def _serial_prop_text(prop: Optional[Dict[str, Any]]) -> str:\n        if not prop:\n            return ""\n        t = prop.get("type")\n        if t in ("title", "rich_text"):\n            return _plain_text(prop)\n        if t == "formula":\n            f = prop.get("formula") or {}\n            value = f.get(f.get("type")) if f.get("type") else None\n            return str(value or "")\n        if t == "rollup":\n            r = prop.get("rollup") or {}\n            if r.get("type") == "array":\n                values = []\n                for item in r.get("array") or []:\n                    if isinstance(item, dict):\n                        val = _prop_value(item)\n                        if isinstance(val, list):\n                            values.extend(str(x) for x in val if x)\n                        elif val not in (None, ""):\n                            values.append(str(val))\n                return "\\n".join(values)\n            value = r.get(r.get("type")) if r.get("type") else None\n            return str(value or "")\n        if t == "multi_select":\n            return "\\n".join(x.get("name") for x in (prop.get("multi_select") or []) if x.get("name"))\n        value = _prop_value(prop)\n        if isinstance(value, list):\n            return "\\n".join(str(x) for x in value if x)\n        return str(value or "")\n\n    serials_list = _parse_serials(_serial_prop_text(sn_prop)) if sn_prop else []\n'''
notion = replace_once(notion, old_serial_parse, new_serial_parse, "parser seriali Inventario")

# 2) Quantità Inventario: supporta anche rollup numerici.
old_qty = '''        elif t == "formula":\n            f = qty_prop.get("formula", {}) or {}\n            if f.get("type") == "number":\n                quantity = f.get("number")\n'''
new_qty = '''        elif t == "formula":\n            f = qty_prop.get("formula", {}) or {}\n            if f.get("type") == "number":\n                quantity = f.get("number")\n        elif t == "rollup":\n            r = qty_prop.get("rollup", {}) or {}\n            if r.get("type") == "number":\n                quantity = r.get("number")\n'''
notion = replace_once(notion, old_qty, new_qty, "quantità rollup Inventario")

# 3) Durante l'import NON sostituire più la quantità Notion con il numero di seriali letti.
old_payload_qty = '''                if tipo == "a_quantita":\n                    payload["quantity"] = float(it.get("quantity") or 0)\n                elif existing:\n                    payload["quantity"] = existing.get("quantity", 0)\n                else:\n                    payload["quantity"] = 0\n'''
new_payload_qty = '''                # R69: la quantità Notion è autorevole per la giacenza anche per i prodotti\n                # a seriale. Il conteggio seriali è un controllo separato, non deve sovrascriverla.\n                payload["quantity"] = float(it.get("quantity") or 0)\n                payload["notion_inventory_quantity"] = float(it.get("quantity") or 0)\n'''
admin = replace_once(admin, old_payload_qty, new_payload_qty, "quantità prodotti serializzati")

old_force_len = '''                    await db.products.update_one({"id": local_id}, {"$set": {"quantity": len(available)}})\n'''
new_force_len = '''                    await db.products.update_one({"id": local_id}, {"$set": {\n                        "available_serial_count": len(available),\n                        "serial_quantity_mismatch": abs(float(it.get("quantity") or 0) - len(available)) > 0.000001,\n                        "updated_at": _now_iso(),\n                    }})\n'''
admin = replace_once(admin, old_force_len, new_force_len, "non sovrascrivere quantità con seriali")

# 4) Memorizza sui seriali disponibili la provenienza Inventario per distinguere stock e storico.
old_serial_set = '''                                "status": "available",\n                                "updated_at": _now_iso(),\n'''
new_serial_set = '''                                "status": "available",\n                                "warehouse_id": "elios-tech",\n                                "last_warehouse_id": "elios-tech",\n                                "import_source": "notion_inventory",\n                                "updated_at": _now_iso(),\n'''
admin = replace_once(admin, old_serial_set, new_serial_set, "provenienza seriali disponibili")

# 5) A fine import aggiunge un report di coerenza per ogni Wallbox serializzata.
marker = '''            order_bridge_stats["normalized_import_records"] = normalized_import_records\n'''
insert = '''            order_bridge_stats["normalized_import_records"] = normalized_import_records\n            inventory_consistency = []\n            async for _product in db.products.find({\n                "tipo_gestione": "a_seriale",\n                "$or": [\n                    {"warehouse_id": "elios-tech"},\n                    {"warehouse_id": {"$exists": False}},\n                    {"warehouse_id": ""},\n                ],\n            }):\n                _pid = str(_product.get("id") or "")\n                if not _pid:\n                    continue\n                _available = await db.product_serials.count_documents({"product_id": _pid, "status": "available"})\n                _total = await db.product_serials.count_documents({"product_id": _pid})\n                try:\n                    _qty = float(_product.get("notion_inventory_quantity", _product.get("quantity", 0)) or 0)\n                except Exception:\n                    _qty = 0.0\n                _mismatch = abs(_qty - _available) > 0.000001\n                await db.products.update_one({"id": _pid}, {"$set": {\n                    "available_serial_count": _available,\n                    "historical_serial_count": max(0, _total - _available),\n                    "serial_quantity_mismatch": _mismatch,\n                    "updated_at": datetime.now(timezone.utc),\n                }})\n                inventory_consistency.append({\n                    "product_id": _pid,\n                    "code": _product.get("code") or "",\n                    "name": _product.get("name") or "",\n                    "notion_quantity": _qty,\n                    "available_serials": _available,\n                    "historical_serials": max(0, _total - _available),\n                    "mismatch": _mismatch,\n                })\n            order_bridge_stats["inventory_consistency"] = inventory_consistency\n            order_bridge_stats["inventory_mismatches"] = [x for x in inventory_consistency if x.get("mismatch")]\n'''
if 'order_bridge_stats["inventory_consistency"]' not in admin:
    if marker not in admin:
        raise RuntimeError("R69: marker riconciliazione finale non trovato")
    admin = admin.replace(marker, insert, 1)
    print("[R69] report coerenza inventario: OK")

# 6) API prodotti: espone chiaramente quantità Notion, seriali disponibili/storici e mismatch.
old_list = '''                doc["available"] = avail\n                doc["shipped"] = shipped\n'''
new_list = '''                doc["available"] = avail\n                doc["shipped"] = shipped\n                total_serials = await db.product_serials.count_documents({"product_id": doc["id"]})\n                doc["available_serial_count"] = avail\n                doc["historical_serial_count"] = max(0, total_serials - avail)\n                doc["notion_inventory_quantity"] = float(doc.get("notion_inventory_quantity", doc.get("quantity", 0)) or 0)\n                doc["serial_quantity_mismatch"] = abs(doc["notion_inventory_quantity"] - avail) > 0.000001\n'''
admin = replace_once(admin, old_list, new_list, "API dettaglio quantità/seriali")

if notion != notion_original:
    notion_path.write_text(notion, encoding="utf-8")
    print("[R69] notion_service.py aggiornato")
else:
    print("[R69] notion_service.py già aggiornato")

if admin != admin_original:
    admin_path.write_text(admin, encoding="utf-8")
    print("[R69] admin_extra_routes.py aggiornato")
else:
    print("[R69] admin_extra_routes.py già aggiornato")
