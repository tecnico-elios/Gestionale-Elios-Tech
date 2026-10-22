"""Gestione documentale locale del Gestionale Elios Tech.

I file vengono salvati sul server locale in backend/uploads e i metadati in MongoDB.
Nessuna dipendenza da Notion. Ogni documento è collegato a una risorsa/record.
"""
from __future__ import annotations

import os
import re
import uuid
import secrets
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

import auth as auth_mod
import persistent_files

MAX_FILE_SIZE = 25 * 1024 * 1024  # 25 MB
UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"
UPLOAD_ROOT.mkdir(parents=True, exist_ok=True)

RESOURCE_MAP = {
    "clienti": ("crm_clienti", "ordini_clienti"),
    "contatti": ("crm_contatti", "ordini_clienti"),
    "sedi": ("crm_sedi", "ordini_clienti"),
    "sopralluoghi": ("crm_sopralluoghi", "sopralluoghi"),
    "preventivi": ("crm_preventivi", "preventivi"),
    "ordini-clienti": ("crm_ordini_clienti", "ordini_clienti"),
    "commesse": ("commesse", "commesse"),
    "installazioni": ("crm_installazioni", "installazioni"),
    "assistenza": ("crm_assistenza", "assistenza"),
}


def _clean_name(name: str) -> str:
    base = os.path.basename(name or "documento")
    base = re.sub(r"[^A-Za-z0-9._() -]+", "_", base).strip(" .")
    return base[:180] or "documento"


def _public(doc):
    return {
        "id": doc.get("id"),
        "resource": doc.get("resource"),
        "record_id": doc.get("record_id"),
        "filename": doc.get("filename"),
        "content_type": doc.get("content_type"),
        "size": doc.get("size", 0),
        "category": doc.get("category") or "Documento",
        "note": doc.get("note") or "",
        "created_at": doc.get("created_at"),
        "created_by": doc.get("created_by"),
        "is_image": str(doc.get("content_type") or "").startswith("image/"),
    }


