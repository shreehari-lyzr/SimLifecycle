"""Application configuration for the SimLifecycle Agent.

All tunables live here. The two knobs that make the prototype demoable without
waiting real calendar days:

* ``time_unit_seconds`` — how many real seconds count as one "day" when the
  lifecycle agent measures inactivity. In production this is 86400 (a real day);
  in demo mode set it low (e.g. 1) so a "30 day" threshold elapses in 30s.
* ``scan_interval_seconds`` — how often the background agent runs a scan.
"""

from __future__ import annotations

from pathlib import Path

from pydantic_settings import BaseSettings, SettingsConfigDict

# Repo layout: <repo>/backend/app/config.py  ->  repo root is two parents up
BACKEND_DIR = Path(__file__).resolve().parent.parent
REPO_ROOT = BACKEND_DIR.parent


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="SIMLC_", env_file=".env", extra="ignore")

    # Persistence
    database_url: str = f"sqlite:///{BACKEND_DIR / 'simlifecycle.db'}"

    # Simulated tiered storage root (gitignored at runtime)
    storage_root: Path = REPO_ROOT / "storage"

    # Time simulation. One "day" of inactivity == this many real seconds.
    # Default 1 second/day so a 30-day threshold triggers after 30 real seconds,
    # which makes the demo observable. Set to 86400 for real-time behaviour.
    time_unit_seconds: float = 1.0

    # How often the background lifecycle agent runs an automatic scan.
    scan_interval_seconds: int = 5

    # Whether to (re)seed demo data on startup if the DB is empty.
    seed_on_startup: bool = True

    # CORS origins for the frontend dev server.
    cors_origins: list[str] = ["http://localhost:5173", "http://127.0.0.1:5173"]

    # Simulated monthly cost per GB by tier (USD). Used for savings metrics.
    cost_per_gb_hot: float = 0.23
    cost_per_gb_warm: float = 0.0125
    cost_per_gb_cold: float = 0.004

    # Simulated read latency per tier (milliseconds). Surfaced in API responses.
    latency_ms_hot: int = 2
    latency_ms_warm: int = 80
    latency_ms_cold: int = 5000


settings = Settings()
