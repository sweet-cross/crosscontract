# Dimension granularity check PRD

> **Sequencing.** The companion PRD
> [2026-09-08-value-variable-is-keys-plus-measures.md](2026-09-08-value-variable-is-keys-plus-measures.md)
> has landed (#94), and it turns out to be load-bearing rather than merely convenient.
> `ValueVariableSchema` now requires every field outside the primary key to be `integer`
> or `number`, so every non-numeric axis — a dimension foreign key among them — is in the
> primary key by construction. That is what makes the group derivation in §4 sound; see
> §6, where it replaces the justification this PRD originally gave.

## 1. Overview

A hierarchical **Dimension** is a strict tree whose members roll up without overlap
([ADR 0001](../adrs/0001-dimensions-are-strict-trees.md)). That invariant holds for the
dimension table and is enforced by `IsValidCrossDimension`. Nothing enforces the
corresponding invariant on the **fact** side: a ValueVariable may today carry a row for
`ch` *and* rows for `ch_ag` / `ch_other` under the same scenario and year, and summing
over the region column then double-counts. The dimension is still valid; the data is not.

This has already happened in production — `admin_tasks/delete_hierachy_duplicates.py` in
the sibling `cross_back` repository exists to find and delete such rows after the fact.
This PRD replaces cleanup with prevention: a validation check that rejects the upload.

The rule, stated precisely: **within one group of otherwise-identical rows, no dimension
member present may be a proper ancestor of another member present.** The set of members
present in a group must form an antichain.

Two things this is *not*:

- It is **not** "all rows at one level". `ch` (level 0) alongside `de_bavaria` (level 1)
  in the same group is legal and normal — different branches, different reporting
  granularity. Only ancestry within a branch matters.
- It is **not** a column-wide rule. Scenario A reporting at `ch` while scenario B reports
  at `ch_ag` + `ch_other` is legal: each group sums correctly, and rolling both up to
  level 0 draws on different rows. Only *within* a group is it a violation. This is why
  the group is load-bearing and why the `cross_back` script groups the same way.

## 2. Core Requirements

- A new `Check` (per [ADR 0006](../adrs/0006-validation-is-a-set-of-check-objects.md)):
  a pydantic model holding a column, its group columns, and a parent map; callable as
  `__call__(df) -> pd.Series`; rendering itself via `to_pandera()`.
- The check flags the **aggregate** row, not the detail row. `ch` fails because `ch_ag` is
  present. That is the row a submitter must remove, and the failure message must say so.
- `PanderaAdapter._derive_checks` derives one such check per foreign key that points at a
  hierarchical `Dimension`, from a new optional argument. Following the established
  semantics: `None` means the check is not derived at all; a supplied mapping derives it.
- `BaseContract.validate_data` gains an opt-in flag. When set, it uses the resolver to
  (a) identify which foreign keys point at a `DimensionSchema` and (b) fetch that
  dimension's `id` / `parent_id` rows to build the parent map.
- The check is **in-frame only**. It compares the rows of the frame under validation
  against each other and against nothing else; the contract's already-stored rows are not
  read. That is how the rule is normally applied, and the stored-rows half is deferred —
  see the decision in §4.
- `ContractResource.validate_dataframe` exposes the flag. `add_data` does **not** set it,
  so the check ships dormant and a caller opts in explicitly.

Done means: uploading `(A, 2030, ch, 100)` and `(A, 2030, ch_ag, 30)` together raises
`SchemaValidationError` naming the `ch` row; uploading `(A, 2030, ch, 100)` and
`(B, 2030, ch_ag, 30)` succeeds.

## 3. Edge Cases & Error Handling

### Which foreign keys get a check

| Case | Behaviour |
|---|---|
| Foreign key to a `DimensionSchema` | Check derived. |
| Foreign key to a `FlexibleDimensionSchema` | **Skipped.** Flat — no hierarchy, no ancestry, nothing to check. The resolved type test must be `DimensionSchema`, **not** `BaseDimensionSchema`, which also matches `FlexibleDimensionSchema` — the same trap already documented in `.ai-context/TODO.md` for `from_server`/`to_server`. **This is not hypothetical:** `dim_model` and `dim_scenario` are the corpus's two FlexibleDimensions and nearly every ValueVariable references both, so a `BaseDimensionSchema` test would wrongly derive a check on almost every contract in the model. |
| Self-referencing foreign key (`reference.resource is None`) | Skipped. Only a dimension's own `parent_id` is self-referencing, and a Dimension contract is not a fact table. |
| Foreign key to a `TableSchema` ("General") | Skipped. |
| Contract whose own `tableschema` is not a `ValueVariableSchema` | **Skipped — no check derived at all.** The group is `primaryKey - fk.fields`, and that is only a sound row identity where every non-numeric field is guaranteed to be in the primary key, which `ValueVariableSchema` enforces and no other schema does. A `General` contract may carry an unkeyed string attribute; two rows differing in both that attribute and the dimension column then have distinct primary keys — so the primary key check stays silent — while collapsing into one group here, and legitimate rows are rejected. Restricting derivation is one type test and keeps the check sound wherever it runs. The cost is that a `General` contract holding fact data gets no granularity check. |
| Referenced contract does not resolve | **Raise**, naming the contract. Consistent with `validate_references` and with ADR 0005's treatment of an unresolvable contract as a wiring error rather than a data failure. |
| Composite foreign key into a dimension | A `DimensionSchema` primary key is the single `id`, so a composite key referencing it is malformed. Skip and leave it to reference validation; do not attempt a multi-column ancestry. The corpus has no such case — but composite keys into a *Flexible* dimension are universal (`[scenario_group, scenario_name, scenario_variant]` → `dim_scenario`), and those are already skipped by the type test above. |
| Foreign key fields not a subset of `primaryKey.fields` | **Skipped.** Rows differing only in that column are already duplicate primary keys, so `IsValidPrimaryKey` owns the defect — "one mistake, one message". After the companion PRD this state is unreachable for a ValueVariable (a dimension `id` is `string`, non-key fields are numeric), but the guard stays as insurance: nothing enforces that a referring field's type matches the referenced field's. |
| No `primaryKey` at all | Skipped — no row identity, no group. Unreachable for a ValueVariable after the companion PRD; still reachable for a `General` contract. |
| Two foreign keys into the *same* dimension (`origin_region`, `destination_region`) | Each gets its own check; the other column stays in its group. Falls out with no special handling. |
| Several dimension foreign keys | One check each. Falls out. The normal case here — a result contract references half a dozen hierarchical dimensions. |

**Audit of the guards.** Against the corpus at `/Users/jan/git/data_model_tmp/data`
(70 contracts), all three skip conditions are currently unreachable: every dimension
foreign key's fields are a subset of its contract's primary key (0 violations), there are
no composite foreign keys into a hierarchical `Dimension` (0), and every referenced
contract resolves (0). 17 hierarchical dimensions are referenced across the model
(`dim_iso_region`, `dim_fuel`, `dim_tech_*`, `dim_use_*`, `dim_trn_mode_*`,
`dim_building`, `dim_endusesector`, `dim_resource`). So the guards are insurance against
future or hand-authored contracts, not handling for existing data — they should still be
written and tested, but nothing in the corpus depends on them.

### Within the check

| Case | Behaviour |
|---|---|
| Member in the data absent from the parent map | Passes this check. It has no ancestors and cannot be an ancestor of anything present. "Unknown member" is `IsSubsetOf`'s defect to report. |
| Null in the dimension column | Passes — but the predicate must return `True` for it itself. Do **not** delegate this to `ignore_na`: on a DataFrame-level pandera check `ignore_na` does not filter rows before the predicate runs (it only suppresses null cells from the reported `failure_cases`), so it cannot make a row pass. The same reason `IsSubsetOf` and `IsNotNull` handle nulls in `__call__`. The flip side is that `ignore_na` also cannot drop a row with a null group column, so the row below is safe. |
| Null in a *group* column | The row still forms a group with other rows sharing that null. Verify the grouping implementation treats NaN keys as equal rather than dropping them — `groupby` drops null keys by default, which is precisely the bug called out for `EachLevelHasOther` in ADR 0006's consequences. Prefer a set-based grouping over `groupby` (see §4), which sidesteps it. |
| `parent_id` empty string vs. null | Both mean "no parent" and terminate the chain. `EachLevelHasOther` reads an empty string as a real parent id while `RootElementHasNoParent` reads it as no parent; that inconsistency is pre-existing and must not be inherited here. Pick "empty or null terminates" and test both. |
| Cycle in the parent map | The dimension's own validation forbids one, but a resolver can return anything. Carry a `seen` set while walking, exactly as `CrossDimension._build_ancestry_chains` does, so a malformed dimension cannot hang an upload. |
| A member and its `_other` sibling (`ch` + `ch_other`) | Violation — `ch_other`'s parent is `ch`. This is the user-facing motivating example and gets its own test. |
| `ch_ag` + `ch_other` (two siblings, no parent) | Passes. Siblings are an antichain. |
| Grandparent and grandchild, parent absent (`ch` + `ch_ag_zurich`) | Violation. Proper ancestry is transitive, not just the direct parent. |
| Empty DataFrame | Passes. |
| Group of one row | Passes. |
| Duplicate rows (same group, same member) | Not this check's defect — `IsUnique` on the primary key owns it. A member is not its own proper ancestor, so this check passes them. |
| Very large fact table | See §4 for the complexity note; no explode/merge. |

### Reporting

Pandera carries exactly one string per check into `failure_cases`, and
`SchemaValidationError` parses the columns back out of it (ADR 0006). The failure message
must therefore name the column and describe the defect in one line, e.g.:

```
Granularity violation in 'region': a row reports an aggregate member while rows
for its descendants are present in the same group. Remove the aggregate row, or
move the detail into the aggregate.
```

Unlike `IsValidCrossDimension` this is **not** a composite: there is one rule and one
actionable message, so `to_pandera()` returns a single check. Compare `IsSubsetOf`, which
ADR 0006 argues is a single check for the same reason.

## 4. Implementation Decisions & File Paths

### The check

A single check class. Working name `HasNoDescendantInGroup` — per ADR 0006 a base check
names its *mechanics*, and this names the failing row's actual defect (a descendant of
mine is present) rather than a domain meaning. Alternatives to weigh when implementing:
`IsMinimalWithinGroup`, `HierarchyCheck`. What the rule *means* on a given schema is
carried by `label`, supplied at derivation ("dimension granularity").

