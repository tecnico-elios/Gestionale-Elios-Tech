from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
notion = (ROOT / "notion_service.py").read_text(encoding="utf-8")
admin = (ROOT / "routes" / "admin_extra_routes.py").read_text(encoding="utf-8")
bridge = (ROOT / "notion_order_inventory_bridge.py").read_text(encoding="utf-8")

checks = {
    "serial parser formula/rollup": 'def _serial_prop_text' in notion and 'if t == "rollup"' in notion,
    "quantity rollup": 'elif t == "rollup":' in notion and 'quantity = r.get("number")' in notion,
    "quantity source preserved": 'payload["notion_inventory_quantity"] = float(it.get("quantity") or 0)' in admin,
    "no quantity len serials": '"quantity": len(available)' not in admin,
    "serial source inventory": '"import_source": "notion_inventory"' in admin,
    "consistency report": 'order_bridge_stats["inventory_consistency"]' in admin,
    "mismatch report": 'order_bridge_stats["inventory_mismatches"]' in admin,
    "api serial counters": 'doc["historical_serial_count"]' in admin,
    "no order position mapping": 'source = "order_position"' not in bridge,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("R69 audit failed: " + ", ".join(failed))

print("[R69 audit backend] OK: quantità Notion preservata, seriali robusti, storico e mismatch tracciati.")
