# Documentation overhaul PRD

Status: **draft**. Written 2026-09-25 from a page-by-page audit of `docs/`, `mkdocs.yml`,
the tutorial notebooks, and `CONTRIBUTING.md` against the code on `main` (v0.23.0) and
`dev` (v0.24.0).

## 1. Overview

The documentation site at <https://sweet-cross.github.io/crosscontract/> has fallen
behind the package. Some pages are wrong: the header link loops back to the docs instead
of GitHub, one import example fails, and a few field constraints are listed incorrectly.
Some are out of date: the tutorials predate the validation changes of v0.22–v0.24. And
parts of the public API have no page at all: submission, transformations, and the client
exceptions.

The work is for three readers:

- **Data consumers**, who use the Registry and the release layer.
- **Data providers**, who author contracts, validate data, and submit it.
- **Contributors**, who need the branching and release flow.

The overhaul is split into **six work packages (WPs)**. Each WP is a separate PR into
`dev` and can land on its own. The order is:

1. Technical fixes to the site itself.
2. Existing content, fixed topic by topic.
3. Release docs.
4. Submission docs, deferred until the submission feature is finished.

| WP | Topic | Depends on | Audit items |
|---|---|---|---|
| WP1 | Site infrastructure: GitHub link, edit link, version display | — | 1, 2, 3 |
| WP2 | Landing page and contributing | — | 9–13, 27, 28 |
| WP3 | Contracts: overview, metadata, schema, contract types, validation, contract tutorial, contracts reference | — | 4–8, 14, 16–18, 23, 29, 30 |
| WP4 | Client and Registry: client tutorial, registry overview, client reference | — | 19, 22, 24 |
| WP5 | Release: own nav section, fetch/aggregation reference | — | 21 (fetch part), 25 |
| WP6 | Submission: new section, contract-type entry, transformation reference | Submission feature complete | 15, 20, 21 (transformation part) |

Item numbers refer to the audit table in the session that produced this PRD. Every item
is restated in its WP below, so this document stands on its own.

