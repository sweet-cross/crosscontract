# WP2 — Add `python-calamine` as a core dependency

## Context
**Part of issue:** [sweet-cross/crosscontract#112](https://github.com/sweet-cross/crosscontract/issues/112) — WP2

The reader parses workbooks with pandas' `calamine` engine. Calamine is a fast,
read-only Rust reader, which matters for `cross_back` parsing uploads inside a request.
It is a **core** dependency, not an extra. The issue's acceptance criterion for an
optional `crosscontract[excel]` extra was dropped: a core dependency means users never
have to install anything extra, and the reader needs no import guard. Calamine cannot
write workbooks, so the tests need `openpyxl` to build fixtures.

## Acceptance Criteria
- [ ] `python-calamine` is listed in `[project] dependencies` in `pyproject.toml`.
- [ ] `openpyxl` is listed in the `test` dependency group only.
- [ ] `uv.lock` is updated, and `uv sync --group dev` installs both.

## Implementation Details
- Modify: `pyproject.toml` and `uv.lock`, via `uv add python-calamine` and
  `uv add --group test openpyxl`.
- No `[project.optional-dependencies]` section is added.
- Dependencies: none (can run in parallel with WP1).
