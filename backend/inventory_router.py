"""Inventory Router — sorgente unica locale del Gestionale Elios Tech.

Notion viene usato esclusivamente dalle route di migrazione iniziale.
Le normali funzioni di magazzino usano sempre MongoDB/inventory_local.
"""
from __future__ import annotations

from typing import Any

import inventory_local


async def get_source(db) -> str:
    """Il gestionale e' autonomo: la fonte operativa e' sempre locale."""
    return "gestionale"


async def get_svc(db) -> Any:
    """Restituisce sempre il servizio inventario locale."""
    return inventory_local
