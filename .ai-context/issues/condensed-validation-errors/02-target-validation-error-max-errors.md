# Pass `max_errors` through `TargetValidationError`

## Context
**Part of PRD:** none. Agreed in a discuss-and-plan session on 2026-09-25.

`TargetValidationError` flattens the per-target `SchemaValidationError` reports, so it
needs the same opt-in bound as its parts. Same PR as
`01-schema-validation-error-max-errors.md`.

## Acceptance Criteria
- [ ] `TargetValidationError.to_list(max_errors: int | None = None)` and
      `to_pandas(max_errors: int | None = None)` exist.
- [ ] `to_list(max_errors)` calls each failing target's `to_list(max_errors)` and adds
      the `target` key as today; it condenses nothing itself. The limit therefore
      applies per target.
- [ ] `max_errors=None` returns exactly today's output.
- [ ] `to_pandas(max_errors)` returns `pd.DataFrame(self.to_list(max_errors))`.
- [ ] Docstrings (Google style, markdown only) state that `max_errors` is passed to
      each target's report, so the limit holds per target.
- [ ] Tests (see below) pass.

## Implementation Details
- Modify `src/crosscontract/submission/exceptions.py` (`TargetValidationError` only;
  `UnclaimedRowsError` is untouched).
- Tests in `src/tests/submission/test_exceptions.py`:
  - two failing targets, each with more distinct failing values than `max_errors`
    in the same column and check: each target keeps `max_errors` rows, each row
    carries `target` and `count`;
  - default output unchanged;
  - `to_pandas(max_errors)` matches `to_list(max_errors)`.
- Dependencies: must be completed after `01-schema-validation-error-max-errors.md`.
- PR: both tasks ship in one PR to `dev`, titled as a conventional commit, e.g.
  `feat: condense validation error reports with max_errors`.
- Follow-up outside this repo (not part of this PR): once released from `main`,
  cross_back replaces `_condense_schema_errors` with `e.to_list(max_errors=10)` in
  `validate_bundle`, and decides whether `contract_data.py` does the same.
