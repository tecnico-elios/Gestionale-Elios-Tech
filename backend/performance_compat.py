"""Compatibility bridge between the current React PWA and paginated CRM API.

The existing RegistryPage still expects complete lookup/list datasets and does
not yet render server-side pagination controls.  Production currently contains
more than 700 clients/sites/orders, so switching the endpoint to 50 rows would
silently hide valid records.

This bridge keeps legacy requests (no explicit page/limit parameters) bounded
to a transitional 1000-row page while new/updated clients get true pagination.
It can be removed once RegistryPage and all lookup consumers send page/limit.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import Depends, Query

import performance_runtime

LEGACY_PAGE_SIZE = max(200, min(int(os.environ.get("CRM_LEGACY_PAGE_SIZE", "1000")), 2000))


def install(app: Any, auth_deps: Any) -> None:
    if getattr(app.state, "performance_compat_installed", False):
        return

    current_endpoint = performance_runtime._capture_get_endpoint(app, "/api/crm/{resource}")
    if current_endpoint is None:
        raise RuntimeError("Rotta CRM ottimizzata non trovata per compatibility bridge")

    dep = auth_deps.require_password_current

    async def list_records_compatible(
        resource: str,
        q: Optional[str] = Query(default=None, max_length=120),
        include_archived: bool = Query(default=False),
        page: Optional[int] = Query(default=None, ge=1),
        limit: Optional[int] = Query(default=None, ge=1, le=performance_runtime.MAX_PAGE_SIZE),
        current: Dict[str, Any] = Depends(dep),
    ):
        # Current PWA sends neither page nor limit. Preserve complete lists during
        # the UI migration, but keep the request bounded and use the optimized
        # Mongo path (server filtering, no N+1, no GET-side calendar sync).
        if page is None and limit is None:
            effective_page = 1
            effective_limit = LEGACY_PAGE_SIZE
        else:
            effective_page = page or 1
            effective_limit = limit or performance_runtime.DEFAULT_PAGE_SIZE

        result = await current_endpoint(
            resource=resource,
            q=q,
            include_archived=include_archived,
            page=effective_page,
            limit=effective_limit,
            current=current,
        )
        result["legacy_compat"] = page is None and limit is None
        return result

    replaced = performance_runtime._replace_get_route(
        app,
        "/api/crm/{resource}",
        list_records_compatible,
        tags=["CRM", "performance", "compat"],
    )
    if not replaced:
        raise RuntimeError("Impossibile installare CRM compatibility bridge")

    app.state.performance_compat_installed = True
