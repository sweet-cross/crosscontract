# WP4 — `validate_submission` in `handlers/submission/`, delegated from the resource

## Context
**Part of:** GitHub issue #122 (`CrossSubmitter.submit`) — WP4 of 6. Critical path.

The sequence in today's `CrossSubmitter.validate_submission` becomes a plain function in
`handlers/submission/`, taking a `SubmissionContract`, a bundle and any `ContractResolver`.
That keeps a submission contract and its data checkable without the client.
`SubmissionContractResource` calls it with its stored contract and a resolver built from
the client. `CrossSubmitter` is the high-level object for the platform: it always takes a
name and passes through to the resource.

`SubmissionHandler` keeps its scope (targets only; reports unclaimed rows, never acts on
them). The function is the caller that sets the policy.

## Acceptance Criteria
- [ ] `validate_submission(contract, df, resolver, check_existing_primary_key=True,
      check_existing_foreign_key=True, check_dimension_granularity=True, lazy=True)` exists
      in `src/crosscontract/handlers/submission/`, is exported from
      `crosscontract.handlers.submission`, and returns `dict[str, pd.DataFrame]`.
- [ ] It runs today's sequence unchanged: `contract.validate_references(resolver)`, then
      (1) `contract.validate_data(df, ...)`, (2) unclaimed rows → `UnclaimedRowsError`,
      (3) `SubmissionHandler.validate_targets`. Extraction runs on the bundle as delivered.
- [ ] `SubmissionContractResource.validate_submission(df, ...)` (same flags and defaults)
      returns `validate_submission(self.contract, df, CrossContractResolver(...), ...)`.
- [ ] `CrossSubmitter.validate_submission(name, df, ...)` takes the submission contract's
      **name** and returns `self._client.submissions.get(name).validate_submission(...)`.
      This is a deliberate breaking change of the submitter's signature (previously a
      `SubmissionContract`).
- [ ] The full docstring (Google style, Args/Returns/Raises, validation is advisory) lives
      on the function. The resource and submitter methods have their own short docstrings
      with the same Args/Returns/Raises.
- [ ] Tests: the sequence is tested on the function with a mocked `ContractResolver`, no
      HTTP (move the current validation tests from `src/tests/submission/test_submitter.py`
      to `src/tests/handlers/submission/`). Resource and submitter tests only check that they
      delegate with the right contract and resolver.

## Implementation Details
- Source: `src/crosscontract/submission/submitter.py` (`validate_submission`).
- Targets: a new module in `src/crosscontract/handlers/submission/` (e.g.
  `validate_submission.py`), `src/crosscontract/crossclient/services/submission/submission_resource.py`,
  `src/crosscontract/submission/submitter.py`.
- The function imports only from `contracts`, `exceptions` and its own package — never
  `crossclient`.
- The resource reaches the client through `self._service._client`; build the resolver as
  `CrossContractResolver(self._service._client.contracts)`.
- After this, `CrossSubmitter` no longer needs its own `self._resolver`; drop it if nothing
  else uses it.
- Update the resource's class docstring: it now validates bundles.
- Dependencies: after `03-move-to-handlers-and-exceptions.md`.
