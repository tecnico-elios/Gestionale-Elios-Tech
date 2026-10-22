from __future__ import annotations
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional
import re, uuid

from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from fastapi.responses import FileResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator


def _now():
    return datetime.now(timezone.utc)


def _slugify(value: str) -> str:
    value = re.sub(r"[^a-zA-Z0-9]+", "-", (value or "").strip().lower()).strip("-")
    return value or f"modulo-{uuid.uuid4().hex[:8]}"


VALID_SECTIONS = {"principale", "amministrazione", "tecnico", "gestione", "sistema"}


def _normalize_section(value: Any, *, allow_principale: bool = False) -> str:
    section = str(value or "amministrazione").strip().lower()
    if section == "commerciale":
        section = "amministrazione"
    allowed = VALID_SECTIONS if allow_principale else VALID_SECTIONS - {"principale"}
    return section if section in allowed else "amministrazione"


class AnyBody(BaseModel):
    model_config = ConfigDict(extra="allow")


class ModuleBody(BaseModel):
    model_config = ConfigDict(extra="allow")
    name: str
    section: str = "amministrazione"
    fields: List[Dict[str, Any]] = Field(default_factory=list)
    slug: Optional[str] = None
    active: bool = True
    sort_order: int = 100

    @field_validator("section", mode="before")
    @classmethod
    def normalize_section(cls, value):
        return _normalize_section(value)


DEFAULT_UI_LISTS = {
    "calendar_categories": ["Installazione", "Sopralluogo", "Assistenza", "Riunione", "Formazione", "Attività", "Altro"],
    "calendar_statuses": ["Da confermare", "Confermato", "In corso", "Completato", "Annullato"],
    "calendar_priorities": ["Bassa", "Normale", "Alta", "Urgente"],
    "client_statuses": ["Prospect", "Attivo", "Da ricontattare", "Sospeso", "Chiuso"],
    "payment_methods": ["Acquisto", "Cofidis", "Noleggio Grenke", "DLL", "Italfinance", "Sella", "Fastrent", "PEAC", "Altro finanziamento / noleggio"],
    "order_finance_statuses": ["Da preparare", "Da inviare", "Inviata", "In istruttoria", "Integrazione richiesta", "Approvata", "Respinta", "Annullata", "Erogata / Contratto attivo"],
    "order_admin_statuses": ["Da fatturare", "Fatturato", "Saldo parziale", "Saldato"],
    "order_logistic_statuses": ["Da preparare", "Materiale parziale", "Materiale disponibile", "Picking", "Pronto alla spedizione", "Spedito", "Consegnato"],
    "order_installation_statuses": ["Da valutare", "Sopralluogo necessario", "Da programmare", "Programmata", "In corso", "Sospesa", "Completata"],
    "order_line_types": ["materiale", "servizio", "installazione", "progettazione", "trasporto", "manodopera"],
    "quote_statuses": ["In preparazione", "Inviato", "Accettato", "Rifiutato"],
    "job_statuses": ["BOZZA", "CONFERMATA", "DA PREPARARE", "IN PICKING", "PRONTA", "SPEDITA PARZIALMENTE", "SPEDITA", "INSTALLATA", "CHIUSA"],
    "installation_statuses": ["Da programmare", "Programmata", "In corso", "Sospesa", "Completata", "Annullata"],
    "assistance_statuses": ["Aperta", "In lavorazione", "In attesa", "Risolta", "Chiusa"],
}


