"""Event management API endpoints."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth.permissions import CurrentUser, require_role
from server.database import get_db
from server.models.db import Event, Photo
from server.models.schemas import EventCreate, EventOut, EventUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])


@router.get("", response_model=list[EventOut])
async def list_events(
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """List all events, newest first."""
    result = await db.execute(
        select(Event).order_by(Event.created_at.desc())
    )
    events = result.scalars().all()

    # Enrich with photo counts
    enriched = []
    for ev in events:
        count_result = await db.execute(
            select(func.count(Photo.id)).where(Photo.event_id == ev.id)
        )
        photo_count = count_result.scalar() or 0
        ev_dict = EventOut.model_validate(ev).model_dump()
        ev_dict["photo_count"] = photo_count
        enriched.append(ev_dict)

    return enriched


@router.post("", response_model=EventOut, status_code=201)
async def create_event(
    body: EventCreate,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Create a new event with auto-generated short UID."""
    event = Event(
        name=body.name,
        description=body.description,
        date=body.date,
        location=body.location,
        created_by=user.user_id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    logger.info("Event created: %s (uid=%s)", event.name, event.uid)
    return event


@router.get("/{uid}", response_model=EventOut)
async def get_event(
    uid: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Get event by short UID."""
    result = await db.execute(select(Event).where(Event.uid == uid))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")
    return event


@router.get("/{uid}/photos")
async def get_event_photos(
    uid: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Get all photos for an event (admin view)."""
    result = await db.execute(select(Event).where(Event.uid == uid))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    photos_result = await db.execute(
        select(Photo)
        .where(Photo.event_id == event.id)
        .order_by(Photo.created_at.desc())
    )
    photos = photos_result.scalars().all()

    return [
        {
            "id": p.id,
            "session_id": p.session_id,
            "booth_id": p.booth_id,
            "seq": p.seq,
            "variant": p.variant,
            "width": p.width,
            "height": p.height,
            "size_bytes": p.size_bytes,
            "url": f"/api/public/photos/{p.id}",
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in photos
    ]


@router.put("/{uid}", response_model=EventOut)
async def update_event(
    uid: str,
    body: EventUpdate,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Update an event (partial)."""
    result = await db.execute(select(Event).where(Event.uid == uid))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    update_data = body.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(event, field, value)

    await db.commit()
    await db.refresh(event)
    logger.info("Event updated: %s (uid=%s)", event.name, event.uid)
    return event


@router.delete("/{uid}")
async def delete_event(
    uid: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Delete an event."""
    result = await db.execute(select(Event).where(Event.uid == uid))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    await db.delete(event)
    await db.commit()
    logger.info("Event deleted: uid=%s", uid)
    return {"message": f"Event '{event.name}' deleted"}

