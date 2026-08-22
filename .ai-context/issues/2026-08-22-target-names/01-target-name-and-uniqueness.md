# WP1 — `Target.name` and the two uniqueness rules

## Context
**Background:** [ADR 0004 — Submission contracts carry their extraction instructions](../../adrs/0004-submission-contracts-carry-extraction-instructions.md)

A `Target` has no identifier of its own. It is identified in practice by its `contract`,
which the contract-uniqueness validator happens to enforce — but that is an accident of
that check, not a design. Two problems follow: `contract` is a platform-side resource
name (it appears in URLs), so using it as a spec-local identifier is semantically wrong;
and binding identity to it cements contract-uniqueness as an *identity* constraint
rather than the primary-key-collision guard it actually is, which makes it expensive to
relax later.

Giving targets a `name` separates the two. Nothing references target names yet — the
motivation is a possible future step that combines several targets into one dataset
(e.g. netting supply against demand), which is **not** in scope here. The point is only
that identity stops riding on `contract`.

## Acceptance Criteria
- [x] `Target` has `name: str`, required, `min_length=1`, **no pattern** and no maximum length.
- [x] Two targets sharing a `name` raise, with a message distinct from the duplicate-contract one.
- [x] Contract uniqueness is unchanged — same rule, same message, its own validator.
- [x] A name that is not a well-formed identifier (e.g. `"StUpid nAming 0f a V@riable"`) is accepted.

## Implementation Details

**Modify:**
- `src/crosscontract/submission/extraction/target.py` — add `name`
- `src/crosscontract/submission/extraction/extraction_instruction.py` — add the name-uniqueness validator

`name` is deliberately unconstrained. `contract` carries `CONTRACT_NAME_PATTERN` and
`max_length=100` because it names a platform resource that ends up in a URL; `name` is
pure local identification, so what an author calls their own target is their decision.
`min_length=1` is not a naming restriction — it is the difference between an identifier
and its absence, and an empty name would also produce an empty routing filter once WP2
lands.

**Two separate validators, not one.** Keep name-uniqueness and contract-uniqueness as
independent `@model_validator(mode="after")` methods with their own messages. They
enforce different things and have different futures: name-uniqueness is structural and
permanent, while contract-uniqueness guards against merged rows colliding on the
contract's primary key and is relaxable if combining targets into one contract ever
becomes a deliberate feature. Folding them together would re-create exactly the coupling
this work package removes.

**Tests:** `src/tests/submission/extraction/`.

The "ugly name is accepted" test earns its place: it is what stops someone later reaching
for `CONTRACT_NAME_PATTERN` on `name` out of symmetry with `contract`.

**Dependencies:** none. Blocks WP2.

**Risk:** low — purely additive, and nothing derives from `name` until WP2.
