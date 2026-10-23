"""Inventory Router — sorgente unica locale del Gestionale Elios Tech.

Notion viene usato esclusivamente dalle route di migrazione iniziale.
Le normali funzioni di magazzino usano sempre MongoDB/inventory_local.
"""
from __future__ import annotations

from typing import Any

import inventory_local
import inventory_integrity
import inventory_transfer_guard

# R4: applica le protezioni di integrità allo stesso modulo condiviso importato
# anche da server.py. In questo modo Arrivi, Spedizioni e Trasferimenti usano
# tutti la stessa implementazione rinforzata.
inventory_integrity.install(inventory_local)
# La guardia trasferimenti viene applicata per ultima: valida e riserva la
# sorgente prima di creare il prodotto nel deposito di destinazione.
inventory_transfer_guard.install(inventory_local)


async def get_source(db) -> str:
    """Il gestionale e' autonomo: la fonte operativa e' sempre locale."""
    return "gestionale"


async def get_svc(db) -> Any:
    """Restituisce sempre il servizio inventario locale."""
    return inventory_local
