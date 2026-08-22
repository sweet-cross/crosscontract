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
real fields at load time, and what lets the routing field's permitted values be derived
from the targets instead of authored twice.

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

- **The routing field's `enum` is derived, never authored.** It comes from the targets'
  filters, so there is one copy and no drift, and a spec whose routing field carries an
  authored `enum` is rejected rather than silently overwritten. *Where* the derivation is
  assembled — a property on the contract, a helper on the instructions, or the validator
  that checks data against the contract — is still open; see `TODO.md`.
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
- **Execution is not in this package yet.** Applying a submission contract to actual data
  is deferred; when it arrives it joins `submission/` alongside the spec models.
- **Filters are mapping-only in the model.** Two authoring forms reach it: an explicit
  mapping, or an omitted `filters` derived on load as `{routing_column: name}`. Either
  way the stored type describes the value rather than the input that produced it, so no
  consumer narrows a union whose other arm is unreachable. A bare scalar `filters` was a
  third form and was removed — it did the same job as the derivation by a second route,
  which gave the routing values two paths to the same place.
