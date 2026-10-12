from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notion_order_inventory_bridge import normalize_codes, normalize_serials, looks_like_wallbox_code

admin = (ROOT / "routes" / "admin_extra_routes.py").read_text(encoding="utf-8")
bridge = (ROOT / "notion_order_inventory_bridge.py").read_text(encoding="utf-8")

checks = {
    "bridge importato": "from notion_order_inventory_bridge import sync_order_wallbox_serials" in admin,
    "bridge chiamato durante import ordini": "bridge_result = await sync_order_wallbox_serials(" in admin,
    "seriali ordini non disponibili a stock": '"status": "shipped"' in bridge,
    "movimento storico creato": 'db.local_picks.insert_one' in bridge and '"import_source": "notion_ordini"' in bridge,
    "collegamento cliente e ordine": '"notion_client_id"' in bridge and '"notion_order_id"' in bridge,
    "statistiche esposte": '"warehouse_from_orders": order_bridge_stats' in admin,
    "placeholder stock zero": '"quantity": 0' in bridge and 'WAREHOUSE_ELIOS' in bridge,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("R66 audit failed: " + ", ".join(failed))

codes = normalize_codes(['["PPR2-0-2-4-K-002","MTR-3P-65A"]'])
assert codes == ["PPR2-0-2-4-K-002", "MTR-3P-65A"], codes
assert looks_like_wallbox_code(codes[0]) is True
assert looks_like_wallbox_code(codes[1]) is False
assert normalize_serials("1262362, 1262310") == ["1262362", "1262310"]

print("[R66 audit backend] OK: Ordini Eliostech -> Wallbox/seriali storici Magazzino Elios, senza alterare la giacenza.")
