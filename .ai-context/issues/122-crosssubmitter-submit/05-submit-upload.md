# WP5 — Upload: `_submit_data`, `SubmissionContractResource.submit`, `CrossSubmitter.submit`

## Context
**Part of:** GitHub issue #122 (`CrossSubmitter.submit`) — WP5 of 6.

The actual feature of #122: submit a bundle that has been validated locally, so errors
surface before upload rather than as a rejected submission.

## Acceptance Criteria
- [ ] `SubmissionContractService._submit_data(name, df)` (private) sends
      `POST {route}/contract/{name}/data` with the bundle serialized as **parquet**, goes
      through `raise_from_response`, and returns a `Submission`.
- [ ] `SubmissionContractResource.submit(df, ...)` runs `validate_submission` first and
      uploads only if it passes. No request is sent if any validation step fails.
- [ ] The **original** bundle (as passed in) is uploaded, never the coerced frame returned
      by validation.
- [ ] It returns the `Submission` (state `received` on success).
- [ ] `CrossSubmitter.submit(name, df, ...)` replaces the `NotImplementedError` stub and
      returns `self._client.submissions.get(name).submit(...)`.
- [ ] Docstrings state that validation is advisory (the platform re-validates on ingest)
      and processing is asynchronous (follow the state via `get_submission`).
- [ ] Mocked-HTTP tests, following `src/tests/crossclient/submission/test_submission_service.py`:
      no request on a failed validation step; body is parquet built from the delivered
      frame; a `Submission` comes back.

## Implementation Details
- Files: `src/crosscontract/crossclient/services/submission/submission_service.py`,
  `.../submission_resource.py`, `src/crosscontract/submission/submitter.py`. The
  resource's `submit` calls its own `validate_submission`, which delegates to
  `handlers/submission/`.
- Look at `ContractService._add_data` / `_get_data` in
  `src/crosscontract/crossclient/services/contract/contract_service.py` for how files and
  parquet are handled today; match it.
- Open, decide while implementing:
  - Whether `submit` gets a `validate: bool = True` opt-out like `ContractResource.add_data`
    (leaning yes). If added, "no upload on failure" only holds when `validate=True`.
  - Whether the endpoint accepts a `project_name` (as `add_data` does); check the backend
    API before adding a parameter.
- `submit` passes through the same check flags as `validate_submission`.
- Out of scope: `submit_file` (#119), waiting for processing to finish.
- Dependencies: after `04-validate-submission-on-resource.md`.
