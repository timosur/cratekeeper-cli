# CRATE-X: Feature Name

## Description

_What this feature does and why it matters._

## Scope

_Which command(s) / pipeline stage(s) and areas this spec covers._

## User Stories

- As a [role], I want [action], so that [benefit].

## CLI Contract

- **Command:** `crate <name>` _(or new option on an existing command)_ — position in the pipeline
- **Arguments / options:** name, type, default, required/optional (e.g. `--dry-run`, `--output` / `-o`)
- **Input:** what it reads (a `data/*.json` plan, a directory, a playlist URL)
- **Output / side effects:** files written, JSON fields added, remote resources created, console summary
- **Exit behaviour:** success vs. failure conditions; what a non-zero exit means
- **Console UX:** what the user sees (Rich tables, progress lines, warnings)

## Acceptance Criteria

- [ ] AC-1: Description of testable condition (observable file/JSON/console output)
- [ ] AC-2: Description of testable condition

## Edge Cases

- EC-1: Description of boundary condition or error scenario (bad input, missing creds, service error, re-run)

## Dependencies

- Requires: CRATE-Y (Feature Name) — _why_

---

<!-- Appended by Solution Architect agent -->

## Tech Design

_To be filled by the Solution Architect agent._

## Implementation Plan

_See `project/plans/CRATE-X-plan.md` (created by the Solution Architect agent)._
