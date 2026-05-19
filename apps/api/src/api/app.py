"""FastAPI application — ties together API routes, WebSocket, and database."""
import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from api.config import settings
from api.database import async_session, engine
from api.models.db import Base, Booth, Event, User
from api.ws.hub import hub

logger = logging.getLogger(__name__)


# --- App lifecycle ---

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Startup: create tables + seed admin user."""
    # Ensure data directories exist
    os.makedirs(settings.photos_dir, exist_ok=True)

    # Create tables
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

        # Lightweight migration: add new columns to existing tables
        # SQLAlchemy's create_all won't add columns to existing tables
        import sqlalchemy as sa

        # Booth columns
        for col_name, col_def in [
            ("api_key_hash", "VARCHAR(64)"),
            ("event_id", "VARCHAR(36)"),
        ]:
            try:
                await conn.execute(sa.text(
                    f"ALTER TABLE booths ADD COLUMN {col_name} {col_def}"
                ))
                logger.info("Added column booths.%s", col_name)
            except Exception:
                pass  # Column already exists

        # Event photo card columns
        for col_name, col_def in [
            ("background_image", "VARCHAR(500)"),
            ("branding_text", "TEXT"),
            ("display_date", "VARCHAR(100)"),
            ("end_date", "DATETIME"),
        ]:
            try:
                await conn.execute(sa.text(
                    f"ALTER TABLE events ADD COLUMN {col_name} {col_def}"
                ))
                logger.info("Added column events.%s", col_name)
            except Exception:
                pass  # Column already exists

    logger.info("Database tables created")

    # AC4: Reset all booth statuses to "offline" on startup (crash recovery)
    async with async_session() as db:
        import sqlalchemy as sa_reset
        await db.execute(sa_reset.text("UPDATE booths SET status = 'offline'"))
        await db.commit()
        logger.info("All booths reset to offline on startup")

    # Seed admin user
    async with async_session() as db:
        from sqlalchemy import select
        result = await db.execute(
            select(User).where(User.email == settings.admin_email)
        )
        if not result.scalar_one_or_none():
            admin = User(
                email=settings.admin_email,
                role="admin",
                name="Admin",
            )
            db.add(admin)
            await db.commit()
            logger.info("Seeded admin user: %s", settings.admin_email)
        else:
            logger.info("Admin user exists: %s", settings.admin_email)

    # AC6: Start stale heartbeat monitor background task
    monitor_task = asyncio.create_task(_heartbeat_monitor())

    yield

    # Shutdown
    monitor_task.cancel()
    try:
        await monitor_task
    except asyncio.CancelledError:
        pass
    await engine.dispose()


async def _heartbeat_monitor():
    """Background task: detect stale booths (no heartbeat for 30s+).

    Runs every 30 seconds. If a booth hasn't sent a heartbeat within
    3× the default heartbeat_interval (10s), it's considered stale
    and marked offline in the database.
    """
    while True:
        await asyncio.sleep(30)
        try:
            stale = hub.get_stale_booths(max_age_seconds=30)
            if stale:
                async with async_session() as db:
                    import sqlalchemy as sa_hb
                    for booth_id in stale:
                        await db.execute(
                            sa_hb.text(
                                "UPDATE booths SET status = 'offline' "
                                "WHERE booth_id = :bid"
                            ),
                            {"bid": booth_id},
                        )
                    await db.commit()
                    logger.info(
                        "Stale heartbeat: marked %d booth(s) offline: %s",
                        len(stale), stale,
                    )
        except asyncio.CancelledError:
            raise
        except Exception as e:
            logger.error("Heartbeat monitor error: %s", e)


# --- Create app ---

app = FastAPI(
    title="Photobooth Admin API",
    version="0.1.0",
    description="REST API + WebSocket hub voor photobooth beheer",
    lifespan=lifespan,
    docs_url=None,         # Disable Swagger UI
    redoc_url="/docs",     # ReDoc at /docs
)

# CORS — allow admin and public frontends
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        f"https://{settings.admin_url.split('//')[1] if '//' in settings.admin_url else settings.admin_url}",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# --- Include routers ---

from api.api import auth as auth_api
from api.api import booths as booths_api
from api.api import events as events_api
from api.api import photos as photos_api
from api.api import public as public_api
from api.ws import booth_ws, admin_ws

app.include_router(auth_api.router)
app.include_router(booths_api.router)
app.include_router(events_api.router)
app.include_router(photos_api.router)
app.include_router(public_api.router)
app.include_router(booth_ws.router)
app.include_router(admin_ws.router)


@app.get("/health")
async def health():
    """Health check endpoint."""
    from api.ws.hub import hub
    return {
        "status": "ok",
        "connected_booths": len(hub.connected_booths),
        "booth_ids": hub.connected_booths,
    }
