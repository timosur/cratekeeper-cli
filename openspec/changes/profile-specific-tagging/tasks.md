## 1. Config layer — TagConfig dataclasses and parsing

- [ ] 1.1 Add `TagFieldDef` and `TagConfig` dataclasses to `config.py`
- [ ] 1.2 Add `tag_config: TagConfig` attribute to `Profile` dataclass
- [ ] 1.3 Implement `_parse_tag_config()` to parse `[profiles.<name>.tags]` TOML section
- [ ] 1.4 Build default `TagConfig` from current `VALID_*` constants when `[tags]` section absent
- [ ] 1.5 Wire `_parse_tag_config()` into `_build_profile()` and `implicit_commercial_profile()`
- [ ] 1.6 Add config validation: reject invalid type, empty values, bad pick ranges
- [ ] 1.7 Update `Profile.describe()` to include tag vocabulary in output
- [ ] 1.8 Update `DEFAULT_CONFIG_TEMPLATE` with electronic tags example

## 2. Track model — generic tags storage

- [ ] 2.1 Add `tags: dict[str, str | list[str]]` field to `Track` dataclass in `models.py`
- [ ] 2.2 Ensure `tags` dict serializes/deserializes with plan JSON (save/load)

## 3. Tag validation — profile-aware apply-tags

- [ ] 3.1 Refactor `apply_tags()` in `tag_writer.py` to accept `TagConfig` parameter
- [ ] 3.2 Replace hardcoded `VALID_*` set checks with `TagConfig.fields` lookup
- [ ] 3.3 Implement strict validation: reject unknown values with clear error messages listing valid alternatives
- [ ] 3.4 Validate pick ranges (min/max) for list fields
- [ ] 3.5 Validate single-type fields reject arrays
- [ ] 3.6 Populate both `Track.tags` dict and legacy fields on successful application

## 4. Prompt builder — profile-aware generation

- [ ] 4.1 Change `build_tag_prompt()` signature to accept `TagConfig` parameter
- [ ] 4.2 Replace hardcoded vocabulary section with dynamic rendering from `TagConfig.fields`
- [ ] 4.3 Replace hardcoded JSON schema section with dynamic field list from `TagConfig`
- [ ] 4.4 Replace hardcoded classification guidance with `TagConfig.guidance`
- [ ] 4.5 Update `cli_pipeline.py` `tag-prompt` command to resolve profile and pass `TagConfig`
- [ ] 4.6 Update wizard `tag_prompt` step to use profile's `TagConfig`

## 5. Tag writer — profile-driven structured comment

- [ ] 5.1 Refactor comment builder to iterate `TagConfig.fields` in definition order
- [ ] 5.2 Remove hardcoded `era:X; energy:X; function:X; crowd:X; mood:X` format
- [ ] 5.3 Read tag values from `Track.tags` dict (fall back to legacy fields)
- [ ] 5.4 Ensure `era` remains implicit (computed, not from tag config)

## 6. CLI integration

- [ ] 6.1 Update `apply-tags` CLI command to resolve profile and pass `TagConfig` to validation
- [ ] 6.2 Update `tag` CLI command to pass `TagConfig` to comment builder
- [ ] 6.3 Ensure `--profile` flag propagates tag config correctly

## 7. Tests

- [ ] 7.1 Unit test: `_parse_tag_config()` with valid electronic config
- [ ] 7.2 Unit test: `_parse_tag_config()` with missing section returns defaults
- [ ] 7.3 Unit test: config validation rejects invalid type/empty values
- [ ] 7.4 Unit test: `apply_tags()` strict validation rejects unknown vocabulary
- [ ] 7.5 Unit test: `apply_tags()` respects pick ranges
- [ ] 7.6 Unit test: `build_tag_prompt()` renders profile-specific vocabulary
- [ ] 7.7 Unit test: comment builder uses profile field order
- [ ] 7.8 Integration test: end-to-end tag-prompt → apply-tags with electronic profile
- [ ] 7.9 Integration test: backward compat — no tags section produces legacy behaviour

## 8. Finalize

- [ ] 8.1 Remove or deprecate `VALID_ENERGY`, `VALID_FUNCTION`, `VALID_CROWD`, `VALID_MOOD` constants from `tag_writer.py` (replace with default TagConfig factory)
- [ ] 8.2 Run `openspec validate profile-specific-tagging --type change --strict`
- [ ] 8.3 Run full test suite, verify no regressions
