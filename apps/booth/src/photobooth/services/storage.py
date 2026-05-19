"""Photo storage service.

Handles saving captured photos to disk and recording metadata in SQLite.

Hierarchy: **events** → **sessions** → **photos**.

- An **event** groups all activity for an occasion (e.g. "Wedding Jan & Lisa").
  Exactly one event can be *active* at a time.  The app requires an active
  event before the booth can be used.
- A **session** is one full capture flow: tap-to-start → capture → review → done.
- A **photo** is a single JPEG image.  Each photo can have multiple
  **variants** (original, filtered, retouched, final, etc.).

Photo files are stored on disk under::

    photos/<event_slug>/session_NNNN/<variant>_<seq>.jpg

Database schema
───────────────

    events
        id          INTEGER PRIMARY KEY
        name        TEXT UNIQUE          -- display name
        slug        TEXT UNIQUE          -- filesystem-safe folder name
        created_at  TEXT (ISO 8601)
        is_active   INTEGER (0/1)

    settings
        key         TEXT PRIMARY KEY
        value       TEXT
        updated_at  TEXT (ISO 8601)

    sessions
        id          INTEGER PRIMARY KEY
        event_id    INTEGER REFERENCES events(id)
        created_at  TEXT (ISO 8601)
        layout      TEXT                 -- single / strip / grid
        filter_name TEXT                 -- classic / vintage_love / …
        theme       TEXT
        language    TEXT
        camera      TEXT
        photo_count INTEGER

    photos
        id          INTEGER PRIMARY KEY
        session_id  INTEGER REFERENCES sessions(id)
        event_id    INTEGER REFERENCES events(id)
        seq         INTEGER              -- 1-based index within session
        variant     TEXT                 -- original / filter / retouch / brightness / glamour / final
        filename    TEXT                 -- relative to photo_dir
        width       INTEGER
        height      INTEGER
        size_bytes  INTEGER
        created_at  TEXT (ISO 8601)
"""

from __future__ import annotations

import logging
import re
import sqlite3
from datetime import datetime, timezone
from pathlib import Path

from PIL import Image

logger = logging.getLogger(__name__)


def _slugify(name: str) -> str:
    """Convert a human-readable event name into a filesystem-safe slug.

    Examples:
        "Wedding Jan & Lisa" → "wedding-jan-lisa"
        "Verjaardag Pieter!" → "verjaardag-pieter"
    """
    slug = name.lower().strip()
    slug = re.sub(r"[^\w\s-]", "", slug)   # strip non-word chars (except hyphen)
    slug = re.sub(r"[\s_]+", "-", slug)    # collapse whitespace / underscores
    slug = re.sub(r"-{2,}", "-", slug)     # collapse multiple hyphens
    slug = slug.strip("-")
    return slug or "event"


