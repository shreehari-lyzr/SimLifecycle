"""Policy engine (UC4 + UC6).

Pure, deterministic evaluation of a dataset against the administrator-defined
policies and exception list. No I/O beyond reading policies/exceptions that the
caller passes in, which keeps it trivially unit-testable.

Inactivity is measured in "days", but one simulated day equals
``settings.time_unit_seconds`` real seconds — letting a 30-day threshold elapse
in 30 real seconds during a demo.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

from ..config import settings
from ..models import Dataset, Exception as PolicyException, Policy, Tier


@dataclass(frozen=True)
class Decision:
    """Result of evaluating one dataset."""

    dataset_id: str
    eligible: bool
    target_tier: Tier | None
    inactive_days: float
    policy_name: str | None
    reason: str


def inactive_days(dataset: Dataset, *, now: datetime | None = None) -> float:
    """Inactivity in simulated days = real_seconds_elapsed / time_unit_seconds."""
    now = now or datetime.now(timezone.utc)
    last = dataset.last_accessed_at
    if last.tzinfo is None:
        last = last.replace(tzinfo=timezone.utc)
    elapsed_seconds = (now - last).total_seconds()
    return max(0.0, elapsed_seconds / settings.time_unit_seconds)


def exemption_reasons(dataset: Dataset, exceptions: list[PolicyException]) -> list[str]:
    """All reasons ``dataset`` is currently exempt from automated movement.

    A dataset can be exempt for more than one independent reason (e.g. both
    flagged critical and covered by a project exception); clearing one does not
    necessarily make it movable. Returning the full list lets the UI explain
    exactly what is holding a dataset in place.
    """
    reasons: list[str] = []
    if dataset.is_critical:
        reasons.append("Marked critical")
    for exc in exceptions:
        if exc.dataset_id and exc.dataset_id == dataset.id:
            reasons.append(f"Dataset exception: {exc.reason or 'no reason given'}")
        elif exc.project and exc.project == dataset.project:
            reasons.append(f"Project '{exc.project}' exception: {exc.reason or 'no reason given'}")
    return reasons


def is_exempt(dataset: Dataset, exceptions: list[PolicyException]) -> bool:
    """A dataset is exempt if flagged critical or matched by an exception entry."""
    return bool(exemption_reasons(dataset, exceptions))


def evaluate(
    dataset: Dataset,
    policies: list[Policy],
    exceptions: list[PolicyException],
    *,
    now: datetime | None = None,
) -> Decision:
    """Decide whether ``dataset`` should move tiers right now.

    Among enabled policies whose ``source_tier`` matches the dataset's current
    tier and whose inactivity threshold is exceeded, the highest-priority one
    (lowest ``priority`` value, then largest threshold) wins.
    """
    days = inactive_days(dataset, now=now)

    if is_exempt(dataset, exceptions):
        return Decision(dataset.id, False, None, days, None, "Exempt (critical or exception)")

    applicable = [
        p
        for p in policies
        if p.enabled and p.source_tier == dataset.tier and days >= p.inactivity_threshold_days
    ]
    if not applicable:
        return Decision(dataset.id, False, None, days, None, "No matching policy / threshold not met")

    # Prefer lower priority value; tie-break on the larger threshold (most "earned").
    applicable.sort(key=lambda p: (p.priority, -p.inactivity_threshold_days))
    chosen = applicable[0]
    return Decision(
        dataset.id,
        True,
        chosen.target_tier,
        days,
        chosen.name,
        f"Inactive {days:.1f}d >= {chosen.inactivity_threshold_days}d "
        f"({chosen.source_tier.value}->{chosen.target_tier.value})",
    )
