"""Tests for profile-specific tagging: validation, prompt, comment builder."""

from __future__ import annotations

import pytest

from cratekeeper.config import TagConfig, TagFieldDef, default_tag_config
from cratekeeper.models import Track
from cratekeeper.pipeline.tag_prompt import build_tag_prompt
from cratekeeper.pipeline.tag_writer import _build_comment, apply_tags_from_data


def _electronic_config() -> TagConfig:
    return TagConfig(
        fields={
            "energy": TagFieldDef(name="energy", type="single", values=["low", "mid", "high"]),
            "function": TagFieldDef(
                name="function", type="list",
                values=["warm-up", "build", "peak-time", "breakdown", "cooldown", "closer"],
                pick=(1, 3),
            ),
            "mood_tags": TagFieldDef(
                name="mood_tags", type="list",
                values=["hypnotic", "driving", "atmospheric", "deep", "acidic",
                         "industrial", "melodic", "dark", "euphoric", "groovy"],
                pick=(1, 4),
            ),
            "mix_traits": TagFieldDef(
                name="mix_traits", type="list",
                values=["loop-friendly", "long-intro", "long-outro", "vocal",
                         "instrumental", "acapella-section"],
                pick=(1, 3),
            ),
        },
        guidance="Classify for a club/festival DJ set.",
    )


def _make_track(id: str = "t1") -> Track:
    return Track(
        id=id, name="Track", artists=["DJ"], artist_ids=["a1"],
        album="Album", duration_ms=300000, bpm=128.0, key="A minor",
    )


# --- apply_tags strict validation ---

class TestApplyTagsValidation:
    def test_rejects_unknown_vocabulary(self):
        """7.4: apply_tags rejects values not in profile vocabulary."""
        tc = _electronic_config()
        tracks = [_make_track()]
        data = [{"id": "t1", "energy": "high", "function": ["floorfiller"], "mood_tags": ["driving"], "mix_traits": ["vocal"]}]
        applied, warnings, errors = apply_tags_from_data(tracks, data, tag_config=tc)
        assert applied == 0
        assert warnings == 1
        assert any("floorfiller" in e for e in errors)

    def test_respects_pick_range_max(self):
        """7.5: apply_tags rejects list exceeding max pick."""
        tc = _electronic_config()
        tracks = [_make_track()]
        data = [{"id": "t1", "energy": "high", "function": ["warm-up", "build", "peak-time", "closer"], "mood_tags": ["driving"], "mix_traits": ["vocal"]}]
        applied, warnings, errors = apply_tags_from_data(tracks, data, tag_config=tc)
        assert applied == 0
        assert any("4 values given" in e for e in errors)

    def test_rejects_array_for_single_field(self):
        """7.5: apply_tags rejects array for single-type field."""
        tc = _electronic_config()
        tracks = [_make_track()]
        data = [{"id": "t1", "energy": ["low", "mid"], "function": ["build"], "mood_tags": ["driving"], "mix_traits": ["vocal"]}]
        applied, warnings, errors = apply_tags_from_data(tracks, data, tag_config=tc)
        assert applied == 0
        assert any("single value" in e for e in errors)

    def test_accepts_valid_electronic_tags(self):
        """Valid electronic vocabulary accepted."""
        tc = _electronic_config()
        tracks = [_make_track()]
        data = [{"id": "t1", "energy": "high", "function": ["peak-time"], "mood_tags": ["euphoric", "driving"], "mix_traits": ["loop-friendly"]}]
        applied, warnings, errors = apply_tags_from_data(tracks, data, tag_config=tc)
        assert applied == 1
        assert warnings == 0
        assert tracks[0].tags["energy"] == "high"
        assert tracks[0].tags["function"] == ["peak-time"]
        assert tracks[0].tags["mix_traits"] == ["loop-friendly"]

    def test_populates_legacy_fields(self):
        """apply_tags populates legacy Track fields for backward compat."""
        tc = _electronic_config()
        tracks = [_make_track()]
        data = [{"id": "t1", "energy": "mid", "function": ["cooldown"], "mood_tags": ["deep"], "mix_traits": ["vocal"]}]
        apply_tags_from_data(tracks, data, tag_config=tc)
        assert tracks[0].energy == "mid"
        assert tracks[0].function == ["cooldown"]
        assert tracks[0].mood_tags == ["deep"]


