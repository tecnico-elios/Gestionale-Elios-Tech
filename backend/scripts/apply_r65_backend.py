from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch(path: Path, changes):
    text = path.read_text(encoding="utf-8")
    original = text
    for old, new, label in changes:
        if new in text:
            continue
        if old not in text:
            raise RuntimeError(f"R65 backend patch: blocco non trovato: {label}")
        text = text.replace(old, new, 1)
    if text != original:
        path.write_text(text, encoding="utf-8")
        print(f"[R65 backend] aggiornato {path.name}")


calendar = ROOT / "routes" / "calendar_routes.py"
patch(calendar, [
    (
        '        installations, surveys, assistance = await asyncio.gather(synth("Installazione", "crm_installazioni", start, end, resources), synth("Sopralluogo", "crm_sopralluoghi", start, end, resources), synth("Assistenza", "crm_assistenza", start, end, resources)); source_keys = {event.get("key") for event in installations + surveys + assistance}; manual = [event for event in manual if not event.get("shadow_source_key") or event.get("shadow_source_key") not in source_keys]; out = manual + installations + surveys + assistance\n',
        '        installations, surveys, technical, assistance = await asyncio.gather(\n'
        '            synth("Installazione", "crm_installazioni", start, end, resources),\n'
        '            synth("Sopralluogo", "crm_sopralluoghi", start, end, resources),\n'
        '            synth("Intervento tecnico", "crm_interventi_tecnici", start, end, resources),\n'
        '            synth("Assistenza", "crm_assistenza", start, end, resources),\n'
        '        )\n'
        '        # R65: il Calendario deve mantenere l\'evento originale importato da Google.\n'
        '        # Le copie operative (Installazioni/Interventi/Assistenza) vengono mostrate solo\n'
        '        # se non esiste gia il relativo evento locale/importato, evitando duplicati.\n'
        '        shadow_keys = {str(event.get("shadow_source_key") or "") for event in manual if event.get("shadow_source_key")}\n'
        '        manual_ids = {str(event.get("id") or "") for event in manual if event.get("id")}\n'
        '        derived = installations + surveys + technical + assistance\n'
        '        derived = [\n'
        '            event for event in derived\n'
        '            if str(event.get("key") or "") not in shadow_keys\n'
        '            and str((event.get("source_record") or {}).get("calendar_event_id") or "") not in manual_ids\n'
        '        ]\n'
        '        out = manual + derived\n',
        "prefer original calendar events and deduplicate derived activities",
    ),
])

print("[R65 backend] Calendario completo: originali Google mantenuti, derivati senza duplicati, Interventi tecnici inclusi.")
