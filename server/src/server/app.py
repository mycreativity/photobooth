"""FastAPI application — ties together API routes, WebSocket, and database."""
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from server.config import settings
from server.database import async_session, engine
from server.models.db import Base, Booth, Event, User

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

    logger.info("Database tables created")

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

    yield

    # Shutdown
    await engine.dispose()


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

from server.api import auth as auth_api
from server.api import booths as booths_api
from server.api import events as events_api
from server.api import public as public_api
from server.ws import booth_ws, admin_ws

app.include_router(auth_api.router)
app.include_router(booths_api.router)
app.include_router(events_api.router)
app.include_router(public_api.router)
app.include_router(booth_ws.router)
app.include_router(admin_ws.router)


@app.get("/health")
async def health():
    """Health check endpoint."""
    from server.ws.hub import hub
    return {
        "status": "ok",
        "connected_booths": len(hub.connected_booths),
        "booth_ids": hub.connected_booths,
    }
