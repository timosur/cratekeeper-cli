## Why

The LLM tag classification step (energy, function, crowd, mood) currently lives only as manual instructions in the prepare-event skill. The DJ must hand-craft or copy-paste a prompt with track data every time. A CLI command that generates a ready-to-use prompt from the plan's analysis data eliminates this friction while keeping the CLI itself LLM-free.

## What Changes

- New command `crate tag-prompt <plan.json>` that prints a self-contained LLM prompt to stdout
- The prompt includes all tracks with their analysis context (name, artists, bucket, era, bpm, key, audio energy/mood scores, arousal, valence)
- The prompt embeds vocabulary constraints and the exact JSON output schema expected by `crate apply-tags`
- Optional `--output <file>` flag to write prompt to a file instead of stdout
- No new runtime dependencies -- the CLI generates text, user feeds it to any LLM harness

## Capabilities

### New Capabilities
- `tag-prompt-generation`: Generates a self-contained LLM prompt from plan analysis data that produces JSON compatible with `crate apply-tags`

### Modified Capabilities
- `tagging`: Spec gains a new requirement for prompt generation alongside the existing apply/embed/untagged requirements

## Impact

- New CLI command registered in `cli_pipeline.py`
- New module `cratekeeper/pipeline/tag_prompt.py` (or similar) for prompt assembly logic
- Reads from plan JSON (same format as `apply-tags` and `tag`)
- No new dependencies -- uses only stdlib string formatting
- Prepare-event skill step 8 can reference `crate tag-prompt` instead of manually building prompts
