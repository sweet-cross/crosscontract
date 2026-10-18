# WP2 — ADR, CONTEXT.md and CLAUDE.md for the release spec move

## Context
**Part of PRD:** none. Source is GitHub issue #127 plus the discuss-and-plan session of
2026-10-18. This is WP2.

After WP1, `contracts/` holds contracts plus the specs that name them (submission and
release), rather than contracts only. That shift and the new home of the release specs
need to be recorded where maintainers and agents look first.

## Acceptance Criteria
- [ ] `.ai-context/adrs/0012-release-specs-live-in-contracts.md` exists and records:
  - `contracts/` is the declarative layer: contracts plus the specs that name them.
  - Release specs live in `contracts/release/`.
  - Release execution stays in `release/data_package/` against `CrossRegistry`. Moving it
    to `handlers/release/` against a resolver is a separate issue, to be opened when
    cross_back needs server-side data packages.
  - The old module path `crosscontract.release.data_package.release_specification` is
    removed without a shim. Package-level re-exports remain.
  - Context: it follows ADR 0010 / ADR 0011 and #120.
- [ ] `.ai-context/CONTEXT.md`: the **Release spec** entry and the relationship notes
      that mention it name the new location. Terminology stays unchanged.
- [ ] `.claude/CLAUDE.md` architecture section:
  - The `contracts/` heading and intro describe the declarative layer, and a
    `contracts/release/` entry lists the three spec classes.
  - The `release/data_package/` section no longer lists `release_specification.py` as
    its own. It says the specs come from `contracts/release/` and are re-exported.
  - The import-graph paragraph mentions that release specs are in `contracts/` and
    execution is in `release/`.
- [ ] Every path and class name mentioned matches the code after WP1.

## Implementation Details
- **Depends on** `01-move-release-specs.md`, but only for the final paths. It can be
  drafted in parallel.
- Files:
  - Create `.ai-context/adrs/0012-release-specs-live-in-contracts.md`, following the
    format of `0010-submission-specs-live-in-contracts-execution-in-submission.md`.
  - Modify `.ai-context/CONTEXT.md`. The relevant hits are around the "Release and
    distribution" section and the relationships list.
  - Modify `.claude/CLAUDE.md`.
- Do not edit `.ai-context/TODO.md` (deprecated).
- Documentation only. No code changes.
