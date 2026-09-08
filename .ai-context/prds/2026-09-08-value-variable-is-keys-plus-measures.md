# ValueVariable is keys plus measures PRD

> **Sequencing.** This PRD is a prerequisite for
> [2026-09-08-dimension-granularity-check.md](2026-09-08-dimension-granularity-check.md)
> and should land first. That PRD's check needs a guaranteed row identity to group by;
> this one supplies it.

## 1. Overview

`ValueVariableSchema` currently adds nothing to `TableSchema` beyond its `table_type`
discriminator — the class body is a `todo` comment. A **ValueVariable** contract is
therefore constructible with no `primaryKey` at all, and with arbitrary non-numeric
columns outside whatever key it does declare.

This PRD makes the schema say what a fact table is: **a set of key columns that identify
a row, plus numeric measures**. Two rules:

1. A `ValueVariableSchema` must declare a non-empty `primaryKey`.
2. Every field not in the `primaryKey` must be of a numeric type (`integer` or
   `number`).

The audience is contract authors and the platform. The motivation is twofold. First, the
row identity becomes a **declaration** rather than something downstream code infers by
guessing at column names — `admin_tasks/delete_hierachy_duplicates.py` in the sibling
`cross_back` repository currently reconstructs it as `[c for c in df.columns if c !=
"value"]`, which relies on an unstandardised column name and silently swallows any
non-key attribute into the group. Second, the two rules together make a useful invariant
total: a `Dimension` `id` is rigidly `type: "string"`
(`DIMENSION_SCHEMA_TEMPLATE` in
[dimension.py](../../src/crosscontract/contracts/schema/subschemas/dimension.py)), so a
column referencing a dimension is non-numeric, and rule 2 therefore forces every
dimension foreign key column into the primary key.

## 2. Core Requirements

- `ValueVariableSchema` rejects construction when `primaryKey` is empty.
- `ValueVariableSchema` rejects construction when any field outside `primaryKey.fields`
  has a type other than `integer` or `number`.
- Both rejections raise at model-validation time with a message naming the contract's
  offending fields, so an author sees which columns to move.
- No other schema type changes behaviour: `TableSchema` ("General"), `DimensionSchema`,
  `FlexibleDimensionSchema` and the `Submission` contract type (which resolves to the
  `General` table type via `CONTRACT_TYPE_TO_TABLE_TYPE`) are untouched.

Done means: a ValueVariable contract without a primary key, or with a string/datetime/list
column outside its key, fails to load; every existing conforming contract still loads
unchanged.

## 3. Edge Cases & Error Handling

| Case | Behaviour |
|---|---|
| `primaryKey` absent (default `PrimaryKey()` → empty root) | Reject. This is the common case for the rule, not an exotic one — the field has a `default_factory`, so omitting it is silent today. |
| `primaryKey` names a field not in `fields` | Already covered — `TableSchema.validate_structural_integrity` calls `primaryKey.validate_fields(field_names)`. No new handling. |
| Every field is in the primary key (no measures) | **Open decision.** Rule 2 is vacuously satisfied, so the schema loads. Requiring at least one non-key field is a third, separate claim ("a fact table has measures") and is deliberately *not* part of this PRD. Flag it in the ADR as considered-and-deferred. |
| Numeric field *inside* the primary key (e.g. `year: integer`) | Allowed. Rule 2 constrains only fields outside the key. |
| `datetime` field outside the primary key | Rejected. A timestamp that distinguishes rows belongs in the key; one that does not is contract metadata. |
| `list` field outside the primary key | Rejected, same reasoning. |
| `string` field outside the primary key (`unit`, `source`, `comment`) | Rejected. **This is the rule that bites** — 18 of the 51 ValueVariable contracts in the corpus violate it, all via `unit: string`. See §5. |
| Field type extended in future (a new `FieldUnion` member) | The rule is expressed as an allow-list of `{"integer", "number"}`, not a deny-list, so a new type is rejected outside the key until someone decides otherwise. Deliberate. |
| Contract stored on the platform that violates a rule | Fails on `CrossContract.from_server`. This is the migration risk; see §5. |
| Multiple violations in one schema | Collect all offending field names into one message rather than raising on the first. Matches `validate_references`, which collects and reports together. |

Error message shape (both rules in one validator or two — see §4):

```
ValueVariableSchema requires a primary key: a ValueVariable is identified by its
key columns. Declare `primaryKey`.

ValueVariableSchema requires every field outside the primary key to be numeric.
Non-numeric fields outside the key: 'unit' (string), 'valid_from' (datetime).
Move them into `primaryKey` if they identify a row, or onto the contract metadata
if they describe the dataset.
```

## 4. Implementation Decisions & File Paths

**Two `@model_validator(mode="after")` methods, not one.** The two rules fail for
different reasons and are fixed differently, so they get separate messages. This mirrors
the reasoning in [ADR 0006](../adrs/0006-validation-is-a-set-of-check-objects.md) about
`IsValidPrimaryKey` unpacking into one report per sub-rule. Ordering matters: the numeric
rule reads `primaryKey.fields`, so it must tolerate an empty key (it then reports every
non-numeric field, which is noisy but not wrong) — or the key validator is declared first
and pydantic's after-validators run in declaration order. Prefer the latter and rely on
declaration order rather than adding a guard.

