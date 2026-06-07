"""Build flat, tag-driven event folders by copying fully-tagged files."""

from __future__ import annotations

import shutil
from dataclasses import dataclass, field
from pathlib import Path

import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.mp4 import MP4

from cratekeeper.models import Track


def _safe_filename(name: str) -> str:
    """Sanitize a string for use as a filename component."""
    for ch in ['/', '\\', ':', '*', '?', '"', '<', '>', '|']:
        name = name.replace(ch, '-')
    return name.strip('. ')


def _track_filename(track: Track) -> str:
    """Build a base filename (no extension) from track metadata: Artist - Title"""
    artist = ", ".join(track.artists) if track.artists else "Unknown"
    title = track.name or "Unknown"
    return _safe_filename(f"{artist} - {title}")


def _is_fully_tagged(track: Track) -> bool:
    """Return True when the track plan has all required structured tag fields."""
    return bool(track.energy and track.function and track.crowd and track.mood_tags)


def _has_embedded_comment(path: Path) -> bool:
    """Return True when the audio file has an embedded structured-tags comment.

    Looks for a non-empty comment field containing 'energy:' — the marker
    written by ``crate tag`` — across MP3, FLAC, and M4A/MP4 formats.
    Falls back to True for unknown formats (can't verify, don't block).
    """
    suffix = path.suffix.lower()
    try:
        if suffix == ".mp3":
            tags = ID3(str(path))
            comm_keys = [k for k in tags.keys() if k.startswith("COMM")]
            for key in comm_keys:
                val = str(tags[key])
                if "energy:" in val:
                    return True
            return False
        elif suffix == ".flac":
            audio = FLAC(str(path))
            comment = " ".join(audio.get("comment", []))
            return "energy:" in comment
        elif suffix in (".m4a", ".mp4"):
            audio = MP4(str(path))
            comment_vals = audio.get("\xa9cmt", [])
            comment = " ".join(str(v) for v in comment_vals)
            return "energy:" in comment
        else:
            audio = mutagen.File(str(path))
            if audio is None:
                return True  # unknown format — allow through
            comment = ""
            for key in ("comment", "COMM", "\xa9cmt"):
                val = audio.get(key)
                if val:
                    comment = " ".join(str(v) for v in (val if isinstance(val, list) else [val]))
                    break
            return "energy:" in comment if comment else True
    except Exception:
        return False


@dataclass
class BuildEventResult:
    """Counts for each disposition category from a build-event run."""

    copied: int = 0
    already_existed: int = 0
    missing_tracks: list[Track] = field(default_factory=list)    # no local file / file gone
    untagged_tracks: list[Track] = field(default_factory=list)   # plan tags missing, no embedded comment, or collision
    collision_tracks: list[Track] = field(default_factory=list)  # filename claimed by a different source file


def build_event_folder(
    tracks: list[Track],
    output_dir: Path,
    progress_callback=None,
) -> BuildEventResult:
    """Copy eligible tracks flat into output_dir (no Genre/ subfolders).

    A track is eligible only when it:
    - has a ``local_path`` that exists on disk
    - passes the plan-field tag gate (energy, function, crowd, mood_tags)
    - has an embedded structured-tags comment in the audio file
    - does not collide with a filename already claimed in this run

    Writes ``_missing.txt`` and ``_untagged.txt`` report files.
    Returns a :class:`BuildEventResult`.
    """
    output_dir = Path(output_dir)
    result = BuildEventResult()

    # Track which dest filenames have been claimed this run (base → source path)
    # to detect intra-run collisions for files not yet on disk.
    claimed: dict[str, Path] = {}

    eligible_total = sum(
        1 for t in tracks
        if t.local_path
        and Path(t.local_path).exists()
        and _is_fully_tagged(t)
        and _has_embedded_comment(Path(t.local_path))
    )
    eligible_idx = 0

    for track in tracks:
        # Gate 1: local file exists
        if not track.local_path:
            result.missing_tracks.append(track)
            continue
        source = Path(track.local_path)
        if not source.exists():
            result.missing_tracks.append(track)
            continue

        # Gate 2: plan JSON fields fully tagged
        if not _is_fully_tagged(track):
            result.untagged_tracks.append(track)
            continue

        # Gate 3: embedded comment present in the audio file
        if not _has_embedded_comment(source):
            result.untagged_tracks.append(track)
            continue

        # Gate 4: filename collision — first write wins
        base_name = _track_filename(track) + source.suffix
        dest_path = output_dir / base_name

        if base_name in claimed and claimed[base_name] != source:
            result.collision_tracks.append(track)
            result.untagged_tracks.append(track)
            continue

        claimed[base_name] = source

        if dest_path.exists():
            result.already_existed += 1
        else:
            output_dir.mkdir(parents=True, exist_ok=True)
            shutil.copy2(str(source), str(dest_path))
            result.copied += 1

        eligible_idx += 1
        if progress_callback:
            progress_callback(eligible_idx, eligible_total, track, dest_path)

    # Write report files
    if result.missing_tracks:
        missing_file = output_dir / "_missing.txt"
        output_dir.mkdir(parents=True, exist_ok=True)
        lines = [f"{t.display_name()} (ISRC: {t.isrc or 'none'})" for t in result.missing_tracks]
        missing_file.write_text("\n".join(lines))

    if result.untagged_tracks:
        untagged_file = output_dir / "_untagged.txt"
        output_dir.mkdir(parents=True, exist_ok=True)
        lines = []
        for t in result.untagged_tracks:
            reason = "collision" if t in result.collision_tracks else "missing tags / not embedded"
            lines.append(f"{t.display_name()} [{reason}]")
        untagged_file.write_text("\n".join(lines))

    return result
