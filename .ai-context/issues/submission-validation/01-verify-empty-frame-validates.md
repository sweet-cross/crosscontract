# Verify an empty frame passes a strict, coercing schema

## Context
**Part of PRD:** [submission-validation.md](../../prds/submission-validation.md) — WP1, edge case 9.

The design says a target claiming no rows is validated like any other and returns an empty
frame. That rests on reasoning, not observation: the base pandera schema is built with
`strict=True` and `coerce=True` ([adapter.py:38](../../../src/crosscontract/contracts/schema/adapters/pandera_pandas/adapter.py:38)),
and nobody has checked how those behave on zero rows. This is a **risk gate** — if the
assumption is wrong, the PRD's edge case 9 changes and WP2/WP3 change with it.

## Acceptance Criteria
- [ ] A test validates an empty `pd.DataFrame` carrying exactly the contract's columns
      against a contract with mixed field types (string, integer, number) and passes.
- [ ] The same is checked with a primary key declared and `primary_key_values=[]`, i.e. the
      in-frame uniqueness check running over zero rows.
- [ ] If either fails, **stop and report** rather than working around it: the finding goes
      back into the PRD's edge case 9 and this task blocks WP2/WP3.

## Implementation Details
- **Modify:** [src/tests/contracts/schema/validation/test_pandas_validation.py](../../../src/tests/contracts/schema/validation/test_pandas_validation.py) —
  this is a property of the validation layer, not of submission, so the test belongs here
  and stays as a permanent regression test.
- No source change. Test-only.
- Construct the frame with the right columns but no rows (`pd.DataFrame({"a": [], ...})` or
  an empty frame with explicit dtypes) — an empty frame with *no* columns is a different
  question and not what extraction produces, since `self.bundle[mask]` keeps the bundle's
  columns.
- **Verification:** `uv run pytest src/tests/contracts/schema/validation/test_pandas_validation.py`
- **Blocks:** tasks 04, 06.
