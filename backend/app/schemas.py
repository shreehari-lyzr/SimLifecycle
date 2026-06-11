"""Pydantic request/response schemas (API contract)."""

from __future__ import annotations

from typing import Optional

from datetime import datetime

from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from .models import EventType, RestoreStatus, Tier


# ---------------------------------------------------------------- Datasets
class DatasetCreate(BaseModel):
    name: str
    project: str
    owner: str
    model_ref: str = ""
    run_config: dict = Field(default_factory=dict)
    size_bytes: int = Field(default=1_000_000_000, ge=0)  # default ~1 GB
    # Rich metadata consumed by the AI tiering advisor.
    criticality_score: int = Field(default=50, ge=0, le=100)
    data_classification: Literal["public", "internal", "confidential", "restricted"] = "internal"
    business_value: Literal["low", "medium", "high"] = "medium"
    tags: list[str] = Field(default_factory=list)
    description: str = ""


class DatasetAccess(BaseModel):
    op_type: str = Field(default="read", pattern="^(read|write)$")
    user: str = ""


class DatasetOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    name: str
    project: str
    owner: str
    model_ref: str
    run_config: dict
    size_bytes: int
    tier: Tier
    physical_path: str
    created_at: datetime
    last_accessed_at: datetime
    access_count: int
    is_critical: bool
    restore_status: RestoreStatus
    criticality_score: int
    data_classification: str
    business_value: str
    tags: list[str]
    description: str
    # Computed: why (if at all) this dataset is exempt from automated movement.
    is_exempt: bool = False
    exempt_reasons: list[str] = Field(default_factory=list)


class AccessResult(BaseModel):
    dataset: DatasetOut
    latency_ms: int
    note: str


class RestoreResult(BaseModel):
    dataset: DatasetOut
    restored_from: Optional[Tier]
    note: str


# ---------------------------------------------------------------- Policies
class PolicyBase(BaseModel):
    name: str
    source_tier: Tier
    target_tier: Tier
    inactivity_threshold_days: int = Field(ge=0)
    enabled: bool = True
    priority: int = 100


class PolicyCreate(PolicyBase):
    pass


class PolicyUpdate(BaseModel):
    name: Optional[str] = None
    source_tier: Optional[Tier] = None
    target_tier: Optional[Tier] = None
    inactivity_threshold_days: Optional[int] = Field(default=None, ge=0)
    enabled: Optional[bool] = None
    priority: Optional[int] = None


class PolicyOut(PolicyBase):
    model_config = ConfigDict(from_attributes=True)
    id: int


# ---------------------------------------------------------------- Exceptions
class ExceptionCreate(BaseModel):
    dataset_id: Optional[str] = None
    project: Optional[str] = None
    reason: str = ""


class ExceptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dataset_id: Optional[str]
    project: Optional[str]
    reason: str
    created_at: datetime


# ---------------------------------------------------------------- Lifecycle
class CandidateOut(BaseModel):
    dataset_id: str
    name: str
    current_tier: Tier
    target_tier: Tier
    inactive_days: float
    policy_name: str


class RecommendationOut(BaseModel):
    """An AI advisor recommendation for a single dataset (keep or move)."""

    dataset_id: str
    name: str
    project: str
    current_tier: Tier
    action: Literal["keep", "move"]
    target_tier: Tier | None
    confidence: float
    rationale: str
    # The signals the decision was based on, surfaced for transparency.
    inactive_days: float
    criticality_score: int
    business_value: str
    policy_eligible: bool
    monthly_savings_usd: float


class RecommendationReport(BaseModel):
    engine: Literal["ai", "heuristic"]
    model: str | None
    recommendations: list[RecommendationOut]


class ScanSummary(BaseModel):
    scanned: int
    moved: int
    skipped_exception: int
    bytes_reclaimed_from_hot: int
    engine: Literal["ai", "heuristic"]
    moves: list[dict]


# ---------------------------------------------------------------- Events / Dashboard
class EventOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    dataset_id: str
    event_type: EventType
    from_tier: Optional[Tier]
    to_tier: Optional[Tier]
    timestamp: datetime
    details: str


class TierStats(BaseModel):
    tier: Tier
    dataset_count: int
    total_bytes: int
    monthly_cost_usd: float


class DashboardMetrics(BaseModel):
    tiers: list[TierStats]
    total_datasets: int
    total_bytes: int
    hot_bytes_reclaimed: int
    monthly_cost_usd: float
    baseline_all_hot_cost_usd: float
    monthly_savings_usd: float
    savings_pct: float
    compliance_pct: float
    noncompliant_count: int
