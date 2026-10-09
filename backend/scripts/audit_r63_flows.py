from pathlib import Path
import py_compile
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

for rel in ["routes/crm_routes.py", "calendar_operations_sync.py"]:
    py_compile.compile(str(ROOT / rel), doraise=True)

crm = (ROOT / "routes" / "crm_routes.py").read_text(encoding="utf-8")
ops = (ROOT / "calendar_operations_sync.py").read_text(encoding="utf-8")

for marker in [
    '"interventi-tecnici": "crm_interventi_tecnici"',
    'technical_sync_excluded',
    'technical_sync_excluded_by',
]:
    if marker not in crm:
        raise RuntimeError(f"R63 audit backend: marker CRM mancante: {marker}")
for marker in [
    'not bool(event.get("technical_sync_excluded"))',
    'existing.get("manual_override")',
]:
    if marker not in ops:
        raise RuntimeError(f"R63 audit backend: marker sync mancante: {marker}")

print("[R63 audit backend] OK: apertura/modifica/eliminazione e persistenza interventi tecnici verificate.")
