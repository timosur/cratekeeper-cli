# CRATE-17: Review Tracks Before Adding to Master Library

## Description

The master library (`~/Music/Library/Genre/…`) is the DJ's long-term, curated collection. Today, `crate build-library` copies **every** track that has a matched local file and a genre bucket straight into the library, which pollutes it with one-off client wish-list tracks the DJ does not want to keep permanently.

This feature adds an **opt-in approval gate**: a new interactive `crate review-library` command where the DJ approves or rejects each candidate track per-track, and `crate build-library` is changed to copy **only approved tracks**. Un-reviewed tracks are never added to the master library.

In addition, `crate build-library` enforces a **tag-completeness admission rule**: a track must carry all required structured tags (`energy`, `function`, `crowd`, `mood`) to enter the master library. This guarantees the library only ever contains fully-tagged, filterable tracks (which downstream event folders inherit — see CRATE-18).

## Scope

- **New command:** `crate review-library` — interactive per-track approve/reject for master-library candidates.
- **Modified command:** `crate build-library` (CRATE-8) — copies only tracks that are **(a) approved** and **(b) fully tagged** (`energy`, `function`, `crowd`, `mood`); warns and exits when none qualify.
- **New data field** on `Track` to persist the approval decision in the event-plan JSON.
- **Out of scope:** event folders (`crate build-event` is handled by CRATE-18), per-bucket/confidence bulk decisions, embedding tags into files (that stays `crate tag`), and audio preview/playback during review.

## User Stories

- As a DJ, I want to approve or reject each matched track before it enters my master library, so my permanent collection stays curated and free of one-off wish-list tracks.
- As a DJ, I want un-reviewed tracks to be excluded by default, so nothing sneaks into my library without my explicit approval.
- As a DJ, I want to quit the review partway and resume later without re-deciding tracks I already judged, so I can review large playlists in multiple sittings.
- As a DJ, I want `build-library` to copy only my approved tracks, so the review actually controls what lands on disk.
- As a DJ, I want to be warned if I run `build-library` with nothing approved, so I don't silently produce an empty library build.

## CLI Contract

### New command: `crate review-library`

- **Command:** `crate review-library` — sits between `match` and `build-library` in the master-library path.
- **Arguments / options:**
  - `input_file` (Path, required) — path to the classified JSON plan.
- **Input:** the classified event-plan JSON. Only **build-library candidates** are presented: tracks that have both a `local_path` (matched local file) **and** a `bucket`.
- **Interactive behaviour:** presents candidates one at a time, showing at least track name, artists, bucket, year, BPM/key if present. For each, the DJ chooses:
  - `a` — **approve** (mark for inclusion)
  - `r` — **reject** (mark for exclusion)
  - `s` — **skip** (leave undecided, decide later)
  - `q` — **quit** and save progress
- **Resumability:** on re-run, tracks already approved or rejected are **skipped**; only undecided candidates are shown. `s` leaves a track undecided so it reappears next run.
- **Output / side effects:** writes the approval decision onto each reviewed track in the JSON and saves the plan back to `input_file`. Prints a running counter and a final summary (approved / rejected / remaining undecided).
- **Exit behaviour:** exit 0 on normal completion or quit. Non-zero only on unrecoverable error (missing/malformed input file).
- **Console UX:** Rich-formatted per-track prompt and a closing summary table.

### Modified command: `crate build-library`

- **Selection change:** copies only tracks that are **approved** AND **fully tagged** (all of `energy`, `function`, `crowd`, `mood_tags` non-empty), in addition to the existing `local_path` + `bucket` requirements. Rejected, undecided, and incompletely-tagged tracks are excluded.
- **Empty-approval safety:** if there are candidates but **zero qualify** (none approved, or approved-but-untagged), print a clear warning telling the DJ what to fix (run `crate review-library` and/or finish tagging) and exit **without copying** (non-zero exit).
- **No `--all` override** in this iteration — approval is the only path into the master library.
- **Summary:** the results table additionally reflects how many candidates were excluded because they were rejected, not yet reviewed, or missing required tags.

## Data Model

