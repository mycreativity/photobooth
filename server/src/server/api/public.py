"""Public API endpoints — no authentication required.

These endpoints are used by the public-facing website
where guests scan a QR code to view their event photos.
"""
import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import get_db
from server.models.db import Event, Photo

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["public"])

PHOTOS_DIR = Path(os.getenv("PHOTOS_DIR", "/data/photos"))


@router.get("/events/{uid}")
async def get_public_event(
    uid: str,
    db: AsyncSession = Depends(get_db),
):
    """Get event info by short UID (for QR code landing pages).

    Returns event name, description, date, location — no sensitive data.
    """
    result = await db.execute(select(Event).where(Event.uid == uid))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    if not event.is_active:
        raise HTTPException(status_code=410, detail="Event is no longer active")

    return {
        "uid": event.uid,
        "name": event.name,
        "description": event.description,
        "date": event.date.isoformat() if event.date else None,
        "location": event.location,
    }


@router.get("/events/{uid}/photos")
async def get_event_photos(
    uid: str,
    variant: str = "final",
    db: AsyncSession = Depends(get_db),
):
    """Get all photos for an event (for the public gallery).

    Returns only 'final' variant by default to avoid raw originals.
    """
    # Resolve event UID → event ID
    result = await db.execute(select(Event).where(Event.uid == uid))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    # Get photos
    result = await db.execute(
        select(Photo)
        .where(Photo.event_id == event.id)
        .where(Photo.variant == variant)
        .order_by(Photo.created_at.desc())
    )
    photos = result.scalars().all()

    return [
        {
            "id": p.id,
            "session_id": p.session_id,
            "seq": p.seq,
            "width": p.width,
            "height": p.height,
            "url": f"/api/public/photos/{p.id}",
            "thumb_url": f"/api/public/photos/{p.id}?w=400",
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in photos
    ]


@router.get("/photos/{photo_id}")
async def serve_photo(
    photo_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve a photo file by ID (no auth — public gallery)."""
    result = await db.execute(select(Photo).where(Photo.id == photo_id))
    photo = result.scalar_one_or_none()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    abs_path = PHOTOS_DIR / photo.filename
    if not abs_path.exists():
        raise HTTPException(status_code=404, detail="Photo file missing")

    return FileResponse(
        abs_path,
        media_type="image/jpeg",
        filename=f"photo_{photo.seq}.jpg",
    )
