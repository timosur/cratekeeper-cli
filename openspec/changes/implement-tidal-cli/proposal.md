## Why

The Tidal integration currently depends on an external `tidal-mcp` package for authentication (`python -m tidal_mcp.auth`) and stores session data at a hardcoded project-relative path (`tidal-mcp/tidal-session.json`). With the tidal-mcp MCP server removed, auth is broken. The `tidalapi` library natively supports PKCE-based login with session file persistence, so we can replace the external dependency with a native `crate tidal-auth` command — matching the existing `crate spotify-auth` pattern — and move the Tidal module out of the `cratekeeper/spotify/` package where it doesn't belong.

## What Changes

- **New `crate tidal-auth` command**: Native PKCE-based Tidal authentication flow using `tidalapi.Session.login_session_file(do_pkce=True)`. Session persisted at `~/.config/cratekeeper/tidal-session.json` (XDG-compliant). Shows login status when session already exists (like `spotify-auth`).
- **New `cratekeeper/tidal/` package**: Move Tidal client code from `cratekeeper/spotify/tidal.py` to `cratekeeper/tidal/` with `auth.py` (auth flow + session management) and `client.py` (playlist ops, ISRC search, sync). Mirrors the `cratekeeper/spotify/` package structure.
- **New `cli_tidal.py` module**: Move `sync-to-tidal` command from `cli_spotify.py` and Tidal URL resolution from `cli_local.py` into `cli_tidal.py`. Register via `register(app)` pattern.
- **Remove `tidal-mcp` dependency**: Delete hardcoded `tidal-mcp/tidal-session.json` path lookups and `python -m tidal_mcp.auth` references. Config lookup follows XDG pattern (`~/.config/cratekeeper/tidal-session.json`).
- **Update all import paths**: Wizard, CLI modules, and matcher that import from `cratekeeper.spotify.tidal` updated to `cratekeeper.tidal.client`.
- **BREAKING**: Session file location changes from `<project>/tidal-mcp/tidal-session.json` to `~/.config/cratekeeper/tidal-session.json`. Users must re-authenticate with `crate tidal-auth`.

## Capabilities

### New Capabilities
- `tidal-auth`: Native Tidal PKCE authentication flow, session persistence, and session loading. Covers the `crate tidal-auth` command and the session management used by all Tidal operations.

### Modified Capabilities
- `playlist-management`: `sync-to-tidal` command moves from `cli_spotify.py` to `cli_tidal.py`; imports change from `cratekeeper.spotify.tidal` to `cratekeeper.tidal.client`.
- `track-matching`: `--tidal-urls` flag on `match` command imports change from `cratekeeper.spotify.tidal` to `cratekeeper.tidal.client`.
- `interactive-wizard`: `sync-to-tidal` wizard step imports change from `cratekeeper.spotify.tidal` to `cratekeeper.tidal.client`.

## Impact

- **Code**: `cratekeeper/spotify/tidal.py` deleted. New `cratekeeper/tidal/` package created. `cli_spotify.py` loses `sync-to-tidal`. `cli_local.py` loses Tidal URL resolution code. New `cli_tidal.py` gains both. `wizard.py` import paths updated. `cli.py` gains `tidal-auth` command registration.
- **Dependencies**: No new dependencies. `tidalapi>=0.8.1` already in `pyproject.toml`. External `tidal-mcp` package no longer referenced.
- **Config**: New session file at `~/.config/cratekeeper/tidal-session.json`. Old path abandoned.
- **Tests**: Existing tests (`test_plan_model.py`, `test_wizard.py`) may need import path updates. New tests for `tidal-auth` flow and session loading.