Fields:

- `column: str` — the dimension foreign key column in the data.
- `group_columns: list[str]` — the columns defining the group.
- `parent_map: dict[Any, Any]` — member id → parent id, from the referenced dimension.

**The check takes a plain `dict`, never a `CrossDimension`.** `CrossDimension` lives in
`registry/`, a layer above; `checks/` depends on pandas, pandera and pydantic only, and
ADR 0006 is explicit about keeping it that way. `CrossDimension` may build such a dict
for a registry-side caller, but it cannot be the input type.

Algorithm — sets, not joins:

1. Build proper-ancestor chains from `parent_map` once, with a `seen` guard.
2. `implied = {(group_key, ancestor) for each present row, for each proper ancestor of
   its member}`, over the frame's rows.
3. A row fails iff `(its group_key, its own member) in implied`.

`O(rows x depth)` with hash lookups. This is the `cross_back` script's logic without its
`explode` + `merge`, which materialise a frame several times the input size.

A new module rather than an addition to `dimension_checks.py`: the checks there are rules
about a *dimension's own table*, this is a rule about a *fact table that references one*.
Different subject, and `dimension_checks.py`'s `DimensionCheck` base (with its `id_col` /
`parent_id_col` / `level_col` fields) does not fit. The working name `hierarchy_checks.py`
reads confusingly next to `dimension_checks.py`, though — prefer a filename that names the
fact-table subject. Settle it at implementation time; `reference_checks.py` is the other
plausible home.

