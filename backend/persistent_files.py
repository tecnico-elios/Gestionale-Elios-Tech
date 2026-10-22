from __future__ import annotations

import os
import tempfile
from pathlib import Path
from typing import Any, Optional

from bson import ObjectId
from motor.motor_asyncio import AsyncIOMotorGridFSBucket

BUCKET_NAME = "elios_files"


def _bucket(db) -> AsyncIOMotorGridFSBucket:
    return AsyncIOMotorGridFSBucket(db, bucket_name=BUCKET_NAME)


def _object_id(value: Any) -> Optional[ObjectId]:
    if not value:
        return None
    try:
        return ObjectId(str(value))
    except Exception:
        return None


async def store_bytes(db, data: bytes, filename: str, content_type: str = "application/octet-stream", metadata: Optional[dict] = None) -> str:
    meta = {"content_type": content_type or "application/octet-stream", **(metadata or {})}
    file_id = await _bucket(db).upload_from_stream(filename or "file", data, metadata=meta)
    return str(file_id)


async def read_bytes(db, file_id: Any) -> bytes:
    oid = _object_id(file_id)
    if not oid:
        raise FileNotFoundError("Identificativo file persistente non valido")
    try:
        stream = await _bucket(db).open_download_stream(oid)
        return await stream.read()
    except Exception as exc:
        raise FileNotFoundError("File persistente non disponibile") from exc


async def delete_bytes(db, file_id: Any) -> None:
    oid = _object_id(file_id)
    if not oid:
        return
    try:
        await _bucket(db).delete(oid)
    except Exception:
        # La cancellazione applicativa non deve fallire se il blob era gia assente.
        pass


async def replace_bytes(db, old_file_id: Any, data: bytes, filename: str, content_type: str = "application/octet-stream", metadata: Optional[dict] = None) -> str:
    new_id = await store_bytes(db, data, filename, content_type, metadata)
    if old_file_id and str(old_file_id) != new_id:
        await delete_bytes(db, old_file_id)
    return new_id


async def ensure_local(db, file_id: Any, target: Any) -> Path:
    raw_target = str(target or "").strip()
    if not raw_target:
        raise FileNotFoundError("Percorso cache locale non disponibile")
    path = Path(raw_target)
    if path.exists():
        return path
    data = await read_bytes(db, file_id)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


async def materialize_temp(db, file_id: Any, suffix: str = "") -> Path:
    data = await read_bytes(db, file_id)
    fd, name = tempfile.mkstemp(prefix="elios-file-", suffix=suffix)
    with os.fdopen(fd, "wb") as out:
        out.write(data)
    return Path(name)
