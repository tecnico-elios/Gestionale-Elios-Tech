from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def replace_once(text: str, old: str, new: str, label: str) -> str:
    if old not in text:
        if new in text:
            return text
        raise RuntimeError(f"R78: {label} non trovato")
    return text.replace(old, new, 1)


# ---------------------------------------------------------------------------
# Documenti e fotografie caricati dagli utenti
# ---------------------------------------------------------------------------
doc_path = ROOT / "routes" / "documents_routes.py"
doc = doc_path.read_text(encoding="utf-8")

if "import persistent_files" not in doc:
    doc = doc.replace("import auth as auth_mod\n", "import auth as auth_mod\nimport persistent_files\n", 1)

# I Lead non fanno parte del gestionale definitivo.
doc = doc.replace('    "lead": ("crm_lead", "lead"),\n', "")

restore_old = '''        path = Path(doc.get("stored_path") or "")
        if not path.exists():
            raise HTTPException(404, "File non disponibile sul server")
'''
restore_new = '''        path = Path(doc.get("stored_path") or "")
        if not path.exists() and doc.get("gridfs_id"):
            try:
                path = await persistent_files.ensure_local(db, doc.get("gridfs_id"), path)
            except FileNotFoundError:
                pass
        if not path.exists():
            raise HTTPException(404, "File non disponibile sul server")
'''
if doc.count(restore_old) < 2 and doc.count(restore_new) < 2:
    raise RuntimeError("R78: blocchi ripristino documenti non trovati")
doc = doc.replace(restore_old, restore_new, 2)

# Cancellazione coerente anche dal bucket persistente.
delete_anchor = '        path = Path(doc.get("stored_path") or "")\n        await db.documents.delete_one({"id": document_id})\n'
if 'await persistent_files.delete_bytes(db, doc.get("gridfs_id"))' not in doc:
    doc = replace_once(
        doc,
        delete_anchor,
        '        path = Path(doc.get("stored_path") or "")\n        await persistent_files.delete_bytes(db, doc.get("gridfs_id"))\n        await db.documents.delete_one({"id": document_id})\n',
        "cancellazione GridFS documenti",
    )

# Dopo aver ricevuto il file lo duplichiamo in GridFS: il file locale resta solo cache runtime.
upload_anchor = '''        now = datetime.now(timezone.utc)
        doc = {
            "id": doc_id,
'''
if 'gridfs_id = await persistent_files.store_bytes' not in doc:
    upload_new = '''        try:
            gridfs_id = await persistent_files.store_bytes(
                db, stored.read_bytes(), filename, file.content_type or "application/octet-stream",
                metadata={"resource": resource, "record_id": record_id, "document_id": doc_id},
            )
        except Exception as exc:
            stored.unlink(missing_ok=True)
            raise HTTPException(500, f"Impossibile salvare il file in modo persistente: {exc}")
        now = datetime.now(timezone.utc)
        doc = {
            "id": doc_id,
'''
    doc = replace_once(doc, upload_anchor, upload_new, "upload persistente documenti")

stored_anchor = '            "stored_path": str(stored),\n            "content_type": file.content_type or "application/octet-stream",\n'
if '            "gridfs_id": gridfs_id,\n' not in doc:
    doc = replace_once(
        doc,
        stored_anchor,
        '            "stored_path": str(stored),\n            "gridfs_id": gridfs_id,\n            "storage": "gridfs",\n            "content_type": file.content_type or "application/octet-stream",\n',
        "metadati GridFS documenti",
    )

doc_path.write_text(doc, encoding="utf-8")


# ---------------------------------------------------------------------------
# Report collegato a Installazioni
# ---------------------------------------------------------------------------
inst_path = ROOT / "routes" / "installation_report_routes.py"
inst = inst_path.read_text(encoding="utf-8")
if "import persistent_files" not in inst:
    inst = inst.replace("import inventory_local\n", "import inventory_local\nimport persistent_files\n", 1)

render_anchor = '        _render_pdf(data, out, page_numbers=(2, 3) if pdf_pages == "2-3" else (1, 2, 3))\n        now = datetime.now(timezone.utc)\n'
if 'gridfs_id = await persistent_files.replace_bytes' not in inst:
    render_new = '''        _render_pdf(data, out, page_numbers=(2, 3) if pdf_pages == "2-3" else (1, 2, 3))
        gridfs_id = await persistent_files.replace_bytes(
            db, inst.get("report_installazione_gridfs_id"), out.read_bytes(), filename, "application/pdf",
            metadata={"resource": "installazioni", "record_id": installation_id, "category": "Report installazione"},
        )
        now = datetime.now(timezone.utc)
'''
    inst = replace_once(inst, render_anchor, render_new, "salvataggio GridFS report installazione")

# Entrambi i rami, update e insert del documento, ricevono lo stesso id persistente.
size_old = '"size": out.stat().st_size, "category": "Report installazione",'
size_new = '"size": out.stat().st_size, "gridfs_id": gridfs_id, "storage": "gridfs", "category": "Report installazione",'
if inst.count(size_new) < 2:
    if inst.count(size_old) != 2:
        raise RuntimeError("R78: metadati documenti report installazione non trovati")
    inst = inst.replace(size_old, size_new, 2)

