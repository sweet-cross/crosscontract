# WP1 — `UnclaimedRowsError`

## Context
**Part of PRD:** [2026-09-02-cross-submitter.md](../../prds/2026-09-02-cross-submitter.md)

Step 2 of a **Submission validation** raises when a delivered bundle contains rows no
**Target** claims. Because `submit` will upload the raw bundle and the platform re-runs
extraction on it, an unclaimed row is silent data loss on the server — so it must abort
the run and hand the caller the rows themselves, not a count. This work package adds the
exception on its own so the rest of the feature can be written against a settled type.

Standalone: it depends on nothing and blocks WP3.

## Acceptance Criteria
- [ ] `UnclaimedRowsError` exists in `src/crosscontract/submission/exceptions.py`, beside
      `TargetValidationError`.
- [ ] It carries the unclaimed rows as a `pd.DataFrame` attribute — the frame, not a
      count, not a formatted string.
- [ ] Its message states the number of unclaimed rows and points the reader at the
      attribute holding them.
- [ ] Tests in `src/tests/submission/test_exceptions.py` (beside the existing
      `TargetValidationError` tests) cover: the frame is reachable and equal to what was
      passed, and the message reports the correct row count.
- [ ] Docstrings follow the Google-style / markdown-only convention in CLAUDE.md.

## Implementation Details

**Modify:** `src/crosscontract/submission/exceptions.py`
**Modify:** `src/tests/submission/test_exceptions.py`

- Mirror the shape of `TargetValidationError`: an exception that carries the data needed
  to act on it, and builds its message from that data. Read that class first and follow
  it rather than inventing a second style in the same file.
- Constructor takes the unclaimed frame. No other parameters — the caller that raises it
  (WP3) has nothing else to add.
- Do **not** export it from `__init__.py` yet; the public surface is WP4.
- Per CLAUDE.md, do not run `pytest` / `ruff` / `mypy` on your own initiative — ask first.
