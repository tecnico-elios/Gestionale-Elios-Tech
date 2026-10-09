from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: Path, changes):
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new, label in changes:
        if new in text:
            continue
        if old not in text:
            raise RuntimeError(f"R63 backend patch: blocco non trovato: {label}")
        text = text.replace(old, new, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"[R63 backend] aggiornato {path.name}")


crm = ROOT / "routes" / "crm_routes.py"
patch(crm, [
    (
        '    "installazioni": "crm_installazioni",\n    "assistenza": "crm_assistenza",',
        '    "installazioni": "crm_installazioni",\n    "interventi-tecnici": "crm_interventi_tecnici",\n    "assistenza": "crm_assistenza",',
        "resource interventi tecnici",
    ),
    (
        '        if not res.deleted_count:\n            raise HTTPException(404, "Record non trovato")\n        if resource == "preventivi" and previous_revision_id:',
        '        if not res.deleted_count:\n            raise HTTPException(404, "Record non trovato")\n        if resource == "interventi-tecnici" and existing.get("calendar_event_id"):\n            await db.calendar_events.update_one(\n                {"id": str(existing.get("calendar_event_id"))},\n                {"$set": {"technical_sync_excluded": True, "technical_sync_excluded_at": datetime.now(timezone.utc), "technical_sync_excluded_by": current.get("username") or current.get("email") or "utente"}},\n            )\n        if resource == "preventivi" and previous_revision_id:',
        "delete imported technical intervention suppression",
    ),
])

ops = ROOT / "calendar_operations_sync.py"
patch(ops, [
    (
        '    riccardo_technical = is_technical and _event_has_person(event, resources, TECHNICAL_PEOPLE)',
        '    riccardo_technical = is_technical and _event_has_person(event, resources, TECHNICAL_PEOPLE) and not bool(event.get("technical_sync_excluded"))',
        "respect technical sync exclusion",
    ),
    (
        '    existing = await db.crm_interventi_tecnici.find_one({"calendar_event_id": event_id})\n    if existing:\n        await db.crm_interventi_tecnici.update_one({"id": existing.get("id")}, {"$set": payload})\n        return str(existing.get("id"))',
        '    existing = await db.crm_interventi_tecnici.find_one({"calendar_event_id": event_id})\n    if existing and existing.get("manual_override"):\n        return str(existing.get("id"))\n    if existing:\n        await db.crm_interventi_tecnici.update_one({"id": existing.get("id")}, {"$set": payload})\n        return str(existing.get("id"))',
        "preserve manual technical edits",
    ),
])

print("[R63 backend] Interventi tecnici modificabili/eliminabili con override persistente.")
