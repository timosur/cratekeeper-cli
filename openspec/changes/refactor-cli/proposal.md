## Why

`cli.py` has grown to 1238 lines with business logic embedded directly in command handlers, making the codebase hard to test, extend, and reason about. The package is also structurally awkward: double-nested directories, config baked into Python modules, and hard PostgreSQL coupling with no abstraction. A full structural refactor is needed before the pipeline grows further.

## What Changes

- **Flatten repo layout**: move `pyproject.toml` and `cratekeeper/` from `cratekeeper-cli/cratekeeper-cli/` to the repo root, eliminating double-nesting
- **Split `cratekeeper/` into domain sub-packages**: `spotify/`, `local/`, `export/`, `analysis/`, keeping `cli.py` at the top level as a thin entry point
- **Thin CLI handlers**: extract all inline business logic from `cli.py` into the appropriate domain modules; each command becomes an orchestration call only
- **Wizard delegates to CLI handlers**: `wizard.py` calls the same Typer command functions rather than reimplementing pipeline steps
- **Config-as-code → data files**: move `genre_buckets.py` and `mood_config.py` data structures to `.yaml` files loaded at runtime
- **Repository abstraction for DB**: introduce a thin repository/DAO layer over `local_scanner.py` and `matcher.py` so PostgreSQL is not directly coupled to domain logic
- **Resolve mixed public/private API**: standardise `is_fully_tagged` across `event_builder.py`, `library_builder.py`, and `cli.py`; eliminate cross-module private imports
- **All existing tests must pass** after the refactor

**BREAKING**: internal module paths and import locations will change. The public `crate` CLI surface (command names and flags) is unchanged.

## Capabilities

### New Capabilities

- `repository-layer`: DAO/repository abstraction over PostgreSQL for local file scanning and track matching — enables testing without a live DB connection

### Modified Capabilities

- `cli-pipeline`: behaviour unchanged, but implementation moves to domain modules; wizard delegates to CLI handlers instead of re-implementing steps
- `config-loading`: genre bucket and mood config data loaded from YAML files instead of inline Python dicts

## Impact

- **Code**: all 18 modules under `cratekeeper/`; `cli.py` (1238 lines), `wizard.py` (730 lines), `mood_analyzer.py` (454 lines), `local_scanner.py`, `matcher.py`
- **Directory layout**: `cratekeeper-cli/cratekeeper-cli/` collapses to repo root
- **Dependencies**: `pyyaml` added for config loading; no new runtime deps for repository layer
- **Tests**: all 9 test files updated to match new import paths; suite must be green on completion
- **Build**: `pyproject.toml` paths updated for new layout
