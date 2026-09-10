# Derive the granularity check in PanderaAdapter

## Context

**Part of PRD:** [.ai-context/prds/2026-09-08-dimension-granularity-check.md](../../prds/2026-09-08-dimension-granularity-check.md)

WP2, step 1. `_derive_checks` is the only place a schema becomes checks (ADR 0006), and
the caller supplies **values, never checks**. The adapter cannot know that a referenced
resource is a hierarchical dimension, so it receives the parent maps as a new optional
argument and decides only the mechanical part: which foreign keys qualify, and what the
group columns are.

## Acceptance Criteria

- [X] `PanderaAdapter._derive_checks` takes
  `dimension_hierarchies: dict[str, dict[str, str | None]] | None = None`, keyed by
  the single referring column — **not** by `tuple(fk.fields)` like
  `foreign_key_values`. A qualifying foreign key always has exactly one field (a
  `DimensionSchema` primary key is the single `id`), that field is the check's
  `column`, and the value type then matches `HasNoDescendantInGroup.parent_map`
  exactly, keeping `Any` out of the signature.
- [X] `None` → no such check is derived at all. A supplied mapping derives one check per
  qualifying foreign key. Same opt-in semantics as the key checks (ADR 0006).
- [X] Group columns are `primaryKey.fields` minus `fk.fields`, in the schema's declared
  order.
- [X] Guards (PRD §3), each of which skips the foreign key silently:
  no `primaryKey`; `fk.fields` not a subset of `primaryKey.fields`; a composite
  foreign key; a self-referencing foreign key (`reference.resource is None`).
- [X] git a The composite guard is an explicit `len(fk.fields) == 1` test, not a lookup that
  happens to miss. With a single-column key there is no sensible thing to look up for
  a multi-column foreign key, and an explicit refusal holds however the caller builds
  the mapping. Its test is only meaningful this way round.
- [X] The check is built with `label="dimension hierarchy"`.
- [X] Threaded through unchanged: `convert`, `convert_schema`,
  `TableSchema.to_pandera_schema`, `TableSchema.validate_dataframe` — each gaining the
  same argument with the same default and a docstring entry matching the existing
  `foreign_key_values` wording.
- [X] Tests in `test_adapter.py`: `None` → nothing derived; supplied → one check per
  qualifying key with the right `column`, `group_columns` and `label`; fk outside the
  primary key → nothing; no primary key → nothing; **two foreign keys into the same
  dimension → two checks, each excluding only its own column from the group** (a real
  shape in the model: `from` / `to` both referencing `dim_iso_region`).

## Implementation Details

- Modify:
  - `src/crosscontract/contracts/schema/adapters/pandera_pandas/adapter.py`
  - `src/crosscontract/contracts/schema/schema.py`
  - `src/tests/contracts/schema/adapters/pandera_pandas/test_adapter.py`
- The type test that decides *which* foreign keys are hierarchical does **not** live here —
  it needs `resolver.resolve` and belongs to `05`. The adapter qualifies a foreign key
  purely by its presence as a key in `dimension_hierarchies` plus the structural guards.
- Depends on `02`.
- Do not run pytest, ruff or mypy without asking (repo `CLAUDE.md`).
