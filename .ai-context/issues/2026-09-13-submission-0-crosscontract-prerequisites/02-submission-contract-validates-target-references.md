# WP2 — Reference validation of a Submission Contract checks its targets

## Context

**Part of PRD:** `.ai-context/prds/2026-09-13-submission-0-crosscontract-prerequisites.md` (Part B)

`SubmissionContract` inherits `validate_references`, which only walks foreign keys. A
bundle schema declares none, so the call passes for any Submission Contract even when its
targets name contracts that do not exist. The server needs this check when a Submission
Contract is created.

**Dependencies:** none (independent of WP1).
**Priority:** unblocks cross_back Step 1 and WP3.

## Acceptance Criteria

- [X] `SubmissionContract.validate_references(resolver, enforce_star_schema=True)`
  resolves every target's `contract` through `resolver.resolve`.
- [X] All targets resolve → returns `None`.
- [X] One or several unresolved targets → one `ValueError` listing each, naming target and
  contract, in the style of `BaseContract.validate_references`.
- [X] `enforce_star_schema` is accepted and has no effect; docstring says so.
- [X] The contract type a target resolves to is not checked.
- [X] Resolver exceptions propagate unchan sged.
- [X] `resolver.get_data` is never called.
- [X] Google-style docstring per CLAUDE.md.

## Implementation Details

- `src/crosscontract/submission/submission_contract.py` — the override. Iterate
  `self.extraction.targets`; collect failures; raise once.
- Out of scope: duplicate contracts across targets (already rejected at parse time),
  whether transformations produce the target's columns, Draft/Retired status.
- Tests: `src/tests/submission/test_submission_contract.py`, using the resolver helpers
  in `src/tests/submission/conftest.py` (`resolver_for` / `resolver_returning`): all
  resolve; one unresolved; several unresolved in one error; resolver raises; passing
  `enforce_star_schema` either way changes nothing; `get_data` not called.

## Verification

Ask before running: `uv run pytest src/tests/submission/test_submission_contract.py`,
then `uv run mypy src/crosscontract/`.
