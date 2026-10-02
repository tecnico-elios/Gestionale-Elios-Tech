from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re, uuid

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field


def _now():
    return datetime.now(timezone.utc)


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return value or f"modulo-{uuid.uuid4().hex[:8]}"


class AnyBody(BaseModel):
    model_config = ConfigDict(extra="allow")


class ModuleBody(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    section: str = "amministrazione"
    description: str = ""
    fields: List[Dict[str, Any]] = Field(default_factory=list)
    slug: Optional[str] = None
    active: bool = True
    sort_order: int = 100
    calendar_enabled: bool = False
    calendar_date_field: str = ""
    calendar_time_field: str = ""
    calendar_title_field: str = ""
    access_mode: str = "everyone"  # everyone | custom
    user_permissions: Dict[str, List[str]] = Field(default_factory=dict)


ACTIONS = {"view", "create", "edit", "delete", "export"}


def build_router(db, deps):
    router = APIRouter(prefix="/custom", tags=["Custom modules"])

    def clean(x):
        if not x:
            return x
        d = dict(x)
        d.pop("_id", None)
        for k in ("created_at", "updated_at"):
            if isinstance(d.get(k), datetime):
                d[k] = d[k].isoformat()
        return d

    def _is_admin(current) -> bool:
        return str(current.get("role") or "").lower() == "admin"

    def _allowed(module: Dict[str, Any], current: Dict[str, Any], action: str) -> bool:
        if _is_admin(current):
            return True
        if action not in ACTIONS:
            return False
        # Retrocompatibilità: i moduli precedenti erano accessibili a tutti gli utenti autenticati.
        if (module.get("access_mode") or "everyone") != "custom":
            return True
        uid = str(current.get("_id") or current.get("id") or "")
        perms = module.get("user_permissions") or {}
        user_actions = set(perms.get(uid) or [])
        return action in user_actions

    def _deny_unless(module, current, action):
        if not _allowed(module, current, action):
            raise HTTPException(403, "Non hai il permesso per questa operazione")

    @router.get("/modules")
    async def list_modules(current=Depends(deps.require_password_current)):
        rows = await db.custom_modules.find({"active": {"$ne": False}}).sort([("section", 1), ("sort_order", 1), ("name", 1)]).to_list(length=500)
        return {"items": [clean(x) for x in rows if _allowed(x, current, "view")]}

    @router.get("/modules/all")
    async def list_modules_all(current=Depends(deps.require_admin)):
        rows = await db.custom_modules.find({}).sort([("section", 1), ("sort_order", 1), ("name", 1)]).to_list(length=500)
        return {"items": [clean(x) for x in rows]}

    @router.post("/modules")
    async def create_module(body: ModuleBody, current=Depends(deps.require_admin)):
        name = body.name.strip()
        if not name:
            raise HTTPException(400, "Nome modulo obbligatorio")
        slug = _slugify(body.slug or name)
        if await db.custom_modules.find_one({"slug": slug}):
            slug = f"{slug}-{uuid.uuid4().hex[:4]}"
        now = _now()
        doc = body.model_dump()
        doc.update({"id": str(uuid.uuid4()), "name": name, "slug": slug, "created_at": now, "updated_at": now, "created_by": current.get("username")})
        await db.custom_modules.insert_one(doc)
        return clean(doc)

    @router.put("/modules/{module_id}")
    async def update_module(module_id: str, body: ModuleBody, current=Depends(deps.require_admin)):
        old = await db.custom_modules.find_one({"id": module_id})
        if not old:
            raise HTTPException(404, "Modulo non trovato")
        data = body.model_dump()
        data["name"] = body.name.strip()
        data["slug"] = old.get("slug") or _slugify(body.slug or body.name)
        data["updated_at"] = _now()
        await db.custom_modules.update_one({"id": module_id}, {"$set": data})
        return clean(await db.custom_modules.find_one({"id": module_id}))

    @router.delete("/modules/{module_id}")
    async def archive_module(module_id: str, current=Depends(deps.require_admin)):
        await db.custom_modules.update_one({"id": module_id}, {"$set": {"active": False, "updated_at": _now()}})
        return {"ok": True}

    async def by_slug(slug: str):
        m = await db.custom_modules.find_one({"slug": slug, "active": {"$ne": False}})
        if not m:
            raise HTTPException(404, "Modulo non trovato")
        return m

    @router.get("/{slug}")
    async def module_with_records(slug: str, current=Depends(deps.require_password_current)):
        m = await by_slug(slug)
        _deny_unless(m, current, "view")
        rows = await db.custom_records.find({"module_id": m["id"]}).sort("created_at", -1).to_list(length=5000)
        return {"module": clean(m), "items": [clean(x) for x in rows]}

    @router.post("/{slug}")
    async def create_record(slug: str, body: AnyBody, current=Depends(deps.require_password_current)):
        m = await by_slug(slug)
        _deny_unless(m, current, "create")
        now = _now()
        payload = body.model_dump()
        doc = {"id": str(uuid.uuid4()), "module_id": m["id"], "data": payload, "created_at": now, "updated_at": now, "created_by": current.get("username")}
        await db.custom_records.insert_one(doc)
        return clean(doc)

    @router.put("/{slug}/{record_id}")
    async def update_record(slug: str, record_id: str, body: AnyBody, current=Depends(deps.require_password_current)):
        m = await by_slug(slug)
        _deny_unless(m, current, "edit")
        if not await db.custom_records.find_one({"id": record_id, "module_id": m["id"]}):
            raise HTTPException(404, "Record non trovato")
        await db.custom_records.update_one({"id": record_id, "module_id": m["id"]}, {"$set": {"data": body.model_dump(), "updated_at": _now(), "updated_by": current.get("username")}})
        return clean(await db.custom_records.find_one({"id": record_id}))

    @router.delete("/{slug}/{record_id}")
    async def delete_record(slug: str, record_id: str, current=Depends(deps.require_password_current)):
        m = await by_slug(slug)
        _deny_unless(m, current, "delete")
        await db.custom_records.delete_one({"id": record_id, "module_id": m["id"]})
        return {"ok": True}

    return router
