"""ORM models for the SimLifecycle Agent.

The data model is deliberately small but complete enough to drive all 8 use
cases:

* ``Dataset``        — the logical catalog entry (single source of truth).
* ``AccessLog``      — every read/write, driving recency & frequency (UC2).
* ``Policy``         — administrator-defined tier transition rules (UC4).
* ``Exception``      — datasets/projects exempt from automated movement (UC4).
* ``LifecycleEvent`` — append-only audit trail of create/move/restore (UC8).
"""

from __future__ import annotations

import enum
from datetime import datetime, timezone

from sqlalchemy import JSON, Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Tier(str, enum.Enum):
    hot = "hot"
    warm = "warm"
    cold = "cold"


class RestoreStatus(str, enum.Enum):
    none = "none"
    restoring = "restoring"
    restored = "restored"


class EventType(str, enum.Enum):
    create = "create"
    access = "access"
    move = "move"
    restore = "restore"


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[str] = mapped_column(String(36), primary_key=True)
    name: Mapped[str] = mapped_column(String(255), index=True)
    project: Mapped[str] = mapped_column(String(255), index=True)
    owner: Mapped[str] = mapped_column(String(255))
    model_ref: Mapped[str] = mapped_column(String(255), default="")
    run_config: Mapped[dict] = mapped_column(JSON, default=dict)

    size_bytes: Mapped[int] = mapped_column(Integer, default=0)
    tier: Mapped[Tier] = mapped_column(Enum(Tier), default=Tier.hot, index=True)
    physical_path: Mapped[str] = mapped_column(String(1024), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    last_accessed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    access_count: Mapped[int] = mapped_column(Integer, default=0)

    is_critical: Mapped[bool] = mapped_column(Boolean, default=False)
    restore_status: Mapped[RestoreStatus] = mapped_column(
        Enum(RestoreStatus), default=RestoreStatus.none
    )

    events: Mapped[list["LifecycleEvent"]] = relationship(
        back_populates="dataset", cascade="all, delete-orphan"
    )


class AccessLog(Base):
    __tablename__ = "access_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    op_type: Mapped[str] = mapped_column(String(16))  # read | write
    user: Mapped[str] = mapped_column(String(255), default="")
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class Policy(Base):
    __tablename__ = "policies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(255))
    source_tier: Mapped[Tier] = mapped_column(Enum(Tier))
    target_tier: Mapped[Tier] = mapped_column(Enum(Tier))
    # Inactivity threshold expressed in "days" (interpreted via TIME_UNIT at eval time).
    inactivity_threshold_days: Mapped[int] = mapped_column(Integer)
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    priority: Mapped[int] = mapped_column(Integer, default=100)


class Exception(Base):
    __tablename__ = "exceptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    # Either a specific dataset or a whole project may be exempted.
    dataset_id: Mapped[str | None] = mapped_column(String(36), nullable=True, index=True)
    project: Mapped[str | None] = mapped_column(String(255), nullable=True, index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


class LifecycleEvent(Base):
    __tablename__ = "lifecycle_events"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    dataset_id: Mapped[str] = mapped_column(ForeignKey("datasets.id"), index=True)
    event_type: Mapped[EventType] = mapped_column(Enum(EventType))
    from_tier: Mapped[Tier | None] = mapped_column(Enum(Tier), nullable=True)
    to_tier: Mapped[Tier | None] = mapped_column(Enum(Tier), nullable=True)
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, index=True)
    details: Mapped[str] = mapped_column(Text, default="")

    dataset: Mapped["Dataset"] = relationship(back_populates="events")
