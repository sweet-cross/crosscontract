# WP1 — The check classes

## Context
**Part of PRD:** [check-based-validation.md](../../prds/check-based-validation.md) — WP1

Today there is no answer to *what a check is*: primary-key, foreign-key and dimension
checks have three different shapes, three different gates, and live in two modules. This
task introduces the missing concept as a class hierarchy. Pure addition — nothing is
wired in yet, so no behaviour changes.

## Acceptance Criteria
- [x] `BaseCheck` exists with `name`, an optional `label`, `__call__(df) -> pd.Series`, `describe()`, and `to_pandera()`.
- [ ] `IsUnique(columns, existing=None, label=None)` reproduces the current primary-key behaviour: non-null, unique within the data, and — when `existing` is given — not colliding with it.
- [ ] `IsSubsetOf(columns, allowed=None, within=None, label=None)` reproduces the current foreign-key behaviour: empty strings read as null, null rows pass, and `within` unions the data's own rows into the valid set.
- [ ] `IsSubsetOf.from_foreign_key(fk, allowed=None)` is the **only** place deciding `within = fk.reference.fields if fk.reference.resource is None else None`.
- [ ] Four dimension rules exist as classes and reproduce the behaviour of `_pandera_dimension_checks.py` exactly.
- [ ] `name` is **stable and equal** for the same mechanic and columns, regardless of `label`, `existing`, or `allowed`. The merge in WP2 depends on this.
- [ ] `IsSubsetOf` with `allowed=[]` fails every non-null row and passes null ones.
- [ ] A composite `IsSubsetOf` compares positionally — `(a, b)` against `(a, b)`, never `(b, a)`.
- [ ] `_check_reference_inputs`' format validation happens in the constructor that consumes the values, not at the call site.

## Implementation Details
- **Create:** `src/crosscontract/contracts/schema/validation/checks.py`

  ```python
  class BaseCheck(ABC):
      name: str                  # mechanical identity, e.g. "is-unique:id"
      label: str | None          # what it means here, e.g. "primary key"

      def __call__(self, df: pd.DataFrame) -> pd.Series: ...
      def describe(self) -> str: ...
      def to_pandera(self) -> pa.Check: ...
  ```

  The instance holds what the current closures capture, `__call__` is the predicate, and
  `pa.Check(self, ...)` works because the instance is callable.

- **Names are mechanics, not meanings.** `IsUnique`, `IsSubsetOf` — not
  `PrimaryKeyUniqueness` or `ForeignKeyIntegrity`. `fields/base.py` carries a
  `unique: bool` field constraint, so a single-column unique constraint and a
  multi-column primary key are the same rule at different arities. The business meaning
  is the `label`, supplied at derivation, never a subclass.
- **No `Check` prefix** on class names — the module they are imported from says it.
- `ignore_na` is not universal: foreign keys handle nulls explicitly, the primary-key
  check does not. Make it a class attribute rather than a constant in `to_pandera`.
- **Port, do not rewrite**, the predicates in
  [pandera_adapter.py](../../../src/crosscontract/contracts/schema/adapters/pandera_adapter.py)
  (`_check_pk_integrity`, `_check_fk_integrity`) and
  [_pandera_dimension_checks.py](../../../src/crosscontract/contracts/schema/adapters/_pandera_dimension_checks.py).
  Their logic is correct; only its housing changes.
- **Do not delete anything yet.** `_pandera_dimension_checks.py` and the adapter's check
  builders stay until WP2 wires the new classes in.
- **Tests:** `src/tests/contracts/schema/validation/`. The existing
  `test_dimension_check.py` cases should pass against the new classes with only their
  construction re-pointed.
- **PR:** ships with WP2 as one `refactor:` — classes with no caller are dead code.
- **Depends on:** nothing.
