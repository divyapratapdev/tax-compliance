"""
compliance_router.py
--------------------
All /api/v1/compliance/* endpoints.

Mount in main.py with:
    from app.compliance.compliance_router import router as compliance_router
    app.include_router(compliance_router)
"""

from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta
from typing import List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.database import get_db
from app.compliance.compliance_engine import ComplianceEngine
from app.compliance.models.compliance_models import ComplianceItem, ComplianceStatus

router = APIRouter(prefix="/api/v1/compliance", tags=["compliance"])
_engine = ComplianceEngine()


# ---------------------------------------------------------------------------
# Pydantic response schemas
# ---------------------------------------------------------------------------

class ComplianceItemOut(BaseModel):
    id: str
    client_id: int
    type: str
    due_date: datetime
    period_month: Optional[int]
    period_year: Optional[int]
    quarter: Optional[str]
    description: Optional[str]
    status: str
    filed_at: Optional[datetime]
    filed_by: Optional[str]
    reminder_7day_sent: bool
    reminder_1day_sent: bool
    escalation_sent: bool
    penalty_per_day: float
    penalty_description: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True


class OverdueItemOut(ComplianceItemOut):
    days_overdue: int
    estimated_penalty: float


class GenerateRequest(BaseModel):
    is_audit_case: bool = False
    agm_date: Optional[date] = None   # ISO date string, e.g. "2025-09-30"


class MarkFiledRequest(BaseModel):
    filed_by: Optional[str] = None


class GenerateResponse(BaseModel):
    client_id: int
    items_created: int
    message: str


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@router.post("/generate/{client_id}", response_model=GenerateResponse)
def generate_calendar(
    client_id: int,
    body: GenerateRequest = GenerateRequest(),
    db: Session = Depends(get_db),
):
    """
    Generate (or regenerate) the full compliance calendar for a client.
    Safe to call multiple times — deletes existing items first.
    """
    items = _engine.generate_calendar(
        client_id=client_id,
        db=db,
        is_audit_case=body.is_audit_case,
        agm_date=body.agm_date,
    )
    return GenerateResponse(
        client_id=client_id,
        items_created=len(items),
        message=f"Generated {len(items)} compliance items.",
    )


@router.get("/{client_id}", response_model=List[ComplianceItemOut])
def list_compliance_items(
    client_id: int,
    status: Optional[str]    = Query(None, description="pending | filed | missed"),
    type:   Optional[str]    = Query(None, description="GSTR1 | GSTR3B | TDS_RETURN | ADVANCE_TAX | ITR | ROC"),
    month:  Optional[int]    = Query(None, ge=1, le=12),
    year:   Optional[int]    = Query(None),
    db: Session = Depends(get_db),
):
    """List all compliance items for a client with optional filters."""
    q = db.query(ComplianceItem).filter(ComplianceItem.client_id == client_id)

    if status:
        q = q.filter(ComplianceItem.status == status)
    if type:
        q = q.filter(ComplianceItem.type == type)
    if month:
        q = q.filter(ComplianceItem.period_month == month)
    if year:
        q = q.filter(ComplianceItem.period_year == year)

    return q.order_by(ComplianceItem.due_date).all()


@router.post("/{item_id}/mark-filed", response_model=ComplianceItemOut)
def mark_filed(
    item_id: str,
    body: MarkFiledRequest = MarkFiledRequest(),
    db: Session = Depends(get_db),
):
    """CA marks a compliance item as filed."""
    item = db.query(ComplianceItem).filter(ComplianceItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Compliance item not found")
    if item.status == ComplianceStatus.FILED:
        raise HTTPException(status_code=400, detail="Already marked as filed")

    item.status   = ComplianceStatus.FILED.value
    item.filed_at = datetime.utcnow()
    item.filed_by = body.filed_by
    db.commit()
    db.refresh(item)
    return item


@router.get("/{client_id}/overdue", response_model=List[OverdueItemOut])
def get_overdue(
    client_id: int,
    db: Session = Depends(get_db),
):
    """Return all missed/overdue items with days overdue and estimated penalty."""
    now = datetime.utcnow()
    items = (
        db.query(ComplianceItem)
        .filter(
            ComplianceItem.client_id == client_id,
            ComplianceItem.status    == ComplianceStatus.MISSED.value,
        )
        .order_by(ComplianceItem.due_date)
        .all()
    )

    result = []
    for item in items:
        days_overdue      = max((now - item.due_date).days, 1)
        estimated_penalty = item.penalty_per_day * days_overdue if item.penalty_per_day else 0
        out = OverdueItemOut(
            **ComplianceItemOut.model_validate(item).model_dump(),
            days_overdue=days_overdue,
            estimated_penalty=estimated_penalty,
        )
        result.append(out)
    return result


@router.get("/{client_id}/upcoming", response_model=List[ComplianceItemOut])
def get_upcoming(
    client_id: int,
    days: int = Query(7, ge=1, le=90, description="Look-ahead window in days"),
    db: Session = Depends(get_db),
):
    """Return pending items due within the next N days."""
    now     = datetime.utcnow()
    cutoff  = now + timedelta(days=days)
    items   = (
        db.query(ComplianceItem)
        .filter(
            ComplianceItem.client_id == client_id,
            ComplianceItem.status    == ComplianceStatus.PENDING.value,
            ComplianceItem.due_date  >= now,
            ComplianceItem.due_date  <= cutoff,
        )
        .order_by(ComplianceItem.due_date)
        .all()
    )
    return items
