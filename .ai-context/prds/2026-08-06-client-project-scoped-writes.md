# Project-Scoped Data Writes in `crossclient` PRD

## 1. Overview

The CROSS platform has introduced **projects**: data rows are owned by a project, and a
caller acts *on behalf of* one project when writing or deleting data. The platform's
data endpoints now accept an optional `project_name` query parameter to name that
project, and the delete endpoint additionally accepts a `delete_all` flag that
authorises an unfiltered delete.

`crossclient` — currently the only write path to the platform — cannot express either.
This PRD covers extending the client's data-write and data-delete methods so that a
caller who belongs to more than one project can say which one they are acting for, and
so that a caller can clear their project's slice of a contract without decommissioning
the contract entirely.

**Audience:** data providers using `CrossClient` / `ContractResource` to submit and
remove data, particularly those who belong to more than one project.

**Non-goals:** project management (creating, listing, joining projects), project-scoped
reads, and any client-side resolution or validation of project names. The platform
remains the sole authority on which project a caller may act under.

## 2. Core Requirements

### R1 — `project_name` on the write path

`ContractService._add_data` and `ContractResource.add_data` accept an optional
`project_name: str | None = None`, forwarded to the platform as a **query** parameter
on `POST /api/v1/contract/{name}/data`.

### R2 — `project_name` on the delete path

`ContractService._delete_data` and `ContractResource.delete_data` accept the same
optional parameter, forwarded as a query parameter on
`DELETE /api/v1/contract/{name}/data`.

### R3 — Omission semantics

When `project_name` is `None`, the parameter is **absent from the query string**
entirely. It is never sent as an empty value or as the string `"None"`. Omission is what
tells the platform to infer the project from the caller's memberships.

### R4 — `confirm_delete_all` on the delete path

`ContractService._delete_data` and `ContractResource.delete_data` accept
`confirm_delete_all: bool = False`. When `True` **and** `filters` is empty it is
forwarded as the query parameter `delete_all`; otherwise it is omitted. The flag governs
the empty-filter case only, so a filtered delete never carries it (E8).

The client parameter is deliberately named for the ceremony it performs, so the call
site reads as a deliberate act rather than a configuration value. The platform declares
the parameter as `delete_all`, so the two names differ and the mapping happens in exactly
one place: where `_delete_data` assembles its query parameters. Both client methods use
`confirm_delete_all`, so the client's own vocabulary stays internally consistent and no
rename occurs at the resource → service boundary.

### R5 — Empty filters require explicit intent

`delete_data(filters)` keeps `filters` as a **required positional** argument. An empty
`filters` mapping raises `ValueError` **unless** `confirm_delete_all=True` is also
passed. This preserves today's guarantee that a filter mapping which collapsed to empty
through a bug cannot trigger a wipe.

### R6 — Corrected guidance on the empty-filter error

The current `ValueError` message directs users to `drop_data()`. That advice is now
wrong: `drop_data()` drops the whole storage table across every project and requires the
contract to be `Retired`, whereas the newly reachable operation clears only the caller's
project rows and requires `Active`. The message must be rewritten to name
`confirm_delete_all=True`.

### R7 — No client-side project logic

The client performs no project resolution, membership lookup, name validation, or
caching. `project_name` is an opaque pass-through string. No client-level default
project is introduced.

### R8 — Documentation

The deleting-data section of `docs/client/index.md` distinguishes all three removal
operations and their project scope. The generated API reference picks up the new
parameters from the docstrings.

### Definition of done

- All four methods accept the new parameters with the omission semantics of R3/R4.
- `uv run pytest` passes, including updated pinned-delegation assertions and new
  query-string coverage.
- `uv run ruff check src/`, `uv run ruff format src/`, and
  `uv run mypy src/crosscontract/` are clean.
- `docs/client/index.md` documents the three removal operations and when `project_name`
  is required.

## 3. Edge Cases & Error Handling

### Parameter encoding

| # | Case | Required behaviour |
|---|---|---|
| E1 | `project_name=None` | Parameter omitted from the query string. Building `params["project_name"] = None` would make httpx send the literal string `None`; the platform would then resolve a project named `"None"` and return 404. |
| E2 | `project_name=""` | **Sent** as an empty value, not omitted. The guard must be `if project_name is not None`, never a truthiness test — a truthiness test would silently convert an empty string into "infer the project", which can land the write in the wrong project. An empty name reaches the platform and is rejected there as a missing project (404). |
| E3 | `project_name` on `POST` | Must be a **query** parameter. `post_data_for_contract` declares it as a bare scalar alongside `File(...)`, so FastAPI reads it from the query string. Placing it in the multipart body means it is silently ignored and the platform falls back to inference — a wrong-project write with no error. `_add_data` currently passes no `params` at all, so this argument is new. |
| E4 | `confirm_delete_all=False` | Omitted from the query string. |
| E5 | `confirm_delete_all=True`, `filters` empty | Sent as `delete_all`, the platform's name for it. Value serialisation must be one the platform's bool parser accepts. |

