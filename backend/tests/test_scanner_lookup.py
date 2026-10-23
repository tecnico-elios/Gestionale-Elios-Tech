"""Regressioni scanner /api/inventory/lookup sul backend isolato."""
import pytest
import requests

from conftest import BASE_URL, _ensure_admin_token, _ensure_op_token


def _op_hdr():
    admin_tok, _ = _ensure_admin_token()
    tok, _ = _ensure_op_token(admin_tok)
    return {"Authorization": f"Bearer {tok}"}


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update(_op_hdr())
    return s


def test_health(api):
    r = api.get(f"{BASE_URL}/api/")
    assert r.status_code == 200
    assert r.json().get("status") == "ok"


def test_lookup_not_found(api):
    r = api.get(f"{BASE_URL}/api/inventory/lookup", params={"code": "INVALID_XYZ_123_R4"})
    assert r.status_code == 200
    data = r.json()
    assert data["status"] == "not_found"
    assert data["code"] == "INVALID_XYZ_123_R4"


def test_lookup_empty_code(api):
    r = api.get(f"{BASE_URL}/api/inventory/lookup", params={"code": ""})
    assert r.status_code == 400
    assert "Codice mancante" in r.json().get("detail", "")


def test_lookup_sku_case_insensitive_when_catalog_has_sku(api):
    inv = api.get(f"{BASE_URL}/api/inventory")
    assert inv.status_code == 200, inv.text[:300]
    item = next((x for x in inv.json().get("items", []) if x.get("code")), None)
    if not item:
        pytest.skip("DB isolato senza SKU")
    code = str(item["code"])
    upper = api.get(f"{BASE_URL}/api/inventory/lookup", params={"code": code.upper()})
    lower = api.get(f"{BASE_URL}/api/inventory/lookup", params={"code": code.lower()})
    assert upper.status_code == 200 and lower.status_code == 200
    assert upper.json().get("status") == "ok"
    assert lower.json().get("status") == "ok"
    assert upper.json().get("item", {}).get("id") == lower.json().get("item", {}).get("id")


def test_inventory_contract(api):
    r = api.get(f"{BASE_URL}/api/inventory")
    assert r.status_code == 200
    body = r.json()
    assert body.get("source") == "gestionale"
    assert isinstance(body.get("items"), list)
