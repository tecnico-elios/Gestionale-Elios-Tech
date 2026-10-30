"""Compatibility bridge between the current React PWA and paginated CRM API.

Some legacy screens still need complete customer/site/order lookup datasets.
Those screens keep a bounded compatibility page, while hot startup screens
(Dashboard/Calendar) are explicitly paginated by the frontend request guard.
This bridge can be removed once every consumer uses server-side pagination.
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from fastapi import Depends, Query

import performance_runtime

# Production currently contains more than 700 clients/sites/orders. 100 rows can
# make valid linked records disappear from legacy selectors and cause UI failures.
# Keep the compatibility dataset complete but bounded; hot pages explicitly send
# page/limit and therefore never hit this larger fallback.
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
