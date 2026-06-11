"""SimLifecycle Agent — FastAPI application entry point.

Wires together the catalog, policy, lifecycle, and dashboard routers; creates
the database and tier directories; optionally seeds demo data; and starts the
background lifecycle scheduler (the automated agent).
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import SessionLocal, init_db, reset_db
from .routers import dashboard, datasets, lifecycle, policies
from .scheduler import shutdown_scheduler, start_scheduler
from .seed import seed_if_empty
from .storage.backend import storage_backend

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("simlifecycle")


@asynccontextmanager
async def lifespan(app: FastAPI):
    if settings.reset_on_startup:
        reset_db()
        if hasattr(storage_backend, "clear"):
            storage_backend.clear()
        logger.info("Reset database and cleared simulated storage on startup")
    else:
        init_db()
    if settings.seed_on_startup:
        db = SessionLocal()
        try:
            if seed_if_empty(db):
                logger.info("Seeded demo datasets and default policies")
        finally:
            db.close()
    start_scheduler()
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(
    title="SimLifecycle Agent",
    description="Policy-driven simulation data lifecycle management across Hot/Warm/Cold tiers.",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(datasets.router)
app.include_router(policies.router)
app.include_router(lifecycle.router)
app.include_router(dashboard.router)


@app.get("/health", tags=["meta"])
def health() -> dict:
    return {
        "status": "ok",
        "time_unit_seconds": settings.time_unit_seconds,
        "scan_interval_seconds": settings.scan_interval_seconds,
    }
