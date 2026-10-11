# feat: add an excel_processor section to SubmissionContract

## Summary
CROSS will accept Excel submission bundles in which a single workbook mixes long sheets with wide sheets (e.g. one column per year). The layout cannot be inferred from a Submission Contract's `tableschema`, so the contract now declares it: an optional `excel_processor` section lists the workbook's sheets by fixed name and marks each wide sheet with the field spread across its headers and the field held in its cells. This PR adds the declaration and its validation only. The reader that melts a workbook is #112.

Closes #111.

## Changes
- **New models** in `submission/excel_processor.py`:
  - `WideLayout(header_field, value_field)`: the two fields must differ.
  - `ExcelSheet(name, description=None, wide=None)`:
    - `name` is non-empty and not stripped, because it must match the workbook's sheet name exactly;
    - a sheet without `wide` is long.
  - `ExcelProcessor(sheets)`:
    - at least one sheet;
    - sheet names are unique case-insensitively, matching Excel, which cannot hold `Costs` and `costs` together.
  - All three models reject unknown keys.
- **`SubmissionContract`:**
  - new optional `excel_processor: ExcelProcessor | None = None`;
  - new validator `_check_wide_fields`, which rejects a wide sheet whose `header_field` or `value_field` is not a `tableschema` field, naming the sheet and the unknown fields.
- **Backwards compatibility:** contracts without the section validate as before. `to_server()` is unchanged and now emits `excel_processor: null` for them, which is accepted because no contracts are stored server-side yet.
- **Planning:** task files for the three work packages in `.ai-context/issues/excel-processor/`.

## Testing
- New `test_excel_processor.py` covers:
  - a valid example;
  - long sheets with and without a description, and a wide sheet;
  - rejected: equal header and value fields, an empty name, an empty `sheets` list, duplicate names (including names differing only in case), and unknown keys at each level.
- `test_submission_contract.py` covers:
  - the section being optional;
  - wide fields that exist in the tableschema, and a long sheet not being checked;
  - unknown header field, value field, or both, rejected with the sheet named;
  - `from_server(to_server())` round trips with and without the section.
- `example_submission.yaml` now carries one long and one wide sheet, so the existing YAML round-trip test covers the section too. A new test checks that the example's sheets load.
- `ruff`, `mypy` and `pytest` pass.

## Notes for reviewer
- The section's shape is the format `cross_back` and contract authors will write, so the naming and nesting are the part that is expensive to change later:
  - `excel_processor` / `sheets` / `wide` / `header_field` / `value_field`;
  - `wide` is its own model so the header and value fields are always declared together.
- Sheets are keyed by fixed name on purpose. Template sheet names become part of the contract.
- No reader, no `openpyxl` dependency and no docs here. The reader is #112, and the docs will be a separate issue covering the submission work as a whole.
