# Move the Excel specs to `contracts/readers/`

## Context
**Part of PRD:** GitHub issue sweet-cross/crosscontract#134 (no PRD file)

The Excel spec is declarative and belongs in the `contracts/` layer, independent of
submission; its reader moves to `handlers/readers/` in task 03. This task is a pure
move with no behaviour change.

## Acceptance Criteria
- [ ] `ExcelProcessor`, `ExcelSheet` and `WideLayout` live in
      `crosscontract.contracts.readers` and are exported from it.
- [ ] `SubmissionContract` imports `ExcelProcessor` from there; `excel_processor`
      keeps its type and its check that each wide sheet's `header_field` and
      `value_field` are `tableschema` fields.
- [ ] The spec tests live in `src/tests/contracts/readers/` and pass unchanged in
      content.

## Implementation Details
- Move `src/crosscontract/transformations/excel/specs.py` →
  `src/crosscontract/contracts/readers/specs.py`; add
  `src/crosscontract/contracts/readers/__init__.py`.
- Modify `src/crosscontract/contracts/submission/submission_contract.py` (import at
  line 12).
- `transformations/excel/__init__.py` keeps exporting `read_excel_workbook_bytes`
  until task 03 removes the package; update its spec import so it still loads.
- Move `src/tests/transformations/excel/test_specs.py` →
  `src/tests/contracts/readers/test_specs.py` (with `__init__.py`).
- Import graph stays one way: `contracts` must not import `handlers`.
- Dependencies: none. Can be done alongside 01.
