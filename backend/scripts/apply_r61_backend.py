from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: Path, changes):
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new, label in changes:
        if new in text:
            continue
        if old not in text:
            raise RuntimeError(f"R61 backend patch: blocco non trovato: {label}")
        text = text.replace(old, new, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"[R61 backend] aggiornato {path.name}")


# ---------------------------------------------------------------------------
# Calendar -> Installazioni: testo leggibile e campi strutturati.
# ---------------------------------------------------------------------------
sync = ROOT / "calendar_installation_sync.py"
patch(sync, [
    (
        "import re\nimport uuid\n",
        "import re\nimport uuid\nfrom calendar_installation_parser import INSTALLATION_NORMALIZATION_VERSION, parse_calendar_installation\n",
        "installation parser import",
    ),
    (
        '    duration = max(15, int((end - start).total_seconds() // 60))\n    client_id, site_id = await _match_client_and_site(db, event, clients_cache, sites_cache)\n    tech_user_id, tech_name = await _resource_assignment(db, event, resources_cache)',
        '    duration = max(15, int((end - start).total_seconds() // 60))\n    parsed = parse_calendar_installation(event.get("title"), event.get("description"), event.get("location"))\n    match_event = dict(event)\n    if parsed.get("structure"):\n        match_event["title"] = f"{event.get(\'title\') or \'\'} {parsed.get(\'structure\')}".strip()\n    if parsed.get("clean_description"):\n        match_event["description"] = parsed.get("clean_description")\n    if parsed.get("address"):\n        match_event["location"] = parsed.get("address")\n    client_id, site_id = await _match_client_and_site(db, match_event, clients_cache, sites_cache)\n    tech_user_id, tech_name = await _resource_assignment(db, event, resources_cache)',
        "parse before matching",
    ),
    (
        '        "calendar_title": str(event.get("title") or "Installazione"),\n        "calendar_source": "calendar_events",',
        '        "calendar_title": parsed.get("title") or str(event.get("title") or "Installazione"),\n        "calendar_source": "calendar_events",\n        "installation_normalization_version": INSTALLATION_NORMALIZATION_VERSION,',
        "normalization marker",
    ),
    (
        '    source_fields = {\n        "data": start.date().isoformat(),\n        "ora": start.strftime("%H:%M"),\n        "durata_prevista": f"{duration} min",\n        "stato": _status(event.get("status"), True),\n        "indirizzo_libero": str(event.get("location") or ""),\n        "istruzioni_intervento": str(event.get("description") or ""),\n        "note": str(event.get("description") or ""),\n        "nominativo": str(event.get("title") or "Installazione"),\n    }',
        '    source_fields = {\n        "data": start.date().isoformat(),\n        "ora": start.strftime("%H:%M"),\n        "durata_prevista": f"{duration} min",\n        "stato": _status(event.get("status"), True),\n        "indirizzo_libero": parsed.get("address") or "",\n        "comune_libero": parsed.get("comune") or "",\n        "provincia_libera": parsed.get("provincia") or "",\n        "cap_libero": parsed.get("cap") or "",\n        "istruzioni_intervento": parsed.get("instructions") or "",\n        "note": parsed.get("technical_notes") or parsed.get("instructions") or "",\n        "descrizione_importata": parsed.get("clean_description") or "",\n        "nominativo": parsed.get("structure") or parsed.get("title") or "Installazione",\n        "referente": parsed.get("referente") or "",\n        "telefono": parsed.get("telefono") or "",\n        "agente": parsed.get("agent") or "",\n        "prodotti_da_installare": parsed.get("products") or [],\n        "prodotti_testo_importato": parsed.get("products_text") or "",\n    }',
        "structured installation fields",
    ),
    (
        '        old_stamp = existing.get("calendar_source_updated_at")\n        source_changed = old_stamp is None or str(source_stamp) != str(old_stamp)\n        if existing.get("import_source") == "calendar" and source_changed:',
        '        old_stamp = existing.get("calendar_source_updated_at")\n        source_changed = old_stamp is None or str(source_stamp) != str(old_stamp)\n        needs_normalization = int(existing.get("installation_normalization_version") or 0) < INSTALLATION_NORMALIZATION_VERSION\n        if existing.get("import_source") == "calendar" and (source_changed or needs_normalization):',
        "renormalize existing calendar imports",
    ),
    (
        '    state = await db.settings.find_one({"_id": "calendar_installations_sync"}) or {}\n    stamps = [str(c.get("updated_at") or c.get("created_at") or "") for c in clients]',
        '    state = await db.settings.find_one({"_id": "calendar_installations_sync"}) or {}\n    normalization_changed = int(state.get("normalization_version") or 0) < INSTALLATION_NORMALIZATION_VERSION\n    if normalization_changed:\n        force = True\n    stamps = [str(c.get("updated_at") or c.get("created_at") or "") for c in clients]',
        "force normalization version",
    ),
    (
        '        "client_revision": client_revision, "client_revision_changed": revision_changed,\n        "errors": [],',
        '        "client_revision": client_revision, "client_revision_changed": revision_changed,\n        "normalization_version": INSTALLATION_NORMALIZATION_VERSION, "normalization_changed": normalization_changed,\n        "errors": [],',
        "normalization stats",
    ),
    (
        '{"$set": {"last_run_at": _now(), "last_result": stats, "client_revision": client_revision}},',
        '{"$set": {"last_run_at": _now(), "last_result": stats, "client_revision": client_revision, "normalization_version": INSTALLATION_NORMALIZATION_VERSION}},',
        "save normalization version",
    ),
])


