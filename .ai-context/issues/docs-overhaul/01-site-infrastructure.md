# WP1 — Site infrastructure: GitHub link, edit link, version display

## Context
**Part of PRD:** [docs-overhaul.md](../../prds/docs-overhaul.md) — WP1

Right now the docs header's repository link points back at the docs site instead of
GitHub, "edit this page" targets `main` although PRs go to `dev`, and the site shows no
version anywhere. This task fixes the site configuration only; no page content changes.

## Acceptance Criteria
- [ ] `mkdocs.yml` has `repo_url: https://github.com/sweet-cross/crosscontract`, and the
      header link opens the GitHub repository.
- [ ] `mkdocs.yml` has `edit_uri: edit/dev/docs/`, and "edit this page" opens the file on
      `dev`.
- [ ] The site footer shows `crosscontract v<version>`, where `<version>` is
      `project.version` from `pyproject.toml` at the checked-out ref. Nobody types it by
      hand.
- [ ] The build fails if `pyproject.toml` or its `project.version` key is missing,
      instead of publishing a footer without a version.
- [ ] If `mkdocs.yml` ever sets `copyright`, the hook appends the version to it rather
      than replacing it.
- [ ] `uv run mkdocs build` introduces no new warnings (run only with the user's
      go-ahead).

## Implementation Details
- **Create `scripts/set_docs_version.py`:** an MkDocs hook with a single `on_config(config, **kwargs)`
  function. It:
  - reads `pyproject.toml` with `tomllib` (stdlib), which avoids importing the package;
  - sets `config["copyright"]` to `crosscontract v<version>`, appending to any existing
    value;
  - lets a missing file or key fail loudly with the natural `FileNotFoundError` or
    `KeyError`, with no added defensive branch.
- **Modify `mkdocs.yml`:** change `repo_url` and `edit_uri`, and add
  `scripts/set_docs_version.py` under `hooks:` next to `scripts/copy_notebooks_to_docs.py`.
- Known and accepted: Material's repository widget shows the latest *GitHub release*,
  fetched client-side. Releases are cut on `dev`, so the widget can be ahead of the
  deployed docs. The footer is the authoritative version. Do not add a theme override to
  hide the widget's version.
- The widget may show no version or stars when GitHub's unauthenticated rate limit is hit.
  This needs no handling.
- Verify manually with `uv run mkdocs serve` (with permission): check the header link,
  the edit link, and the footer text. Check the failure path once by temporarily
  pointing the hook at a missing key. Do not commit a pytest for the hook; it is build
  tooling, not package code.
- Dependencies: none. Branch off `dev`; PR title `docs: ...`.
