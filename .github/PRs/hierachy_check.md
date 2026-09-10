# Reject fact data that reports a dimension member alongside its own descendants

Base branch: `dev`.

## Summary

A hierarchical `Dimension` is a strict tree whose members roll up without overlap
([ADR 0001](../../.ai-context/adrs/0001-dimensions-are-strict-trees.md)), and
`IsValidCrossDimension` enforces that for the dimension table. Nothing enforced the
corresponding invariant on the fact side: a ValueVariable could carry a row for `ch` *and*
rows for `ch_ag` / `ch_other` under the same scenario and year, and summing the region
column then double-counts. The dimension is valid; the data is not.

This adds a validation check that rejects such an upload, replacing cleanup with
prevention — `admin_tasks/delete_hierachy_duplicates.py` in the sibling `cross_back`
repository exists to delete those rows after the fact. The rule: within one group of
otherwise-identical rows, the members present must form an antichain. It is recorded as
[ADR 0009](../../.ai-context/adrs/0009-fact-data-is-reported-at-one-granularity-per-group.md).

## Changes

**The check** — `contracts/schema/validation/checks/hierarchy_checks.py`

- `HasNoDescendantInGroup(BaseCheck)`: a column, its group columns, and a plain `dict`
  parent map. Sets rather than joins — each row marks the aggregates it is part of as
  covered within its own group, and a row fails when its own member is already marked.
  `O(rows x depth)`, with no `explode`/`merge`.
- Reports the **aggregate** row, since that is the row a submitter removes. A member
  missing from the parent map passes, as does a null member; an empty-string parent ends a
  chain; a cyclic parent map terminates via a `seen` set rather than hanging.
- `to_pandera()` is not overridden — one rule, one message. The message leads with
  `Columns '...'` so `SchemaValidationError` parses the columns back out and reports the
  offending row's values.

**Derivation** — `adapters/pandera_pandas/adapter.py`, `schema.py`

- `_derive_checks` gains `dimension_hierarchies: dict[str, dict[str, str | None]] | None`,
  keyed by the single referring column (**not** by `tuple(fk.fields)` like
  `foreign_key_values` — a qualifying foreign key always has exactly one field). Threaded
  unchanged through `convert`, `convert_schema`, `to_pandera_schema` and
  `validate_dataframe`.
- Group columns are `primaryKey.fields` minus the judged column. A column the schema does
  not declare raises `ValueError` rather than failing later inside pandera.

**Resolution** — `contracts/base_contract.py`

- `validate_data` gains `check_dimension_granularity`. When set, and only for a
  `ValueVariableSchema`, `_resolve_dimension_hierarchies` resolves each single-column
  external foreign key and keeps those whose `tableschema` is a `DimensionSchema` — **not**
  `BaseDimensionSchema`, which also matches `FlexibleDimensionSchema`. An unresolvable
  contract raises, naming the column and the contract.
- The parent map is read as `[reference.fields[0], "parent_id"]`, with nulls normalised so
  a root's parent reaches the check as `None`.

**Entry points** — `crossclient/services/contract_resource.py`, `submission/`

- `ContractResource.validate_dataframe` exposes the flag; `add_data` does not set it.
- `SubmissionHandler.validate_target` / `validate_targets` and
  `CrossSubmitter.validate_submission` expose and forward it. The submitter defaults it
  **`True`**, beside the two key flags already `True` there.

**Docs** — ADR 0009 (new), ADR 0001 (cross-link), the PRD, and eight task files under
`.ai-context/issues/`.

## Testing

`pytest`, `ruff` and `mypy` were run by the repository owner throughout; all green at each
step. New tests:

- `test_granularity_checks.py` — the predicate: the done-means pair, two models reporting
  at different granularities, siblings, transitivity through a missing level, `ch` +
  `ch_other`, unknown member, null member, null group column (a float `NaN`, the case that
  breaks tuple keys), empty-string parent, cyclic map, empty frame, single row, duplicate
  rows, multi-column group, and `to_pandera()`.
- `test_adapter.py` — derivation: `None` derives nothing; the column, group and label; two
  columns into one dimension get a check each; an unknown column raises; both `convert`
  entry points thread the argument.
- `test_validate_data.py` — resolution: the dimension is resolved and read, a
  `FlexibleDimension` never is, a `General` contract derives nothing, no resolver raises,
  the flag unset consults nothing, unresolvable raises, composite reference skipped.
- `test_integration_granularity.py` — the assembled schema: the done-means pair, the
  parsed report naming the column and pointing at the `ch` row, and a frame breaking the
  primary key, a foreign key and granularity in one lazy run reporting all three.
- `test_target_granularity.py` — the submission path inherits the check with no
  submission-specific code, keyed by target name. These caught a dropped forward in
  `SubmissionHandler.validate_target`, which is fixed here.

## Notes for reviewer

- **The check is in-frame only.** A violation split across two uploads — aggregate stored,
  detail arriving now — is not caught. Deferred deliberately: it needs a second failure
  message (the "remove the aggregate row" remedy names a row not in the frame) and it
  depends on whether `_add_data` appends or upserts. Both questions are recorded in PRD §4.
- **Two defaults, on purpose.** Off on the upload path so nothing an existing caller does
  starts rejecting; on for `validate_submission`. That asymmetry is the grace period, and
  it is why no warn mode was built — see ADR 0009's consequences before aligning them.
- **`DimensionSchema` vs `BaseDimensionSchema`** is the trap worth checking in review.
  `dim_model` and `dim_scenario` are flat and referenced by nearly every ValueVariable, so
  the looser test would derive a check on almost every contract in the model.
  `ContractResource.is_dimension` still uses the looser test for its own purpose.
- **Derivation is restricted to `ValueVariableSchema`** because the group is only sound
  where ADR 0008 forces every non-numeric field into the primary key. A `General` contract
  gets no check. The PRD originally justified the group differently, via duplicate primary
  keys; that argument is wrong when the dimension column is not the sole differentiator,
  and ADR 0009 records both the correction and what it replaces.
- `PanderaAdapter._derive_checks` trusts the caller's column list — a direct caller of
  `to_pandera_schema` gets none of the qualifying logic above.
- `.github/PRs/value_variables.md` is deleted here; it belonged to the previous PR.
