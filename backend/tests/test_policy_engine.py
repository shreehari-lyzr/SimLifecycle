"""Unit tests for the deterministic policy engine (pure, no DB/IO)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from app.config import settings
from app.models import Dataset, Exception as PolicyException, Policy, Tier
from app.services import policy_engine

NOW = datetime(2026, 1, 1, tzinfo=timezone.utc)


def _dataset(tier: Tier, sim_days_inactive: float, *, critical: bool = False, project="P") -> Dataset:
    last = NOW - timedelta(seconds=sim_days_inactive * settings.time_unit_seconds)
    return Dataset(
        id=f"d-{tier.value}-{sim_days_inactive}",
        name="ds",
        project=project,
        owner="o",
        tier=tier,
        size_bytes=1,
        last_accessed_at=last,
        is_critical=critical,
    )


HOT_TO_WARM = Policy(name="h2w", source_tier=Tier.hot, target_tier=Tier.warm,
                     inactivity_threshold_days=30, enabled=True, priority=10)
WARM_TO_COLD = Policy(name="w2c", source_tier=Tier.warm, target_tier=Tier.cold,
                      inactivity_threshold_days=90, enabled=True, priority=20)
POLICIES = [HOT_TO_WARM, WARM_TO_COLD]


def test_active_hot_dataset_not_moved():
    d = _dataset(Tier.hot, 5)
    decision = policy_engine.evaluate(d, POLICIES, [], now=NOW)
    assert decision.eligible is False
    assert decision.target_tier is None


def test_inactive_hot_moves_to_warm():
    d = _dataset(Tier.hot, 31)
    decision = policy_engine.evaluate(d, POLICIES, [], now=NOW)
    assert decision.eligible is True
    assert decision.target_tier is Tier.warm


def test_threshold_boundary_exactly_30_days_triggers():
    d = _dataset(Tier.hot, 30)
    decision = policy_engine.evaluate(d, POLICIES, [], now=NOW)
    assert decision.eligible is True  # >= threshold


def test_warm_moves_to_cold_after_90():
    d = _dataset(Tier.warm, 95)
    decision = policy_engine.evaluate(d, POLICIES, [], now=NOW)
    assert decision.eligible is True
    assert decision.target_tier is Tier.cold


def test_critical_dataset_is_exempt():
    d = _dataset(Tier.hot, 500, critical=True)
    decision = policy_engine.evaluate(d, POLICIES, [], now=NOW)
    assert decision.eligible is False


def test_project_exception_is_exempt():
    d = _dataset(Tier.hot, 500, project="Durability")
    exc = [PolicyException(project="Durability", reason="regulatory")]
    decision = policy_engine.evaluate(d, POLICIES, exc, now=NOW)
    assert decision.eligible is False


def test_disabled_policy_ignored():
    disabled = Policy(name="off", source_tier=Tier.hot, target_tier=Tier.warm,
                      inactivity_threshold_days=30, enabled=False, priority=1)
    d = _dataset(Tier.hot, 100)
    decision = policy_engine.evaluate(d, [disabled], [], now=NOW)
    assert decision.eligible is False
