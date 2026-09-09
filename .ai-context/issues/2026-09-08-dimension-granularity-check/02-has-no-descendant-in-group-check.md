# Implement HasNoDescendantInGroup

## Context
**Part of PRD:** [.ai-context/prds/2026-09-08-dimension-granularity-check.md](../../prds/2026-09-08-dimension-granularity-check.md)

WP1, step 2. The check itself: within one group of otherwise-identical rows, no dimension
member present may be a proper ancestor of another member present. It reports the
**aggregate** row, because that is the row the submitter has to remove.

## Acceptance Criteria
- [ ] A new module under `src/crosscontract/contracts/schema/validation/checks/` defines
      `HasNoDescendantInGroup(BaseCheck)`.
- [ ] `name: Literal["has_no_descendant_in_group"] = "has_no_descendant_in_group"`.
- [ ] Fields: `column: str`, `group_columns: list[str]`, `parent_map: dict[Any, Any]`.
      **No `existing` field** — the stored-rows half is deferred (PRD §4).
- [ ] `__call__(df) -> pd.Series` returns one boolean per row; the aggregate row fails.
- [ ] A member absent from `parent_map` passes; a null member passes; an empty-string or
      null parent terminates the chain; a cyclic parent map terminates rather than hangs.
- [ ] Nulls are decided **inside `__call__`**, not delegated to `ignore_na` (PRD §3).
- [ ] `failure_message()` names the column and states the remedy in one line (PRD §3).
- [ ] `to_pandera()` is **not** overridden — one rule, one message, so the inherited
      single-check implementation is correct.
- [ ] Exported from `checks/__init__.py` and added to its `__all__`.
- [ ] The two tests from `01` pass.

## Implementation Details
- Create: `src/crosscontract/contracts/schema/validation/checks/granularity_checks.py`.
  The filename was settled in `01` (the PRD left it open): `hierarchy_checks.py` reads
  confusingly next to `dimension_checks.py`, which is about a dimension's *own* table while
  this is about a *fact table referencing one*. The test file is `test_granularity_checks.py`.
- Modify: `src/crosscontract/contracts/schema/validation/checks/__init__.py`.
- Algorithm (PRD §4) — sets, not joins:
  1. Build proper-ancestor chains from `parent_map` once, carrying a `seen` set so a cycle
     terminates (as `CrossDimension._build_ancestry_chains` does).
  2. `implied = {(group_key, ancestor)}` over every row of the frame and every proper
     ancestor of its member.
  3. A row fails iff `(its group_key, its own member)` is in `implied`.
  `O(rows x depth)` with hash lookups. No `explode`, no `merge`.
- Group the rows on the raw values of `group_columns` so a null group key is compared
  rather than dropped — `groupby` drops null keys by default, which is the bug called out
  for `EachLevelHasOther` in ADR 0006's consequences. A set-based grouping sidesteps it.
- `checks/` depends on pandas, pandera and pydantic only. The parent map is a plain
  `dict`; `CrossDimension` lives in `registry/`, a layer above, and must not be imported
  here (ADR 0006).
- Do not run pytest without asking (repo `CLAUDE.md`).
