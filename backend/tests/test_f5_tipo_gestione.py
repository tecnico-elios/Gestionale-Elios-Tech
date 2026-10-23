"""Regressioni Tipo Gestione e KPI sulla fonte locale del Gestionale."""
import requests
import pytest

from conftest import BASE_URL, _ensure_admin_token, _ensure_op_token


def _admin_hdr():
    tok, _ = _ensure_admin_token()
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


def _op_hdr():
    admin_tok, _ = _ensure_admin_token()
    tok, _ = _ensure_op_token(admin_tok)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def api():
    return requests.Session()


def test_inventory_source_is_gestionale(api):
    r = api.get(f"{BASE_URL}/api/inventory", headers=_op_hdr(), timeout=30)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("source") == "gestionale"
    assert isinstance(body.get("items"), list)


def test_inventory_exposes_tipo_gestione_when_products_exist(api):
    items = api.get(f"{BASE_URL}/api/inventory", headers=_op_hdr(), timeout=30).json().get("items", [])
    for it in items:
        assert "tipo_gestione" in it
        assert "configured" in it
        assert "serialized" in it
        if it.get("configured"):
            assert it.get("tipo_gestione") in ("a_seriale", "a_quantita")
            assert it.get("serialized") == (it.get("tipo_gestione") == "a_seriale")


def test_dashboard_kpi_shape(api):
    r = api.get(f"{BASE_URL}/api/dashboard/kpi", headers=_op_hdr(), timeout=30)
    assert r.status_code == 200, r.text[:300]
    j = r.json()
    assert isinstance(j, dict)
    for field in ("sotto_scorta", "esauriti", "non_configurati", "recent_movements"):
        assert field in j
        assert isinstance(j[field], list)


def test_admin_update_tipo_gestione_requires_auth(api):
    r = api.put(
        f"{BASE_URL}/api/admin/inventory/tipo-gestione",
        json={"page_id": "fake", "tipo_gestione": "a_seriale"},
        timeout=30,
    )
    assert r.status_code in (401, 403)


def test_admin_update_tipo_gestione_invalid_value(api):
    r = api.put(
        f"{BASE_URL}/api/admin/inventory/tipo-gestione",
        headers=_admin_hdr(),
        json={"page_id": "fake", "tipo_gestione": "banana"},
        timeout=30,
    )
    assert r.status_code == 400


def test_admin_inventory_is_gestionale(api):
    r = api.get(f"{BASE_URL}/api/admin/inventory", headers=_admin_hdr(), timeout=30)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("source") == "gestionale"
    assert isinstance(body.get("items"), list)


def test_admin_tipo_gestione_roundtrip_when_product_exists(api):
    inv = api.get(f"{BASE_URL}/api/inventory", headers=_op_hdr(), timeout=30).json().get("items", [])
    target = next((it for it in inv if it.get("tipo_gestione") in ("a_seriale", "a_quantita")), None)
    if not target:
        pytest.skip("DB isolato senza prodotto configurato")
    original = target["tipo_gestione"]
    flipped = "a_quantita" if original == "a_seriale" else "a_seriale"
    try:
        r = api.put(
            f"{BASE_URL}/api/admin/inventory/tipo-gestione",
            headers=_admin_hdr(),
            json={"page_id": target["id"], "tipo_gestione": flipped},
            timeout=30,
        )
        assert r.status_code == 200, r.text[:300]
        inv2 = api.get(f"{BASE_URL}/api/inventory", headers=_op_hdr(), timeout=30).json().get("items", [])
        updated = next((it for it in inv2 if it.get("id") == target["id"]), None)
        assert updated and updated.get("tipo_gestione") == flipped
    finally:
        api.put(
            f"{BASE_URL}/api/admin/inventory/tipo-gestione",
            headers=_admin_hdr(),
            json={"page_id": target["id"], "tipo_gestione": original},
            timeout=30,
        )
