# feat: condense validation error reports with max_errors

## Summary
`SchemaValidationError.to_list()` returns one row per failing cell, so one bad value
repeated across a large upload produces a huge report. cross_back has been shortening
these reports with its own `_condense_schema_errors`, which depends on this repo's row
keys and sort order. This PR moves that logic into crosscontract as an opt-in
`max_errors` keyword on `SchemaValidationError` and `TargetValidationError`. The
default output is unchanged. The PR also includes a small fix that silences a pandas
`FutureWarning` in the empty-string parser.

## Changes
- **`SchemaValidationError.to_list(max_errors=None)` / `to_pandas(max_errors=None)`**
  - `None` returns the full report exactly as before.
  - With an integer, rows sharing `(schema_context, column, check, failure_case)`
    merge into the first one. That row keeps its `index` (the first failing row) and
    gains a `count`.
  - At most `max_errors` distinct failing values are kept per `(check, column)`,
    whatever the `schema_context`. This includes the table-level key and hierarchy
    checks, which report one row per failing data row. Once the limit is reached, new
    values are dropped, while repeats of a kept value still add to its `count`.
  - A `failure_case` that can't be hashed (a `list` from a `ListField` check, or a
    key tuple holding one) is matched by its `repr`. The row keeps the original value.
  - Rows are copied, not modified, so the cached `errors` stay complete.
  - `max_errors < 1` raises `ValueError`.
  - `to_pandas` now wraps `to_list`, and its `# pragma: no cover` is removed.
- **`TargetValidationError.to_list(max_errors=None)` / `to_pandas(max_errors=None)`**
  pass `max_errors` to each target's `SchemaValidationError.to_list`, so the limit
  applies per target. With three failing targets, a column can show up to three times
  `max_errors` values.
- **Empty-string parser** (`PanderaAdapter.create_base_schema`): `df.replace("", np.nan)`
  becomes `df.mask(df == "")`.
  - On pandas 2.3.3, `replace` turned an all-null `object` column into `float64` and
    raised a deprecation `FutureWarning`; `mask` leaves the column's type alone.
  - The result doesn't change, because `coerce=True` converts the column to the
    field's type right afterwards.
  - This is also what pandas 3 does by default.
  - The now-unused `numpy` import is removed.
- **Task files** in `.ai-context/issues/condensed-validation-errors/`
  (01: `SchemaValidationError`, 02: `TargetValidationError`).

## Testing
- `src/tests/contracts/schema/exceptions/test_validation_error.py`, new class `TestMaxErrors`:
  - default output unchanged;
  - merging, first `index`, `count` and order;
  - rows merge only within the same check;
  - the limit applies per check and column, and repeats of a kept value still count
    after the limit;
  - table-level errors are limited;
  - the guard rejects `max_errors` of 0 and -1;
  - `to_pandas` matches `to_list`;
  - the cached `errors` aren't modified.
- Real validations through `TableSchema.validate_dataframe` cover:
  - `None`, `NaN` and `""` merging into one `None` row;
  - a repeated `ListField` violation (unhashable `list`);
  - a primary key duplicated three times, merged and limited.
- A mocked failure value that is a tuple holding a list.
- `src/tests/submission/test_exceptions.py`:
  - `TargetValidationError` default output unchanged;
  - limit applied per target;
  - `to_pandas` matches `to_list`.
- `pytest`, `mypy` and `ruff` pass locally (pandas 2.3.3).
- The full suite was also run against pandas 3.0.6 through a temporary
  `uv run --with "pandas>=3"` overlay: 1127 passed, with no warnings. That run came
  before the `mask` fix and the `TargetValidationError` changes.
  `uv.lock` still pins pandas 2.3.3.

## Notes for reviewer
- **Output changes with `max_errors` set.** Rows gain `count`, and `index` is the first
  failing row rather than every failing row. That's why merging is opt-in: with no
  argument, callers such as notebook users still get every row index.
- **`uv.lock`** changes only the project's own version (`0.22.0` → `0.23.0`). A local
  `uv run` synced it to the current release; it's unrelated to this feature.
- **Not in this PR:**
  - The two `ListField` length checks are unnamed and both report
    `check == '<lambda>'`, so min- and max-length failures share one limit group.
  - Wider pandas 3 support: `pyproject.toml` has no upper bound on pandas, but
    mypy against pandas 3 stubs wasn't checked.
- **Follow-up in cross_back:** once this is released from `main`, replace
  `_condense_schema_errors` with `e.to_list(max_errors=10)` in `validate_bundle`, and
  decide whether `contract_data.py` should do the same.

🤖 Generated with [Claude Code](https://claude.com/claude-code)
