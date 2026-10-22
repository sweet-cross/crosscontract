# refactor!: read every bundle format from handlers/readers, with Frictionless NA handling and Excel without excel_processor

## Summary
Closes #134. The Excel reader moves next to the CSV and parquet readers in
`handlers/readers/`, and its spec moves to `contracts/readers/`. A submission
contract without an `excel_processor` now accepts an Excel workbook, read from its
first sheet. CSV and Excel both follow the Frictionless default
`missingValues: [""]`: only an empty cell is a missing value, so the country code
`"NA"` survives in every format. `SubmissionHandler` moves up into
`crosscontract.handlers`, since `handlers/submission/` no longer held anything else.

## Changes
- **NA handling (Frictionless default).** New `handlers/readers/constants.py` holds
  `NA_VALUES = [""]`, used with `keep_default_na=False` by the CSV and the Excel
  reader.
  - CSV: the 17 former tokens (`NULL`, `null`, `None`, `N/A`, `n/a`, `NaN`, `nan`,
    `<NA>`, `#NA`, `undefined`, …) are now read as strings, and an empty cell is
    missing when read instead of being kept as `""`.
  - Excel: no longer uses pandas' default NA list, so `"NA"` and the former tokens
    stay strings. Blank cells stay missing, so blank rows and empty blank-header
    columns are still dropped.
  - The pandera `""` → null parser is unchanged, so parquet and DataFrame input
    behave as before.
- **Excel specs → `contracts/readers/`.** `ExcelProcessor`, `ExcelSheet` and
  `WideLayout` move from `transformations/excel/specs.py` unchanged;
  `SubmissionContract` imports them from there.
- **Excel reader → `handlers/readers/excel_reader.py`.** `read_excel_workbook_bytes`
  (from `transformations/excel/processing.py`) and `read_excel_bundle(_bytes)` (from
  `handlers/submission/excel_processing.py`) are exported from
  `crosscontract.handlers.readers` and `crosscontract.handlers`.
  `transformations/excel/` is removed.
- **Excel without `excel_processor`.** `read_excel_workbook_bytes` takes
  `processor: ExcelProcessor | None`; `None` reads the first sheet as one long sheet
  through the same cleaning. `read_excel_bundle(_bytes)` no longer raises
  `ValueError` for a contract without a processor, so
  `CrossSubmitter.submit_file` reads Excel for every submission contract. Docstrings
  of `SubmissionContract.excel_processor`, the readers and `submit_file` updated.
- **`SubmissionHandler` → `crosscontract.handlers`.**
  `handlers/submission/submission_handler.py` becomes
  `handlers/submission_handler.py`; `crosscontract.handlers.submission` is removed.
  `SubmissionContractResource` imports from `crosscontract.handlers`.
- **Docs.** CLAUDE.md architecture (new `contracts/readers/` subsection, readers and
  NA default, two packages named `submission`, no cross_back references),
  `docs/client/index.md` (Excel works for every submission contract), and the WP6 note
  in `.ai-context/issues/docs-overhaul/06-submission.md`.

BREAKING CHANGE: CSV and Excel files now treat only an empty cell as a missing value.
Text such as `NULL`, `n/a`, `None` or `NaN` is read as a string: in a `number`,
`integer` or `datetime` field it is now a validation error instead of a null, and in
a `string` field it is stored as text. `crosscontract.transformations.excel` and
`crosscontract.handlers.submission` are removed: import the Excel specs from
`crosscontract.contracts.readers`, and `SubmissionHandler` and the Excel readers from
`crosscontract.handlers` (or `crosscontract.handlers.readers`).

## Testing
- CSV reader: `test_empty_cell_becomes_missing` (missing and numeric dtype) and
  `test_former_na_tokens_stay_strings` replace the old empty-string and token tests.
- Excel reader: NA tokens read as strings with blank cells missing; blank rows and an
  empty blank-header column dropped without error (the case that breaks if the shared
  list lacked `""`); without a processor, the first sheet is read long, a second sheet
  is ignored, and the cleaning applies.
- Bundle reader: a contract without `excel_processor` reads the first sheet long.
- `submit_file`: an `.xlsx` on disk for a contract without `excel_processor` is read
  end to end (`"NA"` stays a string).
- Tests moved to mirror the source layout: `src/tests/contracts/readers/`,
  `src/tests/handlers/readers/`, and the handler tests up to `src/tests/handlers/`.
- The test suite was not run as part of writing this description.

## Notes for reviewer
- The NA change is the user-visible part of this `refactor!`; it is spelled out in
  the `BREAKING CHANGE:` footer so it reaches the changelog.
- Known edge effects of reading `""` as missing at read time, accepted: target
  routing on a numeric column with gaps compares `"3.0"` instead of `"3"`, and
  `CastColumn` on a former token raises `ValueError` rather than producing a
  validation report.
- The default path builds an `ExcelSheet` for the first sheet instead of passing
  `sheet_name=0`, so it runs through the same read, cleaning and concat as the
  processor path. A workbook with no sheets would raise `IndexError` there.
- Deriving the NA list from a contract's `missingValues` stays out of scope; the
  strict contract `TableSchema` has no `missingValues` field.
- cross_back adopts this in sweet-cross/cross_back#532 (Updates 3 and 4: crosscontract
  readers, `FileReadError`, the new `SubmissionHandler` path).
