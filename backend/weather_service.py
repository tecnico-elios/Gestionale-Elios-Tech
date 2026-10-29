"""Servizio meteo resiliente per sopralluoghi/installazioni.

Usa MET Norway come sorgente principale nel breve periodo e Open-Meteo come
fallback/estensione. Le coordinate verso MET Norway sono limitate a 4 decimali
come richiesto dal servizio e le risposte sono memorizzate in cache in-process
per ridurre traffico ripetuto.
"""
from __future__ import annotations

import logging
import time
from datetime import date as date_cls, datetime, timezone
from typing import Any, Dict, Optional
from zoneinfo import ZoneInfo

import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)
ROME_TZ = ZoneInfo("Europe/Rome")
USER_AGENT = "Gestionale-Elios-Tech/1.0 github.com/tecnico-elios/Gestionale-Elios-Tech"
CACHE_TTL_SECONDS = 30 * 60
_CACHE: Dict[str, tuple[float, Dict[str, Any]]] = {}


class ProviderUnavailable(RuntimeError):
    pass


def _cache_key(lat: float, lon: float, target: date_cls) -> str:
    return f"{round(lat, 4):.4f}:{round(lon, 4):.4f}:{target.isoformat()}"


def _cache_get(key: str) -> Optional[Dict[str, Any]]:
    entry = _CACHE.get(key)
    if not entry:
        return None
    created, value = entry
    if time.monotonic() - created > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return dict(value)


def _cache_put(key: str, value: Dict[str, Any]) -> None:
    _CACHE[key] = (time.monotonic(), dict(value))
    if len(_CACHE) > 256:
        oldest = min(_CACHE.items(), key=lambda item: item[1][0])[0]
        _CACHE.pop(oldest, None)


def _display_location(address: str, comune: str, provincia: str, cap: str) -> str:
    if (address or "").strip():
        return address.strip()
    return ", ".join(x.strip() for x in [comune, provincia, cap] if (x or "").strip())


async def _geocode(client: httpx.AsyncClient, address: str, comune: str, provincia: str, cap: str) -> tuple[float, float, str]:
    query = ", ".join(x.strip() for x in [address, cap, comune, provincia, "Italia"] if (x or "").strip())
    if not query:
        raise HTTPException(422, "Località mancante")
    try:
        response = await client.get("https://photon.komoot.io/api/", params={"q": query, "limit": 1})
        response.raise_for_status()
        features = (response.json() or {}).get("features") or []
    except httpx.HTTPError as exc:
        raise HTTPException(502, "Servizio di localizzazione temporaneamente non raggiungibile") from exc
    if not features:
        raise HTTPException(422, "Località non trovata. Seleziona un indirizzo suggerito per confermare posizione e meteo.")
    feature = features[0]
    coords = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coords) < 2:
        raise HTTPException(422, "Coordinate della località non disponibili")
    props = feature.get("properties") or {}
    label = _display_location(address, comune, provincia, cap) or ", ".join(
        x for x in [props.get("name"), props.get("city"), props.get("state")] if x
    )
    return float(coords[1]), float(coords[0]), label


def _symbol_to_wmo(symbol: str) -> int:
    s = (symbol or "").lower()
    if "thunder" in s:
        return 95
    if "snow" in s or "sleet" in s:
        return 71
    if "rain" in s or "showers" in s:
        return 61
    if "fog" in s:
        return 45
    if "partlycloudy" in s:
        return 2
    if "cloudy" in s:
        return 3
    if "fair" in s:
        return 1
    if "clearsky" in s:
        return 0
    return 3


