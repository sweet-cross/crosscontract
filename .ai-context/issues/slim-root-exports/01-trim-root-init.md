# WP1 — Trim the root `__init__.py`

## Context
**Part of:** the slim-root-exports refactor (agreed in discussion; no PRD) — WP1

The root `crosscontract` package re-exports exceptions, release specs, a handler and a
client response model, so it reads like an index of the whole package. It should expose
only the entry points and the two contracts users hand to them; everything else is
imported from its subpackage. This is the breaking change of the refactor and the
critical path.

## Acceptance Criteria
- [ ] `crosscontract.__all__` is exactly `CrossClient`, `CrossReader`, `CrossRegistry`,
      `CrossSubmitter`, `CrossContract`, `SubmissionContract`. `__version__` stays.
- [ ] The root no longer exposes `TableSchema`, `BaseContract`,
      `CrossDataPackageReleaseSpec`, `CrossDataResourceReleaseSpec`,
      `SchemaValidationError`, `TargetValidationError`, `UnclaimedRowsError`,
      `SubmissionHandler` or `Submission`. No alias, no deprecation shim.
- [ ] `grep -rn "from crosscontract import" src/ docs/ README.md` shows only the six
      names above.
- [ ] Every removed name stays importable from its home package:
  - `TableSchema`, `BaseContract`, `CrossDataPackageReleaseSpec`,
    `CrossDataResourceReleaseSpec` → `crosscontract.contracts`
  - `SchemaValidationError`, `TargetValidationError`, `UnclaimedRowsError` →
    `crosscontract.exceptions`
  - `SubmissionHandler` → `crosscontract.handlers`
  - `Submission` → `crosscontract.crossclient`

## Implementation Details
- `src/crosscontract/__init__.py`: keep the imports from `.contracts` (only
  `CrossContract`), `.contracts.submission` (`SubmissionContract`), `.crossclient`
  (only `CrossClient`) and `.services`; drop the `.exceptions` and `.handlers` imports.
- Tests:
  - `src/tests/exceptions/test_submission_exceptions.py:4` →
    `from crosscontract.exceptions import TargetValidationError, UnclaimedRowsError`.
  - `src/tests/exceptions/test_schema_exceptions.py`, `test_exported_from_all_paths`:
    remove the `import crosscontract` line and the
    `crosscontract.SchemaValidationError` assertion (WP2 removes the rest of the test).
- Docs: `docs/client/index.md:96` →
  `from crosscontract import CrossClient, SubmissionContract` plus
  `from crosscontract.handlers import SubmissionHandler`.
- The API reference pages (`docs/reference/*.md`) already use full module paths and
  need no change.
- Dependencies: none. Branch off `dev`; PR title `refactor!: ...`.
