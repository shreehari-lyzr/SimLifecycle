"""Lifecycle agent — Detect Inactive (UC6) + Move Across Tiers (UC7).

Brings together the policy engine (decision) and the catalog service (execution).
A single ``scan`` both detects eligible datasets and performs the moves, recording
audit events along the way. ``candidates`` is the read-only preview counterpart.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Dataset, Exception as PolicyException, Policy, Tier
from ..schemas import CandidateOut, ScanSummary
from . import catalog, policy_engine


def _load_rules(db: Session) -> tuple[list[Policy], list[PolicyException]]:
    policies = list(db.scalars(select(Policy)).all())
    exceptions = list(db.scalars(select(PolicyException)).all())
    return policies, exceptions


def candidates(db: Session) -> list[CandidateOut]:
    """UC6 — preview datasets currently eligible for movement (no side effects)."""
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


def scan(db: Session) -> ScanSummary:
    """UC6 + UC7 — evaluate every dataset and move those that are eligible.

    Runs from both the manual trigger endpoint and the background scheduler, so
    it must be safe to call concurrently with request handlers (each gets its
    own session). Returns a summary suitable for logging and the API response.
    """
    policies, exceptions = _load_rules(db)

    scanned = 0
    moved = 0
    skipped_exception = 0
    bytes_reclaimed_from_hot = 0
    moves: list[dict] = []

    for dataset in db.scalars(select(Dataset)).all():
        scanned += 1
        decision = policy_engine.evaluate(dataset, policies, exceptions)

        if not decision.eligible or decision.target_tier is None:
            if policy_engine.is_exempt(dataset, exceptions):
                skipped_exception += 1
            continue

        from_tier = dataset.tier
        catalog.move_dataset(db, dataset, decision.target_tier, reason=decision.reason)
        moved += 1
        if from_tier == Tier.hot:
            bytes_reclaimed_from_hot += dataset.size_bytes
        moves.append(
            {
                "dataset_id": dataset.id,
                "name": dataset.name,
                "from_tier": from_tier.value,
                "to_tier": decision.target_tier.value,
                "inactive_days": round(decision.inactive_days, 2),
                "policy": decision.policy_name,
            }
        )

    return ScanSummary(
        scanned=scanned,
        moved=moved,
        skipped_exception=skipped_exception,
        bytes_reclaimed_from_hot=bytes_reclaimed_from_hot,
        moves=moves,
    )
