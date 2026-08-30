# Check-based validation — agreed design and work packages

Status: WP1 and WP2 complete, WP3 open — see *Work packages*. Written 2026-08-29, revised
2026-08-30 to match what landed.

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
class BaseCheck(BaseModel, ABC):
    name: str                  # class identity / discriminator: "is_unique"
    label: str                 # what it means here: "primary key"
    ignore_na: bool = True

    @abstractmethod
    def __call__(self, df: pd.DataFrame) -> pd.Series: ...
    def failure_message(self) -> str: ...
    def to_pandera(self) -> list[pa.Check]: ...
```

The instance holds what the closures currently capture, `__call__` is the predicate, and
`pa.Check(self, ...)` works because the instance is callable. Two indirections disappear.

A check is a **pydantic model**, like everything else in `contracts/`. That makes `name` a
`Literal` field: it is the discriminator when checks are read from a YAML or JSON spec,
and it cannot be overridden on an instance.

`to_pandera` is a **factory**, not a converter — it returns a list, so a composite can
unpack into one pandera check per sub-rule and a report says which rule broke. Pandera
identifies a check by its `error=` string, so `failure_message()` carries that
identification; no explicit pandera check name is set.

### Base checks name mechanics, not meanings

`IsUnique(columns)` and `IsIn(columns, existing)` — not `PrimaryKeyUniqueness` and
`ForeignKeyIntegrity`.

The evidence is in the schema: `fields/base.py` carries a `unique: bool` constraint, so a
single-column unique constraint and a multi-column primary key are **the same mechanic at
different arities**. A name like `PrimaryKeyUniqueness` would either duplicate that logic
or lie about half its uses.

What a rule *means* on a particular schema is a `label` supplied at derivation, not a
subclass. A subclass hierarchy whose only content is a string would also break the merge
below, because two construction sites would have to remember to instantiate the same
subclass.

Not every check decomposes. The four dimension rules — *"each sub-level must have an
`<parent_id>_other` sibling"* — are irreducibly domain-specific. The hierarchy therefore
has two tiers, generic and domain, and that is honest rather than awkward.

### Composites may name a meaning

A **base check** performs one operation. A **composite** combines several and *is* allowed
to name a meaning: `IsValidPrimaryKey` is `IsNotNull` and `IsUnique` and `IsNotIn` taken
together.

This is a deliberate exception to the rule above, and it reverses the rejection of "a
subclass per business meaning" below. Two things pay for it. A composite unpacks into one
pandera check per sub-rule, so a duplicate reports as a uniqueness failure rather than as
one opaque `PrimaryKeyError` — that is the whole reason `to_pandera` returns a list.
And leaving the assembly to the caller is the copy-pasted derivation ADR 0005 exists to
prevent: every caller would re-derive what a primary key means.

**A foreign key is not one of them.** The test is whether the sub-rules produce distinct,
actionable messages. For a primary key they do: "not unique" and "already exists" are
different problems, fixed differently. For a foreign key there is no such split — "value
not in the referenced set" is one message, and a null row passing is not a failure to
report. So it is a single base check, `IsSubsetOf(columns, allowed, within)`, which
carries the SQL `MATCH SIMPLE` semantics itself: empty strings read as null, a null
anywhere in the key passes the row, and `within` joins the frame's own rows to the valid
set for a self-reference.

`IsSubsetOf` is a sibling of `IsIn` rather than an extension of it. A general-purpose
membership check where nulls silently pass is a trap for the next person who reaches for
one; two discriminators, two honest rules.

Negation is a second class, not a flag. `IsIn` and `IsNotIn` rather than
`IsIn(expected=False)`: the two are not exact complements once nulls are in play, and a
flag would leave two opposite rules sharing one discriminator.

### Standard and additional

- **Standard checks** come from the **Schema** and always run. Nothing supplies them, so
  nothing can omit them.
- **Additional checks** come from the caller, carrying **existing values**.

A caller can add strictness and never remove it. That is the correctness half of the
problem, solved structurally rather than by a rule someone has to remember.

**This turned out to describe two states of one check, not two checks.** The design here
had a standard list and an additional list, merged by rule so that an additional check
replaced a standard one and a single violation was reported once. WP2 removed the need:
one derivation taking optional values emits **one** check per schema construct, so the two
lists never come into existence and there is nothing to merge or to key an identity on.

| construct | no values supplied | values supplied |
|---|---|---|
| primary key | `IsValidPrimaryKey(["id"])` | same, plus `existing=` |
| self-referencing FK | `IsSubsetOf(["parent_id"], within=["id"])` | same, plus `allowed=` |
| external FK | *no check* | `IsSubsetOf(["region_code"], allowed=…)` |

The guarantee survives in a stronger form: a caller supplies **values, never checks**, so
it can inform a check but has no way to drop one. "Standard" and "additional" are best
read as adjectives for how much a check knows, rather than as two kinds of object.

The merge was also not merely tidier. Run as two lists, a self-reference whose parent was
already stored failed the schema-derived check while passing the caller's — the
schema-derived version is *unsound* once data arrives in batches, not merely weaker, so it
had to be replaced rather than supplemented. Deriving once makes that impossible to get
wrong. See WP2.

### The caller derives, the check checks

An earlier draft gave every check derivable from a schema construct its own constructor —
`from_foreign_key(fk, allowed=None)` — so that this line had exactly one home:

```python
within = fk.reference.fields if fk.reference.resource is None else None
```

That is dropped. Three reasons, in increasing weight:

- **Asymmetry.** `IsValidPrimaryKey` has no `from_primary_key` and does not want one. If a
  foreign key needed a constructor to be safe, so would a primary key.
- **The boundary.** Taking a `ForeignKey` would make `checks/` import from
  `contracts/schema/reference/`. The package depends on nothing but pandas, pandera and
  pydantic today, and that is worth keeping: `checks/` knows *how* to check, the schema
  knows *which* checks and *which values*.
- **There is only one site.** The duplication [ADR 0005](../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md)
  guards against needs two derivations. There is one — `PanderaAdapter._derive_checks` —
  so a constructor would be guarding nothing.

The `foreign_key_values` dict stays a transport format for the caller's values. It is not
a field on a check: a check holding the whole dict would be N unrelated rules rather than
one, with nothing for `failure_message()` to name. The derivation iterates the schema's
foreign keys and looks the dict up, so an entry naming something the schema does not
declare cannot invent a check.

**Deferred, not rejected.** The third reason expires the day caller-supplied checks are
exposed through `validate_data` — that gives the derivation a second site, and the
constructor earns its place. Revisit it then, not before.

### Three layers, each with one job

| | job |
|---|---|
| `to_pandera_schema()` | fields → columns. *Landed differently: it also carries the checks the schema requires — see WP2.* |
| `TableSchema.validate_dataframe()` | translate flags into values, delegate. *Landed differently: the derivation sits in the adapter — see WP2.* |
| the runner in `validation/` | execute a pandera schema, translate its exceptions into `SchemaValidationError` |

The runner stops taking a `TableSchema`, so its `if TYPE_CHECKING: from ..schema import
TableSchema` disappears — that import was the symptom of the validator deriving things it
had no business deriving.

`to_pandera_schema` and `validate_dataframe` currently carry the *same five parameters*
and both forward to the adapter independently. After this, one calls the other.

### Placement

- `contracts/schema/validation/checks/` — the check classes, as a package:
  `abstract_base.py` (`BaseCheck`), `base_checks.py` (every check performing one
  operation, so any later check can reuse it), `reference_checks.py` (the checks about
  keys) and `utils.py` (shared helpers). Modules above the base group by **domain**, not
  by tier — later composites get their own domain-named modules rather than one file
  named for being composites.
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
  instantiate the same subclass or duplicate errors return. **Partly reversed** — see
  *Composites may name a meaning*. The rejection stands for a subclass that only adds a
  string; a composite that combines several rules and unpacks into per-rule pandera
  checks earns its name, and pays the coupling with a shared constructor.
- **A negation flag on one class** (`IsIn(expected=False)`). One class covering two rules,
  a two-branch failure message on every check for the one call site that used it, and a
  discriminator that no longer names the rule.
- **A backend-agnostic check description that each adapter renders.** A second parallel
  hierarchy for one backend. [ADR 0003](../adrs/0003-release-is-a-contract-to-frictionless-adapter.md)
  records this codebase's answer to exactly that question.
- **A flag to omit the standard checks "for flexibility".** The door back to skipping
  uniqueness, and a worse one than today's flags because it is all-or-nothing and unnamed.
  The coarse escape hatch already exists a layer up (`add_data(validate=False)`).

---

## Work packages

### WP1 — The check classes — *landed*

**Depends on:** nothing.
**PR:** with WP2, `refactor:` — classes with no caller are dead code.

`validation/checks/`: `BaseCheck`, the one-operation checks, the composites, and the four
dimension rules. `_check_reference_inputs` moves into the constructors that consume the
values.

**Landed — the package is complete.** `BaseCheck` as a pydantic model; `IsUnique`, `IsIn`,
`IsNotIn`, `IsNotNull`, `IsSubsetOf`; the `IsValidPrimaryKey` composite; the four
dimension rules over a `DimensionCheck` base with the `IsValidCrossDimension` composite;
value widths validated by the model; a shared `validate_existing_length_match` in
`checks/utils.py`; tests per module.

**One deviation from the port.** `_check_other_entries` wrote its grouped answer back over
*every* non-root row, but `groupby` forms no group for a row whose `parent_id` is null —
so on a dimension carrying a parentless child it raised `ValueError: cannot set using a
list-like indexer with a different length than the value` instead of reporting the row. No
existing test reached it. The rule is now stated as a conditional — *which sibling group am
I in, and does that group hold the catch-all?* — so a row in no group has nothing to be
asked and passes, and the answer is written back only for the rows that were grouped.
`NonRootElementHasParent` owns the missing parent, so the mistake is still caught, and
reported once rather than twice. `_pandera_dimension_checks.py` keeps the defect until WP2
deletes it.

**Verification:**
- `IsValidPrimaryKey` with no existing values checks non-null and in-frame uniqueness;
  with existing values, also against those.
- `IsSubsetOf` with `within=` unions the data's own rows — a self-reference validates with
  no supplied values.
- `IsSubsetOf` with `allowed=[]` and no `within` fails every non-null row but passes null
  ones. Plain membership with an empty set: `IsIn` fails every row, `IsNotIn` passes every
  row.
- `IsSubsetOf` follows `MATCH SIMPLE`: one null anywhere in a composite key passes the
  row, even when the other columns match nothing.
- Column order: a multi-column check compares positionally.
- The four dimension rules reproduce the existing behaviour and the cases in
  `test_dimension_check.py` pass with only their construction re-pointed — except that a
  row naming no parent now passes the catch-all rule instead of raising. It is in no
  sibling group, so there is nothing to ask, and `NonRootElementHasParent` owns that
  failure.
- ~~`name` is stable and equal for the same mechanic and columns~~ — dropped; the merge
  identity moves to WP2. See *Standard and additional*.

### WP2 — Wire them in ⟵ carries the behaviour change — *landed*

**Depends on:** WP1, complete.
**PR:** with WP1.

`PanderaAdapter._derive_checks(primary_key_values, foreign_key_values)` is the single
derivation: one check per schema construct, folding in whatever values it is given.
`convert` and `convert_schema` forward the values, `TableSchema.to_pandera_schema` forwards
to them, and `validate_dataframe` reduces to translating its flags into values and calling
the runner. The runner takes a pandera schema and does nothing but execute and translate.
`_pandera_dimension_checks.py`, the old `pandera_adapter.py`, `convert_schema_to_pandera`
and `backend` are all gone.

**Three departures from what this PRD specified.**

*The conversion carries the checks.* `to_pandera_schema()` was to return columns only. It
returns a schema that enforces the contract instead, because the entry point is public and
a conversion permitting duplicate primary keys and broken self-references enforces less
than the contract it represents — and because baking them in is what makes them impossible
to omit.

*The derivation lives in the adapter, not on `TableSchema`.* The three-layer table below
puts assembly on `validate_dataframe`. Keeping it in the adapter leaves one dependency edge
(`schema → adapter → checks`) rather than two, keeps `TableSchema` a description of a
table, and puts all pandera knowledge behind one door. Deriving *a primary key implies a
uniqueness check* is conversion, not deciding.

*There is no merge.* Standard and additional checks were two lists only because the
derivation ran twice — once from the schema, once from the caller's values. One derivation
taking optional values yields **one** check per construct: the primary key check is always
derived with `existing=[]` when nothing is supplied; a self-referencing foreign key always
keeps `within` and adds supplied values to it; an external foreign key appears only when
values arrive. So the identity question WP2 was supposed to settle does not arise, and the
guarantee survives in a stronger form — a caller supplies **values, never checks**.

The two-list version had also produced a false rejection: a self-reference whose parent was
already stored failed the schema-derived check while passing the caller's. That is the
concrete reason merging was not merely tidier.

**Public signatures do not change**, apart from `backend` being removed and
`convert_schema_to_pandera` being deleted. `BaseContract.validate_data` is untouched.

**Left open:** `convert_schema_to_pandera` still appears in `contracts/schema/__init__.py`'s
`__all__`; the deleted adapter suite took the only end-to-end coverage of a converted
schema meeting a DataFrame; and the `skip_*` parameters on `validate_dataframe` now carry
no information that the absence of values does not, so they can go in their own PR.

### WP3 — Record it

**Depends on:** WP2 landing.
**PR:** own PR, `docs:`.

- **Amend [ADR 0005](../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md)** — a short dated note that the
  `None`-arm `ValueError` was retired and why, pointing at ADR 0006. Do not rewrite the
  reasoning: it was correct when written, and a reader benefits from seeing why it
  changed rather than finding it quietly edited away. Everything else in 0005 stands.
- **ADR 0006** — why base checks name mechanics rather than meanings, why composites are
  the exception and why a foreign key is not one; why there is no `from_foreign_key` and
  which layer derives what; why negation is a second class rather than a flag; why checks are
  pydantic models and `name` is a `Literal` discriminator; why a check is identified in a
  report by its failure message; why standard checks are not omittable; why an additional
  check replaces rather than adds; why the assembly sits on
  `TableSchema.validate_dataframe` rather than in the runner or the adapter.
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
