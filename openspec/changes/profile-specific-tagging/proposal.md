## Why

The tag vocabulary and LLM prompt are hardcoded and shared across all profiles. An electronic DJ gets asked to classify tracks by "singalong" function and "family" crowd — concepts that don't exist in club/festival contexts. Each profile needs its own tag dimensions, vocabulary, and prompt guidance so the LLM produces contextually meaningful classifications.

## What Changes

- **BREAKING**: Tag vocabulary (valid values per field) moves from hardcoded constants to per-profile structured config in `config.toml`
- **BREAKING**: Tag field definitions (which fields exist) become profile-specific — electronic uses `mix_traits` instead of `crowd`
- Prompt assembly reads vocabulary, field names, and classification guidance from profile config rather than a static template
- Different prompt templates per profile (code selects template based on profile, assembles using config values)
- Structured comment format becomes profile-specific (electronic: `era:X; energy:X; function:X; mood:X; mix:X`)
- `apply-tags` validates incoming JSON against the active profile's vocabulary (strict — rejects unknowns)
- Tracks tagged with old vocabulary get re-tagged on next tagging run (no migration command)

## Capabilities

### New Capabilities

_None — this extends existing capabilities._

### Modified Capabilities

- `profile-config`: Profile gains structured tag configuration: field definitions (name, type, valid values, pick count), classification guidance text, and prompt preamble. Config drives prompt assembly and validation.
- `tag-prompt-generation`: Prompt built dynamically from active profile's tag config instead of static template. Different prompt structures per profile (electronic emphasizes set-position thinking and mix traits; commercial emphasizes crowd demographics and singalong potential).
- `tagging`: Tag field set becomes profile-dependent. Validation checks values against profile vocabulary. Structured comment layout adapts to profile's field definitions. `mix_traits` added as new list field for electronic profile.

## Impact

- **Config schema**: `[profiles.<name>]` table in config.toml grows `[profiles.<name>.tags]` section with field definitions and guidance
- **tag_writer.py**: `VALID_*` constants replaced by profile-driven vocabulary lookup; comment builder reads field list from profile
- **tag_prompt.py**: Static prompt template replaced by profile-aware assembly logic
- **cli_pipeline.py**: `tag-prompt` and `apply-tags` commands must resolve active profile for vocabulary/validation
- **models.py**: Track dataclass gains optional `mix_traits: list[str]` field
- **Backward compat**: No config file → implicit commercial profile with current hardcoded vocabulary (existing behavior preserved)
- **Re-tagging**: Tracks with stale vocabulary values will fail strict validation on next `apply-tags` run, forcing re-classification via `tag-prompt`
