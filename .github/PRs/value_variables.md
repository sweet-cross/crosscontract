# feat!: define a ValueVariable as a primary key plus numeric measures

## Summary

`ValueVariableSchema` added nothing to `TableSchema` beyond its `table_type`
discriminator — its body was a `todo`. A ValueVariable contract was therefore
constructible with no primary key at all and with arbitrary non-numeric columns beside
its values, which left the row identity to be guessed downstream (the admin script in
the sibling `cross_back` repository reconstructs it as
`[c for c in df.columns if c != "value"]`, relying on a column name no schema mandates).

This branch makes the schema say what a fact table is: a primary key that identifies the
row, plus one or more numeric measures, with no third kind of field. The identity becomes
a declaration rather than an inference.

**This is breaking for stored contracts.** ValueVariable schemas round-trip to the
platform in full, so a stored contract violating a rule stops loading via `from_server`.
The contract corpus was migrated ahead of this change; see Testing.

## Changes

**The rule** — `src/crosscontract/contracts/schema/subschemas/value_variable.py`

One `model_validator(mode="after")` enforcing three rules in order:

1. a non-empty `primaryKey` is declared;
2. at least one field lies outside that key;
3. every field outside the key is of type `integer` or `number`.

The type test is an allow-list of `{"integer", "number"}`, not a deny-list, so a future
`FieldUnion` member is rejected outside the key until someone decides otherwise. Multiple
offending fields are collected into one message rather than raising on the first. No other
schema type changes behaviour — `TableSchema`, the two dimension schemas, and the
`Submission` contract type (which resolves to the `General` table type) are untouched.

**Decision record** — `.ai-context/adrs/0008-a-value-variable-is-keys-plus-measures.md`

New ADR recording the three rules, why the identity is declared rather than inferred, and
why the numeric rule costs nothing given that schema drift is not allowed: a non-numeric
column cannot appear by accretion, only through a migration that backfills every row, so
it is identity by construction. Records two rejections and several consequences — see
Notes.

**Glossary** — `.ai-context/CONTEXT.md`

**ValueVariable** redefined as key plus measures; **Measure** and **Qualifier** added
(a qualifier being a non-numeric key column referencing no dimension), plus a
relationships entry stating that a key column is not necessarily a dimension reference,
so "in the key" does not imply "safe to aggregate over".

**User-facing docs** — `docs/contracts/`

New *ValueVariable contracts* section in `contract_types.md` with the three rules, a table
for deciding where a non-numeric column belongs, and a subsection on key columns not being
dimensions. Also corrected two pre-existing errors on that page: the fact-table description
asserted that non-measure columns reference dimensions (which this branch explicitly does
not require), and the type list named three contract types out of five. `metadata.md` was
missing `Submission` from the `contract_type` row.

**Removed** — `.ai-context/prds/2026-09-08-value-variable-is-keys-plus-measures.md`,
superseded by the ADR.

## Testing

New `src/tests/contracts/schema/subschemas/test_value_variable.py`, one test per rule:
the primary key requirement (parametrized over an omitted key and `primaryKey: []`, which
must not diverge since the field has a `default_factory`), the at-least-one-measure rule
(asserting both directions), and the numeric rule (parametrized over `string`, `datetime`
and `list`, asserting the message names the offending field). The shared fixture keeps
string and integer columns *inside* the key, so it doubles as the inside-the-key case.

Three existing tests constructed non-conforming ValueVariables and were fixed:
`test_contract_type_resolves_to_correct_schema` and
`test_instantiated_subclass_schema_mismatch_raises_value_error` in
`test_contract_types.py`, and `test_is_dimension_false` in `test_contract_resource.py`.
The first took its schema from the module-level `data_base_contract`, which the
`Submission` case also uses — and submission contracts reject a `primaryKey` — so the
conforming schema was added as a parametrize column rather than by changing the shared
fixture.

Corpus audit: all 51 ValueVariable contracts in the local snapshot at
`/Users/jan/git/data_model_tmp/data` conform to all three rules, with zero violations.
Re-confirm against the live platform before merging, and check `cross_back` for
server-side fixtures or seeded contracts that would now fail contract *creation*, since
the server validates with these same models.

## Notes for reviewer

- **Ordering across repositories.** The corpus and the platform must be correct before
  this ships, not after. That is the main scheduling risk and it is not enforceable from
  this repository.
- **The uniqueness claim is stronger than what runs.** The definition says the key
  identifies a *unique* row, but the key checks are opt-in and off by default
  ([ADR 0006](../../.ai-context/adrs/0006-validation-is-a-set-of-check-objects.md)) —
  `to_pandera_schema()` called bare permits duplicate primary keys. So downstream code is
  now entitled to trust a declaration that nothing verifies on the ordinary path. This was
  raised and deliberately left out of scope as a validation question; the ADR records it
  as a consequence.
- **The type rule has a blind spot.** An `integer` column wrongly left out of the key is,
  by rule 3, a valid measure, and no validator fires. Only the uniqueness check above
  would catch it. The rule catches non-numeric mistakes loudly and numeric ones not at all.
- **No leniency door on `from_server`.** `Dimension` has a trusted-source path that strips
  and regenerates its rigid schema; ValueVariable has none, so a pre-migration document
  restored from a backup is unloadable. Deliberate by omission — worth a second opinion.
- **`General` is now a permanent escape hatch.** A dataset with a non-numeric measured
  outcome can no longer be a ValueVariable, so this settles General's open deprecation
  question in favour of keeping it. Recorded in the ADR.
- **Rejected: requiring key columns to reference a dimension.** A fourth rule was
  considered and rejected — a ValueVariable declares no foreign keys by requirement, and a
  qualifier is a legitimate permanent shape. The cost is that nothing distinguishes an
  aggregatable key column from one that is not.
- **Title is `feat!:`** because stored contracts break. With `major_on_zero = false` this
  bumps 0.20.1 to 0.21.0 rather than 1.0.0.
