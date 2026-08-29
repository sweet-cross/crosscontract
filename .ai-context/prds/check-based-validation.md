# Check-based validation — agreed design and work packages

Status: agreed, not yet implemented. Written 2026-08-29.

Follow-on to [validation-architecture.md](validation-architecture.md), which deliberately
deferred this. Terminology lives in the *Validation* section of
[`CONTEXT.md`](../CONTEXT.md) — **Check**, **Standard check**, **Additional check**.

---

## The problem

### The structural half

`PanderaPandasAdapter.convert` assembles its checks in three differently-shaped,
differently-gated blocks:

```python
if self.schema.primaryKey and not skip_primary_key_validation:   # flag-gated, one check
if self.schema.table_type == "Dimension":                        # type-gated, four checks
if self.schema.foreignKeys and not skip_foreign_key_validation:  # flag-gated, N checks
```

`_check_reference_inputs` is called at two of the three sites and not the third. The
dimension checks live in `_pandera_dimension_checks.py` with a different signature from
everything else. Each check is a function returning a `pa.Check` wrapping a closure over
local variables, which then delegates to a module-level helper taking those same
variables back as arguments.

There is no answer to *what a check is*, so a fifth one has nowhere obvious to go, and
nobody can read "what gets checked on this schema" without reading three shapes plus a
separate module.

Field conversion, by contrast, is fine: one `match` arm per field type, uniform shape.

### The correctness half

Primary-key uniqueness *within the data*, and the integrity of *self-referencing* foreign
keys, need nothing from outside the data — and they are currently suppressible:

```python
if self.schema.primaryKey and not skip_primary_key_validation:
```

`skip_primary_key_validation=True` removes the whole check, including the in-frame
uniqueness that costs nothing. These are consistency guarantees a **Contract** makes
about its own data; a caller should not be able to switch them off.

---

## The agreed design

### A check is an object

```python
class BaseCheck(ABC):
    name: str                  # mechanical identity: "is-unique:id"
    label: str | None          # what it means here: "primary key"

    def __call__(self, df: pd.DataFrame) -> pd.Series: ...
    def describe(self) -> str: ...
    def to_pandera(self) -> pa.Check: ...
```

The instance holds what the closures currently capture, `__call__` is the predicate, and
`pa.Check(self, ...)` works because the instance is callable. Two indirections disappear.

### Checks name mechanics, not meanings

`IsUnique(columns)` and `IsSubsetOf(columns, allowed=None, within=None)` — not
`PrimaryKeyUniqueness` and `ForeignKeyIntegrity`.

The evidence is in the schema: `fields/base.py` carries a `unique: bool` constraint, so a
single-column unique constraint and a multi-column primary key are **the same mechanic at
different arities**. A name like `PrimaryKeyUniqueness` would either duplicate that logic
or lie about half its uses.

What a rule *means* on a particular schema is a `label` supplied at derivation, not a
subclass. A subclass hierarchy whose only content is a string would also break the merge
below, because two construction sites would have to remember to instantiate the same
subclass.

Not every check decomposes. The four dimension rules — *"each sub-level must have an
`other_<parent_id>` sibling"* — are irreducibly domain-specific. The hierarchy therefore
has two tiers, generic and domain, and that is honest rather than awkward.

### Standard and additional

- **Standard checks** come from the **Schema** and always run. Nothing supplies them, so
  nothing can omit them.
- **Additional checks** come from the caller, carrying **existing values**.

A caller can add strictness and never remove it. That is the correctness half of the
problem, solved structurally rather than by a rule someone has to remember.

**An additional check replaces a standard one with the same name.** The reason is report
clarity, not speed: a row duplicated within the data fails both the standard
`is-unique:id` and the additional one, and would otherwise be reported twice for what is
one problem.

| | standard | additional | outcome |
|---|---|---|---|
| primary key | `IsUnique(["id"])` | same, plus `existing=` | replaced |
| self-referencing FK | `IsSubsetOf(["parent_id"], within=["id"])` | same, plus `allowed=` | replaced |
| external FK | *not emitted* | `IsSubsetOf(["region_code"], allowed=…)` | added |