### The plumbing

The adapter cannot decide this on its own: a `TableSchema` knows a foreign key names a
resource, but not that the resource is a Dimension. That needs `resolver.resolve`, which
lives at the contract layer. So the decision is made in `validate_data` and reaches the
adapter as **values, never checks** (ADR 0006) — the same path `foreign_key_values`
already takes.

New argument, keyed like `foreign_key_values` by `tuple(fk.fields)`:

```python
dimension_hierarchies: dict[tuple[str, ...], dict[Any, Any]] | None = None
```

threaded through `_derive_checks` → `convert` → `convert_schema` →
`TableSchema.to_pandera_schema` → `TableSchema.validate_dataframe`.

In `BaseContract.validate_data`, a new flag — working name
`check_dimension_granularity: bool = False`, defaulting `False` like its siblings and
naming what it *does* rather than what it skips (ADR 0005). When set:

1. Require a resolver, reusing the existing "checking against existing values requires a
   resolver" raise.
2. For each foreign key, `resolver.resolve(fk.reference.resource)`; keep those whose
   `tableschema` is a `DimensionSchema`.
3. Build the parent map from `resolver.get_data(dim_name, columns=[id_col, parent_col],
   unique=True)`.
4. Group columns: `primaryKey.fields` minus `fk.fields`, subject to the §3 guards.

