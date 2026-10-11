# WP4 — Tests for `read_excel_bundle_bytes` / `read_excel_bundle`

## Context
**Part of issue:** [sweet-cross/crosscontract#112](https://github.com/sweet-cross/crosscontract/issues/112) — WP4

A wrong melt that still passes validation would be ingested unnoticed, because the
platform only re-validates the long frame it receives. That makes the rules for
deducing `id_vars` / `value_vars` the main thing to test.

## Acceptance Criteria
- [ ] Workbooks are built in memory with `openpyxl` (or `DataFrame.to_excel` into a
      `BytesIO`) and passed to the reader as bytes. No fixture files on disk.
- [ ] A long sheet comes back unchanged.
- [ ] `_clean_sheet` is tested directly:
  - a clean sheet comes back unchanged;
  - empty rows are dropped;
  - empty `Unnamed: N` columns are dropped;
  - an empty column with a real header is kept;
  - an `Unnamed: N` column with data raises, naming the sheet and that column only;
  - `Unnamed:3` (no blank) is not matched.
- [ ] A wide workbook with a blank-header spacer column and an empty row between data
      rows is cleaned before melting.
- [ ] A wide sheet melts correctly: the id columns are the sheet's `tableschema` fields,
      every other header becomes a `header_field` value, and the cells become
      `value_field` values.
- [ ] Blank cells in a wide sheet come back as rows with a missing `value_field`.
- [ ] A workbook sheet the contract does not list is ignored.
- [ ] A listed sheet missing from the workbook is skipped.
- [ ] A long sheet and a wide sheet are concatenated into one frame, in the order the
      contract lists them.
- [ ] Each error raises `ValueError` with the expected message:
  - contract without `excel_processor`;
  - none of the listed sheets is in the workbook;
  - a column with a blank header holds data;
  - wide sheet with a column header equal to `value_field`.
- [ ] A wide sheet with `header_field: country` and a column header `country` (next to
      `austria`, `germany`) melts that column into rows with `country == "country"`. It
      does not become an id column.
- [ ] An id column header with a typo (e.g. `"Region "` with a trailing space) is
      treated as a `value_var`. This test documents the behaviour; it is not an error.
- [ ] `read_excel_bundle` reads a file path and returns the same frame as the bytes
      reader.
- [ ] Both functions can be imported from `crosscontract.submission`.
- [ ] Coverage of `processing.py` is complete.

## Implementation Details
- Create: `src/tests/submission/excel_processing/test_processing.py`.
- Reuse the contract fixtures in `src/tests/submission/conftest.py` where they fit,
  adding an `excel_processor` section, rather than writing new contracts from scratch.
- Dependencies: after `03-read-excel-bundle.md`.
