# WP3 — `validate_submission`: the three-step sequence and its policy

## Context
**Part of PRD:** [2026-09-02-cross-submitter.md](../../prds/2026-09-02-cross-submitter.md)

The reason the class exists. Every step already works in isolation and is publicly
reachable; nothing composes them, and the two steps most easily forgotten — the bundle's
own schema, and unclaimed rows — are exactly the two whose omission fails silently. This
package adds the composition and the policy joining the steps. The submitter performs no
validation itself: step 1 belongs to the **Submission contract**, step 3 to the
**Submission handler**.

Depends on **WP1** (`UnclaimedRowsError`) and **WP2** (the class).

## Acceptance Criteria
- [ ] `validate_submission(contract, df, check_existing_primary_key=True,
      check_existing_foreign_key=True, lazy=True) -> dict[str, pd.DataFrame]` on
      `CrossSubmitter`.
- [ ] `contract` is typed `SubmissionContract` — the object, **not** `| str`. Name-based
      lookup is deliberately out of scope.
- [ ] Runs in order, stopping at the first failure:
      1. `contract.validate_data(df, resolver=self._resolver, ...)` → `SchemaValidationError`
      2. `handler.unclaimed_rows()` → `UnclaimedRowsError` carrying the frame
      3. `handler.validate_targets(self._resolver, ...)` → `TargetValidationError`
- [ ] Returns step 3's result unchanged: validated frames keyed by **target name**.
- [ ] All three flags are forwarded to **both** step 1 and step 3.
- [ ] Defaults are `True` / `True` / `True` — deliberately opposite to the `False`
      defaults on `validate_data` and `validate_targets`. The docstring must say *why*
      (a resolver always exists here, and a `False` flag suppresses the key check
      entirely rather than only its stored-value half — see ADR 0006).
- [ ] A `SubmissionHandler` is constructed **per call** on the raw `df` and not retained.
- [ ] Step 1's coerced return value is **discarded**; extraction runs on the bundle as
      delivered. The docstring states this and why (`submit` uploads the original bundle
      and the platform re-runs extraction on it).
- [ ] Docstring carries `Args:` / `Returns:` / `Raises:` listing all five exception types,
      and names which step each one identifies.

## Implementation Details

**Modify:** `src/crosscontract/submission/submitter.py`
**Modify:** `src/tests/submission/test_submitter.py`

- Reuse fixtures rather than authoring a fourth submission contract: the inline
  `SubmissionContract` fixtures in `src/tests/submission/test_validate_targets.py` and
  `src/tests/submission/example_submission.yaml`.
- Resolver double: the `Mock(spec=ContractResolver)` pattern from
  `test_validate_targets.py`. Inject by assigning `_resolver` on a constructed submitter,
  or by stubbing `client.contracts` where that reads more naturally — the constructor
  takes no resolver by design, and reaching for the private attribute in a test is the
  accepted cost of that decision.

### Required tests

**Sequencing — the core of the suite.** The *ordering* is the feature, so assert on spies
that later steps were never reached, not merely that the right exception surfaced:
- Happy path returns a dict keyed by target name.
- Bundle fails → `SchemaValidationError`, and `unclaimed_rows` / `validate_targets` were
  never called.
- Unclaimed rows → `UnclaimedRowsError` whose frame equals the expected rows, and
  `validate_targets` never called.
- Target data fails → `TargetValidationError`, one entry per failing target.
- Unresolvable target contract → `ValueError` propagates immediately, **not** collected
  (a wiring error, not a data error).

**Forwarding**
- Defaults reach both `validate_data` and `validate_targets` as `True/True/True`.
- Explicit `False/False/False` reaches both.

**Raw-bundle regression test — the subtlest decision in the PRD.** Build a bundle with an
integer-typed column containing a missing value, so step 1's coercion would widen it to
`float64` and break `astype(str)` filter matching. Assert the run succeeds and every
target claims its rows, i.e. the coerced frame was discarded. Comment it as a regression
test: it is what fails loudly if someone later "optimises" by feeding step 1's output into
the handler.

**Edge cases**
- Empty bundle → steps 1–2 pass vacuously, per-target empty frames, no raise.
- Contract with no targets + non-empty bundle → `UnclaimedRowsError` for every row.
- A target's `filters` naming a column absent from the bundle → `KeyError` propagates, and
  note it surfaces in **step 2** (`unclaimed_rows` masks every target), not step 3.

### Do not
- Do not add an `on_unclaimed=` flag, a `validate_bundle` method on the handler, a
  `targets=` selection parameter, or caching of resolver reads. Repeated `get_data` calls
  across steps are a known, accepted cost recorded in the PRD.
- Do not change `SubmissionHandler` behaviour. It reports; the submitter decides.
- Per CLAUDE.md, do not run `pytest` / `ruff` / `mypy` on your own initiative — ask first.
