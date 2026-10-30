"""Runtime performance layer for Gestionale Elios Tech.

This module is intentionally isolated from the legacy server module so the
performance refactor can be introduced incrementally and safely.  It replaces
only the hottest read routes, adds bounded in-memory caching for semi-static
lookups, installs indexes used by the list views, and logs slow requests.

The existing application already uses Motor/AsyncIOMotorClient.  The main
performance problems addressed here are therefore query shape, unbounded list
reads, Python-side filtering, N+1 queries, and side effects inside GET routes.
"""
from __future__ import annotations

import asyncio
import logging
import math
import os
import re
import time
from collections import OrderedDict
from typing import Any, Awaitable, Callable, Dict, Optional

from fastapi import Depends, HTTPException, Query, Request

logger = logging.getLogger(__name__)

DEFAULT_PAGE_SIZE = max(1, min(int(os.environ.get("CRM_PAGE_SIZE", "50")), 200))
MAX_PAGE_SIZE = max(DEFAULT_PAGE_SIZE, min(int(os.environ.get("CRM_MAX_PAGE_SIZE", "200")), 500))
MONGO_QUERY_MAX_MS = max(500, int(os.environ.get("MONGO_QUERY_MAX_MS", "5000")))
SLOW_REQUEST_MS = max(100, int(os.environ.get("SLOW_REQUEST_MS", "1000")))
CACHE_MAX_ENTRIES = max(32, int(os.environ.get("READ_CACHE_MAX_ENTRIES", "512")))

RESOURCE_COLLECTIONS: Dict[str, str] = {
    "clienti": "crm_clienti",
    "contatti": "crm_contatti",
    "sedi": "crm_sedi",
    "sopralluoghi": "crm_sopralluoghi",
    "preventivi": "crm_preventivi",
    "ordini-clienti": "crm_ordini_clienti",
    "installazioni": "crm_installazioni",
    "interventi-tecnici": "crm_interventi_tecnici",
    "assistenza": "crm_assistenza",
}

# Search only fields that are actually useful in the corresponding list view.
# Escaping the input prevents arbitrary/expensive regex patterns from clients.
SEARCH_FIELDS: Dict[str, tuple[str, ...]] = {
    "clienti": (
        "ragione_sociale", "nome", "cognome", "email", "telefono",
        "partita_iva", "codice_fiscale", "comune", "provincia", "referente",
    ),
    "contatti": ("nome", "cognome", "email", "telefono", "ruolo"),
    "sedi": ("nome", "indirizzo", "comune", "provincia", "cap", "telefono"),
    "sopralluoghi": ("nominativo", "cliente", "sede", "indirizzo", "stato", "note"),
    "preventivi": ("numero", "nominativo", "cliente", "stato", "stato_commerciale", "note"),
    "ordini-clienti": ("numero", "nominativo", "cliente", "stato", "stato_commerciale"),
    "installazioni": ("nominativo", "cliente_nome", "calendar_title", "tecnico", "stato", "note"),
    "interventi-tecnici": ("nominativo", "cliente", "tecnico", "stato", "note"),
    "assistenza": ("nominativo", "cliente", "stato", "note", "descrizione"),
}

# Exclusion projection preserves backward compatibility with the current React
# pages while preventing accidental transfer of large internal/raw payloads.
# Detail endpoints remain responsible for returning heavy content when needed.
LIST_PROJECTION: Dict[str, int] = {
    "_id": 0,
    "raw_payload": 0,
    "raw_response": 0,
    "provider_payload": 0,
    "debug_payload": 0,
    "binary_data": 0,
    "pdf_bytes": 0,
}


