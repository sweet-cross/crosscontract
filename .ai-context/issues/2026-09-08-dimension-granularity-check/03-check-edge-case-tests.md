# Cover the check's edge cases

## Context

**Part of PRD:** [.ai-context/prds/2026-09-08-dimension-granularity-check.md](../../prds/2026-09-08-dimension-granularity-check.md)

WP1, step 3. `01` pinned the rule; this grows the file to the full unit list in PRD §7 so
the transitivity, null and cycle behaviour is nailed down before any plumbing is built on
top of it.

## Acceptance Criteria

Each of these is a test in `test_granularity_checks.py`:

- [X] Two siblings in one group (`ch_ag` + `ch_other`) → all pass. An antichain is legal.
- [X] Grandparent + grandchild with the parent absent (`ch` + `ch_ag_zurich`) → the
  grandparent fails. Proper ancestry is transitive.
- [X] `ch` + `ch_other` → `ch` fails. The user-facing motivating example.
- [X] Member absent from the parent map → passes ("unknown member" is `IsSubsetOf`'s
  defect).
- [X] Null in the dimension column → passes, **asserted on the predicate's own return
  value** rather than on pandera behaviour.
- [X] Null in a *group* column → rows sharing that null are grouped together and compared,
  not dropped.
- [X] Empty-string parent treated as no parent (chain terminates).
- [X] Cyclic parent map → terminates and does not hang.
- [X] Empty DataFrame → passes.
- [X] A group of one row → passes.
- [X] Duplicate rows (same group, same member) → pass; a member is not its own proper
  ancestor, and `IsUnique` owns that defect.
- [X] Multi-column group.
- [X] `to_pandera()` returns exactly one check whose `error` equals `failure_message()`.

## Implementation Details

- Modify: `src/tests/contracts/schema/validation/checks/test_granularity_checks.py`.
- Reuse the §7 parent map fixture from `01`; add a small cyclic map fixture for the cycle
  case (e.g. `{"a": "b", "b": "a"}`) and guard it with a timeout-free assertion — the
  `seen` set is what makes it terminate.
- Depends on `02`.
- Do not run pytest without asking (repo `CLAUDE.md`).
