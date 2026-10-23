from __future__ import annotations

import asyncio
import os
import sys
import uuid
from pathlib import Path

from motor.motor_asyncio import AsyncIOMotorClient

HERE = Path(__file__).resolve().parent
if str(HERE) not in sys.path:
    sys.path.insert(0, str(HERE))

import inventory_integrity
import inventory_local


def ok(message: str) -> None:
    print(f"[OK] {message}")


async def expect_error(awaitable, contains: str | None = None) -> str:
    try:
        await awaitable
    except Exception as exc:
        text = str(exc)
        if contains and contains.lower() not in text.lower():
            raise AssertionError(f"Errore inatteso: {text!r}; atteso testo {contains!r}") from exc
        return text
    raise AssertionError("L'operazione avrebbe dovuto fallire")


async def product(db, *, name: str, code: str, kind: str, warehouse: str = "elios-tech") -> str:
    pid = str(uuid.uuid4())
    await db.products.insert_one({
        "id": pid,
        "name": name,
        "code": code,
        "code_lower": code.lower(),
        "tipo_gestione": kind,
        "unit": "pz",
        "warehouse_id": warehouse,
        "active": True,
        "quantity": 0,
    })
    return pid


async def qty(db, pid: str, wid: str) -> float:
    row = await db.warehouse_stock.find_one({"product_id": pid, "warehouse_id": wid}) or {}
    return float(row.get("quantity") or 0)


