"""Guarantee that only one photobooth process runs at a time.

Uses an advisory file lock (``fcntl.flock``) held for the lifetime of the
process.  The OS releases the lock automatically when the process exits —
even on a crash — so there are no stale-lockfile problems to clean up.

This is a safety net on top of the deployment (which should only ever
launch the app once, via the X11 kiosk session).  If a second instance is
started anyway — e.g. a stray ``systemctl start photobooth`` alongside the
kiosk — it will refuse to run instead of fighting over the camera.
"""

from __future__ import annotations

import fcntl
import os

DEFAULT_LOCK_PATH = "/tmp/photobooth.lock"


class AlreadyRunningError(RuntimeError):
    """Raised when another photobooth instance already holds the lock."""


def acquire_single_instance_lock(lock_path: str = DEFAULT_LOCK_PATH) -> int:
    """Acquire the single-instance lock and return the held file descriptor.

    The caller MUST keep the returned fd alive for the whole process
    lifetime — closing it (or the process exiting) releases the lock.

    Args:
        lock_path: Path to the lock file. Created if missing.

    Returns:
        The open file descriptor holding the lock.

    Raises:
        AlreadyRunningError: if another process already holds the lock.
    """
    # O_RDONLY is enough for flock and keeps the file openable by any user,
    # so the lock still works if a second instance runs as a different user.
    fd = os.open(lock_path, os.O_RDONLY | os.O_CREAT, 0o644)
    try:
        fcntl.flock(fd, fcntl.LOCK_EX | fcntl.LOCK_NB)
    except OSError as exc:
        os.close(fd)
        raise AlreadyRunningError(
            f"Another photobooth instance is already running (lock: {lock_path})"
        ) from exc
    return fd
