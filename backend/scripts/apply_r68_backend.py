from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
admin_path = ROOT / "routes" / "admin_extra_routes.py"
bridge_path = ROOT / "notion_order_inventory_bridge.py"

admin = admin_path.read_text(encoding="utf-8")
bridge = bridge_path.read_text(encoding="utf-8")
admin_original = admin
bridge_original = bridge

# 1) Non associare mai più seriali e prodotti in base alla posizione del multi-select.
old_position = '''            if target is None and len(candidates) == 1:\n                target = candidates[0]\n                source = "order_exact_product"\n            elif target is None and len(candidates) == len(serials) and len(candidates) > 1:\n                target = candidates[idx]\n                source = "order_position"\n                stats["warnings"].append(f"ordine_{order.get('numero')}_abbinamento_per_posizione")\n'''
new_position = '''            if target is None and len(candidates) == 1:\n                target = candidates[0]\n                source = "order_exact_product"\n            elif target is None and len(candidates) > 1:\n                stats["warnings"].append(\n                    f"ordine_{order.get('numero')}_seriale_{serial}_ambiguo_multi_prodotto"\n                )\n'''
if old_position in bridge:
    bridge = bridge.replace(old_position, new_position, 1)
elif 'source = "order_position"' in bridge:
    raise RuntimeError("R68: blocco order_position presente ma non riconosciuto")

# 2) R67 riconciliava prima dello storico ordini. Spostiamo quel blocco alla fine di TUTTO l'import.
start = '        # 3b) R67 - riparazione dei codici lasciati dai vecchi import + riconciliazione\n'
end = '        # 4) Fonti Notion aggiuntive del workspace Elios Tech (storico, Verona, interventi, report)\n'
final_marker = '        await _set_migration_progress(state="running", phase="Verifica e scollegamento"'

if start in admin:
    s = admin.index(start)
    e = admin.index(end, s)
    admin = admin[:s] + admin[e:]

final_block = '''        # R68 - riconciliazione FINALE autorevole, eseguita soltanto dopo che tutte le\n        # fonti Notion sono state importate: Inventario, Tracker, Ordini correnti e Storico.\n        normalized_import_records = 0\n        async for _client in db.crm_clienti.find({"import_source": "notion"}):\n            _before = list(_client.get("codici_prodotto") or [])\n            _after = normalize_codes(_before)\n            if _after != _before:\n                await db.crm_clienti.update_one(\n                    {"id": _client.get("id")},\n                    {"$set": {"codici_prodotto": _after, "updated_at": datetime.now(timezone.utc)}},\n                )\n                normalized_import_records += 1\n        async for _order in db.crm_ordini_clienti.find({"import_source": {"$in": ["notion", "notion_storico"]}}):\n            _before = list(_order.get("prodotti_notion") or [])\n            _after = normalize_codes(_before)\n            if _after != _before:\n                await db.crm_ordini_clienti.update_one(\n                    {"id": _order.get("id")},\n                    {"$set": {"prodotti_notion": _after, "updated_at": datetime.now(timezone.utc)}},\n                )\n                normalized_import_records += 1\n\n        try:\n            order_bridge_stats = await reconcile_order_wallbox_serials(\n                db, actor=str(current_user.get("username") or "notion-import")\n            )\n            order_bridge_stats["normalized_import_records"] = normalized_import_records\n            logger.info(\n                "R68 riconciliazione finale Notion: tracker=%s linked=%s unresolved=%s mismatch=%s duplicates=%s normalized=%s placeholders_removed=%s",\n                order_bridge_stats.get("tracker_serials_used", 0),\n                order_bridge_stats.get("serials_linked", 0),\n                len(order_bridge_stats.get("unresolved_serials") or []),\n                len(order_bridge_stats.get("quantity_serial_mismatches") or []),\n                len(order_bridge_stats.get("duplicate_order_serials") or []),\n                normalized_import_records,\n                order_bridge_stats.get("placeholder_products_removed", 0),\n            )\n        except Exception as exc:\n            logger.exception("R68 riconciliazione finale Notion fallita")\n            raise HTTPException(500, f"Riconciliazione finale Notion fallita: {exc}")\n\n'''

if '# R68 - riconciliazione FINALE autorevole' not in admin:
    pos = admin.find(final_marker)
    if pos < 0:
        raise RuntimeError("R68: punto finale import Notion non trovato")
    admin = admin[:pos] + final_block + admin[pos:]

# 3) Espone nel riepilogo dell'import anche i risultati della riconciliazione.
result_anchor = '            "movements": {"receipts_imported": receipts_imported, "exits_imported": exits_imported},\n'
result_with_reconciliation = result_anchor + '            "order_inventory_reconciliation": order_bridge_stats,\n'
if result_with_reconciliation not in admin:
    if result_anchor not in admin:
        raise RuntimeError("R68: anchor risultato import non trovato")
    admin = admin.replace(result_anchor, result_with_reconciliation, 1)

if admin != admin_original:
    admin_path.write_text(admin, encoding="utf-8")
    print("[R68 backend] admin_extra_routes.py aggiornato")
else:
    print("[R68 backend] admin_extra_routes.py già aggiornato")

if bridge != bridge_original:
    bridge_path.write_text(bridge, encoding="utf-8")
    print("[R68 backend] notion_order_inventory_bridge.py aggiornato")
else:
    print("[R68 backend] notion_order_inventory_bridge.py già aggiornato")
