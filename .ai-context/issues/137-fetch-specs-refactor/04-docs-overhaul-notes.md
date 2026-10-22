# WP4 — Docs-overhaul PRD and tasks follow the new layout

## Context
**Part of:** GitHub issue #137 (no PRD) — WP4

The docs-overhaul tasks still describe the package in three layers and point WP5 at
`transformations/fetch/`. They need the layout-by-role note from issue #137 so the docs
explain the package the way the code is now laid out.

## Acceptance Criteria
- [ ] `.ai-context/prds/docs-overhaul.md` carries a dated note (2026-10-22 or the landing
      date) presenting the package layout by role, as worded in issue #137:
  - `contracts/`: specs (contracts, schemas, and the submission, release, reading and
    fetching specs).
  - `handlers/`: execution based on specs (file readers, `SubmissionHandler`).
  - `crossclient/`: low-level API access.
  - `services/`: high-level API interaction (`CrossReader`, `CrossSubmitter`,
    `create_data_package`).
  - `transformations/`: self-running DataFrame operations, schema-agnostic.
- [ ] In `02-landing-and-contributing.md` the same note supersedes the "package
      architecture (added 2026-10-12)" three-layer note, which is marked superseded and
      kept for history.
- [ ] `04-client-and-registry.md` and `06-submission.md`, which refer to "the same three
      layers", point to the new note instead.
- [ ] `05-release.md` uses `FetchSpec`, renders the fetch models via
      `crosscontract.contracts.fetching`, and lists the new source paths:
      `contracts/fetching/fetch_spec.py`, `contracts/fetching/aggregation_spec.py`, and
      `services/package_creator/_resolve_resource.py` (replacing the stale
      `release/data_package/_resolve_resource.py`).
- [ ] `05-release.md`'s plan for `docs/reference/transformations.md` is adjusted: the
      fetch models belong with the contracts reference, so that page holds the
      transformations only (added in WP6).
- [ ] `grep -rn "FetchSpecMixin\|transformations/fetch" .ai-context/` finds nothing
      outside dated history notes and the deprecated `TODO.md`.

## Implementation Details
- Files:
  - `.ai-context/prds/docs-overhaul.md`
  - `.ai-context/issues/docs-overhaul/02-landing-and-contributing.md`
  - `.ai-context/issues/docs-overhaul/04-client-and-registry.md`
  - `.ai-context/issues/docs-overhaul/05-release.md`
  - `.ai-context/issues/docs-overhaul/06-submission.md`
- Use the wording from WP3's `transformations/` section so CLAUDE.md and the docs plan
  agree.
- Dependencies: after `03-claude-md.md`.