# ---------------------------------------------------------------------------
# Calendario: ruoli creati una volta, poi soltanto assegnabili.
# ---------------------------------------------------------------------------
calendar = ROOT / "routes" / "calendar_routes.py"
patch(calendar, [
    (
        '        raise HTTPException(403, "Permesso negato: gestione persone e ruoli del calendario")\n\n    async def migration_state()',
        '        raise HTTPException(403, "Permesso negato: gestione persone e ruoli del calendario")\n\n    async def calendar_roles() -> List[str]:\n        doc = await db.settings.find_one({"_id": "calendar_roles"}) or {}\n        saved = [str(x).strip() for x in (doc.get("items") or []) if str(x).strip()]\n        resources = await db.calendar_resources.find({"active": {"$ne": False}}).to_list(length=2000)\n        assigned = [str(x.get("role") or "").strip() for x in resources if str(x.get("role") or "").strip()]\n        seed = ["Amministrazione", "Tecnico", "Commerciale", "Assistenza"]\n        out = []\n        seen = set()\n        for role in saved + assigned + seed:\n            key = role.casefold()\n            if key and key not in seen:\n                seen.add(key); out.append(role[:80])\n        if out != saved:\n            await db.settings.update_one({"_id": "calendar_roles"}, {"$set": {"items": out, "updated_at": _now()}}, upsert=True)\n        return out\n\n    async def validated_calendar_role(value: Any) -> str:\n        role = re.sub(r"\\s+", " ", str(value or "Tecnico").strip())[:80]\n        roles = await calendar_roles()\n        match = next((x for x in roles if x.casefold() == role.casefold()), None)\n        if not match:\n            raise HTTPException(400, "Ruolo non valido. Crealo prima nella gestione Ruoli del calendario.")\n        return match\n\n    async def migration_state()',
        "calendar controlled role helpers",
    ),
    (
        '    @router.get("/integration-state")',
        '    @router.get("/roles")\n    async def list_calendar_roles(current=Depends(deps.require_password_current)):\n        return {"items": await calendar_roles()}\n\n    @router.post("/roles")\n    async def create_calendar_role(body: AnyBody, current=Depends(require_people_role_manager)):\n        name = re.sub(r"\\s+", " ", str(body.model_dump().get("name") or "").strip())[:80]\n        if not name:\n            raise HTTPException(400, "Nome ruolo obbligatorio")\n        roles = await calendar_roles()\n        if any(x.casefold() == name.casefold() for x in roles):\n            return {"items": roles, "created": False}\n        roles.append(name)\n        await db.settings.update_one({"_id": "calendar_roles"}, {"$set": {"items": roles, "updated_at": _now(), "updated_by": current.get("username")}}, upsert=True)\n        return {"items": roles, "created": True}\n\n    @router.delete("/roles/{role_name}")\n    async def delete_calendar_role(role_name: str, current=Depends(require_people_role_manager)):\n        roles = await calendar_roles()\n        target = next((x for x in roles if x.casefold() == role_name.casefold()), None)\n        if not target:\n            raise HTTPException(404, "Ruolo non trovato")\n        if await db.calendar_resources.count_documents({"active": {"$ne": False}, "role": {"$regex": f"^{re.escape(target)}$", "$options": "i"}}):\n            raise HTTPException(409, "Ruolo assegnato a una o più persone: riassegnale prima di eliminarlo")\n        next_roles = [x for x in roles if x.casefold() != target.casefold()]\n        await db.settings.update_one({"_id": "calendar_roles"}, {"$set": {"items": next_roles, "updated_at": _now(), "updated_by": current.get("username")}}, upsert=True)\n        return {"items": next_roles}\n\n    @router.get("/integration-state")',
        "calendar role endpoints",
    ),
    (
        '        now = _now(); doc = {**data, "id": str(uuid.uuid4()), "name": name, "color": data.get("color") or "#64748b", "active": True, "created_at": now, "updated_at": now, "created_by": current.get("username")};',
        '        data["role"] = await validated_calendar_role(data.get("role") or "Tecnico")\n        now = _now(); doc = {**data, "id": str(uuid.uuid4()), "name": name, "color": data.get("color") or "#64748b", "active": True, "created_at": now, "updated_at": now, "created_by": current.get("username")};',
        "validate role on person create",
    ),
    (
        '        data = body.model_dump(); data.pop("id", None); data.pop("source_google_name", None)\n        if "role" in data: data["role"] = _normalize_resource_role(data.get("role"))\n        data["updated_at"] = _now(); result = await db.calendar_resources.update_one({"id": resource_id}, {"$set": data})',
        '        data = body.model_dump(); data.pop("id", None); data.pop("source_google_name", None)\n        if "role" in data:\n            data["role"] = await validated_calendar_role(data.get("role"))\n        data["updated_at"] = _now(); result = await db.calendar_resources.update_one({"id": resource_id}, {"$set": data})',
        "validate role on person update",
    ),
])


