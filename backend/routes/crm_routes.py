from __future__ import annotations
from datetime import datetime, timezone, timedelta
import asyncio
from typing import Any, Dict, Optional, List
import uuid
import io
import json
import hashlib
from html import escape

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, ConfigDict
from pymongo import ReturnDocument

import auth as auth_mod
import notion_service
from calendar_installation_sync import sync_all_calendar_installations

RESOURCES = {
    "clienti": "crm_clienti",
    "contatti": "crm_contatti",
    "sedi": "crm_sedi",
    "sopralluoghi": "crm_sopralluoghi",
    "preventivi": "crm_preventivi",
    "ordini-clienti": "crm_ordini_clienti",
    "installazioni": "crm_installazioni",
    "interventi-tecnici": "crm_interventi_tecnici",
    "assistenza": "crm_assistenza",
}

RELATIONS = {
    "contatti": {"cliente_id": "clienti"},
    "sedi": {"cliente_id": "clienti", "contatto_id": "contatti"},
    "sopralluoghi": {"cliente_id": "clienti", "sede_id": "sedi"},
    "preventivi": {"cliente_id": "clienti", "sopralluogo_id": "sopralluoghi"},
    "ordini-clienti": {"cliente_id": "clienti", "sede_id": "sedi", "preventivo_id": "preventivi"},
    "installazioni": {"cliente_id": "clienti", "sede_id": "sedi", "ordine_cliente_id": "ordini-clienti"},
    "assistenza": {"cliente_id": "clienti", "sede_id": "sedi", "installazione_id": "installazioni"},
}

DELETE_GUARDS = {
    "clienti": [
        ("contatti", "cliente_id"),
        ("sedi", "cliente_id"),
        ("sopralluoghi", "cliente_id"),
        ("preventivi", "cliente_id"),
        ("ordini-clienti", "cliente_id"),
        ("installazioni", "cliente_id"),
        ("assistenza", "cliente_id"),
    ],
    "sedi": [
        ("sopralluoghi", "sede_id"),
        ("ordini-clienti", "sede_id"),
        ("installazioni", "sede_id"),
        ("assistenza", "sede_id"),
    ],
    "preventivi": [("ordini-clienti", "preventivo_id")],
    "ordini-clienti": [("installazioni", "ordine_cliente_id")],
    "installazioni": [("assistenza", "installazione_id")],
}

EXTERNAL_DELETE_GUARDS = {
    "clienti": [("commesse", "cliente_id")],
    "sedi": [("commesse", "sede_id")],
    "preventivi": [("commesse", "preventivo_id")],
    "ordini-clienti": [("commesse", "ordine_cliente_id")],
}


class RecordBody(BaseModel):
    model_config = ConfigDict(extra="allow")


def _clean(doc: Dict[str, Any]) -> Dict[str, Any]:
    out = dict(doc)
    out.pop("_id", None)
    # Retrocompatibilità: nelle vecchie installazioni il tecnico era salvato come
    # "installatore". L'interfaccia usa ora un solo campo: "tecnico".
    if not out.get("tecnico") and out.get("installatore"):
        out["tecnico"] = out.get("installatore")
    out.pop("installatore", None)
    for key in ("created_at", "updated_at"):
        if isinstance(out.get(key), datetime):
            out[key] = out[key].isoformat()
    return out



