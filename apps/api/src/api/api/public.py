"""Public API endpoints — no authentication required.

These endpoints are used by the public-facing website
where guests scan a QR code to view their event photos.
"""
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.database import get_db
from api.models.db import Event, Photo, Session

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["public"])

PHOTOS_DIR = Path(os.getenv("PHOTOS_DIR", "/data/photos"))
SESSION_EXPIRY_DAYS = 30


@router.get("/events/{uid}")
async def get_public_event(
    uid: str,
    db: AsyncSession = Depends(get_db),
):
    """Get event info by short UID (for QR code landing pages).

    Returns event name, description, date — no sensitive data.
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
        "end_date": event.end_date.isoformat() if event.end_date else None,
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


# ── Session-based endpoints (privacy-friendly viewer) ────────────────────────


def _check_session_expired(session: Session, event: Event | None) -> None:
    """Raise 410 if the session's event has expired (>30 days past end/start date)."""
    if not event:
        return
    ref_date = event.end_date or event.date
    if ref_date:
        expiry = ref_date + timedelta(days=SESSION_EXPIRY_DAYS)
        if datetime.now(timezone.utc) > expiry.replace(tzinfo=timezone.utc):
            raise HTTPException(status_code=410, detail="Session has expired")


@router.get("/sessions/{token}")
async def get_session_by_token(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Get session info by public token (for QR code viewer).

    Returns session data + parent event info. No sensitive data.
    """
    result = await db.execute(select(Session).where(Session.token == token))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Get parent event
    event = None
    if session.event_id:
        result = await db.execute(select(Event).where(Event.id == session.event_id))
        event = result.scalar_one_or_none()

    _check_session_expired(session, event)

    return {
        "token": session.token,
        "layout": session.layout,
        "photo_count": session.photo_count,
        "created_at": session.created_at.isoformat() if session.created_at else None,
        "event": {
            "name": event.name,
            "description": event.description,
            "date": event.date.isoformat() if event.date else None,
            "location": None,  # Add when location field exists
        } if event else None,
    }


@router.get("/sessions/{token}/photos")
async def get_session_photos(
    token: str,
    db: AsyncSession = Depends(get_db),
):
    """Get all photos for a session (final + print variants).

    Returns photos ordered: print variant first, then individual photos.
    """
    result = await db.execute(select(Session).where(Session.token == token))
    session = result.scalar_one_or_none()
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    # Check expiration via parent event
    if session.event_id:
        result = await db.execute(select(Event).where(Event.id == session.event_id))
        event = result.scalar_one_or_none()
        _check_session_expired(session, event)

    # Get photos: print variant first, then finals
    result = await db.execute(
        select(Photo)
        .where(Photo.session_id == session.id)
        .where(Photo.variant.in_(["final", "print"]))
        .order_by(
            # print variant first (p < f alphabetically, so asc puts print last — reverse)
            Photo.variant.desc(),
            Photo.seq.asc(),
        )
    )
    photos = result.scalars().all()

    return [
        {
            "id": p.id,
            "seq": p.seq,
            "variant": p.variant,
            "width": p.width,
            "height": p.height,
            "url": f"/api/public/photos/{p.id}",
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in photos
    ]
