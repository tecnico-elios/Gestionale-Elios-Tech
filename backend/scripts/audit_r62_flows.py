from pathlib import Path
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for rel in [
    "calendar_operations_sync.py",
    "calendar_installation_parser.py",
    "calendar_installation_sync.py",
    "routes/calendar_routes.py",
    "routes/crm_routes.py",
    "server.py",
]:
    py_compile.compile(str(ROOT / rel), doraise=True)

ops = (ROOT / "calendar_operations_sync.py").read_text(encoding="utf-8")
calendar = (ROOT / "routes" / "calendar_routes.py").read_text(encoding="utf-8")
crm = (ROOT / "routes" / "crm_routes.py").read_text(encoding="utf-8")

for marker in [
    'INSTALLATION_PEOPLE = {"enrico", "riccardo"}',
    'TECHNICAL_PEOPLE = {"riccardo"}',
    'ASSISTANCE_PEOPLE = {"ivan"}',
    "crm_interventi_tecnici",
    "crm_assistenza",
    "sync_all_calendar_operations",
]:
    if marker not in ops:
        raise RuntimeError(f"R62 audit: marker operations mancante: {marker}")
if '"interventi-tecnici": "crm_interventi_tecnici"' not in crm:
    raise RuntimeError("R62 audit: risorsa CRM interventi tecnici non configurata")
for marker in ["sync_calendar_event_operations", 'stats["operations_sync"]', "sync_all_calendar_operations", 'actor=current.get("username") or "calendar-import"']:
    if marker not in calendar:
        raise RuntimeError(f"R62 audit: hook calendario/import mancante: {marker}")

from calendar_operations_sync import _event_has_person, _is_installation
resources = [
    {"id": "r", "name": "RICCARDO"},
    {"id": "e", "name": "ENRICO"},
    {"id": "i", "name": "IVAN"},
]
assert _is_installation({"title": "Installazione Hotel Stendhal", "category": "Installazione"})
assert _event_has_person({"resource_ids": ["r"]}, resources, {"riccardo"})
assert _event_has_person({"resource_ids": ["e"]}, resources, {"enrico", "riccardo"})
assert not _event_has_person({"resource_ids": ["i"]}, resources, {"enrico", "riccardo"})
assert _event_has_person({"resource_ids": ["i"]}, resources, {"ivan"})

print("[R62 audit backend] OK: separazione calendario verificata e riallineamento completo limitato all'importazione.")
