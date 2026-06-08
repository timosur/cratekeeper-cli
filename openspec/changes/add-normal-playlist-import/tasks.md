## 1. Data Model Refactor (models.py)

- [ ] 1.1 Extract `Plan` base dataclass from `EventPlan` with shared fields: `source_playlist_id`, `source_playlist_name`, `tracks`, `plan_type` (default `"event"`)
- [ ] 1.2 Move `save()`, `load()`, and `bucket_summary()` to `Plan` base class. `load()` dispatches on `plan_type` discriminator; missing field defaults to `EventPlan`
- [ ] 1.3 Make `EventPlan` inherit from `Plan`, keeping only `event_name`, `event_date`, `created_playlists`, `tidal_playlists`
- [ ] 1.4 Create `LibraryImportPlan` subclass inheriting from `Plan` with `plan_type = "library-import"` and no extra fields
- [ ] 1.5 Verify backward compatibility: load an existing JSON file without `plan_type` and confirm it deserializes as `EventPlan`

## 2. Update fetch command (cli.py)

- [ ] 2.1 Add interactive plan-type prompt to `fetch` using Rich or Typer: "Is this for an event or a library import?"
- [ ] 2.2 Create `LibraryImportPlan` when "library import" is selected, `EventPlan` when "event" is selected
- [ ] 2.3 Default to `EventPlan` when stdin is not a TTY (non-interactive mode)

## 3. Update pipeline commands to use Plan.load()

- [ ] 3.1 Change `classify` to use `Plan.load()` instead of `EventPlan.load()`
- [ ] 3.2 Change `enrich` to use `Plan.load()`
- [ ] 3.3 Change `review` to use `Plan.load()`
- [ ] 3.4 Change `match` to use `Plan.load()`
- [ ] 3.5 Change `analyze-mood` to use `Plan.load()`
- [ ] 3.6 Change `apply-tags` to use `Plan.load()`
- [ ] 3.7 Change `tag` to use `Plan.load()`
- [ ] 3.8 Change `tag-untagged` to use `Plan.load()`
- [ ] 3.9 Change `review-library` to use `Plan.load()`
- [ ] 3.10 Change `build-library` to use `Plan.load()`
- [ ] 3.11 Change `build-masters` to use `Plan.load()`

## 4. Add type guards for event-only commands

- [ ] 4.1 Add `isinstance(plan, EventPlan)` guard to `create-playlists` — print error and exit 1 for `LibraryImportPlan`
- [ ] 4.2 Add `isinstance(plan, EventPlan)` guard to `build-event` — print error and exit 1 for `LibraryImportPlan`
- [ ] 4.3 Add `isinstance(plan, EventPlan)` guard to `sync-to-tidal` — print error and exit 1 for `LibraryImportPlan`

## 5. Tests

- [ ] 5.1 Test `Plan.load()` returns `EventPlan` for JSON without `plan_type` field
- [ ] 5.2 Test `Plan.load()` returns `EventPlan` for JSON with `plan_type: "event"`
- [ ] 5.3 Test `Plan.load()` returns `LibraryImportPlan` for JSON with `plan_type: "library-import"`
- [ ] 5.4 Test `Plan.save()` round-trip: save and reload preserves `plan_type` and all fields for both subclasses
- [ ] 5.5 Test `EventPlan` retains event-specific fields (`event_name`, `event_date`, `created_playlists`, `tidal_playlists`)
- [ ] 5.6 Test `LibraryImportPlan` serializes without event-specific fields
- [ ] 5.7 Test event-only commands (`create-playlists`, `build-event`, `sync-to-tidal`) exit with error for `LibraryImportPlan`
- [ ] 5.8 Test pipeline commands work with `LibraryImportPlan` (at minimum: `classify`, `build-library`)
- [ ] 5.9 Update any existing tests that use `EventPlan.load()` directly to also cover `Plan.load()`

## 6. Validation and cleanup

- [ ] 6.1 Run `openspec validate add-normal-playlist-import --type change --strict` to verify specs match implementation
- [ ] 6.2 Run full test suite and fix any regressions
- [ ] 6.3 Update import statements across the codebase (`from cratekeeper.models import Plan` where needed)