class StorageService:
    """Manages photo files on disk and metadata in SQLite.

    Directory layout::

        photos/
        ├── wedding-jan-lisa/
        │   ├── session_0001/
        │   │   ├── original_1.jpg
        │   │   ├── filter_golden_hour_1.jpg
        │   │   ├── final_1.jpg
        │   │   └── ...
        │   └── session_0002/
        │       └── ...
        └── verjaardag-pieter/
            └── ...
    """

    def __init__(self, photo_dir: str = "photos", database: str = "photobooth.db") -> None:
        self._photo_dir = Path(photo_dir)
        self._db_path = Path(database)
        self._conn: sqlite3.Connection | None = None
        self._init_db()
        self._migrate_db()
        self._init_dirs()

    # ------------------------------------------------------------------
    # Database initialisation & migration
    # ------------------------------------------------------------------

    def _init_db(self) -> None:
        """Create the database and tables if they don't exist."""
        self._conn = sqlite3.connect(str(self._db_path), check_same_thread=False)
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA journal_mode=WAL")
        self._conn.execute("PRAGMA foreign_keys=ON")

        self._conn.executescript("""
            CREATE TABLE IF NOT EXISTS events (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                name        TEXT NOT NULL UNIQUE,
                slug        TEXT NOT NULL UNIQUE,
                created_at  TEXT NOT NULL,
                is_active   INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS sessions (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                event_id    INTEGER REFERENCES events(id),
                created_at  TEXT NOT NULL,
                event_name  TEXT NOT NULL DEFAULT '',
                layout      TEXT NOT NULL DEFAULT '',
                filter_name TEXT NOT NULL DEFAULT '',
                theme       TEXT NOT NULL DEFAULT '',
                language    TEXT NOT NULL DEFAULT '',
                camera      TEXT NOT NULL DEFAULT '',
                photo_count INTEGER NOT NULL DEFAULT 0
            );

            CREATE TABLE IF NOT EXISTS photos (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id  INTEGER NOT NULL REFERENCES sessions(id),
                event_id    INTEGER REFERENCES events(id),
                seq         INTEGER NOT NULL,
                variant     TEXT NOT NULL DEFAULT 'original',
                filename    TEXT NOT NULL,
                width       INTEGER NOT NULL DEFAULT 0,
                height      INTEGER NOT NULL DEFAULT 0,
                size_bytes  INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_photos_session
                ON photos(session_id);

            CREATE TABLE IF NOT EXISTS settings (
                key         TEXT PRIMARY KEY,
                value       TEXT NOT NULL DEFAULT '',
                updated_at  TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS upload_queue (
                id          INTEGER PRIMARY KEY AUTOINCREMENT,
                file_path   TEXT NOT NULL,
                event_id    TEXT,
                session_id  TEXT,
                seq         INTEGER NOT NULL DEFAULT 1,
                variant     TEXT NOT NULL DEFAULT 'final',
                retries     INTEGER NOT NULL DEFAULT 0,
                created_at  TEXT NOT NULL
            );
        """)
        self._conn.commit()
        logger.info("Database initialized: %s", self._db_path)

    def _migrate_db(self) -> None:
        """Add any missing columns to existing tables.

        SQLite's CREATE TABLE IF NOT EXISTS does not alter an existing
        table, so new columns must be added explicitly.
        """
        # --- sessions table migrations ---
        existing_sessions = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(sessions)").fetchall()
        }
        session_migrations: list[tuple[str, str]] = [
            ("event_name", "ALTER TABLE sessions ADD COLUMN event_name TEXT NOT NULL DEFAULT ''"),
            ("photo_count", "ALTER TABLE sessions ADD COLUMN photo_count INTEGER NOT NULL DEFAULT 0"),
            ("event_id", "ALTER TABLE sessions ADD COLUMN event_id INTEGER REFERENCES events(id)"),
            ("layout", "ALTER TABLE sessions ADD COLUMN layout TEXT NOT NULL DEFAULT ''"),
            ("filter_name", "ALTER TABLE sessions ADD COLUMN filter_name TEXT NOT NULL DEFAULT ''"),
        ]
        for col, stmt in session_migrations:
            if col not in existing_sessions:
                self._conn.execute(stmt)
                logger.info("Migrated sessions table: added column '%s'", col)

        # --- photos table migrations ---
        existing_photos = {
            row[1]
            for row in self._conn.execute("PRAGMA table_info(photos)").fetchall()
        }
        photo_migrations: list[tuple[str, str]] = [
            ("event_id", "ALTER TABLE photos ADD COLUMN event_id INTEGER REFERENCES events(id)"),
            ("variant", "ALTER TABLE photos ADD COLUMN variant TEXT NOT NULL DEFAULT 'original'"),
        ]
        for col, stmt in photo_migrations:
            if col not in existing_photos:
                self._conn.execute(stmt)
                logger.info("Migrated photos table: added column '%s'", col)

        # Create indexes on migrated columns (safe if they already exist)
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_photos_event ON photos(event_id)"
        )
        self._conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_sessions_event ON sessions(event_id)"
        )

        self._conn.commit()

    def _init_dirs(self) -> None:
        """Ensure the photo root directory exists."""
        self._photo_dir.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------
    # Event management
    # ------------------------------------------------------------------

    def create_event(self, name: str) -> int:
        """Create a new event and make it active.

        Deactivates any previously active event first.
        Generates a filesystem-safe slug for the folder name.

        Args:
            name: Human-readable event name (must be unique).

        Returns:
            The new event's ID.

        Raises:
            ValueError: If the name is empty or already exists.
        """
        name = name.strip()
        if not name:
            raise ValueError("Event name cannot be empty")

        if self.event_name_exists(name):
            raise ValueError(f"Event name already exists: {name!r}")

        slug = _slugify(name)
        # Ensure slug uniqueness by appending a counter if needed
        base_slug = slug
        counter = 1
        while self._conn.execute(
            "SELECT 1 FROM events WHERE slug = ?", (slug,)
        ).fetchone():
            counter += 1
            slug = f"{base_slug}-{counter}"

        now = datetime.now(timezone.utc).isoformat()

        # Deactivate current active event
        self._conn.execute("UPDATE events SET is_active = 0 WHERE is_active = 1")

        # Create new active event
        cursor = self._conn.execute(
            "INSERT INTO events (name, slug, created_at, is_active) VALUES (?, ?, ?, 1)",
            (name, slug, now),
        )
        self._conn.commit()
        event_id = cursor.lastrowid

        # Create the event directory
        event_dir = self._photo_dir / slug
        event_dir.mkdir(parents=True, exist_ok=True)

        logger.info("Event %d created: %r (slug=%r)", event_id, name, slug)
        return event_id

    def get_active_event(self) -> dict | None:
        """Return the currently active event, or None if no event is active."""
        row = self._conn.execute(
            "SELECT * FROM events WHERE is_active = 1 LIMIT 1"
        ).fetchone()
        return dict(row) if row else None

    def event_name_exists(self, name: str) -> bool:
        """Check whether an event with this name already exists."""
        row = self._conn.execute(
            "SELECT 1 FROM events WHERE name = ?", (name.strip(),)
        ).fetchone()
        return row is not None

    def reset_active_event(self) -> None:
        """Deactivate the current event without deleting any data.

        After this call, ``get_active_event()`` returns ``None`` and the
        app should block usage until a new event is created.
        """
        self._conn.execute("UPDATE events SET is_active = 0 WHERE is_active = 1")
        self._conn.commit()
        logger.info("Active event reset — no event is active")

    def get_event_session_count(self, event_id: int) -> int:
        """Number of sessions for a specific event."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM sessions WHERE event_id = ?", (event_id,)
        ).fetchone()
        return row[0]

    def get_event_photo_count(self, event_id: int) -> int:
        """Number of photos for a specific event (all variants)."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM photos WHERE event_id = ?", (event_id,)
        ).fetchone()
        return row[0]

    # ------------------------------------------------------------------
    # Session management
    # ------------------------------------------------------------------

    def create_session(
        self,
        event_name: str = "",
        theme: str = "",
        language: str = "",
        camera: str = "",
        event_id: int | None = None,
        layout: str = "",
        filter_name: str = "",
    ) -> int:
        """Start a new photo session.

        Returns:
            The session ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            """INSERT INTO sessions
               (event_id, created_at, event_name, layout, filter_name, theme, language, camera)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (event_id, now, event_name, layout, filter_name, theme, language, camera),
        )
        self._conn.commit()
        session_id = cursor.lastrowid
        logger.info(
            "Session %d created (event_id=%s, event=%r, layout=%r, filter=%r)",
            session_id, event_id, event_name, layout, filter_name,
        )
        return session_id

    def get_session(self, session_id: int) -> dict | None:
        """Retrieve session metadata."""
        row = self._conn.execute(
            "SELECT * FROM sessions WHERE id = ?", (session_id,)
        ).fetchone()
        return dict(row) if row else None

    def get_session_photos(self, session_id: int) -> list[dict]:
        """Retrieve all photos for a session, ordered by sequence."""
        rows = self._conn.execute(
            "SELECT * FROM photos WHERE session_id = ? ORDER BY seq, variant",
            (session_id,),
        ).fetchall()
        return [dict(r) for r in rows]

    # ------------------------------------------------------------------
    # Photo management
    # ------------------------------------------------------------------

    def _get_event_slug(self, event_id: int | None) -> str:
        """Resolve the folder slug for an event.  Falls back to 'unsorted'."""
        if event_id is None:
            return "unsorted"
        row = self._conn.execute(
            "SELECT slug FROM events WHERE id = ?", (event_id,)
        ).fetchone()
        return row[0] if row else "unsorted"

    def save_photo(
        self,
        session_id: int,
        seq: int,
        jpeg_data: bytes,
        variant: str = "original",
        event_id: int | None = None,
    ) -> str:
        """Save a photo to disk and record it in the database.

        Args:
            session_id: The session this photo belongs to.
            seq: 1-based sequence number within the session.
            jpeg_data: Raw JPEG bytes.
            variant: Photo variant (original, filter, retouch, brightness, glamour, final).
            event_id: The event this photo belongs to.

        Returns:
            The relative file path (relative to photo_dir).
        """
        now = datetime.now(timezone.utc)
        event_slug = self._get_event_slug(event_id)
        session_dir = f"session_{session_id:04d}"
        rel_dir = Path(event_slug) / session_dir
        abs_dir = self._photo_dir / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)

        # Write file
        filename = f"{variant}_{seq}.jpg"
        rel_path = rel_dir / filename
        abs_path = abs_dir / filename
        abs_path.write_bytes(jpeg_data)

        # Get image dimensions
        width, height = self._get_image_dimensions(jpeg_data)

        # Record in database
        self._conn.execute(
            """INSERT INTO photos
               (session_id, event_id, seq, variant, filename, width, height, size_bytes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, event_id, seq, variant, str(rel_path),
             width, height, len(jpeg_data), now.isoformat()),
        )
        # Update session photo count
        self._conn.execute(
            "UPDATE sessions SET photo_count = photo_count + 1 WHERE id = ?",
            (session_id,),
        )
        self._conn.commit()

        logger.info(
            "Photo saved: session=%d seq=%d variant=%s path=%s (%dx%d, %d bytes)",
            session_id, seq, variant, rel_path, width, height, len(jpeg_data),
        )
        return str(rel_path)

    def replace_photo(
        self,
        session_id: int,
        seq: int,
        jpeg_data: bytes,
        variant: str = "original",
        event_id: int | None = None,
    ) -> str:
        """Replace an existing photo (e.g. after a retake).

        Overwrites the file on disk and updates the database row.
        Does NOT change the session photo_count.

        Args:
            session_id: The session this photo belongs to.
            seq: 1-based sequence number to replace.
            jpeg_data: New JPEG bytes.
            variant: Photo variant to replace.
            event_id: The event this photo belongs to.

        Returns:
            The relative file path.
        """
        now = datetime.now(timezone.utc)
        event_slug = self._get_event_slug(event_id)
        session_dir = f"session_{session_id:04d}"
        rel_dir = Path(event_slug) / session_dir
        abs_dir = self._photo_dir / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)

        filename = f"{variant}_{seq}.jpg"
        rel_path = rel_dir / filename
        abs_path = abs_dir / filename
        abs_path.write_bytes(jpeg_data)

        width, height = self._get_image_dimensions(jpeg_data)

        # Update existing row or insert if missing
        existing = self._conn.execute(
            "SELECT id FROM photos WHERE session_id = ? AND seq = ? AND variant = ?",
            (session_id, seq, variant),
        ).fetchone()

        if existing:
            self._conn.execute(
                """UPDATE photos
                   SET filename = ?, width = ?, height = ?, size_bytes = ?, created_at = ?,
                       event_id = ?
                   WHERE session_id = ? AND seq = ? AND variant = ?""",
                (str(rel_path), width, height, len(jpeg_data), now.isoformat(),
                 event_id, session_id, seq, variant),
            )
        else:
            self._conn.execute(
                """INSERT INTO photos
                   (session_id, event_id, seq, variant, filename, width, height, size_bytes, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (session_id, event_id, seq, variant, str(rel_path),
                 width, height, len(jpeg_data), now.isoformat()),
            )
        self._conn.commit()

        logger.info(
            "Photo replaced: session=%d seq=%d variant=%s path=%s (%dx%d, %d bytes)",
            session_id, seq, variant, rel_path, width, height, len(jpeg_data),
        )
        return str(rel_path)

    def save_final_variants(
        self,
        session_id: int,
        event_id: int | None,
        photos: list[bytes],
        original_photos: list[bytes],
        filter_name: str = "classic",
        effects: dict[str, bool] | None = None,
    ) -> None:
        """Save all final photo variants for a completed session.

        Stores the original capture, the final processed version, and
        optionally intermediate variants for each active effect.

        Args:
            session_id: Current session ID.
            event_id: Active event ID.
            photos: Final processed JPEG bytes (with all effects applied).
            original_photos: Raw unfiltered JPEG bytes.
            filter_name: Name of the applied filter.
            effects: Dict of active effects {"retouch": bool, "brightness": bool, "glamour": bool}.
        """
        from photobooth.services.processing import (
            apply_filter_to_jpeg, auto_retouch, brightness_boost,
        )

        effects = effects or {}

        for i, (final, original) in enumerate(zip(photos, original_photos)):
            seq = i + 1
            if not final or not original:
                continue

            # 1. Save original (raw capture, no filter)
            self.save_photo(session_id, seq, original,
                            variant="original", event_id=event_id)

            # 2. Save filtered version (if filter applied)
            if filter_name and filter_name != "classic":
                filtered = apply_filter_to_jpeg(original, filter_name)
                self.save_photo(session_id, seq, filtered,
                                variant=f"filter_{filter_name}", event_id=event_id)

            # 3. Save final version (with all effects)
            self.save_photo(session_id, seq, final,
                            variant="final", event_id=event_id)

        # Update session metadata
        self._conn.execute(
            "UPDATE sessions SET layout = ?, filter_name = ? WHERE id = ?",
            ("", filter_name, session_id),
        )
        self._conn.commit()

        logger.info(
            "Final variants saved: session=%d, %d photos, filter=%s, effects=%s",
            session_id, len(photos), filter_name, effects,
        )

    def save_print_composite(
        self,
        session_id: int,
        event_id: int | None,
        layout: str,
        composite_jpeg: bytes,
    ) -> str:
        """Save the composited print image for a session.

        Args:
            session_id: Current session ID.
            event_id: Active event ID.
            layout: Layout name (single, strip, grid).
            composite_jpeg: JPEG bytes of the composited print image.

        Returns:
            Relative file path to the saved composite.
        """
        now = datetime.now(timezone.utc)
        event_slug = self._get_event_slug(event_id)
        session_dir = f"session_{session_id:04d}"
        rel_dir = Path(event_slug) / session_dir
        abs_dir = self._photo_dir / rel_dir
        abs_dir.mkdir(parents=True, exist_ok=True)

        filename = f"print_{layout}.jpg"
        rel_path = rel_dir / filename
        abs_path = abs_dir / filename
        abs_path.write_bytes(composite_jpeg)

        width, height = self._get_image_dimensions(composite_jpeg)

        self._conn.execute(
            """INSERT INTO photos
               (session_id, event_id, seq, variant, filename, width, height, size_bytes, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (session_id, event_id, 0, f"print_{layout}", str(rel_path),
             width, height, len(composite_jpeg), now.isoformat()),
        )
        self._conn.commit()

        logger.info(
            "Print composite saved: session=%d layout=%s path=%s (%dx%d, %d bytes)",
            session_id, layout, rel_path, width, height, len(composite_jpeg),
        )
        return str(rel_path)

    def get_photo_path(self, rel_path: str) -> Path:
        """Get the absolute path for a relative photo path."""
        return self._photo_dir / rel_path

    def get_session_count(self) -> int:
        """Total number of sessions."""
        row = self._conn.execute("SELECT COUNT(*) FROM sessions").fetchone()
        return row[0]

    def get_photo_count(self) -> int:
        """Total number of photos."""
        row = self._conn.execute("SELECT COUNT(*) FROM photos").fetchone()
        return row[0]

    # ------------------------------------------------------------------
    # Settings key-value store
    # ------------------------------------------------------------------

    def get_setting(self, key: str, default: str = "") -> str:
        """Read a single setting value. Returns *default* if not set."""
        row = self._conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row[0] if row else default

    def set_setting(self, key: str, value: str) -> None:
        """Insert or update a setting."""
        now = datetime.now(timezone.utc).isoformat()
        self._conn.execute(
            "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value, updated_at = excluded.updated_at",
            (key, value, now),
        )
        self._conn.commit()
        logger.info("Setting saved: %s = %r", key, value)

    def get_all_settings(self) -> dict[str, str]:
        """Return all settings as a flat dict."""
        rows = self._conn.execute("SELECT key, value FROM settings").fetchall()
        return {row[0]: row[1] for row in rows}

    def close(self) -> None:
        """Close the database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None
            logger.info("Database connection closed")

    @staticmethod
    def _get_image_dimensions(jpeg_data: bytes) -> tuple[int, int]:
        """Extract width and height from JPEG data without full decode."""
        from io import BytesIO
        try:
            img = Image.open(BytesIO(jpeg_data))
            return img.size  # (width, height)
        except Exception:
            return (0, 0)

    # ------------------------------------------------------------------
    # Upload queue (AC1: offline photo queue)
    # ------------------------------------------------------------------

    def enqueue_upload(
        self,
        file_path: str,
        event_id: str = "",
        session_id: str = "",
        seq: int = 1,
        variant: str = "final",
    ) -> int:
        """Add a failed photo upload to the retry queue.

        Returns:
            The queue entry ID.
        """
        now = datetime.now(timezone.utc).isoformat()
        cursor = self._conn.execute(
            """INSERT INTO upload_queue
               (file_path, event_id, session_id, seq, variant, retries, created_at)
               VALUES (?, ?, ?, ?, ?, 0, ?)""",
            (file_path, event_id, session_id, seq, variant, now),
        )
        self._conn.commit()
        queue_id = cursor.lastrowid
        logger.info("Queued upload: %s (id=%d)", file_path, queue_id)
        return queue_id

    def get_pending_uploads(self, limit: int = 5) -> list[dict]:
        """Get the oldest pending uploads from the queue.

        Only returns entries with retries < 50 (max retries).
        """
        rows = self._conn.execute(
            "SELECT * FROM upload_queue WHERE retries < 50 "
            "ORDER BY created_at ASC LIMIT ?",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]

    def dequeue_upload(self, queue_id: int) -> None:
        """Remove a successfully uploaded entry from the queue."""
        self._conn.execute(
            "DELETE FROM upload_queue WHERE id = ?", (queue_id,)
        )
        self._conn.commit()

    def increment_retries(self, queue_id: int) -> None:
        """Increment the retry counter for a failed upload."""
        self._conn.execute(
            "UPDATE upload_queue SET retries = retries + 1 WHERE id = ?",
            (queue_id,),
        )
        self._conn.commit()

    def get_upload_queue_count(self) -> int:
        """Number of pending uploads in the queue."""
        row = self._conn.execute(
            "SELECT COUNT(*) FROM upload_queue WHERE retries < 50"
        ).fetchone()
        return row[0]
