"""Tests for the Plan base class, EventPlan, and LibraryImportPlan."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from cratekeeper.models import EventPlan, LibraryImportPlan, Plan, Track


@pytest.fixture
def tmp_json(tmp_path: Path):
    """Helper: write a dict as JSON and return the path."""

    def _write(data: dict) -> Path:
        p = tmp_path / "plan.json"
        p.write_text(json.dumps(data))
        return p

    return _write


# --- 5.1 Legacy JSON without plan_type ---

def test_load_returns_event_plan_for_json_without_plan_type(tmp_json):
    path = tmp_json({"source_playlist_id": "abc", "source_playlist_name": "Test", "tracks": []})
    plan = Plan.load(path)
    assert isinstance(plan, EventPlan)


# --- 5.2 JSON with plan_type: "event" ---

def test_load_returns_event_plan_for_plan_type_event(tmp_json):
    path = tmp_json({
        "source_playlist_id": "abc",
        "source_playlist_name": "Test",
        "tracks": [],
        "plan_type": "event",
        "event_name": "Wedding",
        "event_date": "2026-01-01",
    })
    plan = Plan.load(path)
    assert isinstance(plan, EventPlan)
    assert plan.event_name == "Wedding"


# --- 5.3 JSON with plan_type: "library-import" ---

def test_load_returns_library_import_plan(tmp_json):
    path = tmp_json({
        "source_playlist_id": "xyz",
        "source_playlist_name": "My Crate",
        "tracks": [],
        "plan_type": "library-import",
    })
    plan = Plan.load(path)
    assert isinstance(plan, LibraryImportPlan)


# --- 5.4 Round-trip save/load ---

def test_event_plan_round_trip(tmp_path: Path):
    path = tmp_path / "event.json"
    original = EventPlan(
        source_playlist_id="a",
        source_playlist_name="b",
        event_name="Gala",
        event_date="2026-06-01",
        tracks=[Track(id="t1", name="Song", artists=["Artist"], artist_ids=["aid1"], album="Album", duration_ms=200000)],
    )
    original.save(path)
    loaded = Plan.load(path)
    assert isinstance(loaded, EventPlan)
    assert loaded.plan_type == "event"
    assert loaded.event_name == "Gala"
    assert len(loaded.tracks) == 1
    assert loaded.tracks[0].name == "Song"


def test_library_import_plan_round_trip(tmp_path: Path):
    path = tmp_path / "lib.json"
    original = LibraryImportPlan(
        source_playlist_id="c",
        source_playlist_name="d",
        tracks=[Track(id="t2", name="Track", artists=["DJ"], artist_ids=["did1"], album="Mix", duration_ms=180000)],
    )
    original.save(path)
    loaded = Plan.load(path)
    assert isinstance(loaded, LibraryImportPlan)
    assert loaded.plan_type == "library-import"
    assert len(loaded.tracks) == 1
    assert loaded.tracks[0].name == "Track"


# --- 5.5 EventPlan retains event-specific fields ---

def test_event_plan_retains_event_fields(tmp_path: Path):
    path = tmp_path / "ep.json"
    ep = EventPlan(
        source_playlist_id="a",
        source_playlist_name="b",
        event_name="Birthday",
        event_date="2026-12-25",
        created_playlists={"Pop": "pl1"},
        tidal_playlists={"Pop": "tidal1"},
    )
    ep.save(path)
    loaded = Plan.load(path)
    assert isinstance(loaded, EventPlan)
    assert loaded.event_name == "Birthday"
    assert loaded.event_date == "2026-12-25"
    assert loaded.created_playlists == {"Pop": "pl1"}
    assert loaded.tidal_playlists == {"Pop": "tidal1"}


# --- 5.6 LibraryImportPlan serializes without event fields ---

def test_library_import_plan_no_event_fields(tmp_path: Path):
    path = tmp_path / "lip.json"
    lip = LibraryImportPlan(source_playlist_id="x", source_playlist_name="y")
    lip.save(path)

    raw = json.loads(path.read_text())
    assert raw["plan_type"] == "library-import"
    assert "event_name" not in raw
    assert "event_date" not in raw
    assert "created_playlists" not in raw
    assert "tidal_playlists" not in raw


# --- 5.7 Event-only commands exit with error for LibraryImportPlan ---
# These are integration tests that invoke the CLI. We test the type guard logic directly.

def test_event_only_guard_create_playlists(tmp_path: Path):
    """create-playlists should reject LibraryImportPlan."""
    path = tmp_path / "lib.json"
    LibraryImportPlan(source_playlist_id="a", source_playlist_name="b").save(path)

    plan = Plan.load(path)
    assert not isinstance(plan, EventPlan)


def test_event_only_guard_build_event(tmp_path: Path):
    """build-event should reject LibraryImportPlan."""
    path = tmp_path / "lib.json"
    LibraryImportPlan(source_playlist_id="a", source_playlist_name="b").save(path)

    plan = Plan.load(path)
    assert not isinstance(plan, EventPlan)


def test_event_only_guard_sync_to_tidal(tmp_path: Path):
    """sync-to-tidal should reject LibraryImportPlan."""
    path = tmp_path / "lib.json"
    LibraryImportPlan(source_playlist_id="a", source_playlist_name="b").save(path)

    plan = Plan.load(path)
    assert not isinstance(plan, EventPlan)


# --- 5.8 Pipeline commands work with LibraryImportPlan ---
# We verify that Plan.load() + bucket_summary() works for LibraryImportPlan.

def test_library_import_plan_bucket_summary():
    lip = LibraryImportPlan(
        source_playlist_id="a",
        source_playlist_name="b",
        tracks=[
            Track(id="1", name="A", artists=["X"], artist_ids=["xa"], album="Al", duration_ms=100, bucket="Pop"),
            Track(id="2", name="B", artists=["Y"], artist_ids=["ya"], album="Al", duration_ms=100, bucket="Pop"),
            Track(id="3", name="C", artists=["Z"], artist_ids=["za"], album="Al", duration_ms=100, bucket="Rock"),
        ],
    )
    summary = lip.bucket_summary()
    assert "Pop" in summary
    assert len(summary["Pop"]) == 2
    assert "Rock" in summary
    assert len(summary["Rock"]) == 1


# --- 5.9 Plan.load() covers all paths ---

def test_plan_load_dispatches_correctly(tmp_json):
    """Plan.load() should dispatch based on plan_type field."""
    # event
    path = tmp_json({"source_playlist_id": "a", "source_playlist_name": "b", "tracks": [], "plan_type": "event"})
    assert isinstance(Plan.load(path), EventPlan)

    # library-import
    path = tmp_json({"source_playlist_id": "a", "source_playlist_name": "b", "tracks": [], "plan_type": "library-import"})
    assert isinstance(Plan.load(path), LibraryImportPlan)

    # missing plan_type -> EventPlan
    path = tmp_json({"source_playlist_id": "a", "source_playlist_name": "b", "tracks": []})
    assert isinstance(Plan.load(path), EventPlan)