DEFAULT_NAVIGATION = [
    {"key": "dashboard", "label": "Dashboard", "section": "principale", "active": True, "sort_order": 10},
    {"key": "calendar", "label": "Calendario", "section": "principale", "active": True, "sort_order": 20},
    {"key": "ordini_clienti", "label": "Clienti / Ordini", "section": "amministrazione", "active": True, "sort_order": 10},
    {"key": "commesse", "label": "Commesse", "section": "amministrazione", "active": True, "sort_order": 20},
    {"key": "fatturato", "label": "Fatturato", "section": "amministrazione", "active": True, "sort_order": 30},
    {"key": "wallbox", "label": "Wallbox", "section": "amministrazione", "active": True, "sort_order": 40},
    {"key": "report", "label": "Report", "section": "amministrazione", "active": True, "sort_order": 50},
    {"key": "sopralluoghi", "label": "Sopralluoghi", "section": "tecnico", "active": True, "sort_order": 10},
    {"key": "preventivi", "label": "Preventivi", "section": "tecnico", "active": True, "sort_order": 20},
    {"key": "installazioni", "label": "Installazioni", "section": "tecnico", "active": True, "sort_order": 30},
    {"key": "assistenza", "label": "Assistenza", "section": "tecnico", "active": True, "sort_order": 40},
    {"key": "inventario", "label": "Magazzino Elios Tech", "section": "gestione", "active": True, "sort_order": 10},
    {"key": "magazzino_verona", "label": "Magazzino Verona", "section": "gestione", "active": True, "sort_order": 20},
    {"key": "trasferimenti", "label": "Trasferimenti", "section": "gestione", "active": True, "sort_order": 30},
    {"key": "arrivi", "label": "Arrivi", "section": "gestione", "active": True, "sort_order": 40},
    {"key": "movimenti", "label": "Movimenti", "section": "gestione", "active": True, "sort_order": 50},
    {"key": "anomalie", "label": "Anomalie", "section": "gestione", "active": True, "sort_order": 60},
    {"key": "ai", "label": "Assistente AI", "section": "sistema", "active": True, "sort_order": 10},
]


# Moduli generati in passato dall'import universale Notion che non devono più
# comparire né conservare dati nel gestionale. Le funzioni operative native
# (Magazzino Elios Tech, Magazzino Verona, Arrivi, Movimenti, ecc.) NON sono coinvolte.
RETIRED_IMPORT_TITLES = {
    "archivio pagine importate",
    "goals tracker",
    "inventario",
    "inventory receipts",
    "inventory tracker",
    "people",
    "preventivi",
}
RETIRED_IMPORT_PREFIXES = ("fonte 278a9b09", "fonte 471a9b09")
RETIRED_IMPORT_SLUGS = {
    "archivio-pagine-importate",
    "import-goals-tracker",
    "import-inventario",
    "import-inventory-receipts",
    "import-inventory-tracker",
    "import-people",
    "import-preventivi",
    "preventivi",
}


def _normalized_title(value: Any) -> str:
    return re.sub(r"\s+", " ", str(value or "").strip()).casefold()


def _is_retired_import(value: Any, slug: Any = None) -> bool:
    title = _normalized_title(value)
    slug_value = str(slug or "").strip().casefold()
    return (
        title in RETIRED_IMPORT_TITLES
        or any(title.startswith(prefix) for prefix in RETIRED_IMPORT_PREFIXES)
        or slug_value in RETIRED_IMPORT_SLUGS
        or slug_value.startswith("import-fonte-278a9b09")
        or slug_value.startswith("import-fonte-471a9b09")
    )


