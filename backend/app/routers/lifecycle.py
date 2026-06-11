"""Lifecycle endpoints — Detect (UC6) preview + Move (UC7) on-demand trigger."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..db import get_db
from ..schemas import CandidateOut, RecommendationReport, ScanSummary
from ..services import ai_advisor, lifecycle_agent

router = APIRouter(prefix="/lifecycle", tags=["lifecycle"])


@router.get("/candidates", response_model=list[CandidateOut])
def list_candidates(db: Session = Depends(get_db)) -> list[CandidateOut]:
    """UC6 — preview datasets eligible for tier movement by policy."""
    return lifecycle_agent.candidates(db)


@router.get("/recommendations", response_model=RecommendationReport)
def recommendations(db: Session = Depends(get_db)) -> RecommendationReport:
    """Ask the AI advisor what it would do with every movable dataset (no moves)."""
    return lifecycle_agent.recommendations(db)


@router.post("/run", response_model=ScanSummary)
def run_scan(db: Session = Depends(get_db)) -> ScanSummary:
    """UC7 — let the AI advisor decide and execute the moves (manual trigger)."""
    return lifecycle_agent.scan(db)


@router.get("/ai-status", tags=["meta"])
def ai_status() -> dict:
    """Report whether the live AI advisor is active or the heuristic fallback."""
    available = ai_advisor.ai_available()
    return {
        "engine": "ai" if available else "heuristic",
        "model": settings.ai_model if available else None,
        "use_ai": settings.use_ai,
    }
