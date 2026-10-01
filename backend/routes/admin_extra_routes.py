"""Admin P1 extra routes (Prompt 220) + F7 extensions.

Include:
  - Audit log
  - Anomalie delete/clear
  - Storico Seriali
  - Impostazioni estese (scanner/dashboard/magazzino/ricerca/movimenti/sicurezza)
  - Cleanup dati TEST_ (mai tocca Notion)
  - Ricerca globale
  - Sessioni attive: GET / DELETE (F7)

Tutte le rotte sono JWT-admin.
"""
import logging
import os
import re
import shutil
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from fastapi import APIRouter, HTTPException, Depends, Query
from pydantic import BaseModel, Field, ConfigDict

import auth as auth_mod
import notion_service
import event_logger
import email_service
import secret_store

logger = logging.getLogger(__name__)


# ---------- Settings model (F7: sezioni annidate) ----------

class ScannerSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # F11 — impostazioni globali scanner
    scanner_enabled: Optional[bool] = None
    camera_enabled: Optional[bool] = None
    continuous_scan: Optional[bool] = None           # scansione continua globale
    auto_acquire: Optional[bool] = None              # acquisizione automatica
    enter_equals_add: Optional[bool] = None          # INVIO = aggiungi
    prevent_double_scan: Optional[bool] = None       # blocca doppia scansione ravvicinata
    min_scan_interval_ms: Optional[int] = Field(default=None, ge=0, le=5000)
    error_behavior: Optional[str] = Field(default=None, pattern="^(retry|block|skip)$")
    autofocus: Optional[bool] = None
    feedback_green_ms: Optional[int] = Field(default=None, ge=200, le=10000)
    feedback_red_ms: Optional[int] = Field(default=None, ge=200, le=10000)
    autoselect_single_result: Optional[bool] = None
    sound_enabled: Optional[bool] = None


class DashboardSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    autorefresh_seconds: Optional[int] = Field(default=None, ge=0, le=3600)
    recent_movements_limit: Optional[int] = Field(default=None, ge=1, le=100)


class MagazzinoSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    low_stock_threshold: Optional[int] = Field(default=None, ge=0, le=1000)
    near_empty_threshold: Optional[int] = Field(default=None, ge=0, le=1000)
    warn_low_stock: Optional[bool] = None
    warn_out_of_stock: Optional[bool] = None
    out_of_stock_behavior: Optional[str] = Field(default=None, pattern="^(block|warn|ignore)$")
    unconfigured_product_behavior: Optional[str] = Field(default=None, pattern="^(block|warn|ignore)$")
    prevent_duplicates: Optional[bool] = None
    allow_partial_shipment: Optional[bool] = None


class RicercaSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    search_on_type: Optional[bool] = None
    max_results: Optional[int] = Field(default=None, ge=1, le=200)
    partial_match: Optional[bool] = None


class MovimentiSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    max_shown: Optional[int] = Field(default=None, ge=10, le=1000)
    auto_open_current_month: Optional[bool] = None


class SicurezzaSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    session_ttl_minutes: Optional[int] = Field(default=None, ge=15, le=60 * 24 * 30)
    idle_logout_minutes: Optional[int] = Field(default=None, ge=1, le=1440)
    max_login_attempts: Optional[int] = Field(default=None, ge=3, le=20)
    lockout_minutes: Optional[int] = Field(default=None, ge=1, le=1440)


class ArriviSettings(BaseModel):
    """F10 §10 — Impostazioni Arrivi realmente configurabili.
    Le protezioni fondamentali (product_required_serial, verify_on_notion) sono
    accettate solo se True — non è possibile disattivarle."""
    model_config = ConfigDict(extra="ignore")
    allow_new_serials: Optional[bool] = None          # consenti seriali mai visti
    continuous_scan: Optional[bool] = None            # focus al prossimo campo dopo INVIO
    enter_equals_add: Optional[bool] = None           # INVIO = aggiungi (no bottone CERCA)
    final_confirmation: Optional[bool] = None         # richiedi dialog di conferma prima di scrivere
    require_code_for_qty: Optional[bool] = None       # codice obbligatorio per Ricevi Quantità
    require_quantity: Optional[bool] = None           # quantità obbligatoria


class SpedizioniSettings(BaseModel):
    """F10 §10 — Impostazioni Spedizioni realmente configurabili.
    Le protezioni fondamentali (verify_serial_in_inventory, block_duplicates,
    block_already_shipped, block_insufficient_qty) NON sono disattivabili."""
    model_config = ConfigDict(extra="ignore")
    continuous_scan: Optional[bool] = None            # focus al prossimo dopo scan/INVIO
    final_check: Optional[bool] = None                # ricontrollo completo prima di CONFERMA
    allow_partial_shipment: Optional[bool] = None     # permetti spedizioni parziali


class RetroattivitaSettings(BaseModel):
    """F14 §9 — Impostazioni retroattività."""
    model_config = ConfigDict(extra="ignore")
    email_enabled: Optional[bool] = None              # invio email automatico dopo save success


# Lista IANA supportata (fusi principali internazionali). L'ora legale/solare è gestita
# automaticamente da ZoneInfo. Sono i tz mostrati nella UI Admin.
SUPPORTED_TIMEZONES = [
    "Europe/Rome", "Europe/London", "Europe/Paris", "Europe/Berlin",
    "Europe/Madrid", "Europe/Lisbon",
    "America/New_York", "America/Chicago", "America/Denver", "America/Los_Angeles",
    "Asia/Dubai", "Asia/Tokyo", "Australia/Sydney", "UTC",
]


