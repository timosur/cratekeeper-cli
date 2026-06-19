"""Build a master library by copying files into Genre/ folder structure."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

from cratekeeper.models import Track
from cratekeeper.pipeline.sorting import sort_tracks

from cratekeeper.pipeline.tag_writer import is_fully_tagged  # re-exported for backward compat

DEFAULT_REQUIRED_FIELDS = ["energy", "function", "crowd", "mood_tags"]


@dataclass
class LibraryPreflight:
    """Result of a pre-flight check before build-library runs.

    ``qualifies`` is True when at least one track will be copied.
    The count fields explain why tracks don't qualify when ``qualifies`` is False.
    """

    candidates: int = 0        # tracks with local_path + bucket
    approved_tagged: int = 0   # candidates that are approved + fully tagged
    undecided: int = 0
    rejected: int = 0
    untagged: int = 0          # approved but missing required tags
    fallback: int = 0          # will use genre_artist fallback due to missing added_at

    @property
    def qualifies(self) -> bool:
        return self.approved_tagged > 0


def library_preflight(
    tracks: list[Track],
    required_fields: list[str] | None = None,
    library_structure: str = "genre_artist",
) -> LibraryPreflight:
    """Return a pre-flight summary without copying any files."""
    candidates = [t for t in tracks if t.local_path and t.bucket]
    approved_tagged = [
        t for t in candidates
        if t.library_approval == "approved" and is_fully_tagged(t, required_fields)
    ]
    fallback = 0
    if library_structure == "genre_year_month":
        fallback = sum(
            1 for t in approved_tagged
            if not t.added_at
        )
    return LibraryPreflight(
        candidates=len(candidates),
        approved_tagged=len(approved_tagged),
        undecided=sum(1 for t in candidates if t.library_approval == "undecided"),
        rejected=sum(1 for t in candidates if t.library_approval == "rejected"),
        untagged=sum(
            1 for t in candidates
            if t.library_approval == "approved" and not is_fully_tagged(t, required_fields)
        ),
        fallback=fallback,
    )


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


def _build_dest_path(
    track: Track,
    target_dir: Path,
    library_structure: str = "genre_artist",
) -> Path:
    """Compute the destination path for a track based on library_structure."""
    genre = _safe_filename(track.bucket)
    source = Path(track.local_path)
    filename = _track_filename(track) + source.suffix

    if library_structure == "genre_year_month" and track.added_at:
        # Parse ISO-8601 timestamp: 2024-03-15T10:00:00Z
        date_part = track.added_at[:10]
        year = date_part[:4]
        month = date_part[5:7]
        dest_dir = target_dir / genre / year / month
    else:
        dest_dir = target_dir / genre

    dest_dir.mkdir(parents=True, exist_ok=True)
    return dest_dir / filename


def build_library(
    tracks: list[Track],
    target_dir: Path,
    progress_callback=None,
    required_fields: list[str] | None = None,
    sort=None,
    library_structure: str = "genre_artist",
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

        dest_path = _build_dest_path(track, target_dir, library_structure)

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
