"""Catalog service — the single source of truth for dataset metadata (UC8).

Every lifecycle operation (create, access, move, restore) funnels through here so
that the logical catalog stays accurate even as physical location changes across
tiers, and so that an append-only ``LifecycleEvent`` audit trail is recorded for
each mutation. Routers and the lifecycle agent must not mutate ``Dataset`` rows
directly — they call these functions.
"""

from __future__ import annotations

import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from ..models import (
    AccessLog,
    Dataset,
    EventType,
    LifecycleEvent,
    RestoreStatus,
    Tier,
    utcnow,
)
from ..storage.backend import storage_backend


def _record_event(
    db: Session,
    dataset: Dataset,
    event_type: EventType,
    *,
    from_tier: Tier | None = None,
    to_tier: Tier | None = None,
    details: str = "",
) -> None:
    db.add(
        LifecycleEvent(
            dataset_id=dataset.id,
            event_type=event_type,
            from_tier=from_tier,
            to_tier=to_tier,
            details=details,
        )
    )


def create_dataset(
    db: Session,
    *,
    name: str,
    project: str,
    owner: str,
    model_ref: str = "",
    run_config: dict | None = None,
    size_bytes: int = 1_000_000_000,
) -> Dataset:
    """UC1 — create a dataset and store it in hot storage."""
    dataset_id = str(uuid.uuid4())
    physical_path = storage_backend.write(Tier.hot, dataset_id, size_bytes)

    dataset = Dataset(
        id=dataset_id,
        name=name,
        project=project,
        owner=owner,
        model_ref=model_ref,
        run_config=run_config or {},
        size_bytes=size_bytes,
        tier=Tier.hot,
        physical_path=physical_path,
        access_count=0,
    )
    db.add(dataset)
    _record_event(db, dataset, EventType.create, to_tier=Tier.hot, details="Dataset created in hot")
    db.commit()
    db.refresh(dataset)
    return dataset


def record_access(db: Session, dataset: Dataset, *, op_type: str, user: str = "") -> None:
    """UC2 — register a read/write, refreshing recency & frequency."""
    now = utcnow()
    dataset.last_accessed_at = now
    dataset.access_count += 1
    db.add(AccessLog(dataset_id=dataset.id, op_type=op_type, user=user, timestamp=now))
    _record_event(db, dataset, EventType.access, details=f"{op_type} by {user or 'unknown'}")
    db.commit()
    db.refresh(dataset)


def move_dataset(db: Session, dataset: Dataset, target_tier: Tier, *, reason: str) -> Dataset:
    """UC7 — physically move a dataset to ``target_tier`` and update the catalog."""
    from_tier = dataset.tier
    if from_tier == target_tier:
        return dataset
    new_path = storage_backend.move(dataset.id, from_tier, target_tier)
    dataset.tier = target_tier
    dataset.physical_path = new_path
    _record_event(
        db,
        dataset,
        EventType.move,
        from_tier=from_tier,
        to_tier=target_tier,
        details=reason,
    )
    db.commit()
    db.refresh(dataset)
    return dataset


def restore_dataset(db: Session, dataset: Dataset) -> tuple[Dataset, Tier | None]:
    """UC3 — restore an archived dataset back to hot storage."""
    from_tier = dataset.tier
    if from_tier == Tier.hot:
        # Already hot; just refresh access so it isn't immediately re-tiered.
        dataset.last_accessed_at = utcnow()
        dataset.restore_status = RestoreStatus.restored
        db.commit()
        db.refresh(dataset)
        return dataset, None

    dataset.restore_status = RestoreStatus.restoring
    db.commit()

    new_path = storage_backend.move(dataset.id, from_tier, Tier.hot)
    dataset.tier = Tier.hot
    dataset.physical_path = new_path
    dataset.restore_status = RestoreStatus.restored
    dataset.last_accessed_at = utcnow()
    _record_event(
        db,
        dataset,
        EventType.restore,
        from_tier=from_tier,
        to_tier=Tier.hot,
        details=f"Restored from {from_tier.value} to hot",
    )
    db.commit()
    db.refresh(dataset)
    return dataset, from_tier


def get_dataset(db: Session, dataset_id: str) -> Dataset | None:
    return db.get(Dataset, dataset_id)


def list_datasets(
    db: Session,
    *,
    tier: Tier | None = None,
    project: str | None = None,
    search: str | None = None,
) -> list[Dataset]:
    stmt = select(Dataset)
    if tier is not None:
        stmt = stmt.where(Dataset.tier == tier)
    if project:
        stmt = stmt.where(Dataset.project == project)
    if search:
        like = f"%{search}%"
        stmt = stmt.where(Dataset.name.ilike(like))
    stmt = stmt.order_by(Dataset.created_at.desc())
    return list(db.scalars(stmt).all())
