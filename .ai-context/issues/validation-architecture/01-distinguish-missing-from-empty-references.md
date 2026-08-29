# WP1 — Distinguish "no existing values supplied" from "the referenced table is empty"

## Context
**Part of PRD:** [validation-architecture.md](../../prds/validation-architecture.md) — WP1

`_get_foreign_key_check` tests truthiness, which merges two different situations: `None`
(nothing supplied for an external foreign key — genuinely *cannot* validate) and `[]`
(the referenced table exists and is empty — every referring non-null row *does* fail).
The second is a validation result, not an inability, and must not surface as a
`ValueError`. This lands first because WP2 builds on the corrected semantics.

## Acceptance Criteria
- [ ] An external foreign key with `foreign_key_values=None` (and not skipped) still raises `ValueError` — the documented behaviour of `TableSchema.validate_dataframe` is unchanged.
- [ ] An external foreign key with `foreign_key_values=[]` raises `SchemaValidationError`, and `e.to_list()` names the failing rows.
- [ ] A row whose foreign-key value is **null** still passes against an empty referenced table (SQL semantics — an empty table fails only the non-null rows). This case has its own test.
- [ ] Existing self-reference tests pass unchanged: for a self-referencing foreign key the in-frame values are the valid set, so `[]` and `None` both validate normally.
- [ ] No change to `_get_primary_key_check`.

## Implementation Details
- **Modify:** `src/crosscontract/contracts/schema/adapters/pandera_adapter.py` — `_get_foreign_key_check` (~line 507). The guard becomes a `None` test rather than a truthiness test:

  ```python
  if foreign_key_values is None and referenced_fields is None:
      raise ValueError(...)
  valid_values = set(foreign_key_values or ())
  ```

- **One-site fix, verified.** Do *not* touch `_check_reference_inputs` — `[]` already passes it (`[]` is a list, and `all()` over an empty list is `True`). Do *not* touch the `foreign_key_values.get(tuple(fk.fields))` lookup at ~line 131: `.get()` already distinguishes an absent key (`None`) from a present-but-empty one (`[]`).
- **Reachable today**, so this is a `fix:`, not a refactor: `ContractResource.get_foreign_key_values` (`src/crosscontract/crossclient/services/contract_resource.py:317`) writes `[]` unconditionally, including when the referenced contract has no rows.
- **Tests:** `src/tests/contracts/schema/` (alongside the existing adapter/validation tests).
- **PR:** own PR, conventional commit `fix:`.
- **Depends on:** nothing.
