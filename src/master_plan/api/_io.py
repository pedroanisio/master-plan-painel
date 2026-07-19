"""Filesystem helpers shared by the JSON-file repositories.

The stores persist by rewriting a whole JSON file. A plain ``write_text`` can
leave a truncated/corrupt file if the process is killed mid-write (a real risk
in production: container stop, OOM, redeploy). :func:`atomic_write_text` makes
the swap crash-safe by writing to a sibling temp file, flushing it to disk, and
renaming it over the target — ``os.replace`` is atomic on the same filesystem,
so a reader ever sees either the old file or the new one, never a half-written
one.
"""

from __future__ import annotations

import os
import tempfile
from collections.abc import Callable
from pathlib import Path

# Post-write hooks run after a store is durably written to local disk. The
# Spaces mirror registers one here to upload the file, keeping the write path
# unaware of any remote backend (see spaces.py). Kept dependency-free.
_post_write_hooks: list[Callable[[Path], None]] = []


def register_post_write_hook(hook: Callable[[Path], None]) -> None:
    """Register a callback invoked with the path after each atomic write."""
    _post_write_hooks.append(hook)


def clear_post_write_hooks() -> None:
    """Drop all registered post-write hooks (test isolation)."""
    _post_write_hooks.clear()


def atomic_write_text(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write ``text`` to ``path`` atomically (temp file + fsync + os.replace).

    After the local file is in place, any registered post-write hooks run
    (e.g. the Spaces write-through mirror).
    """
    path.parent.mkdir(parents=True, exist_ok=True)
    # Temp file in the same directory guarantees os.replace stays on one
    # filesystem (cross-device renames are not atomic and would raise).
    fd, tmp_name = tempfile.mkstemp(
        dir=path.parent, prefix=f".{path.name}.", suffix=".tmp"
    )
    try:
        with os.fdopen(fd, "w", encoding=encoding) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
    except BaseException:
        # Never leave a stray temp file behind on failure.
        try:
            os.unlink(tmp_name)
        except FileNotFoundError:
            pass
        raise
    for hook in _post_write_hooks:
        hook(path)
