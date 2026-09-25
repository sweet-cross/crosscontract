# Condense `SchemaValidationError` reports with `max_errors`

## Context
**Part of PRD:** none. Agreed in a discuss-and-plan session on 2026-09-25; related
background in [`validation-reporting.md`](../../prds/validation-reporting.md).

cross_back shrinks `SchemaValidationError.to_list()` with its own
`_condense_schema_errors` (`cross_back/backend/app/api/crud/submission.py`), which
depends on this repo's report row keys and sort order. The logic moves here as an
opt-in keyword so every consumer can bound a report without knowing its internals.
Same PR as `02-target-validation-error-max-errors.md`.

## Acceptance Criteria
- [ ] `SchemaValidationError.to_list(max_errors: int | None = None)` and
      `to_pandas(max_errors: int | None = None)` exist.
- [ ] `max_errors=None` returns exactly today's output: no `count` key, one row per
      failure, same order.
- [ ] With an integer, rows sharing `(schema_context, column, check, failure_case)`
      merge into the first one, which keeps its `index` (the first failing row) and
      gains `count` (the number of rows merged). Rows keep their original order.
- [ ] With an integer, at most `max_errors` distinct `failure_case` values are kept per
      `(check, column)`, **whatever the `schema_context`** — `Column` and
      `DataFrameSchema` (key / hierarchy checks) alike. Rows beyond the limit are
      dropped; repeats of a value already kept still add to its `count`.
- [ ] An unhashable `failure_case` (a `list` from a `ListField` check) does not raise:
      the merge key uses `repr(failure_case)` for it, and the row keeps the original
      value.
- [ ] Calling `to_list(max_errors=...)` does not mutate the cached `errors`: a
      following `to_list()` still returns the full report.
- [ ] `to_pandas(max_errors)` returns `pd.DataFrame(self.to_list(max_errors))`.
- [ ] Google-style docstrings (markdown only, `Args:` / `Returns:`) state that the
      limit counts distinct failing values per check and column, not total rows, and
      that in condensed mode `index` is the first failing row and `count` is added.
- [ ] Tests (see below) pass.

## Implementation Details
- Modify `src/crosscontract/contracts/schema/exceptions/validation_error.py`:
  - `to_list` does the condensing inline over `self.errors`; build new dicts
    (`{**error, "count": 1}`) rather than editing cached rows.
  - `to_pandas` wraps `to_list`; drop its `# pragma: no cover` once tested.
  - Match the house style: no new module constants or helper classes; a private
    helper only if `to_list` becomes unreadable without one.
- Reference implementation to port and adjust:
  `cross_back/backend/app/api/crud/submission.py::_condense_schema_errors`.
  Differences agreed: the limit applies to every `schema_context` (drop the
  `== "Column"` branch), the unhashable-key fallback is new, and the NaN comment goes
  (nulls already arrive as `None`, see below).
- Verified behaviour of the current report (scratch run, 2026-09-25):
  | Case | `schema_context` | `failure_case` |
  |---|---|---|
  | `None` / `NaN` / `""` in a required number column | `Column` | `None` |
  | `ListField` `maxLength` violated by `[1, 2, 3]` | `Column` | `[1, 2, 3]` (`list`, unhashable) |
  | primary key `a` occurring 3 times | `DataFrameSchema` | `('a',)`, one row per occurrence |
- Tests in `src/tests/contracts/schema/exceptions/test_validation_error.py`:
  - default output unchanged (no `count`, all rows);
  - repeated values merged, correct `count`, first `index`, original order;
  - limit applied per `(check, column)` group, independently for two groups;
  - `None`, `NaN` and `""` in a required number column merge into one row;
  - a `ListField` `maxLength` violation on two rows gives one row with `count == 2`;
  - a primary key duplicated 3 times gives one row with `count == 3`
    (`primary_key_values=[]`), and more distinct duplicated keys than `max_errors`
    are cut to `max_errors`;
  - cached `errors` unchanged after a condensed call;
  - `to_pandas(max_errors)` matches `to_list(max_errors)`.
- Dependencies: none. Blocks `02-target-validation-error-max-errors.md`.
- Out of scope (noted, not to be done here): the `ListField` length checks are
  unnamed and report as `check == '<lambda>'`
  (`src/crosscontract/contracts/schema/adapters/pandera_pandas/field_convertors.py`),
  so min- and max-length failures share one limit group.
