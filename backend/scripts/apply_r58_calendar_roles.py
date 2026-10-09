from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
path = ROOT / "routes" / "calendar_routes.py"
s = path.read_text(encoding="utf-8")


def must_replace(old: str, new: str, label: str):
    global s
    if old not in s:
        if new in s:
            return
        raise RuntimeError(f"R58 backend: blocco non trovato: {label}")
    s = s.replace(old, new, 1)


if "PERSON_ROLES = (\"Amministrazione\", \"Tecnico\", \"Commerciale\", \"Assistenza\")" not in s:
    must_replace(
        "]\n\nCATEGORY_COLORS = {",
        "]\n\nPERSON_ROLES = (\"Amministrazione\", \"Tecnico\", \"Commerciale\", \"Assistenza\")\n\ndef _normalize_resource_role(value: Any) -> str:\n    raw = str(value or \"\").strip().casefold()\n    for role in PERSON_ROLES:\n        if role.casefold() == raw:\n            return role\n    return \"Tecnico\"\n\nCATEGORY_COLORS = {",
        "role constants",
    )

    must_replace(
        'await db.calendar_resources.insert_one({"id": str(uuid.uuid4()), "name": item["name"], "color": item["color"], "linked_user_id": linked, "active": True, "sort_order": index * 10, "created_at": now, "updated_at": now, "created_by": "bootstrap"})',
        'await db.calendar_resources.insert_one({"id": str(uuid.uuid4()), "name": item["name"], "color": item["color"], "role": _normalize_resource_role(item.get("role")), "linked_user_id": linked, "active": True, "sort_order": index * 10, "created_at": now, "updated_at": now, "created_by": "bootstrap"})',
        "default resource role",
    )

    must_replace(
        '    async def all_resources() -> List[Dict[str, Any]]:\n        await ensure_defaults()\n        return [dict(row) for row in await db.calendar_resources.find({"active": {"$ne": False}}).sort([("sort_order", 1), ("name", 1)]).to_list(length=500)]',
        '    async def all_resources() -> List[Dict[str, Any]]:\n        await ensure_defaults()\n        rows = [dict(row) for row in await db.calendar_resources.find({"active": {"$ne": False}}).sort([("sort_order", 1), ("name", 1)]).to_list(length=500)]\n        for row in rows:\n            role = _normalize_resource_role(row.get("role"))\n            if row.get("role") != role:\n                await db.calendar_resources.update_one({"id": row.get("id")}, {"$set": {"role": role, "updated_at": _now()}})\n                row["role"] = role\n        return rows',
        "resource role migration",
    )

    must_replace(
        'now = _now(); doc = {"id": str(uuid.uuid4()), "name": re.sub(r"^Calendario\\s+", "", str(name), flags=re.I).strip() or "Calendario importato", "color": color or "#64748b", "active": True, "sort_order": 1000, "created_at": now, "updated_at": now, "created_by": "calendar-import"}',
        'now = _now(); doc = {"id": str(uuid.uuid4()), "name": re.sub(r"^Calendario\\s+", "", str(name), flags=re.I).strip() or "Calendario importato", "color": color or "#64748b", "role": "Tecnico", "active": True, "sort_order": 1000, "created_at": now, "updated_at": now, "created_by": "calendar-import"}',
        "imported resource role",
    )

    must_replace(
        '        data = body.model_dump(); name = str(data.get("name") or "").strip()\n        if not name: raise HTTPException(400, "Nome calendario/persona obbligatorio")',
        '        data = body.model_dump(); name = str(data.get("name") or "").strip(); data["role"] = _normalize_resource_role(data.get("role"))\n        if not name: raise HTTPException(400, "Nome calendario/persona obbligatorio")',
        "create resource role",
    )

    must_replace(
        '        data = body.model_dump(); data.pop("id", None); data.pop("source_google_name", None); data["updated_at"] = _now(); result = await db.calendar_resources.update_one({"id": resource_id}, {"$set": data})',
        '        data = body.model_dump(); data.pop("id", None); data.pop("source_google_name", None)\n        if "role" in data: data["role"] = _normalize_resource_role(data.get("role"))\n        data["updated_at"] = _now(); result = await db.calendar_resources.update_one({"id": resource_id}, {"$set": data})',
        "update resource role",
    )

path.write_text(s, encoding="utf-8")
print("[R58 backend] ruoli operativi calendario abilitati.")
