# WP3 — Record it

## Context
**Part of PRD:** [check-based-validation.md](../../prds/check-based-validation.md) — WP3

WP2 retires a decision that [ADR 0005](../../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md)
recorded as deliberate. Left alone, that ADR becomes quietly wrong. A future reader will
also wonder why uniqueness runs when they asked to skip it, and why a check is called
`IsUnique` rather than naming the primary key it usually serves.

## Acceptance Criteria
- [ ] ADR 0005 carries a short **dated amendment** noting that the `None`-arm `ValueError` was retired, why, and pointing at ADR 0006. Its existing reasoning is **not rewritten** — it was correct when written, and the change is more useful visible than edited away.
- [ ] ADR 0005's other decisions are left untouched: one resolver rather than two protocols, the derivation living in the library, scope as an unparameterized obligation, the flags naming the existing-values half, the optional resolver, `validate_data` sitting on the contract.
- [ ] `.ai-context/adrs/0006-*.md` exists, following `ADR-FORMAT.md` and the house style of 0001–0005.
- [ ] It records **why base checks name mechanics rather than meanings** — `unique: bool` on field constraints means a primary key is one arity of a general rule, and the business meaning is a label supplied at derivation.
- [ ] It records **why composites are the exception** — `IsValidPrimaryKey` names a meaning, because unpacking into one pandera check per sub-rule is what makes a failure legible: "not unique" and "already exists" are different problems, fixed differently.
- [ ] It records **why a foreign key is not one of them** — no such split exists, so `IsSubsetOf` is a single base check. The test of whether a composite is warranted is whether its sub-rules produce distinct, actionable messages.
- [ ] It records **why there is no `from_foreign_key`** — the asymmetry with `IsValidPrimaryKey`, and that `checks/` would otherwise import schema constructs; which layer resolves values and which decides `within`; and that the constructor is deferred rather than rejected, against the day caller-supplied checks give the derivation a second site.
- [ ] It records **why a check is identified by its failure message** — pandera displays a check by its `error=` string; an instance-level identity was tried and removed because mechanic + columns is not unique within a schema, and see WP2 for what the merge keys on instead.
- [ ] It records **why negation is a second class rather than a flag** — `IsIn` and `IsNotIn` are not exact complements once nulls are in play, and a flag would leave two opposite rules sharing one discriminator.
- [ ] It records **why checks are pydantic models** — the house style of `contracts/`, and it makes `name` a `Literal` discriminator that can be read from a spec and cannot be overridden on an instance.
- [ ] It records **why standard checks are not omittable** — they need nothing from outside the data, so nothing supplies them and nothing can drop them; a caller adds strictness and never removes it.
- [ ] It records **why an additional check replaces rather than adds** — report clarity, so one violation is reported once.
- [ ] It records **why the assembly sits on `TableSchema.validate_dataframe`** rather than in the runner (which would need the schema back) or the adapter (whose one job is format conversion).
- [ ] It records **why an unchecked external reference is silent**, and names validation reporting as the open follow-on.
- [ ] The ADR links to [`CONTEXT.md`](../../CONTEXT.md) for terminology rather than redefining terms.

## Implementation Details
- **Amend:** `.ai-context/adrs/0005-one-contract-resolver-supplies-definitions-and-values.md` — the table row reading `absent, external reference | cannot validate — raises` is the one that changed. Add the note; leave the prose.
- **Create:** `.ai-context/adrs/0006-<slug>.md`, following `.claude/skills/grill-with-docs/ADR-FORMAT.md`.
- **Already done — do not redo:** the `CONTEXT.md` half landed ahead of WP1. The *Validation* section defines **Check**, **Standard check** and **Additional check**, with two relationship lines including the guarantee that a caller adds strictness and can never remove it.
- **Terminology to use:** say **standard** and **additional** for the two kinds of check. Do not reintroduce "reference" for anything concerning data values — `CONTEXT.md` flags that overload and resolves it in favour of **Data validation** and **existing values**.
- **Out of scope, and worth saying so in the ADR:** validation reporting. With the `ValueError` retired, a frame with unchecked external references returns like one where they passed. That is accepted for now and is its own discussion.
- **PR:** own PR, conventional commit `docs:`.
- **Depends on:** `02-wire-in-the-checks.md` landing — write once the shape is real.
