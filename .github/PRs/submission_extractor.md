# Add `SubmissionHandler` to execute a submission contract against a bundle

## Summary

Submission contracts described how a delivered bundle splits into per-variable datasets,
but nothing executed that description — ADR 0004 closed with "execution is not in this
package yet". This branch adds `SubmissionHandler`, which holds a `SubmissionContract`
and a bundle and answers per target: select the rows the target claims, apply its
transformation profile and then its own transformations.

It also moves `unclaimed_rows` off `SubmissionContract`. The spec models' contact with
pandas is otherwise adapter-mediated and backend-parameterized (`validate_dataframe`
carries `backend: Literal["pandas"]`); `unclaimed_rows` was raw `pd.Series` accumulation
sitting in a spec model, and unclaimed rows are a property of a bundle *paired with*
instructions rather than of the contract alone.

## Changes

**`ExtractionInstructions.get_target(name)`** — the spec-side lookup, on the model that
owns `targets`. Raises `KeyError` for an unknown name. Target names are already validated
unique, so no tie-breaking is needed.

**`SubmissionHandler(specs, df)`** in a new `submission/submission_handler.py`, exported
from `submission/__init__.py` and the top-level package:

- `extract_target_data(name)` — rows the target claims, untransformed.
- `transform_target_data(df, name)` — profile steps first, then the target's own.
- `get_target_data(name)` — the composition.
- `unclaimed_rows()` — rows no target claims, moved here from `SubmissionContract`.

Two design points that are decisions rather than details:

- **The handler is per-target and never loops over all of them.** Whether a run aborts on
  the first failing target or collects every failure and reports them together is the
  caller's, not the library's — and with no aggregate return type there is nothing to
  retrofit when that choice is made.
- **A private per-target boolean mask is the single implementation of the filter
  semantics.** `extract_target_data` indexes with one mask; `unclaimed_rows` inverts the
  OR of all of them. Writing the two independently would put the string-form cast and the
  conjunction in two places, and drift between them would be silent — extraction claiming
  a different row set than coverage reports as claimed.

The hoisted per-column string cast from the shipped `unclaimed_rows` was **not** carried
over. The cast covers only filter columns — one column in the cross2025 spec, since the
routing column is required to be string-typed and the cast is near-free there — so the
state a cached string frame costs outweighs what it saves. Recomputing inside the mask is
stateless and leaves hoisting as a local change if profiling ever asks for it.

**Documentation.** CONTEXT.md gains a *Submission handler* term; the three `_Avoid_`
lines that banned "extractor" now point at it rather than leaving a banned word with no
replacement. ADR 0004's "execution is not in this package yet" becomes three consequences
— what landed, pandas as settled, and the resolver constraint (below). `TODO.md` drops the
raise-or-warn item as answered and reprices contested rows.

## Testing

`src/tests/submission/test_submission_handler.py`, built on a fixture with two
transformation profiles and four targets covering every shape: profile only, own
transformations only, both, and neither.

- **Transformation** — one test per shape. The both-case is the order test: `t_year`'s
  own step casts `period`, a column that exists only after the `annual` profile renamed
  `year` to it, so a reversed order raises on a missing column rather than returning a
  subtly different frame.
- **Extraction** — a target claiming rows, claiming none, claiming via a non-routing
  typed column, and an unknown name.
- **Composition** — that `get_target_data` equals transform-of-extract, plus a direct
  assertion on the result so a refactor changing both halves compensatingly still fails.
- **Coverage** — the five `unclaimed_rows` cases moved from
  `test_submission_contract.py` unchanged in substance, which is the regression proof
  that relocating the computation did not alter it, plus a new case pinning that a row
  claimed by two targets counts as claimed.
- Non-mutation on both the transform and coverage paths.

Suite green locally.

## Notes for reviewer

**Base is `dev`, not `main`.**

**`SubmissionHandler` has no class or `__init__` docstring.** Every other public class in
the package carries one, and CLAUDE.md requires them. Known gap, not an oversight in
review.

**The handler resolves nothing, deliberately.** ADR 0004's second named decision is that
target contracts are named and never looked up, so a spec loads and runs with no platform
connection. If a `validate_target_data` is added later, the contract must arrive from the
caller — passed in, or via the `ContractResolver` protocol `BaseContract` already defines
for `validate_references`. A lookup inside `submission/` would quietly undo the property
the format is built around. This is now written into the ADR rather than left to memory.

**`transform_target_data(df, name)` takes the frame and the name independently**, so a
caller can pass one target's rows with another target's name and get a plausible-looking
wrong answer. Left unguarded; worth a second opinion on whether it should be.

**For a target with neither a profile nor transformations, `transform_target_data`
returns the frame it was handed rather than a copy** — the one path in this module that
doesn't return a new DataFrame, against the convention every transformation in
`transformations/` states explicitly. Only observable when called directly; via
`get_target_data` the frame is already a boolean-indexed copy.

**Still deferred, in `TODO.md`:** contested-row detection (now a sum over the masks rather
than a loop reshape, so what remains is the decision, not the plumbing), and load-time
filter-value parseability.
