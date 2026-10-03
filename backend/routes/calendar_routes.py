from __future__ import annotations

from datetime import datetime, timezone, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from pydantic import BaseModel, ConfigDict
import io, re, uuid, zipfile
from zoneinfo import ZoneInfo

try:
    from dateutil.rrule import rrulestr
except Exception:  # pragma: no cover
    rrulestr = None

ROME = ZoneInfo("Europe/Rome")

DEFAULT_RESOURCES = [
    {"name": "RICCARDO", "color": "#ac725e", "source_google_name": "Calendario RICCARDO"},
    {"name": "ENRICO", "color": "#16a765", "source_google_name": "Calendario ENRICO"},
    {"name": "IVAN", "color": "#9a9cff", "source_google_name": "Calendario IVAN"},
    {"name": "BUSSATORI", "color": "#f83a22", "source_google_name": "Calendario BUSSATORI"},
    {"name": "CAMILLA", "color": "#f691b2", "source_google_name": "Calendario CAMILLA"},
    {"name": "ROSSI", "color": "#fa573c", "source_google_name": "Calendario ROSSI"},
    {"name": "TECNICO / GENERALE", "color": "#9fe1e7", "source_google_name": "tecnico@eliostech.org"},
]

CATEGORY_COLORS = {
    "Installazione": "#1d4ed8",
    "Sopralluogo": "#7c3aed",
    "Assistenza": "#dc2626",
    "Commerciale": "#ea580c",
    "Riunione": "#0f766e",
    "Attività": "#475569",
}

class AnyBody(BaseModel):
    model_config = ConfigDict(extra="allow")


def _now():
    return datetime.now(timezone.utc)


def _clean(doc: Optional[Dict[str, Any]]):
    if not doc:
        return doc
    d = dict(doc)
    d.pop("_id", None)
    for k in ("created_at", "updated_at"):
        if isinstance(d.get(k), datetime):
            d[k] = d[k].isoformat()
    return d


def _norm(s: Any) -> str:
    s = str(s or "").casefold()
    s = re.sub(r"[^a-z0-9àèéìòù]+", " ", s)
    return re.sub(r"\s+", " ", s).strip()


def _classify(title: str, description: str = "") -> str:
    s = _norm(f"{title} {description}")
    if "installazione" in s or "installaz" in s:
        return "Installazione"
    if "sopralluogo" in s or "soprallouogo" in s or "soprall" in s:
        return "Sopralluogo"
    if "assistenza" in s or "intervento" in s or "config" in s or "onboarding" in s:
        return "Assistenza"
    if "lead" in s or "cliente" in s or "preventivo" in s or "commercial" in s:
        return "Commerciale"
    if any(x in s for x in ("riunione", "call", "videocall", "video call", "formazione", "meeting")):
        return "Riunione"
    return "Attività"


def _unescape_ics(value: str) -> str:
    return (value or "").replace("\\n", "\n").replace("\\N", "\n").replace("\\,", ",").replace("\\;", ";").replace("\\\\", "\\")


def _unfold(text: str) -> List[str]:
    raw = text.replace("\r\n", "\n").replace("\r", "\n").split("\n")
    out: List[str] = []
    for line in raw:
        if line.startswith((" ", "\t")) and out:
            out[-1] += line[1:]
        else:
            out.append(line)
    return out