class AsyncTTLCache:
    """Small async TTL cache with per-key single-flight protection.

    It avoids the cache-stampede problem: when many PWA requests hit an expired
    lookup simultaneously, only one coroutine refreshes MongoDB while the
    others await the same key lock.
    """

    def __init__(self, max_entries: int = CACHE_MAX_ENTRIES) -> None:
        self._items: "OrderedDict[str, tuple[float, Any]]" = OrderedDict()
        self._locks: Dict[str, asyncio.Lock] = {}
        self._lock = asyncio.Lock()
        self._max_entries = max_entries

    async def get(self, key: str) -> Any:
        now = time.monotonic()
        async with self._lock:
            item = self._items.get(key)
            if item is None:
                return None
            expires_at, value = item
            if expires_at <= now:
                self._items.pop(key, None)
                return None
            self._items.move_to_end(key)
            return value

    async def set(self, key: str, value: Any, ttl: float) -> None:
        async with self._lock:
            self._items[key] = (time.monotonic() + max(0.1, ttl), value)
            self._items.move_to_end(key)
            while len(self._items) > self._max_entries:
                self._items.popitem(last=False)

    async def invalidate(self, prefix: Optional[str] = None) -> None:
        async with self._lock:
            if prefix is None:
                self._items.clear()
                return
            for key in list(self._items):
                if key.startswith(prefix):
                    self._items.pop(key, None)

    async def get_or_set(
        self,
        key: str,
        ttl: float,
        factory: Callable[[], Awaitable[Any]],
    ) -> Any:
        hit = await self.get(key)
        if hit is not None:
            return hit

        async with self._lock:
            key_lock = self._locks.setdefault(key, asyncio.Lock())

        async with key_lock:
            hit = await self.get(key)
            if hit is not None:
                return hit
            value = await factory()
            await self.set(key, value, ttl)
            return value


read_cache = AsyncTTLCache()


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    out.pop("_id", None)
    for key in ("created_at", "updated_at"):
        value = out.get(key)
        if hasattr(value, "isoformat"):
            out[key] = value.isoformat()
    if not out.get("tecnico") and out.get("installatore"):
        out["tecnico"] = out.get("installatore")
    out.pop("installatore", None)
    return out


def _user_cache_key(current: Dict[str, Any]) -> str:
    return str(
        current.get("_id")
        or current.get("id")
        or current.get("username")
        or current.get("email")
        or "anonymous"
    )


def _can_view_all_installations(current: Dict[str, Any], auth_mod: Any) -> bool:
    return bool(
        current.get("role") == getattr(auth_mod, "ROLE_ADMIN", "admin")
        or auth_mod.is_master_user(current)
        or auth_mod.has_permission(current, "installazioni", "view_all")
    )


def _installation_owned_query(current: Dict[str, Any]) -> Dict[str, Any]:
    uid = str(current.get("_id") or current.get("id") or "")
    aliases = [
        str(current.get(k) or "").strip()
        for k in ("username", "full_name", "email")
        if str(current.get(k) or "").strip()
    ]
    clauses: list[Dict[str, Any]] = []
    if uid:
        clauses.append({"tecnico_user_id": uid})
    for alias in aliases:
        clauses.append({"tecnico": {"$regex": f"^{re.escape(alias)}$", "$options": "i"}})
    return {"$or": clauses or [{"tecnico_user_id": "__none__"}]}


def _build_list_query(
    resource: str,
    q: Optional[str],
    include_archived: bool,
    current: Dict[str, Any],
    auth_mod: Any,
) -> Dict[str, Any]:
    clauses: list[Dict[str, Any]] = []

    if resource == "clienti" and not include_archived:
        clauses.append({"archived": {"$ne": True}})

    if resource == "installazioni" and not _can_view_all_installations(current, auth_mod):
        clauses.append(_installation_owned_query(current))

    needle = " ".join((q or "").strip().split())
    if needle:
        regex = {"$regex": re.escape(needle), "$options": "i"}
        fields = SEARCH_FIELDS.get(resource, ())
        if fields:
            clauses.append({"$or": [{field: regex} for field in fields]})

    if not clauses:
        return {}
    if len(clauses) == 1:
        return clauses[0]
    return {"$and": clauses}


