# WP1 — Always check the primary key within the data

## Context
**Part of PRD:** `.ai-context/prds/2026-09-13-submission-0-crosscontract-prerequisites.md` (Part A)

Validating a Contract's data currently skips the primary key entirely unless it is
compared against stored values. The server validates submission targets without that
comparison but must still reject duplicated or missing keys within each target's rows.

**Dependencies:** none.
**Priority:** critical path — the only change that makes existing calls stricter, and the
test sweep is the largest unknown in the PRD. Do first.

## Acceptance Criteria
- [ ] `BaseContract.validate_data` passes `primary_key_values=[]` when
      `check_existing_primary_key` is `False` or no `resolver` is given; stored values
      when the flag is `True` and a resolver is given.
- [ ] For a contract with a primary key, `validate_data` rejects duplicated and null key
      values within the frame for every flag/resolver combination.
- [ ] A contract without a primary key accepts duplicate rows as before.
- [ ] Flag `True` with a resolver: in-frame duplicates and stored collisions are still
      reported as distinct failures.
- [ ] Foreign-key and granularity behaviour unchanged.
- [ ] `TableSchema.validate_dataframe`, `to_pandera_schema()` and the adapter are
      untouched: called bare, they still skip the primary key.
- [ ] Existing tests relying on duplicate keys passing are updated or removed.
- [ ] Docstrings no longer say a `False` primary-key flag suppresses the check entirely:
      `BaseContract.validate_data`, `SubmissionHandler.validate_target`,
      `SubmissionHandler.validate_targets`, `CrossSubmitter.validate_submission`,
      `ContractResource.validate_dataframe`.
- [ ] ADR 0006 carries an inline `> **Amended 2026-09-13.**` note in "Why the key checks
      are opt-in": the primary key is always checked within the data when validating a
      Contract (reason: submission targets validated without stored-value comparison;
      consequence: bare `validate_data(df)` and `add_data(df)` reject duplicate keys;
      the schema-level entry points still skip it unless passed `[]`).

## Implementation Details
- `src/crosscontract/contracts/contracts/base_contract.py` — initialise
  `existing_primary_keys` to `[]` instead of `None`; the resolver branch overwrites it
  when the flag is set. Adapter gate is `primary_key_values is not None and
  self.schema.primaryKey` (`adapters/pandera_pandas/adapter.py`), so nothing else changes.
- Docstrings: `src/crosscontract/submission/submission_handler.py`,
  `src/crosscontract/submission/submitter.py`,
  `src/crosscontract/crossclient/services/contract_resource.py`.
- `.ai-context/adrs/0006-validation-is-a-set-of-check-objects.md` — amendment.
- `.ai-context/CONTEXT.md` — already updated; no change.
- Tests: `src/tests/contracts/contracts/test_validate_data.py` (parametrised over the
  flag/resolver table in PRD §5, composite key, no-key contract, regression guard);
  `src/tests/submission/test_validate_targets.py` (target with duplicate keys fails with
  `check_existing_primary_key=False`). Sweep callers of `validate_data`,
  `validate_target(s)`, `validate_submission` and `add_data` for fixtures with duplicate
  or empty-string keys.
- Known and accepted: a duplicate `Dimension` `id` is reported twice (field `unique`
  constraint plus primary key).

## Verification
Ask before running: `uv run pytest`, `uv run mypy src/crosscontract/`,
`uv run ruff check src/`.