**Deriving the dimension's column names.** `fk.reference.fields` gives the referenced
column (`id`). The parent column is the field of the resolved dimension's *own*
self-referencing foreign key (`fields: ["parent_id"], reference: {fields: ["id"]}` in
`DIMENSION_SCHEMA_TEMPLATE`). Reading it off the schema is two lines and avoids magic
strings; hardcoding `"id"` / `"parent_id"` is defensible because `DimensionSchema` is
rigid. Decide at implementation; the PRD leans to reading it off the schema.

**Decided: the stored-rows half is out of scope**, and `existing` is not added to the
check. The rule is normally applied in-frame, and the deferred half has two unresolved
questions of its own:

- *Which row is reported.* This check reports the aggregate row and tells the submitter to
  remove it. When the aggregate is the **stored** row and the detail is the uploaded one,
  the only row pandera can flag is the uploaded detail row, and that remedy is wrong — the
  row to remove is not in the frame. One rule, one message does not survive the split; a
  second message would be needed, and this PRD has not written it.
- *Idempotency.* Whether `_add_data` appends or upserts decides whether re-uploading a
  corrected row is flagged as a violation against the very row it replaces. See §5.

It is also the only part that costs a wide read — the contract's own
`group_columns + column` over every stored row, not a small dimension table. The
parent-map fetch is cheap (dimensions are small) and is not conflated with it. So
`validate_data` takes **one flag**, and what that flag buys is the parent-map fetch.
Capture the deferred half in [TODO.md](../TODO.md) with both questions above.

### Files

Create:

- `src/crosscontract/contracts/schema/validation/checks/hierarchy_checks.py`
- `src/tests/contracts/schema/validation/checks/test_hierarchy_checks.py`

Modify:

- `src/crosscontract/contracts/schema/validation/checks/__init__.py` — export the check.
- `src/crosscontract/contracts/schema/adapters/pandera_pandas/adapter.py` —
  `_derive_checks`, `convert`, `convert_schema`.
- `src/crosscontract/contracts/schema/schema.py` — `to_pandera_schema`,
  `validate_dataframe`.
- `src/crosscontract/contracts/contracts/base_contract.py` — `validate_data`; the
  resolve-and-build step. Consider a private helper beside `_get_existing_values`, which
  returns tuples and does not fit a dict-shaped result.
- `src/crosscontract/crossclient/services/contract_resource.py` —
  `validate_dataframe` gains the flag. `add_data` does not set it (§5).
- `src/tests/contracts/schema/adapters/pandera_pandas/test_adapter.py`,
  `src/tests/contracts/contracts/test_base_contract.py` (or equivalent) — derivation and
  plumbing tests.

Out of scope, explicitly: the child/descendant map on `CrossDimension`. It is the
*inverse* of what this check needs (the check walks up, `_build_ancestry_chains` already
does that), it cannot be the check's input for the layering reason above, and it is
already captured as its own item in [TODO.md](../TODO.md).

## 5. Data & Schema Changes

No schema model changes — those are the companion PRD's. No database migration.

