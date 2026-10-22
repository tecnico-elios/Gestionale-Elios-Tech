from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re
import uuid

from calendar_installation_parser import parse_calendar_installation
from calendar_installation_sync import sync_calendar_event_to_installation

INSTALLATION_PEOPLE = {"enrico", "riccardo"}
TECHNICAL_PEOPLE = {"riccardo"}
ASSISTANCE_PEOPLE = {"ivan"}


def _norm(value: Any) -> str:
    value = str(value or "").casefold()
    value = re.sub(r"[^a-z0-9àèéìòù]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _person_matches(value: Any, allowed: set[str]) -> bool:
    text = _norm(value)
    if not text:
        return False
    tokens = set(text.split())
    return bool(tokens & allowed) or any(text.startswith(f"{name} ") or text == name for name in allowed)


def _event_text(event: Dict[str, Any]) -> str:
    return _norm(" ".join(str(event.get(k) or "") for k in ("title", "description", "category")))


def _is_installation(event: Dict[str, Any]) -> bool:
    text = _event_text(event)
    return "installaz" in text


def _is_assistance(event: Dict[str, Any]) -> bool:
    category = _norm(event.get("category"))
    text = _event_text(event)
    # L'importatore classifica già come Assistenza anche gli eventi con
    # "intervento", "config" o "onboarding"; manteniamo quindi quel criterio.
    return category == "assistenza" or "assistenza" in text


def _is_technical(event: Dict[str, Any]) -> bool:
    if _is_assistance(event):
        return True
    text = _event_text(event)
    return any(token in text for token in (
        "intervento tecnico", "intervento", "tecnico", "configur", "onboarding",
        "attivazione", "avviamento", "collaudo", "manutenzione",
    ))


def _event_resource_names(event: Dict[str, Any], resources: List[Dict[str, Any]]) -> List[str]:
    wanted = {str(x) for x in (event.get("resource_ids") or []) if x}
    return [str(r.get("name") or "") for r in resources if str(r.get("id") or "") in wanted]


def _event_person_hints(event: Dict[str, Any], resources: List[Dict[str, Any]]) -> List[str]:
    hints = list(_event_resource_names(event, resources))
    for key in (
        "resource_name", "source_calendar", "source_calendar_name", "source_google_name",
        "calendar_name", "source_name", "source_file", "import_calendar",
    ):
        value = str(event.get(key) or "").strip()
        if value:
            hints.append(value)
    return hints


def _event_has_person(event: Dict[str, Any], resources: List[Dict[str, Any]], allowed: set[str]) -> bool:
    return any(_person_matches(name, allowed) for name in _event_person_hints(event, resources))


def _event_primary_person(event: Dict[str, Any], resources: List[Dict[str, Any]]) -> str:
    hints = _event_person_hints(event, resources)
    return hints[0] if hints else ""


def _parse_event_dt(value: Any) -> Optional[datetime]:
    try:
        dt = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except Exception:
        return None


def _time_state(event: Dict[str, Any], future: str, past: str) -> str:
    when = _parse_event_dt(event.get("end") or event.get("start"))
    if not when:
        return future
    return past if when.astimezone(timezone.utc) < datetime.now(timezone.utc) else future


def _common_payload(event: Dict[str, Any], technician: str) -> Dict[str, Any]:
    parsed = parse_calendar_installation(event.get("title"), event.get("description"), event.get("location"))
    start = _parse_event_dt(event.get("start"))
    return {
        "calendar_event_id": str(event.get("id") or ""),
        "calendar_title": parsed.get("title") or str(event.get("title") or "Attività"),
        "data": start.date().isoformat() if start else str(event.get("start") or "")[:10],
        "ora": start.strftime("%H:%M") if start else "",
        "tecnico": technician,
        "nominativo": parsed.get("structure") or parsed.get("title") or str(event.get("title") or "Attività"),
        "indirizzo_libero": parsed.get("address") or str(event.get("location") or ""),
        "comune_libero": parsed.get("comune") or "",
        "provincia_libera": parsed.get("provincia") or "",
        "cap_libero": parsed.get("cap") or "",
        "referente": parsed.get("referente") or "",
        "telefono": parsed.get("telefono") or "",
        "descrizione_importata": parsed.get("clean_description") or "",
        "descrizione": parsed.get("instructions") or parsed.get("clean_description") or "",
        "note_tecniche": parsed.get("technical_notes") or "",
        "updated_at": datetime.now(timezone.utc),
    }


async def _normalize_allowed_installation(db, event: Dict[str, Any], actor: str, resources: List[Dict[str, Any]]) -> Optional[str]:
    result = await sync_calendar_event_to_installation(db, event, actor=actor, resources_cache=resources)
    installation_id = result.get("installation_id")
    if not installation_id:
        existing = await db.crm_installazioni.find_one({"calendar_event_id": str(event.get("id") or "")})
        installation_id = str((existing or {}).get("id") or "") or None
    if not installation_id:
        return None

    technician = _event_primary_person(event, resources)
    payload = _common_payload(event, technician)
    parsed = parse_calendar_installation(event.get("title"), event.get("description"), event.get("location"))
    payload.update({
        "calendar_source": "calendar_events",
        "import_source": "calendar",
        "istruzioni_intervento": parsed.get("instructions") or parsed.get("clean_description") or "",
        "note": parsed.get("technical_notes") or parsed.get("instructions") or "",
        "prodotti_da_installare": parsed.get("products") or [],
        "prodotti_testo_importato": parsed.get("products_text") or "",
        "agente": parsed.get("agent") or "",
    })
    await db.crm_installazioni.update_one({"id": installation_id}, {"$set": payload})
    return installation_id


async def _upsert_technical(db, event: Dict[str, Any], actor: str, resources: List[Dict[str, Any]]) -> str:
    event_id = str(event.get("id") or "")
    technician = _event_primary_person(event, resources) or "RICCARDO"
    payload = _common_payload(event, technician)
    payload.update({
        "titolo": payload.get("calendar_title"),
        "stato": _time_state(event, "Programmato", "Eseguito"),
        "import_source": "calendar-riccardo",
        "updated_by": actor,
    })
    existing = await db.crm_interventi_tecnici.find_one({"calendar_event_id": event_id})
    if existing and existing.get("manual_override"):
        return str(existing.get("id"))
    if existing:
        await db.crm_interventi_tecnici.update_one({"id": existing.get("id")}, {"$set": payload})
        return str(existing.get("id"))
    record_id = str(uuid.uuid4())
    payload.update({"id": record_id, "created_at": datetime.now(timezone.utc), "created_by": actor})
    await db.crm_interventi_tecnici.insert_one(payload)
    return record_id


async def _upsert_assistance(db, event: Dict[str, Any], actor: str, resources: List[Dict[str, Any]]) -> str:
    event_id = str(event.get("id") or "")
    technician = _event_primary_person(event, resources) or "IVAN"
    payload = _common_payload(event, technician)
    payload.update({
        "numero": f"CAL-{event_id[:8].upper()}",
        "tipo": "In loco" if payload.get("indirizzo_libero") else "Remota",
        "priorita": "Normale",
        "stato": _time_state(event, "Programmata", "Completata"),
        "import_source": "calendar-ivan",
        "updated_by": actor,
    })
    existing = await db.crm_assistenza.find_one({"calendar_event_id": event_id})
    if existing:
        assistance_id = str(existing.get("id"))
        await db.crm_assistenza.update_one({"id": assistance_id}, {"$set": payload})
    else:
        assistance_id = str(uuid.uuid4())
        payload.update({"id": assistance_id, "created_at": datetime.now(timezone.utc), "created_by": actor})
        await db.crm_assistenza.insert_one(payload)
    await db.calendar_events.update_one(
        {"id": event_id},
        {"$set": {"shadow_source_key": f"assistenza:{assistance_id}", "calendar_assistance_synced_at": datetime.now(timezone.utc)}},
    )
    return assistance_id


async def sync_calendar_event_operations(db, event: Dict[str, Any], actor: str = "calendar-operations", resources: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
    resources = resources if resources is not None else await db.calendar_resources.find({"active": {"$ne": False}}).to_list(length=2000)
    event_id = str(event.get("id") or "")
    if not event_id:
        return {"event_id": "", "installation": "skipped", "technical": "skipped", "assistance": "skipped"}

    is_installation = _is_installation(event)
    is_technical = _is_technical(event) and not is_installation
    is_assistance = _is_assistance(event) and not is_installation
    allowed_installation = is_installation and _event_has_person(event, resources, INSTALLATION_PEOPLE)
    riccardo_technical = is_technical and _event_has_person(event, resources, TECHNICAL_PEOPLE) and not bool(event.get("technical_sync_excluded"))
    ivan_assistance = is_assistance and _event_has_person(event, resources, ASSISTANCE_PEOPLE)

    result: Dict[str, Any] = {"event_id": event_id, "installation": "skipped", "technical": "skipped", "assistance": "skipped"}

    if allowed_installation:
        iid = await _normalize_allowed_installation(db, event, actor, resources)
        result["installation"] = "synced" if iid else "skipped"
    else:
        deleted = await db.crm_installazioni.delete_many({
            "calendar_event_id": event_id,
            "$or": [{"calendar_source": "calendar_events"}, {"import_source": {"$regex": "^calendar"}}],
        })
        if deleted.deleted_count:
            result["installation"] = "removed"

    if riccardo_technical:
        await _upsert_technical(db, event, actor, resources)
        result["technical"] = "synced"
    else:
        deleted = await db.crm_interventi_tecnici.delete_many({"calendar_event_id": event_id, "import_source": "calendar-riccardo"})
        if deleted.deleted_count:
            result["technical"] = "removed"

    if ivan_assistance:
        await _upsert_assistance(db, event, actor, resources)
        result["assistance"] = "synced"
    else:
        deleted = await db.crm_assistenza.delete_many({"calendar_event_id": event_id, "import_source": "calendar-ivan"})
        if deleted.deleted_count:
            result["assistance"] = "removed"

    return result


async def sync_all_calendar_operations(db, actor: str = "calendar-operations") -> Dict[str, Any]:
    resources = await db.calendar_resources.find({"active": {"$ne": False}}).to_list(length=2000)
    events = await db.calendar_events.find({}).sort("start", 1).to_list(length=50000)
    stats = {
        "checked": len(events),
        "installations_synced": 0,
        "installations_removed": 0,
        "technical_synced": 0,
        "technical_removed": 0,
        "assistance_synced": 0,
        "assistance_removed": 0,
        "errors": [],
    }
    event_ids = set()
    for event in events:
        event_ids.add(str(event.get("id") or ""))
        try:
            result = await sync_calendar_event_operations(db, dict(event), actor=actor, resources=resources)
            for key, prefix in (("installation", "installations"), ("technical", "technical"), ("assistance", "assistance")):
                action = result.get(key)
                if action == "synced":
                    stats[f"{prefix}_synced"] += 1
                elif action == "removed":
                    stats[f"{prefix}_removed"] += 1
        except Exception as exc:
            stats["errors"].append({"event_id": str(event.get("id") or ""), "title": str(event.get("title") or ""), "error": str(exc)})

    # Elimina soltanto record creati dal calendario rimasti orfani; i record manuali restano intatti.
    if event_ids:
        orphan_query = {"calendar_event_id": {"$nin": list(event_ids)}}
        inst_orphans = await db.crm_installazioni.delete_many({"$and": [orphan_query, {"$or": [{"calendar_source": "calendar_events"}, {"import_source": {"$regex": "^calendar"}}]}]})
        tech_orphans = await db.crm_interventi_tecnici.delete_many({"$and": [orphan_query, {"import_source": "calendar-riccardo"}]})
        ass_orphans = await db.crm_assistenza.delete_many({"$and": [orphan_query, {"import_source": "calendar-ivan"}]})
        stats["installations_removed"] += int(inst_orphans.deleted_count or 0)
        stats["technical_removed"] += int(tech_orphans.deleted_count or 0)
        stats["assistance_removed"] += int(ass_orphans.deleted_count or 0)

    await db.settings.update_one(
        {"_id": "calendar_operations_sync"},
        {"$set": {"last_run_at": datetime.now(timezone.utc), "last_result": stats}},
        upsert=True,
    )
    return stats
