# WP1 — Drop the routing-column `enum` ban

## Context

[ADR 0004](../../adrs/0004-submission-contracts-carry-extraction-instructions.md) states
that the routing field's `enum` is *derived* from the targets and never authored, and
`_check_routing_column` in
[submission_contract.py](../../../src/crosscontract/submission/submission_contract.py)
enforces that by rejecting an authored `enum`. Nothing ever built the derived set —
`TODO.md` still carries "Assemble the derived routing `enum`" as open work.

**That work is now cancelled, not deferred.** `Target.filters` is an arbitrary
column → value conjunction, so a target need not constrain the routing column at all and
the permitted set cannot be derived. Deriving it from only the subset of targets that
*do* mention the routing column would be actively wrong — it would reject rows legitimately
destined for a target that filters on other columns.

The derived enum also never answered the question it appeared to. It asserts that a
routing *vocabulary* is known, not that a row was *consumed*: a row carrying a known
routing value still vanishes when a second filter on another column fails to match. That
property is row coverage, it is only decidable against data, and WP2 delivers it.

With nothing deriving the `enum`, the ban has no remaining justification. An authored
`enum` becomes an ordinary field constraint like any other — an author who does know the
closed set may write one and get early, client-side feedback from schema validation.

## Acceptance Criteria

- [ ] `_check_routing_column` no longer rejects an authored `enum` on the routing field.
- [ ] The remaining routing-column rules are untouched: the field exists in the
      `tableschema`, is `required`, and is `type: string`. They still underwrite the
      derive-`filters`-from-`name` mechanism in `ExtractionInstructions`.
- [ ] A `SubmissionContract` whose routing field carries an authored `enum` validates
      successfully, with a test asserting it (replacing the test that asserted the raise).
- [ ] No enum-assembly helper, property, or method is added anywhere. This WP only
      removes; the derived enum is not being relocated.

## Implementation Details

**Modify:**

- `src/crosscontract/submission/submission_contract.py` — remove the
  `routing_field.constraints.enum is not None` branch from `_check_routing_column`, and
  amend the method docstring: the summary's final sentence ("Also the routing column
  cannot have an enum constraint as this is derived from the ExtractionInstructions") and
  the matching clause in `Raises:` both go.
- `src/tests/submission/test_submission_contract.py` — delete
  `test_routing_column_has_enum_constraint` (~line 71) and add a positive test in its
  place: set an `enum` on the routing field of `valid_data` and assert
  `model_validate` succeeds and the constraint survives on the loaded model.
- `src/tests/submission/example_submission.yaml` — the comment above the `variable`
  field (~line 40) says the field is "deliberately without an `enum`, which is derived
  from the targets below". The second half is now false. Keep the fixture free of an
  `enum` — it exercises the ordinary case — but fix the reason.

**Not in scope.** Do not add a cross-check that a target's routing filter value appears
in an authored `enum`. An author who writes an `enum` omitting a target's routing value
gets a loud schema-validation failure on the data itself; policing the spec against it is
a second mechanism for the same error. It is recorded as a non-goal in WP3.

**Dependencies:** none. This WP can land alone.

**Verification:** `uv run pytest src/tests/submission/` plus `uv run mypy
src/crosscontract/`. *Ask before running — see CLAUDE.md.*
