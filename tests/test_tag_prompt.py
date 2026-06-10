"""Tests for tag prompt generation."""

from __future__ import annotations

from cratekeeper.models import Track
from cratekeeper.pipeline.tag_prompt import build_tag_prompt
from cratekeeper.pipeline.tag_writer import (
    VALID_CROWD,
    VALID_ENERGY,
    VALID_FUNCTION,
    VALID_MOOD,
)


def _make_track(id: str = "abc123", analyzed: bool = True) -> Track:
    """Create a fixture track with optional analysis data."""
    t = Track(
        id=id,
        name="Riverside",
        artists=["Tems"],
        artist_ids=["art1"],
        album="Born in the Wild",
        duration_ms=210000,
        bucket="rnb",
        era="2020s",
        release_year=2024,
    )
    if analyzed:
        t.bpm = 105.0
        t.key = "C minor"
        t.audio_energy = 0.62
        t.audio_mood = {"happy": 0.4, "relaxed": 0.7, "party": 0.3}
        t.arousal = 4.5
        t.valence = 6.2
    return t


def test_prompt_contains_all_track_ids():
    """4.1: build_tag_prompt returns string containing all track IDs."""
    tracks = [_make_track(id=f"track_{i}") for i in range(5)]
    prompt = build_tag_prompt(tracks)
    for t in tracks:
        assert t.id in prompt, f"Track ID {t.id} not found in prompt"


def test_prompt_contains_all_vocabulary_values():
    """4.2: prompt text contains all vocabulary values from VALID_* constants."""
    tracks = [_make_track()]
    prompt = build_tag_prompt(tracks)

    for val in VALID_ENERGY:
        assert val in prompt, f"VALID_ENERGY value '{val}' not in prompt"
    for val in VALID_FUNCTION:
        assert val in prompt, f"VALID_FUNCTION value '{val}' not in prompt"
    for val in VALID_CROWD:
        assert val in prompt, f"VALID_CROWD value '{val}' not in prompt"
    for val in VALID_MOOD:
        assert val in prompt, f"VALID_MOOD value '{val}' not in prompt"


def test_prompt_contains_json_schema():
    """4.3: prompt text contains JSON schema description with correct field names."""
    tracks = [_make_track()]
    prompt = build_tag_prompt(tracks)

    assert '"id"' in prompt
    assert '"energy"' in prompt
    assert '"function"' in prompt
    assert '"crowd"' in prompt
    assert '"mood_tags"' in prompt
    assert '"genre_suggestion"' in prompt


def test_prompt_with_unanalyzed_tracks():
    """4.5: build_tag_prompt with tracks lacking analysis data still produces valid prompt."""
    tracks = [_make_track(analyzed=False)]
    prompt = build_tag_prompt(tracks)

    # Should still contain the track ID and basic info
    assert "abc123" in prompt
    assert "Riverside" in prompt
    assert "Tems" in prompt
    # Unknown placeholders for missing analysis
    assert "unknown" in prompt
    # Should still have vocabulary and schema
    assert "energy" in prompt
    assert "mood_tags" in prompt


def test_prompt_includes_track_context_fields():
    """Prompt includes per-track context with all analysis fields."""
    tracks = [_make_track()]
    prompt = build_tag_prompt(tracks)

    assert "abc123" in prompt
    assert "Riverside" in prompt
    assert "Tems" in prompt
    assert "rnb" in prompt
    assert "2020s" in prompt
    assert "105" in prompt
    assert "C minor" in prompt
    assert "0.62" in prompt  # audio_energy
    assert "4.5" in prompt  # arousal
    assert "6.2" in prompt  # valence


def test_prompt_ends_with_json_only_instruction():
    """Prompt ends with explicit JSON-only instruction."""
    tracks = [_make_track()]
    prompt = build_tag_prompt(tracks)

    assert "Return ONLY the JSON array" in prompt
    assert "No markdown fences" in prompt


def test_cli_tag_prompt_command(tmp_path):
    """4.4: crate tag-prompt CLI command exits 0 and produces non-empty output."""
    from typer.testing import CliRunner
    from cratekeeper.cli import app
    from cratekeeper.models import EventPlan

    # Create a minimal plan file
    plan = EventPlan(
        source_playlist_id="sp123",
        source_playlist_name="Test Event",
        event_name="Wedding",
        event_date="2026-06-15",
        tracks=[_make_track()],
    )
    plan_file = tmp_path / "plan.json"
    plan.save(plan_file)

    runner = CliRunner()
    result = runner.invoke(app, ["tag-prompt", str(plan_file)])
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert len(result.output) > 100, "Output too short to be a valid prompt"
    assert "abc123" in result.output


def test_cli_tag_prompt_output_flag(tmp_path):
    """crate tag-prompt --output writes to file."""
    from typer.testing import CliRunner
    from cratekeeper.cli import app
    from cratekeeper.models import EventPlan

    plan = EventPlan(
        source_playlist_id="sp123",
        source_playlist_name="Test",
        event_name="Party",
        event_date="2026-01-01",
        tracks=[_make_track()],
    )
    plan_file = tmp_path / "plan.json"
    plan.save(plan_file)

    out_file = tmp_path / "prompt.txt"
    runner = CliRunner()
    result = runner.invoke(app, ["tag-prompt", str(plan_file), "--output", str(out_file)])
    assert result.exit_code == 0, f"CLI failed: {result.output}"
    assert out_file.exists()
    content = out_file.read_text()
    assert "abc123" in content
    assert "Return ONLY the JSON array" in content
