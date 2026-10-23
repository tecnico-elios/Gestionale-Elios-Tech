from __future__ import annotations

import sys
import time
from typing import Any

import requests

BASE = "http://127.0.0.1:8001"
ADMIN_USER = "auditadmin"
ADMIN_PASSWORD = "AuditPass!2026"


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


def login(username: str, password: str) -> dict:
    for _ in range(30):
        try:
            r = requests.post(f"{BASE}/api/auth/login", json={"username": username, "password": password, "remember_me": False}, timeout=3)
            if r.status_code == 200:
                return r.json()
        except Exception:
            pass
        time.sleep(1)
    fail(f"Login non riuscito per {username}")


def main() -> None:
    admin_login = login(ADMIN_USER, ADMIN_PASSWORD)
    admin = admin_login["user"]
    admin_token = admin_login["token"]

    # ------------------------------------------------------------------
    # Cambio password obbligatorio + permessi ruoli
    # ------------------------------------------------------------------
    operator = expect(
        "POST", "/api/admin/users", token=admin_token,
        json={"first_name": "Audit", "last_name": "Operator", "username": "auditoperator", "password": "TempOp!2026", "role": "operator"},
    ).json()
    operator_id = operator["id"]
    op_login = login("auditoperator", "TempOp!2026")
    assert op_login.get("must_change_password") is True, op_login
    op_temp_token = op_login["token"]

    # Un nuovo utente non deve poter usare NESSUNA funzione operativa prima del cambio password.
    blocked = expect("GET", "/api/inventory", token=op_temp_token, status=403)
    assert "password_change_required" in blocked.text, blocked.text

    changed = expect(
        "POST", "/api/auth/change-my-password", token=op_temp_token,
        json={"old_password": "TempOp!2026", "new_password": "Operator!2026"},
    ).json()
    op_token = changed["token"]
    expect("GET", "/api/inventory", token=op_token)
    expect("GET", "/api/admin/users", token=op_token, status=403)
    # Operatore ha calendar:view ma non calendar:create.
    expect("GET", "/api/calendar/resources", token=op_token)
    expect(
        "POST", "/api/calendar/events", token=op_token, status=403,
        json={"title": "Evento non autorizzato", "start": "2026-10-23T12:00:00+02:00"},
    )

    technician = expect(
        "POST", "/api/admin/users", token=admin_token,
        json={"first_name": "Audit", "last_name": "Tecnico", "username": "audittecnico", "password": "TempTech!2026", "role": "tecnico"},
    ).json()
    tech_id = technician["id"]
    tech_login = login("audittecnico", "TempTech!2026")
    tech_temp_token = tech_login["token"]
    expect("GET", "/api/calendar/resources", token=tech_temp_token, status=403)
    tech_token = expect(
        "POST", "/api/auth/change-my-password", token=tech_temp_token,
        json={"old_password": "TempTech!2026", "new_password": "Tecnico!2026"},
    ).json()["token"]
    expect("GET", "/api/calendar/resources", token=tech_token)
    expect("GET", "/api/inventory", token=tech_token, status=403)
    expect("GET", "/api/admin/users", token=tech_token, status=403)

    # ------------------------------------------------------------------
    # Installazioni: il Tecnico deve vedere solo quelle assegnate a lui.
    # ------------------------------------------------------------------
    assigned = expect(
        "POST", "/api/crm/installazioni", token=admin_token,
        json={"cliente": "Audit assegnata", "tecnico_user_id": tech_id, "data": "2026-10-23", "stato": "Programmato"},
    ).json()
    other = expect(
        "POST", "/api/crm/installazioni", token=admin_token,
        json={"cliente": "Audit non assegnata", "tecnico_user_id": admin["id"], "data": "2026-10-23", "stato": "Programmato"},
    ).json()
    assigned_id = assigned["id"]
    other_id = other["id"]

    tech_list = expect("GET", "/api/crm/installazioni", token=tech_token).json().get("items", [])
    ids = {x.get("id") for x in tech_list}
    assert assigned_id in ids, f"Installazione assegnata non visibile: {ids}"
    assert other_id not in ids, f"Installazione altrui visibile al Tecnico: {ids}"
    expect("GET", f"/api/crm/installazioni/{assigned_id}", token=tech_token)
    expect("GET", f"/api/crm/installazioni/{other_id}", token=tech_token, status=403)
    expect("PUT", f"/api/crm/installazioni/{assigned_id}", token=tech_token, json={"note": "Aggiornata dal tecnico audit"})
    expect("DELETE", f"/api/crm/installazioni/{assigned_id}", token=tech_token, status=403)

    # ------------------------------------------------------------------
    # Calendario manuale: CRUD Admin, sola lettura Operatore/Tecnico.
    # ------------------------------------------------------------------
    event = expect(
        "POST", "/api/calendar/events", token=admin_token,
        json={"title": "Evento Audit Calendario", "start": "2026-10-24T09:00:00+02:00", "end": "2026-10-24T10:00:00+02:00", "category": "Attività"},
    ).json()
    event_id = event["id"]
    events = expect(
        "GET", "/api/calendar/events?start=2026-10-24T00:00:00%2B02:00&end=2026-10-25T00:00:00%2B02:00", token=tech_token,
    ).json().get("items", [])
    assert any(x.get("id") == event_id for x in events), events
    updated = expect(
        "PUT", f"/api/calendar/events/manual:{event_id}", token=admin_token,
        json={"title": "Evento Audit Calendario aggiornato"},
    ).json()
    assert updated.get("title") == "Evento Audit Calendario aggiornato", updated
    expect("DELETE", f"/api/calendar/events/manual:{event_id}", token=admin_token)

    # ------------------------------------------------------------------
    # QR: config slot, unicità globale QR, unicità seriale/slot, detach.
    # ------------------------------------------------------------------
    qr_product = expect(
        "POST", "/api/products", token=admin_token,
        json={"warehouse_id": "elios-tech", "name": "Wallbox QR Audit", "code": "AUD-QR-R2", "unit": "pz", "tipo_gestione": "a_seriale", "active": True},
    ).json()
    qr_pid = qr_product["id"]
    expect(
        "POST", "/api/arrivi/send", token=admin_token,
        json={
            "warehouse_id": "elios-tech", "operator": "Audit", "arrival_date": "2026-10-23", "fornitore": "Audit",
            "items": [{"page_id": qr_pid, "name": "Wallbox QR Audit", "unit": "pz", "serialized": True, "quantity": 2, "serials": ["AUD-QR-SN-001", "AUD-QR-SN-002"]}],
        },
    )
    expect(
        "PUT", f"/api/qr/product-config/{qr_pid}", token=admin_token,
        json={"enabled": True, "slots": ["single"], "product_code": "AUD-QR-R2", "product_name": "Wallbox QR Audit"},
    )
    binding = expect(
        "POST", "/api/qr/bindings", token=admin_token,
        json={"serial": "AUD-QR-SN-001", "slot": "single", "qr_code": "https://qr.eliostech.it/webapp?qrCodeId=AUD_QR_001", "product_page_id": qr_pid, "product_name": "Wallbox QR Audit"},
    ).json()["binding"]
    binding_id = binding["id"]
    assert binding.get("qr_code") == "AUD_QR_001", binding
    expect(
        "POST", "/api/qr/bindings", token=admin_token, status=409,
        json={"serial": "AUD-QR-SN-002", "slot": "single", "qr_code": "AUD_QR_001", "product_page_id": qr_pid},
    )
    expect(
        "POST", "/api/qr/bindings", token=admin_token, status=409,
        json={"serial": "AUD-QR-SN-001", "slot": "single", "qr_code": "AUD_QR_002", "product_page_id": qr_pid},
    )
    check = expect("GET", "/api/qr/check-multi?qr=AUD_QR_001", token=admin_token).json()
    assert check.get("exists") is True and check.get("serial") == "AUD-QR-SN-001", check
    expect("DELETE", f"/api/qr/bindings/{binding_id}?reason=audit", token=admin_token)
    check2 = expect("GET", "/api/qr/check-multi?qr=AUD_QR_001", token=admin_token).json()
    assert check2.get("exists") is False, check2

    # ------------------------------------------------------------------
    # Revoca sessione su disattivazione + cleanup.
    # ------------------------------------------------------------------
    expect("DELETE", f"/api/crm/installazioni/{assigned_id}", token=admin_token)
    expect("DELETE", f"/api/crm/installazioni/{other_id}", token=admin_token)
    expect("PATCH", f"/api/admin/users/{operator_id}", token=admin_token, json={"active": False})
    expect("GET", "/api/inventory", token=op_token, status=(401, 403))
    expect("DELETE", f"/api/admin/users/{operator_id}", token=admin_token)
    expect("DELETE", f"/api/admin/users/{tech_id}", token=admin_token)

    print("\n[PASS] Permessi, cambio password, visibilità Installazioni, Calendario e QR verificati")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
