"""Dashboard & reporting endpoints (UC5) + audit event feed (UC8)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import LifecycleEvent
from ..schemas import DashboardMetrics, EventOut
from ..services import metrics

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get("/metrics", response_model=DashboardMetrics)
def get_metrics(db: Session = Depends(get_db)) -> DashboardMetrics:
    """UC5 — utilisation, reclaimed capacity, cost savings, compliance."""
    return metrics.compute_metrics(db)


@router.get("/events", response_model=list[EventOut])
def get_events(
    db: Session = Depends(get_db), limit: int = Query(default=50, ge=1, le=500)
) -> list[EventOut]:
    """UC8 — recent lifecycle audit events (create/access/move/restore)."""
    rows = db.scalars(
        select(LifecycleEvent).order_by(LifecycleEvent.timestamp.desc()).limit(limit)
    ).all()
    return [EventOut.model_validate(r) for r in rows]