One interaction with the companion PRD, and it works in this check's favour. That PRD
promotes `unit` into the primary key of the 18 assumption contracts, so `unit` becomes a
group column here. That is the correct grouping: the same quantity reported in two units
is two measurements, and rows in different units must never be compared for granularity —
`(A, 2030, ch, CHF)` alongside `(A, 2030, ch_ag, EUR)` is not a violation, while
`(A, 2030, ch, CHF)` alongside `(A, 2030, ch_ag, CHF)` is. Taking the group from the
primary key gets this right for free; a group inferred from column names would not.

Nothing changes for today's data, since those datasets are currently single-unit — but the
check stays correct when they stop being.

**This is a behaviour change for submitters, not only an addition.** Anyone currently
reporting an aggregate alongside partial sub-level detail starts being rejected. The
`can_delete=False` cases in the `cross_back` script are exactly those rows: aggregates
whose descendants do *not* sum to them, i.e. partial reporting. Under ADR 0001 the
correct answer is to put the remainder in `<parent_id>_other`, which the mandatory
catch-all member guarantees always exists — so the rule is always satisfiable. It will
still break a pipeline the day it ships.

Two things follow:

- **Decided: it raises, and there is no warn mode.** The grace period is bought by the
  flag's default, not by a third behaviour: `check_dimension_granularity` defaults `False`
  and `add_data` does not set it, so nothing starts rejecting on the day this ships and a
  submitter opts in when ready. A warn mode would add a third state to five layers to buy
  what the default already gives.
- Existing violations already on the platform are not this PRD's business — the
  `cross_back` script remains the tool for those, and should be run before the check is
  enforced, or contracts will reject *corrections* to data they already hold once the
  stored-rows half is enabled.

Per ADR 0005 the client-side result is **advisory**: a resolver reads through whatever the
caller's permissions allow, and the platform re-validates on ingest. The guarantee lives
in `cross_back`. This PRD delivers early, actionable feedback, not the guarantee.

## 6. Related ADRs

- **[ADR 0001 — Dimensions are strict trees](../adrs/0001-dimensions-are-strict-trees.md).**
  Supplies the invariant. This PRD extends its reach from the dimension table to the fact
  data referencing it; the mandatory `other` / `<parent_id>_other` members are what make
  the new rule always satisfiable.
- **[ADR 0006 — Validation is a set of check objects](../adrs/0006-validation-is-a-set-of-check-objects.md).**
  Complied with throughout: a check is a pydantic model with `__call__` and
  `to_pandera()`; there is one derivation point (`_derive_checks`); the caller supplies
  **values, never checks**; `None` versus a supplied mapping is "do not check" versus
  "check"; the check is identified by its failure message; and the check stays in
  `checks/`, which imports nothing from `contracts/schema/reference/` or `registry/`.
- **[ADR 0005 — One contract resolver supplies definitions and values](../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md).**
  This is the first caller to use **both** protocol members in one operation — `resolve`
  to learn a reference is hierarchical, `get_data` to read it. That is the ADR's stated
  reason for keeping one protocol rather than two, so this is corroboration, not a
  deviation. The positive flag polarity follows its "flags name the stored-value half"
  section.
- **[ADR 0007 — The submitter is the provider-side mirror of the registry](../adrs/0007-the-submitter-is-the-provider-side-mirror-of-the-registry.md).**
  No change needed. The check lives at the *variable* level, on the target contract's
  `validate_data`. A submission bundle is split into targets first and each target then
  validates as an ordinary variable, so `SubmissionHandler.validate_target` inherits the
  check with no submission-specific code.

### New ADR (decided)

A new ADR, working title **"Fact data is reported at one granularity per group"** (next
free number). It should record:

- The decision: within a group of otherwise-identical rows, the dimension members present
  form an antichain.
- Why an antichain and not "one level" — the cross-branch counter-example from §1.
- Why the group and not the whole column — the cross-scenario counter-example from §1.
  This is the point most likely to be re-litigated, so the example belongs in the ADR
  rather than only here.
