# WP2 — `SchemaValidationError` only from `crosscontract.exceptions`

## Context
**Part of:** the slim-root-exports refactor (agreed in discussion; no PRD) — WP2

Exceptions are imported from `crosscontract.exceptions`. `SchemaValidationError`
already lives there (`exceptions/schema_exceptions.py`), but `contracts/` and
`contracts/schema/` still re-export it, so the same rule breaks one level below the
root.

## Acceptance Criteria
- [ ] `crosscontract.contracts` and `crosscontract.contracts.schema` no longer export
      `SchemaValidationError` (neither imported in the `__init__.py` nor in `__all__`).
- [ ] `grep -rnE "import .*SchemaValidationError" src/` shows only imports from
      `crosscontract.exceptions` or relative imports inside `exceptions/`.
- [ ] `test_exported_from_all_paths` in `test_schema_exceptions.py` is removed.

## Implementation Details
- `src/crosscontract/contracts/__init__.py`: line 3 becomes
  `from .schema import TableSchema`; drop `"SchemaValidationError"` from `__all__`.
- `src/crosscontract/contracts/schema/__init__.py`: drop the import at line 20 and the
  `__all__` entry at line 39. Check that no module in `contracts/schema/` imports it
  through the package `__init__` (`validate_dataframe.py` already imports from
  `crosscontract.exceptions`).
- Tests that switch to `from crosscontract.exceptions import SchemaValidationError`:
  - `src/tests/contracts/contracts/test_validate_data.py:4` (keep `BaseContract`,
    `CrossContract` from `crosscontract.contracts`)
  - `src/tests/contracts/schema/adapters/pandera_pandas/test_integration_granularity.py:16`
    (keep `TableSchema` from `crosscontract.contracts.schema`)
  - `src/tests/crossclient/submission/test_submission_resource.py:9`
  - `src/tests/handlers/test_target_granularity.py:15`
  - `src/tests/handlers/test_validate_submission.py:6`
- Delete `test_exported_from_all_paths` in
  `src/tests/exceptions/test_schema_exceptions.py`; with only one path left it tests
  nothing.
- Dependencies: none in code. Lands in the same PR as WP1; if WP1 is not in yet, the
  root line of `test_exported_from_all_paths` goes with the test.
