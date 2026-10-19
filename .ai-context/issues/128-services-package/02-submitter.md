# Move `submission/` to `services/submitter/`

## Context
**Part of PRD:** none. Source is GitHub issue #128 and the agreed design discussion.

`crosscontract.submission` holds only `CrossSubmitter` plus a re-export shim. Calling the new folder `submitter` (after its class) reduces the packages named `submission` from four to three. The shim is dropped.

## Acceptance Criteria
- [ ] `src/crosscontract/submission/` no longer exists; `submitter.py` lives in `src/crosscontract/services/submitter/`.
- [ ] `services/submitter/__init__.py` exports only `CrossSubmitter`.
- [ ] The root `crosscontract` still exports `CrossSubmitter`, `Submission`, `SubmissionContract`, `SubmissionHandler`, `TargetValidationError`, `UnclaimedRowsError`, now imported from their home packages (`contracts.submission`, `crossclient`, `handlers`, `exceptions`).
- [ ] No code or test imports `crosscontract.submission`.

## Implementation Details
- `git mv src/crosscontract/submission/submitter.py src/crosscontract/services/submitter/submitter.py`, then delete the old package.
- Tests: move `src/tests/submission/test_submitter.py` to `src/tests/services/submitter/`. In its `TestPublicSurface`:
  - `test_exported_from_both_paths` and `test_listed_in_all` point at `crosscontract.services.submitter` instead of `crosscontract.submission`;
  - `test_reexports_handler_and_readers` is removed, because the shim is gone.
- `src/tests/exceptions/test_submission_exceptions.py:91` (`test_exported_from_both_paths`) imports from `crosscontract.submission`; point it at the root `crosscontract` or remove it.
- Depends on: nothing (can run alongside 01).
