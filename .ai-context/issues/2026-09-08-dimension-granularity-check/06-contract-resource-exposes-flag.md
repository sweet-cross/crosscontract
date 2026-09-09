# Expose the flag on the client path

## Context
**Part of PRD:** [.ai-context/prds/2026-09-08-dimension-granularity-check.md](../../prds/2026-09-08-dimension-granularity-check.md)

WP2, step 3. The client path is where an upload is actually gated. The default here is
what buys submitters their grace period, so it is load-bearing rather than incidental.

## Acceptance Criteria
- [ ] `ContractResource.validate_dataframe` takes `check_dimension_granularity: bool =
      False` and passes it to `contract.validate_data`.
- [ ] `add_data` does **not** set it — the check ships dormant and a caller opts in
      explicitly (PRD §5).
- [ ] The docstring states that a `SchemaValidationError` from this check is converted to
      `ValidationError` like the others, and that the client-side result is advisory: the
      platform re-validates on ingest (ADR 0005).
- [ ] A test asserts `add_data` does not enable the flag.

## Implementation Details
- Modify: `src/crosscontract/crossclient/services/contract_resource.py` and its tests.
- There is deliberately **no warn mode**. A warning would add a third state to five layers
  to buy what the `False` default already gives (PRD §5).
- Depends on `05`.
- Do not run pytest, ruff or mypy without asking (repo `CLAUDE.md`).
