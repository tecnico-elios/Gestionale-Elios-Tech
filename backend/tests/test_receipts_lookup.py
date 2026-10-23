"""Regressioni /api/inventory/lookup sul database isolato."""
import requests
import pytest

from conftest import BASE_URL, _ensure_admin_token, _ensure_op_token


def _op_hdr():
    admin_tok, _ = _ensure_admin_token()
    tok, _ = _ensure_op_token(admin_tok)
    return {"Authorization": f"Bearer {tok}"}


def _get(code):
    return requests.get(
        f"{BASE_URL}/api/inventory/lookup",
        headers=_op_hdr(),
        params={"code": code},
        timeout=30,
    )


def test_not_found():
    r = _get("9999999_NOT_EXIST_R4")
    assert r.status_code == 200
    assert r.json()["status"] == "not_found"


def test_sku_lookup_when_catalog_has_code():
    inv = requests.get(f"{BASE_URL}/api/inventory", headers=_op_hdr(), timeout=30)
    assert inv.status_code == 200, inv.text[:300]
    item = next((x for x in inv.json().get("items", []) if x.get("code")), None)
    if not item:
        pytest.skip("DB isolato senza SKU; lookup sintetico coperto da smoke stock")
    r = _get(item["code"])
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["matched_by"] == "sku"
    assert d.get("item", {}).get("id") == item.get("id")
