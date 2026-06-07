# Plan: CRATE-17 — Review Tracks Before Adding to Master Library

> Status: Complete
> Feature spec: [CRATE-17](../features/CRATE-17-review-library-before-add.md)
> Created: 2026-06-07

## Phase 1: Data Model & Module Skeleton

- [x] Add `library_approval: str = "undecided"` field to `Track` in `cratekeeper/models.py`
- [x] Create module `cratekeeper/review_library.py` with signatures for `candidate_tracks(tracks)` (local_path AND bucket) and `undecided_candidates(tracks)` (candidates still `"undecided"`)
- [x] Add `is_fully_tagged(track)` helper to `cratekeeper/library_builder.py` (energy + function + crowd + mood_tags all non-empty)
- [x] **Checkpoint**: Manual verification — load an existing `data/*.json` plan and re-save; confirm it still loads, every track defaults to `library_approval == "undecided"`, and imports succeed

## Phase 2: Review Command (interactive)

- [x] Implement `crate review-library <input_file>` in `cli.py`: load plan, select candidates, run the per-track `a/r/s/q` prompt loop, persist `library_approval`
- [x] Handle edge cases: no candidates (EC-1), all decided (EC-2), missing/malformed file (EC-3), invalid keypress re-prompts (EC-4), non-TTY stdin guard (EC-5)
- [x] Save plan on `q` and on completion (EC-8); print running counter and final approved/rejected/undecided summary (AC-9)
- [x] **Checkpoint**: Manual verification — run `crate review-library data/<plan>.classified.json`, approve/reject/skip/quit, re-run to confirm only undecided tracks reappear (AC-4), inspect the JSON for persisted decisions

## Phase 3: Revise build-library (admission rule)

- [x] Extend `library_builder.build_library` to copy only `approved` + fully-tagged + `local_path` + `bucket` tracks, returning the six-count breakdown (copied, already-existed, missing, rejected, undecided, missing-tags) + missing list
- [x] Add empty-approval safety in `cli.py`: candidates exist but zero qualify → warning explaining what to fix → exit non-zero, no copy (AC-6)
- [x] Update the `build-library` Rich summary table to report all six counts (AC-7); confirm idempotent re-run after more approvals (EC-7)
- [x] **Checkpoint**: Manual verification — run `crate build-library` on a plan with mixed approved/rejected/undecided/untagged tracks; confirm only approved+fully-tagged files land in `--target`, counts are correct, and an all-unapproved plan exits non-zero without copying

> Destructive note: `build-library` copies files into `~/Music/Library`. Verify counts via the summary table before/after; existing `dest_path.exists()` dedup keeps re-runs safe. No mutation of remote playlists or tag-writing in this feature.
