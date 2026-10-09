from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo
import re
import uuid

ROME = ZoneInfo("Europe/Rome")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(value: Any) -> str:
    value = str(value or "").casefold()
    value = re.sub(r"[^a-z0-9àèéìòù@.+]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        out = value
    else:
        out = datetime.fromisoformat(str(value or "").replace("Z", "+00:00"))
    if out.tzinfo is None:
        out = out.replace(tzinfo=ROME)
    return out.astimezone(ROME)


def _status(value: Any, has_date: bool = True) -> str:
    raw = _norm(value)
    if raw in {"installata", "installed"}: return "Installata"
    if raw in {"completata", "completato", "completed"}: return "Completata"
    if raw in {"annullata", "annullato", "cancelled", "cancellato"}: return "Annullata"
    if raw in {"confermata da installare", "confermato", "confermata"}: return "Confermata / Da installare"
    if raw in {"in sospeso", "sospesa", "sospeso"}: return "In sospeso"
    return "Programmata" if has_date else "Da programmare"


def _source_stamp(event: Dict[str, Any]):
    return event.get("updated_at") or event.get("created_at") or _now()


async def _best_site(db, client_id: str, location: Any) -> Optional[str]:
    sites = await db.crm_sedi.find({"cliente_id": client_id}).to_list(length=500)
    if not sites:
        return None
    loc = _norm(location)
    if loc:
        scored = []
        for site in sites:
            parts = [site.get("nome"), site.get("indirizzo"), site.get("civico"), site.get("cap"), site.get("comune"), site.get("provincia")]
            text = _norm(" ".join(str(x or "") for x in parts))
            score = 0
            if text and text in loc: score += 100 + len(text)
            for part in parts:
                p = _norm(part)
                if len(p) >= 4 and p in loc: score += len(p)
            scored.append((score, site))
        scored.sort(key=lambda x: x[0], reverse=True)
        if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
            return str(scored[0][1].get("id") or "") or None
    primary = next((s for s in sites if s.get("is_primary") is True), None)
    if primary:
        return str(primary.get("id") or "") or None
    if len(sites) == 1:
        return str(sites[0].get("id") or "") or None
    return None


async def _match_client_and_site(db, event: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    existing_client = str(event.get("cliente_id") or "").strip()
    if existing_client:
        client = await db.crm_clienti.find_one({"id": existing_client, "archived": {"$ne": True}})
        if client:
            existing_site = str(event.get("sede_id") or "").strip()
            if existing_site:
                site = await db.crm_sedi.find_one({"id": existing_site, "cliente_id": existing_client})
                if site:
                    return existing_client, existing_site
            return existing_client, await _best_site(db, existing_client, event.get("location"))

    hay_raw = " ".join(str(event.get(k) or "") for k in ("title", "description", "location"))
    hay = _norm(hay_raw)
    hay_digits = _digits(hay_raw)
    clients = await db.crm_clienti.find({"archived": {"$ne": True}}).to_list(length=20000)
    best = None
    best_score = 0
    tied = False
    for client in clients:
        score = 0
        for name in (
            client.get("ragione_sociale"), client.get("nome_struttura"),
            " ".join(x for x in (client.get("nome"), client.get("cognome")) if x),
            client.get("referente"),
        ):
            n = _norm(name)
            if len(n) >= 4 and n in hay:
                score = max(score, 100 + len(n))
        for email_field in ("email", "pec"):
            email = str(client.get(email_field) or "").strip().casefold()
            if email and email in hay_raw.casefold():
                score = max(score, 220 + len(email))
        phone = _digits(client.get("telefono"))
        if len(phone) >= 7 and phone in hay_digits:
            score = max(score, 180 + len(phone))
        if score > best_score:
            best, best_score, tied = client, score, False
        elif score and score == best_score:
            tied = True
    if not best or best_score < 104 or tied:
        return None, None
    client_id = str(best.get("id") or "") or None
    return client_id, (await _best_site(db, client_id, event.get("location")) if client_id else None)


async def _resource_assignment(db, event: Dict[str, Any]) -> tuple[Optional[str], Optional[str]]:
    resource_ids = event.get("resource_ids") or []
    rid = str(resource_ids[0] or "") if resource_ids else ""
    if not rid:
        return None, None
    resource = await db.calendar_resources.find_one({"id": rid})
    if not resource:
        return None, None
    return (str(resource.get("linked_user_id") or "") or None, str(resource.get("name") or "") or None)


async def sync_calendar_event_to_installation(db, event: Dict[str, Any], actor: str = "calendar-sync") -> Dict[str, Any]:
    category = _norm(event.get("category"))
    title_norm = _norm(event.get("title"))
    if category != "installazione" and "installaz" not in title_norm:
        return {"action": "skipped", "reason": "not_installation"}
    event_id = str(event.get("id") or "").strip()
    if not event_id or not event.get("start"):
        return {"action": "skipped", "reason": "missing_id_or_start"}

    start = _dt(event.get("start"))
    try:
        end = _dt(event.get("end")) if event.get("end") else start + timedelta(hours=1)
    except Exception:
        end = start + timedelta(hours=1)
    duration = max(15, int((end - start).total_seconds() // 60))
    client_id, site_id = await _match_client_and_site(db, event)
    tech_user_id, tech_name = await _resource_assignment(db, event)

    existing = await db.crm_installazioni.find_one({"calendar_event_id": event_id})
    linked_existing = False
    if not existing:
        shadow = str(event.get("shadow_source_key") or "")
        if shadow.startswith("installazione:"):
            existing = await db.crm_installazioni.find_one({"id": shadow.split(":", 1)[1]})
            linked_existing = bool(existing)
    if not existing and client_id:
        candidates = await db.crm_installazioni.find({
            "data": start.date().isoformat(),
            "cliente_id": client_id,
            "$or": [{"calendar_event_id": {"$exists": False}}, {"calendar_event_id": None}, {"calendar_event_id": ""}],
        }).limit(5).to_list(length=5)
        if len(candidates) == 1:
            existing = candidates[0]
            linked_existing = True

    source_stamp = _source_stamp(event)
    base_payload: Dict[str, Any] = {
        "calendar_event_id": event_id,
        "calendar_title": str(event.get("title") or "Installazione"),
        "calendar_source": "calendar_events",
        "calendar_source_updated_at": source_stamp,
        "cliente_collegamento_stato": "collegato" if client_id else "da_collegare",
        "updated_at": _now(),
    }
    if client_id: base_payload["cliente_id"] = client_id
    if site_id: base_payload["sede_id"] = site_id
    if event.get("commessa_id"): base_payload["commessa_id"] = event.get("commessa_id")
    if tech_user_id: base_payload["tecnico_user_id"] = tech_user_id
    if tech_name: base_payload["tecnico"] = tech_name

    source_fields = {
        "data": start.date().isoformat(),
        "ora": start.strftime("%H:%M"),
        "durata_prevista": f"{duration} min",
        "stato": _status(event.get("status"), True),
        "indirizzo_libero": str(event.get("location") or ""),
        "istruzioni_intervento": str(event.get("description") or ""),
        "note": str(event.get("description") or ""),
        "nominativo": str(event.get("title") or "Installazione"),
    }

    if existing:
        update = dict(base_payload)
        old_stamp = existing.get("calendar_source_updated_at")
        source_changed = old_stamp is None or str(source_stamp) != str(old_stamp)
        if existing.get("import_source") == "calendar" and source_changed:
            update.update(source_fields)
        else:
            for key, value in source_fields.items():
                if existing.get(key) in (None, "") and value not in (None, ""):
                    update[key] = value
        if not existing.get("import_source"):
            update["import_source"] = "calendar-linked" if linked_existing else "calendar"
        await db.crm_installazioni.update_one({"id": existing.get("id")}, {"$set": update})
        installation_id = str(existing.get("id"))
        action = "linked" if linked_existing else "updated"
    else:
        installation_id = str(uuid.uuid4())
        doc = {
            **source_fields,
            **base_payload,
            "id": installation_id,
            "import_source": "calendar",
            "created_at": _now(),
            "created_by": actor,
        }
        await db.crm_installazioni.insert_one(doc)
        action = "created"

    event_update: Dict[str, Any] = {
        "shadow_source_key": f"installazione:{installation_id}",
        "calendar_installation_synced_at": _now(),
        "calendar_installation_synced_source_updated_at": source_stamp,
    }
    if client_id: event_update["cliente_id"] = client_id
    if site_id: event_update["sede_id"] = site_id
    await db.calendar_events.update_one({"id": event_id}, {"$set": event_update})
    return {"action": action, "installation_id": installation_id, "client_linked": bool(client_id), "site_linked": bool(site_id)}


async def sync_all_calendar_installations(db, actor: str = "calendar-sync", force: bool = False) -> Dict[str, Any]:
    category_match: Dict[str, Any] = {"$or": [
        {"category": {"$regex": "^Installazione$", "$options": "i"}},
        {"title": {"$regex": "installaz", "$options": "i"}},
    ]}
    query: Dict[str, Any] = category_match
    if not force:
        query = {"$and": [category_match, {"$or": [
            {"calendar_installation_synced_at": {"$exists": False}},
            {"$expr": {"$ne": ["$updated_at", "$calendar_installation_synced_source_updated_at"]}},
        ]}]}
    rows = await db.calendar_events.find(query).sort("start", 1).to_list(length=50000)
    stats = {"checked": len(rows), "created": 0, "updated": 0, "linked": 0, "clients_linked": 0, "clients_to_link": 0, "errors": []}
    for event in rows:
        try:
            result = await sync_calendar_event_to_installation(db, dict(event), actor=actor)
            action = result.get("action")
            if action in stats: stats[action] += 1
            if result.get("client_linked"): stats["clients_linked"] += 1
            elif action not in ("skipped", None): stats["clients_to_link"] += 1
        except Exception as exc:
            stats["errors"].append({"event_id": str(event.get("id") or ""), "title": str(event.get("title") or ""), "error": str(exc)})
    await db.settings.update_one({"_id": "calendar_installations_sync"}, {"$set": {"last_run_at": _now(), "last_result": stats}}, upsert=True)
    return stats
