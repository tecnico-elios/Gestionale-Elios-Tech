"""Authentication, sessions and granular permissions for Gestionale Elios Tech."""
from __future__ import annotations

import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import bcrypt
import jwt
from bson import ObjectId
from fastapi import Depends, Header, HTTPException, Request

logger = logging.getLogger(__name__)

PERMISSION_ACTIONS = ["view", "create", "edit", "delete", "export"]
PERMISSION_MODULES = [
    "dashboard", "calendar", "clienti", "contatti", "sedi", "sopralluoghi",
    "preventivi", "ordini_clienti", "commesse", "installazioni", "assistenza",
    "inventario", "arrivi", "spedizioni", "movimenti", "anomalie",
    "ai", "impostazioni", "utenti", "importazione_dati",
]
LEGACY_PERMISSIONS = {"gestione_commesse", "modifica_retroattiva"}
SPECIAL_PERMISSIONS = {"installazioni:view_all"}

ROLE_ADMIN = "admin"
ROLE_RESPONSABILE = "responsabile"
ROLE_OPERATOR = "operator"
ROLE_TECNICO = "tecnico"
# Conservato solo per leggere eventuali account storici. Non è più assegnabile.
ROLE_COMMERCIALE = "commerciale"
VALID_ROLES = {ROLE_ADMIN, ROLE_RESPONSABILE, ROLE_OPERATOR, ROLE_TECNICO}

JWT_ALGORITHM = "HS256"
MASTER_EMAIL = "tecnico@eliostech.org"


def _perms(modules, actions=("view", "create", "edit", "delete", "export")):
    return {f"{m}:{a}" for m in modules for a in actions}


def default_permissions_for_role(role: str):
    if role == ROLE_ADMIN:
        return _perms(PERMISSION_MODULES) | LEGACY_PERMISSIONS
    if role == ROLE_OPERATOR:
        base = _perms(["inventario", "arrivi", "spedizioni"], ("view", "create", "edit"))
        base |= _perms(["calendar"], ("view",))
        base |= _perms(["commesse"], ("view", "edit"))
        return base | {"gestione_commesse"}
    if role == ROLE_TECNICO:
        return _perms(["dashboard", "calendar"], ("view",)) | _perms(["installazioni"], ("view", "edit", "export"))
    if role == ROLE_RESPONSABILE:
        mods = [
            "dashboard", "calendar", "clienti", "contatti", "sedi", "sopralluoghi",
            "preventivi", "ordini_clienti", "commesse", "installazioni", "assistenza",
            "inventario", "arrivi", "spedizioni", "movimenti", "anomalie", "ai",
        ]
        return _perms(mods) | {"gestione_commesse", "modifica_retroattiva", "installazioni:view_all"}
    if role == ROLE_COMMERCIALE:
        # Compatibilità per account creati prima della rimozione dell'area Commerciale.
        # Nessun accesso Lead; l'account mantiene solo funzioni amministrative essenziali.
        return _perms(["ordini_clienti"], ("view", "create", "edit", "export")) | _perms(["commesse", "calendar"], ("view", "export"))
    return set()


def is_master_user(user_doc) -> bool:
    if not user_doc:
        return False
    return str(user_doc.get("email") or "").strip().lower() == MASTER_EMAIL


def effective_permissions(user_doc):
    if not user_doc:
        return set()
    role = user_doc.get("role")
    if role == ROLE_ADMIN or is_master_user(user_doc):
        return default_permissions_for_role(ROLE_ADMIN)
    if user_doc.get("permissions_customized"):
        # Rimuove eventuali vecchi permessi Lead senza alterare gli altri permessi personalizzati.
        return {p for p in (user_doc.get("permissions") or []) if p != "lead" and not str(p).startswith("lead:")}
    return default_permissions_for_role(role)


def has_permission(user_doc, module: str, action: str = "view") -> bool:
    if not user_doc:
        return False
    if user_doc.get("role") == ROLE_ADMIN or is_master_user(user_doc):
        return True
    perms = effective_permissions(user_doc)
    if module in LEGACY_PERMISSIONS:
        return module in perms
    if module not in PERMISSION_MODULES:
        return False
    return module in perms or f"{module}:{action}" in perms


def _request_module_action(request: Request):
    path = request.url.path or ""
    method = request.method.upper()
    if not path.startswith("/api/"):
        return None, None
    if path.startswith("/api/auth/") or path == "/api/time":
        return None, None
    if path.startswith("/api/admin/"):
        return None, None

    module = None
    if path.startswith("/api/crm/"):
        tail = path[len("/api/crm/"):].split("/", 1)[0]
        module = {
            # Le vecchie API Lead restano archivistiche ma non sono più esposte come modulo operativo.
            "lead": "lead_removed",
            "clienti": "ordini_clienti", "contatti": "ordini_clienti", "sedi": "ordini_clienti",
            "sopralluoghi": "sopralluoghi", "preventivi": "preventivi", "ordini-clienti": "ordini_clienti",
            "installazioni": "installazioni", "assistenza": "assistenza",
        }.get(tail)
        if tail == "meta": module = "dashboard"
        elif tail == "lookups": module = "commesse"
    elif path.startswith("/api/commesse"): module = "commesse"
    elif path.startswith("/api/inventory"): module = "inventario"
    elif path.startswith("/api/arrivi"): module = "arrivi"
    elif path.startswith("/api/checklist"): module = "spedizioni"
    elif path.startswith("/api/movimenti") or path.startswith("/api/warehouse"): module = "movimenti"
    elif path.startswith("/api/anomalie"): module = "anomalie"
    elif path.startswith("/api/dashboard"): module = "dashboard"
    elif path.startswith("/api/calendar"): module = "calendar"
    elif path.startswith("/api/ai"): module = "ai"
    elif path.startswith("/api/files"): module = None

    if not module:
        return None, None
    if method == "GET": action = "view"
    elif method == "DELETE": action = "delete"
    elif method in {"PUT", "PATCH"}: action = "edit"
    elif module == "commesse" and path.count("/") > 3: action = "edit"
    else: action = "create"
    return module, action


