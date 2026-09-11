# WP1 — A blank cell must not fail the `pattern` constraint of an optional field

## Context
**Part of PRD:** none — standalone regression fix, found downstream in `cross_back`
while bumping it from 0.13.0 to 0.22.0.

The package already decides what an empty string means, and says so twice in its
own checks:

- `IsSubsetOf`: "An empty string is read as null. Tabular sources carry no null
  of their own, so a blank cell arrives as `""` and means the same thing."
- `RootElementHasNoParent`: "An empty string counts as no parent, the same as a
  null."

`StringFieldConverter` does not honour that convention. Since 0.18.0 the
`pattern` constraint is emitted as `pa.Check.str_matches(...)`, which rejects
`""` — so the same `parent_id` value is null for foreign-key purposes, null for
hierarchy purposes, and a real value for pattern purposes.

The visible consequence is that a `Dimension` upload containing **root rows**
is rejected. A root has no parent, the blank cell arrives as `""`, and the rigid
`Dimension` template constrains `parent_id` with `^[a-zA-Z][a-zA-Z0-9_]*$`.
`color` is optional with a pattern too, so a blank colour fails identically.
This is not a test artefact: it breaks real dimension ingestion, and it is
blocking the `cross_back` package update.

**Why it appears now.** At 0.13.0 the constraint was emitted as
`kwargs["regex"] = field.constraints.pattern`, and those kwargs go straight into
`pa.Column(**kwargs)`. In pandera, `regex` means *treat the column's **name** as
a pattern* — it is not a value check at all. The constraint was dead, and
harmlessly so, because `^[a-zA-Z][a-zA-Z0-9_]*$` happens to match the column
name `parent_id`. 0.18.0 made it real. `test_pattern_becomes_a_value_check` in
`src/tests/contracts/schema/adapters/pandera_pandas/test_field_convertors.py`
pins that fix and must keep passing.

So this is a fix to a fix: the pattern check is correct to exist, and wrong
about blanks.

## Acceptance Criteria
- [ ] A non-required `StringField` with a `pattern` accepts `""`.
- [ ] It still accepts null, and still rejects a genuine violation.
- [ ] A **required** `StringField` with a `pattern` still rejects `""` — its
      emitted check is unchanged.
- [ ] The rendered check name stays a `str_matches(...)` string (see the
      reporting hazard below).
- [ ] `test_pattern_becomes_a_value_check` and
      `test_pattern_must_match_the_whole_value` still pass.
- [ ] A `Dimension` frame whose roots carry `parent_id == ""` validates.

## Implementation Details

**Modify:**
`src/crosscontract/contracts/schema/adapters/pandera_pandas/field_convertors.py`
— `StringFieldConverter.get_checks()`.

Widen the pattern to admit the empty string when, and only when, the field is
not required:

```python
# non-required: a blank cell is a null, so it is not the pattern's business
pa.Check.str_matches(f"(?:{pattern}|)$")
# required: unchanged
pa.Check.str_matches(f"(?:{pattern})$")
```

Verified against `["i1", "", None, "9bad"]` with `^[a-zA-Z][a-zA-Z0-9_]*$`:
the blank passes, the null still passes (pandera's `str_matches` ignores nulls
already), and `9bad` still fails.

### The reporting hazard — why not a wrapped check

`SchemaValidationError` recovers a check's columns by parsing its
`failure_message()`, which
[validation-reporting.md](../../prds/validation-reporting.md) records as a
standing coupling: rewording a message silently degrades reports with no test
failing.

Widening the regex keeps the check a `str_matches`, so the rendered string keeps
its shape. A hand-rolled `pa.Check(lambda s: (s == "") | ...)` wrapper would
change it. Do not take that route without also addressing the parsing.

### Keep the required case byte-identical

Do not "simplify" by always widening. A blank in a **required** patterned field
should fail, and today it does. `nullable=False` catches nulls, not `""`, so the
pattern is the only thing rejecting a blank there.

### Considered and rejected — normalising `""` to `NA`

The most faithful reading of "a blank cell is null" is to make it null in the
frame, via a `Parser` on the column. Rejected here: `validate_dataframe` returns
the coerced frame and consumers persist it, so blanks would start being stored
as `NULL` instead of `""`. `cross_back`'s dimension round-trip test asserts
`parent_id == ["", "", ""]` survives an upload and a read, and stored data across
the platform would change meaning. That may be the better long-term model, but
it is a data decision, not a bug fix. If it is ever taken, it supersedes this
change rather than building on it.

### Out of scope — the same class, but not a regression

`minLength` and `enum` reject `""` on a non-required string field in exactly the
same way; both verified. Neither is caused by this release — `pa.Check.isin` and
`pa.Check.str_length` were already emitted correctly at 0.13.0, so those have
always behaved this way.

The general rule — *no value-level constraint applies to a blank in a
non-required string field* — is the right end state and deserves its own change.
It is deliberately not bundled here: this issue unblocks a downstream regression,
and widening it would ship a behaviour change to every optional enum and
length-constrained column in the corpus inside a fix meant to restore intent.
Raise it separately, with a corpus audit.

### Tests

`src/tests/contracts/schema/adapters/pandera_pandas/test_field_convertors.py`,
beside the two existing pattern tests and following their shape — a
`StringField` built inline, `parametrize` over the cases:

- non-required + pattern: `""` passes, `None` passes, a violation fails;
- required + pattern: `""` fails;
- the emitted check is still named `str_matches`.

`test_integration_dimension.py` is the right home for the case that motivates
this: an assembled `DimensionSchema` whose root rows carry `parent_id == ""`
validates. That is the regression, and it is the one that should fail loudly if
someone narrows the fix back to nothing.

### Release

`fix:` — the constraint never enforced anything before 0.18.0, so this restores
intent rather than changing it, and a patch release reads correctly. `cross_back`
pins whatever version carries it instead of `0.22.0`; see that repository's
`.ai-context/issues/2026-09-11-crosscontract-0-22-package-update/01-bump-the-crosscontract-pin.md`,
finding F1.

**Depends on:** nothing.
