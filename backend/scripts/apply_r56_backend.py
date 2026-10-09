from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: Path, changes):
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new, label in changes:
        if old not in text:
            if new in text:
                continue
            raise RuntimeError(f"R56 backend patch: blocco non trovato: {label}")
        text = text.replace(old, new, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"[R56 backend] aggiornato {path.name}")
    else:
        print(f"[R56 backend] {path.name} gia aggiornato")


# Calendario: gli eventi Lead NON devono entrare nella migrazione locale.
calendar = ROOT / "routes" / "calendar_routes.py"
patch(calendar, [
    (
        'stats: Dict[str, Any] = {"calendars": 0, "parsed": 0, "imported": 0, "updated": 0, "skipped_cancelled": 0, "linked_clients": 0, "errors": [], "per_calendar": []}; clients_cache = await db.crm_clienti.find({}).to_list(length=10000)',
        'stats: Dict[str, Any] = {"calendars": 0, "parsed": 0, "imported": 0, "updated": 0, "skipped_cancelled": 0, "skipped_leads": 0, "linked_clients": 0, "errors": [], "per_calendar": []}; clients_cache = await db.crm_clienti.find({}).to_list(length=10000)  # R56_CALENDAR_FILTERS',
        "calendar stats",
    ),
    (
        '                if str(source.get("status") or "").upper() == "CANCELLED": stats["skipped_cancelled"] += 1; continue\n                if not source.get("dtstart") or not source.get("uid"): continue\n                title = source.get("summary") or "Senza titolo"; start = source.get("dtstart"); end = source.get("dtend") or (_parse_dt(start) + (timedelta(days=1) if source.get("all_day") else timedelta(hours=1))).isoformat(); import_key = f"{source.get(\'uid\')}|{source.get(\'recurrence_id\') or \'\'}|{resource.get(\'id\')}"',
        '                if str(source.get("status") or "").upper() == "CANCELLED": stats["skipped_cancelled"] += 1; continue\n                lead_text = _norm(f"{name} {source.get(\'summary\') or \'\'} {source.get(\'description\') or \'\'}")\n                if re.search(r"(^| )leads?( |$)", lead_text): stats["skipped_leads"] += 1; continue\n                if not source.get("dtstart") or not source.get("uid"): continue\n                title = source.get("summary") or "Senza titolo"; start = source.get("dtstart"); end = source.get("dtend") or (_parse_dt(start) + (timedelta(days=1) if source.get("all_day") else timedelta(hours=1))).isoformat(); import_key = f"{source.get(\'uid\')}|{source.get(\'recurrence_id\') or \'\'}|{resource.get(\'id\')}"',
        "calendar lead exclusion",
    ),
])


# Notion: importazione finale selettiva. Niente fonti/pagine generiche; riconosci anche Consegne.
admin = ROOT / "routes" / "admin_extra_routes.py"
patch(admin, [
    (
        '            if ("entrate" in low or "arrivi" in low) and not is_verona and "receipts_ds_id" not in picked: picked["receipts_ds_id"]=sid',
        '            if ("entrate" in low or "arrivi" in low or ("consegn" in low and ("entrata" in low or "entrate" in low or "ricev" in low))) and not is_verona and "receipts_ds_id" not in picked: picked["receipts_ds_id"]=sid  # R56_NOTION_SELECTIVE',
        "Elios incoming deliveries autodetect",
    ),
    (
        '            if ("uscite" in low or "tracker" in low or "spedizioni" in low) and not is_verona and "tracker_ds_id" not in picked: picked["tracker_ds_id"]=sid',
        '            if ("uscite" in low or "tracker" in low or "spedizioni" in low or ("consegn" in low and ("uscita" in low or "uscite" in low or "sped" in low))) and not is_verona and "tracker_ds_id" not in picked: picked["tracker_ds_id"]=sid',
        "Elios outgoing deliveries autodetect",
    ),
    (
        '            if ("entrate" in low or "arrivi" in low) and is_verona and "verona_receipts_ds_id" not in picked: picked["verona_receipts_ds_id"]=sid',
        '            if ("entrate" in low or "arrivi" in low or ("consegn" in low and ("entrata" in low or "entrate" in low or "ricev" in low))) and is_verona and "verona_receipts_ds_id" not in picked: picked["verona_receipts_ds_id"]=sid',
        "Verona incoming deliveries autodetect",
    ),
    (
        '            if ("uscite" in low or "tracker" in low or "spedizioni" in low) and is_verona and "verona_tracker_ds_id" not in picked: picked["verona_tracker_ds_id"]=sid',
        '            if ("uscite" in low or "tracker" in low or "spedizioni" in low or ("consegn" in low and ("uscita" in low or "uscite" in low or "sped" in low))) and is_verona and "verona_tracker_ds_id" not in picked: picked["verona_tracker_ds_id"]=sid',
        "Verona outgoing deliveries autodetect",
    ),
    (
        '                    title_parts = src.get("title") or []\n                    title = "".join(str(x.get("plain_text") or "") for x in title_parts).strip() or f"Fonte {ds_id[:8]}"\n                    try:\n                        pages = await _query_notion_source(ds_id)',
        '                    title_parts = src.get("title") or []\n                    title = "".join(str(x.get("plain_text") or "") for x in title_parts).strip() or f"Fonte {ds_id[:8]}"\n                    # R56: importa soltanto le fonti operative esplicitamente riconosciute.\n                    if ds_id not in known_ids:\n                        continue\n                    try:\n                        pages = await _query_notion_source(ds_id)',
        "skip unknown Notion data sources",
    ),
    (
        '                pm=await db.custom_modules.find_one({"migration_role":"workspace_pages"})\n                if not pm:',
        '                # R56: le pagine autonome/generiche del workspace non fanno parte della migrazione operativa.\n                pages_found = []\n                pm={"id":"r56-pages-disabled"}\n                if False and not pm:',
        "disable generic workspace pages",
    ),
])

print("[R56 backend] filtri migrazione applicati.")
