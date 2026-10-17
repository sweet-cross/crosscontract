# WP5 — ADR, CONTEXT.md, CLAUDE.md and TODO.md

## Context
**Part of:** GitHub issue #122 (`CrossSubmitter.submit`) — WP5 of 5.

WP1–WP4 move submission processing from `crosscontract.submission` into the client layer
and reduce `CrossSubmitter` to a pass-through. The recorded decisions and the
architecture description must follow.

## Acceptance Criteria
- [ ] A new ADR `.ai-context/adrs/0011-…md` records: the client is the centralized service
      layer, so `SubmissionHandler`, the Excel bundle readers, the submission exceptions,
      `validate_submission` and `submit` live in `crossclient/`; `CrossSubmitter` is a
      pass-through; a dedicated service module would be the cleaner home but is out of
      reach for now.
- [ ] It supersedes ADR 0007's "the submitter sequences the steps / validates nothing
      itself but owns the policy" consequence, and ADR 0010's placement of the handler,
      the readers and the exceptions in `submission/`. Both old ADRs get a one-line
      pointer to 0011.
- [ ] `.ai-context/CONTEXT.md`: **Submitter**, **Submission handler** and related entries
      reflect the new placement.
- [ ] `.claude/CLAUDE.md` architecture section: `crossclient/services/submission/` now
      holds the handler, readers, `validate_submission` and `submit` (remove "It neither
      validates nor submits bundles"); `submission/` holds only `CrossSubmitter` plus
      re-exports; the import-graph paragraph is still correct.
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
- Not in scope: the possible merge of `CrossSubmitter` into `CrossRegistry`; decided later.
- Dependencies: after `04-submit-upload.md`.
