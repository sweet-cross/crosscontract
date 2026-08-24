# WP3 — Transformation and composition

## Context

WP2 delivers the **E** of the handler's ETL trio. This is the **T**, plus the composition
that is the method most callers will actually use.

## Acceptance Criteria

- [x] `transform_target_data(df, target_name)` applies the target's
      **transformation profile first, then the target's own `transformations`**.
- [x] A target with a profile and no `transformations` of its own gets the profile's
      steps.
- [x] A target with `transformations` and no profile gets its own steps.
- [x] A target with neither is a no-op returning equivalent data.
- [x] `get_target_data(target_name)` returns  `transform_target_data(extract_target_data(target_name), target_name)`.
- [x] No transformation is reimplemented — each step is applied through its existing
      `TransformationUnion.apply`.

## Implementation Details

**Modify:**

- `src/crosscontract/submission/submission_handler.py`
- the handler test module created in WP2

### Ordering is load-bearing

[ADR 0004](../../adrs/0004-submission-contracts-carry-extraction-instructions.md) devotes
a section to this. Profiles are **append-only and do not compose**: the profile's steps
run first, the target's own run after. The ADR spells out why the conventional
base-first-`extends` reading would be a silent correctness bug — a profile renames
`timestamp` → `year` and casts it, so a target's own steps operate on columns that only
exist *after* the profile has run. Reversing the order produces pipelines addressing
columns that do not exist yet.

Resolving the profile is a plain lookup into
`self.specs.extraction.transformation_profiles`. `_check_transformation_profiles`
already guarantees that a referenced profile is defined, so no defensive branch is
needed for a missing one.

### The failure mode to test for

A target carrying a profile and **no** `transformations` of its own is not an edge case —
it is the majority shape in the reference spec. In
[cross2025_submission.yaml](../../prds/cross2025_submission.yaml), `carbon_emissions`
declares `transformation_profile: demand` and nothing else. An implementation that
iterates only `target.transformations` returns the raw filtered rows for it: wrong
columns, wrong dtypes, and a downstream validation failure that points at the *contract*
rather than at the handler. Build the test on that shape.

`district_heat_useful_energy_production` is the other shape worth copying — profile
`supply` plus its own `drop_rows_by_value` — and it is what pins the *order*, not just
the presence, of both halves.

### Note on `transform_target_data(df, target_name)`

The frame and the name are independent arguments, so a caller can pass one target's rows
with another target's name and get a plausible-looking wrong answer. Whether that
warrants a guard, or just a documented assumption, is an implementation-time call.

**Dependencies:** WP1, WP2.

**Verification:** `uv run pytest src/tests/submission/` plus `uv run mypy
src/crosscontract/`. Cover all four combinations (profile only, own only, both, neither),
with the both-case asserting order rather than merely that all steps ran. Prefer the real
`demand` / `supply` profiles from the reference YAML over synthetic ones for at least one
case. *Ask before running — see CLAUDE.md.*
