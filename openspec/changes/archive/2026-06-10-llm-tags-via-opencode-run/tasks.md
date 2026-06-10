## 1. Core prompt generation module

- [x] 1.1 Create `cratekeeper/pipeline/tag_prompt.py` with `build_tag_prompt(tracks: list[Track]) -> str` function
- [x] 1.2 Import `VALID_ENERGY`, `VALID_FUNCTION`, `VALID_CROWD`, `VALID_MOOD` from `tag_writer.py` — single source of truth
- [x] 1.3 Render per-track context lines (id, name, artists, bucket, era, bpm, key, audio_energy, audio_mood, arousal, valence)
- [x] 1.4 Embed vocabulary constraints and JSON output schema in prompt text
- [x] 1.5 Add explicit instruction: "Return ONLY the JSON array. No markdown fences, no commentary."

## 2. CLI command registration

- [x] 2.1 Add `tag-prompt` command to `cli_pipeline.py` with `plan_file` argument and `--output` option
- [x] 2.2 Load plan via `Plan.load()` (polymorphic per ADR-0001)
- [x] 2.3 Call `build_tag_prompt(plan.tracks)`, print to stdout or write to `--output` path
- [x] 2.4 Warn if no tracks have analysis data (bpm/audio_mood missing)

## 3. Wizard integration

- [x] 3.1 In `wizard.py` `_run_apply_tags`, generate prompt file to `data/<slug>.tag-prompt.txt` before asking for tags path
- [x] 3.2 Print the prompt file path and instruct DJ to feed to LLM
- [x] 3.3 Skip prompt generation if step is already complete (`_apply_tags_complete` returns True)

## 4. Tests

- [x] 4.1 Unit test: `build_tag_prompt` returns string containing all track IDs from fixture plan
- [x] 4.2 Unit test: prompt text contains all vocabulary values from `VALID_*` constants
- [x] 4.3 Unit test: prompt text contains JSON schema description with correct field names
- [x] 4.4 Integration test: `crate tag-prompt` CLI command exits 0 and produces non-empty output for a fixture plan
- [x] 4.5 Unit test: `build_tag_prompt` with tracks lacking analysis data still produces valid prompt with available fields

## 5. Documentation and skill update

- [x] 5.1 Update prepare-event skill step 8 to reference `crate tag-prompt` instead of manual prompt construction
