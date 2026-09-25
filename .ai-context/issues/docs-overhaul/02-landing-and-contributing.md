# WP2 — Landing page and contributing

## Context
**Part of PRD:** [docs-overhaul.md](../../prds/docs-overhaul.md) — WP2

The landing page describes an older package: a wrong component count, an install claim
that the package comes from GitHub, a broken `uv` command, and an incomplete dependency
list. The contributing pages send readers to an AI-assistant instructions file for local
setup. This task brings the entry pages up to date.

## Acceptance Criteria
- [ ] `docs/index.md` introduces the components that currently have pages: CrossContract,
      CrossRegistry, CrossClient, and Release. The "two main components" sentence is gone.
      **Submission is not listed and not linked** (that is WP6).
- [ ] The installation section says the package is installed from PyPI (not "hosted
      directly on GitHub") and links the PyPI page.
- [ ] `uv pip crosscontract` is corrected to `uv pip install crosscontract`.
- [ ] The dependency list names pandas, pandera, pydantic, pyarrow, SQLAlchemy, and httpx,
      and describes httpx as synchronous only.
- [ ] "Quick Links" point to the rendered tutorial pages (`notebooks/*.ipynb` within the
      site) instead of the raw notebooks on GitHub, and include a link to `CHANGELOG.md` on
      GitHub.
- [ ] `docs/contributing.md` has a "Local development" section listing the setup
      (`uv sync --group dev`), test, lint, format, and docs (`uv sync --group docs`,
      `uv run mkdocs serve`) commands. It no longer points to `.claude/CLAUDE.md`.
- [ ] Both contributing files note that while the version is below 1.0, a breaking change
      (`feat!:` / `BREAKING CHANGE:`) bumps the **minor** version, because of
      `major_on_zero = false`.
- [ ] The root `CONTRIBUTING.md` receives the same two changes, as its sync comment
      requires. The only intended difference between the two files stays the link style
      (relative vs. absolute GitHub URLs).
- [ ] `uv run mkdocs build` introduces no new warnings (run only with the user's
      go-ahead).

## Implementation Details
- Files to modify:
  - `docs/index.md`
  - `docs/contributing.md`
  - `CONTRIBUTING.md`
- Take the command list from the "Commands" section of `.claude/CLAUDE.md`, but keep it
  short. Contributors need the commands, not the AI-specific rules.
- The component list is edited again in WP6 to add Submission. Keep it a plain bullet
  list so that edit is a one-line addition.
- No changelog page is created (out of scope per the PRD); the GitHub link is the
  replacement.
- Dependencies: none. Can land before or after WP1, WP3, WP4, and WP5. Branch off `dev`;
  PR title `docs: ...`.
