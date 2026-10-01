"""Auth core — bcrypt hashing, JWT tokens, FastAPI dependencies.

Design (Prompt 220 §Auth) + F7 estensioni:
  - Users stored in MongoDB `users` collection. NEVER in Notion.
  - Passwords: bcrypt hash only. NEVER plaintext (DB/logs/Notion/frontend/source).
  - Ruoli: Admin, Responsabile, Operatore, Commerciale e Tecnico.
  - Session invalidation after password reset via `password_version` — the JWT
    embeds `pwv`, and `get_current_user` rejects tokens whose `pwv` no longer
    matches the user's current `password_version`.
  - `active_sessions` MongoDB collection tracks per-JWT session:
      {sid, user_id, username, created_at, last_activity, last_login}
    Ogni JWT contiene `sid` (session id). `get_current_user` verifica che la
    sessione esista ancora (l'admin può disconnetterla via DELETE /admin/sessions/{sid}).
    Ad ogni chiamata autenticata `last_activity` viene aggiornata.
    NON viene mai salvata informazione sul dispositivo (IP/UA) — solo tempo.
  - `must_change_password`: se True l'utente può usare SOLO /auth/me e
    /auth/change-my-password. Ogni altra rotta ritorna 403 con codice specifico.
  - Bootstrap: NO auto-seeded admin. Endpoint `POST /api/auth/bootstrap`
    works ONLY when `db.users` is empty (see routes/auth_routes.py).
"""
from __future__ import annotations

import os
import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, Dict, Any

import bcrypt
import jwt
from bson import ObjectId
from fastapi import HTTPException, Depends, Header, Request

logger = logging.getLogger(__name__)

# Permessi granulari del Gestionale Elios Tech.
# Ogni permesso è nel formato "modulo:azione". Le azioni supportate sono
# visualizzazione, creazione, modifica, eliminazione ed esportazione.
PERMISSION_ACTIONS = ["view", "create", "edit", "delete", "export"]
PERMISSION_MODULES = [
    "dashboard", "lead", "clienti", "contatti", "sedi", "sopralluoghi",
    "preventivi", "ordini_clienti", "commesse", "installazioni", "assistenza",
    "inventario", "arrivi", "spedizioni", "movimenti", "anomalie",
    "ai", "impostazioni", "utenti", "importazione_dati",
]

# Permessi legacy ancora usati da alcune funzioni specialistiche.
LEGACY_PERMISSIONS = {"gestione_commesse", "modifica_retroattiva"}
SPECIAL_PERMISSIONS = {"installazioni:view_all"}

ROLE_ADMIN = "admin"
ROLE_RESPONSABILE = "responsabile"
ROLE_OPERATOR = "operator"
ROLE_COMMERCIALE = "commerciale"
ROLE_TECNICO = "tecnico"
VALID_ROLES = {ROLE_ADMIN, ROLE_RESPONSABILE, ROLE_OPERATOR, ROLE_COMMERCIALE, ROLE_TECNICO}


def _perms(modules, actions=("view", "create", "edit", "delete", "export")):
    return {f"{m}:{a}" for m in modules for a in actions}


def default_permissions_for_role(role: str):
    """Permessi predefiniti. L'Admin può poi personalizzarli utente per utente."""
    if role == ROLE_ADMIN:
        return _perms(PERMISSION_MODULES) | LEGACY_PERMISSIONS
    if role == ROLE_OPERATOR:
        # L'operatore lavora sulle commesse esistenti e sui flussi di magazzino.
        # La creazione di nuove commesse resta separata e può essere concessa dall'Admin.
        base = _perms(["inventario", "arrivi", "spedizioni"], ("view", "create", "edit"))
        base |= _perms(["commesse"], ("view", "edit"))
        return base | {"gestione_commesse"}
    if role == ROLE_COMMERCIALE:
        # Il Commerciale usa Lead e la scheda unificata Elios Tech Ordini.
        return _perms(["lead", "ordini_clienti"]) | _perms(["commesse"], ("view", "export"))
    if role == ROLE_TECNICO:
        # Profilo operativo essenziale: il tecnico vede e aggiorna solo le installazioni
        # assegnate a lui. Accessi extra possono essere concessi dall'Admin dalla matrice.
        return _perms(["dashboard"], ("view",)) | _perms(["installazioni"], ("view", "edit", "export"))
    if role == ROLE_RESPONSABILE:
        mods = [
            "dashboard", "lead", "clienti", "contatti", "sedi", "sopralluoghi",
            "preventivi", "ordini_clienti", "commesse", "installazioni", "assistenza",
            "inventario", "arrivi", "spedizioni", "movimenti", "anomalie", "ai",
        ]
        return _perms(mods) | {"gestione_commesse", "modifica_retroattiva", "installazioni:view_all"}
    return set()


