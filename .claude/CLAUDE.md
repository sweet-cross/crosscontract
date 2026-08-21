# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

The project uses `uv` for package management and Python 3.11+.

```bash
# Install dependencies (including dev group)
uv sync --group dev

# Run all tests
uv run pytest

# Run a single test file
uv run pytest src/tests/contracts/schema/test_schema.py

# Run a single test by name
uv run pytest src/tests/contracts/schema/test_schema.py::test_name

# Lint (check only)
uv run ruff check src/

# Lint with auto-fix
uv run ruff check --fix src/

# Format
uv run ruff format src/

# Type-check
uv run mypy src/crosscontract/

# Run coverage
uv run coverage run -m pytest && uv run coverage report

# Build docs (requires docs group)
uv run mkdocs serve
```

Pre-commit hooks run `ruff check` (F401 + isort) and `ruff-format` on commit.

### Do not run validation automatically

Do **not** run tests, linting, type-checking, coverage, or any other validation
command (`pytest`, `ruff`, `mypy`, `coverage`, etc.) on your own initiative. After
making changes, stop and **ask for permission** before running any of them. Only run
a validation command when the user has explicitly asked for it or granted permission
in the current exchange.

### Implement only what was asked, as simply as possible

When handed a scoped change, implement **exactly** that change and nothing adjacent.
Acceptance criteria in a task or PRD file you happened to read, and findings from your
own earlier review, are **not** authorization — they stay open until handed over
separately. State the requested change in one line before editing, and let only that
line justify each edit; everything else you noticed goes in the reply as a note, never
into the code. If a fix seems to require adjacent work, say so and ask rather than
bundling it in.

Prefer the simplest implementation that satisfies the request. Do not add helper
functions, module constants, curated error messages, or defensive branches unless the
change cannot be expressed without them — a one-line change should land as a one-line
change. The house style is deliberately plain (pure function plus thin pydantic model,
`apply()` a single delegating call); match it. If you think an abstraction is
warranted, propose it and let the user decide.

## Branching and releases

- `main` is the public release branch. Pushes to main publish to PyPI (gated by the `pypi` GitHub Environment) and deploy the docs.
- `dev` is the integration branch and the default branch on GitHub. Versioning happens here: every push to dev runs `python-semantic-release`, which bumps the version and creates a `vX.Y.Z` tag based on conventional-commit messages.
- Feature branches **squash-merge** into `dev`. The PR title must be a valid conventional commit (`feat:`, `fix:`, etc.) — it becomes the squash commit message that PSR analyzes. Hotfixes follow the same path.
- `dev` **fast-forwards** into `main`. The version commits and tags created on dev carry over to main as-is. No version bumps happen on the dev → main promotion.

## Deferred work

Out-of-scope, separate-PR follow-ups are collected in
[`.ai-context/TODO.md`](../.ai-context/TODO.md). When you spot work worth doing but
that would bloat the change in front of you, **append it there** (with enough context
to act on it cold) rather than expanding the current PR. Consult this file when
planning a change, and remove an item once its PR lands.

## Architecture

The public surface — `contracts/`, `crossclient/`, and `registry/` — is re-exported from `crosscontract/__init__.py`. `_standards/` is an internal module (not re-exported) holding faithful models of the upstream Frictionless standard.

### `contracts/` — Schema and contract definitions

**`contracts/contracts/`** — The contract classes:
- `BaseContract` (Pydantic model): minimal contract with `name` + `tableschema`. Intended for custom contract definitions outside the CROSS platform. Loads from YAML/JSON via `from_file()`.
- `CrossContract(BaseContract, CrossMetaData)`: the full contract for the CROSS platform, adding `title`, `description`, `tags`, and `contract_type`. The `contract_type` field (`"General"` | `"Dimension"` | `"ValueVariable"` | `"FlexibleDimension"` | `"Submission"`) drives a discriminated union: it is resolved through `CONTRACT_TYPE_TO_TABLE_TYPE` and the resulting `table_type` is injected into the `tableschema` dict before validation, so callers never set `table_type` manually.
- `CrossContract.from_server()` / `to_server()`: strip/restore the `tableschema` for `Dimension` contracts because the server owns that schema.
- `ContractResolver` protocol: used to look up contracts by name during `validate_references()`.

**`contracts/schema/`** — The schema classes:
- `TableSchema`: base Frictionless-compatible schema with `fields`, `primaryKey`, `foreignKeys`, and optional `fieldDescriptors`. Supports `__getitem__` (by index or name) and provides conversion helpers: `to_pandera_schema()`, `to_pydantic_model()`, `to_sa_table()`, `validate_dataframe()`.
- Discriminated union via `table_type`: `TableSchema` ("General") | `DimensionSchema` ("Dimension") | `ValueVariableSchema` ("ValueVariable") | `FlexibleDimensionSchema` ("FlexibleDimension").
- `BaseDimensionSchema` (abstract): enforces self-only foreign keys and a required primary key. Subclassed by `DimensionSchema` and `FlexibleDimensionSchema`.
- `DimensionSchema`: rigid template (id, level, parent_id, label, description). Rejects any user-provided fields.
- `FlexibleDimensionSchema`: user-defined fields, but mandates `label` and `description` fields.
- `_mandatory_fields` class variable: list of `MandatoryField` specs validated at schema construction time.
- Vendored copies of the upstream Frictionless JSON Schemas (`table-schema.json`, `data-resource.json`, `data-package.json`, `tabular-data-resource.json`) live in `.ai-context/additional_info/` — the authoritative reference for what fields, types, and constraints the schema layer must stay compatible with. Reference only; no code loads them at runtime. The `_standards/frictionless/` package (below) is a faithful pydantic mirror of these.

