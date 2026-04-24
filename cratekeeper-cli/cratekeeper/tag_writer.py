"""Write genre, BPM, key, and structured tags into audio file ID3/FLAC tags.

Tag mapping:
- Genre (TCON / genre): bucket name
- BPM (TBPM / bpm): beats per minute
- Key (TKEY / initialkey): musical key
- Comment (COMM / comment): structured tags string
  Format: era:90s; energy:high; function:floorfiller,singalong; crowd:mixed-age; mood:feelgood,euphoric
"""

from __future__ import annotations

from pathlib import Path

import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3, TCON, COMM, TBPM, TKEY
from mutagen.mp4 import MP4

from cratekeeper.models import Track


def _build_comment(track: Track) -> str:
    """Build the structured tags comment string."""
    parts = []

    era = track.era or track.compute_era()
    if era:
        parts.append(f"era:{era}")

    if track.energy:
        parts.append(f"energy:{track.energy}")

    if track.function:
        parts.append(f"function:{','.join(track.function)}")

    if track.crowd:
        parts.append(f"crowd:{','.join(track.crowd)}")

    if track.mood_tags:
        parts.append(f"mood:{','.join(track.mood_tags)}")

    return "; ".join(parts)


def tag_track(track: Track) -> bool:
    """Write classification metadata into a track's audio file tags.

    Returns True if tags were written successfully.
    """
    if not track.local_path:
        return False

    path = Path(track.local_path)
    if not path.exists():
        return False

    suffix = path.suffix.lower()

    try:
        if suffix == ".mp3":
            return _tag_mp3(path, track)
        elif suffix == ".flac":
            return _tag_flac(path, track)
        elif suffix in (".m4a", ".mp4"):
            return _tag_m4a(path, track)
        else:
            return _tag_generic(path, track)
    except Exception:
        return False


def _tag_mp3(path: Path, track: Track) -> bool:
    """Write tags to an MP3 file using ID3."""
    try:
        tags = ID3(str(path))
    except mutagen.id3.ID3NoHeaderError:
        tags = ID3()

    # Genre (TCON)
    if track.bucket:
        tags.delall("TCON")
        tags.add(TCON(encoding=3, text=[track.bucket]))

    # BPM (TBPM)
    if track.bpm:
        tags.delall("TBPM")
        tags.add(TBPM(encoding=3, text=[str(int(round(track.bpm)))]))

    # Key (TKEY)
    if track.key:
        tags.delall("TKEY")
        tags.add(TKEY(encoding=3, text=[track.key]))

    # Structured tags comment
    comment = _build_comment(track)
    if comment:
        tags.delall("COMM")
        tags.add(COMM(encoding=3, lang="eng", desc="", text=[comment]))

    tags.save(str(path))
    return True


def _tag_flac(path: Path, track: Track) -> bool:
    """Write tags to a FLAC file."""
    audio = FLAC(str(path))

    if track.bucket:
        audio["genre"] = track.bucket

    if track.bpm:
        audio["bpm"] = str(int(round(track.bpm)))

    if track.key:
        audio["initialkey"] = track.key

    comment = _build_comment(track)
    if comment:
        audio["comment"] = comment

    audio.save()
    return True


def _tag_m4a(path: Path, track: Track) -> bool:
    """Write tags to an M4A/MP4 file using iTunes-style atoms."""
    audio = MP4(str(path))

    if track.bucket:
        audio["\xa9gen"] = [track.bucket]

    if track.bpm:
        audio["tmpo"] = [int(round(track.bpm))]

    comment = _build_comment(track)
    if comment:
        audio["\xa9cmt"] = [comment]

    # Key — no standard MP4 atom, store as freeform
    if track.key:
        audio["----:com.apple.iTunes:initialkey"] = [
            track.key.encode("utf-8")
        ]

    audio.save()
    return True


def _tag_generic(path: Path, track: Track) -> bool:
    """Try to write tags using mutagen's easy interface."""
    audio = mutagen.File(str(path), easy=True)
    if audio is None:
        return False

    if track.bucket:
        audio["genre"] = track.bucket

    audio.save()
    return True


def tag_tracks(tracks: list[Track], progress_callback=None) -> tuple[int, int]:
    """Write tags for all tracks with a local_path.

    Returns (success_count, fail_count).
    """
    candidates = [t for t in tracks if t.local_path]
    success = 0
    failed = 0

    for i, track in enumerate(candidates):
        ok = tag_track(track)
        if ok:
            success += 1
        else:
            failed += 1
        if progress_callback:
            progress_callback(i + 1, len(candidates), track, ok)

    return success, failed
