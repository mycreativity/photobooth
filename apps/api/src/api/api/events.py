"""Event management API endpoints."""
import logging
import os
import uuid
from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.permissions import CurrentUser, require_role
from api.database import get_db
from api.models.db import Event, Photo
from api.models.schemas import EventCreate, EventOut, EventUpdate

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/events", tags=["events"])

BACKGROUNDS_DIR = Path(os.getenv("BACKGROUNDS_DIR", "/data/backgrounds"))

# Pre-generated background presets (filenames)
PRESET_BACKGROUNDS = [
    "festive_confetti.png",
    "floral_botanical.png",
    "starry_night.png",
    "abstract_geometric.png",
    "tropical_watercolor.png",
    "autumn_leaves.png",
    "winter_wonderland.png",
    "music_party.png",
    "romantic_roses.png",
    "minimalist_gradient.png",
    "kids_party.png",
    "hearts_love.png",
    "elegant_wedding.png",
    "corporate_business.png",
    "disco_party.png",
]


def _generate_dutch_date(dt) -> str:
    """Generate a human-readable Dutch date string."""
    if not dt:
        return ""
    days = ["Maandag", "Dinsdag", "Woensdag", "Donderdag", "Vrijdag", "Zaterdag", "Zondag"]
    months = [
        "Januari", "Februari", "Maart", "April", "Mei", "Juni",
        "Juli", "Augustus", "September", "Oktober", "November", "December",
    ]
    return f"{days[dt.weekday()]} {dt.day} {months[dt.month - 1]} {dt.year}"


def _generate_branding_text(event_name: str) -> str:
    """Generate a fun Dutch prefill text based on the event name."""
    return f"**{event_name}** ✨\n_Wat een feest!_"


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
    # Auto-generate display_date and branding_text if not provided
    display_date = body.display_date
    if not display_date and body.date:
        display_date = _generate_dutch_date(body.date)

    branding_text = body.branding_text
    if not branding_text:
        branding_text = _generate_branding_text(body.name)

    event = Event(
        name=body.name,
        description=body.description,
        date=body.date,
        end_date=body.end_date,
        branding_text=branding_text,
        display_date=display_date,
        created_by=user.user_id,
    )
    db.add(event)
    await db.commit()
    await db.refresh(event)
    logger.info("Event created: %s (uid=%s)", event.name, event.uid)
    return event


@router.get("/presets/backgrounds")
async def list_preset_backgrounds(
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
):
    """List available preset background images."""
    presets = []
    preset_dir = BACKGROUNDS_DIR / "presets"
    for name in PRESET_BACKGROUNDS:
        path = preset_dir / name
        presets.append({
            "name": name,
            "label": name.replace("_", " ").replace(".png", "").title(),
            "url": f"/api/events/presets/backgrounds/{name}",
            "exists": path.exists(),
        })
    return presets


@router.get("/presets/backgrounds/{filename}")
async def serve_preset_background(filename: str):
    """Serve a preset background image."""
    # Sanitize filename
    if "/" in filename or ".." in filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    path = BACKGROUNDS_DIR / "presets" / filename
    if not path.exists():
        raise HTTPException(status_code=404, detail="Background not found")
    media_type = "image/png" if filename.endswith(".png") else "image/jpeg"
    return FileResponse(path, media_type=media_type)


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

    # Auto-generate display_date if date changes and no explicit display_date
    if "date" in update_data and "display_date" not in update_data:
        update_data["display_date"] = _generate_dutch_date(update_data["date"])

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

    # Clean up background image
    if event.background_image:
        if not event.background_image.startswith("presets/"):
            bg_path = BACKGROUNDS_DIR / event.background_image
            if bg_path.exists():
                bg_path.unlink()

    await db.delete(event)
    await db.commit()
    logger.info("Event deleted: uid=%s", uid)
    return {"message": f"Event '{event.name}' deleted"}


# --- Background image management ---


