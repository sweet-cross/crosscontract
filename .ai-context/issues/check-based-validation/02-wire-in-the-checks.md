# WP2 — Wire the checks in

## Context
**Part of PRD:** [check-based-validation.md](../../prds/check-based-validation.md) — WP2

This is where the behaviour changes. Primary-key uniqueness *within the data* and the
integrity of *self-referencing* foreign keys need nothing from outside the data, yet
today a flag can switch them off. After this task they always run, because nothing
supplies them and therefore nothing can omit them.

## Acceptance Criteria

### Landed — the new adapter exists, unwired
- [x] The pandera adapter is a package, `adapters/pandera_pandas/`, holding `adapter.py`
      (`PanderaAdapter`, `convert_schema_to_pandera`) and `field_convertors.py` (one
      converter class per field type behind a `get_field_converter` factory).
- [x] `PanderaAdapter.create_base_schema()` builds columns from fields and attaches no
      checks; `add_internal_checks()` adds what the schema requires of its own data;
      `convert()` is the two together.
- [x] The conversion derives the standard checks: `IsValidPrimaryKey` for the primary key,
      one `IsSubsetOf` per **self-referencing** foreign key, and `IsValidCrossDimension`
      for a `Dimension` table type.
- [x] An external foreign key emits **no** check — it cannot be validated without the
      referenced values.
- [x] Tests for both modules in `src/tests/contracts/schema/adapters/pandera_pandas/`,
      porting the cases from the old adapter's suite.

### Reversed, deliberately
- ~~`to_pandera_schema()` returns a schema with **no** checks attached.~~ The conversion
  carries the schema's standard checks instead. `convert_schema_to_pandera` is public, and
  a conversion that permits duplicate primary keys and broken self-references enforces
  less than the contract it claims to represent. This also makes the standard checks
  structurally impossible to omit — the correctness half of the PRD — rather than
  something the assembly step has to remember.
- ~~`PanderaPandasAdapter.convert(name, checks=None)` derives nothing.~~ It derives the
  standard set. The `checks=None` parameter is still needed, but as the seam for the
  **merged** list (see below), not as the only source of checks.
- ~~`convert_schema_to_pandera(schema, name)` keeps its signature.~~ `name` is dropped and
  the `pa.DataFrameSchema` is left unnamed. Reports therefore read
  `DataFrameSchema 'None' failed …`; accepted for now.

### Still open
- [ ] Nothing calls the new adapter. `contracts/schema/schema.py`,
      `validation/validate_dataframe.py` and `adapters/__init__.py` all still import the
      old `pandera_adapter.py`.
- [ ] `convert(checks=None)`: when given a list, use it; when `None`, derive the standard
      set. This is the merge seam — the merge must happen while the checks are still check
      objects, because a `pa.Check` cannot be matched against another by rule.
- [ ] `skip_primary_key_validation=True` **still** checks non-null and uniqueness within the data. This is the point of the work package.
- [ ] `skip_foreign_key_validation=True` **still** checks self-referencing foreign keys against the data's own rows.
- [ ] An external foreign key with no supplied values is **not checked and does not raise**. The existing test asserting `ValueError` is **inverted, not deleted**, so the reversal is visible in the diff.
- [ ] A row duplicated within the data is reported **once**, not twice, when existing primary keys are also supplied — the additional check replaces the standard one expressing the same rule.
- [ ] **What "the same rule" means is decided here.** WP1 dropped the instance-level identity it was going to be derived from (see *Standard and additional* in the PRD), so the merge needs a mechanism: an identity on the composites only, an explicit slot the assembly keys on, or replacement decided by construction rather than by comparison. Whatever it is, both construction sites must reach it without coordinating.
- [ ] The runner in `validation/` takes a pandera schema, not a `TableSchema`; its `if TYPE_CHECKING: from ..schema import TableSchema` is gone.
- [ ] `_pandera_dimension_checks.py` and the old `pandera_adapter.py` are deleted.
- [ ] `backend` is removed from `TableSchema.validate_dataframe` and `to_pandera_schema`; the two tests that exist only to assert the dead branch raises go with it.
- [ ] `BaseContract.validate_data`'s signature is untouched.
- [ ] `[]` still means "the referenced table exists and is empty" and fails every non-null referring row.

## Implementation Details
- **Done:** the replacement lives in `src/crosscontract/contracts/schema/adapters/pandera_pandas/`. `_get_primary_key_check`, `_get_foreign_key_check`, `_check_pk_integrity`, `_check_fk_integrity` and `_check_reference_inputs` have no equivalent there. The old `pandera_adapter.py` stays until the callers move, and the package is named `pandera_pandas` because a package cannot share a directory with a module of the same name.
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
- **The trap to avoid.** A *self-referencing* foreign key must carry `within`. Dropping it replaces the standard check with a weaker one and self-references silently stop being validated against the data's own rows. There is no `from_foreign_key` guarding this (see *The caller derives, the check checks* in the PRD for why), so the derivation above must be written **once** — if the standard and additional lists are built in two places, that is the moment to reconsider the constructor.
- **Done — the standard checks are derived in `add_internal_checks`.** The three gates are the primary key, the self-referencing foreign keys and the `Dimension` table type. Their labels are `"Internal PrimaryKey Check"`, `"Internal ForeignKey Check"` and `"CrossDimension Check"`, and every check's `failure_message()` names its columns alongside the label.
- **Tests:** `src/tests/contracts/schema/validation/test_pandas_validation.py` and `src/tests/contracts/schema/adapters/pandera/test_integration_references.py` pass, except where they assert the retired `ValueError` or the `backend` guard.
- **PR:** ships with WP1 as one `refactor:`.
- **Depends on:** WP1, the check classes, which is complete. Attach
  `IsValidCrossDimension` where `get_dimension_checks` is called today; deleting
  `_pandera_dimension_checks.py` also retires the `ValueError` it raises on a dimension
  with a parentless child, which the ported rule no longer has.
