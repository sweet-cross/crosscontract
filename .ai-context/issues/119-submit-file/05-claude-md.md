# WP5 — CLAUDE.md architecture update

## Context
**Part of:** GitHub issue #119 (body, discussion summary, and the 2026-10-22 update comment)

CLAUDE.md describes the package layout for agents working in the repo, and #119 changes
it. The user-facing docs for `submit_file` and `FileReadError` are not part of this task:
they are recorded in `.ai-context/issues/docs-overhaul/06-submission.md` (note of
2026-10-22).

## Acceptance Criteria
- [ ] The `handlers/` section describes `handlers/readers/`: the CSV and parquet readers
      (bytes core plus path wrapper, cross_back's `read_csv` settings) and that they raise
      `FileReadError`.
- [ ] The `exceptions/` section lists `reader_exceptions.py` with `FileReadError`.
- [ ] The `transformations/excel/` and `handlers/submission/` entries say the Excel
      readers raise `FileReadError` for an unreadable workbook or a layout mismatch.
- [ ] The `services/submitter/` entry lists `submit_file(name, path, ...)`.
- [ ] Nothing else in CLAUDE.md changes.

## Implementation Details
- Files to modify:
  - `.claude/CLAUDE.md`
- Describe the final shape as merged, not the plan: re-read the code from WP1–WP4 first.
- Dependencies: after 01–04.