async def _enrich_installations(
    db: Any,
    items: list[Dict[str, Any]],
) -> list[Dict[str, Any]]:
    """Batch-load installation relations and eliminate the former N+1 queries."""
    if not items:
        return items

    commessa_ids = {
        str(item.get("commessa_id") or "")
        for item in items
        if item.get("commessa_id")
    }
    cliente_ids = {
        str(item.get("cliente_id") or "")
        for item in items
        if item.get("cliente_id")
    }
    sede_ids = {
        str(item.get("sede_id") or "")
        for item in items
        if item.get("sede_id")
    }

    async def load_commesse() -> list[Dict[str, Any]]:
        if not commessa_ids:
            return []
        return await db.commesse.find(
            {"id": {"$in": list(commessa_ids)}},
            {
                "_id": 0,
                "id": 1,
                "cliente_id": 1,
                "sede_id": 1,
                "cliente": 1,
                "note": 1,
                "righe": 1,
                "servizi": 1,
            },
        ).to_list(length=len(commessa_ids))

    # Client/site ids may also live only on the linked commessa, so load commesse
    # first, then fetch both relation sets concurrently.
    commesse = await load_commesse()
    comm_by_id = {str(x.get("id") or ""): x for x in commesse}
    for comm in commesse:
        if comm.get("cliente_id"):
            cliente_ids.add(str(comm["cliente_id"]))
        if comm.get("sede_id"):
            sede_ids.add(str(comm["sede_id"]))

    async def load_clienti() -> list[Dict[str, Any]]:
        if not cliente_ids:
            return []
        return await db.crm_clienti.find(
            {"id": {"$in": list(cliente_ids)}},
            {"_id": 0, "id": 1, "ragione_sociale": 1, "nome": 1, "cognome": 1, "name": 1},
        ).to_list(length=len(cliente_ids))

    async def load_sedi() -> list[Dict[str, Any]]:
        if not sede_ids:
            return []
        return await db.crm_sedi.find(
            {"id": {"$in": list(sede_ids)}},
            {
                "_id": 0, "id": 1, "nome": 1, "name": 1, "indirizzo": 1,
                "address": 1, "civico": 1, "cap": 1, "comune": 1, "provincia": 1,
            },
        ).to_list(length=len(sede_ids))

    clienti, sedi = await asyncio.gather(load_clienti(), load_sedi())
    client_by_id = {str(x.get("id") or ""): x for x in clienti}
    site_by_id = {str(x.get("id") or ""): x for x in sedi}

    for item in items:
        comm = comm_by_id.get(str(item.get("commessa_id") or "")) or {}
        item["prodotti_da_installare"] = [
            {
                "nome": row.get("product_name") or row.get("descrizione") or "Prodotto",
                "codice": row.get("product_code"),
                "quantita": row.get("qty_richiesta") or row.get("quantity") or 1,
                "seriali": list(dict.fromkeys(
                    (row.get("seriali_prelevati") or []) + (row.get("seriali_spediti") or [])
                )),
            }
            for row in (comm.get("righe") or [])
        ]
        item["attivita_da_eseguire"] = [
            {
                "descrizione": row.get("descrizione") or row.get("product_name") or str(row.get("tipo_riga") or "Servizio"),
                "quantita": row.get("quantity") or row.get("quantita") or 1,
            }
            for row in (comm.get("servizi") or [])
        ]
        item["istruzioni_intervento"] = item.get("istruzioni_intervento") or comm.get("note") or ""

        cliente_id = str(item.get("cliente_id") or comm.get("cliente_id") or "")
        sede_id = str(item.get("sede_id") or comm.get("sede_id") or "")
        cliente = client_by_id.get(cliente_id) or {}
        sede = site_by_id.get(sede_id) or {}

        if cliente:
            full_name = " ".join(x for x in [cliente.get("nome"), cliente.get("cognome")] if x).strip()
            item["cliente_nome"] = cliente.get("ragione_sociale") or full_name or cliente.get("name") or "Cliente"
        item["cliente_nome"] = (
            item.get("cliente_nome")
            or comm.get("cliente")
            or item.get("nominativo")
            or item.get("calendar_title")
            or "Cliente da collegare"
        )

        if sede:
            item["sede_nome"] = sede.get("nome") or sede.get("name") or sede.get("indirizzo") or "Sede"
            addr = " ".join(x for x in [sede.get("indirizzo") or sede.get("address"), sede.get("civico")] if x).strip()
            loc = " ".join(x for x in [sede.get("cap"), sede.get("comune"), sede.get("provincia")] if x).strip()
            item["sede_indirizzo"] = addr
            item["sede_indirizzo_completo"] = ", ".join(x for x in [addr, loc] if x)
            item["sede_comune"] = sede.get("comune") or ""
            item["sede_provincia"] = sede.get("provincia") or ""
            item["sede_cap"] = sede.get("cap") or ""
        item["sede_nome"] = item.get("sede_nome") or item.get("sede") or ""

    return items


def _replace_get_route(app: Any, path: str, endpoint: Callable[..., Awaitable[Any]], *, tags: Optional[list[str]] = None) -> bool:
    old_index: Optional[int] = None
    old_name: Optional[str] = None
    for idx, route in enumerate(app.router.routes):
        if getattr(route, "path", None) == path and "GET" in (getattr(route, "methods", None) or set()):
            old_index = idx
            old_name = getattr(route, "name", None)
            break
    if old_index is None:
        logger.warning("Performance route replacement skipped; route not found: %s", path)
        return False

    app.router.routes.pop(old_index)
    app.add_api_route(path, endpoint, methods=["GET"], name=old_name, tags=tags or ["performance"])
    new_route = app.router.routes.pop()
    app.router.routes.insert(old_index, new_route)
    return True


