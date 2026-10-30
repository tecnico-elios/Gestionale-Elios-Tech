"""Entrypoint applicativo.

Mantiene l'app FastAPI esistente e sostituisce in modo mirato la sola rotta
meteo con il servizio resiliente multi-provider. R18 aggiunge una risoluzione
coordinate robusta per installazioni/sedi storiche che hanno solo Comune o
indirizzo e non latitudine/longitudine salvate.

Il performance runtime applica inoltre il refactoring globale delle letture
CRM senza duplicare il core storico di server.py: paginazione, query Mongo
bounded, eliminazione N+1, cache lookup, indici e slow-request monitoring.
"""
from typing import Optional

from fastapi import Depends

import server
import weather_location
import weather_service
import performance_runtime
import performance_compat
import emergency_runtime

app = server.app

# Shared process-wide handles for new routers using Depends(get_database).
# No client is opened per request: the legacy server's AsyncIOMotorClient remains
# the single source during the incremental migration to database.py.
app.state.db = server.db
app.state.mongo_client = server.client


async def weather_installation_r17(
    date: str,
    comune: str = "",
    provincia: str = "",
    cap: str = "",
    address: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
):
    location_attribution = ""
    location_source = ""
    if latitude is None or longitude is None:
        latitude, longitude, _resolved_label, location_attribution = await weather_location.resolve_weather_location(
            address=address,
            comune=comune,
            provincia=provincia,
            cap=cap,
        )
        location_source = "backend-geocode"

    result = await weather_service.get_installation_weather(
        date=date,
        comune=comune,
        provincia=provincia,
        cap=cap,
        address=address,
        latitude=latitude,
        longitude=longitude,
    )
    if isinstance(result, dict) and result.get("state") == "ok" and location_attribution:
        result = dict(result)
        base_attribution = str(result.get("attribution") or "").strip()
        suffix = f"Località {location_attribution}"
        result["attribution"] = f"{base_attribution} · {suffix}" if base_attribution else suffix
        result["location_source"] = location_source
    return result


def _install_weather_route() -> None:
    path = "/api/weather-installation"
    old_index = None
    for idx, route in enumerate(app.router.routes):
        if getattr(route, "path", None) == path and "GET" in (getattr(route, "methods", None) or set()):
            old_index = idx
            break
    if old_index is None:
        raise RuntimeError("Rotta meteo esistente non trovata")

    app.router.routes.pop(old_index)
    app.add_api_route(
        path,
        weather_installation_r17,
        methods=["GET"],
        dependencies=[Depends(server.dep_current_user)],
        tags=["weather"],
    )
    new_route = app.router.routes.pop()
    app.router.routes.insert(old_index, new_route)


_install_weather_route()

# Global backend performance refactor. server.py already owns the Motor client;
# this layer optimizes the hot read paths while preserving all write semantics.
performance_runtime.install(
    app,
    server.db,
    server.auth_deps,
    server.auth_mod,
)

# Transitional compatibility for the current PWA: legacy list requests still
# receive a bounded dataset, while explicit page/limit calls use the paginated
# contract immediately.
performance_compat.install(app, server.auth_deps)

# Temporary emergency diagnostics: per-request source/concurrency timing plus
# isolated Motor-vs-PyMongo read probes. No production read/write route is
# converted to synchronous execution by this layer.
emergency_runtime.install(app, server.db, server.auth_deps)
