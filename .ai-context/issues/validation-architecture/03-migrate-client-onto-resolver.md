# WP3 — Migrate the client onto `ContractResolver`

## Context
**Part of PRD:** [validation-architecture.md](../../prds/validation-architecture.md) — WP3

The first real consumer, and the proof the design holds. If the client cannot be
expressed cleanly as a `ContractResolver` plus a `validate_data` call, the design is
wrong — better to find that here than in `cross_back`.

## Acceptance Criteria
- [x] A `ClientContractResolver` class exists, wraps a `ContractService`, and implements both protocol members.
- [x] `ContractService._get_data` stays **private**. Users read data through a `ContractResource`, not by name off the service — that API shape is deliberate.
- [x] `ContractResource.validate_dataframe` routes through `contract.validate_data`, passing `check_existing_primary_key=False` / `check_existing_foreign_key=False` **explicitly** — the same no-network behaviour it has today, under the new polarity.
- [x] `ContractResource.validate_dataframe`'s own parameters are renamed to match (`check_existing_primary_key` / `check_existing_foreign_key`, both defaulting to `False`), so the client and the library speak one vocabulary rather than inverting at the boundary. Breaking, and acceptable on 0.x.
- [x] `ContractResource.get_primary_key_values` and `get_foreign_key_values` are removed.
- [x] The `ContractResource.validate_dataframe` docstring no longer claims "Default is False" for two flags that both default to `True` — under the rename the defaults genuinely are `False`, and the docstring says what `False` means.
- [x] The existing `src/tests/crossclient/contracts/test_contract_resource.py` suite passes with its mocks re-pointed.
- [x] The default behaviour is **provably unchanged** — a test asserts that a default `validate_dataframe` call performs no data fetch. This is the property that matters; note it is *not* the same as "the same checks run", which the handoff PRD in `04-record-the-decision.md` will deliberately change.

## Implementation Details
- **Create:** `src/crosscontract/crossclient/services/resolver.py` — the client-side implementor of the protocol, mirroring `DbContractResolver` on the server. Export it from `crossclient/services/__init__.py` only if `contract_resource.py` needs it there; no top-level export.

  ```python
  class ClientContractResolver:
      def __init__(self, service: ContractService):
          self._service = service

      def resolve(self, name: str) -> CrossContract | None:
          try:
              return self._service.get(name).contract
          except ResourceNotFoundError:
              return None

      def get_data(self, name, columns, *, unique=True) -> pd.DataFrame:
          return self._service._get_data(name, columns=columns, unique=unique)
  ```

  It carries `resolve` because the protocol is one piece. That is the bill for the
  single-protocol decision — and also its dividend: it makes `validate_references`
  runnable client-side against the live platform before `create()`, which nothing can do
  today.

- **Modify:** `src/crosscontract/crossclient/services/contract_resource.py`
  - `validate_dataframe` (line 217) constructs a `ClientContractResolver(self._service)` internally and delegates to `self.contract.validate_data(...)`.
  - Delete `get_primary_key_values` (line 280) and `get_foreign_key_values` (line 317) — their derivation now lives in `BaseContract.validate_data`.
  - Keep the `SchemaValidationError` → `ValidationError` translation.
- **Scope discipline:** no leading underscore on the class name, **no** top-level export, **no** convenience property on `CrossClient`. Exposing it is a one-line follow-up if wanted, not part of this task.
- **Do not** promote `_get_data` and do not change `ContractResource.get_data`.
- **Tests:** `src/tests/crossclient/contracts/test_contract_resource.py`.
- **PR:** ships with WP2 as one `feat:`.
- **Depends on:** `02-contract-resolver-and-validate-data.md`.
