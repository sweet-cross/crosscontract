# WP2 — Derive `filters` from `name`, drop the scalar shorthand

## Context
**Background:** [ADR 0004 — Submission contracts carry their extraction instructions](../../adrs/0004-submission-contracts-carry-extraction-instructions.md)

Once a target has a `name` (WP1), the authoring surface has three ways to say one thing:
omit `filters` and derive them, write a scalar `filters` and derive them from the routing
column, or write the mapping out. The first two do the same job by different routes, and
the enum derivation gets two paths to the same value.

This work package settles on two forms — `name`-derived or explicit mapping — and removes
the scalar shorthand.

## Acceptance Criteria
- [x] `filters` omitted with `name` given yields `{routing_column: name}`.
- [x] `filters` given as a mapping is stored verbatim; `name` plays no part in routing.
- [x] A scalar `filters` is rejected.
- [x] `filters` remains `dict[str, str]` and required on `Target` — the validator populates it, so the annotation never describes a shape the stored value cannot hold.
- [x] `example_submission.yaml` loads and both round-trip tests pass; the fixture keeps one `name`-derived target and one explicit-mapping target.
- [x] A missing or invalid `routing_column` still hands the input through untouched, so pydantic reports it rather than this validator failing first.

## Implementation Details

**Modify:**
- `src/crosscontract/submission/extraction/extraction_instruction.py` — rewrite the `field_validator("targets", mode="before")`
- `src/crosscontract/submission/extraction/target.py` — `filters` description
- `src/tests/submission/example_submission.yaml` — add names, convert the scalar target
- `src/tests/submission/extraction/test_extraction_instructions.py` — replace the scalar-expansion test

The existing validator expands a scalar `filters`; it now injects `{routing_column: name}`
when the `filters` **key is absent**. Everything else about it stays: it reads
`routing_column` off `info.data` (which is why it is a *field* validator on `targets`
rather than a model validator — the value is already validated and defaulted there), it
copies rather than mutating the caller's dicts, and it hands shapes it does not recognise
straight through.

A scalar `filters` becomes a plain `dict[str, str]` type error. Pydantic's own message is
enough — no authored file uses the old form, so nobody carries the habit.

**Descriptions to update.** `Target.filters` currently documents the shorthand ("a bare
value is accepted as shorthand for a single filter on the routing column"). The
`ExtractionInstructions.targets` description lists a target's parts without mentioning
`name`. Both are user-facing through the generated JSON Schema, not just docstrings.

**Tests:** `src/tests/submission/extraction/` and `src/tests/submission/`.

The round-trip tests are the real verification here rather than the unit cases: they push
the derived filters through a full serialize-and-reload cycle, so a derivation that is
wrong but well-formed still shows up.

**Dependencies:** WP1.

**Risk: highest of the three.** This is the only behavioural change, it touches the one
piece of non-trivial logic in the package, and a mis-derivation fails *silently* — the
model validates and the wrong rows are extracted. Review the validator body directly
rather than trusting the tests alone.
