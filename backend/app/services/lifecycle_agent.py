"""Lifecycle agent — Detect Inactive (UC6) + Move Across Tiers (UC7).

Brings together the policy engine (decision) and the catalog service (execution).
A single ``scan`` both detects eligible datasets and performs the moves, recording
audit events along the way. ``candidates`` is the read-only preview counterpart.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Dataset, Exception as PolicyException, Policy, Tier
from ..schemas import CandidateOut, RecommendationReport, ScanSummary
from . import ai_advisor, catalog, policy_engine


def _load_rules(db: Session) -> tuple[list[Policy], list[PolicyException]]:
    policies = list(db.scalars(select(Policy)).all())
    exceptions = list(db.scalars(select(PolicyException)).all())
    return policies, exceptions


def _movable(db: Session, exceptions: list[PolicyException]) -> list[Dataset]:
    """All datasets that are not hard-exempt (the AI advisor's candidate set)."""
    return [
        d
        for d in db.scalars(select(Dataset)).all()
        if not policy_engine.is_exempt(d, exceptions)
    ]


def candidates(db: Session) -> list[CandidateOut]:
    """UC6 — deterministic preview of datasets eligible by policy (no side effects)."""
    policies, exceptions = _load_rules(db)
    out: list[CandidateOut] = []
    for dataset in db.scalars(select(Dataset)).all():
        decision = policy_engine.evaluate(dataset, policies, exceptions)
        if decision.eligible and decision.target_tier is not None:
            out.append(
                CandidateOut(
                    dataset_id=dataset.id,
                    name=dataset.name,
                    current_tier=dataset.tier,
                    target_tier=decision.target_tier,
                    inactive_days=round(decision.inactive_days, 2),
                    policy_name=decision.policy_name or "",
                )
            )
    return out


def recommendations(db: Session) -> RecommendationReport:
    """Ask the AI advisor what it would do with every movable dataset (no moves)."""
    policies, exceptions = _load_rules(db)
    return ai_advisor.recommend(_movable(db, exceptions), policies, exceptions)


def scan(db: Session) -> ScanSummary:
    """UC6 + UC7 — let the AI advisor decide, then execute the moves it recommends.

    The advisor weighs policy + criticality + cost/GB for every non-exempt
    dataset; exempt datasets are never offered to it. Runs from both the manual
    trigger and the background scheduler (each gets its own session). The AI's
    rationale is recorded on each move event for the audit trail.
    """
    policies, exceptions = _load_rules(db)
    all_datasets = list(db.scalars(select(Dataset)).all())
    movable = [d for d in all_datasets if not policy_engine.is_exempt(d, exceptions)]
    skipped_exception = len(all_datasets) - len(movable)

    report = ai_advisor.recommend(movable, policies, exceptions)
    by_id = {d.id: d for d in movable}

    moved = 0
    bytes_reclaimed_from_hot = 0
    moves: list[dict] = []

    for rec in report.recommendations:
        if rec.action != "move" or rec.target_tier is None:
            continue
        dataset = by_id.get(rec.dataset_id)
        if dataset is None or rec.target_tier == dataset.tier:
            continue

        from_tier = dataset.tier
        catalog.move_dataset(
            db,
            dataset,
            rec.target_tier,
            reason=f"AI ({report.engine}): {rec.rationale}",
        )
        moved += 1
        if from_tier == Tier.hot:
            bytes_reclaimed_from_hot += dataset.size_bytes
        moves.append(
            {
                "dataset_id": dataset.id,
                "name": dataset.name,
                "from_tier": from_tier.value,
                "to_tier": rec.target_tier.value,
                "inactive_days": rec.inactive_days,
                "criticality_score": rec.criticality_score,
                "monthly_savings_usd": rec.monthly_savings_usd,
                "confidence": rec.confidence,
                "rationale": rec.rationale,
            }
        )

    return ScanSummary(
        scanned=len(all_datasets),
        moved=moved,
        skipped_exception=skipped_exception,
        bytes_reclaimed_from_hot=bytes_reclaimed_from_hot,
        engine=report.engine,
        moves=moves,
    )
