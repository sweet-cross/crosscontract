# WP2 — `excel_processor` section on `SubmissionContract`

## Context
**Part of issue:** [sweet-cross/crosscontract#111](https://github.com/sweet-cross/crosscontract/issues/111) — WP2

This task adds the WP1 models to `SubmissionContract` as an optional section. Checks that
need the `tableschema` belong here: a wide sheet must name fields the contract actually
declares.

## Acceptance Criteria
- [ ] `SubmissionContract` has `excel_processor: ExcelProcessor | None = None`, with a
      `Field(description=...)`.
- [ ] Validation fails if a sheet's `header_field` or `value_field` is not a
      `tableschema` field. The error names the sheet and the unknown field(s).
- [ ] A contract without the section validates as before.
- [ ] `to_server()` is unchanged. A contract without the section serialises
      `excel_processor: null`, which is accepted.
- [ ] The class docstring's `Attributes:` block lists `excel_processor`.

## Implementation Details
- File to modify: `src/crosscontract/submission/submission_contract.py`.
- Add a `model_validator(mode="after")` modelled on `_check_filters`:
  - check membership against `self.tableschema.field_names`;
  - return early when `excel_processor` is `None`;
  - skip sheets without `wide`.
- Leave `to_server()` / `from_server()` alone.
- Dependencies: must be completed after `01-layout-models.md`.
