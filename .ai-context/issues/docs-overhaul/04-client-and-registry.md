# WP4 — Client and Registry: tutorial, registry overview, client reference

## Context
**Part of PRD:** [docs-overhaul.md](../../prds/docs-overhaul.md) — WP4

The client tutorial has a wrong status value and a stale reference to a context manager,
and it doesn't show the validation flags. The registry overview is five lines long. The
client reference leaves out the exceptions the tutorial catches. This task brings the
platform-access docs up to date.

## Acceptance Criteria

**Client tutorial (`notebooks/client_tutorial.ipynb`)**
- [ ] Uses `change_status("Retired")` (capitalised, matching `ContractStatus`).
- [ ] Drops the sentence referring to a context manager "noted above" that the notebook
      never uses.
- [ ] The local-versus-remote validity section shows that
      `ContractResource.validate_dataframe(..., check_existing_primary_key=True)` (and
      `check_existing_foreign_key`) checks against stored values before upload.

**`docs/registry/index.md`**
- [ ] Constructing a `CrossRegistry` from credentials or from an existing `CrossClient`.
- [ ] Getting a variable with `add_variable`, attribute access (`registry.name`), and item
      access (`registry["name"]`).
- [ ] `contract_overview`.
- [ ] `.data` versus `get_data`.
- [ ] `get_data` options: `filters`; the three forms of `aggregation` (a level, a list of
      target ids, and `{"level": ..., "keep": [...]}`); `use_titles`; `columns`.
- [ ] Inspecting a variable's `dimensions`.
- [ ] Links to the registry tutorial as the worked example.

**`docs/reference/client.md`**
- [ ] Renders `CrossClientError`, `ValidationError`, `ConflictError`,
      `PermissionDeniedError`, `ResourceNotFoundError`, and `AuthenticationError` from
      `crosscontract.crossclient.exceptions`, each once.

**Checks**
- [ ] Every Python snippet on `registry/index.md` matches the current signatures in
      `registry/registry.py` and `registry/variables/data_variable.py`.
- [ ] `uv run mkdocs build` introduces no new warnings (run only with the user's
      go-ahead).

## Implementation Details
- Files to modify:
  - `docs/registry/index.md`
  - `docs/reference/client.md`
  - `notebooks/client_tutorial.ipynb` (edit the source in `notebooks/`, never the
    gitignored copy in `docs/notebooks/`)
- **Notebook outputs:** the client and registry tutorials need live-platform credentials
  and are built with `execute: false`. Re-run the client tutorial by hand with a platform
  account and commit its outputs. If no account is available, change only markdown and
  code cells, leave the outputs, and say so in the PR description.
- The registry overview summarises; the tutorial demonstrates. Don't copy the tutorial's
  cells into the page.
- Sources of truth:
  - `CrossRegistry.__init__`, `add_variable`, `get_variable`, and `contract_overview` in
    `registry/registry.py`.
  - `CrossDataVariable.get_data` in `registry/variables/data_variable.py`.
  - `ContractResource.validate_dataframe` in `crossclient/services/contract_resource.py`.
  - `crossclient/exceptions/exceptions.py`.
- Dependencies: none. Branch off `dev`; PR title `docs: ...`.