**Shape copied, not shared.** `BaseDimensionSchema._validate_primary_key_defined`
([base_dimension.py](../../src/crosscontract/contracts/schema/subschemas/base_dimension.py):33)
is the same validator for dimensions. `ValueVariableSchema` gets its own copy. The two
classes are unrelated — one describes a dimension, one a fact table — and factoring a
shared mixin out of two three-line validators would be exactly the abstraction the
repository's house style says to propose rather than assume.

**No new module.** Both validators live on the existing class.

Files to modify:

- `src/crosscontract/contracts/schema/subschemas/value_variable.py` — the two validators;
  delete the `# todo add value variable-specific fields or constraints` comment.

Files to create:

- `src/tests/contracts/schema/subschemas/test_value_variable.py` — no test module exists
  for this schema today (`src/tests/contracts/schema/subschemas/` holds only the three
  dimension test modules).

Files possibly touched (confirm during implementation, do not assume):

- `src/tests/**` — any fixture building a `ValueVariable` contract or schema without a
  primary key, or with a non-numeric non-key column, now fails. Grep for
  `contract_type: ValueVariable` / `"ValueVariable"` across `src/tests/` before starting;
  fixing fixtures is in scope, changing what they assert is not.

## 5. Data & Schema Changes

**This is a breaking change for stored contracts, and the audit below confirms it bites.** ValueVariable schemas round-trip to
the platform in full — unlike `Dimension`, whose `tableschema` `CrossContract.to_server`
strips because the server owns it — so any stored ValueVariable contract violating either
rule stops loading via `from_server` the moment this ships.

### Audit — done

Run against the contract corpus at `/Users/jan/git/data_model_tmp/data` (70 contracts:
51 ValueVariable, 17 Dimension, 2 FlexibleDimension). This is a local snapshot, so
re-confirm against the live platform before the PR lands, but it is the same set of
documents.

**Rule 1 — no primary key: 0 violations.** Every ValueVariable already declares one. The
primary key mandate is free; it codifies existing practice and breaks nothing.

**Rule 2 — non-numeric field outside the primary key: 18 of 51 violations.** Every one has
the same single cause — a `unit: string` field outside the key — and every one is in the
assumptions family:

`entsoe_tyndp_ntc`, `scenass_aviation_fuel_demand`, `scenass_biomass_potential`,
`scenass_cost_generation_technologies`, `scenass_cost_heating_technologies`,
`scenass_cost_storage_technologies`,
`scenass_electric_appliances_useful_energy_demand`, `scenass_energy_reference_area`,
`scenass_freight_transport_useful_energy_demand`, `scenass_gdp`, `scenass_households`,
`scenass_import_prices`, `scenass_passenger_transport_useful_energy_demand`,
`scenass_population`, `scenass_process_heat_useful_energy_demand`,
`scenass_space_heating_useful_energy_demand`,
`scenass_warm_water_useful_energy_demand`, `scenass_working_population`

No other field type and no other field name offends. All 32 `result_*` contracts pass —
they already carry `unit` **inside** the primary key (e.g. `result_carbon_emissions`:
`[model, scenario_group, scenario_name, scenario_variant, country, year, unit, end_use]`).

So the corpus is internally inconsistent about `unit`, and this rule is what surfaces it.
The assumptions treat `unit` as a descriptor of the dataset; the results treat it as part
of the row identity. **The results are right** — see the decision below.

Also confirmed: 0 ValueVariable contracts have *every* field in the primary key, so the
deferred "must have at least one measure" question is not urgent.

### Remaining gating work

1. **Promote `unit` into the primary key** on the 18 contracts. **Decided.**

   The reason is not that it is the cheap option — it is that `unit` genuinely belongs to
   the row identity, whether or not a given dataset happens to use one unit today. The
   same quantity can legitimately be submitted in two units for the same
   scenario/country/year, and those are two distinct rows, not a conflict. That the
   assumption datasets are currently single-unit is a property of the data submitted so
   far, not of the contract.

   Note the consequence runs the other way from how it first reads: with `unit` *outside*
   the key, those 18 contracts today **cannot** accept the same key in two units — the
   second row is a duplicate primary key and is rejected. Promoting `unit` does not
   loosen anything; it removes a restriction that was never intended. And because every
   existing row is single-unit, no stored row's uniqueness changes, so the promotion is
   safe to apply to live contracts.

   The rejected alternative — dropping the field and carrying the unit as contract
   metadata or a field descriptor — is what "unit is a constant descriptor" would imply,
   and it is wrong for the reason above. It would also change the uploaded frame's column
   set for every producer of those datasets.

   **This fix lands in the contract repository** (the corpus at
   `/Users/jan/git/data_model_tmp/data`), not in this one. It is a prerequisite for the
   model change here, not part of this PR.
2. **Coordinate with `cross_back`.** The server validates contracts on creation using
   these same models, so a stricter schema also rejects contract *creation* — check
   whether any server-side fixture, migration, or seeded contract violates the rules.