### Filter and delete semantics

| # | Case | Required behaviour |
|---|---|---|
| E6 | `delete_data({})` | `ValueError` raised client-side before any request. Message names `confirm_delete_all=True`, not `drop_data()`. |
| E7 | `delete_data({}, confirm_delete_all=True)` | Request issued; every row the resolved project owns under the contract is removed. Table and contract survive. |
| E8 | `delete_data({"year": 2020}, confirm_delete_all=True)` | **Filters win, enforced client-side.** The combination is not rejected — the filters are sent and `delete_all` is dropped, so only matching rows are removed. The flag governs the empty-filter case only, and suppressing it means the scope of the deletion does not depend on how the platform prioritises the two. The blast radius of guessing that precedence wrong is every row the project owns, which is why the guarantee is made locally rather than assumed of the platform. |
| E9 | `delete_data()` with no arguments | `TypeError` — `filters` stays required positional. |
| E10 | Filter key shadows a reserved query parameter (`project_name`, `delete_all`, `limit`, `offset`, `format`, `columns`, `unique`) | **Accepted, unguarded.** The platform strips these from the filter set, so such a column is unreachable through this endpoint regardless of what the client does. In practice a value that is not also a real project name produces a fast 404. See §4 "Rejected alternatives" for why no client-side guard is added. |

### Authorization and platform-side failures

All of these already map onto existing client exceptions through
`exception_factory.py`, which carries the platform's `detail` message through verbatim.
**No new exception types or handling are required** — they are listed to confirm the
surface is adequate.

| # | Case | Platform response | Client exception |
|---|---|---|---|
| E11 | Caller belongs to multiple projects, `project_name` omitted | 403, *"Caller belongs to multiple projects. Please specify the project name."* | `PermissionDeniedError` |
| E12 | Caller belongs to no project, `project_name` omitted | 403, *"Caller belongs to no project and cannot act on project data."* | `PermissionDeniedError` |
| E13 | Service caller (holds no memberships), `project_name` omitted | 403 as E12 — service callers can only resolve a project by naming one | `PermissionDeniedError` |
| E14 | `project_name` names a non-existent project | 404 | `ResourceNotFoundError` |
| E15 | Caller lacks write/delete rights in the named project | 403 | `PermissionDeniedError` |
| E16 | Contract not `Active` on the platform | 409 | `ConflictError` |

E11 is the principal new failure mode and is self-explanatory to the user because the
platform's message names the remedy.

### Interaction with existing client behaviour

| # | Case | Required behaviour |
|---|---|---|
| E17 | `delete_data` on a non-`Active` cached status | The existing local status check fires **first**, before the empty-filter check and before any request — unchanged by this work, and it must stay ahead of `confirm_delete_all`. |
| E18 | `add_data(validate=True)` | Client-side schema validation is local and unaffected by project scope. It runs before the upload, as today. |
| E19 | `drop_data()` / `ContractService._drop_data_table` | Unchanged. `DELETE /contract/{name}/storage` takes no project parameter. |
| E20 | `ContractService.delete(hard=True)` | Unchanged — it composes `change_status` and `_drop_data_table`, neither of which is project-scoped. |
| E21 | `CrossRegistry` and `release/data_package` | Unchanged. Both are read-only paths. |

### Known asymmetry (documented, not fixed here)

`ContractResource.get_primary_key_values()` and `get_foreign_key_values()` read through
`_get_data`, and the platform scopes reads to **every** project the caller may read
(`DataAccessChecker.get_read_filter()`). A write, by contrast, lands in exactly **one**
project. So opt-in primary-key validation compares new rows against key values drawn
from a potentially wider set of projects than the one being written to.

This is plausibly the correct behaviour — primary-key uniqueness is arguably a
contract-level property, not a per-project one — but the asymmetry is not currently
documented anywhere. Recording it here; no change proposed. If it turns out to be
wrong it is a platform-side question about whether reads should be project-scoped, not a
client fix.

## 4. Implementation Decisions & File Paths

