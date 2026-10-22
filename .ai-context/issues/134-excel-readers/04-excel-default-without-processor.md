# Read Excel without an `excel_processor`

## Context
**Part of PRD:** GitHub issue sweet-cross/crosscontract#134 (no PRD file)

Any submission contract should accept an Excel file. Without an `excel_processor`,
the workbook is read like pandas' default: the first sheet, taken as one long sheet.

## Acceptance Criteria
- [ ] `read_excel_workbook_bytes` takes `processor: ExcelProcessor | None`; with
      `None` it reads the first sheet as a long sheet, through the same blank-row and
      blank-header-column cleaning and the same NA setting.
- [ ] A second sheet is ignored on the default path.
- [ ] `read_excel_bundle(_bytes)` no longer raises `ValueError` for a contract without
      `excel_processor`; the `ValueError` lines leave their docstrings.
- [ ] `CrossSubmitter.submit_file` reads an Excel file for a contract without
      `excel_processor`; its docstring drops that `ValueError` case.
- [ ] The `SubmissionContract.excel_processor` description and the class docstring no
      longer say that without it only non-Excel bundles are accepted.

## Implementation Details
- Modify `src/crosscontract/handlers/readers/excel_reader.py` (from task 03).
- Modify `src/crosscontract/services/submitter/submitter.py` (`submit_file`
  docstring, `Raises:`).
- Modify `src/crosscontract/contracts/submission/submission_contract.py`: the
  docstring at line ~45 and the `Field(description=...)` at line ~82; the wide-sheet
  validator already returns early on `None`.
- Tests in `src/tests/handlers/readers/` (no processor → first sheet long, second
  ignored; blank cleaning applies) and `src/tests/services/submitter/test_submitter.py`
  (Excel for a contract without processor).
- Out of scope: reading every sheet when there is no processor.
- Dependencies: after 03.
