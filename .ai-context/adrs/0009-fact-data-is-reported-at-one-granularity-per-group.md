# Fact data is reported at one granularity per group

Within one group of otherwise-identical rows, the dimension members a fact table reports
must form an antichain: no member present may be a proper ancestor of another member
present. A group is the row's primary key minus the dimension column being judged. The
rule is enforced by `HasNoDescendantInGroup`, derived per referencing column from a parent
map the caller supplies.

[ADR 0001](0001-dimensions-are-strict-trees.md) gives the **Sum invariant** for a
dimension's own table. This is its fact-side half: a valid dimension does not stop a
ValueVariable from reporting `(A, 2030, ch, 100)` alongside `(A, 2030, ch_ag, 30)`, and
summing the region column then counts the 30 twice. The dimension is still correct; the
data is not.

This replaces cleanup with prevention: `admin_tasks/delete_hierachy_duplicates.py` in the
sibling `cross_back` repository exists to find and delete such rows after the fact.

## Why an antichain and not "one level"

`ch` at level 0 beside `de_bavaria` at level 1 in the same group is legal and normal —
different branches, reported at whatever granularity each was measured. Requiring a single
level would reject it while catching nothing extra: two members on different branches
cannot double-count each other, whatever their levels. Only ancestry within a branch is a
defect, and ancestry is what the rule names.

## Why the group and not the whole column

Scenario A reporting at `ch` while scenario B reports at `ch_ag` and `ch_other` is legal.
Each group sums correctly on its own, and rolling both up to level 0 draws on different
rows. A column-wide rule would reject that, and it is a normal shape: two models are
alternative estimates of the same quantity, never additive parts of one, so one model
reporting a country total while another reports its regions is not double-counting
anything.

This is the point most likely to be re-litigated, which is why the counter-example is
recorded here rather than only in the PRD.

## Why the group is the primary key minus the dimension column

Because [ADR 0008](0008-a-value-variable-is-keys-plus-measures.md) makes every field
outside a ValueVariable's primary key `integer` or `number`. A dimension foreign key is a
string column, so it cannot fall out of the key, and neither can any other non-numeric
axis. The key is therefore the full set of columns that distinguish rows, and removing the
judged column from it leaves exactly the rows that ought to be comparable.

**The reasoning this replaces, because it is wrong and will otherwise be re-derived:** that
a distinguishing column missing from the key produces duplicate primary keys, which the
primary key check owns — the argument ADR 0008 uses for a different purpose. It holds only
when the missing column is the *sole* differentiator. Two rows differing in both an unkeyed
attribute and the dimension column have distinct primary keys, so the primary key check
says nothing, yet they collapse into one group here and legitimate data is rejected.

That is why derivation is restricted to a `ValueVariableSchema`. A `General` contract may
carry an unkeyed string attribute, so its group cannot be trusted, and it gets no
granularity check at all.

## Why the aggregate row is reported

`ch` fails because `ch_ag` is present, not the other way round. The aggregate is the row a
submitter has to act on: remove it, or move the detail into it. Reporting the detail row
would send them after data that is very likely correct. ADR 0001's mandatory
`<parent_id>_other` member is what makes the remedy always available — a partial
sub-level split can always be completed rather than abandoned.

## Consequences

- **This is a behaviour change for submitters, not only an addition.** Anyone reporting an
  aggregate alongside partial sub-level detail starts being rejected. The
  `can_delete=False` cases in the `cross_back` script are exactly those rows. The remedy is
  always available (above), but it will still break a pipeline the day it reaches that
  pipeline.
- **The default differs by entry point, on purpose.** `check_dimension_granularity`
  defaults `False` on `BaseContract.validate_data` and
  `ContractResource.validate_dataframe`, and `add_data` does not set it, so an existing
  uploader opts in when ready. `CrossSubmitter.validate_submission` defaults it `True`,
  beside the two key flags that are already `True` there: a submission is the strictest
  gate in the system, and `submit()` still raises `NotImplementedError`, so there is no
  installed base to break. This asymmetry is the grace period, and it is why no warn mode
  was built. Do not align the two defaults without deciding this again.
- **The check is in-frame only.** It compares the rows under validation against each other
  and reads nothing the contract already stores. A violation split across two uploads —
  the aggregate stored, the detail arriving now — is not caught. Closing that costs a wide
  read (the contract's own group columns and member over every stored row, not a small
  dimension table) and needs a second failure message, because "remove the aggregate row"
  names a row that is not in the frame.
- **The client-side result is advisory** ([ADR 0005](0005-one-contract-resolver-supplies-definitions-and-values.md)).
  A resolver reads through whatever the caller's permissions allow, and the platform
  re-validates on ingest. The guarantee lives in `cross_back`; this delivers early,
  actionable feedback.
- **Existing violations already on the platform are not addressed.** The `cross_back`
  script remains the tool for those and should be run before the check is enforced widely.
- **A flat `FlexibleDimension` is never checked.** The type test is `DimensionSchema`, not
  `BaseDimensionSchema`, which also matches `FlexibleDimensionSchema`. `dim_model` and
  `dim_scenario` are flat and referenced by nearly every ValueVariable, so the looser test
  would derive a check on almost every contract in the model. Note
  `ContractResource.is_dimension` uses the looser test for its own purposes.
- **The adapter trusts the caller's column list.** `_derive_checks` takes a mapping from
  column to parent map and builds one check per entry, refusing only a column the schema
  does not declare. Which references are hierarchical is decided in
  `BaseContract.validate_data`, which is the first caller to use both members of the
  **Contract resolver** in one operation — `resolve` to learn a reference is a dimension,
  `get_data` to read it. A caller reaching `to_pandera_schema` directly gets no such
  filtering.
- **A malformed parent map terminates rather than hangs.** The walk carries a `seen` set,
  so a cycle a resolver hands over stops at the repeat instead of looping, and a member
  never lands in its own ancestor chain.
