## 1. Create `cratekeeper/tidal/` package

- [ ] 1.1 Create `cratekeeper/tidal/__init__.py` (empty)
- [ ] 1.2 Create `cratekeeper/tidal/auth.py` with `_session_path()` (XDG-compliant, respects `XDG_CONFIG_HOME`), `run_tidal_auth()` (PKCE flow via `login_session_file(do_pkce=True)`, checks existing session, Rich console output), and `get_tidal_session()` (loads session, validates login, raises with "run `crate tidal-auth`" message)
- [ ] 1.3 Create `cratekeeper/tidal/client.py` by moving all functions from `cratekeeper/spotify/tidal.py` (`create_playlist`, `add_tracks_by_isrc`, `get_user_playlists`, `search_track_by_isrc`, `sync_plan_to_tidal`, `resolve_tidal_urls`). Import `get_tidal_session` from `cratekeeper.tidal.auth` instead of defining it locally.

## 2. Register `crate tidal-auth` command

- [ ] 2.1 Add `tidal-auth` command in `cratekeeper/cli.py` (matching `spotify-auth` pattern), calling `run_tidal_auth()` from `cratekeeper.tidal.auth`

## 3. Create `cli_tidal.py` and move Tidal CLI commands

- [ ] 3.1 Create `cratekeeper/cli_tidal.py` with `register(app)` function
- [ ] 3.2 Move `sync-to-tidal` command from `cli_spotify.py` to `cli_tidal.py`, update import from `cratekeeper.tidal.client`
- [ ] 3.3 Move `--tidal-urls` resolution logic from `cli_local.py` `match` command into a helper in `cli_tidal.py` or keep the flag on `match` but update import to `cratekeeper.tidal.client` (per design D6: flag stays on `match`, only import changes)
- [ ] 3.4 Register `cli_tidal` in `cli.py` alongside other `cli_*.py` modules

## 4. Update existing imports

- [ ] 4.1 Update `wizard.py` `_run_sync_tidal()` to import from `cratekeeper.tidal.client` instead of `cratekeeper.spotify.tidal`
- [ ] 4.2 Update `cli_local.py` `match` command `--tidal-urls` to import from `cratekeeper.tidal.client` instead of `cratekeeper.spotify.tidal`
- [ ] 4.3 Remove `sync-to-tidal` command from `cli_spotify.py`

## 5. Delete old module

- [ ] 5.1 Delete `cratekeeper/spotify/tidal.py`

## 6. Tests

- [ ] 6.1 Add test for `_session_path()` respecting `XDG_CONFIG_HOME` and default
- [ ] 6.2 Add test for `get_tidal_session()` raising `FileNotFoundError` when no session file exists
- [ ] 6.3 Verify existing tests pass (`test_plan_model.py`, `test_wizard.py`) — update imports if needed
- [ ] 6.4 Run full test suite: `make test`

## 7. Validation

- [ ] 7.1 Run `openspec validate implement-tidal-cli --type change --strict` to verify specs are coherent