class GeneralSettings(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # F11 — nuove impostazioni gestionale
    app_name: Optional[str] = Field(default=None, min_length=1, max_length=80)
    company_name: Optional[str] = Field(default=None, min_length=1, max_length=120)
    logo_url: Optional[str] = Field(default=None, max_length=500)
    language: Optional[str] = Field(default=None, pattern="^(it|en)$")
    date_format: Optional[str] = Field(default=None, pattern="^(DD/MM/YYYY|YYYY-MM-DD|MM/DD/YYYY)$")
    time_format: Optional[str] = Field(default=None, pattern="^(24h|12h)$")
    primary_color: Optional[str] = Field(default=None, pattern="^#[0-9a-fA-F]{6}$")
    auto_refresh_enabled: Optional[bool] = None
    confirm_important_ops: Optional[bool] = None
    timezone: Optional[str] = Field(default=None, min_length=2, max_length=64)
    inventory_source: Optional[str] = Field(default=None, pattern="^(notion|gestionale)$")


class SettingsBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    # Retro-compat flat fields (usati dal frontend F6)
    low_stock_threshold: Optional[int] = Field(default=None, ge=0, le=1000)
    test_prefix: Optional[str] = Field(default=None, min_length=1, max_length=20)
    feedback_seconds: Optional[int] = Field(default=None, ge=1, le=30)
    # F7 nested sections
    scanner: Optional[ScannerSettings] = None
    dashboard: Optional[DashboardSettings] = None
    magazzino: Optional[MagazzinoSettings] = None
    ricerca: Optional[RicercaSettings] = None
    movimenti: Optional[MovimentiSettings] = None
    sicurezza: Optional[SicurezzaSettings] = None
    # F10 Arrivi/Spedizioni configurabili
    arrivi: Optional[ArriviSettings] = None
    spedizioni: Optional[SpedizioniSettings] = None
    # F14 Retroattività
    retroattivita: Optional[RetroattivitaSettings] = None
    # F8 general (timezone)
    general: Optional[GeneralSettings] = None


class EmailConfigBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    enabled: Optional[bool] = None
    host: Optional[str] = Field(default=None, max_length=255)
    port: Optional[int] = Field(default=None, ge=1, le=65535)
    username: Optional[str] = Field(default=None, max_length=255)
    password: Optional[str] = Field(default=None, max_length=500)
    from_email: Optional[str] = Field(default=None, max_length=255)
    from_name: Optional[str] = Field(default=None, max_length=120)
    security: Optional[str] = Field(default=None, pattern="^(starttls|ssl|none)$")


class EmailTestBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    recipient: str = Field(min_length=3, max_length=255)


class CleanupConfirmBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    confirm: bool = False
    prefix: Optional[str] = None


class DataResetBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    scope: str = Field(default="all", pattern="^(all|crm|commesse|magazzino|movimenti|documenti|assistente)$")
    confirmation_text: str = Field(default="", max_length=80)


# ---------- Default settings ----------

DEFAULT_SETTINGS: Dict[str, Any] = {
    # Retro-compat flat (usati da F6)
    "low_stock_threshold": 2,
    "test_prefix": "TEST_",
    "feedback_seconds": 3,
    # F7 nested
    "scanner": {
        "scanner_enabled": True,
        "camera_enabled": True,
        "continuous_scan": True,
        "auto_acquire": True,
        "enter_equals_add": True,
        "prevent_double_scan": True,
        "min_scan_interval_ms": 300,
        "error_behavior": "retry",
        "autofocus": True,
        "feedback_green_ms": 3000,
        "feedback_red_ms": 3000,
        "autoselect_single_result": True,
        "sound_enabled": False,
    },
    "dashboard": {
        "autorefresh_seconds": 0,          # 0 = disattivato
        "recent_movements_limit": 10,
    },
    "magazzino": {
        "low_stock_threshold": 2,
        "near_empty_threshold": 5,
        "warn_low_stock": True,
        "warn_out_of_stock": True,
        "out_of_stock_behavior": "warn",   # block | warn | ignore
        "unconfigured_product_behavior": "block",
        "prevent_duplicates": True,
        "allow_partial_shipment": False,
    },
    "ricerca": {
        "search_on_type": True,
        "max_results": 50,
        "partial_match": True,
    },
    "movimenti": {
        "max_shown": 200,
        "auto_open_current_month": True,
    },
    "sicurezza": {
        "session_ttl_minutes": 480,        # 8h default (allineato JWT_ACCESS_TTL_MINUTES)
        "idle_logout_minutes": 30,
        "max_login_attempts": 5,
        "lockout_minutes": 5,
    },
    "arrivi": {
        "allow_new_serials": True,
        "continuous_scan": True,
        "enter_equals_add": True,
        "final_confirmation": True,
        "require_code_for_qty": True,
        "require_quantity": True,
    },
    "spedizioni": {
        "continuous_scan": True,
        "final_check": True,
        "allow_partial_shipment": False,
    },
    "retroattivita": {
        "email_enabled": False,   # F14 §9 — default OFF (no email)
    },
    "general": {
        "app_name": "Gestionale Elios Tech",
        "company_name": "Elios Tech S.r.l.",
        "logo_url": "",
        "language": "it",
        "date_format": "DD/MM/YYYY",
        "time_format": "24h",
        "primary_color": "#0f172a",
        "auto_refresh_enabled": False,
        "confirm_important_ops": True,
        "timezone": "Europe/Rome",         # IANA — gestisce auto ora legale/solare
        "inventory_source": "gestionale",       # 'notion' | 'gestionale' — switch fonte inventario
    },
}


def _merge_section(base: Dict[str, Any], override: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    """Merge override sopra base, ignorando chiavi None."""
    out = dict(base)
    if isinstance(override, dict):
        for k, v in override.items():
            if v is not None:
                out[k] = v
    return out


async def get_app_settings(db) -> Dict[str, Any]:
    doc = await db.settings.find_one({"_id": "app_settings"}) or {}
    result: Dict[str, Any] = {
        # Retro-compat flat
        "low_stock_threshold": int(doc.get("low_stock_threshold", DEFAULT_SETTINGS["low_stock_threshold"])),
        "test_prefix": doc.get("test_prefix", DEFAULT_SETTINGS["test_prefix"]),
        "feedback_seconds": int(doc.get("feedback_seconds", DEFAULT_SETTINGS["feedback_seconds"])),
    }
    # Nested — merge default con quanto salvato
    for section in ("scanner", "dashboard", "magazzino", "ricerca", "movimenti", "sicurezza", "arrivi", "spedizioni", "retroattivita", "general"):
        result[section] = _merge_section(DEFAULT_SETTINGS[section], doc.get(section))
    # Coerenza: mantieni magazzino.low_stock_threshold allineato al flat top-level
    result["magazzino"]["low_stock_threshold"] = result["low_stock_threshold"]
    # Gestionale autonomo: Notion e' solo una sorgente di migrazione iniziale.
    result["general"]["inventory_source"] = "gestionale"
    return result


def build_router(db, deps: auth_mod.AuthDependencies) -> APIRouter:
    router = APIRouter(prefix="/admin", tags=["admin-extra"], dependencies=[Depends(deps.require_admin)])

    # R13 — aree dati cancellabili. Utenti, impostazioni, configurazioni e log NON sono inclusi.
    RESET_GROUPS = {
        "crm": [
            "crm_lead", "crm_clienti", "crm_contatti", "crm_sedi", "crm_sopralluoghi",
            "crm_preventivi", "crm_ordini_clienti", "crm_installazioni", "crm_assistenza",
        ],
        "commesse": ["commesse"],
        "magazzino": [
            "products", "warehouse_stock", "product_serials", "product_qr_config",
            "qr_associations", "qr_bindings",
        ],
        "movimenti": [
            "arrivi", "checklists", "local_picks", "local_receipts", "local_transfers", "anomalies",
        ],
        "documenti": ["documents"],
        "assistente": ["ai_sessions", "ai_requests", "ai_pending_ops"],
    }
    RESET_LABELS = {
        "crm": "Clienti e CRM",
        "commesse": "Commesse",
        "magazzino": "Magazzino e prodotti",
        "movimenti": "Arrivi, spedizioni e movimenti",
        "documenti": "Documenti e allegati",
        "assistente": "Storico Assistente AI",
    }

    async def _reset_preview():
        groups = {}
        for scope, collections in RESET_GROUPS.items():
            by_collection = {}
            total = 0
            for name in collections:
                count = await db[name].count_documents({})
                by_collection[name] = count
                total += count
            groups[scope] = {"label": RESET_LABELS[scope], "total": total, "collections": by_collection}
        return {
            "groups": groups,
            "total": sum(g["total"] for g in groups.values()),
            "preserved": ["Utenti", "Impostazioni", "Ruoli e permessi", "Configurazioni", "Log sistema", "Audit attività"],
        }

    # ---------- Audit Log ----------
    @router.post("/audit-logs/clear-all")
    async def clear_all_audit_logs(current=Depends(deps.require_admin)):
        """F15 §18 — Cancella TUTTI i log del registro attività. Richiede admin.
        F18: registra CANCELLAZIONE_MASSIVA in app_events (persiste anche dopo clear)."""
        res = await db.audit_logs.delete_many({})
        await event_logger.log_event(
            db, category="CANCELLAZIONE", event_type="CANCELLAZIONE_MASSIVA",
            action="audit_logs.clear_all", level="WARNING", status="SUCCESS",
            user=current.get("username"), user_role=current.get("role"),
            endpoint="POST /api/admin/audit-logs/clear-all",
            resource="audit_logs",
            message=f"Cancellazione massiva Registro Attività: {res.deleted_count} record eliminati",
            details={"deleted_count": res.deleted_count},
        )
        return {"ok": True, "deleted": res.deleted_count}

    @router.delete("/audit-logs/{log_id}")
    async def delete_audit_log(log_id: str, current=Depends(deps.require_admin)):
        """F15 §18 — Cancella un singolo record dal registro attività.
        F18: registra CANCELLAZIONE_SINGOLA in app_events con snapshot del record."""
        from bson import ObjectId
        try:
            oid = ObjectId(log_id)
        except Exception:
            raise HTTPException(400, "ID non valido")
        target = await db.audit_logs.find_one({"_id": oid})
        target_snapshot = None
        if target:
            target_snapshot = {
                "action": target.get("action"),
                "actor_username": target.get("actor_username"),
                "at": target.get("at").isoformat() if isinstance(target.get("at"), datetime) else target.get("at"),
                "meta_keys": list((target.get("meta") or {}).keys()),
            }
        res = await db.audit_logs.delete_one({"_id": oid})
        if res.deleted_count == 0:
            raise HTTPException(404, "Record non trovato")
        await event_logger.log_event(
            db, category="CANCELLAZIONE", event_type="CANCELLAZIONE_SINGOLA",
            action="audit_logs.delete_one", level="INFO", status="SUCCESS",
            user=current.get("username"), user_role=current.get("role"),
            endpoint=f"DELETE /api/admin/audit-logs/{log_id}",
            resource="audit_logs",
            message=f"Record audit {log_id} cancellato",
            details={"deleted_id": log_id, "snapshot": target_snapshot},
        )
        return {"ok": True}

    @router.get("/system-logs")
    async def system_logs(
        limit: int = Query(default=500, ge=10, le=5000),
        level: Optional[str] = Query(default=None),
        q: Optional[str] = Query(default=None),
        source: Optional[str] = Query(default=None, pattern="^(app|http|all)?$"),
        category: Optional[str] = Query(default=None),
        event_type: Optional[str] = Query(default=None),
        user: Optional[str] = Query(default=None),
        product: Optional[str] = Query(default=None),
        serial: Optional[str] = Query(default=None),
        customer: Optional[str] = Query(default=None),
        status: Optional[str] = Query(default=None),
        operation_id: Optional[str] = Query(default=None),
        date_from: Optional[str] = Query(default=None),
        date_to: Optional[str] = Query(default=None),
    ):
        """F18 — Registro Log unificato: eventi applicativi (`app_events` in Mongo,
        strutturati, permanenti) + log HTTP/supervisor (file di sistema, best-effort).

        `source`:
          - `app`  → solo eventi applicativi (default per filtri applicativi)
          - `http` → solo log HTTP/supervisor
          - `all` / omesso → entrambi uniti (default retro-compat)
        """
        import re as _re
        results: List[Dict[str, Any]] = []
        want_app = source in (None, "", "app", "all")
        want_http = source in (None, "", "http", "all")
        applicative_filters_used = any([category, event_type, user, product, serial, customer, status, operation_id, date_from, date_to])
        if applicative_filters_used and source in (None, ""):
            want_http = False  # se l'utente filtra su campi applicativi, mostra solo app

        # 1) Eventi applicativi da Mongo
        if want_app:
            mongo_q: Dict[str, Any] = {}
            if level: mongo_q["level"] = level.upper()
            if category: mongo_q["category"] = category.upper()
            if event_type: mongo_q["event_type"] = event_type.upper()
            if user: mongo_q["user"] = {"$regex": _re.escape(user), "$options": "i"}
            if product: mongo_q["product"] = {"$regex": _re.escape(product), "$options": "i"}
            if serial: mongo_q["$or"] = [
                {"serial": {"$regex": _re.escape(serial), "$options": "i"}},
                {"serials": {"$regex": _re.escape(serial), "$options": "i"}},
            ]
            if customer: mongo_q["customer"] = {"$regex": _re.escape(customer), "$options": "i"}
            if status: mongo_q["status"] = status.upper()
            if operation_id: mongo_q["operation_id"] = operation_id
            if q:
                # ricerca testuale full-text semplice su message + action + product + serial
                rx = {"$regex": _re.escape(q), "$options": "i"}
                mongo_q.setdefault("$or", []).extend([
                    {"message": rx}, {"action": rx}, {"product": rx},
                    {"serial": rx}, {"customer": rx}, {"operation_id": rx},
                ])
            if date_from or date_to:
                ts_range = {}
                if date_from:
                    try:
                        ts_range["$gte"] = datetime.fromisoformat(date_from).replace(tzinfo=timezone.utc)
                    except Exception:
                        pass
                if date_to:
                    try:
                        # end-of-day inclusive
                        _d = datetime.fromisoformat(date_to).replace(tzinfo=timezone.utc)
                        ts_range["$lte"] = _d.replace(hour=23, minute=59, second=59)
                    except Exception:
                        pass
                if ts_range:
                    mongo_q["created_at"] = ts_range
            cursor = db.app_events.find(mongo_q).sort("created_at", -1).limit(limit)
            async for row in cursor:
                row.pop("_id", None)
                if isinstance(row.get("created_at"), datetime):
                    row["created_at"] = row["created_at"].isoformat()
                row["source"] = "app"
                row["file"] = None
                results.append(row)

        # 2) Log HTTP/supervisor da file (invariato — retro-compat)
        if want_http:
            paths = ["/var/log/supervisor/backend.err.log", "/var/log/supervisor/backend.out.log"]
            lines = []
            for p in paths:
                try:
                    with open(p, "r", errors="ignore") as f:
                        file_lines = f.readlines()[-limit:]
                        for line in file_lines:
                            lines.append({"file": p.split("/")[-1], "raw": line.rstrip()})
                except Exception:
                    pass
            secret_re = _re.compile(r'(password|passwd|pwd|token|api[_-]?key|secret|authorization|cookie|bearer)\s*[:=]\s*["\']?([^"\'\s,;]+)', _re.IGNORECASE)
            lvl_re = _re.compile(r'\b(DEBUG|INFO|WARNING|ERROR|CRITICAL)\b')
            ts_re = _re.compile(r'(\d{4}-\d{2}-\d{2}[ T]\d{2}:\d{2}:\d{2}(?:[.,]\d+)?(?:Z|[+-]\d{2}:?\d{2})?)')
            http_out = []
            for item in lines:
                raw = secret_re.sub(lambda m: f'{m.group(1)}=***REDACTED***', item["raw"])
                m_lvl = lvl_re.search(raw)
                m_ts = ts_re.search(raw)
                entry_level = m_lvl.group(1) if m_lvl else "INFO"
                if level and entry_level != level.upper():
                    continue
                if q and q.lower() not in raw.lower():
                    continue
                http_out.append({
                    "id": None,
                    "source": "http",
                    "file": item["file"],
                    "timestamp": m_ts.group(1) if m_ts else None,
                    "level": entry_level,
                    "category": "SYSTEM",
                    "event_type": "HTTP",
                    "message": raw,
                })
            http_out.reverse()
            results.extend(http_out)

        # Merge + limit
        # Ordina per timestamp (fallback: mantiene ordine)
        def _key(x):
            t = x.get("timestamp") or x.get("created_at") or ""
            return str(t)
        results.sort(key=_key, reverse=True)
        return {"items": results[:limit], "total": len(results)}

    @router.get("/system-logs/{event_id}")
    async def system_log_detail(event_id: str):
        """F18 — Dettaglio completo evento applicativo (solo source=app)."""
        doc = await db.app_events.find_one({"id": event_id})
        if not doc:
            raise HTTPException(404, "Evento non trovato")
        doc.pop("_id", None)
        if isinstance(doc.get("created_at"), datetime):
            doc["created_at"] = doc["created_at"].isoformat()
        # Correlati (stessa operation_id)
        related: List[Dict[str, Any]] = []
        if doc.get("operation_id"):
            cur = db.app_events.find({"operation_id": doc["operation_id"], "id": {"$ne": event_id}}).sort("created_at", 1).limit(50)
            async for r in cur:
                r.pop("_id", None)
                if isinstance(r.get("created_at"), datetime):
                    r["created_at"] = r["created_at"].isoformat()
                related.append(r)
        return {"item": doc, "related": related}

    @router.get("/audit-logs")
    async def list_audit_logs(limit: int = Query(default=200, ge=1, le=1000)):
        cursor = db.audit_logs.find({}).sort("at", -1).limit(limit)
        out = []
        async for row in cursor:
            row["_id"] = str(row["_id"])
            if isinstance(row.get("at"), datetime):
                row["at"] = row["at"].isoformat()
            out.append(row)
        return {"items": out, "count": len(out)}

    # ---------- Anomalie delete ----------
    @router.delete("/anomalie/{anomaly_id}")
    async def delete_anomaly(anomaly_id: str, current_user=Depends(deps.require_admin)):
        res = await db.anomalies.delete_one({"id": anomaly_id})
        if res.deleted_count == 0:
            res = await db.anomalies.delete_one({"_id": anomaly_id})
        if res.deleted_count == 0:
            raise HTTPException(404, "Anomalia non trovata")
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user["_id"]),
            "actor_username": current_user.get("username"),
            "action": "anomaly.delete",
            "target_user_id": None,
            "meta": {"anomaly_id": anomaly_id},
        })
        return {"ok": True}

    @router.delete("/anomalie")
    async def clear_all_anomalies(current_user=Depends(deps.require_admin)):
        res = await db.anomalies.delete_many({})
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user["_id"]),
            "actor_username": current_user.get("username"),
            "action": "anomaly.clear_all",
            "target_user_id": None,
            "meta": {"deleted": res.deleted_count},
        })
        return {"ok": True, "deleted": res.deleted_count}

    # ---------- Storico Seriali ----------
    @router.get("/serial-history/{sn}")
    async def serial_history(sn: str):
        sn_clean = (sn or "").strip()
        if not sn_clean:
            raise HTTPException(400, "SN obbligatorio")
        import inventory_local
        status = await inventory_local.latest_serial_status(sn_clean)
        return {
            "sn": sn_clean,
            "status": status.get("status"),
            "last_entrata": status.get("receipt"),
            "last_uscita": status.get("exit"),
        }

    # ---------- Impostazioni (estese F7) ----------
    @router.get("/settings")
    async def get_settings_route():
        return await get_app_settings(db)

    @router.put("/settings")
    async def put_settings(body: SettingsBody, current_user=Depends(deps.require_admin)):
        updates: Dict[str, Any] = {}
        # Retro-compat flat
        if body.low_stock_threshold is not None:
            updates["low_stock_threshold"] = int(body.low_stock_threshold)
        if body.test_prefix is not None:
            tp = body.test_prefix.strip()
            if not tp:
                raise HTTPException(400, "test_prefix non può essere vuoto")
            updates["test_prefix"] = tp
        if body.feedback_seconds is not None:
            updates["feedback_seconds"] = int(body.feedback_seconds)
        # F7 nested — merge sezione per sezione
        for section_name, section_body in [
            ("scanner", body.scanner),
            ("dashboard", body.dashboard),
            ("magazzino", body.magazzino),
            ("ricerca", body.ricerca),
            ("movimenti", body.movimenti),
            ("sicurezza", body.sicurezza),
            ("arrivi", body.arrivi),
            ("spedizioni", body.spedizioni),
            ("general", body.general),
        ]:
            if section_body is None:
                continue
            section_dict = section_body.model_dump(exclude_none=True)
            if not section_dict:
                continue
            # F8: valida timezone IANA
            if section_name == "general" and "timezone" in section_dict:
                tz_name = section_dict["timezone"]
                try:
                    from zoneinfo import ZoneInfo
                    ZoneInfo(tz_name)
                except Exception:
                    raise HTTPException(400, f"Fuso orario non valido: {tz_name}")
            current_doc = await db.settings.find_one({"_id": "app_settings"}) or {}
            merged = _merge_section(current_doc.get(section_name) or DEFAULT_SETTINGS[section_name], section_dict)
            updates[section_name] = merged
        # Se magazzino.low_stock_threshold è stato aggiornato, propaga al flat
        if isinstance(updates.get("magazzino"), dict) and "low_stock_threshold" in updates["magazzino"]:
            updates["low_stock_threshold"] = int(updates["magazzino"]["low_stock_threshold"])
        if not updates:
            raise HTTPException(400, "Nessun campo da aggiornare")
        await db.settings.update_one({"_id": "app_settings"}, {"$set": updates}, upsert=True)
        # Audit — senza payload sensibili
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user["_id"]),
            "actor_username": current_user.get("username"),
            "action": "settings.update",
            "target_user_id": None,
            "meta": {"sections": list(updates.keys())},
        })
        return await get_app_settings(db)

    # ---------- Sessioni attive (F7) ----------
    def _to_utc(dt):
        if not isinstance(dt, datetime):
            return None
        return dt if dt.tzinfo else dt.replace(tzinfo=timezone.utc)

    @router.get("/sessions")
    async def list_sessions():
        """Elenca tutte le sessioni attive. NON include informazioni sul dispositivo.

        Return: {items: [{sid, username, full_name, role, last_login, last_activity, online}]}
        online = last_activity nelle ultime 2 minuti.
        """
        settings = await get_app_settings(db)
        idle_min = int(settings["sicurezza"].get("idle_logout_minutes", 30))
        now = datetime.now(timezone.utc)
        cursor = db.active_sessions.find({}).sort("last_activity", -1)
        items = []
        users_by_id: Dict[str, Dict[str, Any]] = {}
        async for s in cursor:
            uid = s.get("user_id")
            user = users_by_id.get(uid)
            if user is None:
                from bson import ObjectId
                try:
                    user = await db.users.find_one({"_id": ObjectId(uid)}) or {}
                except Exception:
                    user = {}
                users_by_id[uid] = user
            la = _to_utc(s.get("last_activity"))
            ll = _to_utc(s.get("last_login"))
            online = False
            if la is not None:
                delta_min = (now - la).total_seconds() / 60.0
                online = delta_min < 2
                if delta_min > idle_min:
                    await db.active_sessions.delete_one({"sid": s.get("sid")})
                    continue
            items.append({
                "sid": s.get("sid"),
                "user_id": uid,
                "username": s.get("username") or user.get("username"),
                "full_name": f"{(user.get('first_name') or '').strip()} {(user.get('last_name') or '').strip()}".strip() or (user.get("username") or "—"),
                "email": user.get("email"),
                "role": user.get("role"),
                "last_login": ll.isoformat() if ll else None,
                "last_activity": la.isoformat() if la else None,
                "online": online,
            })
        return {"items": items, "count": len(items)}

    @router.delete("/sessions/{sid}")
    async def delete_session(sid: str, current_user=Depends(deps.require_admin)):
        # F8 — Account master: nessuno può forzare il logout delle sue sessioni.
        session = await db.active_sessions.find_one({"sid": sid})
        if session:
            user_id = session.get("user_id")
            if user_id:
                try:
                    from bson import ObjectId as _OID
                    user_doc = await db.users.find_one({"_id": _OID(user_id)})
                    if auth_mod.is_master_user(user_doc):
                        raise HTTPException(403, "Account master protetto: sessione non revocabile")
                except HTTPException:
                    raise
                except Exception:
                    pass
        res = await db.active_sessions.delete_one({"sid": sid})
        if res.deleted_count == 0:
            raise HTTPException(404, "Sessione non trovata")
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user["_id"]),
            "actor_username": current_user.get("username"),
            "action": "session.revoke",
            "target_user_id": None,
            "meta": {"sid": sid},
        })
        return {"ok": True}

    # ---------- Cleanup dati TEST_ ----------
    def _test_regex(prefix: str) -> re.Pattern:
        return re.compile(rf"^{re.escape(prefix)}", re.IGNORECASE)

    @router.get("/email/config")
    async def get_email_config_route(current_user=Depends(deps.require_admin)):
        return await email_service.get_email_config(db)

    @router.put("/email/config")
    async def put_email_config_route(body: EmailConfigBody, current_user=Depends(deps.require_admin)):
        payload = body.model_dump(exclude_unset=True)
        if payload.get("security") not in (None, "starttls", "ssl", "none"):
            raise HTTPException(400, "Sicurezza SMTP non valida")
        result = await email_service.save_email_config(db, payload)
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user.get("_id", "")),
            "actor_username": current_user.get("username"),
            "action": "email.config.update",
            "meta": {"enabled": result.get("enabled"), "host": result.get("host"), "password_updated": bool(payload.get("password"))},
        })
        return result

    @router.post("/email/test")
    async def test_email_config_route(body: EmailTestBody, current_user=Depends(deps.require_admin)):
        html = "<h2>Test Gestionale Elios Tech</h2><p>La configurazione email SMTP funziona correttamente.</p>"
        try:
            await email_service.send_email(db, body.recipient.strip(), "Test email - Gestionale Elios Tech", html)
        except Exception as e:
            raise HTTPException(502, f"Invio test fallito: {e}")
        return {"ok": True, "message": f"Email di test inviata a {body.recipient.strip()}"}

    @router.get("/system/status")
    async def system_status(current_user=Depends(deps.require_admin)):
        database_ok = False
        try:
            await db.command("ping")
            database_ok = True
        except Exception:
            database_ok = False
        try:
            from routes.ai_routes import get_provider_config
            ai_cfg = await get_provider_config(db)
        except Exception:
            ai_cfg = {"configured": False}
        try:
            email_cfg = await email_service.get_email_config(db)
        except Exception:
            email_cfg = {"configured": False, "enabled": False}
        # Notion non fa parte della diagnostica operativa: serve solo alla migrazione iniziale.
        try:
            from routes.documents_routes import UPLOAD_ROOT
            storage_ok = UPLOAD_ROOT.exists() and UPLOAD_ROOT.is_dir()
            storage_path = str(UPLOAD_ROOT)
        except Exception:
            storage_ok = False
            storage_path = ""
        return {
            "backend": {"ok": True, "label": "Backend locale"},
            "database": {"ok": database_ok, "label": "MongoDB locale"},
            "storage": {"ok": storage_ok, "label": "Archivio documenti", "path": storage_path},
            "ai": {"configured": bool(ai_cfg.get("configured")), "provider": ai_cfg.get("provider"), "model": ai_cfg.get("model")},
            "email": {"configured": bool(email_cfg.get("configured")), "enabled": bool(email_cfg.get("enabled"))},
        }

    # ---------- R13 — Svuota dati gestionali ----------
    @router.get("/data-reset/preview")
    async def data_reset_preview(current=Depends(deps.require_admin)):
        return await _reset_preview()

    @router.post("/data-reset")
    async def data_reset_execute(body: DataResetBody, current=Depends(deps.require_admin)):
        expected = "ELIMINA TUTTI I DATI" if body.scope == "all" else "ELIMINA DATI"
        if (body.confirmation_text or "").strip().upper() != expected:
            raise HTTPException(400, f'Conferma non valida. Digita esattamente: {expected}')

        selected_scopes = list(RESET_GROUPS.keys()) if body.scope == "all" else [body.scope]
        before = await _reset_preview()
        deleted = {}
        for scope in selected_scopes:
            for name in RESET_GROUPS[scope]:
                res = await db[name].delete_many({})
                deleted[name] = int(res.deleted_count)

        # I contatori sono dati operativi: se si azzera tutto ripartono anche le numerazioni.
        if body.scope == "all":
            res = await db.counters.delete_many({})
            deleted["counters"] = int(res.deleted_count)

        # Gli allegati fisici vengono rimossi solo quando si elimina l'area documenti/tutto.
        files_deleted = 0
        if "documenti" in selected_scopes:
            try:
                from routes.documents_routes import UPLOAD_ROOT
                if UPLOAD_ROOT.exists():
                    for child in list(UPLOAD_ROOT.iterdir()):
                        if child.is_dir():
                            for f in child.rglob("*"):
                                if f.is_file():
                                    files_deleted += 1
                            shutil.rmtree(child, ignore_errors=True)
                        elif child.is_file():
                            child.unlink(missing_ok=True)
                            files_deleted += 1
                UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)
            except Exception as exc:
                logging.getLogger(__name__).warning("Pulizia allegati incompleta: %s", exc)

        # I log restano intenzionalmente: registriamo anche questa azione distruttiva.
        now = datetime.now(timezone.utc)
        await db.audit_logs.insert_one({
            "at": now,
            "actor_id": str(current.get("_id") or current.get("id") or ""),
            "actor_username": current.get("username"),
            "action": "data.reset",
            "target_user_id": None,
            "meta": {"scope": body.scope, "deleted": deleted, "files_deleted": files_deleted},
        })
        try:
            await event_logger.log_event(
                db, category="CANCELLAZIONE", event_type="RESET_DATI_GESTIONALI",
                action="data.reset", level="WARNING", status="SUCCESS",
                user=current.get("username"), user_role=current.get("role"),
                endpoint="POST /api/admin/data-reset", resource="gestionale",
                message=f"Reset dati gestionali eseguito: {body.scope}",
                details={"scope": body.scope, "deleted": deleted, "files_deleted": files_deleted},
            )
        except Exception:
            pass

        return {
            "ok": True, "scope": body.scope, "deleted": deleted,
            "deleted_total": sum(deleted.values()), "files_deleted": files_deleted,
            "before": before, "preserved": before.get("preserved", []),
        }

    @router.get("/cleanup-test-data")
    async def cleanup_preview(prefix: Optional[str] = None):
        settings = await get_app_settings(db)
        p = (prefix or settings["test_prefix"]).strip()
        rx = _test_regex(p)
        checklists = await db.checklists.find(
            {"$or": [{"structure": {"$regex": rx}}, {"taken_by": {"$regex": rx}}, {"operator": {"$regex": rx}}]},
            {"id": 1, "structure": 1, "operator": 1, "shipping_date": 1, "created_at": 1, "_id": 0}
        ).to_list(500)
        arrivi = await db.arrivi.find(
            {"$or": [{"fornitore": {"$regex": rx}}, {"operator": {"$regex": rx}}]},
            {"id": 1, "fornitore": 1, "operator": 1, "arrival_date": 1, "created_at": 1, "_id": 0}
        ).to_list(500)
        anomalies = await db.anomalies.find(
            {"$or": [{"operator": {"$regex": rx}}, {"product": {"$regex": rx}}, {"description": {"$regex": rx}}]},
            {"_id": 0, "id": 1, "kind": 1, "operator": 1, "description": 1, "timestamp": 1}
        ).to_list(500)
        return {
            "prefix": p,
            "checklists": checklists,
            "arrivi": arrivi,
            "anomalies": anomalies,
            "total": len(checklists) + len(arrivi) + len(anomalies),
        }

    @router.post("/cleanup-test-data")
    async def cleanup_execute(body: CleanupConfirmBody, current_user=Depends(deps.require_admin)):
        if not body.confirm:
            raise HTTPException(400, "Conferma obbligatoria — imposta confirm=true")
        settings = await get_app_settings(db)
        p = ((body.prefix or settings["test_prefix"]) or "").strip()
        if not p:
            raise HTTPException(400, "Prefisso non valido")
        rx = _test_regex(p)
        r1 = await db.checklists.delete_many(
            {"$or": [{"structure": {"$regex": rx}}, {"taken_by": {"$regex": rx}}, {"operator": {"$regex": rx}}]}
        )
        r2 = await db.arrivi.delete_many(
            {"$or": [{"fornitore": {"$regex": rx}}, {"operator": {"$regex": rx}}]}
        )
        r3 = await db.anomalies.delete_many(
            {"$or": [{"operator": {"$regex": rx}}, {"product": {"$regex": rx}}, {"description": {"$regex": rx}}]}
        )
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user["_id"]),
            "actor_username": current_user.get("username"),
            "action": "cleanup.execute",
            "target_user_id": None,
            "meta": {"prefix": p, "checklists": r1.deleted_count, "arrivi": r2.deleted_count, "anomalies": r3.deleted_count},
        })
        return {
            "ok": True,
            "prefix": p,
            "checklists_deleted": r1.deleted_count,
            "arrivi_deleted": r2.deleted_count,
            "anomalies_deleted": r3.deleted_count,
        }

    # ---------- Ricerca globale ----------
    @router.get("/global-search")
    async def global_search(q: str = Query(..., min_length=1, max_length=100)):
        q_lower = q.strip().lower()
        try:
            import inventory_local
            inv = await inventory_local.list_inventory()
        except Exception:
            inv = []
        products = [it for it in inv if
                    q_lower in (it.get("name") or "").lower() or
                    q_lower in (it.get("code") or "").lower() or
                    q_lower in (it.get("category") or "").lower()][:25]
        checklists = await db.checklists.find(
            {"$or": [
                {"structure": {"$regex": q, "$options": "i"}},
                {"operator": {"$regex": q, "$options": "i"}},
                {"taken_by": {"$regex": q, "$options": "i"}},
            ]},
            {"_id": 0, "id": 1, "structure": 1, "operator": 1, "shipping_date": 1, "created_at": 1}
        ).sort("created_at", -1).limit(25).to_list(25)
        arrivi = await db.arrivi.find(
            {"$or": [
                {"fornitore": {"$regex": q, "$options": "i"}},
                {"operator": {"$regex": q, "$options": "i"}},
            ]},
            {"_id": 0, "id": 1, "fornitore": 1, "operator": 1, "arrival_date": 1, "created_at": 1}
        ).sort("created_at", -1).limit(25).to_list(25)
        sn_hit = None
        if len(q_lower) >= 4 and not any(c.isspace() for c in q_lower):
            try:
                st = await inventory_local.latest_serial_status(q.strip())
                if st.get("status") != "unseen":
                    sn_hit = st
            except Exception:
                pass
        return {
            "query": q,
            "products": products,
            "checklists": checklists,
            "arrivi": arrivi,
            "serial_status": sn_hit,
        }

    # ---------- Sistema / Manutenzione (F9) ----------
    @router.post("/maintenance/refresh-cache")
    async def refresh_cache():
        """Verifica e rilegge l'inventario locale. MongoDB è la fonte operativa unica."""
        try:
            import inventory_local
            items = await inventory_local.list_inventory(force_refresh=True)
            return {
                "ok": True,
                "source": "gestionale",
                "items_count": len(items),
                "at": datetime.now(timezone.utc).isoformat(),
            }
        except Exception as e:
            logger.error("inventory local refresh failed: %s", e)
            raise HTTPException(502, f"Errore verifica inventario locale: {e}")

    @router.get("/maintenance/status")
    async def maintenance_status():
        """Stato della fonte dati locale del gestionale."""
        try:
            import inventory_local
            items = await inventory_local.list_inventory()
            return {
                "source": "gestionale",
                "inventory_items": len(items),
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "ok": True,
            }
        except Exception as e:
            logger.warning("maintenance-status error: %s", e)
            return {
                "source": "gestionale",
                "inventory_items": 0,
                "checked_at": datetime.now(timezone.utc).isoformat(),
                "ok": False,
                "error": str(e),
            }

    # ---------- Inventario Gestionale: prodotti locali (F8/§16) ----------
    import uuid as _uuid
    import inventory_local

    class ProductCreate(BaseModel):
        model_config = ConfigDict(extra="ignore")
        name: str = Field(min_length=1, max_length=200)
        code: str = Field(min_length=1, max_length=100)
        category: Optional[str] = None
        tipo_gestione: str = Field(pattern="^(a_seriale|a_quantita)$")
        quantity: Optional[float] = 0
        unit: Optional[str] = "pz"
        threshold: Optional[int] = 0
        notes: Optional[str] = None
        active: Optional[bool] = True

    class ProductUpdate(BaseModel):
        model_config = ConfigDict(extra="ignore")
        name: Optional[str] = Field(default=None, min_length=1, max_length=200)
        code: Optional[str] = Field(default=None, min_length=1, max_length=100)
        category: Optional[str] = None
        tipo_gestione: Optional[str] = Field(default=None, pattern="^(a_seriale|a_quantita)$")
        quantity: Optional[float] = None
        unit: Optional[str] = None
        threshold: Optional[int] = None
        notes: Optional[str] = None
        active: Optional[bool] = None

    class SerialInput(BaseModel):
        model_config = ConfigDict(extra="ignore")
        serial: str = Field(min_length=1, max_length=200)

    def _now_iso() -> str:
        return datetime.now(timezone.utc).isoformat()

    @router.get("/products")
    async def list_products():
        out: List[Dict[str, Any]] = []
        async for doc in db.products.find({}):
            doc.pop("_id", None)
            if doc.get("tipo_gestione") == "a_seriale":
                avail = await db.product_serials.count_documents({"product_id": doc["id"], "status": "available"})
                shipped = await db.product_serials.count_documents({"product_id": doc["id"], "status": "shipped"})
                doc["available"] = avail
                doc["shipped"] = shipped
            out.append(doc)
        out.sort(key=lambda p: (p.get("name") or "").lower())
        return {"items": out, "count": len(out)}

    @router.post("/products")
    async def create_product(body: ProductCreate, current_user=Depends(deps.require_admin)):
        exists = await db.products.find_one({"code": body.code})
        if exists:
            raise HTTPException(409, f"Codice '{body.code}' già in uso")
        doc = {
            "id": str(_uuid.uuid4()),
            "name": body.name,
            "code": body.code,
            "category": body.category,
            "tipo_gestione": body.tipo_gestione,
            "quantity": float(body.quantity or 0) if body.tipo_gestione == "a_quantita" else 0,
            "unit": body.unit or "pz",
            "threshold": int(body.threshold or 0),
            "notes": body.notes,
            "active": body.active if body.active is not None else True,
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        }
        await db.products.insert_one(doc)
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user["_id"]),
            "actor_username": current_user.get("username"),
            "action": "product.create",
            "meta": {"product_id": doc["id"], "code": doc["code"]},
        })
        # F18 — Evento applicativo strutturato
        await event_logger.log_event(
            db, category="INVENTARIO", event_type="CREAZIONE_PRODOTTO",
            action="product.create", level="INFO", status="SUCCESS",
            user=current_user.get("username"), user_role=current_user.get("role"),
            endpoint="POST /api/admin/products",
            product=doc.get("name"), product_code=doc.get("code"),
            quantity_after=doc.get("quantity"),
            message=f"Creato prodotto {doc.get('name')} ({doc.get('code')})",
            details={"product_id": doc["id"], "tipo_gestione": doc.get("tipo_gestione")},
        )
        doc.pop("_id", None)
        return doc

    @router.patch("/products/{product_id}")
    async def update_product(product_id: str, body: ProductUpdate, current_user=Depends(deps.require_admin)):
        updates = {k: v for k, v in body.model_dump(exclude_unset=True).items() if v is not None}
        if not updates:
            raise HTTPException(400, "Nessun campo da aggiornare")
        updates["updated_at"] = _now_iso()
        if "code" in updates:
            other = await db.products.find_one({"code": updates["code"], "id": {"$ne": product_id}})
            if other:
                raise HTTPException(409, f"Codice '{updates['code']}' già in uso")
        prev = await db.products.find_one({"id": product_id})
        r = await db.products.update_one({"id": product_id}, {"$set": updates})
        if r.matched_count == 0:
            raise HTTPException(404, "Prodotto non trovato")
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user["_id"]),
            "actor_username": current_user.get("username"),
            "action": "product.update",
            "meta": {"product_id": product_id, "changes": list(updates.keys())},
        })
        # F18 — event structured: MODIFICA_PRODOTTO / MODIFICA_QUANTITA / MODIFICA_GESTIONE
        try:
            evt_type = "MODIFICA_PRODOTTO"
            q_before = float((prev or {}).get("quantity") or 0)
            q_after = q_before
            q_change = None
            if "quantity" in updates:
                q_after = float(updates.get("quantity") or 0)
                q_change = q_after - q_before
                if q_after == 0 and q_before > 0:
                    evt_type = "AZZERAMENTO_QUANTITA"
                elif q_change > 0:
                    evt_type = "AUMENTO_QUANTITA"
                elif q_change < 0:
                    evt_type = "DIMINUZIONE_QUANTITA"
                else:
                    evt_type = "MODIFICA_QUANTITA"
            elif "tipo_gestione" in updates:
                evt_type = "MODIFICA_TIPO_GESTIONE"
            await event_logger.log_event(
                db, category="INVENTARIO", event_type=evt_type,
                action="product.update", level="INFO", status="SUCCESS",
                user=current_user.get("username"), user_role=current_user.get("role"),
                endpoint=f"PATCH /api/admin/products/{product_id}",
                product=(prev or {}).get("name"), product_code=(prev or {}).get("code"),
                quantity_before=q_before if "quantity" in updates else None,
                quantity_change=q_change,
                quantity_after=q_after if "quantity" in updates else None,
                message=f"Modificato prodotto {(prev or {}).get('name')} — campi: {', '.join(updates.keys())}",
                details={"product_id": product_id, "changes": list(updates.keys())},
            )
        except Exception as _e:
            logger.warning(f"log_event product.update fallito: {_e}")
        doc = await db.products.find_one({"id": product_id})
        doc.pop("_id", None)
        return doc

    @router.delete("/products/{product_id}")
    async def delete_product(product_id: str, current_user=Depends(deps.require_admin)):
        prev = await db.products.find_one({"id": product_id})
        r = await db.products.delete_one({"id": product_id})
        if r.deleted_count == 0:
            raise HTTPException(404, "Prodotto non trovato")
        await db.product_serials.delete_many({"product_id": product_id})
        await event_logger.log_event(
            db, category="INVENTARIO", event_type="ELIMINAZIONE_PRODOTTO",
            action="product.delete", level="WARNING", status="SUCCESS",
            user=current_user.get("username"), user_role=current_user.get("role"),
            endpoint=f"DELETE /api/admin/products/{product_id}",
            product=(prev or {}).get("name"), product_code=(prev or {}).get("code"),
            message=f"Eliminato prodotto {(prev or {}).get('name')} ({(prev or {}).get('code')})",
            details={"product_id": product_id},
        )
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user["_id"]),
            "actor_username": current_user.get("username"),
            "action": "product.delete",
            "meta": {"product_id": product_id},
        })
        return {"ok": True}

    @router.get("/products/{product_id}/serials")
    async def list_product_serials(product_id: str):
        prod = await db.products.find_one({"id": product_id})
        if not prod:
            raise HTTPException(404, "Prodotto non trovato")
        out: List[Dict[str, Any]] = []
        async for row in db.product_serials.find({"product_id": product_id}).sort("created_at", -1):
            row.pop("_id", None)
            out.append(row)
        return {"items": out, "count": len(out)}

    @router.post("/products/{product_id}/serials")
    async def add_product_serial(product_id: str, body: SerialInput, current_user=Depends(deps.require_admin)):
        prod = await db.products.find_one({"id": product_id})
        if not prod:
            raise HTTPException(404, "Prodotto non trovato")
        if prod.get("tipo_gestione") != "a_seriale":
            raise HTTPException(400, "Prodotto non a seriale")
        sn = body.serial.strip()
        exists = await db.product_serials.find_one({"serial_lower": sn.lower(), "product_id": product_id})
        if exists:
            raise HTTPException(409, f"Seriale '{sn}' già registrato")
        await db.product_serials.insert_one({
            "product_id": product_id,
            "serial": sn,
            "serial_lower": sn.lower(),
            "status": "available",
            "created_at": _now_iso(),
            "updated_at": _now_iso(),
        })
        return {"ok": True, "serial": sn}

    @router.delete("/products/{product_id}/serials/{serial}")
    async def delete_product_serial(product_id: str, serial: str, current_user=Depends(deps.require_admin)):
        r = await db.product_serials.delete_one({
            "product_id": product_id,
            "serial_lower": serial.strip().lower(),
        })
        if r.deleted_count == 0:
            raise HTTPException(404, "Seriale non trovato")
        return {"ok": True}

    # ---------- Configurazione Notion essenziale (Gestionale locale) ----------
    class NotionConfigBody(BaseModel):
        model_config = ConfigDict(extra="ignore")
        token: Optional[str] = None
        inventario_ds_id: Optional[str] = None
        receipts_ds_id: Optional[str] = None
        tracker_ds_id: Optional[str] = None
        verona_inventario_ds_id: Optional[str] = None
        verona_receipts_ds_id: Optional[str] = None
        verona_tracker_ds_id: Optional[str] = None
        ordini_ds_id: Optional[str] = None

    async def _apply_saved_notion_config() -> Dict[str, Any]:
        doc = await db.settings.find_one({"_id": "notion_config"}) or {}
        token = secret_store.decrypt_secret(doc.get("token_encrypted") or "") or (notion_service.NOTION_TOKEN or "").strip()
        inventario = (doc.get("inventario_ds_id") or notion_service.NOTION_INVENTARIO_DS_ID or "").strip()
        receipts = (doc.get("receipts_ds_id") or notion_service.NOTION_RECEIPTS_DS_ID or "").strip()
        tracker = (doc.get("tracker_ds_id") or notion_service.NOTION_TRACKER_DS_ID or "").strip()
        ordini = (doc.get("ordini_ds_id") or notion_service.NOTION_ORDINI_DS_ID or "").strip()
        verona_inventario = (doc.get("verona_inventario_ds_id") or "").strip()
        verona_receipts = (doc.get("verona_receipts_ds_id") or "").strip()
        verona_tracker = (doc.get("verona_tracker_ds_id") or "").strip()
        notion_service.configure(
            token=token,
            inventario_ds_id=inventario,
            receipts_ds_id=receipts,
            tracker_ds_id=tracker,
            ordini_ds_id=ordini,
        )
        return {
            "token": token,
            "inventario_ds_id": inventario,
            "receipts_ds_id": receipts,
            "tracker_ds_id": tracker,
            "verona_inventario_ds_id": verona_inventario,
            "verona_receipts_ds_id": verona_receipts,
            "verona_tracker_ds_id": verona_tracker,
            "ordini_ds_id": ordini,
        }

    def _notion_config_public(cfg: Dict[str, Any]) -> Dict[str, Any]:
        tok = cfg.get("token") or ""
        masked = ""
        if tok:
            masked = (tok[:6] + "••••" + tok[-4:]) if len(tok) > 12 else "••••••••"
        return {
            "configured": bool(tok and (cfg.get("inventario_ds_id") or cfg.get("verona_inventario_ds_id") or cfg.get("ordini_ds_id"))),
            "token_configured": bool(tok),
            "token_masked": masked,
            "inventario_ds_id": cfg.get("inventario_ds_id") or "",
            "receipts_ds_id": cfg.get("receipts_ds_id") or "",
            "tracker_ds_id": cfg.get("tracker_ds_id") or "",
            "verona_inventario_ds_id": cfg.get("verona_inventario_ds_id") or "",
            "verona_receipts_ds_id": cfg.get("verona_receipts_ds_id") or "",
            "verona_tracker_ds_id": cfg.get("verona_tracker_ds_id") or "",
            "ordini_ds_id": cfg.get("ordini_ds_id") or "",
        }

    @router.get("/notion/config")
    async def get_notion_config(current_user=Depends(deps.require_admin)):
        return _notion_config_public(await _apply_saved_notion_config())

    @router.post("/notion/test")
    async def test_notion_config(current_user=Depends(deps.require_admin)):
        cfg = await _apply_saved_notion_config()
        if not cfg.get("token"):
            raise HTTPException(400, "Token Notion non configurato")
        import httpx
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                r = await client.get(f"{notion_service.NOTION_BASE}/users/me", headers=notion_service._headers())
            if r.status_code >= 400:
                raise HTTPException(502, f"Notion ha risposto {r.status_code}: verifica il token")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(502, f"Notion non raggiungibile: {e}")
        return {"ok": True, "message": "Connessione Notion funzionante"}

    @router.get("/notion/import-preview")
    async def notion_import_preview(current_user=Depends(deps.require_admin)):
        cfg = await _apply_saved_notion_config()
        if not cfg.get("token"):
            raise HTTPException(400, "Token Notion non configurato")
        counts = {"inventory_count": 0, "orders_count": 0, "receipts_count": 0, "exits_count": 0, "verona_inventory_count": 0, "verona_receipts_count": 0, "verona_exits_count": 0}
        try:
            if notion_service.NOTION_INVENTARIO_DS_ID:
                notion_service.invalidate_inventory_cache()
                counts["inventory_count"] = len(await notion_service.list_inventory(force_refresh=True))
            if notion_service.NOTION_ORDINI_DS_ID:
                counts["orders_count"] = len(await _query_notion_source(notion_service.NOTION_ORDINI_DS_ID))
            if notion_service.NOTION_RECEIPTS_DS_ID:
                counts["receipts_count"] = len(await notion_service.list_receipts_all())
            if notion_service.NOTION_TRACKER_DS_ID:
                counts["exits_count"] = len(await notion_service.list_exits())
            if cfg.get("verona_inventario_ds_id"):
                counts["verona_inventory_count"] = len(await _query_notion_source(cfg["verona_inventario_ds_id"]))
            if cfg.get("verona_receipts_ds_id"):
                counts["verona_receipts_count"] = len(await _query_notion_source(cfg["verona_receipts_ds_id"]))
            if cfg.get("verona_tracker_ds_id"):
                counts["verona_exits_count"] = len(await _query_notion_source(cfg["verona_tracker_ds_id"]))
        except Exception as e:
            raise HTTPException(502, f"Impossibile preparare l'anteprima: {e}")
        previous = await db.settings.find_one({"_id": "notion_migration"}) or {}
        counts["last_import_at"] = previous.get("last_import_at")
        counts["last_result"] = previous.get("last_result")
        return counts

    @router.delete("/notion/config")
    async def delete_notion_config(current_user=Depends(deps.require_admin)):
        await db.settings.delete_one({"_id": "notion_config"})
        notion_service.configure(token="", inventario_ds_id="", receipts_ds_id="", tracker_ds_id="", ordini_ds_id="")
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user.get("_id", "")),
            "actor_username": current_user.get("username"),
            "action": "notion.config.disconnect",
            "meta": {"local_data_preserved": True},
        })
        return {"ok": True, "message": "Notion disconnesso. I dati locali non sono stati modificati."}

    @router.put("/notion/config")
    async def put_notion_config(body: NotionConfigBody, current_user=Depends(deps.require_admin)):
        current = await db.settings.find_one({"_id": "notion_config"}) or {}
        updates: Dict[str, Any] = {}
        # Token vuoto = mantieni quello già salvato. Gli ID invece possono essere aggiornati/azzerati.
        if body.token is not None and body.token.strip():
            updates["token_encrypted"] = secret_store.encrypt_secret(body.token.strip())
        for key in ("inventario_ds_id", "receipts_ds_id", "tracker_ds_id", "verona_inventario_ds_id", "verona_receipts_ds_id", "verona_tracker_ds_id", "ordini_ds_id"):
            value = getattr(body, key)
            if value is not None:
                updates[key] = value.strip()
        if updates:
            await db.settings.update_one({"_id": "notion_config"}, {"$set": updates}, upsert=True)
        cfg = await _apply_saved_notion_config()
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user.get("_id", "")),
            "actor_username": current_user.get("username"),
            "action": "notion.config.update",
            "meta": {"fields": [k for k in updates.keys() if k != "token_encrypted"], "token_updated": "token_encrypted" in updates},
        })
        return _notion_config_public(cfg)

    # ---------- Fonte Inventario: switch + import da Notion (F8/§19-20) ----------
    class SourceSwitch(BaseModel):
        model_config = ConfigDict(extra="ignore")
        source: str = Field(pattern="^gestionale$")
        confirm: bool = False

    @router.post("/inventory/source")
    async def switch_inventory_source(body: SourceSwitch, current_user=Depends(deps.require_admin)):
        """Compatibilità: la fonte operativa del gestionale può essere solo locale (gestionale)."""
        import auth as _auth
        email = (current_user.get("email") or "").strip().lower()
        if email != _auth.MASTER_EMAIL:
            raise HTTPException(403, "Solo l'account master può cambiare la fonte Inventario")
        if not body.confirm:
            raise HTTPException(400, "Conferma esplicita mancante (confirm=true)")
        # Aggiorna solo general.inventory_source, preserva timezone
        doc = await db.settings.find_one({"_id": "app_settings"}) or {}
        gen = doc.get("general") or {}
        gen["inventory_source"] = body.source
        await db.settings.update_one(
            {"_id": "app_settings"},
            {"$set": {"general": gen}},
            upsert=True,
        )
        # Invalida cache Notion se stiamo passando a gestionale (evita risultati stantii)
        try:
            notion_service.invalidate_inventory_cache()
        except Exception:
            pass
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user["_id"]),
            "actor_username": current_user.get("username"),
            "action": "inventory.source.switch",
            "meta": {"source": body.source},
        })
        return {"ok": True, "source": body.source}

    async def _notion_inventory_plan() -> Dict[str, Any]:
        """Prepara un piano di migrazione READ-ONLY dell'Inventario Elios Tech.

        Legge esclusivamente il data source Inventario configurato. Non consulta Verona,
        non crea entrate/uscite su Notion e non richiama nessuna funzione di scrittura.
        """
        if not notion_service.is_configured():
            raise HTTPException(503, "Notion non configurato")
        try:
            notion_service.invalidate_inventory_cache()
            items = await notion_service.list_inventory(force_refresh=True)
        except Exception as e:
            raise HTTPException(502, f"Impossibile leggere l'Inventario Notion: {e}")

        importable: List[Dict[str, Any]] = []
        skipped: List[Dict[str, Any]] = []
        serial_count = 0
        for it in items:
            tipo = it.get("tipo_gestione")
            if tipo not in ("a_seriale", "a_quantita"):
                skipped.append({"name": it.get("name"), "code": it.get("code"), "reason": "Tipo gestione non configurato"})
                continue
            serials = list(dict.fromkeys([str(x).strip() for x in (it.get("serials") or []) if str(x).strip()]))
            serial_count += len(serials)
            importable.append({
                "notion_page_id": it.get("id"),
                "name": it.get("name") or "Senza nome",
                "code": (it.get("code") or "").strip(),
                "category": it.get("category") or "",
                "tipo_gestione": tipo,
                "quantity": float(it.get("quantity") or 0),
                "serials": serials,
                "min_stock": float(it.get("min_stock") or 0),
                "unit_price": it.get("unit_price"),
                "power": it.get("power") or "",
                "cable": it.get("cable") or "",
                "notion_url": it.get("url"),
            })
        return {
            "source_count": len(items),
            "importable": importable,
            "skipped": skipped,
            "serial_count": serial_count,
        }

    @router.get("/inventory/import-from-notion-preview")
    async def import_from_notion_preview(current_user=Depends(deps.require_admin)):
        plan = await _notion_inventory_plan()
        serial_products = sum(1 for x in plan["importable"] if x["tipo_gestione"] == "a_seriale")
        quantity_products = sum(1 for x in plan["importable"] if x["tipo_gestione"] == "a_quantita")
        warnings = []
        for x in plan["importable"]:
            if x["tipo_gestione"] == "a_seriale" and int(round(x["quantity"])) != len(x["serials"]):
                warnings.append({
                    "name": x["name"],
                    "message": f"Notion indica {x['quantity']:g} pz ma sono presenti {len(x['serials'])} seriali. Nel gestionale la disponibilità serializzata sarà basata sui seriali importati.",
                })
        return {
            "ok": True,
            "mode": "read_only_notion_to_elios",
            "notion_is_modified": False,
            "target_warehouse": "elios-tech",
            "source_count": plan["source_count"],
            "importable_count": len(plan["importable"]),
            "skipped_count": len(plan["skipped"]),
            "serial_products": serial_products,
            "quantity_products": quantity_products,
            "serials_count": plan["serial_count"],
            "warnings": warnings[:30],
            "skipped": plan["skipped"][:30],
            "sample": [{k: x.get(k) for k in ("name", "code", "category", "tipo_gestione", "quantity", "min_stock")} for x in plan["importable"][:12]],
        }

    @router.post("/inventory/import-from-notion")
    async def import_from_notion(current_user=Depends(deps.require_admin)):
        """Importa SOLO Inventario Notion -> Magazzino Elios Tech locale.

        Garanzie:
        - nessuna scrittura verso Notion;
        - nessun dato del Magazzino Verona viene letto/modificato;
        - import idempotente tramite notion_source_page_id e, come fallback, codice nel solo deposito Elios Tech;
        - seriali aggiunti senza duplicare quelli già presenti;
        - i prodotti locali non presenti su Notion NON vengono cancellati.
        """
        plan = await _notion_inventory_plan()
        created = 0
        updated = 0
        serials_created = 0
        warnings: List[str] = []
        now = datetime.now(timezone.utc)

        for it in plan["importable"]:
            page_id = str(it.get("notion_page_id") or "").strip()
            code = (it.get("code") or "").strip()
            # Scope tassativo: Magazzino Elios Tech. I record legacy senza warehouse_id
            # sono considerati Elios Tech per compatibilità con le revisioni precedenti.
            existing = None
            if page_id:
                existing = await db.products.find_one({
                    "notion_source_page_id": page_id,
                    "$or": [{"warehouse_id": "elios-tech"}, {"warehouse_id": {"$exists": False}}],
                })
            if not existing and code:
                existing = await db.products.find_one({
                    "$or": [{"warehouse_id": "elios-tech"}, {"warehouse_id": {"$exists": False}}],
                    "code_lower": code.lower(),
                })
                # Compatibilità con prodotti precedenti senza code_lower.
                if not existing:
                    existing = await db.products.find_one({
                        "$or": [{"warehouse_id": "elios-tech"}, {"warehouse_id": {"$exists": False}}],
                        "code": code,
                    })

            pid = existing.get("id") if existing else str(_uuid.uuid4())
            payload = {
                "name": it.get("name") or code or "Senza nome",
                "code": code,
                "code_lower": code.lower(),
                "category": it.get("category") or "",
                "tipo_gestione": it.get("tipo_gestione"),
                "unit": "pz",
                "warehouse_id": "elios-tech",
                "active": True,
                "low_stock_threshold": float(it.get("min_stock") or 0),
                "threshold": float(it.get("min_stock") or 0),
                "notion_source_page_id": page_id,
                "notion_source_url": it.get("notion_url"),
                "notion_unit_price": it.get("unit_price"),
                "notion_power": it.get("power") or "",
                "notion_cable": it.get("cable") or "",
                "unit_price": it.get("unit_price"),
                "power": it.get("power") or "",
                "cable": it.get("cable") or "",
                "notion_imported_at": now,
                "updated_at": now,
            }
            if existing:
                await db.products.update_one({"id": pid}, {"$set": payload})
                updated += 1
            else:
                payload.update({"id": pid, "quantity": 0, "created_at": now, "created_by": current_user.get("username")})
                await db.products.insert_one(payload)
                created += 1

            tipo = it.get("tipo_gestione")
            if tipo == "a_quantita":
                qty = max(0.0, float(it.get("quantity") or 0))
                await db.warehouse_stock.update_one(
                    {"product_id": pid, "warehouse_id": "elios-tech"},
                    {"$set": {"quantity": qty, "low_stock_threshold": float(it.get("min_stock") or 0), "updated_at": now}, "$setOnInsert": {"created_at": now, "location": ""}},
                    upsert=True,
                )
                await db.products.update_one({"id": pid}, {"$set": {"quantity": qty}})
            else:
                await db.warehouse_stock.update_one(
                    {"product_id": pid, "warehouse_id": "elios-tech"},
                    {"$set": {"quantity": 0, "low_stock_threshold": float(it.get("min_stock") or 0), "updated_at": now}, "$setOnInsert": {"created_at": now, "location": ""}},
                    upsert=True,
                )
                for sn in it.get("serials") or []:
                    dup = await db.product_serials.find_one({"serial_lower": sn.lower()})
                    if dup:
                        # Non spostare seriali già gestiti localmente.
                        if dup.get("product_id") != pid:
                            warnings.append(f"Seriale {sn} già presente su un altro prodotto locale")
                        continue
                    await db.product_serials.insert_one({
                        "id": str(_uuid.uuid4()),
                        "product_id": pid,
                        "serial": sn,
                        "serial_lower": sn.lower(),
                        "status": "available",
                        "warehouse_id": "elios-tech",
                        "source": "notion_initial_import",
                        "created_at": now,
                        "updated_at": now,
                    })
                    serials_created += 1

        result = {
            "ok": True,
            "mode": "read_only_notion_to_elios",
            "notion_modified": False,
            "warehouse": "elios-tech",
            "source_count": plan["source_count"],
            "created": created,
            "updated": updated,
            "serials_created": serials_created,
            "skipped": len(plan["skipped"]),
            "warnings": warnings[:50],
        }
        await db.settings.update_one(
            {"_id": "notion_migration"},
            {"$set": {"last_import_at": now, "last_result": result}},
            upsert=True,
        )
        await db.audit_logs.insert_one({
            "at": now,
            "actor_id": str(current_user["_id"]),
            "actor_username": current_user.get("username"),
            "action": "inventory.import.notion.readonly",
            "meta": result,
        })
        return result

    # ---------- Importazione completa da Notion ----------
    def _notion_value(props: Dict[str, Any], *names: str) -> Any:
        prop = notion_service._get_prop(props, *names)
        if not prop:
            return None
        t = prop.get("type")
        if t in ("title", "rich_text"):
            return notion_service._plain_text(prop).strip()
        if t in ("email", "phone_number", "url", "number", "checkbox"):
            return prop.get(t)
        if t in ("select", "status"):
            obj = prop.get(t) or {}
            return obj.get("name")
        if t == "date":
            obj = prop.get("date") or {}
            return obj.get("start")
        if t == "multi_select":
            return ", ".join(x.get("name", "") for x in (prop.get("multi_select") or []) if x.get("name"))
        if t == "formula":
            obj = prop.get("formula") or {}
            return obj.get(obj.get("type"))
        return None

    async def _query_notion_source(ds_id: str) -> List[Dict[str, Any]]:
        if not notion_service.NOTION_TOKEN or not ds_id:
            return []
        import httpx
        url = f"{notion_service.NOTION_BASE}/data_sources/{ds_id}/query"
        body: Dict[str, Any] = {"page_size": 100}
        out: List[Dict[str, Any]] = []
        async with httpx.AsyncClient(timeout=30) as client:
            while True:
                r = await client.post(url, headers=notion_service._headers(), json=body)
                if r.status_code >= 400:
                    raise HTTPException(502, f"Errore Notion ({r.status_code}): {r.text[:200]}")
                data = r.json()
                out.extend(data.get("results", []))
                if not data.get("has_more"):
                    break
                body["start_cursor"] = data.get("next_cursor")
        return out

    @router.post("/notion/import-all")
    async def import_all_from_notion(current_user=Depends(deps.require_admin)):
        """Importa nel gestionale locale tutto ciò che è ricostruibile dalle fonti Notion configurate.

        - Inventario: prodotti, quantità e seriali disponibili.
        - Ordini: crea/aggiorna clienti, eventuali contatti/sedi e ordini cliente usando i campi presenti.
        - Entrate/Uscite: importa lo storico movimenti senza alterare le giacenze già importate.
        Notion è sempre read-only in questa operazione.
        """
        await _apply_saved_notion_config()
        if not notion_service.NOTION_TOKEN:
            raise HTTPException(503, "Token Notion non configurato")

        # 1) Inventario locale
        inv_created = inv_updated = 0
        notion_to_local: Dict[str, str] = {}
        if notion_service.NOTION_INVENTARIO_DS_ID:
            try:
                notion_service.invalidate_inventory_cache()
                items = await notion_service.list_inventory(force_refresh=True)
            except Exception as e:
                raise HTTPException(502, f"Impossibile leggere Inventario Notion: {e}")
            for it in items:
                code = (it.get("code") or "").strip()
                if not code:
                    continue
                tipo = it.get("tipo_gestione") if it.get("tipo_gestione") in ("a_seriale", "a_quantita") else "a_quantita"
                existing = await db.products.find_one({"$or": [{"notion_page_id": it.get("id")}, {"code": code}]})
                payload = {
                    "name": it.get("name") or code,
                    "code": code,
                    "category": it.get("category"),
                    "tipo_gestione": tipo,
                    "unit": it.get("unit") or "pz",
                    "notion_page_id": it.get("id"),
                    "active": True,
                    "updated_at": _now_iso(),
                }
                if tipo == "a_quantita":
                    payload["quantity"] = float(it.get("quantity") or 0)
                elif existing:
                    payload["quantity"] = existing.get("quantity", 0)
                else:
                    payload["quantity"] = 0
                if existing:
                    local_id = existing["id"]
                    await db.products.update_one({"id": local_id}, {"$set": payload})
                    inv_updated += 1
                else:
                    local_id = str(_uuid.uuid4())
                    payload.update({"id": local_id, "created_at": _now_iso(), "threshold": 0})
                    await db.products.insert_one(payload)
                    inv_created += 1
                notion_to_local[str(it.get("id"))] = local_id

                if tipo == "a_seriale":
                    available = {str(x).strip() for x in (it.get("serials") or []) if str(x).strip()}
                    for sn in available:
                        await db.product_serials.update_one(
                            {"product_id": local_id, "serial_lower": sn.lower()},
                            {"$set": {
                                "product_id": local_id,
                                "serial": sn,
                                "serial_lower": sn.lower(),
                                "status": "available",
                                "updated_at": _now_iso(),
                            }, "$setOnInsert": {"created_at": _now_iso()}},
                            upsert=True,
                        )
                    await db.products.update_one({"id": local_id}, {"$set": {"quantity": len(available)}})

        # 2) Clienti / contatti / sedi / ordini ricavati da Eliostech Ordini
        clients_created = clients_updated = sites_created = contacts_created = 0
        orders_created = orders_updated = 0
        documents_imported = documents_skipped = document_errors = 0
        if notion_service.NOTION_ORDINI_DS_ID:
            pages = await _query_notion_source(notion_service.NOTION_ORDINI_DS_ID)
            existing_clients = await db.crm_clienti.find({}).to_list(length=10000)
            client_map = {
                str(x.get("ragione_sociale") or "").strip().casefold(): x
                for x in existing_clients if str(x.get("ragione_sociale") or "").strip()
            }
            for page in pages:
                props = page.get("properties", {})
                # Il titolo Notion è "Modulo Ordine/Struttura": lo conserviamo sempre e
                # lo usiamo come fallback se manca la ragione sociale.
                title = ""
                for prop in props.values():
                    if prop.get("type") == "title":
                        title = notion_service._plain_text(prop).strip()
                        if title:
                            break
                company = (_notion_value(
                    props,
                    notion_service.NOTION_ORDINE_STRUCTURE_FIELD,
                    "Ragione sociale", "Cliente", "Azienda", "Nome cliente", "Struttura"
                ) or title or "").strip()
                if not company:
                    continue
                key = company.casefold()
                client = client_map.get(key)
                # Tutti i campi operativi presenti in Eliostech Ordini.
                codes_val = _notion_value(props, "Codice prodotto") or ""
                codes = [x.strip() for x in str(codes_val).split(",") if x.strip()]
                sn_raw = _notion_value(props, "SN WB") or ""
                qr_raw = _notion_value(props, "CODICI QR") or ""
                serials = notion_service._parse_serials(str(sn_raw))
                qrs = notion_service._parse_serials(str(qr_raw))
                client_payload = {
                    "tipo": "Azienda",
                    "ragione_sociale": company,
                    "nome_struttura": title or company,
                    "partita_iva": _notion_value(props, "Partita IVA", "P. IVA", "PIVA") or "",
                    "codice_fiscale": _notion_value(props, "Codice fiscale", "CF") or "",
                    "sdi": _notion_value(props, "SDI", "Codice SDI") or "",
                    "pec": _notion_value(props, "PEC") or "",
                    "referente": _notion_value(props, "Referente") or "",
                    "telefono": _notion_value(props, "Telefono", "Phone") or "",
                    "email": _notion_value(props, "Email", "E-mail") or "",
                    "indirizzo": _notion_value(props, "Indirizzo") or "",
                    "comune": _notion_value(props, "Comune") or "",
                    "provincia": _notion_value(props, "Provincia") or "",
                    "agente": _notion_value(props, "Agente") or "",
                    "provenienza_cliente": _notion_value(props, "Provenienza Cliente") or "",
                    "stato_cliente": _notion_value(props, "Stato Cliente") or "",
                    "data_firma": _notion_value(props, "Data firma") or "",
                    "pagamento": _notion_value(props, "Pagamento") or "",
                    "capitale": _notion_value(props, "Capitale (€)"),
                    "codici_prodotto": codes,
                    "qty_wb": _notion_value(props, "QTY WB") or len(serials),
                    "sn_wb": serials,
                    "qr_codes": qrs,
                    "installatore_notion": _notion_value(props, "Installatore") or "",
                    "id_wallbox": _notion_value(props, "ID WB") or "",
                    "password_wallbox": _notion_value(props, "PSW") or "",
                    "assistenza_smart": bool(_notion_value(props, "Assistenza SMART")),
                    "backend_elios_tech": bool(_notion_value(props, "Backend Elios Tech")),
                    "scadenza_backend": _notion_value(props, "Scadenza Backend") or "",
                    "electromaps": bool(_notion_value(props, "Electromaps")),
                    "eviaggio": bool(_notion_value(props, "Eviaggio")),
                    "nextcharge": bool(_notion_value(props, "Nextcharge")),
                    "plugshare": bool(_notion_value(props, "Plugshare")),
                    "recensione_google": bool(_notion_value(props, "Recensione Google")),
                    "numero_caso_wallbox": _notion_value(props, "Numero Caso WB") or "",
                    "notion_last_page_id": page.get("id"),
                    "notion_url": page.get("url"),
                    "updated_at": datetime.now(timezone.utc),
                    "import_source": "notion",
                }
                if client:
                    # Un cliente può avere più righe/ordini Notion: non perdiamo prodotti,
                    # seriali, QR o riferimenti importati nelle righe precedenti.
                    for list_key in ("codici_prodotto", "sn_wb", "qr_codes"):
                        merged = []
                        seen = set()
                        for value in list(client.get(list_key) or []) + list(client_payload.get(list_key) or []):
                            sv = str(value).strip()
                            if sv and sv.casefold() not in seen:
                                seen.add(sv.casefold()); merged.append(sv)
                        client_payload[list_key] = merged
                    ids = [str(x) for x in (client.get("notion_source_ids") or []) if x]
                    if page.get("id") and str(page.get("id")) not in ids:
                        ids.append(str(page.get("id")))
                    client_payload["notion_source_ids"] = ids
                    # I servizi cliente non vengono disattivati da una seconda riga Notion vuota/no.
                    for flag in ("assistenza_smart", "backend_elios_tech", "electromaps", "eviaggio", "nextcharge", "plugshare", "recensione_google"):
                        client_payload[flag] = bool(client.get(flag)) or bool(client_payload.get(flag))
                    await db.crm_clienti.update_one({"id": client["id"]}, {"$set": {k: v for k, v in client_payload.items() if v not in (None, "")}})
                    client_id = client["id"]
                    client.update(client_payload)
                    clients_updated += 1
                else:
                    client_id = str(_uuid.uuid4())
                    client_payload.update({
                        "id": client_id,
                        "notion_source_ids": [str(page.get("id"))] if page.get("id") else [],
                        "created_at": datetime.now(timezone.utc),
                        "created_by": current_user.get("username"),
                    })
                    await db.crm_clienti.insert_one(client_payload)
                    client = client_payload
                    client_map[key] = client
                    clients_created += 1

                # Referente, se i campi esistono.
                referente = (_notion_value(props, "Referente", "Contatto", "Nome referente") or "").strip()
                contact_id = None
                if referente:
                    parts = referente.split(None, 1)
                    nome = parts[0]
                    cognome = parts[1] if len(parts) > 1 else "-"
                    existing_contact = await db.crm_contatti.find_one({
                        "cliente_id": client_id,
                        "nome": {"$regex": f"^{re.escape(nome)}$", "$options": "i"},
                        "cognome": {"$regex": f"^{re.escape(cognome)}$", "$options": "i"},
                    })
                    if existing_contact:
                        contact_id = existing_contact["id"]
                    else:
                        contact_id = str(_uuid.uuid4())
                        await db.crm_contatti.insert_one({
                            "id": contact_id,
                            "cliente_id": client_id,
                            "nome": nome,
                            "cognome": cognome,
                            "telefono": _notion_value(props, "Telefono referente", "Cellulare referente") or "",
                            "email": _notion_value(props, "Email referente") or "",
                            "principale": "Sì",
                            "created_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                            "created_by": current_user.get("username"),
                            "import_source": "notion",
                        })
                        contacts_created += 1

                address = (_notion_value(props, "Indirizzo installazione", "Indirizzo", "Via", "Sede installazione") or "").strip()
                comune = (_notion_value(props, "Comune", "Città", "Citta") or "").strip()
                site_id = None
                if address or comune:
                    site_query = {"cliente_id": client_id}
                    if address:
                        site_query["indirizzo"] = {"$regex": f"^{re.escape(address)}$", "$options": "i"}
                    elif comune:
                        site_query["comune"] = {"$regex": f"^{re.escape(comune)}$", "$options": "i"}
                    existing_site = await db.crm_sedi.find_one(site_query)
                    if existing_site:
                        site_id = existing_site["id"]
                    else:
                        site_id = str(_uuid.uuid4())
                        await db.crm_sedi.insert_one({
                            "id": site_id,
                            "cliente_id": client_id,
                            "contatto_id": contact_id,
                            "nome": _notion_value(props, "Nome sede", "Sede") or "Sede installazione",
                            "tipo": "Installazione",
                            "indirizzo": address or "Da completare",
                            "civico": _notion_value(props, "Civico") or "",
                            "cap": _notion_value(props, "CAP") or "",
                            "comune": comune or "Da completare",
                            "provincia": _notion_value(props, "Provincia", "Prov.") or "",
                            "telefono": _notion_value(props, "Telefono sede") or "",
                            "created_at": datetime.now(timezone.utc),
                            "updated_at": datetime.now(timezone.utc),
                            "created_by": current_user.get("username"),
                            "import_source": "notion",
                        })
                        sites_created += 1

                order_number = (_notion_value(props, "Numero ordine", "N. ordine", "Ordine") or title or str(page.get("id", ""))[:8]).strip()
                order_date = _notion_value(props, "Data ordine", "Data", "Date", "Data firma") or ""
                order_status = _notion_value(props, "Stato", "Status", "Stato Cliente") or "Ricevuto"
                existing_order = await db.crm_ordini_clienti.find_one({"notion_page_id": page.get("id")})
                order_payload = {
                    "numero": order_number,
                    "cliente_id": client_id,
                    "sede_id": site_id,
                    "data": order_date,
                    "stato": order_status if order_status in ("Ricevuto", "Confermato", "In lavorazione", "Completato", "Annullato") else "Ricevuto",
                    "stato_notion": order_status,
                    "modalita_pagamento": _notion_value(props, "Pagamento") or "",
                    "importo": _notion_value(props, "Capitale (€)"),
                    "data_firma": _notion_value(props, "Data firma") or "",
                    "prodotti_notion": codes,
                    "qty_wb": _notion_value(props, "QTY WB") or len(serials),
                    "sn_wb": serials,
                    "qr_codes": qrs,
                    "installatore_notion": _notion_value(props, "Installatore") or "",
                    "notion_page_id": page.get("id"),
                    "notion_url": page.get("url"),
                    "updated_at": datetime.now(timezone.utc),
                    "import_source": "notion",
                }
                if existing_order:
                    await db.crm_ordini_clienti.update_one({"id": existing_order["id"]}, {"$set": order_payload})
                    orders_updated += 1
                else:
                    order_payload.update({
                        "id": str(_uuid.uuid4()),
                        "created_at": datetime.now(timezone.utc),
                        "created_by": current_user.get("username"),
                    })
                    await db.crm_ordini_clienti.insert_one(order_payload)
                    orders_created += 1

                # Copia locale degli allegati Notion. I link firmati Notion sono temporanei,
                # quindi scarichiamo i file durante la migrazione e li registriamo nel documentale.
                file_categories = [
                    ("Contratto", "Contratto"),
                    ("Fattura", "Fattura"),
                    ("Report installazione", "Report installazione"),
                    ("Report Fotografico", "Report fotografico"),
                ]
                try:
                    from pathlib import Path as _Path
                    import mimetypes as _mimetypes
                    import httpx as _httpx
                    upload_root = _Path(__file__).resolve().parent.parent / "uploads" / "clienti" / client_id
                    upload_root.mkdir(parents=True, exist_ok=True)
                    async with _httpx.AsyncClient(timeout=60, follow_redirects=True) as _file_client:
                        for prop_name, category in file_categories:
                            prop = notion_service._get_prop(props, prop_name)
                            if not prop or prop.get("type") != "files":
                                continue
                            for f in prop.get("files") or []:
                                src = None
                                if f.get("type") == "file":
                                    src = (f.get("file") or {}).get("url")
                                elif f.get("type") == "external":
                                    src = (f.get("external") or {}).get("url")
                                filename = (f.get("name") or f"{category}.bin").strip()
                                safe = re.sub(r"[^A-Za-z0-9._() -]+", "_", filename).strip(" .")[:180] or "documento"
                                existing_doc = await db.documents.find_one({
                                    "resource": "clienti", "record_id": client_id,
                                    "notion_page_id": page.get("id"), "notion_filename": filename,
                                })
                                if existing_doc:
                                    documents_skipped += 1
                                    continue
                                if not src:
                                    document_errors += 1
                                    continue
                                rr = await _file_client.get(src)
                                if rr.status_code >= 400 or len(rr.content) > 25 * 1024 * 1024:
                                    document_errors += 1
                                    continue
                                doc_id = str(_uuid.uuid4())
                                ext = _Path(safe).suffix[:12]
                                stored = upload_root / f"{doc_id}{ext}"
                                stored.write_bytes(rr.content)
                                await db.documents.insert_one({
                                    "id": doc_id, "resource": "clienti", "record_id": client_id,
                                    "filename": safe, "stored_path": str(stored),
                                    "content_type": rr.headers.get("content-type") or _mimetypes.guess_type(safe)[0] or "application/octet-stream",
                                    "size": len(rr.content), "category": category,
                                    "note": "Importato da Notion", "created_at": datetime.now(timezone.utc),
                                    "created_by": current_user.get("username"), "import_source": "notion",
                                    "notion_page_id": page.get("id"), "notion_filename": filename,
                                })
                                documents_imported += 1
                except Exception as exc:
                    logger.warning("Import allegati Notion fallito per %s: %s", company, exc)
                    document_errors += 1

        # 3) Storico entrate/uscite: inserimento idempotente, senza modificare le quantità.
        receipts_imported = exits_imported = 0
        if notion_service.NOTION_RECEIPTS_DS_ID:
            try:
                for row in await notion_service.list_receipts_all():
                    rid = f"notion:{row.get('id')}"
                    if await db.local_receipts.find_one({"id": rid}):
                        continue
                    notion_pid = (row.get("item_ids") or [None])[0]
                    local_pid = notion_to_local.get(str(notion_pid))
                    await db.local_receipts.insert_one({
                        "id": rid,
                        "product_id": local_pid,
                        "product_name": row.get("item_name") or row.get("sn") or "Movimento Notion",
                        "sn": row.get("sn") or "",
                        "quantity": row.get("quantity") or 0,
                        "data_consegna": row.get("date") or "",
                        "unit": row.get("unit") or "pz",
                        "created_at": row.get("created_time") or _now_iso(),
                        "import_source": "notion",
                    })
                    receipts_imported += 1
            except Exception as e:
                logger.warning("Import storico entrate Notion fallito: %s", e)

        if notion_service.NOTION_TRACKER_DS_ID:
            try:
                for row in await notion_service.list_exits():
                    pid = f"notion:{row.get('id')}"
                    if await db.local_picks.find_one({"id": pid}):
                        continue
                    notion_pid = (row.get("item_ids") or [None])[0]
                    local_pid = notion_to_local.get(str(notion_pid))
                    await db.local_picks.insert_one({
                        "id": pid,
                        "product_id": local_pid,
                        "product_name": row.get("item_name") or row.get("sn") or "Movimento Notion",
                        "sn": row.get("sn") or "",
                        "quantity": row.get("quantity") or 0,
                        "cliente": row.get("cliente") or "",
                        "taken_by": row.get("taken_by") or "",
                        "data_uscita": row.get("date") or "",
                        "unit": row.get("unit") or "pz",
                        "created_at": row.get("created_time") or _now_iso(),
                        "import_source": "notion",
                    })
                    exits_imported += 1
            except Exception as e:
                logger.warning("Import storico uscite Notion fallito: %s", e)

        result = {
            "ok": True,
            "inventory": {"created": inv_created, "updated": inv_updated},
            "crm": {
                "clients_created": clients_created,
                "clients_updated": clients_updated,
                "contacts_created": contacts_created,
                "sites_created": sites_created,
                "orders_created": orders_created,
                "orders_updated": orders_updated,
                "documents_imported": documents_imported,
                "documents_skipped": documents_skipped,
                "document_errors": document_errors,
            },
            "movements": {"receipts_imported": receipts_imported, "exits_imported": exits_imported},
        }
        await db.settings.update_one(
            {"_id": "notion_migration"},
            {"$set": {"last_import_at": datetime.now(timezone.utc), "last_result": result}},
            upsert=True,
        )
        # Il gestionale resta sempre la fonte operativa dopo la migrazione.
        app_doc = await db.settings.find_one({"_id": "app_settings"}) or {}
        general = _merge_section(DEFAULT_SETTINGS["general"], app_doc.get("general"))
        general["inventory_source"] = "gestionale"
        await db.settings.update_one({"_id": "app_settings"}, {"$set": {"general": general}}, upsert=True)
        await db.audit_logs.insert_one({
            "at": datetime.now(timezone.utc),
            "actor_id": str(current_user.get("_id", "")),
            "actor_username": current_user.get("username"),
            "action": "notion.import.all",
            "meta": result,
        })
        return result

    # ─────────────────────────────────────────────────────────────────
    # F17 (26/02) — Export CSV storico Arrivi/Spedizioni
    # ─────────────────────────────────────────────────────────────────
    @router.get("/export/movimenti")
    async def export_movimenti(
        tipo: str = Query("all", pattern="^(all|arrivo|spedizione)$"),
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        current_user: Dict[str, Any] = Depends(deps.require_admin),
    ):
        """Esporta CSV dei movimenti Arrivi/Spedizioni.
        Filtri: tipo (all|arrivo|spedizione), date_from, date_to (YYYY-MM-DD).
        Sorgente: storico locale del Gestionale Elios Tech. Nessuna modifica dati."""
        from fastapi.responses import Response as _Resp
        import csv as _csv
        import io as _io
        from inventory_router import get_svc as _get_svc
        svc = await _get_svc(db)
        if not svc.is_configured():
            raise HTTPException(503, "Fonte inventario non configurata")
        rows: List[Dict[str, Any]] = []
        try:
            if tipo in ("all", "arrivo"):
                entrate = await svc.list_receipts_all(date_from=date_from, date_to=date_to)
                for r in entrate:
                    rows.append({
                        "tipo": "arrivo",
                        "data": r.get("date") or "",
                        "prodotto": r.get("item_name") or "",
                        "quantita": r.get("quantity") if r.get("quantity") is not None else "",
                        "unita": r.get("unit") or "",
                        "seriale": r.get("sn") or "",
                        "cliente": "",
                        "operatore": "",
                    })
            if tipo in ("all", "spedizione"):
                uscite = await svc.list_exits(date_from=date_from, date_to=date_to)
                for u in uscite:
                    rows.append({
                        "tipo": "spedizione",
                        "data": u.get("date") or "",
                        "prodotto": u.get("item_name") or "",
                        "quantita": u.get("quantity") if u.get("quantity") is not None else "",
                        "unita": u.get("unit") or "",
                        "seriale": u.get("sn") or "",
                        "cliente": u.get("cliente") or "",
                        "operatore": u.get("taken_by") or "",
                    })
        except Exception as e:
            raise HTTPException(502, f"Errore lettura movimenti: {e}")
        rows.sort(key=lambda x: (x.get("data") or ""), reverse=True)
        buf = _io.StringIO()
        w = _csv.writer(buf, delimiter=";", quoting=_csv.QUOTE_MINIMAL)
        w.writerow(["Tipo", "Data", "Prodotto", "Quantità", "Unità", "Seriale/SN", "Cliente", "Operatore"])
        for r in rows:
            w.writerow([r["tipo"], r["data"], r["prodotto"], r["quantita"], r["unita"], r["seriale"], r["cliente"], r["operatore"]])
        csv_bytes = ("\ufeff" + buf.getvalue()).encode("utf-8")
        # Audit non-blocking
        try:
            await db.audit_logs.insert_one({
                "at": datetime.now(timezone.utc).isoformat(),
                "actor_id": str(current_user.get("_id")),
                "actor_username": current_user.get("username"),
                "action": "export.movimenti",
                "meta": {"tipo": tipo, "date_from": date_from, "date_to": date_to, "count": len(rows)},
            })
        except Exception:
            pass
        fname = f"movimenti_{tipo}_{date_from or 'inizio'}_{date_to or 'oggi'}.csv"
        return _Resp(
            content=csv_bytes,
            media_type="text/csv; charset=utf-8",
            headers={"Content-Disposition": f'attachment; filename="{fname}"'},
        )

    return router
