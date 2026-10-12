from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "admin_extra_routes.py"
text = path.read_text(encoding="utf-8")
original = text


def replace_all(old: str, new: str, label: str) -> int:
    global text
    if new in text and old not in text:
        return 0
    count = text.count(old)
    if count == 0:
        raise RuntimeError(f"R66 backend patch: blocco non trovato: {label}")
    text = text.replace(old, new)
    print(f"[R66 backend] {label}: {count} sostituzioni")
    return count


if "from notion_order_inventory_bridge import sync_order_wallbox_serials" not in text:
    marker = "import secret_store\n"
    if marker not in text:
        raise RuntimeError("R66 backend patch: import secret_store non trovato")
    text = text.replace(marker, marker + "from notion_order_inventory_bridge import sync_order_wallbox_serials\n", 1)

replace_all(
    "        orders_created = orders_updated = 0\n        documents_imported = documents_skipped = document_errors = 0\n",
    "        orders_created = orders_updated = 0\n"
    "        order_bridge_stats = {\"products_created\": 0, \"products_linked\": 0, \"serials_created\": 0, \"serials_linked\": 0, \"movements_created\": 0, \"warnings\": []}\n"
    "        documents_imported = documents_skipped = document_errors = 0\n",
    "inizializzazione statistiche ordini-magazzino",
)

old_order_block = '''                if existing_order:\n                    await db.crm_ordini_clienti.update_one({"id": existing_order["id"]}, {"$set": order_payload})\n                    orders_updated += 1\n                else:\n                    order_payload.update({\n                        "id": str(_uuid.uuid4()),\n                        "created_at": datetime.now(timezone.utc),\n                        "created_by": current_user.get("username"),\n                    })\n                    await db.crm_ordini_clienti.insert_one(order_payload)\n                    orders_created += 1\n'''

new_order_block = old_order_block + '''\n                # R66: Eliostech Ordini alimenta anche lo storico Wallbox/seriali del Magazzino Elios.\n                # I seriali dell'ordine sono storici/assegnati: NON aumentano mai la giacenza disponibile.\n                local_order_id = str(existing_order["id"]) if existing_order else str(order_payload["id"])\n                bridge_result = await sync_order_wallbox_serials(\n                    db,\n                    codes=codes,\n                    serials=serials,\n                    client_id=str(client_id or ""),\n                    order_id=local_order_id,\n                    order_number=str(order_number or ""),\n                    order_date=str(order_date or ""),\n                    company=str(company or ""),\n                    notion_page_id=str(page.get("id") or ""),\n                    actor=str(current_user.get("username") or "notion-import"),\n                )\n                for stat_key in ("products_created", "products_linked", "serials_created", "serials_linked", "movements_created"):\n                    order_bridge_stats[stat_key] += int(bridge_result.get(stat_key) or 0)\n                order_bridge_stats["warnings"].extend(bridge_result.get("warnings") or [])\n'''
replace_all(old_order_block, new_order_block, "sincronizzazione wallbox e seriali dagli ordini")

replace_all(
    '                "orders_updated": orders_updated,\n                "documents_imported": documents_imported,\n',
    '                "orders_updated": orders_updated,\n                "warehouse_from_orders": order_bridge_stats,\n                "documents_imported": documents_imported,\n',
    "statistiche import magazzino da ordini",
)

if text != original:
    path.write_text(text, encoding="utf-8")
    print("[R66 backend] aggiornato admin_extra_routes.py")
else:
    print("[R66 backend] nessuna modifica necessaria")
