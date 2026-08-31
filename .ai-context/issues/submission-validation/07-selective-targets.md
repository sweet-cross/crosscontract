# Selective target validation

## Context
**Part of PRD:** [submission-validation.md](../../prds/submission-validation.md) — WP3, edge cases 13–14.

`validate_targets` takes `targets: list[str] | None`, so a caller can re-check the three
targets they just fixed instead of the whole bundle. Split from task 06 to keep the loop's
core semantics and its selection semantics separately reviewable.

## Acceptance Criteria
- [ ] `targets=None` validates every target, in declaration order.
- [ ] A named subset validates only those targets, and the resolver is **not** asked to
      resolve the contracts of the others — asserted through the recording double.
- [ ] `targets=[]` returns `{}` — empty means empty, `None` means all.
- [ ] An unknown name in the list raises `KeyError` (inherited from `get_target`), not a
      silent skip.
- [ ] A name repeated in the list is harmless: the returned dict collapses it. No dedupe
      guard, and the test must not pin whether the target was validated once or twice.
- [ ] The docstring states the `None` vs `[]` distinction explicitly — it is the kind of
      thing a caller guesses wrong.

## Implementation Details
- **Modify:** [src/crosscontract/submission/submission_handler.py](../../../src/crosscontract/submission/submission_handler.py),
  **modify:** `src/tests/submission/test_validate_targets.py`.
- Selection is a filter over `self.contract.extraction.targets` by name; resolve nothing for
  the unselected ones. The point of the "not asked" assertion is that a subset run stays
  cheap on the wire.
- **Unclaimed rows stay out of this method.** They are a bundle-level property, reported
  separately by `unclaimed_rows`, and folding them in reads especially badly here — you
  asked about three targets and would get an error about rows destined for a fourth.
- **Depends on:** task 06.
- **Verification:** `uv run pytest src/tests/submission/test_validate_targets.py`
