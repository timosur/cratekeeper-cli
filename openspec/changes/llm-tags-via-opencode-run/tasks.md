## 1. Core prompt generation module

- [ ] 1.1 Create `cratekeeper/pipeline/tag_prompt.py` with `build_tag_prompt(tracks: list[Track]) -> str` function
- [ ] 1.2 Import `VALID_ENERGY`, `VALID_FUNCTION`, `VALID_CROWD`, `VALID_MOOD` from `tag_writer.py` — single source of truth
- [ ] 1.3 Render per-track context lines (id, name, artists, bucket, era, bpm, key, audio_energy, audio_mood, arousal, valence)
- [ ] 1.4 Embed vocabulary constraints and JSON output schema in prompt text
- [ ] 1.5 Add explicit instruction: "Return ONLY the JSON array. No markdown fences, no commentary."

## 2. CLI command registration

- [ ] 2.1 Add `tag-prompt` command to `cli_pipeline.py` with `plan_file` argument and `--output` option
- [ ] 2.2 Load plan via `Plan.load()` (polymorphic per ADR-0001)
- [ ] 2.3 Call `build_tag_prompt(plan.tracks)`, print to stdout or write to `--output` path
- [ ] 2.4 Warn if no tracks have analysis data (bpm/audio_mood missing)

## 3. Wizard integration

- [ ] 3.1 In `wizard.py` `_run_apply_tags`, generate prompt file to `data/<slug>.tag-prompt.txt` before asking for tags path
- [ ] 3.2 Print the prompt file path and instruct DJ to feed to LLM
- [ ] 3.3 Skip prompt generation if step is already complete (`_apply_tags_complete` returns True)

## 4. Tests

- [ ] 4.1 Unit test: `build_tag_prompt` returns string containing all track IDs from fixture plan
- [ ] 4.2 Unit test: prompt text contains all vocabulary values from `VALID_*` constants
- [ ] 4.3 Unit test: prompt text contains JSON schema description with correct field names
- [ ] 4.4 Integration test: `crate tag-prompt` CLI command exits 0 and produces non-empty output for a fixture plan
- [ ] 4.5 Unit test: `build_tag_prompt` with tracks lacking analysis data still produces valid prompt with available fields

## 5. Documentation and skill update

- [ ] 5.1 Update prepare-event skill step 8 to reference `crate tag-prompt` instead of manual prompt construction
