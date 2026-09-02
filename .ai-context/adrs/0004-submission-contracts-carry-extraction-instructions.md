# Submission contracts carry their extraction instructions

A **Submission contract** is a `CrossContract` whose **Schema** describes a delivered
bundle — one file carrying rows for many datasets at once — and which additionally
carries an `extraction` block: a **Routing column**, reusable **Transformation
profiles**, and one **Target** per dataset to extract. It is authored as a single YAML
file and loaded as a pydantic model, and it lives in a top-level `submission/` package,
the ingress peer of `release/`.

Three decisions below are the ones expensive to reverse. Everything else about the
format — the model shapes, the validators, the vocabulary — is in the code and in
[CONTEXT.md](../CONTEXT.md).

## Why

### The contract carries the spec, rather than a spec naming a contract

This is the deliberate asymmetry with [ADR 0003](./0003-release-is-a-contract-to-frictionless-adapter.md).
On egress, `CrossDataPackageReleaseSpec` **names** contracts and is emphatically not one
itself. On ingress the reverse holds: the artifact *is* a contract, and the extraction
instructions ride along inside it.

The reason is that a submission bundle has a schema of its own — eleven columns, a
composite primary key, foreign keys into dimensions — and that schema and the
instructions for splitting it are two halves of one authored thing. Separating them
would mean two files that must agree about the bundle's shape, with nothing enforcing
the agreement. Keeping them together is what lets the routing column be checked against
real fields at load time, and what lets a delivered bundle be checked against the targets
that claim its rows — only an artifact holding both halves can tell whether extraction
would silently drop a row.

The cost is that a submission contract is not interchangeable with a plain contract on
the wire: it carries two keys — `project_name` and `extraction` — that `CrossContract`'s
`extra="forbid"` would reject coming back the other way.

### Extraction names its target contracts and never resolves them

A **Target** carries a contract *name*, validated against `CONTRACT_NAME_PATTERN`, and
nothing more. Extraction is a pure function from bundle to tabular data; validating each
result against its target contract is a separate, downstream step. Nothing in the
package looks a target contract up, and no spec requires a platform connection to load,
validate, or execute.

**The accepted cost is redundancy, and it is deliberate.** Column drops and type casts
are authored in the spec rather than derived from the target schema, so the same facts
appear in two places and can drift. Deriving them would be strictly less code and is the
obvious-looking cleanup — it is rejected because it would make every spec unloadable
without the platform, which is the property the whole format is built around.

### Transformation profiles are append-only and do not compose

A **Target** may name one **Transformation profile** and may also carry its own
`transformations`. The profile's steps run first, then the target's. Profiles do not
reference other profiles, and there is no `extends`.

This looks like an omission and is not. The shared steps are the *tail* of a pipeline
while the varying part is its *head*: a profile typically renames `timestamp` to `year`
and then casts `year` to integer, while a target's own steps adjust values in the
already-renamed columns. Conventional base-first composition — a profile extending
another, base steps first — would therefore produce pipelines that operate on columns
that do not exist yet, e.g. `cast_column year` before anything has been renamed to
`year`.

If composition is ever wanted, the semantics that fit this shape are **own steps first,
then the base** — the inverse of what `extends` normally means. Adding `extends` with
its usual meaning would be a silent correctness bug, not a feature.

## Consequences

- **The routing field's `enum` is neither derived nor banned.** An earlier revision of
  this ADR had it derived from the targets and rejected an authored one. That is
  withdrawn: `filters` is an arbitrary column → value conjunction, so a target need not
  constrain the routing column at all and the permitted set is underivable — and deriving
  it from only the targets that *do* mention it would wrongly reject rows destined for the
  rest. The `enum` also never expressed the property it appeared to. It asserts that a
  routing vocabulary is *known*, not that a row is *consumed*: a row carrying a valid
  routing value still vanishes when a second filter over another column fails. That
  property is row coverage, it is decidable only against data, and it lives in
  `SubmissionHandler.unclaimed_rows`, which reports the rows no target claims and does
  nothing with them — whether an unclaimed row is an error or a warning is the caller's
  decision, deliberately still open. An authored `enum` is now an ordinary field
  constraint, useful to an author who does know the closed set.
- **A target is identified by its `name`, not by its contract.** `name` is spec-local and
  deliberately carries no pattern and no maximum length — what an author calls their own
  target is their decision — where `contract` carries `CONTRACT_NAME_PATTERN` because it
  names a platform resource that ends up in a URL. Names are unique across targets; that
  rule is structural and permanent, and it is what any later reference to a target would
  use.
- **Contract-uniqueness is a separate rule, and a relaxable one.** A contract may not be
  fed twice, because after the routing column is dropped the merged rows collide on that
  contract's primary key — a failure that would otherwise surface only at insertion time.
  This is a guard against a concrete breakage, *not* an identity constraint, and keeping
  it distinct from `name` is what leaves it relaxable: if combining several targets into
  one contract ever becomes a deliberate feature, nothing that identifies a target has to
  change. Repeated *filters* are already fine — two targets may select the same rows and
  reshape them differently for two different contracts.
