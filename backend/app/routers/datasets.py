"""Dataset endpoints — UC1 (create), UC2 (access), UC3 (restore), UC8 (lookup)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from sqlalchemy import select

from ..db import get_db
from ..models import Dataset, Exception as PolicyException, Tier
from ..schemas import (
    AccessResult,
    DatasetAccess,
    DatasetCreate,
    DatasetOut,
    RestoreResult,
)
from ..services import catalog, policy_engine
from ..storage.backend import StorageBackend

router = APIRouter(prefix="/datasets", tags=["datasets"])


def _to_out(dataset: Dataset, exceptions: list[PolicyException]) -> DatasetOut:
    """Serialize a dataset, annotating why it is exempt from automated movement."""
    out = DatasetOut.model_validate(dataset)
    out.exempt_reasons = policy_engine.exemption_reasons(dataset, exceptions)
    out.is_exempt = bool(out.exempt_reasons)
    return out


def _load_exceptions(db: Session) -> list[PolicyException]:
    return list(db.scalars(select(PolicyException)).all())


@router.post("", response_model=DatasetOut, status_code=201)
def create_dataset(payload: DatasetCreate, db: Session = Depends(get_db)) -> DatasetOut:
    """UC1 — Create Simulation Data (stored in hot storage)."""
    dataset = catalog.create_dataset(
        db,
        name=payload.name,
        project=payload.project,
        owner=payload.owner,
        model_ref=payload.model_ref,
        run_config=payload.run_config,
        size_bytes=payload.size_bytes,
    )
    return _to_out(dataset, _load_exceptions(db))


@router.get("", response_model=list[DatasetOut])
def list_datasets(
    db: Session = Depends(get_db),
    tier: Tier | None = Query(default=None),
    project: str | None = Query(default=None),
    search: str | None = Query(default=None),
) -> list[DatasetOut]:
    """UC8 — Catalog lookup/search (transparent discoverability)."""
    rows = catalog.list_datasets(db, tier=tier, project=project, search=search)
    exceptions = _load_exceptions(db)
    return [_to_out(r, exceptions) for r in rows]


@router.get("/{dataset_id}", response_model=DatasetOut)
def get_dataset(dataset_id: str, db: Session = Depends(get_db)) -> DatasetOut:
    dataset = catalog.get_dataset(db, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    return _to_out(dataset, _load_exceptions(db))


@router.post("/{dataset_id}/access", response_model=AccessResult)
def access_dataset(
    dataset_id: str, payload: DatasetAccess, db: Session = Depends(get_db)
) -> AccessResult:
    """UC2 — Access Active Simulation Data; updates recency/frequency.

    If the dataset has been tiered out of hot, accessing it from warm/cold
    surfaces the simulated higher latency (and the engineer would typically
    restore it via UC3 for sustained work).
    """
    dataset = catalog.get_dataset(db, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    latency = StorageBackend.latency_ms(dataset.tier)
    catalog.record_access(db, dataset, op_type=payload.op_type, user=payload.user)

    note = (
        "Served from hot storage with low latency."
        if dataset.tier == Tier.hot
        else f"Served from {dataset.tier.value} storage (higher latency); "
        "consider restoring for sustained access."
    )
    return AccessResult(dataset=DatasetOut.model_validate(dataset), latency_ms=latency, note=note)


@router.post("/{dataset_id}/restore", response_model=RestoreResult)
def restore_dataset(dataset_id: str, db: Session = Depends(get_db)) -> RestoreResult:
    """UC3 — Retrieve Archived Simulation Data (restore to hot)."""
    dataset = catalog.get_dataset(db, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")

    dataset, restored_from = catalog.restore_dataset(db, dataset)
    note = (
        "Dataset already in hot storage; access refreshed."
        if restored_from is None
        else f"Dataset restored from {restored_from.value} to hot storage."
    )
    return RestoreResult(
        dataset=DatasetOut.model_validate(dataset),
        restored_from=restored_from,
        note=note,
    )
