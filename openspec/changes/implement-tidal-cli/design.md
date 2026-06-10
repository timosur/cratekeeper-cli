## Context

The `crate` CLI integrates with Tidal for playlist syncing (`sync-to-tidal`) and ISRC-based track URL resolution (`match --tidal-urls`). Currently, all Tidal code lives in `cratekeeper/spotify/tidal.py` and delegates authentication to an external `tidal-mcp` package that has been removed. The session file is hardcoded at `<project-root>/tidal-mcp/tidal-session.json`.

The Spotify integration follows a clean pattern: `cratekeeper/spotify/auth.py` handles OAuth interactively, `cratekeeper/spotify/client.py` wraps API calls, config lives at `~/.config/cratekeeper/spotify-config.json`, and a top-level `crate spotify-auth` command runs the flow.

ADR-0001 (Plan base class with type discriminator) is in force. The `EventPlan.tidal_playlists` field and `Plan` polymorphism are unchanged by this design.

### Component Diagram (C4 Level 3 — CLI container internals, Tidal scope)

```
┌──────────────────────────────────────────────────────────────────────┐
│                          crate CLI (Typer)                           │
│                                                                      │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐               │
│  │  cli.py       │  │ cli_tidal.py │  │  wizard.py   │               │
│  │ [tidal-auth]  │  │ [sync-to-   │  │ [sync-to-    │               │
│  │              │  │  tidal,      │  │  tidal step]  │               │
│  │              │  │  tidal-urls] │  │              │               │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘               │
│         │                 │                 │                        │
│         ▼                 ▼                 ▼                        │
│  ┌──────────────────────────────────────────────────────┐           │
│  │                cratekeeper/tidal/                      │           │
│  │  ┌────────────┐            ┌────────────────┐        │           │
│  │  │  auth.py   │            │   client.py    │        │           │
│  │  │            │            │                │        │           │
│  │  │ session    │───────────▶│ get_session()  │        │           │
│  │  │ config     │  provides  │ create_playlist│        │           │
│  │  │ path &     │  session   │ add_by_isrc    │        │           │
│  │  │ PKCE login │            │ sync_plan      │        │           │
│  │  │            │            │ resolve_urls   │        │           │
│  │  └─────┬──────┘            └───────┬────────┘        │           │
│  │        │                           │                  │           │
│  └────────┼───────────────────────────┼──────────────────┘           │
│           │                           │                              │
└───────────┼───────────────────────────┼──────────────────────────────┘
            │                           │
            ▼                           ▼
   ┌────────────────┐          ┌────────────────┐
   │ ~/.config/     │          │  Tidal API     │
   │ cratekeeper/   │          │  (tidalapi)    │
   │ tidal-session  │          │                │
   │ .json          │          └────────────────┘
   └────────────────┘
```

**Boundaries**: `cratekeeper/tidal/` is a self-contained package. Auth produces and consumes a session file. Client consumes sessions and talks to the Tidal API. CLI modules and wizard depend on the package — never the other way around.

## Goals / Non-Goals

**Goals:**
- Native `crate tidal-auth` command using tidalapi's PKCE flow, matching the Spotify auth UX pattern
- Self-contained `cratekeeper/tidal/` package with auth and client separated
- Session stored at `~/.config/cratekeeper/tidal-session.json` (XDG-compliant)
- All Tidal CLI commands in `cli_tidal.py` (decoupled from Spotify module)
- Zero external auth dependencies — only `tidalapi` (already in pyproject.toml)
- All existing Tidal functionality preserved (sync, ISRC resolve, wizard step)

**Non-Goals:**
- Tidal as a track ingestion source (fetching playlists FROM Tidal — Spotify remains the ingestion source)
- Tidal HiRes download or streaming integration
- Tidal-specific playlist management beyond what exists today
- Migrating existing session files from old location (users re-auth once)

## Decisions

### D1: Use `login_session_file(do_pkce=True)` for auth

**Choice**: Delegate to tidalapi's built-in `Session.login_session_file()` with PKCE enabled.

**Rationale**: This method handles the complete lifecycle — checks for existing session, prompts for PKCE login if needed, persists tokens to JSON, and refreshes expired tokens on reload. No custom token management needed, unlike the Spotify integration which manually manages token refresh.

**Alternatives considered**:
- `login_oauth_simple()` (device code flow): Simpler but no HiRes FLAC access. PKCE gives maximum quality access.
- Custom OAuth flow (like Spotify `auth.py`): Unnecessary complexity — tidalapi already wraps this cleanly. Spotify needed it because spotipy's auth is lower-level.

### D2: Session file at `~/.config/cratekeeper/tidal-session.json`

**Choice**: XDG config home, same directory as `spotify-config.json`.