**`contracts/schema/adapters/`** — Converts `TableSchema` to external formats:
- `PanderaPandasAdapter`: builds a `pandera.DataFrameSchema` with primary-key uniqueness and foreign-key checks.
- `PydanticAdapter`: generates a dynamic Pydantic model class.
- `SQLAlchemyPostgresAdapter`: generates SQLAlchemy `Table` columns.
- `_pandera_dimension_checks.py`: custom Pandera checks enforcing dimension hierarchy invariants (level 0 = no parent, level N > 0 = parent at N-1, required "other" sentinel entries).

**`contracts/schema/fields/`** — Field types (`IntegerField`, `NumberField`, `StringField`, `DateTimeField`, `ListField`), all discriminated by `type`. Each carries a typed `constraints` submodel (e.g. `min`/`max` for numbers, `pattern`/`maxLength` for strings).

### `_standards/frictionless/` — Faithful, permissive Frictionless models (internal)

A pydantic mirror of the upstream Frictionless standard, distinct from the stricter `contracts/` layer: every model is `extra="allow"` and carries no CROSS domain logic, so the standard's extensibility rides through losslessly. Internal — not re-exported from the top-level package; sibling modules import from `crosscontract._standards.frictionless`.

- `fields.py` — permissive field models (`StringField`, `IntegerField`, … discriminated by `type`) with typed `constraints` submodels.
- `table_schema.py` — the permissive `TableSchema` (`fields`, `primaryKey`, `foreignKeys`, `missingValues`). Shares its bare name with the strict contract `TableSchema`; disambiguate by module.
- `metadata.py` — reusable metadata building blocks composed by the descriptors: `BaseMetaData` (fields identical in both descriptors), `ResourceMetaData` / `PackageMetaData` (descriptive parts), `FileMetaData` (the physical data binding), plus the permissive leaf models `Source`, `License`, `Contributor`. Also defines `FRICTIONLESS_NAME_PATTERN` (the resource/package `name` pattern, which permits `/`).
- `descriptors.py` — thin compositions: `DataResource(ResourceMetaData, FileMetaData)` and `DataPackage(PackageMetaData)` (adds the required `resources` array). The Frictionless `schema` key maps to a `table_schema` field (via `alias`) to avoid shadowing `BaseModel.schema`.

### `crossclient/` — HTTP client for the CROSS platform

- `CrossClient`: synchronous `httpx.Client` wrapper. Authenticates on construction (JWT Bearer token), re-authenticates automatically on 401. Exposes `client.contracts` as a `ContractService`. Use as a context manager or call `close()` explicitly.
- `ContractService`: CRUD operations on contracts (`create`, `get`, `get_list`, `delete`, `change_status`). Also manages data upload (`_add_data`) and retrieval (`_get_data` — uses parquet format).
- `ContractResource`: per-contract handle returned by the service. Wraps the `CrossContract` instance and `status`. Exposes `add_data(df)` (validates against schema before upload) and `get_data()`.

### `registry/` — High-level data access layer

- `CrossRegistry`: wraps a `CrossClient`. Lazy-loads variables by name via `add_variable()` / `get_variable()`. Supports attribute access (`registry.my_variable`) and item access (`registry["my_variable"]`). Automatically resolves foreign key relationships by fetching referenced dimension contracts.
- `CrossDataVariable`: holds a fetched `ContractResource` and its resolved `CrossDimension` objects. Main entry point is `get_data()`, which supports filtering, dimension aggregation (by level, target ID list, or custom mapping), title relabeling (`use_titles=True`), and column selection.
- `CrossDimension`: dimension-specific variable. Exposes `label_map`, `ancestor_maps` (precomputed per-level), and `get_ancestor_map_by_ids()` for aggregation.

### `release/data_package/` — Contract → Frictionless Data Package adapter

A stateless adapter that turns CROSS contracts into a Frictionless Data Package (a zip on disk). It assembles the permissive `_standards.frictionless` `DataResource` / `DataPackage` models directly — there are no bespoke descriptor classes (see ADR 0003).

