# WP1 — Move `SchemaValidationError` into `crosscontract.exceptions`

## Context
**Part of:** sweet-cross/crosscontract#126 — WP1

`SchemaValidationError` lives in `contracts/schema/exceptions/`, so `exceptions/submission_exceptions.py`
has to import it from `contracts/`. That import is the only thing keeping `exceptions/` from being a base
layer. This task moves the class unchanged and ends with the full suite passing. It is the critical path:
once `exceptions/` imports nothing from the package, `contracts/` can import from it without a cycle.

## Acceptance Criteria
- [ ] `SchemaValidationError` lives in `src/crosscontract/exceptions/schema_exceptions.py`, moved
      **unchanged**, together with `CHECK_COLUMNS_PATTERN` and the whole pandera report parser.
- [ ] `crosscontract.exceptions` exports `SchemaValidationError` (import and `__all__`).
- [ ] `src/crosscontract/exceptions/` imports nothing from the rest of `crosscontract`.
      `submission_exceptions.py` imports `SchemaValidationError` relatively from `.schema_exceptions`.
- [ ] `src/crosscontract/contracts/schema/exceptions/` is deleted. No shim module is left behind.
- [ ] These paths still re-export the same class object: `crosscontract`, `crosscontract.contracts`,
      `crosscontract.contracts.schema`.
- [ ] Behaviour is unchanged: message, `errors`, `to_list`, `to_pandas`, `max_errors` condensing.
- [ ] Tests are moved and updated (see below). No test or module in `src/` references
      `contracts.schema.exceptions`.
- [ ] `import crosscontract` works in a fresh interpreter, and the full suite passes (run only with
      the user's go-ahead).

## Implementation Details
- **Move:** `src/crosscontract/contracts/schema/exceptions/validation_error.py` →
  `src/crosscontract/exceptions/schema_exceptions.py`. Delete `contracts/schema/exceptions/__init__.py`
  and the directory.
- **Modify:**
  - `src/crosscontract/exceptions/__init__.py`: add `SchemaValidationError` to the imports and `__all__`.
  - `src/crosscontract/exceptions/submission_exceptions.py`:
    `from crosscontract.contracts.schema import SchemaValidationError` → `from .schema_exceptions import SchemaValidationError`.
  - `src/crosscontract/contracts/schema/__init__.py`: `from .exceptions import SchemaValidationError` →
    `from crosscontract.exceptions import SchemaValidationError`. Keep it in `__all__`.
  - `src/crosscontract/contracts/schema/validation/validate_dataframe.py`:
    `from ..exceptions import SchemaValidationError` → `from crosscontract.exceptions import SchemaValidationError`.
  - `src/crosscontract/contracts/__init__.py` and `src/crosscontract/__init__.py` already import from
    `.schema` / `.contracts`. Leave them unchanged.
- **Tests:**
  - Move `src/tests/contracts/schema/exceptions/test_validation_error.py` →
    `src/tests/exceptions/test_schema_exceptions.py`, importing from `crosscontract.exceptions`.
    Delete `src/tests/contracts/schema/exceptions/`.
  - `src/tests/contracts/schema/validation/test_pandas_validation.py`: switch its deep import
    (`crosscontract.contracts.schema.exceptions.validation_error`) to `crosscontract.exceptions`.
  - In `test_schema_exceptions.py`, add a test that `crosscontract.exceptions`, `crosscontract`,
    `crosscontract.contracts` and `crosscontract.contracts.schema` all expose the same class object,
    following `test_exported_from_exceptions_package` in `src/tests/exceptions/test_submission_exceptions.py`.
  - Imports through package-level paths (`crosscontract.contracts.schema`, `crosscontract.contracts`)
    keep working. Leave them as they are.
- **Import order:** `crosscontract/__init__` loads `contracts`, which now loads `crosscontract.exceptions`.
  This is safe only while `exceptions/` imports nothing internal, so check that `submission_exceptions.py`
  has no absolute `crosscontract.` imports left.
- **Do not** touch `docs/reference/contracts.md` here. It breaks until WP3; `mkdocs build` is checked there.
- **Dependencies:** none. WP2 is independent of this task.
