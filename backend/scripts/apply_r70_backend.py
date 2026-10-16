from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "server.py"
text = path.read_text(encoding="utf-8")
original = text

old_import = "from routes import custom_modules_routes, calendar_routes\n"
new_import = "from routes import custom_modules_routes, calendar_routes, free_reports_routes\n"
if new_import not in text:
    if old_import not in text:
        raise RuntimeError("R70 backend: import routes anchor non trovato")
    text = text.replace(old_import, new_import, 1)

anchor = 'app.include_router(installation_report_routes.build_router(db, auth_deps), prefix="/api")\n'
insert = anchor + 'app.include_router(free_reports_routes.build_router(db, auth_deps), prefix="/api")\n'
if 'free_reports_routes.build_router' not in text:
    if anchor not in text:
        raise RuntimeError("R70 backend: include_router anchor non trovato")
    text = text.replace(anchor, insert, 1)

index_anchor = '        await db.audit_logs.create_index([("at", -1)])\n'
index_insert = index_anchor + '        await db.free_technical_reports.create_index([("updated_at", -1)])\n        await db.free_technical_reports.create_index("created_by")\n'
if 'free_technical_reports.create_index' not in text:
    if index_anchor not in text:
        raise RuntimeError("R70 backend: startup index anchor non trovato")
    text = text.replace(index_anchor, index_insert, 1)

if text != original:
    path.write_text(text, encoding="utf-8")
    print("[R70 backend] server.py aggiornato")
else:
    print("[R70 backend] server.py già aggiornato")
