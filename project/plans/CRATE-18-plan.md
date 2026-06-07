# Plan: CRATE-18 — Flat, Tag-Driven Event Folders

> Status: Complete
> Feature spec: [CRATE-18](../features/CRATE-18-flat-tag-driven-event-folders.md)
> Created: 2026-06-07

## Phase 1: Rewrite event_builder.py

- [x] Add `BuildEventResult` dataclass (copied, already_existed, missing, untagged, collisions counts + `missing_tracks` and `untagged_tracks` lists)
- [x] Add `_is_fully_tagged(track)` — checks `energy`, `function`, `crowd`, `mood_tags` all non-empty in the plan
- [x] Add `_has_embedded_comment(path)` — reads the audio file via mutagen and checks for a non-empty comment containing `energy:` (MP3 `COMM::eng`, FLAC `comment`, M4A `©cmt`)
- [x] Rewrite `build_event_folder`: flat layout (files directly in `output_dir`), dual gate, first-writer-wins collision detection, `_missing.txt` + `_untagged.txt` report writing, returns `BuildEventResult`
- [x] **Checkpoint**: Manual verification — import the module, call `build_event_folder` on a small hand-crafted track list (with and without tags), confirm flat output, no Genre/ subfolders, correct counts

## Phase 2: Update build-event command (cli.py)

- [x] Update `build_event_cmd` to consume `BuildEventResult` (replace the old tuple unpacking)
- [x] Add AC-7 empty-eligible guard: candidates exist but zero qualify → warn clearly + exit non-zero, no output folder created
- [x] Update the Rich summary table to report: copied / already existed / missing local file / skipped (untagged or collision)
- [x] Add a warning line pointing at `_untagged.txt` when the untagged count is non-zero
- [x] **Checkpoint**: Manual verification — run `crate build-event data/<plan>.classified.json -o /tmp/event-test`; confirm: (a) flat output, (b) summary counts correct, (c) `_untagged.txt` written for untagged/collision tracks, (d) re-run is idempotent (already-existed count rises, no duplicate errors)

> Note: This command copies files into whatever `--output` directory the DJ specifies. Use `/tmp/event-test` or a scratch location for testing — never an active event folder.
