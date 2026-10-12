from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: Path, changes):
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new, label in changes:
        if new in text:
            continue
        if old not in text:
            raise RuntimeError(f"R64 backend patch: blocco non trovato: {label}")
        text = text.replace(old, new, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"[R64 backend] aggiornato {path.name}")


# ---------------------------------------------------------------------------
# Reset totale: cancella TUTTI i dati operativi presenti e futuri.
# Preserva soltanto identità/configurazione del gestionale e log di sistema.
# ---------------------------------------------------------------------------
admin = ROOT / "routes" / "admin_extra_routes.py"
patch(admin, [
    (
        '            "crm_preventivi", "crm_ordini_clienti", "crm_installazioni", "crm_assistenza",\n',
        '            "crm_preventivi", "crm_ordini_clienti", "crm_installazioni", "crm_interventi_tecnici", "crm_assistenza",\n',
        "interventi tecnici nel reset CRM",
    ),
    (
        '    async def _reset_preview():\n',
        '    SYSTEM_PRESERVED_COLLECTIONS = {\n'
        '        "users", "settings", "active_sessions", "audit_logs", "app_events",\n'
        '        "system_logs", "http_logs", "roles", "permissions", "feature_flags",\n'
        '        "schema_migrations", "custom_modules",\n'
        '    }\n\n'
        '    async def _all_operational_collections():\n'
        '        names = await db.list_collection_names()\n'
        '        return sorted(\n'
        '            name for name in names\n'
        '            if name not in SYSTEM_PRESERVED_COLLECTIONS\n'
        '            and not str(name).startswith("system.")\n'
        '        )\n\n'
        '    async def _reset_preview():\n',
        "future proof operational reset helper",
    ),
    (
        '        selected_scopes = list(RESET_GROUPS.keys()) if body.scope == "all" else [body.scope]\n'
        '        before = await _reset_preview()\n'
        '        deleted = {}\n'
        '        for scope in selected_scopes:\n'
        '            for name in RESET_GROUPS[scope]:\n'
        '                res = await db[name].delete_many({})\n'
        '                deleted[name] = int(res.deleted_count)\n\n'
        '        # I contatori sono dati operativi: se si azzera tutto ripartono anche le numerazioni.\n'
        '        if body.scope == "all":\n'
        '            res = await db.counters.delete_many({})\n'
        '            deleted["counters"] = int(res.deleted_count)\n',
        '        selected_scopes = list(RESET_GROUPS.keys()) if body.scope == "all" else [body.scope]\n'
        '        before = await _reset_preview()\n'
        '        deleted = {}\n'
        '        if body.scope == "all":\n'
        '            # Elimina ogni collezione operativa esistente, incluse quelle aggiunte da release future.\n'
        '            # Questo evita che Interventi tecnici, Calendario, report, archivi migrazione o nuovi\n'
        '            # moduli restino fuori dalla cancellazione totale.\n'
        '            for name in await _all_operational_collections():\n'
        '                res = await db[name].delete_many({})\n'
        '                deleted[name] = int(res.deleted_count or 0)\n'
        '        else:\n'
        '            for scope in selected_scopes:\n'
        '                for name in RESET_GROUPS[scope]:\n'
        '                    res = await db[name].delete_many({})\n'
        '                    deleted[name] = int(res.deleted_count or 0)\n\n'
        '        if body.scope == "all":\n'
        '            # Gli stati di sincronizzazione sono operativi. Se una migrazione NON è stata\n'
        '            # finalizzata, il reset la riporta a zero per consentire un nuovo import pulito.\n'
        '            # Una migrazione già finalizzata resta invece irreversibilmente chiusa.\n'
        '            calendar_state = await db.settings.find_one({"_id": "calendar_migration"}) or {}\n'
        '            notion_state = await db.settings.find_one({"_id": "notion_migration"}) or {}\n'
        '            await db.settings.delete_many({"_id": {"$in": [\n'
        '                "calendar_installations_sync", "calendar_operations_sync", "notion_migration_progress"\n'
        '            ]}})\n'
        '            if not calendar_state.get("finalized"):\n'
        '                await db.settings.delete_one({"_id": "calendar_migration"})\n'
        '            if not notion_state.get("finalized"):\n'
        '                await db.settings.delete_one({"_id": "notion_migration"})\n',
        "dynamic full reset",
    ),
    (
        '        # I log restano intenzionalmente: registriamo anche questa azione distruttiva.\n',
        '        if body.scope == "all":\n'
        '            # Elimina anche tutti gli allegati operativi, non soltanto la cartella Documenti.\n'
        '            try:\n'
        '                from pathlib import Path as _Path\n'
        '                uploads_root = _Path("/app/data/uploads")\n'
        '                if uploads_root.exists():\n'
        '                    for child in list(uploads_root.iterdir()):\n'
        '                        if child.is_dir():\n'
        '                            for f in child.rglob("*"):\n'
        '                                if f.is_file(): files_deleted += 1\n'
        '                            shutil.rmtree(child, ignore_errors=True)\n'
        '                        elif child.is_file():\n'
        '                            child.unlink(missing_ok=True); files_deleted += 1\n'
        '                uploads_root.mkdir(parents=True, exist_ok=True)\n'
        '            except Exception as exc:\n'
        '                logging.getLogger(__name__).warning("Pulizia completa allegati incompleta: %s", exc)\n\n'
        '        # I log restano intenzionalmente: registriamo anche questa azione distruttiva.\n',
        "full upload cleanup",
    ),
])


