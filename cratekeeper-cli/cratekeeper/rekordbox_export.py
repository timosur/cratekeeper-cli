"""Generate a Rekordbox-compatible XML from a built library.

Walks a profile's built library directory (one subfolder per genre bucket),
reads BPM / key / genre from the audio tags, and emits a ``rekordbox.xml`` with
a ``<COLLECTION>`` of tracks and ``<PLAYLISTS>`` nodes mirroring the buckets.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote
from xml.dom import minidom

import mutagen
from mutagen.flac import FLAC
from mutagen.id3 import ID3
from mutagen.mp4 import MP4

from cratekeeper.models import Track
from cratekeeper.sorting import sort_tracks

AUDIO_EXTENSIONS = {".mp3", ".flac", ".m4a", ".mp4", ".wav", ".aiff", ".aif"}

_KIND = {
    ".mp3": "MP3 File",
    ".flac": "FLAC File",
    ".m4a": "M4A File",
    ".mp4": "M4A File",
    ".wav": "WAV File",
    ".aiff": "AIFF File",
    ".aif": "AIFF File",
}


class EmptyLibraryError(Exception):
    """Raised when the library directory contains no eligible audio files."""


def _read_meta(path: Path) -> dict:
    """Read bpm, key, genre, title, artist from an audio file's tags."""
    bpm = key = genre = title = artist = None
    suffix = path.suffix.lower()
    try:
        if suffix == ".mp3":
            tags = ID3(str(path))
            bpm = _first(tags.get("TBPM"))
            key = _first(tags.get("TKEY"))
            genre = _first(tags.get("TCON"))
            title = _first(tags.get("TIT2"))
            artist = _first(tags.get("TPE1"))
        elif suffix == ".flac":
            audio = FLAC(str(path))
            bpm = _first(audio.get("bpm"))
            key = _first(audio.get("initialkey"))
            genre = _first(audio.get("genre"))
            title = _first(audio.get("title"))
            artist = _first(audio.get("artist"))
        elif suffix in (".m4a", ".mp4"):
            audio = MP4(str(path))
            t = audio.tags or {}
            tmpo = t.get("tmpo")
            bpm = str(tmpo[0]) if tmpo else None
            genre = _first(t.get("\xa9gen"))
            title = _first(t.get("\xa9nam"))
            artist = _first(t.get("\xa9ART"))
            raw_key = t.get("----:com.apple.iTunes:initialkey")
            if raw_key:
                val = raw_key[0]
                key = val.decode("utf-8") if isinstance(val, bytes) else str(val)
        else:
            audio = mutagen.File(str(path), easy=True)
            if audio is not None:
                bpm = _first(audio.get("bpm"))
                genre = _first(audio.get("genre"))
                title = _first(audio.get("title"))
                artist = _first(audio.get("artist"))
    except Exception:
        pass
    return {"bpm": bpm, "key": key, "genre": genre, "title": title, "artist": artist}


def _first(val):
    if val is None:
        return None
    if isinstance(val, list):
        return str(val[0]) if val else None
    return str(val)


def _parse_filename(path: Path) -> tuple[str, str]:
    """Fall back to 'Artist - Title' from the filename stem."""
    stem = path.stem
    if " - " in stem:
        artist, title = stem.split(" - ", 1)
        return artist.strip(), title.strip()
    return "", stem


def collect_library(library_dir: Path, buckets_filter: list[str] | None = None) -> dict[str, list[Track]]:
    """Build {bucket: [Track]} from the library's genre subfolders."""
    library_dir = Path(library_dir)
    grouped: dict[str, list[Track]] = {}
    if not library_dir.is_dir():
        return grouped

    wanted = set(buckets_filter) if buckets_filter else None

    for bucket_dir in sorted(p for p in library_dir.iterdir() if p.is_dir()):
        bucket = bucket_dir.name
        if wanted is not None and bucket not in wanted:
            continue
        for file_path in sorted(bucket_dir.rglob("*")):
            if not file_path.is_file() or file_path.suffix.lower() not in AUDIO_EXTENSIONS:
                continue
            meta = _read_meta(file_path)
            fn_artist, fn_title = _parse_filename(file_path)
            name = meta["title"] or fn_title
            artist = meta["artist"] or fn_artist
            try:
                bpm = float(meta["bpm"]) if meta["bpm"] else None
            except (TypeError, ValueError):
                bpm = None
            track = Track(
                id=str(file_path),
                name=name,
                artists=[artist] if artist else [],
                artist_ids=[],
                album="",
                duration_ms=0,
                bucket=bucket,
                local_path=str(file_path),
                bpm=bpm,
                key=meta["key"],
            )
            grouped.setdefault(bucket, []).append(track)

    return grouped


def _location(path: str) -> str:
    """Rekordbox file location: file://localhost/<url-encoded absolute path>."""
    abs_path = str(Path(path).resolve())
    return "file://localhost" + quote(abs_path)


def build_xml(grouped: dict[str, list[Track]], sort=None) -> str:
    """Build the Rekordbox XML string from grouped tracks."""
    # Assign stable track IDs across the whole collection.
    ordered_buckets = {b: sort_tracks(tracks, sort) for b, tracks in grouped.items()}

    track_ids: dict[str, int] = {}
    next_id = 1
    for tracks in ordered_buckets.values():
        for t in tracks:
            if t.local_path not in track_ids:
                track_ids[t.local_path] = next_id
                next_id += 1

    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")
    ET.SubElement(root, "PRODUCT", Name="Cratekeeper", Version="1.0.0", Company="Cratekeeper")

    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(track_ids)))
    emitted: set[int] = set()
    for tracks in ordered_buckets.values():
        for t in tracks:
            tid = track_ids[t.local_path]
            if tid in emitted:
                continue
            emitted.add(tid)
            attrs = {
                "TrackID": str(tid),
                "Name": t.name or "",
                "Artist": ", ".join(t.artists),
                "Genre": t.bucket or "",
                "Kind": _KIND.get(Path(t.local_path).suffix.lower(), "Unknown"),
                "Location": _location(t.local_path),
            }
            if t.bpm:
                attrs["AverageBpm"] = f"{t.bpm:.2f}"
            if t.key:
                attrs["Tonality"] = t.key
            ET.SubElement(collection, "TRACK", **attrs)

    playlists = ET.SubElement(root, "PLAYLISTS")
    root_node = ET.SubElement(
        playlists, "NODE", Type="0", Name="ROOT", Count=str(len(ordered_buckets))
    )
    for bucket, tracks in ordered_buckets.items():
        node = ET.SubElement(
            root_node, "NODE", Name=bucket, Type="1", KeyType="0", Entries=str(len(tracks))
        )
        for t in tracks:
            ET.SubElement(node, "TRACK", Key=str(track_ids[t.local_path]))

    rough = ET.tostring(root, encoding="utf-8")
    return minidom.parseString(rough).toprettyxml(indent="  ", encoding="UTF-8").decode("utf-8")


def export_rekordbox(
    library_dir: Path,
    output_path: Path,
    buckets_filter: list[str] | None = None,
    sort=None,
) -> tuple[int, int]:
    """Write a rekordbox.xml for the library. Returns (track_count, bucket_count).

    Raises :class:`EmptyLibraryError` when no eligible tracks are found.
    """
    grouped = collect_library(library_dir, buckets_filter)
    track_count = sum(len(v) for v in grouped.values())
    if track_count == 0:
        raise EmptyLibraryError(f"No eligible audio files found under {library_dir}.")

    xml = build_xml(grouped, sort)
    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(xml, encoding="utf-8")
    return track_count, len(grouped)
