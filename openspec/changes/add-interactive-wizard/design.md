## Context

Cratekeeper CLI has ~18 commands forming two pipelines (event and library-import) with strict dependency ordering. Users must memorize command sequences, track progress manually, and know which arguments each step needs. The proposal calls for a `crate wizard` command that guides users through the full pipeline interactively.

The existing codebase has clean extraction boundaries: core pipeline functions live in dedicated worker modules (`classifier`, `matcher`, `mood_analyzer`, `tag_writer`, `library_builder`, `event_builder`, etc.) and are directly callable. Commands in `cli.py` are mostly thin wrappers around these workers. The profile system (`config.resolve_profile()`) provides all per-profile settings as a dataclass.

In-force ADR: ADR-0001 (Plan base class with type discriminator) — the wizard uses `Plan.load()` polymorphism to handle both `EventPlan` and `LibraryImportPlan` transparently.

## Goals / Non-Goals

**Goals:**

- Single `crate wizard` command that walks the user through the full pipeline
- Supports both event and library-import pipelines
- Executes steps internally by calling existing worker module functions
- Collects inputs just-in-time (playlist URL, music directory, output paths)
- Labels steps required/optional; optional steps can be skipped
- Detects progress from plan JSON and resumes from the next incomplete step
- Uses only existing dependencies (Rich, Typer)

**Non-Goals:**

- Full TUI framework (no textual/curses dependency)
- Modifying existing CLI commands or their behavior
- Extracting inline `cli.py` logic into shared modules (out of scope; wizard calls workers directly)
- LLM integration (apply-tags requires external tags JSON — wizard prompts for the file path)
- Batch/non-interactive mode for the wizard itself

## Architecture

### Component Diagram (C4 Level 3 — inside the `crate` CLI container)

```
┌─────────────────────────────────────────────────────────────┐
│  crate CLI  (Python, Typer)                                 │
│                                                             │
│  ┌───────────────┐     ┌──────────────────────────────────┐ │
│  │   cli.py      │     │  wizard.py                       │ │
│  │  (existing    │     │                                  │ │
│  │   commands)   │     │  ┌────────────┐  ┌────────────┐  │ │
│  │               │     │  │ PIPELINES  │  │ StepRunner │  │ │
│  │  fetch        │     │  │ (step      │  │ (execute,  │  │ │
│  │  classify     │     │  │  registry) │  │  prompt,   │  │ │
│  │  enrich       │     │  │            │  │  display)  │  │ │
│  │  match        │     │  └─────┬──────┘  └─────┬──────┘  │ │
│  │  tag  ...     │     │        │               │         │ │
│  └───────┬───────┘     │  ┌─────┴───────────────┴──────┐  │ │
│          │             │  │    ProgressDetector         │  │ │
│          │             │  │    (plan JSON inspection)   │  │ │
│          │             │  └────────────┬───────────────┘  │ │
│          │             └───────────────┼──────────────────┘ │
│          │                             │                    │
│  ┌───────┴─────────────────────────────┴──────────────────┐ │
│  │              Worker Modules (shared)                    │ │
│  │  spotify_client · classifier · musicbrainz_client      │ │
│  │  matcher · mood_analyzer · tag_writer · local_scanner  │ │
│  │  library_builder · event_builder · review_library      │ │
│  └────────────────────────────────────────────────────────┘ │
│                             │                               │
│  ┌──────────────────────────┴─────────────────────────────┐ │
│  │              models.py  ·  config.py                   │ │
│  │  Plan.load() / plan.save()  ·  resolve_profile()      │ │
│  └────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────┘
         │                    │                    │
    ┌────┴───┐          ┌────┴────┐         ┌─────┴─────┐
    │Spotify │          │PostgreSQL│         │ Filesystem│
    │  API   │          │ (scan)  │         │ (audio)   │
    └────────┘          └─────────┘         └───────────┘
```

**Key relationships:**
- `wizard.py` calls the same worker modules that `cli.py` commands use — no duplication
- `PIPELINES` is a data structure defining step sequences for event and library-import flows
- `StepRunner` handles execution, Rich output, and user prompts for each step
- `ProgressDetector` reads the plan JSON to determine which steps are already complete
- `cli.py` and `wizard.py` are siblings — both import from workers and models, neither depends on the other

