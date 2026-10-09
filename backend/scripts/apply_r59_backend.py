from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def patch_file(rel: str, patches: list[tuple[str, str, str]]) -> None:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    changed = False
    for old, new, label in patches:
        if new in text:
            continue
        if old not in text:
            raise RuntimeError(f"R59 backend: blocco non trovato in {rel}: {label}")
        text = text.replace(old, new, 1)
        changed = True
    if changed:
        path.write_text(text, encoding="utf-8")
        print(f"[R59 backend] aggiornato {rel}")


# Permesso speciale delegabile: consente di gestire persone/ruoli del calendario
# senza concedere i normali permessi di creazione/modifica eventi.
patch_file(
    "auth.py",
    [
        (
            'SPECIAL_PERMISSIONS = {"installazioni:view_all"}',
            'SPECIAL_PERMISSIONS = {"installazioni:view_all", "calendar:manage_people_roles"}',
            "special permission calendar people roles",
        ),
        (
            '    elif path.startswith("/api/calendar"):\n        module = "calendar"',
            '    elif path.startswith("/api/calendar"):\n        # Le mutazioni di persone/calendari hanno un permesso dedicato e vengono\n        # autorizzate dalla dependency specifica della rotta. Il GET resta invece\n        # protetto dal normale permesso calendar:view.\n        if path.startswith("/api/calendar/resources") and method in {"POST", "PUT", "PATCH", "DELETE"}:\n            return None, None\n        module = "calendar"',
            "calendar resource permission bypass",
        ),
    ],
)

# PEC e codice SDI devono essere inclusi anche nell'elenco aggregato Clienti/Ordini,
# altrimenti ricerca e filtri non possono trovarli.
patch_file(
    "routes/crm_routes.py",
    [
        (
            '             "agente": 1, "data_firma": 1, "pagamento": 1, "capitale": 1, "qty_wb": 1, "stato_cliente": 1,\n             "da_ricontattare": 1, "data_ricontatto": 1, "priorita_ricontatto": 1, "referente": 1}',
            '             "agente": 1, "data_firma": 1, "pagamento": 1, "capitale": 1, "qty_wb": 1, "stato_cliente": 1,\n             "pec": 1, "codice_sdi": 1, "sdi": 1,\n             "da_ricontattare": 1, "data_ricontatto": 1, "priorita_ricontatto": 1, "referente": 1}',
            "client summary PEC/SDI projection",
        ),
    ],
)

# R58 introdusse quattro ruoli fissi. R59 li mantiene solo come suggerimenti iniziali:
# il ruolo operativo è ora testo libero (es. Direttore tecnico, Direttore commerciale).
patch_file(
    "routes/calendar_routes.py",
    [
        (
            'import uuid\nimport zipfile\nfrom zoneinfo import ZoneInfo',
            'import uuid\nimport zipfile\nimport auth as auth_mod\nfrom zoneinfo import ZoneInfo',
            "auth import",
        ),
        (
            'PERSON_ROLES = ("Amministrazione", "Tecnico", "Commerciale", "Assistenza")\n\ndef _normalize_resource_role(value: Any) -> str:\n    raw = str(value or "").strip().casefold()\n    for role in PERSON_ROLES:\n        if role.casefold() == raw:\n            return role\n    return "Tecnico"',
            'DEFAULT_PERSON_ROLES = ("Amministrazione", "Tecnico", "Commerciale", "Assistenza")\n\ndef _normalize_resource_role(value: Any) -> str:\n    """Ruolo operativo libero, ripulito e limitato a una lunghezza ragionevole."""\n    role = re.sub(r"\\s+", " ", str(value or "").strip())\n    if not role:\n        return "Tecnico"\n    return role[:80].strip()',
            "free-form calendar person roles",
        ),
        (
            '    router = APIRouter(prefix="/calendar", tags=["Calendar"])\n',
            '    router = APIRouter(prefix="/calendar", tags=["Calendar"])\n\n    async def require_people_role_manager(current=Depends(deps.require_password_current)):\n        """Admin oppure utente a cui l\'Admin ha delegato la gestione persone/ruoli."""\n        if (\n            current.get("role") == auth_mod.ROLE_ADMIN\n            or auth_mod.is_master_user(current)\n            or auth_mod.has_permission(current, "calendar", "manage_people_roles")\n        ):\n            return current\n        raise HTTPException(403, "Permesso negato: gestione persone e ruoli del calendario")\n',
            "calendar people role dependency",
        ),
        (
            '    async def create_resource(body: AnyBody, current=Depends(deps.require_admin)):',
            '    async def create_resource(body: AnyBody, current=Depends(require_people_role_manager)):',
            "delegated create resource",
        ),
        (
            '    async def update_resource(resource_id: str, body: AnyBody, current=Depends(deps.require_admin)):',
            '    async def update_resource(resource_id: str, body: AnyBody, current=Depends(require_people_role_manager)):',
            "delegated update resource",
        ),
        (
            '    async def delete_resource(resource_id: str, current=Depends(deps.require_admin)):',
            '    async def delete_resource(resource_id: str, current=Depends(require_people_role_manager)):',
            "delegated delete resource",
        ),
    ],
)

print("[R59 backend] permessi calendario, ruoli liberi e PEC/SDI applicati.")