def _capture_get_endpoint(app: Any, path: str) -> Optional[Callable[..., Awaitable[Any]]]:
    for route in app.router.routes:
        if getattr(route, "path", None) == path and "GET" in (getattr(route, "methods", None) or set()):
            return getattr(route, "endpoint", None)
    return None


def install_request_timing(app: Any) -> None:
    if getattr(app.state, "performance_timing_installed", False):
        return
    app.state.performance_timing_installed = True

    @app.middleware("http")
    async def performance_timing_middleware(request: Request, call_next: Callable[..., Awaitable[Any]]):
        started = time.perf_counter()
        try:
            response = await call_next(request)
            return response
        finally:
            elapsed_ms = (time.perf_counter() - started) * 1000
            if elapsed_ms >= SLOW_REQUEST_MS:
                logger.warning(
                    "SLOW_REQUEST method=%s path=%s elapsed_ms=%.1f query=%s",
                    request.method,
                    request.url.path,
                    elapsed_ms,
                    request.url.query[:500],
                )


def install_performance_routes(app: Any, db: Any, auth_deps: Any, auth_mod: Any) -> None:
    dep = auth_deps.require_password_current

    async def list_records_optimized(
        resource: str,
        q: Optional[str] = Query(default=None, max_length=120),
        include_archived: bool = Query(default=False),
        page: int = Query(default=1, ge=1),
        limit: int = Query(default=DEFAULT_PAGE_SIZE, ge=1, le=MAX_PAGE_SIZE),
        current: Dict[str, Any] = Depends(dep),
    ):
        collection_name = RESOURCE_COLLECTIONS.get(resource)
        if not collection_name:
            raise HTTPException(404, "Risorsa non valida")

        query = _build_list_query(resource, q, include_archived, current, auth_mod)
        collection = db[collection_name]
        skip = (page - 1) * limit

        cursor = (
            collection
            .find(query, LIST_PROJECTION)
            .sort("updated_at", -1)
            .skip(skip)
            .limit(limit)
            .max_time_ms(MONGO_QUERY_MAX_MS)
        )

        docs_task = cursor.to_list(length=limit)
        total_task = collection.count_documents(query, maxTimeMS=MONGO_QUERY_MAX_MS)
        docs, total = await asyncio.gather(docs_task, total_task)

        items = [_clean(doc) for doc in docs]
        if resource == "installazioni":
            # IMPORTANT: no calendar/network sync in GET. Startup/write flows are
            # responsible for synchronization.  Relations are loaded in batches.
            items = await _enrich_installations(db, items)

        pages = math.ceil(total / limit) if total else 0
        return {
            "items": items,
            "count": len(items),
            "total": int(total),
            "page": page,
            "limit": limit,
            "pages": pages,
            "has_more": page < pages,
        }

    async def dashboard_counts_optimized(current: Dict[str, Any] = Depends(dep)):
        cache_key = f"crm:dashboard:{_user_cache_key(current)}"

        async def factory():
            names = list(RESOURCE_COLLECTIONS.items())
            tasks = [db[name].count_documents({}, maxTimeMS=MONGO_QUERY_MAX_MS) for _, name in names]
            tasks.append(db.commesse.count_documents({"stato": {"$ne": "annullata"}}, maxTimeMS=MONGO_QUERY_MAX_MS))
            values = await asyncio.gather(*tasks)
            out = {key: int(values[idx]) for idx, (key, _) in enumerate(names)}
            out["commesse"] = int(values[-1])
            return out

        return await read_cache.get_or_set(cache_key, ttl=10, factory=factory)

    async def lookup_commesse_optimized(current: Dict[str, Any] = Depends(dep)):
        async def factory():
            docs = await (
                db.commesse
                .find(
                    {"stato": {"$ne": "annullata"}},
                    {
                        "_id": 0, "id": 1, "number": 1, "numero": 1,
                        "cliente": 1, "cliente_id": 1, "sede_id": 1,
                        "stato": 1, "updated_at": 1,
                    },
                )
                .sort("updated_at", -1)
                .limit(500)
                .max_time_ms(MONGO_QUERY_MAX_MS)
                .to_list(length=500)
            )
            return {"items": docs, "count": len(docs)}

        return await read_cache.get_or_set("crm:lookup:commesse", ttl=30, factory=factory)

    async def lookup_technicians_optimized(current: Dict[str, Any] = Depends(dep)):
        if not auth_mod.has_permission(current, "installazioni", "create") and not auth_mod.has_permission(current, "installazioni", "edit"):
            raise HTTPException(403, "Non hai il permesso per assegnare tecnici")

        async def factory():
            docs = await (
                db.users
                .find(
                    {"active": True},
                    {"username": 1, "full_name": 1, "email": 1, "role": 1, "permissions": 1},
                )
                .sort("full_name", 1)
                .limit(300)
                .to_list(length=300)
            )
            items = []
            for user in docs:
                if user.get("role") == getattr(auth_mod, "ROLE_TECNICO", "tecnico") or auth_mod.has_permission(user, "installazioni", "edit"):
                    items.append({
                        "id": str(user.get("_id")),
                        "username": user.get("username"),
                        "full_name": user.get("full_name"),
                        "email": user.get("email"),
                        "role": user.get("role"),
                    })
            return {"items": items, "count": len(items)}

        return await read_cache.get_or_set("crm:lookup:technicians", ttl=60, factory=factory)

    _replace_get_route(app, "/api/crm/{resource}", list_records_optimized, tags=["CRM", "performance"])
    _replace_get_route(app, "/api/crm/meta/dashboard", dashboard_counts_optimized, tags=["CRM", "performance"])
    _replace_get_route(app, "/api/crm/lookups/commesse", lookup_commesse_optimized, tags=["CRM", "performance"])
    _replace_get_route(app, "/api/crm/lookups/technicians", lookup_technicians_optimized, tags=["CRM", "performance"])

    # The two analytical endpoints currently materialize very large datasets in
    # Python.  Preserve exact response semantics for now, but shield MongoDB and
    # Uvicorn from repeated refresh storms with a short-lived single-flight cache.
    for path, ttl in (
        ("/api/crm/clienti-summary", 30),
        ("/api/crm/ordini-insights", 30),
    ):
        original = _capture_get_endpoint(app, path)
        if original is None:
            continue

        def make_cached_endpoint(original_endpoint: Callable[..., Awaitable[Any]], route_path: str, route_ttl: int):
            async def cached_endpoint(current: Dict[str, Any] = Depends(dep)):
                key = f"heavy:{route_path}:{_user_cache_key(current)}"

                async def factory():
                    return await original_endpoint(current=current)

                return await read_cache.get_or_set(key, ttl=route_ttl, factory=factory)

            cached_endpoint.__name__ = f"cached_{getattr(original_endpoint, '__name__', 'endpoint')}"
            return cached_endpoint

        _replace_get_route(app, path, make_cached_endpoint(original, path, ttl), tags=["CRM", "performance"])

    async def bootstrap(current: Dict[str, Any] = Depends(dep)):
        user_key = _user_cache_key(current)

        async def factory():
            technicians_task = db.users.find(
                {"active": True},
                {"username": 1, "full_name": 1, "email": 1, "role": 1},
            ).sort("full_name", 1).limit(300).to_list(length=300)
            settings_task = db.settings.find_one(
                {"_id": {"$in": ["features", "app_settings"]}},
                {"_id": 1, "commesse_enabled": 1, "general": 1},
            )
            commesse_task = db.commesse.find(
                {"stato": {"$ne": "annullata"}},
                {"_id": 0, "id": 1, "number": 1, "numero": 1, "cliente": 1, "stato": 1},
            ).sort("updated_at", -1).limit(300).to_list(length=300)
            technicians, settings, commesse = await asyncio.gather(
                technicians_task,
                settings_task,
                commesse_task,
            )
            return {
                "technicians": [
                    {
                        **{k: v for k, v in user.items() if k != "_id"},
                        "id": str(user.get("_id")),
                    }
                    for user in technicians
                ],
                "commesse": commesse,
                "features": {
                    "commesse_enabled": bool((settings or {}).get("commesse_enabled", True)),
                },
                "page_size": DEFAULT_PAGE_SIZE,
                "max_page_size": MAX_PAGE_SIZE,
            }

        return await read_cache.get_or_set(f"bootstrap:{user_key}", ttl=60, factory=factory)

    # New consolidated endpoint for PWA initialization. Existing clients keep
    # working; the frontend can migrate incrementally from scattered lookups.
    app.add_api_route("/api/bootstrap", bootstrap, methods=["GET"], tags=["performance"])


