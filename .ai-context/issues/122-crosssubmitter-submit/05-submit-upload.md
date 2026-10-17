# WP5 — Upload: `_upload_submission`, `SubmissionContractResource.submit`, `CrossSubmitter.submit`

## Context

**Part of:** GitHub issue #122 (`CrossSubmitter.submit`) — WP5 of 6.

The actual feature of #122: submit a bundle that has been validated locally, so errors
surface before upload rather than as a rejected submission.

## Signatures

```python
# SubmissionContractService
def _upload_submission(
    self, name: str, file: bytes | BinaryIO, filename: str
) -> Submission: ...

# SubmissionContractResource
def submit(
    self,
    df: pd.DataFrame,
    filename: str | None = None,
    validate: bool = True,
) -> Submission: ...

# CrossSubmitter
def submit(
    self,
    name: str,
    df: pd.DataFrame,
    filename: str | None = None,
    validate: bool = True,
) -> Submission: ...
```

- `filename` is the **stem** of the uploaded file; `.parquet` is appended. `None` means
  the submission contract's name, i.e. `f"{self.name}.parquet"`.
- `validate` switches the whole local validation on or off. `submit` runs
  `validate_submission` with its defaults (every check on); there are no per-check flags.
  For fine-grained checking — e.g. a corrected resubmission under the same `replace_key`,
  whose keys collide with the stored ones — call `validate_submission` with the flags
  needed, then `submit(..., validate=False)`.
- No `project_name`: it is part of the submission contract.

## Acceptance Criteria

- [X] `SubmissionContractService._upload_submission(name, file, filename)` (private)
  sends the file unchanged as one file part to `POST {route}/contract/{name}/data` (no
  explicit content type; the platform checks the filename extension and rejects
  unsupported formats), goes through `raise_from_response`, and returns a `Submission`.
  `submit_file` (#119) can reuse it.
- [ ] `SubmissionContractResource.submit` serializes the delivered frame to **parquet**
  and uploads it as `f"{filename or self.name}.parquet"`.
- [ ] With `validate=True` (default) it runs `self.validate_submission(df)` first and
  uploads only if it passes. No request is sent if any validation step fails. With
  `validate=False` it uploads without validating.
- [ ] The **original** bundle (as passed in) is uploaded, never the coerced frame returned
  by validation.
- [ ] It returns the `Submission` (state `received` on success).
- [ ] `CrossSubmitter.submit(name, df, filename=None, validate=True)` replaces the
  `NotImplementedError` stub and returns
  `self._client.submissions.get(name).submit(df, filename=filename, validate=validate)`.
- [ ] Docstrings state that validation is advisory (the platform re-validates on ingest),
  that processing is asynchronous (follow the state via `get_submission`), and how to
  check with custom flags (`validate_submission`, then `validate=False`).
- [ ] Mocked-HTTP tests, following `src/tests/crossclient/submission/test_submission_service.py`:
  no request on a failed validation step; body is parquet built from the delivered
  frame; a `Submission` comes back.

## Implementation Details

- Files: `src/crosscontract/crossclient/services/submission/submission_service.py`,
  `.../submission_resource.py`, `src/crosscontract/submission/submitter.py`. The
  resource's `submit` calls its own `validate_submission`, which delegates to
  `handlers/submission/`.
- Look at `ContractService._add_data` in
  `src/crosscontract/crossclient/services/contract/contract_service.py` for how parquet
  is written and posted today. Unlike `_add_data`, serialization lives in the resource,
  not the service.
- Out of scope: `submit_file` (#119), waiting for processing to finish.
- Dependencies: after `04-validate-submission-on-resource.md`.
