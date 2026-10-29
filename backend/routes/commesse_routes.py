"""F23 (26/02/2026) — Gestione Commesse.
Storage: MongoDB. Inventario, spedizioni, ordini e rollback usano il database locale
del Gestionale Elios Tech. Notion è previsto soltanto per la migrazione iniziale.

L'annullamento di una commessa ripristina i movimenti locali, aggiorna lo storico
dell'ordine e disattiva le associazioni QR legate alla spedizione.
"""
from __future__ import annotations
import os
import uuid
import logging
import re
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional, Tuple

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query, Request
from pydantic import BaseModel, ConfigDict, Field

import auth as auth_mod
import event_logger
from inventory_router import get_svc as _get_inventory_svc

logger = logging.getLogger(__name__)

STATI = ("da_preparare", "in_preparazione", "parziale", "pronta", "solo_servizi", "bozza_spedizione", "parzialmente_spedita", "spedita", "annullata")
PRIORITA = ("urgente", "alta", "normale", "bassa")


class RigaBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    product_page_id: str
    product_name: str
    product_code: Optional[str] = None
    tipo_gestione: str  # a_seriale | a_quantita
    unit: str = "pz"
    qty_richiesta: float = Field(gt=0)


class CommessaCreate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    number: str = Field(min_length=1, max_length=50)
    cliente: str = Field(min_length=1, max_length=200)
    # Collegamenti nativi del nuovo gestionale.
    cliente_id: Optional[str] = None
    sede_id: Optional[str] = None
    ordine_cliente_id: Optional[str] = None
    preventivo_id: Optional[str] = None
    # Identificativo legacy importato, mantenuto solo per compatibilità con dati storici.
    order_page_id: Optional[str] = None
    data_ordine: Optional[str] = None
    data_prevista: Optional[str] = None
    priorita: str = "normale"
    note: Optional[str] = None
    warehouse_id: str = "elios-tech"
    righe: List[RigaBody] = Field(min_length=1)


class CommessaUpdate(BaseModel):
    model_config = ConfigDict(extra="ignore")
    cliente: Optional[str] = None
    cliente_id: Optional[str] = None
    sede_id: Optional[str] = None
    ordine_cliente_id: Optional[str] = None
    preventivo_id: Optional[str] = None
    data_ordine: Optional[str] = None
    data_prevista: Optional[str] = None
    priorita: Optional[str] = None
    note: Optional[str] = None
    warehouse_id: Optional[str] = None
    righe: Optional[List[RigaBody]] = None


class PickBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    riga_index: int
    quantity: Optional[float] = None
    serial: Optional[str] = None
    remove: Optional[bool] = False  # F28 — se true su A Seriale rimuove il seriale specificato


def _now():
    return datetime.now(timezone.utc)


def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    d = {**doc}
    d.pop("_id", None)
    for k in ("created_at", "updated_at", "presa_in_carico_at", "completed_at", "shipped_at", "cancelled_at"):
        if isinstance(d.get(k), datetime):
            d[k] = d[k].isoformat()
    return d


def _compute_stato(doc: Dict[str, Any]) -> str:
    """Ricalcola stato in base ai prelievi delle righe (esclude stati terminali/bozza).
    F30 — Considera anche qty_spedita: il "residuo" da preparare è (richiesta - spedita)."""
    # F25.b — bozza_spedizione è uno stato manuale: non lo ricalcoliamo dalle righe.
    if doc.get("stato") in ("spedita", "annullata", "bozza_spedizione", "parzialmente_spedita", "solo_servizi"):
        return doc["stato"]
    if not doc.get("operatore_carico"):
        return "da_preparare"
    righe = doc.get("righe") or []
    residui = 0
    prelevati = 0
    for r in righe:
        qr = float(r.get("qty_richiesta") or 0)
        qs = float(r.get("qty_spedita") or 0)
        residui += max(0.0, qr - qs)
        prelevati += float(r.get("qty_prelevata") or 0)
    if residui > 0 and prelevati >= residui:
        return "pronta"
    if prelevati > 0:
        return "parziale"
    return "in_preparazione"


async def _get_feature(db) -> bool:
    doc = await db.settings.find_one({"_id": "features"}) or {}
    return bool(doc.get("commesse_enabled", True))


async def _rollback_shipment(db, shipment_id: str, actor: str, reason: str) -> Dict[str, Any]:
    """F30.b — Annulla una spedizione confermata (rollback controllato).

    Ripristina in modo controllato una spedizione già confermata:
      1. carica il record locale della spedizione;
      2. annulla i movimenti e ripristina quantità/seriali nel magazzino locale;
      3. aggiorna l'ordine cliente locale collegato;
      4. disattiva le associazioni QR della spedizione;
      5. conserva il record annullato per audit.
    """
    ck = await db.checklists.find_one({"id": shipment_id})
    if not ck:
        # Legacy o checklist non trovato: solo warning, ma continua (rollback parziale)
        logger.warning(f"[rollback] checklist {shipment_id} non trovato — skip")
        return {"ok": True, "note": "checklist_missing", "archived_pages": 0,
                "reinstated_serials": [], "order_updated": False, "warnings": ["checklist not found in db"]}
    if ck.get("status") == "cancelled":
        return {"ok": True, "note": "already_cancelled", "archived_pages": 0,
                "reinstated_serials": [], "order_updated": False, "warnings": []}

    warnings: List[str] = []
    # 1. Rollback dei movimenti sul servizio inventario attivo (Gestionale locale).
    svc = await _get_inventory_svc(db)
    archived = 0
    for pid in (ck.get("tracker_page_ids") or []):
        try:
            await svc.archive_page(pid)
            archived += 1
        except Exception as e:
            warnings.append(f"rollback movimento {pid} fallito: {e}")
            raise RuntimeError(f"Rollback movimento fallito: {e}")

    # archive_page ripristina già quantità/seriali in modalità gestionale.
    reinstated: List[str] = [serial for item in (ck.get("items") or []) if item.get("serialized") for serial in (item.get("serials") or []) if serial]

    # 2. Aggiorna soltanto l'ordine locale collegato, se presente.
    order_updated = False
    order_page_id: Optional[str] = None
    ck_serial_lows = {x.strip().lower() for item in (ck.get("items") or []) for x in (item.get("serials") or []) if x}
    ck_qr_lows = {x.strip().lower() for item in (ck.get("items") or []) for x in (item.get("qr_codes") or []) if x}
    ck_qr_lows.update({str(b.get("qr_code") or "").strip().lower() for item in (ck.get("items") or []) for b in (item.get("qr_bindings") or []) if b.get("qr_code")})
    if ck_serial_lows:
        assoc = await db.qr_associations.find_one({"serial_lower": {"$in": list(ck_serial_lows)}, "active": True})
        if assoc and assoc.get("order_page_id"):
            order_page_id = assoc.get("order_page_id")
    if order_page_id:
        all_sn = [x for item in (ck.get("items") or []) for x in (item.get("serials") or []) if x]
        all_qr = [x for item in (ck.get("items") or []) for x in (item.get("qr_codes") or []) if x]
        all_qr.extend([str(b.get("qr_code") or "").strip() for item in (ck.get("items") or []) for b in (item.get("qr_bindings") or []) if b.get("qr_code")])
        all_qr = list(dict.fromkeys(x for x in all_qr if x))
        update_doc = {"$set": {"updated_at": datetime.now(timezone.utc)}}
        pull = {}
        if all_sn:
            pull["seriali_spediti"] = {"$in": all_sn}
        if all_qr:
            pull["qr_spediti"] = {"$in": all_qr}
        if pull:
            update_doc["$pull"] = pull
        await db.crm_ordini_clienti.update_one({"id": order_page_id}, update_doc)
        order_updated = True

    # 4. Disattiva le associazioni QR (legacy qr_associations + nuovo qr_bindings)
    #    Solo quelle che corrispondono ai seriali della spedizione (non tocchiamo altre).
    detach_meta = {"detached_by": actor, "detached_at": datetime.now(timezone.utc).isoformat(),
                   "detached_reason": f"rollback shipment {shipment_id}: {reason or 'commessa annullata'}"}
    if ck_serial_lows:
        await db.qr_associations.update_many(
            {"serial_lower": {"$in": list(ck_serial_lows)}, "active": True},
            {"$set": {"active": False, **detach_meta}},
        )
        await db.qr_bindings.update_many(
            {"serial_lower": {"$in": list(ck_serial_lows)}, "active": True},
            {"$set": {"active": False, **detach_meta}},
        )

    # 5. Marca il checklist come cancelled (mantiene record per audit)
    await db.checklists.update_one(
        {"id": shipment_id},
        {"$set": {
            "status": "cancelled",
            "cancelled_at": datetime.now(timezone.utc).isoformat(),
            "cancelled_by": actor,
            "cancel_reason": reason or None,
            "rollback_warnings": warnings,
        }},
    )

    try:
        svc.invalidate_inventory_cache()
    except Exception:
        pass
    return {
        "ok": True,
        "archived_pages": archived,
        "reinstated_serials": reinstated,
        "order_updated": order_updated,
        "warnings": warnings,
    }


