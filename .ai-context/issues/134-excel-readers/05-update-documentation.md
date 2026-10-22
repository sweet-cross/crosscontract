# Update documentation for the readers move and NA default

## Context
**Part of PRD:** GitHub issue sweet-cross/crosscontract#134 (no PRD file)

The architecture notes and user docs still describe `transformations/excel/`, the
Excel reader under `handlers/submission/`, and the CSV token list.

## Acceptance Criteria
- [ ] `.claude/CLAUDE.md` architecture section:
  - `contracts/readers/` described (Excel specs); `transformations/excel/` removed.
  - `handlers/readers/` lists the Excel reader and `constants.py`; the readers text
    states the Frictionless NA default (only an empty cell is missing, `"NA"` stays a
    string) and drops "uses cross_back's `read_csv` settings" and the explicit NA list.
  - `handlers/submission/` no longer lists `excel_processing.py`.
  - `SubmissionContract`'s `excel_processor` text says it is optional for Excel.
  - The import-graph sentence still matches (no `transformations` Excel reader).
- [ ] The WP6 note in `.ai-context/issues/docs-overhaul/06-submission.md` names the new
      paths and the default without `excel_processor`.
- [ ] `docs/client/index.md` (lines ~106–107) says `read_excel_bundle` works for any
      submission contract.
- [ ] No old path (`transformations.excel`, `handlers.submission.excel_processing`)
      remains in `.claude/CLAUDE.md` or `docs/`.

## Implementation Details
- Files: `.claude/CLAUDE.md`, `.ai-context/issues/docs-overhaul/06-submission.md`,
  `docs/client/index.md`.
- ADR `.ai-context/adrs/0010-submission-specs-live-in-contracts-execution-in-submission.md`
  stays unchanged (historical record).
- Docstrings follow the repo convention (Google style, markdown only, caller's view).
- Dependencies: after 03 and 04.