def effective_permissions(user_doc):
    if not user_doc:
        return set()
    role = user_doc.get("role")
    if role == ROLE_ADMIN or is_master_user(user_doc):
        return default_permissions_for_role(ROLE_ADMIN)
    # Se l'Admin ha personalizzato la matrice, usa esattamente quella.
    if user_doc.get("permissions_customized"):
        return set(user_doc.get("permissions") or [])
    return default_permissions_for_role(role)


def has_permission(user_doc, module: str, action: str = "view") -> bool:
    """Controllo permessi compatibile sia con la nuova matrice sia con i permessi legacy."""
    if not user_doc:
        return False
    if user_doc.get("role") == ROLE_ADMIN or is_master_user(user_doc):
        return True
    perms = effective_permissions(user_doc)
    if module in LEGACY_PERMISSIONS:
        return module in perms
    if module not in PERMISSION_MODULES:
        return False
    # Retrocompatibilità: un vecchio permesso bare "inventario" equivale a tutte le azioni.
    return module in perms or f"{module}:{action}" in perms


def _request_module_action(request: Request):
    """Mappa le API del gestionale alla matrice permessi. None = nessun gate aggiuntivo."""
    path = request.url.path or ""
    method = request.method.upper()
    if not path.startswith("/api/"):
        return None, None
    # Auth e bootstrap devono restare accessibili all'utente autenticato.
    if path.startswith("/api/auth/") or path == "/api/time":
        return None, None
    # Tutte le rotte amministrative continuano ad avere require_admin dove previsto.
    if path.startswith("/api/admin/"):
        return None, None

    module = None
    if path.startswith("/api/crm/"):
        tail = path[len("/api/crm/"):].split("/", 1)[0]
        module = {
            "lead": "lead", "clienti": "ordini_clienti", "contatti": "ordini_clienti",
            "sedi": "ordini_clienti", "sopralluoghi": "sopralluoghi", "preventivi": "preventivi",
            "ordini-clienti": "ordini_clienti", "installazioni": "installazioni",
            "assistenza": "assistenza",
        }.get(tail)
        if tail == "meta":
            module = "dashboard"
        elif tail == "lookups":
            module = "commesse"
    elif path.startswith("/api/commesse"):
        module = "commesse"
    elif path.startswith("/api/inventory"):
        module = "inventario"
    elif path.startswith("/api/arrivi"):
        module = "arrivi"
    elif path.startswith("/api/checklist"):
        module = "spedizioni"
    elif path.startswith("/api/movimenti"):
        module = "movimenti"
    elif path.startswith("/api/warehouse"):
        module = "movimenti"
    elif path.startswith("/api/anomalie"):
        module = "anomalie"
    elif path.startswith("/api/dashboard"):
        module = "dashboard"
    elif path.startswith("/api/ai"):
        module = "ai"
    elif path.startswith("/api/files"):
        # I file vengono autorizzati dalla rotta in base alla risorsa padre.
        module = None

    if not module:
        return None, None
    if method == "GET":
        action = "view"
    elif method == "DELETE":
        action = "delete"
    elif method in {"PUT", "PATCH"}:
        action = "edit"
    else:
        # POST su una collection crea; POST su /commesse/<id>/... modifica il record.
        if module == "commesse" and path.count("/") > 3:
            action = "edit"
        else:
            action = "create"
    return module, action


