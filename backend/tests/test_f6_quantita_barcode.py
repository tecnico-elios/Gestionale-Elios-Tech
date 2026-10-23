"""Regressioni barcode/seriali sulla API inventario corrente.

Il barcode di un prodotto a quantità identifica il modello, non la singola unità.
I test usano esclusivamente il backend isolato della CI.
"""
import requests
import pytest

from conftest import BASE_URL, _ensure_admin_token, _ensure_op_token


def _op_hdr():
    admin_tok, _ = _ensure_admin_token()
    tok, _ = _ensure_op_token(admin_tok)
    return {"Authorization": f"Bearer {tok}", "Content-Type": "application/json"}


@pytest.fixture(scope="module")
def api():
    s = requests.Session()
    s.headers.update(_op_hdr())
    return s


def test_lookup_barcode_of_a_quantita_returns_ok(api):
    mov_r = api.get(f"{BASE_URL}/api/movimenti", timeout=30)
    inv_r = api.get(f"{BASE_URL}/api/inventory", timeout=30)
    assert mov_r.status_code == 200, mov_r.text[:300]
    assert inv_r.status_code == 200, inv_r.text[:300]
    mov = mov_r.json().get("items", [])
    inv = inv_r.json().get("items", [])
    if not inv:
        pytest.skip("DB isolato senza prodotti; coperto da r4_stock_smoke")

    for m in mov:
        code = (m.get("serial_or_code") or "").strip()
        if not code or " " in code or "," in code or ";" in code:
            continue
        r = api.get(f"{BASE_URL}/api/inventory/lookup", params={"code": code}, timeout=30)
        if r.status_code != 200:
            continue
        d = r.json()
        item = d.get("item") or {}
        if item.get("tipo_gestione") == "a_quantita":
            assert d["status"] == "ok"
            assert d["matched_by"] in ("barcode", "sku")
            return
    pytest.skip("Nessun barcode a quantità presente nel DB isolato")


def test_lookup_sku_of_a_quantita_still_returns_ok_sku(api):
    r_inv = api.get(f"{BASE_URL}/api/inventory", timeout=30)
    assert r_inv.status_code == 200, r_inv.text[:300]
    inv = r_inv.json().get("items", [])
    q_item = next(
        (i for i in inv if i.get("tipo_gestione") == "a_quantita" and i.get("code")),
        None,
    )
    if not q_item:
        pytest.skip("DB isolato senza prodotto a quantità con SKU")
    r = api.get(f"{BASE_URL}/api/inventory/lookup", params={"code": q_item["code"]}, timeout=30)
    assert r.status_code == 200
    d = r.json()
    assert d["status"] == "ok"
    assert d["matched_by"] == "sku"


def test_unknown_code_is_not_found(api):
    r = api.get(
        f"{BASE_URL}/api/inventory/lookup",
        params={"code": "R4_UNKNOWN_BARCODE_9F84A"},
        timeout=30,
    )
    assert r.status_code == 200
    assert r.json().get("status") == "not_found"
