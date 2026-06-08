"""Build a master library by copying files into Genre/ folder structure."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from cratekeeper.models import Track
from cratekeeper.sorting import sort_tracks

DEFAULT_REQUIRED_FIELDS = ["energy", "function", "crowd", "mood_tags"]


def is_fully_tagged(track: Track, required_fields: list[str] | None = None) -> bool:
    """Return True when the track has every profile-required structured tag field.

    ``required_fields`` defaults to the commercial set
    (``energy``, ``function``, ``crowd``, ``mood_tags``) when not supplied,
    preserving the historical admission gate.
    """
    fields = required_fields if required_fields is not None else DEFAULT_REQUIRED_FIELDS
    return all(getattr(track, f, None) for f in fields)


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
    required_fields: list[str] | None = None,
    sort=None,
) -> BuildLibraryResult:
    """Copy approved, fully-tagged local files into Genre/ structure in the target directory.

    Only processes tracks that are:
    - ``library_approval == "approved"``
    - fully tagged for the active profile's ``required_fields``
    - have ``local_path`` and ``bucket`` set

    When ``sort`` is provided, tracks within each genre bucket are processed in
    that order. Returns a :class:`BuildLibraryResult` with disposition counts.
    """
    target_dir = Path(target_dir)
    result = BuildLibraryResult()

    # Order tracks within each bucket per the profile sort rule (stable, so the
    # disposition logic below is unaffected for tracks that don't qualify).
    if sort is not None:
        grouped: dict[str | None, list[Track]] = {}
        for t in tracks:
            grouped.setdefault(t.bucket, []).append(t)
        ordered: list[Track] = []
        for bucket_tracks in grouped.values():
            ordered.extend(sort_tracks(bucket_tracks, sort))
        tracks = ordered

    # Pre-count qualifying tracks so progress_callback receives a meaningful total.
    qualifying_total = sum(
        1 for t in tracks
        if t.library_approval == "approved"
        and is_fully_tagged(t, required_fields)
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

        if not is_fully_tagged(track, required_fields):
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
