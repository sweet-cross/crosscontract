# WP2 — `SubmissionHandler` and target selection

## Context

**This is the critical path.** It introduces the class that executes a submission
contract, and it fixes the primitive every later piece sits on.

[ADR 0004](../../adrs/0004-submission-contracts-carry-extraction-instructions.md) closes
with "Execution is not in this package yet… when it arrives it joins `submission/`
alongside the spec models". This is that arrival.

The handler is deliberately **per-target**: it exposes one target at a time and never
loops over all of them. Whether a run aborts on the first failing target or collects
every failure and reports them together is the caller's decision, not the library's —
and with no aggregate return type there is nothing to retrofit when that choice changes.

### Engine: pandas, and not deferred

The bundle is a CSV of roughly 15 MB. DuckDB and friends were considered and rejected —
not on size, but structurally: `BaseTransformation.apply` is typed
`pd.DataFrame -> pd.DataFrame`, all six transformations are pandas functions, and
`ContractService._add_data` serializes a `pd.DataFrame` to parquet on the way out.
Adopting another engine would mean either reimplementing every transformation in SQL —
forking the transformation layer and raising the price of adding a seventh, which cuts
against the extensibility goal ADR 0004 names — or round-tripping back to pandas per
target, which buys nothing. This stays true well beyond the current data size, so it is
**settled**, not deferred.

## Acceptance Criteria

- [ ] `SubmissionHandler(specs: SubmissionContract, df: pd.DataFrame)` stores
      `self.specs` and `self.bundle`.
- [ ] A private per-target **boolean mask** is the single implementation of the filter
      semantics.
- [ ] `extract_target_data(target_name)` returns the rows the target claims, before any
      transformation.
- [ ] `unclaimed_rows` moves here from `SubmissionContract` and is re-expressed on the
      mask.
- [ ] `SubmissionContract` no longer imports pandas.
- [ ] `SubmissionHandler` is exported from `submission/__init__.py` and the top-level
      `crosscontract/__init__.py`, where `SubmissionContract` already sits.

## Implementation Details

**Create:**

- `src/crosscontract/submission/submission_handler.py` (matching the existing
  `submission_contract.py` naming)

**Modify:**

- `src/crosscontract/submission/submission_contract.py` — remove `unclaimed_rows` and
  the `import pandas as pd` it brought in
- `src/crosscontract/submission/__init__.py`, `src/crosscontract/__init__.py` — exports
- `src/tests/submission/` — see below

### The mask is the primitive, not the frame

Both public methods sit on a private per-target boolean mask:

- `extract_target_data(name)` → `self.bundle[mask(target)]`
- `unclaimed_rows` → `self.bundle[~ OR of every target's mask]`

Folding *frames* instead would mean set-differencing ~24 materialized frames to find the
leftovers — wasteful and awkward. The mask keeps one implementation of the filter
semantics (string-form cast, conjunction across entries, the hoisted per-column cast) so
selection and coverage cannot drift apart. Drift here would be silent and is exactly the
class of bug this line of work exists to prevent: extraction claiming a different row set
than coverage reports as claimed.

Carry the semantics over from the shipped `SubmissionContract.unclaimed_rows` verbatim —
`df[col].astype(str) == value`, all entries must match, filter columns cast once rather
than once per (target, filter) pair.

### Why `unclaimed_rows` moves, and why now

`contracts/` is not pandas-free — `TableSchema.validate_dataframe` exists and the
adapters are pandas by definition — but every one of those contacts is **adapter-mediated
and backend-parameterized** (`validate_dataframe` carries
`backend: Literal["pandas"] = "pandas"`). `unclaimed_rows` is neither: raw `pd.Series`
accumulation inside a spec model. It belongs where execution-flavoured pandas lives.

**The move is free right now and will not stay free.** `unclaimed_rows` shipped in
`v0.16.1`, which is tagged on `dev` — but `main` is still at `#71`, so it has **not**
published to PyPI. Once `dev` fast-forwards into `main` it becomes a released public
method on a re-exported class, and removing it owes a deprecation cycle (the repo's
precedent is the `FutureWarning` on `CrossDataVariable`'s construction-time `filters`,
[issue #77](https://github.com/sweet-cross/crosscontract/issues/77)). Land this before
the next promotion.

### Open at implementation time

- **`unclaimed_rows` as a property or a method.** Authored as a property. It recomputes
  every mask plus a string cast of each filter column on each access, and `self.bundle`
  is a public attribute that could be reassigned, so caching would risk staleness. At this
  data size neither matters. Decide when writing it; nothing downstream depends on which.

### Tests

**Move the five `TestUnclaimedRows` cases** from
`src/tests/submission/test_submission_contract.py` to a handler test module, rewritten to
construct a `SubmissionHandler`. They must pass **unchanged in substance** — that is the
regression proof that relocating the computation did not alter it. The `coverage_data`
contract and the `bundle()` builder move with them.

Add selection tests for `extract_target_data`: a target claiming several rows, a target
claiming none (empty frame, not an error), and a target whose filter names a non-routing
column.

**Dependencies:** WP1.

**Verification:** `uv run pytest src/tests/submission/` plus `uv run mypy
src/crosscontract/`. *Ask before running — see CLAUDE.md.*
