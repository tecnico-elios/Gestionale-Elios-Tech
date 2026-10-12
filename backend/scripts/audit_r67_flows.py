from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notion_order_inventory_bridge import (
    canonical_order_code,
    normalize_codes,
    normalize_serials,
)

admin = (ROOT / "routes" / "admin_extra_routes.py").read_text(encoding="utf-8")
bridge = (ROOT / "notion_order_inventory_bridge.py").read_text(encoding="utf-8")

checks = {
    "multi-select ordini correnti": "codes = normalize_codes(codes_val)" in admin,
    "multi-select ordini storici": "codes = normalize_codes(codes_raw)" in admin,
    "vecchio split rimosso": 'str(codes_val).split(",")' not in admin,
    "inventario marcato Elios": '"warehouse_id": "elios-tech"' in admin and '"import_source": "notion_inventory"' in admin,
    "seriale inventario globale": '{"serial_lower": sn.lower()},' in admin,
    "riconciliazione chiamata": "order_bridge_stats = await reconcile_order_wallbox_serials(" in admin,
    "tracker prima della riconciliazione": admin.find('if notion_service.NOTION_TRACKER_DS_ID:') < admin.find("order_bridge_stats = await reconcile_order_wallbox_serials("),
    "nessun prodotto inventato dal bridge ordine": "async def _ensure_product" not in bridge,
    "movimenti sintetici R66 ripuliti": 'delete_many({"import_source": "notion_ordini"})' in bridge,
    "ambigui non assegnati al primo": 'unresolved_serials' in bridge and 'len(candidates) == 1' in bridge,
    "tracker autorevole": 'source = "tracker"' in bridge and 'tracker_serials_used' in bridge,
    "mismatch quantità tracciato": 'quantity_serial_mismatches' in bridge,
    "duplicati ordine tracciati": 'duplicate_order_serials' in bridge,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("R67 audit failed: " + ", ".join(failed))

assert normalize_codes(["MTR-1P-100A", "PPR2-M-2-4-K-002"]) == ["MTR-1P-100A", "PPR2-M-2-4-K-002"]
assert normalize_codes("['MTR-1P-100A', 'PPR2-M-2-4-K-002']") == ["MTR-1P-100A", "PPR2-M-2-4-K-002"]
assert normalize_serials("1426760\n1433687") == ["1426760", "1433687"]
assert canonical_order_code("DAZE-DUO-S-2X22") == "OS01IT64TCP"
assert canonical_order_code("PPR2-0-2-4-K-002") == "PPR2-0-2-4-K-002"

print("[R67 audit backend] OK: Inventario -> Tracker -> Ordini, senza associazioni seriale/prodotto arbitrarie.")
