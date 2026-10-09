from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, Optional, List
from zoneinfo import ZoneInfo
import re
import uuid

ROME = ZoneInfo("Europe/Rome")
STOPWORDS = {
    "srl", "s.r.l", "spa", "s.p.a", "snc", "s.n.c", "sas", "s.a.s", "ss",
    "societa", "società", "azienda", "di", "del", "della", "dei", "degli", "delle",
    "e", "ed", "la", "le", "il", "lo", "i", "gli", "un", "una", "the",
}


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _norm(value: Any) -> str:
    value = str(value or "").casefold()
    value = re.sub(r"[^a-z0-9àèéìòù@.+]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _digits(value: Any) -> str:
    return re.sub(r"\D+", "", str(value or ""))


def _tokens(value: Any) -> List[str]:
    return [t for t in _norm(value).split() if len(t) >= 3 and t not in STOPWORDS]


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


def _site_score(site: Dict[str, Any], location: Any) -> int:
    loc = _norm(location)
    if not loc:
        return 0
    score = 0
    name = _norm(site.get("nome"))
    address = _norm(" ".join(x for x in [site.get("indirizzo"), site.get("civico")] if x))
    comune = _norm(site.get("comune"))
    cap = _norm(site.get("cap"))
    provincia = _norm(site.get("provincia"))
    if address and len(address) >= 5 and address in loc:
        score += 140 + min(len(address), 40)
    elif _norm(site.get("indirizzo")) and len(_norm(site.get("indirizzo"))) >= 5 and _norm(site.get("indirizzo")) in loc:
        score += 120
    if name and len(name) >= 5 and name in loc:
        score += 55
    if comune and len(comune) >= 4 and comune in loc:
        score += 35
    if cap and cap in loc:
        score += 25
    if provincia and len(provincia) >= 2 and re.search(rf"(^| ){re.escape(provincia)}( |$)", loc):
        score += 8
    return score


async def _best_site(db, client_id: str, location: Any, sites_cache: Optional[List[Dict[str, Any]]] = None) -> Optional[str]:
    if sites_cache is None:
        sites = await db.crm_sedi.find({"cliente_id": client_id}).to_list(length=500)
    else:
        sites = [s for s in sites_cache if str(s.get("cliente_id") or "") == str(client_id)]
    if not sites:
        return None
    scored = sorted(((_site_score(site, location), site) for site in sites), key=lambda x: x[0], reverse=True)
    if scored and scored[0][0] > 0 and (len(scored) == 1 or scored[0][0] > scored[1][0]):
        return str(scored[0][1].get("id") or "") or None
    primary = next((s for s in sites if s.get("is_primary") is True), None)
    if primary:
        return str(primary.get("id") or "") or None
    if len(sites) == 1:
        return str(sites[0].get("id") or "") or None
    return None


async def _match_client_and_site(
    db,
    event: Dict[str, Any],
    clients_cache: Optional[List[Dict[str, Any]]] = None,
    sites_cache: Optional[List[Dict[str, Any]]] = None,
) -> tuple[Optional[str], Optional[str]]:
    clients = clients_cache if clients_cache is not None else await db.crm_clienti.find({"archived": {"$ne": True}}).to_list(length=20000)
    sites = sites_cache if sites_cache is not None else await db.crm_sedi.find({}).to_list(length=20000)

    existing_client = str(event.get("cliente_id") or "").strip()
    if existing_client:
        client = next((c for c in clients if str(c.get("id") or "") == existing_client), None)
        if client:
            existing_site = str(event.get("sede_id") or "").strip()
            if existing_site and any(str(s.get("id") or "") == existing_site and str(s.get("cliente_id") or "") == existing_client for s in sites):
                return existing_client, existing_site
            return existing_client, await _best_site(db, existing_client, event.get("location"), sites)

    # Indirizzo/sede: segnale molto affidabile quando il titolo usa un nome abbreviato.
    location = event.get("location") or ""
    if location and sites:
        ranked_sites = sorted(((_site_score(site, location), site) for site in sites), key=lambda x: x[0], reverse=True)
        if ranked_sites and ranked_sites[0][0] >= 120 and (len(ranked_sites) == 1 or ranked_sites[0][0] > ranked_sites[1][0]):
            site = ranked_sites[0][1]
            cid = str(site.get("cliente_id") or "").strip()
            if cid and any(str(c.get("id") or "") == cid for c in clients):
                return cid, str(site.get("id") or "") or None

    # Ragione sociale/nome, anche abbreviati. I criteri sono volutamente prudenti:
    # in caso di parità/ambiguità non viene creato un collegamento sbagliato.
    hay_raw = " ".join(str(event.get(k) or "") for k in ("title", "description", "location"))
    hay = _norm(hay_raw)
    hay_tokens = set(_tokens(hay_raw))
    hay_digits = _digits(hay_raw)
    best = None
    best_score = 0
    tied = False
    for client in clients:
        score = 0
        names = [
            client.get("ragione_sociale"), client.get("nome_struttura"),
            " ".join(x for x in (client.get("nome"), client.get("cognome")) if x),
            client.get("referente"),
        ]
        for name in names:
            n = _norm(name)
            if not n:
                continue
            if len(n) >= 4 and n in hay:
                score = max(score, 170 + min(len(n), 60))
            ntokens = _tokens(name)
            matched = [t for t in ntokens if t in hay_tokens]
            if len(matched) >= 2:
                coverage = len(matched) / max(1, len(ntokens))
                score = max(score, int(125 + 25 * len(matched) + 30 * coverage))
            elif len(matched) == 1:
                token = matched[0]
                if any(ch.isdigit() for ch in token) and len(token) >= 3:
                    score = max(score, 145 + len(token))
                elif len(token) >= 8:
                    score = max(score, 128 + len(token))
        for email_field in ("email", "pec"):
            email = str(client.get(email_field) or "").strip().casefold()
            if email and email in hay_raw.casefold():
                score = max(score, 320 + len(email))
        phone = _digits(client.get("telefono"))
        if len(phone) >= 7 and phone in hay_digits:
            score = max(score, 280 + len(phone))
        if score > best_score:
            best, best_score, tied = client, score, False
        elif score and score == best_score:
            tied = True

    if not best or best_score < 130 or tied:
        return None, None
    client_id = str(best.get("id") or "") or None
    return client_id, (await _best_site(db, client_id, event.get("location"), sites) if client_id else None)


async def _resource_assignment(
    db,
    event: Dict[str, Any],
    resources_cache: Optional[List[Dict[str, Any]]] = None,
) -> tuple[Optional[str], Optional[str]]:
    resource_ids = event.get("resource_ids") or []
    rid = str(resource_ids[0] or "") if resource_ids else ""
    if not rid:
        return None, None
    if resources_cache is None:
        resource = await db.calendar_resources.find_one({"id": rid})
    else:
        resource = next((r for r in resources_cache if str(r.get("id") or "") == rid), None)
    if not resource:
        return None, None
    return (str(resource.get("linked_user_id") or "") or None, str(resource.get("name") or "") or None)


async def sync_calendar_event_to_installation(
    db,
    event: Dict[str, Any],
    actor: str = "calendar-sync",
    clients_cache: Optional[List[Dict[str, Any]]] = None,
    sites_cache: Optional[List[Dict[str, Any]]] = None,
    resources_cache: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
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
    client_id, site_id = await _match_client_and_site(db, event, clients_cache, sites_cache)
    tech_user_id, tech_name = await _resource_assignment(db, event, resources_cache)

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
        "calendar_client_link_pending": not bool(client_id),
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

    # Carica una volta sola le anagrafiche: evita centinaia di query ripetute e rende
    # possibile capire quando l'elenco clienti è cambiato e serve ritentare i link pendenti.
    clients = await db.crm_clienti.find({"archived": {"$ne": True}}).to_list(length=20000)
    sites = await db.crm_sedi.find({}).to_list(length=20000)
    resources = await db.calendar_resources.find({"active": {"$ne": False}}).to_list(length=2000)
    state = await db.settings.find_one({"_id": "calendar_installations_sync"}) or {}
    stamps = [str(c.get("updated_at") or c.get("created_at") or "") for c in clients]
    latest_client_stamp = max(stamps, default="")
    client_revision = f"{len(clients)}:{latest_client_stamp}"
    previous_revision = str(state.get("client_revision") or "")
    first_revision = not bool(previous_revision)
    revision_changed = previous_revision != client_revision

    query: Dict[str, Any] = category_match
    if not force and not first_revision:
        conditions: List[Dict[str, Any]] = [
            {"calendar_installation_synced_at": {"$exists": False}},
            {"$expr": {"$ne": ["$updated_at", "$calendar_installation_synced_source_updated_at"]}},
        ]
        # Solo quando l'anagrafica clienti cambia vengono riesaminate le installazioni
        # rimaste senza associazione: niente 323 controlli inutili a ogni apertura pagina.
        if revision_changed:
            conditions.extend([
                {"calendar_client_link_pending": True},
                {"calendar_client_link_pending": {"$exists": False}},
            ])
        query = {"$and": [category_match, {"$or": conditions}]}

    rows = await db.calendar_events.find(query).sort("start", 1).to_list(length=50000)
    stats = {
        "checked": len(rows), "created": 0, "updated": 0, "linked": 0,
        "clients_linked": 0, "clients_to_link": 0,
        "clients_available": len(clients), "sites_available": len(sites),
        "client_revision": client_revision, "client_revision_changed": revision_changed,
        "errors": [],
    }
    for event in rows:
        try:
            result = await sync_calendar_event_to_installation(
                db, dict(event), actor=actor,
                clients_cache=clients, sites_cache=sites, resources_cache=resources,
            )
            action = result.get("action")
            if action in stats: stats[action] += 1
            if result.get("client_linked"): stats["clients_linked"] += 1
            elif action not in ("skipped", None): stats["clients_to_link"] += 1
        except Exception as exc:
            stats["errors"].append({"event_id": str(event.get("id") or ""), "title": str(event.get("title") or ""), "error": str(exc)})
    await db.settings.update_one(
        {"_id": "calendar_installations_sync"},
        {"$set": {"last_run_at": _now(), "last_result": stats, "client_revision": client_revision}},
        upsert=True,
    )
    return stats
