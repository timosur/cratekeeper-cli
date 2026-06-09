"""Tests for the interactive wizard module."""

from __future__ import annotations

from cratekeeper.models import EventPlan, Track
from cratekeeper.wizard import (
    EVENT_PIPELINE,
    LIBRARY_PIPELINE,
    Step,
    _analyze_mood_complete,
    _apply_tags_complete,
    _classify_complete,
    _enrich_complete,
    _fetch_complete,
    _match_complete,
    _review_library_complete,
    detect_resume_index,
)


def _make_track(**overrides) -> Track:
    defaults = dict(
        id="t1", name="Track", artists=["Artist"], artist_ids=["a1"],
        album="Album", duration_ms=200000,
    )
    defaults.update(overrides)
    return Track(**defaults)


def _make_plan(tracks=None, **kw) -> EventPlan:
    return EventPlan(
        source_playlist_id="sp:123",
        source_playlist_name="Test",
        tracks=tracks or [],
        **kw,
    )


# ---------------------------------------------------------------------------
# 6.1 Pipeline definitions
# ---------------------------------------------------------------------------

class TestPipelineDefinitions:
    def test_event_pipeline_step_count(self):
        assert len(EVENT_PIPELINE) == 11

    def test_library_pipeline_step_count(self):
        assert len(LIBRARY_PIPELINE) == 11

    def test_event_pipeline_ordering(self):
        ids = [s.id for s in EVENT_PIPELINE]
        assert ids == [
            "fetch", "classify", "enrich", "review", "match",
            "analyze-mood", "apply-tags", "tag",
            "create-playlists", "sync-to-tidal", "build-event",
        ]

    def test_library_pipeline_ordering(self):
        ids = [s.id for s in LIBRARY_PIPELINE]
        assert ids == [
            "scan", "import-library", "classify", "enrich", "match",
            "analyze-mood", "apply-tags", "tag",
            "review-library", "build-library", "export-rekordbox",
        ]

    def test_event_pipeline_optional_steps(self):
        optional = [s.id for s in EVENT_PIPELINE if not s.required]
        assert set(optional) == {"enrich", "review", "create-playlists", "sync-to-tidal"}

    def test_library_pipeline_optional_steps(self):
        optional = [s.id for s in LIBRARY_PIPELINE if not s.required]
        assert set(optional) == {"enrich", "export-rekordbox"}

    def test_all_steps_have_run_callable(self):
        for step in EVENT_PIPELINE + LIBRARY_PIPELINE:
            assert callable(step.run), f"Step {step.id} missing run callable"

    def test_all_steps_have_is_complete_callable(self):
        for step in EVENT_PIPELINE + LIBRARY_PIPELINE:
            assert callable(step.is_complete), f"Step {step.id} missing is_complete"


# ---------------------------------------------------------------------------
# 6.3 is_complete functions
# ---------------------------------------------------------------------------