def build_router(db, deps):
    router = APIRouter(prefix="/custom", tags=["Custom modules"])

    def clean(x):
        if not x:
            return x
        d = dict(x)
        d.pop("_id", None)
        if "section" in d:
            d["section"] = _normalize_section(d.get("section"), allow_principale=True)
        for k in ("created_at", "updated_at"):
            if isinstance(d.get(k), datetime):
                d[k] = d[k].isoformat()
        return d

    async def _purge_retired_import_artifacts() -> Dict[str, int]:
        """Rimuove definitivamente i vecchi moduli Notion indicati dall'utente.

        La pulizia è idempotente e viene eseguita quando il menu/configuratore
        carica i moduli, così elimina anche eventuali ricreazioni da import legacy.
        """
        result = {"modules": 0, "records": 0, "attachments": 0, "archive_records": 0, "sources": 0}
        modules = await db.custom_modules.find({}).to_list(length=2000)
        retired = [m for m in modules if _is_retired_import(m.get("name"), m.get("slug"))]
        module_ids = [m.get("id") for m in retired if m.get("id")]

        if module_ids:
            attachments = await db.custom_attachments.find({"module_id": {"$in": module_ids}}).to_list(length=10000)
            if attachments:
                from pathlib import Path
                for attachment in attachments:
                    path = Path(str(attachment.get("stored_path") or ""))
                    if path.exists() and path.is_file():
                        try:
                            path.unlink()
                        except OSError:
                            pass
            result["attachments"] = int((await db.custom_attachments.delete_many({"module_id": {"$in": module_ids}})).deleted_count or 0)
            result["records"] = int((await db.custom_records.delete_many({"module_id": {"$in": module_ids}})).deleted_count or 0)
            result["modules"] = int((await db.custom_modules.delete_many({"id": {"$in": module_ids}})).deleted_count or 0)

        # Elimina anche l'archivio tecnico della migrazione per le stesse fonti.
        source_rows = await db.migration_sources.find({}).to_list(length=5000)
        retired_source_ids = {
            str(row.get("source_id"))
            for row in source_rows
            if row.get("source_id") and _is_retired_import(row.get("title"))
        }
        archive_rows = await db.migration_archive.find({}, {"source_id": 1, "source_title": 1}).to_list(length=20000)
        retired_source_ids.update(
            str(row.get("source_id"))
            for row in archive_rows
            if row.get("source_id") and _is_retired_import(row.get("source_title"))
        )
        if retired_source_ids:
            ids = list(retired_source_ids)
            result["archive_records"] = int((await db.migration_archive.delete_many({"source_id": {"$in": ids}})).deleted_count or 0)
            result["sources"] = int((await db.migration_sources.delete_many({"source_id": {"$in": ids}})).deleted_count or 0)
        return result

    def module_visible(m: Dict[str, Any], current: Dict[str, Any]) -> bool:
        if current.get("role") == "admin":
            return True
        roles = m.get("visible_roles")
        users = m.get("visible_usernames")
        if isinstance(roles, list) and roles and current.get("role") not in roles:
            return False
        if isinstance(users, list) and users and current.get("username") not in users:
            return False
        return True

    def require_module_action(m: Dict[str, Any], current: Dict[str, Any], action: str):
        if not module_visible(m, current):
            raise HTTPException(403, "Modulo non disponibile per questo utente")
        if m.get(f"allow_{action}") is False:
            raise HTTPException(403, f"Operazione {action} disattivata per questo modulo")

    @router.get("/config/lists")
    async def get_configurable_lists(current=Depends(deps.require_password_current)):
        doc = await db.settings.find_one({"_id": "configurable_lists"}) or {}
        values = dict(DEFAULT_UI_LISTS)
        for k, v in (doc.get("values") or {}).items():
            if k not in DEFAULT_UI_LISTS or not isinstance(v, list):
                continue
            cleaned = []
            for item in v:
                item = str(item).strip()
                if k == "calendar_categories" and item.casefold() == "commerciale":
                    continue
                if item and item not in cleaned:
                    cleaned.append(item)
            if cleaned:
                values[k] = cleaned
        return {"values": values, "updated_at": clean(doc).get("updated_at") if doc else None}

    @router.put("/config/lists")
    async def put_configurable_lists(body: AnyBody, current=Depends(deps.require_admin)):
        raw = body.model_dump().get("values") or body.model_dump()
        values = {}
        for k, default in DEFAULT_UI_LISTS.items():
            v = raw.get(k, default) if isinstance(raw, dict) else default
            if not isinstance(v, list):
                raise HTTPException(400, f"{k}: elenco non valido")
            cleaned = []
            for item in v:
                item = str(item).strip()
                if k == "calendar_categories" and item.casefold() == "commerciale":
                    continue
                if item and item not in cleaned:
                    cleaned.append(item)
            if not cleaned:
                raise HTTPException(400, f"{k}: inserisci almeno una voce")
            values[k] = cleaned
        await db.settings.update_one(
            {"_id": "configurable_lists"},
            {"$set": {"values": values, "updated_at": _now(), "updated_by": current.get("username")}},
            upsert=True,
        )
        return {"values": values}

    @router.get("/config/navigation")
    async def get_navigation_config(current=Depends(deps.require_password_current)):
        await _purge_retired_import_artifacts()
        doc = await db.settings.find_one({"_id": "navigation_config"}) or {}
        saved = {str(x.get("key")): x for x in (doc.get("items") or []) if isinstance(x, dict) and x.get("key")}
        items = []
        repaired = False
        for default in DEFAULT_NAVIGATION:
            item = dict(default)
            item.update(saved.get(default["key"], {}))
            item["section"] = _normalize_section(item.get("section"), allow_principale=True)
            # Migrazione R49: una vecchia configurazione aveva rinominato anche
            # Trasferimenti in "Movimenti", creando due voci indistinguibili.
            if default["key"] == "trasferimenti" and _normalized_title(item.get("label")) == "movimenti":
                item["label"] = "Trasferimenti"
                repaired = True
            items.append(item)
        items.sort(key=lambda x: (str(x.get("section") or ""), int(x.get("sort_order") or 100), str(x.get("label") or "")))
        if repaired:
            await db.settings.update_one(
                {"_id": "navigation_config"},
                {"$set": {"items": [{k: x.get(k) for k in ("key", "label", "section", "active", "sort_order")} for x in items], "updated_at": _now(), "migration": "r49-fix-trasferimenti"}},
                upsert=True,
            )
        return {"items": items}

    @router.put("/config/navigation")
    async def put_navigation_config(body: AnyBody, current=Depends(deps.require_admin)):
        raw = body.model_dump().get("items") or []
        if not isinstance(raw, list):
            raise HTTPException(400, "Configurazione menu non valida")
        allowed = {x["key"] for x in DEFAULT_NAVIGATION}
        cleaned = []
        for row in raw:
            if not isinstance(row, dict) or row.get("key") not in allowed:
                continue
            label = str(row.get("label") or row["key"]).strip()[:80]
            if row["key"] == "trasferimenti" and _normalized_title(label) == "movimenti":
                label = "Trasferimenti"
            cleaned.append({
                "key": row["key"],
                "label": label,
                "section": _normalize_section(row.get("section"), allow_principale=True),
                "active": bool(row.get("active", True)),
                "sort_order": int(row.get("sort_order") or 100),
            })
        await db.settings.update_one(
            {"_id": "navigation_config"},
            {"$set": {"items": cleaned, "updated_at": _now(), "updated_by": current.get("username")}},
            upsert=True,
        )
        return await get_navigation_config(current)

    @router.get("/modules")
    async def list_modules(current=Depends(deps.require_password_current)):
        await _purge_retired_import_artifacts()
        rows = await db.custom_modules.find({"active": {"$ne": False}}).sort([("section", 1), ("sort_order", 1), ("name", 1)]).to_list(length=500)
        return {"items": [clean(x) for x in rows if module_visible(x, current)]}

    @router.get("/modules/all")
    async def list_modules_all(current=Depends(deps.require_admin)):
        await _purge_retired_import_artifacts()
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
        doc["section"] = _normalize_section(doc.get("section"))
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
        data["section"] = _normalize_section(data.get("section"))
        data["slug"] = old.get("slug") or _slugify(body.slug or body.name)
        data["updated_at"] = _now()
        await db.custom_modules.update_one({"id": module_id}, {"$set": data})
        return clean(await db.custom_modules.find_one({"id": module_id}))

    @router.delete("/modules/{module_id}")
    async def archive_module(module_id: str, current=Depends(deps.require_admin)):
        await db.custom_modules.update_one({"id": module_id}, {"$set": {"active": False, "updated_at": _now()}})
        return {"ok": True}

    @router.post("/modules/{module_id}/duplicate")
    async def duplicate_module(module_id: str, current=Depends(deps.require_admin)):
        old = await db.custom_modules.find_one({"id": module_id})
        if not old:
            raise HTTPException(404, "Modulo non trovato")
        doc = {k: v for k, v in old.items() if k not in ("_id", "id", "slug", "created_at", "updated_at", "created_by", "source_notion_id")}
        doc["id"] = str(uuid.uuid4())
        doc["name"] = f"{old.get('name') or 'Modulo'} - copia"
        doc["section"] = _normalize_section(doc.get("section"))
        base = _slugify(doc["name"])
        slug = base
        i = 2
        while await db.custom_modules.find_one({"slug": slug}):
            slug = f"{base}-{i}"
            i += 1
        doc["slug"] = slug
        doc["active"] = True
        doc["created_at"] = _now()
        doc["updated_at"] = _now()
        doc["created_by"] = current.get("username")
        await db.custom_modules.insert_one(doc)
        return clean(doc)

    @router.delete("/modules/{module_id}/permanent")
    async def permanently_delete_module(module_id: str, current=Depends(deps.require_admin)):
        old = await db.custom_modules.find_one({"id": module_id})
        if not old:
            raise HTTPException(404, "Modulo non trovato")
        attachments = await db.custom_attachments.find({"module_id": module_id}).to_list(length=10000)
        if attachments:
            from pathlib import Path
            for attachment in attachments:
                path = Path(str(attachment.get("stored_path") or ""))
                if path.exists() and path.is_file():
                    try:
                        path.unlink()
                    except OSError:
                        pass
        await db.custom_attachments.delete_many({"module_id": module_id})
        await db.custom_records.delete_many({"module_id": module_id})
        await db.custom_modules.delete_one({"id": module_id})
        return {"ok": True, "deleted_records": True, "deleted_attachments": True}

    async def by_slug(slug: str, current: Dict[str, Any]):
        m = await db.custom_modules.find_one({"slug": slug, "active": {"$ne": False}})
        if not m:
            raise HTTPException(404, "Modulo non trovato")
        if not module_visible(m, current):
            raise HTTPException(403, "Modulo non disponibile per questo utente")
        return m

    @router.get("/attachment/{attachment_id}")
    async def open_attachment(attachment_id: str, current=Depends(deps.require_password_current)):
        doc = await db.custom_attachments.find_one({"id": attachment_id})
        if not doc:
            raise HTTPException(404, "Allegato non trovato")
        from pathlib import Path
        path = Path(doc.get("stored_path") or "")
        if not path.exists():
            raise HTTPException(404, "File non disponibile sul server")
        return FileResponse(path, media_type=doc.get("content_type") or "application/octet-stream", filename=doc.get("filename") or path.name)

    @router.get("/{slug}")
    async def module_with_records(slug: str, current=Depends(deps.require_password_current)):
        m = await by_slug(slug, current)
        rows = await db.custom_records.find({"module_id": m["id"]}).sort("created_at", -1).to_list(length=5000)
        return {"module": clean(m), "items": [clean(x) for x in rows]}

    @router.post("/{slug}")
    async def create_record(slug: str, body: AnyBody, current=Depends(deps.require_password_current)):
        m = await by_slug(slug, current)
        require_module_action(m, current, "create")
        now = _now()
        payload = body.model_dump()
        doc = {"id": str(uuid.uuid4()), "module_id": m["id"], "data": payload, "created_at": now, "updated_at": now, "created_by": current.get("username")}
        await db.custom_records.insert_one(doc)
        return clean(doc)

    @router.put("/{slug}/{record_id}")
    async def update_record(slug: str, record_id: str, body: AnyBody, current=Depends(deps.require_password_current)):
        m = await by_slug(slug, current)
        require_module_action(m, current, "edit")
        if not await db.custom_records.find_one({"id": record_id, "module_id": m["id"]}):
            raise HTTPException(404, "Record non trovato")
        await db.custom_records.update_one({"id": record_id, "module_id": m["id"]}, {"$set": {"data": body.model_dump(), "updated_at": _now(), "updated_by": current.get("username")}})
        return clean(await db.custom_records.find_one({"id": record_id}))

    @router.post("/{slug}/{record_id}/file/{field_key}")
    async def upload_record_file(slug: str, record_id: str, field_key: str, file: UploadFile = File(...), current=Depends(deps.require_password_current)):
        m = await by_slug(slug, current)
        require_module_action(m, current, "edit")
        rec = await db.custom_records.find_one({"id": record_id, "module_id": m["id"]})
        if not rec:
            raise HTTPException(404, "Record non trovato")
        field = next((f for f in (m.get("fields") or []) if f.get("key") == field_key), None)
        if not field or field.get("type") != "file":
            raise HTTPException(400, "Campo file non valido")
        content = await file.read(25 * 1024 * 1024 + 1)
        if len(content) > 25 * 1024 * 1024:
            raise HTTPException(413, "File troppo grande (max 25 MB)")
        from pathlib import Path
        import re as _re
        root = Path(__file__).resolve().parent.parent / "uploads" / "custom" / m["id"] / record_id
        root.mkdir(parents=True, exist_ok=True)
        safe = _re.sub(r"[^A-Za-z0-9._() -]+", "_", Path(file.filename or "documento").name).strip(" .")[:180] or "documento"
        aid = str(uuid.uuid4())
        ext = Path(safe).suffix[:12]
        path = root / f"{aid}{ext}"
        path.write_bytes(content)
        doc = {"id": aid, "module_id": m["id"], "record_id": record_id, "field_key": field_key, "filename": safe, "stored_path": str(path), "content_type": file.content_type or "application/octet-stream", "size": len(content), "created_at": _now(), "created_by": current.get("username"), "import_source": "gestionale"}
        await db.custom_attachments.insert_one(doc)
        data = dict(rec.get("data") or {})
        current_files = data.get(field_key) if isinstance(data.get(field_key), list) else []
        data[field_key] = current_files + [{"id": aid, "name": safe, "size": len(content)}]
        await db.custom_records.update_one({"id": record_id}, {"$set": {"data": data, "updated_at": _now(), "updated_by": current.get("username")}})
        return {"ok": True, "attachment": {"id": aid, "name": safe, "size": len(content)}}

    @router.delete("/attachment/{attachment_id}")
    async def delete_attachment(attachment_id: str, current=Depends(deps.require_password_current)):
        doc = await db.custom_attachments.find_one({"id": attachment_id})
        if not doc:
            raise HTTPException(404, "Allegato non trovato")
        rec = await db.custom_records.find_one({"id": doc.get("record_id"), "module_id": doc.get("module_id")})
        if rec:
            data = dict(rec.get("data") or {})
            key = doc.get("field_key")
            vals = data.get(key) if isinstance(data.get(key), list) else []
            data[key] = [x for x in vals if not isinstance(x, dict) or x.get("id") != attachment_id]
            await db.custom_records.update_one({"id": rec.get("id")}, {"$set": {"data": data, "updated_at": _now()}})
        from pathlib import Path
        path = Path(doc.get("stored_path") or "")
        await db.custom_attachments.delete_one({"id": attachment_id})
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        return {"ok": True}

    @router.delete("/{slug}/{record_id}")
    async def delete_record(slug: str, record_id: str, current=Depends(deps.require_password_current)):
        m = await by_slug(slug, current)
        require_module_action(m, current, "delete")
        await db.custom_records.delete_one({"id": record_id, "module_id": m["id"]})
        return {"ok": True}

    return router
