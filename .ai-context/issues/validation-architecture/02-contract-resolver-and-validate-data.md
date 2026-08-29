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
- [ ] The flags are named `check_existing_primary_key` / `check_existing_foreign_key`, both defaulting to `False`, and they read in the positive: `True` means *additionally consult stored values*.
- [ ] `resolver` is optional (`ContractResolver | None = None`), so a `BaseContract` used off-platform can validate without one.
- [ ] Requesting either check without a resolver raises a `ValueError` that names the contract and both remedies. Raised unconditionally on the flag-plus-`None` combination, not only when the schema happens to have keys to fetch.
- [ ] With both flags `False` and no resolver, **no data is fetched** — `get_data` is never called.
- [ ] A dict-backed fake resolver proves the derivation, **including a case where `fk.fields` and `fk.reference.fields` differ** — that is where a direction error hides.
- [ ] A **composite** foreign key whose resolver returns the requested columns in a *different order* still validates. Without the `df[columns]` reindex this fails silently, so it needs its own test.
- [ ] A stale explicit subclass of `ContractResolver` (one that implements `resolve` but not `get_data`) raises `TypeError` at construction.
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
      check_existing_primary_key: bool = False,
      check_existing_foreign_key: bool = False,
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

- **The flags name the *external* half, and default to `False`.** `check_existing_*=True`
  means "also consult stored values"; `False` means "check what is in the frame". The
  polarity is positive because that is how the caller thinks and how `cross_back` already
  names it (`check_primary_key` / `check_foreign_keys`, which it currently has to invert
  at the boundary). Translate to the schema layer with
  `skip_primary_key_validation=not check_existing_primary_key` and likewise for foreign
  keys. Do **not** derive the skip flags from the schema — see the known gap below.

- **Known gap, deliberate — the names promise more than the validator currently
  delivers.** `check_existing_foreign_key=False` reads as "do not consult other
  contracts", but today it maps onto `skip_foreign_key_validation=True`, which suppresses
  the check *entirely* — so a `Dimension` validated through `validate_data` does not get
  its self-referencing foreign key checked, and no contract gets in-frame primary-key
  uniqueness. That matches the client's current behaviour, so it is not a regression, and
  fixing it belongs at the validator, not here. The name is the specification; the
  handoff PRD described in `04-record-the-decision.md` brings the validator up to it.
  Renaming once, now, is cheaper than letting `cross_back` and the submission handler
  bind to `skip_*` and churning them later. State this gap in `validate_data`'s
  docstring so it is not mistaken for a bug.

- **No `backend` parameter** — one legal value, and the schema layer already defaults it.
- **The parameter is `resolver`, not `references`** — matches `validate_references` and the **Contract resolver** entry in [`CONTEXT.md`](../../CONTEXT.md).
- **Tests:** `src/tests/contracts/contracts/`.
- **PR:** ships with WP3 as one `feat:` — a protocol with no implementor is dead code.
- **Depends on:** `01-distinguish-missing-from-empty-references.md`.
