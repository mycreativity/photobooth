"""Public API endpoints — no authentication required.

These endpoints are used by the public-facing website
where guests scan a QR code to view their event photos.
"""
import logging
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.database import get_db
from server.models.db import Event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/public", tags=["public"])


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
