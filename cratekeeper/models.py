"""Data models for DJ CLI pipeline."""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
import json
from pathlib import Path


@dataclass
class Track:
    """A single track with Spotify metadata and classification info."""

    id: str
    name: str
    artists: list[str]
    artist_ids: list[str]
    album: str
    duration_ms: int
    isrc: str | None = None
    release_year: int | None = None
    artist_genres: list[str] = field(default_factory=list)
    bucket: str | None = None
    confidence: str = "high"  # high, medium, low
    local_path: str | None = None
    added_at: str | None = None  # ISO 8601 timestamp when track entered source playlist
    mood: str | None = None  # legacy: old mood system (Chill/Groovy/Peak etc.)
    era: str | None = None

    # --- New tag fields ---
    energy: str | None = None  # low / mid / high
    function: list[str] = field(default_factory=list)  # floorfiller, singalong, bridge, reset, closer, opener
    crowd: list[str] = field(default_factory=list)  # mixed-age, older, younger, family
    mood_tags: list[str] = field(default_factory=list)  # feelgood, emotional, euphoric, nostalgic

    # --- Generic tags dict (profile-driven, forward-looking storage) ---
    tags: dict[str, str | list[str]] = field(default_factory=dict)

    # --- Library approval ---
    library_approval: str = "undecided"  # undecided | approved | rejected

    # --- Audio analysis fields (from essentia) ---
    bpm: float | None = None
    key: str | None = None  # e.g. "C major", "A minor"
    danceability: float | None = None  # 0-1
    audio_energy: float | None = None  # raw 0-1 energy from essentia
    audio_mood: dict[str, float] = field(default_factory=dict)  # {happy: 0.8, party: 0.9, ...}
    arousal: float | None = None  # 1-9
    valence: float | None = None  # 1-9

    def display_name(self) -> str:
        return f'"{self.name}" by {", ".join(self.artists)}'

    def compute_era(self) -> str | None:
        """Derive era label from release_year."""
        if not self.release_year:
            return None
        decade = (self.release_year // 10) * 10
        if decade <= 1970:
            return "Oldschool"
        return f"{decade}s"


@dataclass
class LocalTrack:
    """A locally indexed audio file with metadata from ID3/FLAC tags."""

    path: str
    title: str | None = None
    artist: str | None = None
    album: str | None = None
    isrc: str | None = None
    year: int | None = None
    duration_ms: int = 0
    format: str = ""  # mp3, flac, wav, etc.

    def display_name(self) -> str:
        artist = self.artist or "Unknown"
        title = self.title or Path(self.path).stem
        return f'"{title}" by {artist}'


@dataclass
class LocalLibrary:
    """Index of all local audio files."""

    root_path: str
    tracks: list[LocalTrack] = field(default_factory=list)
    scanned_at: str | None = None

    def save(self, path: Path) -> None:
        data = asdict(self)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: Path) -> LocalLibrary:
        data = json.loads(path.read_text())
        tracks = [LocalTrack(**t) for t in data.pop("tracks", [])]
        return cls(tracks=tracks, **data)


@dataclass
class Plan:
    """Base plan — shared fields and serialization for all plan types."""

    source_playlist_id: str
    source_playlist_name: str
    tracks: list[Track] = field(default_factory=list)
    plan_type: str = "event"

    def save(self, path: Path) -> None:
        data = asdict(self)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False))

    @classmethod
    def load(cls, path: Path) -> Plan:
        """Load a plan from JSON, dispatching on plan_type discriminator."""
        data = json.loads(path.read_text())
        tracks = [Track(**t) for t in data.pop("tracks", [])]
        plan_type = data.pop("plan_type", "event")
        if plan_type == "library-import":
            return LibraryImportPlan(tracks=tracks, **data)
        # Default: EventPlan (backward compatible for missing plan_type)
        return EventPlan(tracks=tracks, **data)

    def bucket_summary(self) -> dict[str, list[Track]]:
        """Group tracks by bucket."""
        buckets: dict[str, list[Track]] = {}
        for track in self.tracks:
            bucket = track.bucket or "Unclassified"
            buckets.setdefault(bucket, []).append(track)
        return dict(sorted(buckets.items(), key=lambda x: -len(x[1])))


@dataclass
class EventPlan(Plan):
    """Plan for an event — adds event-specific fields."""

    event_name: str | None = None
    event_date: str | None = None
    created_playlists: dict[str, str] = field(default_factory=dict)  # bucket -> playlist_id
    tidal_playlists: dict[str, str] = field(default_factory=dict)  # bucket -> tidal_playlist_id

    def __post_init__(self) -> None:
        self.plan_type = "event"


@dataclass
class LibraryImportPlan(Plan):
    """Plan for importing a curated playlist into the master library."""

    def __post_init__(self) -> None:
        self.plan_type = "library-import"
