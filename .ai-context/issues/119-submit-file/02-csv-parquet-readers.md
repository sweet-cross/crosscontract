# WP2 — CSV and parquet readers in `handlers/readers/`

## Context
**Part of:** GitHub issue #119 (body, discussion summary, and the 2026-10-22 update comment)

The client must read a file exactly as cross_back does, otherwise local validation
checks a different frame than the platform. This task moves cross_back's CSV and
parquet readers into crosscontract; cross_back then imports them
(sweet-cross/cross_back#532). This is the critical path: its whole job is parity with
cross_back.

## Acceptance Criteria
- [ ] A new `handlers/readers/` package holds a bytes core and a path wrapper per
      format: `read_csv_file_bytes(data)` / `read_csv_file(filename)` and
      `read_parquet_file_bytes(data)` / `read_parquet_file(filename)` (names proposed;
      settle them before implementing).
- [ ] The CSV bytes core calls `pd.read_csv` with exactly cross_back's settings:
      `encoding="utf-8"`, `encoding_errors="strict"`, `keep_default_na=False`,
      `on_bad_lines="error"`, and the hard-coded 17-entry `na_values` list.
- [ ] The bytes cores translate only "bad file" errors into `FileReadError`, with
      cross_back's current messages:
  - `UnicodeDecodeError` → `"Invalid file encoding: must be UTF-8"`
  - `pd.errors.ParserError` → `f"Invalid CSV format: {e}"`
  - `pd.errors.EmptyDataError` → `f"Could not parse file: {e}"` (what cross_back's
    catch-all produces today)
  - the pyarrow read error for parquet → `f"Invalid Parquet format: {e}"`
- [ ] Any other exception propagates unchanged; no `except Exception`.
- [ ] The path wrappers read the file and call the bytes core; they do not translate
      `FileNotFoundError`.
- [ ] Exported from `crosscontract.handlers.readers` and re-exported from
      `crosscontract.handlers`.
- [ ] cross_back's reader tests are ported: `"NA"` stays a string, each listed NA token
      becomes missing, invalid UTF-8, a bad line, empty input, and invalid or empty
      parquet.
- [ ] A test pins the exception class pyarrow actually raises for invalid and for empty
      parquet before the `except` clause is fixed.

## Implementation Details
- Files to create:
  - `src/crosscontract/handlers/readers/__init__.py`
  - `src/crosscontract/handlers/readers/` module(s) for the two formats
  - `src/tests/handlers/readers/__init__.py` and the test module(s)
- Files to modify:
  - `src/crosscontract/handlers/__init__.py` (re-exports)
  - `src/tests/handlers/test_handlers.py` (export test)
- Source to copy from: cross_back `backend/app/api/utils/readers.py`
  (`get_dataframe_from_csv_bytes`, `get_dataframe_from_parquet_bytes`); tests from
  cross_back `backend/tests/utils/test_readers.py`.
- Pattern to follow: `read_excel_bundle_bytes` / `read_excel_bundle` in
  `handlers/submission/excel_processing.py` (bytes core plus `Path(filename).read_bytes()`
  wrapper). No IO-buffer variant.
- The readers take no contract. NA handling from the schema's `missingValues` is out of
  scope.
- `handlers/` may import `exceptions/`; it must not import `crossclient/` or `services/`.
- Dependencies: after 01-file-read-error.md. Independent of 03-excel-file-read-error.md.
