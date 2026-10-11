# feat: add an Excel reader that melts a workbook into the long submission bundle

## Summary
#111 lets a `SubmissionContract` declare an Excel bundle's sheets and which of them are laid out wide (`excel_processor`). This branch adds the reader that carries that declaration out. It turns a workbook into the one long `pd.DataFrame` the contract's `tableschema` describes, so the client and `cross_back` go through the same conversion. The reader is a pure conversion: it reshapes, it does not validate values. Closes #112.

## Changes
- **Restructure:** `submission/excel_processor.py` becomes the package `submission/excel_processing/`.
  - `specs.py` holds `ExcelProcessor` / `ExcelSheet` / `WideLayout`, moved unchanged.
  - `processing.py` holds the reader.
  - `SubmissionContract` and the tests import from the new package.
- **`read_excel_bundle_bytes(contract, data: bytes)`:** the core, for `cross_back`, which receives uploads as bytes.
  - Reads with pandas' `calamine` engine and parses the workbook once.
  - Listed sheets are matched by exact name. A listed sheet missing from the workbook is skipped, because providers may submit only part of the sheets. Unlisted sheets are ignored.
  - Each sheet is cleaned first by `_clean_sheet`:
    - rows that are entirely blank are dropped;
    - columns with a blank header (`Unnamed: N`) are dropped if they hold no data, and raise if they do.
  - A long sheet is then taken unchanged.
  - A wide sheet is melted:
    - `id_vars` = the sheet's columns that are `tableschema` fields, excluding `header_field` and `value_field`;
    - every other column becomes a `header_field` value, and its cells become `value_field` values.
    - Blank cells are kept as rows with a missing value, and headers are not converted.
  - Sheets are concatenated in the order the contract lists them.
  - Raises `ValueError` when:
    - the contract has no `excel_processor`;
    - none of the listed sheets is in the workbook;
    - a column with a blank header holds data;
    - a wide sheet has a header equal to `value_field` (pandas' `melt` error).
- **`read_excel_bundle(contract, filename)`:** a thin path wrapper for the client that reads the file and delegates to the bytes reader.
- Both readers are exported from `crosscontract.submission`.
- **Dependencies:**
  - `python-calamine` is added as a **core** dependency.
  - `openpyxl` is added to the `test` group only, to build test workbooks.
- **Docs and context:**
  - CLAUDE.md describes `excel_processing/`.
  - The task files for this issue are in `.ai-context/issues/excel-reader/`, and the finished #111 task files are removed.

## Testing
- New `test_processing.py`. Workbooks are built in memory, and the tests cover:
  - a long sheet passing through unchanged;
  - a full-frame check of a wide melt, so each cell lands in the row of its id values and header, blanks included;
  - int headers left as `int`;
  - unlisted sheets ignored, missing sheets skipped, exact (case-sensitive) name matching;
  - concatenation order and a fresh index;
  - each error;
  - a header equal to `header_field` being melted, not used as an id column;
  - a misspelled id column becoming a header value;
  - the path wrapper with `Path` and `str`, and a missing file.
- `_clean_sheet` is tested directly, plus an end-to-end wide workbook with a spacer column and an empty row.
- `test_specs.py`, the moved spec tests, now has docstrings.
- The test suite, mypy and ruff pass.

## Notes for reviewer
- **This departs from the original issue in places.** The issue was updated to match:
  - calamine is a core dependency, not an `openpyxl` extra;
  - there is a path wrapper, and the bytes core is `read_excel_bundle_bytes`;
  - missing listed sheets are skipped instead of rejected;
  - a wide header equal to `header_field` is valid data, not an error.
- **The import path changed.** `crosscontract.submission.excel_processor` (released in 0.26.0) is gone. The spec models are now under `crosscontract.submission.excel_processing`. If `cross_back` already imports from the old path, it needs updating when it bumps.
- **Why the `id_vars` exclusion stays for `value_field`.** A wide header equal to `value_field` raises pandas' error either way. The exclusion is kept anyway, so that header is classified as a header value, not an id column.
- **Silent skips are possible.** Exact name matching combined with skipping missing sheets means a tab named `Costs` when the contract lists `costs` is skipped without an error. This is deliberate and covered by a test.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