JWT_ALGORITHM = "HS256"
# Account master protetto — non modificabile/eliminabile/disattivabile da nessuno,
# neanche da altri Admin. Confronto case-insensitive sull'email.
MASTER_EMAIL = "tecnico@eliostech.org"


def is_master_user(user_doc) -> bool:
    """True se l'utente è l'account master protetto (Riccardo Biuso)."""
    if not user_doc:
        return False
    email = str(user_doc.get("email") or "").strip().lower()
    return email == MASTER_EMAIL


def _jwt_secret() -> str:
    s = os.environ.get("JWT_SECRET")
    if not s:
        raise RuntimeError("JWT_SECRET missing in environment")
    return s


def _access_ttl_minutes() -> int:
    try:
        return int(os.environ.get("JWT_ACCESS_TTL_MINUTES", "480"))
    except ValueError:
        return 480


def _remember_ttl_minutes() -> int:
    """Durata token quando l'utente ha spuntato 'Rimani collegato'."""
    try:
        return int(os.environ.get("JWT_REMEMBER_TTL_MINUTES", str(60 * 24 * 30)))  # 30 giorni
    except ValueError:
        return 60 * 24 * 30


# ---------- Password hashing ----------

def hash_password(password: str) -> str:
    if not password or len(password) < 6:
        raise ValueError("La password deve avere almeno 6 caratteri")
    salt = bcrypt.gensalt(rounds=12)
    return bcrypt.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def verify_password(plain: str, hashed: str) -> bool:
    if not plain or not hashed:
        return False
    try:
        return bcrypt.checkpw(plain.encode("utf-8"), hashed.encode("utf-8"))
    except (ValueError, TypeError):
        return False


# ---------- JWT ----------

def create_access_token(
    user_id: str,
    username: str,
    role: str,
    password_version: int,
    remember: bool = False,
    sid: Optional[str] = None,
) -> str:
    now = datetime.now(timezone.utc)
    ttl_min = _remember_ttl_minutes() if remember else _access_ttl_minutes()
    payload = {
        "sub": user_id,
        "username": username,
        "role": role,
        "pwv": password_version,
        "rem": bool(remember),
        "iat": int(now.timestamp()),
        "exp": now + timedelta(minutes=ttl_min),
        "type": "access",
    }
    if sid:
        payload["sid"] = sid
    return jwt.encode(payload, _jwt_secret(), algorithm=JWT_ALGORITHM)


def decode_token(token: str) -> Dict[str, Any]:
    try:
        return jwt.decode(token, _jwt_secret(), algorithms=[JWT_ALGORITHM])
    except jwt.ExpiredSignatureError:
        raise HTTPException(401, "Token scaduto")
    except jwt.InvalidTokenError:
        raise HTTPException(401, "Token non valido")


# ---------- Sanitization ----------

