# WP3 — Excel readers raise `FileReadError`

## Context
**Part of:** GitHub issue #119 (body, discussion summary, and the 2026-10-22 update comment)

cross_back currently treats a `ValueError` from `read_excel_bundle_bytes` as a layout
mismatch and logs any other error. With the Excel readers raising `FileReadError` like
the CSV and parquet readers, cross_back translates one exception for all formats. This is
a breaking change to a released function, which is why #119's PR title is `feat!:`.

## Acceptance Criteria
- [ ] `read_excel_workbook_bytes` raises `FileReadError` instead of `ValueError` for:
      none of the listed sheets found; a column with a blank header holding data
      (raised in `_clean_sheet`); a wide sheet with a column named like its
      `value_field`. The messages are unchanged.
- [ ] `read_excel_workbook_bytes` translates `python_calamine.CalamineError` (an
      unreadable workbook) into `FileReadError`.
- [ ] Any other exception propagates unchanged.
- [ ] The "contract has no `excel_processor`" check in `read_excel_bundle_bytes` stays a
      `ValueError` (a caller error, not a bad file). `FileNotFoundError` from
      `read_excel_bundle` is not translated.
- [ ] The `Raises:` sections of `read_excel_workbook_bytes`, `read_excel_bundle_bytes`
      and `read_excel_bundle` name `FileReadError`.
- [ ] The existing layout-error tests expect `FileReadError`; a new test covers a
      corrupt workbook.

## Implementation Details
- Files to modify:
  - `src/crosscontract/transformations/excel/processing.py`
  - `src/crosscontract/handlers/submission/excel_processing.py` (docstrings only)
  - `src/tests/transformations/excel/test_processing.py`
  - `src/tests/handlers/submission/test_excel_processing.py`
- Raise `FileReadError` where the error happens, not by catching `ValueError` in the
  handlers wrapper: a wrapper catch would also wrap unexpected `ValueError`s from pandas.
- `transformations/` may import `exceptions/` (a base package).
- Nothing moves: `transformations/excel/` stays whole and `read_excel_bundle(_bytes)`
  stays in `handlers/submission/`. The spec/reader split is a separate refactor.
- Dependencies: after 01-file-read-error.md. Independent of 02-csv-parquet-readers.md.
