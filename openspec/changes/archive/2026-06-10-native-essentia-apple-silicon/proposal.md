## Why

essentia-tensorflow now ships native ARM64 wheels for macOS (`macosx_15_0_arm64`), starting from version `2.1b6.dev1389` (Jul 2025). The project currently forces all audio analysis through a Docker container running Linux x86_64 with QEMU emulation on Apple Silicon, adding ~3-5x overhead per track. Docker is no longer needed for essentia — only for PostgreSQL.

## What Changes

- **BREAKING**: Remove the essentia/TF Docker image (`Dockerfile`). Audio analysis runs natively via `pip install essentia-tensorflow`. Users on macOS 15+ Apple Silicon (or Linux x86_64) can run `crate analyze-mood` directly without Docker.
- Move `essentia-tensorflow` from optional `[audio]` extra to core dependency (guarded by `platform_system != 'Windows'`).
- Remove Docker path detection (`/.dockerenv`) and path remapping (`_remap_path()`) from `mood_analyzer.py`.
- Models continue to lazy-download to `~/.cache/cratekeeper/models` on first use (existing `_ensure_model()` mechanism). No baked-in models needed.
- Update all documentation, specs, and config referencing "Docker required for essentia" or "Linux x86_64 only".
- Simplify the Dockerfile to serve only PostgreSQL (or remove it entirely if Docker Compose already handles DB separately).

## Capabilities

### New Capabilities

_(none — this change removes infrastructure, it does not introduce new user-facing capabilities)_

### Modified Capabilities

- `audio-analysis`: Remove Docker/Linux x86_64 requirement. Analysis runs natively on macOS Apple Silicon and Linux. Dockerfile and container path remapping are removed. Model download behaviour unchanged.

## Impact

- **Dependencies**: `essentia-tensorflow` moves from optional `[audio]` to core in `pyproject.toml`.
- **Dockerfile**: Removed or reduced to DB-only scope. No more essentia/model layers.
- **mood_analyzer.py**: Remove `_remap_path()`, `/.dockerenv` detection, `/app/models` path branch.
- **Documentation**: README, openspec/config.yaml, prepare-event skill, audio-analysis spec all reference Docker requirement — all need updating.
- **CI**: If CI relied on Docker for audio tests, it can now `pip install essentia-tensorflow` directly.
- **Platform requirements**: macOS 15.0+ (Sequoia) for Apple Silicon wheels. Linux x86_64 continues to work via pip.
