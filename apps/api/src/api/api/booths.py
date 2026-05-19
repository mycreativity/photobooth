"""Booth management API endpoints."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.permissions import CurrentUser, require_role
from api.database import get_db
from api.models.db import Booth, generate_api_key, hash_api_key
from api.models.schemas import BoothCreate, BoothCreatedOut, BoothOut, BoothUpdate
from api.ws.hub import hub

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


@router.post("", response_model=BoothCreatedOut, status_code=201)
async def create_booth(
    body: BoothCreate,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Register a new booth — generates API key (shown only once)."""
    # Check if booth_id already exists
    result = await db.execute(
        select(Booth).where(Booth.booth_id == body.booth_id)
    )
    if result.scalar_one_or_none():
        raise HTTPException(status_code=409, detail=f"Booth '{body.booth_id}' already exists")

    # Generate API key
    plaintext_key = generate_api_key()
    key_hash = hash_api_key(plaintext_key)

    booth = Booth(
        booth_id=body.booth_id,
        name=body.name,
        api_key_hash=key_hash,
    )
    db.add(booth)
    await db.commit()
    await db.refresh(booth)

    logger.info("Booth created: %s (by %s)", body.booth_id, user.email)

    return BoothCreatedOut(
        id=booth.id,
        booth_id=booth.booth_id,
        name=booth.name,
        api_key=plaintext_key,
    )


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


@router.put("/{booth_id}", response_model=BoothOut)
async def update_booth(
    booth_id: str,
    body: BoothUpdate,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Update booth info (name, event coupling)."""
    result = await db.execute(
        select(Booth).where(Booth.booth_id == booth_id)
    )
    booth = result.scalar_one_or_none()
    if not booth:
        raise HTTPException(status_code=404, detail="Booth not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(booth, field, value)

    await db.commit()
    await db.refresh(booth)
    logger.info("Booth updated: %s", booth_id)
    return booth


@router.post("/{booth_id}/regenerate-key", response_model=BoothCreatedOut)
async def regenerate_key(
    booth_id: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Generate a new API key for a booth (invalidates the old one)."""
    result = await db.execute(
        select(Booth).where(Booth.booth_id == booth_id)
    )
    booth = result.scalar_one_or_none()
    if not booth:
        raise HTTPException(status_code=404, detail="Booth not found")

    plaintext_key = generate_api_key()
    booth.api_key_hash = hash_api_key(plaintext_key)
    await db.commit()

    logger.info("API key regenerated for booth: %s (by %s)", booth_id, user.email)

    return BoothCreatedOut(
        id=booth.id,
        booth_id=booth.booth_id,
        name=booth.name,
        api_key=plaintext_key,
    )


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
        "event_id": booth.event_id,
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
        # Power / electricity
        "power_voltage": live.get("power_voltage"),
        "power_current_a": live.get("power_current_a"),
        "power_watts": live.get("power_watts"),
        "power_throttled": live.get("power_throttled"),
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


@router.post("/{booth_id}/settings")
async def update_booth_settings(
    booth_id: str,
    settings: dict,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
):
    """Push settings to a booth via WebSocket.

    The booth agent will update its booth.toml and optionally restart.
    """
    if not hub.is_booth_connected(booth_id):
        raise HTTPException(status_code=503, detail="Booth is offline")

    sent = await hub.send_to_booth(booth_id, {
        "type": "update_settings",
        "settings": settings,
    })
    if not sent:
        raise HTTPException(status_code=503, detail="Failed to send to booth")

    return {"message": "Settings sent", "booth_id": booth_id}


@router.post("/{booth_id}/restart")
async def restart_booth(
    booth_id: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
):
    """Send a restart command to a booth."""
    if not hub.is_booth_connected(booth_id):
        raise HTTPException(status_code=503, detail="Booth is offline")

    sent = await hub.send_to_booth(booth_id, {"type": "restart"})
    if not sent:
        raise HTTPException(status_code=503, detail="Failed to send to booth")

    return {"message": "Restart command sent", "booth_id": booth_id}


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


def build_push_event_data(event) -> dict:
    """Build the push_event WebSocket message for a booth.

    Shared between the admin push endpoint and auto-push on reconnect.

    Args:
        event: An Event model instance.

    Returns:
        A dict ready to be sent via WebSocket to a booth.
    """
    from api.config import settings as api_settings
    server_url = api_settings.api_url.rstrip("/")
    return {
        "type": "push_event",
        "event": {
            "event_uid": event.uid,
            "event_name": event.name,
            "display_date": event.display_date or "",
            "branding_text": event.branding_text or "",
            "background_image": event.background_image,
            "background_url": (
                f"{server_url}/api/events/{event.uid}/background"
                if event.background_image else None
            ),
        },
    }


@router.post("/{booth_id}/push-event")
async def push_event_to_booth(
    booth_id: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Push event card configuration to a connected booth.

    Reads the booth's assigned event, collects all card settings
    (background, branding text, date), and sends them to the booth
    via WebSocket. The booth downloads the background image once
    and caches it locally.
    """
    if not hub.is_booth_connected(booth_id):
        raise HTTPException(status_code=503, detail="Booth is offline")

    # Get booth and its assigned event
    result = await db.execute(
        select(Booth).where(Booth.booth_id == booth_id)
    )
    booth = result.scalar_one_or_none()
    if not booth:
        raise HTTPException(status_code=404, detail="Booth not found")
    if not booth.event_id:
        raise HTTPException(status_code=400, detail="Booth has no event assigned")

    # Get event data
    ev_result = await db.execute(
        select(Event).where(Event.id == booth.event_id)
    )
    event = ev_result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Assigned event not found")

    push_data = build_push_event_data(event)

    sent = await hub.send_to_booth(booth_id, push_data)
    if not sent:
        raise HTTPException(status_code=503, detail="Failed to send to booth")

    logger.info("Event card pushed to booth %s: event=%s", booth_id, event.uid)
    return {
        "message": "Event card configuration pushed",
        "booth_id": booth_id,
        "event_uid": event.uid,
    }

