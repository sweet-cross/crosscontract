# Read CSV with the Frictionless NA default

## Context
**Part of PRD:** GitHub issue sweet-cross/crosscontract#134 (no PRD file)

The file readers follow the Frictionless default `missingValues: [""]`: only an empty
cell is a missing value. This task introduces the shared NA setting and applies it to
the CSV reader; task 03 applies it to Excel.

## Acceptance Criteria
- [ ] `handlers/readers/constants.py` holds the shared NA list, `[""]`.
- [ ] `read_csv_file_bytes` reads with `keep_default_na=False` and that list.
- [ ] An empty CSV cell becomes a missing value; a numeric column with an empty cell
      is read as numbers, not strings.
- [ ] The 17 former tokens (`#N/A N/A`, `#NA`, `-1.#IND`, `-1.#QNAN`, `-NaN`, `-nan`,
      `1.#IND`, `1.#QNAN`, `<NA>`, `N/A`, `NULL`, `NaN`, `None`, `n/a`, `nan`, `null`,
      `undefined`) are read as strings; `"NA"` stays a string.
- [ ] The `read_csv_file_bytes` docstring describes the new rule and drops the token
      list and the "single empty cell turns a numeric column into strings" sentence.

## Implementation Details
- Create `src/crosscontract/handlers/readers/constants.py` with the shared constant.
- Modify `src/crosscontract/handlers/readers/csv_reader.py`: remove `_NA_VALUES`,
  import the constant.
- Tests in `src/tests/handlers/readers/test_readers.py`:
  - `test_empty_cell_stays_an_empty_string` → an empty cell becomes missing.
  - `test_na_tokens_become_missing` → the same tokens stay strings.
  - `test_na_stays_a_string` unchanged.
- The pandera `""` → null parser in
  `contracts/schema/adapters/pandera_pandas/adapter.py` stays: parquet and DataFrame
  input still need it.
- Behaviour to name in the PR's `BREAKING CHANGE:` footer: a former token in a
  `number`, `integer` or `datetime` field is now a validation error instead of a null;
  in a `string` field it is stored as text.
- Dependencies: none. Can be done alongside 02.
