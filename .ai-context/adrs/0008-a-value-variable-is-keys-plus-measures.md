# A ValueVariable is keys plus measures

A `ValueVariableSchema` must declare a non-empty `primaryKey`, every field outside that
key must be `integer` or `number`, and there must be at least one such field. The three
rules together say what a fact table is: a key that identifies the row, plus the numbers
measured at it. See **ValueVariable**, **Measure** and **Qualifier** in
[CONTEXT.md](../CONTEXT.md) for the terms.

Before this, the class body was a `todo`: a ValueVariable contract was constructible with
no key at all and with arbitrary non-numeric columns beside its values.

## Why the identity is declared rather than inferred

Downstream code needs to know which columns identify a row, and without a declaration it
guesses. The concrete failure mode is `admin_tasks/delete_hierachy_duplicates.py` in the
sibling `cross_back` repository, which reconstructs the key as
`[c for c in df.columns if c != "value"]` — relying on a column name no schema mandates,
and silently absorbing any non-key attribute into the group. System columns
(`uploaded_by`, `uploaded_at`) are the server's concern and never appear in an authored
schema, so the guess has no way to be right in general.

An under-specified key is not a second risk on top of this. A column that genuinely
distinguishes two rows and is missing from the key produces duplicate primary keys, so the
primary key check already owns that defect and the declaration may be trusted — with the
caveat below.

## Why the numeric rule is bundled rather than split

Rule 2 is what makes the partition total: with no third kind of field, an attribute is
either identity or a measure. That is what lets a consumer take `primaryKey.fields` as the
grain and everything else as values, with no fallback branch.

It costs nothing here because **schema drift is not allowed**. A future non-numeric
column — a per-row `source`, say — cannot appear by accretion; it arrives through a
contract migration that backfills a value for every existing row, and is therefore part of
the row's identity by construction. There is no case of a descriptive per-row string
column that the rule wrongly forces into the key, because there is no way for one to come
into being.

The rule is an allow-list of `{"integer", "number"}`, not a deny-list, so a future
`FieldUnion` member is rejected outside the key until someone decides otherwise.

## `unit` as the worked example

`unit` was the only rule-2 offender in the corpus: 18 of 51 ValueVariable contracts, all
in the assumptions family, carried `unit: string` outside the key, while all 32 `result_*`
contracts already carried it inside. The corpus was internally inconsistent, and the rule
is what surfaced it.

The results were right. The same quantity may legitimately be delivered in two units for
one scenario/country/year, and those are two rows, not a conflict. Note the consequence
runs opposite to how it first reads: with `unit` *outside* the key those 18 contracts
**could not** accept two units for one key — the second row was a duplicate primary key.
Promoting `unit` removed a restriction nobody had chosen. Because every stored row was
single-unit, no row's uniqueness changed and the promotion was safe to apply live. It has
been applied; the corpus conforms.

The rejected alternative — dropping the column and carrying the unit as contract metadata
or a `ValueFieldDescriptor` — is what "unit is a constant descriptor of the dataset" would
imply. It is wrong for the reason above, and it would have changed the uploaded frame's
column set for every producer of those datasets.

## Considered and rejected: requiring key columns to reference a Dimension

A fourth rule was considered — that every non-numeric key column must be a foreign key to
a `Dimension` or `FlexibleDimension` — which would make the key partition mechanically
into axes and scalars. It was rejected: a ValueVariable has no foreign key requirement at
all, and `unit` references nothing. A **Qualifier** is a permanent, legitimate shape.

The consequence is that "in the primary key" does not imply "safe to aggregate over", and
nothing in the schema distinguishes `country` from `unit`. Code that aggregates must not
assume otherwise.

## Consequences

- **Breaking for stored contracts.** ValueVariable schemas round-trip in full — unlike
  `Dimension`, whose `tableschema` `to_server` strips because the server owns it — so a
  stored contract violating a rule stops loading via `from_server`. The corpus was
  migrated before the rule shipped; the ordering constraint spans this repository, the
  contract repository and `cross_back`, which validates contracts on creation with these
  same models.
- **No leniency door.** `Dimension` has a trusted-source path on `from_server` that strips
  and regenerates its rigid schema. ValueVariable has none, so a pre-migration document
  restored from a backup or held as a fixture in a sibling repository is unloadable. This
  is by omission made deliberate; add a door only if that case actually arises.
- **`General` becomes a permanent escape hatch, not a deprecation candidate.** A dataset
  with a non-numeric measured outcome — a binding constraint name, a dominant technology
  per country/year — can no longer be a ValueVariable. `CONTEXT.md` records General's fate
  as undecided; this decision settles it in favour of keeping it.
- **The uniqueness claim is stronger than what runs.** The definition says the key
  identifies a *unique* row, but the primary key check is opt-in and off by default
  ([ADR 0006](0006-validation-is-a-set-of-check-objects.md)) — `to_pandera_schema()`
  called bare permits duplicate keys. So on the ordinary path nothing verifies the
  declaration that downstream code is now entitled to trust. Whether ValueVariable should
  run within-frame key uniqueness unconditionally — which needs no **Contract resolver**,
  being the empty-collection case — is open, and should be settled before anything groups
  by the declared key.
- **The rule catches string mistakes, not integer ones.** A `year: integer` column omitted
  from the key is, by rule 2, a perfectly good measure, and no validator fires. Only the
  uniqueness check above would catch it.
- **A referring field's type is not checked against the referenced field's.**
  `ForeignKey.validate_referenced_fields` checks names only, so a contract declaring
  `region: integer` while referencing `dim_region.id` loads today and fails later at
  pandera coercion. The argument that rule 2 forces every dimension foreign key into the
  key rests on `DimensionSchema.id` being rigidly `string`, which is a convention the
  models do not enforce at the referring end.
- **Considered and deferred: nothing further.** Requiring at least one measure, deferred
  in the PRD, is included here as rule 3; no ValueVariable in the corpus had every field
  in its key, so it broke nothing.
- **Relaxing later is backwards-compatible.** Removing a rule leaves every existing
  document loadable, so the expensive direction has already been paid. Introducing a new
  contract type is not required as a fallback.
