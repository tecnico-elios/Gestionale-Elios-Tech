from __future__ import annotations

import asyncio
import os
import sys
import tempfile
from pathlib import Path

import httpx
from motor.motor_asyncio import AsyncIOMotorClient

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import auth
import email_service
import persistent_files


BASE_URL = os.environ.get("AUDIT_BASE_URL", "http://127.0.0.1:8001").rstrip("/")


def ok(message: str) -> None:
    print(f"[OK] {message}")


async def main() -> None:
    mongo_url = os.environ["MONGO_URL"]
    db_name = os.environ["DB_NAME"]
    client = AsyncIOMotorClient(mongo_url)
    db = client[db_name]

    username = "audit_operator_r3"
    password = "Audit-R3-Password!"
    await db.users.delete_many({"username": username})
    await db.active_sessions.delete_many({"username": username})

    user = {
        "username": username,
        "first_name": "Audit",
        "last_name": "Operator",
        "email": "audit-operator@example.invalid",
        "password_hash": auth.hash_password(password),
        "role": auth.ROLE_OPERATOR,
        "active": True,
        "password_version": 1,
        "must_change_password": False,
    }
    await db.users.insert_one(user)

    try:
        async with httpx.AsyncClient(base_url=BASE_URL, timeout=20.0) as http:
            login = await http.post("/api/auth/login", json={"username": username, "password": password})
            assert login.status_code == 200, (login.status_code, login.text)
            token = login.json()["token"]
            headers = {"Authorization": f"Bearer {token}"}

            listing = await http.get("/api/free-reports", headers=headers)
            assert listing.status_code == 403, (listing.status_code, listing.text)
            ok("Operatore senza permesso Installazioni bloccato sulla lettura Report Tecnico")

            creation = await http.post(
                "/api/free-reports",
                headers=headers,
                json={"data": {"cliente": "TEST NON AUTORIZZATO"}},
            )
            assert creation.status_code == 403, (creation.status_code, creation.text)
            ok("Operatore senza permesso Installazioni bloccato sulla creazione Report Tecnico")

        with tempfile.TemporaryDirectory(prefix="elios-r3-") as tmp:
            path = Path(tmp) / "report_email.pdf"
            payload = b"%PDF-1.4\n% R3 GridFS attachment smoke test\n"
            gridfs_id = await persistent_files.store_bytes(
                db,
                payload,
                path.name,
                "application/pdf",
                metadata={"resource": "audit_r3", "record_id": "email-attachment"},
            )
            doc_id = "audit-r3-email-document"
            await db.documents.delete_many({"id": doc_id})
            await db.documents.insert_one({
                "id": doc_id,
                "resource": "audit_r3",
                "record_id": "email-attachment",
                "filename": path.name,
                "stored_path": str(path),
                "gridfs_id": gridfs_id,
                "storage": "gridfs",
                "content_type": "application/pdf",
            })
            assert not path.exists()
            restored = await email_service._ensure_persistent_attachment(db, path)
            assert restored.exists()
            assert restored.read_bytes() == payload
            ok("Allegato email ricostruito da GridFS quando la cache locale manca")
            await db.documents.delete_many({"id": doc_id})
            await persistent_files.delete_bytes(db, gridfs_id)

        print("[PASS] Smoke test R3 completato")
    finally:
        await db.active_sessions.delete_many({"username": username})
        await db.users.delete_many({"username": username})
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
