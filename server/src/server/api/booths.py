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
from server.ws.hub import hub

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


@router.get("/{booth_id}/info")
async def get_booth_info(
    booth_id: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Get booth DB record + live system info from WebSocket heartbeat."""
    result = await db.execute(
        select(Booth).where(Booth.booth_id == booth_id)
    )
    booth = result.scalar_one_or_none()
    if not booth:
        raise HTTPException(status_code=404, detail="Booth not found")

    # Merge DB data with live heartbeat info
    live = hub.get_booth_info(booth_id)
    return {
        "id": booth.id,
        "booth_id": booth.booth_id,
        "name": booth.name,
        "status": booth.status,
        "last_seen": booth.last_seen.isoformat() if booth.last_seen else None,
        "version": booth.version,
        # Live system metrics
        "cpu_percent": live.get("cpu", booth.cpu_percent),
        "camera_connected": live.get("cam_connected", booth.camera_connected),
        "uptime_seconds": live.get("uptime", booth.uptime_seconds),
        "mem_total_mb": live.get("mem_total_mb", 0),
        "mem_used_mb": live.get("mem_used_mb", 0),
        "mem_percent": live.get("mem_percent", 0),
        "cpu_temp": live.get("cpu_temp"),
        "disk_total_gb": live.get("disk_total_gb", 0),
        "disk_used_gb": live.get("disk_used_gb", 0),
        "disk_free_gb": live.get("disk_free_gb", 0),
        "disk_percent": live.get("disk_percent", 0),
        "hostname": live.get("hostname", ""),
        "platform": live.get("platform", ""),
        "python": live.get("python", ""),
        "settings": live.get("settings", {}),
    }



@router.get("/{booth_id}/logs")
async def get_booth_logs(
    booth_id: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    limit: int = 100,
):
    """Get recent log lines from a booth's ring buffer."""
    return hub.get_logs(booth_id, limit=min(limit, 200))


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
