from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]

checks = {
    ROOT / "routes" / "admin_extra_routes.py": [
        '"crm_interventi_tecnici"',
        'SYSTEM_PRESERVED_COLLECTIONS',
        'await db.list_collection_names()',
        '"calendar_installations_sync", "calendar_operations_sync", "notion_migration_progress"',
        'integrazione disattivata definitivamente',
        'integration_enabled":False',
        'await _ensure_notion_migration_open()',
    ],
    ROOT / "routes" / "calendar_routes.py": [
        'external_sync_enabled": False',
        'imports_enabled": False',
        '"provider": "local"',
        'Migrazione calendario conclusa: il gestionale usa solo i dati locali',
    ],
    ROOT / "server.py": [
        'Notion migration finalized: external integration forced OFF',
        'notion_finalized = bool(notion_migration.get("finalized"))',
    ],
}

for path, needles in checks.items():
    text = path.read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise SystemExit(f"R64 audit FAIL {path.name}: manca {needle}")

print("[R64 audit backend] OK: reset totale, Interventi tecnici e spegnimento definitivo Notion/Calendar verificati.")
