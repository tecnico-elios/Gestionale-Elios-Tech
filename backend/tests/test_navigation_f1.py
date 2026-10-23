"""Regressioni base API/navigazione della base corrente."""
import requests
import pytest

from conftest import BASE_URL, _ensure_admin_token, _ensure_op_token


def _admin_hdr():
    tok, _ = _ensure_admin_token()
    return {"Authorization": f"Bearer {tok}"}


def _op_hdr():
    admin_tok, _ = _ensure_admin_token()
    tok, _ = _ensure_op_token(admin_tok)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _get(path, **kw):
    return requests.get(f"{BASE_URL}{path}", timeout=30, **kw)


def _post(path, **kw):
    return requests.post(f"{BASE_URL}{path}", timeout=30, **kw)


def test_root_service_name():
    r = _get("/api/")
    assert r.status_code == 200
    data = r.json()
    assert data.get("service") == "Gestionale Elios Tech"
    assert data.get("database") == "locale"


def test_inventory_available_for_authenticated_operator():
    r = _get("/api/inventory", headers=_op_hdr())
    assert r.status_code == 200, r.text[:300]
    d = r.json()
    assert "items" in d and "categories" in d
    assert isinstance(d["items"], list)
    assert isinstance(d["categories"], list)
    assert d.get("source") == "gestionale"


def test_lookup_not_found():
    r = _get(
        "/api/inventory/lookup",
        headers=_op_hdr(),
        params={"code": "NEVER_EXISTS_XYZ_12345"},
    )
    assert r.status_code == 200
    assert r.json().get("status") == "not_found"


def _first_serialized_item():
    r = _get("/api/inventory", headers=_op_hdr())
    if r.status_code != 200:
        return None
    for it in r.json().get("items", []):
        if it.get("serialized") and (it.get("quantity") or 0) > 0:
            return it
    return None


def test_checklist_send_fake_serial_rejected_when_stock_exists():
    item = _first_serialized_item()
    if not item:
        pytest.skip("DB isolato senza seriali; coperto da r4_stock_smoke")
    payload = {
        "operator": "TEST_OP",
        "shipping_date": "2026-10-23",
        "structure": "TEST_CLIENT_DO_NOT_CREATE",
        "taken_by": "TEST_OP",
        "items": [{
            "page_id": item["id"],
            "name": item["name"],
            "category": item.get("category"),
            "unit": item.get("unit") or "pz",
            "serialized": True,
            "quantity": 1,
            "serials": ["NEVER_SEEN_XYZ_FAKE_9999"],
        }],
    }
    r = _post("/api/checklist/send", headers=_op_hdr(), json=payload)
    assert r.status_code in (400, 409), f"got {r.status_code}: {r.text[:300]}"


def test_admin_history_requires_auth():
    r = _get("/api/admin/history")
    assert r.status_code in (401, 403)


def test_admin_history_with_admin():
    r = _get("/api/admin/history", headers=_admin_hdr())
    assert r.status_code == 200
    assert isinstance(r.json(), (list, dict))


def test_admin_history_pdf_removed():
    r = _get("/api/admin/history/some-id/pdf", headers=_admin_hdr())
    assert r.status_code == 404
