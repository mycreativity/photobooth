"""Booth management API endpoints."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth.permissions import CurrentUser, require_role
from server.database import get_db
from server.models.db import Booth
from server.models.schemas import BoothOut

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/booths", tags=["booths"])


@router.get("", response_model=list[BoothOut])
async def list_booths(
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """List all registered booths with their status."""
    result = await db.execute(
        select(Booth).order_by(Booth.created_at.desc())
    )
    return result.scalars().all()


@router.get("/{booth_id}", response_model=BoothOut)
async def get_booth(
    booth_id: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Get a specific booth by ID."""
    result = await db.execute(
        select(Booth).where(Booth.booth_id == booth_id)
    )
    booth = result.scalar_one_or_none()
    if not booth:
        raise HTTPException(status_code=404, detail="Booth not found")
    return booth


@router.delete("/{booth_id}")
async def delete_booth(
    booth_id: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Remove a booth registration."""
    result = await db.execute(
        select(Booth).where(Booth.booth_id == booth_id)
    )
    booth = result.scalar_one_or_none()
    if not booth:
        raise HTTPException(status_code=404, detail="Booth not found")

    await db.delete(booth)
    await db.commit()
    return {"message": f"Booth {booth_id} deleted"}
