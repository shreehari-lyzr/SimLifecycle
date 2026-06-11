"""Pluggable tiered-storage backend.

The ``StorageBackend`` interface abstracts the physical movement of dataset
payloads between Hot / Warm / Cold tiers. For the prototype, ``LocalTieredStorage``
implements it over three local directories. A real ``S3GlacierStorage`` could
implement the same interface later (Hot=S3 Standard, Warm=S3-IA, Cold=Glacier)
without touching the catalog or lifecycle logic.

Each tier exposes a simulated read latency and cost-per-GB so the dashboard and
API responses can demonstrate realistic trade-offs.
"""

from __future__ import annotations

from typing import Optional

import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from ..config import settings
from ..models import Tier

TIER_LATENCY_MS: dict[Tier, int] = {
    Tier.hot: settings.latency_ms_hot,
    Tier.warm: settings.latency_ms_warm,
    Tier.cold: settings.latency_ms_cold,
}

TIER_COST_PER_GB: dict[Tier, float] = {
    Tier.hot: settings.cost_per_gb_hot,
    Tier.warm: settings.cost_per_gb_warm,
    Tier.cold: settings.cost_per_gb_cold,
}


class StorageBackend(ABC):
    @abstractmethod
    def write(self, tier: Tier, dataset_id: str, size_bytes: int) -> str:
        """Persist a dataset payload to ``tier``; return its physical path."""

    @abstractmethod
    def move(self, dataset_id: str, from_tier: Tier, to_tier: Tier) -> str:
        """Move a dataset between tiers; return the new physical path."""

    @abstractmethod
    def delete(self, tier: Tier, dataset_id: str) -> None:
        """Remove a dataset payload from a tier."""

    @staticmethod
    def latency_ms(tier: Tier) -> int:
        return TIER_LATENCY_MS[tier]

    @staticmethod
    def cost_per_gb(tier: Tier) -> float:
        return TIER_COST_PER_GB[tier]


class LocalTieredStorage(StorageBackend):
    """Simulates tiers as ``<storage_root>/{hot,warm,cold}/<dataset_id>.bin``.

    Payloads are sparse placeholder files — we record the logical size in the
    catalog rather than writing gigabytes to disk. The file's existence and its
    location represent the dataset's physical placement.
    """

    def __init__(self, root: Optional[Path] = None) -> None:
        self.root = Path(root or settings.storage_root)
        for tier in Tier:
            (self.root / tier.value).mkdir(parents=True, exist_ok=True)

    def _path(self, tier: Tier, dataset_id: str) -> Path:
        return self.root / tier.value / f"{dataset_id}.bin"

    def write(self, tier: Tier, dataset_id: str, size_bytes: int) -> str:
        path = self._path(tier, dataset_id)
        # Write a small marker file recording the logical size (no real GBs on disk).
        path.write_text(f"dataset={dataset_id}\nsize_bytes={size_bytes}\ntier={tier.value}\n")
        return str(path)

    def move(self, dataset_id: str, from_tier: Tier, to_tier: Tier) -> str:
        src = self._path(from_tier, dataset_id)
        dst = self._path(to_tier, dataset_id)
        if src.exists():
            shutil.move(str(src), str(dst))
        else:
            # Self-heal: source missing (e.g. fresh seed) — materialize at target.
            dst.write_text(f"dataset={dataset_id}\ntier={to_tier.value}\n")
        return str(dst)

    def delete(self, tier: Tier, dataset_id: str) -> None:
        path = self._path(tier, dataset_id)
        path.unlink(missing_ok=True)

    def clear(self) -> None:
        """Remove all payloads from every tier (used on startup reset)."""
        for tier in Tier:
            tier_dir = self.root / tier.value
            for f in tier_dir.glob("*.bin"):
                f.unlink(missing_ok=True)


# Module-level singleton used across the app.
storage_backend: StorageBackend = LocalTieredStorage()
