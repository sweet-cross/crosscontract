# Add `project_name` and `confirm_delete_all` to `ContractService` data methods

## Context
**Part of PRD:** [`2026-08-06-client-project-scoped-writes.md`](../../prds/2026-08-06-client-project-scoped-writes.md)

The CROSS platform now scopes data writes and deletes to a **project**, named by an
optional `project_name` query parameter, and gates unfiltered deletes behind a
`delete_all` query parameter. This task adds both to the client's transport layer.

This is the **critical path**: tasks 02 and 03 are pure pass-through and documentation on
top of the wire format established here.

## Acceptance Criteria

- [ ] `ContractService._add_data` accepts `project_name: str | None = None` and sends it
      as a **query** parameter on the POST.
- [ ] `ContractService._delete_data` accepts `project_name: str | None = None` and
      `confirm_delete_all: bool = False`.
- [ ] `project_name` is absent from the query string when `None`, and **present** when
      `""` — the guard is `if project_name is not None`, never a truthiness test.
- [ ] `confirm_delete_all=True` is sent as the query key **`delete_all`**;
      `confirm_delete_all=False` sends nothing.
- [ ] Empty `filters` raises `ValueError` only when `confirm_delete_all` is `False`;
      with `confirm_delete_all=True` the request is issued.
- [ ] The `ValueError` message names `confirm_delete_all=True` and no longer directs
      users to `drop_data()`.
- [ ] Docstrings updated in Google style per `CLAUDE.md` (they generate the API
      reference via mkdocstrings). No ADR/PRD/task references in docstrings — those are
      user-facing.
- [ ] New tests in `src/tests/crossclient/contracts/test_contracts_service.py` pass, and
      pre-existing `_delete_data` / `_add_data` tests still pass.

## Implementation Details

### File to modify
`src/crosscontract/crossclient/services/contract_service.py`

### Target signatures

```python
def _add_data(
    self,
    name: str,
    data: pd.DataFrame,
    project_name: str | None = None,
) -> None: ...

def _delete_data(
    self,
    name: str,
    filters: dict[str, FilterValue | list[FilterValue]],
    project_name: str | None = None,
    confirm_delete_all: bool = False,
) -> None: ...
```

### `_add_data`

The method currently passes only `files=` to `self._client.post` and no `params` at all —
the `params` argument is new. The platform declares `project_name` as a bare scalar
alongside `File(...)`, so FastAPI reads it from the **query string**. Putting it into the
multipart body means it is silently ignored and the platform falls back to inferring the
project from the caller's memberships — a wrong-project write with no error. Build the
params dict outside the `with io.BytesIO()` block and pass it alongside `files`.

### `_delete_data`

Merge both parameters into the existing `params` dict built from `filters`. This is the
**single place** where `confirm_delete_all` maps onto the platform's `delete_all` key —
keep the mapping here so no rename happens at the resource → service boundary.

Relax the existing guard:

```python
if not filters and not confirm_delete_all:
    raise ValueError(...)  # message must name confirm_delete_all=True
```

The current message ("Use drop_data() to delete all data associated with a contract") is
now actively wrong and must be replaced: `drop_data()` drops the whole storage table
across **every** project and requires the contract to be `Retired`, whereas
`confirm_delete_all` clears only the caller's project rows and requires `Active`.

### Why the empty-filter rule is mirrored client-side

It duplicates a rule the platform also enforces, which is deliberate and differs from
duplicating a platform *constant*: the rule appears in the platform's own 400 response,
so both sides enforce one rule rather than two that can drift, and the client check saves
a round trip on an obvious mistake. Note the deliberate **absence** of any client-side
guard on filter keys that shadow reserved query parameters — see the PRD's rejected
alternatives before adding one.

### Tests to add
`src/tests/crossclient/contracts/test_contracts_service.py`, following the existing
`respx` patterns and asserting on `respx.calls.last.request.url`:

- `_add_data` with `project_name` set → parameter present in the query string.
- `_add_data` with `project_name=None` → parameter **absent**.
- `_add_data` with `project_name` set → parameter in the URL and **not** in the multipart
  body.
- `_delete_data` with `project_name` set → present alongside the filter parameters.
- `_delete_data` with `project_name=None` → absent.
- `_delete_data` with `project_name=""` → **present and empty**. This test fails if the
  omission check is written as a truthiness test.
- `_delete_data({}, confirm_delete_all=True)` → request issued and the query string
  carries **`delete_all`**, not `confirm_delete_all`. Fails if the client parameter name
  leaks onto the wire.
- `_delete_data({}, confirm_delete_all=False)` → `ValueError` and **no request issued**;
  assert `respx.calls` is empty, not merely that the exception raised.
- `_delete_data({"region": "DE"})` → `delete_all` absent from the query string.
- `_delete_data({"region": "DE"}, confirm_delete_all=True)` → both filters and flag
  present; the platform applies the filters and ignores the flag.

Existing `_delete_data` tests (list-value repetition, stringification, server error,
empty-filter raise) stay as they are — except that the empty-filter test's message
assertion needs updating if it asserts on message content.

### Dependencies
None. This task is first.

### Validation
Per `CLAUDE.md`, do **not** run these unprompted — ask first:

```bash
uv run pytest src/tests/crossclient/contracts/test_contracts_service.py
```
