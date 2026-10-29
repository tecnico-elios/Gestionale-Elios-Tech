from __future__ import annotations

import os
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
FRONTEND = ROOT / "frontend"

issues: list[str] = []
warnings: list[str] = []


def issue(msg: str) -> None:
    issues.append(msg)
    print(f"[ERRORE] {msg}")


def warn(msg: str) -> None:
    warnings.append(msg)
    print(f"[WARN] {msg}")


def ok(msg: str) -> None:
    print(f"[OK] {msg}")


version = (ROOT / "VERSION").read_text(encoding="utf-8").strip()
if not re.fullmatch(r"R[1-9][0-9]*", version):
    issue(f"VERSION non valida: {version!r}")
else:
    ok(f"VERSION = {version}")

# La nuova base non deve eseguire patch storiche a runtime/build.
for rel in ("Dockerfile", "frontend/package.json"):
    text = (ROOT / rel).read_text(encoding="utf-8")
    if re.search(r"(?:apply|audit|prepare)[-_]r\d+", text, flags=re.I):
        issue(f"{rel}: contiene ancora riferimenti a patch storiche")
    else:
        ok(f"{rel}: nessuna patch storica eseguita")

server_text = (BACKEND / "server.py").read_text(encoding="utf-8")
old_build = re.search(r'"build"\s*:\s*"([^"]+)"', server_text)
if old_build and old_build.group(1) != version:
    warn(f"server.py espone build non coerente: {old_build.group(1)} (VERSION={version})")

# I Lead non devono più essere una risorsa operativa/API.
active_files = [
    BACKEND / "auth.py",
    BACKEND / "routes" / "crm_routes.py",
    BACKEND / "routes" / "documents_routes.py",
]
for path in active_files:
    text = path.read_text(encoding="utf-8")
    if "crm_lead" in text or re.search(r'["\']/lead(?:/|["\'])', text):
        issue(f"{path.relative_to(ROOT)}: residuo operativo Lead")
    if path.name == "auth.py" and re.search(r'["\']lead["\']\s*:\s*["\']ordini_clienti["\']', text):
        warn("auth.py contiene ancora mapping permessi legacy per Lead")

# Import reale dell'app: intercetta import mancanti, route non registrate e collisioni.
os.environ.setdefault("MONGO_URL", "mongodb://127.0.0.1:27017")
os.environ.setdefault("DB_NAME", "elios_system_audit")
os.environ.setdefault("JWT_SECRET", "elios-system-audit-secret")
os.environ.setdefault("ADMIN_PASSWORD", "audit-admin-password")
os.environ.setdefault("CHECKLIST_RECIPIENTS", "")
os.environ.setdefault("PUBLIC_FRONTEND_URL", "http://127.0.0.1:8001")
sys.path.insert(0, str(BACKEND))

# Le route CRM statiche, che non coincidono con una chiave RESOURCES, devono
# essere mappate esplicitamente al modulo autorizzativo corretto.
try:
    import auth as audit_auth  # noqa: E402
    from types import SimpleNamespace

    permission_cases = [
        ("GET", "/api/crm/clienti-summary", ("ordini_clienti", "view")),
        ("GET", "/api/crm/ordini-insights", ("commesse", "view")),
        ("GET", "/api/crm/interventi-tecnici", ("installazioni", "view")),
        ("POST", "/api/crm/interventi-tecnici", ("installazioni", "create")),
    ]
    for method, path, expected in permission_cases:
        req = SimpleNamespace(method=method, url=SimpleNamespace(path=path))
        actual = audit_auth._request_module_action(req)
        if actual != expected:
            issue(f"Mapping permesso errato per {method} {path}: {actual!r}, atteso {expected!r}")
        else:
            ok(f"Mapping permesso {method} {path} -> {expected[0]}/{expected[1]}")
except Exception as exc:
    issue(f"Verifica mapping permessi fallita: {type(exc).__name__}: {exc}")

# La policy password deve restare unica e forte su backend e frontend.
try:
    for weak in ("Abc!123", "solominuscole!2026", "SenzaSpeciale2026"):
        try:
            audit_auth.validate_password(weak)
        except ValueError:
            pass
        else:
            issue(f"Policy password troppo permissiva per {weak!r}")
    audit_auth.validate_password("Password!2026")
    ok("Policy password: minimo 8, maiuscola e carattere speciale")
