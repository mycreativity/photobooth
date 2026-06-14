"""Unit tests for the single-instance lock.

Regression cover for: the app must only ever run once. Two instances
fight over the camera (black/missing preview) and double the CPU load.
"""

import os

import pytest

from photobooth.single_instance import (
    AlreadyRunningError,
    acquire_single_instance_lock,
)


class TestSingleInstanceLock:
    def test_first_acquire_succeeds(self, tmp_path):
        fd = acquire_single_instance_lock(str(tmp_path / "pb.lock"))
        assert isinstance(fd, int)
        os.close(fd)

    def test_second_acquire_is_refused(self, tmp_path):
        """The whole point: a second holder must be rejected, not allowed."""
        lock = str(tmp_path / "pb.lock")
        fd = acquire_single_instance_lock(lock)
        try:
            with pytest.raises(AlreadyRunningError):
                acquire_single_instance_lock(lock)
        finally:
            os.close(fd)

    def test_lock_is_released_on_close(self, tmp_path):
        """Releasing the lock (process exit) must let a new instance start."""
        lock = str(tmp_path / "pb.lock")
        fd1 = acquire_single_instance_lock(lock)
        os.close(fd1)  # simulates the previous process exiting
        fd2 = acquire_single_instance_lock(lock)  # must succeed now
        os.close(fd2)

    def test_no_leftover_lock_file_blocks_startup(self, tmp_path):
        """A stale lock *file* (not held) must not block a fresh start."""
        lock = tmp_path / "pb.lock"
        lock.write_text("")  # leftover file, nobody holding the flock
        fd = acquire_single_instance_lock(str(lock))
        os.close(fd)
