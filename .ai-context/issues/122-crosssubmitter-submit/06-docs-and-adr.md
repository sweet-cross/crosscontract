# WP6 — ADR, CONTEXT.md, CLAUDE.md and TODO.md

## Context
**Part of:** GitHub issue #122 (`CrossSubmitter.submit`) — WP6 of 6.

WP3–WP5 move submission execution to a new top-level `handlers/` package, the submission
exceptions to a new top-level `exceptions/` package, put validation and upload on
`SubmissionContractResource`, and reduce `CrossSubmitter` to a name-based pass-through.
The recorded decisions and the architecture description must follow.

## Acceptance Criteria
- [ ] A new ADR `.ai-context/adrs/0011-…md` records:
  - the layering `constants ← transformations ← contracts ← handlers ← crossclient ← submission`;
  - `handlers/` executes specs (here: `handlers/submission/` with `SubmissionHandler`, the
    Excel bundle readers and `validate_submission`), depends only on `contracts` and
    `transformations`, and reaches the platform only through the `ContractResolver`
    protocol;
  - `crossclient/` is transport: the resource validates and submits by delegating to
    `handlers/`;
  - `CrossSubmitter` is the high-level object for the platform, takes names only, and
    passes through; validating a local contract goes through
    `handlers.submission.validate_submission` directly;
  - top-level `exceptions/` is the target home for all exception classes; for now it holds
    only the submission exceptions (the rest follows in a separate issue).
- [ ] It supersedes ADR 0007's "the submitter sequences the steps and owns the policy"
      consequence, and ADR 0010's placement of the handler, the readers and the
      exceptions in `submission/`. Both old ADRs get a one-line pointer to 0011.
- [ ] `.ai-context/CONTEXT.md`: **Submitter**, **Submission handler**, **Submission
      validation** (the caller that sets the policy is now `validate_submission`) and
      related entries reflect the new placement.
- [ ] `.claude/CLAUDE.md` architecture section: new `handlers/` and `exceptions/`
      sections; `crossclient/services/submission/` validates and submits (remove "It
      neither validates nor submits bundles" and "No upload yet"); `submission/` holds only
      `CrossSubmitter` plus re-exports; the import-graph paragraph and the "packages named
      `submission`" note updated (now four).
- [ ] `crosscontract.submission`'s package docstring matches what is left in it.
- [ ] The `.ai-context/TODO.md` entry "Write a docs page for the submission path" is
      removed (acceptance criterion of #122).

## Implementation Details
- Files: `.ai-context/adrs/0007-the-submitter-is-the-provider-side-mirror-of-the-registry.md`,
  `.ai-context/adrs/0010-submission-specs-live-in-contracts-execution-in-submission.md`,
  new `.ai-context/adrs/0011-*.md`, `.ai-context/CONTEXT.md`, `.claude/CLAUDE.md`,
  `src/crosscontract/submission/__init__.py`, `.ai-context/TODO.md`.
- `docs/` currently has no page referencing the moved symbols; no mkdocs change needed
  unless one appears by then. The deferred docs task
  `.ai-context/issues/docs-overhaul/06-submission.md` re-reads `dev` before starting and is
  not edited here.
- Not in scope: merging `CrossSubmitter` into `CrossRegistry` (decided later); moving the
  remaining exceptions (separate issue).
- Dependencies: after `05-submit-upload.md`.