- Why the group is `primaryKey - fk.fields`, and why it is sound: because
  `ValueVariableSchema` requires every field outside the primary key to be `integer` or
  `number`, every non-numeric axis is in the key, so no column that distinguishes rows can
  fall out of the group. Record the reasoning this **replaces**, because it is wrong and
  will otherwise be re-derived: that a distinguishing column missing from the key produces
  duplicate primary keys which the primary key check owns. That holds only when the
  missing column is the *sole* differentiator. Two rows differing in both an unkeyed
  attribute and the dimension column have distinct primary keys — the primary key check
  says nothing — yet collapse into one group, and legitimate data is rejected. This is why
  derivation is restricted to `ValueVariableSchema` (§3), which is the guarantee the
  soundness actually rests on.
- Why the aggregate row is reported rather than the detail row.
- Consequences: the behaviour change for partial reporters and the `<parent_id>_other`
  remedy; the client result being advisory per ADR 0005; the wide read the stored-rows
  half costs.

**Decided: a separate ADR, cross-linked to ADR 0001, rather than an amendment to it.**
ADR 0001 decides the *shape of a dimension* and has no submitter-facing consequences; this
decides the *shape of fact data* and its principal consequence is a behaviour change for
partial reporters. Different decisions with different consequence sections, so they are
recorded separately and linked.

## 7. Testing Strategy

### Unit — the check (`test_hierarchy_checks.py`)

Fixture: a three-level parent map, e.g.
`{"ch": None, "de": None, "other": None, "ch_ag": "ch", "ch_other": "ch",
"ch_ag_zurich": "ch_ag", "ch_ag_other": "ch_ag"}`.

- Aggregate plus descendant in one group → the **aggregate row** fails, the descendant
  passes. Assert which row, not just that something failed.
- Aggregate and descendant in *different* groups → all pass. The core false-positive
  guard.
- Two siblings in one group → all pass.
- Grandparent plus grandchild, parent absent → grandparent fails (transitivity).
- `ch` + `ch_other` → `ch` fails (the motivating example).
- Member absent from the parent map → passes.
- Null in the dimension column → passes.
- Null in a group column → rows sharing the null group together; assert they are compared,
  not dropped.
- Empty-string parent treated as no parent.
- Cyclic parent map → terminates and does not hang.
- Empty DataFrame → passes.
- Multi-column group.
- `to_pandera()` returns exactly one check, and its `error` is `failure_message()`.

### Unit — derivation (`test_adapter.py`)

- `dimension_hierarchies=None` → no such check derived.
- Supplied → one check per qualifying foreign key, with the right `column`,
  `group_columns` and `label`.
- Foreign key outside the primary key → no check derived.
- No primary key → no check derived.
- Two foreign keys into the same dimension → two checks, each excluding only its own
  column from the group. A real shape in the model (`from` / `to` both referencing
  `dim_iso_region`), so it gets a test rather than being left to fall out.
- Contract whose `tableschema` is not a `ValueVariableSchema` → no check derived.

### Unit — `validate_data`

Test doubles for `ContractResolver` already exist in the suite; extend one to return a
`DimensionSchema` contract and a two-column frame.

- Flag set, foreign key to a `Dimension` → resolver asked for the dimension, check runs.
- Flag set, foreign key to a `FlexibleDimension` → resolver may be asked, no check runs.
  **The regression test that matters** — a `BaseDimensionSchema` isinstance test passes
  this case wrongly.
- Flag set, contract is not a `ValueVariable` → no check runs.
- Flag set, no resolver → raises, message names the contract and the remedy.
- Flag unset → resolver not consulted for hierarchies at all.
- Unresolvable referenced contract → raises naming it.

### Integration

- `TableSchema.validate_dataframe` end-to-end: a violating frame raises
  `SchemaValidationError`, and the parsed error names the dimension column.
- Alongside a primary key violation and a foreign key violation in one lazy run: all three
  are reported, each by the rule that owns it.
- Through `SubmissionHandler.validate_target`, to confirm the submission path inherits the
  check with no submission-specific code — this is the ADR 0007 claim in §6 and it should
  be tested rather than asserted.

Per the repository's `CLAUDE.md`, do not run `pytest`, `ruff`, `mypy` or `coverage`
without asking first.
