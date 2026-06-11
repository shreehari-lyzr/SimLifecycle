"""AI tiering advisor — the agentic decision layer.

This is what turns SimLifecycle from a rule engine into an AI storage manager.
For each movable dataset it weighs three signals — the **policy signal**, **how
critical the data is**, and the **cost/GB savings** of moving it — and decides
whether to keep it where it is or tier it down, with a natural-language rationale.

It uses Claude (Opus 4.8) with structured outputs. If no ``ANTHROPIC_API_KEY``
is configured (or the call fails), it falls back to a deterministic heuristic
that mirrors the same three-factor reasoning, so the prototype always runs and
the API/UX is identical either way.

Exempt datasets (critical flag / exceptions) are a hard guardrail and are
filtered out by the caller before they ever reach the advisor.
"""

from __future__ import annotations

import json
import logging
import os
from dataclasses import dataclass
from typing import Literal

from pydantic import BaseModel, Field

from ..config import settings
from ..models import Dataset, Exception as PolicyException, Policy, Tier
from ..schemas import RecommendationOut, RecommendationReport
from ..storage.backend import StorageBackend
from . import policy_engine

logger = logging.getLogger("simlifecycle.ai")

_GB = 1_000_000_000


# --------------------------------------------------------------------------- #
# Signal assembly                                                             #
# --------------------------------------------------------------------------- #
@dataclass
class _Signal:
    """The three-factor decision inputs for one dataset."""

    dataset: Dataset
    inactive_days: float
    policy_eligible: bool
    suggested_target: Tier | None
    policy_reason: str

    def monthly_cost(self, tier: Tier) -> float:
        return (self.dataset.size_bytes / _GB) * StorageBackend.cost_per_gb(tier)

    def savings_to(self, target: Tier | None) -> float:
        if target is None or target == self.dataset.tier:
            return 0.0
        return round(self.monthly_cost(self.dataset.tier) - self.monthly_cost(target), 2)

    def as_context(self) -> dict:
        """Compact JSON-able view handed to the LLM."""
        d = self.dataset
        return {
            "dataset_id": d.id,
            "name": d.name,
            "project": d.project,
            "current_tier": d.tier.value,
            "size_gb": round(d.size_bytes / _GB, 2),
            "inactive_days": round(self.inactive_days, 1),
            "criticality_score_0_100": d.criticality_score,
            "business_value": d.business_value,
            "data_classification": d.data_classification,
            "tags": d.tags,
            "description": d.description,
            "policy": {
                "eligible_for_move": self.policy_eligible,
                "suggested_target_tier": self.suggested_target.value if self.suggested_target else None,
                "reason": self.policy_reason,
            },
            "monthly_cost_by_tier_usd": {
                t.value: round(self.monthly_cost(t), 4) for t in Tier
            },
        }


def _build_signal(dataset: Dataset, policies: list[Policy], exceptions: list[PolicyException]) -> _Signal:
    decision = policy_engine.evaluate(dataset, policies, exceptions)
    return _Signal(
        dataset=dataset,
        inactive_days=policy_engine.inactive_days(dataset),
        policy_eligible=decision.eligible,
        suggested_target=decision.target_tier,
        policy_reason=decision.reason,
    )


# --------------------------------------------------------------------------- #
# LLM structured-output schema                                                #
# --------------------------------------------------------------------------- #
class _AIDecision(BaseModel):
    dataset_id: str
    action: Literal["keep", "move"]
    target_tier: Literal["hot", "warm", "cold"] | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    rationale: str


class _AIPlan(BaseModel):
    decisions: list[_AIDecision]


_SYSTEM_PROMPT = """You are the SimLifecycle Storage Manager — an autonomous agent \
that decides how simulation datasets should be tiered across Hot, Warm, and Cold \
storage to minimise cost while protecting fast access to data that matters.

Storage tiers (latency / cost tradeoff):
- hot:  low latency, most expensive per GB. For active, important data.
- warm: moderate latency, ~18x cheaper than hot. For inactive but still-relevant data.
- cold: high retrieval latency, ~57x cheaper than hot. For archival / rarely-needed data.

For each dataset you must weigh THREE factors and decide to "keep" it in its \
current tier or "move" it to a cheaper tier:
1. POLICY SIGNAL — whether inactivity thresholds make it eligible to move, and the \
   tier policy suggests. Treat this as a strong default, not an absolute command.
2. CRITICALITY — criticality_score (0-100), business_value, and data_classification. \
   High-criticality / high-value data should stay on faster tiers even when inactive; \
   the cost of a slow restore at a critical moment outweighs the storage savings.
3. COST/GB — the monthly_cost_by_tier and the savings a move would realise. Large, \
   low-value, deeply-inactive datasets are the best move candidates. When potential \
   savings are tiny, a move rarely justifies the added latency.

Guidance:
- If the policy says the dataset is NOT eligible (still active), keep it.
- Otherwise, balance the savings against criticality. You MAY move straight to cold \
  (skipping warm) for large, low-value, long-inactive data. You MAY override the \
  policy and keep a high-criticality dataset hot even though it is eligible to move.
- Every dataset you are given is already cleared for movement (no hard exemptions), \
  so the decision is purely the cost/criticality tradeoff.

Return a decision for EVERY dataset_id provided. Keep each rationale to one or two \
sentences that explicitly reference the factors that drove the call (e.g. the \
criticality score, the inactivity, and the dollar savings)."""


