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

# --- Single source of truth for structured-tag vocabulary and comment format ---

VALID_ENERGY = {"low", "mid", "high"}
VALID_FUNCTION = {"floorfiller", "singalong", "bridge", "reset", "closer", "opener"}
VALID_CROWD = {"mixed-age", "older", "younger", "family"}
VALID_MOOD = {
    "feelgood", "emotional", "euphoric", "nostalgic",
    "romantic", "melancholic", "dark", "aggressive",
    "uplifting", "dreamy", "funky", "groovy",
}

# Marker that identifies a structured-tags comment embedded in an audio file.
COMMENT_MARKER = "energy:"

# Tag format names (see cratekeeper.config).
STRUCTURED_COMMENT = "structured_comment"
ID3_ONLY = "id3_only"


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


def tag_track(track: Track, tag_format: str = STRUCTURED_COMMENT) -> bool:
    """Write classification metadata into a track's audio file tags.

    ``tag_format`` controls whether the structured comment is written:
    - ``structured_comment``: genre/BPM/key plus the structured comment.
    - ``id3_only``: only genre/BPM/key; no structured comment.

    Returns True if tags were written successfully.
    """
    if not track.local_path:
        return False

    path = Path(track.local_path)
    if not path.exists():
        return False

    write_comment = tag_format != ID3_ONLY
    suffix = path.suffix.lower()

    try:
        if suffix == ".mp3":
            return _tag_mp3(path, track, write_comment)
        elif suffix == ".flac":
            return _tag_flac(path, track, write_comment)
        elif suffix in (".m4a", ".mp4"):
            return _tag_m4a(path, track, write_comment)
        else:
            return _tag_generic(path, track)
    except Exception:
        return False


def _tag_mp3(path: Path, track: Track, write_comment: bool = True) -> bool:
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
    if write_comment:
        comment = _build_comment(track)
        if comment:
            tags.delall("COMM")
            tags.add(COMM(encoding=3, lang="eng", desc="", text=[comment]))

    tags.save(str(path))
    return True


def _tag_flac(path: Path, track: Track, write_comment: bool = True) -> bool:
    """Write tags to a FLAC file."""
    audio = FLAC(str(path))

    if track.bucket:
        audio["genre"] = track.bucket

    if track.bpm:
        audio["bpm"] = str(int(round(track.bpm)))

    if track.key:
        audio["initialkey"] = track.key

    if write_comment:
        comment = _build_comment(track)
        if comment:
            audio["comment"] = comment

    audio.save()
    return True


def _tag_m4a(path: Path, track: Track, write_comment: bool = True) -> bool:
    """Write tags to an M4A/MP4 file using iTunes-style atoms."""
    audio = MP4(str(path))

    if track.bucket:
        audio["\xa9gen"] = [track.bucket]

    if track.bpm:
        audio["tmpo"] = [int(round(track.bpm))]

    if write_comment:
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


DEFAULT_REQUIRED_FIELDS = ["energy", "function", "crowd", "mood_tags"]


def is_fully_tagged(track: Track, required_fields: list[str] | None = None) -> bool:
    """Return True when the track has every profile-required structured tag field."""
    fields = required_fields if required_fields is not None else DEFAULT_REQUIRED_FIELDS
    return all(getattr(track, f, None) for f in fields)


def tag_untagged_files(
    tracks: list[Track],
    audio_dir: Path,
    progress_callback=None,
) -> tuple[int, int, int]:
    """Match untagged tracks to audio files by filename and write basic ID3 metadata.

    Matches tracks from the plan to files in ``audio_dir`` by normalizing
    filenames against track titles. Useful for purchased files missing ID3 tags.

    Returns (tagged_count, not_found_count, error_count).
    """
    import re
    import unicodedata
    from mutagen.mp4 import MP4 as _MP4

    def _norm(text: str) -> str:
        text = text.lower().strip()
        text = unicodedata.normalize("NFKD", text)
        text = "".join(c for c in text if not unicodedata.combining(c))
        text = re.sub(r"[^\w\s]", "", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    audio_files: list[Path] = []
    for ext in ("*.m4a", "*.mp4", "*.flac", "*.mp3"):
        audio_files.extend(audio_dir.rglob(ext))

    file_map: dict[str, Path] = {_norm(f.stem): f for f in audio_files}

    unmatched = [t for t in tracks if not t.local_path]
    tagged = 0
    not_found = 0
    errors = 0

    for track in unmatched:
        norm_title = _norm(track.name)
        matched_file = file_map.get(norm_title)

        if not matched_file:
            for norm_stem, fpath in file_map.items():
                if norm_title in norm_stem or norm_stem in norm_title:
                    matched_file = fpath
                    break

        if not matched_file:
            not_found += 1
            if progress_callback:
                progress_callback(track, None, None)
            continue

        suffix = matched_file.suffix.lower()
        try:
            if suffix in (".m4a", ".mp4"):
                audio = _MP4(str(matched_file))
                audio["\xa9nam"] = [track.name]
                audio["\xa9ART"] = [", ".join(track.artists)]
                audio["\xa9alb"] = [track.album]
                if track.release_year:
                    audio["\xa9day"] = [str(track.release_year)]
                if track.isrc:
                    audio["----:com.apple.iTunes:ISRC"] = [track.isrc.encode("utf-8")]
                audio.save()
            else:
                audio = mutagen.File(str(matched_file), easy=True)
                if audio is None:
                    raise ValueError("Cannot open file")
                audio["title"] = track.name
                audio["artist"] = ", ".join(track.artists)
                audio["album"] = track.album
                if track.release_year:
                    audio["date"] = str(track.release_year)
                audio.save()
            tagged += 1
            if progress_callback:
                progress_callback(track, matched_file, None)
        except Exception as exc:
            errors += 1
            if progress_callback:
                progress_callback(track, matched_file, exc)

    return tagged, not_found, errors


def apply_tags_from_data(
    tracks: list[Track],
    tags_data: list[dict],
) -> tuple[int, int]:
    """Apply pre-classified tags from a list of tag dicts into track objects in-place.

    Each entry in ``tags_data`` is ``{id, energy, function, crowd, mood_tags, genre_suggestion}``.
    Returns (applied_count, warning_count).
    """
    track_map = {t.id: t for t in tracks}
    applied = 0
    warnings = 0

    for entry in tags_data:
        tid = entry.get("id")
        track = track_map.get(tid)
        if not track:
            warnings += 1
            continue

        energy = entry.get("energy")
        if energy and energy in VALID_ENERGY:
            track.energy = energy

        funcs = entry.get("function", [])
        track.function = [f for f in funcs if f in VALID_FUNCTION]

        crowd = entry.get("crowd", [])
        track.crowd = [c for c in crowd if c in VALID_CROWD]

        mood_tags = entry.get("mood_tags", [])
        track.mood_tags = [m for m in mood_tags if m in VALID_MOOD]

        genre = entry.get("genre_suggestion")
        if genre and genre != track.bucket:
            track.bucket = genre

        applied += 1

    return applied, warnings


def tag_tracks(tracks: list[Track], progress_callback=None, tag_format: str = STRUCTURED_COMMENT) -> tuple[int, int]:
    """Write tags for all tracks with a local_path.

    Returns (success_count, fail_count).
    """
    candidates = [t for t in tracks if t.local_path]
    success = 0
    failed = 0

    for i, track in enumerate(candidates):
        ok = tag_track(track, tag_format)
        if ok:
            success += 1
        else:
            failed += 1
        if progress_callback:
            progress_callback(i + 1, len(candidates), track, ok)

    return success, failed