- `release_specification.py` — the build-recipe spec models: `CrossDataResourceReleaseSpec` (per-resource descriptive overrides + a `DataInstructions` wrapping the `FetchSpecMixin`; `name` defaults to the fetch contract) and `CrossDataPackageReleaseSpec` (authored package metadata + `resources`, with a unique-resource-name validator).
- `create_data_package.py` — `create_data_package(registry, release_spec, fn_out)`: the slim orchestrator. Loads the spec from a YAML/JSON path (or accepts an instance), then delegates.
- `_resolve_resource.py` — `fetch_data` (fetch via the registry's trusted path), `build_data_resource` (overlay contract metadata with the spec field-by-field, embed the contract `schema`, derive `path`/`profile` from `format`), and `resolve_resources` (the per-resource loop: empty data is warned-and-skipped; an all-empty release raises).
- `_resolve_package.py` — `save_data_package`: writes each resource's data file plus `datapackage.json` and `datapackage.yaml` into the output zip.

### `submission/` — Submission contracts and extraction instructions

The ingress mirror of `release/`, and top-level for the same reason: it owns its spec models *and* (later) the code that executes them, so the concept lives in one package. `release/` turns contracts into a published data package; `submission/` describes a delivered bundle — one wide file carrying many variables — and how it is split back into per-variable contracts.

- `submission_contract.py` — `SubmissionContract`: a contract whose `tableschema` describes the bundle itself, plus `project_name` and (once WP2 lands) an `extraction` block.
- `extraction/` — the declarative split instructions: `Target` (which rows go to which target contract, and the transformations applied on the way) and `ExtractionInstructions` (the routing column, the reusable transformation profiles, and the targets).

`SubmissionContract` lives here rather than in `contracts/` deliberately: that it *is* a contract is expressed by inheritance, not by file location, and `contracts/` describes what a dataset looks like while extraction is a process. Keeping it out of `contracts/` also keeps the import graph one-way — `transformations/fetch/fetch_spec.py` already imports `CONTRACT_NAME_PATTERN` out of `contracts`, so extraction living under `contracts/` and importing `transformations` would close a cycle.

### `_helpers/` — Internal, dependency-free helpers

Not re-exported from the top-level package. `_pydantic.py` holds reusable pydantic types (`OptionalNonEmptyList`, which collapses `[]`→`None` for Frictionless `minItems: 1` optional arrays); `_io.py` holds `read_yaml_or_json_file` and `dump_to_file`.

### Key design patterns

- **Discriminated unions**: `contract_type` on `CrossContract` selects the schema's `table_type` via the `CONTRACT_TYPE_TO_TABLE_TYPE` table in `contracts/contracts/cross_contract.py`. The mapping is **not** the identity: `Submission` resolves to the `General` table type, because a submission bundle needs its own contract type but not its own schema. The two vocabularies are deliberately separate so several contract types can share one schema — never assume the two strings are equal, and never add an empty schema class just to give a contract type a discriminator target. The `_inject_table_type` validator bridges them automatically.
- **Adapters are stateless class methods**: call `Adapter.convert_schema(schema, ...)` directly; the adapter pattern exists for extensibility but doesn't require instantiation in practice.
- **Two `name` patterns, deliberately distinct**: `CONTRACT_NAME_PATTERN` (in `contracts/contracts/base_contract.py`) is the strict contract/field identifier — no `/`; `FRICTIONLESS_NAME_PATTERN` (in `_standards/frictionless/metadata.py`) is the looser standard resource/package identifier that permits `/`. The contract pattern is a subset, so any contract name is also a valid Frictionless name.
- **Tests live in `src/tests/`**, mirroring the `src/crosscontract/` structure. `pythonpath = "src"` in `pyproject.toml` means imports use `from crosscontract import ...` without editable install, though the package should be installed via `uv sync`.

## Docstring convention

All Python docstrings in this package use **Google style** (rendered by mkdocs via mkdocstrings). **Markdown formatting only** — single-backtick `code`, dashes for bullet lists, and **no reStructuredText syntax of any kind**: no ``double-backtick literals``, no `:param:` / `:returns:` / `:raises:` field markers, no `:attr:` / `:class:` / `:meth:` / `:func:` roles, no rST directives.

**Every docstring** carries `Args:`, `Returns:`, and `Raises:` sections — each when applicable (e.g. no `Returns:` on `__init__`, no `Args:` on a no-argument method) — with parameter types in parentheses, e.g. `value (str | None): ...`.

Standard sections (omit any that don't apply):

```python
def f(x: int, y: str | None = None) -> bool:
    """One-line summary in the imperative.

    Optional longer description in plain prose. Reference symbols with
    backticks, e.g. `PlotSpec`, `value_column`, `pd.DataFrame`.

    Args:
        x (int): What it is.
        y (str | None, optional): What it is. Defaults to `None`.

    Returns:
        bool: What comes back.

    Raises:
        ValueError: When and why.
    """
```

Rules of thumb:

- Docstrings are user-facing. Do **not** reference internal notes (ADRs, issue numbers, task numbers, migration cycles) — those belong in commit messages, PRs, or `.ai-context/`.
- For Pydantic field descriptions, use the `Field(description=...)` argument with the same markdown conventions; no Args block on the field itself.
- For `@model_validator` / `@model_serializer` methods, document the invariant they enforce in the summary, plus `Returns:` (typically `Self`) and `Raises:` where applicable.
- Properties: document via `Returns:` rather than restating the property name.
