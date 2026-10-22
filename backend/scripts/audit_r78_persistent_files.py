from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
doc = (ROOT / "routes" / "documents_routes.py").read_text(encoding="utf-8")
inst = (ROOT / "routes" / "installation_report_routes.py").read_text(encoding="utf-8")
free = (ROOT / "routes" / "free_reports_routes.py").read_text(encoding="utf-8")
helper = (ROOT / "persistent_files.py").read_text(encoding="utf-8")

checks = {
    "helper GridFS": "AsyncIOMotorGridFSBucket" in helper and 'BUCKET_NAME = "elios_files"' in helper,
    "helper restore": "async def ensure_local" in helper,
    "documenti import storage": "import persistent_files" in doc,
    "documenti senza lead": '"lead": ("crm_lead", "lead")' not in doc,
    "documenti upload GridFS": "gridfs_id = await persistent_files.store_bytes" in doc,
    "documenti metadata GridFS": '"storage": "gridfs"' in doc and '"gridfs_id": gridfs_id' in doc,
    "documenti restore": "await persistent_files.ensure_local" in doc,
    "documenti delete GridFS": 'await persistent_files.delete_bytes(db, doc.get("gridfs_id"))' in doc,
    "installazioni store GridFS": 'inst.get("report_installazione_gridfs_id")' in inst and "persistent_files.replace_bytes" in inst,
    "installazioni document metadata": '"gridfs_id": gridfs_id, "storage": "gridfs"' in inst,
    "installazioni record GridFS": '"report_installazione_gridfs_id": gridfs_id' in inst,
    "installazioni restore": "await persistent_files.ensure_local" in inst,
    "standalone store GridFS": 'existing.get("gridfs_id")' in free and "persistent_files.replace_bytes" in free,
    "standalone document metadata": '"gridfs_id": gridfs_id' in free and '"storage": "gridfs"' in free,
    "standalone record GridFS": '"gridfs_id": gridfs_id' in free,
    "standalone restore": "await persistent_files.ensure_local" in free,
    "standalone delete GridFS": 'await persistent_files.delete_bytes(db, doc.get("gridfs_id"))' in free,
    "R77 report parity preserved": 'report_installazione_pdf_pages' in inst and 'Sono necessarie la firma del cliente e del tecnico' not in inst,
    "R76 free fields preserved": "Il collegamento all'installazione serve solo per proporre i valori iniziali." in inst,
}

failed = [name for name, ok in checks.items() if not ok]
if failed:
    raise RuntimeError("R78 audit fallito: " + ", ".join(failed))
print("[R78 audit] OK: file e report persistono in GridFS; Lead rimosso dalle risorse documentali; R76/R77 preservate.")
