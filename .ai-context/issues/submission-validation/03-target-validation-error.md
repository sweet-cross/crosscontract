# Add `TargetValidationError`

## Context
**Part of PRD:** [submission-validation.md](../../prds/submission-validation.md) — WP1, §5.

`validate_targets` collects every target's failure rather than stopping at the first, so it
needs an aggregate to raise. This is that type. It lands before the loop that raises it so
the loop task is purely about looping.

## Acceptance Criteria
- [ ] `TargetValidationError(errors: dict[str, SchemaValidationError])` exists, subclassing
      plain `Exception`.
- [ ] `.errors` exposes the mapping unchanged.
- [ ] `.to_list()` returns the flattened rows of every sub-error, each row carrying a
      `target` key naming the target it came from.
- [ ] `.to_pandas()` returns `pd.DataFrame(self.to_list())`.
- [ ] The exception message names the failing targets.
- [ ] Importable from both `crosscontract` and `crosscontract.submission`.
- [ ] Docstrings follow the house Google-style convention (`Args:` / `Returns:` / `Raises:`
      where applicable, markdown only, no rST).

## Implementation Details
- **Create:** `src/crosscontract/submission/exceptions.py`. Its own module rather than
  beside the handler, matching `contracts/schema/exceptions/` and `crossclient/exceptions/`.
- **Modify:** [src/crosscontract/submission/\_\_init\_\_.py](../../../src/crosscontract/submission/__init__.py)
  and [src/crosscontract/\_\_init\_\_.py](../../../src/crosscontract/__init__.py) — export it
  alongside `SchemaValidationError`.
- **Create:** `src/tests/submission/test_exceptions.py`.
- **Do not subclass `SchemaValidationError`.** It exists to wrap and parse a pandera
  exception; this one holds a mapping and parses nothing, so inheriting gives it a
  constructor it cannot honour and an `.errors` that means something different.
- Build the sub-errors in tests by validating a genuinely bad frame against a small
  contract, not by constructing `SchemaValidationError("msg")` bare — a bare one carries no
  pandera errors and its `to_list()` is `[]`, which would make the flattening test vacuous.
- **Verification:** `uv run pytest src/tests/submission/test_exceptions.py`
- **Depends on:** nothing. **Blocks:** task 06.
