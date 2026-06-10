# Tidal Authentication

## Purpose

Provides native Tidal PKCE authentication and session management for all CLI commands that interact with Tidal, persisting credentials to a local JSON file with XDG-compliant paths.

## Requirements

### Requirement: Tidal PKCE authentication flow

The system SHALL provide a native `crate tidal-auth` command that authenticates with Tidal using PKCE OAuth and persists the session to a local JSON file.

#### Scenario: First-time authentication

- **GIVEN** no Tidal session file exists at `~/.config/cratekeeper/tidal-session.json`
- **WHEN** the DJ runs `crate tidal-auth`
- **THEN** the system initiates a PKCE login flow via `tidalapi`
- **AND** the DJ is prompted to visit a URL and paste the redirect back
- **AND** upon successful login, the session is saved to `~/.config/cratekeeper/tidal-session.json`
- **AND** a success message is displayed with the logged-in user info

#### Scenario: Re-authentication when session exists and is valid

- **GIVEN** a valid Tidal session file exists
- **WHEN** the DJ runs `crate tidal-auth`
- **THEN** the system detects the existing session and asks whether to re-authenticate
- **AND** if the DJ declines, the existing session is kept

#### Scenario: Re-authentication when session is expired

- **GIVEN** a Tidal session file exists but the session is expired and cannot be refreshed
- **WHEN** the DJ runs `crate tidal-auth`
- **THEN** the system detects the expired session and initiates a new PKCE login flow
- **AND** the new session replaces the old file

#### Scenario: XDG-compliant session path

- **GIVEN** the environment variable `XDG_CONFIG_HOME` is set to `/custom/config`
- **WHEN** the DJ runs `crate tidal-auth`
- **THEN** the session file is stored at `/custom/config/cratekeeper/tidal-session.json`

#### Scenario: XDG default when not set

- **GIVEN** the environment variable `XDG_CONFIG_HOME` is not set
- **WHEN** the DJ runs `crate tidal-auth`
- **THEN** the session file is stored at `~/.config/cratekeeper/tidal-session.json`

### Requirement: Tidal session loading for CLI commands

The system SHALL load the persisted Tidal session for all Tidal operations and MUST fail with a clear message if not authenticated.

#### Scenario: Load valid session

- **GIVEN** a valid Tidal session file exists
- **WHEN** a Tidal operation (sync, URL resolve) is invoked
- **THEN** the session is loaded and login is verified before proceeding

#### Scenario: Session file missing

- **GIVEN** no Tidal session file exists
- **WHEN** a Tidal operation is invoked
- **THEN** the system raises an error with the message "Run `crate tidal-auth` to authenticate"

#### Scenario: Session file exists but login invalid

- **GIVEN** a Tidal session file exists but `check_login()` returns false
- **WHEN** a Tidal operation is invoked
- **THEN** the system raises an error indicating the session is expired and to re-run `crate tidal-auth`
