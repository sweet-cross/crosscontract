# WP2 — Move `SubmissionHandler` and the Excel bundle readers to `crossclient/services/submission/`

## Context
**Part of:** GitHub issue #122 (`CrossSubmitter.submit`) — WP2 of 5.

`SubmissionContractResource` will validate and upload bundles (WP3, WP4). Everything it
calls must sit in or below `crossclient`, so the processing that today lives in
`crosscontract.submission` — the handler and the contract-taking Excel readers — moves
next to the service.

## Acceptance Criteria
- [ ] `SubmissionHandler` lives in `src/crosscontract/crossclient/services/submission/`.
- [ ] `read_excel_bundle` and `read_excel_bundle_bytes` live in
      `src/crosscontract/crossclient/services/submission/`.
- [ ] Both are exported from `crosscontract.crossclient.services.submission`.
- [ ] `crosscontract.submission` and `crosscontract` keep re-exporting
      `SubmissionHandler`, `read_excel_bundle` and `read_excel_bundle_bytes`; public import
      paths are unchanged.
- [ ] `src/crosscontract/submission/submission_handler.py` and
      `src/crosscontract/submission/excel_processing.py` are removed.
- [ ] Nothing under `src/crosscontract/crossclient/` imports from `crosscontract.submission`.
- [ ] The handler and reader tests move to `src/tests/crossclient/submission/` and pass
      without any HTTP (no client, no mocked responses).

## Implementation Details
- Sources: `src/crosscontract/submission/submission_handler.py`,
  `src/crosscontract/submission/excel_processing.py`.
- Targets: `src/crosscontract/crossclient/services/submission/submission_handler.py` and
  `.../excel_processing.py` (same file names); update
  `src/crosscontract/crossclient/services/submission/__init__.py`.
- `transformations/excel/` (`read_excel_workbook_bytes`, the specs) does **not** move.
- Tests to move: `test_submission_handler.py`, `test_validate_targets.py`,
  `test_target_granularity.py`, `test_excel_processing.py` from `src/tests/submission/`,
  plus whatever they need from `src/tests/submission/conftest.py` (e.g. `bundle`). Keep
  `test_submitter.py` where it is.
- `test_excel_processing.py` patches/reads via `crosscontract.submission` as a module;
  re-target those references to the new module.
- Pure move: no behaviour change.
- Dependencies: after `01-move-exceptions-to-crossclient.md`.
