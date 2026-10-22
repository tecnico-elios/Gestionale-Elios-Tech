from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, ConfigDict
import asyncio
import io
import re
import uuid
import zipfile
import auth as auth_mod
from zoneinfo import ZoneInfo
from calendar_installation_sync import sync_all_calendar_installations, sync_calendar_event_to_installation
from calendar_operations_sync import sync_all_calendar_operations, sync_calendar_event_operations

try:
    from dateutil.rrule import rrulestr
except Exception:  # pragma: no cover
    rrulestr = None

ROME = ZoneInfo("Europe/Rome")

DEFAULT_RESOURCES = [
    {"name": "RICCARDO", "color": "#ac725e"},
    {"name": "ENRICO", "color": "#16a765"},
    {"name": "IVAN", "color": "#9a9cff"},
    {"name": "BUSSATORI", "color": "#f83a22"},
    {"name": "CAMILLA", "color": "#f691b2"},
    {"name": "ROSSI", "color": "#fa573c"},
    {"name": "TECNICO / GENERALE", "color": "#2d6ea3"},
]

DEFAULT_PERSON_ROLES = ("Amministrazione", "Tecnico", "Commerciale", "Assistenza")

def _normalize_resource_role(value: Any) -> str:
    """Ruolo operativo libero, ripulito e limitato a una lunghezza ragionevole."""
    role = re.sub(r"\s+", " ", str(value or "").strip())
    if not role:
        return "Tecnico"
    return role[:80].strip()

CATEGORY_COLORS = {
    "Installazione": "#2563eb", "Sopralluogo": "#7c3aed", "Assistenza": "#dc2626",
    "Riunione": "#0f766e", "Formazione": "#0369a1", "Attività": "#475569", "Altro": "#64748b",
}

class AnyBody(BaseModel):
    model_config = ConfigDict(extra="allow")


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _clean(doc: Optional[Dict[str, Any]]):
    if not doc: return doc
    out = dict(doc); out.pop("_id", None)
    for key in ("created_at", "updated_at", "finalized_at", "last_import_at"):
        if isinstance(out.get(key), datetime): out[key] = out[key].isoformat()
    return out


