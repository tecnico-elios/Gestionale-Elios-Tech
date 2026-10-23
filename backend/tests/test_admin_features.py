"""Regressioni admin della base corrente Gestionale Elios Tech."""
import requests
import pytest

from conftest import BASE_URL


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


# ---- Health / base consolidata ----
def test_root(api):
    r = api.get(f"{BASE_URL}/api/")
    assert r.status_code == 200
    j = r.json()
    assert j.get("status") == "ok"
    assert j.get("service") == "Gestionale Elios Tech"
    assert j.get("database") == "locale"


def test_legacy_admin_login_wrong(api):
    r = api.post(f"{BASE_URL}/api/admin/login", json={"password": "wrong"})
    assert r.status_code == 401


def test_admin_history_requires_auth(api):
    r = api.get(f"{BASE_URL}/api/admin/history")
    assert r.status_code in (401, 403)


def test_admin_history_rejects_operator(op_headers):
    r = requests.get(f"{BASE_URL}/api/admin/history", headers=op_headers)
    assert r.status_code == 403


def test_admin_history_no_filter(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/history", headers=admin_headers)
    assert r.status_code == 200
    j = r.json()
    assert "items" in j and "count" in j
    assert isinstance(j["items"], list)


def test_admin_history_date_filter(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/history",
        headers=admin_headers,
        params={"date_from": "1900-01-01", "date_to": "1900-12-31"},
    )
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_admin_history_materiale_filter(admin_headers):
    r = requests.get(
        f"{BASE_URL}/api/admin/history",
        headers=admin_headers,
        params={"materiale": "ZZZZ_NOSUCH_ITEM"},
    )
    assert r.status_code == 200
    assert r.json()["count"] == 0


def test_admin_inventory_is_local(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/inventory", headers=admin_headers, timeout=30)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("source") == "gestionale"
    assert isinstance(body.get("items"), list)


def test_admin_history_pdf_endpoint_removed(admin_headers):
    r = requests.get(f"{BASE_URL}/api/admin/history/anyid/pdf", headers=admin_headers)
    assert r.status_code == 404


# ---- Strict serial validation: eseguita solo se il DB isolato ha dati adatti ----
def test_submit_rejects_unknown_serial(op_headers):
    inv_r = requests.get(f"{BASE_URL}/api/inventory", headers=op_headers, timeout=30)
    assert inv_r.status_code == 200, inv_r.text[:300]
    inv = inv_r.json().get("items", [])
    serialized = next(
        (it for it in inv if it.get("serialized") and (it.get("quantity") or 0) >= 1),
        None,
    )
    if not serialized:
        pytest.skip("DB isolato senza seriali; coperto da r4_stock_smoke")
    payload = {
        "operator": "Test F0",
        "shipping_date": "2026-10-23",
        "structure": "TEST_CLIENTE_F0_STRICT",
        "items": [{
            "page_id": serialized["id"],
            "name": serialized["name"],
            "category": serialized.get("category"),
            "unit": serialized.get("unit") or "pz",
            "serialized": True,
            "quantity": 1,
            "serials": ["ELIOSTEST_UNKNOWN_SN_9999999"],
        }],
    }
    r = requests.post(
        f"{BASE_URL}/api/checklist/send", headers=op_headers, json=payload, timeout=30
    )
    assert r.status_code in (400, 409), r.text[:300]