async def ensure_performance_indexes(db: Any) -> None:
    """Create the indexes used by the hot list/filter/sort paths.

    Each index is isolated: one legacy-data conflict must not prevent all other
    performance indexes from being created.
    """
    specs = {
        "crm_clienti": [
            ([('updated_at', -1)], "perf_clienti_updated"),
            ([('archived', 1), ('updated_at', -1)], "perf_clienti_archived_updated"),
            ([('id', 1)], "perf_clienti_id"),
            ([('email', 1)], "perf_clienti_email"),
        ],
        "crm_sedi": [
            ([('updated_at', -1)], "perf_sedi_updated"),
            ([('cliente_id', 1), ('updated_at', -1)], "perf_sedi_cliente_updated"),
            ([('id', 1)], "perf_sedi_id"),
        ],
        "crm_contatti": [
            ([('cliente_id', 1), ('updated_at', -1)], "perf_contatti_cliente_updated"),
            ([('updated_at', -1)], "perf_contatti_updated"),
        ],
        "crm_preventivi": [
            ([('cliente_id', 1), ('updated_at', -1)], "perf_preventivi_cliente_updated"),
            ([('updated_at', -1)], "perf_preventivi_updated"),
            ([('numero', 1)], "perf_preventivi_numero"),
        ],
        "crm_ordini_clienti": [
            ([('cliente_id', 1), ('updated_at', -1)], "perf_ordini_cliente_updated"),
            ([('data_firma', -1)], "perf_ordini_data_firma"),
            ([('updated_at', -1)], "perf_ordini_updated"),
        ],
        "crm_installazioni": [
            ([('updated_at', -1)], "perf_installazioni_updated"),
            ([('tecnico_user_id', 1), ('updated_at', -1)], "perf_installazioni_tecnico_updated"),
            ([('commessa_id', 1)], "perf_installazioni_commessa"),
            ([('cliente_id', 1)], "perf_installazioni_cliente"),
            ([('sede_id', 1)], "perf_installazioni_sede"),
        ],
        "crm_assistenza": [
            ([('cliente_id', 1), ('updated_at', -1)], "perf_assistenza_cliente_updated"),
            ([('updated_at', -1)], "perf_assistenza_updated"),
        ],
        "commesse": [
            ([('updated_at', -1)], "perf_commesse_updated"),
            ([('cliente_id', 1), ('stato', 1), ('updated_at', -1)], "perf_commesse_cliente_stato_updated"),
            ([('sede_id', 1)], "perf_commesse_sede"),
            ([('id', 1)], "perf_commesse_id"),
        ],
    }

    for collection_name, indexes in specs.items():
        collection = db[collection_name]
        for keys, name in indexes:
            try:
                await collection.create_index(keys, name=name, background=True)
            except Exception as exc:  # index conflicts must never block app startup
                logger.warning("Index creation skipped collection=%s index=%s error=%s", collection_name, name, exc)


