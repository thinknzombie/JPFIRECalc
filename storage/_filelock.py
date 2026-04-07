"""
Portable file locking for JSON storage.

Uses msvcrt on Windows and fcntl on POSIX (Linux/macOS).
Provides a context manager that acquires an exclusive lock on a
dedicated .lock file next to the target path.
"""
from __future__ import annotations

import os
import sys
from contextlib import contextmanager
from pathlib import Path


@contextmanager
def file_lock(target_path: Path):
    """
    Acquire an exclusive lock on ``target_path.lock``.

    Usage::

        with file_lock(Path("data/settings.json")):
            # read / write the file safely
            ...
    """
    lock_path = target_path.with_suffix(target_path.suffix + ".lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fd = os.open(str(lock_path), os.O_CREAT | os.O_RDWR)
    try:
        if sys.platform == "win32":
            import msvcrt
            msvcrt.locking(fd, msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_EX)
        yield
    finally:
        if sys.platform == "win32":
            import msvcrt
            try:
                msvcrt.locking(fd, msvcrt.LK_UNLCK, 1)
            except OSError:
                pass
        else:
            import fcntl
            fcntl.flock(fd, fcntl.LOCK_UN)
        os.close(fd)
