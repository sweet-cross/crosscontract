# WP2 — Wire the checks in

## Context
**Part of PRD:** [check-based-validation.md](../../prds/check-based-validation.md) — WP2

This is where the behaviour changes. Primary-key uniqueness *within the data* and the
integrity of *self-referencing* foreign keys need nothing from outside the data, yet
today a flag can switch them off. After this task they always run, because nothing
supplies them and therefore nothing can omit them.

## Acceptance Criteria
- [ ] `skip_primary_key_validation=True` **still** checks non-null and uniqueness within the data. This is the point of the work package.
- [ ] `skip_foreign_key_validation=True` **still** checks self-referencing foreign keys against the data's own rows.
- [ ] An external foreign key with no supplied values is **not checked and does not raise**. The existing test asserting `ValueError` is **inverted, not deleted**, so the reversal is visible in the diff.
- [ ] A row duplicated within the data is reported **once**, not twice, when existing primary keys are also supplied — the additional check replaces the standard one expressing the same rule.
- [ ] **What "the same rule" means is decided here.** WP1 dropped the instance-level identity it was going to be derived from (see WP1 and the PRD), so the merge needs a mechanism: an identity on the composites only, an explicit slot the assembly keys on, or replacement decided by construction rather than by comparison. Whatever it is, both construction sites must reach it without coordinating.
- [ ] `to_pandera_schema()` returns a schema with **no** checks attached.
- [ ] `PanderaPandasAdapter.convert(name, checks=None)` derives nothing: it builds columns from fields and attaches the checks it is given.
- [ ] The runner in `validation/` takes a pandera schema, not a `TableSchema`; its `if TYPE_CHECKING: from ..schema import TableSchema` is gone.
- [ ] `_pandera_dimension_checks.py` is deleted.
- [ ] `backend` is removed from `TableSchema.validate_dataframe` and `to_pandera_schema`; the two tests that exist only to assert the dead branch raises go with it.
- [ ] `BaseContract.validate_data`'s signature is untouched.
- [ ] `[]` still means "the referenced table exists and is empty" and fails every non-null referring row.

## Implementation Details
- **Modify:** `src/crosscontract/contracts/schema/adapters/pandera_adapter.py` — `convert` keeps the field→column `match` (that part was never the problem) and loses all three check-assembly blocks, `_get_primary_key_check`, `_get_foreign_key_check`, `_check_pk_integrity`, `_check_fk_integrity`, and `_check_reference_inputs`.
- **Modify:** `src/crosscontract/contracts/schema/schema.py`
  - `to_pandera_schema(name=...)` — columns only. Its five value/flag parameters go.
  - `validate_dataframe(...)` — **keeps its signature** minus `backend`, and becomes the assembly point: translate values and flags into additional checks, merge with the schema's standard checks, hand the result to the adapter, call the runner.
  - Merge with additional winning. The shape is a dict keyed on whatever identity the
    first acceptance criterion settles on — **not** `c.name`, which is now the check
    class's discriminator and equal across every instance of it, so keying on it would
    collapse a primary key and a foreign key onto each other:
    ```python
    merged = {identity(c): c for c in standard}
    merged.update({identity(c): c for c in additional})
    ```
- **Modify:** `src/crosscontract/contracts/schema/validation/validate_dataframe.py` — reduced to executing a pandera schema and translating `pa.errors.SchemaError(s)` into `SchemaValidationError`. No schema, no values, no flags, no `match backend`.
- **Delete:** `src/crosscontract/contracts/schema/adapters/_pandera_dimension_checks.py`.
- **Foreign keys are assembled here, not in `checks/`.** Iterate `schema.foreignKeys` and build one `IsSubsetOf` per key:
  ```python
  within = fk.reference.fields if fk.reference.resource is None else None
  allowed = (foreign_key_values or {}).get(tuple(fk.fields)) or []
  ```
  The `foreign_key_values` dict is a transport format for the caller's values, not a field on a check — a check that held the whole dict would be N rules rather than one, with nothing for the merge to key on and nothing for `failure_message()` to name.
- **The trap to avoid.** A *self-referencing* foreign key must carry `within`. Dropping it replaces the standard check with a weaker one and self-references silently stop being validated against the data's own rows. There is no `from_foreign_key` guarding this (see WP1 for why), so the derivation above must be written **once** — if the standard and additional lists are built in two places, that is the moment to reconsider the constructor.
- **`convert_schema_to_pandera(schema, name)`** keeps its signature but changes behaviour — it returns columns without checks. Exported from `crosscontract.contracts.schema`; no caller in this repository or `cross_back`.
- **Tests:** `src/tests/contracts/schema/validation/test_pandas_validation.py` and `src/tests/contracts/schema/adapters/pandera/test_integration_references.py` pass, except where they assert the retired `ValueError` or the `backend` guard.
- **PR:** ships with WP1 as one `refactor:`.
- **Depends on:** `01-the-check-classes.md` — specifically its one open item, the four
  dimension rules. This package cannot delete `_pandera_dimension_checks.py` before they
  exist.
