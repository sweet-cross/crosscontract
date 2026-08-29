# WP4 — Record the decision (ADR 0005)

## Context
**Part of PRD:** [validation-architecture.md](../../prds/validation-architecture.md) — WP4

The protocol shape is consumed by `cross_back` and by step 2's submission validation, so
changing it later means coordinated releases across repositories. A future reader will
also wonder why one resolver carries two unrelated-looking methods, and why its reads
deliberately ignore the caller's permissions — which reads as a bug without the
rationale. Write it once the shape is real.

## Acceptance Criteria
- [ ] `.ai-context/adrs/0005-*.md` exists, following `ADR-FORMAT.md` and the house style of ADRs 0001–0004.
- [ ] It records **why one resolver rather than two protocols**: the two lookups are one job seen twice — a contract cannot answer anything about the world outside itself. It names the accepted cost (`validate_references` asks for a `get_data` it never calls; `FakeResolver` grows a stub).
- [ ] It records **why the derivation lives in the library** — `fk.fields` vs `fk.reference.fields` is silently wrong rather than a crash, so it must not be copy-pasted into consumers.
- [ ] It records **why scope is an unparameterized obligation** — the library has no notion of projects and never should.
- [ ] It records **why the flags name the *existing-values* half** (`check_existing_primary_key` / `check_existing_foreign_key`) rather than being `skip_*`: the positive polarity makes the default call honest about what it did not check, so the caller does not need an exception to tell them. It also notes that `cross_back` already used this polarity and had to invert it at the boundary.
- [ ] It records **why the resolver is optional** — `BaseContract` exists for use off the platform, where there is nothing to pass; and a null-object resolver returning empty frames is unsafe post-WP1, because `[]` now means "the referenced table is empty" and fails every row.
- [ ] It records **why `validate_data` sits on the contract, not the schema** — the name is load-bearing, and `TableSchema` has none.
- [ ] It records **why `None` ≠ `[]` for external foreign keys only** — for a primary key the two genuinely mean the same thing, and a self-referencing foreign key takes its valid set from the frame.
- [ ] The ADR links to [`CONTEXT.md`](../../CONTEXT.md) for terminology rather than redefining terms.
- [ ] A **handoff section** for the next PRD exists (see below). The deliverable is the written handoff, not the planning session itself.

## Hand off to the next PRD — validator-level checks

WP2 lands flag *names* the validator does not yet honour. `check_existing_*=False` should
mean "do not consult other contracts", but it currently suppresses the whole check. Two
requirements were agreed and deliberately deferred, because deciding them properly needs
its own planning and grilling session rather than being folded into WP2.

Write this section so the next session can start cold. It should record:

- **The requirement.** Internal consistency is unconditional: in-frame primary-key
  uniqueness and self-referencing foreign keys are checked **always**, whatever the
  flags say. The flags govern only whether **existing values** are additionally
  consulted. This belongs at the validator; it does not touch `validate_data`, which
  only passes values or does not.
- **The open question, left open on purpose.** Either (a) `skip_primary_key_validation` /
  `skip_foreign_key_validation` change meaning to cover only the existing-values
  comparison, keeping the flags; or (b) they disappear from the validator entirely, with
  presence-or-absence of values as the instruction — no `primary_key_values` means
  in-frame only, no entry for an external foreign key means it is not checked externally.
  (b) removes a signature that can express the contradiction "skip the check, and here
  are the values", but retires WP1's `None`-arm `ValueError` and drops two public
  parameters from `TableSchema.validate_dataframe`. Do not pre-decide this.
- **What survives either way.** WP1's `[]` semantics — an empty referenced table is a
  validation result, not an inability. Only the `None` arm is in question.
- **The shape already visible.** Whether the boolean pair becomes `checks: list[Check]`.
  What forces the question is per-check granularity: a foreign key has three states
  (self-referencing and checkable in-frame / external and needing values / not checked
  externally), and two booleans cannot carry that. A schema mixing self-referencing and
  external foreign keys is the case where the boolean version has no correct answer.
- **Feasibility already established.** The adapter builds foreign-key checks **per key**
  ([pandera_adapter.py:129](../../../src/crosscontract/contracts/schema/adapters/pandera_adapter.py#L129))
  and `_get_foreign_key_check` already distinguishes self-references internally via
  `referenced_fields`. Per-key granularity exists; what has to move is the outer flag
  gating the loop and the `ValueError` for an external key with no values.
- **Consumers to re-check.** `TableSchema.validate_dataframe`'s public signature,
  `ContractResource.validate_dataframe`, and `cross_back`'s `check_primary_key` /
  `check_foreign_keys` — which already use the positive polarity and would stop needing
  to invert it.

## Implementation Details
- **Create:** `.ai-context/adrs/0005-<slug>.md`, following `.claude/skills/grill-with-docs/ADR-FORMAT.md`.
- **Already done — do not redo:** the `CONTEXT.md` half of this work package landed ahead of WP2. The *Validation* section defines **Well-formedness**, **Reference validation**, **Data validation**, **Contract resolver**, and **Existing values**, organized by what each check must fetch from outside the contract, plus three relationship lines and two flagged ambiguities.
- **Terminology to use:** say **existing values**, never "reference values" — "reference" already carries *reference validation* (definition against definition), and overloading it onto values is exactly the ambiguity flagged in `CONTEXT.md`.
- **PR:** own PR, conventional commit `docs:`.
- **Depends on:** `02-contract-resolver-and-validate-data.md` landing — write once the shape is real. May run concurrently with `03-migrate-client-onto-resolver.md`.