# ---------------------------------------------------------------------------
# Notion: dopo finalizzazione non può più essere riattivato neanche tramite ENV.
# ---------------------------------------------------------------------------
patch(admin, [
    (
        '    async def _apply_saved_notion_config() -> Dict[str, Any]:\n'
        '        doc = await db.settings.find_one({"_id": "notion_config"}) or {}\n',
        '    async def _notion_migration_finalized() -> bool:\n'
        '        state = await db.settings.find_one({"_id": "notion_migration"}) or {}\n'
        '        return bool(state.get("finalized"))\n\n'
        '    async def _ensure_notion_migration_open():\n'
        '        if await _notion_migration_finalized():\n'
        '            raise HTTPException(410, "Migrazione Notion conclusa: integrazione disattivata definitivamente")\n\n'
        '    async def _apply_saved_notion_config() -> Dict[str, Any]:\n'
        '        if await _notion_migration_finalized():\n'
        '            notion_service.configure(token="", inventario_ds_id="", receipts_ds_id="", tracker_ds_id="", ordini_ds_id="")\n'
        '            return {\n'
        '                "token": "", "inventario_ds_id": "", "receipts_ds_id": "", "tracker_ds_id": "",\n'
        '                "ordini_ds_id": "", "verona_inventario_ds_id": "",\n'
        '                "verona_receipts_ds_id": "", "verona_tracker_ds_id": "",\n'
        '            }\n'
        '        doc = await db.settings.find_one({"_id": "notion_config"}) or {}\n',
        "hard disable notion helper",
    ),
    (
        '    async def put_notion_config(body: NotionConfigBody, current_user=Depends(deps.require_admin)):\n'
        '        current = await db.settings.find_one({"_id": "notion_config"}) or {}\n',
        '    async def put_notion_config(body: NotionConfigBody, current_user=Depends(deps.require_admin)):\n'
        '        await _ensure_notion_migration_open()\n'
        '        current = await db.settings.find_one({"_id": "notion_config"}) or {}\n',
        "block notion config after finalize",
    ),
    (
        '    async def test_notion_config(current_user=Depends(deps.require_admin)):\n'
        '        cfg = await _apply_saved_notion_config()\n',
        '    async def test_notion_config(current_user=Depends(deps.require_admin)):\n'
        '        await _ensure_notion_migration_open()\n'
        '        cfg = await _apply_saved_notion_config()\n',
        "block notion test after finalize",
    ),
    (
        '    async def notion_import_preview(current_user=Depends(deps.require_admin)):\n'
        '        cfg = await _apply_saved_notion_config()\n',
        '    async def notion_import_preview(current_user=Depends(deps.require_admin)):\n'
        '        await _ensure_notion_migration_open()\n'
        '        cfg = await _apply_saved_notion_config()\n',
        "block notion preview after finalize",
    ),
    (
        '    async def import_from_notion_preview(current_user=Depends(deps.require_admin)):\n'
        '        plan = await _notion_inventory_plan()\n',
        '    async def import_from_notion_preview(current_user=Depends(deps.require_admin)):\n'
        '        await _ensure_notion_migration_open()\n'
        '        plan = await _notion_inventory_plan()\n',
        "block notion inventory preview after finalize",
    ),
    (
        '    async def import_from_notion(current_user=Depends(deps.require_admin)):\n'
        '        """Importa SOLO Inventario Notion -> Magazzino Elios Tech locale.\n',
        '    async def import_from_notion(current_user=Depends(deps.require_admin)):\n'
        '        await _ensure_notion_migration_open()\n'
        '        """Importa SOLO Inventario Notion -> Magazzino Elios Tech locale.\n',
        "block notion inventory import after finalize",
    ),
    (
        '    async def start_notion_import(background_tasks: BackgroundTasks, current_user=Depends(deps.require_admin)):\n'
        '        progress = await db.settings.find_one({"_id": "notion_migration_progress"}) or {}\n',
        '    async def start_notion_import(background_tasks: BackgroundTasks, current_user=Depends(deps.require_admin)):\n'
        '        await _ensure_notion_migration_open()\n'
        '        progress = await db.settings.find_one({"_id": "notion_migration_progress"}) or {}\n',
        "block notion background start after finalize",
    ),
    (
        '    async def import_all_from_notion(current_user=Depends(deps.require_admin)):\n'
        '        """Migrazione una tantum completa Notion -> gestionale locale.\n',
        '    async def import_all_from_notion(current_user=Depends(deps.require_admin)):\n'
        '        await _ensure_notion_migration_open()\n'
        '        """Migrazione una tantum completa Notion -> gestionale locale.\n',
        "block notion full import after finalize",
    ),
    (
        '        await db.settings.update_one({"_id":"notion_migration"},{"$set":{"finalized":True,"finalized_at":now,"completed_at":now}},upsert=True)\n'
        '        await db.settings.delete_one({"_id":"notion_config"})\n',
        '        await db.settings.update_one({"_id":"notion_migration"},{"$set":{\n'
        '            "finalized":True,"finalized_at":now,"completed_at":now,"ready_to_finalize":False,\n'
        '            "integration_enabled":False,"credentials_removed":True,"provider":"local"\n'
        '        }},upsert=True)\n'
        '        await db.settings.delete_one({"_id":"notion_config"})\n'
        '        await db.settings.delete_one({"_id":"notion_migration_progress"})\n',
        "final notion state",
    ),
])