def _quote_signature(doc: Dict[str, Any]) -> str:
    """Firma stabile dei dati commerciali che compongono il PDF del preventivo."""
    keys = (
        "numero", "cliente_id", "nominativo", "telefono", "email", "sede_id",
        "sopralluogo_id", "data", "validita_giorni", "condizioni_pagamento", "tempi_consegna", "note", "righe",
        "imponibile", "iva_totale", "totale", "importo",
    )
    payload = {k: doc.get(k) for k in keys}
    raw = json.dumps(payload, ensure_ascii=False, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _eur(value: Any) -> str:
    try:
        n = float(value or 0)
    except (TypeError, ValueError):
        n = 0.0
    return f"{n:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def build_router(db, auth_deps):
    router = APIRouter(prefix="/crm", tags=["CRM"])
    dep = auth_deps.require_password_current

    def coll(resource: str):
        name = RESOURCES.get(resource)
        if not name:
            raise HTTPException(404, "Risorsa non valida")
        return db[name]

    def _user_id(current: Dict[str, Any]) -> str:
        return str(current.get("_id") or current.get("id") or "")

    def _can_view_all_installations(current: Dict[str, Any]) -> bool:
        return bool(current.get("role") == auth_mod.ROLE_ADMIN or auth_mod.is_master_user(current) or auth_mod.has_permission(current, "installazioni", "view_all"))

    def _installation_owned_query(current: Dict[str, Any]) -> Dict[str, Any]:
        """Filtro per utenti che possono vedere solo le installazioni assegnate a loro.
        Supporta sia il nuovo tecnico_user_id sia i vecchi record salvati per nome/username."""
        uid = _user_id(current)
        username = str(current.get("username") or "").strip()
        full_name = str(current.get("full_name") or "").strip()
        email = str(current.get("email") or "").strip()
        ors = []
        if uid:
            ors.append({"tecnico_user_id": uid})
        for value in (username, full_name, email):
            if value:
                ors.append({"tecnico": {"$regex": f"^{__import__('re').escape(value)}$", "$options": "i"}})
        return {"$or": ors or [{"tecnico_user_id": "__none__"}]}

    async def _ensure_installation_owner_access(record: Dict[str, Any], current: Dict[str, Any]) -> None:
        if _can_view_all_installations(current):
            return
        q = _installation_owned_query(current)
        # Valuta il record in memoria in modo semplice/robusto.
        uid = _user_id(current)
        assigned_id = str(record.get("tecnico_user_id") or "")
        assigned_name = str(record.get("tecnico") or "").strip().lower()
        aliases = {str(current.get(k) or "").strip().lower() for k in ("username", "full_name", "email")}
        aliases.discard("")
        if (uid and assigned_id == uid) or (assigned_name and assigned_name in aliases):
            return
        raise HTTPException(403, "Questa installazione non è assegnata al tuo utente")


    async def sync_primary_client_links(cliente: Dict[str, Any]) -> None:
        """Mantiene Referente principale e Sede principale allineati all'anagrafica cliente.

        Evita doppio inserimento: aggiorna i record marcati primary; se non esistono li crea.
        """
        client_id = str(cliente.get("id") or "").strip()
        if not client_id:
            return
        now = datetime.now(timezone.utc)
        contact_id = None
        referente = str(cliente.get("referente") or "").strip()
        telefono = str(cliente.get("telefono") or "").strip()
        email = str(cliente.get("email") or "").strip()
        if referente or telefono or email:
            existing = await coll("contatti").find_one({"cliente_id": client_id, "is_primary": True})
            payload = {
                "cliente_id": client_id, "nome": referente or "Referente principale",
                "telefono": telefono, "email": email, "ruolo": "Referente principale",
                "is_primary": True, "updated_at": now,
            }
            if existing:
                contact_id = existing.get("id")
                await coll("contatti").update_one({"id": contact_id}, {"$set": payload})
            else:
                contact_id = str(uuid.uuid4())
                payload.update({"id": contact_id, "created_at": now, "created_by": cliente.get("created_by")})
                await coll("contatti").insert_one(payload)

        indirizzo = str(cliente.get("indirizzo") or "").strip()
        comune = str(cliente.get("comune") or "").strip()
        cap = str(cliente.get("cap") or "").strip()
        provincia = str(cliente.get("provincia") or "").strip()
        if indirizzo or comune or cap or provincia:
            existing = await coll("sedi").find_one({"cliente_id": client_id, "is_primary": True})
            payload = {
                "cliente_id": client_id, "nome": "Sede principale", "tipo": "Principale",
                "indirizzo": indirizzo, "cap": cap, "comune": comune, "provincia": provincia,
                "telefono": telefono, "contatto_id": contact_id, "is_primary": True, "updated_at": now,
            }
            if existing:
                await coll("sedi").update_one({"id": existing.get("id")}, {"$set": payload})
            else:
                payload.update({"id": str(uuid.uuid4()), "created_at": now, "created_by": cliente.get("created_by")})
                await coll("sedi").insert_one(payload)

    async def normalize_relations(resource: str, data: Dict[str, Any]) -> Dict[str, Any]:
        """Deriva e verifica i collegamenti del flusso commerciale/operativo."""
        data = dict(data)

        # Un solo responsabile tecnico: vecchi payload con "installatore" vengono
        # ricondotti a "tecnico" e il campo legacy non viene più salvato.
        if resource == "installazioni":
            if not data.get("tecnico") and data.get("installatore"):
                data["tecnico"] = data.get("installatore")
            data.pop("installatore", None)
            if data.get("tecnico_user_id"):
                try:
                    from bson import ObjectId
                    user_doc = await db.users.find_one({"_id": ObjectId(str(data.get("tecnico_user_id")))})
                except Exception:
                    user_doc = None
                if not user_doc or not user_doc.get("active", True):
                    raise HTTPException(400, "Tecnico assegnato non valido")
                data["tecnico"] = user_doc.get("full_name") or user_doc.get("username") or user_doc.get("email")


        # Installazione: la commessa è la fonte principale per cliente/sede/ordine.
        if resource in ("installazioni", "assistenza") and data.get("commessa_id"):
            commessa = await db.commesse.find_one({"id": str(data["commessa_id"])})
            if not commessa:
                raise HTTPException(400, "Commessa collegata non valida")
            for target, source in (
                ("cliente_id", "cliente_id"),
                ("sede_id", "sede_id"),
                ("ordine_cliente_id", "ordine_cliente_id"),
            ):
                derived = commessa.get(source)
                if derived:
                    if data.get(target) and str(data[target]) != str(derived):
                        raise HTTPException(400, f"{target} non coerente con la commessa")
                    data[target] = derived

        # Assistenza: se parte da una installazione, eredita i collegamenti.
        if resource == "assistenza" and data.get("installazione_id"):
            inst = await coll("installazioni").find_one({"id": str(data["installazione_id"])})
            if not inst:
                raise HTTPException(400, "Installazione collegata non valida")
            for field in ("commessa_id", "cliente_id", "sede_id"):
                derived = inst.get(field)
                if derived:
                    if data.get(field) and str(data[field]) != str(derived):
                        raise HTTPException(400, f"{field} non coerente con l'installazione")
                    data[field] = derived

        # Verifica relazioni CRM.
        for field, target_resource in RELATIONS.get(resource, {}).items():
            value = data.get(field)
            if not value:
                continue
            target = coll(target_resource)
            linked = await target.find_one({"id": str(value)})
            if not linked:
                raise HTTPException(400, f"Collegamento non valido: {field}")

        # Coerenza cliente ↔ sede.
        if data.get("cliente_id") and data.get("sede_id"):
            sede = await coll("sedi").find_one({"id": str(data["sede_id"])})
            if sede and str(sede.get("cliente_id")) != str(data.get("cliente_id")):
                raise HTTPException(400, "La sede selezionata non appartiene al cliente")

        # Coerenza cliente ↔ preventivo / ordine.
        if resource == "ordini-clienti" and data.get("preventivo_id"):
            prev = await coll("preventivi").find_one({"id": str(data["preventivo_id"])})
            if prev and data.get("cliente_id") and str(prev.get("cliente_id")) != str(data.get("cliente_id")):
                raise HTTPException(400, "Il preventivo selezionato non appartiene al cliente")

        return data


    def _is_material_row(row: Dict[str, Any]) -> bool:
        kind = str(row.get("tipo_riga") or row.get("categoria") or "materiale").strip().lower()
        return kind in ("materiale", "prodotto", "magazzino", "product")

    async def _ensure_client_for_quote(preventivo: Dict[str, Any], actor: str) -> tuple[Optional[str], Optional[str]]:
        """Garantisce che un preventivo accettato abbia un cliente reale.
        Se il preventivo nasce da un prospect/nominativo libero, crea (o riusa) l'anagrafica cliente
        e collega automaticamente anche la sede principale quando disponibile.
        """
        cliente_id = str(preventivo.get("cliente_id") or "").strip() or None
        sede_id = str(preventivo.get("sede_id") or "").strip() or None
        if cliente_id:
            return cliente_id, sede_id

        nominativo = str(preventivo.get("nominativo") or preventivo.get("azienda") or "").strip()
        telefono = str(preventivo.get("telefono") or "").strip()
        email = str(preventivo.get("email") or "").strip()
        if not nominativo:
            return None, sede_id

        # Prima prova a riusare una anagrafica già esistente per evitare duplicati.
        ors = []
        import re
        if email:
            ors.append({"email": {"$regex": f"^{re.escape(email)}$", "$options": "i"}})
        if telefono:
            ors.append({"telefono": {"$regex": f"^{re.escape(telefono)}$", "$options": "i"}})
        existing = await coll("clienti").find_one({"$or": ors}) if ors else None
        if existing:
            cliente_id = str(existing.get("id"))
        else:
            now = datetime.now(timezone.utc)
            cliente_id = str(uuid.uuid4())
            cliente_doc = {
                "id": cliente_id,
                "tipo": "Privato",
                "nome": nominativo,
                "cognome": "",
                "ragione_sociale": "",
                "referente": nominativo,
                "telefono": telefono,
                "email": email,
                "created_at": now,
                "updated_at": now,
                "created_by": actor,
                "origine": "Preventivo accettato",
            }
            await coll("clienti").insert_one(cliente_doc)
            await sync_primary_client_links(cliente_doc)

        if not sede_id:
            primary_site = await coll("sedi").find_one({"cliente_id": cliente_id, "is_primary": True})
            if primary_site:
                sede_id = str(primary_site.get("id"))

        await coll("preventivi").update_one(
            {"id": str(preventivo.get("id"))},
            {"$set": {"cliente_id": cliente_id, "sede_id": sede_id, "updated_at": datetime.now(timezone.utc)}},
        )
        preventivo["cliente_id"] = cliente_id
        preventivo["sede_id"] = sede_id
        return cliente_id, sede_id

    async def _material_rows(rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out: List[Dict[str, Any]] = []
        for row in rows or []:
            if not _is_material_row(row):
                continue
            qty = float(row.get("quantity") or row.get("quantita") or row.get("qty_richiesta") or 0)
            if qty <= 0:
                continue
            pid = row.get("product_page_id") or row.get("prodotto_id")
            prod = await db.products.find_one({"id": pid}) if pid else None
            out.append({
                "product_page_id": pid,
                "product_name": row.get("product_name") or row.get("descrizione") or (prod or {}).get("name") or "Materiale",
                "product_code": row.get("product_code") or (prod or {}).get("code") or "",
                "product_barcode": row.get("product_barcode") or row.get("barcode") or (prod or {}).get("barcode") or "",
                "tipo_gestione": row.get("tipo_gestione") or (prod or {}).get("tipo_gestione") or "a_quantita",
                "unit": row.get("unit") or row.get("unita") or (prod or {}).get("unit") or "pz",
                "qty_richiesta": qty,
                "qty_prelevata": 0.0,
                "seriali_prelevati": [],
            })
        return out

    def _merge_operational_rows(old_rows: List[Dict[str, Any]], new_rows: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sincronizza il fabbisogno senza perdere materiale già preparato o spedito.
        Funziona anche per righe materiale libere non collegate al catalogo.
        """
        def row_key(r: Dict[str, Any]) -> str:
            pid = str(r.get("product_page_id") or "").strip()
            if pid:
                return f"id:{pid}"
            code = str(r.get("product_code") or "").strip().casefold()
            if code:
                return f"code:{code}"
            name = str(r.get("product_name") or r.get("descrizione") or "").strip().casefold()
            unit = str(r.get("unit") or "pz").strip().casefold()
            return f"free:{name}:{unit}"

        old_by_key = {row_key(r): r for r in (old_rows or [])}
        merged: List[Dict[str, Any]] = []
        seen = set()
        for nr in new_rows:
            key = row_key(nr)
            old = old_by_key.get(key)
            rr = dict(nr)
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

    def _services_need_installation(services: List[Dict[str, Any]]) -> bool:
        return any(
            str(s.get("tipo_riga") or s.get("categoria") or "").strip().lower() in ("installazione", "posa")
            for s in (services or [])
        )

    async def _ensure_service_only_installation(commessa: Dict[str, Any], actor: str) -> None:
        """Per commesse senza materiale ma con installazione venduta, crea subito l'attività da programmare."""
        if not commessa or (commessa.get("righe") or []) or not _services_need_installation(commessa.get("servizi") or []):
            return
        if not commessa.get("cliente_id") or not commessa.get("sede_id"):
            return
        existing_inst = await coll("installazioni").find_one({"commessa_id": str(commessa.get("id"))})
        if existing_inst:
            return
        now = datetime.now(timezone.utc)
        await coll("installazioni").insert_one({
            "id": str(uuid.uuid4()),
            "commessa_id": str(commessa.get("id")),
            "ordine_cliente_id": commessa.get("ordine_cliente_id"),
            "cliente_id": commessa.get("cliente_id"),
            "sede_id": commessa.get("sede_id"),
            "tecnico": "",
            "data": "",
            "stato": "Da programmare",
            "note": f"Creata automaticamente dalla commessa #{commessa.get('number')}",
            "created_by": actor,
            "created_at": now,
            "updated_at": now,
        })

    async def _commessa_from_quote(preventivo: Dict[str, Any], actor: str) -> Dict[str, Any]:
        """Crea o sincronizza una sola commessa dal preventivo accettato.
        Le righe materiale alimentano il picking; i servizi restano attività operative della stessa commessa.
        """
        quote_id = str(preventivo.get("id") or "")
        quote_root_id = str(preventivo.get("revision_root_id") or quote_id)
        cliente_id, sede_id = await _ensure_client_for_quote(preventivo, actor)
        righe = await _material_rows(preventivo.get("righe") or [])
        servizi = [dict(r) for r in (preventivo.get("righe") or []) if not _is_material_row(r)]

        existing = await db.commesse.find_one({
            "$or": [
                {"preventivo_root_id": quote_root_id},
                {"preventivo_id": quote_id},
            ],
            "stato": {"$ne": "annullata"},
        })
        if existing:
            # Dopo l'arrivo dell'ordine, l'ordine diventa la fonte definitiva del fabbisogno.
            if not existing.get("ordine_cliente_id"):
                merged_rows = _merge_operational_rows(existing.get("righe") or [], righe)
                next_state = existing.get("stato") or ("da_preparare" if merged_rows else "solo_servizi")
                if merged_rows and next_state == "solo_servizi":
                    next_state = "da_preparare"
                if not merged_rows and next_state in ("da_preparare", "in_preparazione", "parziale", "pronta"):
                    next_state = "solo_servizi"
                await db.commesse.update_one({"id": existing.get("id")}, {"$set": {
                    "cliente_id": cliente_id,
                    "sede_id": sede_id,
                    "preventivo_id": quote_id,
                    "preventivo_root_id": quote_root_id,
                    "preventivo_revision": int(preventivo.get("quote_revision") or 1),
                    "cliente": existing.get("cliente") or preventivo.get("nominativo") or "Cliente",
                    "righe": merged_rows,
                    "servizi": servizi,
                    "tipo_commessa": "mista" if merged_rows and servizi else ("materiali" if merged_rows else "servizi"),
                    "stato_servizi": "Da programmare" if servizi else None,
                    "stato": next_state,
                    "note": preventivo.get("note") or existing.get("note") or "",
                    "updated_at": datetime.now(timezone.utc),
                }})
            else:
                # Se esiste già un ordine cliente, la nuova revisione accettata aggiorna
                # anche l'ordine commerciale e poi sincronizza la stessa commessa.
                order_id = str(existing.get("ordine_cliente_id") or "")
                linked_order = await coll("ordini-clienti").find_one({"id": order_id}) if order_id else None
                if linked_order:
                    order_update = {
                        "preventivo_id": quote_id,
                        "righe": [dict(r) for r in (preventivo.get("righe") or [])],
                        "importo": preventivo.get("totale") if preventivo.get("totale") is not None else preventivo.get("importo"),
                        "sopralluogo_id": preventivo.get("sopralluogo_id") or linked_order.get("sopralluogo_id"),
                        "updated_at": datetime.now(timezone.utc),
                        "updated_by": actor,
                    }
                    await coll("ordini-clienti").update_one({"id": order_id}, {"$set": order_update})
                    linked_order.update(order_update)
                    synced = await _sync_order_to_commessa(linked_order)
                    if synced:
                        await db.commesse.update_one({"id": existing.get("id")}, {"$set": {
                            "preventivo_id": quote_id,
                            "preventivo_root_id": quote_root_id,
                            "preventivo_revision": int(preventivo.get("quote_revision") or 1),
                            "updated_at": datetime.now(timezone.utc),
                        }})
            updated = await db.commesse.find_one({"id": existing.get("id")})
            await _ensure_service_only_installation(updated or {}, actor)
            return _clean(updated)

        cliente = await coll("clienti").find_one({"id": cliente_id}) if cliente_id else None
        cliente_nome = (cliente or {}).get("ragione_sociale") or " ".join(x for x in [(cliente or {}).get("nome"), (cliente or {}).get("cognome")] if x)
        cliente_nome = cliente_nome or preventivo.get("nominativo") or preventivo.get("azienda") or "Cliente"
        base_number = f"C-PREV-{preventivo.get('numero') or quote_id[:8]}"
        number = base_number
        suffix = 1
        while await db.commesse.find_one({"number": number, "stato": {"$ne": "annullata"}}):
            suffix += 1
            number = f"{base_number}-{suffix}"
        now = datetime.now(timezone.utc)
        tipo = "mista" if righe and servizi else ("materiali" if righe else "servizi")
        doc = {
            "id": str(uuid.uuid4()), "number": number, "cliente": str(cliente_nome).strip(),
            "cliente_id": cliente_id, "sede_id": sede_id,
            "ordine_cliente_id": None, "preventivo_id": quote_id, "preventivo_root_id": quote_root_id,
            "preventivo_revision": int(preventivo.get("quote_revision") or 1),
            "data_ordine": preventivo.get("data"), "data_prevista": None,
            "priorita": "normale", "note": preventivo.get("note") or "",
            "warehouse_id": "elios-tech", "stato": "da_preparare" if righe else "solo_servizi", "righe": righe,
            "servizi": servizi, "tipo_commessa": tipo,
            "stato_servizi": "Da programmare" if servizi else None,
            "operatore_carico": None, "presa_in_carico_at": None, "completed_at": None,
            "shipped_at": None, "cancelled_at": None, "created_by": actor,
            "created_at": now, "updated_at": now,
        }
        await db.commesse.insert_one(doc)
        await _ensure_service_only_installation(doc, actor)
        return _clean(doc)

    async def _sync_order_to_commessa(ordine: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """Se l'ordine è già collegato a una commessa, sincronizza quantità/materiali/servizi.
        L'ordine è la fonte definitiva, ma i prelievi già fatti non vengono persi né resi incoerenti.
        """
        order_id = str(ordine.get("id") or "")
        commessa = await db.commesse.find_one({"ordine_cliente_id": order_id, "stato": {"$ne": "annullata"}})
        if not commessa and ordine.get("preventivo_id"):
            commessa = await db.commesse.find_one({"preventivo_id": str(ordine.get("preventivo_id")), "stato": {"$ne": "annullata"}})
        if not commessa:
            return None
        new_rows = await _material_rows(ordine.get("righe") or [])
        merged_rows = _merge_operational_rows(commessa.get("righe") or [], new_rows)
        servizi = [dict(r) for r in (ordine.get("righe") or []) if not _is_material_row(r)]
        current_state = commessa.get("stato") or "da_preparare"
        if not merged_rows and current_state in ("da_preparare", "in_preparazione", "parziale"):
            current_state = "solo_servizi"
        elif merged_rows and current_state == "pronta" and not any(float(r.get("qty_prelevata") or 0) > 0 for r in merged_rows):
            current_state = "da_preparare"
        tipo = "mista" if merged_rows and servizi else ("materiali" if merged_rows else "servizi")
        await db.commesse.update_one({"id": commessa.get("id")}, {"$set": {
            "ordine_cliente_id": order_id,
            "cliente_id": ordine.get("cliente_id") or commessa.get("cliente_id"),
            "sede_id": ordine.get("sede_id") or commessa.get("sede_id"),
            "data_ordine": ordine.get("data") or commessa.get("data_ordine"),
            "righe": merged_rows,
            "servizi": servizi,
            "tipo_commessa": tipo,
            "stato_servizi": "Da programmare" if servizi else None,
            "stato": current_state,
            "note": ordine.get("note") or commessa.get("note") or "",
            "updated_at": datetime.now(timezone.utc),
        }})
        return _clean(await db.commesse.find_one({"id": commessa.get("id")}))

    # Rotte statiche PRIMA della rotta dinamica /{resource}.
    @router.get("/meta/dashboard")
    async def dashboard_counts(current=Depends(dep)):
        out = {}
        for key, name in RESOURCES.items():
            out[key] = await db[name].count_documents({})
        out["commesse"] = await db.commesse.count_documents({"stato": {"$ne": "annullata"}})
        return out

    @router.get("/lookups/commesse")
    async def lookup_commesse(current=Depends(dep)):
        docs = await db.commesse.find({"stato": {"$ne": "annullata"}}).sort("updated_at", -1).to_list(length=2000)
        items = []
        for doc in docs:
            items.append({
                "id": doc.get("id"),
                "number": doc.get("number"),
                "cliente": doc.get("cliente"),
                "cliente_id": doc.get("cliente_id"),
                "sede_id": doc.get("sede_id"),
                "ordine_cliente_id": doc.get("ordine_cliente_id"),
                "preventivo_id": doc.get("preventivo_id"),
                "stato": doc.get("stato"),
                "data_ordine": doc.get("data_ordine"),
                "data_prevista": doc.get("data_prevista"),
            })
        return {"items": items, "count": len(items)}

    @router.get("/lookups/technicians")
    async def lookup_technicians(current=Depends(dep)):
        if not auth_mod.has_permission(current, "installazioni", "create") and not auth_mod.has_permission(current, "installazioni", "edit"):
            raise HTTPException(403, "Non hai il permesso per assegnare tecnici")
        docs = await db.users.find({"active": True}).sort("full_name", 1).to_list(length=500)
        items = []
        for u in docs:
            if u.get("role") == auth_mod.ROLE_TECNICO or auth_mod.has_permission(u, "installazioni", "edit"):
                items.append({
                    "id": str(u.get("_id")),
                    "username": u.get("username"),
                    "full_name": u.get("full_name") or u.get("username"),
                    "email": u.get("email"),
                    "role": u.get("role"),
                })
        return {"items": items, "count": len(items)}

    @router.get("/clienti/{client_id}/dossier")
    async def client_dossier(client_id: str, current=Depends(dep)):
        cliente = await coll("clienti").find_one({"id": client_id})
        if not cliente:
            raise HTTPException(404, "Cliente non trovato")

        async def rows(resource: str, query: Dict[str, Any], length: int = 2000):
            docs = await coll(resource).find(query).sort("updated_at", -1).to_list(length=length)
            return [_clean(x) for x in docs]

        # R39 — tutte le sezioni del dossier vengono lette in parallelo da MongoDB.
        # Dopo la migrazione Notion non deve piu' essere interrogato ad ogni apertura cliente.
        contatti, sedi, sopralluoghi, preventivi, ordini, installazioni, assistenza, comm_docs, client_docs = await asyncio.gather(
            rows("contatti", {"cliente_id": client_id}),
            rows("sedi", {"cliente_id": client_id}),
            rows("sopralluoghi", {"cliente_id": client_id}),
            rows("preventivi", {"cliente_id": client_id}),
            rows("ordini-clienti", {"cliente_id": client_id}),
            rows("installazioni", {"cliente_id": client_id}),
            rows("assistenza", {"cliente_id": client_id}),
            db.commesse.find({"cliente_id": client_id}).sort("updated_at", -1).to_list(length=2000),
            db.documents.find({"resource": "clienti", "record_id": client_id}).sort("created_at", -1).to_list(length=500),
        )
        commesse = [_clean(x) for x in comm_docs]

        def _docs_by_category(category: str):
            out = []
            wanted = category.casefold()
            for d in client_docs:
                if str(d.get("category") or "").casefold() == wanted:
                    out.append({
                        "id": d.get("id"), "name": d.get("filename"),
                        "category": d.get("category"), "size": d.get("size", 0),
                    })
            return out

        # Compatibilita' UI: la vecchia scheda chiamava questi dati "notion".
        # Ora sono la copia locale/migrata e quindi l'apertura e' immediata e non dipende da Notion.
        notion_data: Dict[str, Any] = {
            "status": "found" if cliente.get("import_source") == "notion" or cliente.get("notion_source_ids") else "local",
            "source": "mongo_migration",
            "ragione_sociale": cliente.get("ragione_sociale"),
            "referente": cliente.get("referente"), "telefono": cliente.get("telefono"), "email": cliente.get("email"),
            "indirizzo": cliente.get("indirizzo"), "comune": cliente.get("comune"), "provincia": cliente.get("provincia"),
            "agente": cliente.get("agente"), "provenienza_cliente": cliente.get("provenienza_cliente"),
            "stato_cliente": cliente.get("stato_cliente"), "data_firma": cliente.get("data_firma"),
            "pagamento": cliente.get("pagamento"), "capitale": cliente.get("capitale"),
            "codici_prodotto": cliente.get("codici_prodotto") or [], "qty_wb": cliente.get("qty_wb"),
            "sn_wb": cliente.get("sn_wb") or [], "qr_codes": cliente.get("qr_codes") or [],
            "installatore": cliente.get("installatore_notion"), "id_wallbox": cliente.get("id_wallbox"),
            "password_wallbox": cliente.get("password_wallbox"), "numero_caso_wallbox": cliente.get("numero_caso_wallbox"),
            "assistenza_smart": bool(cliente.get("assistenza_smart")), "backend_elios_tech": bool(cliente.get("backend_elios_tech")),
            "scadenza_backend": cliente.get("scadenza_backend"), "electromaps": bool(cliente.get("electromaps")),
            "eviaggio": bool(cliente.get("eviaggio")), "nextcharge": bool(cliente.get("nextcharge")),
            "plugshare": bool(cliente.get("plugshare")), "recensione_google": bool(cliente.get("recensione_google")),
            "contratto": _docs_by_category("Contratto"), "fattura": _docs_by_category("Fattura"),
            "report_installazione": _docs_by_category("Report installazione"),
            "report_fotografico": _docs_by_category("Report fotografico"),
        }

        timeline: List[Dict[str, Any]] = []
        def add_many(items, type_name, label_fn, detail_fn=None):
            for item in items:
                dt = item.get("updated_at") or item.get("created_at") or item.get("data") or item.get("data_ordine") or ""
                timeline.append({
                    "id": item.get("id"), "type": type_name, "date": dt,
                    "label": label_fn(item), "detail": detail_fn(item) if detail_fn else "",
                })
        add_many(ordini, "ordine", lambda x: f"Ordine {x.get('numero') or ''}".strip(), lambda x: " · ".join(v for v in [x.get("stato_commerciale") or x.get("stato"), x.get("stato_finanziaria") if x.get("stato_finanziaria") != "Non richiesta" else None] if v))
        add_many(commesse, "commessa", lambda x: f"Commessa #{x.get('number') or ''}".strip(), lambda x: str(x.get("stato") or ""))
        add_many(sopralluoghi, "sopralluogo", lambda x: "Sopralluogo", lambda x: " · ".join(v for v in [x.get("data"), x.get("tecnico"), x.get("stato")] if v))
        add_many(preventivi, "preventivo", lambda x: f"Preventivo {x.get('numero') or ''}".strip(), lambda x: str(x.get("stato") or ""))
        add_many(installazioni, "installazione", lambda x: "Installazione", lambda x: " · ".join(v for v in [x.get("data"), x.get("tecnico"), x.get("stato")] if v))
        add_many(assistenza, "assistenza", lambda x: f"Assistenza {x.get('numero') or ''}".strip(), lambda x: " · ".join(v for v in [x.get("tipo"), x.get("stato")] if v))
        timeline.sort(key=lambda x: str(x.get("date") or ""), reverse=True)

        return {
            "cliente": _clean(cliente), "contatti": contatti, "sedi": sedi,
            "sopralluoghi": sopralluoghi, "preventivi": preventivi, "ordini": ordini,
            "commesse": commesse, "installazioni": installazioni, "assistenza": assistenza,
            "timeline": timeline, "notion": notion_data,
        }

    @router.get("/clienti-summary")
    async def clienti_summary(current=Depends(dep)):
        """Elenco leggero per Elios Tech Ordini, gia' aggregato e ordinato per Data firma.

        Evita di trasferire al browser tutte le collezioni clienti+ordini e rende la pagina
        veloce anche con migliaia di record.
        """
        clients_task = db.crm_clienti.find(
            {"archived": {"$ne": True}},
            {"_id": 0, "id": 1, "ragione_sociale": 1, "nome_struttura": 1, "nome": 1, "cognome": 1,
             "partita_iva": 1, "codice_fiscale": 1, "telefono": 1, "email": 1, "comune": 1, "provincia": 1,
             "agente": 1, "data_firma": 1, "pagamento": 1, "capitale": 1, "qty_wb": 1, "stato_cliente": 1,
             "pec": 1, "codice_sdi": 1, "sdi": 1,
             "da_ricontattare": 1, "data_ricontatto": 1, "priorita_ricontatto": 1, "referente": 1}
        ).to_list(length=10000)
        orders_task = db.crm_ordini_clienti.find(
            {},
            {"_id": 0, "id": 1, "cliente_id": 1, "data_firma": 1, "data": 1, "modalita_pagamento": 1,
             "importo": 1, "qty_wb": 1, "stato": 1, "stato_commerciale": 1, "stato_finanziaria": 1}
        ).to_list(length=20000)
        docs_task = db.documents.find(
            {"resource": "clienti"},
            {"_id": 0, "record_id": 1, "category": 1}
        ).to_list(length=50000)
        clients, orders, documents = await asyncio.gather(clients_task, orders_task, docs_task)

        docs_by_client: Dict[str, Dict[str, int]] = {}
        for doc in documents:
            cid = str(doc.get("record_id") or "")
            bucket = docs_by_client.setdefault(cid, {"documents_count": 0, "reports_count": 0})
            bucket["documents_count"] += 1
            if "report" in str(doc.get("category") or "").casefold():
                bucket["reports_count"] += 1

        by_client: Dict[str, List[Dict[str, Any]]] = {}
        for order in orders:
            by_client.setdefault(str(order.get("cliente_id") or ""), []).append(order)

        def date_key(value: Any) -> str:
            raw = str(value or "").strip()
            return raw[:10] if raw else ""

        items = []
        for c in clients:
            cid = str(c.get("id") or "")
            cos = by_client.get(cid, [])
            cos.sort(key=lambda o: (date_key(o.get("data_firma") or o.get("data")), str(o.get("id") or "")), reverse=True)
            latest = cos[0] if cos else {}
            dates = [date_key(c.get("data_firma"))] + [date_key(o.get("data_firma") or o.get("data")) for o in cos]
            firma = max((d for d in dates if d), default="")
            order_amounts = [float(o.get("importo") or 0) for o in cos if o.get("importo") not in (None, "")]
            order_wb = [float(o.get("qty_wb") or 0) for o in cos if o.get("qty_wb") not in (None, "")]
            fatturato = sum(order_amounts) if order_amounts else (float(c.get("capitale") or 0) if c.get("capitale") not in (None, "") else None)
            wb_totali = sum(order_wb) if order_wb else c.get("qty_wb")
            items.append({
                **c,
                "data_firma": firma,
                "pagamento": latest.get("modalita_pagamento") or c.get("pagamento") or "",
                "capitale": latest.get("importo") if latest.get("importo") is not None else c.get("capitale"),
                "fatturato": fatturato,
                "qty_wb": latest.get("qty_wb") if latest.get("qty_wb") not in (None, "") else c.get("qty_wb"),
                "wb_totali": wb_totali,
                "ordini_count": len(cos),
                "ultimo_stato": latest.get("stato_commerciale") or latest.get("stato") or c.get("stato_cliente") or "",
                "stato_finanziaria": latest.get("stato_finanziaria") or "",
                "documents_count": docs_by_client.get(cid, {}).get("documents_count", 0),
                "reports_count": docs_by_client.get(cid, {}).get("reports_count", 0),
            })
        # Record senza Data firma in fondo; a parita' di data ordina alfabeticamente.
        items.sort(key=lambda x: (date_key(x.get("data_firma")), str(x.get("ragione_sociale") or x.get("nome_struttura") or "").casefold()), reverse=True)
        return {"items": items, "count": len(items)}

    @router.get("/{resource}")
    async def list_records(resource: str, q: Optional[str] = Query(default=None), include_archived: bool = Query(default=False), current=Depends(dep)):
        c = coll(resource)
        if resource == "installazioni":
            await sync_all_calendar_installations(db, actor=current.get("username") or "installazioni", force=False)
        query = {}
        if resource == "clienti" and not include_archived:
            query = {"archived": {"$ne": True}}
        if resource == "installazioni" and not _can_view_all_installations(current):
            query = {"$and": [query, _installation_owned_query(current)]} if query else _installation_owned_query(current)
        docs = await c.find(query).sort("updated_at", -1).to_list(length=2000)
        items = [_clean(x) for x in docs]
        if resource == "installazioni":
            # La scheda tecnico mostra direttamente prodotti e attività da eseguire,
            # senza esporre il tecnico al picking o ai codici di magazzino.
            for item in items:
                cid = str(item.get("commessa_id") or "")
                comm = await db.commesse.find_one({"id": cid}) if cid else None
                if comm:
                    item["prodotti_da_installare"] = [
                    {
                        "nome": r.get("product_name") or r.get("descrizione") or "Prodotto",
                        "codice": r.get("product_code"),
                        "quantita": r.get("qty_richiesta") or r.get("quantity") or 1,
                        "seriali": list(dict.fromkeys((r.get("seriali_prelevati") or []) + (r.get("seriali_spediti") or []))),
                    }
                    for r in (comm.get("righe") or [])
                ]
                    item["attivita_da_eseguire"] = [
                        {"descrizione": x.get("descrizione") or x.get("product_name") or str(x.get("tipo_riga") or "Servizio"), "quantita": x.get("quantity") or x.get("quantita") or 1}
                        for x in (comm.get("servizi") or [])
                    ]
                    item["istruzioni_intervento"] = item.get("istruzioni_intervento") or comm.get("note") or ""
                else:
                    item.setdefault("prodotti_da_installare", [])
                    item.setdefault("attivita_da_eseguire", [])
                # R60 — cliente e sede vengono mostrati anche per installazioni nate dal Calendario, senza commessa.
                cliente_id = str(item.get("cliente_id") or (comm or {}).get("cliente_id") or "")
                sede_id = str(item.get("sede_id") or (comm or {}).get("sede_id") or "")
                if cliente_id:
                    cliente = await coll("clienti").find_one({"id": cliente_id})
                    if cliente:
                        item["cliente_nome"] = cliente.get("ragione_sociale") or cliente.get("nome") or cliente.get("name") or comm.get("cliente") or "Cliente"
                item["cliente_nome"] = item.get("cliente_nome") or (comm or {}).get("cliente") or item.get("nominativo") or item.get("calendar_title") or "Cliente da collegare"
                if sede_id:
                    sede = await coll("sedi").find_one({"id": sede_id})
                    if sede:
                        item["sede_nome"] = sede.get("nome") or sede.get("name") or sede.get("indirizzo") or "Sede"
                        addr = " ".join(x for x in [sede.get("indirizzo") or sede.get("address"), sede.get("civico")] if x).strip()
                        loc = " ".join(x for x in [sede.get("cap"), sede.get("comune"), sede.get("provincia")] if x).strip()
                        item["sede_indirizzo"] = addr
                        item["sede_indirizzo_completo"] = ", ".join(x for x in [addr, loc] if x)
                        item["sede_comune"] = sede.get("comune") or ""
                        item["sede_provincia"] = sede.get("provincia") or ""
                        item["sede_cap"] = sede.get("cap") or ""
                item["sede_nome"] = item.get("sede_nome") or item.get("sede") or ""
        if q:
            needle = q.lower().strip()
            items = [x for x in items if needle in " ".join(str(v) for v in x.values()).lower()]
        return {"items": items, "count": len(items)}

    @router.get("/preventivi/{record_id}/pdf")
    async def generate_quote_pdf(record_id: str, current=Depends(dep)):
        """Genera il PDF commerciale del preventivo e registra la revisione generata."""
        quote = await coll("preventivi").find_one({"id": record_id})
        if not quote:
            raise HTTPException(404, "Preventivo non trovato")
        if not (quote.get("righe") or []):
            raise HTTPException(400, "Il preventivo non contiene righe")

        signature = _quote_signature(quote)
        previous_signature = str(quote.get("pdf_signature") or "")
        revision = int(quote.get("pdf_revision") or 0)
        if not previous_signature or previous_signature != signature:
            revision += 1
        revision = max(1, revision)

        cliente = None
        sede = None
        if quote.get("cliente_id"):
            cliente = await coll("clienti").find_one({"id": str(quote.get("cliente_id"))})
        if quote.get("sede_id"):
            sede = await coll("sedi").find_one({"id": str(quote.get("sede_id"))})
        settings_doc = await db.settings.find_one({"_id": "app_settings"}) or {}
        general = settings_doc.get("general") or {}
        company_name = str(general.get("company_name") or "Elios Tech S.r.l.")
        company_address = str(general.get("address") or "Via San Marco, 14 · 29121 Piacenza (PC)")
        company_vat = str(general.get("vat") or general.get("partita_iva") or "02212580035")
        company_email = str(general.get("email") or "info@eliostech.org")
        company_phone = str(general.get("phone") or general.get("telefono") or "0523 183 8530")

        try:
            from reportlab.lib import colors
            from reportlab.lib.enums import TA_RIGHT, TA_LEFT
            from reportlab.lib.pagesizes import A4
            from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
            from reportlab.lib.units import mm
            from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, KeepTogether, Image
            from reportlab.graphics.shapes import Drawing, Circle, Line, String
        except Exception as exc:
            raise HTTPException(500, f"Generazione PDF non disponibile: {exc}")

        buf = io.BytesIO()
        doc = SimpleDocTemplate(
            buf, pagesize=A4, rightMargin=14*mm, leftMargin=14*mm,
            topMargin=14*mm, bottomMargin=14*mm,
            title="Preventivo", author=company_name,
        )
        styles = getSampleStyleSheet()
        navy = colors.HexColor("#1A456B")
        navy_dark = colors.HexColor("#163B5C")
        amber = colors.HexColor("#FACC15")
        light = colors.HexColor("#F8FAFC")
        border = colors.HexColor("#E2E8F0")
        muted = colors.HexColor("#64748B")
        small = ParagraphStyle("small", parent=styles["BodyText"], fontSize=8.5, leading=11, textColor=muted)
        body = ParagraphStyle("body", parent=styles["BodyText"], fontSize=9.5, leading=13, textColor=colors.HexColor("#334155"))
        bold = ParagraphStyle("bold", parent=body, fontName="Helvetica-Bold", textColor=colors.HexColor("#0F172A"))
        right = ParagraphStyle("right", parent=body, alignment=TA_RIGHT)
        right_bold = ParagraphStyle("rightbold", parent=bold, alignment=TA_RIGHT)
        h1 = ParagraphStyle("h1", parent=styles["Heading1"], fontName="Helvetica-Bold", fontSize=19, leading=22, textColor=navy_dark, spaceAfter=2)
        brand = ParagraphStyle("brand", parent=styles["Heading2"], fontName="Helvetica-Bold", fontSize=17, leading=19, textColor=colors.white)
        story = []

        # Header brand — usa il logo ufficiale fornito da Elios Tech.
        logo_path = __import__("os").path.join(__import__("os").path.dirname(__import__("os").path.dirname(__file__)), "assets", "elios-tech-logo-official.png")
        if __import__("os").path.exists(logo_path):
            logo = Image(logo_path, width=73*mm, height=14.7*mm)
        else:
            logo = Paragraph("ELIOS TECH", brand)
        company_info = Paragraph(
            f"<font size='8'>{escape(company_email)} · {escape(company_phone)}</font>",
            ParagraphStyle("brandinfo", parent=small, textColor=colors.white, leading=10),
        )
        brand_cell = Table([[logo, company_info]], colWidths=[78*mm, 47*mm])
        brand_cell.setStyle(TableStyle([
            ("VALIGN",(0,0),(-1,-1),"MIDDLE"),("LEFTPADDING",(0,0),(-1,-1),0),
            ("RIGHTPADDING",(0,0),(-1,-1),4),("TOPPADDING",(0,0),(-1,-1),0),("BOTTOMPADDING",(0,0),(-1,-1),0)
        ]))
        header = Table([[brand_cell, Paragraph("PREVENTIVO", ParagraphStyle("hr", parent=brand, alignment=TA_RIGHT, fontSize=14, leading=16))]], colWidths=[125*mm, 51*mm])
        header.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), navy), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 10), ("RIGHTPADDING", (0,0), (-1,-1), 10),
            ("TOPPADDING", (0,0), (-1,-1), 10), ("BOTTOMPADDING", (0,0), (-1,-1), 10),
            ("LINEBELOW", (0,0), (-1,-1), 3, amber),
        ]))
        story += [header, Spacer(1, 7*mm)]

        numero = str(quote.get("numero") or "—")
        data_q = str(quote.get("data") or "—")
        validita = int(quote.get("validita_giorni") or 30)
        try:
            parsed_date = datetime.fromisoformat(data_q).date()
            display_date = parsed_date.strftime("%d/%m/%Y")
            expires = (parsed_date + timedelta(days=validita)).strftime("%d/%m/%Y")
        except Exception:
            display_date = data_q
            expires = f"{validita} giorni"
        meta = Table([
            [Paragraph("Data", small), Paragraph("Validità", small), Paragraph("Totale", small)],
            [Paragraph(display_date, bold), Paragraph(expires, bold), Paragraph(f"€ {_eur(quote.get('totale') if quote.get('totale') is not None else quote.get('importo'))}", right_bold)],
        ], colWidths=[55*mm, 55*mm, 66*mm])
        meta.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,-1), light), ("BOX", (0,0), (-1,-1), .7, border),
            ("INNERGRID", (0,0), (-1,-1), .4, border), ("VALIGN", (0,0), (-1,-1), "MIDDLE"),
            ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
            ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story += [meta, Spacer(1, 6*mm)]

        client_title = (cliente or {}).get("ragione_sociale") or " ".join(x for x in [(cliente or {}).get("nome"), (cliente or {}).get("cognome")] if x) or quote.get("nominativo") or "Cliente"
        client_lines = [str(client_title)]
        if cliente:
            for val in (cliente.get("indirizzo"), " ".join(x for x in [cliente.get("cap"), cliente.get("comune"), cliente.get("provincia")] if x), cliente.get("partita_iva") and f"P. IVA {cliente.get('partita_iva')}", cliente.get("codice_fiscale") and f"C.F. {cliente.get('codice_fiscale')}"):
                if val: client_lines.append(str(val))
        elif quote.get("email") or quote.get("telefono"):
            if quote.get("email"): client_lines.append(str(quote.get("email")))
            if quote.get("telefono"): client_lines.append(str(quote.get("telefono")))
        site_lines = []
        if sede:
            site_lines.append(str(sede.get("nome") or "Sede intervento"))
            addr = " ".join(x for x in [sede.get("indirizzo"), sede.get("civico")] if x)
            loc = " ".join(x for x in [sede.get("cap"), sede.get("comune"), sede.get("provincia")] if x)
            if addr: site_lines.append(addr)
            if loc: site_lines.append(loc)
        customer_box = Table([
            [Paragraph("DESTINATARIO", small), Paragraph("SEDE / INTERVENTO", small)],
            [Paragraph("<br/>".join(escape(x) for x in client_lines), bold), Paragraph("<br/>".join(escape(x) for x in site_lines) if site_lines else "—", body)],
        ], colWidths=[88*mm, 88*mm])
        customer_box.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), .7, border), ("INNERGRID", (0,0), (-1,-1), .4, border),
            ("BACKGROUND", (0,0), (-1,0), colors.HexColor("#F1F5F9")), ("VALIGN", (0,0), (-1,-1), "TOP"),
            ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING", (0,0), (-1,-1), 7), ("BOTTOMPADDING", (0,0), (-1,-1), 7),
        ]))
        story += [customer_box, Spacer(1, 7*mm)]

        # Stampa TUTTE le voci commerciali. `righe` è il formato attuale; gli array
        # legacy vengono aggiunti solo se contengono voci non già presenti.
        pdf_rows = [dict(r) for r in (quote.get("righe") or [])]
        seen = set()
        for r in pdf_rows:
            seen.add((str(r.get("tipo_riga") or "materiale").casefold(), str(r.get("descrizione") or r.get("product_name") or "").strip().casefold(), float(r.get("quantity") or r.get("quantita") or 0), float(r.get("prezzo_unitario") or r.get("prezzo") or 0)))
        for legacy_key, default_type in (("servizi", "servizio"), ("materiali", "materiale"), ("voci", "servizio")):
            for raw in (quote.get(legacy_key) or []):
                r = dict(raw)
                r.setdefault("tipo_riga", default_type)
                r.setdefault("descrizione", r.get("product_name") or r.get("nome") or r.get("description") or "")
                r.setdefault("quantity", r.get("quantita") or r.get("qty") or 1)
                r.setdefault("prezzo_unitario", r.get("prezzo") or r.get("price") or r.get("importo_unitario") or 0)
                r.setdefault("sconto", r.get("discount") or 0)
                r.setdefault("iva", r.get("vat") or 22)
                key=(str(r.get("tipo_riga") or default_type).casefold(), str(r.get("descrizione") or r.get("product_name") or "").strip().casefold(), float(r.get("quantity") or 0), float(r.get("prezzo_unitario") or 0))
                if key not in seen:
                    pdf_rows.append(r); seen.add(key)

        rows = [[Paragraph("Descrizione", bold), Paragraph("Q.tà", right_bold), Paragraph("Prezzo", right_bold), Paragraph("Sc.", right_bold), Paragraph("IVA", right_bold), Paragraph("Totale", right_bold)]]
        printed_imponibile = 0.0
        printed_iva = 0.0
        for row in pdf_rows:
            desc = escape(str(row.get("descrizione") or row.get("product_name") or row.get("voce") or ""))
            qty = float(row.get("quantity") or 0)
            price = float(row.get("prezzo_unitario") or 0)
            discount = float(row.get("sconto") or 0)
            vat = float(row.get("iva") or 0)
            line = qty * price * (1 - discount/100)
            printed_imponibile += line
            printed_iva += line * vat / 100
            rows.append([
                Paragraph(desc or "—", body), Paragraph(f"{qty:g}", right), Paragraph(f"€ {_eur(price)}", right),
                Paragraph(f"{discount:g}%", right), Paragraph(f"{vat:g}%", right), Paragraph(f"€ {_eur(line)}", right_bold),
            ])
        t = Table(rows, colWidths=[79*mm, 14*mm, 24*mm, 14*mm, 14*mm, 31*mm], repeatRows=1)
        t.setStyle(TableStyle([
            ("BACKGROUND", (0,0), (-1,0), navy), ("TEXTCOLOR", (0,0), (-1,0), colors.white),
            ("BOX", (0,0), (-1,-1), .7, border), ("INNERGRID", (0,0), (-1,-1), .3, border),
            ("VALIGN", (0,0), (-1,-1), "TOP"), ("LEFTPADDING", (0,0), (-1,-1), 6),
            ("RIGHTPADDING", (0,0), (-1,-1), 6), ("TOPPADDING", (0,0), (-1,-1), 6),
            ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story += [t, Spacer(1, 5*mm)]

        totals = Table([
            [Paragraph("Imponibile", body), Paragraph(f"€ {_eur(printed_imponibile)}", right_bold)],
            [Paragraph("IVA", body), Paragraph(f"€ {_eur(printed_iva)}", right_bold)],
            [Paragraph("TOTALE", bold), Paragraph(f"€ {_eur(printed_imponibile + printed_iva)}", right_bold)],
        ], colWidths=[42*mm, 38*mm], hAlign="RIGHT")
        totals.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), .7, border), ("INNERGRID", (0,0), (-1,-1), .3, border),
            ("BACKGROUND", (0,2), (-1,2), colors.HexColor("#FFF8D6")),
            ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
            ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
        ]))
        story += [totals]
        commercial_terms = []
        if quote.get("condizioni_pagamento"):
            commercial_terms.append([Paragraph("Condizioni di pagamento", bold), Paragraph(escape(str(quote.get("condizioni_pagamento"))), body)])
        if quote.get("tempi_consegna"):
            commercial_terms.append([Paragraph("Tempi di consegna / esecuzione", bold), Paragraph(escape(str(quote.get("tempi_consegna"))), body)])
        if commercial_terms:
            story += [Spacer(1, 6*mm)]
            terms = Table(commercial_terms, colWidths=[55*mm, 121*mm])
            terms.setStyle(TableStyle([
                ("BOX", (0,0), (-1,-1), .7, border), ("INNERGRID", (0,0), (-1,-1), .3, border),
                ("BACKGROUND", (0,0), (0,-1), light), ("VALIGN", (0,0), (-1,-1), "TOP"),
                ("LEFTPADDING", (0,0), (-1,-1), 7), ("RIGHTPADDING", (0,0), (-1,-1), 7),
                ("TOPPADDING", (0,0), (-1,-1), 6), ("BOTTOMPADDING", (0,0), (-1,-1), 6),
            ]))
            story.append(terms)
        if quote.get("note"):
            story += [Spacer(1, 6*mm), Paragraph("NOTE", bold), Spacer(1, 2*mm), Paragraph(escape(str(quote.get("note"))).replace("\n", "<br/>"), body)]

        story += [Spacer(1, 10*mm)]
        sign = Table([
            [Paragraph("Accettazione", bold), Paragraph("Data e firma", bold)],
            [Paragraph("<br/><br/>____________________________", body), Paragraph("<br/><br/>____________________________", right)],
        ], colWidths=[96*mm, 80*mm])
        sign.setStyle(TableStyle([
            ("BOX", (0,0), (-1,-1), .7, border), ("INNERGRID", (0,0), (-1,-1), .3, border),
            ("LEFTPADDING", (0,0), (-1,-1), 8), ("RIGHTPADDING", (0,0), (-1,-1), 8),
            ("TOPPADDING", (0,0), (-1,-1), 8), ("BOTTOMPADDING", (0,0), (-1,-1), 8),
        ]))
        story += [KeepTogether(sign)]
        story += [Spacer(1, 7*mm), Paragraph(
            f"{escape(company_email)} · {escape(company_phone)}",
            ParagraphStyle("footerbrand", parent=small, alignment=TA_LEFT, textColor=muted, borderColor=border, borderWidth=.5, borderPadding=6)
        )]
        doc.build(story)
        buf.seek(0)

        now = datetime.now(timezone.utc)
        pdf_update = {
            "pdf_revision": revision, "pdf_signature": signature, "pdf_outdated": False,
            "pdf_generated_at": now, "pdf_generated_by": current.get("username"), "updated_at": now,
        }
        if str(quote.get("stato") or "").lower() in ("", "bozza"):
            pdf_update["stato"] = "Da inviare"
        await coll("preventivi").update_one({"id": record_id}, {"$set": pdf_update})
        filename = f"{numero}.pdf".replace("/", "-").replace("\\", "-")
        headers = {"Content-Disposition": f'attachment; filename="{filename}"', "X-Quote-Revision": str(int(quote.get("quote_revision") or 1))}
        return StreamingResponse(buf, media_type="application/pdf", headers=headers)

    @router.post("/preventivi/{record_id}/revision")
    async def create_quote_revision(record_id: str, current=Depends(dep)):
        """Crea una nuova revisione commerciale modificabile dello stesso preventivo.
        La revisione accettata precedente resta congelata e tracciabile; la nuova revisione
        aggiornerà la stessa commessa quando verrà accettata.
        """
        quote = await coll("preventivi").find_one({"id": record_id})
        if not quote:
            raise HTTPException(404, "Preventivo non trovato")
        if str(quote.get("stato") or "").lower() != "accettato":
            raise HTTPException(409, "Puoi creare una nuova revisione solo da un preventivo accettato")
        successor_id = str(quote.get("superseded_by_revision_id") or "").strip()
        if successor_id:
            successor = await coll("preventivi").find_one({"id": successor_id})
            if successor:
                raise HTTPException(409, f"Esiste già la Rev. {int(successor.get('quote_revision') or 2)} di questo preventivo")

        root_id = str(quote.get("revision_root_id") or quote.get("id"))
        siblings = await coll("preventivi").find({
            "$or": [{"revision_root_id": root_id}, {"id": root_id}]
        }).to_list(length=500)
        current_rev = max([int(x.get("quote_revision") or 1) for x in siblings] or [1])
        new_rev = current_rev + 1
        now = datetime.now(timezone.utc)

        copy_fields = [
            "numero", "cliente_id", "nominativo", "telefono", "email", "sopralluogo_id",
            "sede_id", "data", "validita_giorni", "condizioni_pagamento", "tempi_consegna",
            "note", "righe", "imponibile", "iva_totale", "totale", "importo",
        ]
        doc = {k: quote.get(k) for k in copy_fields if k in quote}
        doc.update({
            "id": str(uuid.uuid4()),
            "quote_revision": new_rev,
            "revision_root_id": root_id,
            "previous_revision_id": str(quote.get("id")),
            "stato": "Bozza",
            "pdf_revision": 0,
            "pdf_signature": None,
            "pdf_outdated": False,
            "accepted_at": None,
            "accepted_by": None,
            "accepted_pdf_revision": None,
            "sent_at": None,
            "sent_by": None,
            "created_at": now,
            "updated_at": now,
            "created_by": current.get("username"),
            "revision_created_from": str(quote.get("id")),
        })
        await coll("preventivi").insert_one(doc)
        await coll("preventivi").update_one({"id": record_id}, {"$set": {
            "superseded_by_revision_id": doc["id"],
            "updated_at": now,
        }})
        return _clean(doc)

    @router.get("/preventivi/{record_id}/revisions")
    async def list_quote_revisions(record_id: str, current=Depends(dep)):
        quote = await coll("preventivi").find_one({"id": record_id})
        if not quote:
            raise HTTPException(404, "Preventivo non trovato")
        root_id = str(quote.get("revision_root_id") or quote.get("id"))
        docs = await coll("preventivi").find({
            "$or": [{"revision_root_id": root_id}, {"id": root_id}]
        }).to_list(length=500)
        docs.sort(key=lambda x: int(x.get("quote_revision") or 1), reverse=True)
        return {"items": [_clean(x) for x in docs], "count": len(docs), "root_id": root_id}

    @router.post("/preventivi/{record_id}/mark-sent")
    async def mark_quote_sent(record_id: str, current=Depends(dep)):
        quote = await coll("preventivi").find_one({"id": record_id})
        if not quote:
            raise HTTPException(404, "Preventivo non trovato")
        if str(quote.get("stato") or "").lower() == "accettato":
            raise HTTPException(409, "Il preventivo è già accettato")
        if not quote.get("pdf_revision") or quote.get("pdf_outdated"):
            raise HTTPException(409, "Genera il PDF aggiornato prima di segnare il preventivo come inviato")
        now = datetime.now(timezone.utc)
        await coll("preventivi").update_one({"id": record_id}, {"$set": {
            "stato": "Inviato", "sent_at": now, "sent_by": current.get("username"), "updated_at": now,
        }})
        return _clean(await coll("preventivi").find_one({"id": record_id}))

    @router.post("/preventivi/{record_id}/accept")
    async def accept_quote(record_id: str, current=Depends(dep)):
        quote = await coll("preventivi").find_one({"id": record_id})
        if not quote:
            raise HTTPException(404, "Preventivo non trovato")
        if str(quote.get("stato") or "").lower() == "accettato":
            root_id = str(quote.get("revision_root_id") or record_id)
            existing_commessa = await db.commesse.find_one({"$or": [{"preventivo_root_id": root_id}, {"preventivo_id": record_id}], "stato": {"$ne": "annullata"}})
            result = _clean(quote)
            result["commessa"] = _clean(existing_commessa) if existing_commessa else None
            return result
        if not quote.get("pdf_revision") or quote.get("pdf_outdated"):
            raise HTTPException(409, "Genera il PDF aggiornato del preventivo prima di confermarlo")
        now = datetime.now(timezone.utc)
        await coll("preventivi").update_one({"id": record_id}, {"$set": {
            "stato": "Accettato", "accepted_at": now, "accepted_by": current.get("username"),
            "accepted_pdf_revision": int(quote.get("pdf_revision") or 1),
            "accepted_quote_revision": int(quote.get("quote_revision") or 1), "updated_at": now,
        }})
        fresh = await coll("preventivi").find_one({"id": record_id})
        commessa = await _commessa_from_quote(fresh, current.get("username") or "utente")
        result = _clean(fresh)
        result["commessa"] = commessa
        return result

    @router.post("/clienti/{client_id}/archive")
    async def archive_client(client_id: str, current=Depends(dep)):
        cliente = await coll("clienti").find_one({"id": client_id})
        if not cliente:
            raise HTTPException(404, "Cliente non trovato")
        now = datetime.now(timezone.utc)
        await coll("clienti").update_one({"id": client_id}, {"$set": {
            "archived": True, "archived_at": now, "archived_by": current.get("username"), "updated_at": now
        }})
        return _clean(await coll("clienti").find_one({"id": client_id}))

    @router.post("/clienti/{client_id}/restore")
    async def restore_client(client_id: str, current=Depends(dep)):
        cliente = await coll("clienti").find_one({"id": client_id})
        if not cliente:
            raise HTTPException(404, "Cliente non trovato")
        now = datetime.now(timezone.utc)
        await coll("clienti").update_one({"id": client_id}, {"$set": {
            "archived": False, "updated_at": now, "restored_by": current.get("username")
        }, "$unset": {"archived_at": "", "archived_by": ""}})
        return _clean(await coll("clienti").find_one({"id": client_id}))

    @router.get("/clienti/{client_id}/delete-impact")
    async def client_delete_impact(client_id: str, current=Depends(dep)):
        cliente = await coll("clienti").find_one({"id": client_id})
        if not cliente:
            raise HTTPException(404, "Cliente non trovato")
        counts = {}
        for child_resource, child_field in DELETE_GUARDS.get("clienti", []):
            n = await coll(child_resource).count_documents({child_field: client_id})
            if n:
                counts[child_resource] = n
        for collection_name, child_field in EXTERNAL_DELETE_GUARDS.get("clienti", []):
            n = await db[collection_name].count_documents({child_field: client_id})
            if n:
                counts[collection_name] = n
        docs = await db.documents.count_documents({"resource": "clienti", "record_id": client_id})
        if docs:
            counts["documenti"] = docs
        return {"can_delete": not bool(counts), "linked": counts, "archived": bool(cliente.get("archived"))}

    @router.post("/{resource}")
    async def create_record(resource: str, body: RecordBody, current=Depends(dep)):
        c = coll(resource)
        now = datetime.now(timezone.utc)
        data = body.model_dump(exclude_none=True)
        data = await normalize_relations(resource, data)

        # Anagrafica cliente unica: previene i duplicati più comuni.
        if resource == "clienti":
            ors = []
            for field in ("partita_iva", "codice_fiscale", "email", "telefono"):
                value = str(data.get(field) or "").strip()
                if value:
                    ors.append({field: {"$regex": f"^{__import__('re').escape(value)}$", "$options": "i"}})
            if ors:
                duplicate = await c.find_one({"$or": ors})
                if duplicate:
                    raise HTTPException(409, f"Esiste già il cliente '{duplicate.get('ragione_sociale') or duplicate.get('nome') or 'senza nome'}' con uno dei dati inseriti")

        # Gli stati Inviato/Accettato devono passare dalle azioni dedicate,
        # così PDF/revisione e commessa restano coerenti.
        if resource == "preventivi" and str(data.get("stato") or "").lower() in ("inviato", "accettato"):
            raise HTTPException(409, "Salva il preventivo in bozza/da inviare e usa le azioni Invia o Accetta")

        # Numerazioni locali automatiche.
        if resource == "preventivi" and not str(data.get("numero") or "").strip():
            year = now.year
            counter = await db.counters.find_one_and_update(
                {"_id": f"quotes:{year}"}, {"$inc": {"value": 1}}, upsert=True, return_document=ReturnDocument.AFTER
            )
            seq = int((counter or {}).get("value") or 1)
            data["numero"] = f"PREV-{year}-{seq:04d}"

        if resource == "preventivi":
            data.setdefault("quote_revision", 1)

        if resource == "ordini-clienti" and not str(data.get("numero") or "").strip():
            year = now.year
            counter = await db.counters.find_one_and_update(
                {"_id": f"orders:{year}"}, {"$inc": {"value": 1}}, upsert=True, return_document=ReturnDocument.AFTER
            )
            seq = int((counter or {}).get("value") or 1)
            data["numero"] = f"ET-{year}-{seq:04d}"

        # Se l'ordine nasce da un preventivo, eredita automaticamente righe e importo
        # quando non sono stati modificati esplicitamente nell'ordine.
        if resource == "ordini-clienti" and data.get("preventivo_id"):
            prev = await coll("preventivi").find_one({"id": str(data.get("preventivo_id"))})
            if prev:
                if not data.get("righe"):
                    data["righe"] = prev.get("righe") or []
                if data.get("importo") in (None, ""):
                    data["importo"] = prev.get("totale") if prev.get("totale") is not None else prev.get("importo")
                data.setdefault("sopralluogo_id", prev.get("sopralluogo_id"))

        data.update({
            "id": str(uuid.uuid4()),
            "created_at": now,
            "updated_at": now,
            "created_by": current.get("username"),
        })
        await c.insert_one(data)
        if resource == "clienti":
            await sync_primary_client_links(data)
        if resource == "preventivi" and str(data.get("stato") or "").lower() == "accettato":
            data["commessa"] = await _commessa_from_quote(data, current.get("username") or "utente")
        return _clean(data)

    @router.put("/{resource}/{record_id}")
    async def update_record(resource: str, record_id: str, body: RecordBody, current=Depends(dep)):
        c = coll(resource)
        existing = await c.find_one({"id": record_id})
        if not existing:
            raise HTTPException(404, "Record non trovato")
        if resource == "installazioni":
            await _ensure_installation_owner_access(existing, current)
        data = body.model_dump(exclude_none=True)
        if resource == "installazioni" and current.get("role") == auth_mod.ROLE_TECNICO:
            # Il tecnico può soltanto dichiarare l'esito operativo dell'intervento.
            allowed_keys = {"stato", "note"}
            forbidden = [k for k in data.keys() if k not in allowed_keys and data.get(k) != existing.get(k)]
            if forbidden:
                raise HTTPException(403, "Il tecnico può modificare solo stato e note dell'intervento")
            requested = str(data.get("stato") or existing.get("stato") or "")
            if requested not in ("Installata", "Annullata"):
                raise HTTPException(403, "Il tecnico può impostare solo Installata o Annullata")
        if resource == "preventivi":
            existing_state = str(existing.get("stato") or "").lower()
            requested_state = str(data.get("stato") or existing.get("stato") or "").lower()
            if existing_state == "accettato":
                raise HTTPException(409, "Un preventivo accettato non è modificabile. Usa 'Crea nuova revisione'.")
            if requested_state in ("inviato", "accettato") and requested_state != existing_state:
                raise HTTPException(409, "Usa le azioni dedicate Invia o Accetta per mantenere PDF, revisione e commessa coerenti")
        data.pop("id", None)
        data.pop("created_at", None)
        data.pop("created_by", None)
        data = await normalize_relations(resource, data)
        if resource == "preventivi" and existing.get("pdf_signature"):
            merged_for_pdf = dict(existing)
            merged_for_pdf.update(data)
            data["pdf_outdated"] = _quote_signature(merged_for_pdf) != str(existing.get("pdf_signature"))
            if data["pdf_outdated"] and str(existing.get("stato") or "").lower() == "inviato":
                data["stato"] = "Da inviare"
        if resource == "ordini-clienti" and data.get("preventivo_id"):
            prev = await coll("preventivi").find_one({"id": str(data.get("preventivo_id"))})
            if prev:
                if not data.get("righe"):
                    data["righe"] = prev.get("righe") or []
                if data.get("importo") in (None, ""):
                    data["importo"] = prev.get("totale") if prev.get("totale") is not None else prev.get("importo")
                data.setdefault("sopralluogo_id", prev.get("sopralluogo_id"))
        data["updated_at"] = datetime.now(timezone.utc)
        data["updated_by"] = current.get("username")
        if resource == "preventivi" and str(data.get("stato") or "").lower() == "accettato":
            data["accepted_at"] = datetime.now(timezone.utc)
            data["accepted_by"] = current.get("username")
            data["accepted_pdf_revision"] = int(existing.get("pdf_revision") or 0) or None
        await c.update_one({"id": record_id}, {"$set": data})
        if resource == "clienti":
            merged = dict(existing)
            merged.update(data)
            merged["id"] = record_id
            await sync_primary_client_links(merged)

        # Se una installazione viene completata, chiude l'ordine cliente collegato.
        # "Installata" è l'esito del tecnico; "Completata" è la chiusura amministrativa.
        if resource == "installazioni" and data.get("stato") in ("Installata", "Completata"):
            ordine_id = data.get("ordine_cliente_id") or existing.get("ordine_cliente_id")
            if ordine_id:
                await coll("ordini-clienti").update_one(
                    {"id": ordine_id},
                    {"$set": {
                        "stato": "Completato",
                        "stato_installazione": "Completata",
                        "updated_at": datetime.now(timezone.utc),
                    }},
                )

        doc = await c.find_one({"id": record_id})
        if resource == "ordini-clienti":
            synced = await _sync_order_to_commessa(doc or {})
            if synced:
                result = _clean(doc)
                result["commessa"] = synced
                return result
        if resource == "preventivi" and str((doc or {}).get("stato") or "").lower() == "accettato":
            result = _clean(doc)
            result["commessa"] = await _commessa_from_quote(doc, current.get("username") or "utente")
            return result
        return _clean(doc)

    @router.delete("/{resource}/{record_id}")
    async def delete_record(resource: str, record_id: str, current=Depends(dep)):
        if resource == "clienti" and str(current.get("role") or "").lower() != "admin":
            raise HTTPException(403, "Solo un Admin può eliminare definitivamente un cliente. Puoi archiviarlo.")
        c = coll(resource)
        existing = await c.find_one({"id": record_id})
        if not existing:
            raise HTTPException(404, "Record non trovato")
        if resource == "installazioni":
            _ensure_installation_owner_access(existing, current)

        linked = []
        for child_resource, child_field in DELETE_GUARDS.get(resource, []):
            count = await coll(child_resource).count_documents({child_field: record_id})
            if count:
                linked.append(f"{child_resource}: {count}")
        for collection_name, child_field in EXTERNAL_DELETE_GUARDS.get(resource, []):
            count = await db[collection_name].count_documents({child_field: record_id})
            if count:
                linked.append(f"{collection_name}: {count}")
        doc_count = await db.documents.count_documents({"resource": resource, "record_id": record_id})
        if doc_count:
            linked.append(f"documenti: {doc_count}")
        if linked:
            raise HTTPException(
                409,
                "Impossibile eliminare: il record è ancora collegato a " + ", ".join(linked),
            )

        previous_revision_id = str(existing.get("previous_revision_id") or "") if resource == "preventivi" else ""
        res = await c.delete_one({"id": record_id})
        if not res.deleted_count:
            raise HTTPException(404, "Record non trovato")
        if resource == "interventi-tecnici" and existing.get("calendar_event_id"):
            await db.calendar_events.update_one(
                {"id": str(existing.get("calendar_event_id"))},
                {"$set": {"technical_sync_excluded": True, "technical_sync_excluded_at": datetime.now(timezone.utc), "technical_sync_excluded_by": current.get("username") or current.get("email") or "utente"}},
            )
        if resource == "preventivi" and previous_revision_id:
            await coll("preventivi").update_one(
                {"id": previous_revision_id, "superseded_by_revision_id": record_id},
                {"$unset": {"superseded_by_revision_id": ""}, "$set": {"updated_at": datetime.now(timezone.utc)}},
            )
        return {"ok": True}

    return router
