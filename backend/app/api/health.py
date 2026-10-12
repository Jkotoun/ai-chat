import asyncio
from typing import Literal

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep

logger = structlog.get_logger()

router = APIRouter(tags=["health"])

READY_TIMEOUT_SECONDS = 2.0


class HealthStatus(BaseModel):
    status: Literal["ok"]


class ReadyStatus(BaseModel):
    status: Literal["ready"]


@router.get("/health")
async def health() -> HealthStatus:
    """Liveness probe: the process is up."""
    return HealthStatus(status="ok")


@router.get(
    "/health/ready",
    responses={status.HTTP_503_SERVICE_UNAVAILABLE: {"description": "Database unavailable"}},
)
async def ready(session: SessionDep) -> ReadyStatus:
    """Readiness probe: the database is reachable."""
    try:
        async with asyncio.timeout(READY_TIMEOUT_SECONDS):
            await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as exc:  # TimeoutError is an OSError
        logger.warning("readiness_check_failed", error=repr(exc))
        raise HTTPException(
            status.HTTP_503_SERVICE_UNAVAILABLE, detail="database unavailable"
        ) from exc
    return ReadyStatus(status="ready")
