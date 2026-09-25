# docs: fix repository link and show the package version in the docs footer

## Summary
The docs header's repository link pointed at the docs site itself
(`https://sweet-cross.github.io/crosscontract`), so clicking it just reloaded the docs.
The site also showed no version anywhere. This branch fixes the link and shows the
version the docs were built from in the footer. It also fixes a docstring that produced
the only warning in the docs build.

This is WP1 of a staged docs overhaul. The branch also adds the PRD and the task files
for the remaining work packages.

## Changes
- **Repository link:** `repo_url` in `mkdocs.yml` now points to
  `https://github.com/sweet-cross/crosscontract`.
- **Edit link target:** `edit_uri` now targets `dev` instead of `main`. The theme's edit
  button stays **off**, so readers see no change. The setting only matters if the button
  is turned on later, and then edits land on `dev`, which PRs target.
- **Version in the footer:** the new MkDocs hook `scripts/set_docs_version.py` reads
  `project.version` from `pyproject.toml` with `tomllib` at build time. It sets
  `copyright`, which Material renders in the footer as e.g. `crosscontract v0.24.0`. If a
  `copyright` is ever configured in `mkdocs.yml`, the version is appended to it instead
  of replacing it. A missing `pyproject.toml` or `project.version` fails the build.
- **Docstring fix:** in the `TableSchema.validate_dataframe` docstring, the type of
  `foreign_key_values` was wrapped over two lines. griffe could not parse the entry, which
  caused a build warning and dropped the argument from the rendered API reference. The
  type now fits on one line as `dict[tuple[str, ...], list[tuple]] | None`, which keeps
  it within the 88-character limit. Only the docstring changed; no code did.
- **Planning files:**
  - `.ai-context/prds/docs-overhaul.md`: the PRD for the docs overhaul, covering WP1–WP6.
  - `.ai-context/issues/docs-overhaul/02–06`: one task file per remaining work package.
    WP1's task file was removed, because this branch implements it.

## Testing
- `uv run mkdocs build` finishes with no warnings. Before this change it showed the one
  griffe warning described above.
- Checked the built HTML:
  - The header links to `https://github.com/sweet-cross/crosscontract`.
  - The footer reads `crosscontract v0.24.0`.
- Not checked:
  - The build failing when the version is missing.
  - The served site itself, including the repository widget.
- No ruff, mypy, or pytest run.

## Notes for reviewer
- **Two version numbers can appear.** Now that `repo_url` points at GitHub, Material's
  repository widget in the header shows the latest *GitHub release*, fetched in the
  reader's browser. Releases are cut on `dev`, so the widget can be ahead of the deployed
  docs, which are built from `main`. The footer is the authoritative version: it is read
  from the checked-out ref at build time. The PRD accepts the widget as it is rather than
  hiding its version with a theme override.
- **`uv.lock` is stale on `dev`.** It still records `crosscontract` as 0.23.0. Running
  `uv sync` or `uv run` rewrites it to 0.24.0. Those rewrites were deliberately kept out
  of this PR.