**Out of scope:** a changelog page (#26). `CHANGELOG.md` embeds whole PR bodies,
including their own `#` headings, and rendered as a docs page it would swamp the table of
contents. WP2 links to the file on GitHub instead. A curated changelog page can be its
own item later.

## 2. Core Requirements

### Cross-cutting (all WPs)

- Each WP branches off `dev` and is squash-merged back with a `docs:` PR title, so it
  produces no version bump. Docs reach the live site only when `dev` is fast-forwarded
  into `main`.
- Every Python snippet on a page runs as written against the version the WP targets.
- No page links to a file that does not exist.
- Prose follows the docstring rules in `.claude/CLAUDE.md`: say what the thing does and
  what the reader must do, not why it was built that way. No ADR or issue references on
  user-facing pages.
- Where a docstring is rendered by an API reference page, a wrong docstring counts as a
  wrong page and is fixed in the WP that owns that reference page.

### WP1 — Site infrastructure

Done when:

1. The header repository link opens `https://github.com/sweet-cross/crosscontract`
   (`repo_url` currently points at the docs site itself).
2. The "edit this page" link opens the file on `dev`, the branch PRs target
   (`edit_uri: edit/dev/docs/`).
3. The site footer shows the package version the docs were built from, e.g.
   `crosscontract v0.23.0`. The version is read at build time and never typed in by hand.

### WP2 — Landing page and contributing

Done when:

1. `docs/index.md` introduces the components that currently have pages: CrossContract,
   CrossRegistry, CrossClient, and Release. The old "two main components" sentence, which
   listed three, is gone. Submission is added by WP6.
2. The installation section says the package comes from PyPI (not "hosted directly on
   GitHub"), links the PyPI page, and fixes `uv pip crosscontract` → `uv pip install
   crosscontract`.
3. The dependency list names pandas, pandera, pydantic, pyarrow, SQLAlchemy, and httpx,
   and describes httpx as synchronous only.
4. "Quick Links" point to the rendered tutorial pages instead of raw `.ipynb` files on
   GitHub, and include a link to `CHANGELOG.md` on GitHub.
5. `docs/contributing.md` gets a short "Local development" section listing the setup,
   test, lint, format, and docs commands, instead of sending readers to
   `.claude/CLAUDE.md`. The same change goes into the root `CONTRIBUTING.md`, as that
   file's sync comment requires.
6. Both contributing files note that while the version is below 1.0, a breaking change
   bumps the **minor** version (`major_on_zero = false`).

### WP3 — Contracts

Done when:

1. **`contracts/index.md`**:
   - The broken link `(see contracts/custom_metadata.md)` points to
     `metadata.md#custom-metadata`.
   - The numbered list reads 1, 2 (it currently jumps from 1 to 3).
   - Typos are fixed ("is build", "contact" for "contract", "this packages").
   - `gdp_example.yaml` is linked as the example for `CrossContract.from_file`.
2. **`contracts/metadata.md`**:
   - `DataSource` is renamed to `Source` in the attribute table, the heading text, and
     the import example.
   - The empty-list bullet says only `contributors` and `licenses` turn `[]` into `None`;
     an empty `sources` list is kept.
   - The forward-looking sentence about a DCAT adapter is removed.
3. **`contracts/schema.md`** grows from a field table into a schema page that covers:
   - The field table, corrected: `DateTimeField` has `minimum`/`maximum` only (no
     `enum`), and every field supports `required` and `unique`.
   - `primaryKey` (single or composite).
   - `foreignKeys`: references to other contracts, and self-references.
   - `fieldDescriptors`: value descriptors with a `unit`, time descriptors with a
     `frequency`, and location descriptors with a `locationType`.
4. **Validation section** (in `schema.md`, or a new `contracts/validation.md` if it grows
   past one screen). It covers:
   - `contract.validate_data` versus `tableschema.validate_dataframe`, and when to use
     which.
   - The primary key is always checked within the data.
   - The `check_existing_primary_key`, `check_existing_foreign_key`, and
     `check_dimension_granularity` flags, and that setting any of them requires a
     `resolver`.
   - `validate_references`.
   - How to read a `SchemaValidationError`: `to_list`, `to_pandas`, and `max_errors`
     (v0.24.0, on `dev`).
5. **`contracts/contract_types.md`**: typos fixed ("The however,", "The start nature" →
   "star"), and *FlexibleDimension* described on its own instead of folded into the
   *Dimension* bullet.
6. **Contract tutorial notebook** (`notebooks/contract_tutorial.ipynb`):
   - Stops claiming a valid frame gives "an empty response"; `validate_dataframe` returns
     the DataFrame.
   - Shows `gdp_contract.validate_data(df)` as the contract-level entry point.
   - The markdown cells still describe the outputs correctly.
7. **`reference/contracts.md`** adds `ContractResolver` and the field-descriptor models.
8. **Docstrings rendered on the contracts reference page**:
   - `BaseContract` and `CrossContract` describe the `name` rule as it is enforced
     (lowercase letters, digits, `.`, `_`, `-`; at most 100 characters).
   - The `BaseContract` example comment refers to `tableschema`, not `schema`.
   - `CrossContract`'s summary no longer describes itself as "adding tagging
     capabilities".
9. **ADR 0002** refers to `Source`, not `DataSource`. This is a name correction only;
   the decision itself is unchanged.

### WP4 — Client and Registry

Done when:

1. **Client tutorial notebook** (`notebooks/client_tutorial.ipynb`):
   - Uses `change_status("Retired")`, matching `ContractStatus`.
   - Drops the reference to a context manager that the notebook never uses.
   - The local-versus-remote validity section shows that
     `ContractResource.validate_dataframe` can check against stored values with
     `check_existing_primary_key` and `check_existing_foreign_key`.
2. **`registry/index.md`** becomes a real overview:
   - Constructing the registry, from credentials or from a `CrossClient`.
   - Getting a variable: `add_variable`, attribute access, item access.
   - `contract_overview`.
   - `.data` versus `get_data`.
   - `get_data` options: `filters`; the three forms of `aggregation` (a level, a list of
     target ids, and `{"level": ..., "keep": [...]}`); `use_titles`; `columns`.
   - Inspecting a variable's `dimensions`.
   - The tutorial stays the worked example; the overview links to it.
3. **`reference/client.md`** adds the `crosscontract.crossclient.exceptions` classes the
   tutorial relies on: `CrossClientError`, `ValidationError`, `ConflictError`,
   `PermissionDeniedError`, `ResourceNotFoundError`, `AuthenticationError`.

### WP5 — Release

Done when:

1. Release has its own top-level nav entry ("Release": Overview, plus the reference page
   under API Reference) instead of sitting under CrossRegistry.
2. The fetch and aggregation models that a release spec's `data_instructions.fetch`
   accepts (`FetchSpecMixin`, `AggregationSpec`, `LevelKeepSpec`, `ColumnAggregation`)
   are rendered in the API reference. `release/index.md` links to them where it now says
   "see the registry tutorial".
3. `release/index.md` is re-checked against `create_data_package` on `dev`. Every YAML
   key in its example is still accepted, and the "taken from the contract vs. the
   specification" table still matches what `build_data_resource` does.

### WP6 — Submission (deferred)

Start only once the submission feature is settled. That means at least:
`CrossSubmitter.submit` no longer being a stub, and the extraction format no longer
changing between PRs.

Done when:

1. A new top-level "Submission" section exists (`docs/submission/index.md`), written for
   data providers. It covers:
   - What a submission bundle and a `SubmissionContract` are.
   - The `extraction` block: routing column, transformation profiles, and targets.
   - Checking a bundle offline with `SubmissionHandler`: target extraction,
     `validate_target`/`validate_targets`, and `unclaimed_rows`.
   - Checking it against the platform with `CrossSubmitter.validate_submission`, and
     later submitting it.
   - The errors a provider meets: `TargetValidationError` and `UnclaimedRowsError`.
2. `contracts/contract_types.md` gets a *Submission contracts* section with the rules
   specific to that type:
   - The `tableschema` declares neither `primaryKey` nor `foreignKeys`.
   - `project_name` and `extraction` are required.
   - The routing column must be a required string field.
3. `docs/reference/submission.md` renders `SubmissionContract`, `SubmissionHandler`,
   `CrossSubmitter`, the extraction models, and the two exceptions.
4. The column transformations (`CastColumn`, `DropColumns`, `DropRowsByValue`,
   `MapColumnValues`, `ParseDatetimeColumn`, `RenameColumns`) are rendered in the API
   reference.
5. `docs/index.md` lists Submission as a component.

## 3. Edge Cases & Error Handling

- **Two version numbers in the header and footer.** Once `repo_url` points at GitHub,
  Material's repository widget shows the *latest GitHub release*, fetched client-side.
  Releases are cut on `dev`, so the widget can show a version not yet on `main` or PyPI
  (today: v0.24.0 against a deployed v0.23.0). The footer version from WP1 is the
  authoritative one, which is why WP1 requires it. The widget is accepted as it is;
  hiding its version needs a theme template override, which is more machinery than the
  mismatch is worth.
- **GitHub API rate limit.** The widget calls the GitHub API unauthenticated from the
  reader's browser (60 requests per hour per IP). If the limit is hit, the widget shows
  the repository name without version or stars. Nothing breaks, and the footer is
  unaffected.
- **Version source unavailable at build time.** The hook reads `pyproject.toml`, which
  is always present in a checkout, so it doesn't depend on the package being installed.
  If the file or key is missing, the build must fail loudly rather than publish a footer
  without a version.
- **Existing `copyright` value.** `mkdocs.yml` sets no `copyright` today. If one is
  added later, the hook must append the version to it, not overwrite it.
- **Docs deploy at a tag, not at `main`'s tip.** `deploy_docs.yml` accepts a `ref`; the
  hook reads `pyproject.toml` at whatever ref was checked out, so the footer matches the
  deployed code by construction.
- **Notebooks that need credentials.** The client and registry tutorials talk to the
  live platform and have `execute: false`. Their stored outputs cannot be refreshed in
  CI. WP4 re-runs them by hand with a platform account and commits the outputs, or, if
  no account is at hand, edits only the markdown and code cells and says so in the PR.
- **Notebook source of truth.** The build hook copies `notebooks/*.ipynb` into
  `docs/notebooks/`, which is gitignored. Edits go to `notebooks/`, never to the copy.
- **Merge conflicts in `mkdocs.yml`.** WP1, WP5, and WP6 all touch `mkdocs.yml` (config
  and nav). The conflicts are textual and small; whichever WP lands second rebases.
- **WP2 and WP6 both edit the component list in `index.md`.** WP2 writes the list
  without Submission; WP6 adds it. WP2 must not link to a Submission page that doesn't
  exist yet.
- **Content written against `dev` features.** WP3's validation section documents
  `max_errors`, which is on `dev` (v0.24.0) but not on `main`. That is fine because docs
  deploy with the `dev` → `main` promotion, but it rules out cherry-picking WP3 onto
  `main` by itself.
- **Mkdocstrings targets that move.** Reference pages address modules by dotted path. A
  rename in `src/` breaks the build. Prefer the public re-export (e.g.
  `crosscontract.release.create_data_package`) over the private module path where one
  exists.
- **Duplicate autodoc.** Rendering a module *and* a class re-exported from it on the same
  page duplicates headings and anchors. Each object is rendered once per page.

## 4. Implementation Decisions & File Paths

### WP1

- **Version in the footer via an MkDocs hook.** A new hook reads `project.version` from
  `pyproject.toml` with `tomllib` (stdlib, Python 3.11+) in `on_config` and sets
  `config["copyright"]` to `crosscontract v<version>`, appending to any existing value.
  Material renders `copyright` in the footer with no template override.
  - Why `tomllib`: it reads the version PSR writes into `pyproject.toml`, the same file
    that decides what PyPI gets, with no import of the package.
  - Why a separate hook file: `copy_notebooks_to_docs.py` is named for one job, so the
    version goes in its own file. This avoids renaming a file other config refers to.
- Files to be created:
  - `scripts/set_docs_version.py`: the hook, a single `on_config` function.
- Files to be modified:
  - `mkdocs.yml`: `repo_url`, `edit_uri`, and the new hook added under `hooks:`.

### WP2

- Files to be modified: `docs/index.md`, `docs/contributing.md`, `CONTRIBUTING.md`.

### WP3

- Files to be modified:
  - `docs/contracts/index.md`
  - `docs/contracts/metadata.md`
  - `docs/contracts/schema.md`
  - `docs/contracts/contract_types.md`
  - `docs/reference/contracts.md`
  - `notebooks/contract_tutorial.ipynb`
  - `src/crosscontract/contracts/contracts/base_contract.py` (docstrings only)
  - `src/crosscontract/contracts/contracts/cross_contract.py` (docstrings only)
  - `.ai-context/adrs/0002-metadata-follows-frictionless-with-deviations.md`
  - `mkdocs.yml`, only if the validation section becomes its own page.
- Files possibly created: `docs/contracts/validation.md`, only if the section outgrows
  `schema.md`.

### WP4

- Files to be modified:
  - `docs/registry/index.md`
  - `docs/reference/client.md`
  - `notebooks/client_tutorial.ipynb`

### WP5

- Files to be modified:
  - `mkdocs.yml` (nav)
  - `docs/release/index.md`
  - `docs/reference/release.md` (adds the fetch and aggregation models, or links to a
    new page for them)
- Files possibly created: `docs/reference/transformations.md`. WP5 creates it with the
  fetch and aggregation models; WP6 adds the column transformations to the same page.

### WP6

- Files to be created:
  - `docs/submission/index.md`
  - `docs/reference/submission.md`
- Files to be modified:
  - `mkdocs.yml` (nav)
  - `docs/contracts/contract_types.md`
  - `docs/index.md`
  - `docs/reference/transformations.md`

## 5. Data & Schema Changes

None. No pydantic model, field, or runtime behaviour changes. The only code touched is:

- The new build-time hook `scripts/set_docs_version.py`, which is not part of the
  package.
- Docstring text in two contract modules (WP3).

## 6. Related ADRs

- **ADR 0002 — metadata follows Frictionless with deviations.** WP3's metadata page
  describes the deviations as they are and does not "fix" them toward strict
  Frictionless. WP3 corrects the ADR's stale `DataSource` class name. It removes the DCAT
  sentence from the user-facing page only; the ADR keeps it as part of the record.
- **ADR 0003 — release is a contract → Frictionless adapter.** WP5 documents
  `create_data_package` and the spec models as the whole public surface, with no
  descriptor classes, matching the ADR.
- **ADR 0004 — submission contracts carry extraction instructions; ADR 0007 — the
  Submitter mirrors the Registry.** WP6 presents `SubmissionContract` + `extraction`
  as one authored YAML, and `CrossSubmitter` as the provider entry point next to
  `CrossRegistry`. Deferring WP6 follows from these still moving.
- **ADR 0005 — one contract resolver; ADR 0006 — validation is a set of check objects.**
  WP3's validation section uses their terms (resolver, existing values, opt-in key
  checks) as defined in `CONTEXT.md`.
- **ADR 0001 — dimensions are strict trees; ADR 0008 — a ValueVariable is keys plus
  measures; ADR 0009 — one granularity per group.** WP3's contract-types and validation
  text states these rules (the `other` entries, keys plus numeric measures,
  `check_dimension_granularity`) without restating their rationale.

## 7. Testing Strategy

Per `.claude/CLAUDE.md`, none of the commands below runs without the user's go-ahead in
the session.

- **Site build, every WP:** `uv run mkdocs build` from `uv sync --group docs`. The WP
  introduces no new warnings. It removes the warnings it owns: after WP3, the
  `custom_metadata.md` warning is gone.
- **WP1 by inspection** after `uv run mkdocs serve`:
  - The header link opens the GitHub repository.
  - "Edit this page" opens `edit/dev/docs/...`.
  - The footer shows the version from `pyproject.toml`.
- **WP1 failure path:** temporarily pointing the hook at a missing key fails the build.
  This is a one-off manual check, not a committed test; the hook is build tooling, not
  package code, so it gets no pytest.
- **Snippets, WP3/WP4/WP5:** every Python block on a touched page is run once in
  `uv run python` against the target version. The metadata imports in particular must
  run (`from crosscontract.contracts.contracts.metadata_models import Contributor,
  Source, License`). These are not turned into doctests; the site has too few snippets
  to justify the machinery.
- **Notebooks:**
  - The contract tutorial runs offline and is re-executed with outputs committed.
  - The client and registry tutorials follow the credentials rule in §3.
- **Docstring edits (WP3):** docstring text changes only, so the existing test suite is
  the regression check, run with permission.
- **Follow-up, not in this PRD:** once WP2–WP5 have cleared the existing warnings,
  switching CI to `mkdocs build --strict` stops broken links from coming back. It is
  listed here because the idea comes out of this work; decide after WP5.
