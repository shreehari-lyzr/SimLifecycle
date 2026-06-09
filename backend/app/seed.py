"""Seed demo data: default lifecycle policies + datasets with varied activity.

Datasets are created in hot storage, then their ``last_accessed_at`` is
backdated to simulate different inactivity ages so a lifecycle scan immediately
has work to do across all tiers. Inactivity ages are expressed in *simulated*
days converted to real seconds via ``settings.time_unit_seconds``.
"""

from __future__ import annotations

from datetime import timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from .config import settings
from .models import Dataset, Exception as PolicyException, Policy, Tier, utcnow
from .services import catalog

# (name, project, owner, simulated days since last access, size GB, critical)
_DATASETS = [
    ("aero_wing_v3_run42", "Aerodynamics", "j.chen", 0, 4, False),
    ("aero_wing_v3_run43", "Aerodynamics", "j.chen", 2, 4, False),
    ("thermal_block_baseline", "ThermalSim", "m.patel", 12, 2, False),
    ("crash_frontal_iter7", "CrashSafety", "l.gomez", 35, 8, False),
    ("crash_side_iter2", "CrashSafety", "l.gomez", 41, 6, False),
    ("turbine_cfd_legacy", "Turbomachinery", "s.okafor", 95, 12, False),
    ("turbine_cfd_archive_2023", "Turbomachinery", "s.okafor", 140, 10, False),
    ("acoustics_cabin_v1", "NVH", "r.singh", 60, 3, False),
    ("fatigue_chassis_master", "Durability", "a.rossi", 200, 5, True),  # critical → exempt
    ("em_field_motor_run9", "Electromagnetics", "t.nguyen", 33, 7, False),
]

_POLICIES = [
    # name, source, target, threshold_days, priority
    ("Hot to Warm after 30d inactivity", Tier.hot, Tier.warm, 30, 10),
    ("Warm to Cold after 90d inactivity", Tier.warm, Tier.cold, 90, 20),
]


def _backdate(db: Session, dataset: Dataset, sim_days: float) -> None:
    real_seconds = sim_days * settings.time_unit_seconds
    dataset.last_accessed_at = utcnow() - timedelta(seconds=real_seconds)
    db.add(dataset)


def seed_if_empty(db: Session) -> bool:
    """Seed policies + datasets if no datasets exist yet. Returns True if seeded."""
    if db.scalar(select(Dataset).limit(1)) is not None:
        return False

    for name, source, target, threshold, priority in _POLICIES:
        db.add(
            Policy(
                name=name,
                source_tier=source,
                target_tier=target,
                inactivity_threshold_days=threshold,
                enabled=True,
                priority=priority,
            )
        )
    db.commit()

    for name, project, owner, sim_days, size_gb, critical in _DATASETS:
        dataset = catalog.create_dataset(
            db,
            name=name,
            project=project,
            owner=owner,
            model_ref=f"{project.lower()}/{name}",
            run_config={"solver": "implicit", "cores": 64},
            size_bytes=size_gb * 1_000_000_000,
        )
        dataset.is_critical = critical
        _backdate(db, dataset, sim_days)
        db.commit()

    # A project-scoped exception demonstrating override behaviour (UC4).
    db.add(
        PolicyException(
            project="Durability",
            reason="Active regulatory durability program — retain in current tier.",
        )
    )
    db.commit()
    return True
