# Cratekeeper — Product Requirements Document

> Status: Draft
> Last updated: 2026-06-07
> Owner: Requirements Engineer

## Vision

Cratekeeper is a single-binary Python command-line tool (`crate`) that turns a DJ's Spotify wish playlist into an organized, analyzed, and tagged local music crate — and keeps a master library curated the same way over time. It runs a file-driven pipeline that classifies tracks by genre, matches them to local audio files, analyzes their sound, tags them, and lays them out in event-ready folders.

## Target Users

**Primary: the solo DJ.** A working DJ who receives wish playlists from clients (weddings, parties, corporate events), owns a local/NAS music library, and wants to go from "here's the playlist" to "a sorted, tagged, event-ready crate" with minimal manual effort. They are comfortable on the command line and value reproducibility, accuracy, and control over their files and metadata.

**Needs**
- Convert a client wish playlist into a structured, DJ-ready crate quickly
- Trust automatic genre classification and local-file matching
- Enrich tracks with objective audio data (BPM, key, energy, mood) and DJ-oriented tags
- Keep a consistent master library that grows event over event

**Pain points (today)**
- Manually sorting wish-list tracks by genre is slow and inconsistent
- Finding which wished tracks already exist locally is tedious
- No consistent metadata/tagging scheme across the library
- Re-doing the same prep work for every event

## Core Features (Roadmap)

Priority: **P0 = MVP**, **P1 = next**, **P2 = later**. All features are expressed as `crate` commands / pipeline stages.

| ID | Feature | Command | Priority | Status |
|----|---------|---------|----------|--------|
| CRATE-1 | Fetch Spotify playlist → JSON plan | `crate fetch` | P0 | Done (shipped) |
| CRATE-2 | Enrich genres & release years (MusicBrainz) | `crate enrich` | P0 | Done (shipped) |
| CRATE-3 | Classify tracks into genre buckets | `crate classify` | P0 | Done (shipped) |
| CRATE-4 | Scan local library into a file index | `crate scan` | P0 | Done (shipped) |
| CRATE-5 | Match tracks to local audio files | `crate match` | P0 | Done (shipped) |
| CRATE-6 | Audio analysis (BPM/key/mood via essentia) | `crate analyze-mood` | P0 | Done (shipped) |
| CRATE-7 | LLM structured tagging (energy/function/crowd/mood) | `crate classify-tags` | P0 | **Won't build (superseded by CRATE-15)** |
| CRATE-8 | Build master library folder structure | `crate build-library` | P0 | Done (shipped) — revised by CRATE-17 |
| CRATE-9 | Build event-specific folder structure | `crate build-event` | P0 | Done (shipped) — revised by CRATE-18 |
| CRATE-10 | Write genre/BPM/key/tags into audio file metadata | `crate tag` | P0 | Done (shipped) |
| CRATE-11 | Review low-confidence classifications | `crate review` | P1 | Done (shipped) |
| CRATE-12 | Create Spotify sub-playlists per genre bucket | `crate create-playlists` | P1 | Done (shipped) |
| CRATE-13 | Sync classified playlists to Tidal (by ISRC) | `crate sync-to-tidal` | P2 | Done (shipped) |
| CRATE-14 | Cross-event `[DJ] Genre` master playlists | `crate build-masters` | P2 | Done (shipped) |
| CRATE-15 | Apply pre-classified tags from a JSON file | `crate apply-tags` | P1 | Done (shipped) |
| CRATE-16 | Write basic metadata into untagged audio files | `crate tag-untagged` | P2 | Done (shipped) |
| CRATE-17 | Review tracks before adding to master library | `crate review-library` | P1 | Planned |
| CRATE-18 | Flat, tag-driven event folders | `crate build-event` | P1 | Planned |

> **CRATE-7 will not be built.** LLM tagging is by design an agent-layer step: a sub-agent produces a tags JSON from the classified + audio-analyzed plan, and `crate apply-tags` (CRATE-15) validates and writes it. Keeping the LLM out of the CLI avoids an `anthropic` dependency and an API key requirement in the tool, and keeps the prompt editable in the [prepare-event skill](../.github/skills/prepare-event/SKILL.md). Build a native `crate classify-tags` only if agent-free, scriptable tagging (cron/CI) is ever needed.
> P1/P2 ordering is tentative — the DJ has not committed to all features. Treat the P0 set as the firm MVP; revisit P1/P2 before specing them.

## Success Metrics

| Metric | Definition | Target (initial) |
|--------|------------|------------------|
| Auto-classification rate | % of fetched tracks assigned a genre bucket without manual edits | ≥ 90% |
| Local match rate | % of tracks matched to a local audio file (ISRC → exact → fuzzy) | ≥ 80% of owned tracks |
| Analysis & tag coverage | % of matched tracks with full audio analysis + LLM tags | ≥ 95% of matched tracks |
| End-to-end prep time | Wall-clock time from `fetch` to event-ready folder for a ~100-track playlist | Materially faster than manual; track per release |
| Manual review rate | % of tracks flagged low-confidence requiring human review | ≤ 15% |

## Constraints

- **Single CLI, no services.** Cratekeeper stays a single `crate` Typer CLI — no web server, no background daemons.
- **File-driven, re-runnable stages.** State lives in `data/*.json` event plans; every stage should be safe to re-run (idempotent) and resumable.
- **Docker for audio analysis.** `analyze-mood` relies on essentia + TensorFlow models that run in the provided Docker image (Linux x86_64). Docker is an accepted dependency for that stage only.
- **PostgreSQL for the local file index.** `scan`/`match` use a local PostgreSQL index (`DATABASE_URL`, default `postgresql://dj:dj@localhost:5432/djlib`).
- **External API rate limits.** Spotify and MusicBrainz calls must respect rate limits (batching, throttling, retries).
- **Secrets via environment only.** Spotify credentials, `ANTHROPIC_API_KEY`, and `DATABASE_URL` come from the environment / gitignored config — never committed.
- **Python ≥ 3.11.**

## Non-Goals

Explicitly **not** part of Cratekeeper:

- **No GUI / web interface** — command line only.
- **No real-time playback or live-mixing engine** — Cratekeeper prepares crates; it does not play or mix.
- **No music streaming or downloading** — it organizes files the DJ already owns; it never pirates or downloads audio.
- **No multi-user or cloud sync** — single-operator, local-first.
- **No mobile app.**

## Open Questions

- Which P1/P2 features (Tidal sync, Spotify sub-playlists, cross-event masters) does the DJ actually want long-term?
- Should there be a single `crate prepare` orchestrator that chains the P0 pipeline, or keep stages discrete?
- Is an automated test suite in scope for the MVP, or added once the pipeline stabilizes?
