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
- [ ] It records **why `skip_*` stays orthogonal to the resolver** — folding `resolver=None` into "skip both" would silently delete in-frame primary-key uniqueness checking.
- [ ] It records **why `validate_data` sits on the contract, not the schema** — the name is load-bearing, and `TableSchema` has none.
- [ ] It records **why `None` ≠ `[]` for external foreign keys only** — for a primary key the two genuinely mean the same thing, and a self-referencing foreign key takes its valid set from the frame.
- [ ] The ADR links to [`CONTEXT.md`](../../CONTEXT.md) for terminology rather than redefining terms.

## Implementation Details
- **Create:** `.ai-context/adrs/0005-<slug>.md`, following `.claude/skills/grill-with-docs/ADR-FORMAT.md`.
- **Already done — do not redo:** the `CONTEXT.md` half of this work package landed ahead of WP2. The *Validation* section defines **Well-formedness**, **Reference validation**, **Data validation**, **Contract resolver**, and **Existing values**, organized by what each check must fetch from outside the contract, plus three relationship lines and two flagged ambiguities.
- **Terminology to use:** say **existing values**, never "reference values" — "reference" already carries *reference validation* (definition against definition), and overloading it onto values is exactly the ambiguity flagged in `CONTEXT.md`.
- **PR:** own PR, conventional commit `docs:`.
- **Depends on:** `02-contract-resolver-and-validate-data.md` landing — write once the shape is real. May run concurrently with `03-migrate-client-onto-resolver.md`.
