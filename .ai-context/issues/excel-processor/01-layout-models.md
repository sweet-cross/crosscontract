# WP1 — Excel layout models

## Context
**Part of issue:** [sweet-cross/crosscontract#111](https://github.com/sweet-cross/crosscontract/issues/111) — WP1

A Submission Contract has to declare the sheets of an Excel bundle and which of them are
laid out wide. This task adds the models for that declaration. They stand alone, with no
reference to the `tableschema`; checking them against it is WP2. These models define the
YAML format that `cross_back` and contract authors write, so their names and nesting are
the expensive part to change later.

## Acceptance Criteria
- [ ] `WideLayout` has required `header_field: str` and `value_field: str`, and fails
      validation when the two are equal.
- [ ] `ExcelSheet` has `name: str` (non-empty), `description: str | None = None` and
      `wide: WideLayout | None = None`.
- [ ] `ExcelProcessor` has `sheets: list[ExcelSheet]` with at least one entry, and fails
      validation when sheet names repeat, naming the duplicates.
- [ ] All three models use `extra="forbid"`, so unknown keys are rejected.
- [ ] The field descriptions state the meaning:
  - a sheet is identified by its fixed `name`;
  - a sheet without `wide` is long and is used as is;
  - in a wide sheet, every `tableschema` field other than `header_field` and
    `value_field` appears as a column, every remaining column header is a value of
    `header_field`, and the cells are values of `value_field`.
- [ ] This YAML validates into an `ExcelProcessor`:
  ```yaml
  sheets:
    - name: capacities
      description: Installed capacities per technology.
    - name: costs
      wide:
        header_field: year
        value_field: value
  ```

## Implementation Details
- File to create: `src/crosscontract/submission/excel_processor.py`.
- Follow `src/crosscontract/submission/extraction/extraction_instruction.py`:
  - `model_config = ConfigDict(extra="forbid")`;
  - `Field(description=...)` on every field;
  - Google-style docstrings with an `Attributes:` block.
- The unique-name check mirrors `ExtractionInstructions._check_name_unique`.
- For `name`, use `Field(..., min_length=1)`. Do **not** strip whitespace: the name must
  match the workbook's sheet name exactly.
- Do not export the models from `submission/__init__.py`; they are reached through
  `SubmissionContract`.
- Dependencies: none.
