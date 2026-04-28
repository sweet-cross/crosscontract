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

## Branching and releases

- `main` is the public release branch. Pushes to main publish to PyPI (gated by the `pypi` GitHub Environment) and deploy the docs.
- `dev` is the integration branch and the default branch on GitHub. Versioning happens here: every push to dev runs `python-semantic-release`, which bumps the version and creates a `vX.Y.Z` tag based on conventional-commit messages.
- Feature branches **squash-merge** into `dev`. The PR title must be a valid conventional commit (`feat:`, `fix:`, etc.) — it becomes the squash commit message that PSR analyzes. Hotfixes follow the same path.
- `dev` **fast-forwards** into `main`. The version commits and tags created on dev carry over to main as-is. No version bumps happen on the dev → main promotion.

## Architecture

The package has three independent top-level modules, all re-exported from `crosscontract/__init__.py`:

### `contracts/` — Schema and contract definitions

**`contracts/contracts/`** — The contract classes:
- `BaseContract` (Pydantic model): minimal contract with `name` + `tableschema`. Intended for custom contract definitions outside the CROSS platform. Loads from YAML/JSON via `from_file()`.
- `CrossContract(BaseContract, CrossMetaData)`: the full contract for the CROSS platform, adding `title`, `description`, `tags`, and `contract_type`. The `contract_type` field (`"General"` | `"Dimension"` | `"ValueVariable"` | `"FlexibleDimension"`) drives a discriminated union: it is automatically injected as `table_type` into the `tableschema` dict before validation, so callers never set `table_type` manually.
- `CrossContract.from_server()` / `to_server()`: strip/restore the `tableschema` for `Dimension` contracts because the server owns that schema.
- `ContractResolver` protocol: used to look up contracts by name during `validate_references()`.

**`contracts/schema/`** — The schema classes:
- `TableSchema`: base Frictionless-compatible schema with `fields`, `primaryKey`, `foreignKeys`, and optional `fieldDescriptors`. Supports `__getitem__` (by index or name) and provides conversion helpers: `to_pandera_schema()`, `to_pydantic_model()`, `to_sa_table()`, `validate_dataframe()`.
- Discriminated union via `table_type`: `TableSchema` ("General") | `DimensionSchema` ("Dimension") | `ValueVariableSchema` ("ValueVariable") | `FlexibleDimensionSchema` ("FlexibleDimension").
- `BaseDimensionSchema` (abstract): enforces self-only foreign keys and a required primary key. Subclassed by `DimensionSchema` and `FlexibleDimensionSchema`.
- `DimensionSchema`: rigid template (id, level, parent_id, label, description). Rejects any user-provided fields.
- `FlexibleDimensionSchema`: user-defined fields, but mandates `label` and `description` fields.
- `_mandatory_fields` class variable: list of `MandatoryField` specs validated at schema construction time.

**`contracts/schema/adapters/`** — Converts `TableSchema` to external formats:
- `PanderaPandasAdapter`: builds a `pandera.DataFrameSchema` with primary-key uniqueness and foreign-key checks.
- `PydanticAdapter`: generates a dynamic Pydantic model class.
- `SQLAlchemyPostgresAdapter`: generates SQLAlchemy `Table` columns.
- `_pandera_dimension_checks.py`: custom Pandera checks enforcing dimension hierarchy invariants (level 0 = no parent, level N > 0 = parent at N-1, required "other" sentinel entries).

**`contracts/schema/fields/`** — Field types (`IntegerField`, `NumberField`, `StringField`, `DateTimeField`, `ListField`), all discriminated by `type`. Each carries a typed `constraints` submodel (e.g. `min`/`max` for numbers, `pattern`/`maxLength` for strings).

### `crossclient/` — HTTP client for the CROSS platform

- `CrossClient`: synchronous `httpx.Client` wrapper. Authenticates on construction (JWT Bearer token), re-authenticates automatically on 401. Exposes `client.contracts` as a `ContractService`. Use as a context manager or call `close()` explicitly.
- `ContractService`: CRUD operations on contracts (`create`, `get`, `get_list`, `delete`, `change_status`). Also manages data upload (`_add_data`) and retrieval (`_get_data` — uses parquet format).
- `ContractResource`: per-contract handle returned by the service. Wraps the `CrossContract` instance and `status`. Exposes `add_data(df)` (validates against schema before upload) and `get_data()`.

### `registry/` — High-level data access layer

- `CrossRegistry`: wraps a `CrossClient`. Lazy-loads variables by name via `add_variable()` / `get_variable()`. Supports attribute access (`registry.my_variable`) and item access (`registry["my_variable"]`). Automatically resolves foreign key relationships by fetching referenced dimension contracts.
- `CrossDataVariable`: holds a fetched `ContractResource` and its resolved `CrossDimension` objects. Main entry point is `get_data()`, which supports filtering, dimension aggregation (by level, target ID list, or custom mapping), title relabeling (`use_titles=True`), and column selection.
- `CrossDimension`: dimension-specific variable. Exposes `label_map`, `ancestor_maps` (precomputed per-level), and `get_ancestor_map_by_ids()` for aggregation.

### Key design patterns

- **Discriminated unions**: `contract_type` on `CrossContract` maps 1:1 to `table_type` on the schema. The `_inject_table_type` validator bridges them automatically.
- **Adapters are stateless class methods**: call `Adapter.convert_schema(schema, ...)` directly; the adapter pattern exists for extensibility but doesn't require instantiation in practice.
- **Tests live in `src/tests/`**, mirroring the `src/crosscontract/` structure. `pythonpath = "src"` in `pyproject.toml` means imports use `from crosscontract import ...` without editable install, though the package should be installed via `uv sync`.
