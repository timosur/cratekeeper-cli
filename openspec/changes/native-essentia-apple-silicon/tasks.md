## 1. Dependencies

- [ ] 1.1 In `pyproject.toml`, move `essentia-tensorflow>=2.1b6.dev1389` from optional `[audio]` extra to core `dependencies` (keep `platform_system != 'Windows'` marker)
- [ ] 1.2 Remove the `[audio]` optional-dependencies group if it becomes empty

## 2. mood_analyzer.py cleanup

- [ ] 2.1 Remove `_remap_path()` function and all calls to it in `analyze_tracks()`
- [ ] 2.2 Simplify `_default_models_dir()` — remove `/.dockerenv` check, always use `~/.cache/cratekeeper/models` (respecting `XDG_CACHE_HOME` and `ESSENTIA_MODELS_DIR` env override)
- [ ] 2.3 Update the `ImportError` message in `extract_features()` to say `pip install essentia-tensorflow` instead of referencing Docker
- [ ] 2.4 Update module docstring to remove Docker/Linux references

## 3. Docker cleanup

- [ ] 3.1 Delete `Dockerfile`
- [ ] 3.2 Remove the `crate` service from `docker-compose.yml`, keep only the `db` service and `pgdata` volume

## 4. Documentation updates

- [ ] 4.1 Update `README.md` — remove all "Docker for essentia" / "Linux x86_64 only" references, document native `pip install` path, note macOS 15+ requirement and first-run model download
- [ ] 4.2 Update `openspec/config.yaml` — remove "Docker for audio analysis only" constraint
- [ ] 4.3 Update `.agents/skills/prepare-event/SKILL.md` — remove "Docker for essentia audio analysis" references, update to native execution

## 5. Verification

- [ ] 5.1 Reinstall project in venv (`pip install -e .`) and confirm essentia-tensorflow installs natively on Apple Silicon
- [ ] 5.2 Run `crate analyze-mood` on a test plan to verify native analysis works end-to-end
- [ ] 5.3 Run `pytest` to ensure no regressions
