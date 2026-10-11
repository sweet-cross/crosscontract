# WP3 — `read_excel_bundle`

## Context
**Part of issue:** [sweet-cross/crosscontract#112](https://github.com/sweet-cross/crosscontract/issues/112) — WP3

This is the core of the issue: a pure conversion from an Excel workbook, given as bytes,
to the long bundle its `SubmissionContract` describes. The client and `cross_back` both
call it, so the logic lives only here. The reader does **not** validate values. It only
reshapes them; validation is a separate step elsewhere.

## Acceptance Criteria
- [ ] `read_excel_bundle(contract: SubmissionContract, data: bytes) -> pd.DataFrame` is
      a free function in `processing.py`. It is not a method on the spec models.
- [ ] The workbook is read with `pd.read_excel(BytesIO(data), sheet_name=None,
      engine="calamine")`.
- [ ] Sheets in the workbook that `excel_processor.sheets` does not list are ignored.
- [ ] A long sheet (no `wide`) is taken unchanged.
- [ ] A wide sheet is melted with:
  - `id_vars` = the sheet's columns that are `tableschema` fields;
  - `value_vars` = every remaining column;
  - `var_name = wide.header_field`, `value_name = wide.value_field`.
- [ ] Blank cells in wide sheets are kept as rows with a missing value. Nothing is
      dropped.
- [ ] Header values and cell values are not converted. They come out exactly as pandas
      reads them.
- [ ] All listed sheets, after processing, are concatenated into one frame in the order
      they are listed (`ignore_index=True`).
- [ ] Raises `ValueError` when:
  - the contract has no `excel_processor`;
  - a listed sheet is missing from the workbook (the error names the sheet);
  - a wide sheet already has a `header_field` or `value_field` column (the error names
    the sheet and the column).
- [ ] The function is exported from `crosscontract.submission` (`__init__.py` and
      `__all__`).
- [ ] The Google-style docstring states the expected workbook layout (long vs wide,
      unlisted sheets ignored, blanks kept) and every error in `Raises:`. It contains no
      design rationale.

## Implementation Details
- Modify: `src/crosscontract/submission/excel_processing/processing.py`,
  `src/crosscontract/submission/excel_processing/__init__.py` (re-export),
  `src/crosscontract/submission/__init__.py` (re-export and `__all__`).
- Import `SubmissionContract` under `typing.TYPE_CHECKING` only. A runtime import would
  close a cycle: `submission_contract` → `excel_processing` → `processing` →
  `submission_contract`.
- Sheet names match exactly, as the `ExcelSheet.name` description states.
- Keep it plain: one function, no helpers, no extra validation beyond the three errors.
- Dependencies: after `01-restructure.md` and `02-dependency.md`.
