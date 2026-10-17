# WP3 — Move submission execution to `handlers/submission/`, its exceptions to `exceptions/`

## Context
**Part of:** GitHub issue #122 (`CrossSubmitter.submit`) — WP3 of 6. Supersedes the
targets of WP1 and WP2, which moved this code into `crossclient/`.

`crossclient/services/submission/` ended up with two jobs: transport (service, resource,
schemas) and execution (handler, readers). Execution moves to its own top-level package,
`handlers/`, a sibling of `crossclient/` on disk and below it in the import graph:

```
constants ← transformations ← contracts ← handlers ← crossclient ← submission
```

The handler raises the submission exceptions and must not import `crossclient`, so those
move to a new top-level `exceptions/` package. Moving every other exception class there is
a separate follow-up issue; until then `exceptions/` imports `SchemaValidationError` from
`contracts` and sits above it.

## Acceptance Criteria
- [ ] `src/crosscontract/handlers/submission/` holds `SubmissionHandler`,
      `read_excel_bundle` and `read_excel_bundle_bytes`, exported from
      `crosscontract.handlers.submission` (and `crosscontract.handlers`).
- [ ] `src/crosscontract/exceptions/` holds `TargetValidationError` and
      `UnclaimedRowsError`, exported from `crosscontract.exceptions`.
- [ ] Nothing under `handlers/` or `exceptions/` imports `crossclient` or
      `crosscontract.submission`.
- [ ] `crossclient/services/submission/` keeps only transport: service, resource, schemas.
      `crossclient/exceptions/` keeps only the `CrossClientError` family and
      `raise_from_response`.
- [ ] Public import paths unchanged: `crosscontract` and `crosscontract.submission` still
      export `SubmissionHandler`, the readers and both exceptions. `crossclient` no longer
      re-exports any of them.
- [ ] Tests move to `src/tests/handlers/submission/` and `src/tests/exceptions/`, stay free
      of HTTP, and pass. The re-export test in `src/tests/submission/test_submitter.py`
      checks against the new modules.

## Implementation Details
- Sources: `src/crosscontract/crossclient/services/submission/submission_handler.py`,
  `.../excel_processing.py`, `src/crosscontract/crossclient/exceptions/submission_exceptions.py`.
- Targets: `src/crosscontract/handlers/__init__.py`,
  `src/crosscontract/handlers/submission/{__init__,submission_handler,excel_processing}.py`,
  `src/crosscontract/exceptions/{__init__,submission_exceptions}.py` (keep the file names).
- Update `__init__.py` of `crossclient/services/submission/`, `crossclient/exceptions/`,
  `crosscontract.submission`, plus `submission/submitter.py`.
- Tests to move: `src/tests/crossclient/submission/{test_submission_handler,test_validate_targets,test_target_granularity,test_excel_processing}.py`
  and `src/tests/crossclient/exceptions/test_submission_exceptions.py`. Add the matching
  `__init__.py` files.
- Pure move: no behaviour change.
- Dependencies: none (WP1 and WP2 are done).
