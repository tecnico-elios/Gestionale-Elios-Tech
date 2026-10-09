from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: Path, changes):
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new, label in changes:
        if old not in text:
            if new in text:
                continue
            raise RuntimeError(f"R60 backend patch: blocco non trovato: {label}")
        text = text.replace(old, new, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"[R60 backend] aggiornato {path.name}")


calendar = ROOT / "routes" / "calendar_routes.py"
patch(calendar, [
    (
        "import zipfile\nfrom zoneinfo import ZoneInfo",
        "import zipfile\nfrom zoneinfo import ZoneInfo\nfrom calendar_installation_sync import sync_all_calendar_installations, sync_calendar_event_to_installation",
        "calendar sync import",
    ),
    (
        '        await db.calendar_events.insert_one(doc); return _clean(doc)',
        '        await db.calendar_events.insert_one(doc)\n        if str(doc.get("category") or "").casefold() == "installazione":\n            await sync_calendar_event_to_installation(db, doc, actor=current.get("username") or "calendar")\n            doc = await db.calendar_events.find_one({"id": doc.get("id")}) or doc\n        return _clean(doc)',
        "create event sync",
    ),
    (
        '            if not result.matched_count: raise HTTPException(404, "Evento non trovato")\n            return _clean(await db.calendar_events.find_one({"id": event_id}))',
        '            if not result.matched_count: raise HTTPException(404, "Evento non trovato")\n            fresh = await db.calendar_events.find_one({"id": event_id})\n            if fresh and str(fresh.get("category") or "").casefold() == "installazione":\n                await sync_calendar_event_to_installation(db, fresh, actor=current.get("username") or "calendar")\n                fresh = await db.calendar_events.find_one({"id": event_id}) or fresh\n            return _clean(fresh)',
        "update event sync",
    ),
    (
        '        now = _now(); await db.settings.update_one({"_id": "calendar_migration"}, {"$set": {"completed": True, "ready_to_finalize": True, "finalized": False, "last_import_at": now, "last_result": stats}}, upsert=True); return stats',
        '        sync_stats = await sync_all_calendar_installations(db, actor=current.get("username") or "calendar-import", force=True)\n        stats["installations_sync"] = sync_stats\n        now = _now(); await db.settings.update_one({"_id": "calendar_migration"}, {"$set": {"completed": True, "ready_to_finalize": True, "finalized": False, "last_import_at": now, "last_result": stats}}, upsert=True); return stats',
        "ics import sync",
    ),
    (
        '        return {"checked": len(rows), "linked": linked}',
        '        sync_stats = await sync_all_calendar_installations(db, actor=current.get("username") or "calendar-relink", force=True)\n        return {"checked": len(rows), "linked": linked, "installations_sync": sync_stats}',
        "relink sync",
    ),
    (
        '    @router.post("/migration/finalize")',
        '    @router.post("/sync-installations")\n    async def sync_installations(current=Depends(deps.require_admin)):\n        return await sync_all_calendar_installations(db, actor=current.get("username") or "calendar-admin", force=True)\n\n    @router.post("/migration/finalize")',
        "manual sync endpoint",
    ),
])

crm = ROOT / "routes" / "crm_routes.py"
patch(crm, [
    (
        "import notion_service\n",
        "import notion_service\nfrom calendar_installation_sync import sync_all_calendar_installations\n",
        "crm sync import",
    ),
    (
        '    async def list_records(resource: str, q: Optional[str] = Query(default=None), include_archived: bool = Query(default=False), current=Depends(dep)):\n        c = coll(resource)\n        query = {}',
        '    async def list_records(resource: str, q: Optional[str] = Query(default=None), include_archived: bool = Query(default=False), current=Depends(dep)):\n        c = coll(resource)\n        if resource == "installazioni":\n            await sync_all_calendar_installations(db, actor=current.get("username") or "installazioni", force=False)\n        query = {}',
        "installations list sync",
    ),
    (
        '            for item in items:\n                cid = str(item.get("commessa_id") or "")\n                if not cid:\n                    continue\n                comm = await db.commesse.find_one({"id": cid})\n                if not comm:\n                    continue\n                item["prodotti_da_installare"] = [',
        '            for item in items:\n                cid = str(item.get("commessa_id") or "")\n                comm = await db.commesse.find_one({"id": cid}) if cid else None\n                if comm:\n                    item["prodotti_da_installare"] = [',
        "installation enrichment no commessa",
    ),
    (
        '                item["attivita_da_eseguire"] = [\n                    {"descrizione": x.get("descrizione") or x.get("product_name") or str(x.get("tipo_riga") or "Servizio"), "quantita": x.get("quantity") or x.get("quantita") or 1}\n                    for x in (comm.get("servizi") or [])\n                ]\n                item["istruzioni_intervento"] = item.get("istruzioni_intervento") or comm.get("note") or ""\n                # R15 — dati leggibili per la scheda del tecnico.\n                cliente_id = str(item.get("cliente_id") or comm.get("cliente_id") or "")\n                sede_id = str(item.get("sede_id") or comm.get("sede_id") or "")',
        '                    item["attivita_da_eseguire"] = [\n                        {"descrizione": x.get("descrizione") or x.get("product_name") or str(x.get("tipo_riga") or "Servizio"), "quantita": x.get("quantity") or x.get("quantita") or 1}\n                        for x in (comm.get("servizi") or [])\n                    ]\n                    item["istruzioni_intervento"] = item.get("istruzioni_intervento") or comm.get("note") or ""\n                else:\n                    item.setdefault("prodotti_da_installare", [])\n                    item.setdefault("attivita_da_eseguire", [])\n                # R60 — cliente e sede vengono mostrati anche per installazioni nate dal Calendario, senza commessa.\n                cliente_id = str(item.get("cliente_id") or (comm or {}).get("cliente_id") or "")\n                sede_id = str(item.get("sede_id") or (comm or {}).get("sede_id") or "")',
        "installation enrichment indentation and links",
    ),
    (
        '                item["cliente_nome"] = item.get("cliente_nome") or comm.get("cliente") or "Cliente"',
        '                item["cliente_nome"] = item.get("cliente_nome") or (comm or {}).get("cliente") or item.get("nominativo") or item.get("calendar_title") or "Cliente da collegare"',
        "calendar install client label",
    ),
])

print("[R60 backend] sincronizzazione Calendario → Installazioni applicata.")