def _jwt_secret() -> str:
    secret = os.environ.get("JWT_SECRET")
    if not secret:
        raise RuntimeError("JWT_SECRET missing in environment")
    return secret


def _access_ttl_minutes() -> int:
    try: return int(os.environ.get("JWT_ACCESS_TTL_MINUTES", "480"))
    except ValueError: return 480


def _remember_ttl_minutes() -> int:
    try: return int(os.environ.get("JWT_REMEMBER_TTL_MINUTES", str(60 * 24 * 30)))
    except ValueError: return 60 * 24 * 30


def hash_password(password: str) -> str:
    if not password or len(password) < 6:
        raise ValueError("La password deve avere almeno 6 caratteri")
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed: return False
    try: return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError): return False


def create_access_token(user_id: str, username: str, role: str, password_version: int, remember: bool = False, sid: Optional[str] = None) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": user_id, "username": username, "role": role, "pwv": password_version,
        "rem": bool(remember), "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=_remember_ttl_minutes() if remember else _access_ttl_minutes()),
        "type": "access",
    }
    if sid: payload["sid"] = sid
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    try: return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError: raise HTTPException(401, "Token scaduto")
    except jwt.InvalidTokenError: raise HTTPException(401, "Token non valido")


def public_user(doc: Dict[str, Any]) -> Dict[str, Any]:
    if not doc: return {}
    return {
        "id": str(doc.get("_id")), "username": doc.get("username"), "first_name": doc.get("first_name"),
        "last_name": doc.get("last_name"), "full_name": f"{doc.get('first_name') or ''} {doc.get('last_name') or ''}".strip() or doc.get("username"),
        "email": doc.get("email"), "role": doc.get("role"), "active": bool(doc.get("active", True)),
        "must_change_password": bool(doc.get("must_change_password", False)), "last_login": doc.get("last_login"),
        "created_at": doc.get("created_at"), "permissions": [p for p in (doc.get("permissions") or []) if p != "lead" and not str(p).startswith("lead:")],
        "permissions_customized": bool(doc.get("permissions_customized", False)), "effective_permissions": sorted(effective_permissions(doc)),
    }


async def create_session(db, user_id: str, username: str) -> str:
    sid = uuid.uuid4().hex; now = datetime.now(timezone.utc)
    await db.active_sessions.insert_one({"sid": sid, "user_id": user_id, "username": username, "created_at": now, "last_login": now, "last_activity": now})
    return sid


async def touch_session(db, sid: str) -> None:
    if not sid: return
    try: await db.active_sessions.update_one({"sid": sid}, {"$set": {"last_activity": datetime.now(timezone.utc)}})
    except Exception as e: logger.warning("touch_session failed for sid=%s: %s", sid, e)


async def invalidate_all_sessions_for_user(db, user_id: str) -> int:
    try:
        res = await db.active_sessions.delete_many({"user_id": str(user_id)})
        return int(res.deleted_count or 0)
    except Exception: return 0


def _extract_token(request: Request, authorization: Optional[str]) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    raise HTTPException(401, "Autenticazione richiesta")


async def _load_user_from_db(db, user_id: str) -> Dict[str, Any]:
    try: oid = ObjectId(user_id)
    except Exception: raise HTTPException(401, "Token non valido")
    doc = await db.users.find_one({"_id": oid})
    if not doc: raise HTTPException(401, "Utente non trovato")
    return doc


class AuthDependencies:
    def __init__(self, db): self.db = db

    async def get_current_user(self, request: Request, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        token = _extract_token(request, authorization)
        payload = decode_token(token)
        if payload.get("type") != "access": raise HTTPException(401, "Tipo token non valido")
        user_id = payload.get("sub")
        if not user_id: raise HTTPException(401, "Token malformato")
        doc = await _load_user_from_db(self.db, user_id)
        if int(payload.get("pwv", 0)) != int(doc.get("password_version", 1)):
            raise HTTPException(401, "Sessione scaduta — rieffettua il login")
        if not doc.get("active", True): raise HTTPException(403, "Utente disattivato")
        sid = payload.get("sid")
        if sid:
            sess = await self.db.active_sessions.find_one({"sid": sid})
            if not sess: raise HTTPException(401, "Sessione disconnessa")
            await touch_session(self.db, sid); doc["_sid"] = sid
        module, action = _request_module_action(request)
        if module and not has_permission(doc, module, action):
            raise HTTPException(403, f"Permesso negato: {module}/{action}")
        return doc

    async def require_password_current(self, request: Request, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        user = await self.get_current_user(request, authorization)
        if user.get("must_change_password"):
            raise HTTPException(403, detail={"code": "password_change_required", "message": "Devi impostare una nuova password al primo accesso."})
        return user

    async def require_admin(self, request: Request, authorization: Optional[str] = Header(default=None)) -> Dict[str, Any]:
        user = await self.require_password_current(request, authorization)
        if user.get("role") != ROLE_ADMIN: raise HTTPException(403, "Solo gli amministratori possono accedere a questa risorsa")
        return user

    async def optional_user(self, request: Request, authorization: Optional[str] = Header(default=None)) -> Optional[Dict[str, Any]]:
        try: return await self.get_current_user(request, authorization)
        except HTTPException: return None