def public_user(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Strip sensitive fields before exposing a user document via API."""
    if not doc:
        return {}
    return {
        "id": str(doc.get("_id")),
        "username": doc.get("username"),
        "first_name": doc.get("first_name"),
        "last_name": doc.get("last_name"),
        "full_name": f"{doc.get('first_name') or ''} {doc.get('last_name') or ''}".strip() or doc.get("username"),
        "email": doc.get("email"),
        "role": doc.get("role"),
        "active": bool(doc.get("active", True)),
        "must_change_password": bool(doc.get("must_change_password", False)),
        "last_login": doc.get("last_login"),
        "created_at": doc.get("created_at"),
        "permissions": doc.get("permissions") or [],
        "permissions_customized": bool(doc.get("permissions_customized", False)),
        "effective_permissions": sorted(effective_permissions(doc)),
    }


# ---------- Session helpers ----------

async def create_session(db, user_id: str, username: str) -> str:
    """Crea una nuova sessione in `active_sessions` e ritorna il session id."""
    sid = uuid.uuid4().hex
    now = datetime.now(timezone.utc)
    await db.active_sessions.insert_one({
        "sid": sid,
        "user_id": user_id,
        "username": username,
        "created_at": now,
        "last_login": now,
        "last_activity": now,
    })
    return sid


async def touch_session(db, sid: str) -> None:
    """Aggiorna last_activity — best-effort, non blocca la request se fallisce."""
    if not sid:
        return
    try:
        await db.active_sessions.update_one(
            {"sid": sid},
            {"$set": {"last_activity": datetime.now(timezone.utc)}},
        )
    except Exception as e:
        logger.warning("touch_session failed for sid=%s: %s", sid, e)


async def invalidate_all_sessions_for_user(db, user_id: str) -> int:
    """Elimina tutte le sessioni di un utente (usato dopo reset password / disattivazione)."""
    try:
        res = await db.active_sessions.delete_many({"user_id": str(user_id)})
        return int(res.deleted_count or 0)
    except Exception:
        return 0


# ---------- FastAPI dependencies ----------

def _extract_token(request: Request, authorization: Optional[str]) -> str:
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    # NO cookie fallback: i cookie possono essere sincronizzati tra dispositivi
    # via Chrome Sync o iCloud Keychain. Solo Bearer header è per-device.
    raise HTTPException(401, "Autenticazione richiesta")


async def _load_user_from_db(db, user_id: str) -> Dict[str, Any]:
    try:
        oid = ObjectId(user_id)
    except Exception:
        raise HTTPException(401, "Token non valido")
    doc = await db.users.find_one({"_id": oid})
    if not doc:
        raise HTTPException(401, "Utente non trovato")
    return doc


class AuthDependencies:
    """Bound to the db handle from server.py. Exposes FastAPI dependencies
    that DON'T need `db` to be passed explicitly at call sites."""

    def __init__(self, db):
        self.db = db

    async def get_current_user(
        self,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        token = _extract_token(request, authorization)
        payload = decode_token(token)
        if payload.get("type") != "access":
            raise HTTPException(401, "Tipo token non valido")
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(401, "Token malformato")
        doc = await _load_user_from_db(self.db, user_id)
        # Invalidation: JWT pwv must match user's current password_version
        if int(payload.get("pwv", 0)) != int(doc.get("password_version", 1)):
            raise HTTPException(401, "Sessione scaduta — rieffettua il login")
        if not doc.get("active", True):
            raise HTTPException(403, "Utente disattivato")
        # Session check — se il JWT ha un sid, deve esistere in active_sessions
        sid = payload.get("sid")
        if sid:
            sess = await self.db.active_sessions.find_one({"sid": sid})
            if not sess:
                raise HTTPException(401, "Sessione disconnessa")
            # Touch last_activity (best-effort, non blocca)
            await touch_session(self.db, sid)
            doc["_sid"] = sid
        # Gate permessi applicato anche lato backend: nascondere una voce nel menu non basta.
        module, action = _request_module_action(request)
        if module and not has_permission(doc, module, action):
            raise HTTPException(403, f"Permesso negato: {module}/{action}")
        # must_change_password: guard applied by require_password_current below
        return doc

    async def require_password_current(
        self,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        """Come get_current_user ma blocca l'accesso se must_change_password=True.
        Usa questa in tutte le rotte NON coinvolte nel cambio password."""
        user = await self.get_current_user(request, authorization)
        if user.get("must_change_password"):
            raise HTTPException(
                status_code=403,
                detail={
                    "code": "password_change_required",
                    "message": "Devi impostare una nuova password al primo accesso.",
                },
            )
        return user

    async def require_admin(
        self,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> Dict[str, Any]:
        user = await self.require_password_current(request, authorization)
        if user.get("role") != ROLE_ADMIN:
            raise HTTPException(403, "Solo gli amministratori possono accedere a questa risorsa")
        return user

    async def optional_user(
        self,
        request: Request,
        authorization: Optional[str] = Header(default=None),
    ) -> Optional[Dict[str, Any]]:
        """Return the current user if a valid token is present, else None.
        Never raises. Used to gracefully upgrade F6 endpoints during migration."""
        try:
            return await self.get_current_user(request, authorization)
        except HTTPException:
            return None
