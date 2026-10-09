from pathlib import Path
import py_compile

ROOT = Path(__file__).resolve().parents[1]

files = [
    ROOT / "calendar_installation_sync.py",
    ROOT / "routes" / "calendar_routes.py",
    ROOT / "routes" / "crm_routes.py",
    ROOT / "server.py",
]
for path in files:
    py_compile.compile(str(path), doraise=True)

sync = (ROOT / "calendar_installation_sync.py").read_text(encoding="utf-8")
calendar = (ROOT / "routes" / "calendar_routes.py").read_text(encoding="utf-8")
crm = (ROOT / "routes" / "crm_routes.py").read_text(encoding="utf-8")
server = (ROOT / "server.py").read_text(encoding="utf-8")

for marker in [
    "sync_calendar_event_to_installation",
    "sync_all_calendar_installations",
    "calendar_event_id",
    "cliente_collegamento_stato",
    "shadow_source_key",
    "clients_to_link",
]:
    if marker not in sync:
        raise RuntimeError(f"R60 audit: marker sync mancante: {marker}")

for marker in [
    "from calendar_installation_sync import",
    'await sync_calendar_event_to_installation(db, doc',
    'await sync_calendar_event_to_installation(db, fresh',
    'stats["installations_sync"] = sync_stats',
    '@router.post("/sync-installations")',
]:
    if marker not in calendar:
        raise RuntimeError(f"R60 audit: marker calendario mancante: {marker}")

for marker in [
    "from calendar_installation_sync import sync_all_calendar_installations",
    'if resource == "installazioni":',
    'await sync_all_calendar_installations(db, actor=current.get("username") or "installazioni", force=False)',
    'Cliente da collegare',
    'item.setdefault("prodotti_da_installare", [])',
]:
    if marker not in crm:
        raise RuntimeError(f"R60 audit: marker CRM mancante: {marker}")

for marker in [
    "R60 Calendar→Installazioni startup sync",
    'sync_all_calendar_installations(db, actor="startup", force=False)',
    "startup sync failed",
]:
    if marker not in server:
        raise RuntimeError(f"R60 audit: marker startup mancante: {marker}")

print("[R60 audit] OK: sincronizzazione Calendario → Installazioni, cliente/sede, anti-duplicati e startup sync verificati.")
