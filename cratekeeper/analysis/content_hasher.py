"""Content hashing utility for audio file deduplication."""

from __future__ import annotations

import hashlib
from pathlib import Path

_CHUNK_SIZE = 8192  # 8KB chunks to avoid memory spikes on large files


def compute_content_hash(file_path: str | Path) -> str | None:
    """Compute SHA256 hash of file content, streaming in chunks.

    Args:
        file_path: Path to the audio file.

    Returns:
        Hex digest string, or None if the file is missing/unreadable.
    """
    path = Path(file_path)
    if not path.exists():
        return None

    try:
        sha256 = hashlib.sha256()
        with open(path, "rb") as f:
            while chunk := f.read(_CHUNK_SIZE):
                sha256.update(chunk)
        return sha256.hexdigest()
    except (OSError, PermissionError):
        return None
