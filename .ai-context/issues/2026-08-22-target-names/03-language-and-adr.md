# WP3 — Language and decision record

## Context
**Background:** [ADR 0004 — Submission contracts carry their extraction instructions](../../adrs/0004-submission-contracts-carry-extraction-instructions.md)

Both `CONTEXT.md` and ADR 0004 describe a `Target` that has no identifier of its own, and
ADR 0004 states contract-uniqueness as though it were the identity rule. After WP1 and WP2
that is wrong in a way that matters: the whole point of `name` is that identity and
contract-uniqueness are separable, and a reader who takes the current wording at face
value will re-couple them.

## Acceptance Criteria
- [ ] ADR 0004's Consequences separate the two uniqueness rules and say why contract-uniqueness is relaxable.
- [ ] `CONTEXT.md`'s **Target** entry leads with `name` and covers the routing-value default.
- [ ] No description, docstring or glossary entry still refers to the scalar shorthand.

## Implementation Details

**Modify:**
- `.ai-context/adrs/0004-submission-contracts-carry-extraction-instructions.md`
- `.ai-context/CONTEXT.md`

**ADR 0004.** The Consequences bullet currently reads "One target per contract; repeated
filters are fine", which frames contract-uniqueness as identity. Split it: `name` is the
identifier, structural and permanent; contract-uniqueness is the guard against merged rows
colliding on the contract's primary key — situational, and relaxable if combining several
targets into one contract becomes a deliberate feature. Record that identity no longer
rides on `contract`, since that is what makes the relaxation cheap. Keep it to the
Consequences section: nothing in **Why** changes, because none of the three decisions
recorded there is affected.

**CONTEXT.md.** The **Target** entry defines a target by its filters, transformations and
contract. `name` goes to the front. Worth a clause on the routing-value default, because
this is the one place in the language where an identifier doubles as data — and note the
asymmetry with `contract`, which is pattern-constrained precisely because it is not
spec-local.

**Verification.** Read both entries cold and check they describe the shipped model. Grep
the package for stale "shorthand" / "bare value" / "scalar" wording. Check the **Routing
column** entry in particular — it currently implies filters are always authored, which
stops being true once they can be derived.

**Dependencies:** WP1 and WP2 landed, so the wording describes what shipped rather than
what was planned.