Because `name` is derived from the mechanic and the columns, the two construction sites
agree without coordinating.

### One constructor per schema construct

Both sites build a check from the same `ForeignKey`, and both must reach the same
conclusion about `within`:

```python
within = fk.reference.fields if fk.reference.resource is None else None
```

Getting that wrong on the additional side replaces a standard self-reference check with a
weaker one, and self-references silently stop being validated against the data's own rows.
That is the copy-pasted derivation [ADR 0005](../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md)
exists to prevent, in a new costume. So a check derivable from a schema construct gets
**one** shared constructor — `IsSubsetOf.from_foreign_key(fk, allowed=None)` — which both
sites call.

### Three layers, each with one job

| | job |
|---|---|
| `to_pandera_schema()` | fields → columns. **Nothing else.** |
| `TableSchema.validate_dataframe()` | translate values and flags into checks, assemble standard + additional, delegate |
| the runner in `validation/` | execute a pandera schema, translate its exceptions into `SchemaValidationError` |

The runner stops taking a `TableSchema`, so its `if TYPE_CHECKING: from ..schema import
TableSchema` disappears — that import was the symptom of the validator deriving things it
had no business deriving.

`to_pandera_schema` and `validate_dataframe` currently carry the *same five parameters*
and both forward to the adapter independently. After this, one calls the other.

### Placement

- `contracts/schema/validation/checks.py` — the check classes.
- `contracts/schema/validation/` — the runner, as now.
- `contracts/schema/adapters/` — regains one plain meaning: convert a schema into another
  format. `_pandera_dimension_checks.py` was the thing violating that, and it moves.

This also resolves the "lopsided package" noted in the previous PRD: `validation/` was one
function; it becomes the checks and the thing that runs them.

### `backend` is dropped

`backend: Literal["pandas"] = "pandas"` has one legal value and guards a `match` statement
with a dead arm. No caller in either repository passes it. It goes from
`validate_dataframe` and `to_pandera_schema`, and the two tests that exist only to assert
the dead branch raises go with it.

### An unchecked external reference is silent

An external foreign key with no supplied values produces no additional check, so it is not
checked and nothing is raised. This **retires the `ValueError`** that WP1 of the previous
PRD deliberately kept.

That reversal is principled rather than a regression: WP1 kept the raise because there was
no other way for a caller to say "I am not checking this one", and there now is. The `[]`
semantics — an empty referenced table fails every non-null referring row — survive
untouched.

Whether silence is good enough is the one question this design leaves open; see
*Deliberately open* below.

---

## Rejected alternatives

- **The caller supplies the whole check list.** Maximum flexibility, and it makes
  "the primary key is always checked" unenforceable — the guarantee you most want becomes
  the easiest thing to drop.
- **Checks derive themselves (`Check.from_schema(schema)`), adapter iterates a list of
  check types.** Genuinely extensible, but the dimension gate does not disappear — it
  moves and is written four times instead of once, recoverable only by adding an
  intermediate base class. It also puts `TableSchema` knowledge inside every check, which
  is dead weight the moment checks are caller-instantiated.
- **A subclass per business meaning** (`PrimaryKey(IsUnique)`). A class hierarchy whose
  only content is a string, and it breaks merge-by-name: `validate_data` must remember to
  instantiate the same subclass or duplicate errors return.
- **A backend-agnostic check description that each adapter renders.** A second parallel
  hierarchy for one backend. [ADR 0003](../adrs/0003-release-is-a-contract-to-frictionless-adapter.md)
  records this codebase's answer to exactly that question.
- **A flag to omit the standard checks "for flexibility".** The door back to skipping
  uniqueness, and a worse one than today's flags because it is all-or-nothing and unnamed.
  The coarse escape hatch already exists a layer up (`add_data(validate=False)`).

---

## Work packages

### WP1 — The check classes

