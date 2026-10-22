# WP1 — Fetch specs move to `contracts/fetching/` as `FetchSpec`

## Context
**Part of:** GitHub issue #137 (no PRD) — WP1

The fetch specs are declarative and run nothing themselves, so they belong with the
other specs in `contracts/`. `FetchSpecMixin` is never mixed in (it is a field type and
instantiated directly), so it is renamed `FetchSpec` in the same move. This is the
breaking API change of the issue and the critical path.

## Acceptance Criteria
- [ ] `FetchSpec`, `AggregationSpec`, `ColumnAggregation` and `LevelKeepSpec` live in
      `crosscontract.contracts.fetching` and are exported from it. They are not
      re-exported from `crosscontract.contracts` or the top-level package.
- [ ] The name `FetchSpecMixin` is gone, with no alias. `crosscontract.transformations`
      no longer exports any of the four names.
- [ ] `transformations/fetch/` is gone.
- [ ] `DataInstructions.fetch` and the package creator keep their behaviour.
- [ ] Tests live in `src/tests/contracts/fetching/`; `src/tests/transformations/fetch/`
      is gone.
- [ ] `grep -rn "FetchSpecMixin\|transformations.fetch\|transformations/fetch" src/`
      finds nothing.

## Implementation Details
- Move with `git mv` so history follows:
  - `src/crosscontract/transformations/fetch/fetch_spec.py` →
    `src/crosscontract/contracts/fetching/fetch_spec.py`
  - `src/crosscontract/transformations/fetch/aggregation_spec.py` →
    `src/crosscontract/contracts/fetching/aggregation_spec.py`
  - `src/tests/transformations/fetch/test_fetch_spec.py` and `test_aggregation_spec.py`
    → `src/tests/contracts/fetching/` (with an `__init__.py`, like the sibling test
    packages).
- New `src/crosscontract/contracts/fetching/__init__.py` exporting the four names, in the
  style of `transformations/fetch/__init__.py` today.
- `fetch_spec.py`: rename the class; the docstring summary drops "Mixin". Leave
  `get_data_kwargs` where it is (agreed in the #137 discussion).
- Remove the `from .fetch import ...` block and the `# fetch/` entries from
  `src/crosscontract/transformations/__init__.py`; delete
  `src/crosscontract/transformations/fetch/__init__.py`.
- Update importers:
  - `src/crosscontract/contracts/release/release_specification.py` (import, field type)
  - `src/crosscontract/services/package_creator/_resolve_resource.py` (import, the
    `fetch_spec` annotation and its docstring, `FetchSpec(contract=ref_name, ...)`)
  - `src/tests/contracts/fetching/test_fetch_spec.py`, `test_aggregation_spec.py`
  - `src/tests/services/package_creator/test_resolve_resource.py` (import, calls, the
    comment at line 169)
  - `src/tests/services/reader/test_data_variable.py` (docstring at line 474)
- Import graph unchanged: `fetch_spec.py` imports only `crosscontract.constants` and its
  sibling `aggregation_spec`.
- Dependencies: none. Do before `02-flatten-transformations.md` (both edit
  `transformations/__init__.py`).
