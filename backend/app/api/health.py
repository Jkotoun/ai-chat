import asyncio

import structlog
from fastapi import APIRouter, HTTPException
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import SessionDep

logger = structlog.get_logger()

router = APIRouter(tags=["health"])

READY_TIMEOUT_SECONDS = 2.0


@router.get("/health")
async def health() -> dict[str, str]:
    """Liveness probe: the process is up."""
    return {"status": "ok"}


@router.get("/health/ready")
async def ready(session: SessionDep) -> dict[str, str]:
    """Readiness probe: the database is reachable."""
    try:
        async with asyncio.timeout(READY_TIMEOUT_SECONDS):
            await session.execute(text("SELECT 1"))
    except (SQLAlchemyError, OSError) as exc:  # TimeoutError is an OSError
        logger.warning("readiness_check_failed", error=repr(exc))
        raise HTTPException(status_code=503, detail="database unavailable") from exc
    return {"status": "ready"}