**Depends on:** nothing.
**PR:** with WP2, `refactor:` — classes with no caller are dead code.

`validation/checks.py`: `BaseCheck`, `IsUnique`, `IsSubsetOf`, and the four dimension
rules. `IsSubsetOf.from_foreign_key(fk, allowed=None)` as the single constructor.
`_check_reference_inputs` moves into the constructors that consume the values.

**Verification:**
- `IsUnique` with no existing values checks non-null and in-frame uniqueness; with
  existing values, also against those.
- `IsSubsetOf` with `within=` unions the data's own rows — a self-reference validates with
  `allowed=None`.
- `IsSubsetOf` with `allowed=[]` fails every non-null row but passes null ones.
- Column order: a composite check compares positionally.
- `name` is stable and equal for the same mechanic and columns regardless of `label`,
  `existing`, or `allowed` — this is what the merge depends on.
- The four dimension rules reproduce the existing behaviour; the tests in
  `test_dimension_check.py` should pass with only their construction re-pointed.

### WP2 — Wire them in ⟵ carries the behaviour change

**Depends on:** WP1.
**PR:** with WP1.

- `PanderaPandasAdapter.convert(name, checks=None)`: columns from fields, attach the
  checks it is given, derive nothing.
- `to_pandera_schema()`: columns only.
- `TableSchema.validate_dataframe`: translate values and flags into additional checks,
  merge with the schema's standard checks, call the runner.
- The runner: execute and translate exceptions.
- Delete `_pandera_dimension_checks.py` and the `backend` parameter.

**Public signatures do not change**, apart from `backend` being removed.
`BaseContract.validate_data` is untouched.

**Verification:**
- `skip_primary_key_validation=True` **still** checks non-null and in-frame uniqueness.
  This is the behaviour change and the reason the package exists.
- `skip_foreign_key_validation=True` **still** checks self-referencing foreign keys.
- An external foreign key with no values is not checked and does not raise — the previous
  `ValueError` test is inverted, not deleted, so the change is visible in the diff.
- A duplicate row is reported **once**, not twice, when existing primary keys are supplied.
- `to_pandera_schema()` returns a schema with no checks attached.
- The existing `test_pandas_validation.py` and `test_integration_references.py` suites
  pass, except where they assert the retired `ValueError` or the `backend` guard.

### WP3 — Record it

**Depends on:** WP2 landing.
**PR:** own PR, `docs:`.

- **Amend [ADR 0005](../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md)** — a short dated note that the
  `None`-arm `ValueError` was retired and why, pointing at ADR 0006. Do not rewrite the
  reasoning: it was correct when written, and a reader benefits from seeing why it
  changed rather than finding it quietly edited away. Everything else in 0005 stands.
- **ADR 0006** — why checks name mechanics rather than meanings; why standard checks are
  not omittable; why an additional check replaces rather than adds; why the assembly sits
  on `TableSchema.validate_dataframe` rather than in the runner or the adapter.
- **`CONTEXT.md`** — **done**, ahead of WP1. **Check**, **Standard check** and
  **Additional check** are defined, with two relationship lines.

---

## Deliberately open

**Validation reporting.** With the `ValueError` retired, a frame with four unchecked
external references returns exactly like one where all four passed. We accepted silence
for now, on the grounds that the caller chose not to supply values and the flag names say
so — and that a check's `name` makes the executed set inspectable for anyone who wants it.

The real answer is probably a validation *report*: what was checked, what was skipped, what
failed. That is a larger topic than this PRD and touches `SchemaValidationError`,
`ValidationError` on the client, and whatever `cross_back` returns to a submitter. **It
should be discussed once this design has landed**, not folded into it.

---

## Out of scope

- Changing the signatures of `BaseContract.validate_data` or
  `TableSchema.validate_dataframe`, beyond removing `backend`. Deleting the now-redundant
  value and flag parameters is a separate PR.
- Caller-supplied checks reaching through `validate_data`. The design allows it; exposing
  it is later.
- Anything in `cross_back`.
