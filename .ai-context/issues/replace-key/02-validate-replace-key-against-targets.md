# WP2 — Check `replace_key` against the target contracts in `validate_references`

## Context
**Source:** [sweet-cross/crosscontract#108](https://github.com/sweet-cross/crosscontract/issues/108) — no PRD; follows
[01-replace-key-field.md](01-replace-key-field.md).

WP1 gives `replace_key` a well-formed value but says nothing about whether the columns
it names actually exist where the backend will look for them. That check needs the
target contracts, so it belongs in `validate_references`, which already takes a
`ContractResolver` and already loops the targets resolving each one. A `replace_key`
column that a target does not declare, or declares as optional, makes the replace
unreliable: a null key tuple either matches nothing and leaves stale rows behind, or
matches too much.

## Acceptance Criteria
- [ ] When `replace_key` is a list, `validate_references` reports every target whose
      contract does not declare every `replace_key` column.
- [ ] It also reports every target whose contract declares a `replace_key` column with
      `constraints.required` false.
- [ ] Those errors are collected into the same aggregate `ValueError` as the
      unresolved-contract errors, not raised early — a contract with both kinds of
      problem reports both in one exception.
- [ ] A target whose contract does not resolve produces only the unresolved-contract
      error; the column check is skipped for it rather than failing on `None`.
- [ ] `replace_key == "all"` skips the check entirely.
- [ ] Each error names the target and the offending column(s).

## Implementation Details
- Files to modify:
  - `src/crosscontract/submission/submission_contract.py` — `validate_references`
    (around line 139). The new checks go inside the existing `for target in
    self.extraction.targets` loop, appending to the existing `errors` list.
  - `src/tests/submission/test_submission_contract.py` — or
    `test_validate_targets.py`, wherever the existing `validate_references` tests live.
  - `src/tests/submission/conftest.py` — the `resolver_for(...)` /
    `target_contract(...)` helpers (lines ~88–158) already build target contracts from
    field dicts; reuse them for the missing-column and optional-column cases.
- Read the declared fields off the resolved contract's `tableschema`; `required` lives
  on the field's `constraints` (`Constraints.required`,
  `src/crosscontract/contracts/schema/fields/base.py:23`).
- `Constraints.required` defaults to `False`, and the schema does **not** force
  primary-key fields to be required (`contracts/schema/schema.py:151`), so the
  `required` half of the check is load-bearing even when the key column is part of the
  target's primary key. Do not treat primary-key membership as implying required.
- A `Dimension` target resolves with a usable `tableschema`: `from_server` strips it
  only so the fixed template can be rebuilt (`cross_contract.py:158`). So no special
  case is needed for dimension targets — and a `Dimension` target under a scoped
  `replace_key` will correctly fail, since the template declares only
  `id`/`level`/`parent_id`/`label`/`description`. That is intended; there is no
  per-target opt-out.
- `CrossSubmitter.validate_submission` already calls `validate_references` first, so
  authors hit this on their normal path. No change needed there.
- Keep the loop plain — no helper function; the two conditions are a few lines inside
  the existing body.
- Dependencies: must be completed after `01-replace-key-field.md`.
