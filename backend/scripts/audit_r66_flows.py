from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notion_order_inventory_bridge import normalize_codes, normalize_serials, looks_like_wallbox_code

admin = (ROOT / "routes" / "admin_extra_routes.py").read_text(encoding="utf-8")
bridge = (ROOT / "notion_order_inventory_bridge.py").read_text(encoding="utf-8")

# R67 rende R66 non distruttiva durante la lettura Ordini: il bridge collega soltanto
# seriali già noti e rinvia l'associazione definitiva a dopo Inventory Tracker.
checks = {
    "bridge importato": "from notion_order_inventory_bridge import sync_order_wallbox_serials" in admin,
    "bridge chiamato durante import ordini": "bridge_result = await sync_order_wallbox_serials(" in admin,
    "nessuna creazione prodotto durante ordine": '"products_created": 0' in bridge,
    "riconciliazione prevista": "reconcile_order_wallbox_serials" in bridge,
    "collegamento cliente e ordine": '"notion_client_id"' in bridge and '"notion_order_id"' in bridge,
    "statistiche esposte": '"warehouse_from_orders": order_bridge_stats' in admin,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("R66 audit failed: " + ", ".join(failed))

# Il valore reale di una property Notion multi_select arriva già come lista Python.
codes = normalize_codes(["PPR2-0-2-4-K-002", "MTR-3P-65A"])
assert codes == ["PPR2-0-2-4-K-002", "MTR-3P-65A"], codes
assert looks_like_wallbox_code(codes[0]) is True
assert looks_like_wallbox_code(codes[1]) is False
assert normalize_serials("1262362, 1262310") == ["1262362", "1262310"]

print("[R66 audit backend] OK: bridge Ordini sicuro e riconciliazione differita pronta.")
