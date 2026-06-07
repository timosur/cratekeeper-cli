# CRATE-18: Flat, Tag-Driven Event Folders

## Description

Event folders are built with `crate build-event` and loaded into djay PRO for the actual gig. Today the command copies files into a `Genre/` subfolder structure (`output_dir/Deep House/Artist - Title.ext`). In practice the DJ does **not** mix by genre during a set — they mix by **function, energy, crowd, and mood** (e.g. "a high-energy singalong for a mixed-age crowd"), which cut across genres. Genre folders force navigating many buckets to find the right track.

This feature changes `crate build-event` to produce a **flat folder** (all files directly in the output directory, no genre subfolders) and to rely on the **structured tags already embedded in the files** (`era`, `energy`, `function`, `crowd`, `mood`), which the DJ filters with djay PRO quick filters at the gig. To guarantee those filters work, `build-event` only includes tracks that carry the **required structured tags**, and skips/reports anything not fully tagged.

## Scope

- **Modified command:** `crate build-event` (CRATE-9, shipped).
  - Remove the `Genre/` subfolder layout entirely — output is **flat**.
  - **Tag-completeness gate:** only copy tracks that have all required structured tags (`energy`, `function`, `crowd`, `mood`). Skip and report the rest.
- **Out of scope:**
  - The master library layout (`crate build-library` keeps its `Genre/` structure — see CRATE-8 / CRATE-17).
  - Embedding/writing tags into files — that remains `crate tag` (CRATE-10). This command only **verifies** tags are present.
  - Changing the tag comment format or djay-side configuration.

## User Stories

- As a DJ, I want my event folder to be a single flat folder of tagged files, so I can drop it into djay PRO and slice it with quick filters instead of digging through genre folders.
- As a DJ, I want to filter the event set by energy / function / crowd / mood at the gig, so I can pick the right track for the moment regardless of its genre.
- As a DJ, I want `build-event` to refuse tracks that aren't fully tagged, so my event folder never contains tracks I can't filter on.
- As a DJ, I want a clear report of which tracks were skipped for missing tags, so I know what still needs tagging.
- As a DJ, I want re-running `build-event` to be safe, so I can rebuild after tagging more tracks without creating a mess.

## CLI Contract

- **Command:** `crate build-event` — final local-output stage of the event path.
- **Arguments / options:**
  - `input_file` (Path, required) — path to the classified JSON plan.
  - `--output` / `-o` (Path, required) — event output directory (e.g. `~/Music/Events/Wedding/`).
- **Input:** the classified event-plan JSON. A track is **eligible** only if it has a `local_path` (matched, file exists) **and** all required structured tags present.
- **Required structured tags (all must be non-empty):** `energy`, `function`, `crowd`, `mood` (`mood_tags`). `era` is informational, not required.
- **Output / side effects:**
  - Copies each eligible track's file directly into the output directory as `Artist - Title.ext` — **no genre subfolders**.
  - Writes a report of tracks **skipped for missing tags** (e.g. `_untagged.txt`) and continues writing the existing missing-local-file report (`_missing.txt`).
  - Prints a Rich summary table (copied / already existed / missing local file / skipped-untagged).
- **Exit behaviour:** exit 0 on a normal build (even if some tracks were skipped). Non-zero only on unrecoverable error (missing/malformed input, output path not creatable). If **zero** tracks are eligible, warn clearly and exit non-zero without creating an empty/again-misleading folder.
- **Console UX:** progress lines and a final summary table; a warning line pointing at the skipped-tags report when any track is skipped for missing tags.

## Data Model

- No new fields. Reuses existing `Track` tag fields: `energy`, `function`, `crowd`, `mood_tags`, `era`.

## Acceptance Criteria