except Exception as exc:
    issue(f"Verifica policy password fallita: {type(exc).__name__}: {exc}")

password_ui_files = [
    FRONTEND / "src" / "pages" / "LoginPage.jsx",
    FRONTEND / "src" / "pages" / "ForceChangePasswordPage.jsx",
    FRONTEND / "src" / "pages" / "ResetPasswordPage.jsx",
    FRONTEND / "src" / "pages" / "AdminUsersPage.jsx",
    FRONTEND / "src" / "components" / "ChangeMyPasswordDialog.jsx",
]
for path in password_ui_files:
    text = path.read_text(encoding="utf-8")
    if "minLength={6}" in text or "almeno 6 caratteri" in text.lower() or "min. 6 caratteri" in text.lower():
        issue(f"{path.relative_to(ROOT)}: residuo policy password a 6 caratteri")
else:
    ok("Frontend password allineato alla policy R8")

native_dialog_hits = []
for path in (FRONTEND / "src").rglob("*"):
    if path.suffix not in {".js", ".jsx"}:
        continue
    text = path.read_text(encoding="utf-8")
    if re.search(r"\bwindow\.(?:confirm|alert|prompt)\s*\(", text):
        native_dialog_hits.append(path.relative_to(ROOT))
if native_dialog_hits:
    for path in native_dialog_hits:
        issue(f"Popup browser nativo residuo: {path}")
else:
    ok("Nessun popup browser nativo window.confirm/alert/prompt")

try:
    import server  # noqa: E402
except Exception as exc:  # pragma: no cover - CI diagnostic
    issue(f"Import backend/server.py fallito: {type(exc).__name__}: {exc}")
    server = None

if server is not None:
    seen: dict[tuple[str, str], list[str]] = defaultdict(list)
    api_routes = []
    for route in server.app.routes:
        path = getattr(route, "path", None)
        methods = sorted(getattr(route, "methods", None) or [])
        if not path:
            continue
        if path.startswith("/api"):
            api_routes.append(path)
        for method in methods:
            if method in {"HEAD", "OPTIONS"}:
                continue
            seen[(method, path)].append(getattr(route, "name", "?"))

    duplicates = [(k, v) for k, v in seen.items() if len(v) > 1]
    if duplicates:
        for (method, path), names in duplicates:
            issue(f"Rotta duplicata {method} {path}: {names}")
    else:
        ok(f"Nessuna collisione tra {len(seen)} route HTTP")

    required_prefixes = {
        "auth": "/api/auth",
        "crm": "/api/crm",
        "commesse": "/api/commesse",
        "calendar": "/api/calendar",
        "documenti": "/api/files",
        "report installazioni": "/api/installation-reports",
        "report tecnico": "/api/free-reports",
        "inventario": "/api/inventory",
    }
    for label, prefix in required_prefixes.items():
        if any(p.startswith(prefix) for p in api_routes):
            ok(f"Gruppo API presente: {label} ({prefix})")
        else:
            issue(f"Gruppo API mancante: {label} ({prefix})")

    if any("/lead" in p for p in api_routes):
        issue("Route Lead ancora registrata in FastAPI")
    else:
        ok("Nessuna route Lead registrata")

    print(f"[INFO] Route API registrate: {len(set(api_routes))}")

# Controllo basilare degli import alias @/ del frontend.
missing_imports = []
for path in (FRONTEND / "src").rglob("*"):
    if path.suffix not in {".js", ".jsx"}:
        continue
    text = path.read_text(encoding="utf-8")
    for target in re.findall(r'from\s+["\']@/([^"\']+)["\']', text):
        base = FRONTEND / "src" / target
        candidates = [base, base.with_suffix(".js"), base.with_suffix(".jsx"), base / "index.js", base / "index.jsx"]
        if not any(c.exists() for c in candidates):
            missing_imports.append((path.relative_to(ROOT), target))
if missing_imports:
    for src, target in missing_imports[:20]:
        issue(f"Import frontend non risolto: {src} -> @/{target}")
else:
    ok("Import frontend @/ risolti")

print(f"\nAudit strutturale concluso: {len(issues)} errori, {len(warnings)} avvisi")
if issues:
    raise SystemExit(1)
