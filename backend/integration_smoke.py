from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
from pymongo import MongoClient

BASE = "http://127.0.0.1:8001"
SYNC_DB = MongoClient(os.environ.get("MONGO_URL", "mongodb://127.0.0.1:27017"))[os.environ.get("DB_NAME", "elios_system_audit")]


def fail(message: str, response: requests.Response | None = None) -> None:
    if response is not None:
        body = response.text[:1500]
        raise AssertionError(f"{message}: HTTP {response.status_code} - {body}")
    raise AssertionError(message)


def wait_server() -> None:
    last = None
    for _ in range(60):
        try:
            r = requests.get(f"{BASE}/api/", timeout=2)
            if r.status_code == 200:
                print("[OK] Backend avviato")
                return
            last = f"HTTP {r.status_code}: {r.text[:200]}"
        except Exception as exc:
            last = str(exc)
        time.sleep(1)
    fail(f"Backend non disponibile: {last}")


def expect(method: str, path: str, *, status: int | tuple[int, ...] = 200, token: str | None = None, **kwargs: Any) -> requests.Response:
    headers = dict(kwargs.pop("headers", {}) or {})
    if token:
        headers["Authorization"] = f"Bearer {token}"
    r = requests.request(method, f"{BASE}{path}", headers=headers, timeout=30, **kwargs)
    allowed = (status,) if isinstance(status, int) else status
    if r.status_code not in allowed:
        fail(f"{method} {path} inatteso", r)
    print(f"[OK] {method} {path} -> {r.status_code}")
    return r


