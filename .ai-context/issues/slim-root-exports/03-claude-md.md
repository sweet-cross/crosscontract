# WP3 — CLAUDE.md states the new export rule

## Context
**Part of:** the slim-root-exports refactor (agreed in discussion; no PRD) — WP3

CLAUDE.md still says the public subpackages are re-exported from the root. After WP1 and
WP2 it must state the rule: the root exposes the entry points plus `CrossContract` and
`SubmissionContract`; everything else is imported from its subpackage, and exceptions
only from `crosscontract.exceptions`.

## Acceptance Criteria
- [ ] The Architecture intro (`CLAUDE.md` line 47) states what the root exposes
      (`CrossClient`, `CrossReader`, `CrossRegistry`, `CrossSubmitter`, `CrossContract`,
      `SubmissionContract`) and that everything else comes from its subpackage. It no
      longer says `contracts/`, `crossclient/` and `services/` are re-exported from the
      root.
- [ ] The `contracts/release/` entry (line 81) says the two release specs are
      re-exported from `contracts/` only, not from the top-level package.
- [ ] The `exceptions/` section says exceptions are imported from
      `crosscontract.exceptions` only; no other package re-exports them.
- [ ] The `services/` section (line 138, "the root re-exports the three classes but not
      `create_data_package`") is checked and still true.
- [ ] No sentence in CLAUDE.md claims a root or subpackage re-export that the
      `__init__.py` files do not have.

## Implementation Details
- File: `CLAUDE.md` (repo root).
- Describe the rule, not why it changed (rationale goes in the PR body).
- The PR body carries a "where things moved" table, one row per removed root name with
  its new import, as the migration guide for cross_back (pinned to 0.28.0; it imports
  `TableSchema`, `SchemaValidationError` and `SubmissionHandler` from the root).
- Dependencies: after `01-trim-root-init.md` and
  `02-schema-validation-error-from-exceptions-only.md`.
