# WP2 — Flatten `transformations/`

## Context
**Part of:** GitHub issue #137 (no PRD) — WP2

With the fetch specs gone, `transformations/` holds only transformations, so the
`transformation/` subpackage is one level too deep.

## Acceptance Criteria
- [ ] `base.py`, `column_transformations.py`, `dataframe_transformations.py` and
      `union.py` live directly in `src/crosscontract/transformations/`.
- [ ] `crosscontract.transformations` exports the same transformation names as before
      (`BaseTransformation`, `TransformationUnion`, the six transformation classes and
      the six pure functions).
- [ ] `crosscontract.transformations.transformation` is gone, and nothing imports from
      it.
- [ ] Tests are flattened into `src/tests/transformations/`; every `patch()` target
      points at the new module path.
- [ ] `grep -rn "transformations\.transformation\|transformations/transformation" src/`
      finds nothing.

## Implementation Details
- Move with `git mv`:
  - `src/crosscontract/transformations/transformation/{base,column_transformations,dataframe_transformations,union}.py`
    → `src/crosscontract/transformations/`
  - `src/tests/transformations/transformation/test_*.py` → `src/tests/transformations/`
- Rewrite `src/crosscontract/transformations/__init__.py` to import from the flattened
  modules (the content of today's `transformation/__init__.py`); delete
  `transformation/__init__.py` and `src/tests/transformations/transformation/__init__.py`.
- The relative imports inside the moved modules (`from .base import ...`,
  `from .column_transformations import ...`) keep working unchanged.
- Update importers to `from crosscontract.transformations import TransformationUnion`:
  - `src/crosscontract/contracts/submission/extraction/target.py`
  - `src/crosscontract/contracts/submission/extraction/extraction_instruction.py`
- Update test imports and the four `patch()` targets, e.g.
  `"crosscontract.transformations.transformation.dataframe_transformations.rename_columns"`
  → `"crosscontract.transformations.dataframe_transformations.rename_columns"`:
  - `test_dataframe_transformations.py` (lines 7, 82, 150, 209)
  - `test_column_transformations.py` (lines 8, 293)
  - `test_union.py` (line 4)
- Dependencies: after `01-fetch-specs-to-contracts-fetching.md`.
