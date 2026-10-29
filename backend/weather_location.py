"""Risoluzione coordinate per record storici senza lat/lon.

Nuovi sopralluoghi continuano a usare Photon in autocomplete. Questo modulo viene
usato solo lato backend quando una installazione/sede storica ha Comune o
indirizzo ma non coordinate salvate.
"""
from __future__ import annotations

import asyncio
import time
from typing import Any, Dict, Optional, Tuple

import httpx
from fastapi import HTTPException

USER_AGENT = "Gestionale-Elios-Tech/1.0 github.com/tecnico-elios/Gestionale-Elios-Tech"
CACHE_TTL_SECONDS = 24 * 60 * 60
_CACHE: Dict[str, tuple[float, Tuple[float, float, str, str]]] = {}
_NOMINATIM_LOCK = asyncio.Lock()
_NOMINATIM_LAST_REQUEST = 0.0


def _parts(address: str, cap: str, comune: str, provincia: str) -> list[str]:
    out: list[str] = []
    seen: set[str] = set()
    for raw in [address, cap, comune, provincia, "Italia"]:
        value = str(raw or "").strip()
        if not value:
            continue
        key = value.casefold()
        if key in seen:
            continue
        seen.add(key)
        out.append(value)
    return out


def _cache_get(key: str) -> Optional[Tuple[float, float, str, str]]:
    hit = _CACHE.get(key)
    if not hit:
        return None
    created, value = hit
    if time.monotonic() - created > CACHE_TTL_SECONDS:
        _CACHE.pop(key, None)
        return None
    return value


def _cache_put(key: str, value: Tuple[float, float, str, str]) -> None:
    _CACHE[key] = (time.monotonic(), value)
    if len(_CACHE) > 512:
        oldest = min(_CACHE.items(), key=lambda item: item[1][0])[0]
        _CACHE.pop(oldest, None)


async def _photon(client: httpx.AsyncClient, query: str) -> Optional[Tuple[float, float, str, str]]:
    try:
        response = await client.get(
            "https://photon.komoot.io/api/",
            params={"q": query, "limit": 1},
            headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
        )
        response.raise_for_status()
        features = (response.json() or {}).get("features") or []
    except httpx.HTTPError:
        return None
    if not features:
        return None
    feature = features[0]
    coords = (feature.get("geometry") or {}).get("coordinates") or []
    if len(coords) < 2:
        return None
    props = feature.get("properties") or {}
    label = ", ".join(
        x for x in [props.get("name"), props.get("city"), props.get("state"), props.get("country")] if x
    ) or query
    return float(coords[1]), float(coords[0]), label, "OpenStreetMap/Photon"


async def _nominatim(client: httpx.AsyncClient, query: str) -> Optional[Tuple[float, float, str, str]]:
    global _NOMINATIM_LAST_REQUEST
    async with _NOMINATIM_LOCK:
        elapsed = time.monotonic() - _NOMINATIM_LAST_REQUEST
        if elapsed < 1.05:
            await asyncio.sleep(1.05 - elapsed)
        try:
            response = await client.get(
                "https://nominatim.openstreetmap.org/search",
                params={
                    "q": query,
                    "format": "jsonv2",
                    "limit": 1,
                    "countrycodes": "it",
                    "addressdetails": 1,
                },
                headers={"User-Agent": USER_AGENT, "Accept": "application/json"},
            )
            _NOMINATIM_LAST_REQUEST = time.monotonic()
            response.raise_for_status()
            rows = response.json() or []
        except httpx.HTTPError:
            _NOMINATIM_LAST_REQUEST = time.monotonic()
            return None
    if not rows:
        return None
    row: Dict[str, Any] = rows[0]
    try:
        lat = float(row.get("lat"))
        lon = float(row.get("lon"))
    except (TypeError, ValueError):
        return None
    label = str(row.get("display_name") or query).strip()
    return lat, lon, label, "© OpenStreetMap contributors"


async def resolve_weather_location(address: str = "", comune: str = "", provincia: str = "", cap: str = "") -> Tuple[float, float, str, str]:
    parts = _parts(address, cap, comune, provincia)
    if len(parts) <= 1:  # solo "Italia"
        raise HTTPException(422, "Località mancante")
    query = ", ".join(parts)
    key = query.casefold()
    cached = _cache_get(key)
    if cached:
        return cached

    timeout = httpx.Timeout(8.0, connect=4.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True) as client:
        result = await _photon(client, query)
        if result is None:
            # Fallback deliberatamente non usato per autocomplete: solo record
            # storici privi di coordinate e con cache backend di 24 ore.
            result = await _nominatim(client, query)

    if result is None:
        raise HTTPException(502, "Impossibile determinare le coordinate della sede. Verifica Comune o indirizzo.")
    _cache_put(key, result)
    return result
