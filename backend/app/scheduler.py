"""Background scheduler that runs the lifecycle agent automatically (UC7).

Demonstrates "zero manual intervention" — the agent periodically scans and
tiers inactive datasets with no operator action. The same ``scan`` is also
exposed via the API for on-demand runs.
"""

from __future__ import annotations

from typing import Optional

import logging

from apscheduler.schedulers.background import BackgroundScheduler

from .config import settings
from .db import SessionLocal
from .services import lifecycle_agent

logger = logging.getLogger("simlifecycle.scheduler")

_scheduler: Optional[BackgroundScheduler] = None


def _run_scan_job() -> None:
    db = SessionLocal()
    try:
        summary = lifecycle_agent.scan(db)
        if summary.moved:
            logger.info(
                "Automatic lifecycle scan: %d moved, %d MB reclaimed from hot",
                summary.moved,
                summary.bytes_reclaimed_from_hot // 1_000_000,
            )
    except Exception:  # noqa: BLE001 — never let a bad scan kill the scheduler
        logger.exception("Lifecycle scan failed")
    finally:
        db.close()


def start_scheduler() -> BackgroundScheduler:
    global _scheduler
    if _scheduler is not None:
        return _scheduler
    scheduler = BackgroundScheduler(daemon=True)
    scheduler.add_job(
        _run_scan_job,
        "interval",
        seconds=settings.scan_interval_seconds,
        id="lifecycle_scan",
        max_instances=1,
        coalesce=True,
    )
    scheduler.start()
    logger.info("Lifecycle scheduler started (every %ss)", settings.scan_interval_seconds)
    _scheduler = scheduler
    return scheduler


def shutdown_scheduler() -> None:
    global _scheduler
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _scheduler = None
