# WP2 — `SubmissionService` and wiring into `CrossClient`

## Context
**Part of PRD:** none — GitHub issue #121, as refined in the planning session of 2026-10-16
(see `01-models-and-submission-contract-resource.md`).

The low-level service wrapping the backend's `/api/v1/submission` endpoints, built the same
way as `ContractService` but without any data methods (`_add_data`-style upload is out of
scope). It produces the `SubmissionContractResource` from WP1 and is exposed as
`client.submissions`.

## Acceptance Criteria
- [ ] `SubmissionService(client)` with these methods, all checking responses via
      `raise_from_response`:

  | Method | Endpoint | Returns |
  |---|---|---|
  | `create(contract: SubmissionContract)` | `POST /submission/contract`, then `GET /submission/contract/{name}` | `SubmissionContractResource` built from the GET response |
  | `get(name)` | `GET /submission/contract/{name}` | `SubmissionContractResource` |
  | `overview(project_name)` | `GET /submission/contract?project_name=…` | `pd.DataFrame` of the page's `items` |
  | `delete(name)` | `DELETE /submission/contract/{name}` | `None` |
  | `set_allow_submissions(name, allow)` | `PUT /submission/contract/{name}/allow-submissions` with body `{"allow_submissions": allow}` | `None` |
  | `get_submission(uuid)` | `GET /submission/{uuid}` | `Submission` |
  | `get_submissions(name)` | `GET /submission/contract/{name}/data` | `list[Submission]` from the page's `items` |

- [ ] `overview` and `get_submissions` send no `limit` (the server then returns every
      remaining item) and read `items` from the `Page` envelope.
- [ ] `CrossClient` exposes `self.submissions: SubmissionService`.
- [ ] `SubmissionService`, `SubmissionContractResource`, and `Submission` are exported from
      `crossclient/services/__init__.py` and `crossclient/__init__.py`.
- [ ] Mocked-HTTP tests (respx, pattern of
      `src/tests/crossclient/contracts/test_contracts_service.py`) cover:
  - `create` issues the POST and then the GET, and the resource reflects the GET body.
  - `overview` sends `project_name` and no `limit`; DataFrame columns match the metadata.
  - `get_submission` / `get_submissions` return `Submission` objects with the right `state`.
  - `set_allow_submissions` sends exactly `{"allow_submissions": <bool>}`.
  - A 404 and a 403 raise the mapped client exceptions.
  - `client.submissions` is a `SubmissionService`.

## Implementation Details
- New files:
  - `src/crosscontract/crossclient/services/submission/submission_service.py`
  - `src/tests/crossclient/submission/test_submission_service.py`
- Modify:
  - `src/crosscontract/crossclient/services/submission/__init__.py`
  - `src/crosscontract/crossclient/services/__init__.py`
  - `src/crosscontract/crossclient/__init__.py`
  - `src/crosscontract/crossclient/crossclient.py` — add `self.submissions` next to
    `self.contracts` (line ~54).
  - `src/tests/crossclient/conftest.py` — a `submission_service` fixture if useful.
- Route base: `f"{client._base_url}/api/v1/submission/"`, mirroring `ContractService._route`.
- `create` sends `contract.model_dump(mode="json")` as the body; the POST response is a
  `SubmissionContractMetaDataResponse` without `contract`, which is why the GET follows.
- Server routes to mirror: `cross_back/backend/app/api/routes/submission_contract.py` and
  `cross_back/backend/app/api/routes/submission.py`; paging envelope in
  `cross_back/backend/app/schemas/page.py`.
- No upload method, public or private, in this task.
- Depends on: `01-models-and-submission-contract-resource.md`.
