## MODIFIED Requirements

### Requirement: Optional step skipping

The wizard SHALL allow optional steps to be skipped; required steps MUST NOT be skippable. The sync-to-tidal wizard step imports from `cratekeeper.tidal.client` (previously `cratekeeper.spotify.tidal`) and SHALL use the native Tidal session at `~/.config/cratekeeper/tidal-session.json`.

#### Scenario: User skips an optional step

- **GIVEN** the wizard is on an optional step (e.g. "enrich")
- **WHEN** the wizard asks "Run this step or skip?"
- **THEN** the user can choose "skip"
- **AND** the wizard advances to the next step without executing

#### Scenario: Required steps cannot be skipped

- **GIVEN** the wizard is on a required step (e.g. "classify")
- **WHEN** the wizard presents the step
- **THEN** no skip option is offered
- **AND** the step executes

#### Scenario: Optional terminal steps can be skipped

- **GIVEN** the wizard is on an optional terminal step (e.g. "create-playlists")
- **WHEN** the wizard asks "Run this step or skip?"
- **AND** the user chooses "skip"
- **THEN** the wizard advances (or finishes if no more steps remain)

#### Scenario: Sync-to-tidal step uses native session

- **GIVEN** the wizard is on the "sync-to-tidal" optional step
- **AND** a valid Tidal session exists at `~/.config/cratekeeper/tidal-session.json`
- **WHEN** the step executes
- **THEN** the system loads the Tidal session from the native path
- **AND** syncs per-bucket playlists to Tidal via ISRC

#### Scenario: Sync-to-tidal step without Tidal session

- **GIVEN** the wizard is on the "sync-to-tidal" optional step
- **AND** no Tidal session file exists
- **WHEN** the step attempts execution
- **THEN** the system displays an error directing the user to run `crate tidal-auth`
- **AND** the wizard does not silently skip the step
