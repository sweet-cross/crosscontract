# feat: Always check primary keys within the data and validate submission target references

## Summary
Server-side submission validation needs two things `crosscontract` could not provide.
First, each target's rows must have unique, non-null primary keys without being compared
against stored data — but `validate_data(check_existing_primary_key=False)` dropped the
primary-key check entirely. Second, nothing verified that the contracts a Submission
Contract's targets name actually exist: the inherited `validate_references` only walks
foreign keys, which a bundle schema never declares, so it passed for any Submission
Contract. This branch fixes both and has `CrossSubmitter` run the reference check first.

## Changes
- **Primary key always checked within the data.** `BaseContract.validate_data` now passes
  `primary_key_values=[]` instead of `None` when stored keys are not requested, so
  `IsValidPrimaryKey` always runs for a contract with a primary key. The flag governs only
  the comparison with stored keys. Foreign-key and granularity checks are unchanged
  (still opt-in). The schema-level entry points (`TableSchema.validate_dataframe`,
  `to_pandera_schema()`) are untouched and still skip the key when called bare.
- **`SubmissionContract.validate_references` override.** Resolves each target's
  `contract` by name, collects every unresolved one and raises a single `ValueError` in
  the same shape as `BaseContract.validate_references`. Checks existence only — not
  contract type or fields — and never reads data. `enforce_star_schema` is accepted for
  signature compatibility and has no effect.
- **`CrossSubmitter.validate_submission` checks references first**, so a target naming a
  missing contract fails as a wiring error before the bundle is validated, listing all
  such targets rather than stopping at the first.
- **Docs.** Docstrings in `base_contract.py` and `submitter.py` no longer say a `False`
  primary-key flag suppresses the check entirely. ADR 0006 carries an amendment for the
  primary-key change; `CONTEXT.md` updates the key-check relationship line, notes that
  Reference validation of a Submission contract covers its targets, and that a Contract
  resolver never supplies a Submission contract.

## Testing
- `test_validate_data.py`: duplicate and null keys rejected with no resolver and with a
  resolver but the flag off (asserting the failure is the primary-key check); a contract
  without a primary key still accepts duplicates.
- `test_validate_targets.py`: two bundle rows landing on one key in a target are rejected
  with the flag off.
- `test_submission_contract.py`: all targets resolve (looked up by contract name,
  `get_data` never called); one and several unresolved targets reported; resolver errors
  propagate; `enforce_star_schema` has no effect.
- `test_submitter.py`: an unresolvable target now stops before step 1.
- Full test suite and mypy run green.

## Notes for reviewer
- **Behaviour change for existing callers.** A bare `validate_data(df)` — and with it the
  client's `ContractResource.add_data(df)` — now rejects duplicated or empty/null primary
  keys that previously passed. Duplicates are never legitimate, so this is intended; it
  is released as `feat:` because `major_on_zero = false` would bump the same minor version
  either way.
- A duplicate `Dimension` `id` is now reported twice by default (the field's `unique`
  constraint plus the primary key), as it already was with the flag on.
- Primary-key uniqueness is per target's extracted rows, not across the bundle: the same
  key may appear in two targets; two bundle rows that collide in one target after
  transformation are rejected.
- The planning PRD and task files under `.ai-context/` are removed before merge.
