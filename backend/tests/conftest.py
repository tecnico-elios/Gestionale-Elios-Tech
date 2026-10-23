"""Shared pytest fixtures for backend tests.

I test usano per default il backend locale avviato dalla CI. Non devono mai
ripiegare automaticamente sull'URL di produzione.
"""
from pathlib import Path
import os
import requests
import pytest


BASE_URL = os.environ.get("AUDIT_BASE_URL", "").strip().rstrip("/")
if not BASE_URL:
    # Retro-compat per sviluppo locale: leggi frontend/.env solo se presente.
    env_path = Path(__file__).resolve().parents[2] / "frontend" / ".env"
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if line.startswith("REACT_APP_BACKEND_URL="):
                candidate = line.split("=", 1)[1].strip().rstrip("/")
                # In CI non consentiamo un fallback involontario verso Render/produzione.
                if candidate.startswith("http://127.0.0.1") or candidate.startswith("http://localhost"):
                    BASE_URL = candidate
                break
if not BASE_URL:
    BASE_URL = "http://127.0.0.1:8001"

TEST_ADMIN_USER = "test_admin_ci"
TEST_ADMIN_PWD = "test_admin_ci_pw_1"
TEST_OP_USER = "test_op_ci"
TEST_OP_PWD = "test_op_ci_pw_1"


def _login(username, password):
    try:
        return requests.post(
            f"{BASE_URL}/api/auth/login",
            json={"username": username, "password": password},
            timeout=10,
        )
    except requests.RequestException as exc:
        pytest.fail(f"Backend di test non raggiungibile su {BASE_URL}: {exc}")


def _ensure_admin_token():
    """Bootstrap/login admin sul database isolato della CI."""
    r = _login(TEST_ADMIN_USER, TEST_ADMIN_PWD)
    if r.status_code == 200:
        d = r.json()
        return d["token"], d["user"]["id"]

    bs = requests.get(f"{BASE_URL}/api/auth/bootstrap-status", timeout=5).json()
    if bs.get("needs_bootstrap"):
        r = requests.post(
            f"{BASE_URL}/api/auth/bootstrap",
            json={
                "first_name": "Test",
                "last_name": "AdminCI",
                "username": TEST_ADMIN_USER,
                "password": TEST_ADMIN_PWD,
            },
            timeout=10,
        )
        if r.status_code < 400:
            d = r.json()
            return d["token"], d["user"]["id"]

    # integration_smoke può aver già creato il proprio admin nello stesso DB isolato.
    # Usarlo evita di saltare silenziosamente i test autorizzati.
    r = _login("auditadmin", "AuditPass!2026")
    if r.status_code == 200:
        d = r.json()
        return d["token"], d["user"]["id"]

    pytest.fail("Impossibile ottenere un admin nel database di test isolato")


def _ensure_op_token(admin_token):
    """Get or create the test operator user, return (token, user_id)."""
    r = _login(TEST_OP_USER, TEST_OP_PWD)
    if r.status_code == 200:
        d = r.json()
        return d["token"], d["user"]["id"]

    r = requests.post(
        f"{BASE_URL}/api/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "first_name": "Test",
            "last_name": "OperatorCI",
            "username": TEST_OP_USER,
            "password": TEST_OP_PWD,
            "role": "operator",
        },
        timeout=10,
    )
    if r.status_code == 409:
        list_r = requests.get(
            f"{BASE_URL}/api/admin/users",
            headers={"Authorization": f"Bearer {admin_token}"},
            timeout=10,
        ).json()
        target = next((u for u in list_r["items"] if u["username"] == TEST_OP_USER), None)
        if target:
            requests.patch(
                f"{BASE_URL}/api/admin/users/{target['id']}",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"active": True},
                timeout=10,
            )
            requests.post(
                f"{BASE_URL}/api/admin/users/{target['id']}/reset-password",
                headers={"Authorization": f"Bearer {admin_token}"},
                json={"new_password": TEST_OP_PWD},
                timeout=10,
            )
    r = _login(TEST_OP_USER, TEST_OP_PWD)
    if r.status_code != 200:
        pytest.fail(f"Impossibile ottenere utente Operatore di test: {r.status_code} {r.text[:300]}")
    d = r.json()
    return d["token"], d["user"]["id"]


@pytest.fixture(scope="session")
def admin_token():
    tok, _ = _ensure_admin_token()
    return tok


@pytest.fixture(scope="session")
def admin_user_id():
    _, uid = _ensure_admin_token()
    return uid


@pytest.fixture(scope="session")
def op_token(admin_token):
    tok, _ = _ensure_op_token(admin_token)
    return tok


@pytest.fixture(scope="session")
def op_user_id(admin_token):
    _, uid = _ensure_op_token(admin_token)
    return uid


@pytest.fixture
def admin_headers(admin_token):
    return {"Authorization": f"Bearer {admin_token}", "Content-Type": "application/json"}


@pytest.fixture
def op_headers(op_token):
    return {"Authorization": f"Bearer {op_token}", "Content-Type": "application/json"}


@pytest.fixture(scope="session")
def base_url():
    return BASE_URL
