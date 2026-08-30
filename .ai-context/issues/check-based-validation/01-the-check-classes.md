# WP1 — The check classes

## Context
**Part of PRD:** [check-based-validation.md](../../prds/check-based-validation.md) — WP1

Today there is no answer to *what a check is*: primary-key, foreign-key and dimension
checks have three different shapes, three different gates, and live in two modules. This
task introduces the missing concept as a class hierarchy. Pure addition — nothing is
wired in yet, so no behaviour changes.

## Acceptance Criteria

### Landed
- [x] `BaseCheck` exists with `name`, `label`, `__call__(df) -> pd.Series`,
      `failure_message()` and `to_pandera()`. It is a pydantic model, like the rest of
      `contracts/`.
- [x] `IsUnique(columns, label)` — jointly unique values, every occurrence of a duplicate
      failing.
- [x] `IsIn(columns, existing, label)` and `IsNotIn(columns, existing, label)` —
      membership in either direction, as two classes rather than one negatable class.
- [x] `IsNotNull(columns, label)`, carrying `ignore_na=False` because it inspects the
      nulls itself.
- [x] `IsValidPrimaryKey(columns, existing, label)` reproduces the current primary-key
      behaviour: non-null, unique within the data, and — when `existing` is given — not
      colliding with it.
- [x] `IsIn` with `existing=[]` fails every row; `IsNotIn` with `existing=[]` passes
      every row.
- [x] A composite check compares positionally — `(a, b)` against `(a, b)`, never
      `(b, a)`.
- [x] `_check_reference_inputs`' format validation happens in the constructor that
      consumes the values: pydantic validates `list[tuple[Any, ...]]`, and a
      `model_validator` raises when an entry does not hold one value per column.
- [x] Tests in `src/tests/contracts/schema/validation/checks/`, one file per module.

- [x] `IsSubsetOf(columns, allowed, within)` carries the foreign key as **one** check:
      empty strings read as null, null rows pass (SQL `MATCH SIMPLE`), and `within` joins
      the frame's own rows to the valid set for a self-reference. `allowed=[]` with no
      `within` fails every non-null row.

### Still open
- [ ] Four dimension rules exist as classes and reproduce the behaviour of
      `_pandera_dimension_checks.py` exactly. The cases in `test_dimension_check.py`
      should pass against them with only their construction re-pointed.

### Dropped, with the reason
- ~~`name` is stable and equal for the same mechanic and columns, regardless of `label`,
  `existing` or `allowed`.~~ `name` is the identity of the check *class* — a pydantic
  `Literal`, so it can act as the discriminator when checks are read from a YAML or JSON
  spec — not the identity of the instance. An instance-level `key` of mechanic + columns
  was tried and removed: it is not unique within one schema (a self-referencing foreign
  key yields two membership checks on the same column), and anything made unique enough
  to fix that stops colliding where the merge needs it to. **WP2 has to decide what it
  merges on**; see the PRD.

## Implementation Details
- **Create:** `src/crosscontract/contracts/schema/validation/checks/` — a package, not a
  single module:
  - `abstract_base.py` — `BaseCheck`.
  - `base_checks.py` — every check that performs one operation, whatever it is about:
    `IsUnique`, `IsIn`, `IsNotIn`, `IsSubsetOf`, `IsNotNull`. Membership in one place
    means any later check can reuse it.
  - `reference_checks.py` — the checks about keys, currently `IsValidPrimaryKey`.
  - `utils.py` — helpers shared across checks.

  Modules above the base group by **domain**, not by tier: later composites go into
  further domain-named modules (`dimension_checks.py` and so on), not into one file named
  after the fact that they are composites. `IsSubsetOf` therefore sits with the base
  checks even though it is about foreign keys — it is one operation, and that is the axis
  `base_checks.py` is sorted on.

  ```python
  class BaseCheck(BaseModel, ABC):
      name: str                  # class identity / discriminator, e.g. "is_unique"
      label: str                 # what it means here, e.g. "primary key"
      ignore_na: bool = True

      @abstractmethod
      def __call__(self, df: pd.DataFrame) -> pd.Series: ...
      def failure_message(self) -> str: ...
      def to_pandera(self) -> list[pa.Check]: ...
  ```

  The instance holds what the current closures capture, `__call__` is the predicate, and
  `pa.Check(self, ...)` works because the instance is callable.

- **`to_pandera` is a factory**, returning `list[pa.Check]` rather than one check. A
  composite unpacks into one pandera check per sub-rule, so a report says *which* rule
  broke instead of showing one opaque failure.
- **A check is identified in a report by its failure message.** Pandera displays a check
  by its `error=` string, so `failure_message()` carries the identification and no
  explicit pandera check name is set. `describe()` in the original sketch is this method,
  renamed for what it is.
- **Two tiers.** Base checks perform one operation; composites combine them and are
  allowed to name a meaning (`IsValidPrimaryKey`). This is a deliberate exception to
  "mechanics, not meanings" — see the PRD.
- **A foreign key is not a composite.** What paid for `IsValidPrimaryKey` was per-sub-rule
  messages: "not unique" and "already exists" are different problems, fixed differently.
  A foreign key has no such split — "value not in the referenced set" is one message, and
  a null row passing is not a failure to report. So it is one base check, `IsSubsetOf`.
- **No `from_foreign_key`.** `IsValidPrimaryKey` has no `from_primary_key` either, and the
  asymmetry was the tell. A constructor taking a `ForeignKey` would make `checks/` import
  from `contracts/schema/reference/`; today the package depends on nothing but pandas,
  pandera and pydantic, and that is worth keeping. The caller decides
  `within = fk.reference.fields if fk.reference.resource is None else None` and supplies
  the values — see WP2. Deferred rather than rejected: it earns its place if
  caller-supplied checks are ever exposed, because that gives the derivation a second
  construction site.
- **Names are mechanics, not meanings,** for the base checks: `IsUnique`, `IsIn` — not
  `PrimaryKeyUniqueness`. `fields/base.py` carries a `unique: bool` field constraint, so
  a single-column unique constraint and a multi-column primary key are the same rule at
  different arities.
- **No `Check` prefix** on class names — the module they are imported from says it.
- `ignore_na` is not universal: it is a pydantic field with a per-class default, `False`
  on `IsNotNull` and `True` elsewhere.
- **Port, do not rewrite**, the predicates in
  [pandera_adapter.py](../../../src/crosscontract/contracts/schema/adapters/pandera_adapter.py)
  (`_check_pk_integrity`, `_check_fk_integrity`) and
  [_pandera_dimension_checks.py](../../../src/crosscontract/contracts/schema/adapters/_pandera_dimension_checks.py).
  Their logic is correct; only its housing changes.
- **Do not delete anything yet.** `_pandera_dimension_checks.py` and the adapter's check
  builders stay until WP2 wires the new classes in.
- **Arity is validated, not just shape.** `[(10, 11)]` supplied for a single-column key
  would pass a `list[tuple[Any, ...]]` annotation and then silently fail every row,
  because the frame's keys are one wide. A `model_validator` compares each entry against
  `len(columns)` and raises — which the free `_check_reference_inputs` could never do,
  having only the values and not the columns.
- **PR:** ships with WP2 as one `refactor:` — classes with no caller are dead code.
- **Depends on:** nothing.
