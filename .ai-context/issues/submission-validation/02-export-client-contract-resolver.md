# Export `ClientContractResolver` as public API

## Context
**Part of PRD:** [submission-validation.md](../../prds/submission-validation.md) — WP1.

`validate_targets` requires a `ContractResolver`, and today a user holding a `CrossClient`
has no public way to build one: `ClientContractResolver` is reachable only by its full
module path. Without this export the feature has an argument nobody can supply.

## Acceptance Criteria
- [ ] `from crosscontract.crossclient import ClientContractResolver` works.
- [ ] The class is listed in `__all__` of both modified `__init__.py` files.
- [ ] A test asserts the import path, so a future `__init__` edit that drops it fails loudly.
- [ ] No behaviour change to the class itself.

## Implementation Details
- **Modify:** [src/crosscontract/crossclient/services/\_\_init\_\_.py](../../../src/crosscontract/crossclient/services/__init__.py) —
  re-export from `.resolver`.
- **Modify:** [src/crosscontract/crossclient/\_\_init\_\_.py](../../../src/crosscontract/crossclient/__init__.py) —
  re-export from `.services`, matching how `ContractResource` / `ContractService` are already
  exposed.
- **Modify:** [src/tests/crossclient/contracts/test_resolver.py](../../../src/tests/crossclient/contracts/test_resolver.py) —
  add the import assertion beside the existing resolver tests.
- Do **not** add a `resolver` property to `CrossClient` or `ContractService`. That was
  considered and rejected in the design session: it hides that the resolver wraps a
  *service*, and adds a cached-or-fresh question the plain export does not have.
- Note for the reviewer: this makes the class public API with the same breaking-change
  obligation [ADR 0005](../../adrs/0005-one-contract-resolver-supplies-definitions-and-values.md)
  recorded when `ContractResolver` itself was promoted.
- **Verification:** `uv run pytest src/tests/crossclient/`
- **Depends on:** nothing.
