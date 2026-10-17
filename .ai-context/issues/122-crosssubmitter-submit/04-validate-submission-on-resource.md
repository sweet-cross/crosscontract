# WP4 — `SubmissionHandler.validate_submission`, delegated from the resource

## Context
**Part of:** GitHub issue #122 (`CrossSubmitter.submit`) — WP4 of 6. Critical path.

The sequence in today's `CrossSubmitter.validate_submission` becomes a method on
`SubmissionHandler`, which already binds the contract and the bundle. It takes any
`ContractResolver`, so a submission contract and its data stay checkable without the
client, and the handler remains the one public element for executing a submission.
`SubmissionContractResource` calls it with its stored contract and a resolver built from
the client. `CrossSubmitter` is the high-level object for the platform: it always takes a
name and passes through to the resource.

The handler thereby takes over the policy that the submitter held: a bundle failing its
own schema stops the run, and unclaimed rows raise `UnclaimedRowsError`.

## Acceptance Criteria
- [ ] `SubmissionHandler.validate_submission(resolver, check_existing_primary_key=True,
      check_existing_foreign_key=True, check_dimension_granularity=True, lazy=True)` exists
      and returns `dict[str, pd.DataFrame]`.
- [ ] It runs today's sequence unchanged: `self.contract.validate_references(resolver)`,
      then (1) `self.contract.validate_data(self.bundle, ...)`, (2) `self.unclaimed_rows()`
      → `UnclaimedRowsError`, (3) `self.validate_targets(...)`. Extraction runs on the bundle
      as delivered, never on the coerced frame step 1 returns.
- [ ] The docstring states plainly that the key-check defaults are `True` here, unlike
      `validate_targets`, because a resolver is required.
- [ ] `SubmissionContractResource.validate_submission(df, ...)` (same flags and defaults)
      returns `SubmissionHandler(self.contract, df).validate_submission(CrossContractResolver(...), ...)`.
- [ ] `CrossSubmitter.validate_submission(name, df, ...)` takes the submission contract's
      **name** and returns `self._client.submissions.get(name).validate_submission(...)`.
      This is a deliberate breaking change of the submitter's signature (previously a
      `SubmissionContract`).
- [ ] The full docstring (Google style, Args/Returns/Raises, validation is advisory) lives
      on the handler method. The resource and submitter methods have their own short
      docstrings with the same Args/Returns/Raises.
- [ ] Tests: the sequence is tested on the handler with a mocked `ContractResolver`, no HTTP
      (move the current validation tests from `src/tests/submission/test_submitter.py` to
      `src/tests/handlers/submission/`). Resource and submitter tests only check that they
      delegate with the right contract and resolver.

## Implementation Details
- Source: `src/crosscontract/submission/submitter.py` (`validate_submission`).
- Targets: `src/crosscontract/handlers/submission/submission_handler.py`,
  `src/crosscontract/crossclient/services/submission/submission_resource.py`,
  `src/crosscontract/submission/submitter.py`.
- The handler imports `UnclaimedRowsError` from `crosscontract.exceptions`; it never
  imports `crossclient`.
- Update the handler's class docstring: its scope now includes the full submission
  validation, not only targets.
- The resource reaches the client through `self._service._client`; build the resolver as
  `CrossContractResolver(self._service._client.contracts)`.
- After this, `CrossSubmitter` no longer needs its own `self._resolver`; drop it if nothing
  else uses it.
- Update the resource's class docstring: it now validates bundles.
- Dependencies: after `03-move-to-handlers-and-exceptions.md`.