**Rationale**: Consistent with Spotify config location. `tidalapi` manages the file format — we just provide the path. The file contains OAuth tokens (token_type, access_token, refresh_token, expiry_time, is_pkce).

**Alternatives considered**:
- Project-relative path (current): Breaks when running from different directories. Couples to workspace layout.
- Separate `~/.config/tidal/` directory: Fragments config. All cratekeeper config should live together.

### D3: Module structure mirrors Spotify

**Choice**: `cratekeeper/tidal/__init__.py`, `auth.py`, `client.py` — mirroring `cratekeeper/spotify/`.

**Rationale**: Consistent internal structure. `auth.py` owns the session path, login flow, and session loading. `client.py` owns all API operations (moved from `cratekeeper/spotify/tidal.py`). Clean import paths: `from cratekeeper.tidal.auth import run_tidal_auth` and `from cratekeeper.tidal.client import get_tidal_session`.

**Alternatives considered**:
- Single `cratekeeper/tidal.py` module: No room for separation. Auth and client mixed together.
- Keep in `cratekeeper/spotify/tidal.py`: Misleading location. Tidal is an independent service.

### D4: CLI commands in `cli_tidal.py`

**Choice**: New `cli_tidal.py` with `register(app)` pattern. Contains:
- `sync-to-tidal` (moved from `cli_spotify.py`)
- `tidal-urls` subcommand or flag handling (moved from `cli_local.py`)

The `tidal-auth` command registers directly in `cli.py` (like `spotify-auth`) since it's a top-level auth command, not a pipeline step.

**Rationale**: Follows established CLI module pattern. Each `cli_*.py` registers its own commands. `tidal-auth` in `cli.py` matches `spotify-auth` placement.

**Alternatives considered**:
- Keep `sync-to-tidal` in `cli_spotify.py`: Misleading — it's a Tidal command, not Spotify.
- Tidal sub-app (`crate tidal auth/sync/...`): Inconsistent with existing top-level command pattern.

### D5: `auth.py` wraps tidalapi session management

The `auth.py` module provides:
- `_session_path() -> Path`: Returns XDG-compliant session path
- `run_tidal_auth() -> None`: Interactive PKCE auth flow. Checks existing session, prompts re-auth if valid. Uses Rich console output matching Spotify auth UX.
- `get_tidal_session() -> tidalapi.Session`: Loads session from file, validates login. Called by client functions. Raises `FileNotFoundError` with "run `crate tidal-auth`" message if no session exists.

The `client.py` module imports `get_tidal_session` from `auth.py` and keeps all existing API functions unchanged (just updated imports).

### D6: `match --tidal-urls` stays as a flag on `match`

**Choice**: Keep `--tidal-urls` as a flag on the `match` command in `cli_local.py`, but change the import to `cratekeeper.tidal.client`. Do NOT move the entire `match` command to `cli_tidal.py`.

**Rationale**: `match` is fundamentally a local-file operation. The `--tidal-urls` flag is an optional enrichment. Moving the whole command would break the logical grouping. Only the import path changes.

## Risks / Trade-offs

- **[Breaking change: re-auth required]** → Acceptable for alpha-stage tool. Document in commit message.
- **[tidalapi session format coupling]** → We depend on tidalapi's session JSON format. If tidalapi changes it, sessions break. → Mitigation: `login_session_file()` is tidalapi's public API; format changes would be handled by the library itself on reload.
- **[PKCE requires browser interaction]** → User must paste a redirect URL back into the terminal. Less seamless than Spotify's auto-callback server. → Mitigation: This is tidalapi's standard flow. Could add device-code fallback later if needed.
- **[No session auto-refresh on expiry during commands]** → If session expires mid-operation, it fails. → Mitigation: `login_session_file()` auto-refreshes on load. Sessions typically last 7 days. Users can re-run `crate tidal-auth` if expired.

## Migration Plan

1. Create `cratekeeper/tidal/` package with `__init__.py`, `auth.py`, `client.py`
2. Move client functions from `cratekeeper/spotify/tidal.py` to `cratekeeper/tidal/client.py`
3. Implement auth flow in `cratekeeper/tidal/auth.py`
4. Create `cli_tidal.py`, move `sync-to-tidal` from `cli_spotify.py`
5. Register `tidal-auth` in `cli.py`, register `cli_tidal` commands
6. Update imports in `wizard.py`, `cli_local.py`
7. Delete `cratekeeper/spotify/tidal.py`
8. Update tests
9. No data migration — users re-authenticate once

Rollback: Revert the commit. Old `tidal-mcp` auth was already broken, so there's no regression risk.

## Open Questions

None — all decisions resolved during proposal grilling.
