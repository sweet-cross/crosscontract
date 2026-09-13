# WP3 — The submitter checks target references before touching data

## Context
**Part of PRD:** `.ai-context/prds/2026-09-13-submission-0-crosscontract-prerequisites.md` (open question 3, resolved)

Today a target naming a missing contract surfaces as a `ValueError` midway through target
validation. Running reference validation first makes a broken Submission Contract fail as
a wiring error before any bundle data is read.

**Dependencies:** WP2 (the override). Lands after WP1, which edits the same docstring.
**Priority:** last; small. Closes the single PR (`feat:`) for both parts.

## Acceptance Criteria
- [ ] `CrossSubmitter.validate_submission` calls
      `contract.validate_references(self._resolver)` before step 1 (bundle schema).
- [ ] An unresolved target raises `ValueError` without the bundle being validated or
      extracted.
- [ ] Docstring lists the new first step and its `Raises:` entry reflects it.
- [ ] Existing submitter tests still pass; resolver mocks that do not resolve every
      target are adjusted.

## Implementation Details
- `src/crosscontract/submission/submitter.py` — one call at the top of
  `validate_submission`; update the "Runs three steps" docstring.
- Tests: the submitter's test module under `src/tests/submission/` — an unresolved target
  fails before `SubmissionHandler` is used (e.g. bundle that would fail step 1 still
  reports the reference error).

## Verification
Ask before running: `uv run pytest src/tests/submission/`, then the full suite, `mypy`
and `ruff` before opening the PR.