def _norm(value: Any) -> str:
    value = str(value or "").casefold()
    value = re.sub(r"[^a-z0-9àèéìòù]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _classify(title: str, description: str = "") -> str:
    text = _norm(f"{title} {description}")
    if "installazione" in text or "installaz" in text: return "Installazione"
    if "sopralluogo" in text or "soprallouogo" in text or "soprall" in text: return "Sopralluogo"
    if "assistenza" in text or "intervento" in text or "config" in text or "onboarding" in text: return "Assistenza"
    if "formazione" in text or "corso" in text: return "Formazione"
    if any(x in text for x in ("riunione", "call", "videocall", "video call", "meeting")): return "Riunione"
    return "Attività"


def _parse_dt(value: Any, fallback: Optional[datetime] = None) -> datetime:
    try:
        dt = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        if dt.tzinfo is None: dt = dt.replace(tzinfo=ROME)
        return dt.astimezone(ROME)
    except Exception:
        return fallback or datetime.now(ROME)


def _date_only(value: Any) -> str:
    try: return _parse_dt(value).date().isoformat()
    except Exception: return str(value or "")[:10]


def _unescape_ics(value: str) -> str:
    return (value or "").replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _unfold(text: str) -> List[str]:
    raw = text.replace("\r\n", "\n").replace("\r", "\n").split("\n"); out: List[str] = []
    for line in raw:
        if line.startswith((" ", "\t")) and out: out[-1] += line[1:]
        else: out.append(line)
    return out


def _parse_ics_dt(key: str, value: str) -> tuple[str, bool]:
    pmap: Dict[str, str] = {}
    for param in key.split(";")[1:]:
        if "=" in param:
            a, b = param.split("=", 1); pmap[a.upper()] = b
    all_day = pmap.get("VALUE") == "DATE" or (len(value) == 8 and "T" not in value)
    if all_day:
        return datetime.strptime(value[:8], "%Y%m%d").replace(tzinfo=ROME).isoformat(), True
    tzid = pmap.get("TZID")
    if value.endswith("Z"):
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(ROME)
    else:
        fmt = "%Y%m%dT%H%M%S" if len(value) >= 15 else "%Y%m%dT%H%M"
        dt = datetime.strptime(value[:15] if fmt.endswith("%S") else value[:13], fmt)
        try: tz = ZoneInfo(tzid) if tzid else ROME
        except Exception: tz = ROME
        dt = dt.replace(tzinfo=tz).astimezone(ROME)
    return dt.isoformat(), False


def _parse_ics(text: str) -> List[Dict[str, Any]]:
    events: List[Dict[str, Any]] = []; current: Optional[Dict[str, Any]] = None
    for line in _unfold(text):
        if line == "BEGIN:VEVENT": current = {}; continue
        if line == "END:VEVENT":
            if current is not None: events.append(current)
            current = None; continue
        if current is None or ":" not in line: continue
        key, value = line.split(":", 1); base = key.split(";", 1)[0].upper()
        if base in ("DTSTART", "DTEND", "RECURRENCE-ID"):
            try:
                iso, all_day = _parse_ics_dt(key, value); current[base.lower().replace("-", "_")] = iso
                if base == "DTSTART": current["all_day"] = all_day
            except Exception: pass
        elif base in ("SUMMARY", "DESCRIPTION", "LOCATION", "UID", "STATUS", "RRULE"):
            current[base.lower()] = _unescape_ics(value)
    return events


def _calendar_name_from_path(name: str) -> str:
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base = re.sub(r"\.ics$", "", base, flags=re.I).strip()
    base = re.sub(r"^calendario\s+", "", base, flags=re.I).strip()
    return base or "Calendario importato"


def build_router(db, deps):
    router = APIRouter(prefix="/calendar", tags=["Calendar"])

    async def require_people_role_manager(current=Depends(deps.require_password_current)):
        """Admin oppure utente a cui l'Admin ha delegato la gestione persone/ruoli."""
        if (
            current.get("role") == auth_mod.ROLE_ADMIN
            or auth_mod.is_master_user(current)
            or auth_mod.has_permission(current, "calendar", "manage_people_roles")
        ):
            return current
        raise HTTPException(403, "Permesso negato: gestione persone e ruoli del calendario")

    async def calendar_roles() -> List[str]:
        doc = await db.settings.find_one({"_id": "calendar_roles"}) or {}
        saved = [str(x).strip() for x in (doc.get("items") or []) if str(x).strip()]
        resources = await db.calendar_resources.find({"active": {"$ne": False}}).to_list(length=2000)
        assigned = [str(x.get("role") or "").strip() for x in resources if str(x.get("role") or "").strip()]
        seed = ["Amministrazione", "Tecnico", "Commerciale", "Assistenza"]
        out = []
        seen = set()
        for role in saved + assigned + seed:
            key = role.casefold()
            if key and key not in seen:
                seen.add(key); out.append(role[:80])
        if out != saved:
            await db.settings.update_one({"_id": "calendar_roles"}, {"$set": {"items": out, "updated_at": _now()}}, upsert=True)
        return out

    async def validated_calendar_role(value: Any) -> str:
        role = re.sub(r"\s+", " ", str(value or "Tecnico").strip())[:80]
        roles = await calendar_roles()
        match = next((x for x in roles if x.casefold() == role.casefold()), None)
        if not match:
            raise HTTPException(400, "Ruolo non valido. Crealo prima nella gestione Ruoli del calendario.")
        return match

    async def migration_state() -> Dict[str, Any]:
        doc = await db.settings.find_one({"_id": "calendar_migration"}) or {}
        return {"completed": bool(doc.get("completed")), "ready_to_finalize": bool(doc.get("ready_to_finalize")), "finalized": bool(doc.get("finalized")), "imports_enabled": not bool(doc.get("finalized")), "last_import_at": doc.get("last_import_at"), "finalized_at": doc.get("finalized_at"), "last_result": doc.get("last_result") or {}}

    async def ensure_defaults():
        if await db.calendar_resources.count_documents({"active": {"$ne": False}}): return
        now = _now(); users = await db.users.find({"active": {"$ne": False}}).to_list(length=500)
        for index, item in enumerate(DEFAULT_RESOURCES):
            linked = None; target = _norm(item["name"].split("/")[0])
            for user in users:
                hay = " ".join([_norm(user.get("full_name")), _norm(user.get("username")), _norm(user.get("email"))])
                if target and target in hay: linked = str(user.get("_id")); break
            await db.calendar_resources.insert_one({"id": str(uuid.uuid4()), "name": item["name"], "color": item["color"], "role": _normalize_resource_role(item.get("role")), "linked_user_id": linked, "active": True, "sort_order": index * 10, "created_at": now, "updated_at": now, "created_by": "bootstrap"})

    async def all_resources() -> List[Dict[str, Any]]:
        await ensure_defaults()
        rows = [dict(row) for row in await db.calendar_resources.find({"active": {"$ne": False}}).sort([("sort_order", 1), ("name", 1)]).to_list(length=500)]
        for row in rows:
            role = _normalize_resource_role(row.get("role"))
            if row.get("role") != role:
                await db.calendar_resources.update_one({"id": row.get("id")}, {"$set": {"role": role, "updated_at": _now()}})
                row["role"] = role
        return rows

    async def resource_for_import_name(name: str, color: Optional[str] = None) -> Dict[str, Any]:
        raw = _norm(name); compact = _norm(re.sub(r"^calendario\s+", "", str(name), flags=re.I)); resources = await all_resources()
        for resource in resources:
            aliases = [_norm(resource.get("name")), _norm(resource.get("display_name")), _norm(resource.get("source_google_name"))]
            for alias in aliases:
                if alias and (raw == alias or compact == alias or alias in raw or compact in alias): return resource
        now = _now(); doc = {"id": str(uuid.uuid4()), "name": re.sub(r"^Calendario\s+", "", str(name), flags=re.I).strip() or "Calendario importato", "color": color or "#64748b", "role": "Tecnico", "active": True, "sort_order": 1000, "created_at": now, "updated_at": now, "created_by": "calendar-import"}
        await db.calendar_resources.insert_one(doc); return doc

    async def client_site_names(client_id=None, site_id=None):
        client = await db.crm_clienti.find_one({"id": client_id}) if client_id else None; site = await db.crm_sedi.find_one({"id": site_id}) if site_id else None
        cname = client.get("ragione_sociale") or " ".join(x for x in [client.get("nome"), client.get("cognome")] if x) or client.get("referente") or "Cliente" if client else ""
        address = ", ".join(str(x) for x in [site.get("indirizzo"), site.get("civico"), site.get("cap"), site.get("comune"), site.get("provincia")] if x) if site else ""
        return cname, address

    async def resource_from_technician(record: Dict[str, Any], resources: List[Dict[str, Any]]):
        uid = str(record.get("tecnico_user_id") or ""); tech = _norm(record.get("tecnico") or record.get("installatore"))
        for resource in resources:
            if uid and str(resource.get("linked_user_id") or "") == uid: return resource
            rn = _norm(resource.get("name"))
            if tech and rn and (tech in rn or rn in tech): return resource
        return None

    def resource_from_custom_data(data: Dict[str, Any], resources: List[Dict[str, Any]]):
        if not isinstance(data, dict): return None
        parts: List[str] = []; key_tokens = ("agente", "owner", "account_owner", "persona", "tecnico", "installatore", "assegnato", "responsabile", "utente", "calendario")
        for key, value in data.items():
            nk = _norm(key).replace(" ", "_")
            if not any(token in nk for token in key_tokens): continue
            if isinstance(value, list): parts.extend(str(x.get("name") or x.get("label") or x.get("id") or x) if isinstance(x, dict) else str(x) for x in value)
            elif isinstance(value, dict): parts.append(str(value.get("name") or value.get("label") or value.get("id") or ""))
            else: parts.append(str(value or ""))
        hay = _norm(" ".join(parts)); best = None; best_score = 0
        if not hay: return None
        for resource in resources:
            for alias in [_norm(resource.get("name")), _norm(resource.get("display_name"))]:
                if not alias: continue
                score = 100 + len(alias) if alias == hay else (50 + len(alias) if alias in hay else 0)
                if score > best_score: best, best_score = resource, score
        return best

    async def synth(resource_type: str, coll_name: str, start: str, end: str, resources: List[Dict[str, Any]]):
        rows = await db[coll_name].find({"data": {"$gte": start[:10], "$lte": end[:10]}}).to_list(length=10000); out = []
        for row in rows:
            date = str(row.get("data") or "")[:10]
            if not date: continue
            clock = str(row.get("ora") or "09:00")[:5] or "09:00"
            try: start_dt = datetime.fromisoformat(f"{date}T{clock}:00").replace(tzinfo=ROME)
            except Exception: start_dt = datetime.fromisoformat(f"{date}T09:00:00").replace(tzinfo=ROME)
            duration = 60; match = re.search(r"(\d+(?:[.,]\d+)?)", str(row.get("durata_prevista") or ""))
            if match:
                number = float(match.group(1).replace(",", ".")); duration = int(number * 60) if number <= 12 else int(number)
            end_dt = start_dt + timedelta(minutes=max(15, duration)); cname, address = await client_site_names(row.get("cliente_id"), row.get("sede_id")); base = cname or row.get("nominativo") or row.get("numero") or resource_type; resource = await resource_from_technician(row, resources)
            out.append({"key": f"{resource_type.lower()}:{row.get('id')}", "id": str(row.get("id")), "source_type": resource_type.lower(), "source_id": str(row.get("id")), "title": f"{resource_type} · {base}", "start": start_dt.isoformat(), "end": end_dt.isoformat(), "all_day": False, "category": resource_type, "status": row.get("stato") or "", "description": row.get("descrizione") or row.get("note") or row.get("istruzioni_intervento") or "", "location": row.get("indirizzo_libero") or address, "resource_ids": [resource.get("id")] if resource else [], "resource_name": resource.get("name") if resource else (row.get("tecnico") or "Da assegnare"), "resource_color": resource.get("color") if resource else "#94a3b8", "cliente_id": row.get("cliente_id"), "sede_id": row.get("sede_id"), "commessa_id": row.get("commessa_id"), "source_record": _clean(row)})
        return out

    def expand_manual(doc: Dict[str, Any], start_dt: datetime, end_dt: datetime):
        base = _clean(doc)
        if not base.get("rrule") or rrulestr is None: return [base]
        try:
            first = _parse_dt(base["start"]); rule = rrulestr(base["rrule"], dtstart=first); occurrences = rule.between(start_dt, end_dt, inc=True); original_end = _parse_dt(base.get("end"), first + timedelta(hours=1)); duration = original_end - first; out = []
            for occurrence in occurrences[:2000]:
                item = dict(base); item["start"] = occurrence.isoformat(); item["end"] = (occurrence + duration).isoformat(); item["key"] = f"manual:{base['id']}:{occurrence.isoformat()}"; item["recurrence_instance"] = True; out.append(item)
            return out
        except Exception: return [base]

    async def try_link_client(event: Dict[str, Any], clients: Optional[List[Dict[str, Any]]] = None):
        hay = _norm(" ".join([event.get("title") or "", event.get("description") or "", event.get("location") or ""]))
        if not hay: return event
        clients = clients if clients is not None else await db.crm_clienti.find({}).to_list(length=10000); best = None; best_len = 0
        for client in clients:
            for name in [client.get("ragione_sociale"), " ".join(x for x in [client.get("nome"), client.get("cognome")] if x), client.get("referente")]:
                normalized = _norm(name)
                if len(normalized) >= 5 and normalized in hay and len(normalized) > best_len: best, best_len = client, len(normalized)
        if best:
            event["cliente_id"] = best.get("id"); site = await db.crm_sedi.find_one({"cliente_id": best.get("id"), "is_primary": True})
            if site: event["sede_id"] = site.get("id")
        return event

    async def try_link_operational_source(event: Dict[str, Any]):
        mapping = {"Installazione": ("crm_installazioni", "installazione"), "Sopralluogo": ("crm_sopralluoghi", "sopralluogo"), "Assistenza": ("crm_assistenza", "assistenza")}; category = event.get("category")
        if category not in mapping: return event
        coll_name, prefix = mapping[category]; query: Dict[str, Any] = {"data": _date_only(event.get("start"))}
        if event.get("cliente_id"): query["cliente_id"] = event.get("cliente_id")
        rows = await db[coll_name].find(query).limit(5).to_list(length=5)
        if len(rows) == 1: event["shadow_source_key"] = f"{prefix}:{rows[0].get('id')}"
        return event

    @router.get("/roles")
    async def list_calendar_roles(current=Depends(deps.require_password_current)):
        return {"items": await calendar_roles()}

    @router.post("/roles")
    async def create_calendar_role(body: AnyBody, current=Depends(require_people_role_manager)):
        name = re.sub(r"\s+", " ", str(body.model_dump().get("name") or "").strip())[:80]
        if not name:
            raise HTTPException(400, "Nome ruolo obbligatorio")
        roles = await calendar_roles()
        if any(x.casefold() == name.casefold() for x in roles):
            return {"items": roles, "created": False}
        roles.append(name)
        await db.settings.update_one({"_id": "calendar_roles"}, {"$set": {"items": roles, "updated_at": _now(), "updated_by": current.get("username")}}, upsert=True)
        return {"items": roles, "created": True}

    @router.delete("/roles/{role_name}")
    async def delete_calendar_role(role_name: str, current=Depends(require_people_role_manager)):
        roles = await calendar_roles()
        target = next((x for x in roles if x.casefold() == role_name.casefold()), None)
        if not target:
            raise HTTPException(404, "Ruolo non trovato")
        if await db.calendar_resources.count_documents({"active": {"$ne": False}, "role": {"$regex": f"^{re.escape(target)}$", "$options": "i"}}):
            raise HTTPException(409, "Ruolo assegnato a una o più persone: riassegnale prima di eliminarlo")
        next_roles = [x for x in roles if x.casefold() != target.casefold()]
        await db.settings.update_one({"_id": "calendar_roles"}, {"$set": {"items": next_roles, "updated_at": _now(), "updated_by": current.get("username")}}, upsert=True)
        return {"items": next_roles}

    @router.get("/integration-state")
    async def integration_state(current=Depends(deps.require_password_current)): return _clean(await migration_state())

    @router.get("/resources")
    async def list_resources(current=Depends(deps.require_password_current)): return {"items": [_clean(x) for x in await all_resources()]}

    @router.post("/resources")
    async def create_resource(body: AnyBody, current=Depends(require_people_role_manager)):
        data = body.model_dump(); name = str(data.get("name") or "").strip(); data["role"] = _normalize_resource_role(data.get("role"))
        if not name: raise HTTPException(400, "Nome calendario/persona obbligatorio")
        if await db.calendar_resources.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}, "active": {"$ne": False}}): raise HTTPException(409, "Calendario già presente")
        data["role"] = await validated_calendar_role(data.get("role") or "Tecnico")
        now = _now(); doc = {**data, "id": str(uuid.uuid4()), "name": name, "color": data.get("color") or "#64748b", "active": True, "created_at": now, "updated_at": now, "created_by": current.get("username")}; doc.pop("source_google_name", None); await db.calendar_resources.insert_one(doc); return _clean(doc)

    @router.put("/resources/{resource_id}")
    async def update_resource(resource_id: str, body: AnyBody, current=Depends(require_people_role_manager)):
        data = body.model_dump(); data.pop("id", None); data.pop("source_google_name", None)
        if "role" in data:
            data["role"] = await validated_calendar_role(data.get("role"))
        data["updated_at"] = _now(); result = await db.calendar_resources.update_one({"id": resource_id}, {"$set": data})
        if not result.matched_count: raise HTTPException(404, "Calendario non trovato")
        return _clean(await db.calendar_resources.find_one({"id": resource_id}))

    @router.delete("/resources/{resource_id}")
    async def delete_resource(resource_id: str, current=Depends(require_people_role_manager)):
        await db.calendar_resources.update_one({"id": resource_id}, {"$set": {"active": False, "updated_at": _now()}}); return {"ok": True}

    @router.get("/events")
    async def events(start: str = Query(...), end: str = Query(...), resource_id: Optional[str] = None, category: Optional[str] = None, current=Depends(deps.require_password_current)):
        start_dt = _parse_dt(start); end_dt = _parse_dt(end); resources = await all_resources(); rows = await db.calendar_events.find({"start": {"$lte": end_dt.isoformat()}}).to_list(length=30000); manual = []
        for row in rows:
            for event in expand_manual(row, start_dt, end_dt):
                estart = _parse_dt(event.get("start")); eend = _parse_dt(event.get("end") or event.get("start"))
                if eend < start_dt or estart > end_dt: continue
                event["key"] = event.get("key") or f"manual:{event.get('id')}"; event["source_type"] = "manual"; event["source_id"] = event.get("id"); rid = (event.get("resource_ids") or [None])[0]; resource = next((x for x in resources if x.get("id") == rid), None)
                if resource: event["resource_name"] = resource.get("name"); event["resource_color"] = resource.get("color")
                manual.append(event)
        installations, surveys, technical, assistance = await asyncio.gather(
            synth("Installazione", "crm_installazioni", start, end, resources),
            synth("Sopralluogo", "crm_sopralluoghi", start, end, resources),
            synth("Intervento tecnico", "crm_interventi_tecnici", start, end, resources),
            synth("Assistenza", "crm_assistenza", start, end, resources),
        )
        # R65: il Calendario deve mantenere l'evento originale importato da Google.
        # Le copie operative (Installazioni/Interventi/Assistenza) vengono mostrate solo
        # se non esiste gia il relativo evento locale/importato, evitando duplicati.
        shadow_keys = {str(event.get("shadow_source_key") or "") for event in manual if event.get("shadow_source_key")}
        manual_ids = {str(event.get("id") or "") for event in manual if event.get("id")}
        derived = installations + surveys + technical + assistance
        derived = [
            event for event in derived
            if str(event.get("key") or "") not in shadow_keys
            and str((event.get("source_record") or {}).get("calendar_event_id") or "") not in manual_ids
        ]
        out = manual + derived
        modules = await db.custom_modules.find({"active": {"$ne": False}, "calendar_enabled": True}).to_list(length=500)
        for module in modules:
            date_field = module.get("calendar_date_field") or "data"; time_field = module.get("calendar_time_field") or "ora"; title_field = module.get("calendar_title_field") or ((module.get("fields") or [{}])[0].get("key") if module.get("fields") else ""); records = await db.custom_records.find({"module_id": module.get("id")}).to_list(length=10000)
            for record in records:
                data = record.get("data") or {}; date = str(data.get(date_field) or "")[:10]
                if not date or date < start[:10] or date > end[:10]: continue
                clock = str(data.get(time_field) or "09:00")[:5]
                try: start_custom = datetime.fromisoformat(f"{date}T{clock}:00").replace(tzinfo=ROME)
                except Exception: continue
                resource = resource_from_custom_data(data, resources); out.append({"key": f"custom:{module.get('slug')}:{record.get('id')}", "id": record.get("id"), "source_type": "custom", "source_id": record.get("id"), "module_slug": module.get("slug"), "title": str(data.get(title_field) or module.get("name") or "Attività"), "start": start_custom.isoformat(), "end": (start_custom + timedelta(hours=1)).isoformat(), "all_day": False, "category": module.get("name"), "status": "", "description": str(data.get("note") or data.get("descrizione") or data.get("description") or ""), "location": str(data.get("luogo") or data.get("indirizzo") or ""), "resource_ids": [resource.get("id")] if resource else [], "resource_name": resource.get("name") if resource else "Non assegnato", "resource_color": resource.get("color") if resource else "#94a3b8"})
        if resource_id: out = [event for event in out if resource_id in (event.get("resource_ids") or [])]
        if category: out = [event for event in out if str(event.get("category") or "").casefold() == category.casefold()]
        out.sort(key=lambda event: (event.get("start") or "", event.get("title") or "")); return {"items": out, "resources": [_clean(x) for x in resources]}

    @router.post("/events")
    async def create_event(body: AnyBody, current=Depends(deps.require_password_current)):
        data = body.model_dump(); title = str(data.get("title") or "").strip()
        if not title or not data.get("start"): raise HTTPException(400, "Titolo e data/ora obbligatori")
        now = _now(); doc = {**data, "id": str(uuid.uuid4()), "title": title, "category": data.get("category") or _classify(title, data.get("description") or ""), "created_at": now, "updated_at": now, "created_by": current.get("username")}
        if not doc.get("end"): doc["end"] = (_parse_dt(doc["start"]) + timedelta(hours=1)).isoformat()
        await db.calendar_events.insert_one(doc)
        if str(doc.get("category") or "").casefold() == "installazione":
            await sync_calendar_event_to_installation(db, doc, actor=current.get("username") or "calendar")
            doc = await db.calendar_events.find_one({"id": doc.get("id")}) or doc
        await sync_calendar_event_operations(db, doc, actor=current.get("username") or "calendar")
        doc = await db.calendar_events.find_one({"id": doc.get("id")}) or doc
        return _clean(doc)

    @router.put("/events/{event_key:path}")
    async def update_event(event_key: str, body: AnyBody, current=Depends(deps.require_password_current)):
        data = body.model_dump(); data["updated_at"] = _now()
        if event_key.startswith("manual:"):
            event_id = event_key.split(":", 2)[1]; allowed = {key: value for key, value in data.items() if key not in ("id", "source_type", "source_id")}; result = await db.calendar_events.update_one({"id": event_id}, {"$set": allowed})
            if not result.matched_count: raise HTTPException(404, "Evento non trovato")
            fresh = await db.calendar_events.find_one({"id": event_id})
            if fresh and str(fresh.get("category") or "").casefold() == "installazione":
                await sync_calendar_event_to_installation(db, fresh, actor=current.get("username") or "calendar")
                fresh = await db.calendar_events.find_one({"id": event_id}) or fresh
            if fresh:
                await sync_calendar_event_operations(db, fresh, actor=current.get("username") or "calendar")
                fresh = await db.calendar_events.find_one({"id": event_id}) or fresh
            return _clean(fresh)
        mappings = {"installazione": "crm_installazioni", "sopralluogo": "crm_sopralluoghi", "assistenza": "crm_assistenza"}; prefix, _, record_id = event_key.partition(":")
        if prefix not in mappings: raise HTTPException(400, "Tipo evento non modificabile")
        update: Dict[str, Any] = {}
        if data.get("start"):
            dt = _parse_dt(data["start"]); update["data"] = dt.date().isoformat(); update["ora"] = dt.strftime("%H:%M")
        for key in ("stato", "tecnico", "tecnico_user_id", "note", "descrizione"):
            if key in data: update[key] = data[key]
        update["updated_at"] = _now(); result = await db[mappings[prefix]].update_one({"id": record_id}, {"$set": update})
        if not result.matched_count: raise HTTPException(404, "Attività collegata non trovata")
        return {"ok": True, "source_type": prefix, "source_id": record_id}

    @router.delete("/events/{event_key:path}")
    async def delete_event(event_key: str, current=Depends(deps.require_password_current)):
        if not event_key.startswith("manual:"): raise HTTPException(409, "Le attività collegate vanno eliminate dal loro modulo originale")
        await db.calendar_events.delete_one({"id": event_key.split(":", 2)[1]}); return {"ok": True}

    @router.post("/import/ics")
    async def import_ics(file: UploadFile = File(...), current=Depends(deps.require_admin)):
        state = await migration_state()
        if state["finalized"]: raise HTTPException(410, "Migrazione calendario conclusa: il gestionale usa solo i dati locali")
        raw = await file.read()
        if not raw: raise HTTPException(400, "File vuoto")
        entries: List[tuple[str, bytes]] = []
        if zipfile.is_zipfile(io.BytesIO(raw)):
            with zipfile.ZipFile(io.BytesIO(raw)) as archive:
                for name in archive.namelist():
                    if name.lower().endswith(".ics"): entries.append((name, archive.read(name)))
        elif (file.filename or "").lower().endswith(".ics"): entries.append((file.filename or "calendar.ics", raw))
        else: raise HTTPException(400, "Carica un file .ics o uno ZIP contenente calendari .ics")
        if not entries: raise HTTPException(400, "Nessun calendario .ics trovato")
        stats: Dict[str, Any] = {"calendars": 0, "parsed": 0, "imported": 0, "updated": 0, "skipped_cancelled": 0, "skipped_leads": 0, "linked_clients": 0, "errors": [], "per_calendar": []}; clients_cache = await db.crm_clienti.find({}).to_list(length=10000)  # R56_CALENDAR_FILTERS
        for path, blob in entries:
            name = _calendar_name_from_path(path)
            # R65: importa TUTTI i calendari Google. L'unica esclusione ammessa e' l'evento Lead.
            resource = await resource_for_import_name(name); stats["calendars"] += 1; cstats = {"name": name, "resource": resource.get("name"), "imported": 0, "updated": 0}; text = blob.decode("utf-8-sig", errors="replace")
            for source in _parse_ics(text):
                stats["parsed"] += 1
                if str(source.get("status") or "").upper() == "CANCELLED": stats["skipped_cancelled"] += 1; continue
                lead_text = _norm(f"{name} {source.get('summary') or ''} {source.get('description') or ''}")
                if re.search(r"(^| )leads?( |$)", lead_text): stats["skipped_leads"] += 1; continue
                if not source.get("dtstart") or not source.get("uid"): continue
                title = source.get("summary") or "Senza titolo"; start = source.get("dtstart"); end = source.get("dtend") or (_parse_dt(start) + (timedelta(days=1) if source.get("all_day") else timedelta(hours=1))).isoformat(); import_key = f"{source.get('uid')}|{source.get('recurrence_id') or ''}|{resource.get('id')}"
                doc: Dict[str, Any] = {"title": title, "start": start, "end": end, "all_day": bool(source.get("all_day")), "category": _classify(title, source.get("description") or ""), "status": "Importato", "description": source.get("description") or "", "location": source.get("location") or "", "resource_ids": [resource.get("id")], "rrule": source.get("rrule"), "migration_source": "ics", "migration_import_key": import_key, "migration_calendar": name, "updated_at": _now()}
                before = await db.calendar_events.find_one({"$or": [{"migration_import_key": import_key}, {"google_import_key": import_key}]})
                if not before:
                    doc = await try_link_client(doc, clients_cache); doc = await try_link_operational_source(doc)
                    if doc.get("cliente_id"): stats["linked_clients"] += 1
                    doc.update({"id": str(uuid.uuid4()), "created_at": _now(), "created_by": current.get("username")}); await db.calendar_events.insert_one(doc); stats["imported"] += 1; cstats["imported"] += 1
                else:
                    keep = {key: before.get(key) for key in ("cliente_id", "sede_id", "commessa_id", "shadow_source_key") if before.get(key)}; doc.update(keep); await db.calendar_events.update_one({"id": before.get("id")}, {"$set": doc}); stats["updated"] += 1; cstats["updated"] += 1
            stats["per_calendar"].append(cstats)
        sync_stats = await sync_all_calendar_installations(db, actor=current.get("username") or "calendar-import", force=True)
        stats["installations_sync"] = sync_stats
        operations_stats = await sync_all_calendar_operations(db, actor=current.get("username") or "calendar-import")
        stats["operations_sync"] = operations_stats
        now = _now(); await db.settings.update_one({"_id": "calendar_migration"}, {"$set": {"completed": True, "ready_to_finalize": True, "finalized": False, "last_import_at": now, "last_result": stats}}, upsert=True); return stats

    @router.post("/relink")
    async def relink(current=Depends(deps.require_admin)):
        rows = await db.calendar_events.find({"$and": [{"$or": [{"migration_source": "ics"}, {"source_origin": "google_ics"}]}, {"$or": [{"cliente_id": {"$exists": False}}, {"cliente_id": None}, {"cliente_id": ""}]}]}).to_list(length=50000); linked = 0
        for row in rows:
            event = await try_link_client(dict(row)); event = await try_link_operational_source(event)
            if event.get("cliente_id"):
                update = {"cliente_id": event.get("cliente_id"), "sede_id": event.get("sede_id"), "updated_at": _now()}
                if event.get("shadow_source_key"): update["shadow_source_key"] = event.get("shadow_source_key")
                await db.calendar_events.update_one({"id": row.get("id")}, {"$set": update}); linked += 1
        sync_stats = await sync_all_calendar_installations(db, actor=current.get("username") or "calendar-relink", force=True)
        operations_stats = await sync_all_calendar_operations(db, actor=current.get("username") or "calendar-relink")
        return {"checked": len(rows), "linked": linked, "installations_sync": sync_stats, "operations_sync": operations_stats}

    @router.post("/sync-installations")
    async def sync_installations(current=Depends(deps.require_admin)):
        return await sync_all_calendar_installations(db, actor=current.get("username") or "calendar-admin", force=True)

    @router.post("/migration/finalize")
    async def finalize_migration(current=Depends(deps.require_admin)):
        state = await migration_state()
        if not state["completed"]: raise HTTPException(409, "Importa e verifica prima il calendario")
        now = _now(); event_result = await db.calendar_events.update_many({"$or": [{"migration_source": "ics"}, {"source_origin": "google_ics"}, {"google_import_key": {"$exists": True}}]}, {"$unset": {"migration_source": "", "migration_import_key": "", "migration_calendar": "", "google_uid": "", "google_recurrence_id": "", "google_import_key": "", "source_origin": "", "source_calendar": ""}, "$set": {"updated_at": now}}); resource_result = await db.calendar_resources.update_many({"source_google_name": {"$exists": True}}, {"$unset": {"source_google_name": ""}, "$set": {"updated_at": now}}); await db.settings.update_one({"_id": "calendar_migration"}, {"$set": {"completed": True, "ready_to_finalize": False, "finalized": True, "finalized_at": now, "imports_enabled": False, "external_sync_enabled": False, "provider": "local"}}, upsert=True); await db.settings.delete_many({"_id": {"$in": ["google_calendar_config", "calendar_google_config", "google_calendar", "calendar_integration"]}}); await db.audit_logs.insert_one({"at": now, "actor_id": str(current.get("_id") or ""), "actor_username": current.get("username"), "action": "calendar.migration.finalize", "meta": {"events_localized": int(event_result.modified_count or 0), "resources_cleaned": int(resource_result.modified_count or 0)}})
        return {"ok": True, "events_localized": int(event_result.modified_count or 0), "resources_cleaned": int(resource_result.modified_count or 0), "message": "Migrazione calendario conclusa. Tutti gli eventi sono ora locali e l'importazione esterna è disattivata."}

    return router
