# feat: add the Submission contract type and the first transformation union

## Summary

Lays the two independent foundations for submission contracts (PRD
`2026-08-14-submission-contracts.md`, WP0 and WP1): a `Submission` contract type, and
the vocabulary of transformations plus the discriminated union that authored extraction
specs will dispatch on. Neither half depends on the other — `Submission` is inert until
something emits it, and the three new transformations are additive. The one behavioural
change is to `MapColumnValues.default_value` (below); no authored specs exist yet, so
nothing in the wild changes meaning.

The union is the higher-leverage half: no discriminated union over transformations had
ever been defined, and `DataInstructions` in the release spec is documented as an
extension point waiting for one. This PR supplies it.

Base branch is `dev`.

## Changes

**`Submission` contract type (WP0).** `ContractType` gains `"Submission"`, and
`CONTRACT_TYPE_TO_TABLE_TYPE` maps it onto the existing `General` table type. No new
schema class: the submission bundle is a standard flat table with a primary key and
foreign keys, so it needs its own contract type but not its own schema. This is the
first entry that makes the mapping non-identity, and the comment above the table was
rewritten accordingly — including the note that the relation is many-to-one, so a
`table_type` no longer determines a `contract_type`.

**Three new transformations (WP1).** Each is a pure function plus a thin
`BaseTransformation` subclass whose `apply()` is a single delegating call:

- `cast_column` / `CastColumn` — `to_type` is a `CastableType` literal spelled with the
  Frictionless field-type vocabulary (`integer`, `number`, `string`, `boolean`), not
  pandas dtype strings, so a bad value fails at load rather than at execution. Integer
  and number casts target the pandas nullable `Int64` / `Float64`, so fractional floats
  raise rather than truncating and nulls survive the cast. `datetime` is deliberately
  *not* a member: including it would let a spec validate at load and then fail at
  `apply()` time, which is precisely what the literal exists to prevent. The pure
  function keeps a dedicated branch raising a pointer to `parse_datetime_column`, since
  it is the obvious thing a direct caller tries. The literal is declared locally rather
  than imported from `contracts/schema/fields/`, because `contracts/` imports from this
  package and the reverse import would be circular.
- `parse_datetime_column` / `ParseDatetimeColumn` — `format` defaults to `None`
  (pandas infers); `format: mixed` and `dayfirst` pass through. Parse errors propagate
  from pandas unchanged.
- `drop_rows_by_value` / `DropRowsByValue` — boolean-mask filter, copied before it is
  returned so callers do not inherit a slice and the `SettingWithCopyWarning` that comes
  with it. The original index is preserved deliberately and pinned by tests.

**`TransformationUnion`.** New `transformation/union.py` holding
`Annotated[... , Field(discriminator="type")]` over all six transformations, following
the house idiom and the `field_descriptors/` split of classes from union. It imports the
leaf modules rather than the package `__init__`, which re-exports it — going through
`__init__` would be circular. Exported from both `transformation/` and
`transformations/`, along with the four new symbols that were previously reachable only
from the leaf module.

**`MapColumnValues` serialization.** `default_value` now defaults to the `KEEP_ORIGINAL`
sentinel directly, so `apply()` is a pure delegation instead of translating `None` into
the sentinel — which is what previously made "map unmapped entries to `None`"
unreachable from a spec. Because the sentinel has no serialized form and would crash the
JSON encoder, the field carries `exclude=True` and a `mode="wrap"` serializer re-adds
the key only when it holds a real value. Omission is therefore the default path, which
is exactly what "keep the original values" means on reload. Three cases now round-trip:
omitted → keep original, explicit `null` → `None` is the fallback, explicit value → that
value.

**Test restructure.** Function tests and spec tests for a transformation now live in the
same file and class, so `test_transformation_specs.py` is deleted and its
union-and-discrimination tests move to a new `test_union.py`. Two principles are applied
throughout: don't re-test pandas, and test spec pass-through by patching the underlying
function. `MapColumnValues` is the deliberate exception — its default handling is
involved enough to be worth exercising end to end.

