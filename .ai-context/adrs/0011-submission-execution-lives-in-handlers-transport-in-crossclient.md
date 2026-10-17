# Submission execution lives in handlers/, transport in crossclient/

Executing a **Submission contract** moves out of `submission/` into a new top-level
`handlers/` package: `handlers/submission/` holds `SubmissionHandler` and the Excel bundle
readers. The exceptions they raise, `TargetValidationError` and `UnclaimedRowsError`, move
to a new top-level `exceptions/` package. `crossclient/` keeps transport only, and its
`SubmissionContractResource` validates and submits bundles by delegating to the handler.
`CrossSubmitter` becomes a name-based pass-through. The import graph runs:

```
constants ← transformations ← contracts ← exceptions ← handlers ← crossclient ← submission
```

This supersedes ADR 0010's placement of the handler, the readers and the exceptions in
`submission/`, and ADR 0007's consequence that the **Submitter** sequences the steps of a
**Submission validation** and owns the policy between them. That `CrossSubmitter` is the
**Data provider**'s entry point (ADR 0007) is unchanged.

## Why

The low-level client is the centralized service layer, the same way `ContractResource`
validates and uploads data for a **Contract**. So validating and submitting a bundle
belongs on the resource, and the high-level `CrossSubmitter` only looks a contract up by
name and passes through. Everything the resource calls must then sit at or below
`crossclient/`.

Inside `crossclient/services/submission/` the execution would have given that package two
jobs: transport (service, resource, schemas) and execution, which runs offline and needs
only a contract and a `ContractResolver`. A sibling package keeps them apart. Its name
follows the domain term: `handlers/submission/` holds the **Submission handler**. A
dedicated service module above the client would be the cleaner long-term home for all
execution, but is out of reach for now.

`handlers/` sits below `crossclient/` and must not import it, so the handler cannot raise
exceptions defined in `crossclient/exceptions/`. Exceptions in general belong in one
top-level package. For now `exceptions/` holds only the submission exceptions and sits
above `contracts/`, because `TargetValidationError` holds `SchemaValidationError`s; issue
#126 moves every exception class there and makes it a dependency-free base.

> **Amended 2026-10-17** (#126). `exceptions/` now holds every exception class:
> `SchemaValidationError`, the submission exceptions and the `CrossClientError` family. It
> imports nothing from the rest of the package, so the import graph runs
> `constants, exceptions ← transformations ← contracts ← handlers ← crossclient ← submission`.
> It is not free of dependencies: `SchemaValidationError` carries the pandera report
> parser, so `exceptions/` depends on pandas and pandera. That parser reads, through
> `CHECK_COLUMNS_PATTERN`, the message format the checks in
> `contracts/schema/validation/checks/` write (`Columns '<cols>' in check '<label>' …`), so
> the format is shared across the two layers and changes in both together.
> `raise_from_response` stays in `crossclient/`, now as `crossclient/exception_factory.py`;
> `crossclient/exceptions/` and `contracts/schema/exceptions/` are gone, and so are their
> import paths.

## The full validation is a method on the handler

`SubmissionHandler.validate_submission(resolver, ...)` runs the whole **Submission
validation**: the bundle against its own **Schema**, then its **Unclaimed rows**, then every
**Target**, stopping at the first step that fails. A method rather than a free function
keeps the handler the one public element for executing a submission, and the handler
already binds the contract and the bundle. The handler thereby owns the policy the
**Submitter** held: a failed bundle stops the run, and unclaimed rows raise
`UnclaimedRowsError`. Taking any `ContractResolver` keeps a local contract checkable
without the client: `SubmissionHandler(contract, df).validate_submission(resolver)`.

Two choices follow cross_back's ingest pipeline:

- **`check_existing_primary_key` defaults to `False`**; the other checks stay on. The
  stored keys still include the rows a resubmission replaces under its `replace_key`, so
  checking against them would reject every correction. Duplicated or missing key values
  within a target are caught either way; collisions with rows stored by *other*
  submissions are not.
- **No `validate_references` pre-check.** A target contract the resolver cannot supply
  surfaces in the target step as a `ValueError`, not collected into the
  `TargetValidationError`. The platform enforces that every target contract declares the
  `replace_key` columns when the submission contract is created.

## Submitting

`SubmissionContractResource.submit(df, filename=None, validate=True)` validates with the
handler's defaults, then serializes the bundle exactly as delivered to parquet and uploads
it; `CrossSubmitter.submit(name, df, filename=None, validate=True)` passes through. There
are no per-check flags: `validate` switches the whole local validation on or off, and
custom checks go through `validate_submission` followed by `submit(..., validate=False)`.
`filename` is a stem; `.parquet` is appended, and without one the file is named after the
contract and the UTC upload time. The service's private `_upload_submission(name, file,
filename)` sends a file unchanged, so `submit_file` (#119) can reuse it; the platform
reads the format from the filename extension.

## Consequences worth knowing

- **Four packages named `submission`**: `contracts.submission` (specs),
  `handlers.submission` (execution), `crossclient.services.submission` (transport) and
  `submission` (`CrossSubmitter` plus re-exports). Name the full path.
- **Public import paths are unchanged.** `crosscontract` and `crosscontract.submission`
  still export `SubmissionHandler`, the readers and both exceptions, and now also
  `Submission`.
- **Breaking:** `CrossSubmitter.validate_submission` takes a submission contract's name
  instead of a `SubmissionContract`.
- **ADR 0007's claim that a `False` `check_existing_primary_key` suppresses primary-key
  uniqueness entirely is wrong.** Uniqueness within the data is always checked; the flag
  only adds the comparison with stored values.
