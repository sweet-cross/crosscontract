# WP0 — Add the `Submission` contract type and its schema class

## Context
**Part of PRD:** [2026-08-14-submission-contracts.md](../../prds/2026-08-14-submission-contracts.md) (§2.2, §4.5)

A submission bundle is a flat table with a primary key and foreign keys — genuinely
neither a Variable nor a Dimension. `General` would fit mechanically, but `CONTEXT.md`
documents it as legacy and "should no longer be chosen for new contracts", so a new
`Submission` type is added rather than deepening the dependency on a type whose
deprecation is undecided. Adding the literal here is inert until `to_server()` exposes
it, which is why this can land independently of any platform change.

## Acceptance Criteria
- [ ] `ContractType` includes `"Submission"`.
- [ ] `SubmissionSchema` exists with `table_type: Literal["Submission"]` and is a member of `AnyTableSchema`.
- [ ] A contract dict with `contract_type: Submission` routes through `_inject_table_type` and validates to `SubmissionSchema`.
- [ ] `SubmissionSchema` accepts the full cross2025 submission `tableschema` (11 fields, composite primary key, three foreign keys) unchanged.
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

**Decision required before starting (PRD §4.5).** `SubmissionSchema` cannot see
`extraction.routing_column` — that lives one layer up on the contract — so the routing
invariants land on `SubmissionContract` (task 04) and this class is left carrying only
the discriminator. Two options:

- **(a)** Accept the bare label. Minimal; `SubmissionSchema` is `TableSchema` plus a
  `table_type` literal.
- **(b)** Add a `RoutingFieldDescriptor` to `contracts/schema/field_descriptors/`
  alongside `ValueFieldDescriptor` / `TimeFieldDescriptor` / `LocationFieldDescriptor`.
  `SubmissionSchema` then self-validates via the `_mandatory_fields` pattern, and
  `extraction.routing_column` leaves the YAML entirely.

(b) is cleaner but widens the change into the descriptor layer and changes the
authored YAML. Pick before writing code; the rest of the PRD is unaffected either way.

**Dependencies:** none. Can run in parallel with task 02.