async def main() -> None:
    mongo_url = os.environ["MONGO_URL"]
    base_name = os.environ.get("DB_NAME", "elios_system_audit")
    db_name = f"{base_name}_r4_stock"
    client = AsyncIOMotorClient(mongo_url)
    await client.drop_database(db_name)
    db = client[db_name]
    inventory_local.set_db(db)
    inventory_integrity.install(inventory_local)

    try:
        q1 = await product(db, name="Cavo R4", code="R4-Q1", kind="a_quantita")
        s1 = await product(db, name="Wallbox R4 A", code="R4-S1", kind="a_seriale")
        s2 = await product(db, name="Wallbox R4 B", code="R4-S2", kind="a_seriale")

        await inventory_local.create_receipt(q1, "Cavo R4", 10, "2026-10-23", warehouse_id="elios-tech")
        assert await qty(db, q1, "elios-tech") == 10
        await inventory_local.create_pick(q1, "Cavo R4", 3, "Audit", "2026-10-23", warehouse_id="elios-tech")
        assert await qty(db, q1, "elios-tech") == 7
        ok("Arrivo e uscita a quantità aggiornano la giacenza correttamente")

        await expect_error(
            inventory_local.create_receipt(q1, "Cavo R4", -1, "2026-10-23", warehouse_id="elios-tech"),
            "maggiore di zero",
        )
        await expect_error(
            inventory_local.create_pick(q1, "Cavo R4", -1, "Audit", "2026-10-23", warehouse_id="elios-tech"),
            "maggiore di zero",
        )
        assert await qty(db, q1, "elios-tech") == 7
        ok("Quantità negative bloccate senza alterare lo stock")

        await inventory_local.create_receipt(s1, "R4-SN-001", 1, "2026-10-23", warehouse_id="elios-tech")
        await expect_error(
            inventory_local.create_receipt(s1, "R4-SN-001", 1, "2026-10-23", warehouse_id="elios-tech"),
            "già presente",
        )
        assert await db.local_receipts.count_documents({"sn": "R4-SN-001"}) == 1
        ok("Doppio Arrivo dello stesso seriale bloccato senza movimento duplicato")

        await expect_error(
            inventory_local.create_receipt(s2, "R4-SN-001", 1, "2026-10-23", warehouse_id="elios-tech"),
            "già associato",
        )
        assert await db.product_serials.count_documents({"serial_lower": "r4-sn-001"}) == 1
        ok("Lo stesso seriale non può appartenere a due prodotti")

        await inventory_local.create_pick(s1, "R4-SN-001", 1, "Cliente Audit", "2026-10-23", warehouse_id="elios-tech")
        state = await inventory_local.latest_serial_status("R4-SN-001")
        assert state.get("status") == "out", state
        await inventory_local.create_receipt(s1, "R4-SN-001", 1, "2026-10-24", warehouse_id="elios-tech")
        state = await inventory_local.latest_serial_status("R4-SN-001")
        assert state.get("status") == "in_warehouse", state
        ok("Rientro dello stesso seriale sul prodotto corretto resta consentito")

        await inventory_local.create_receipt(s1, "R4-SN-002", 1, "2026-10-23", warehouse_id="elios-tech")
        await expect_error(
            inventory_local.transfer_stock(
                s1, 2, "elios-tech", "verona",
                serials=["R4-SN-002", "R4-SN-002"], operator="Audit", note="test duplicato",
            ),
            "più volte",
        )
        before_transfer = await db.product_serials.find_one({"serial_lower": "r4-sn-002"})
        assert before_transfer.get("warehouse_id") == "elios-tech"
        ok("Trasferimento con seriale duplicato bloccato prima di modificare il deposito")

        moved = await inventory_local.transfer_stock(
            s1, 1, "elios-tech", "verona",
            serials=["R4-SN-002"], operator="Audit", note="test valido",
        )
        assert moved["quantity"] == 1 and moved["serials"] == ["R4-SN-002"], moved
        moved_row = await db.product_serials.find_one({"serial_lower": "r4-sn-002"})
        assert moved_row.get("warehouse_id") == "verona", moved_row
        assert await db.local_transfers.count_documents({"id": moved["id"]}) == 1
        ok("Trasferimento serializzato sposta una sola unità e crea un solo storico")

        moved_qty = await inventory_local.transfer_stock(
            q1, 2, "elios-tech", "verona", serials=[], operator="Audit", note="quantità valida",
        )
        target_q1 = moved_qty["target_product_id"]
        assert await qty(db, q1, "elios-tech") == 5
        assert await qty(db, target_q1, "verona") == 2
        ok("Trasferimento a quantità mantiene coerenti origine e destinazione")

        q2 = await product(db, name="Morsetto R4", code="R4-Q2", kind="a_quantita")
        await inventory_local.create_receipt(q2, "Morsetto R4", 10, "2026-10-23", warehouse_id="elios-tech")
        results = await asyncio.gather(
            inventory_local.create_pick(q2, "Morsetto R4", 7, "A", "2026-10-23", warehouse_id="elios-tech"),
            inventory_local.create_pick(q2, "Morsetto R4", 7, "B", "2026-10-23", warehouse_id="elios-tech"),
            return_exceptions=True,
        )
        successes = [x for x in results if isinstance(x, str)]
        failures = [x for x in results if isinstance(x, Exception)]
        assert len(successes) == 1 and len(failures) == 1, results
        assert await qty(db, q2, "elios-tech") == 3
        assert await db.local_picks.count_documents({"product_id": q2}) == 1
        ok("Due uscite concorrenti non possono portare la giacenza sotto zero")

        s3 = await product(db, name="Wallbox R4 C", code="R4-S3", kind="a_seriale")
        concurrent = await asyncio.gather(
            inventory_local.create_receipt(s3, "R4-CONCURRENT-SN", 1, "2026-10-23", warehouse_id="elios-tech"),
            inventory_local.create_receipt(s3, "R4-CONCURRENT-SN", 1, "2026-10-23", warehouse_id="elios-tech"),
            return_exceptions=True,
        )
        successes = [x for x in concurrent if isinstance(x, str)]
        failures = [x for x in concurrent if isinstance(x, Exception)]
        assert len(successes) == 1 and len(failures) == 1, concurrent
        assert await db.local_receipts.count_documents({"sn": "R4-CONCURRENT-SN"}) == 1
        ok("Due Arrivi concorrenti dello stesso seriale producono un solo movimento")

        print("\n[PASS] Smoke test integrità stock R4 completato")
    finally:
        await client.drop_database(db_name)
        client.close()


if __name__ == "__main__":
    asyncio.run(main())
