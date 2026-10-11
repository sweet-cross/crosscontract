# WP1 — Restructure into `excel_processing/`

## Context
**Part of issue:** [sweet-cross/crosscontract#112](https://github.com/sweet-cross/crosscontract/issues/112) — WP1

The Excel reader belongs next to the spec models it carries out, the same way `release/`
keeps its specs and the code that executes them together. This task turns the single
`excel_processor.py` module into a package with room for the reader. It changes no
behaviour.

## Acceptance Criteria
- [ ] `src/crosscontract/submission/excel_processing/` exists with `__init__.py`,
      `specs.py` and `processing.py`.
- [ ] `specs.py` holds `WideLayout`, `ExcelSheet` and `ExcelProcessor`, moved unchanged
      from `excel_processor.py`. `excel_processor.py` is deleted.
- [ ] `processing.py` exists but is empty apart from a module docstring (the reader is
      WP3).
- [ ] `excel_processing/__init__.py` re-exports the three spec models.
- [ ] `submission_contract.py` imports `ExcelProcessor` from `.excel_processing`.
- [ ] The spec tests move to `src/tests/submission/excel_processing/test_specs.py`
      (with an `__init__.py` in that folder, matching the existing test packages), and
      their imports are updated. `test_submission_contract.py` imports `WideLayout`
      from the new location.
- [ ] The `submission/` section in `.claude/CLAUDE.md` describes
      `excel_processing/` (`specs.py` for the declaration, `processing.py` for the
      reader) instead of `excel_processor.py`.
- [ ] The existing test suite passes unchanged.

## Implementation Details
- Move: `src/crosscontract/submission/excel_processor.py` →
  `src/crosscontract/submission/excel_processing/specs.py` (use `git mv` to keep
  history).
- Move: `src/tests/submission/test_excel_processor.py` →
  `src/tests/submission/excel_processing/test_specs.py`.
- Modify: `src/crosscontract/submission/submission_contract.py`,
  `src/tests/submission/test_submission_contract.py`, `.claude/CLAUDE.md`.
- Do not re-export anything from `processing.py` in this task. WP3 adds that export.
- Dependencies: none.
