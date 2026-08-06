# Forward `project_name` and `confirm_delete_all` through `ContractResource`

## Context
**Part of PRD:** [`2026-08-06-client-project-scoped-writes.md`](../../prds/2026-08-06-client-project-scoped-writes.md)

`ContractResource` is the handle end users actually hold, so the parameters added to
`ContractService` in task 01 are not reachable until they are exposed here. This task is
pure forwarding — no new logic, no project resolution, no validation.

## Acceptance Criteria

- [x] `ContractResource.add_data` accepts a **keyword-only** `project_name: str | None = None`
      and forwards it to `ContractService._add_data`.
- [x] `ContractResource.delete_data` accepts **keyword-only** `project_name: str | None = None`
      and `confirm_delete_all: bool = False`, forwarding both to
      `ContractService._delete_data`.
- [x] `filters` remains a **required positional** argument on `delete_data`.
- [x] The existing `Active`-status check in `delete_data` still runs **first**, ahead of
      the empty-filter check and ahead of `confirm_delete_all`.
- [x] The three pre-existing pinned delegation assertions are updated and pass.
- [x] A non-default value for each new parameter is pinned as reaching the service.
- [x] Docstrings updated in Google style per `CLAUDE.md`.

Keyword-only enforcement is left to mypy ("Too many positional arguments") rather than
runtime `TypeError` tests — those would assert CPython behaviour, not ours.

## Implementation Details

### File to modify
`src/crosscontract/crossclient/services/contract_resource.py`

### Target signatures

```python
def add_data(
    self,
    data: pd.DataFrame,
    validate: bool = True,
    *,
    project_name: str | None = None,
) -> None: ...

def delete_data(
    self,
    filters: "dict[str, FilterValue | list[FilterValue]]",
    *,
    project_name: str | None = None,
    confirm_delete_all: bool = False,
) -> None: ...
```

Both new parameters are keyword-only. This keeps call sites self-documenting on
destructive operations and leaves the existing positional signatures untouched.

### Behaviour that must not change

- `add_data` runs client-side schema validation before upload when `validate=True`.
  Validation is local and unaffected by project scope.
- `delete_data` raises its local `ValueError` when the cached status is not `"Active"`,
  **before** any request is issued. This check must stay ahead of `confirm_delete_all` —
  an unfiltered delete on a non-`Active` contract must not reach the platform.
- `drop_data()` is untouched. It targets `DELETE /contract/{name}/storage`, which takes
  no project parameter and drops the table across every project.

### Pinned assertions to update
These pin the exact delegation call and fail the moment a new argument is forwarded:

- `src/tests/crossclient/contracts/test_contract_resource.py:136` —
  `_add_data.assert_called_once_with(name, data)`
- `src/tests/crossclient/contracts/test_contract_resource.py:152` — same, validation variant
- `src/tests/crossclient/contracts/test_contract_resource.py:566` —
  `_delete_data.assert_called_once_with(resource.name, filters)`

### Tests to add
`src/tests/crossclient/contracts/test_contract_resource.py`, using the existing `Mock`
delegation pattern and `ModelFactory` contract builders. This layer decides three things
and only those are worth asserting here — the query-string behaviour belongs to the
service's own tests and must not be restated:

- The three pinned delegation assertions, updated for the new defaults.
- `add_data(df, project_name="p")` forwards the value. A default-valued assertion still
  passes if the parameter is accepted and then dropped, which mypy does not catch, so a
  non-default value is what actually pins the forwarding.
- `delete_data({}, project_name="p", confirm_delete_all=True)` forwards both, same
  reasoning.

Deliberately **not** added: a status-check test parametrised over `confirm_delete_all`.
The guard sits at the top of `delete_data` and does not reference the flag, so the
existing `test_delete_data_non_active_status_raises` already covers every value of it.

### Not tested here
Authorization outcomes (caller in multiple projects, unknown project, insufficient
rights) are platform behaviour reached through `raise_from_response`, which already has
coverage under `src/tests/crossclient/exceptions/`. The 403/404 responses map onto
`PermissionDeniedError` / `ResourceNotFoundError` and carry the platform's `detail`
message verbatim, so no new exception types or handling are needed.

### Dependencies
Must be completed after
[`01-service-layer-query-parameters.md`](01-service-layer-query-parameters.md) — the
service signatures it forwards to are defined there.

### Validation
Per `CLAUDE.md`, do **not** run these unprompted — ask first:

```bash
uv run pytest src/tests/crossclient/
```
