from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: Path, changes):
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new, label in changes:
        if new in text:
            continue
        if old not in text:
            raise RuntimeError(f"R62 backend patch: blocco non trovato: {label}")
        text = text.replace(old, new, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"[R62 backend] aggiornato {path.name}")


# CRM: nuova raccolta per gli interventi tecnici di Riccardo.
crm = ROOT / "routes" / "crm_routes.py"
patch(crm, [
    (
        '    "installazioni": "crm_installazioni",\n    "assistenza": "crm_assistenza",',
        '    "installazioni": "crm_installazioni",\n    "interventi-tecnici": "crm_interventi_tecnici",\n    "assistenza": "crm_assistenza",',
        "technical interventions CRM resource",
    ),
])


# Calendario: dopo ogni import/variazione sincronizza i tre flussi separati.
calendar = ROOT / "routes" / "calendar_routes.py"
patch(calendar, [
    (
        'from calendar_installation_sync import sync_all_calendar_installations, sync_calendar_event_to_installation',
        'from calendar_installation_sync import sync_all_calendar_installations, sync_calendar_event_to_installation\nfrom calendar_operations_sync import sync_all_calendar_operations, sync_calendar_event_operations',
        "calendar operations imports",
    ),
    (
        '        if str(doc.get("category") or "").casefold() == "installazione":\n            await sync_calendar_event_to_installation(db, doc, actor=current.get("username") or "calendar")\n            doc = await db.calendar_events.find_one({"id": doc.get("id")}) or doc\n        return _clean(doc)',
        '        if str(doc.get("category") or "").casefold() == "installazione":\n            await sync_calendar_event_to_installation(db, doc, actor=current.get("username") or "calendar")\n            doc = await db.calendar_events.find_one({"id": doc.get("id")}) or doc\n        await sync_calendar_event_operations(db, doc, actor=current.get("username") or "calendar")\n        doc = await db.calendar_events.find_one({"id": doc.get("id")}) or doc\n        return _clean(doc)',
        "single event operational sync on create",
    ),
    (
        '            if fresh and str(fresh.get("category") or "").casefold() == "installazione":\n                await sync_calendar_event_to_installation(db, fresh, actor=current.get("username") or "calendar")\n                fresh = await db.calendar_events.find_one({"id": event_id}) or fresh\n            return _clean(fresh)',
        '            if fresh and str(fresh.get("category") or "").casefold() == "installazione":\n                await sync_calendar_event_to_installation(db, fresh, actor=current.get("username") or "calendar")\n                fresh = await db.calendar_events.find_one({"id": event_id}) or fresh\n            if fresh:\n                await sync_calendar_event_operations(db, fresh, actor=current.get("username") or "calendar")\n                fresh = await db.calendar_events.find_one({"id": event_id}) or fresh\n            return _clean(fresh)',
        "single event operational sync on update",
    ),
    (
        '        stats["installations_sync"] = sync_stats\n        now = _now(); await db.settings.update_one({"_id": "calendar_migration"}, {"$set": {"completed": True, "ready_to_finalize": True, "finalized": False, "last_import_at": now, "last_result": stats}}, upsert=True); return stats',
        '        stats["installations_sync"] = sync_stats\n        operations_stats = await sync_all_calendar_operations(db, actor=current.get("username") or "calendar-import")\n        stats["operations_sync"] = operations_stats\n        now = _now(); await db.settings.update_one({"_id": "calendar_migration"}, {"$set": {"completed": True, "ready_to_finalize": True, "finalized": False, "last_import_at": now, "last_result": stats}}, upsert=True); return stats',
        "ICS separated operational sync",
    ),
    (
        '        sync_stats = await sync_all_calendar_installations(db, actor=current.get("username") or "calendar-relink", force=True)\n        return {"checked": len(rows), "linked": linked, "installations_sync": sync_stats}',
        '        sync_stats = await sync_all_calendar_installations(db, actor=current.get("username") or "calendar-relink", force=True)\n        operations_stats = await sync_all_calendar_operations(db, actor=current.get("username") or "calendar-relink")\n        return {"checked": len(rows), "linked": linked, "installations_sync": sync_stats, "operations_sync": operations_stats}',
        "relink separated operational sync",
    ),
])


# Startup: riallinea subito installazioni, interventi tecnici e assistenze importate.
server = ROOT / "server.py"
patch(server, [
    (
        '            sync_stats = await sync_all_calendar_installations(db, actor="startup", force=False)\n            logging.info("R60 Calendar→Installazioni startup sync: %s", sync_stats)',
        '            sync_stats = await sync_all_calendar_installations(db, actor="startup", force=False)\n            logging.info("R60 Calendar→Installazioni startup sync: %s", sync_stats)\n            from calendar_operations_sync import sync_all_calendar_operations\n            operations_stats = await sync_all_calendar_operations(db, actor="startup-r62")\n            logging.info("R62 Calendar operational split startup sync: %s", operations_stats)',
        "startup separated calendar streams",
    ),
])

print("[R62 backend] Installazioni ENRICO/RICCARDO, Interventi tecnici RICCARDO e Assistenza IVAN configurati.")
