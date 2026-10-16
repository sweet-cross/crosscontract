# WP1 — Package, models and `SubmissionContractResource`

## Context

**Part of PRD:** none — GitHub issue #121 (*SubmissionService and SubmissionContractResource
on CrossClient*), as refined in the planning session of 2026-10-16. That session changed the
issue in three places: no `get_list` (an `overview` instead), `create` re-fetches after the
POST, and the upload is out of scope.

The client half of the backend's `/api/v1/submission` endpoints needs a handle to a stored
submission contract, built the same way as `ContractResource`. This task creates the package,
the payload models mirroring the server's responses, and that handle. The service it delegates
to is WP2; here it is only referenced and is mocked in tests.

## Acceptance Criteria

- [X] `src/crosscontract/crossclient/services/submission/` exists as a package.
- [X] A private `_SubmissionContractEntryPayload` parses a `SubmissionContractEntryResponse`
  dict: `name`, `project_name`, `title`, `description`, `tags`, `allow_submissions`,
  `contract: dict[str, Any]`.
- [ ] A public `Submission` pydantic model mirrors `SubmissionResponse`: `uuid`,
  `submission_contract_name`, `project_name`, `submitted_by`, `original_filename`,
  `size`, `hash`, `state`, `created_at`.
- [X] `SubmissionState` is a `Literal["received", "processing", "current", "superseded", "rejected", "failed"]`.
- [X] `SubmissionContractResource.from_response(service, json)` builds the handle and parses
  `contract` into a `SubmissionContract`.
- [X] Read-only properties: `name`, `contract`, `project_name`, `allow_submissions`. Setting
  one raises `AttributeError`, as on `ContractResource`.
- [ ] Methods, each delegating to the service:
  - `set_allow_submissions(allow: bool) -> None` — calls the service, then updates the local
    flag.
  - `delete() -> None`.
  - `refresh() -> None` — re-`get`s and replaces contract, `project_name`, and
    `allow_submissions`.
  - `submissions() -> list[Submission]` — the submissions of this submission contract.
- [ ] The resource has no validate, submit, or upload method.
- [ ] Tests against a mocked service (pattern of
  `src/tests/crossclient/contracts/test_contract_resource.py`) cover: parsing a realistic
  response dict, read-only properties, `set_allow_submissions` updating the flag,
  `refresh` replacing state, and `delete` / `submissions()` delegating.

## Implementation Details

- New files:
  - `src/crosscontract/crossclient/services/submission/__init__.py`
  - `src/crosscontract/crossclient/services/submission/submission_resource.py` — the payload
    model and `SubmissionContractResource`.
  - `src/crosscontract/crossclient/services/submission/submission.py` (or alongside the
    resource) — `Submission` and `SubmissionState`.
  - `src/tests/crossclient/submission/__init__.py`,
    `src/tests/crossclient/submission/test_submission_resource.py`.
- Import `SubmissionContract` from `crosscontract.contracts.submission`. **Never** import from
  the top-level `crosscontract.submission` package — that imports `crossclient` and would be
  a cycle (ADR 0010).
- Reference `SubmissionService` only under `TYPE_CHECKING`, as `contract_resource.py` does
  with `ContractService`.
- Server shapes to mirror live in `cross_back`:
  `backend/app/schemas/submission_contract.py` (`SubmissionContractEntryResponse`) and
  `backend/app/schemas/submission.py` (`SubmissionResponse`, `SubmissionState`).
- Follow `contract_resource.py` for structure (`__init__` taking a parsed payload,
  `from_response`, the `__setattr__` read-only guard, `__repr__`). Google-style docstrings
  per CLAUDE.md.
- The service method names the resource calls are fixed in WP2: `set_allow_submissions(name, allow)`, `delete(name)`, `get(name)`, `get_submissions(name)`.
- Depends on: nothing.
