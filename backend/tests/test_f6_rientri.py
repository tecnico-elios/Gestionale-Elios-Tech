"""Regressioni rientri/ultimo stato seriale sulla API locale corrente.

Il rientro non usa un endpoint separato: un seriale spedito rientra tramite il normale
flusso Arrivi. La prova completa entrata→uscita→rientro e' in r4_stock_smoke.py.
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


def test_lookup_unseen_serial_is_not_found(api):
    r = api.get(
        f"{BASE_URL}/api/inventory/lookup",
        params={"code": "F6RIENTRI_NEVER_SEEN_XYZ"},
        timeout=30,
    )
    assert r.status_code == 200, r.text[:300]
    assert r.json()["status"] == "not_found"


def test_inventory_is_local_gestionale(api):
    r = api.get(f"{BASE_URL}/api/inventory", timeout=30)
    assert r.status_code == 200, r.text[:300]
    body = r.json()
    assert body.get("source") == "gestionale"
    assert isinstance(body.get("items"), list)


def test_movimenti_endpoint_is_local_and_available(api):
    r = api.get(f"{BASE_URL}/api/movimenti", timeout=30)
    assert r.status_code == 200, r.text[:300]
    assert isinstance(r.json().get("items"), list)


def test_arrivo_duplicate_serial_is_blocked_when_serial_product_exists(api):
    inv = api.get(f"{BASE_URL}/api/inventory", timeout=30).json().get("items", [])
    ser_item = next((i for i in inv if i.get("tipo_gestione") == "a_seriale"), None)
    if not ser_item:
        pytest.skip("DB isolato senza prodotto serializzato; coperto da r4_stock_smoke")

    # Se non ci sono seriali disponibili non possiamo costruire una prova API read-only.
    serials = ser_item.get("serials") or []
    if not serials:
        pytest.skip("Nessun seriale disponibile nel DB isolato")
    serial = str(serials[0]).strip()
    if not serial:
        pytest.skip("Seriale vuoto")

    payload = {
        "operator": "F6-rientri test",
        "arrival_date": "2026-10-23",
        "fornitore": "F6 TEST",
        "items": [{
            "page_id": ser_item["id"],
            "name": ser_item["name"],
            "unit": ser_item.get("unit") or "pz",
            "serialized": True,
            "quantity": 1,
            "serials": [serial],
        }],
    }
    r = api.post(f"{BASE_URL}/api/arrivi/send", json=payload, timeout=30)
    assert r.status_code == 409, r.text[:300]
    assert "presente" in (r.json().get("detail") or "").lower()


def test_no_legacy_return_endpoint_contract(api):
    """Il rientro avviene da Arrivi; non deve dipendere dal vecchio /inventory/return."""
    r = api.post(f"{BASE_URL}/api/inventory/return", json={}, timeout=30)
    assert r.status_code == 404