- [ ] AC-1: `crate build-event -o <dir> <plan>` writes eligible files **directly** into `<dir>` with no genre subfolders.
- [ ] AC-2: A track is copied only if it has a usable `local_path` **and** all of `energy`, `function`, `crowd`, `mood_tags` are non-empty.
- [ ] AC-3: Tracks missing one or more required tags are **not** copied and are listed in a skipped-tags report file in the output directory.
- [ ] AC-4: Tracks with no `local_path` or a missing file continue to be reported in `_missing.txt` and are not copied.
- [ ] AC-5: The summary table reports counts for copied, already-existed, missing-local-file, and skipped-for-missing-tags.
- [ ] AC-6: Re-running the command after more tracks are tagged copies the newly-eligible tracks and does not error on files already present (idempotent).
- [ ] AC-7: When no track is eligible, the command warns and exits non-zero without producing a misleading "success" summary.
- [ ] AC-8: The `Genre/` subfolder layout no longer appears anywhere in the event output.

## Edge Cases

- EC-1: **Filename collision in a flat folder** — two different tracks resolve to the same `Artist - Title.ext` (e.g. radio vs extended edit). The command must not silently overwrite one with the other; it should disambiguate (e.g. suffix) or skip-and-report. _(Exact strategy for the Solution Architect.)_
- EC-2: **Partially tagged track** (e.g. has `energy` and `mood` but no `function`/`crowd`) — treated as not fully tagged → skipped and reported.
- EC-3: **Tags present in the plan but not yet embedded in the file** — see Open Question; for djay filtering the files must carry the comment, so `crate tag` ordering matters.
- EC-4: **Missing or malformed input file** — clear error, non-zero exit, no partial output.
- EC-5: **Output directory not writable / cannot be created** — clear error, non-zero exit.
- EC-6: **All tracks fully tagged but none matched locally** — nothing to copy → warn, non-zero exit (same as EC in AC-7).
- EC-7: **Re-run into an existing event folder** — already-present files are handled gracefully (copied/overwritten consistently), staying idempotent.

## Open Questions

- **Tag embedding vs. verification order.** This command *verifies* the structured tags are present (in the plan) but does not embed them; embedding is `crate tag` (CRATE-10). For djay PRO quick filters to work, the **copied event files must carry the embedded comment**. This implies `crate tag` should run on the files before `build-event` copies them (or the pipeline order must change). The Solution Architect should resolve the exact ordering / whether `build-event` should additionally confirm the embedded comment exists, not just the plan fields.
- **Pipeline order shift.** Requiring full tags at `build-event` means LLM tagging (CRATE-15 `apply-tags`) and `crate tag` must precede `build-event`, which changes the documented pipeline order (currently `… build-event → tag`).

## Dependencies

- Modifies: CRATE-9 (`crate build-event`) — layout and eligibility change.
- Requires: CRATE-15 (`apply-tags`) — populates the structured tag fields the gate checks.
- Related: CRATE-10 (`crate tag`) — embeds the tags into files so djay can filter them.
- Related: CRATE-17 — applies the same tag-completeness idea as a master-library admission rule.

---

<!-- Appended by Solution Architect agent -->

## Tech Design

### A) Impact Map

```
Command:   revised `crate build-event <input_file> --output <dir>` (cli.py)
Modules:   rewrite cratekeeper/event_builder.py:
           - flat folder layout (no Genre/ subdirectory)
           - _is_fully_tagged(track)     — plan JSON field gate
           - _has_embedded_comment(path) — mutagen file read gate
           - BuildEventResult dataclass  (5 counts + track lists)
           - collision detection: first write wins → _untagged.txt
Data model: no new fields — reuses energy, function, crowd, mood_tags, era
External:  local filesystem + mutagen (already a dependency)
Deps:      none new
```

This is a self-contained change to the **event-folder output stage**. It does not touch the master-library path (`build-library`) or any upstream pipeline command.

### B) Command & Module Structure