def _parse_ics_dt(key: str, value: str) -> tuple[str, bool]:
    params = key.split(";")[1:]
    pmap = {}
    for p in params:
        if "=" in p:
            a, b = p.split("=", 1); pmap[a.upper()] = b
    all_day = pmap.get("VALUE") == "DATE" or (len(value) == 8 and "T" not in value)
    if all_day:
        dt = datetime.strptime(value[:8], "%Y%m%d").replace(tzinfo=ROME)
        return dt.isoformat(), True
    tzid = pmap.get("TZID")
    if value.endswith("Z"):
        dt = datetime.strptime(value, "%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc).astimezone(ROME)
    else:
        fmt = "%Y%m%dT%H%M%S" if len(value) >= 15 else "%Y%m%dT%H%M"
        dt = datetime.strptime(value[:15] if fmt.endswith("%S") else value[:13], fmt)
        try:
            tz = ZoneInfo(tzid) if tzid else ROME
        except Exception:
            tz = ROME
        dt = dt.replace(tzinfo=tz).astimezone(ROME)
    return dt.isoformat(), False


def _parse_ics(text: str) -> List[Dict[str, Any]]:
    lines = _unfold(text)
    events: List[Dict[str, Any]] = []
    cur = None
    for line in lines:
        if line == "BEGIN:VEVENT":
            cur = {}
            continue
        if line == "END:VEVENT":
            if cur is not None:
                events.append(cur)
            cur = None
            continue
        if cur is None or ":" not in line:
            continue
        key, value = line.split(":", 1)
        base = key.split(";", 1)[0].upper()
        if base in ("DTSTART", "DTEND", "RECURRENCE-ID"):
            try:
                iso, all_day = _parse_ics_dt(key, value)
                cur[base.lower().replace("-", "_")] = iso
                if base == "DTSTART": cur["all_day"] = all_day
            except Exception:
                pass
        elif base in ("SUMMARY", "DESCRIPTION", "LOCATION", "UID", "STATUS", "RRULE"):
            cur[base.lower()] = _unescape_ics(value)
    return events


def _calendar_name_from_path(name: str) -> str:
    base = name.rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    base = re.sub(r"\.ics$", "", base, flags=re.I).strip()
    return base or "Calendario importato"


def _date_only(iso: str) -> str:
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).astimezone(ROME).date().isoformat()
    except Exception:
        return str(iso or "")[:10]


