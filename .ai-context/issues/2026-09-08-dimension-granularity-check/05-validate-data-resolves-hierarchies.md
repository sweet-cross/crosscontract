# Wire check_dimension_granularity into BaseContract.validate_data

## Context

**Part of PRD:** [.ai-context/prds/2026-09-08-dimension-granularity-check.md](../../prds/2026-09-08-dimension-granularity-check.md)

WP2, step 2 — the architectural risk of the whole PRD. This is the first caller to use
**both** members of `ContractResolver` in one operation (ADR 0005): `resolve` to learn that
a reference is hierarchical, `get_data` to read it.

## Acceptance Criteria

- [X] `BaseContract.validate_data` takes `check_dimension_granularity: bool = False`.
- [X] Set without a `resolver` → raises, reusing the existing "checking against existing
  values requires a resolver" message, extended to name the new flag.
- [X] Unset → the resolver is not consulted for hierarchies at all, and
  `dimension_hierarchies` stays `None`.
- [ ] Derivation happens **only** when this contract's own `tableschema` is a
  `ValueVariableSchema` (PRD §3). Any other schema type → no check, no resolver calls
  for hierarchies.
- [ ] For each foreign key, `resolver.resolve(fk.reference.resource)`; keep those whose
  `tableschema` is a **`DimensionSchema`** — **not** `BaseDimensionSchema`, which also
  matches `FlexibleDimensionSchema`.
- [ ] A referenced contract that does not resolve → raises, naming the contract.
- [ ] The parent map is built from `resolver.get_data(dim_name, columns=[id_col, parent_col], unique=True)`, with `id_col` read off `fk.reference.fields` and
  `parent_col` off the resolved dimension's own self-referencing foreign key.
- [ ] Tests: flag set with a `Dimension` fk → the resolver is asked and the check runs;
  **flag set with a `FlexibleDimension` fk → no check runs** (the regression that
  matters); flag set on a non-`ValueVariable` contract → no check runs; flag set with
  no resolver → raises; flag unset → resolver not consulted; unresolvable contract →
  raises naming it.

## Implementation Details

- Modify:
  - `src/crosscontract/contracts/contracts/base_contract.py`
  - `src/tests/contracts/contracts/test_base_contract.py` (or equivalent)
- The `BaseDimensionSchema` trap is live, not hypothetical: `dim_model` and `dim_scenario`
  are FlexibleDimensions referenced by nearly every ValueVariable, so a loose isinstance
  test would derive a check on almost every contract in the model. Note that
  `ContractResource.is_dimension` uses the loose test today — do not copy it.
- Import `DimensionSchema` / `ValueVariableSchema` inside the method if needed to avoid a
  circular import, as `validate_references` already does for `BaseDimensionSchema`.
- `_get_existing_values` returns tuples and does not fit a dict-shaped result; a private
  helper beside it is acceptable if the resolve-and-build step does not read cleanly
  inline. Prefer the plainest thing that works (repo `CLAUDE.md`).
- Depends on `04`.
- Do not run pytest, ruff or mypy without asking (repo `CLAUDE.md`).
