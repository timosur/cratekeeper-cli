"""Build a master library by copying files into Genre/ folder structure."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from cratekeeper.models import Track


def is_fully_tagged(track: Track) -> bool:
    """Return True when track carries all required structured tags for library admission."""
    return bool(track.energy and track.function and track.crowd and track.mood_tags)


@dataclass
class BuildLibraryResult:
    """Counts for each disposition category from a build-library run."""

    copied: int = 0
    already_existed: int = 0
    rejected: int = 0
    undecided: int = 0
    missing_tags: int = 0
    missing: list[Track] = field(default_factory=list)  # no local file or no bucket


def _safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename."""
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, '-')
    return name.strip('. ')


def _track_filename(track: Track) -> str:
    """Build a filename from track metadata: Artist - Title.ext"""
    artist = ", ".join(track.artists) if track.artists else "Unknown"
    title = track.name or "Unknown"
    return _safe_filename(f"{artist} - {title}")


def build_library(
    tracks: list[Track],
    target_dir: Path,
    progress_callback=None,
) -> BuildLibraryResult:
    """Copy approved, fully-tagged local files into Genre/ structure in the target directory.

    Only processes tracks that are:
    - ``library_approval == "approved"``
    - fully tagged (energy, function, crowd, mood_tags all non-empty)
    - have ``local_path`` and ``bucket`` set

    Returns a :class:`BuildLibraryResult` with counts for all disposition categories.
    """
    target_dir = Path(target_dir)
    result = BuildLibraryResult()

    # Pre-count qualifying tracks so progress_callback receives a meaningful total.
    qualifying_total = sum(
        1 for t in tracks
        if t.library_approval == "approved"
        and is_fully_tagged(t)
        and t.local_path
        and t.bucket
    )
    qualifying_idx = 0

    for track in tracks:
        if not track.local_path or not track.bucket:
            result.missing.append(track)
            continue

        if track.library_approval == "rejected":
            result.rejected += 1
            continue

        if track.library_approval == "undecided":
            result.undecided += 1
            continue

        if not is_fully_tagged(track):
            result.missing_tags += 1
            continue

        # Track is approved + fully tagged + has local_path + bucket.
        source = Path(track.local_path)
        if not source.exists():
            result.missing.append(track)
            continue

        genre = _safe_filename(track.bucket)
        filename = _track_filename(track) + source.suffix
        dest_dir = target_dir / genre
        dest_dir.mkdir(parents=True, exist_ok=True)
        dest_path = dest_dir / filename

        if dest_path.exists():
            result.already_existed += 1
        else:
            shutil.copy2(str(source), str(dest_path))
            result.copied += 1

        track.local_path = str(dest_path)

        qualifying_idx += 1
        if progress_callback:
            progress_callback(qualifying_idx, qualifying_total, track, dest_path)

    return result