# Startup: finalized Notion overrides old environment variables too.
server = ROOT / "server.py"
patch(server, [
    (
        '        notion_cfg = await db.settings.find_one({"_id": "notion_config"}) or {}\n'
        '        if notion_cfg:\n',
        '        notion_migration = await db.settings.find_one({"_id": "notion_migration"}) or {}\n'
        '        notion_finalized = bool(notion_migration.get("finalized"))\n'
        '        notion_cfg = {} if notion_finalized else (await db.settings.find_one({"_id": "notion_config"}) or {})\n'
        '        if notion_finalized:\n'
        '            notion_service.configure(token="", inventario_ds_id="", receipts_ds_id="", tracker_ds_id="", ordini_ds_id="")\n'
        '            logger.info("Notion migration finalized: external integration forced OFF")\n'
        '        if notion_cfg:\n',
        "startup notion hard off",
    ),
])


# ---------------------------------------------------------------------------
# Calendar/Google export: finalizzazione locale esplicita e irreversibile.
# ---------------------------------------------------------------------------
calendar = ROOT / "routes" / "calendar_routes.py"
patch(calendar, [
    (
        'await db.settings.update_one({"_id": "calendar_migration"}, {"$set": {"completed": True, "ready_to_finalize": False, "finalized": True, "finalized_at": now}}, upsert=True); await db.audit_logs.insert_one',
        'await db.settings.update_one({"_id": "calendar_migration"}, {"$set": {"completed": True, "ready_to_finalize": False, "finalized": True, "finalized_at": now, "imports_enabled": False, "external_sync_enabled": False, "provider": "local"}}, upsert=True); await db.settings.delete_many({"_id": {"$in": ["google_calendar_config", "calendar_google_config", "google_calendar", "calendar_integration"]}}); await db.audit_logs.insert_one',
        "calendar final state",
    ),
])

print("[R64 backend] reset totale completo e integrazioni Notion/Calendar finalizzabili in modo irreversibile.")
