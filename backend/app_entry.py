"""Entrypoint applicativo.

Mantiene l'app FastAPI esistente e sostituisce in modo mirato la sola rotta
meteo con il servizio resiliente multi-provider di R17.
"""
from typing import Optional

from fastapi import Depends

import server
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
    return await weather_service.get_installation_weather(
        date=date,
        comune=comune,
        provincia=provincia,
        cap=cap,
        address=address,
        latitude=latitude,
        longitude=longitude,
    )


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
