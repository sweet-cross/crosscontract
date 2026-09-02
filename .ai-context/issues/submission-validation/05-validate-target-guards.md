# Guard the contract argument on `validate_target`

## Context
**Part of PRD:** [submission-validation.md](../../prds/submission-validation.md) — WP2, edge cases 1–5.

Because `contract` wins over `resolver`, a caller can hand one target's rows to another
target's contract and the validation will happily pass. That is silently wrong rather than
a crash — the [ADR 0005](../../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md)
criterion for knowledge the library must own — so it is guarded here, together with the two
other ways the contract can fail to arrive.

## Status

The guards themselves landed with task 04 — all three `ValueError` branches are in
`validate_target` and no `check_existing_*` guard was added. **Only the tests are
outstanding.**

## Acceptance Criteria
- [X] `contract.name != target.contract` raises `ValueError` naming both.
- [X] `resolver.resolve(target.contract)` returning `None` raises `ValueError` naming the
      target **and** the contract it names.
- [X] Neither `contract` nor `resolver` given raises `ValueError` naming both remedies.
- [ ] An unknown `target_name` still surfaces as `KeyError` from
      `ExtractionInstructions.get_target` — unchanged, and asserted so the two stay
      distinguishable. *(Behaviour holds; the assertion is missing.)*
- [X] **No guard is added** for `check_existing_*=True` with a contract but no resolver:
      `validate_data` already raises there, naming the contract and both remedies, and a
      second guard would produce two messages for one mistake. ~~Assert the existing message
      surfaces.~~ *(Guard correctly absent; the assertion is missing.)*
- [ ] One test per case.

## Implementation Details
- **Modify:** [src/crosscontract/submission/submission_handler.py](../../../src/crosscontract/submission/submission_handler.py),
  **modify:** `src/tests/submission/test_validate_targets.py`.
- `ValueError` for the unresolvable case, deliberately **not** `KeyError`: that is already
  the "no such target" signal, and a caller catching around a loop must be able to tell
  "you asked for a target that does not exist" from "the platform does not have that
  contract".
- Expect review pushback on the mismatch guard — CLAUDE.md bans defensive branches. The
  answer is the ADR 0004 amendment and ADR 0005's criterion; cite them in the PR rather
  than in the code.
- Note the counter-precedent honestly: `transform_target_data` *documents* the analogous
  mistake instead of guarding it. The difference is that a DataFrame carries no identity,
  while here `target.contract` is in hand.
- **Depends on:** task 04.
- **Verification:** `uv run pytest src/tests/submission/test_validate_targets.py`
