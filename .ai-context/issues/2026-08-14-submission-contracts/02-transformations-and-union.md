# WP1 — Three new transformations and the first `TransformationUnion`

## Context
**Part of PRD:** [2026-08-14-submission-contracts.md](../../prds/2026-08-14-submission-contracts.md) (§4.4, §5.1, §5.5)

Only three transformations exist today (`RenameColumns`, `DropColumns`,
`MapColumnValues`), and **no discriminated union over them has ever been defined** —
`DataInstructions` in the release spec documents transformations as a future extension
point still waiting for one. This task supplies both the missing vocabulary and the
union, making it the highest-leverage step in the PRD: the pattern established here is
what every future Build spec inherits.

## Acceptance Criteria
- [x] `cast_column` / `CastColumn`, `parse_datetime_column` / `ParseDatetimeColumn`, `drop_rows_by_value` / `DropRowsByValue` exist, each as a pure function plus a `BaseTransformation` subclass.
- [x] `TransformationUnion` dispatches all six transformations on `type` alone; an unknown `type` raises.
- [x] Every new transformation returns a new frame and leaves its input **unmutated**.
- [ ] `cast_column`'s `to_type` reuses the Frictionless field-type literals from `contracts/schema/fields/` — no parallel pandas-dtype vocabulary.
- [x] Integer cast over NaN raises, naming the column and the offending row count.
- [x] Integer cast over floats with fractional parts raises rather than truncating.
- [x] `parse_datetime_column` raises on unparseable values with a bounded sample in the message; `format: mixed` and `dayfirst` pass through to pandas.
- [x] Every field carries a `description=`; no bare `Any` where a narrower type will do.
- [ ] The §5.5 `MapColumnValues` gap is either fixed or recorded in `TODO.md` — decided, not left silent.

## Implementation Details

**Create:**
- `src/crosscontract/transformations/transformation/union.py` — `TransformationUnion`

Mirrors `contracts/schema/field_descriptors/`, which splits the classes
(`descriptors.py`) from the union (`field_descriptors.py`). Use the house idiom:
`Annotated[A | B | ..., Field(discriminator="type")]`.

**Modify:**
- `src/crosscontract/transformations/transformation/column_transformations.py` — add `cast_column` / `CastColumn`, `parse_datetime_column` / `ParseDatetimeColumn`
- `src/crosscontract/transformations/transformation/dataframe_transformations.py` — add `drop_rows_by_value` / `DropRowsByValue`
- `src/crosscontract/transformations/transformation/__init__.py` — exports
- `src/crosscontract/transformations/__init__.py` — re-exports

No new transformation modules: the two casts are column-scoped and belong in
`column_transformations.py`; `drop_rows_by_value` changes row cardinality and belongs
in `dataframe_transformations.py`.

**Model shapes (PRD §5.1):**

| `type` | Fields |
|---|---|
| `cast_column` | `column_name: str`, `to_type` (Frictionless field-type literal) |
| `parse_datetime_column` | `column_name: str`, `format: str = "%Y-%m-%d %H:%M"`, `dayfirst: bool = False` |
| `drop_rows_by_value` | `column_name: str`, `values: list[Any]` |

`parse_datetime_column`'s default mirrors `DateTimeField.format`, but note they mean
different things: the contract's `format` is the *canonical stored* form, this one the
*incoming* form. They legitimately differ per submission (cross2022 uses
`%m/%d/%y %H:%M`, cross2025 uses `mixed` + `dayfirst: true`).

**Extensibility rules to honour** — adding a transformation later must stay "one class
plus one union entry" (PRD §4.4): `type: Literal["snake_case"]` matching the function
name; `extra="forbid"` (inherited); pure `df -> df`; every field described.

**The function is the first-class citizen; the model is its pydantic projection.**
The pure function is the transformation. The `BaseTransformation` subclass exists only
to make that function's signature declarable in YAML and checkable by pydantic — so the
model's fields mirror the function's parameters, and:

> `apply()` is a pure delegation. Any translation inside it means the model has drifted
> from the function, and the fix belongs in the function's signature — not in `apply()`.

Write each new transformation function-first, using only YAML-expressible types: no
module-level sentinels, no bare `Any` where a literal will do. If the model cannot
mirror the signature, the signature is wrong. `output_columns` (below) is the one
legitimate model-only member — it is metadata *about* the function for static checking,
not part of the pandas call.

This also settles a question raised against the split: the function is not folded into
the class as a static method, because that would make it a member of its own
projection and invert the dependency. The functions are additionally published API
(`__all__` of `crosscontract.transformations`), so collapsing them is a breaking change
and out of scope here.

**Optional `output_columns` hook.** If task 04 adopts option (b) for column tracking
(PRD §3.4), the three transformations here should implement
`output_columns(input_columns) -> set[str] | None`. Coordinate with task 04 before
finalising the base class; implementing it here is cheap, retrofitting is not.

**Known gap to decide (PRD §5.5).** `MapColumnValues` has no equivalent of the legacy
`rename_items_in_column` conflict guard, and its `default_value=None` collides with
"keep original" (admitted in its own docstring). Migrating the legacy extractors
changes behaviour on both counts, and on a foreign-key column a silent merge produces
duplicate primary keys downstream — breaking the sum invariant of
[ADR 0001](../../adrs/0001-dimensions-are-strict-trees.md). Add an `on_conflict`
option or record it; do not migrate silently.

This is the worked example of the rule above. `map_column_values` defaults
`default_value` to the module sentinel `KEEP_ORIGINAL`, which YAML cannot express, so
`MapColumnValues.apply` translates:

```python
default_value = KEEP_ORIGINAL if self.default_value is None else self.default_value
```

That translation is the defect, not a workaround for it — it is what makes "remap
unmapped entries to `None`" unreachable from a spec. Fix it in the **function's**
signature by replacing the sentinel with something authorable (e.g. an explicit
`on_unmapped: Literal["keep", "replace"] = "keep"` alongside `default_value: Any =
None`). `MapColumnValues` then mirrors the signature 1:1, `apply()` becomes a straight
call, and the caveat leaves the docstring. The `on_conflict` guard belongs in the same
signature change.

**Tests:** `src/tests/transformations/transformation/` (PRD §7.1).

**Dependencies:** none. Can run in parallel with task 01. Blocks tasks 03 and 04.
