# Scope data writes and deletes to a project

## Summary
The CROSS platform now owns submitted data by project and requires a caller to
act on behalf of one project when writing or deleting data. This adds an
optional `project_name` parameter to the client's data-write and data-delete
paths (`ContractService._add_data`/`_delete_data` and
`ContractResource.add_data`/`delete_data`), so callers who belong to more than
one project can say which one they're acting for. Callers with exactly one
project membership are unaffected — the platform infers it as before.

Alongside `project_name`, `delete_data` gains a `confirm_delete_all` flag that
authorizes clearing every row the resolved project owns under a contract,
without dropping the storage table. This closes a gap the project change
otherwise opened: the existing `filters`-required guard on `delete_data`
pointed users at `drop_data()` for a full wipe, but `drop_data()` now destroys
every project's data and requires the contract to be `Retired` — not the
scoped, `Active`-only operation a project owner actually wants.

## Changes
- `ContractService._add_data` accepts `project_name: str | None = None`,
  sent as a query parameter on the POST (previously the method sent no
  `params` at all). Omitted from the query string when `None`; sent when
  `""` — the guard is `is not None`, not truthiness, since an omitted
  parameter means "infer the project" and a falsy-but-not-None value must
  not be silently reinterpreted that way.
- `ContractService._delete_data` accepts `project_name` (same omission rule)
  and `confirm_delete_all: bool = False`. The empty-`filters` guard now
  reads `if not filters and not confirm_delete_all`, and its message no
  longer points at `drop_data()`. The client parameter `confirm_delete_all`
  is mapped to the platform's `delete_all` query key in exactly this one
  place, so the client and wire vocabularies can differ without a rename
  leaking through the resource → service boundary. The flag is sent only
  when `filters` is empty: combining the two is allowed and resolves as
  "filters win", enforced client-side by dropping the flag rather than by
  assuming how the platform orders the two — the fallout of guessing that
  wrong is every row the project owns.
- `ContractResource.add_data` and `delete_data` gain the same parameters,
  both keyword-only, and forward to the service unchanged. `delete_data`'s
  existing `Active`-status check still runs first, ahead of the empty-filter
  check and ahead of `confirm_delete_all` — an unfiltered delete on a
  non-`Active` contract still can't reach the platform.
- `drop_data()` docstring rewritten to state plainly that it is a
  decommissioning operation restricted to administrators, crossing every
  project, as distinct from the newly-scoped `delete_data`.
- No client-side project resolution, validation, or default project was
  added — `project_name` is an opaque pass-through string; the platform
  remains the sole authority on which project a caller may act under.
- `docs/client/index.md`: new "Projects" section, and the removal-operations
  table grows a Scope column and a third row for the unfiltered
  `confirm_delete_all` form.
- `notebooks/client_tutorial.ipynb`: one markdown cell added ahead of the
  `add_data` example, noting when `project_name` is needed. Code cells
  unchanged — the parameter is optional, so the existing calls stay valid.
- `.ai-context/CONTEXT.md`: added a **Project** entry to the ubiquitous
  language, noting that a contract itself belongs to no project (only its
  rows do) and that reads are not scoped the way writes are.
- `.claude/CLAUDE.md`: tightened the docstring convention to explicitly ban
  rST double-backtick literals and field markers (matching the sibling
  `cross_back` repo's rule) and to require `Args`/`Returns`/`Raises` on every
  applicable docstring. Existing double-backtick usage elsewhere in the
  package is pre-existing and out of scope; tracked in `.ai-context/TODO.md`
  for a dedicated sweep.

## Testing
- New `respx`-backed tests in `test_contracts_service.py` covering, for both
  `_add_data` and `_delete_data`: `project_name` present when set, absent
  when `None`, and present-but-empty when `""` (guards the truthiness-vs-
  `is not None` distinction); `_add_data`'s `project_name` landing in the
  query string and not the multipart body; `confirm_delete_all` mapping to
  the wire key `delete_all` (and `confirm_delete_all` itself never reaching
  the wire, where it would be swept up as a bogus filter); the empty-filters
  guard raising with no filters and no confirmation, issuing a request with
  confirmation, and `delete_all` being dropped when filters are also given.
- New delegation tests in `test_contract_resource.py` asserting non-default
  `project_name` / `confirm_delete_all` values actually reach the service —
  the three pre-existing pinned assertions only pinned the default (`None`
  / `False`) case, which would still pass if the parameter were accepted
  and silently dropped.
- Full suite, `ruff check`, `ruff format --check`, and `mypy` all green.

## Notes for reviewer
- `drop_data()` was deliberately left without its own confirmation
  parameter: it's already an admin-only route, so the extra ceremony
  wasn't judged to buy anything.
- `_delete_data`'s empty-filters rule is mirrored client-side (raising
  before any request when `filters` is empty and `confirm_delete_all` is
  `False`), which duplicates a rule the platform also enforces. This was a
  deliberate choice — the rule is stated in the platform's own 400 response,
  so both sides enforce one rule rather than two that can drift, and it
  saves a round trip on an obvious mistake. By contrast, no client-side
  guard was added against filter keys that shadow reserved query parameters
  (e.g. a contract column literally named `project_name`) — that would
  require copying a platform constant the platform doesn't expose, and the
  platform already rejects the realistic collision with a fast 404.
- The full design discussion (rejected alternatives, edge-case table, wire
  contracts) lives in `.ai-context/prds/2026-08-06-client-project-scoped-writes.md`.
