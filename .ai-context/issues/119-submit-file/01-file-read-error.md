# WP1 — `FileReadError`

## Context
**Part of:** GitHub issue #119 (body, discussion summary, and the 2026-10-22 update comment)

Every reader raises one exception for a file that cannot be read, so that cross_back
translates a single type into its HTTP `ValidationError` instead of knowing which
built-in exception each reader raises. This task only adds the exception; WP2 and WP3
raise it.

## Acceptance Criteria
- [ ] `FileReadError` exists in `exceptions/reader_exceptions.py`, as a plain `Exception`
      subclass whose message is the user-facing text.
- [ ] It is exported from `crosscontract.exceptions` and listed in its `__all__`.
- [ ] It is not a subclass of `ValueError`, `SchemaValidationError` or `CrossClientError`.
- [ ] A test covers the export (extend `src/tests/exceptions/test_exceptions_package.py`).

## Implementation Details
- Files to create:
  - `src/crosscontract/exceptions/reader_exceptions.py`
- Files to modify:
  - `src/crosscontract/exceptions/__init__.py`
  - `src/tests/exceptions/test_exceptions_package.py`
- The name is deliberately not bundle-specific: cross_back also uses the CSV and parquet
  readers for contract-data uploads.
- `exceptions/` imports nothing from the rest of the package; keep it that way.
- No extra attributes or constructor arguments: the message is the whole payload.
- Docstring: Google style, describing when a caller meets it (a file whose content
  cannot be read as the expected format, or a workbook that does not match the
  contract's Excel layout).
- Dependencies: none. WP2 and WP3 depend on this task.
