"""Regressioni API correnti del Gestionale Elios Tech.

Questi test girano solo contro il backend isolato della CI: niente Notion e niente
produzione. I flussi stock con dati reali sintetici sono coperti da r4_stock_smoke.py.
"""
import requests
import pytest

from conftest import BASE_URL, _ensure_admin_token, _ensure_op_token

API = f"{BASE_URL}/api"
FAKE_SN = "F6FAKE_SN_NOT_EXISTS_XYZ"


def _admin_hdr():
    tok, _ = _ensure_admin_token()
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _op_hdr():
    admin_tok, _ = _ensure_admin_token()
    tok, _ = _ensure_op_token(admin_tok)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _unwrap(payload):
    if isinstance(payload, dict) and "items" in payload:
        return payload["items"]
    return payload


class TestOperationalEndpoints:
    def test_inventory(self):
        r = requests.get(f"{API}/inventory", headers=_op_hdr(), timeout=30)
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("source") == "gestionale"
        assert isinstance(body.get("items"), list)

    def test_inventory_lookup_not_found(self):
        r = requests.get(
            f"{API}/inventory/lookup", headers=_op_hdr(), params={"code": FAKE_SN}, timeout=30
        )
        assert r.status_code == 200, r.text[:300]
        assert r.json().get("status") == "not_found"

    def test_movimenti_no_month(self):
        r = requests.get(f"{API}/movimenti", headers=_op_hdr(), timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(_unwrap(r.json()), list)

    def test_movimenti_month_current(self):
        r = requests.get(
            f"{API}/movimenti", headers=_op_hdr(), params={"month": "2026-10"}, timeout=30
        )
        assert r.status_code == 200, r.text[:300]
        body = r.json()
        assert body.get("month") == "2026-10"
        assert isinstance(_unwrap(body), list)

    def test_movimenti_month_invalid(self):
        r = requests.get(
            f"{API}/movimenti", headers=_op_hdr(), params={"month": "not-a-month"}, timeout=30
        )
        assert r.status_code in (400, 422)

    def test_dashboard_kpi(self):
        r = requests.get(f"{API}/dashboard/kpi", headers=_op_hdr(), timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(r.json(), dict)

    def test_anomalie(self):
        r = requests.get(f"{API}/anomalie", headers=_op_hdr(), timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(_unwrap(r.json()), list)

    def test_checklist_history(self):
        r = requests.get(f"{API}/checklist/history", headers=_op_hdr(), timeout=30)
        assert r.status_code == 200, r.text[:300]


class TestAdminEndpoints:
    def test_admin_inventory_requires_auth(self):
        r = requests.get(f"{API}/admin/inventory", timeout=30)
        assert r.status_code in (401, 403)

    def test_admin_inventory_ok(self):
        r = requests.get(f"{API}/admin/inventory", headers=_admin_hdr(), timeout=30)
        assert r.status_code == 200, r.text[:300]
        assert isinstance(_unwrap(r.json()), list)

    def test_admin_recipients(self):
        r = requests.get(f"{API}/admin/recipients", headers=_admin_hdr(), timeout=30)
        assert r.status_code == 200, r.text[:300]


class TestSerialStrictValidation:
    def _inventory(self):
        return _unwrap(requests.get(f"{API}/inventory", headers=_op_hdr(), timeout=30).json())

    def _find_serialized_item(self):
        return next((i for i in self._inventory() if i.get("tipo_gestione") == "a_seriale"), None)

    def _find_quantity_item(self):
        return next((i for i in self._inventory() if i.get("tipo_gestione") == "a_quantita"), None)

    def test_shipment_unknown_serial_blocked_when_serial_product_exists(self):
        s = self._find_serialized_item()
        if not s:
            pytest.skip("DB isolato senza prodotto serializzato; coperto da r4_stock_smoke")
        payload = {
            "operator": "TEST_F6",
            "taken_by": "TEST_F6",
            "structure": "TEST_F6_CLIENTE",
            "shipping_date": "2026-10-23",
            "items": [{
                "page_id": s["id"], "name": s["name"], "serialized": True,
                "quantity": 1, "serials": [FAKE_SN],
            }],
        }
        r = requests.post(f"{API}/checklist/send", headers=_op_hdr(), json=payload, timeout=30)
        assert r.status_code in (400, 409), r.text[:300]

    def test_shipment_quantity_over_stock_when_quantity_product_exists(self):
        q = self._find_quantity_item()
        if not q:
            pytest.skip("DB isolato senza prodotto a quantità; coperto da r4_stock_smoke")
        payload = {
            "operator": "TEST_F6",
            "taken_by": "TEST_F6",
            "structure": "TEST_F6_CLIENTE",
            "shipping_date": "2026-10-23",
            "items": [{
                "page_id": q["id"], "name": q["name"], "serialized": False,
                "quantity": 99999999, "serials": [],
            }],
        }
        r = requests.post(f"{API}/checklist/send", headers=_op_hdr(), json=payload, timeout=30)
        assert r.status_code in (400, 409), r.text[:300]