def main() -> None:
    wait_server()

    root = expect("GET", "/api/").json()
    assert root.get("status") == "ok", root

    # Database di test vuoto: bootstrap e autenticazione reale.
    st = expect("GET", "/api/auth/bootstrap-status").json()
    assert st.get("needs_bootstrap") is True, st

    bootstrap = expect(
        "POST", "/api/auth/bootstrap",
        json={"first_name": "Audit", "last_name": "Admin", "username": "auditadmin", "password": "AuditPass!2026"},
    ).json()
    token = bootstrap.get("token")
    assert token, bootstrap

    expect("POST", "/api/auth/login", status=401, json={"username": "auditadmin", "password": "sbagliata"})
    login = expect("POST", "/api/auth/login", json={"username": "auditadmin", "password": "AuditPass!2026", "remember_me": False}).json()
    token = login.get("token")
    assert token, login
    me = expect("GET", "/api/auth/me", token=token).json()
    assert me.get("username") == "auditadmin" and me.get("role") == "admin", me

    # Feature flag pubblico e aree principali autenticate.
    expect("GET", "/api/features")
    expect("GET", "/api/commesse", token=token)
    expect("GET", "/api/calendar/resources", token=token)
    expect("GET", "/api/calendar/events?start=2026-10-01T00:00:00%2B02:00&end=2026-11-01T00:00:00%2B01:00", token=token)

    inv = expect("GET", "/api/inventory", status=(200, 503), token=token)
    if inv.status_code == 503:
        print("[INFO] Inventario non configurato nel DB effimero: comportamento atteso")

    # CRUD Clienti.
    client = expect(
        "POST", "/api/crm/clienti", token=token,
        json={"ragione_sociale": "Cliente Audit R1", "tipo": "Azienda", "note": "Creato solo dal test automatico"},
    ).json()
    client_id = client.get("id")
    assert client_id, client

    clients = expect("GET", "/api/crm/clienti", token=token).json()
    assert any(x.get("id") == client_id for x in clients.get("items", [])), clients

    updated = expect(
        "PUT", f"/api/crm/clienti/{client_id}", token=token,
        json={"ragione_sociale": "Cliente Audit R1 Aggiornato", "tipo": "Azienda"},
    ).json()
    assert updated.get("ragione_sociale") == "Cliente Audit R1 Aggiornato", updated

    # Ordine cliente semplice collegato al cliente.
    order = expect(
        "POST", "/api/crm/ordini-clienti", token=token,
        json={"cliente_id": client_id, "numero": "AUDIT-001", "stato": "Bozza", "righe": []},
    ).json()
    order_id = order.get("id")
    assert order_id, order
    expect("GET", "/api/crm/ordini-clienti", token=token)

    # Installazione: creazione, report PDF, documenti GridFS.
    install = expect(
        "POST", "/api/crm/installazioni", token=token,
        json={
            "cliente_id": client_id,
            "ordine_cliente_id": order_id,
            "cliente": "Cliente Audit R1 Aggiornato",
            "tecnico": "Audit Admin",
            "data": "2026-10-23",
            "indirizzo": "Via Audit 1, 29121 Piacenza PC",
            "stato": "Programmato",
        },
    ).json()
    install_id = install.get("id")
    assert install_id, install

    prefill = expect("GET", f"/api/installation-reports/{install_id}", token=token).json()
    assert "data" in prefill, prefill

    report_data = {
        "data": "23/10/2026",
        "cliente": "Cliente Audit R1 Aggiornato",
        "tecnico": "Audit Admin",
        "indirizzo": "Via Audit 1, 29121 Piacenza PC",
        "societa_installatrice": "Elios Tech S.r.l.",
        "note": "PDF generato dal test automatico R1",
    }
    gen = expect(
        "POST", f"/api/installation-reports/{install_id}/generate", token=token,
        json={"data": report_data, "pdf_pages": "all"},
    ).json()
    assert gen.get("document_id"), gen

    install_db = SYNC_DB.crm_installazioni.find_one({"id": install_id})
    assert install_db and install_db.get("report_installazione_gridfs_id"), install_db
    install_doc = SYNC_DB.documents.find_one({"id": gen.get("document_id")})
    assert install_doc and install_doc.get("gridfs_id"), install_doc
    install_cache = Path(install_doc.get("stored_path") or "")
    if install_cache.exists():
        install_cache.unlink()
    pdf = expect("GET", f"/api/installation-reports/{install_id}/pdf", token=token)
    assert pdf.content.startswith(b"%PDF"), "PDF installazione non valido dopo ripristino GridFS"

    upload = expect(
        "POST", f"/api/files/installazioni/{install_id}", token=token,
        files={"file": ("audit.txt", b"file di test R1", "text/plain")},
        data={"category": "Altro", "note": "test GridFS"},
    ).json()
    document_id = upload.get("id")
    assert document_id, upload

    uploaded_db = SYNC_DB.documents.find_one({"id": document_id})
    assert uploaded_db and uploaded_db.get("gridfs_id"), uploaded_db
    uploaded_cache = Path(uploaded_db.get("stored_path") or "")
    if uploaded_cache.exists():
        uploaded_cache.unlink()
    listing = expect("GET", f"/api/files/installazioni/{install_id}", token=token).json()
    assert any(x.get("id") == document_id for x in listing.get("items", [])), listing

    downloaded = expect("GET", f"/api/files/download/{document_id}", token=token)
    assert downloaded.content == b"file di test R1", downloaded.content

    ticket = expect("POST", f"/api/files/open-ticket/{document_id}", token=token).json().get("ticket")
    assert ticket
    opened = expect("GET", f"/api/files/open/{ticket}")
    assert opened.content == b"file di test R1"

    expect("DELETE", f"/api/files/document/{document_id}", token=token)

    # Report Tecnico standalone: CRUD e PDF.
    free = expect(
        "POST", "/api/free-reports", token=token,
        json={"data": report_data, "pdf_pages": "2-3"},
    ).json()
    free_id = free.get("id")
    assert free_id, free
    expect("GET", f"/api/free-reports/{free_id}", token=token)
    expect(
        "PUT", f"/api/free-reports/{free_id}", token=token,
        json={"data": {**report_data, "note": "aggiornato"}, "pdf_pages": "2-3"},
    )
    free_gen = expect(
        "POST", f"/api/free-reports/{free_id}/generate", token=token,
        json={"data": {**report_data, "note": "aggiornato"}, "pdf_pages": "2-3"},
    ).json()
    assert free_gen.get("document_id"), free_gen
    free_db = SYNC_DB.free_technical_reports.find_one({"id": free_id})
    assert free_db and free_db.get("gridfs_id"), f"Report Tecnico senza gridfs_id: {free_db}"
    free_cache = Path(free_db.get("pdf_path") or "")
    if free_cache.exists():
        free_cache.unlink()
    free_pdf = expect("GET", f"/api/free-reports/{free_id}/pdf", token=token)
    assert free_pdf.content.startswith(b"%PDF"), "PDF standalone non valido dopo ripristino GridFS"
    expect("DELETE", f"/api/free-reports/{free_id}", token=token)

    # Assistenza collegata all'installazione.
    assistance = expect(
        "POST", "/api/crm/assistenza", token=token,
        json={"cliente_id": client_id, "installazione_id": install_id, "problema": "Test automatico", "stato": "Aperta"},
    ).json()
    assistance_id = assistance.get("id")
    assert assistance_id, assistance
    expect("GET", "/api/crm/assistenza", token=token)
    expect("DELETE", f"/api/crm/assistenza/{assistance_id}", token=token)

    # Pulizia record di test e verifica logout/sessione.
    # La cancellazione deve essere bloccata finché il report installazione è collegato.
    expect("DELETE", f"/api/crm/installazioni/{install_id}", status=409, token=token)
    expect("DELETE", f"/api/files/document/{gen.get('document_id')}", token=token)
    expect("DELETE", f"/api/crm/installazioni/{install_id}", token=token)
    expect("DELETE", f"/api/crm/ordini-clienti/{order_id}", token=token)
    expect("DELETE", f"/api/crm/clienti/{client_id}", token=token)

    expect("POST", "/api/auth/logout", token=token)
    expect("GET", "/api/auth/me", status=401, token=token)

    print("\n[PASS] Smoke test integrazione R1 completato senza errori")


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(f"\n[FAIL] {type(exc).__name__}: {exc}", file=sys.stderr)
        raise
