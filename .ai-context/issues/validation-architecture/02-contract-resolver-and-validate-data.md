# WP2 — `ContractResolver.get_data` + `BaseContract.validate_data`

## Context
**Part of PRD:** [validation-architecture.md](../../prds/validation-architecture.md) — WP2

This is the critical path. Every consumer today re-derives the same four lines of schema
semantics to build reference values, and confusing `fk.fields` with
`fk.reference.fields` is silently wrong rather than a crash. This task moves that
derivation into the library behind a signature that step 2 (submission validation) and
step 3a (`cross_back`) will both bind to — so the signature, not the amount of code, is
the expensive part.

## Acceptance Criteria
- [x] `ContractResolver` carries **both** `resolve` and `get_data`, as a single protocol, with `@abstractmethod` on both members.
- [x] `get_data`'s docstring states the scope obligation: it returns rows *irrespective of the caller's read permissions*, and is never narrowed by project.
- [x] `get_data`'s docstring states that `unique` is a cost hint — correctness does not depend on it, because both key checks build a `set()`.
- [ ] `BaseContract.validate_data` exists with the agreed signature and owns the whole derivation.
- [ ] A dict-backed fake resolver proves the derivation, **including a case where `fk.fields` and `fk.reference.fields` differ** — that is where a direction error hides.
- [ ] A **composite** foreign key whose resolver returns the requested columns in a *different order* still validates. Without the `df[columns]` reindex this fails silently, so it needs its own test.
- [ ] A stale explicit subclass of `ContractResolver` (one that implements `resolve` but not `get_data`) raises `TypeError` at construction.
- [ ] `resolver=None` with `skip_primary_key_validation=False` still runs in-frame primary-key uniqueness — it must **not** collapse into "skip both".
- [ ] `FakeResolver` in `src/tests/contracts/contracts/test_contract_reference_validation.py` gains a `get_data` stub. It keeps working untouched at runtime, but no longer satisfies the protocol structurally, and the stub is what keeps that honest.

## Implementation Details
- **Modify:** `src/crosscontract/contracts/contracts/resolvers.py`

  ```python
  @runtime_checkable
  class ContractResolver(Protocol):
      @abstractmethod
      def resolve(self, name: str) -> "BaseContract | None": ...

      @abstractmethod
      def get_data(
          self, name: str, columns: list[str], *, unique: bool = True
      ) -> pd.DataFrame: ...
  ```

  `unique` is **keyword-only**: `get_data(name, cols, True)` is unreadable and collides
  positionally with `ContractService._get_data`'s `filters` parameter.

- **Modify:** `src/crosscontract/contracts/contracts/base_contract.py`

  ```python
  def validate_data(
      self,
      df: pd.DataFrame,
      resolver: ContractResolver | None = None,
      skip_primary_key_validation: bool = False,
      skip_foreign_key_validation: bool = False,
      lazy: bool = True,
  ) -> pd.DataFrame
  ```

  The derivation it owns:
  - primary-key lookup against `self.name`, columns `self.tableschema.primaryKey.root`
  - foreign-key target name via `fk.reference.resource or self.name`
  - referenced columns via `fk.reference.fields`
  - keyed by `tuple(fk.fields)`
  - **order-safe** tuple-ification: `df[columns].itertuples(index=False, name=None)` — never bare `df.itertuples(...)`. `fk.fields` and `fk.reference.fields` correspond positionally (`foreign_key.py:34` and `:64` both say so, and `validate_field_length_match` enforces equal length), but `itertuples` follows the frame's own column order.

  It then hands materialized values to `self.tableschema.validate_dataframe`, which is
  **unchanged**.

- **Defaults are `False` / `False`**, matching `TableSchema.validate_dataframe`, not the client. A method one layer up must not validate less than the thing it delegates to.
- **No `backend` parameter** — one legal value, and the schema layer already defaults it.
- **The parameter is `resolver`, not `references`** — matches `validate_references` and the **Contract resolver** entry in [`CONTEXT.md`](../../CONTEXT.md).
- **Tests:** `src/tests/contracts/contracts/`.
- **PR:** ships with WP3 as one `feat:` — a protocol with no implementor is dead code.
- **Depends on:** `01-distinguish-missing-from-empty-references.md`.