That file's two chained-application tests (`test_ordered_application` and
`test_rename_after_drop_raises_on_missing_column`) are dropped rather than moved. There
is no function yet that applies a list of specs to a DataFrame, so a hand-rolled `for`
loop over `apply()` tests the test rather than the package. They return as integration
tests once that function exists.

**Docs.** PRD and task files updated as decisions were settled: §4.5 (no
`SubmissionSchema`), §5.3 (`SubmissionContract` shape and the deferred routing-enum
question), §5.4 (`project` renamed `project_name` to match the existing
`ContractService` keyword), §3.5 and §5.1 (integer casts keep nulls; datetime parse
errors come from pandas; the `format` default). WP0's task file is deleted, per the
convention of removing a task description once it lands. `CLAUDE.md` gains a section on
implementing only what was asked, as simply as possible.

**Housekeeping.** Removed two stale PR descriptions from `.github/PRs/`, and wrapped
four over-long `description=` strings in `_standards/frictionless/fields.py`.

## Testing

Suite reported green by the author.

- `test_union.py` — discriminator resolution parametrized over all six members,
  `extra="forbid"` through the union, and rejection of an unknown `type`.
- `test_column_transformations.py` — cast success matrix and error cases (kept
  deliberately broad, since type casting is sensitive and the behaviour is worth
  documenting), datetime wiring and kwarg pass-through, and a three-case round-trip test
  for `MapColumnValues` across both the python and JSON dump paths. The two halves of
  the `datetime` decision are pinned separately: the spec rejects it at load, while a
  direct call to `cast_column` still gets the pointer to `parse_datetime_column`.
- `test_dataframe_transformations.py` — per-transformation success and error cases plus
  a patched pass-through test for each spec.
- `test_contract_types.py` — `contract_type: Submission` resolving to `TableSchema`, and
  the pre-instantiated-schema pass-through parametrized over `General` and `Submission`,
  which is the branch that breaks if the lookup ever regresses to comparing
  `contract_type` against `table_type` directly.

## Notes for reviewer

**`submission_contract.py` lands as a draft and is finished in WP3.** It composes
`BaseContract, CrossMetaData` as a sibling and has `extraction` commented out behind a
TODO. The design settled later on inheriting `CrossContract` — for
`validate_references`'s `enforce_star_schema=True` default, which is correct here since
the submission foreign keys all point at dimensions, and to stay usable wherever a
`CrossContract` is accepted. PRD §5.3 and the WP3 task file record that shape.

Until then the class is deliberately inert: it is exported from nowhere, has no tests,
and — because it is not a `CrossContract` — has no `to_server()`, so
`ContractService.create()` cannot accept it. Nothing can reach it by accident. It
carries drafted docstrings so the file reads as intended rather than as an orphan; the
class docstring states the `Submission` → `General` mapping as a design fact rather than
as something this class performs, since `_inject_table_type` only runs on
`CrossContract`. That sentence can take its stronger form once WP3 changes the base.

**The `output_columns` hook was not implemented.** WP1's task file noted that adding it
while the transformations were being written is cheap and retrofitting is not. It went
in without. If WP3 adopts option (a) or (b) for column tracking, the cost is now
retrofitting all six rather than writing three — recorded in the WP3 task file.

**Still open, tracked in the WP4 task file:** `MapColumnValues` has no `on_conflict`
guard, so mapping a value onto one already present in the column merges the two
silently. On a foreign-key column that produces duplicate primary keys downstream,
breaking the sum invariant of ADR 0001.

**Worth extra scrutiny:** the `exclude=True` plus wrap-serializer pattern on
`MapColumnValues.default_value` is the only place in the package where a field is hidden
from the standard serializer and reinstated by hand. An earlier attempt using only a
wrap serializer crashed inside `handler(self)`, because the handler serializes the
sentinel before the callback can drop it; `exclude=True` is what keeps the handler away
from it. `model_json_schema()` emits a `PydanticJsonSchemaWarning` about the
non-serializable default and omits it — the resulting schema is correct, but the warning
is visible.
