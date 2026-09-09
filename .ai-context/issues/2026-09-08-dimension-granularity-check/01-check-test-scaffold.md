# Scaffold the granularity check test file

## Context
**Part of PRD:** [.ai-context/prds/2026-09-08-dimension-granularity-check.md](../../prds/2026-09-08-dimension-granularity-check.md)

WP1, step 1. The check is a pure predicate over a DataFrame plus a parent map — no
adapter, no resolver — so it can be specified by test before any of it exists. This task
writes only the two cases that pin the rule down: the violation, and the false positive
that must not happen. Everything else in PRD §7 comes later, in `03`.

## Acceptance Criteria
- [ ] `src/tests/contracts/schema/validation/checks/test_granularity_checks.py` exists.
- [ ] It carries the three-level parent map fixture from PRD §7:
      `{"ch": None, "de": None, "other": None, "ch_ag": "ch", "ch_other": "ch",
      "ch_ag_zurich": "ch_ag", "ch_ag_other": "ch_ag"}`.
- [ ] Case 1 — aggregate and descendant in **one** group: `(A, 2030, ch)` and
      `(A, 2030, ch_ag)`. Asserts **per row** that the `ch` row fails and the `ch_ag` row
      passes. Asserting "something failed" is not sufficient.
- [ ] Case 2 — aggregate and descendant in **different** groups: `(A, 2030, ch)` and
      `(B, 2030, ch_ag)`. Asserts every row passes. This is the core false-positive guard.
- [ ] Case 3 — two **models** reporting at different granularities under the same
      scenario: `(m1, A, 2030, ch)` and `(m2, A, 2030, ch_ag)`. Asserts every row passes.
      Models are alternative estimates, never additive parts, so this must not be flagged;
      it is the case that motivated the group derivation and is only safe because `model`
      is a group column.
- [ ] The frame carries a `model` column and `group_columns` is `["model", "scenario",
      "year"]`, so every case above runs against a realistic multi-column group.
- [ ] No other cases in this task.
- [ ] The tests fail (import error is fine) until `02` lands.

## Implementation Details
- Create: `src/tests/contracts/schema/validation/checks/test_granularity_checks.py`.
- Follow the style of the neighbouring `test_dimension_checks.py`: a class per behaviour,
  a `pytest.fixture` for the check, a small `_make_df` row-dict helper.
- The check is constructed as
  `HasNoDescendantInGroup(label=..., column="region", group_columns=["scenario", "year"],
  parent_map=PARENT_MAP)` and called directly as `check(df)`, which returns a boolean
  `pd.Series` — one entry per row, `True` meaning the row passes.
- Settled here and binding on `02`: the module is `granularity_checks.py`, so the test
  file is `test_granularity_checks.py` — the repo pairs the two one-to-one.
- Do not run pytest without asking (repo `CLAUDE.md`).
