"""FastAPI database dependency for routers migrated to the centralized DB layer."""
from __future__ import annotations

from typing import Any

from fastapi import Request


def get_database(request: Request) -> Any:
    """Return the process-wide Mongo database handle from app.state.

    app_entry exposes the existing Motor database on app.state so new routers
    can use Depends(get_database) without opening clients per request.
    """
    db = getattr(request.app.state, "db", None)
    if db is None:
        raise RuntimeError("MongoDB non inizializzato")
    return db
