# Integration tests through the schema and submission paths

## Context

**Part of PRD:** [.ai-context/prds/2026-09-08-dimension-granularity-check.md](../../prds/2026-09-08-dimension-granularity-check.md)

WP2, step 4. The unit tests prove the predicate and the derivation; these prove the whole
path reports the right thing, and they turn the ADR 0007 claim in PRD §6 from an assertion
into a test.

## Acceptance Criteria

- [X] End-to-end through `TableSchema.validate_dataframe`: a violating frame raises
  `SchemaValidationError`, and the parsed error names the dimension column.
- [X] The PRD's "done means" pair: `(A, 2030, ch, 100)` + `(A, 2030, ch_ag, 30)` raises and
  names the `ch` row; `(A, 2030, ch, 100)` + `(B, 2030, ch_ag, 30)` succeeds.
- [X] A frame carrying a granularity violation, a primary key violation and a foreign key
  violation in one `lazy=True` run reports all three, each by the rule that owns it.
- [X] Through `SubmissionHandler.validate_target`: the submission path inherits the check
  with no submission-specific code.

## Implementation Details

- Modify the integration-level tests under `src/tests/contracts/schema/` and
  `src/tests/submission/`.
- Pandera carries exactly one string per check into `failure_cases` and
  `SchemaValidationError` parses the columns back out of it (ADR 0006) — assert on the
  parsed column, not on the raw pandera output.
- Depends on `05` (and `06` if the client path is exercised).
- Do not run pytest without asking (repo `CLAUDE.md`).
