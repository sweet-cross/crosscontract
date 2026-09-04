# WP4 — Public surface and documentation

## Context

**Part of PRD:** [2026-09-02-cross-submitter.md](../../prds/2026-09-02-cross-submitter.md)

`CrossSubmitter` is a top-level entry point for a whole role — the **Data provider** —
so it belongs beside `CrossRegistry` and `CrossClient` in the package's public surface,
not buried in a submodule. This package exports it, and records in prose the one
structural property the code no longer enforces: `SubmissionHandler` stays offline.

Depends on **WP1**, **WP2** and **WP3**.

## Acceptance Criteria

- [X] `src/crosscontract/submission/__init__.py` exports `CrossSubmitter` and
  `UnclaimedRowsError`, both added to `__all__`.
- [X] `src/crosscontract/__init__.py` re-exports both, both added to `__all__`.
- [X] `from crosscontract import CrossSubmitter, UnclaimedRowsError` works, covered by a
  test in `src/tests/submission/test_submitter.py`.
- [ ] The `submission/__init__.py` module docstring notes that the package now contains
  both the offline concepts and the one connected class, and why
  ([ADR 0007](../../adrs/0007-the-submitter-is-the-provider-side-mirror-of-the-registry.md)).
- [ ] `SubmissionHandler`'s class docstring
  (`src/crosscontract/submission/submission_handler.py`) states that it remains
  offline and that `CrossSubmitter` is the connected composition. **Docstring only —
  no behavioural change.**
- [ ] A usage page exists under `docs/` *if* the docs tree covers `CrossRegistry`
  equivalently — check first; not a blocker if there is no comparable page.

## Implementation Details

**Modify:** `src/crosscontract/submission/__init__.py`
**Modify:** `src/crosscontract/__init__.py`
**Modify:** `src/crosscontract/submission/submission_handler.py` *(docstring only)*
**Modify:** `src/tests/submission/test_submitter.py`
**Possibly create:** a `docs/` page mirroring the registry's

- Import order in `crosscontract/__init__.py` already loads `.crossclient` before
  `.submission`, so no cycle arises. Verified during design; if an `ImportError` appears
  here, something in WP2/WP3 imported the client layer at an unexpected point — fix that,
  do not reorder `__init__.py`.
- Any docs page should show the one-call path and be explicit that a client-side
  validation is **advisory** — the platform re-validates on ingest (ADR 0005) — and that
  `submit` is not yet available.
- Per CLAUDE.md, do not run `pytest` / `ruff` / `mypy` on your own initiative — ask first.
