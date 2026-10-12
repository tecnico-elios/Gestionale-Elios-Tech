from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from notion_order_inventory_bridge import normalize_codes

admin = (ROOT / "routes" / "admin_extra_routes.py").read_text(encoding="utf-8")
bridge = (ROOT / "notion_order_inventory_bridge.py").read_text(encoding="utf-8")

historical = admin.find("# Storico Ordini 2023/24")
final_reconciliation = admin.find("# R68 - riconciliazione FINALE autorevole")
result_reconciliation = admin.find('"order_inventory_reconciliation": order_bridge_stats')

checks = {
    "nessun abbinamento per posizione": 'source = "order_position"' not in bridge,
    "nessun warning per posizione": "abbinamento_per_posizione" not in bridge,
    "ambigui multi-prodotto segnalati": "ambiguo_multi_prodotto" in bridge,
    "riconciliazione finale presente": final_reconciliation >= 0,
    "riconciliazione dopo storico ordini": historical >= 0 and final_reconciliation > historical,
    "riepilogo riconciliazione esposto": result_reconciliation > final_reconciliation,
    "ordini correnti e storici riconciliati": '"$in": ["notion", "notion_storico"]' in admin,
    "parser codici normalizzato": "normalize_codes(_before)" in admin,
}
failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise SystemExit("R68 audit failed: " + ", ".join(failed))

assert normalize_codes(["['MTR-1P-100A'", " 'PPR2-M-2-4-K-002']"]) == ["MTR-1P-100A", "PPR2-M-2-4-K-002"]

print("[R68 audit backend] OK: riconciliazione eseguita a fine import e nessun abbinamento seriale/prodotto per posizione.")