# Elimina anche eventuali blob persistenti duplicati storici.
dup_anchor = '            await db.documents.delete_one({"id": dup.get("id")})\n'
if 'await persistent_files.delete_bytes(db, dup.get("gridfs_id"))' not in inst:
    inst = replace_once(
        inst,
        dup_anchor,
        '            await persistent_files.delete_bytes(db, dup.get("gridfs_id"))\n            await db.documents.delete_one({"id": dup.get("id")})\n',
        "pulizia duplicati GridFS",
    )

final_anchor = '            "report_installazione_document_id": doc_id,\n            "report_installazione_pdf_pages": pdf_pages,\n'
if '            "report_installazione_gridfs_id": gridfs_id,\n' not in inst:
    inst = replace_once(
        inst,
        final_anchor,
        '            "report_installazione_document_id": doc_id,\n            "report_installazione_gridfs_id": gridfs_id,\n            "report_installazione_pdf_pages": pdf_pages,\n',
        "persistenza id GridFS installazione",
    )

# Download e invio email: se il deploy ha perso la cache locale, ricostruiscila da GridFS.
old_doc_check = '''        doc = await db.documents.find_one({"id": doc_id})
        if not doc or not Path(doc.get("stored_path") or "").exists():
            raise HTTPException(404, "File report non disponibile")
'''
new_doc_check = '''        doc = await db.documents.find_one({"id": doc_id})
        if not doc:
            raise HTTPException(404, "File report non disponibile")
        report_path = Path(doc.get("stored_path") or "")
        if not report_path.exists() and doc.get("gridfs_id"):
            try:
                report_path = await persistent_files.ensure_local(db, doc.get("gridfs_id"), report_path)
            except FileNotFoundError:
                pass
        if not report_path.exists():
            raise HTTPException(404, "File report non disponibile")
'''
if inst.count(old_doc_check) < 2 and inst.count(new_doc_check) < 2:
    raise RuntimeError("R78: blocchi download/invio report installazione non trovati")
inst = inst.replace(old_doc_check, new_doc_check, 2)

inst_path.write_text(inst, encoding="utf-8")


# ---------------------------------------------------------------------------
# Report Tecnico standalone
# ---------------------------------------------------------------------------
free_path = ROOT / "routes" / "free_reports_routes.py"
free = free_path.read_text(encoding="utf-8")
if "import persistent_files" not in free:
    free = free.replace("from routes.installation_report_routes import ASSET_DIR, UPLOAD_ROOT, _render_pdf\n", "from routes.installation_report_routes import ASSET_DIR, UPLOAD_ROOT, _render_pdf\nimport persistent_files\n", 1)

free_render_anchor = '        _render_pdf(data, out, page_numbers=(2, 3) if pdf_pages == "2-3" else (1, 2, 3))\n\n        now = datetime.now(timezone.utc)\n'
if 'gridfs_id = await persistent_files.replace_bytes' not in free:
    free_render_new = '''        _render_pdf(data, out, page_numbers=(2, 3) if pdf_pages == "2-3" else (1, 2, 3))
        gridfs_id = await persistent_files.replace_bytes(
            db, existing.get("gridfs_id"), out.read_bytes(), filename, "application/pdf",
            metadata={"resource": "report_liberi", "record_id": report_id, "category": "Report installazione libero"},
        )

        now = datetime.now(timezone.utc)
'''
    free = replace_once(free, free_render_anchor, free_render_new, "salvataggio GridFS report standalone")

free_size_old = '                "size": out.stat().st_size,\n                "category": "Report installazione libero",\n'
free_size_new = '                "size": out.stat().st_size,\n                "gridfs_id": gridfs_id,\n                "storage": "gridfs",\n                "category": "Report installazione libero",\n'
if free.count(free_size_new) < 2:
    if free.count(free_size_old) != 2:
        raise RuntimeError("R78: metadati documenti report standalone non trovati")
    free = free.replace(free_size_old, free_size_new, 2)

free_update_anchor = '            "generated_document_id": doc_id,\n            "pdf_path": str(out),\n            "pdf_pages": pdf_pages,\n'
if '            "gridfs_id": gridfs_id,\n' not in free:
    free = replace_once(
        free,
        free_update_anchor,
        '            "generated_document_id": doc_id,\n            "gridfs_id": gridfs_id,\n            "pdf_path": str(out),\n            "pdf_pages": pdf_pages,\n',
        "persistenza id GridFS standalone",
    )

free_download_old = '''        path = Path(doc.get("pdf_path") or "")
        if not path.exists():
            raise HTTPException(404, "PDF non ancora generato")
'''
free_download_new = '''        path = Path(doc.get("pdf_path") or "")
        if not path.exists() and doc.get("gridfs_id"):
            try:
                path = await persistent_files.ensure_local(db, doc.get("gridfs_id"), path)
            except FileNotFoundError:
                pass
        if not path.exists():
            raise HTTPException(404, "PDF non ancora generato")
'''
if free_download_new not in free:
    free = replace_once(free, free_download_old, free_download_new, "ripristino PDF standalone")

free_delete_anchor = '        document_id = doc.get("generated_document_id")\n'
if '        await persistent_files.delete_bytes(db, doc.get("gridfs_id"))\n' not in free:
    free = replace_once(
        free,
        free_delete_anchor,
        '        await persistent_files.delete_bytes(db, doc.get("gridfs_id"))\n        document_id = doc.get("generated_document_id")\n',
        "cancellazione GridFS standalone",
    )

free_path.write_text(free, encoding="utf-8")

print("[R78] storage persistente GridFS applicato a documenti, foto e report; risorsa Lead rimossa dai documenti.")
