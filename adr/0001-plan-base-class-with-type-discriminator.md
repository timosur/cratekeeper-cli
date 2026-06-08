# Plan base class with type discriminator

- Status: accepted
- Date: 2026-06-08

## Context and Problem Statement

The CLI pipeline processes Spotify playlists through fetch, enrich, classify, match, analyze, tag, review, and build steps. The data model (`EventPlan`) assumes every playlist is tied to an event with `event_name`, `event_date`, and per-bucket Spotify/Tidal playlist IDs. Adding library imports — playlists that go through the same pipeline but are not event-bound — requires the data model to support multiple plan types while keeping pipeline commands polymorphic.

## Considered Options

- **Plan base class with type discriminator**: Extract shared fields (`source_playlist_id`, `source_playlist_name`, `tracks`) into a `Plan` base dataclass. Add a `plan_type` string discriminator. `Plan.load()` inspects the discriminator and returns the correct subclass. Missing discriminator defaults to `EventPlan` for backward compatibility.
- **Make event fields optional on EventPlan**: Minimal change — mark `event_name`, `event_date`, etc. as `Optional`. Every consumer must check for `None`. Muddies the model semantics.
- **Separate LibraryImportPlan with no shared base**: Clean separation but duplicates `tracks`, `save()`, `load()`, `bucket_summary()`, and all shared fields. DRY violation grows with each new plan type.

## Decision Outcome

Chosen option: "Plan base class with type discriminator", because it keeps pipeline commands polymorphic (they accept `Plan`), gives event-only commands a clean `isinstance` check, avoids field duplication, and supports future plan types (e.g., crate-dig, sample-pack) without further refactoring. The discriminator pattern is standard in Python dataclass serialization.

### Consequences

- Good, because pipeline commands operate on `Plan` without type-specific branching
- Good, because `EventPlan` remains fully backward-compatible — existing JSON files without `plan_type` load as `EventPlan`
- Good, because new plan types can be added by subclassing `Plan` and adding a discriminator value
- Bad, because all existing code importing `EventPlan.load()` must migrate to `Plan.load()` for polymorphic behavior
- Bad, because tests that construct `EventPlan` directly need updating to cover the base-class contract
- Neutral, because `LibraryImportPlan` is initially thin (no extra fields), but the subclass provides type safety and a place for future extensions
