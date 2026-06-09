"""Policy & exception management endpoints (UC4 — Define Lifecycle Policies).

Includes the ``<<include>> Manage Exceptions & Overrides`` behaviour: critical
datasets and exception entries are exempted from automated tier movement.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from ..db import get_db
from ..models import Dataset, Exception as PolicyException, Policy
from ..schemas import (
    DatasetOut,
    ExceptionCreate,
    ExceptionOut,
    PolicyCreate,
    PolicyOut,
    PolicyUpdate,
)

router = APIRouter(tags=["policies"])


# ----------------------------------------------------------------- Policies
@router.get("/policies", response_model=list[PolicyOut])
def list_policies(db: Session = Depends(get_db)) -> list[PolicyOut]:
    rows = db.scalars(select(Policy).order_by(Policy.priority)).all()
    return [PolicyOut.model_validate(r) for r in rows]


@router.post("/policies", response_model=PolicyOut, status_code=201)
def create_policy(payload: PolicyCreate, db: Session = Depends(get_db)) -> PolicyOut:
    policy = Policy(**payload.model_dump())
    db.add(policy)
    db.commit()
    db.refresh(policy)
    return PolicyOut.model_validate(policy)


@router.put("/policies/{policy_id}", response_model=PolicyOut)
def update_policy(
    policy_id: int, payload: PolicyUpdate, db: Session = Depends(get_db)
) -> PolicyOut:
    policy = db.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    for field, value in payload.model_dump(exclude_unset=True).items():
        setattr(policy, field, value)
    db.commit()
    db.refresh(policy)
    return PolicyOut.model_validate(policy)


@router.delete("/policies/{policy_id}", status_code=204, response_class=Response)
def delete_policy(policy_id: int, db: Session = Depends(get_db)) -> Response:
    policy = db.get(Policy, policy_id)
    if policy is None:
        raise HTTPException(status_code=404, detail="Policy not found")
    db.delete(policy)
    db.commit()
    return Response(status_code=204)


# --------------------------------------------------------------- Exceptions
@router.get("/exceptions", response_model=list[ExceptionOut])
def list_exceptions(db: Session = Depends(get_db)) -> list[ExceptionOut]:
    rows = db.scalars(select(PolicyException).order_by(PolicyException.created_at.desc())).all()
    return [ExceptionOut.model_validate(r) for r in rows]


@router.post("/exceptions", response_model=ExceptionOut, status_code=201)
def create_exception(payload: ExceptionCreate, db: Session = Depends(get_db)) -> ExceptionOut:
    if not payload.dataset_id and not payload.project:
        raise HTTPException(status_code=400, detail="Provide dataset_id or project")
    exc = PolicyException(**payload.model_dump())
    db.add(exc)
    db.commit()
    db.refresh(exc)
    return ExceptionOut.model_validate(exc)


@router.delete("/exceptions/{exception_id}", status_code=204, response_class=Response)
def delete_exception(exception_id: int, db: Session = Depends(get_db)) -> Response:
    exc = db.get(PolicyException, exception_id)
    if exc is None:
        raise HTTPException(status_code=404, detail="Exception not found")
    db.delete(exc)
    db.commit()
    return Response(status_code=204)


# -------------------------------------- Critical flag (override shortcut, UC4)
@router.post("/datasets/{dataset_id}/critical", response_model=DatasetOut)
def set_critical(dataset_id: str, is_critical: bool, db: Session = Depends(get_db)) -> DatasetOut:
    """Mark/unmark a dataset critical so it is exempt from automated movement."""
    dataset = db.get(Dataset, dataset_id)
    if dataset is None:
        raise HTTPException(status_code=404, detail="Dataset not found")
    dataset.is_critical = is_critical
    db.commit()
    db.refresh(dataset)
    return DatasetOut.model_validate(dataset)
