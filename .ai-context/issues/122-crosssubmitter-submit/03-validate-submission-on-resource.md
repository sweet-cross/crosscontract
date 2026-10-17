# WP3 — Move `validate_submission` onto `SubmissionContractResource`

## Context
**Part of:** GitHub issue #122 (`CrossSubmitter.submit`) — WP3 of 5. Critical path.

Validation of a delivered bundle moves to the low-level client, the same way
`ContractResource.validate_dataframe` validates data for a contract. The resource holds
the submission contract the platform stores, so validation always runs against the
platform's copy. `CrossSubmitter` becomes a pure pass-through.

## Acceptance Criteria
- [ ] `SubmissionContractResource.validate_submission(df, check_existing_primary_key=True,
      check_existing_foreign_key=True, check_dimension_granularity=True, lazy=True)` exists
      and returns `dict[str, pd.DataFrame]` (validated target data keyed by target name).
- [ ] It runs the same sequence as today's `CrossSubmitter.validate_submission`: check
      every target's contract (`validate_references`), then (1) the bundle against the
      submission contract's `tableschema`, (2) unclaimed rows → `UnclaimedRowsError`,
      (3) every target via `SubmissionHandler.validate_targets`. Extraction runs on the
      bundle as delivered.
- [ ] Its resolver is a `CrossContractResolver` built from the client the service holds
      (`client.contracts`).
- [ ] `CrossSubmitter.validate_submission(name, df, ...)` takes the submission contract's
      **name** and returns `self._client.submissions.get(name).validate_submission(...)`.
      This is a deliberate breaking change of the submitter's signature (previously a
      `SubmissionContract`).
- [ ] The docstring moves with the method (Google style, Args/Returns/Raises) and keeps
      stating that validation is advisory.
- [ ] The current validation tests in `src/tests/submission/test_submitter.py` run against
      the resource (in `src/tests/crossclient/submission/test_submission_resource.py`); the
      submitter tests only check that it fetches by name and delegates.

## Implementation Details
- Source: `src/crosscontract/submission/submitter.py` (`validate_submission`).
- Target: `src/crosscontract/crossclient/services/submission/submission_resource.py`.
- The resource reaches the client through `self._service._client`; build the resolver as
  `CrossContractResolver(self._service._client.contracts)`.
- After this, `CrossSubmitter` no longer needs its own `self._resolver`; drop it if nothing
  else uses it.
- Update the resource's class docstring: it now validates bundles.
- Dependencies: after `02-move-handler-and-readers-to-crossclient.md`.
