"""Compatibility bridge between the current React PWA and paginated CRM API.

The current UI still has a few consumers that do not send explicit page/limit.
During the performance incident we intentionally keep that fallback small so a
single page cannot materialize hundreds or thousands of documents at startup.
Updated clients should always send page/limit explicitly.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import Depends, Query

import performance_runtime

# Emergency back-pressure: legacy calls are capped aggressively. This remains
# configurable from Render and can be raised temporarily if a specific legacy
# screen still needs more rows while it is being migrated to server pagination.
LEGACY_PAGE_SIZE = max(50, min(int(os.environ.get("CRM_LEGACY_PAGE_SIZE", "100")), 500))


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
