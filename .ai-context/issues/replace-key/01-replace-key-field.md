# WP1 — `replace_key` field on `SubmissionContract`

## Context
**Source:** [sweet-cross/crosscontract#108](https://github.com/sweet-cross/crosscontract/issues/108) — no PRD; the shape
below was agreed in a design discussion that departs from the issue text (see
Implementation Details).

A Submission Contract can be shared by several teams, typically one per model. The
backend does not know which team a user belongs to, so the team has to be identified by
the data: `replace_key` names the target columns whose tuples identify a submitter's
slice, so a resubmission replaces exactly that slice. The replace itself is performed by
`cross_back`; this package only declares and validates the field. This task adds the
field and everything checkable without a resolver; WP2 adds the checks against the
target contracts.

## Acceptance Criteria
- [ ] `SubmissionContract.replace_key: list[str] | Literal["all"]` exists and is
      **required** — omitting it is a validation error.
- [ ] A list value round-trips through `model_validate` / `model_dump` and through
      `to_server()` / `from_server()`.
- [ ] `"all"` round-trips the same way and is the only accepted string value; a bare
      string such as `"model_id"` is rejected.
- [ ] An empty list is rejected.
- [ ] A list with duplicate column names is rejected, and the error names the
      duplicates.
- [ ] The `Attributes:` block in the `SubmissionContract` docstring documents the field,
      including what `"all"` means.
- [ ] Every existing fixture and example that builds a `SubmissionContract` is updated
      and the submission tests pass.

## Implementation Details
- Files to modify:
  - `src/crosscontract/submission/submission_contract.py` — the field and its validator.
  - `src/tests/submission/conftest.py` — the `contract()` fixture (line ~11).
  - `src/tests/submission/example_submission.yaml` — the round-tripping fixture.
  - `src/tests/submission/test_submission_contract.py` — new cases for the criteria
    above.
  - `.ai-context/prds/cross2025_submission.yaml` — the realistic campaign file, which
    `example_submission.yaml` points at as the non-minimal example.
  - Check `test_target_granularity.py`, `test_validate_targets.py`,
    `test_submitter.py`, `test_submission_handler.py` for further construction sites.
- **The agreed shape deviates from the issue.** The issue proposes
  `replace_key: list[str] | None = None`, with `None` meaning "replace everything this
  contract wrote". That was rejected: the most destructive setting must not be reachable
  by omission, and `[]` as the spelling for it is the same trap one level down (a falsy
  value that reads like "no key" to a human). Hence a required field with an explicit
  word:

  ```yaml
  replace_key: [model_id]   # replace the slice matching these tuples
  replace_key: all          # replace everything this contract wrote
  ```

  "Append-only, never replace" is deliberately not expressible — it is not a case the
  platform handles.
- Reject the empty list declaratively (`min_length=1` on the list member of the union)
  rather than in a validator; only the duplicate check needs a `field_validator`. Keep
  it plain — no helper function, no module constant.
- Names columns of the **target** contracts as they land in the target tables, not of
  the submission `tableschema`; extraction transformations may rename bundle columns.
  Nothing in this task resolves targets — that is WP2.
- Dependencies: none. Branch off `dev`.
- Breaking change to the Python API (callers must now pass the field). PR title
  `feat!: ...`. Nothing is deployed server-side, so no data migration is needed.
