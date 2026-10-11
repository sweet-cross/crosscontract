# WP3 — Tests for the `excel_processor` section

## Context
**Part of issue:** [sweet-cross/crosscontract#111](https://github.com/sweet-cross/crosscontract/issues/111) — WP3

This task covers the WP1 models, the WP2 contract validator, and backwards compatibility.
`cross_back` will pin a release with this section, so contracts written before it must
keep loading and round-tripping.

## Acceptance Criteria
- [ ] Model tests for `WideLayout`, `ExcelSheet` and `ExcelProcessor`:
  - a valid long sheet, with and without `description`;
  - a valid wide sheet;
  - rejected: `header_field == value_field`;
  - rejected: an empty `name`;
  - rejected: an empty `sheets` list;
  - rejected: duplicate sheet names;
  - rejected: an unknown key at each level.
- [ ] Contract tests:
  - a contract with a valid `excel_processor` section loads;
  - a wide sheet whose `header_field` is not a `tableschema` field is rejected;
  - a wide sheet whose `value_field` is not a `tableschema` field is rejected;
  - in both rejections, the error names the sheet.
- [ ] Backwards compatibility:
  - `src/tests/submission/example_submission.yaml` loads unchanged with
    `excel_processor` as `None`;
  - `SubmissionContract.from_server(contract.to_server())` round-trips both with and
    without the section.
- [ ] Existing tests in `src/tests/submission/` are untouched and still pass.

## Implementation Details
- Files to create or modify:
  - `src/tests/submission/test_excel_processor.py` (new): model tests;
  - `src/tests/submission/test_submission_contract.py`: contract and round-trip tests.
- Build contracts with the section from the `contract` fixture in
  `src/tests/submission/conftest.py`: dump it, add `excel_processor` to the dict, and
  validate the result. Do not edit `example_submission.yaml`.
- Run the tests only with the user's go-ahead.
- Dependencies: written alongside `01-layout-models.md` and
  `02-submission-contract-section.md`; finished after both.
