## Why

The CLI has ~18 commands with a strict dependency chain (fetch → classify → match → tag → build). New users must memorize the pipeline order, remember which arguments each step needs, and manually track progress across sessions. An interactive wizard that guides users step-by-step through the full pipeline removes this friction without adding token cost (it runs locally, no LLM needed).

## What Changes

- Add a `crate wizard` top-level command that guides users through the full pipeline interactively
- The wizard asks which pipeline to run (event or library-import), then walks through each step in order
- Each step executes internally (calls the same functions as the individual CLI commands), shows output, and prompts before advancing
- Optional steps (enrich, review, create-playlists, sync-to-tidal) can be skipped; required steps cannot
- The wizard detects progress from the plan JSON and offers to resume from the next incomplete step
- Inputs are collected just-in-time before each step (e.g. playlist URL before fetch, music directory before scan)
- Docker-dependent steps (analyze-mood) attempt execution and fail loudly if Docker is unavailable

## Capabilities

### New Capabilities

- `interactive-wizard`: The `crate wizard` command — pipeline selection, step-by-step guided execution, progress detection and resume, input collection, skip/continue prompts for optional steps

### Modified Capabilities

_(none — existing commands are unchanged; the wizard calls their internal functions)_

## Impact

- **New code**: `cratekeeper/wizard.py` module + registration in `cli.py`
- **Dependencies**: None new — uses existing Rich (prompts, progress, panels) and Typer
- **Existing commands**: Unchanged — wizard calls the same internal functions, individual commands remain available for direct use
- **CLI surface**: One new top-level command (`crate wizard`)