def build_router(db, deps: auth_mod.AuthDependencies) -> APIRouter:
    router = APIRouter(prefix="/files", tags=["documents"])

    async def _check(resource: str, record_id: str, current, action: str = "view"):
        cfg = RESOURCE_MAP.get(resource)
        if not cfg:
            raise HTTPException(404, "Risorsa documentale non valida")
        collection_name, module = cfg
        if not auth_mod.has_permission(current, module, action):
            raise HTTPException(403, "Non hai il permesso per questa operazione")
        record = await db[collection_name].find_one({"id": record_id})
        if not record:
            raise HTTPException(404, "Record collegato non trovato")
        if resource == "installazioni" and not (current.get("role") == auth_mod.ROLE_ADMIN or auth_mod.is_master_user(current) or auth_mod.has_permission(current, "installazioni", "view_all")):
            uid = str(current.get("_id") or current.get("id") or "")
            assigned_id = str(record.get("tecnico_user_id") or "")
            assigned_name = str(record.get("tecnico") or "").strip().lower()
            aliases = {str(current.get(k) or "").strip().lower() for k in ("username", "full_name", "email")}
            aliases.discard("")
            if not ((uid and assigned_id == uid) or (assigned_name and assigned_name in aliases)):
                raise HTTPException(403, "Questa installazione non è assegnata al tuo utente")
        return record

    # Le rotte statiche devono precedere /{resource}/{record_id}.
    @router.post("/open-ticket/{document_id}")
    async def create_open_ticket(document_id: str, current=Depends(deps.require_password_current)):
        """Genera un ticket temporaneo per aprire il file direttamente nel browser.

        In questo modo PDF e immagini vengono streammati dal server e non devono essere
        scaricati interamente da Axios prima di comparire a schermo.
        """
        doc = await db.documents.find_one({"id": document_id})
        if not doc:
            raise HTTPException(404, "Documento non trovato")
        await _check(doc.get("resource"), doc.get("record_id"), current, "view")
        token = secrets.token_urlsafe(32)
        expires_at = datetime.now(timezone.utc) + timedelta(minutes=2)
        await db.file_open_tickets.insert_one({
            "token": token, "document_id": document_id, "expires_at": expires_at,
            "created_by": current.get("username"),
        })
        return {"ticket": token, "expires_in": 120}

    @router.get("/open/{ticket}")
    async def open_by_ticket(ticket: str):
        now = datetime.now(timezone.utc)
        row = await db.file_open_tickets.find_one({"token": ticket, "expires_at": {"$gt": now}})
        if not row:
            raise HTTPException(401, "Link documento scaduto o non valido")
        doc = await db.documents.find_one({"id": row.get("document_id")})
        if not doc:
            raise HTTPException(404, "Documento non trovato")
        path = Path(doc.get("stored_path") or "")
        if not path.exists() and doc.get("gridfs_id"):
            try:
                path = await persistent_files.ensure_local(db, doc.get("gridfs_id"), path)
            except FileNotFoundError:
                pass
        if not path.exists():
            raise HTTPException(404, "File non disponibile sul server")
        # Il ticket resta valido per 2 minuti: permette al browser di effettuare richieste
        # Range aggiuntive (tipiche dei visualizzatori PDF) senza dover rigenerare il link.
        safe_name = _clean_name(doc.get("filename") or path.name).replace('"', '')
        return FileResponse(
            path,
            media_type=doc.get("content_type") or "application/octet-stream",
            headers={
                "Content-Disposition": f'inline; filename="{safe_name}"',
                "Cache-Control": "private, max-age=120",
            },
        )

    @router.get("/download/{document_id}")
    async def download(document_id: str, current=Depends(deps.require_password_current)):
        doc = await db.documents.find_one({"id": document_id})
        if not doc:
            raise HTTPException(404, "Documento non trovato")
        await _check(doc.get("resource"), doc.get("record_id"), current, "view")
        path = Path(doc.get("stored_path") or "")
        if not path.exists() and doc.get("gridfs_id"):
            try:
                path = await persistent_files.ensure_local(db, doc.get("gridfs_id"), path)
            except FileNotFoundError:
                pass
        if not path.exists():
            raise HTTPException(404, "File non disponibile sul server")
        return FileResponse(
            path,
            media_type=doc.get("content_type") or "application/octet-stream",
            filename=doc.get("filename") or path.name,
        )

    @router.delete("/document/{document_id}")
    async def delete(document_id: str, current=Depends(deps.require_password_current)):
        doc = await db.documents.find_one({"id": document_id})
        if not doc:
            raise HTTPException(404, "Documento non trovato")
        await _check(doc.get("resource"), doc.get("record_id"), current, "delete")
        path = Path(doc.get("stored_path") or "")
        await persistent_files.delete_bytes(db, doc.get("gridfs_id"))
        await db.documents.delete_one({"id": document_id})
        if path.exists():
            try:
                path.unlink()
            except OSError:
                pass
        return {"ok": True}

    @router.get("/{resource}/{record_id}")
    async def list_files(resource: str, record_id: str, current=Depends(deps.require_password_current)):
        await _check(resource, record_id, current, "view")
        docs = await db.documents.find({"resource": resource, "record_id": record_id}).sort("created_at", -1).to_list(length=500)
        return {"items": [_public(x) for x in docs], "count": len(docs)}

    @router.post("/{resource}/{record_id}")
    async def upload_file(
        resource: str,
        record_id: str,
        file: UploadFile = File(...),
        category: str = Form(default="Documento"),
        note: str = Form(default=""),
        current=Depends(deps.require_password_current),
    ):
        await _check(resource, record_id, current, "edit")
        if resource == "installazioni" and current.get("role") == auth_mod.ROLE_TECNICO:
            allowed_categories = {"Report fotografico", "Report installazione", "Altro"}
            if (category or "") not in allowed_categories:
                raise HTTPException(403, "Per il tecnico sono disponibili solo Report fotografico, Report installazione e Altro")
        filename = _clean_name(file.filename or "documento")
        ext = Path(filename).suffix[:12]
        doc_id = str(uuid.uuid4())
        folder = UPLOAD_ROOT / resource / record_id
        folder.mkdir(parents=True, exist_ok=True)
        stored = folder / f"{doc_id}{ext}"
        total = 0
        try:
            with stored.open("wb") as out:
                while True:
                    chunk = await file.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_FILE_SIZE:
                        raise HTTPException(413, "File troppo grande: massimo 25 MB")
                    out.write(chunk)
        except Exception:
            if stored.exists():
                stored.unlink(missing_ok=True)
            raise
        try:
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
            "resource": resource,
            "record_id": record_id,
            "filename": filename,
            "stored_path": str(stored),
            "gridfs_id": gridfs_id,
            "storage": "gridfs",
            "content_type": file.content_type or "application/octet-stream",
            "size": total,
            "category": (category or "Documento")[:80],
            "note": (note or "")[:1000],
            "created_at": now,
            "created_by": current.get("username"),
        }
        await db.documents.insert_one(doc)
        return _public(doc)

    return router