async def _event_loop_monitor(app: Any) -> None:
    interval = 1.0
    warning_lag = max(0.1, float(os.environ.get("EVENT_LOOP_LAG_WARNING_SECONDS", "0.35")))
    while True:
        before = time.monotonic()
        await asyncio.sleep(interval)
        lag = time.monotonic() - before - interval
        if lag >= warning_lag:
            logger.warning("EVENT_LOOP_LAG seconds=%.3f", lag)


def install(app: Any, db: Any, auth_deps: Any, auth_mod: Any) -> None:
    """Install all performance features exactly once."""
    if getattr(app.state, "global_performance_refactor_installed", False):
        return
    app.state.global_performance_refactor_installed = True

    install_request_timing(app)
    install_performance_routes(app, db, auth_deps, auth_mod)

    @app.on_event("startup")
    async def _performance_startup():
        await ensure_performance_indexes(db)
        app.state.event_loop_monitor_task = asyncio.create_task(_event_loop_monitor(app))
        logger.info(
            "Global performance runtime enabled page_size=%s max_page_size=%s mongo_max_ms=%s",
            DEFAULT_PAGE_SIZE,
            MAX_PAGE_SIZE,
            MONGO_QUERY_MAX_MS,
        )

    @app.on_event("shutdown")
    async def _performance_shutdown():
        task = getattr(app.state, "event_loop_monitor_task", None)
        if task is not None:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
