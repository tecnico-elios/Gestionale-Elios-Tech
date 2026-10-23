"""Regressioni Spedizioni sulla API locale autenticata.

I casi con stock sintetico/concorrenza sono coperti da r4_stock_smoke.py; qui
verifichiamo contratto API e validazioni quando il DB isolato contiene prodotti.
"""
import requests
import pytest

from conftest import BASE_URL


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update({"Content-Type": "application/json"})
    return s


def _first_serialized(op_headers):
    r = requests.get(f"{BASE_URL}/api/inventory", headers=op_headers, timeout=30)
    assert r.status_code == 200, r.text[:300]
    inv = r.json().get("items", [])
    return next((i for i in inv if i.get("serialized") and (i.get("quantity") or 0) >= 1), None)


def _first_quantity(op_headers):
    r = requests.get(f"{BASE_URL}/api/inventory", headers=op_headers, timeout=30)
    assert r.status_code == 200, r.text[:300]
    inv = r.json().get("items", [])
    return next((i for i in inv if not i.get("serialized") and (i.get("quantity") or 0) >= 1), None)


def test_spedizione_requires_auth(api):
    r = api.post(f"{BASE_URL}/api/checklist/send", json={
        "operator": "T", "shipping_date": "2026-10-23",
        "structure": "TEST_CLIENTE_F3",
        "items": [{"page_id": "x", "name": "y", "serialized": False, "quantity": 1, "serials": []}],
    })
    assert r.status_code in (401, 403), r.text[:200]


def test_spedizione_missing_cliente(op_headers):
    r = requests.post(f"{BASE_URL}/api/checklist/send", headers=op_headers, json={
        "operator": "T", "shipping_date": "2026-10-23",
        "structure": "",
        "items": [{"page_id": "x", "name": "y", "serialized": False, "quantity": 1, "serials": []}],
    }, timeout=30)
    assert r.status_code == 400
    assert "cliente" in r.json()["detail"].lower()


def test_spedizione_strict_serial_not_in_stock(op_headers):
    s = _first_serialized(op_headers)
    if not s:
        pytest.skip("DB isolato senza prodotto serializzato; coperto da r4_stock_smoke")
    r = requests.post(f"{BASE_URL}/api/checklist/send", headers=op_headers, json={
        "operator": "T", "shipping_date": "2026-10-23",
        "structure": "TEST_CLIENTE_F3",
        "items": [{"page_id": s["id"], "name": s["name"], "serialized": True, "quantity": 1,
                   "serials": ["NEVER_F3_SN_XYZ"]}],
    }, timeout=30)
    assert r.status_code in (400, 409), r.text[:300]


def test_spedizione_duplicate_serial_payload(op_headers):
    s = _first_serialized(op_headers)
    if not s:
        pytest.skip("DB isolato senza prodotto serializzato; coperto da r4_stock_smoke")
    r = requests.post(f"{BASE_URL}/api/checklist/send", headers=op_headers, json={
        "operator": "T", "shipping_date": "2026-10-23",
        "structure": "TEST_CLIENTE_F3",
        "items": [{"page_id": s["id"], "name": s["name"], "serialized": True, "quantity": 2,
                   "serials": ["DUP_F3_A", "DUP_F3_A"]}],
    }, timeout=30)
    assert r.status_code in (400, 409), r.text[:300]


def test_spedizione_quantity_over_stock(op_headers):
    q = _first_quantity(op_headers)
    if not q:
        pytest.skip("DB isolato senza prodotto a quantità; coperto da r4_stock_smoke")
    r = requests.post(f"{BASE_URL}/api/checklist/send", headers=op_headers, json={
        "operator": "T", "shipping_date": "2026-10-23",
        "structure": "TEST_CLIENTE_F3",
        "items": [{"page_id": q["id"], "name": q["name"], "serialized": False,
                   "quantity": 99999999, "serials": []}],
    }, timeout=30)
    assert r.status_code in (400, 409), r.text[:300]