- New field on `Track` to persist the per-track decision, JSON-serializable and backwards-compatible with existing `data/*.json` plans:
  - Conceptually three states: **approved**, **rejected**, **undecided** (default for any track that predates this feature or hasn't been reviewed).
- The exact field name/representation is for the Solution Architect to finalize; the requirement is only that the three states persist in the plan JSON and default to **undecided**.

## Acceptance Criteria

- [ ] AC-1: `crate review-library data/<plan>.classified.json` presents only tracks that have both a `local_path` and a `bucket`; tracks missing either are never shown.
- [ ] AC-2: Choosing `a` / `r` / `s` records approve / reject / undecided respectively on the track, and the choice is persisted to the JSON.
- [ ] AC-3: Choosing `q` saves all decisions made so far and exits 0 without showing remaining tracks.
- [ ] AC-4: Re-running the command shows only tracks that are still undecided (previously approved or rejected tracks are skipped); skipped (`s`) tracks reappear.
- [ ] AC-5: `crate build-library` copies a track **only** if it is approved AND fully tagged (`energy`, `function`, `crowd`, `mood_tags` all non-empty) and still has `local_path` + `bucket`; rejected, undecided, and incompletely-tagged tracks are not copied.
- [ ] AC-6: When candidates exist but none qualify (none approved, or approved-but-untagged), `crate build-library` prints a warning explaining what to fix and exits non-zero without copying any files.
- [ ] AC-7: The `build-library` results summary reports counts for copied, already-existed, missing, rejected, undecided/un-reviewed, and excluded-for-missing-tags.
- [ ] AC-8: Loading an older `data/*.json` plan that has no approval field treats every track as **undecided** (i.e. nothing is copied until reviewed) without error.
- [ ] AC-9: The review command prints a final summary of approved / rejected / remaining-undecided counts.

## Edge Cases

- EC-1: **No candidates at all** (no track has both `local_path` and `bucket`) — `review-library` prints an informative message ("nothing to review; run match/classify first") and exits 0 without prompting.
- EC-2: **All candidates already decided** — `review-library` prints "all candidates already reviewed" and exits 0.
- EC-3: **Malformed or missing input file** — clear error message, non-zero exit, no partial writes.
- EC-4: **Invalid keypress** at the prompt — re-prompt for the same track rather than advancing or crashing.
- EC-5: **Non-interactive / piped stdin** (no TTY) — detect and exit with a clear message instead of hanging or consuming EOF as input.
- EC-6: **Track approved, then its local file disappears** before `build-library` runs — handled by the existing missing-file path (counted as missing, not copied).
- EC-7: **Re-running `build-library` after more approvals** — newly approved tracks are copied; already-copied files are skipped (existing dedup behaviour), so the command stays idempotent.
- EC-8: **Plan saved mid-review** — quitting (`q`) or finishing must leave the JSON in a valid, re-loadable state with all decisions so far persisted.
- EC-9: **Approved but not fully tagged** — a track the DJ approved that lacks one or more required tags is excluded by `build-library` and reported as missing-tags, not silently copied.

## Dependencies

- Requires: CRATE-5 (`crate match`) — produces the `local_path` values that make a track a candidate.
- Requires: CRATE-3 (`crate classify`) — produces the `bucket` values that make a track a candidate.
- Requires: CRATE-15 (`apply-tags`) — populates the structured tags the admission rule checks.
- Modifies: CRATE-8 (`crate build-library`) — changes its selection logic to honour approvals and tag-completeness.
- Related: CRATE-18 — applies the same tag-completeness rule to event folders.

---

<!-- Appended by Solution Architect agent -->

## Tech Design

### A) Impact Map

```
Command:    new `crate review-library <input_file>` (interactive approve/reject)
            revised `crate build-library` (selection + empty-safety + richer summary)
Modules:    new module  cratekeeper/review_library.py   (pure candidate-selection helpers)
            extend       cratekeeper/library_builder.py  (admission rule + richer result)
Data model: 1 new field on Track — `library_approval` (three-state string), JSON-compatible
External:   local filesystem only (read plan JSON, copy audio files). No new APIs.
Deps:       none (reuses typer, rich, existing models). No Docker / PostgreSQL.
```

This is a single-stage change in the **master-library path** (`match → review-library → build-library`). It does not touch fetch/enrich/classify/scan/match or the event-folder path (CRATE-18).

### B) Command & Module Structure

```
crate review-library <input_file>   (cli.py — owns prompt loop & Rich I/O)
├── EventPlan.load(input_file)
├── review_library.candidate_tracks(plan.tracks)      # local_path AND bucket
│   └── EC-1: empty → "nothing to review" → exit 0
├── refuse if stdin is not a TTY                       # EC-5
├── review_library.undecided_candidates(plan.tracks)  # still "undecided" only
│   └── EC-2: empty → "all candidates already reviewed" → exit 0
├── for each undecided candidate:                      # AC-2/3/4, EC-4
│   prompt a/r/s/q  →  set track.library_approval
│   (q → break; invalid key → re-prompt same track)
├── plan.save(input_file)                              # after q and on completion (EC-8)
└── Rich summary: approved / rejected / remaining-undecided   # AC-9


crate build-library <input_file> [--target]   (cli.py)
├── EventPlan.load(input_file)
├── library_builder.is_fully_tagged(track)            # energy+function+crowd+mood_tags
├── library_builder.partition_candidates(plan.tracks) # counts qualifying vs excluded
│   └── AC-6: candidates exist but qualifying == 0 → warning → exit non-zero, no copy
├── library_builder.build_library(...)                # copies ONLY qualifying tracks
└── Rich summary table with the full count breakdown  # AC-7
```

### C) Data Model Changes

**One new field on `Track`** in [models.py](../../cratekeeper-cli/cratekeeper/models.py):

- `library_approval: str = "undecided"` — the per-track master-library decision.
  - Allowed values: `"undecided"` (default), `"approved"`, `"rejected"`.
  - **Backwards compatibility:** because the dataclass field has a default, loading any existing `data/*.json` plan that lacks the field constructs every track as `"undecided"` — so nothing is copied until reviewed (AC-8). No migration needed; the field is added to `asdict` output on the next save automatically.

No new fields are required for the tag-completeness rule — it reads the existing `energy`, `function`, `crowd`, and `mood_tags` fields.

### D) CLI Surface

**New — `crate review-library`**
- Argument: `input_file` (Path, required) — the classified plan JSON.
- No options in this iteration.
- Input: the classified `EventPlan` JSON. Candidates = tracks with both `local_path` and `bucket`.
- Interactive keys per track: `a` approve · `r` reject · `s` skip (stay undecided) · `q` quit & save.
- Side effects: writes `library_approval` onto reviewed tracks and saves the plan back to `input_file`.
- Exit: `0` on completion or quit; non-zero only on missing/malformed input (EC-3) or no TTY (EC-5).

**Revised — `crate build-library`** (unchanged signature: `input_file`, `--target/-t`)
- Now copies a track only when it is `library_approval == "approved"` **and** fully tagged **and** still has `local_path` + `bucket`.
- No `--all` override (approval is the only path in).
- Summary table reports: **copied, already existed, missing (no local file), rejected, undecided/un-reviewed, excluded (missing tags)**.
- Exits non-zero without copying when candidates exist but none qualify (AC-6).

### E) Tech Decisions (why)

- **Three-state string over nullable boolean** — `"undecided"/"approved"/"rejected"` is self-describing in the JSON the DJ may inspect by hand, and gives a clean default that makes old plans safe-by-default. The chosen field name `library_approval` is explicit about scope (it governs the *library*, not the event folder).
- **New `review_library.py` for pure selection helpers, prompt loop stays in `cli.py`** — keeps the module free of console I/O (testable, consistent with the thin-command/module layering) while honouring the project's "heavy/interaction logic lives in modules, but Rich + stdin stay in commands" pattern. The interactive loop is intrinsically a command concern.
- **Admission rule lives in `library_builder.py`** — `is_fully_tagged()` and the partition/qualify logic sit next to the copy logic they gate, so `build_library` cannot be called in a way that bypasses them.
- **`build_library` returns a richer result** — the current `(copied, skipped, missing)` tuple can't express the new exclusion reasons (AC-7), so it returns a small result structure carrying all six counts plus the missing-file list. This is an internal contract; no other command depends on the old tuple.
- **TTY guard before prompting (EC-5)** — checking `sys.stdin.isatty()` avoids hangs / EOF-as-input under pipes or CI, with a clear message instead of silent failure.
- **Incremental-safe saves (EC-8)** — the plan is saved on `q` and on normal completion, leaving a valid, re-loadable JSON with every decision persisted; re-runs only re-present undecided tracks (AC-4).
- **File-driven, idempotent** — reuses the existing dedup (`dest_path.exists()` → skipped) so re-running after more approvals copies only the newly-qualified tracks (EC-7).

### F) Dependencies

None. Reuses `typer`, `rich`, and the existing `EventPlan`/`Track` models and `shutil`-based copy already declared in [pyproject.toml](../../cratekeeper-cli/pyproject.toml).

## Implementation Plan

_See [CRATE-17-plan.md](../plans/CRATE-17-plan.md)._