# ---------------------------------------------------------------------------
# Notion: avvio rapido + lavoro in background, niente richiesta HTTP da 2 minuti.
# ---------------------------------------------------------------------------
admin = ROOT / "routes" / "admin_extra_routes.py"
patch(admin, [
    (
        "from fastapi import APIRouter, HTTPException, Depends, Query",
        "from fastapi import APIRouter, HTTPException, Depends, Query, BackgroundTasks",
        "background tasks import",
    ),
    (
        '    @router.post("/notion/import-all")\n    async def import_all_from_notion(current_user=Depends(deps.require_admin)):',
        '    async def _run_notion_import_background(actor: Dict[str, Any]):\n        try:\n            result = await import_all_from_notion(current_user=actor)\n            progress = await db.settings.find_one({"_id": "notion_migration_progress"}) or {}\n            await _set_migration_progress(\n                state="completed", phase="Completata", percent=100,\n                processed=progress.get("processed", 0), total=progress.get("total", 0),\n                started_at=progress.get("started_at"), completed_at=datetime.now(timezone.utc),\n                message="Migrazione Notion completata", result=result,\n            )\n        except Exception as exc:\n            logger.exception("Migrazione Notion in background fallita")\n            progress = await db.settings.find_one({"_id": "notion_migration_progress"}) or {}\n            await _set_migration_progress(\n                state="error", phase="Errore", percent=progress.get("percent", 0),\n                processed=progress.get("processed", 0), total=progress.get("total", 0),\n                started_at=progress.get("started_at"), message=str(getattr(exc, "detail", None) or exc)[:500],\n            )\n\n    @router.post("/notion/import-all/start", status_code=202)\n    async def start_notion_import(background_tasks: BackgroundTasks, current_user=Depends(deps.require_admin)):\n        progress = await db.settings.find_one({"_id": "notion_migration_progress"}) or {}\n        if progress.get("state") == "running":\n            updated = progress.get("updated_at")\n            age = None\n            if isinstance(updated, datetime):\n                age = (datetime.now(timezone.utc) - updated).total_seconds()\n            if age is None or age < 600:\n                return {"ok": True, "started": False, "already_running": True}\n        await _set_migration_progress(state="queued", phase="In coda", percent=0, processed=0, total=0, message="Migrazione in avvio")\n        actor = dict(current_user)\n        actor.pop("password_hash", None)\n        background_tasks.add_task(_run_notion_import_background, actor)\n        return {"ok": True, "started": True, "message": "Migrazione avviata sul server"}\n\n    @router.post("/notion/import-all")\n    async def import_all_from_notion(current_user=Depends(deps.require_admin)):',
        "background Notion start route",
    ),
])

print("[R61 backend] ruoli controllati, migrazione resiliente e installazioni leggibili applicati.")
