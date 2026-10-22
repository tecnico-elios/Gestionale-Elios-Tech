from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from routes.installation_report_routes import ASSET_DIR, UPLOAD_ROOT, _render_pdf
import persistent_files


class FreeReportBody(BaseModel):
    model_config = {"extra": "allow"}
    data: Dict[str, Any] = Field(default_factory=dict)
    pdf_pages: str = "all"


def _display_title(data: Dict[str, Any]) -> str:
    cliente = str(data.get("cliente") or "").strip()
    data_report = str(data.get("data") or "").strip()
    if cliente and data_report:
        return f"{cliente} · {data_report}"
    if cliente:
        return cliente
    if data_report:
        return f"Report pre e post installazione · {data_report}"
    return "Report pre e post installazione"


def _normalize_pdf_pages(value: Any) -> str:
    return "2-3" if str(value or "").strip() == "2-3" else "all"


def build_router(db, deps) -> APIRouter:
    router = APIRouter(prefix="/free-reports", tags=["free-reports"])
    dep = deps.require_password_current

    @router.get("")
    async def list_reports(current=Depends(dep)):
        docs = await db.free_technical_reports.find({}, {"_id": 0}).sort("updated_at", -1).to_list(length=5000)
        return {"items": docs, "count": len(docs)}

    @router.get("/template")
    async def template(current=Depends(dep)):
        path = ASSET_DIR / "modello_originale.pdf"
        if not path.exists():
            raise HTTPException(404, "Modello report non disponibile")
        return FileResponse(path, media_type="application/pdf", filename="DOCUMENTO PRE E POST INSTALLAZIONE.pdf")

    @router.get("/{report_id}")
    async def get_report(report_id: str, current=Depends(dep)):
        doc = await db.free_technical_reports.find_one({"id": report_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Report non trovato")
        return {
            "id": doc.get("id"),
            "data": doc.get("data") or {},
            "generated_document_id": doc.get("generated_document_id"),
            "pdf_pages": doc.get("pdf_pages") or "all",
            "title": doc.get("title") or _display_title(doc.get("data") or {}),
        }

    @router.post("")
    async def create_report(body: FreeReportBody, current=Depends(dep)):
        now = datetime.now(timezone.utc)
        rid = str(uuid.uuid4())
        data = dict(body.data or {})
        doc = {
            "id": rid,
            "title": _display_title(data),
            "data": data,
            "pdf_pages": _normalize_pdf_pages(body.pdf_pages),
            "created_by": str(current.get("username") or ""),
            "created_at": now,
            "updated_at": now,
            "source": "standalone_installation_report",
            "linked_client_id": None,
            "linked_job_id": None,
            "linked_installation_id": None,
        }
        await db.free_technical_reports.insert_one(doc)
        return {"ok": True, "id": rid, "title": doc["title"], "data": data}

    @router.put("/{report_id}")
    async def update_report(report_id: str, body: FreeReportBody, current=Depends(dep)):
        existing = await db.free_technical_reports.find_one({"id": report_id})
        if not existing:
            raise HTTPException(404, "Report non trovato")
        data = dict(body.data or {})
        await db.free_technical_reports.update_one(
            {"id": report_id},
            {"$set": {
                "data": data,
                "title": _display_title(data),
                "pdf_pages": _normalize_pdf_pages(body.pdf_pages),
                "updated_at": datetime.now(timezone.utc),
                "updated_by": str(current.get("username") or ""),
            }},
        )
        return {"ok": True, "id": report_id, "title": _display_title(data), "data": data}

    @router.post("/{report_id}/generate")
    async def generate_report(report_id: str, body: FreeReportBody, current=Depends(dep)):
        existing = await db.free_technical_reports.find_one({"id": report_id})
        if not existing:
            raise HTTPException(404, "Report non trovato")
        data = {**(existing.get("data") or {}), **(body.data or {})}
        pdf_pages = _normalize_pdf_pages(body.pdf_pages)
        folder = UPLOAD_ROOT / "standalone" / report_id
        folder.mkdir(parents=True, exist_ok=True)
        filename = "Report_pre_post_installazione.pdf"
        out = folder / filename
        _render_pdf(data, out, page_numbers=(2, 3) if pdf_pages == "2-3" else (1, 2, 3))
        gridfs_id = await persistent_files.replace_bytes(
            db, existing.get("gridfs_id"), out.read_bytes(), filename, "application/pdf",
            metadata={"resource": "report_liberi", "record_id": report_id, "category": "Report installazione libero"},
        )

        now = datetime.now(timezone.utc)
        existing_id = existing.get("generated_document_id")
        existing_doc = await db.documents.find_one({"id": existing_id}) if existing_id else None
        if existing_doc:
            doc_id = existing_id
            old_path = Path(existing_doc.get("stored_path") or "")
            if old_path and old_path != out and old_path.exists():
                try:
                    old_path.unlink()
                except OSError:
                    pass
            await db.documents.update_one({"id": doc_id}, {"$set": {
                "filename": filename,
                "stored_path": str(out),
                "content_type": "application/pdf",
                "size": out.stat().st_size,
                "gridfs_id": gridfs_id,
                "storage": "gridfs",
                "category": "Report installazione libero",
                "note": "Report pre e post installazione, non collegato a installazione",
                "updated_at": now,
                "updated_by": current.get("username"),
            }})
            updated_existing = True
        else:
            doc_id = str(uuid.uuid4())
            await db.documents.insert_one({
                "id": doc_id,
                "resource": "report_liberi",
                "record_id": report_id,
                "filename": filename,
                "stored_path": str(out),
                "content_type": "application/pdf",
                "size": out.stat().st_size,
                "gridfs_id": gridfs_id,
                "storage": "gridfs",
                "category": "Report installazione libero",
                "note": "Report pre e post installazione, non collegato a installazione",
                "created_at": now,
                "created_by": current.get("username"),
            })
            updated_existing = False

        await db.free_technical_reports.update_one({"id": report_id}, {"$set": {
            "data": data,
            "title": _display_title(data),
            "generated_document_id": doc_id,
            "pdf_path": str(out),
            "pdf_pages": pdf_pages,
            "updated_at": now,
            "updated_by": str(current.get("username") or ""),
        }})
        return {"ok": True, "id": report_id, "document_id": doc_id, "updated_existing": updated_existing, "pdf_pages": pdf_pages}

    @router.get("/{report_id}/pdf")
    async def get_pdf(report_id: str, current=Depends(dep)):
        doc = await db.free_technical_reports.find_one({"id": report_id})
        if not doc:
            raise HTTPException(404, "Report non trovato")
        path = Path(doc.get("pdf_path") or "")
        if not path.exists() and doc.get("gridfs_id"):
            try:
                path = await persistent_files.ensure_local(db, doc.get("gridfs_id"), path)
            except FileNotFoundError:
                pass
        if not path.exists():
            raise HTTPException(404, "PDF non ancora generato")
        return FileResponse(path, media_type="application/pdf", filename="Report_pre_post_installazione.pdf")

    @router.delete("/{report_id}")
    async def delete_report(report_id: str, current=Depends(dep)):
        doc = await db.free_technical_reports.find_one({"id": report_id})
        if not doc:
            raise HTTPException(404, "Report non trovato")
        pdf_path = Path(doc.get("pdf_path") or "")
        if pdf_path.exists():
            try:
                pdf_path.unlink()
            except OSError:
                pass
        await persistent_files.delete_bytes(db, doc.get("gridfs_id"))
        document_id = doc.get("generated_document_id")
        if document_id:
            await db.documents.delete_one({"id": document_id})
        await db.free_technical_reports.delete_one({"id": report_id})
        return {"ok": True, "id": report_id}

    return router
