# Correct the prose that now contradicts the code

## Context
**Part of PRD:** [submission-validation.md](../../prds/submission-validation.md) — WP4, §4.

Two documents assert the rule this feature reverses. `SubmissionHandler`'s class docstring
states outright that no method runs every target, and CLAUDE.md's `submission/` section does
not mention the handler at all. Left alone, both become actively misleading rather than
merely stale.

## Acceptance Criteria
- [ ] The `SubmissionHandler` class docstring no longer claims "There is deliberately no
      method that runs every target…". The paragraph is **rewritten**, not appended to.
- [ ] It states the current shape: one target at a time or all of them; across targets every
      failure is collected; target contracts arrive from the caller, directly or through a
      resolver, and the handler never constructs one.
- [ ] The `Attributes:` block still matches the class, and the docstring follows the house
      Google-style convention.
- [ ] CLAUDE.md's `submission/` section lists `submission_handler.py` — currently absent
      entirely — with one line each for extraction and the validation surface.
- [ ] No behaviour change; no test change.

## Implementation Details
- **Modify:** [src/crosscontract/submission/submission_handler.py](../../../src/crosscontract/submission/submission_handler.py) —
  the class docstring, lines 17–35.
- **Modify:** [.claude/CLAUDE.md](../../../.claude/CLAUDE.md) — the `submission/` subsection
  under *Architecture*.
- Source of truth for the wording: the **Submission handler** and **Submission validation**
  entries in [CONTEXT.md](../../CONTEXT.md), already updated, and the 2026-08-31 amendment in
  [ADR 0004](../../adrs/0004-submission-contracts-carry-extraction-instructions.md).
- Docstrings are user-facing: **do not** reference the ADR, this PRD, or task numbers in
  them. That context belongs in the PR description.
- There is no mkdocs page for `submission/` to update — a pre-existing gap, out of scope here.
- **Depends on:** tasks 04, 06.
- **Verification:** `uv run mkdocs serve` renders the handler's API page without warnings;
  `uv run ruff check src/`.
