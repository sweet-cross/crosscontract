# Implement `SubmissionHandler.validate_target`

## Context

**Part of PRD:** [submission-validation.md](../../prds/submission-validation.md) — WP2, §4.

The primitive of the whole feature: extract one target, transform it, validate the result
against the contract that target names. Everything else in this PRD either supports it or
loops it. Guards are deliberately a separate task (05) so this one stays about the happy
path.

## Acceptance Criteria

- [X] `validate_target(target_name, contract=None, resolver=None, check_existing_primary_key=False, check_existing_foreign_key=False, lazy=True) -> pd.DataFrame`
  exists on `SubmissionHandler`.
- [X] It composes `get_target_data(target_name)` with `contract.validate_data(...)` and
  returns the **validated, coerced** frame.
- [X] `contract` takes precedence: when both are given, the resolver is never asked to
  resolve. Tested with a resolver whose contract *would* fail.
- [X] When only `resolver` is given, the target's contract is resolved through it.
- [X] All three pass-through parameters reach `validate_data` unchanged.
- [X] With both `check_existing_*` flags `False`, the resolver receives **no `get_data`
  calls** — assert this explicitly; it is the "no unexpected network" property.
- [X] A target claiming no rows returns an empty frame (the permanent handler-level
  counterpart to task 01).
- [X] Coercion is asserted by a changed dtype, not merely by the absence of an exception.
- [X] Google-style docstring covering `Args:` / `Returns:` / `Raises:`, including the note
  that a non-lazy report is degraded (pandera does not attach the frame, so key values
  cannot be recovered).

## Implementation Details

- **Modify:** [src/crosscontract/submission/submission_handler.py](../../../src/crosscontract/submission/submission_handler.py).
- **Create:** `src/tests/submission/test_validate_targets.py` — covers this task and 05/06/07.
  Reuse the fixture shape from
  [test_submission_handler.py](../../../src/tests/submission/test_submission_handler.py)
  (two profiles, targets with and without their own transformations).
- Use a duck-typed resolver double following `RecordingResolver` in
  [test_validate_data.py](../../../src/tests/contracts/contracts/test_validate_data.py) —
  satisfies the protocol structurally, records its calls.
- **The handler must not import `crossclient`** and must not construct a resolver. It stays
  loadable and runnable with no platform connection
  ([ADR 0004](../../adrs/0004-submission-contracts-carry-extraction-instructions.md)).
- Keep it a thin delegation — the house style is `apply()`-style single calls. No helper
  functions, no curated messages beyond what task 05 requires.
- **Depends on:** task 01 (its assumption). **Blocks:** tasks 05, 06.
- **Verification:** `uv run pytest src/tests/submission/`
