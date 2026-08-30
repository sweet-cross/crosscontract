# WP2 — Wire the checks in

## Context
**Part of PRD:** [check-based-validation.md](../../prds/check-based-validation.md) — WP2

This is where the behaviour changed. Primary-key uniqueness *within the data* and the
integrity of *self-referencing* foreign keys need nothing from outside the data, yet a
flag could switch them off. They now always run, because nothing supplies them and
therefore nothing can omit them.

## Acceptance Criteria

### Landed
- [x] The pandera adapter is a package, `adapters/pandera_pandas/`, holding `adapter.py`
      and `field_convertors.py` (one converter class per field type behind a
      `get_field_converter` factory).
- [x] `PanderaAdapter._derive_checks(primary_key_values, foreign_key_values)` is the
      **single** derivation: one check per schema construct, folding in whatever values it
      is given. `create_base_schema()` builds columns and attaches nothing; `convert()` is
      the two together, and `convert_schema()` forwards the values.
- [x] `TableSchema.to_pandera_schema(values…)` forwards to the adapter, and
      `TableSchema.validate_dataframe` reduces to translating its flags into values and
      calling the runner. The schema imports no check classes.
- [x] The runner in `validation/` takes a pandera schema, not a `TableSchema`; its
      `if TYPE_CHECKING: from ..schema import TableSchema` is gone.
- [x] `skip_primary_key_validation=True` **still** checks non-null and uniqueness within
      the data. This is the point of the work package.
- [x] `skip_foreign_key_validation=True` **still** checks self-referencing foreign keys
      against the data's own rows.
- [x] An external foreign key with no supplied values is **not checked and does not
      raise**. The test asserting `ValueError` is inverted, not deleted.
- [x] `[]` still means "the referenced table exists and is empty" and fails every non-null
      referring row.
- [x] `BaseContract.validate_data`'s signature is untouched.
- [x] `backend` is removed from `TableSchema.validate_dataframe` and `to_pandera_schema`,
      and the dead-branch tests with it.
- [x] `_pandera_dimension_checks.py` and the old `pandera_adapter.py` are deleted.

### Decided differently from the plan

**The conversion carries the checks.** `to_pandera_schema()` was to return columns only.
It returns a schema that enforces the contract instead: the entry point is public, and a
conversion permitting duplicate primary keys and broken self-references enforces less than
the contract it claims to represent. Baking them in is also what makes them impossible to
omit, which is the correctness half of the PRD.

**The derivation lives in the adapter, not on `TableSchema`.** The PRD put assembly on
`validate_dataframe`. Keeping it in the adapter leaves one dependency edge
(`schema → adapter → checks`) instead of two, keeps `TableSchema` a description of a
table, and means all pandera knowledge sits behind one door. Deriving *a primary key
implies a uniqueness check* is conversion, not deciding.

**There is no merge, and no identity to key one on.** Standard and additional checks were
two lists only because the derivation ran twice — once from the schema, once from the
caller's values. One derivation taking optional values produces **one** check per
construct, so there is nothing to reconcile:

- the primary key check is always derived; `existing=[]` when nothing is supplied
- a self-referencing foreign key always keeps `within`; supplied values are added to it
- an external foreign key yields a check only when values are supplied

A caller therefore supplies **values, never checks** — it can inform a check but not drop
one, which is the guarantee the standard/additional split existed to protect. This also
removed a false rejection the two-list version produced: a self-reference whose parent was
already stored failed the schema-derived check while passing the caller's.

**`convert_schema_to_pandera` is deleted, not kept.** It was an alias over
`PanderaAdapter.convert_schema`, which already spares instantiation.
`TableSchema.to_pandera_schema` remains as the discoverable entry point.

**The `pa.DataFrameSchema` is unnamed**, so reports read `DataFrameSchema 'None' failed …`.
Accepted for now; the contract name is the right thing to put there, and only
`BaseContract` knows it.

### Still open
- [ ] `contracts/schema/__init__.py` still names `convert_schema_to_pandera` in `__all__`
      after the function was deleted.
- [ ] End-to-end coverage went with the deleted adapter suite. Nothing runs a converted
      schema against a DataFrame at field level — coercion, bounds, string length, strict
      mode — and nothing exercises an assembled `DimensionSchema`, including the lazy
      collection of several hierarchy errors. The check classes are covered directly; the
      assembled schema is not.
- [ ] The two `skip_*` parameters on `TableSchema.validate_dataframe` now only discard
      values before deriving. Absent values mean the same thing, so they carry no
      information and can go — a separate PR, since `cross_back` passes them.

## Implementation Details
- **The package is named `pandera_pandas`** because a package cannot share a directory
  with a module of the same name, and `pandera_adapter.py` had to stay live during the
  transition. It can be renamed now that the old module is gone.
- **`SchemaValidationError` had to learn the new checks.** Its reference-error handling
  collapses one violation to a single row and substitutes the offending key values, and it
  recognised failures by the legacy `PrimaryKeyError: ['id']` naming. The check classes
  report as `Columns 'id' in check '<label>' …`, so `CHECK_COLUMNS_PATTERN` was added
  alongside the legacy tokens. That coupling — the parser depending on the wording of
  `failure_message()` — is the subject of
  [validation-reporting.md](../../prds/validation-reporting.md).
- **`_get_primary_key_check`, `_get_foreign_key_check`, `_check_pk_integrity`,
  `_check_fk_integrity` and `_check_reference_inputs`** have no equivalent in the new
  adapter. The format validation the last of them performed is now a `model_validator` on
  the checks that consume the values, and it also checks arity, which the free function
  could not.
- **Tests:** `src/tests/contracts/schema/adapters/pandera_pandas/` covers the field
  converters and the derivation; `validation/test_pandas_validation.py` covers the flags,
  values and reference semantics through `TableSchema.validate_dataframe`.
- **PR:** ships with WP1 as one `refactor:`.
- **Depends on:** WP1, complete.