async def _met_norway(client: httpx.AsyncClient, lat: float, lon: float, target: date_cls, location: str) -> Dict[str, Any]:
    # MET Norway richiede al massimo 4 decimali per favorire la cache lato provider.
    params = {"lat": f"{round(lat, 4):.4f}", "lon": f"{round(lon, 4):.4f}"}
    try:
        response = await client.get(
            "https://api.met.no/weatherapi/locationforecast/2.0/complete",
            params=params,
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        response.raise_for_status()
        payload = response.json() or {}
    except httpx.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        raise ProviderUnavailable(f"MET Norway HTTP {status or 'network'}") from exc

    target_iso = target.isoformat()
    temps: list[float] = []
    winds: list[float] = []
    rain_probs: list[float] = []
    rain_amounts: list[float] = []
    codes: list[int] = []

    for step in ((payload.get("properties") or {}).get("timeseries") or []):
        raw_time = step.get("time")
        if not raw_time:
            continue
        try:
            instant_utc = datetime.fromisoformat(raw_time.replace("Z", "+00:00"))
            local_day = instant_utc.astimezone(ROME_TZ).date().isoformat()
        except (TypeError, ValueError):
            continue
        if local_day != target_iso:
            continue

        data = step.get("data") or {}
        instant = ((data.get("instant") or {}).get("details") or {})
        temp = instant.get("air_temperature")
        wind = instant.get("wind_speed")
        if isinstance(temp, (int, float)):
            temps.append(float(temp))
        if isinstance(wind, (int, float)):
            winds.append(float(wind) * 3.6)  # m/s -> km/h

        for bucket in ("next_1_hours", "next_6_hours", "next_12_hours"):
            period = data.get(bucket) or {}
            details = period.get("details") or {}
            probability = details.get("probability_of_precipitation")
            amount = details.get("precipitation_amount")
            if isinstance(probability, (int, float)):
                rain_probs.append(float(probability))
            if isinstance(amount, (int, float)):
                rain_amounts.append(float(amount))
            symbol = ((period.get("summary") or {}).get("symbol_code") or "")
            if symbol:
                codes.append(_symbol_to_wmo(symbol))

            period_min = details.get("air_temperature_min")
            period_max = details.get("air_temperature_max")
            if isinstance(period_min, (int, float)):
                temps.append(float(period_min))
            if isinstance(period_max, (int, float)):
                temps.append(float(period_max))

    if not temps:
        raise ProviderUnavailable("MET Norway: data non presente per la data richiesta")

    rain = max(rain_probs) if rain_probs else (80.0 if any(v > 0 for v in rain_amounts) else 0.0)
    return {
        "state": "ok",
        "location": location,
        "code": max(codes) if codes else 3,
        "min": round(min(temps), 1),
        "max": round(max(temps), 1),
        "rain": round(rain),
        "wind": round(max(winds), 1) if winds else 0,
        "provider": "MET Norway",
        "attribution": "Dati da MET Norway (CC BY 4.0)",
    }


async def _open_meteo(client: httpx.AsyncClient, lat: float, lon: float, target: date_cls, location: str) -> Dict[str, Any]:
    try:
        response = await client.get(
            "https://api.open-meteo.com/v1/forecast",
            params={
                "latitude": lat,
                "longitude": lon,
                "daily": "weather_code,temperature_2m_max,temperature_2m_min,precipitation_probability_max,wind_speed_10m_max",
                "timezone": "Europe/Rome",
                "forecast_days": 16,
            },
            headers={"User-Agent": USER_AGENT},
        )
        response.raise_for_status()
        daily = (response.json() or {}).get("daily") or {}
    except httpx.HTTPError as exc:
        status = getattr(getattr(exc, "response", None), "status_code", None)
        raise ProviderUnavailable(f"Open-Meteo HTTP {status or 'network'}") from exc

    times = daily.get("time") or []
    try:
        idx = times.index(target.isoformat())
    except ValueError as exc:
        raise ProviderUnavailable("Open-Meteo: data non presente per la data richiesta") from exc

    def at(key: str, default: Any = None) -> Any:
        values = daily.get(key) or []
        return values[idx] if idx < len(values) else default

    return {
        "state": "ok",
        "location": location,
        "code": at("weather_code", 3),
        "min": at("temperature_2m_min"),
        "max": at("temperature_2m_max"),
        "rain": at("precipitation_probability_max", 0),
        "wind": at("wind_speed_10m_max", 0),
        "provider": "Open-Meteo",
        "attribution": "Dati da Open-Meteo",
    }


async def get_installation_weather(
    date: str,
    comune: str = "",
    provincia: str = "",
    cap: str = "",
    address: str = "",
    latitude: Optional[float] = None,
    longitude: Optional[float] = None,
) -> Dict[str, Any]:
    try:
        target = date_cls.fromisoformat((date or "").strip())
    except ValueError as exc:
        raise HTTPException(422, "Data meteo non valida") from exc

    today = datetime.now(ROME_TZ).date()
    delta = (target - today).days
    if delta < 0:
        return {"state": "past"}
    if delta > 15:
        return {"state": "range"}

    timeout = httpx.Timeout(9.0, connect=5.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        if latitude is not None and longitude is not None:
            lat = float(latitude)
            lon = float(longitude)
            location = _display_location(address, comune, provincia, cap)
        else:
            lat, lon, location = await _geocode(client, address, comune, provincia, cap)

        key = _cache_key(lat, lon, target)
        cached = _cache_get(key)
        if cached:
            cached["cached"] = True
            return cached

        # MET Norway copre fino a circa 9 giorni; per il breve periodo lo usiamo
        # per primo, così non dipendiamo dal rate-limit degli IP condivisi Render.
        providers = (_met_norway, _open_meteo) if delta <= 8 else (_open_meteo, _met_norway)
        errors: list[str] = []
        for provider in providers:
            try:
                result = await provider(client, lat, lon, target, location)
                result["cached"] = False
                _cache_put(key, result)
                return result
            except ProviderUnavailable as exc:
                errors.append(str(exc))
                logger.warning("Provider meteo non disponibile: %s", exc)

    # Per date oltre l'orizzonte del provider alternativo non mostriamo un errore
    # tecnico: il widget tornerà a provarci quando la data si avvicina.
    if delta > 8:
        return {"state": "range"}
    logger.error("Tutti i provider meteo indisponibili: %s", " | ".join(errors))
    raise HTTPException(503, "Previsioni meteo momentaneamente non disponibili. Riprova tra poco.")