# --- Prompt builder ---

class TestPromptBuilder:
    def test_renders_profile_vocabulary(self):
        """7.6: build_tag_prompt renders profile-specific vocabulary."""
        tc = _electronic_config()
        tracks = [_make_track()]
        prompt = build_tag_prompt(tracks, tag_config=tc)
        assert "warm-up" in prompt
        assert "peak-time" in prompt
        assert "loop-friendly" in prompt
        assert "hypnotic" in prompt
        # Must NOT contain commercial-only values
        assert "singalong" not in prompt
        assert "family" not in prompt
        assert "crowd" not in prompt

    def test_includes_guidance(self):
        """Prompt includes profile guidance."""
        tc = _electronic_config()
        prompt = build_tag_prompt([_make_track()], tag_config=tc)
        assert "club/festival DJ set" in prompt

    def test_default_prompt_backward_compat(self):
        """7.9: No tag_config produces legacy vocabulary."""
        prompt = build_tag_prompt([_make_track()])
        assert "floorfiller" in prompt
        assert "mixed-age" in prompt
        assert "euphoric" in prompt


# --- Comment builder ---

class TestCommentBuilder:
    def test_uses_profile_field_order(self):
        """7.7: comment builder uses profile fields in definition order."""
        tc = _electronic_config()
        track = _make_track()
        track.tags = {
            "energy": "high",
            "function": ["peak-time"],
            "mood_tags": ["driving"],
            "mix_traits": ["loop-friendly"],
        }
        track.era = "2020s"
        comment = _build_comment(track, tc)
        # era always first, then fields in definition order
        assert comment.startswith("era:2020s")
        assert "energy:high" in comment
        assert "function:peak-time" in comment
        assert "mood_tags:driving" in comment
        assert "mix_traits:loop-friendly" in comment
        # No crowd field
        assert "crowd" not in comment

    def test_falls_back_to_legacy_fields(self):
        """Comment builder falls back to legacy Track fields."""
        tc = default_tag_config()
        track = _make_track()
        track.energy = "mid"
        track.function = ["bridge"]
        track.crowd = ["mixed-age"]
        track.mood_tags = ["nostalgic"]
        comment = _build_comment(track, tc)
        assert "energy:mid" in comment
        assert "function:bridge" in comment
        assert "crowd:mixed-age" in comment
        assert "mood_tags:nostalgic" in comment

    def test_default_config_backward_compat(self):
        """7.9: default TagConfig produces same comment fields as before."""
        track = _make_track()
        track.energy = "high"
        track.function = ["floorfiller"]
        track.crowd = ["younger"]
        track.mood_tags = ["euphoric"]
        track.era = "90s"
        comment = _build_comment(track)
        assert "era:90s; energy:high; function:floorfiller; crowd:younger; mood_tags:euphoric" == comment


# --- Integration: end-to-end electronic profile ---

class TestElectronicIntegration:
    def test_tag_prompt_apply_tags_roundtrip(self):
        """7.8: end-to-end tag-prompt → apply-tags with electronic profile."""
        tc = _electronic_config()
        tracks = [_make_track("t1"), _make_track("t2")]
        tracks[1].id = "t2"

        # Generate prompt
        prompt = build_tag_prompt(tracks, tag_config=tc)
        assert "mix_traits" in prompt

        # Simulate LLM response
        tags_data = [
            {"id": "t1", "energy": "high", "function": ["peak-time"], "mood_tags": ["euphoric"], "mix_traits": ["loop-friendly"]},
            {"id": "t2", "energy": "low", "function": ["warm-up"], "mood_tags": ["atmospheric", "deep"], "mix_traits": ["long-intro"]},
        ]

        applied, warnings, errors = apply_tags_from_data(tracks, tags_data, tag_config=tc)
        assert applied == 2
        assert warnings == 0
        assert tracks[0].tags["mix_traits"] == ["loop-friendly"]
        assert tracks[1].tags["function"] == ["warm-up"]
