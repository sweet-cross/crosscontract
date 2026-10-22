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
- [ ] The dependency list names pandas, pandera, pydantic, pyarrow, and httpx,
      and describes httpx as synchronous only.
- [ ] "Quick Links" point to the rendered tutorial pages (`notebooks/*.ipynb` within the
      site) instead of the raw notebooks on GitHub, and include a link to `CHANGELOG.md` on
      GitHub.
- [x] `docs/contributing.md` has a "Local development" section listing the setup
      (`uv sync --group dev`), test, lint, format, and docs (`uv sync --group docs`,
      `uv run mkdocs serve`) commands. It no longer points to `CLAUDE.md`.
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
- Take the command list from the "Commands" section of `CLAUDE.md`, but keep it
  short. Contributors need the commands, not the AI-specific rules.
- The component list is edited again in WP6 to add Submission. Keep it a plain bullet
  list so that edit is a one-line addition.
- No changelog page is created (out of scope per the PRD); the GitHub link is the
  replacement.
- **Note — package layout (added 2026-10-22, #137).** Supersedes the 2026-10-12 note
  below. Present the package by role:

  - **`contracts/`: specs.** Declarative, authored as YAML: the contracts and their
    schemas, and the specs for submission, release, reading (`readers/`) and fetching
    (`fetching/`).
  - **`handlers/`: execution based on specs.** Runs specs offline: the file readers and
    the `SubmissionHandler`.
  - **`crossclient/`: low-level API access.** `CrossClient` and its per-endpoint services
    and resources.
  - **`services/`: high-level API interaction.** The role entry points `CrossReader`,
    `CrossSubmitter` and `create_data_package`, built on a `CrossClient`.
  - **`transformations/`: self-running DataFrame operations.** Each is a spec that runs
    itself (`apply`), schema-agnostic. Specs in `contracts/` compose them, and
    `handlers/` runs them.

  Keep the component list a plain bullet list; the layout can be a short paragraph
  before it.
- **Note — package architecture (added 2026-10-12; superseded by the note above).**
  Present the components as three layers rather than a flat list:
  - **Specs and offline logic**: `contracts/` (including the submission specs under
    `contracts/submission/`) and `transformations/`. These run without a platform
    connection.
  - **Client services and resources**: `CrossClient` with `client.contracts`
    (`ContractService` → `ContractResource`) and `client.submissions`
    (`SubmissionService` → `SubmissionContractResource`). This layer talks to the
    endpoints and is what managers and admins use.
  - **High-level role wrappers**: `CrossRegistry` (data consumer) and `CrossSubmitter`
    (data provider), each built on one `CrossClient`.

  The client and submitter parts land with #120–#122. Describe only what exists on `dev`
  when this task is done, and extend it in WP6 if submission isn't there yet. Keep the
  component list a plain bullet list (see above); the layering can be a short paragraph
  before it.
- Dependencies: none. Can land before or after WP1, WP3, WP4, and WP5. Branch off `dev`;
  PR title `docs: ...`.