- **`contract_type: Submission` maps to the `General` table type.** A submission bundle
  needs its own contract type but not its own schema; see the **Table type** entry in
  [CONTEXT.md](../CONTEXT.md) for why no empty schema class was minted.
- **`SubmissionContract` inherits `CrossContract`** rather than composing `BaseContract`
  and `CrossMetaData` as a sibling — for `validate_references`'s star-schema default,
  which is correct here since a bundle's foreign keys all point at dimensions, and so the
  contract stays usable wherever a `CrossContract` is accepted.
- **`submission/` is top-level, peer to `release/`.** It owns its spec models and, when
  it lands, the code that executes them, so the concept lives in one package. It also
  keeps the import graph one-way: `transformations` already imports `CONTRACT_NAME_PATTERN`
  out of `contracts`, so extraction living under `contracts/` and importing
  `transformations` would have closed a cycle.
- **Execution lives in `submission/` as `SubmissionHandler`.** It holds a submission
  contract and a bundle, and answers **one target at a time**: select the rows a target
  claims, apply its transformation profile and then the target's own transformations.
  There is deliberately no method that runs every target, so whether a run aborts on the
  first failure or collects them all stays the caller's decision — with no aggregate
  return type, that choice can change without anything to retrofit. `unclaimed_rows`
  lives here too rather than on the contract: the spec models' contact with pandas is
  otherwise adapter-mediated and backend-parameterized, and unclaimed rows are a property
  of a bundle *paired with* instructions, not of either alone.

  > **Amended 2026-08-31.** The "no method runs every target" consequence is withdrawn.
  > The handler gains `validate_target` (one target) and `validate_targets` (every target,
  > or a named subset). The reasoning above held while nothing consumed a loop; batch
  > submission through the server is that consumer, and leaving the loop to callers would
  > put the same three lines in `cross_back`, in `admin_tools`, and in every notebook.
  >
  > The decision the absent method was protecting is therefore made rather than deferred:
  > **across targets every failure is collected**, with no `fail_fast` escape — the posture
  > `lazy=True` already takes within one dataset — and raised together as a
  > `TargetValidationError` holding one `SchemaValidationError` per target. On success the
  > return is the validated, coerced frames keyed by **target name**, not by contract:
  > contract-uniqueness is a relaxable guard (above), while a target's name is its
  > identity, so a contract-keyed result would silently collapse two entries if that guard
  > were ever relaxed.
  >
  > **The second decision stands untouched.** The handler still resolves nothing. The
  > primitive takes the target's contract directly; the loop takes a `ContractResolver` the
  > caller supplies — the escape hatch this ADR already named — and neither ever constructs
  > one. A contract handed in wins over one the resolver would return, so a provider can
  > validate against a contract not yet on the platform. Both a mismatched contract and an
  > unresolvable one raise immediately instead of joining the collected failures: they mean
  > the run is wired wrong, not that the rows are bad.
  >
  > Three things deliberately stayed out. Validating the **bundle** remains the caller's
  > ordinary `validate_data` call, so "does a failed bundle stop the run" needs no flag —
  > the caller simply does not go on, and the handler stays agnostic about whether the frame
  > it holds was coerced. **Unclaimed rows** are a bundle-level property, not a target's,
  > and remain a report nobody acts on. A target claiming **no rows** validates like any
  > other and returns an empty frame — the ingress inverse of `release/`'s warn-and-skip,
  > because an empty resource corrupts a published package while an empty target is a
  > submission that legitimately carried nothing this round.
- **The handler is pandas, and that is settled rather than provisional.** Not because
  bundles are small — they are, around 15 MB — but because `BaseTransformation.apply` is
  typed `pd.DataFrame -> pd.DataFrame`, every transformation is a pandas function, and
  `ContractService._add_data` serializes a `pd.DataFrame` on the way out. Another engine
  would mean reimplementing all six transformations in SQL, forking the layer this format
  is built to keep extensible, or round-tripping back to pandas per target for nothing.
- **The handler resolves nothing either.** It holds to the second decision above: target
  contracts are named, never looked up, so a handler loads and runs with no platform
  connection. Should a validation step join it, the contract must arrive from the
  caller — passed in directly, or through the `ContractResolver` protocol `BaseContract`
  already defines for `validate_references` — rather than being resolved inside
  `submission/`. Adding a lookup here would quietly undo the property that the whole
  format is built around.
- **Filters are mapping-only in the model.** Two authoring forms reach it: an explicit
  mapping, or an omitted `filters` derived on load as `{routing_column: name}`. Either
  way the stored type describes the value rather than the input that produced it, so no
  consumer narrows a union whose other arm is unreachable. A bare scalar `filters` was a
  third form and was removed — it did the same job as the derivation by a second route,
  which gave the routing values two paths to the same place.
