"""Entrypoint applicativo.

Mantiene l'app FastAPI esistente e sostituisce in modo mirato la sola rotta
meteo con il servizio resiliente multi-provider. R18 aggiunge una risoluzione
coordinate robusta per installazioni/sedi storiche che hanno solo Comune o
indirizzo e non latitudine/longitudine salvate.
"""
from typing import Optional

from fastapi import Depends

import server
import weather_location
import weather_service

app = server.app


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
