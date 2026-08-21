# feat: add extraction instructions and the submission contract

## Summary

Completes the submission-contract feature: the declarative models that describe how a
delivered bundle is split (`Target`, `ExtractionInstructions`), the `SubmissionContract`
that binds them to a schema, and the language and decision record that keep the design
findable once the planning documents are gone.

A submission bundle is one wide file carrying rows for many datasets at once. Until now
the knowledge of how to split it lived in hand-written Python dictionaries that could not
be authored, reviewed or versioned. This branch makes that knowledge a YAML artifact that
loads, validates standalone, and round-trips.

Base branch is `dev`. The transformations and the `Submission` contract type landed
earlier; this branch is the ingress spec on top of them.

## Changes

**`submission/` becomes a real package.** `submission_contract.py` moves out of
`contracts/contracts/` (history preserved via `git mv`), and `submission/extraction/`
is added alongside it. The package now owns the contract, the spec models, and — when it
lands — the code that executes them. `SubmissionContract` is exported from
`crosscontract/__init__.py`.

**`Target`** carries `filters` (mapping-only; a bare value is accepted as authoring
shorthand and expanded on load), a `contract` **name** validated against
`CONTRACT_NAME_PATTERN`, an optional `transformation_profile`, and its own
`transformations`. It names its target contract and never resolves it.

**`ExtractionInstructions`** holds the required `routing_column`, the reusable
`transformation_profiles`, and a non-empty `targets` list. Three validators:

- a `field_validator("targets", mode="before")` that expands scalar `filters` into
  `{routing_column: value}`. It is a *field* validator rather than a model validator so
  `info.data` already carries the validated `routing_column`; it copies rather than
  mutating the caller's dicts, and hands unrecognised shapes straight through so pydantic
  reports them.
- contract-uniqueness across targets. Repeated *filters* are deliberately allowed — the
  same rows may feed two contracts through different transformations — because a repeated
  contract is the only case that actually breaks: after the routing column is dropped the
  merged rows collide on that contract's primary key.
- every `transformation_profile` reference resolves to a defined profile.

**`SubmissionContract(CrossContract)`** adds `project_name`, `extraction`, and
`contract_type` pinned to `Literal["Submission"]`, plus two model validators: the routing
column must exist in the tableschema, be `required`, be `type: string`, and carry no
authored `enum` (it is derived); and every key of every target's `filters` must name a
field in the tableschema.

**Documentation.** `CONTEXT.md` gains a **Submission and extraction** section defining
*Submission contract*, *Extraction instructions*, *Transformation profile*, *Target* and
*Routing column*, three new **Relationships** bullets for the ingress path, and an updated
**Table type** entry — the mapping is no longer the identity. The **General** ambiguity is
resolved in place: "General is legacy" is true of the *contract type* only, since
`Submission` maps onto the General *table type*, which outlives it.
`ADR 0004` records the three decisions that are expensive to reverse. `CLAUDE.md` gains
the `submission/` architecture entry.

**The PRD and its task files are deleted.** They were planning artifacts; their durable
content is now in ADR 0004 and `CONTEXT.md`.

## Testing

`src/tests/submission/` — 15 tests, no new dependencies.

- **Extraction models** (7): valid construction, scalar-`filters` expansion, an invalid
  contract name, omitted `targets`, duplicate contracts, an undefined profile reference,
  and a missing `routing_column` — the last one pinning that the before-validator hands
  input through so pydantic reports the real error rather than failing on raw data first.
- **`SubmissionContract`** (6): each routing-column invariant separately, plus a filter
  key naming a column absent from the tableschema.
- **Round-trip** (2): `example_submission.yaml` → model → YAML file → model, and the same
  through JSON, asserting model equality. Both hops go through an actual file, so the dump
  is proven serializable rather than merely re-validatable.

`example_submission.yaml` is purpose-built and deliberately small, but covers what can
silently break: both `filters` forms, a profile shared by two targets, a target appending
its own steps after a profile, and a `map_column_values` with `default_value` omitted —
the `KEEP_ORIGINAL` sentinel, which has no serialized form and is nested inside a contract
here for the first time.

## Notes for reviewer

**Nothing derives the routing enum yet.** The format's central claim is that the routing
field's permitted values come from the targets rather than being authored — the contract
*rejects* an authored `enum` for exactly that reason. But no code assembles the derived
set. Where it belongs (a property on the contract, a helper on the instructions, or the
validator that checks data against the contract) was deliberately left open, and it is
recorded for follow-up. Worth confirming you're happy shipping the rejection without the
derivation.

**The cross2025 acceptance test was dropped on purpose.**
`.ai-context/prds/cross2025_submission.yaml` was written to drive design discussion, not
as a fixture; this is all new work with no legacy specification to match, so pinning the
models to one hand-written file would have measured that file rather than the format. If
the PRD directory goes, decide whether that YAML goes with it.

**`submission_contract.py` imports `from crosscontract import CrossContract`** — the
top-level package. This works because `.submission` is imported last in
`crosscontract/__init__.py`, so `CrossContract` is already bound by then. It is an
ordering dependency rather than a guarantee; `from crosscontract.contracts import
CrossContract` would remove it at no cost.

**Deferred, recorded for planning rather than fixed here:** column tracking through a
transformation pipeline (the `output_columns` hook was never added, so adopting it now
means retrofitting all six transformations), the `MapColumnValues` `on_conflict` guard,
and the execution package itself.

**Minor:** the module is `extraction_instruction.py` (singular) while the class is
`ExtractionInstructions` (plural).