def build_router(db, deps: auth_mod.AuthDependencies) -> APIRouter:
    router = APIRouter(prefix="/commesse", tags=["commesse"], dependencies=[Depends(deps.get_current_user)])

    async def _require_enabled():
        if not await _get_feature(db):
            raise HTTPException(403, "Gestione Commesse disabilitata")

    async def _require_commesse_manager(current=Depends(deps.require_password_current)):
        """Operazioni sulle commesse esistenti."""
        if not auth_mod.has_permission(current, "commesse", "edit"):
            raise HTTPException(403, "Permesso di modifica Commesse richiesto")
        return current

    async def _require_commesse_create(current=Depends(deps.require_password_current)):
        if not auth_mod.has_permission(current, "commesse", "create"):
            raise HTTPException(403, "Non hai il permesso per creare nuove commesse")
        return current

    async def _require_commesse_delete(current=Depends(deps.require_password_current)):
        if not auth_mod.has_permission(current, "commesse", "delete"):
            raise HTTPException(403, "Non hai il permesso per eliminare le commesse")
        return current

    @router.get("")
    async def list_commesse(
        stato: Optional[str] = Query(None),
        priorita: Optional[str] = Query(None),
        cliente: Optional[str] = Query(None),
        limit: int = Query(100, ge=1, le=500),
    ):
        await _require_enabled()
        q: Dict[str, Any] = {}
        if stato: q["stato"] = stato
        if priorita: q["priorita"] = priorita
        if cliente: q["cliente"] = {"$regex": cliente, "$options": "i"}
        cursor = db.commesse.find(q).sort([("priorita", 1), ("data_prevista", 1), ("created_at", -1)]).limit(limit)
        # Ordine priorità: urgente, alta, normale, bassa
        priority_rank = {"urgente": 0, "alta": 1, "normale": 2, "bassa": 3}
        items = []
        async for d in cursor:
            items.append(_serialize(d))
        items.sort(key=lambda x: (priority_rank.get(x.get("priorita", "normale"), 2), x.get("data_prevista") or "9999", x.get("created_at") or ""))
        # KPI
        kpi = {s: await db.commesse.count_documents({"stato": s}) for s in STATI}
        return {"items": items, "kpi": kpi}

    @router.get("/kpi")
    async def kpi():
        await _require_enabled()
        return {s: await db.commesse.count_documents({"stato": s}) for s in STATI}

    @router.post("/from-order/{order_id}")
    async def create_commessa_from_order(order_id: str, current=Depends(_require_commesse_create)):
        """Crea o aggiorna una sola commessa dall'ordine cliente.
        Materiali -> picking; servizi/manodopera/installazione -> attività operative.
        Se esiste già la commessa nata dal preventivo, viene aggiornata senza duplicarla.
        """
        await _require_enabled()
        ordine = await db.crm_ordini_clienti.find_one({"id": order_id})
        if not ordine:
            raise HTTPException(404, "Ordine cliente non trovato")

        finance_state = str(ordine.get("stato_finanziaria") or "Non richiesta")
        if finance_state not in ("Non richiesta", "Approvata", "Erogata", "Contratto attivo", "Erogata / Contratto attivo"):
            raise HTTPException(409, f"Pratica finanziaria non ancora approvata: {finance_state}")

        async def material_rows(source_rows):
            out = []
            for row in (source_rows or []):
                kind = str(row.get("tipo_riga") or row.get("categoria") or "materiale").strip().lower()
                if kind not in ("materiale", "prodotto", "magazzino", "product"):
                    continue
                qty = float(row.get("quantity") or row.get("quantita") or 0)
                if qty <= 0:
                    continue
                pid = row.get("product_page_id") or row.get("prodotto_id")
                prod = await db.products.find_one({"id": pid}) if pid else None
                out.append({
                    "product_page_id": pid,
                    "product_name": row.get("product_name") or row.get("descrizione") or (prod or {}).get("name") or "Materiale",
                    "product_code": row.get("product_code") or (prod or {}).get("code") or "",
                    "tipo_gestione": row.get("tipo_gestione") or (prod or {}).get("tipo_gestione") or "a_quantita",
                    "unit": row.get("unit") or row.get("unita") or (prod or {}).get("unit") or "pz",
                    "qty_richiesta": qty,
                    "qty_prelevata": 0.0,
                    "seriali_prelevati": [],
                })
            return out

        def merge_rows(old_rows, new_rows):
            """Sincronizza il fabbisogno senza perdere righe libere, prelievi o spedizioni già registrate."""
            def row_key(r):
                pid = str(r.get("product_page_id") or "").strip()
                if pid:
                    return f"id:{pid}"
                code = str(r.get("product_code") or "").strip().casefold()
                if code:
                    return f"code:{code}"
                name = str(r.get("product_name") or r.get("descrizione") or "").strip().casefold()
                unit = str(r.get("unit") or r.get("unita") or "pz").strip().casefold()
                return f"free:{name}:{unit}"

            old_by_key = {row_key(r): r for r in (old_rows or [])}
            merged, seen = [], set()
            for nr in new_rows:
                rr = dict(nr)
                key = row_key(rr)
                old = old_by_key.get(key)
                if old:
                    picked = float(old.get("qty_prelevata") or 0)
                    shipped = float(old.get("qty_spedita") or 0)
                    committed = picked + shipped
                    if float(rr.get("qty_richiesta") or 0) < committed:
                        raise HTTPException(409, f"Impossibile ridurre '{rr.get('product_name') or 'prodotto'}' sotto la quantità già preparata/spedita ({committed:g})")
                    rr["qty_prelevata"] = picked
                    rr["seriali_prelevati"] = list(old.get("seriali_prelevati") or [])
                    rr["qty_spedita"] = shipped
                    rr["seriali_spediti"] = list(old.get("seriali_spediti") or [])
                merged.append(rr)
                seen.add(key)
            for key, old in old_by_key.items():
                if key in seen:
                    continue
                committed = float(old.get("qty_prelevata") or 0) + float(old.get("qty_spedita") or 0)
                if committed > 0 or (old.get("seriali_prelevati") or []) or (old.get("seriali_spediti") or []):
                    raise HTTPException(409, f"Impossibile rimuovere '{old.get('product_name') or 'prodotto'}': materiale già preparato o spedito")
            return merged

        rows = await material_rows(ordine.get("righe") or [])
        servizi = [dict(r) for r in (ordine.get("righe") or []) if str(r.get("tipo_riga") or r.get("categoria") or "materiale").strip().lower() not in ("materiale", "prodotto", "magazzino", "product")]
        tipo = "mista" if rows and servizi else ("materiali" if rows else "servizi")

        existing = await db.commesse.find_one({"ordine_cliente_id": order_id, "stato": {"$ne": "annullata"}})
        if not existing and ordine.get("preventivo_id"):
            existing = await db.commesse.find_one({"preventivo_id": ordine.get("preventivo_id"), "stato": {"$ne": "annullata"}})

        if existing:
            merged = merge_rows(existing.get("righe") or [], rows)
            current_state = existing.get("stato") or "da_preparare"
            if not merged and current_state in ("da_preparare", "in_preparazione", "parziale"):
                current_state = "solo_servizi"
            elif merged and current_state == "pronta" and not any(float(r.get("qty_prelevata") or 0) > 0 for r in merged):
                current_state = "da_preparare"
            now = _now()
            await db.commesse.update_one({"id": existing.get("id")}, {"$set": {
                "ordine_cliente_id": order_id,
                "cliente_id": ordine.get("cliente_id") or existing.get("cliente_id"),
                "sede_id": ordine.get("sede_id") or existing.get("sede_id"),
                "preventivo_id": ordine.get("preventivo_id") or existing.get("preventivo_id"),
                "data_ordine": ordine.get("data") or existing.get("data_ordine"),
                "note": ordine.get("note") or existing.get("note") or "",
                "righe": merged,
                "servizi": servizi,
                "tipo_commessa": tipo,
                "stato_servizi": "Da programmare" if servizi else None,
                "stato": current_state,
                "updated_at": now,
            }})
            await db.crm_ordini_clienti.update_one(
                {"id": order_id},
                {"$set": {"stato": "In lavorazione", "stato_logistico": "Da preparare" if merged else "Nessun materiale da preparare", "updated_at": now}},
            )
            updated = await db.commesse.find_one({"id": existing.get("id")})
            if not merged and any(str(s.get("tipo_riga") or s.get("categoria") or "").strip().lower() in ("installazione", "posa") for s in servizi) and updated.get("cliente_id") and updated.get("sede_id"):
                existing_installation = await db.crm_installazioni.find_one({"commessa_id": updated.get("id")})
                if not existing_installation:
                    await db.crm_installazioni.insert_one({
                        "id": str(uuid.uuid4()), "commessa_id": updated.get("id"),
                        "ordine_cliente_id": order_id, "cliente_id": updated.get("cliente_id"),
                        "sede_id": updated.get("sede_id"), "tecnico": "", "data": "",
                        "stato": "Da programmare",
                        "note": f"Creata automaticamente dalla commessa #{updated.get('number')}",
                        "created_by": current.get("username"), "created_at": now, "updated_at": now,
                    })
            return {"ok": True, "created": False, "commessa": _serialize(updated)}

        client_id = ordine.get("cliente_id")
        cliente = await db.crm_clienti.find_one({"id": client_id}) if client_id else None
        cliente_nome = (cliente or {}).get("ragione_sociale") or " ".join(x for x in [(cliente or {}).get("nome"), (cliente or {}).get("cognome")] if x) or ordine.get("nominativo") or "Cliente"
        base_number = f"C-{ordine.get('numero') or order_id[:8]}"
        number = base_number
        suffix = 1
        while await db.commesse.find_one({"number": number, "stato": {"$ne": "annullata"}}):
            suffix += 1
            number = f"{base_number}-{suffix}"
        now = _now()
        doc = {
            "id": str(uuid.uuid4()), "number": number, "cliente": cliente_nome.strip(),
            "cliente_id": client_id, "sede_id": ordine.get("sede_id"), "ordine_cliente_id": order_id,
            "preventivo_id": ordine.get("preventivo_id"), "data_ordine": ordine.get("data"),
            "data_prevista": None, "priorita": "normale", "note": ordine.get("note") or "",
            "warehouse_id": "elios-tech", "stato": "da_preparare" if rows else "solo_servizi", "righe": rows,
            "servizi": servizi, "tipo_commessa": tipo, "stato_servizi": "Da programmare" if servizi else None,
            "operatore_carico": None, "presa_in_carico_at": None, "completed_at": None,
            "shipped_at": None, "cancelled_at": None, "created_by": current.get("username"),
            "created_at": now, "updated_at": now, "operation_id": event_logger.new_operation_id("CMM"),
        }
        await db.commesse.insert_one(doc)
        await db.crm_ordini_clienti.update_one(
            {"id": order_id},
            {"$set": {"stato": "In lavorazione", "stato_logistico": "Da preparare" if rows else "Nessun materiale da preparare", "updated_at": now}},
        )
        if not rows and any(str(s.get("tipo_riga") or s.get("categoria") or "").strip().lower() in ("installazione", "posa") for s in servizi) and doc.get("cliente_id") and doc.get("sede_id"):
            await db.crm_installazioni.insert_one({
                "id": str(uuid.uuid4()), "commessa_id": doc.get("id"),
                "ordine_cliente_id": order_id, "cliente_id": doc.get("cliente_id"),
                "sede_id": doc.get("sede_id"), "tecnico": "", "data": "",
                "stato": "Da programmare",
                "note": f"Creata automaticamente dalla commessa #{doc.get('number')}",
                "created_by": current.get("username"), "created_at": now, "updated_at": now,
            })
        return {"ok": True, "created": True, "commessa": _serialize(doc)}

    @router.get("/{cid}")
    async def get_commessa(cid: str):
        await _require_enabled()
        doc = await db.commesse.find_one({"id": cid})
        if not doc: raise HTTPException(404, "Commessa non trovata")
        # Ripara record storici incoerenti: una commessa con materiale non può restare "solo_servizi".
        if (doc.get("righe") or []) and doc.get("stato") == "solo_servizi":
            await db.commesse.update_one({"id": cid}, {"$set": {"stato": "da_preparare", "updated_at": _now()}})
            doc["stato"] = "da_preparare"
        return _serialize(doc)

    @router.post("")
    async def create_commessa(body: CommessaCreate, current=Depends(_require_commesse_create)):
        """Crea una commessa collegata al flusso Ordine cliente → Commessa.
        Resta retrocompatibile con le vecchie commesse importate.
        """
        await _require_enabled()
        if body.priorita not in PRIORITA:
            raise HTTPException(400, "Priorità non valida")
        exists = await db.commesse.find_one({"number": body.number, "stato": {"$ne": "annullata"}})
        if exists:
            raise HTTPException(409, f"Numero commessa '{body.number}' già in uso")

        cliente_id = (body.cliente_id or "").strip() or None
        sede_id = (body.sede_id or "").strip() or None
        ordine_cliente_id = (body.ordine_cliente_id or "").strip() or None
        preventivo_id = (body.preventivo_id or "").strip() or None

        # Se viene scelto un ordine cliente, è lui la fonte dei collegamenti.
        if ordine_cliente_id:
            existing_for_order = await db.commesse.find_one({
                "ordine_cliente_id": ordine_cliente_id,
                "stato": {"$ne": "annullata"},
            })
            if existing_for_order:
                raise HTTPException(409, f"L'ordine cliente è già collegato alla commessa #{existing_for_order.get('number')}")
            ordine = await db.crm_ordini_clienti.find_one({"id": ordine_cliente_id})
            if not ordine:
                raise HTTPException(400, "Ordine cliente non valido")
            for current_value, expected, label in (
                (cliente_id, ordine.get("cliente_id"), "cliente"),
                (sede_id, ordine.get("sede_id"), "sede"),
                (preventivo_id, ordine.get("preventivo_id"), "preventivo"),
            ):
                if current_value and expected and str(current_value) != str(expected):
                    raise HTTPException(400, f"{label.capitalize()} non coerente con l'ordine cliente")
            cliente_id = cliente_id or ordine.get("cliente_id")
            sede_id = sede_id or ordine.get("sede_id")
            preventivo_id = preventivo_id or ordine.get("preventivo_id")

        cliente_nome = body.cliente.strip()
        if cliente_id:
            cliente_doc = await db.crm_clienti.find_one({"id": cliente_id})
            if not cliente_doc:
                raise HTTPException(400, "Cliente non valido")
            cliente_nome = (
                cliente_doc.get("ragione_sociale")
                or " ".join(x for x in [cliente_doc.get("nome"), cliente_doc.get("cognome")] if x)
                or cliente_nome
            ).strip()

        if sede_id:
            sede = await db.crm_sedi.find_one({"id": sede_id})
            if not sede:
                raise HTTPException(400, "Sede non valida")
            if cliente_id and str(sede.get("cliente_id")) != str(cliente_id):
                raise HTTPException(400, "La sede non appartiene al cliente")

        op_id = event_logger.new_operation_id("CMM")
        doc = {
            "id": str(uuid.uuid4()),
            "number": body.number.strip(),
            "cliente": cliente_nome,
            "cliente_id": cliente_id,
            "sede_id": sede_id,
            "ordine_cliente_id": ordine_cliente_id,
            "preventivo_id": preventivo_id,
            "order_page_id": (body.order_page_id or "").strip() or None,
            "data_ordine": body.data_ordine,
            "data_prevista": body.data_prevista,
            "priorita": body.priorita,
            "note": body.note,
            "warehouse_id": body.warehouse_id if body.warehouse_id in ("elios-tech", "verona") else "elios-tech",
            "stato": "da_preparare",
            "righe": [{**r.model_dump(), "qty_prelevata": 0.0, "seriali_prelevati": []} for r in body.righe],
            "operatore_carico": None,
            "presa_in_carico_at": None,
            "completed_at": None, "shipped_at": None, "cancelled_at": None,
            "created_by": current.get("username"),
            "created_at": _now(), "updated_at": _now(),
            "operation_id": op_id,
        }
        await db.commesse.insert_one(doc)

        # L'ordine passa automaticamente in lavorazione quando nasce la commessa.
        if ordine_cliente_id:
            await db.crm_ordini_clienti.update_one(
                {"id": ordine_cliente_id},
                {"$set": {
                    "stato": "In lavorazione",
                    "stato_logistico": "Da preparare",
                    "updated_at": _now(),
                }},
            )

        await event_logger.log_event(
            db, category="COMMESSE", event_type="COMMESSA_CREATA",
            action="commesse.create", level="INFO", status="SUCCESS",
            user=current.get("username"), user_role=current.get("role"),
            operation_id=op_id, endpoint="POST /api/commesse",
            customer=cliente_nome,
            message=f"Commessa #{body.number} creata per {cliente_nome} ({len(body.righe)} righe)",
            details={
                "commessa_id": doc["id"], "number": body.number,
                "righe_count": len(body.righe), "priorita": body.priorita,
                "cliente_id": cliente_id, "sede_id": sede_id,
                "ordine_cliente_id": ordine_cliente_id,
            },
        )
        return _serialize(doc)

    @router.patch("/{cid}")
    async def update_commessa(cid: str, body: CommessaUpdate, current=Depends(_require_commesse_manager)):
        """F29/F30 — Admin o Responsabile con permesso 'gestione_commesse' può modificare commesse."""
        """F27 — Modifica completa con regole per stato + audit diff dettagliato.
        - Da preparare: full edit
        - In preparazione/Parziale: qty_richiesta >= qty_prelevata, no rimozione righe con prelievi, no rimozione seriali già prelevati
        - Pronta: blocco righe (annulla completamento per modificare)
        - Bozza spedizione: blocco (annulla prima la bozza)
        - Spedita/Annullata: blocco (usa reopen)
        """
        await _require_enabled()
        doc = await db.commesse.find_one({"id": cid})
        if not doc: raise HTTPException(404, "Commessa non trovata")
        stato = doc.get("stato")
        if stato in ("spedita", "annullata"):
            raise HTTPException(409, f"Commessa {stato}: usa 'Riapri' per modificarla" if stato == "annullata" else "Commessa spedita: non modificabile")
        if stato == "bozza_spedizione":
            raise HTTPException(409, "Bozza spedizione attiva: annulla la bozza per modificare la commessa")
        updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
        if "priorita" in updates and updates["priorita"] not in PRIORITA:
            raise HTTPException(400, "Priorità non valida")
        if "warehouse_id" in updates:
            if updates["warehouse_id"] not in ("elios-tech", "verona"):
                raise HTTPException(400, "Deposito non valido")
            if updates["warehouse_id"] != (doc.get("warehouse_id") or "elios-tech"):
                has_picks = any(float(r.get("qty_prelevata") or 0) > 0 or (r.get("seriali_prelevati") or []) for r in (doc.get("righe") or []))
                if has_picks or stato not in ("da_preparare", "in_preparazione", "parziale"):
                    raise HTTPException(409, "Il deposito può essere cambiato solo prima di effettuare prelievi")

        if "righe" in updates:
            if stato == "pronta":
                raise HTTPException(409, "Commessa pronta: le righe non sono modificabili. Annulla il completamento per modificarle.")
            old_righe = doc.get("righe") or []
            old_by_pid = {r.get("product_page_id"): r for r in old_righe}
            new_input = updates["righe"]
            merged = []
            seen_pids = set()
            for r in new_input:
                rr = r.model_dump() if hasattr(r, "model_dump") else dict(r)
                pid = rr.get("product_page_id")
                seen_pids.add(pid)
                old = old_by_pid.get(pid)
                if old and (float(old.get("qty_prelevata") or 0) > 0 or (old.get("seriali_prelevati") or [])):
                    # Riga con prelievi: preservali + verifica compatibilità quantità
                    qp = float(old.get("qty_prelevata") or 0)
                    if float(rr.get("qty_richiesta") or 0) < qp:
                        raise HTTPException(400,
                            f"'{rr.get('product_name')}': quantità richiesta ({rr.get('qty_richiesta')}) inferiore alla già preparata ({qp:g}). Aumenta la quantità o rimuovi i prelievi.")
                    if rr.get("tipo_gestione") != old.get("tipo_gestione"):
                        raise HTTPException(400,
                            f"'{rr.get('product_name')}': impossibile cambiare tipo gestione con prelievi già effettuati.")
                    rr["qty_prelevata"] = qp
                    rr["seriali_prelevati"] = list(old.get("seriali_prelevati") or [])
                else:
                    # Nuova riga o riga senza prelievi
                    rr["qty_prelevata"] = 0.0
                    rr["seriali_prelevati"] = []
                merged.append(rr)
            # Verifica righe eliminate: quelle con prelievi non possono essere rimosse
            removed_with_picks = [r for pid, r in old_by_pid.items()
                                  if pid not in seen_pids and
                                  (float(r.get("qty_prelevata") or 0) > 0 or (r.get("seriali_prelevati") or []))]
            if removed_with_picks:
                names = ", ".join(r.get("product_name") or "?" for r in removed_with_picks)
                raise HTTPException(400, f"Non puoi rimuovere prodotti con prelievi effettuati: {names}. Prima rimuovi i prelievi.")
            updates["righe"] = merged

        # Calcola diff prima di applicare (per audit)
        diff = {}
        for k in ("cliente", "data_ordine", "data_prevista", "priorita", "note"):
            if k in updates and doc.get(k) != updates[k]:
                diff[k] = {"before": doc.get(k), "after": updates[k]}
        if "righe" in updates:
            old_pids = {r.get("product_page_id") for r in (doc.get("righe") or [])}
            new_pids = {r.get("product_page_id") for r in updates["righe"]}
            added = [r for r in updates["righe"] if r.get("product_page_id") not in old_pids]
            removed = [r for r in (doc.get("righe") or []) if r.get("product_page_id") not in new_pids]
            qty_changes = []
            for r in updates["righe"]:
                pid = r.get("product_page_id")
                if pid in old_pids:
                    old = next((o for o in (doc.get("righe") or []) if o.get("product_page_id") == pid), None)
                    if old and float(old.get("qty_richiesta") or 0) != float(r.get("qty_richiesta") or 0):
                        qty_changes.append({"product": r.get("product_name"),
                                            "before": old.get("qty_richiesta"), "after": r.get("qty_richiesta")})
            if added or removed or qty_changes:
                diff["righe"] = {
                    "added": [{"product": r.get("product_name"), "qty": r.get("qty_richiesta")} for r in added],
                    "removed": [{"product": r.get("product_name"), "qty": r.get("qty_richiesta")} for r in removed],
                    "qty_changes": qty_changes,
                }
        # Ricalcola stato se righe cambiate (in preparazione ↔ parziale, ecc.)
        if "righe" in updates:
            preview = {**doc, **updates}
            updates["stato"] = _compute_stato(preview)
            if updates["stato"] == stato:
                updates.pop("stato")

        updates["updated_at"] = _now()
        await db.commesse.update_one({"id": cid}, {"$set": updates})
        await event_logger.log_event(
            db, category="COMMESSE", event_type="COMMESSA_MODIFICATA",
            action="commesse.update", level="INFO", status="SUCCESS",
            user=current.get("username"), operation_id=doc.get("operation_id"),
            endpoint=f"PATCH /api/commesse/{cid}",
            customer=doc.get("cliente"),
            message=f"Commessa #{doc.get('number')} modificata ({len(diff)} campi)",
            details={"commessa_id": cid, "changed_fields": list(diff.keys()), "diff": diff},
        )
        fresh = await db.commesse.find_one({"id": cid})
        return _serialize(fresh)

    @router.post("/{cid}/reopen")
    async def reopen_commessa(cid: str, current=Depends(deps.require_admin)):
        """F27/F29 — SOLO ADMIN. Riapre una commessa annullata mantenendo storico e prelievi.
        Ricalcola lo stato in base ai prelievi effettivi (da_preparare / in_preparazione / parziale / pronta).
        Non crea nuova commessa: stesso id, stesso operation_id."""
        await _require_enabled()
        doc = await db.commesse.find_one({"id": cid})
        if not doc: raise HTTPException(404, "Commessa non trovata")
        if doc.get("stato") != "annullata":
            raise HTTPException(409, f"Riapri disponibile solo su commesse annullate (stato attuale: {doc.get('stato')})")
        # Ricalcola stato: se ci sono prelievi → in_preparazione/parziale/pronta; altrimenti da_preparare
        base = {**doc, "stato": "in_preparazione"}
        new_stato = _compute_stato(base)
        if new_stato == "spedita":  # safety
            new_stato = "pronta"
        updated = await db.commesse.find_one_and_update(
            {"id": cid, "stato": "annullata"},
            {"$set": {"stato": new_stato, "updated_at": _now()},
             "$unset": {"cancelled_at": ""}},
            return_document=True,
        )
        if not updated:
            raise HTTPException(409, "Riapertura non riuscita (stato cambiato in concorrenza)")
        await event_logger.log_event(
            db, category="COMMESSE", event_type="COMMESSA_RIAPERTA",
            action="commesse.reopen", level="INFO", status="SUCCESS",
            user=current.get("username"), operation_id=doc.get("operation_id"),
            endpoint=f"POST /api/commesse/{cid}/reopen",
            customer=doc.get("cliente"),
            message=f"Commessa #{doc.get('number')} riaperta (nuovo stato: {new_stato})",
            details={"commessa_id": cid, "previous_stato": "annullata", "new_stato": new_stato},
        )
        return _serialize(updated)

    @router.delete("/{cid}")
    async def delete_commessa(cid: str, current=Depends(_require_commesse_delete)):
        """F27/F29/F30/F30.c — Cancellazione definitiva con permesso dedicato.

        Regole:
        - Commesse ATTIVE (stato != annullata): bloccata se esistono operazioni
          collegate (spedizione confermata, storico spedizioni, bozza in corso,
          picking o materiale spedito). Usare "Annulla" per queste.
        - Commesse ANNULLATE: consentita se tutte le spedizioni referenced sono
          effettivamente `status=cancelled` in db.checklists (rollback completato).
          Le righe sono state resettate durante il cancel, quindi picking/shipped
          sono 0. Lo storico spedizioni (incl. entry di cancellation) è ammesso.
        """
        await _require_enabled()
        doc = await db.commesse.find_one({"id": cid})
        if not doc:
            raise HTTPException(404, "Commessa non trovata")
        doc_count = await db.documents.count_documents({"resource": "commesse", "record_id": cid})
        if doc_count:
            raise HTTPException(409, f"Impossibile eliminare: sono presenti {doc_count} documenti collegati")
        stato = doc.get("stato")
        blockers: List[str] = []

        if stato == "annullata":
            # Verifica che tutti i checklist referenced siano effettivamente cancelled.
            # Le entry di storico con type="cancellation" non hanno shipment_id → skip.
            ship_ids: set = set()
            for h in (doc.get("shipments_history") or []):
                sid = h.get("shipment_id") or h.get("checklist_id")
                if sid: ship_ids.add(sid)
            if doc.get("shipment_ref"):
                ship_ids.add(doc.get("shipment_ref"))
            active_shipments: List[str] = []
            for sid in ship_ids:
                ck = await db.checklists.find_one({"id": sid})
                if ck and ck.get("status") != "cancelled":
                    active_shipments.append(sid)
            if active_shipments:
                blockers.append(
                    f"{len(active_shipments)} spedizioni non ancora annullate: "
                    + ", ".join(active_shipments[:3])
                    + (" …" if len(active_shipments) > 3 else "")
                )
        else:
            # Regole strette per commesse non-annullate
            if doc.get("shipment_ref") or stato == "spedita":
                blockers.append("commessa collegata a una spedizione confermata")
            if doc.get("shipments_history"):
                blockers.append(f"esistono {len(doc.get('shipments_history') or [])} spedizioni nello storico")
            if doc.get("shipment_draft"):
                blockers.append("è presente una bozza di spedizione in corso")
            picked_rows = 0
            shipped_rows = 0
            for r in (doc.get("righe") or []):
                if float(r.get("qty_prelevata") or 0) > 0 or (r.get("seriali_prelevati") or []):
                    picked_rows += 1
                if float(r.get("qty_spedita") or 0) > 0 or (r.get("seriali_spediti") or []):
                    shipped_rows += 1
            if picked_rows:
                blockers.append(f"picking effettuato su {picked_rows} righe")
            if shipped_rows:
                blockers.append(f"materiale già spedito su {shipped_rows} righe")

        if blockers:
            raise HTTPException(
                status_code=409,
                detail=(
                    "Cancellazione definitiva bloccata: " + "; ".join(blockers) +
                    (". Annulla prima le spedizioni pendenti." if stato == "annullata"
                     else ". Usa 'Annulla' per conservare lo storico.")
                ),
            )
        # Log PRIMA della cancellazione (retention audit)
        await event_logger.log_event(
            db, category="COMMESSE", event_type="COMMESSA_ELIMINATA",
            action="commesse.delete", level="WARNING", status="SUCCESS",
            user=current.get("username"), user_role=current.get("role"),
            operation_id=doc.get("operation_id"),
            endpoint=f"DELETE /api/commesse/{cid}",
            customer=doc.get("cliente"),
            message=(f"Commessa #{doc.get('number')} ELIMINATA DEFINITIVAMENTE da Admin {current.get('username')} "
                     f"(stato pre-delete: {stato})"),
            details={"commessa_id": cid, "number": doc.get("number"), "cliente": doc.get("cliente"),
                     "stato": stato, "righe_snapshot": doc.get("righe") or [],
                     "shipments_history_snapshot": doc.get("shipments_history") or []},
        )
        await db.commesse.delete_one({"id": cid})
        return {"ok": True, "deleted": cid}

    @router.post("/{cid}/take")
    async def take_commessa(cid: str, current=Depends(deps.get_current_user)):
        await _require_enabled()
        # F23.b — Presa in carico ATOMICA per prevenire race condition tra operatori.
        # find_one_and_update accetta la mutazione SOLO se lo stato è ancora 'da_preparare'
        # e non c'è già un operatore_carico. Il secondo operatore che tenta in parallelo
        # riceve doc=None → 409 (nessun falso successo, log corretto).
        updated = await db.commesse.find_one_and_update(
            {"id": cid, "stato": "da_preparare", "$or": [
                {"operatore_carico": None}, {"operatore_carico": {"$exists": False}}
            ]},
            {"$set": {
                "stato": "in_preparazione",
                "operatore_carico": current.get("username"),
                "presa_in_carico_at": _now(), "updated_at": _now(),
            }},
            return_document=True,
        )
        if not updated:
            # Verifica motivo del fallimento per messaggio chiaro
            doc = await db.commesse.find_one({"id": cid})
            if not doc: raise HTTPException(404, "Commessa non trovata")
            if doc.get("operatore_carico") and doc.get("operatore_carico") != current.get("username"):
                raise HTTPException(409, f"Commessa già presa in carico da {doc.get('operatore_carico')}")
            if doc.get("operatore_carico") == current.get("username"):
                # Idempotente: se sono io stesso, restituisco lo stato attuale
                return _serialize(doc)
            raise HTTPException(409, f"Presa in carico non consentita nello stato {doc.get('stato')}")
        doc = updated
        await event_logger.log_event(
            db, category="COMMESSE", event_type="COMMESSA_PRESA_IN_CARICO",
            action="commesse.take", level="INFO", status="SUCCESS",
            user=current.get("username"), operation_id=doc.get("operation_id"),
            endpoint=f"POST /api/commesse/{cid}/take",
            customer=doc.get("cliente"),
            message=f"Commessa #{doc.get('number')} presa in carico da {current.get('username')}",
            details={"commessa_id": cid},
        )
        return _serialize(doc)

    @router.post("/{cid}/pick")
    async def pick_commessa(cid: str, body: PickBody, current=Depends(deps.get_current_user)):
        """Prelievo di una riga. Non scala inventario: registra solo cosa è stato preso.
        - A Quantità: body.quantity = incremento (o decremento se negativo)
        - A Seriale: body.serial = un singolo seriale
        """
        await _require_enabled()
        doc = await db.commesse.find_one({"id": cid})
        if not doc: raise HTTPException(404, "Commessa non trovata")
        if doc.get("stato") in ("spedita", "annullata", "bozza_spedizione"):
            raise HTTPException(409, f"Prelievo non consentito. Stato: {doc.get('stato')}")
        if doc.get("stato") == "solo_servizi" and (doc.get("righe") or []):
            doc["stato"] = "da_preparare"
        if doc.get("operatore_carico") and doc.get("operatore_carico") != current.get("username"):
            raise HTTPException(409, f"Commessa in carico a {doc.get('operatore_carico')}")
        # UX R17: al primo + / scanner prende automaticamente in carico la commessa.
        if doc.get("stato") == "da_preparare":
            doc["stato"] = "in_preparazione"
            doc["operatore_carico"] = current.get("username")
            doc["presa_in_carico_at"] = _now()
            await db.commesse.update_one({"id": cid}, {"$set": {
                "stato": "in_preparazione", "operatore_carico": current.get("username"),
                "presa_in_carico_at": doc["presa_in_carico_at"], "updated_at": _now(),
            }})
        righe = doc.get("righe") or []
        idx = body.riga_index
        if idx < 0 or idx >= len(righe):
            raise HTTPException(400, "riga_index fuori range")
        riga = righe[idx]
        tg = riga.get("tipo_gestione")
        qty_req = float(riga.get("qty_richiesta") or 0)
        qty_prev = float(riga.get("qty_prelevata") or 0)

        if tg == "a_quantita":
            if body.quantity is None:
                raise HTTPException(400, "quantity richiesta per prodotti A Quantità")
            delta = float(body.quantity)
            new_prev = qty_prev + delta
            if new_prev < 0:
                raise HTTPException(400, "Quantità prelevata non può essere negativa")
            # F30 — Il residuo è calcolato considerando anche ciò che è già stato spedito
            qty_ship = float(riga.get("qty_spedita") or 0)
            if new_prev + qty_ship > qty_req:
                raise HTTPException(400, f"Superata quantità richiesta ({qty_req}) — già spediti {qty_ship:g}, preparati {new_prev:g}")
            # Per incrementi, verifica la giacenza reale del deposito e le quantità già riservate da altre commesse.
            if delta > 0:
                try:
                    from inventory_router import get_svc as _get_svc
                    svc = await _get_svc(db)
                    warehouse_id = doc.get("warehouse_id") or "elios-tech"
                    inv_item = await svc.get_item(riga.get("product_page_id"), warehouse_id=warehouse_id)
                    stock_available = float(inv_item.get("quantity") or 0)
                    active_states = ["in_preparazione", "parziale", "pronta", "bozza_spedizione", "parzialmente_spedita"]
                    reserved_other = 0.0
                    async for oc in db.commesse.find({"id": {"$ne": cid}, "warehouse_id": warehouse_id, "stato": {"$in": active_states}}):
                        for origa in (oc.get("righe") or []):
                            if origa.get("product_page_id") == riga.get("product_page_id"):
                                reserved_other += float(origa.get("qty_prelevata") or 0)
                    if reserved_other + new_prev > stock_available:
                        libero = max(0.0, stock_available - reserved_other)
                        raise HTTPException(409, f"Giacenza insufficiente nel deposito selezionato: disponibili {libero:g} {riga.get('unit') or 'pz'}")
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Validazione giacenza fallita: {e}")
                    raise HTTPException(502, "Errore validazione giacenza")
            riga["qty_prelevata"] = new_prev
            log_msg = f"Prelievo {delta:+g} × {riga.get('product_name')} (commessa #{doc.get('number')})"
            evt = "PRELIEVO_QUANTITA"
        elif tg == "a_seriale":
            if not (body.serial or "").strip():
                raise HTTPException(400, "serial richiesto per prodotti A Seriale")
            sn = body.serial.strip()
            existing = riga.get("seriali_prelevati") or []
            spediti = riga.get("seriali_spediti") or []
            # F28 — Rimozione seriale (decremento controllato)
            if body.remove:
                match_idx = next((i for i, s in enumerate(existing) if s.lower() == sn.lower()), None)
                if match_idx is None:
                    raise HTTPException(404, f"Seriale '{sn}' non presente tra i prelievi di questa riga")
                new_serials = existing[:match_idx] + existing[match_idx+1:]
                riga["seriali_prelevati"] = new_serials
                riga["qty_prelevata"] = max(0.0, qty_prev - 1)
                log_msg = f"Rimozione seriale {sn} × {riga.get('product_name')} (commessa #{doc.get('number')})"
                evt = "PRELIEVO_SERIALE_RIMOSSO"
            else:
                if any(s.lower() == sn.lower() for s in existing):
                    raise HTTPException(409, "Seriale già prelevato per questa riga")
                # F30 — Rifiuta seriali già SPEDITI nella stessa riga
                if any(s.lower() == sn.lower() for s in spediti):
                    raise HTTPException(409, f"Seriale '{sn}' già spedito in una precedente spedizione di questa commessa")
                # Verifica cross-righe (non prelevare due volte nella stessa commessa)
                # F30 — Controlla anche seriali_spediti di altre righe
                for j, other in enumerate(righe):
                    if j == idx: continue
                    for s in (other.get("seriali_prelevati") or []):
                        if s.lower() == sn.lower():
                            raise HTTPException(409, f"Seriale già prelevato per '{other.get('product_name')}'")
                    for s in (other.get("seriali_spediti") or []):
                        if s.lower() == sn.lower():
                            raise HTTPException(409, f"Seriale già spedito per '{other.get('product_name')}'")
                # Validazione contro il deposito selezionato e contro prenotazioni di altre commesse.
                try:
                    from inventory_router import get_svc as _get_svc
                    svc = await _get_svc(db)
                    warehouse_id = doc.get("warehouse_id") or "elios-tech"
                    found = await svc.find_serial_in_inventory(sn, warehouse_id=warehouse_id)
                    if not found:
                        anywhere = await svc.latest_serial_status(sn)
                        if anywhere.get("status") == "in_warehouse":
                            other_wh = anywhere.get("warehouse_name") or anywhere.get("warehouse_id") or "altro deposito"
                            raise HTTPException(409, f"Il seriale è disponibile in {other_wh}, non nel deposito selezionato")
                        if anywhere.get("status") not in (None, "unseen"):
                            raise HTTPException(409, f"Seriale non disponibile: stato {anywhere.get('status')}")
                        raise HTTPException(400, "Seriale inesistente o non caricato tramite Arrivi")
                    if (found.get("id") or found.get("page_id")) != riga.get("product_page_id"):
                        raise HTTPException(400, f"Il seriale appartiene a '{found.get('name')}', non a '{riga.get('product_name')}'")
                    # Lo stesso seriale non può essere prenotato in un'altra commessa attiva.
                    reserved = await db.commesse.find_one({
                        "id": {"$ne": cid},
                        "stato": {"$in": ["in_preparazione", "parziale", "pronta", "bozza_spedizione", "parzialmente_spedita"]},
                        "righe.seriali_prelevati": {"$regex": f"^{re.escape(sn)}$", "$options": "i"},
                    })
                    if reserved:
                        raise HTTPException(409, f"Seriale già preparato nella commessa #{reserved.get('number')}")
                    qty_ship_s = float(riga.get("qty_spedita") or 0)
                    if qty_prev + 1 + qty_ship_s > qty_req:
                        raise HTTPException(400, f"Superata quantità richiesta ({qty_req}) — già spediti {qty_ship_s:g}")
                    riga["seriali_prelevati"] = existing + [sn]
                    riga["qty_prelevata"] = qty_prev + 1
                except HTTPException:
                    raise
                except Exception as e:
                    logger.error(f"Validazione seriale fallita: {e}")
                    raise HTTPException(502, "Errore validazione inventario")
                log_msg = f"Prelievo seriale {sn} × {riga.get('product_name')} (commessa #{doc.get('number')})"
                evt = "PRELIEVO_SERIALE"
        else:
            raise HTTPException(400, f"tipo_gestione non valido: {tg}")

        # Ricalcola stato
        doc["righe"] = righe
        new_stato = _compute_stato(doc)
        await db.commesse.update_one({"id": cid}, {"$set": {
            "righe": righe, "stato": new_stato, "updated_at": _now(),
        }})
        await event_logger.log_event(
            db, category="COMMESSE", event_type=evt,
            action="commesse.pick", level="INFO", status="SUCCESS",
            user=current.get("username"), operation_id=doc.get("operation_id"),
            endpoint=f"POST /api/commesse/{cid}/pick",
            product=riga.get("product_name"), product_code=riga.get("product_code"),
            serial=body.serial, customer=doc.get("cliente"),
            quantity_change=(float(body.quantity) if body.quantity is not None else 1.0),
            message=log_msg,
            details={"commessa_id": cid, "riga_index": idx, "new_stato": new_stato},
        )
        fresh = await db.commesse.find_one({"id": cid})
        return _serialize(fresh)

    @router.post("/{cid}/complete")
    async def complete_commessa(cid: str, current=Depends(deps.get_current_user)):
        await _require_enabled()
        doc = await db.commesse.find_one({"id": cid})
        if not doc: raise HTTPException(404, "Commessa non trovata")
        stato_calc = _compute_stato(doc)
        if stato_calc != "pronta":
            raise HTTPException(409, "Commessa non completa: non tutte le righe sono state prelevate integralmente")
        await db.commesse.update_one({"id": cid}, {"$set": {
            "stato": "pronta", "completed_at": _now(), "updated_at": _now(),
        }})
        await event_logger.log_event(
            db, category="COMMESSE", event_type="COMMESSA_COMPLETATA",
            action="commesse.complete", level="INFO", status="SUCCESS",
            user=current.get("username"), operation_id=doc.get("operation_id"),
            endpoint=f"POST /api/commesse/{cid}/complete",
            customer=doc.get("cliente"),
            message=f"Commessa #{doc.get('number')} completata → pronta per spedizione",
            details={"commessa_id": cid},
        )
        return _serialize(await db.commesse.find_one({"id": cid}))

    @router.post("/{cid}/reopen-preparation")
    async def reopen_preparation(cid: str, current=Depends(deps.require_admin)):
        """F29 — Riapre la preparazione di una commessa 'pronta' o 'parzialmente_spedita'
        (per continuare il picking sul residuo). Solo admin."""
        await _require_enabled()
        doc = await db.commesse.find_one({"id": cid})
        if not doc: raise HTTPException(404, "Commessa non trovata")
        if doc.get("stato") not in ("pronta", "parzialmente_spedita"):
            raise HTTPException(409, f"Riapertura preparazione non consentita: stato {doc.get('stato')}")
        # Da parzialmente_spedita: torna 'in_preparazione' per il residuo
        # (righe già hanno qty_spedita accumulato, il "residuo" viene calcolato lato UI/pick)
        updated = await db.commesse.find_one_and_update(
            {"id": cid, "stato": {"$in": ["pronta", "parzialmente_spedita"]}},
            {"$set": {"stato": "in_preparazione", "updated_at": _now()}, "$unset": {"completed_at": ""}},
            return_document=True,
        )
        if not updated:
            raise HTTPException(409, "Riapertura preparazione non riuscita (stato cambiato)")
        await event_logger.log_event(
            db, category="COMMESSE", event_type="PREPARAZIONE_RIAPERTA",
            action="commesse.reopen_preparation", level="INFO", status="SUCCESS",
            user=current.get("username"), user_role=current.get("role"),
            operation_id=doc.get("operation_id"),
            endpoint=f"POST /api/commesse/{cid}/reopen-preparation",
            customer=doc.get("cliente"),
            message=f"Preparazione commessa #{doc.get('number')} riaperta da {doc.get('stato')}",
            details={"commessa_id": cid, "previous_stato": doc.get("stato")},
        )
        return _serialize(updated)

    async def _build_draft_payload(doc: Dict[str, Any], operator: str) -> Dict[str, Any]:
        """Costruisce lo snapshot bozza dai dati correnti della commessa.
        F28.b/c — payload IDENTICO a quello inviato da /ChecklistPage (spedizione normale):
        include shipping_date, order_page_id, notes, e qr_codes allineati ai seriali.
        F30 — Legge i QR da `qr_bindings` (multi-slot). Per il ChecklistPayload legacy
        che accetta 1 QR per seriale, includiamo il primo binding attivo trovato.
        L'elenco completo dei bindings resta comunque persistito e visibile via /qr/bindings.
        """
        items_payload = []
        for r in doc.get("righe") or []:
            serials = list(r.get("seriali_prelevati") or [])
            # F30 — Prima cerca in qr_bindings (nuovo), fallback qr_associations (legacy)
            qr_codes: List[str] = []
            qr_bindings: List[Dict[str, str]] = []
            if serials:
                sn_lows = [s.strip().lower() for s in serials if s]
                if sn_lows:
                    qr_map: Dict[str, str] = {}
                    # R15: conserva TUTTI i QR per presa; qr_codes resta solo compatibilità legacy.
                    async for d in db.qr_bindings.find(
                        {"serial_lower": {"$in": sn_lows}, "active": True}
                    ).sort("created_at", 1):
                        sl = d.get("serial_lower")
                        if not sl:
                            continue
                        qr = d.get("qr_code") or ""
                        qr_bindings.append({
                            "serial": d.get("serial") or next((x for x in serials if x.strip().lower() == sl), ""),
                            "slot": d.get("slot") or "single",
                            "qr_code": qr,
                        })
                        if sl not in qr_map:
                            qr_map[sl] = qr
                    # Legacy fallback per seriali non ancora in qr_bindings.
                    missing = [s for s in sn_lows if s not in qr_map]
                    if missing:
                        async for d in db.qr_associations.find(
                            {"serial_lower": {"$in": missing}, "active": True}
                        ):
                            sl = d.get("serial_lower")
                            if sl and sl not in qr_map:
                                qr_map[sl] = d.get("qr_code") or ""
                                qr_bindings.append({"serial": d.get("serial") or "", "slot": "single", "qr_code": d.get("qr_code") or ""})
                    qr_codes = [qr_map.get(s.strip().lower(), "") for s in serials]
            items_payload.append({
                "page_id": r.get("product_page_id"),
                "name": r.get("product_name"),
                "product_code": r.get("product_code"),
                "serialized": (r.get("tipo_gestione") == "a_seriale"),
                "serials": serials,
                "qr_codes": qr_codes,  # compatibilità legacy: primo QR per seriale
                "qr_bindings": qr_bindings,  # R15: tutti i QR, inclusi sinistra/destra Daze Duo
                "quantity": float(r.get("qty_prelevata") or 0),
                "unit": r.get("unit") or "pz",
            })
        # Data spedizione: usa data_prevista della commessa se presente, altrimenti oggi
        ship_date = doc.get("data_prevista") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # F28.c — Note: prefisso automatico con riferimento commessa per tracciabilità dello storico.
        base_notes = (doc.get("note") or "").strip()
        combined_notes = f"Commessa #{doc.get('number')}" + (f" — {base_notes}" if base_notes else "")
        return {
            "shipping_date": ship_date,
            "operator": operator,
            "structure": doc.get("cliente"),
            "taken_by": doc.get("operatore_carico") or operator,
            "order_page_id": doc.get("ordine_cliente_id") or doc.get("order_page_id"),
            "notes": combined_notes,
            "items": items_payload,
            "commessa_ref": doc.get("number"),
            "warehouse_id": doc.get("warehouse_id") or "elios-tech",
        }

    @router.post("/{cid}/draft")
    async def create_draft(cid: str, current=Depends(deps.get_current_user)):
        """F25.b — Crea/recupera una BOZZA DI SPEDIZIONE persistente sul server.
        - Idempotente: se esiste già una bozza per la commessa, ritorna quella.
        - Atomico: transizione stato pronta/parziale → bozza_spedizione via find_one_and_update.
        - non modifica direttamente il magazzino finché la spedizione non viene confermata.
        - F29.b — Accetta anche stato 'parziale' (spedizione parziale con residuo).
        """
        await _require_enabled()
        # Ripresa idempotente: se già in bozza_spedizione, restituisci lo snapshot corrente
        existing = await db.commesse.find_one({"id": cid})
        if not existing: raise HTTPException(404, "Commessa non trovata")
        if existing.get("stato") == "bozza_spedizione":
            return {"ok": True, "resumed": True, "draft": existing.get("shipment_draft"),
                    "commessa": _serialize(existing)}
        # Verifica preparato > 0 e impostazione operativa per gli stati parziali.
        if existing.get("stato") == "parziale":
            prep = sum(float(r.get("qty_prelevata") or 0) for r in (existing.get("righe") or []))
            if prep <= 0:
                raise HTTPException(409, "Nessun materiale preparato: impossibile creare spedizione parziale")
        # Transizione atomica da 'pronta' O 'parziale' a 'bozza_spedizione'
        draft_payload = await _build_draft_payload(existing, current.get("username"))
        draft_meta = {
            "created_by": current.get("username"), "created_at": _now(),
            "updated_at": _now(), "operation_id": existing.get("operation_id"),
            "previous_stato": existing.get("stato") or "pronta",
            "payload": draft_payload,
        }
        updated = await db.commesse.find_one_and_update(
            {"id": cid, "stato": {"$in": ["pronta", "parziale"]}},
            {"$set": {"stato": "bozza_spedizione", "shipment_draft": draft_meta, "updated_at": _now()}},
            return_document=True,
        )
        if not updated:
            fresh = await db.commesse.find_one({"id": cid})
            raise HTTPException(409, f"Bozza non creabile: stato attuale {fresh.get('stato')}")
        await event_logger.log_event(
            db, category="COMMESSE", event_type="BOZZA_CREATA",
            action="commesse.draft.create", level="INFO", status="SUCCESS",
            user=current.get("username"), operation_id=existing.get("operation_id"),
            endpoint=f"POST /api/commesse/{cid}/draft",
            customer=existing.get("cliente"),
            message=f"Bozza spedizione creata per commessa #{existing.get('number')}",
            details={"commessa_id": cid, "righe_count": len(draft_payload["items"])},
        )
        return {"ok": True, "resumed": False, "draft": draft_meta, "commessa": _serialize(updated)}

    @router.post("/{cid}/draft/cancel")
    async def cancel_draft(cid: str, current=Depends(deps.get_current_user)):
        """Annulla la bozza persistente e riporta la commessa a 'pronta'. Nessun tocco inventario."""
        await _require_enabled()
        current_doc = await db.commesse.find_one({"id": cid, "stato": "bozza_spedizione"})
        previous_stato = str(((current_doc or {}).get("shipment_draft") or {}).get("previous_stato") or "pronta")
        if previous_stato not in ("pronta", "parziale"):
            previous_stato = "pronta"
        updated = await db.commesse.find_one_and_update(
            {"id": cid, "stato": "bozza_spedizione"},
            {"$set": {"stato": previous_stato, "updated_at": _now()}, "$unset": {"shipment_draft": ""}},
            return_document=True,
        )
        if not updated:
            fresh = await db.commesse.find_one({"id": cid})
            if not fresh: raise HTTPException(404, "Commessa non trovata")
            raise HTTPException(409, f"Nessuna bozza attiva: stato {fresh.get('stato')}")
        await event_logger.log_event(
            db, category="COMMESSE", event_type="BOZZA_ANNULLATA",
            action="commesse.draft.cancel", level="INFO", status="SUCCESS",
            user=current.get("username"), operation_id=updated.get("operation_id"),
            endpoint=f"POST /api/commesse/{cid}/draft/cancel",
            customer=updated.get("cliente"),
            message=f"Bozza spedizione annullata per commessa #{updated.get('number')}",
            details={"commessa_id": cid},
        )
        return {"ok": True, "commessa": _serialize(updated)}

    @router.post("/{cid}/ship")
    async def ship_commessa(cid: str, request: Request, current=Depends(deps.get_current_user)):
        """F25.b/F28.b — CONFERMA la spedizione (partendo da bozza persistente).
        - Body opzionale {shipping_date: "YYYY-MM-DD"} per override.
        - Idempotente: se già spedita ritorna 200 con `already_shipped: true` (no doppia spedizione).
        - Esegue /api/checklist/send solo una volta (transizione atomica → spedita)."""
        await _require_enabled()
        doc = await db.commesse.find_one({"id": cid})
        if not doc: raise HTTPException(404, "Commessa non trovata")
        # F28.b — Idempotenza: se già spedita, ritorna il risultato precedente
        if doc.get("stato") == "spedita" and doc.get("shipment_ref"):
            return {"ok": True, "already_shipped": True,
                    "shipment": {"checklist_id": doc.get("shipment_ref"),
                                 "message": f"Commessa già spedita (id {doc.get('shipment_ref')})"},
                    "commessa": _serialize(doc)}
        # Body opzionale con override shipping_date/taken_by
        override: Dict[str, Any] = {}
        try:
            body = await request.json()
            if isinstance(body, dict):
                if body.get("shipping_date"): override["shipping_date"] = str(body["shipping_date"]).strip()
                if body.get("taken_by"): override["taken_by"] = str(body["taken_by"]).strip()
        except Exception:
            pass
        # Se la commessa è ancora 'pronta' o 'parziale', creiamo prima la bozza (retro-compat client)
        if doc.get("stato") in ("pronta", "parziale"):
            draft_meta = {
                "created_by": current.get("username"), "created_at": _now(),
                "updated_at": _now(), "operation_id": doc.get("operation_id"),
                "previous_stato": doc.get("stato") or "pronta",
                "payload": await _build_draft_payload(doc, current.get("username")),
            }
            promoted = await db.commesse.find_one_and_update(
                {"id": cid, "stato": {"$in": ["pronta", "parziale"]}},
                {"$set": {"stato": "bozza_spedizione", "shipment_draft": draft_meta, "updated_at": _now()}},
                return_document=True,
            )
            if not promoted:
                fresh = await db.commesse.find_one({"id": cid})
                # Race: se un altro operatore l'ha appena spedita, ritorna idempotente
                if fresh and fresh.get("stato") == "spedita":
                    return {"ok": True, "already_shipped": True,
                            "shipment": {"checklist_id": fresh.get("shipment_ref"), "message": "Commessa già spedita"},
                            "commessa": _serialize(fresh)}
                raise HTTPException(409, f"Impossibile confermare: stato {fresh.get('stato')}")
            doc = promoted
        if doc.get("stato") != "bozza_spedizione":
            raise HTTPException(409, "Confermabile solo da bozza_spedizione o pronta")
        auth_header = request.headers.get("Authorization") or ""
        # Usa il payload persistito (se presente) altrimenti ricostruisci dai dati correnti
        draft = doc.get("shipment_draft") or {}
        payload = draft.get("payload") or await _build_draft_payload(doc, current.get("username"))
        # Older drafts did not preserve the native order link.
        payload = {**payload, "order_page_id": doc.get("ordine_cliente_id") or doc.get("order_page_id") or payload.get("order_page_id")}
        # F28.b — Assicura shipping_date SEMPRE presente (retro-compat con bozze pre-fix)
        if not payload.get("shipping_date"):
            payload["shipping_date"] = doc.get("data_prevista") or datetime.now(timezone.utc).strftime("%Y-%m-%d")
        # Applica override utente (data / preso da)
        payload = {**payload, **override}
        # Ricostruisci items nel formato atteso da /checklist/send (senza product_code)
        items_payload = [{k: v for k, v in it.items() if k != "product_code"} for it in payload.get("items", [])]
        payload = {**payload, "items": items_payload}
        # F28.c — Rimuovi eventuali campi extra non riconosciuti da ChecklistPayload (extra="ignore" li ignora,
        # ma per pulizia log/curl li omettiamo). commessa_ref viene silenziosamente ignorato dal backend
        # (ChecklistPayload ha extra="ignore") ma lo lasciamo perché serve al log della commessa.
        try:
            # Dispatch through the same authenticated application. Render's PORT
            # is dynamic: a loopback request to 8001 fails in the Docker runtime.
            async with httpx.AsyncClient(
                transport=httpx.ASGITransport(app=request.app),
                base_url="http://internal", timeout=90.0,
                headers={"Authorization": auth_header},
            ) as client:
                r = await client.post("/api/checklist/send", json=payload)
            if r.status_code >= 400:
                await event_logger.log_event(
                    db, category="COMMESSE", event_type="COMMESSA_SPEDIZIONE_FALLITA",
                    action="commesse.ship", level="ERROR", status="FAILURE",
                    user=current.get("username"), operation_id=doc.get("operation_id"),
                    customer=doc.get("cliente"),
                    message=f"Spedizione commessa #{doc.get('number')} fallita: {r.status_code}",
                    details={"commessa_id": cid, "status": r.status_code, "error": r.text[:400]},
                )
                raise HTTPException(r.status_code, f"Spedizione fallita: {r.text[:200]}")
            ship_result = r.json()
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(500, f"Errore chiamata spedizione: {e}")
        # Spedizione parziale: se dopo lo scarico locale rimane materiale non ancora spedito
        # (qty_prelevata < qty_richiesta), la commessa va in 'parzialmente_spedita' e le righe
        # vengono resettate (qty_prelevata=0, seriali_prelevati=[]) MA accumuliamo qty_spedita/seriali_spediti
        # per storico e per calcolo del residuo. La preparazione può essere riaperta con
        # /reopen-preparation per il ciclo successivo.
        righe = doc.get("righe") or []
        any_residuo = False
        new_righe = []
        for r in righe:
            qr = float(r.get("qty_richiesta") or 0)
            qp = float(r.get("qty_prelevata") or 0)
            qs_prev = float(r.get("qty_spedita") or 0)
            new_qs = qs_prev + qp
            residuo = qr - new_qs
            if residuo > 0:
                any_residuo = True
            new_righe.append({
                **r,
                "qty_prelevata": 0.0,
                "seriali_prelevati": [],
                "qty_spedita": new_qs,
                "seriali_spediti": list(r.get("seriali_spediti") or []) + list(r.get("seriali_prelevati") or []),
            })
        # Determina stato finale in base al residuo (spedizione parziale vs completa)
        final_stato = "parzialmente_spedita" if any_residuo else "spedita"
        upd = {"$set": {
            "stato": final_stato, "shipped_at": _now(), "updated_at": _now(),
            "shipment_ref": ship_result.get("checklist_id"),
            "righe": new_righe,
        }, "$unset": {"shipment_draft": ""}}
        # Storico spedizioni multiple (aggiunge al vettore shipments_history)
        history_entry = {
            "shipment_id": ship_result.get("checklist_id"),
            "shipped_at": _now(), "operator": current.get("username"),
            "items": [{"product_name": r.get("product_name"),
                       "qty": float(r.get("qty_prelevata") or 0),
                       "seriali": list(r.get("seriali_prelevati") or [])}
                      for r in righe if float(r.get("qty_prelevata") or 0) > 0],
        }
        upd["$push"] = {"shipments_history": history_entry}
        await db.commesse.update_one({"id": cid}, upd)

        if doc.get("ordine_cliente_id"):
            order_set = {
                "stato_logistico": "Spedito" if final_stato == "spedita" else "Parzialmente spedito",
                "updated_at": _now(),
            }
            if final_stato == "spedita":
                order_set["stato_installazione"] = "Da programmare"
            await db.crm_ordini_clienti.update_one({"id": doc.get("ordine_cliente_id")}, {"$set": order_set})

        # L'installazione nasce automaticamente solo se è realmente prevista tra i servizi.
        services = doc.get("servizi") or []
        needs_installation = any(
            str(s.get("tipo_riga") or s.get("categoria") or "").strip().lower() in ("installazione", "posa")
            for s in services
        )
        if final_stato == "spedita" and needs_installation and doc.get("cliente_id") and doc.get("sede_id"):
            existing_installation = await db.crm_installazioni.find_one({"commessa_id": cid})
            if not existing_installation:
                now = _now()
                await db.crm_installazioni.insert_one({
                    "id": str(uuid.uuid4()),
                    "commessa_id": cid,
                    "ordine_cliente_id": doc.get("ordine_cliente_id"),
                    "cliente_id": doc.get("cliente_id"),
                    "sede_id": doc.get("sede_id"),
                    "tecnico": "",
                    "data": "",
                    "stato": "Da programmare",
                    "note": f"Creata automaticamente dalla commessa #{doc.get('number')}",
                    "created_by": current.get("username"),
                    "created_at": now,
                    "updated_at": now,
                })
        elif final_stato == "spedita" and doc.get("ordine_cliente_id") and not services:
            await db.crm_ordini_clienti.update_one(
                {"id": doc.get("ordine_cliente_id")},
                {"$set": {"stato": "Completato", "stato_installazione": "Non prevista", "updated_at": _now()}},
            )

        await event_logger.log_event(
            db, category="COMMESSE", event_type="COMMESSA_SPEDITA",
            action="commesse.ship", level="INFO", status="SUCCESS",
            user=current.get("username"), operation_id=doc.get("operation_id"),
            customer=doc.get("cliente"),
            message=f"Commessa #{doc.get('number')} → spedizione {ship_result.get('checklist_id')}",
            details={"commessa_id": cid, "shipment_id": ship_result.get("checklist_id"),
                     "inventory_warnings": ship_result.get("inventory_warnings") or []},
        )
        return {"ok": True, "shipment": ship_result, "commessa": _serialize(await db.commesse.find_one({"id": cid}))}

    @router.post("/{cid}/cancel")
    async def cancel_commessa(cid: str, request: Request, current=Depends(deps.require_admin)):
        """F29/F30.b — SOLO ADMIN. Annullamento commessa con ROLLBACK COMPLETO.

        - Da stati non-terminali (`da_preparare`, `in_preparazione`, `parziale`,
          `pronta`, `bozza_spedizione`): reset del picking + cancel bozza + stato
          → `annullata`.
        - Da stati con spedizioni confermate (`spedita`, `parzialmente_spedita`):
          rollback di TUTTE le spedizioni presenti in `shipments_history` (o
          `shipment_ref` se history è vuoto — legacy). Per ciascuna:
            1. annulla i movimenti locali della spedizione;
            2. ripristina seriali/quantità nel magazzino;
            3. aggiorna l'ordine cliente locale;
            4. disattiva le associazioni QR;
            5. marca la spedizione come annullata mantenendo lo storico.

        Body opzionale: {reason: str}
        """
        await _require_enabled()
        doc = await db.commesse.find_one({"id": cid})
        if not doc: raise HTTPException(404, "Commessa non trovata")
        stato = doc.get("stato")
        if stato == "annullata":
            raise HTTPException(409, "Commessa già annullata")
        # Parse reason opzionale
        reason: str = ""
        try:
            b = await request.json()
            if isinstance(b, dict):
                reason = str(b.get("reason") or "").strip()[:500]
        except Exception:
            pass

        # Costruisci lista spedizioni da rollbackare
        shipments = list(doc.get("shipments_history") or [])
        if not shipments and doc.get("shipment_ref"):
            # Legacy: nessun history ma un shipment_ref → costruisci entry sintetico
            shipments = [{
                "shipment_id": doc.get("shipment_ref"),
                "shipped_at": doc.get("shipped_at"),
                "operator": doc.get("operatore_carico"),
                "items": [],  # verranno recuperati dal db.checklists
            }]

        # Rollback delle spedizioni
        rollback_report: List[Dict[str, Any]] = []
        for sh in shipments:
            ship_id = sh.get("shipment_id") or sh.get("checklist_id")
            if not ship_id:
                continue
            try:
                res = await _rollback_shipment(db, ship_id, actor=current.get("username"), reason=reason)
                rollback_report.append({"shipment_id": ship_id, **res})
            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Rollback shipment {ship_id} failed: {e}")
                raise HTTPException(
                    status_code=502,
                    detail=(f"Rollback spedizione {ship_id} fallito: {e}. "
                            "Nessuna modifica applicata alla commessa. "
                            "Verifica il magazzino e lo storico spedizioni prima di riprovare."),
                )

        # Snapshot dei prelievi/spediti pre-cancellazione (per audit)
        picked_snapshot = [
            {"product": r.get("product_name"), "product_code": r.get("product_code"),
             "qty_prelevata": r.get("qty_prelevata"), "qty_spedita": r.get("qty_spedita"),
             "seriali_prelevati": r.get("seriali_prelevati"),
             "seriali_spediti": r.get("seriali_spediti")}
            for r in (doc.get("righe") or [])
            if (r.get("qty_prelevata") or 0) > 0 or (r.get("qty_spedita") or 0) > 0
            or (r.get("seriali_prelevati") or []) or (r.get("seriali_spediti") or [])
        ]

        # Reset delle righe (rimuovi picking + spediti — la commessa non ha più operazioni attive)
        new_righe: List[Dict[str, Any]] = []
        for r in (doc.get("righe") or []):
            new_righe.append({
                **r,
                "qty_prelevata": 0.0,
                "seriali_prelevati": [],
                "qty_spedita": 0.0,
                "seriali_spediti": [],
            })

        # Cancel bozza attiva (se presente)
        update_set: Dict[str, Any] = {
            "stato": "annullata", "cancelled_at": _now(), "updated_at": _now(),
            "righe": new_righe,
            "cancel_reason": reason or None,
            "cancelled_by": current.get("username"),
        }
        update_unset: Dict[str, Any] = {}
        if doc.get("shipment_draft"):
            update_unset["shipment_draft"] = ""
        # F30.c — dopo il rollback lo shipment_ref non punta più a una spedizione attiva.
        # Rimuoverlo permette il DELETE della commessa annullata senza confondere le check.
        if doc.get("shipment_ref"):
            update_unset["shipment_ref"] = ""
        # Aggiungi record di ANNULLAMENTO nello storico per audit
        annull_entry = {
            "type": "cancellation",
            "shipment_id": None,
            "cancelled_at": _now(),
            "cancelled_by": current.get("username"),
            "reason": reason or None,
            "rolled_back_shipments": [r.get("shipment_id") for r in rollback_report],
            "previous_stato": stato,
        }
        mongo_update: Dict[str, Any] = {
            "$set": update_set,
            "$push": {"shipments_history": annull_entry},
        }
        if update_unset:
            mongo_update["$unset"] = update_unset
        await db.commesse.update_one({"id": cid}, mongo_update)
        await event_logger.log_event(
            db, category="COMMESSE", event_type="COMMESSA_ANNULLATA",
            action="commesse.cancel", level="WARNING", status="SUCCESS",
            user=current.get("username"), user_role=current.get("role"),
            operation_id=doc.get("operation_id"),
            endpoint=f"POST /api/commesse/{cid}/cancel",
            customer=doc.get("cliente"),
            message=(f"Commessa #{doc.get('number')} annullata "
                     f"(prev={stato}, rollback spedizioni: {len(rollback_report)})"),
            details={
                "commessa_id": cid,
                "previous_stato": stato,
                "reason": reason,
                "picked_snapshot": picked_snapshot,
                "rollback_report": rollback_report,
            },
        )
        return _serialize(await db.commesse.find_one({"id": cid}))

    @router.get("/{cid}/history")
    async def history_commessa(cid: str):
        await _require_enabled()
        doc = await db.commesse.find_one({"id": cid})
        if not doc: raise HTTPException(404, "Commessa non trovata")
        events = []
        cursor = db.app_events.find({
            "$or": [
                {"operation_id": doc.get("operation_id")},
                {"details.commessa_id": cid},
            ]
        }).sort("created_at", 1)
        async for e in cursor:
            e.pop("_id", None)
            if isinstance(e.get("created_at"), datetime):
                e["created_at"] = e["created_at"].isoformat()
            events.append(e)
        return {"events": events}

    return router