```
crate build-event <input_file> --output <dir>  (cli.py)
├── EventPlan.load(input_file)
├── build_event_folder(plan.tracks, output_dir)   # event_builder.py (rewritten)
│   ├── for each track (in order):
│   │   ├── no local_path or file missing on disk  → missing list
│   │   ├── not _is_fully_tagged(track)            → untagged list
│   │   ├── not _has_embedded_comment(path)        → untagged list
│   │   ├── Artist - Title.ext already claimed
│   │   │   by a different source file             → untagged list (collision)
│   │   ├── dest_path.exists()                     → already_existed count
│   │   └── shutil.copy2 → dest_path              → copied count
│   ├── write output_dir/_missing.txt  (if any missing)
│   ├── write output_dir/_untagged.txt (if any untagged/collision)
│   └── return BuildEventResult
├── AC-7: zero eligible → warn + exit non-zero
└── Rich summary table + warning line pointing at _untagged.txt
```

**Embedded-comment check** — `_has_embedded_comment(path)` reads the audio file with mutagen and looks for a non-empty comment field containing `energy:` (the marker written by `crate tag`):
- MP3: `COMM::eng` ID3 frame
- FLAC: vorbis `comment` tag
- M4A: `©cmt` (`\xa9cmt`) atom

This confirms `crate tag` ran on the file and that djay PRO quick filters will work. If the check fails (plan tags present but not yet embedded), the track joins the **untagged** list, directing the DJ to re-run `crate tag`.

### C) Data Model Changes

None. No new `Track` or `EventPlan` fields. Reuses existing `energy`, `function`, `crowd`, `mood_tags` (gate), `era` (informational), `local_path`, `artists`, `name`.

### D) CLI Surface

`crate build-event <input_file> --output/-o <dir>` — **signature unchanged**. Only the internal behaviour and output layout change:

- Output: files land directly in `<dir>` as `Artist - Title.ext` — no `Genre/` subdirectory.
- New report file: `<dir>/_untagged.txt` — tracks skipped for missing plan tags, unembedded file comment, or filename collision (first-writer-wins).
- Existing report: `<dir>/_missing.txt` — unchanged (no `local_path` or file not on disk).
- Summary table: **copied / already existed / missing local file / skipped (untagged or collision)**.
- Exit: 0 on a successful build (even with some skips). Non-zero when zero tracks are eligible (AC-7) or on unrecoverable I/O error.

**Resolved: Open Question — pipeline ordering.** `build-event` verifies both plan JSON fields *and* the embedded file comment. This means `crate apply-tags` → `crate tag` must precede `build-event`. The feature index pipeline order already reflects this.

### E) Tech Decisions (why)

- **Flat folder**: djay PRO quick-filter workflow needs a single folder the DJ can slice by energy/function/crowd/mood. Genre subfolders actively impede this — one track can match multiple tag dimensions that cut across genre.
- **Dual gate (plan + embedded)**: checking only the plan would allow copying files that haven't had `crate tag` run yet, making djay filters silently fail. The mutagen read adds a tiny per-file cost (~1 ms) but gives a hard guarantee.
- **Collision: first-writer-wins + `_untagged.txt`**: avoids silent data loss (overwriting into the same filename slot). The DJ can inspect the report and manually include the other version. Reusing `_untagged.txt` keeps the output directory uncluttered — both "not fully tagged" and "collision" mean "not eligible for this build."
- **`BuildEventResult` dataclass**: mirrors `BuildLibraryResult` from CRATE-17, making the summary table straightforward and keeping `build_event_folder` a pure function.
- **Idempotency (`dest_path.exists()` → skip)**: consistent with `build_library`. Re-running after tagging more tracks copies only newly-eligible files without disturbing those already present.
- **mutagen** is already declared in `pyproject.toml` (used by `tag_writer.py`). No new dependency.

### F) Dependencies

None new. Reuses `mutagen` (already installed), `shutil`, `typer`, `rich`, and the existing `EventPlan`/`Track` models.

## Implementation Plan

_See [CRATE-18-plan.md](../plans/CRATE-18-plan.md)._