3. **Order of operations.** The 18 contracts must be corrected in the contract repository
   and on the platform *before* the stricter model ships, or they stop loading. This is a
   cross-repository sequencing constraint and the main scheduling risk in this PRD.

No database migration is authored by this repository — the schema lives in contract
documents, not in tables.

Input/output contract: unchanged. `ValueVariableSchema` still serialises and deserialises
exactly as before; only the set of accepted documents narrows.

## 6. Related ADRs

- **[ADR 0001 — Dimensions are strict trees](../adrs/0001-dimensions-are-strict-trees.md).**
  The `Sum invariant` this PRD ultimately serves. Rule 2 plus the rigid string `id` on
  `DimensionSchema` is what guarantees a dimension foreign key column sits in the primary
  key, which is what lets the granularity check (the companion PRD) form a group without
  a fallback branch. This PRD does not change ADR 0001.
- **[ADR 0006 — Validation is a set of check objects](../adrs/0006-validation-is-a-set-of-check-objects.md).**
  These are *schema-construction* validators, not `Check` objects: they constrain the
  document, not the data, so they belong on the model and not in
  `contracts/schema/validation/checks/`. The "one mistake, one message" principle is
  followed by using two validators.
- **[ADR 0005 — One contract resolver supplies definitions and values](../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md).**
  Untouched — nothing here needs a resolver.

### Proposed ADR change (not decided)

A new ADR, **"A ValueVariable is keys plus measures"** (next free number, likely `0008`
unless the companion PRD lands first). It should record:

- The decision: the two rules above.
- Why the identity is declared rather than inferred — the `cross_back` admin script's
  `!= "value"` heuristic as the concrete failure mode, and the fact that system columns
  (`uploaded_by`, `uploaded_at`) are the server's concern and never appear in an authored
  schema.
- Why an under-specified primary key is not a separate risk: any column that genuinely
  distinguishes two rows and is missing from the key produces duplicate primary keys, so
  the primary key check already owns that defect. The granularity check is therefore
  entitled to trust the declaration. **Caveat to record honestly:** the primary key check
  is opt-in and off by default (ADR 0006), so on the ordinary path nothing has verified
  the claim.
- Why the numeric rule is bundled rather than split: it is what makes the dimension
  foreign key's membership in the primary key structural rather than conditional. Record
  that this argument only holds because `DimensionSchema.id` is rigidly `string`, and
  that **nothing enforces that a referring field's type matches the referenced field's**
  — `ForeignKey.validate_referenced_fields` checks names only. A contract declaring
  `region: integer` while referencing `dim_region.id` loads today. It fails later at
  pandera coercion, so it is loud rather than silent, but the inference is a convention
  the models do not enforce.
- **`unit` as the worked example.** It is the only rule-2 offender in the corpus and it
  shows what the rule is for: a non-numeric column outside the key is almost always a
  column whose role in the row's identity was never decided. Here the answer is that
  `unit` *is* identity — the same quantity may be submitted in two units — and the rule
  is what surfaced 18 contracts that had silently decided otherwise, and had thereby
  made two-unit submission impossible without anyone choosing that.
- Considered and deferred: requiring at least one non-key field.
- Consequences: breaking for stored contracts; non-numeric attributes must move into the
  key or onto contract metadata.

**The ADR is deliberately not written as part of this PRD.** Whether it is one ADR or two
amendments, and its final wording, is decided when the work is picked up.

## 7. Testing Strategy

New module `src/tests/contracts/schema/subschemas/test_value_variable.py`, mirroring the
style of `test_dimension_schema.py`.

Unit tests — rule 1:

- A `ValueVariableSchema` with a declared primary key constructs.
- One with `primaryKey` omitted raises `ValidationError`, message names the missing key.
- One with `primaryKey: []` raises identically (the empty-list and omitted cases must not
  diverge).

Unit tests — rule 2:

- Fields split key/measure correctly: `integer` and `number` outside the key pass.
- `string`, `datetime`, `list` outside the key each raise, and the message names the
  offending field and its type.
- A `string` field *inside* the key passes (the common `scenario`/`region` case).
- An `integer` field inside the key passes (`year`).
- Multiple offenders are reported in **one** message, not one exception per field.
- A schema where every field is in the primary key constructs (documents the deferred
  decision as a test, so a future change to it is deliberate).

Integration tests:

- `CrossContract` with `contract_type: "ValueVariable"` and a conforming schema
  round-trips through `to_server` / `from_server`.
- A `CrossContract` with `contract_type: "General"` and a non-numeric non-key column still
  constructs — proves the rule did not leak onto the base schema.
- A `SubmissionContract` still constructs — it resolves to the `General` table type, and
  a submission bundle is wide and mostly non-numeric, so this is the regression most
  likely to bite.

Fixtures/mocks: none new. Reuse the YAML fixture pattern of
`src/tests/contracts/schema/subschemas/example_dimension.yaml` if a document-level case
is wanted; otherwise construct dicts inline.

Repository-wide: run the full suite and fix any fixture that constructs a non-conforming
ValueVariable. Per the repository's `CLAUDE.md`, do not run the suite without asking
first.
