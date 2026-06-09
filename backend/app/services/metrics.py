"""Metrics service (UC5 — Monitor Storage & Reports).

Aggregates the live catalog into the numbers the administrator dashboard needs:
tier distribution, monthly storage cost vs an all-hot baseline (the savings the
lifecycle automation has produced), reclaimed hot capacity, and a policy
compliance indicator.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import Dataset, Exception as PolicyException, Policy, Tier
from ..schemas import DashboardMetrics, TierStats
from ..storage.backend import StorageBackend
from . import policy_engine

_GB = 1_000_000_000


def _monthly_cost(tier: Tier, total_bytes: int) -> float:
    return (total_bytes / _GB) * StorageBackend.cost_per_gb(tier)


def compute_metrics(db: Session) -> DashboardMetrics:
    datasets = list(db.scalars(select(Dataset)).all())
    policies = list(db.scalars(select(Policy)).all())
    exceptions = list(db.scalars(select(PolicyException)).all())

    per_tier_bytes: dict[Tier, int] = {t: 0 for t in Tier}
    per_tier_count: dict[Tier, int] = {t: 0 for t in Tier}
    total_bytes = 0

    for d in datasets:
        per_tier_bytes[d.tier] += d.size_bytes
        per_tier_count[d.tier] += 1
        total_bytes += d.size_bytes

    tiers = [
        TierStats(
            tier=t,
            dataset_count=per_tier_count[t],
            total_bytes=per_tier_bytes[t],
            monthly_cost_usd=round(_monthly_cost(t, per_tier_bytes[t]), 2),
        )
        for t in Tier
    ]

    monthly_cost = sum(ts.monthly_cost_usd for ts in tiers)
    # Baseline: what it would cost if every dataset still lived in hot storage.
    baseline_all_hot = _monthly_cost(Tier.hot, total_bytes)
    savings = max(0.0, baseline_all_hot - monthly_cost)
    savings_pct = (savings / baseline_all_hot * 100) if baseline_all_hot else 0.0

    # Reclaimed hot capacity = bytes that policies have moved out of hot.
    hot_reclaimed = per_tier_bytes[Tier.warm] + per_tier_bytes[Tier.cold]

    # Compliance: a dataset is non-compliant if it currently sits in a tier the
    # policy engine says it should have already moved out of (i.e. an eligible
    # move is still pending). After a scan this should be ~100%.
    noncompliant = 0
    for d in datasets:
        decision = policy_engine.evaluate(d, policies, exceptions)
        if decision.eligible:
            noncompliant += 1
    total = len(datasets)
    compliance_pct = ((total - noncompliant) / total * 100) if total else 100.0

    return DashboardMetrics(
        tiers=tiers,
        total_datasets=total,
        total_bytes=total_bytes,
        hot_bytes_reclaimed=hot_reclaimed,
        monthly_cost_usd=round(monthly_cost, 2),
        baseline_all_hot_cost_usd=round(baseline_all_hot, 2),
        monthly_savings_usd=round(savings, 2),
        savings_pct=round(savings_pct, 1),
        compliance_pct=round(compliance_pct, 1),
        noncompliant_count=noncompliant,
    )
