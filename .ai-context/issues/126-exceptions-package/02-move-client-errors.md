# WP2 — Move the `CrossClientError` family into `crosscontract.exceptions`

## Context
**Part of:** sweet-cross/crosscontract#126 — WP2

The client exceptions live in `crossclient/exceptions/exceptions.py`, next to `raise_from_response`.
This task moves the classes to `crosscontract.exceptions` and leaves only the HTTP response → exception
translation in `crossclient/`, since that part is transport. The task moves the classes unchanged and
ends with the full suite passing.

## Acceptance Criteria
- [ ] `CrossClientError`, `ValidationError`, `RequestValidationError`, `UnprocessableEntityError`,
      `AuthenticationError`, `PermissionDeniedError`, `ResourceNotFoundError`, `ServerError` and
      `ConflictError` live in `src/crosscontract/exceptions/client_exceptions.py`, moved **unchanged**.
- [ ] `crosscontract.exceptions` exports all nine (import and `__all__`).
- [ ] `raise_from_response` stays in `src/crosscontract/crossclient/exceptions/exception_factory.py`
      and imports the classes from `crosscontract.exceptions`.
- [ ] `src/crosscontract/crossclient/exceptions/exceptions.py` is deleted. No shim module is left behind.
- [ ] `crosscontract.crossclient.exceptions` re-exports exactly the names it exports today: its current
      `__all__`, which does **not** include `RequestValidationError`.
- [ ] `src/crosscontract/exceptions/` still imports nothing from the rest of `crosscontract`.
- [ ] Behaviour is unchanged: class hierarchy, default messages, `ValidationError`'s message note,
      `to_list`, `to_pandas`, and `raise_from_response`'s mapping.
- [ ] Tests are moved and updated (see below). No test or module in `src/` references
      `crossclient.exceptions.exceptions`.
- [ ] The full suite passes (run only with the user's go-ahead).

## Implementation Details
- **Move:** `src/crosscontract/crossclient/exceptions/exceptions.py` →
  `src/crosscontract/exceptions/client_exceptions.py`.
- **Modify:**
  - `src/crosscontract/exceptions/__init__.py`: import the nine classes from `.client_exceptions` and add
    them to `__all__`.
  - `src/crosscontract/crossclient/exceptions/exception_factory.py`: `from .exceptions import (...)` →
    `from crosscontract.exceptions import (...)`.
  - `src/crosscontract/crossclient/exceptions/__init__.py`: import the classes from
    `crosscontract.exceptions`. Keep `raise_from_response` and leave `__all__` unchanged.
  - Internal users of the package-level path stay as they are, because the path keeps working:
    `crossclient/services/contract/resolver.py`, `contract_service.py`, `contract_resource.py`,
    `crossclient/services/submission/submission_service.py`.
- **Tests:**
  - Move `src/tests/crossclient/exceptions/test_exceptions.py` →
    `src/tests/exceptions/test_client_exceptions.py`, importing from `crosscontract.exceptions`.
  - `src/tests/crossclient/exceptions/test_exception_factory.py` stays where it is. Switch its class
    imports from `crosscontract.crossclient.exceptions.exceptions` to `crosscontract.exceptions`.
  - Switch the deep import `crosscontract.crossclient.exceptions.exceptions` to `crosscontract.exceptions`
    in `src/tests/crossclient/contract/test_contract_resource.py` and
    `src/tests/crossclient/contract/test_resolver.py`.
  - In `test_client_exceptions.py`, add a test that `crosscontract.crossclient.exceptions` exposes the
    same class objects as `crosscontract.exceptions` for every name in its `__all__` except
    `raise_from_response`.
- **Name note:** `crosscontract.exceptions.ValidationError` now sits next to `SchemaValidationError`,
  `TargetValidationError` and pydantic's `ValidationError`. It is **not** renamed (out of scope).
- **Dependencies:** none. This task can land before or after WP1.