@router.post("/{uid}/background")
async def upload_background(
    uid: str,
    file: UploadFile = File(None),
    preset: str | None = None,
    user: Annotated[CurrentUser, Depends(require_role("admin"))] = None,
    db: AsyncSession = Depends(get_db),
):
    """Upload or select a background image for an event.

    Either upload a file OR specify a preset name via query parameter.
    """
    result = await db.execute(select(Event).where(Event.uid == uid))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    BACKGROUNDS_DIR.mkdir(parents=True, exist_ok=True)

    if preset:
        # Use a preset background
        preset_path = BACKGROUNDS_DIR / "presets" / preset
        if not preset_path.exists():
            raise HTTPException(status_code=404, detail=f"Preset '{preset}' not found")
        # Remove old custom background
        if event.background_image and not event.background_image.startswith("presets/"):
            old_path = BACKGROUNDS_DIR / event.background_image
            if old_path.exists():
                old_path.unlink()
        event.background_image = f"presets/{preset}"
    elif file:
        if not file.content_type or not file.content_type.startswith("image/"):
            raise HTTPException(status_code=400, detail="File must be an image")

        # Remove old custom background
        if event.background_image and not event.background_image.startswith("presets/"):
            old_path = BACKGROUNDS_DIR / event.background_image
            if old_path.exists():
                old_path.unlink()

        # Save new background
        ext = ".png" if "png" in (file.content_type or "") else ".jpg"
        filename = f"event_{uid}_{uuid.uuid4().hex[:8]}{ext}"
        dest = BACKGROUNDS_DIR / filename
        data = await file.read()
        dest.write_bytes(data)
        event.background_image = filename
        logger.info("Background uploaded: %s (%d bytes)", filename, len(data))
    else:
        raise HTTPException(status_code=400, detail="Provide a file or preset name")

    await db.commit()
    await db.refresh(event)
    return {
        "message": "Background updated",
        "background_image": event.background_image,
        "url": f"/api/events/{uid}/background",
    }


@router.get("/{uid}/background")
async def serve_background(
    uid: str,
    db: AsyncSession = Depends(get_db),
):
    """Serve the background image for an event (no auth — used by booth)."""
    result = await db.execute(select(Event).where(Event.uid == uid))
    event = result.scalar_one_or_none()
    if not event or not event.background_image:
        raise HTTPException(status_code=404, detail="No background image")

    path = BACKGROUNDS_DIR / event.background_image
    if not path.exists():
        raise HTTPException(status_code=404, detail="Background file missing")

    media_type = "image/png" if path.suffix == ".png" else "image/jpeg"
    return FileResponse(path, media_type=media_type)


@router.delete("/{uid}/background")
async def delete_background(
    uid: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Remove the background image for an event."""
    result = await db.execute(select(Event).where(Event.uid == uid))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    if event.background_image:
        # Only delete custom uploads, not presets
        if not event.background_image.startswith("presets/"):
            bg_path = BACKGROUNDS_DIR / event.background_image
            if bg_path.exists():
                bg_path.unlink()
        event.background_image = None
        await db.commit()

    return {"message": "Background removed"}


# --- Push bundle for booth sync ---


@router.get("/{uid}/push-bundle")
async def get_push_bundle(
    uid: str,
    user: Annotated[CurrentUser, Depends(require_role("admin"))],
    db: AsyncSession = Depends(get_db),
):
    """Get the full event card configuration for booth sync.

    Returns all data the booth needs to render custom photo cards.
    """
    result = await db.execute(select(Event).where(Event.uid == uid))
    event = result.scalar_one_or_none()
    if not event:
        raise HTTPException(status_code=404, detail="Event not found")

    return {
        "event_uid": event.uid,
        "event_name": event.name,
        "display_date": event.display_date or "",
        "branding_text": event.branding_text or "",
        "background_image": event.background_image,
        "background_url": f"/api/events/{uid}/background" if event.background_image else None,
    }
