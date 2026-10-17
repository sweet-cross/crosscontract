# WP1 — Move the submission exceptions to `crossclient/exceptions/`

## Context
**Part of:** GitHub issue #122 (`CrossSubmitter.submit`) — WP1 of 5. No PRD; the approach
was agreed in a discuss-and-plan session.

Validation and upload of a submission move into the low-level client, which is the
centralized service layer (see WP2–WP4). The exceptions that validation raises move first,
so the handler can import them from its new home.

## Acceptance Criteria
- [ ] `TargetValidationError` and `UnclaimedRowsError` live in
      `src/crosscontract/crossclient/exceptions/` and are exported from
      `crosscontract.crossclient.exceptions`.
- [ ] `src/crosscontract/submission/exceptions.py` is removed.
- [ ] `from crosscontract import TargetValidationError, UnclaimedRowsError` and
      `from crosscontract.submission import TargetValidationError, UnclaimedRowsError` still
      work.
- [ ] The behaviour of both exceptions (`to_list`, `to_pandas`, messages) is unchanged.
- [ ] `src/tests/submission/test_exceptions.py` moves to
      `src/tests/crossclient/exceptions/` (e.g. `test_submission_exceptions.py`) and passes.

## Implementation Details
- Source: `src/crosscontract/submission/exceptions.py`.
- Target: a new module in `src/crosscontract/crossclient/exceptions/` (e.g.
  `submission_exceptions.py`), added to that package's `__init__.py` and `__all__`.
  They stay plain `Exception` subclasses — do not rebase them onto `CrossClientError`;
  that is a behaviour change and was not agreed.
- Update the imports in `src/crosscontract/submission/submission_handler.py`,
  `src/crosscontract/submission/submitter.py` and `src/crosscontract/submission/__init__.py`.
- `src/tests/submission/test_target_granularity.py` imports
  `crosscontract.submission.exceptions` directly; point it at the package-level
  re-export instead.
- Pure move: no renames, no new behaviour.
- Dependencies: none.
