# Record the decision: ADR 0009 and the deferred stored-rows half

## Context

**Part of PRD:** [.ai-context/prds/2026-09-08-dimension-granularity-check.md](../../prds/2026-09-08-dimension-granularity-check.md)

The rule is a decision about the shape of fact data, and the group-derivation argument is
the point most likely to be re-litigated — so it gets written down. This task also parks
the stored-rows half that was cut from scope, with the questions that must be answered
before it can be picked up.

## Acceptance Criteria

- [X] `.ai-context/adrs/0009-fact-data-is-reported-at-one-granularity-per-group.md` exists,
  following the structure of the existing ADRs and cross-linked from ADR 0001.
- [X] It records: the decision (within a group of otherwise-identical rows, the members
  present form an antichain); why an antichain and not "one level" (the cross-branch
  counter-example from PRD §1); why the group and not the whole column (the
  cross-scenario counter-example); why the aggregate row is reported.
- [X] It records **why the group is sound**: `ValueVariableSchema` requires every field
  outside the primary key to be `integer` or `number`, so every non-numeric axis is in
  the key and no distinguishing column can fall out of the group. It explicitly records
  the reasoning this **replaces** — that a distinguishing column missing from the key
  produces duplicate primary keys which the primary key check owns — and why that is
  wrong (it holds only when the missing column is the sole differentiator), so it is
  not re-derived later. This is why derivation is restricted to `ValueVariableSchema`.
- [X] Consequences: the behaviour change for partial reporters and the `<parent_id>_other`
  remedy; the flag default as the grace period and the absence of a warn mode; the
  client result being advisory per ADR 0005; a `General` contract holding fact data
  getting no granularity check.
- [X] The deferred stored-rows half is recorded — in PRD §4 rather than
  `.ai-context/TODO.md`, decided at implementation time so the questions sit beside the
  scope decision that produced them —
  carrying both unresolved questions: **which row is reported** when the aggregate is
  the stored row and the detail is the uploaded one (the "remove the aggregate row"
  remedy names a row not in the frame), and **whether `_add_data` appends or upserts**
  (which decides whether re-uploading a corrected row is flagged against the row it
  replaces). It also notes the wide read it costs.

## Implementation Details

- Create: `.ai-context/adrs/0009-fact-data-is-reported-at-one-granularity-per-group.md`.
- Modify: `.ai-context/adrs/0001-dimensions-are-strict-trees.md` (cross-link only).
- A separate ADR rather than an amendment to 0001 was decided (PRD §6): 0001 decides the
  shape of a *dimension* and has no submitter-facing consequences; this decides the shape
  of *fact data* and its principal consequence is a behaviour change.
- Can land any time after `05`; independent of `06` and `07`.
