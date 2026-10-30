"""Emergency diagnostics for request storms, event-loop stalls and UI crashes.

This module is intentionally isolated and safe to remove after the performance
incident. It adds request timing/source diagnostics, prevents stale SPA HTML
from surviving a deploy, records React ErrorBoundary crashes, and exposes two
isolated Mongo read probes without changing production CRM write semantics.
"""
from __future__ import annotations

import asyncio
import logging
import os
import time
from typing import Any

from fastapi import Depends, Query, Request
from pymongo import MongoClient

logger = logging.getLogger("emergency_perf")
_active_requests = 0
_active_lock = asyncio.Lock()


def _clip(value: Any, limit: int) -> str:
    return str(value or "").replace("\x00", "")[:limit]


def install(app: Any, async_db: Any, auth_deps: Any) -> None:
    if getattr(app.state, "emergency_runtime_installed", False):
        return
    app.state.emergency_runtime_installed = True

    @app.middleware("http")
    async def emergency_request_trace(request: Request, call_next):
        global _active_requests
        async with _active_lock:
            _active_requests += 1
            active_now = _active_requests
        started = time.perf_counter()
        status = "ERR"
        try:
            response = await call_next(request)
            status = response.status_code

            # The React bundle has hashed filenames, but index.html is the pointer
            # to those hashes. Never cache SPA HTML across a Render deploy.
            content_type = str(response.headers.get("content-type") or "").lower()
            if not request.url.path.startswith("/api/") and "text/html" in content_type:
                response.headers["Cache-Control"] = "no-store, no-cache, must-revalidate, max-age=0"
                response.headers["Pragma"] = "no-cache"
                response.headers["Expires"] = "0"

            return response
        finally:
            elapsed = time.perf_counter() - started
            source = request.headers.get("x-client-source", "-")[:120]
            logger.warning(
                "ROUTE %s %s elapsed=%.3fs status=%s active=%d source=%s query=%s",
                request.method,
                request.url.path,
                elapsed,
                status,
                active_now,
                source,
                request.url.query[:300],
            )
            async with _active_lock:
                _active_requests = max(0, _active_requests - 1)

    @app.post("/api/_diag/ui-error", tags=["diagnostics"])
    async def ui_error(request: Request):
        """Receive a bounded same-app React crash report for Render diagnostics."""
        try:
            payload = await request.json()
            if not isinstance(payload, dict):
                payload = {}
        except Exception:
            payload = {}

        logger.error(
            "UI_ERROR path=%s message=%s stack=%s component=%s ua=%s",
            _clip(payload.get("path"), 240),
            _clip(payload.get("message"), 600),
            _clip(payload.get("stack"), 3000),
            _clip(payload.get("componentStack"), 3000),
            _clip(payload.get("userAgent") or request.headers.get("user-agent"), 400),
        )
        return {"ok": True}

    dep = auth_deps.require_password_current

    @app.get("/api/_diag/clienti-async", tags=["diagnostics"])
    async def clienti_async_probe(
        limit: int = Query(default=50, ge=1, le=100),
        current=Depends(dep),
    ):
        started = time.perf_counter()
        docs = await (
            async_db.crm_clienti
            .find(
                {"archived": {"$ne": True}},
                {
                    "_id": 0,
                    "id": 1,
                    "ragione_sociale": 1,
                    "email": 1,
                    "telefono": 1,
                    "updated_at": 1,
                },
            )
            .sort("updated_at", -1)
            .limit(limit)
            .max_time_ms(3000)
            .to_list(length=limit)
        )
        return {
            "driver": "motor-async",
            "seconds": round(time.perf_counter() - started, 4),
            "count": len(docs),
        }

    mongo_url = os.environ.get("MONGO_URL") or os.environ.get("MONGODB_URI")
    db_name = os.environ.get("DB_NAME") or os.environ.get("MONGO_DB_NAME") or "elios_tech"
    sync_client = None
    sync_db = None
    if mongo_url:
        sync_client = MongoClient(
            mongo_url,
            maxPoolSize=20,
            serverSelectionTimeoutMS=3000,
            connectTimeoutMS=3000,
            socketTimeoutMS=10000,
            retryReads=True,
        )
        sync_db = sync_client[db_name]
        app.state.emergency_sync_mongo_client = sync_client

    @app.get("/api/_diag/clienti-sync", tags=["diagnostics"])
    def clienti_sync_probe(
        limit: int = Query(default=50, ge=1, le=100),
        current=Depends(dep),
    ):
        if sync_db is None:
            return {"driver": "pymongo-sync", "available": False, "reason": "Mongo URL not configured"}
        started = time.perf_counter()
        docs = list(
            sync_db.crm_clienti
            .find(
                {"archived": {"$ne": True}},
                {
                    "_id": 0,
                    "id": 1,
                    "ragione_sociale": 1,
                    "email": 1,
                    "telefono": 1,
                    "updated_at": 1,
                },
            )
            .sort("updated_at", -1)
            .limit(limit)
            .max_time_ms(3000)
        )
        return {
            "driver": "pymongo-sync-threadpool",
            "seconds": round(time.perf_counter() - started, 4),
            "count": len(docs),
        }