### Approach

A thin pass-through. The client gains no state, no inference, and no knowledge of the
project model beyond forwarding a string. This mirrors how `ContractService` already
treats `contract_type` and `columns`: assemble query parameters, let the platform decide.

The one piece of platform logic the client does mirror is R5's empty-filter rule. That
is deliberate and differs in kind from mirroring a constant: the rule is stated in the
platform's own 400 response, so both sides enforce one rule rather than two that can
drift, and the client's copy saves a round trip on an obvious mistake. The check already
exists today — only its condition and message change.

### Files to be modified

**`src/crosscontract/crossclient/services/contract_service.py`**

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

- `_add_data` gains a `params` argument on the POST — it currently sends only `files`.
  The parameter must not enter the multipart body (E3).
- `_delete_data` merges the two new parameters into the existing `params` dict built
  from `filters`, applying the omission rules of E1/E4. This is the single place where
  `confirm_delete_all` is mapped onto the platform's `delete_all` key (R4).
- The empty-filter guard becomes `if not filters and not confirm_delete_all`, with the
  message rewritten per R6.

**`src/crosscontract/crossclient/services/contract_resource.py`**

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

Both new parameters are **keyword-only**, keeping call sites self-documenting on
destructive operations and leaving the existing positional signatures untouched. The
methods forward; the local `Active`-status check in `delete_data` stays ahead of
everything (E17).

**`src/tests/crossclient/contracts/test_contracts_service.py`** — new query-string
coverage (§7).

**`src/tests/crossclient/contracts/test_contract_resource.py`** — three pinned
delegation assertions need the new arguments (lines 136, 152, 566), plus new coverage.

**`docs/client/index.md`** — the deleting-data table gains a row and a project-scope
column; new prose and example for the unfiltered form; a note on when `project_name` is
needed.

**`docs/notebooks/client_tutorial.ipynb`** — a short markdown note only. Code cells stay
as they are: the parameter is optional and the tutorial's single-project flow remains
correct.

**`.ai-context/CONTEXT.md`** — **done.** The ubiquitous-language file had no entry for
**project**, yet this change puts the term into the client's public signature. A
definition has been added under "The platform and its access layers", recording that a
contract itself belongs to no project — only the rows stored under it do — and that
reads are not narrowed the way writes are.

### Files to be created

None.

### Rejected alternatives

**A client-side reserved-key guard on `filters` (E10).** Rejected: it requires copying
the platform's `IGNORE_FILTER_KEYS` list, which the platform does not expose, creating a
standing obligation to synchronise on every platform change. The platform already
rejects the realistic collision quickly, since a column value that is not also a real
project name yields a 404.

**A separate `clear_data()` method for the unfiltered delete.** Rejected as too much
public surface for the benefit. It would have kept `filters` required and made the
incoherent combination unrepresentable, but R5 achieves the safety property with one
method.

**Empty `filters` as the signal for an unfiltered delete** (no flag). Rejected: `{}` is
exactly the value a bug produces — a comprehension over user input where everything
filters out — so intent and malfunction would be indistinguishable at the call site.
`confirm_delete_all=True` cannot arise accidentally.

**Naming the client flag `delete_all`** to match the platform 1:1. Rejected in favour of
`confirm_delete_all`, which reads at the call site as an act of confirmation rather than
a setting. The cost is one name mapping at the transport boundary (R4), which is
contained to a single line.

**A default project on `CrossClient`.** Rejected for now. It would duplicate the
platform's inference logic client-side and let a stale default silently retarget a
destructive operation. The per-call form is strictly additive, so a default can be
layered on later if repetition proves tedious.

## 5. Data & Schema Changes

No database, Pydantic model, or data-pipeline changes. `_ContractEntryPayload` and the
`CrossContract` / `TableSchema` models are untouched; this affects request construction
only.

### Wire contract — `POST /api/v1/contract/{contract_name}/data`

| Element | Value |
|---|---|
| Body | multipart `file`, parquet — unchanged |
| Query | `project_name` (string, optional, omitted when `None`) |
| Success | 200 |
| Errors | 400, 403, 404, 409, 422 |

### Wire contract — `DELETE /api/v1/contract/{contract_name}/data`

| Element | Value |
|---|---|
| Query | filter columns (repeated for multi-value) — unchanged |
| Query | `project_name` (string, optional, omitted when `None`) |
| Query | `delete_all` (bool, optional, omitted when `False`) — the client's `confirm_delete_all` |
| Success | 200, body `{"detail": "Deleted N rows"}` |
| Errors | 400 (no filters and no `delete_all`), 403, 404, 409 |

