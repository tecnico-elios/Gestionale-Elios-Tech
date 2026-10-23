"""Regressioni endpoint Arrivi sulla base locale corrente."""
import requests
import pytest

from conftest import BASE_URL


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _get_first_serialized(op_headers):
    r = requests.get(f"{BASE_URL}/api/inventory", headers=op_headers, timeout=30)
    assert r.status_code == 200, r.text[:300]
    return next((i for i in r.json().get("items", []) if i.get("serialized")), None)


def test_arrivi_requires_auth(api):
    r = api.post(f"{BASE_URL}/api/arrivi/send", json={
        "operator": "T", "arrival_date": "2026-10-23", "fornitore": "F",
        "items": [{"page_id": "x", "name": "y", "serialized": False, "quantity": 1, "serials": []}],
    })
    assert r.status_code in (401, 403)


def test_arrivi_validation_missing_fornitore(op_headers):
    r = requests.post(f"{BASE_URL}/api/arrivi/send", headers=op_headers, json={
        "operator": "T", "arrival_date": "2026-10-23", "fornitore": "",
        "items": [{"page_id": "x", "name": "y", "serialized": False, "quantity": 1, "serials": []}],
    })
    assert r.status_code == 400
    assert "fornitore" in r.json()["detail"].lower()


def test_arrivi_validation_empty_items(op_headers):
    r = requests.post(f"{BASE_URL}/api/arrivi/send", headers=op_headers, json={
        "operator": "T", "arrival_date": "2026-10-23", "fornitore": "TestSup", "items": [],
    })
    assert r.status_code == 400


def test_arrivi_rejects_duplicate_serial_in_payload(op_headers):
    s = _get_first_serialized(op_headers)
    if not s:
        pytest.skip("DB isolato senza prodotto serializzato; coperto da r4_stock_smoke")
    r = requests.post(f"{BASE_URL}/api/arrivi/send", headers=op_headers, json={
        "operator": "Tester", "arrival_date": "2026-10-23", "fornitore": "TestSup",
        "items": [{
            "page_id": s["id"], "name": s["name"], "serialized": True, "quantity": 2,
            "serials": ["DUP_ARRIVAL_TEST_XYZ", "DUP_ARRIVAL_TEST_XYZ"],
        }],
    }, timeout=30)
    assert r.status_code == 409, r.text[:300]
    assert "più volte" in r.json()["detail"].lower() or "piu volte" in r.json()["detail"].lower()


def test_arrivi_rejects_serialized_wrong_serial_count(op_headers):
    r = requests.post(f"{BASE_URL}/api/arrivi/send", headers=op_headers, json={
        "operator": "T", "arrival_date": "2026-10-23", "fornitore": "TestSup",
        "items": [{"page_id": "abc", "name": "P", "serialized": True, "quantity": 3, "serials": ["A"]}],
    })
    assert r.status_code == 400
    assert "seriali" in r.json()["detail"].lower()
