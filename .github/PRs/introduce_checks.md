# Replace ad-hoc pandera checks with check objects derived in one place

## Summary
Validation checks were three differently-shaped, differently-gated blocks inside
`PanderaPandasAdapter`, each building a `pa.Check` around a closure that delegated back to
a module-level helper, with the dimension rules living in a separate module under a
different signature. There was no answer to *what a check is*, so a new one had nowhere to
go and nobody could read "what gets checked on this schema" in one place. This branch
introduces checks as objects, moves their derivation to a single function, and rebuilds the
pandera adapter around it. It carries deliberate behaviour changes and removes public
parameters — see *Notes for reviewer*.

Base is `dev`, not `main`: `main` is five merged PRs behind, so a `main` diff shows
unrelated submission and transformation work.

## Changes

**New `contracts/schema/validation/checks/` package.** A check is a pydantic model holding
what it needs, callable on a DataFrame (`__call__(df) -> pd.Series`), rendering itself via
`to_pandera() -> list[pa.Check]`, and describing its own failure. `name` is a `Literal`
discriminator so checks can later be read from a specification.

- `base_checks.py` — one operation each: `IsUnique`, `IsIn`, `IsNotIn`, `IsNotNull`, and
  `IsSubsetOf`, which carries SQL `MATCH SIMPLE` foreign-key semantics (empty strings read
  as null, a null anywhere in the key passes the row, `within` joins the frame's own rows
  to the valid set for a self-reference).
- `reference_checks.py` — `IsValidPrimaryKey`, a composite that unpacks into one pandera
  check per sub-rule so a report says which rule broke.
- `dimension_checks.py` — the four hierarchy rules over a `DimensionCheck` base carrying
  configurable column names, plus the `IsValidCrossDimension` composite. Ported from
  `_pandera_dimension_checks.py`.
- `utils.py` — `validate_existing_length_match`, used by a `model_validator` on every check
  carrying existing values.

**Pandera adapter rebuilt as `adapters/pandera_pandas/`.** `field_convertors.py` holds one
converter class per field type behind a `get_field_converter` factory; `adapter.py` holds
`PanderaAdapter` with `create_base_schema()` (columns only) and
`_derive_checks(primary_key_values, foreign_key_values)` — the single place a schema
becomes checks, taking existing values as optional arguments. `_pandera_dimension_checks.py`
and the old `pandera_adapter.py` are deleted, along with `convert_schema_to_pandera`.

**`TableSchema` and the runner are thinned.** `validate_dataframe` forwards values to
`to_pandera_schema` and calls the runner; it builds no checks and imports no check classes.
`validation/validate_dataframe.py` takes a `pa.DataFrameSchema` rather than a
`TableSchema`, executes it, and translates pandera exceptions — its
`if TYPE_CHECKING: from ..schema import TableSchema` is gone, as is `backend`.

**`SchemaValidationError` recognises the new checks.** Its reference-error handling
collapses a violation to one row and substitutes the offending key values; it identified
those failures by the old `PrimaryKeyError: ['id']` naming. `CHECK_COLUMNS_PATTERN` now
matches the check classes' message shape alongside the legacy tokens.

**Documentation.** ADR 0006 records the design; ADR 0005 carries a dated amendment for the
retired `ValueError` and the changed `None`/`[]` semantics, with its reasoning left intact.
`CONTEXT.md` retires **Standard check** / **Additional check** in favour of **Base check**,
**Composite check** and **Derivation**. The check-based-validation PRD is updated to what
landed; a new `validation-reporting.md` PRD states the error-reporting problem and its
options. The three work-package issue files are removed now that they are complete.

## Testing
New suites under `src/tests/contracts/schema/validation/checks/` (abstract base, base
checks, dimension checks, reference checks, utils) and
`src/tests/contracts/schema/adapters/pandera_pandas/` (field converters, adapter and
derivation). `validation/test_pandas_validation.py` is re-pointed at
`TableSchema.validate_dataframe` and its expectations updated for the behaviour changes
below. The old `adapters/pandera/` suite is deleted; its field-conversion, integration and
dimension cases are ported.

## Notes for reviewer

**Public removals.** `skip_primary_key_validation` / `skip_foreign_key_validation` and
`backend` on `TableSchema.validate_dataframe`, and `convert_schema_to_pandera`.
`PanderaPandasAdapter` is also renamed to `PanderaAdapter`. `cross_back` passes both
`skip_*` arguments at `backend/app/api/crud/contract_data.py:111` and will raise
`TypeError` until updated — worth landing in the same cycle.

**The key checks became opt-in, reversing the PRD's original goal.** `None` for a group of
values now means "do not check this"; an empty collection means "check it, with nothing to
compare against". So `to_pandera_schema()` called bare returns a schema permitting
duplicate keys, and `contract.validate_data(df)` with no resolver validates types and
dimension structure only. This is deliberate and recorded in ADR 0006, but it is the
opposite of what the PRD set out to do, so it deserves a second opinion.

**Two behaviour changes worth checking against your expectations.** An external foreign key
with no supplied values is now left unchecked rather than raising `ValueError` — the test
asserting the old behaviour is inverted, not deleted. And a dimension frame whose non-root
rows all lack a parent no longer raises `ValueError: cannot set using a list-like
indexer…`. The crash is what was retired, not the double report: a parentless row sitting
alongside rows that do name a parent still fails the catch-all rule as well as
`NonRootElementHasParent`, which is the rule that owns the defect.

**End-to-end coverage restored.** The deleted `adapters/pandera/` suite held the only tests
where a converted schema met a DataFrame. Those are ported into
`adapters/pandera_pandas/test_integration.py` (coercion, numeric bounds, string length,
datetime bounds, nullability, strict mode) and `test_integration_dimension.py` (an
assembled `DimensionSchema`, one rule per frame, plus lazy collection of several). Two
cases are new rather than ported: that a bare conversion permits a duplicate primary key
while an empty list rejects it, since the opt-in semantics had no end-to-end test.

**One coupling to be aware of.** `SchemaValidationError` recovers a check's columns by
parsing its `failure_message()`, because pandera exposes exactly one identifying string per
check. Rewording a `failure_message()` silently degrades reports with no test failing.
`validation-reporting.md` states the problem and sketches the ways out.
