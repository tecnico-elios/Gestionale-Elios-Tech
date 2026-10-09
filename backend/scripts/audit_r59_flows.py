from pathlib import Path
import ast

ROOT = Path(__file__).resolve().parents[1]

FILES = [
    "auth.py",
    "server.py",
    "routes/calendar_routes.py",
    "routes/crm_routes.py",
    "routes/admin_users_routes.py",
    "routes/commesse_routes.py",
    "routes/products_routes.py",
    "routes/documents_routes.py",
]

for rel in FILES:
    path = ROOT / rel
    text = path.read_text(encoding="utf-8")
    ast.parse(text, filename=str(path))

checks = {
    "auth.py": [
        "calendar:manage_people_roles",
        "/api/calendar/resources",
    ],
    "routes/calendar_routes.py": [
        "require_people_role_manager",
        "manage_people_roles",
        "DEFAULT_PERSON_ROLES",
        "Ruolo operativo libero",
        '@router.get("/events")',
        '@router.post("/events")',
        '@router.get("/resources")',
        '@router.post("/resources")',
        '@router.put("/resources/{resource_id}")',
    ],
    "routes/crm_routes.py": [
        '@router.get("/clienti-summary")',
        '"pec": 1',
        '"codice_sdi": 1',
        '"ordini-clienti"',
        '"installazioni"',
        '"assistenza"',
    ],
    "server.py": [
        '@api_router.get("/weather-installation"',
        "geocoding-api.open-meteo.com",
        "api.open-meteo.com/v1/forecast",
    ],
}

for rel, needles in checks.items():
    text = (ROOT / rel).read_text(encoding="utf-8")
    for needle in needles:
        if needle not in text:
            raise RuntimeError(f"R59 audit backend: {needle!r} mancante in {rel}")

print(f"[R59 audit backend] OK: {len(FILES)} file Python analizzati, contratti principali verificati.")