The `{"detail": ...}` response body is discarded by the client today, and this PRD does
not change that. Returning the deleted row count is a plausible future improvement but
would change the return type of a public method, so it stays out.

## 6. Related ADRs

Scanned `.ai-context/adrs/`:

- **0001 — Dimensions are strict trees.** Not applicable. Touches no dimension logic.
- **0002 — Metadata follows Frictionless with deviations.** Not applicable. Adds no
  metadata to contracts or descriptors; `project_name` is a request parameter, never
  persisted on a contract.
- **0003 — Release is a contract-to-Frictionless adapter.** Not applicable. The release
  path is read-only and unaffected (E21).

**No new ADR is warranted.** The decisions here are local to the client's request
construction and are reversible; the rejected alternatives in §4 record the reasoning
adequately. The one architecturally-shaped decision — no client-side project state or
inference (R7) — merely preserves the existing property that the client is a thin
transport over platform authority, rather than establishing anything new.

## 7. Testing Strategy

Existing tests use `respx` to mock HTTP and `unittest.mock.Mock` for delegation, with
`ModelFactory` builders for contracts. All new tests follow those patterns; no new
fixtures or dependencies.

### Service layer — `src/tests/crossclient/contracts/test_contracts_service.py`

Query-string assertions on `respx.calls.last.request.url`:

- `_add_data` with `project_name` set → the parameter appears in the query string.
- `_add_data` with `project_name=None` → the parameter is **absent**. Guards E1.
- `_add_data` with `project_name` set → the parameter is in the URL and **not** in the
  multipart body. Guards E3, the silent wrong-project failure.
- `_delete_data` with `project_name` set → present alongside the filter parameters.
- `_delete_data` with `project_name=None` → absent; existing filter behaviour unchanged.
- `_delete_data` with `project_name=""` → **present** and empty. Guards E2 — this test
  fails if the omission check is written as a truthiness test.
- `_delete_data({}, confirm_delete_all=True)` → request issued, and the query string
  carries **`delete_all`**, not `confirm_delete_all`. Guards the R4 name mapping — this
  is the test that fails if the client parameter name leaks onto the wire.
- `_delete_data({}, confirm_delete_all=False)` → `ValueError`; **no request issued**.
  Assert `respx.calls` is empty, not merely that the exception raised.
- `_delete_data({"region": "DE"})` → `delete_all` absent from the query string.
- `_delete_data({"region": "DE"}, confirm_delete_all=True)` → filters present,
  `delete_all` **absent** (E8). This is the test that fails if the client ever starts
  delegating the filters-vs-flag precedence to the platform.

Existing `_delete_data` tests (list-value repetition, stringification, server error,
empty-filter raise) stay as they are, except that the empty-filter test's message
assertion tracks R6 if it asserts on message content.

### Resource layer — `src/tests/crossclient/contracts/test_contract_resource.py`

Pinned assertions to update — these fail as soon as the methods forward a new argument:

- line 136 — `_add_data.assert_called_once_with(name, data)`
- line 152 — same, validation variant
- line 566 — `_delete_data.assert_called_once_with(resource.name, filters)`

New delegation coverage:

- `add_data(df, project_name="p")` forwards the value to `_add_data`.
- `add_data(df)` forwards `None`.
- `delete_data(filters, project_name="p")` forwards the value.
- `delete_data({}, confirm_delete_all=True)` on an `Active` contract forwards both.
- `delete_data({}, confirm_delete_all=True)` on a **non-`Active`** contract raises the
  status `ValueError` and `_delete_data` is **not called** — confirms E17, that the
  status check stays ahead of `confirm_delete_all`.
- `add_data(df, "p")` positionally → `TypeError`, confirming keyword-only.

### Not tested

Authorization outcomes (E11–E16) are platform behaviour reached through the existing
`raise_from_response` path, which already has its own coverage under
`src/tests/crossclient/exceptions/`. Re-asserting them here would test the platform, not
the client.

### Validation commands

Per `CLAUDE.md`, these are run only on explicit request:

```bash
uv run pytest src/tests/crossclient/
```

Followed by the full suite, `uv run ruff check src/`, `uv run ruff format src/`, and
`uv run mypy src/crosscontract/` before the PR.

### Landing

`feat:` conventional commit as the PR title (additive public API), squash-merged into
`dev`. `CHANGELOG.md` is generated by `python-semantic-release` — not hand-edited.
