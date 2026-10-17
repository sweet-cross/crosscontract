# WP3 — Document the exceptions package

## Context
**Part of:** sweet-cross/crosscontract#126 — WP3

After WP1 and WP2, every exception class lives in `crosscontract.exceptions`, and `exceptions/` is a
base layer. The API reference, CLAUDE.md and ADR 0011 still describe the old layout. This task
brings them up to date.

## Acceptance Criteria
- [ ] The API reference renders `SchemaValidationError` from its new module. Nothing in `docs/` refers
      to `crosscontract.contracts.schema.exceptions`.
- [ ] In `.claude/CLAUDE.md`:
  - The `exceptions/` section lists every class it holds: `SchemaValidationError`,
    `TargetValidationError`, `UnclaimedRowsError` and the `CrossClientError` family.
  - The `crossclient/` section says `crossclient/exceptions/` holds only `raise_from_response` plus
    re-exports.
  - The import graph reads `constants, exceptions ← transformations ← contracts ← handlers ← crossclient ← submission`,
    and its rules forbid importing anything internal from `exceptions/`.
  - Every "issue #126 moves the rest" / "for now `exceptions/` sits above `contracts/`" remark is gone.
- [ ] ADR 0011 (`.ai-context/adrs/0011-submission-execution-lives-in-handlers-transport-in-crossclient.md`)
      has an amendment recording three points:
  - `exceptions/` now holds every exception class and imports nothing from the package.
  - It does depend on pandas and pandera, because `SchemaValidationError` carries the pandera report parser.
  - That parser reads the message format (`Columns '<cols>' in check '<label>' …`, `CHECK_COLUMNS_PATTERN`)
    that the checks in `contracts/schema/validation/checks/` write, so the format is shared across the
    two layers.
- [ ] `uv run mkdocs build` resolves the reference and introduces no new warnings (run only with the
      user's go-ahead).

## Implementation Details
- **Modify:**
  - `docs/reference/contracts.md:36`: `::: crosscontract.contracts.schema.exceptions.validation_error`
    → `::: crosscontract.exceptions.schema_exceptions`. Decide whether the client exceptions and the
    submission exceptions also get a reference entry. Keep it to what fits the existing reference pages,
    or ask.
  - `.claude/CLAUDE.md`: these sections — `contracts/schema/` (where `SchemaValidationError` is mentioned
    via `validate_dataframe.py`), `crossclient/`, `exceptions/`, and the import-graph paragraph at the end
    of the `submission/` section.
  - `.ai-context/adrs/0011-submission-execution-lives-in-handlers-transport-in-crossclient.md`: append an
    amendment section dated when it lands. Do not rewrite the original decision text.
- Follow the CLAUDE.md docstring and doc conventions. This task changes no code.
- **Dependencies:** must be done after `01-move-schema-validation-error.md` and `02-move-client-errors.md`.
- **Downstream:** once this ships, sweet-cross/cross_back#532 can pin the release and switch its
  `SchemaValidationError` imports to `crosscontract.exceptions`.