## Decisions

### D1: Wizard as a single module (`wizard.py`) registered in `cli.py`

**Choice:** One new file `cratekeeper/wizard.py` containing all wizard logic, registered as `app.command("wizard")` in `cli.py`.

**Why over alternatives:**
- *Subcommand group (`crate wizard start`, `crate wizard resume`)*: Unnecessary complexity — the wizard auto-detects resume from the plan file.
- *Inline in cli.py*: `cli.py` is already ~1000 lines. Separate module keeps it focused.

### D2: Pipeline definitions as data, not code

**Choice:** Define pipelines as lists of step descriptors:

```python
@dataclass
class Step:
    id: str                    # e.g. "fetch", "classify"
    label: str                 # human-readable name
    required: bool             # can this step be skipped?
    needs_docker: bool         # does this step need Docker?
    needs_input: list[str]     # inputs to collect (e.g. ["playlist_url"])
    run: Callable              # function to execute
    is_complete: Callable      # function to check plan progress
```

**Why:** Adding steps or reordering the pipeline is a data change, not a logic change. Each step's `run` callable wraps the worker module function. Each step's `is_complete` callable inspects the plan to detect prior progress.

### D3: Progress detection via plan field inspection

**Choice:** Each step has an `is_complete` function that checks specific plan fields:

| Step | Complete when |
|------|--------------|
| fetch | `plan.tracks` is non-empty |
| classify | all tracks have `bucket` set |
| enrich | checked via `artist_genres` presence on tracks missing them |
| match | all tracks have `local_path` or are in missing list |
| analyze-mood | tracks with `local_path` have `bpm` and `audio_mood` |
| apply-tags | tracks have `energy` and `function` tags |
| tag | tracks have `tags_written` flag |
| review-library | all candidate tracks have `library_approval` set |
| build-library | plan has been saved after library build |
| build-event | plan has been saved after event build |

**Why over alternatives:**
- *Separate progress file*: Extra state to track, can drift from plan JSON.
- *Timestamp-based*: Doesn't capture partial completion within a step.

### D4: Wizard calls worker modules directly, not CLI command functions

**Choice:** The wizard imports and calls worker functions (e.g. `classifier.classify_tracks()`, `matcher.match_tracks()`) rather than invoking CLI command functions.

**Why:**
- CLI commands mix business logic with Typer argument parsing and Rich output
- Worker functions have clean signatures and return values
- Wizard provides its own Rich output (progress panels, step headers)
- Only `apply-tags` logic is inline in cli.py — the wizard replicates its ~30 lines of validation/mutation rather than extracting it (keeps this change minimal)

### D5: Profile resolved once at wizard start

**Choice:** The wizard calls `resolve_profile(profile_name)` once at the beginning and threads the `Profile` dataclass through all steps.

**Why:** Same pattern as `cli.py`'s `@app.callback()`. Profile doesn't change mid-pipeline.

### D6: User interaction via Rich prompts

**Choice:** Use `rich.prompt.Prompt.ask()` and `rich.prompt.Confirm.ask()` for all wizard interactions. Step output uses `rich.console.Console` with panels and tables.

**Why:** Already in the dependency tree. Consistent with existing interactive prompts in `fetch` and `review-library`.

## Risks / Trade-offs

- **[Risk] Worker function signatures may change** → Wizard tests will catch breakage. Keep wizard step wrappers thin so updates are trivial.
- **[Risk] apply-tags logic duplication** → ~30 lines of validation logic copied from cli.py. Acceptable for now; can be extracted to a shared function later if it drifts.
- **[Risk] Docker step fails confusingly** → The wizard does not attempt to detect Docker availability; it calls `mood_analyzer.analyze_tracks()` which already reports a clear error if essentia is not installed. Consistent with direct CLI behavior.
- **[Trade-off] No non-interactive mode** → The wizard is purely interactive. Users wanting automation use individual commands or scripts. This is intentional — the wizard's value is guidance, not automation.

## Migration Plan

No migration needed. This is purely additive:
- New file: `cratekeeper/wizard.py`
- Small addition to `cli.py`: import and register the wizard command
- No changes to existing commands, models, or worker modules
- No database changes
- Rollback: delete `wizard.py` and remove the registration line

## Open Questions

None — all key decisions resolved during proposal grilling.