def _ai_decide(client, signals: list[_Signal]) -> dict[str, _AIDecision]:
    contexts = [s.as_context() for s in signals]
    user_content = (
        "Decide the tiering action for each of these datasets. "
        "Return one decision per dataset_id.\n\n"
        f"{json.dumps(contexts, indent=2)}"
    )
    response = client.messages.parse(
        model=settings.ai_model,
        max_tokens=8000,
        system=_SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_content}],
        output_format=_AIPlan,
    )
    plan = response.parsed_output
    if plan is None:
        raise ValueError("AI advisor returned no parseable plan")
    return {d.dataset_id: d for d in plan.decisions}


# --------------------------------------------------------------------------- #
# Deterministic fallback (mirrors the three-factor reasoning)                 #
# --------------------------------------------------------------------------- #
def _heuristic_decide(signals: list[_Signal]) -> dict[str, _AIDecision]:
    out: dict[str, _AIDecision] = {}
    for s in signals:
        d = s.dataset
        if not s.policy_eligible or s.suggested_target is None:
            out[d.id] = _AIDecision(
                dataset_id=d.id,
                action="keep",
                target_tier=None,
                confidence=0.9,
                rationale=(
                    f"Still within policy thresholds ({s.inactive_days:.0f}d inactive) — "
                    f"retained in {d.tier.value}."
                ),
            )
            continue

        target = s.suggested_target
        savings = s.savings_to(target)
        crit = d.criticality_score

        if crit >= 75:
            out[d.id] = _AIDecision(
                dataset_id=d.id,
                action="keep",
                target_tier=None,
                confidence=0.82,
                rationale=(
                    f"High criticality ({crit}/100, {d.business_value} business value) — "
                    f"kept in {d.tier.value} despite {s.inactive_days:.0f}d inactivity; a slow "
                    f"restore would outweigh the ${savings:.2f}/mo saving."
                ),
            )
        elif crit >= 55 and savings < 0.5:
            out[d.id] = _AIDecision(
                dataset_id=d.id,
                action="keep",
                target_tier=None,
                confidence=0.7,
                rationale=(
                    f"Moderate criticality ({crit}/100) and only ${savings:.2f}/mo savings — "
                    f"not worth the added latency."
                ),
            )
        else:
            out[d.id] = _AIDecision(
                dataset_id=d.id,
                action="move",
                target_tier=target.value,
                confidence=0.86,
                rationale=(
                    f"Inactive {s.inactive_days:.0f}d, low criticality ({crit}/100), "
                    f"${savings:.2f}/mo savings → tier down to {target.value}."
                ),
            )
    return out


# --------------------------------------------------------------------------- #
# Client                                                                      #
# --------------------------------------------------------------------------- #
def _get_client():
    """Return an Anthropic client, or None to signal heuristic fallback."""
    if not settings.use_ai:
        return None
    if not (os.environ.get("ANTHROPIC_API_KEY") or settings.anthropic_api_key):
        return None
    try:
        import anthropic
    except ImportError:
        logger.info("anthropic SDK not installed — using heuristic advisor")
        return None
    try:
        return anthropic.Anthropic(api_key=settings.anthropic_api_key or None)
    except Exception:  # noqa: BLE001
        logger.exception("Failed to construct Anthropic client — using heuristic advisor")
        return None


def ai_available() -> bool:
    return _get_client() is not None


# --------------------------------------------------------------------------- #
# Public entry point                                                          #
# --------------------------------------------------------------------------- #
def recommend(
    datasets: list[Dataset],
    policies: list[Policy],
    exceptions: list[PolicyException],
) -> RecommendationReport:
    """Produce a keep/move recommendation for each (non-exempt) dataset.

    ``datasets`` must already exclude hard-exempt datasets — those are never
    candidates for automated movement.
    """
    signals = [_build_signal(d, policies, exceptions) for d in datasets]
    by_id = {s.dataset.id: s for s in signals}

    client = _get_client()
    if client is not None:
        try:
            decisions = _ai_decide(client, signals)
            engine, model = "ai", settings.ai_model
        except Exception:  # noqa: BLE001 — never let an AI failure block tiering
            logger.exception("AI advisor failed — falling back to heuristic")
            decisions = _heuristic_decide(signals)
            engine, model = "heuristic", None
    else:
        decisions = _heuristic_decide(signals)
        engine, model = "heuristic", None

    recs: list[RecommendationOut] = []
    for ds_id, sig in by_id.items():
        dec = decisions.get(ds_id)
        if dec is None:
            # AI omitted this dataset — default to a safe keep.
            dec = _AIDecision(
                dataset_id=ds_id,
                action="keep",
                target_tier=None,
                confidence=0.5,
                rationale="No recommendation returned — retained by default.",
            )
        target = Tier(dec.target_tier) if (dec.action == "move" and dec.target_tier) else None
        recs.append(
            RecommendationOut(
                dataset_id=ds_id,
                name=sig.dataset.name,
                project=sig.dataset.project,
                current_tier=sig.dataset.tier,
                action=dec.action,
                target_tier=target,
                confidence=round(dec.confidence, 2),
                rationale=dec.rationale,
                inactive_days=round(sig.inactive_days, 1),
                criticality_score=sig.dataset.criticality_score,
                business_value=sig.dataset.business_value,
                policy_eligible=sig.policy_eligible,
                monthly_savings_usd=sig.savings_to(target),
            )
        )

    # Most actionable first: moves before keeps, larger savings first.
    recs.sort(key=lambda r: (r.action != "move", -r.monthly_savings_usd))
    return RecommendationReport(engine=engine, model=model, recommendations=recs)
