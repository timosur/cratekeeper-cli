## 1. Core data structures

- [x] 1.1 Create `cratekeeper/wizard.py` with `Step` dataclass (id, label, required, needs_docker, needs_input, run callable, is_complete callable)
- [x] 1.2 Define `EVENT_PIPELINE` step list: fetch → classify → enrich (opt) → review (opt) → match → analyze-mood → apply-tags → tag → create-playlists (opt) → sync-to-tidal (opt) → build-event
- [x] 1.3 Define `LIBRARY_PIPELINE` step list: scan → import-library → classify → enrich (opt) → match → analyze-mood → apply-tags → tag → review-library → build-library → export-rekordbox (opt)

## 2. Progress detection

- [x] 2.1 Implement `is_complete` functions for each step using plan field inspection (per design D3: tracks have bucket, local_path, bpm/audio_mood, energy/function, tags_written, library_approval)
- [x] 2.2 Implement `ProgressDetector` that walks the pipeline steps, calls each `is_complete`, and returns the index of the first incomplete step

## 3. Step execution

- [x] 3.1 Implement step runner functions that wrap worker module calls (spotify_client, classifier, musicbrainz_client, matcher, mood_analyzer, tag_writer, library_builder, event_builder, local_scanner, review_library)
- [x] 3.2 Implement just-in-time input collection using `rich.prompt.Prompt.ask()` for each step's `needs_input` (playlist_url, music_directory, output_path, tags_file, event_name, event_date, library_target, etc.)
- [x] 3.3 Implement apply-tags step logic inline (replicate ~30 lines of validation/mutation from cli.py using tag_writer.VALID_* constants)
- [x] 3.4 Implement Rich output for each step: step header panel, progress during execution, result summary after completion

## 4. Wizard flow

- [x] 4.1 Implement pipeline selection prompt (event vs library-import) using `rich.prompt.Prompt.ask()`
- [x] 4.2 Implement resume logic: if user provides an existing plan file, run ProgressDetector and offer to resume from next incomplete step
- [x] 4.3 Implement step loop: for each step, show label → collect inputs → execute (or offer skip for optional) → show result → prompt "Continue?"
- [x] 4.4 Implement abort handling: on decline at "Continue?" prompt, save plan and exit cleanly
- [x] 4.5 Implement completion summary: after all steps finish, display table of steps and outcomes plus final output path

## 5. CLI registration

- [x] 5.1 Register `wizard` command in `cli.py` with `--profile` support (profile resolved via existing `ctx.obj` callback)
- [x] 5.2 Add optional `--plan` argument to `crate wizard` for providing an existing plan file (enables resume)

## 6. Tests

- [x] 6.1 Test pipeline definitions: verify EVENT_PIPELINE and LIBRARY_PIPELINE have correct step count, ordering, and required/optional flags
- [x] 6.2 Test progress detection: given plan JSONs with varying field completeness, verify ProgressDetector returns correct resume index
- [x] 6.3 Test step `is_complete` functions individually with mock plan data
- [x] 6.4 Test wizard flow with monkeypatched prompts and worker functions: verify step execution order, skip behavior, and abort handling

## 7. Validation

- [x] 7.1 Run `make check` (lint + test) and fix any issues
- [ ] 7.2 Manual smoke test: run `./crate wizard` through event pipeline with a real playlist
