"""Photo upload and serving API endpoints."""
import logging
import os
import uuid
from datetime import datetime, timedelta, timezone
from io import BytesIO
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.auth.permissions import require_role, CurrentUser
from api.database import get_db
from api.models.db import Photo, Session, Event

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/photos", tags=["photos"])

PHOTOS_DIR = Path(os.getenv("PHOTOS_DIR", "/data/photos"))


@router.post("/upload")
async def upload_photo(
    file: UploadFile = File(...),
    event_id: str = Form(""),
    booth_id: str = Form(""),
    session_id: str = Form(""),
    seq: int = Form(1),
    variant: str = Form("final"),
    db: AsyncSession = Depends(get_db),
):
    """Upload a photo from a booth.

    Creates session if session_id is empty.
    Stores file under: /data/photos/{event_id}/{session_id}/{variant}_{seq}.jpg

    AC5: Idempotent — duplicate uploads (same booth_id+session_id+seq+variant)
    return the existing photo without creating a new record.

    AC8: Rejects uploads to events that expired more than 24h ago (HTTP 410).
    """
    if not file.content_type or not file.content_type.startswith("image/"):
        raise HTTPException(status_code=400, detail="File must be an image")

    # AC8: Event soft expiration guard
    if event_id:
        ev_result = await db.execute(
            select(Event).where(Event.id == event_id)
        )
        ev = ev_result.scalar_one_or_none()
        if ev and ev.end_date:
            expiry = ev.end_date + timedelta(hours=24)
            if datetime.now(timezone.utc) > expiry:
                raise HTTPException(
                    status_code=410,
                    detail="Event expired — uploads no longer accepted",
                )

    # AC5: Deduplication — check if photo already exists
    if booth_id and session_id:
        existing_result = await db.execute(
            select(Photo).where(
                Photo.booth_id == booth_id,
                Photo.session_id == session_id,
                Photo.seq == seq,
                Photo.variant == variant,
            )
        )
        existing = existing_result.scalar_one_or_none()
        if existing:
            logger.info(
                "Duplicate upload skipped: booth=%s session=%s seq=%d variant=%s",
                booth_id, session_id, seq, variant,
            )
            return {
                "id": existing.id,
                "session_id": session_id,
                "filename": existing.filename,
                "width": existing.width,
                "height": existing.height,
            }

    # Read file data
    data = await file.read()
    if len(data) < 100:
        raise HTTPException(status_code=400, detail="File too small")

    # Create session if needed
    if not session_id:
        session = Session(
            event_id=event_id or None,
            booth_id=booth_id or None,
        )
        db.add(session)
        await db.flush()
        session_id = session.id

    # Build storage path
    event_dir = event_id or "unsorted"
    rel_dir = Path(event_dir) / session_id
    abs_dir = PHOTOS_DIR / rel_dir
    abs_dir.mkdir(parents=True, exist_ok=True)

    filename = f"{variant}_{seq}.jpg"
    rel_path = str(rel_dir / filename)
    abs_path = abs_dir / filename
    abs_path.write_bytes(data)

    # Get dimensions
    width, height = 0, 0
    try:
        from PIL import Image
        img = Image.open(BytesIO(data))
        width, height = img.size
    except Exception:
        pass

    # Save to DB
    photo = Photo(
        session_id=session_id,
        event_id=event_id or None,
        booth_id=booth_id or None,
        seq=seq,
        variant=variant,
        filename=rel_path,
        width=width,
        height=height,
        size_bytes=len(data),
    )
    db.add(photo)

    # Update session photo count
    result = await db.execute(
        select(Session).where(Session.id == session_id)
    )
    session = result.scalar_one_or_none()
    if session:
        session.photo_count = (session.photo_count or 0) + 1

    await db.commit()

    logger.info(
        "Photo uploaded: event=%s session=%s seq=%d variant=%s (%dx%d, %d bytes)",
        event_id, session_id, seq, variant, width, height, len(data),
    )

    return {
        "id": photo.id,
        "session_id": session_id,
        "session_token": session.token if session else None,
        "filename": rel_path,
        "width": width,
        "height": height,
    }
