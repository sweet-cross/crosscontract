# Move the Excel reader to `handlers/readers/` with the shared NA setting

## Context
**Part of PRD:** GitHub issue sweet-cross/crosscontract#134 (no PRD file)

Every bundle format is read from `handlers/readers/`. The Excel reader moves there
and stops using pandas' default NA list, so `"NA"` survives in Excel as in CSV. This
is the critical path: the NA setting meets `_clean_sheet`. A probe showed that reading
with `keep_default_na=False` *without* `""` in the list turns blank cells into `""`,
so blank rows are no longer dropped and an empty blank-header column raises
`FileReadError`. The shared `[""]` from task 01 avoids this.

## Acceptance Criteria
- [ ] `read_excel_workbook_bytes`, `read_excel_bundle_bytes` and `read_excel_bundle`
      live in `handlers/readers/excel_reader.py` and are exported from
      `crosscontract.handlers.readers` and `crosscontract.handlers`.
- [ ] `pd.read_excel` reads with `keep_default_na=False` and the shared NA constant.
- [ ] Cells holding `"NA"`, `"NULL"`, `"n/a"` or `"None"` are read as strings; blank
      cells are missing values.
- [ ] Fully blank rows are still dropped, and an empty column with a blank header is
      still dropped without an error.
- [ ] Unreadable workbooks and layout mismatches still raise `FileReadError`.
- [ ] `transformations/excel/` and `handlers/submission/excel_processing.py` are gone;
      nothing imports from them; `handlers.submission` no longer exports the readers.

## Implementation Details
- Create `src/crosscontract/handlers/readers/excel_reader.py` from
  `src/crosscontract/transformations/excel/processing.py` (`_clean_sheet`,
  `read_excel_workbook_bytes`) and
  `src/crosscontract/handlers/submission/excel_processing.py`
  (`read_excel_bundle_bytes`, `read_excel_bundle`). Spec imports come from
  `crosscontract.contracts.readers` (task 02).
- Modify `src/crosscontract/handlers/readers/__init__.py`,
  `src/crosscontract/handlers/__init__.py` (import the Excel readers from `.readers`),
  `src/crosscontract/handlers/submission/__init__.py` (exports `SubmissionHandler`
  only), `src/crosscontract/services/submitter/submitter.py` (import unchanged via
  `crosscontract.handlers`; check it still resolves).
- Delete `src/crosscontract/transformations/excel/` and
  `src/crosscontract/handlers/submission/excel_processing.py`. Check
  `src/crosscontract/transformations/__init__.py` for a reference.
- Move tests: `src/tests/transformations/excel/test_processing.py` and
  `src/tests/handlers/submission/test_excel_processing.py` →
  `src/tests/handlers/readers/` (e.g. `test_excel_reader.py`); delete
  `src/tests/transformations/excel/`. Update imports in
  `src/tests/handlers/test_handlers.py` and
  `src/tests/contracts/submission/test_submission_contract.py`.
- New tests: NA tokens as strings, blank cells missing, blank rows dropped, empty
  blank-header column dropped.
- Behaviour with no `excel_processor` is unchanged here (still `ValueError`); task 04
  changes it.
- Dependencies: after 01 (constant) and 02 (spec location).
