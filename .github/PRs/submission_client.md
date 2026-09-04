# Add `CrossSubmitter`, the provider-side entry point for submission validation

## Summary

Every step of a submission validation already worked and was publicly reachable, but
nothing composed them — and the two steps most easily forgotten (the bundle's own
schema, and rows no target claims) are exactly the two whose omission fails silently.
This branch adds `CrossSubmitter`, the write-side mirror of `CrossRegistry`: hand it a
`SubmissionContract` and a delivered bundle and it runs the whole sequence against
contracts fetched live from the platform. It also adds `UnclaimedRowsError`, the
exception step 2 needs, since an unclaimed row is silent data loss once the platform
re-runs extraction server-side.

`submit` itself is an honest stub — the CROSS platform exposes no submission endpoint
yet.

## Changes

**New `CrossSubmitter`** (`submission/submitter.py`)
- Constructed exactly like `CrossRegistry` — from credentials or an existing
  `CrossClient`, no `base_url` — and builds its own `CrossContractResolver` over that
  client. No `close()` and no context manager: a client handed in is not the submitter's
  to close.
- `validate_submission(contract, df, ...)` runs three steps in order, stopping at the
  first failure: the bundle against the submission contract's own schema, the bundle for
  unclaimed rows, then each target's extracted data against the contract it names. It
  returns step 3's result unchanged, keyed by target name.
- The `check_existing_*` flags default to `True` here, against the `False` used
  everywhere else in the package. Those defaults exist because a resolver is optional
  elsewhere; on the submitter one always exists. It matters — a `False`
  `check_existing_primary_key` suppresses uniqueness *entirely*, not merely its
  stored-value half.
- Extraction runs on the bundle **as delivered**: step 1's coerced frame is discarded,
  because target filters match a column's string form and a coerced value can change
  which target claims a row.
- A `SubmissionHandler` is built per call and not retained.

**New `UnclaimedRowsError`** (`submission/exceptions.py`)
- Carries the unclaimed rows as a `pd.DataFrame`, not a count or a formatted string,
  plus `to_list()` / `to_pandas()`. Mirrors `TargetValidationError`, its sibling in the
  same module.

**Public surface**
- `CrossSubmitter` and `UnclaimedRowsError` are exported from `crosscontract.submission`
  and from the top-level package, both in `__all__`.

**Docs and conventions**
- ADR 0007 records why the submitter is named as it is, why it lives in `submission/`
  rather than in `crossclient/` or its own package, and the cost that decision accepts:
  `submission/` is now the one domain package that imports the client layer.
- CONTEXT.md gains the **Submitter** term and sharpens **Submission validation** — the
  policy joining the steps is the caller's, and the submitter is the caller that makes
  it.
- CLAUDE.md's docstring convention now separates *what a thing does* from *why it was
  built that way*: rationale, rejected alternatives and sibling-class comparisons stay
  out of docstrings, while a consequence a caller must act on stays in. Written after a
  review turned up docstrings explaining decisions to people who only wanted to call the
  code.

## Testing

New `src/tests/submission/test_submitter.py` (241 lines):

- **Construction** — credentials build a client, an injected client is used as-is and
  wins over credentials, incomplete credentials raise `ValueError`, the resolver is
  wired to that client's `contracts` and is not a constructor parameter.
- **Sequencing**, which is the feature: each failure asserts the later steps were never
  *reached*, via spies, not merely that the right exception surfaced. Covers the happy
  path, a failing bundle (no handler is even built), unclaimed rows (targets never
  attempted), collected per-target failures, and an unresolvable target contract
  escaping uncollected as a wiring error.
- **Flag forwarding** — defaults and explicit values reach both step 1 and step 3.
- **A regression test** for feeding step 1's output into the handler: `validate_data` is
  patched to return a frame whose routing column is mangled and whose `year` has widened
  to `float64`. If that frame reached the handler, no target would claim anything.

`test_exceptions.py` gains a `TestUnclaimedRowsError` class. Shared fixtures moved from
`test_validate_targets.py` into a new `src/tests/submission/conftest.py`, now that two
modules use them; the call sites in that module are unchanged.

## Notes for reviewer

- **Two edge cases from the plan are unreachable and deliberately untested.**
  `ExtractionInstructions.targets` carries `min_length=1`, so a contract with no targets
  cannot be constructed; and `SubmissionContract._check_filters` rejects a filter column
  absent from the schema at construction, so the `KeyError` path in step 2 cannot
  surface through `validate_submission`. The `KeyError` clause was removed from the
  docstring for that reason.
- **`submitter.py` imports `from crosscontract import CrossClient`**, matching
  `registry.py`. This works only because `crosscontract/__init__.py` loads `.crossclient`
  before `.submission` — inert until this branch exported `CrossSubmitter`, load-bearing
  now. `from crosscontract.crossclient import CrossClient` would remove the constraint
  and fold in the resolver import on the next line. Left alone as out of scope; worth a
  decision.
- **`submit()`** has no `-> None` annotation, and its `NotImplementedError` message
  restates the exception type rather than naming the platform gap. The docstring says it;
  the message a caller sees does not.
- **No docs page.** `docs/` covers `CrossRegistry` but nothing on the provider side.
  Deferred to `.ai-context/TODO.md` rather than expanding this branch.
- Repeated `get_data` calls across steps (once in step 1, once per target) are a known,
  accepted cost — no caching in this change.
