"""Backup locale del Gestionale Elios Tech.

Crea un archivio ZIP con tutte le collection MongoDB e gli allegati presenti
in backend/uploads. Rotta riservata agli Admin.
"""
from __future__ import annotations

import json
import os
import tempfile
import zipfile
from datetime import datetime, timezone
from pathlib import Path

from bson import json_util
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

import auth as auth_mod

UPLOAD_ROOT = Path(__file__).resolve().parent.parent / "uploads"


def build_router(db, deps: auth_mod.AuthDependencies) -> APIRouter:
    router = APIRouter(prefix="/admin/backup", tags=["backup"])

    @router.get("/download")
    async def download_backup(current=Depends(deps.require_admin)):
        stamp = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")
        fd, tmp_path = tempfile.mkstemp(prefix="elios_backup_", suffix=".zip")
        os.close(fd)
        try:
            collections = await db.list_collection_names()
            manifest = {
                "app": "Gestionale Elios Tech",
                "format": 1,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "created_by": current.get("username"),
                "database": db.name,
                "collections": sorted(collections),
                "includes_uploads": UPLOAD_ROOT.exists(),
            }
            with zipfile.ZipFile(tmp_path, "w", compression=zipfile.ZIP_DEFLATED, allowZip64=True) as zf:
                zf.writestr("manifest.json", json.dumps(manifest, ensure_ascii=False, indent=2).encode("utf-8"))
                for collection_name in sorted(collections):
                    # JSON Lines: scalabile e conserva ObjectId/date tramite Extended JSON BSON.
                    with zf.open(f"database/{collection_name}.jsonl", "w") as out:
                        async for doc in db[collection_name].find({}):
                            line = json_util.dumps(doc, ensure_ascii=False) + "\n"
                            out.write(line.encode("utf-8"))
                if UPLOAD_ROOT.exists():
                    for file_path in UPLOAD_ROOT.rglob("*"):
                        if file_path.is_file():
                            rel = file_path.relative_to(UPLOAD_ROOT)
                            zf.write(file_path, f"uploads/{rel.as_posix()}")
            filename = f"Gestionale_Elios_Tech_backup_{stamp}.zip"
            return FileResponse(
                tmp_path,
                media_type="application/zip",
                filename=filename,
                background=BackgroundTask(lambda: os.path.exists(tmp_path) and os.remove(tmp_path)),
            )
        except Exception as exc:
            try:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)
            except OSError:
                pass
            raise HTTPException(500, f"Impossibile creare il backup: {exc}")

    return router