class TestIsComplete:
    def test_fetch_empty(self):
        plan = _make_plan(tracks=[])
        assert _fetch_complete(plan) is False

    def test_fetch_with_tracks(self):
        plan = _make_plan(tracks=[_make_track()])
        assert _fetch_complete(plan) is True

    def test_classify_no_buckets(self):
        plan = _make_plan(tracks=[_make_track(bucket=None)])
        assert _classify_complete(plan) is False

    def test_classify_all_bucketed(self):
        plan = _make_plan(tracks=[_make_track(bucket="Pop")])
        assert _classify_complete(plan) is True

    def test_enrich_no_isrc(self):
        plan = _make_plan(tracks=[_make_track(isrc=None, artist_genres=[])])
        assert _enrich_complete(plan) is True  # nothing to enrich

    def test_enrich_missing_genres(self):
        plan = _make_plan(tracks=[_make_track(isrc="US1234", artist_genres=[])])
        assert _enrich_complete(plan) is False

    def test_enrich_all_have_genres(self):
        plan = _make_plan(tracks=[_make_track(isrc="US1234", artist_genres=["pop"])])
        assert _enrich_complete(plan) is True

    def test_match_no_local_path(self):
        plan = _make_plan(tracks=[_make_track(bucket="Pop", local_path=None)])
        assert _match_complete(plan) is False

    def test_match_all_matched(self):
        plan = _make_plan(tracks=[_make_track(bucket="Pop", local_path="/music/track.mp3")])
        assert _match_complete(plan) is True

    def test_analyze_mood_incomplete(self):
        plan = _make_plan(tracks=[_make_track(local_path="/a.mp3", bpm=None)])
        assert _analyze_mood_complete(plan) is False

    def test_analyze_mood_complete(self):
        plan = _make_plan(tracks=[_make_track(
            local_path="/a.mp3", bpm=128.0, audio_mood={"happy": 0.8},
        )])
        assert _analyze_mood_complete(plan) is True

    def test_apply_tags_incomplete(self):
        plan = _make_plan(tracks=[_make_track(local_path="/a.mp3", energy=None)])
        assert _apply_tags_complete(plan) is False

    def test_apply_tags_complete(self):
        plan = _make_plan(tracks=[_make_track(
            local_path="/a.mp3", energy="high", function=["floorfiller"],
        )])
        assert _apply_tags_complete(plan) is True

    def test_review_library_undecided(self):
        plan = _make_plan(tracks=[_make_track(
            bucket="Pop", local_path="/a.mp3", library_approval="undecided",
        )])
        assert _review_library_complete(plan) is False

    def test_review_library_all_decided(self):
        plan = _make_plan(tracks=[_make_track(
            bucket="Pop", local_path="/a.mp3", library_approval="approved",
        )])
        assert _review_library_complete(plan) is True


# ---------------------------------------------------------------------------
# 6.2 Progress detection
# ---------------------------------------------------------------------------

class TestProgressDetection:
    def test_empty_plan_starts_at_zero(self):
        plan = _make_plan(tracks=[])
        idx = detect_resume_index(EVENT_PIPELINE, plan)
        assert idx == 0  # fetch not complete

    def test_fetched_plan_resumes_at_classify(self):
        plan = _make_plan(tracks=[_make_track(bucket=None)])
        idx = detect_resume_index(EVENT_PIPELINE, plan)
        assert idx == 1  # fetch done, classify not

    def test_classified_plan_resumes_at_enrich(self):
        plan = _make_plan(tracks=[_make_track(bucket="Pop", isrc="US123", artist_genres=[])])
        idx = detect_resume_index(EVENT_PIPELINE, plan)
        assert idx == 2  # classify done, enrich not

    def test_fully_enriched_classified_skips_to_match(self):
        plan = _make_plan(tracks=[_make_track(
            bucket="Pop", isrc="US123", artist_genres=["pop"], local_path=None,
        )])
        idx = detect_resume_index(EVENT_PIPELINE, plan)
        # enrich is complete, review always returns False, so index=3 (review)
        assert idx == 3

    def test_matched_plan_stops_at_review(self):
        """Review step always returns is_complete=False (display-only), so resume stops there."""
        plan = _make_plan(tracks=[_make_track(
            bucket="Pop", isrc="US123", artist_genres=["pop"],
            local_path="/a.mp3", bpm=None,
        )])
        idx = detect_resume_index(EVENT_PIPELINE, plan)
        # review (idx=3) is_complete always returns False — by design it's optional
        # and always "incomplete" since it's a display-only step
        assert idx == 3


# ---------------------------------------------------------------------------
# 6.4 Wizard flow (structure tests — no actual execution)
# ---------------------------------------------------------------------------

class TestWizardFlowStructure:
    def test_step_dataclass_fields(self):
        step = Step(id="test", label="Test Step", required=True)
        assert step.id == "test"
        assert step.label == "Test Step"
        assert step.required is True
        assert step.needs_docker is False
        assert step.needs_input == []
        assert callable(step.run)
        assert callable(step.is_complete)

    def test_docker_step_flagged(self):
        docker_steps = [s for s in EVENT_PIPELINE if s.needs_docker]
        assert len(docker_steps) == 1
        assert docker_steps[0].id == "analyze-mood"

    def test_input_steps_have_prompts(self):
        from cratekeeper.wizard import INPUT_PROMPTS
        for step in EVENT_PIPELINE + LIBRARY_PIPELINE:
            for key in step.needs_input:
                assert key in INPUT_PROMPTS, f"Step {step.id} needs '{key}' but no prompt defined"
