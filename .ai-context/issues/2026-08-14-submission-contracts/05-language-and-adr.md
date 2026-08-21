# WP4 — Ubiquitous language, ADR 0004, and deferred-work entries

## Context
**Part of PRD:** [2026-08-14-submission-contracts.md](../../prds/2026-08-14-submission-contracts.md) (§5.6, §6, §4.7)

Five new terms enter the domain language with this feature, and three architectural
decisions are expensive to reverse and easy to forget the reasons for. `CONTEXT.md` is
the glossary and `adrs/` the decision record; both fall out of date silently unless
updated with the code that motivated them.

## Acceptance Criteria
- [ ] `CONTEXT.md` defines **Submission contract**, **Extraction instructions**, **Transformation profile**, **Target**, and **Routing column**, each with an `_Avoid_` line where a competing word exists.
- [ ] The **Relationships** section covers the ingress path, mirroring how it already covers the Release adapter.
- [ ] The flagged ambiguity on **General** is resolved in place: it stays legacy, and new submission contracts use `Submission` rather than deepening a dependency on a type whose deprecation is undecided.
- [ ] `.ai-context/adrs/0004-submission-contracts-carry-extraction-instructions.md` exists, following the shape of ADR 0003 (statement → **Why** → **Consequences**).
- [ ] `TODO.md` carries the deferred items listed below, each with enough context to act on cold.
- [ ] `.ai-context/prds/` and `.ai-context/issues/` are staged in git — both are currently untracked.

## Implementation Details

**Create:**
- `.ai-context/adrs/0004-submission-contracts-carry-extraction-instructions.md`

**Modify:**
- `.ai-context/CONTEXT.md`
- `.ai-context/TODO.md`

### ADR 0004 must record

- **Named, not resolved.** A submission contract names its target contracts and never
  resolves them. Extraction is a pure `submission file → DataFrame` function;
  validation against the target is downstream. The cost — column drops and type casts
  stay authored rather than derived from the target schema — is accepted deliberately
  in exchange for a spec that loads and runs with no platform connection.
- **Profiles are append-only and do not compose.** No `extends`. The shared steps are
  the *tail* of the pipeline while the varying rename is its *head*, so conventional
  base-first composition would produce wrong pipelines (`cast_column year` before
  `timestamp` has been renamed to `year`). If composition is ever added, the semantics
  that fit are "own steps first, then the base" — the inverse of `extends`.
- **The spec is upstream of the contract.** The routing field's `enum` is derived from
  the targets, not authored, so there is one copy and no drift. Where that derivation
  is assembled is deliberately still open (PRD §5.3) — record the invariant, not a
  method name.
- **`contract_type: Submission`, with no schema class of its own.** It is mapped onto
  the existing `General` table type through `CONTRACT_TYPE_TO_TABLE_TYPE`. This is the
  first real use of the contract-type/table-type split: a contract type says what the
  contract is *for*, a table type selects the schema that backs it, and the submission
  bundle needs a distinct type but not a distinct schema. Minting an empty
  `SubmissionSchema` to satisfy a discriminator would have made "one contract type, one
  schema class" a standing rule and taxed every later contract-type distinction.
- **`SubmissionContract` inherits `CrossContract`** rather than composing
  `BaseContract, CrossMetaData` as a sibling — for `validate_references`'s star-schema
  default and for staying usable wherever a `CrossContract` is accepted.

Cross-reference [ADR 0003](../../adrs/0003-release-is-a-contract-to-frictionless-adapter.md):
this is its ingress mirror. `Target.contract` names a contract exactly as
`FetchSpecMixin.contract` does, and the derived enum is the same "correct by
construction" move. Note too that ADR 0003's `DataInstructions` extension point — the
one documented as awaiting transformations — is satisfied by the union from task 02.

### `TODO.md` entries

- **Execution package.** Applying a submission contract to a DataFrame. It joins
  `submission/` alongside the spec models — a pipeline, not a schema conversion.
- **Where the derived routing `enum` is assembled** (PRD §5.3). Something must inject
  it before data is validated against a submission contract; the candidate sites are a
  property on `SubmissionContract`, a helper on `ExtractionInstructions`, or the
  validator itself. Deliberately left open in WP3.
- **Cross-repo: platform acceptance of `contract_type: Submission` and the
  `extraction` block**, and migrating the three legacy extractor modules (`cross2022`, `cross2025`, `nuclear2025`) to
  YAML. Note that `nuclear2025` additionally needs a numeric string-format
  transformation for its `month` column, which no current transformation covers.
- **`MapColumnValues` `on_conflict` guard** (PRD §5.5). Mapping a value onto one
  already present in the column merges the two silently; on a foreign-key column that
  produces duplicate primary keys downstream, breaking the sum invariant of
  [ADR 0001](../../adrs/0001-dimensions-are-strict-trees.md). Task 02 fixed the other
  half of §5.5 — `default_value` no longer collides with "keep original" — but left
  this one. Note the original framing (that migrating legacy extractors would change
  behaviour) does not apply: there are no legacy specifications to migrate. This is a
  standalone correctness question about the transformation itself.
- **`CONTRACT_NAME_PATTERN` placement.** Relocating it out of
  `contracts/contracts/base_contract.py` would make the `contracts` ↔ `transformations`
  import boundary structural rather than conventional.
- **`contracts/` depends on pandas/pandera** via `schema/adapters/`,
  `schema/validation/`, and `schema/exceptions/`. A pure-model `contracts/` with the
  DataFrame layer extracted is desirable but breaks the public surface — out of scope,
  worth recording.
- **Combining several variables into one target contract** (e.g. net demand).
  Currently raises; revisit as a deliberate feature. `filters` is already typed
  scalar-or-mapping so the YAML need not change.

**Dependencies:** requires task 04 — write the language after the code settles the
terms, not before.
