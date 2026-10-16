# WP3 — Docs and issue text

## Context
**Part of PRD:** none — GitHub issue #121, as refined in the planning session of 2026-10-16
(see `01-models-and-submission-contract-resource.md`).

Records what WP1 and WP2 built: in CLAUDE.md's architecture section, in the API reference,
and in the issue itself, whose text predates the planning decisions.

## Acceptance Criteria
- [ ] CLAUDE.md, `crossclient/` section: describes `SubmissionService` (exposed as
      `client.submissions`), `SubmissionContractResource`, and `Submission`.
- [ ] CLAUDE.md, *Two packages named `submission`* paragraph: extended to three —
      `crosscontract.contracts.submission` (specification),
      `crosscontract.crossclient.services.submission` (low-level client),
      `crosscontract.submission` (high-level execution).
- [ ] `docs/reference/client.md` renders `SubmissionService`, `SubmissionContractResource`,
      and `Submission`, each once.
- [ ] Issue #121 text updated: `get_list` removed, `overview(project_name)` added, `create`
      re-fetches after the POST, the upload moved to the follow-up issue along with its open
      public/private question.
- [ ] `uv run mkdocs build` succeeds (run only with the user's permission).

## Implementation Details
- Modify:
  - `.claude/CLAUDE.md`
  - `docs/reference/client.md` — add `::: crosscontract.crossclient.services.SubmissionService`
    etc., following the existing `ContractService` entries.
- The issue edit is outward-facing: draft the new text and confirm with the user before
  running `gh issue edit 121`.
- Depends on: `02-submission-service-and-wiring.md`.
