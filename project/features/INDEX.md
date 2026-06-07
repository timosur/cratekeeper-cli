# Feature Index

> Project: Cratekeeper — DJ library management CLI (`crate`)
> See [PRD](../PRD.md) for vision, roadmap, and metrics.

## Conventions

- Each feature = ONE testable, runnable unit — usually one `crate` command or pipeline stage.
- Feature specs live at `project/features/CRATE-X-feature-name.md`.
- Implementation plans live at `project/plans/CRATE-X-plan.md`.
- Statuses: **Planned** → **In Progress** → **Done**.

## Pipeline Order

`fetch → enrich → classify → scan → match → analyze-mood → [LLM tagging] → apply-tags → tag → review-library → build-library → build-event` (P0)
plus `review`, `create-playlists`, `sync-to-tidal`, `build-masters` (P1/P2).

> LLM tagging is **not** a `crate` command. It runs in the agent layer (sub-agent), and the result is applied with `crate apply-tags` (CRATE-15). See the [prepare-event skill](../../.github/skills/prepare-event/SKILL.md), Step 8.
>
> Since CRATE-17/CRATE-18 require tracks to be **fully tagged** before they enter the library or an event folder, `apply-tags` and `tag` now run **before** `build-library` / `build-event` (previously `tag` ran last).

## Features

| ID | Feature | Command | Priority | Status | Spec |
|----|---------|---------|----------|--------|------|
| CRATE-1 | Fetch Spotify playlist → JSON plan | `crate fetch` | P0 | Done (shipped) | _existing code_ |
| CRATE-2 | Enrich genres & release years (MusicBrainz) | `crate enrich` | P0 | Done (shipped) | _existing code_ |
| CRATE-3 | Classify tracks into genre buckets | `crate classify` | P0 | Done (shipped) | _existing code_ |
| CRATE-4 | Scan local library into a file index | `crate scan` | P0 | Done (shipped) | _existing code_ |
| CRATE-5 | Match tracks to local audio files | `crate match` | P0 | Done (shipped) | _existing code_ |
| CRATE-6 | Audio analysis (BPM/key/mood via essentia) | `crate analyze-mood` | P0 | Done (shipped) | _existing code_ |
| CRATE-7 | LLM structured tagging | `crate classify-tags` | P0 | Won't build (superseded by CRATE-15) | _n/a_ |
| CRATE-8 | Build master library folder structure | `crate build-library` | P0 | Done (shipped) — revised by CRATE-17 | _existing code_ |
| CRATE-9 | Build event-specific folder structure | `crate build-event` | P0 | Done (shipped) — revised by CRATE-18 | _existing code_ |
| CRATE-10 | Write metadata tags into audio files | `crate tag` | P0 | Done (shipped) | _existing code_ |
| CRATE-11 | Review low-confidence classifications | `crate review` | P1 | Done (shipped) | _existing code_ |
| CRATE-12 | Create Spotify sub-playlists per genre bucket | `crate create-playlists` | P1 | Done (shipped) | _existing code_ |
| CRATE-13 | Sync classified playlists to Tidal | `crate sync-to-tidal` | P2 | Done (shipped) | _existing code_ |
| CRATE-14 | Cross-event master playlists | `crate build-masters` | P2 | Done (shipped) | _existing code_ |
| CRATE-15 | Apply pre-classified tags from a JSON file | `crate apply-tags` | P1 | Done (shipped) | _existing code_ |
| CRATE-16 | Write basic metadata into untagged audio files | `crate tag-untagged` | P2 | Done (shipped) | _existing code_ |
| CRATE-17 | Review tracks before adding to master library | `crate review-library` (+ revises `build-library`) | P1 | Done (shipped) | [CRATE-17](CRATE-17-review-library-before-add.md) |
| CRATE-18 | Flat, tag-driven event folders | `crate build-event` (revised) | P1 | Planned | [CRATE-18](CRATE-18-flat-tag-driven-event-folders.md) |

> **CRATE-7 will not be built.** LLM tagging is intentionally an **agent-layer** concern, not a CLI command. The orchestrating agent builds a prompt from the classified + audio-analyzed plan, calls a sub-agent to produce a tags JSON, and `crate apply-tags` (CRATE-15) validates and writes the tags into the plan. A native `crate classify-tags` would only relocate the LLM call into the CLI — adding an `anthropic` SDK dependency and requiring `ANTHROPIC_API_KEY` in the CLI — without adding any capability. Revisit only if headless, agent-free scripting (cron/CI) of LLM tagging is ever required.

### Extra shipped commands (documented for completeness)

CRATE-15 and CRATE-16 were not in the original roadmap but exist in `cli.py`; recorded here so the index matches the actual CLI surface.

## Dependency Graph (P0)

```
CRATE-1 fetch
  └─> CRATE-2 enrich
        └─> CRATE-3 classify ──────────────┐
CRATE-4 scan                               │
  └─> CRATE-5 match (needs CRATE-3 + scan) │
        ├─> CRATE-6 analyze-mood           │
        │     └─> [LLM sub-agent] ─> CRATE-15 apply-tags ─> CRATE-10 tag
        │            (energy/function/crowd/mood required downstream)
        ├─> CRATE-17 review-library ─> CRATE-8 build-library (approved + fully tagged)
        ├─> CRATE-18 build-event (flat, fully tagged) <──┘
        └─> CRATE-10 tag embeds tags so djay can filter the event folder
```
