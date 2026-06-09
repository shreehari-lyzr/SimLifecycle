"""Lifecycle endpoints — Detect (UC6) preview + Move (UC7) on-demand trigger."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..db import get_db
from ..schemas import CandidateOut, ScanSummary
from ..services import lifecycle_agent

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


@router.get("/candidates", response_model=list[CandidateOut])
def list_candidates(db: Session = Depends(get_db)) -> list[CandidateOut]:
    """UC6 — preview datasets eligible for tier movement right now."""
    return lifecycle_agent.candidates(db)


@router.post("/run", response_model=ScanSummary)
def run_scan(db: Session = Depends(get_db)) -> ScanSummary:
    """UC7 — trigger a lifecycle scan immediately (same logic as the scheduler)."""
    return lifecycle_agent.scan(db)
