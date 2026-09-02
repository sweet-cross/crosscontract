# Implement `SubmissionHandler.validate_targets` — loop and collection

## Context

**Part of PRD:** [submission-validation.md](../../prds/submission-validation.md) — WP3, §4, edge cases 7–12.

The loop over every target, collecting failures instead of stopping at the first. This is
the method the [ADR 0004 amendment](../../adrs/0004-submission-contracts-carry-extraction-instructions.md)
exists to permit; the selective `targets` argument is task 07.

## Acceptance Criteria

- [X] `validate_targets(resolver, targets=None, check_existing_primary_key=False, check_existing_foreign_key=False, lazy=True) -> dict[str, pd.DataFrame]`
  exists, `resolver` **required**.
- [X] Delegates to `validate_target` per target and does no resolution of its own.
- [X] Returns validated, coerced frames keyed by **target name** (not contract name).
- [X] Every failing target is validated before anything is raised — no fail-fast, and no
  `fail_fast` parameter.
- [X] Failures are raised together as `TargetValidationError`, one entry per failing target.
- [X] When some targets pass and others fail, the passing frames are discarded (all-or-nothing);
  a test pins this so it is a decision rather than an accident.
- [X] The message names the failing targets; `to_list()` rows carry their `target`.
- [X] Wiring failures (task 05's three `ValueError`s) escape **immediately** and are not
  collected — one test asserting a `ValueError`, not a `TargetValidationError`.
- [ ] A forgotten `drop_columns` (extra column, caught by `strict=True`) is a *collected*
  failure, not an escaping exception.
- [X] `lazy=False` still yields one `SchemaValidationError` per failing target.

## Implementation Details

- **Modify:** [src/crosscontract/submission/submission_handler.py](../../../src/crosscontract/submission/submission_handler.py),
  **modify:** `src/tests/submission/test_validate_targets.py`.
- **Confirm the open decision first** — PRD edge case 7: an exception raised *by a
  transformation* propagates immediately rather than joining the collection, because the
  mapping is typed `dict[str, SchemaValidationError]`. This was not settled in the design
  session. If it flips, the mapping needs a wider value type and task 03's `to_list()` row
  shape has to say what a non-schema failure looks like — so resolve it before writing code,
  not after.
- Do not catch broadly: catch `SchemaValidationError` only. Anything else escaping is the
  intended behaviour, not an oversight.
- Keying by target name is load-bearing: contract-uniqueness is a relaxable guard, a target
  name is its identity, so a contract-keyed dict would silently collapse two entries if that
  guard were ever relaxed.
- **Depends on:** tasks 03, 04 (and 05 for the wiring-failure test).
- **Verification:** `uv run pytest src/tests/submission/`