def build_router(db, deps):
    router = APIRouter(prefix="/calendar", tags=["Calendar"])

    async def ensure_defaults():
        count = await db.calendar_resources.count_documents({"active": {"$ne": False}})
        if count:
            return
        now = _now()
        users = await db.users.find({"active": {"$ne": False}}).to_list(length=500)
        for i, item in enumerate(DEFAULT_RESOURCES):
            linked = None
            target = _norm(item["name"].split("/")[0])
            for u in users:
                hay = " ".join([_norm(u.get("full_name")), _norm(u.get("username")), _norm(u.get("email"))])
                if target and target in hay:
                    linked = str(u.get("_id")); break
            await db.calendar_resources.insert_one({
                "id": str(uuid.uuid4()), "name": item["name"], "color": item["color"],
                "source_google_name": item["source_google_name"], "linked_user_id": linked,
                "active": True, "sort_order": i * 10, "created_at": now, "updated_at": now,
                "created_by": "bootstrap-google",
            })

    async def all_resources():
        await ensure_defaults()
        return await db.calendar_resources.find({"active": {"$ne": False}}).sort([("sort_order", 1), ("name", 1)]).to_list(length=500)

    async def resource_for_name(name: str, color: Optional[str] = None):
        n = _norm(name)
        rows = await all_resources()
        for r in rows:
            aliases = [_norm(r.get("name")), _norm(r.get("source_google_name"))]
            if n in aliases or any(a and (a in n or n in a) for a in aliases):
                return r
        now = _now()
        doc = {"id": str(uuid.uuid4()), "name": name, "color": color or "#64748b", "active": True,
               "sort_order": 1000, "source_google_name": name, "created_at": now, "updated_at": now}
        await db.calendar_resources.insert_one(doc)
        return doc

    async def client_site_names(client_id=None, site_id=None):
        client = await db.crm_clienti.find_one({"id": client_id}) if client_id else None
        site = await db.crm_sedi.find_one({"id": site_id}) if site_id else None
        cname = ""
        if client:
            cname = client.get("ragione_sociale") or " ".join(x for x in [client.get("nome"), client.get("cognome")] if x) or client.get("referente") or "Cliente"
        sname = ""
        address = ""
        if site:
            sname = site.get("nome") or site.get("comune") or "Sede"
            address = ", ".join(str(x) for x in [site.get("indirizzo"), site.get("cap"), site.get("comune"), site.get("provincia")] if x)
        return cname, sname, address

    async def resource_from_technician(record: Dict[str, Any], resources: List[Dict[str, Any]]):
        uid = str(record.get("tecnico_user_id") or "")
        tech = _norm(record.get("tecnico") or record.get("installatore"))
        for r in resources:
            if uid and str(r.get("linked_user_id") or "") == uid:
                return r
            rn = _norm(r.get("name"))
            if tech and rn and (tech in rn or rn in tech):
                return r
        return None

    async def synth(resource_type: str, coll_name: str, start: str, end: str, resources: List[Dict[str, Any]]):
        q = {"data": {"$gte": start[:10], "$lte": end[:10]}}
        rows = await db[coll_name].find(q).to_list(length=10000)
        out = []
        for x in rows:
            date = str(x.get("data") or "")[:10]
            if not date: continue
            time = str(x.get("ora") or "09:00")[:5] or "09:00"
            try: sdt = datetime.fromisoformat(f"{date}T{time}:00").replace(tzinfo=ROME)
            except Exception: sdt = datetime.fromisoformat(f"{date}T09:00:00").replace(tzinfo=ROME)
            duration = 60
            raw_duration = str(x.get("durata_prevista") or "")
            m = re.search(r"(\d+(?:[.,]\d+)?)", raw_duration)
            if m:
                n = float(m.group(1).replace(",", ".")); duration = int(n * 60) if n <= 12 else int(n)
            edt = sdt + timedelta(minutes=max(15, duration))
            cname, sname, address = await client_site_names(x.get("cliente_id"), x.get("sede_id"))
            title = cname or x.get("nominativo") or x.get("numero") or resource_type
            if resource_type == "Installazione": title = f"Installazione · {title}"
            elif resource_type == "Sopralluogo": title = f"Sopralluogo · {title}"
            elif resource_type == "Assistenza": title = f"Assistenza · {title}"
            rr = await resource_from_technician(x, resources)
            out.append({
                "key": f"{resource_type.lower()}:{x.get('id')}", "id": str(x.get("id")), "source_type": resource_type.lower(),
                "source_id": str(x.get("id")), "title": title, "start": sdt.isoformat(), "end": edt.isoformat(), "all_day": False,
                "category": resource_type, "status": x.get("stato") or "", "description": x.get("descrizione") or x.get("note") or x.get("istruzioni_intervento") or "",
                "location": x.get("indirizzo_libero") or address, "resource_ids": [rr.get("id")] if rr else [], "resource_name": rr.get("name") if rr else (x.get("tecnico") or "Da assegnare"),
                "resource_color": rr.get("color") if rr else "#94a3b8",
                "cliente_id": x.get("cliente_id"), "sede_id": x.get("sede_id"), "commessa_id": x.get("commessa_id"),
                "installazione_id": str(x.get("id")) if resource_type == "Installazione" else x.get("installazione_id"),
                "sopralluogo_id": str(x.get("id")) if resource_type == "Sopralluogo" else None,
                "assistenza_id": str(x.get("id")) if resource_type == "Assistenza" else None,
                "source_record": _clean(x),
            })
        return out

    def expand_manual(doc: Dict[str, Any], start_dt: datetime, end_dt: datetime):
        base = _clean(doc)
        if not base.get("rrule") or rrulestr is None:
            return [base]
        try:
            dtstart = datetime.fromisoformat(base["start"].replace("Z", "+00:00"))
            if dtstart.tzinfo is None: dtstart = dtstart.replace(tzinfo=ROME)
            rule = rrulestr(base["rrule"], dtstart=dtstart)
            occs = rule.between(start_dt, end_dt, inc=True)
            original_end = datetime.fromisoformat(base["end"].replace("Z", "+00:00")) if base.get("end") else dtstart + timedelta(hours=1)
            if original_end.tzinfo is None: original_end = original_end.replace(tzinfo=ROME)
            duration = original_end - dtstart
            out = []
            for occ in occs[:2000]:
                z = dict(base); z["start"] = occ.isoformat(); z["end"] = (occ + duration).isoformat(); z["key"] = f"manual:{base['id']}:{occ.isoformat()}"; z["recurrence_instance"] = True
                out.append(z)
            return out
        except Exception:
            return [base]

    @router.get("/integration-state")
    async def integration_state(current=Depends(deps.require_password_current)):
        migration = await db.settings.find_one({"_id": "notion_migration"}) or {}
        return {"initial_migration_completed": bool(migration.get("completed"))}

    @router.get("/resources")
    async def list_resources(current=Depends(deps.require_password_current)):
        return {"items": [_clean(x) for x in await all_resources()]}

    @router.post("/resources")
    async def create_resource(body: AnyBody, current=Depends(deps.require_admin)):
        data = body.model_dump(); name = str(data.get("name") or "").strip()
        if not name: raise HTTPException(400, "Nome calendario/persona obbligatorio")
        if await db.calendar_resources.find_one({"name": {"$regex": f"^{re.escape(name)}$", "$options": "i"}, "active": {"$ne": False}}):
            raise HTTPException(409, "Calendario già presente")
        now = _now(); doc = {**data, "id": str(uuid.uuid4()), "name": name, "color": data.get("color") or "#64748b", "active": True, "created_at": now, "updated_at": now, "created_by": current.get("username")}
        await db.calendar_resources.insert_one(doc); return _clean(doc)

    @router.put("/resources/{resource_id}")
    async def update_resource(resource_id: str, body: AnyBody, current=Depends(deps.require_admin)):
        data = body.model_dump(); data["updated_at"] = _now(); data.pop("id", None)
        await db.calendar_resources.update_one({"id": resource_id}, {"$set": data})
        row = await db.calendar_resources.find_one({"id": resource_id})
        if not row: raise HTTPException(404, "Calendario non trovato")
        return _clean(row)

    @router.delete("/resources/{resource_id}")
    async def delete_resource(resource_id: str, current=Depends(deps.require_admin)):
        await db.calendar_resources.update_one({"id": resource_id}, {"$set": {"active": False, "updated_at": _now()}})
        return {"ok": True}

    @router.get("/events")
    async def events(start: str = Query(...), end: str = Query(...), resource_id: Optional[str] = None, category: Optional[str] = None, current=Depends(deps.require_password_current)):
        try:
            start_dt = datetime.fromisoformat(start.replace("Z", "+00:00")); end_dt = datetime.fromisoformat(end.replace("Z", "+00:00"))
            if start_dt.tzinfo is None: start_dt = start_dt.replace(tzinfo=ROME)
            if end_dt.tzinfo is None: end_dt = end_dt.replace(tzinfo=ROME)
        except Exception:
            raise HTTPException(400, "Intervallo calendario non valido")
        resources = await all_resources()
        manual_q = {"start": {"$lte": end_dt.isoformat()}}
        manual_rows = await db.calendar_events.find(manual_q).to_list(length=20000)
        manual = []
        for row in manual_rows:
            for ev in expand_manual(row, start_dt, end_dt):
                try:
                    eend = datetime.fromisoformat(str(ev.get("end") or ev.get("start")).replace("Z", "+00:00")); estart = datetime.fromisoformat(str(ev.get("start")).replace("Z", "+00:00"))
                    if eend.tzinfo is None: eend = eend.replace(tzinfo=ROME)
                    if estart.tzinfo is None: estart = estart.replace(tzinfo=ROME)
                    if eend < start_dt or estart > end_dt: continue
                except Exception: continue
                ev["key"] = ev.get("key") or f"manual:{ev.get('id')}"; ev["source_type"] = "manual"; ev["source_id"] = ev.get("id")
                rid = (ev.get("resource_ids") or [None])[0]
                rr = next((r for r in resources if r.get("id") == rid), None)
                if rr:
                    ev["resource_name"] = rr.get("name"); ev["resource_color"] = rr.get("color")
                manual.append(ev)
        inst, surveys, assist = await __import__('asyncio').gather(
            synth("Installazione", "crm_installazioni", start, end, resources),
            synth("Sopralluogo", "crm_sopralluoghi", start, end, resources),
            synth("Assistenza", "crm_assistenza", start, end, resources),
        )
        source_keys = {e.get("key") for e in (inst + surveys + assist)}
        manual = [e for e in manual if not e.get("shadow_source_key") or e.get("shadow_source_key") not in source_keys]
        out = manual + inst + surveys + assist

        # Moduli personalizzati calendarizzabili: stessa sorgente, nessuna copia.
        mods = await db.custom_modules.find({"active": {"$ne": False}, "calendar_enabled": True}).to_list(length=500)
        for mod in mods:
            date_key = mod.get("calendar_date_field") or "data"; time_key = mod.get("calendar_time_field") or "ora"; title_key = mod.get("calendar_title_field") or ((mod.get("fields") or [{}])[0].get("key") if mod.get("fields") else "")
            recs = await db.custom_records.find({"module_id": mod.get("id")}).to_list(length=10000)
            for rec in recs:
                data = rec.get("data") or {}; date = str(data.get(date_key) or "")[:10]
                if not date or date < start[:10] or date > end[:10]: continue
                time = str(data.get(time_key) or "09:00")[:5]
                try: sdt = datetime.fromisoformat(f"{date}T{time}:00").replace(tzinfo=ROME)
                except Exception: continue
                title = str(data.get(title_key) or mod.get("name") or "Attività")
                out.append({"key": f"custom:{mod.get('slug')}:{rec.get('id')}", "id": rec.get("id"), "source_type": "custom", "source_id": rec.get("id"), "module_slug": mod.get("slug"), "title": title, "start": sdt.isoformat(), "end": (sdt+timedelta(hours=1)).isoformat(), "all_day": False, "category": mod.get("name"), "status": "", "description": "", "location": "", "resource_ids": [], "resource_name": mod.get("name"), "resource_color": "#64748b"})

        if resource_id:
            out = [e for e in out if resource_id in (e.get("resource_ids") or [])]
        if category:
            out = [e for e in out if str(e.get("category") or "").casefold() == category.casefold()]
        out.sort(key=lambda e: (e.get("start") or "", e.get("title") or ""))
        return {"items": out, "resources": [_clean(r) for r in resources]}

    @router.post("/events")
    async def create_event(body: AnyBody, current=Depends(deps.require_password_current)):
        data = body.model_dump(); title = str(data.get("title") or "").strip()
        if not title or not data.get("start"): raise HTTPException(400, "Titolo e data/ora obbligatori")
        now = _now(); doc = {**data, "id": str(uuid.uuid4()), "title": title, "category": data.get("category") or _classify(title, data.get("description") or ""), "created_at": now, "updated_at": now, "created_by": current.get("username")}
        if not doc.get("end"):
            try: doc["end"] = (datetime.fromisoformat(doc["start"]) + timedelta(hours=1)).isoformat()
            except Exception: doc["end"] = doc["start"]
        await db.calendar_events.insert_one(doc); return _clean(doc)

    @router.put("/events/{event_key:path}")
    async def update_event(event_key: str, body: AnyBody, current=Depends(deps.require_password_current)):
        data = body.model_dump(); data["updated_at"] = _now()
        if event_key.startswith("manual:"):
            eid = event_key.split(":", 2)[1]
            allowed = {k:v for k,v in data.items() if k not in ("id", "source_type", "source_id")}
            await db.calendar_events.update_one({"id": eid}, {"$set": allowed})
            row = await db.calendar_events.find_one({"id": eid});
            if not row: raise HTTPException(404, "Evento non trovato")
            return _clean(row)
        mappings = {"installazione": ("crm_installazioni", "installazioni"), "sopralluogo": ("crm_sopralluoghi", "sopralluoghi"), "assistenza": ("crm_assistenza", "assistenza")}
        prefix, _, rid = event_key.partition(":")
        if prefix in mappings:
            coll_name, _module = mappings[prefix]
            upd = {}
            if data.get("start"):
                try:
                    dt = datetime.fromisoformat(str(data["start"]).replace("Z", "+00:00")).astimezone(ROME); upd["data"] = dt.date().isoformat(); upd["ora"] = dt.strftime("%H:%M")
                except Exception: pass
            for k in ("stato", "tecnico", "tecnico_user_id", "note", "descrizione"):
                if k in data: upd[k] = data[k]
            upd["updated_at"] = _now()
            result = await db[coll_name].update_one({"id": rid}, {"$set": upd})
            if not result.matched_count: raise HTTPException(404, "Attività collegata non trovata")
            return {"ok": True, "source_type": prefix, "source_id": rid}
        raise HTTPException(400, "Tipo evento non modificabile")

    @router.delete("/events/{event_key:path}")
    async def delete_event(event_key: str, current=Depends(deps.require_password_current)):
        if not event_key.startswith("manual:"):
            raise HTTPException(409, "Le attività collegate vanno eliminate dal loro modulo originale")
        eid = event_key.split(":", 2)[1]; await db.calendar_events.delete_one({"id": eid}); return {"ok": True}

    async def try_link_client(ev: Dict[str, Any], clients: Optional[List[Dict[str, Any]]] = None):
        hay = _norm(" ".join([ev.get("title") or "", ev.get("description") or "", ev.get("location") or ""]))
        if not hay: return ev
        clients = clients if clients is not None else await db.crm_clienti.find({}).to_list(length=10000)
        best = None; best_len = 0
        for c in clients:
            names = [c.get("ragione_sociale"), " ".join(x for x in [c.get("nome"), c.get("cognome")] if x), c.get("referente")]
            for name in names:
                nn = _norm(name)
                if len(nn) >= 5 and nn in hay and len(nn) > best_len:
                    best, best_len = c, len(nn)
        if best:
            ev["cliente_id"] = best.get("id")
            site = await db.crm_sedi.find_one({"cliente_id": best.get("id"), "is_primary": True})
            if site: ev["sede_id"] = site.get("id")
        return ev

    async def try_link_operational_source(ev: Dict[str, Any]):
        category = ev.get("category")
        coll_map = {"Installazione": ("crm_installazioni", "installazione"), "Sopralluogo": ("crm_sopralluoghi", "sopralluogo"), "Assistenza": ("crm_assistenza", "assistenza")}
        if category not in coll_map:
            return ev
        date = _date_only(ev.get("start") or "")
        if not date:
            return ev
        coll_name, prefix = coll_map[category]
        q: Dict[str, Any] = {"data": date}
        if ev.get("cliente_id"):
            q["cliente_id"] = ev.get("cliente_id")
        rows = await db[coll_name].find(q).limit(5).to_list(length=5)
        if len(rows) == 1:
            ev["shadow_source_key"] = f"{prefix}:{rows[0].get('id')}"
        return ev

    @router.post("/import/google-ics")
    async def import_google_ics(file: UploadFile = File(...), current=Depends(deps.require_admin)):
        migration = await db.settings.find_one({"_id":"notion_migration"}) or {}
        if migration.get("finalized"):
            raise HTTPException(410, "Importazione esterna disattivata: il gestionale è autonomo")
        raw = await file.read()
        if not raw: raise HTTPException(400, "File vuoto")
        entries: List[tuple[str, bytes]] = []
        if zipfile.is_zipfile(io.BytesIO(raw)):
            with zipfile.ZipFile(io.BytesIO(raw)) as z:
                for name in z.namelist():
                    if name.lower().endswith(".ics"):
                        entries.append((name, z.read(name)))
        elif (file.filename or "").lower().endswith(".ics"):
            entries.append((file.filename or "calendar.ics", raw))
        else:
            raise HTTPException(400, "Carica un file .ics oppure lo ZIP esportato da Google Calendar")
        if not entries: raise HTTPException(400, "Nessun calendario .ics trovato")

        stats = {"calendars": 0, "parsed": 0, "imported": 0, "updated": 0, "skipped_cancelled": 0, "linked_clients": 0, "errors": []}
        per_calendar = []
        clients_cache = await db.crm_clienti.find({}).to_list(length=10000)
        for path, blob in entries:
            name = _calendar_name_from_path(path)
            if _norm(name) in (_norm("Festività in Italia"), _norm("Holidays in Italy")):
                continue
            rr = await resource_for_name(name)
            stats["calendars"] += 1; cstats = {"name": name, "resource": rr.get("name"), "imported": 0, "updated": 0}
            try: text = blob.decode("utf-8-sig", errors="replace")
            except Exception: text = blob.decode(errors="replace")
            for src in _parse_ics(text):
                stats["parsed"] += 1
                if str(src.get("status") or "").upper() == "CANCELLED":
                    stats["skipped_cancelled"] += 1; continue
                if not src.get("dtstart") or not src.get("uid"): continue
                title = src.get("summary") or "Senza titolo"; start = src.get("dtstart"); end = src.get("dtend")
                if not end:
                    try: end = (datetime.fromisoformat(start) + (timedelta(days=1) if src.get("all_day") else timedelta(hours=1))).isoformat()
                    except Exception: end = start
                imported_key = f"{src.get('uid')}|{src.get('recurrence_id') or ''}|{rr.get('id')}"
                doc = {
                    "title": title, "start": start, "end": end, "all_day": bool(src.get("all_day")),
                    "category": _classify(title, src.get("description") or ""), "status": "Importato",
                    "description": src.get("description") or "", "location": src.get("location") or "",
                    "resource_ids": [rr.get("id")], "rrule": src.get("rrule"),
                    "google_uid": src.get("uid"), "google_recurrence_id": src.get("recurrence_id"),
                    "google_import_key": imported_key, "source_origin": "google_ics", "source_calendar": name,
                    "updated_at": _now(),
                }
                before = await db.calendar_events.find_one({"google_import_key": imported_key})
                if not before:
                    doc = await try_link_client(doc, clients_cache)
                    doc = await try_link_operational_source(doc)
                    if doc.get("cliente_id"): stats["linked_clients"] += 1
                    doc.update({"id": str(uuid.uuid4()), "created_at": _now(), "created_by": current.get("username")})
                    await db.calendar_events.insert_one(doc); stats["imported"] += 1; cstats["imported"] += 1
                else:
                    keep_links = {k: before.get(k) for k in ("cliente_id", "sede_id", "commessa_id", "installazione_id", "sopralluogo_id", "assistenza_id") if before.get(k)}
                    doc.update(keep_links)
                    await db.calendar_events.update_one({"id": before.get("id")}, {"$set": doc}); stats["updated"] += 1; cstats["updated"] += 1
            per_calendar.append(cstats)
        stats["per_calendar"] = per_calendar
        return stats

    @router.post("/relink")
    async def relink(current=Depends(deps.require_admin)):
        rows = await db.calendar_events.find({"source_origin": "google_ics", "$or": [{"cliente_id": {"$exists": False}}, {"cliente_id": None}, {"cliente_id": ""}]}).to_list(length=50000)
        linked = 0
        for row in rows:
            ev = await try_link_client(dict(row))
            ev = await try_link_operational_source(ev)
            if ev.get("cliente_id"):
                upd = {"cliente_id": ev.get("cliente_id"), "sede_id": ev.get("sede_id"), "updated_at": _now()}
                if ev.get("shadow_source_key"): upd["shadow_source_key"] = ev.get("shadow_source_key")
                await db.calendar_events.update_one({"id": row.get("id")}, {"$set": upd}); linked += 1
        return {"checked": len(rows), "linked": linked}

    return router
