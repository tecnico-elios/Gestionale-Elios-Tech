from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field


class FreeField(BaseModel):
    model_config = ConfigDict(extra="ignore")
    label: str = Field(min_length=1, max_length=120)
    value: str = Field(default="", max_length=5000)


class FreeReportBody(BaseModel):
    model_config = ConfigDict(extra="ignore")
    title: str = Field(min_length=1, max_length=200)
    report_date: str = Field(default="", max_length=40)
    technician: str = Field(default="", max_length=160)
    notes: str = Field(default="", max_length=20000)
    fields: List[FreeField] = Field(default_factory=list, max_length=100)


def build_router(db, deps) -> APIRouter:
    router = APIRouter(prefix="/free-reports", tags=["free-reports"])

    def clean_fields(items: List[FreeField]) -> List[Dict[str, str]]:
        out: List[Dict[str, str]] = []
        for item in items or []:
            label = (item.label or "").strip()
            if not label:
                continue
            out.append({"label": label, "value": str(item.value or "").strip()})
        return out

    @router.get("")
    async def list_reports(current=Depends(deps.get_current_user)):
        docs = await db.free_technical_reports.find({}, {"_id": 0}).sort("updated_at", -1).to_list(length=5000)
        return {"items": docs, "count": len(docs)}

    @router.get("/{report_id}")
    async def get_report(report_id: str, current=Depends(deps.get_current_user)):
        doc = await db.free_technical_reports.find_one({"id": report_id}, {"_id": 0})
        if not doc:
            raise HTTPException(404, "Report non trovato")
        return doc

    @router.post("")
    async def create_report(body: FreeReportBody, current=Depends(deps.get_current_user)):
        now = datetime.now(timezone.utc).isoformat()
        display_name = (
            f"{current.get('first_name','')} {current.get('last_name','')}".strip()
            or current.get("username")
            or ""
        )
        doc = {
            "id": str(uuid.uuid4()),
            "title": body.title.strip(),
            "report_date": (body.report_date or "").strip(),
            "technician": (body.technician or "").strip() or display_name,
            "notes": (body.notes or "").strip(),
            "fields": clean_fields(body.fields),
            "created_by": str(current.get("username") or ""),
            "created_by_name": display_name,
            "created_at": now,
            "updated_at": now,
            "source": "free_technical_report",
            "linked_client_id": None,
            "linked_job_id": None,
            "linked_installation_id": None,
        }
        await db.free_technical_reports.insert_one(doc)
        doc.pop("_id", None)
        return doc

    @router.put("/{report_id}")
    async def update_report(report_id: str, body: FreeReportBody, current=Depends(deps.get_current_user)):
        existing = await db.free_technical_reports.find_one({"id": report_id})
        if not existing:
            raise HTTPException(404, "Report non trovato")
        update = {
            "title": body.title.strip(),
            "report_date": (body.report_date or "").strip(),
            "technician": (body.technician or "").strip(),
            "notes": (body.notes or "").strip(),
            "fields": clean_fields(body.fields),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "updated_by": str(current.get("username") or ""),
        }
        await db.free_technical_reports.update_one({"id": report_id}, {"$set": update})
        doc = await db.free_technical_reports.find_one({"id": report_id}, {"_id": 0})
        return doc

    @router.delete("/{report_id}")
    async def delete_report(report_id: str, current=Depends(deps.get_current_user)):
        result = await db.free_technical_reports.delete_one({"id": report_id})
        if result.deleted_count == 0:
            raise HTTPException(404, "Report non trovato")
        return {"ok": True, "id": report_id}

    return router
