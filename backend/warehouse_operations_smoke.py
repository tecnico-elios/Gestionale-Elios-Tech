from __future__ import annotations

import sys
import time
from typing import Any

import requests

BASE = "http://127.0.0.1:8001"
USER = "auditadmin"
PASSWORD = "AuditPass!2026"


def fail(message: str, response: requests.Response | None = None) -> None:
    if response is not None:
        raise AssertionError(f"{message}: HTTP {response.status_code} - {response.text[:1500]}")
    raise AssertionError(message)


def expect(method: str, path: str, *, token: str | None = None, status: int | tuple[int, ...] = 200, **kwargs: Any) -> requests.Response:
    headers = dict(kwargs.pop("headers", {}) or {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, f"{BASE}{path}", headers=headers, timeout=30, **kwargs)
    allowed = (status,) if isinstance(status, int) else status
    if r.status_code not in allowed:
        fail(f"{method} {path} inatteso", r)
    print(f"[OK] {method} {path} -> {r.status_code}")
    return r


def login() -> str:
    for _ in range(30):
        try:
            r = requests.post(f"{BASE}/api/auth/login", json={"username": USER, "password": PASSWORD, "remember_me": False}, timeout=3)
            if r.status_code == 200 and r.json().get("token"):
                return r.json()["token"]
        except Exception:
            pass
        time.sleep(1)
    fail("Impossibile autenticarsi con l'utente audit creato dallo smoke test principale")


def inventory_item(items: list[dict], product_id: str) -> dict:
    for item in items:
        if str(item.get("id") or item.get("page_id")) == product_id:
            return item
    fail(f"Prodotto {product_id} non trovato nell'inventario")


def main() -> None:
    token = login()

    qty_product = expect(
        "POST", "/api/products", token=token,
        json={
            "warehouse_id": "elios-tech", "name": "Cavo Audit R2", "code": "AUD-QTY-R2",
            "category": "Test", "unit": "m", "tipo_gestione": "a_quantita", "active": True,
        },
    ).json()
    serial_product = expect(
        "POST", "/api/products", token=token,
        json={
            "warehouse_id": "elios-tech", "name": "Wallbox Audit R2", "code": "AUD-SER-R2",
            "category": "Test", "unit": "pz", "tipo_gestione": "a_seriale", "active": True,
        },
    ).json()
    qty_id = qty_product["id"]
    ser_id = serial_product["id"]

    # Duplicati anagrafica nello stesso deposito devono essere bloccati.
    expect(
        "POST", "/api/products", token=token, status=409,
        json={
            "warehouse_id": "elios-tech", "name": "Duplicato", "code": "AUD-QTY-R2",
            "unit": "m", "tipo_gestione": "a_quantita", "active": True,
        },
    )

    # Entrata contemporanea prodotto a quantità + prodotto serializzato.
    arrival = expect(
        "POST", "/api/arrivi/send", token=token,
        json={
            "warehouse_id": "elios-tech", "operator": "Audit", "arrival_date": "2026-10-23",
            "fornitore": "Fornitore Audit",
            "items": [
                {"page_id": qty_id, "name": "Cavo Audit R2", "unit": "m", "serialized": False, "quantity": 10, "serials": []},
                {"page_id": ser_id, "name": "Wallbox Audit R2", "unit": "pz", "serialized": True, "quantity": 2, "serials": ["AUD-R2-SN-001", "AUD-R2-SN-002"]},
            ],
            "notes": "Test automatico isolato",
        },
    ).json()
    assert arrival.get("status") == "success", arrival

    # Lo stesso seriale non può rientrare una seconda volta se è già disponibile.
    expect(
        "POST", "/api/arrivi/send", token=token, status=409,
        json={
            "warehouse_id": "elios-tech", "operator": "Audit", "arrival_date": "2026-10-23",
            "fornitore": "Fornitore Audit",
            "items": [{"page_id": ser_id, "name": "Wallbox Audit R2", "unit": "pz", "serialized": True, "quantity": 1, "serials": ["AUD-R2-SN-001"]}],
        },
    )

    inv_elios = expect("GET", "/api/inventory?warehouse_id=elios-tech", token=token).json().get("items", [])
    q0 = inventory_item(inv_elios, qty_id)
    s0 = inventory_item(inv_elios, ser_id)
    assert float(q0.get("quantity") or 0) == 10, q0
    assert float(s0.get("quantity") or 0) == 2, s0

    # Lookup per codice prodotto e seriale.
    expect("GET", "/api/inventory/lookup?code=AUD-QTY-R2&warehouse_id=elios-tech", token=token)
    expect("GET", "/api/inventory/lookup?code=AUD-R2-SN-001&warehouse_id=elios-tech", token=token)

    # Trasferimenti tra depositi: quantità e seriale.
    qty_transfer = expect(
        "POST", "/api/warehouse/transfers", token=token,
        json={"product_id": qty_id, "quantity": 3, "serials": [], "from_warehouse_id": "elios-tech", "to_warehouse_id": "verona", "note": "Audit quantità"},
    ).json()["transfer"]
    qty_verona_id = qty_transfer["target_product_id"]
    ser_transfer = expect(
        "POST", "/api/warehouse/transfers", token=token,
        json={"product_id": ser_id, "quantity": 1, "serials": ["AUD-R2-SN-002"], "from_warehouse_id": "elios-tech", "to_warehouse_id": "verona", "note": "Audit seriale"},
    ).json()["transfer"]
    ser_verona_id = ser_transfer["target_product_id"]
    # Non deve essere possibile trasferire di nuovo dal deposito sbagliato lo stesso seriale.
    expect(
        "POST", "/api/warehouse/transfers", token=token, status=409,
        json={"product_id": ser_id, "quantity": 1, "serials": ["AUD-R2-SN-002"], "from_warehouse_id": "elios-tech", "to_warehouse_id": "verona", "note": "Audit duplicato"},
    )

    inv_elios = expect("GET", "/api/inventory?warehouse_id=elios-tech", token=token).json().get("items", [])
    inv_verona = expect("GET", "/api/inventory?warehouse_id=verona", token=token).json().get("items", [])
    assert float(inventory_item(inv_elios, qty_id).get("quantity") or 0) == 7
    assert float(inventory_item(inv_verona, qty_verona_id).get("quantity") or 0) == 3
    assert float(inventory_item(inv_elios, ser_id).get("quantity") or 0) == 1
    assert float(inventory_item(inv_verona, ser_verona_id).get("quantity") or 0) == 1

    transfers = expect("GET", "/api/warehouse/transfers", token=token).json().get("items", [])
    assert len(transfers) >= 2, transfers
    movements = expect("GET", "/api/movimenti?warehouse_id=elios-tech", token=token).json().get("items", [])
    assert movements, "Nessun movimento visibile dopo arrivi/trasferimenti"

    # Riporta il seriale a Elios per il test Commessa.
    expect(
        "POST", "/api/warehouse/transfers", token=token,
        json={"product_id": ser_verona_id, "quantity": 1, "serials": ["AUD-R2-SN-002"], "from_warehouse_id": "verona", "to_warehouse_id": "elios-tech", "note": "Rientro audit"},
    )

    # Commessa mista quantità + seriale.
    commessa = expect(
        "POST", "/api/commesse", token=token,
        json={
            "number": "AUD-R2-001", "cliente": "Cliente Audit Magazzino", "priorita": "normale", "warehouse_id": "elios-tech",
            "righe": [
                {"product_page_id": qty_id, "product_name": "Cavo Audit R2", "product_code": "AUD-QTY-R2", "tipo_gestione": "a_quantita", "unit": "m", "qty_richiesta": 2},
                {"product_page_id": ser_id, "product_name": "Wallbox Audit R2", "product_code": "AUD-SER-R2", "tipo_gestione": "a_seriale", "unit": "pz", "qty_richiesta": 1},
            ],
        },
    ).json()
    cid = commessa["id"]
    assert commessa.get("stato") == "da_preparare", commessa

    taken = expect("POST", f"/api/commesse/{cid}/take", token=token).json()
    assert taken.get("stato") == "in_preparazione", taken

    expect("POST", f"/api/commesse/{cid}/pick", token=token, json={"riga_index": 0, "quantity": 2})
    expect("POST", f"/api/commesse/{cid}/pick", token=token, json={"riga_index": 1, "serial": "AUD-R2-SN-001"})
    # Over-pick quantità e doppio uso seriale devono essere bloccati.
    expect("POST", f"/api/commesse/{cid}/pick", token=token, status=400, json={"riga_index": 0, "quantity": 1})
    expect("POST", f"/api/commesse/{cid}/pick", token=token, status=409, json={"riga_index": 1, "serial": "AUD-R2-SN-001"})

    current = expect("GET", f"/api/commesse/{cid}", token=token).json()
    assert current.get("stato") == "pronta", current
    assert float(current["righe"][0].get("qty_prelevata") or 0) == 2
    assert current["righe"][1].get("seriali_prelevati") == ["AUD-R2-SN-001"]

    # Con picking presente la cancellazione definitiva è correttamente protetta.
    expect("DELETE", f"/api/commesse/{cid}", token=token, status=409)

    # Rimuove i prelievi e verifica che la commessa possa essere eliminata senza movimenti/spedizioni.
    expect("POST", f"/api/commesse/{cid}/pick", token=token, json={"riga_index": 0, "quantity": -2})
    expect("POST", f"/api/commesse/{cid}/pick", token=token, json={"riga_index": 1, "serial": "AUD-R2-SN-001", "remove": True})
    expect("DELETE", f"/api/commesse/{cid}", token=token)

    # Prodotto con giacenza non deve essere archiviabile.
    expect("DELETE", f"/api/products/{qty_id}", token=token, status=409)
    expect("DELETE", f"/api/products/{ser_id}", token=token, status=409)

    print("\n[PASS] Magazzino, seriali, trasferimenti, movimenti e commesse verificati")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
