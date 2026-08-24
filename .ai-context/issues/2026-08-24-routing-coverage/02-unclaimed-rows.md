# WP2 — Unclaimed rows on `SubmissionContract`

## Context

WP1 removes the derived routing `enum`. This WP delivers what replaces it: a computation
that reports which submitted rows **no target claims**.

A row is *claimed* by a target when it satisfies every entry of that target's `filters`
(a conjunction). A row claimed by no target would be silently dropped during extraction —
the data loss the `enum` was reaching for and never actually caught, because a row can
carry a perfectly valid routing value and still fall through on a second filter over
another column.

**This is a query, not a validator.** It returns the unclaimed rows and does nothing with
them — no raise, no `warnings.warn`. Whether an unclaimed row is an error or a warning is
a policy decision that is deliberately still open; implementing either here would settle
it by accident and make reversing it an edit to the computation rather than to the policy
that consumes it.

## Acceptance Criteria

- [ ] `SubmissionContract` gains a method returning the rows of a submission
      `pd.DataFrame` that no target's `filters` match. Suggested name `unclaimed_rows`,
      matching the agreed term.
- [ ] It is **pure**: no exception raised on unclaimed rows, no warning emitted, the
      input frame not mutated.
- [ ] Filters match against the **string form** of the column (see below).
- [ ] A target's filters are a conjunction — all entries must match for the row to be
      claimed.
- [ ] All rows claimed → an empty frame is returned (not `None`).
- [ ] The returned rows preserve the input frame's index, so a caller can report *which*
      rows are unclaimed.
- [ ] `Target.filters`' field description states that values are matched against the
      column's string form.
- [ ] `TableSchema` and the rest of `contracts/` are untouched.

## Implementation Details

**Modify:**

- `src/crosscontract/submission/submission_contract.py` — add the method; `import pandas
  as pd` arrives with it. `submission/` acquiring a pandas dependency is expected: ADR
  0004 already states that execution lands in this package.
- `src/crosscontract/submission/extraction/target.py` — one sentence on the `filters`
  description.
- `src/tests/submission/test_submission_contract.py` — tests.

### Match on the string form, and why that is enough

Compare `df[column].astype(str)` against the filter value. No coercion of the filter
value, no Frictionless → backend type mapping, nothing new in `contracts/`.

The concern this settles: `Target.filters` is `dict[str, str]`, but the frame is not all
strings — the `tableschema` may declare `year` as integer. A naive `df["year"] ==
"2030"` is `False` for every row, and the target silently claims nothing.

Coercing the other way was considered and rejected. Fields carry only the Frictionless
type string; every Frictionless → Python mapping lives in the adapters
(`PydanticAdapter` picking `int`/`float`, `PanderaPandasAdapter` picking `"Int64"`), and
putting a `python_type` on `BaseField` is exactly the backend leak the adapter layer
exists to prevent. `cast_column` in
[column_transformations.py](../../../src/crosscontract/transformations/transformation/column_transformations.py)
is the established precedent — spec vocabulary stays Frictionless, the pandas mapping
lives inside the function that touches pandas.

**String comparison is sound here because it can only under-match, never over-match** — a
target claims fewer rows than intended, essentially never more. Under-matching is exactly
what this computation detects, so the imprecision is bounded by the mechanism being added:
the two close the loop on each other, and no failure slips past both. The common case
(`{year: "2030"}` against an `Int64` column) matches correctly regardless.

The one residual is datetime columns, where the string form is
`"2030-01-01 00:00:00"` and an author writing `{date: "2030-01-01"}` gets zero rows. The
report is correct — those rows *are* unclaimed — but the cause will not be obvious from
it. This is why the `filters` description note above is an acceptance criterion rather
than a nicety.

Prefer `.astype(str)` over `.astype("string")`: on a nullable dtype the latter propagates
`pd.NA` through the comparison, yielding a nullable boolean the caller must then
`fillna(False)`. `.astype(str)` renders missing values as the literal `"<NA>"` and keeps
the comparison plainly boolean.

### Shape and placement — recommendations, not mandates

- **Return a sub-frame** rather than a mask or an index. "Determine the unclaimed rows"
  is answered most directly by the rows, and both plausible consumers (an error message,
  a warning) want `len(...)` and a sample. A mask composes better, so if the eventual
  caller turns out to want one, that is a fine reversal — it is a small, local method.
- **Keep it a single method on `SubmissionContract`**; do not give `Target` a
  `matches(df)`. `Target` has no data-touching behaviour today, and granting it one is a
  larger commitment than this change needs. Per CLAUDE.md, no module-level helper unless
  the method cannot be written without one.
- **Assume a conforming frame.** `_check_filters` already guarantees every filter key
  names a field in the `tableschema`, so a frame that conforms to the schema has the
  columns. Document that precondition in the docstring; do not add a defensive branch for
  a non-conforming frame.

### Not in scope

**Contested rows** — rows claimed by more than one target. ADR 0004 makes overlap legal
("several targets may take the same rows and reshape them differently"), so this is a
separate question, and WP3 records it in `TODO.md`. Note only that whatever intermediate
this method builds determines whether contested rows are later a sum instead of an OR, or
a second pass.

**Load-time filter parseability** — checking in `_check_filters` that each authored filter
string parses as its field's Frictionless type, catching `{year: "abc"}` in the YAML. It
needs no backend at all, so it would sit cleanly in `contracts/`, but it is an authoring
nicety once the coverage report is loud. WP3 records it.

### Tests

In `src/tests/submission/test_submission_contract.py`, building on the existing
`valid_data` fixture:

- Every row claimed → empty frame returned.
- Some rows claimed, some not → exactly the unclaimed rows come back, with their original
  index labels.
- An integer-typed column with a string filter value (`{year: "2030"}` against `Int64`)
  claims the matching rows — the case the string cast exists for.
- A multi-entry filter behaves as a conjunction: a row matching one entry but not the
  other is unclaimed.
- A target filtering **only** on a non-routing column claims its rows — the case that
  made the derived enum underivable in the first place, and the reason this WP exists.
- The input frame is not mutated.

**Dependencies:** none technically; sequence after WP1 so the branch never carries both
the ban and its replacement.

**Verification:** `uv run pytest src/tests/submission/` plus `uv run mypy
src/crosscontract/`. *Ask before running — see CLAUDE.md.*
