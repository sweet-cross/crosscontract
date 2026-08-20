# WP0 — Add the `Submission` contract type and its schema class

## Context
**Part of PRD:** [2026-08-14-submission-contracts.md](../../prds/2026-08-14-submission-contracts.md) (§2.2, §4.5)

A submission bundle is a flat table with a primary key and foreign keys — genuinely
neither a Variable nor a Dimension. `General` would fit mechanically, but `CONTEXT.md`
documents it as legacy and "should no longer be chosen for new contracts", so a new
`Submission` type is added rather than deepening the dependency on a type whose
deprecation is undecided.

`SubmissionContract` inherits from `CrossContract` (task 04), so it inherits
`tableschema: AnyTableSchema`, and `_inject_table_type` copies `contract_type` verbatim
into `tableschema.table_type`. A `SubmissionSchema` member in the union is therefore
required for the class to validate at all. That is the whole justification — see the
resolved decision below.

## Acceptance Criteria
- [ ] `ContractType` includes `"Submission"`.
- [ ] `SubmissionSchema` exists with `table_type: Literal["Submission"]` and is a member of `AnyTableSchema`.
- [ ] A contract dict with `contract_type: Submission` routes through `_inject_table_type` and validates to `SubmissionSchema`.
- [ ] Existing contract types (`General`, `Dimension`, `ValueVariable`, `FlexibleDimension`) still discriminate correctly — no regressions in `src/tests/contracts/schema/`.
- [ ] The §4.5 decision is recorded in the ADR stub or `TODO.md`, whichever WP4 uses.

## Implementation Details

**Create:**
- `src/crosscontract/contracts/schema/subschemas/submission.py` — `SubmissionSchema`

**Modify:**
- `src/crosscontract/contracts/contracts/cross_contract.py` — add `"Submission"` to the `ContractType` literal; add `SubmissionSchema` to the `AnyTableSchema` union
- `src/crosscontract/contracts/schema/subschemas/__init__.py` — export
- `src/crosscontract/contracts/schema/__init__.py` — re-export

Follow the existing subschema pattern (`dimension.py`, `flexible_dimension.py`,
`value_variable.py`), including the comment convention about the `table_type`
discriminator default.

### Resolved: `SubmissionSchema` carries only the discriminator (PRD §4.5, option (a))

`SubmissionSchema` is `TableSchema` plus a `table_type` literal — no added fields, no
added constraints. It exists as a **discriminator target**, not because the submission
table needs a special schema; the bundle genuinely is a standard flat table, and
`ValueVariableSchema` is the existing precedent for an otherwise-empty subclass.
If constraints are ever wanted, they go into a class that already exists.

The `RoutingFieldDescriptor` alternative was **not** taken. It would have moved the
routing invariants into the descriptor layer and removed `extraction.routing_column`
from the authored YAML, but it widens the change into `field_descriptors/` for a
concept that belongs to extraction rather than to the schema. The routing invariants
(§3.1) therefore live on `SubmissionContract` in task 04.

**Platform rollout is out of scope.** Adding the literal is inert for existing
contracts, and when the platform begins accepting submission contracts is the
platform's sequencing question, not this package's.

**Dependencies:** none. Can run in parallel with task 02.
