"""Event management API endpoints."""
import logging
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from server.auth.permissions import CurrentUser, require_role
from server.database import get_db
from server.models.db import Event
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
    return result.scalars().all()


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
